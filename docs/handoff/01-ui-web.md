# 01 — UI / Web (no login)

Scope: record OR upload → status → transcript + speaker names → export. Anonymous. Indonesian messages.

## Tasks in order
1. `TK-040` — DONE (scaffold + typed client + mock:api). Don't redo.
2. `TK-042` — record/upload + quota. `MediaRecorder` + file picker, 8MiB chunks x3 parallel, `ListParts` resume, Turnstile stub. Files: `apps/web/src/pages/UploadPage.tsx`, `apps/web/src/api/`.
3. `TK-043` — jobs list + status. Poll 5s, queued/processing/completed/failed, worker-offline notice. Files: `apps/web/src/pages/JobsPage.tsx`.
4. `TK-044` — editor synced. Click segment seeks audio ±1s, low-confidence highlight, autosave ≤5s, rename/move speaker. Then `TK-045` export + delete.

## Mock / verify
```
npm run mock:api   # Prism :4010 from contracts/openapi.yaml
npm run dev        # :5173 vs mock
npm test -- --run && npm run lint && npm run build
```

## Rules
- API base from `VITE_API_BASE_URL` (`:4010` dev, `https://api.<domain>` prod). No hardcoded URLs.
- Contract change → `make gen-client`, tick `docs/CHECKLIST.md` in same PR.
