# Dokumen Privasi (TK-060)

Indeks draf privasi dan kepatuhan. Semua dokumen di sini **belum diverifikasi
hukum** (T-12) dan memakai nama produk sementara (T-14). Jangan dipublikasikan
atau dipakai untuk pilot terbuka sebelum butir di `verifikasi-hukum.md`
diselesaikan.

| Dokumen | Isi | Status |
|---|---|---|
| [pemberitahuan-privasi.md](pemberitahuan-privasi.md) | Pemberitahuan privasi bahasa Indonesia untuk pengguna | Draf `privasi-0.1` |
| [ropa.md](ropa.md) | Records of Processing Activities ringkas: kegiatan, data, penerima, retensi | Draf `ropa-0.1` |
| [dpia-lite.md](dpia-lite.md) | Penilaian risiko ringan (12 risiko, mitigasi, residual) | Draf `dpia-lite-0.1` |
| [verifikasi-hukum.md](verifikasi-hukum.md) | Daftar periksa T-12: 44 butir, rujukan pasal, keputusan yang harus dicatat | Draf, 0/44 dicek |
| [formulir-persetujuan.md](formulir-persetujuan.md) | Templat persetujuan tertulis untuk peserta rekaman set uji | Draf `persetujuan-uji-0.1` |
| [../runbook/insiden-kebocoran.md](../runbook/insiden-kebocoran.md) | Prosedur kebocoran data + permintaan hak subjek | Draf `insiden-0.1` |

## Yang masih terbuka

| Butir | Pemilik | Menghalangi |
|---|---|---|
| Kontak privasi (email) | TK-060 | Publikasi pemberitahuan |
| Lokasi bucket R2 | TK-003 | Bagian transfer lintas negara |
| Penyedia dan negara VPS | T-08 | Bagian transfer lintas negara |
| Peran kampus/dosen | T-06 | Pengendali data, jalur permintaan hak |
| Status hukum embedding suara sementara | T-12 | Fitur pelabelan pembicara |
| Nama produk dan domain | T-14 | Semua dokumen publik |
| Telaah 44 butir verifikasi hukum | T-12 | Pilot di luar undangan |
| Latihan prosedur insiden | TK-062 | Kesiapan pilot (TK-063) |

## Aturan penulisan

1. Setiap klaim tentang perilaku sistem harus cocok dengan PRD 4.11/4.12 dan
   kode. Bila kode berubah, dokumen ikut diperbarui.
2. Jangan menulis nomor pasal sebagai fakta sebelum dicek ke teks resmi. Tandai
   `[VERIFIKASI]` atau `[ ] belum`.
3. Data pribadi (nama, audio, formulir bertanda tangan) tidak boleh masuk git.
   Formulir disimpan terpisah dari audio, di penyimpanan terenkripsi.
4. Setiap perubahan penting menaikkan versi dokumen dan dicatat di
   `pemberitahuan-privasi.md` bagian 11.
5. Dokumen ini bukan nasihat hukum.
