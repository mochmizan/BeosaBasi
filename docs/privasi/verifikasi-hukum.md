# Verifikasi Hukum (T-12)

> **Status: DRAF (TK-060).** Ini daftar periksa, bukan nasihat hukum dan bukan
> hasil telaah. Setiap butir harus dicek ke teks resmi (UU, PP, peraturan
> kampus) sebelum pilot dibuka di luar undangan. Jangan mengutip nomor pasal
> dari dokumen ini tanpa mencocokkannya lagi ke sumber resmi.
> Versi: `verifikasi-hukum-0.1-draf` · 15 November 2026.

## Cara memakai

1. Buka teks resmi (JDIH/BPHN atau salinan resmi kampus), bukan ringkasan
   blog.
2. Isi kolom **Bukti** dengan pasal/ayat persis dan tautan/arsip.
3. Ubah **Status** menjadi `cocok`, `perlu ubah`, atau `tidak berlaku`.
4. Bila hasilnya `perlu ubah`, buat tiket perubahan dan tautkan di sini.
5. Jangan menandai TK-060 selesai sebelum semua butir berstatus `cocok`,
   `tidak berlaku`, atau `ditunda` dengan alasan tertulis.

## A. Dasar pemrosesan dan persetujuan

| # | Yang harus dipastikan | Rujukan awal | Status | Bukti / catatan |
|---|---|---|---|---|
| A1 | Persetujuan eksplisit sebelum unggahan pertama adalah dasar yang sah untuk memproses audio | UU PDP — pasal tentang dasar pemrosesan | `[ ] belum` | Nomor pasal belum dicek |
| A2 | Persetujuan harus dapat dibuktikan: versi dokumen, waktu, dan bukti tindakan pengguna | UU PDP — kewajiban pengendali | `[ ] belum` | Rancangan: catatan persetujuan di SQLite |
| A3 | Menarik persetujuan harus semudah memberikannya | UU PDP — hak subjek | `[ ] belum` | Alur tarik persetujuan belum ada di UI |
| A4 | Pemrosesan tanpa login tetap memerlukan identifikasi pengendali dan kontak | UU PDP — informasi yang wajib diberikan | `[ ] belum` | Kontak privasi masih `[ISI EMAIL]` |
| A5 | Apakah "kepentingan sah" boleh dipakai untuk kuota/anti-bot (IP, Turnstile) tanpa persetujuan terpisah | UU PDP — dasar pemrosesan | `[ ] belum` | ROPA baris 4 memakai "kepentingan sah / persetujuan" |
| A6 | Batas usia 18 tahun dan mekanisme deklarasi cukup, atau perlu verifikasi tambahan | UU PDP — data anak | `[ ] belum` | PRD D-05 |

## B. Hak subjek data

| # | Yang harus dipastikan | Rujukan awal | Status | Bukti / catatan |
|---|---|---|---|---|
| B1 | Daftar hak (akses, salinan, koreksi, hapus, tarik persetujuan, keberatan) sudah lengkap | UU PDP — hak subjek | `[ ] belum` | Pemberitahuan bagian 8 |
| B2 | Target pemenuhan **≤ 3 × 24 jam** sesuai kewajiban, bukan hanya janji internal | UU PDP — tenggat permintaan | `[ ] belum` | PRD 4.11 |
| B3 | Verifikasi identitas tanpa akun (ID job/tautan job) dianggap memadai | Praktik + UU PDP | `[ ] belum` | Runbook bagian 8 |
| B4 | Penghapusan harus mencakup audio, transkrip, segmen, job, dan cadangan (≤ 7 hari) | UU PDP — penghapusan | `[ ] belum` | PRD 4.12 |
| B5 | Catatan persetujuan/audit boleh dipertahankan tanpa isi pribadi | UU PDP — pembatasan penyimpanan | `[ ] belum` | ROPA baris 5 |
| B6 | Apakah diperlukan kanal khusus (email/form) dan siapa yang menjawab | UU PDP + kampus | `[ ] belum` | Peran kampus T-06 |

## C. Pemberitahuan dan transparansi

| # | Yang harus dipastikan | Rujukan awal | Status | Bukti / catatan |
|---|---|---|---|---|
| C1 | Isi minimum pemberitahuan privasi (identitas, tujuan, dasar, penerima, retensi, hak) sudah lengkap | UU PDP — informasi kepada subjek | `[ ] belum` | `pemberitahuan-privasi.md` |
| C2 | Pemberitahuan versi baru harus ditampilkan sebelum unggahan berikutnya | UU PDP — perubahan tujuan | `[ ] belum` | Bagian 11 |
| C3 | Bahasa Indonesia sederhana dianggap cukup; tidak perlu terjemahan Inggris | Kebijakan produk | `[ ] belum` | — |
| C4 | Nama produk dan domain final (T-14) harus muncul di pemberitahuan | UU PDP + merek | `[ ] belum` | Masih "BeosaBasi" sementara |

## D. Insiden dan pemberitahuan kebocoran

| # | Yang harus dipastikan | Rujukan awal | Status | Bukti / catatan |
|---|---|---|---|---|
| D1 | Kewajiban memberi tahu pihak berwenang dalam **3 × 24 jam** | UU PDP — pemberitahuan kegagalan pelindungan | `[ ] belum` | PRD 4.11, runbook bagian 1 |
| D2 | Kewajiban memberi tahu subjek data bila berisiko tinggi | UU PDP — pemberitahuan kepada subjek | `[ ] belum` | Runbook bagian 5 |
| D3 | Isi pemberitahuan minimum (apa, kapan, data, dampak, tindakan, kontak) | UU PDP — isi pemberitahuan | `[ ] belum` | Templat runbook 7.1/7.2 |
| D4 | Siapa pihak berwenang yang dituju dan format kanalnya | Peraturan pelaksana | `[ ] belum` | Belum ditentukan |
| D5 | Batas waktu internal 24 jam untuk penilaian awal cukup realistis untuk satu orang | Operasional | `[ ] belum` | Runbook bagian 4-5 |

## E. Pejabat/petugas pelindungan data dan tata kelola

| # | Yang harus dipastikan | Rujukan awal | Status | Bukti / catatan |
|---|---|---|---|---|
| E1 | Apakah proyek ini wajib menunjuk DPO | UU PDP — kewajiban DPO | `[ ] belum` | Pengendali individu, skala pilot |
| E2 | Bila tidak wajib, apakah cukup menunjuk kontak privasi | UU PDP + praktik | `[ ] belum` | Kontak `[ISI EMAIL]` |
| E3 | Peran kampus dan dosen: pengendali bersama, prosesor, atau tidak terlibat | UU PDP + aturan kampus | `[ ] belum` | T-06 |
| E4 | Apakah proyek perlu izin/registrasi kegiatan penelitian kampus | Aturan kampus | `[ ] belum` | Belum dicek |
| E5 | Apakah kewajiban ROPA dan DPIA berlaku untuk skala ini | UU PDP / PP pelaksana | `[ ] belum` | `ropa.md`, `dpia-lite.md` |

## F. Transfer lintas negara

| # | Yang harus dipastikan | Rujukan awal | Status | Bukti / catatan |
|---|---|---|---|---|
| F1 | Negara lokasi bucket R2 dan negara VPS sudah diketahui | PRD T-08, TK-003 | `[ ] belum` | Masih `[ISI]` di ROPA |
| F2 | Dasar transfer lintas negara yang dipakai (persetujuan, kontrak, atau lainnya) | UU PDP — transfer ke luar wilayah | `[ ] belum` | Belum ditentukan |
| F3 | Pemberitahuan menyebut negara/penyedia dan konsekuensinya | UU PDP — transparansi | `[ ] belum` | Bagian 4 |
| F4 | Apakah perlu salinan klausul pelindungan data dari Cloudflare/penyedia VPS | UU PDP — transfer | `[ ] belum` | DPA/terms belum diarsipkan |

## G. Data biometrik dan fitur pembicara

| # | Yang harus dipastikan | Rujukan awal | Status | Bukti / catatan |
|---|---|---|---|---|
| G1 | Apakah embedding suara sementara (tidak disimpan) termasuk data biometrik | UU PDP — data pribadi spesifik | `[ ] belum` | PRD 4.11, D-17 |
| G2 | Bila ya: dasar pemrosesan tambahan dan persetujuan terpisah | UU PDP — data pribadi spesifik | `[ ] belum` | Fitur ditunda sampai jelas |
| G3 | Klaim "tidak menyimpan sidik suara" harus bisa dibuktikan dari kode | Teknis + hukum | `[ ] belum` | AI-14, TK-051 |
| G4 | Label "Pembicara 1/2" tidak boleh menjadi cara identifikasi lintas rekaman | UU PDP + PRD | `[ ] belum` | PRD 3.5 |
| G5 | Apakah perlu DPIA penuh bila fitur pembicara dilanjutkan | UU PDP — risiko tinggi | `[ ] belum` | `dpia-lite.md` bagian 4 |

## H. Retensi dan keamanan

| # | Yang harus dipastikan | Rujukan awal | Status | Bukti / catatan |
|---|---|---|---|---|
| H1 | Retensi audio ≤ 24 jam, transkrip 30 hari, cadangan ≤ 7 hari konsisten dengan asas pembatasan penyimpanan | UU PDP — pembatasan penyimpanan | `[ ] belum` | PRD 4.12 |
| H2 | Audit retensi (K4) cukup sebagai bukti kepatuhan | UU PDP — akuntabilitas | `[ ] belum` | TK-035, laporan audit |
| H3 | Kewajiban keamanan minimum (enkripsi, kontrol akses, log) terpenuhi | UU PDP — keamanan | `[ ] belum` | TK-061 |
| H4 | Apakah insiden wajib dicatat dalam register khusus | UU PDP — dokumentasi | `[ ] belum` | Runbook bagian 6 |
| H5 | Apakah data uji (rekaman peserta) tunduk pada aturan yang sama dengan data pengguna | UU PDP + etika penelitian | `[ ] belum` | `formulir-persetujuan.md` |

## I. Peraturan pelaksana dan tanggal berlaku

| # | Yang harus dipastikan | Rujukan awal | Status | Bukti / catatan |
|---|---|---|---|---|
| I1 | Status PP 33/2026 dan tanggal berlakunya (PRD menyebut 16 Januari 2027) | PP 33/2026 | `[ ] belum` | Sumber PRD masih sekunder |
| I2 | Kewajiban mana yang baru berlaku setelah tanggal itu | PP 33/2026 | `[ ] belum` | Perlu teks resmi |
| I3 | Apakah ada peraturan kampus/daerah yang lebih ketat | Aturan kampus | `[ ] belum` | T-06 |
| I4 | Apakah aturan berubah selama pilot; siapa yang memantau | Operasional | `[ ] belum` | Belum ada pemilik |

## J. Keputusan yang harus dicatat

| # | Keputusan | Pilihan | Pemilik | Tanggal |
|---|---|---|---|---|
| J1 | Dasar pemrosesan untuk audio | persetujuan / lainnya | — | — |
| J2 | Dasar transfer lintas negara | — | — | — |
| J3 | Status hukum embedding suara sementara | biometrik / bukan | — | — |
| J4 | Peran kampus | pengendali bersama / prosesor / tidak terlibat | — | — |
| J5 | Perlu DPO atau cukup kontak privasi | — | — | — |
| J6 | Fitur pembicara dilanjutkan / ditunda | — | — | — |

## K. Ringkasan status

| Bagian | Butir | Cocok | Perlu ubah | Ditunda | Belum dicek |
|---|---|---|---|---|---|
| A. Dasar pemrosesan | 6 | 0 | 0 | 0 | 6 |
| B. Hak subjek | 6 | 0 | 0 | 0 | 6 |
| C. Pemberitahuan | 4 | 0 | 0 | 0 | 4 |
| D. Insiden | 5 | 0 | 0 | 0 | 5 |
| E. DPO/tata kelola | 5 | 0 | 0 | 0 | 5 |
| F. Lintas negara | 4 | 0 | 0 | 0 | 4 |
| G. Biometrik | 5 | 0 | 0 | 0 | 5 |
| H. Retensi/keamanan | 5 | 0 | 0 | 0 | 5 |
| I. Peraturan pelaksana | 4 | 0 | 0 | 0 | 4 |
| **Total** | **44** | **0** | **0** | **0** | **44** |

## Rujukan internal

- PRD 4.11 (privasi dan kepatuhan), 4.12 (retensi), AI-14, D-05, D-17
- `docs/privasi/pemberitahuan-privasi.md`
- `docs/privasi/ropa.md`
- `docs/privasi/dpia-lite.md`
- `docs/privasi/formulir-persetujuan.md`
- `docs/runbook/insiden-kebocoran.md`
