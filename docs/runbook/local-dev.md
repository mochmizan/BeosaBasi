# Pengembangan lokal (TK-002)

Tanpa akun Cloudflare, tanpa GPU, tanpa R2 asli. Stack lokal memakai API
dengan backend palsu dalam memori (`BEOSABASI_FAKE=1`) dan Garage sebagai
pengganti R2 yang kompatibel S3 (mendukung multipart upload seperti R2).

## Prasyarat

Docker Desktop (untuk `dev-up`), Python 3.12 + `uv`, Node 20 + npm.

## Alur 5 menit

```powershell
make dev-up
```

API sehat di `http://localhost:8000` (`/healthz` menjawab `{"status":"ok"}`).
Garage (S3 lokal) di `http://localhost:3900`, admin di `http://localhost:3903`.
Kredensial dev dicetak oleh `dev-up`: region `garage`, bucket `beosabasi-dev`.
Semua kredensial ini hanya untuk laptop dan tidak dipakai di produksi.

Jalankan satu job ujung ke ujung dengan pekerja palsu:

```powershell
cd apps/worker
uv run worker demo
```

`demo` membuat satu job lewat `POST /dev/jobs`, menyelesaikannya lewat
`claim → heartbeat → result`, lalu mencetak 2 segmen contoh. Tanpa GPU:
pekerja hanya tidur 3 detik sebagai pengganti inferensi.

Mode loop (2+ job, `--once` untuk satu job):

```powershell
uv run worker run --fake
uv run worker run --fake --once
```

Fixture audio hening 10 detik (dibuat saat dibutuhkan, tidak dikomit karena
`*.wav` diabaikan git):

```powershell
uv run worker make-sample --out contoh-hening-10s.wav
```

Hentikan stack:

```powershell
make dev-down
```

## Mock API untuk pengembangan web

Kontrak OpenAPI dipakai sebagai server tiruan agar `web` bisa jalan tanpa API:

```powershell
cd apps/web
npm run mock:api   # Prism di http://localhost:4010 dari contracts/openapi.yaml
```

Contoh respons buatan ada di `contracts/mock/fixtures.json`.

## Backend anonim (TK-023–TK-029)

Router nyata aktif bersamaan dengan backend palsu (`BEOSABASI_FAKE=1` hanya
menambah `/dev/jobs`). Identitas tanpa login dijelaskan di
`docs/ADR/0001-anonymous-identity.md`.

| Area | Endpoint | Catatan |
|---|---|---|
| Unggah | `POST /api/uploads`, `POST /api/uploads/{id}/parts`, `GET /api/uploads/{id}`, `POST /api/uploads/{id}/complete` | Potongan 8 MiB, URL bertanda tangan 15 menit, cek tanda tangan berkas ≤5 dtk |
| Job | `GET /api/jobs`, `GET /api/jobs/{id}`, `DELETE /api/jobs/{id}` | Posisi antrean + ETA, kuota 60 mnt/hari (UTC+7), 2 job aktif, kedaluwarsa 72 jam |
| Transkrip | `GET /api/jobs/{id}/transcript`, `PATCH .../segments/{n}`, `PATCH .../speakers/{sid}`, `GET .../audio-url` | `version` untuk deteksi tabrakan; audio hilang ≤24 jam |
| Ekspor | `GET /api/jobs/{id}/export?format=txt\|srt\|vtt\|docx` | Mencerminkan suntingan terbaru |
| Pekerja | `POST /worker/v1/jobs/claim`, `.../heartbeat`, `.../result`, `.../fail`, `/worker/v1/ping` | Bearer token; sewa 5 menit; maksimal 3 percobaan |
| Admin | `GET /api/admin/metrics` | Header `X-Admin-Token`; `python scripts/metrics.py` |

Contoh manual (PowerShell) memanggil API pekerja:

```powershell
curl.exe -X POST http://localhost:8000/worker/v1/ping `
  -H "Authorization: Bearer dev-worker-token" `
  -H "Content-Type: application/json" `
  -d '{\"worker_id\":\"laptop\",\"version\":\"0.1.0\"}'
```

`worker run --fake` tetap memakai backend palsu TK-002 sampai `TK-030`
menambahkan konfigurasi token di CLI pekerja.

Token pekerja (`BEOSABASI_WORKER_TOKEN`) dan token admin
(`BEOSABASI_ADMIN_TOKEN`) hanya lewat env. **Rotasi token pekerja:** buat nilai
baru (`python -c "import secrets;print(secrets.token_urlsafe(32))"`), set di env
VPS, restart proses API, lalu perbarui konfigurasi pekerja. Token lama langsung
ditolak; pekerja yang sedang memegang job menyelesaikannya lewat sewa yang ada
atau job kembali ke antrean setelah 5 menit tanpa detak.

Penjadwal retensi berjalan di dalam proses API setiap 30 detik
(`BEOSABASI_SWEEPER_INTERVAL`): sewa kedaluwarsa, unggahan basi 24 jam,
antrean 72 jam, audio 24 jam, transkrip 30 hari. Audit K4 (objek yatim di
bucket, audio yang terlambat dihapus) dijalankan sekali sehari dan dicatat di
log JSON (`audit_k4_bersih` / `audit_k4_anomali`), serta tersedia on-demand di
`GET /api/admin/metrics` (`audit_k4`).

Batas yang bisa diubah lewat env: `BEOSABASI_QUOTA_MINUTES`,
`BEOSABASI_MAX_ACTIVE_JOBS`, `BEOSABASI_MAX_UPLOAD_BYTES`,
`BEOSABASI_GLOBAL_CAP_BYTES`, `BEOSABASI_UPLOADS_PER_HOUR`,
`BEOSABASI_EXPORTS_PER_HOUR`, `BEOSABASI_AUDIO_RETENTION_HOURS`,
`BEOSABASI_TRANSCRIPT_RETENTION_DAYS`.

**Catatan Garage lokal:** API di Compose memakai `S3_ENDPOINT=http://s3.localhost:3900`
dengan `extra_hosts: s3.localhost:host-gateway`, sehingga URL bertanda tangan
tetap sah dan bisa dijangkau peramban (loopback) maupun kontainer (host
gateway). Bucket Garage v2.3 belum punya aturan CORS bucket, jadi unggah
langsung dari peramban ke Garage akan gagal preflight. Untuk uji peramban
lokal, pakai server tiruan Prism (`npm run mock:api`), jalankan API di host
dengan `S3_ENDPOINT=http://localhost:3900`, atau tambahkan proksi CORS. Di
produksi aturan CORS R2 ada di `infra/cloudflare/cors.json`
(`ExposeHeaders: ETag`).

Verifikasi cepat backend:

```powershell
cd apps/api
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
```

## Regenerasi klien dari kontrak


Setiap perubahan `contracts/openapi.yaml` wajib diikuti:

```powershell
python scripts/gen_client.py  # atau: make gen-client
```

CI menolak PR bila file terhasilkan (`api-types.ts`, kedua `schemas.py`)
tidak sinkron dengan kontrak.

## Pemecahan masalah

| Gejala | Periksa |
|---|---|
| `dev-up` gagal: Docker tidak tersedia | Nyalakan Docker Desktop, ulangi |
| API tidak menjawab `/healthz` | `docker compose -f infra/compose.local.yaml logs api` |
| `demo` gagal koneksi | Pastikan `make dev-up` hijau dulu |
| Port 8000/3900 dipakai | Hentikan layanan lain atau ubah port di `infra/compose.local.yaml` |
| `gen-client` gagal: pyyaml hilang | Skrip memasang `pyyaml` otomatis; butuh jaringan sekali |
