# Checklist Tiket BeosaBasi

Sumber: `spec/TICKETS.md` (spesifikasi), `spec/PRD.md` (persyaratan).
Satu-satunya status resmi. Setiap agen coding (milik anggota tim) wajib
memperbarui file ini di PR yang sama saat menyelesaikan tiket.

## Aturan main untuk agen

1. Ambil tiket tak-tercentang paling atas yang semua dependensinya sudah `[x]`.
2. Baca baris tiket di `spec/TICKETS.md` sampai paham kriteria penerimaannya.
3. Ubah kontrak (`contracts/openapi.yaml`) hanya lewat PR berlabel jalur
   terdampak, lalu jalankan `make gen-client`.
4. Verifikasi: `python scripts/lint.py` dan `python scripts/test.py` hijau.
5. Centang `[x]` tiketnya di file ini dalam PR yang sama.

## Fase 0: Scaffold

- [x] TK-000 Scaffold repositori monorepo
- [x] TK-001 Kontrak API dan protokol pekerja
- [x] TK-002 Lingkungan lokal dan pekerja palsu (dep: TK-000, TK-001)

## Fase 0: Infra dan benchmark

- [ ] TK-003 Pengaturan Cloudflare Pages, R2, DNS, Turnstile (dep: TK-000)
- [x] TK-004 Penyiapan VPS (dep: TK-000, TK-003) — interim 15 Nov 2026: API+Garage di `beosabasivps`, asap publik + web + e2e worker-transkrip hijau; domain permanen/R2/Turnstile, uji reboot, dan backup terjadwal menunggu TK-003
- [x] TK-005 Penyiapan laptop Windows dan perintah doctor (dep: TK-000)
- [x] TK-010 Harness benchmark transkripsi (dep: TK-005)
- [ ] TK-011 Set uji 60 klip dan pedoman anotasi (tanpa dep, jalur manusia)
- [ ] TK-012 Pipeline skor WER dan daftar pemetaan (dep: TK-010, TK-011)
- [ ] TK-013 GERBANG Jalankan benchmark dan keputusan model (dep: TK-010, TK-011, TK-012)
- [ ] TK-014 Uji halusinasi, pengulangan, dan penanda waktu (dep: TK-012)

## Fase 1: API VPS

- [x] TK-020 Skema basis data dan migrasi (dep: TK-001)
- [ ] TK-021 ~~Autentikasi Google, allowlist, sesi, Turnstile~~ — DIPOTONG (tanpa login, lihat ADR-0001)
- [ ] TK-022 ~~Persetujuan dan pemberitahuan privasi~~ — DIPOTONG (tanpa login/kebijakan)
- [x] TK-023 Alur unggah multipart ke R2 (dep: TK-020, TK-021, TK-022, TK-003)
- [x] TK-024 Siklus job, kuota, dan pembatasan (dep: TK-023)
- [x] TK-025 API pekerja klaim, detak, hasil, gagal (dep: TK-024)
- [x] TK-026 API transkrip segmen, penyuntingan, pembicara (dep: TK-025)
- [x] TK-027 Ekspor TXT, SRT, VTT, DOCX (dep: TK-026)
- [x] TK-028 Retensi dan penghapusan K4 (dep: TK-024, TK-026)
- [x] TK-029 Observabilitas dan metrik (dep: TK-025)

## Fase 1: Pekerja laptop

- [x] TK-030 Kerangka pekerja (dep: TK-001, TK-005)
- [x] TK-031 Validasi dan normalisasi media (dep: TK-030)
- [ ] TK-032 Tahap transkripsi (dep: TK-031, TK-013) — kode + e2e vs API nyata ok, menunggu angka TK-013
- [x] TK-033 Pengemasan hasil dan higiene data (dep: TK-032)
- [ ] TK-034 Perlindungan laptop (dep: TK-030) — kode ok, butuh uji cabut-kabel fisik
- [ ] TK-035 Penanganan OOM dan percobaan ulang (dep: TK-032) — logika retry diuji stub, butuh bukti OOM CUDA nyata

## Fase 1: Web

- [x] TK-040 Scaffold web dan klien API (dep: TK-001)
- [ ] TK-041 ~~Login dan persetujuan~~ — DIPOTONG (tanpa login)
- [x] TK-042 Unggah dapat dilanjutkan, perekam suara web (`MediaRecorder`), dan kuota (dep: TK-040, TK-023, TK-024)
- [x] TK-043 Daftar job dan halaman status jujur (dep: TK-042)
- [x] TK-044 Editor transkrip dengan audio tersinkron dan simpan otomatis ≤2 detik (dep: TK-043, TK-026)
- [x] TK-045 Ekspor (TXT/SRT/VTT/DOCX) dan hapus data/sesi (dep: TK-044, TK-027, TK-028)

## Fase 1: Dokumen, keamanan, QA

- [ ] TK-060 ~~Pemberitahuan privasi, ROPA, dan DPIA-lite~~ — DIPOTONG (tanpa kebijakan)
- [ ] TK-061 Tinjauan model ancaman dan daftar periksa keamanan (dep: TK-025, TK-023, TK-031)
- [ ] TK-062 Uji ujung ke ujung, beban, dan latihan kegagalan (dep: TK-045, TK-035, TK-028)
- [ ] TK-063 Kesiapan pilot tertutup (dep: TK-061, TK-062)

## Fase 2: Pelabelan pembicara

- [ ] TK-050 GERBANG Spike diarisasi di Windows (dep: TK-005)
- [ ] TK-051 Tahap diarisasi di pekerja (dep: TK-050, TK-032)
- [ ] TK-052 Penggabungan transkrip dan pembicara (dep: TK-051)
- [ ] TK-053 Set uji multi-pembicara dan evaluasi DER (dep: TK-050)
- [ ] TK-054 Kuota 2x dan pengembalian saat gagal (dep: TK-024, TK-051)
- [ ] TK-046 Antarmuka pembicara (dep: TK-044, TK-026, TK-052) — UI ganti-nama/pindah ada, menunggu TK-052

## Fase 3: Opsional

- [ ] TK-070 Perluasan, hanya setelah telaah hukum dan DPIA lengkap (dep: TK-063, TK-053)
