# 01 — UI / Web (no login, anonymous-first)

Scope: record OR upload → status → transcript + speaker names → export. Anonymous. Indonesian messages.

## Status — Fully Fleshed Out (`TK-040`, `TK-042`, `TK-043`, `TK-044`, `TK-045`, `TK-046` DONE)

The full anonymous-first studio UI in `apps/web` is wired to the real backend contract:

- **Zero Account / Policy Remnants**: No login, no profile/avatar cards, no allowlist/invitation text, and no blocking consent modal or policy pages (`PrivacyConsent.tsx` removed). Session identity uses the `beosabasi_session` HttpOnly cookie with an automatic `X-Session-Token` header fallback (`localStorage`) so cross-origin Cloudflare quick tunnels and mobile browsers preserve job ownership.
- **Dual Input Studio (`Uploader.tsx`)**:
  - **Web Audio Recorder (`Rekam suara`)**: Direct in-browser microphone recording via `MediaRecorder` + live Web Audio API frequency analyser waveform, pause/resume/stop controls, editable recording title, audio preview player, local audio download, and one-click transcription submission without manual file upload.
  - **Resumable Multipart Uploader (`Unggah berkas`)**: 3× parallel 8 MiB chunk uploads (`uploadFileMultipart`), `1..part_count` indexing via `session.job_id`, pre-upload `<audio>` duration probing (90-minute cap & quota hint), and `ListParts` (`GET /api/uploads/{id}`) resume button on network interruption.
- **Honest Queue & Worker Status (`TK-043`)**: Polls `GET /api/jobs` (5 s), `GET /api/jobs/{id}` (3–4 s while active), and `GET /healthz` (`worker_active` boolean). Displays live `queue_position`, `eta_seconds`, and an explicit `"Pemrosesan tertunda (pekerja offline)"` notice whenever the laptop GPU worker has not pinged within 90 s.
- **Synced Transcript Editor (`TK-044`, `TK-046`)**:
  - Click any segment or timestamp to seek audio (`±0.1 s`), with `-5 s / +5 s` skip buttons and playback speed selector (`0.75×` to `2×`).
  - Debounced autosave (`≤ 2 s` while typing, plus immediate save on `Blur`/`Enter`) with live save status indicator (`Menyimpan…` / `Tersimpan otomatis`) and `409 VERSION_CONFLICT` recovery.
  - Inline transcript search bar, speaker filter dropdown, and low-confidence (`< 85%`) segment filter.
  - Speaker rename (`PATCH /speakers/{sid}`) and per-segment speaker reassignment (`PATCH /segments/{n}`).
- **Exports, Real Insights & Mobile View (`TK-045`)**:
  - Export `TXT`, `SRT`, `VTT`, `DOCX` with optional speaker-label toggle, plus inline confirmation for per-job deletion (`DELETE /api/jobs/{id}`) and local browser session reset (`DELETE /api/me`).
  - `InsightsPage.tsx` computes 7-day usage bars and language distribution directly from the user's real `jobs`.
  - Mobile-first bottom navigation bar (`Studio`, `Rekam`, `Pustaka`, `Kuota`, `Setelan`) for viewports `≤ 760px`.
