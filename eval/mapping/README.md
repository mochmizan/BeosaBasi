# Daftar pemetaan ejaan

`id-v1.json` adalah daftar varian ejaan untuk **WER longgar** (PRD 3.4.3).
Daftar ini diterapkan pada transkrip acuan dan hipotesis sekaligus, sehingga
tidak menguntungkan salah satu pihak.

## Aturan

1. **Beku sebelum benchmark pertama.** Setelah `id-v1` dipakai untuk melihat
   hasil, isinya tidak boleh diubah. Perubahan wajib menjadi `id-v2`.
2. **Hanya varian ejaan/abreviasi dari kata yang sama.** Sinonim tidak
   dipetakan: `tidak` dan `nggak` tetap berbeda, `bikin` dan `buat` tetap
   berbeda. Ini menjaga WER longgar tetap jujur.
3. **Kunci dan nilai dinormalisasi** lebih dulu (huruf kecil, tanpa tanda
   baca). Pemetaan frasa didukung dan kunci terpanjang menang.
4. **Tidak ada rantai.** `a -> b` dan `b -> c` ditolak oleh pemuat mapping.
5. **Angka** dipetakan ke bentuk kata karena pedoman anotasi menulis angka
   sebagai digit.

## Menambah versi

```bash
cp eval/mapping/id-v1.json eval/mapping/id-v2.json
# ubah "version" menjadi "id-v2" dan tambahkan catatan di bawah
python -c "import json; print(json.load(open('eval/mapping/id-v2.json'))['version'])"
python eval/scripts/freeze_set.py --set eval/data/id-v2 --mapping eval/mapping/id-v2.json
```

Skrip akan menulis `id-v2.sha256`. `score_wer.py` memverifikasi hash sebelum
menghitung skor, jadi hasil tidak bisa diproduksi dengan daftar yang sudah
diam-diam diubah.

## Riwayat

| Versi | Tanggal | Perubahan |
|---|---|---|
| `id-v1` | 2026-11-15 | Versi awal: abreviasi umum, partikel informal, angka 0-100, varian kata serapan. |
