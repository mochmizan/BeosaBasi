# Formulir Persetujuan Rekaman Uji

> **Status: DRAF (TK-060/TK-011).** Templat untuk rekaman set uji, bukan
> nasihat hukum. Wajib ditinjau (T-12) sebelum dipakai. Simpan formulir yang
> sudah ditandatangani **terpisah dari audio**; jangan commit ke git.
> Versi: `persetujuan-uji-0.1-draf`.

## Informasi untuk peserta

**Proyek:** BeosaBasi — transkripsi audio bahasa Indonesia (proyek kuliah).
**Pengendali data:** pengembang proyek (peran kampus masih ditetapkan, T-06).
**Kontak:** `[ISI EMAIL]`.

Kami meminta izin merekam suara Anda untuk **menguji kualitas transkripsi**.
Rekaman ini bukan data pengguna layanan dan tidak dipakai untuk melatih model.

### Apa yang direkam

- Suara Anda dalam percakapan/rapat/pesan suara simulasi selama ± 1 menit
  (atau 3-5 menit untuk klip multi-pembicara).
- Tidak ada video wajah bila tidak diperlukan. Bila video direkam, centang
  kotak terpisah di bawah.

### Bagaimana data disimpan

- Berkas audio disimpan di penyimpanan pribadi terenkripsi, **tidak di git**.
- Transkrip acuan disimpan terpisah dari identitas Anda; hanya kode peserta
  (mis. `spk-01`) yang dipakai di dalam set uji.
- Hasil evaluasi dipublikasikan sebagai angka agregat (WER, DER), bukan
  rekaman mentah.
- Audio dihapus setelah evaluasi selesai atau paling lambat `[TANGGAL]`, kecuali
  Anda menyetujui penyimpanan lebih lama untuk reproduksibilitas.

### Risiko

- Rekaman suara dapat memuat informasi pribadi yang Anda ucapkan. Hindari
  menyebut data sensitif (kesehatan, keuangan, rahasia orang lain).
- Suara dapat dikenali oleh orang yang mengenal Anda. Kami tidak menyimpan
  sidik suara dan tidak mengenali Anda di rekaman lain.

### Hak Anda

- Menolak atau berhenti kapan saja, termasuk setelah rekaman dibuat.
- Meminta salinan, koreksi, atau penghapusan rekaman dan transkrip.
- Menarik persetujuan tanpa konsekuensi.
- Permintaan dipenuhi ≤ 3 × 24 jam melalui kontak di atas.

## Pernyataan persetujuan

Saya menyatakan:

- [ ] Saya berusia **≥ 18 tahun**.
- [ ] Saya telah membaca dan memahami informasi di atas.
- [ ] Saya **setuju direkam** untuk pembuatan set uji transkripsi.
- [ ] Saya **setuju transkrip rekaman ini dipakai** untuk evaluasi dan
      pelaporan agregat.
- [ ] Saya **setuju kutipan transkrip anonim** (tanpa nama, tanpa audio)
      ditampilkan di laporan akademik.
- [ ] Saya **setuju rekaman video** bila ada (opsional; kosongkan bila tidak).
- [ ] Saya memahami saya dapat menarik persetujuan kapan saja.

Batasan tambahan yang saya minta (opsional):
`______________________________________________________________`

## Identitas dan tanda tangan

| Field | Isi |
|---|---|
| Kode peserta | `spk-____` |
| Nama lengkap | |
| Tanggal lahir / konfirmasi ≥18 | |
| Tanggal | |
| Tanda tangan | |
| Saksi (bila ada) | |
| Tanda tangan saksi | |

## Diisi oleh peneliti

| Field | Isi |
|---|---|
| ID klip | |
| Kategori | wawancara / rapat / pesan-suara / berderau / campur-id-en / multi-pembicara |
| Tanggal rekaman | |
| Lokasi berkas formulir | `eval/data/<set>/consent/<kode>.pdf` |
| Versi formulir | `persetujuan-uji-0.1-draf` |
| Dicatat di `consent/index.json` | ya / belum |

## Catatan penyimpanan

1. Simpan formulir di folder terenkripsi, bukan di repo.
2. Catat hanya kode peserta dan status di `consent/index.json`; jangan tulis
   nama di file yang bisa terbaca publik.
3. `freeze_set.py --strict-consent` akan gagal bila formulir atau tanggal
   tanda tangan belum lengkap.
