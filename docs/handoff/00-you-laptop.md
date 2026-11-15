# 00 — You (owner + laptop model host)

Scope: model stays on your RTX 4050 laptop. VPS only API/queue. No login anywhere.

## Do now
1. `TK-005` laptop doctor — drivers/CUDA/cuDNN, `worker doctor` green. Lock versions in `apps/worker/requirements.lock`. Runbook: `docs/runbook/worker-windows.md`.
2. `TK-050` diarization spike — `pyannote` community-1 vs WSL2 call. Record VRAM peak + time for 2-4 speaker clips. Write ADR in `docs/ADR/`.
3. `TK-010` bench harness — `worker bench <folder>` JSON: duration, xRT, VRAM peak, temp, segments, versions. 3x repeat on 60-min file.

## Verify
```
cd apps/worker
uv run worker doctor
uv run worker bench eval/sample --repeat 3
```

## Done when
- `doctor` all-pass, versions locked
- xRT + VRAM numbers posted → feeds `TK-013` gate + `TK-032` params
- No secrets in repo, HF token in env only
