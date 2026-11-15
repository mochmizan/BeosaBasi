# eval/

Benchmark harness, scoring scripts, and frozen manifests.

Audio and reference transcripts **never enter git**. Only scripts, the spelling
map, and SHA-256 manifests are committed.

## Layout

```
eval/
  README.md
  pyproject.toml          ruff + pytest config (borrows the worker venv)
  mapping/
    id-v1.json            frozen spelling-variant map (PRD 3.4.3)
    id-v1.sha256          hash written by freeze_set.py
    README.md             freeze policy
  manifests/              <set-version>.sha256 + <set-version>.json (committed)
  scripts/
    eval_common.py        normalization, WER, repeats, timestamps, hashing
    score_wer.py          strict/loose WER + all QA gates (TK-012)
    score_quality.py      hallucination/repeat/timestamp + threshold sweep (TK-014)
    score_der.py          DER + speaker-count accuracy (TK-053)
    freeze_set.py         validate + hash a test set (TK-011)
  tests/                  pytest for the scripts above
  results/                per-run JSON/Markdown reports
  data/                   GIT-IGNORED: audio, refs, consent forms (TK-011)
```

## Test-set schema

`eval/data/<set-version>/meta.json`:

```json
{
  "version": "id-v1",
  "expected": {"wawancara": 12, "rapat": 12, "pesan-suara": 12,
               "berderau": 12, "campur-id-en": 12, "hening": 20},
  "clips": [
    {"id": "wawancara-01", "category": "wawancara",
     "duration_seconds": 60, "speakers": 2}
  ]
}
```

Categories: `wawancara`, `rapat`, `pesan-suara`, `berderau`, `campur-id-en`,
and `hening` (or `derau-murni`) for the 20 silence/noise clips.

For each clip id, the reference lives in `refs/<id>.txt` (plain text). An
optional `refs/<id>.json` with `{"segments": [{"start": 0.0, "end": 2.1,
"text": "..."}]}` supplies timings for the ±1 s worksheet. Audio lives in
`audio/<id>.<ext>`; the extension is not hashed differently, every file in the
folder is hashed.

`consent/index.json` records written consent (never committed):

```json
{"speakers": [
  {"id": "spk-01", "name": "Nama", "form": "consent/spk-01.pdf",
   "signed_at": "2026-11-01", "clip_ids": ["wawancara-01"]}
]}
```

The consent form template is `docs/privasi/formulir-persetujuan.md`.

## Benchmark output schema

`worker bench` writes one JSON per clip plus `summary.json`:

```
eval/results/<config-slug>/
  summary.json
  <clip>.json     segments: [{index, start, end, text, avg_logprob, no_speech_prob}]
```

`--repeat N` stores every run; the summary reports median and worst xRT, peak
VRAM, and peak GPU temperature.

## Commands

Smoke test without a GPU (silent WAVs, sample transcripts):

```bash
cd apps/worker
uv run worker make-sample --out /tmp/contoh.wav
uv run worker bench /tmp --fake --out ../eval/results
```

Real benchmark and scoring (after TK-011 data exists):

```bash
cd apps/worker
uv run worker bench ../eval/data/id-v1/audio --repeat 3 \
  --out ../eval/results/id-v1

cd ../..
python eval/scripts/freeze_set.py --set eval/data/id-v1 --strict-consent
python eval/scripts/score_wer.py \
  --results eval/results/id-v1/large-v3-turbo-int8-float16-beam5-batch8-vad \
  --set eval/data/id-v1 --require-frozen --report
python eval/scripts/score_quality.py \
  --results eval/results/id-v1/large-v3-turbo-int8-float16-beam5-batch8-vad \
  --set eval/data/id-v1 --calibrate
```

`score_wer.py` writes `report.json`, `report.md`, and `timestamps.json` into
the run folder. Fill `manual_start` in `timestamps.json` (100 sampled
segments), then re-run with `--timestamps <file>` to score the ±1 s gate.

Diarization (after TK-050/TK-053 RTTMs exist):

```bash
python eval/scripts/score_der.py \
  --ref eval/data/spk-v1/ref-rttm \
  --hyp eval/results/spk-v1/community-1/rttm --report
```

`--engine auto` uses `pyannote.metrics` when installed and the frame-based
fallback otherwise. Collar defaults to 0.25 s.

## Gates (PRD 3.4.4 / 3.4.9)

| Metric | Threshold |
|---|---|
| Loose WER overall (K1) | ≤ 15% |
| Loose WER per category | reported; > 30% recorded as a limitation |
| Silence clips ≤ 2 words | ≥ 95% of 20 |
| n-gram repeated > 5 times | 0 transcripts |
| Timestamps within ±1 s | ≥ 95% of 100 sampled segments |
| DER, collar 0.25 s (K6) | ≤ 25% |
| Speaker count | ≥ 75% exact, ≥ 90% within ±1 |

`score_wer.py` exits non-zero when a gate fails, so CI can use it directly.

## Freeze policy

`freeze_set.py` validates counts and consent, then writes
`eval/manifests/<version>.sha256` (hashes of `meta.json`, `refs/`, `audio/`)
and `eval/mapping/<version>.sha256`. `score_wer.py --require-frozen` refuses to
score when either hash is missing or changed. A changed set gets a new version
(`id-v2`), never a silent edit of `id-v1`.

## Data rules

- Never commit audio, reference transcripts, consent forms, or benchmark output
  containing user text. `eval/data/` and all audio extensions are git-ignored.
- Production user audio is never used as test data without separate consent.
- The model is never trained on user audio.
- Manifests contain hashes and counts only.
