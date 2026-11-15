# 03 — QA / Eval (sets + gates + privacy)

Scope: prove K1/K2/K4/K6, keep pilot honest. Mostly human + scripts.

## Tasks in order
1. `TK-011` — 60x1min sets (12 each: interview, meeting, WA voice, noisy, ID-EN) + 20 silence/noise. Self-record, written consent, 2 editors, freeze hashes in `eval/`. No audio in git.
2. `TK-012` — WER pipe (`jiwer`), strict + loose + mapping list frozen before scoring.
3. `TK-013` GATE — run turbo vs large-v3 int8, xRT/VRAM/load-time, capacity + quota math, record decision in PRD Lampiran A. Feeds worker `TK-032`.
4. `TK-014` — hallucination/repeat/timestamp calibration. `TK-053` — 20 multi-speaker clips + DER. `TK-061/062/063` — STRIDE, e2e/load/failure drills, pilot readiness.
5. `TK-060` — privacy/ROPA/DPIA-lite draft (no login: anonymous + Turnstile + IP quota + 24h audio/30d transcript). Needs legal verify (T-12) before open pilot.

## Verify
```
worker bench <folder> --repeat 3
python eval/score_wer.py results/<ver>/ --report
```

## Rules
- Data voices never in git, never train on user audio.
- Mapping list + test hashes frozen — changing after seeing scores fails CI.
