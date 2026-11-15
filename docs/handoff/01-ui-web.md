# 01 — UI / Web (no login)

Scope: record OR upload → status → transcript + speaker names → export. Anonymous. Indonesian messages.

## Status — UI merged (mockup → apps/web)

The full studio UI from the design mockup now lives in `apps/web` and is wired to
the contract client:

- Shell: sidebar (macaw logo, BEOSABASI, quota, recent jobs), topbar (search,
  theme, worker chip), blue hill/grain scene with birds + red flowers, command
  palette (`Ctrl/⌘ K`), toast, privacy modal.
- Pages: `/` studio (uploader + transcript), `/jobs` library, `/jobs/:id` detail,
  `/insights`, `/settings`, 404.
- Wired endpoints: `GET /api/me`, `GET /api/jobs` (8 s poll), `GET /api/jobs/{id}`
  (4 s poll while queued/processing), `GET /transcript`, `GET /audio-url`,
  `PATCH /segments/{n}`, `PATCH /speakers/{sid}`, `GET /export`, `DELETE /jobs/{id}`,
  `POST/DELETE /api/consents`, and the multipart upload flow
  (`POST /api/uploads` → `POST /parts` → `PUT` → `POST /complete`).
- Dev: Prism validates the `beosabasi_session` cookie; `main.tsx` sets a dev-only
  cookie so `npm run mock:api` works without Google login.
- Dev: `agentation` toolbar is mounted in `Layout.tsx` only when
  `import.meta.env.DEV` (tree-shaken from production builds).

Still open for TK-042/044/045: real Turnstile token, 3× parallel 8 MiB chunks +
`ListParts` resume, debounced autosave (currently saves on blur/Enter), R2 CORS
must expose `ETag`, and `MediaRecorder` capture.

## Tasks in order
1. `TK-040` — DONE (scaffold + typed client + mock:api). Don't redo.
2. `TK-042` — record/upload + quota. `MediaRecorder` + file picker, 8MiB chunks x3 parallel, `ListParts` resume, Turnstile stub. Files: `apps/web/src/pages/HomePage.tsx`, `apps/web/src/components/Uploader.tsx`, `apps/web/src/api/`.
3. `TK-043` — jobs list + status. Poll 5s, queued/processing/completed/failed, worker-offline notice. Files: `apps/web/src/pages/JobsPage.tsx`, `apps/web/src/pages/JobDetailPage.tsx`.
4. `TK-044` — editor synced. Click segment seeks audio ±1s, low-confidence highlight, autosave ≤5s, rename/move speaker. Then `TK-045` export + delete. Files: `apps/web/src/components/Transcript.tsx`, `apps/web/src/lib/useJobTranscript.ts`.

## Mock / verify
```
npm run mock:api   # Prism :4010 from contracts/openapi.yaml
npm run dev        # :5173 vs mock
npm test -- --run && npm run lint && npm run build
```

## Rules
- API base from `VITE_API_BASE_URL` (`:4010` dev, `https://api.<domain>` prod). No hardcoded URLs.
- Contract change → `make gen-client`, tick `docs/CHECKLIST.md` in same PR.

