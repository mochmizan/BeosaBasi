# 02 — Backend (VPS API + worker, no login)

Scope: anonymous API on VPS (FastAPI + SQLite WAL), worker pulls from laptop. No Google/OIDC/sessions — `TK-021/022/041` login scope is cut.

## Tasks in order
1. `TK-023` — anonymous multipart to R2 (local Garage now). `POST /api/uploads`, `POST /parts`, `GET /uploads/{id}`, `POST /complete`. 200MB/90min reject pre-start, 8MiB parts, `ExposeHeaders: ETag`, light check ≤5s. Files: `apps/api/src/api/uploads.py`.
2. `TK-024` — job cycle + quota. `uploading>queued>processing>completed/failed/expired/cancelled`, queue pos + ETA, IP-based daily minutes (UTC+7), 72h expiry. Files: `apps/api/src/api/jobs.py`, `usage_ledger`.
3. `TK-025` — worker API. `POST /worker/v1/jobs/claim?wait=25`, heartbeat 30s + `cancel`, result/fail, 3 tries, lease sweeper, token hash. Test with `worker --fake`.
4. Then `TK-026/027/028/029`, worker `TK-030/031/032(temp)/033/034/035`.

## Verify
```
python scripts/dev_up.py
cd apps/worker && uv run worker demo
python scripts/lint.py && python scripts/test.py
```

## Rules
- Secrets in env only. R2 creds dev-only in `scripts/dev_up.py`.
- `TK-020` DB/DAL already done — reuse, don't rewrite schema.
- Tick `docs/CHECKLIST.md` per ticket in same PR.
