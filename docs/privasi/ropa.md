# ROPA Ringkas (Records of Processing Activities)

> **Status: DRAF (TK-060).** Ringkasan, bukan catatan resmi yang sudah
> diverifikasi. Wajib ditinjau pada T-12 dan diperbarui bila alur data berubah.
> Versi: `ropa-0.1-draf` · 15 November 2026.

Pengendali: pengembang individu (proyek kuliah). Peran kampus/dosen: T-06.
Tidak ada login; pengguna berinteraksi tanpa akun.

## A. Daftar kegiatan pemrosesan

| # | Kegiatan | Subjek | Data | Tujuan | Dasar | Sistem / penerima | Lokasi | Retensi |
|---|---|---|---|---|---|---|---|---|
| 1 | Unggah audio/video | Pengguna, pembicara dalam rekaman | Berkas audio/video, nama berkas, ukuran, tipe, IP, token Turnstile | Menerima bahan transkripsi; kuota dan anti-bot | Persetujuan | Web (Pages), API (VPS), R2 | R2 `[LOKASI]`, VPS `[NEGARA]` | Audio ≤ 24 jam |
| 2 | Transkripsi | Pengguna, pembicara | Audio, transkrip, segmen, penanda waktu, confidence | Menghasilkan transkrip | Persetujuan | Worker di laptop | Laptop pengelola | Berkas kerja segera; transkrip 30 hari |
| 3 | Pelabelan pembicara (opsional) | Pembicara | Audio, label anonim, embedding sementara di memori | Memisahkan pembicara dalam satu rekaman | Persetujuan | Worker (pyannote) | Laptop | Embedding tidak disimpan |
| 4 | Antrean, status, kuota | Pengguna | ID job, status, waktu, IP, menit terpakai | Menjalankan job, kuota harian UTC+7, pencegahan penyalahgunaan | Kepentingan sah / persetujuan | API + SQLite di VPS | VPS | Job dan metrik sesuai 4.12 |
| 5 | Catatan persetujuan | Pengguna | Versi dokumen, waktu, ID job | Bukti persetujuan | Kewajiban hukum | API + SQLite | VPS | Dipertahankan tanpa isi pribadi |
| 6 | Metrik kualitas tanpa teks | Pengguna (agregat) | xRT, status, proporsi confidence rendah, rasio penyuntingan | Memantau kualitas dan kapasitas | Kepentingan sah | API + SQLite | VPS | Sesuai kebijakan metrik |
| 7 | Cadangan basis data | Pengguna | Salinan terenkripsi basis data | Pemulihan bencana | Kepentingan sah | Penyimpanan cadangan VPS | VPS | ≤ 7 hari |
| 8 | Audit retensi (K4) | — | Daftar objek, waktu hapus, temuan | Memastikan audio terhapus ≤ 24 jam | Kewajiban hukum | Penjadwal + laporan worker | VPS, laptop | Log audit |

## B. Aliran data

```
Browser --Turnstile--> Cloudflare Pages
        --metadata--> VPS API (SQLite, queue)
        --presigned multipart--> Cloudflare R2 (audio)
VPS --claim job--> Laptop worker --unduh sementara--> R2
Laptop worker --hasil transkrip--> VPS API
VPS --hapus audio--> R2 (≤24 jam) ; transkrip (30 hari)
```

Audio tidak melewati VPS; VPS hanya mengatur unggahan dan antrean.

## C. Penerima / prosesor

| Penerima | Peran | Data | Catatan |
|---|---|---|---|
| Cloudflare | R2, Pages, Turnstile, DNS/WAF | audio, metadata, IP | lokasi bucket `[ISI]` (TK-003) |
| Penyedia VPS | komputasi dan penyimpanan | metadata, transkrip, IP | nama/negara `[ISI]` (T-08) |
| Laptop pengelola | inferensi | audio sementara, transkrip | bukan pihak ketiga; akses fisik terbatas |

Tidak ada penjualan data, iklan, atau pelatihan model dengan data pengguna.

## D. Langkah keamanan

- Bucket R2 privat; tautan unggah memakai presigned URL berumur pendek.
- Token pekerja disimpan sebagai hash; rotasi token.
- Turnstile pada unggahan; kuota per IP; batas job aktif.
- Audit retensi harian (K4) dan lifecycle R2 7 hari sebagai jaring pengaman.
- Akses laptop memakai akun OS terpisah dan disk terenkripsi bila tersedia.
- Tidak ada teks sunting yang disimpan untuk analisis.

## E. Kesenjangan yang harus ditutup

| # | Kesenjangan | Pemilik | Target |
|---|---|---|---|
| 1 | Lokasi bucket R2 belum dipilih | TK-003 | sebelum pilot |
| 2 | Penyedia/negara VPS belum dicatat | T-08 | sebelum pilot |
| 3 | Status hukum ciri suara sementara | T-12 | sebelum pilot |
| 4 | Kontak privasi dan prosedur verifikasi permintaan | TK-060 | sebelum pilot |
| 5 | Peran kampus/dosen sebagai pengendali bersama | T-06 | sebelum pilot |
| 6 | Nama produk dan domain | T-14 | sebelum publikasi |

## F. Rujukan

- PRD 4.11, 4.12, AI-14, D-05, D-17
- `docs/privasi/pemberitahuan-privasi.md`
- `docs/privasi/dpia-lite.md`
- `docs/runbook/insiden-kebocoran.md`
