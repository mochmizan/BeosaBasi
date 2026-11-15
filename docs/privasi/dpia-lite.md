# DPIA-lite

> **Status: DRAF (TK-060).** Penilaian ringan, bukan DPIA lengkap. Wajib
> ditinjau hukum (T-12) sebelum pendaftaran dibuka di luar undangan.
> Versi: `dpia-lite-0.1-draf` · 15 November 2026.

## 1. Ruang lingkup

Layanan transkripsi audio/video bahasa Indonesia tanpa login. Data utama:
rekaman suara (dapat memuat data pribadi dan data sensitif), transkrip, label
pembicara anonim, metadata job, dan alamat IP. Audio disimpan sementara di R2,
transkrip 30 hari, cadangan ≤ 7 hari.

## 2. Kebutuhan DPIA

Pemrosesan berpotensi berisiko tinggi karena: (a) rekaman suara dapat
mengidentifikasi orang; (b) pemrosesan sistematis dalam skala pilot;
(c) transfer lintas negara; (d) kemungkinan ciri suara termasuk data biometrik
(T-12). Karena itu DPIA-lite ini dibuat sebelum pilot tertutup.

## 3. Penilaian risiko

Skala: Kemungkinan (K) dan Dampak (D) 1-5; Risiko = K × D. Residual setelah
mitigasi.

| # | Risiko | K | D | Risiko | Mitigasi | Residual |
|---|---|---|---|---|---|---|
| R1 | Audio pengguna tersimpan lebih dari 24 jam karena penghapus gagal | 3 | 4 | 12 | penjadwal 15 menit, lifecycle R2 7 hari, audit K4 harian | 4 (sedang) |
| R2 | Kebocoran bucket R2 atau kredensial | 2 | 5 | 10 | bucket privat, presigned URL pendek, rotasi kunci, least privilege | 4 (sedang) |
| R3 | Akses tidak sah ke VPS / SQLite | 2 | 5 | 10 | firewall, SSH key, pembaruan, token pekerja hash | 4 (sedang) |
| R4 | Rekaman memuat data sensitif (kesehatan, agama, opini) | 3 | 4 | 12 | pemberitahuan, persetujuan, retensi pendek, larangan pelatihan | 6 (sedang) |
| R5 | Ciri suara sementara dianggap data biometrik | 3 | 4 | 12 | tidak menyimpan embedding, tidak mengenali lintas rekaman, telaah T-12 | 6 (sedang) |
| R6 | Transfer lintas negara tanpa dasar yang jelas | 3 | 4 | 12 | sebutkan penyedia/negara, telaah T-12, pilih lokasi bucket | 6 (sedang) |
| R7 | Pengguna di bawah 18 tahun | 2 | 3 | 6 | deklarasi ≥ 18, penghapusan atas permintaan | 2 (rendah) |
| R8 | Penyalahgunaan kuota / DoS | 3 | 3 | 9 | Turnstile, kuota IP, batas job aktif, satu job per waktu | 3 (rendah) |
| R9 | Teks transkrip dipakai untuk pelatihan tanpa izin | 1 | 5 | 5 | kebijakan larangan, tidak ada pipeline pelatihan, audit kode | 1 (rendah) |
| R10 | Permintaan hak subjek tidak terpenuhi ≤ 3 × 24 jam | 2 | 4 | 8 | prosedur runbook, verifikasi ID job, catat waktu | 4 (sedang) |
| R11 | Kehilangan data saat laptop mati | 4 | 2 | 8 | job tetap queued, retry 3x, lease 5 menit | 2 (rendah) |
| R12 | Model berhalusinasi dan pengguna mempercayai teks salah | 4 | 3 | 12 | pemberitahuan keterbatasan, editor, metrik kualitas | 6 (sedang) |

## 4. Risiko yang tidak dapat diterima tanpa keputusan

- **R5/R6** bergantung pada telaah hukum. Bila T-12 menyimpulkan ciri suara
  sementara adalah data biometrik, fitur pelabelan pembicara ditunda sampai
  ada dasar pemrosesan dan persetujuan terpisah.
- **R1** harus dibuktikan dengan audit K4; bila audit menemukan audio > 24 jam,
  pilot dihentikan sampai diperbaiki.

## 5. Hak subjek

Akses, salinan, hapus, tarik persetujuan. Target ≤ 3 × 24 jam. Tanpa akun,
verifikasi memakai ID job. Prosedur dan templat tanggapan ada di
`docs/runbook/insiden-kebocoran.md` (bagian permintaan subjek) dan akan
dipisah bila diperlukan.

## 6. Konsultasi

- Dosen pembimbing: belum (T-06).
- Telaah hukum: belum (T-12).
- Pemilik produk: pengembang.

## 7. Kesimpulan sementara

Pilot tertutup dapat dilanjutkan **hanya jika**:
1. pemberitahuan privasi dan formulir persetujuan sudah diisi kontaknya;
2. lokasi R2 dan penyedia VPS sudah dicatat;
3. audit retensi K4 berjalan;
4. telaah T-12 untuk data suara dan transfer lintas negara selesai, atau
   fitur yang bergantung padanya ditunda.

## 8. Tinjauan ulang

DPIA-lite ditinjau ulang bila: model berubah, penyedia infrastruktur berubah,
fitur baru menyentuh data pribadi, atau terjadi insiden keamanan.
