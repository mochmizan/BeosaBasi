# Runbook VPS BeosaBasi (TK-004, interim)

> Status 15 Nov 2026: API + Garage (pengganti R2 sementara) hidup di VPS,
> dipublikasi lewat tunnel cepat Cloudflare. Domain permanen + R2 asli
> menunggu TK-003 (butuh akses akun Cloudflare pemilik).

## Arsitektur

- VPS `43.173.11.117`, kerja hanya di `/opt/beosabasi` (milik `beosabasi`).
  SSH sebagai `ubuntu`, lalu `sudo -u beosabasi ...` (tanpa kata sandi).
  Jangan sentuh `netclub_*` / `beosabasi_beosabasi-net`.
- Proyek compose: `beosabasivps`, file `vps/compose.yaml`
  (salinan repo `infra/compose.vps.yaml`), jaringan `beosabasivps-net`.
- `api` → `127.0.0.1:18082`, `s3` (Garage v2.3.0) → `127.0.0.1:3900`.
  Tidak ada bind 80/443 di host.
- Web statis: nginx lama `beosabasi_app` melayani `/opt/beosabasi/app`
  di `127.0.0.1:18081` (jangan hapus kontainer itu).
- Tiga tunnel cepat (tidak stabil antar reboot, cetak ulang tiap mulai):
  API, S3, dan web. `S3_ENDPOINT` di `/opt/beosabasi/.env` **wajib**
  URL publik tunnel S3 — URL presigned dipakai verbatim oleh browser
  dan worker, jadi host penandatangan harus bisa dijangkau dari internet.

## Deploy awal (sudah dilakukan 15 Nov 2026)

Skrip di `infra/` dijalankan sebagai `beosabasi` (pipe via base64,
karena `/home/ubuntu` tak terbaca oleh `beosabasi`):

1. `vps-step1.sh` — token acak (`WORKER/ADMIN`, garam IP, kunci S3,
   secret RPC/admin Garage) ke `/opt/beosabasi/.env` (600) + `garage.toml`.
2. `vps-step3.sh` — turunkan percobaan pertama yang gagal, salin compose
   ke `vps/`, bangun konteks `../src/apps/api`, naikkan `s3`.
   (Step2 gagal: mount memakai `./src/...` padahal konteks file di `vps/`.)
3. `vps-step4.sh` — bootstrap Garage: layout 1 node, bucket `beosabasi`,
   kunci `beosabasi01`, izin baca-tulis.
4. `vps-step5.sh` — tunnel S3, tulis `S3_ENDPOINT` publik ke `.env`,
   build + naikkan `api`, tunggu `/healthz` 200.
5. `vps-step6.sh` — tunnel API, tulis `api-url.txt`, cek via tunnel.
6. Web: `npm run build` lokal dengan
   `VITE_API_BASE_URL=<url-tunnel-api>`, lalu
   `scp webdist.tar /tmp/` + `sudo -u beosabasi tar -xf ... -C /opt/beosabasi/app`.
7. Asap: `upload → PUT presigned → complete → claim` hijau;
   e2e penuh (transkripsi tiny + baca transkrip) hijau.

## Operasi harian

- Status: `docker compose -f vps/compose.yaml ps` (dengan
  `COMPOSE_PROJECT_NAME=beosabasivps`), `curl 127.0.0.1:18082/healthz`.
- URL tunnel aktif: `grep -o 'https://[^ ]*trycloudflare.com' *.log`.
- Restart API setelah ubah `.env`:
  `docker compose -f vps/compose.yaml up -d --build api`.
- Token worker: `grep BEOSABASI_WORKER_TOKEN /opt/beosabasi/.env`
  (jangan commit, berikan langsung ke pemilik laptop).
- Log: `docker compose -f vps/compose.yaml logs api|tail`.

## Batasan interim (jujur)

- Tunnel cepat berganti URL tiap restart — web `dist` yang dibakar
  `VITE_API_BASE_URL` harus dibangun ulang tiap URL API berubah.
- Garage satu node = penyimpanan sementara, bukan R2 tahan lama.
  Migrasi ke R2 + domain + Turnstile saat TK-003 tersedia.
