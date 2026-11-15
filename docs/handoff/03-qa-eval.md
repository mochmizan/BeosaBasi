# 03 - QA / Eval (sets + gates + privacy)

Scope: prove K1/K2/K4/K6 and keep the pilot honest. Mostly human work plus
scripts; no ticket below is complete until the real audio and real GPU numbers
exist.

## Status at a glance

| Ticket | What exists now | What is still missing |
|---|---|---|
| TK-010 | `worker bench` harness: per-clip JSON, summary, load time, xRT, VRAM/temp sampling, `--repeat`, `--fake` | Real GPU run on the benchmark laptop |
| TK-011 | `freeze_set.py` validation (counts, consent, audio), SHA-256 manifests | 60 recorded clips + 20 silence clips + signed consent forms |
| TK-012 | `score_wer.py`: strict/loose WER, per-category report, frozen-set check | Real transcripts and a frozen set to score |
| TK-013 | Config comparison supported by `worker bench` flags | Model decision recorded in PRD Lampiran A |
| TK-014 | `score_quality.py`: hallucination, repetition, timestamp sample, threshold sweep | 100 manually filled timestamps and a real calibration re-run |
| TK-053 | `score_der.py`: frame DER + optional pyannote, speaker-count accuracy | TK-050 diarization spike and 20 multi-speaker RTTM pairs |
| TK-060 | Privacy notice, ROPA, DPIA-lite, consent form, breach runbook, legal checklist | Legal verification (T-12), product name (T-14), contact email, R2/VPS locations |

`docs/CHECKLIST.md` is intentionally unchanged: nothing above meets its full
acceptance criteria yet.

## Task order

1. `TK-011` - collect 60 x 1 min clips (12 each: interview, meeting, WA voice,
   noisy, ID-EN) plus 20 silence/noise clips. Self-record, written consent, two
   editors, then freeze. No audio in git.
2. `TK-012` - WER pipeline. Strict score has no mapping; loose score applies
   `eval/mapping/id-v1.json` to reference and hypothesis. Freeze both before
   looking at results.
3. `TK-013` GATE - run turbo vs large-v3 int8; compare xRT, VRAM, load time;
   do capacity and quota math; record the decision in PRD Lampiran A. Feeds
   worker `TK-032`.
4. `TK-014` - hallucination, repetition, and timestamp calibration.
5. `TK-053` - 20 multi-speaker clips and DER, only after `TK-050` passes.
6. `TK-060/061/062/063` - privacy docs, STRIDE, e2e/load/failure drills, pilot
   readiness. `TK-060` needs T-12 and T-14 before publication.

## Commands

Run from the repository root unless noted. The eval scripts are stdlib-only
except for optional `jiwer`, so plain `python` is enough. The worker commands
use `uv`; on a machine without `uv`, use `apps/worker/.venv/Scripts/python.exe
-m worker.cli` (Windows) or the equivalent venv path.

### 1. Benchmark (TK-010/TK-013)

```bash
cd apps/worker
uv run worker bench ../../eval/data/id-v1/audio --repeat 3 \
  --out ../../eval/results/id-v1
```

Compare configurations by changing `--model`, `--compute-type`, `--beam-size`,
`--batch-size`, and `--no-vad`. Each configuration writes its own
`<config-slug>/` folder with `summary.json` plus one JSON per clip.

Harness smoke test without a GPU:

```bash
cd apps/worker
uv run worker bench ../../eval/data/id-v1/audio --fake --repeat 2 \
  --out ../../eval/results/smoke
```

`--fake` produces sample text, so its WER is meaningless; it only proves the
harness and report pipeline run.

### 2. Freeze the set (TK-011)

```bash
python eval/scripts/freeze_set.py --set eval/data/id-v1 --strict-consent
python eval/scripts/freeze_set.py --set eval/data/id-v1 --check
```

This validates category counts (5 x 12 speech + 20 silence/noise), consent
index entries, and the presence of audio, then writes:

- `eval/manifests/id-v1.sha256` (hashes of `meta.json`, `refs/`, `audio/`)
- `eval/manifests/id-v1.json` (counts, mapping version, timestamp)
- `eval/mapping/id-v1.sha256` (hash of the spelling map)

A frozen set is never silently re-frozen. Bump the set version when a change is
intentional, or pass `--force` and record why.

### 3. Score WER and quality (TK-012/TK-014)

```bash
python eval/scripts/score_wer.py \
  --results eval/results/id-v1/large-v3-turbo-int8-float16-beam5-batch8-vad \
  --set eval/data/id-v1 --require-frozen --report

python eval/scripts/score_quality.py \
  --results eval/results/id-v1/large-v3-turbo-int8-float16-beam5-batch8-vad \
  --set eval/data/id-v1 --calibrate --report
```

`score_wer.py` writes `report.json`, `report.md`, and `timestamps.json` into the
run folder. Fill `manual_start` for the 100 sampled segments, then re-run:

```bash
python eval/scripts/score_wer.py \
  --results <run-dir> --set eval/data/id-v1 --require-frozen \
  --timestamps <run-dir>/timestamps.json --report
```

Both scorers exit non-zero when a gate fails, so they can be used in CI.

### 4. Diarization (TK-053)

```bash
python eval/scripts/score_der.py \
  --ref eval/data/spk-v1/ref-rttm \
  --hyp eval/results/spk-v1/community-1/rttm \
  --engine auto --report
```

`--engine auto` uses `pyannote.metrics` when installed and a frame-based DER
with the same 0.25 s collar otherwise. Use `--engine frame` to force the
fallback while the pyannote stack is not available on Windows.

### 5. Test and lint

```bash
python scripts/test.py
python scripts/lint.py
```

Both include `eval/`. The eval scripts borrow the worker environment, so
`apps/worker` must be set up first.

## Gates

| Gate | Threshold | Enforced by |
|---|---|---|
| Loose WER overall (K1) | <= 15% | `score_wer.py` |
| Loose WER per category | reported; > 30% is a limitation | `score_wer.py` |
| Silence clips <= 2 words | >= 95% of 20 | `score_wer.py`, `score_quality.py` |
| Repeated n-gram > 5 times | 0 transcripts | `score_wer.py`, `score_quality.py` |
| Timestamps within +/-1 s | >= 95% of 100 sampled segments | `score_wer.py`, `score_quality.py` |
| DER, collar 0.25 s (K6) | <= 25% | `score_der.py` |
| Speaker count | >= 75% exact, >= 90% within +/-1 | `score_der.py` |

## Rules

- Voice data never enters git. `eval/data/` and all audio extensions are
  ignored; only scripts, the spelling map, and manifests are committed.
- Never train on user audio.
- The mapping list and test-set hashes are frozen before scoring. Changing
  either after seeing scores invalidates the result; use a new version.
- Production user audio is never test data without separate consent.
- Do not tick a ticket in `docs/CHECKLIST.md` from a fake run. `--fake` proves
  the harness, not the model.
- `score_quality.py --calibrate` is a post-hoc proxy over recorded segment
  statistics. Final calibration still re-runs the audio with the chosen VAD and
  decoding parameters.

## References

- `eval/README.md` - schemas, layout, freeze policy
- `eval/mapping/README.md` - mapping rules and version history
- `docs/PRD.md` 3.4.1-3.4.9, 4.11, 4.12
- `docs/privasi/README.md` - privacy document index and open items
- `docs/privasi/verifikasi-hukum.md` - T-12 checklist
- `docs/runbook/insiden-kebocoran.md` - breach and subject-rights procedure

