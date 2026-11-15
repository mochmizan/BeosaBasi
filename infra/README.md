# infra/

Deployment and provider configuration (details in TK-003/TK-004).

- `cloudflare/` — R2 CORS + lifecycle JSON stubs, Pages notes.
- `caddy/` — Caddy reverse-proxy config stub (TK-004).
- `compose.local.yaml` — stack dev lokal (TK-002): API anonim nyata + endpoint seed
  fake demo + Garage (S3 lokal). Lihat `docs/runbook/local-dev.md`.
- `garage.toml` — konfigurasi Garage satu-node, kredensial DEV saja.

No credentials in this directory, ever.
