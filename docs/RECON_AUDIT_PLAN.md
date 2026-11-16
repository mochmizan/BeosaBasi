# BeosaBasi — Full Recon, Audit, Implementation Plan & Verification Report

## 1. Recon & Audit Findings (Critical Bugs & Gaps Discovered)

1. **Broken Multipart Upload Routing (`apps/web/src/components/Layout.tsx`)**:
   - **Root Cause**: `Layout.tsx` passed `session.upload_id` (the S3/Garage internal multipart ID) to `api.signPart(...)` and `api.completeUpload(...)`, whereas `apps/api/src/api/uploads.py` routes `POST /api/uploads/{job_id}/parts`, `GET /api/uploads/{job_id}`, and `POST /api/uploads/{job_id}/complete` by **`session.job_id`**.
   - **Impact**: Every browser upload against the real FastAPI backend failed with `404 Not Found ("Pekerjaan tidak ditemukan")`.
2. **0-Indexed `part_number` Mismatch (`apps/web/src/components/Layout.tsx`)**:
   - **Root Cause**: `Layout.tsx` iterated `for (let i = 0; i < session.part_count; i += 1)` and sent `part_number: 0`. Both `contracts/openapi.yaml` (`minimum: 1`) and `uploads.py` (`1 <= body.part_number <= part_count`) require 1-indexed part numbers.
   - **Impact**: Immediate `400 INVALID_FILE ("Nomor potongan di luar rentang")` on part 0.
3. **Dead Consent Gate Blocking All Uploads (`Layout.tsx`, `Uploader.tsx`, `PrivacyConsent.tsx`)**:
   - **Root Cause**: Per `docs/ADR/0001-anonymous-identity.md` (`TK-021`, `TK-022`, `TK-041`, `TK-060` cut), `/api/consents` is not mounted on the backend and `GET /api/me` always returns `consent: null`. However, `Layout.tsx` blocked `startUpload` when `me.consent === null`, opened `PrivacyConsent.tsx`, and called `POST /api/consents` (which returned `404`).
   - **Impact**: Users were permanently blocked from uploading in the web UI.
4. **Cross-Origin Quick-Tunnel Cookie Loss (`identity.py`, `client.ts`)**:
   - **Root Cause**: Because `trycloudflare.com` is on the Public Suffix List, `https://<web>.trycloudflare.com` and `https://<api>.trycloudflare.com` are cross-site. Modern browsers and mobile Safari ITP drop `SameSite=Lax` cookies on cross-site `fetch()` requests, creating a new anonymous user on every API call.
   - **Fix**: Added `X-Session-Token` response/request header fallback (persisted in `localStorage` and exposed via CORS) alongside the `beosabasi_session` HttpOnly cookie.
5. **Browser `MediaRecorder` WebM/Opus Rejection in API & Worker (`api/config.py`, `api/uploads.py`, `worker/media.py`)**:
   - **Root Cause**: Browser `MediaRecorder` emits `audio/webm;codecs=opus` (missing from `ALLOWED_CONTENT_TYPES` and rejected due to the `;codecs=opus` parameter) and produces streaming WebM containers whose `ffprobe` header duration is `"N/A"`, causing `worker/media.py` `probe()` to fail with `CORRUPT_MEDIA ("durasi tak terbaca")`.
   - **Fix**: Added `audio/webm` and `audio/aac` to `ALLOWED_CONTENT_TYPES`, stripped `;codecs=...` parameters in `uploads.py`, and updated `worker/media.py` `normalize()` to fall back to measuring the decoded 16 kHz mono WAV frame duration when container duration is `"N/A"`.
6. **Stale `BEOSABASI_CORS_ORIGINS` After Tunnel Refresh (`infra/vps-refresh.sh`)**:
   - **Root Cause**: `vps-refresh.sh` recreated `api` before starting the `web` tunnel and never updated `BEOSABASI_CORS_ORIGINS` in `/opt/beosabasi/.env` when the `web` quick tunnel rotated.
   - **Fix**: Updated `infra/vps-refresh.sh` to start the `s3` and `web` tunnels first, write both `S3_ENDPOINT` and `BEOSABASI_CORS_ORIGINS` into `.env`, and force-recreate `api`.

## 2. Web Studio & Mobile Flesh-Out Summary (`TK-042`–`TK-046`)

- **Zero Account / Login / Policy UI**: Removed all profile/avatar cards, allowlist/invitation copy, notification bell, consent checkboxes, and deleted `PrivacyConsent.tsx`.
- **In-Browser Web Audio Recorder (`Uploader.tsx`)**: Added a segmented `Rekam suara` / `Unggah berkas` switcher, `MediaRecorder` capture with live Web Audio API analyser waveform bars, pause/resume/stop controls, editable recording title, audio preview player, local backup download, and one-tap transcription upload.
- **3× Parallel Resumable Upload (`client.ts`, `Layout.tsx`)**: Implemented `uploadFileMultipart` with 3 concurrent 8 MiB chunk workers, 1-indexed part numbers, `session.job_id` routing, pre-upload `<audio>` duration probing (90-minute cap), and `ListParts` (`GET /api/uploads/{id}`) resume on network drop.
- **Synced Editor & Debounced Autosave (`Transcript.tsx`, `useJobTranscript.ts`)**: Added 2-second debounced autosave while typing, live save status indicator, playback speed selector (`0.75×–2×`), `-5s/+5s` skip buttons, inline transcript search, speaker filter, low-confidence (`<85%`) filter, and inline delete confirmation.
- **Real Usage Insights, Persistent Settings & Mobile Bottom Nav**: Connected `InsightsPage.tsx` to real 7-day job data, wired `SettingsPage.tsx` preferences to `localStorage`, and added a 5-tab mobile bottom navigation bar (`Studio`, `Rekam`, `Pustaka`, `Kuota`, `Setelan`) for viewports `<= 760px`.

## 3. Verification Results

- **Python AST Syntax Check**: 72/72 files clean.
- **OpenAPI Contract & Client Codegen (`scripts/gen_client.py`)**: 25 operations, 34 schemas generated cleanly across TypeScript and Pydantic.
- **Backend API Test Suite (`apps/api/tests`)**: 77/77 test cases passing (including new tests for `audio/webm;codecs=opus` and `X-Session-Token` fallback).
- **Worker Test Suite (`apps/worker/tests`)**: 36/36 test cases passing (including new test for streaming WebM `N/A` duration fallback).
- **Eval Test Suite (`eval/tests`)**: 34/34 test cases passing.
- **Web Component & Import Audit**: 30/30 TypeScript/TSX modules verified with zero unresolved imports and zero account/consent remnants.
