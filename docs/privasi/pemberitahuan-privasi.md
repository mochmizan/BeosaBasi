# Pemberitahuan Privasi — BeosaBasi

> **Status: DRAF (TK-060).** Belum diverifikasi ke teks resmi (T-12) dan nama
> produk belum final (T-14). Jangan dipublikasikan sebelum kedua hal itu
> selesai. Setiap klaim di bawah harus cocok dengan perilaku sistem di PRD
> 4.11 dan 4.12; bila kode berubah, dokumen ini ikut diperbarui.

Terakhir diperbarui: 15 November 2026 · Versi dokumen: `privasi-0.1-draf`

## 1. Siapa yang mengelola data

BeosaBasi adalah proyek kuliah perorangan. Pengendali data untuk sementara
adalah pengembang proyek. Peran kampus dan dosen pembimbing belum ditetapkan
(T-06).

Kontak privasi: **`[ISI EMAIL]`** (wajib diisi sebelum pilot).

## 2. Data yang kami proses

| Data | Contoh | Wajib? |
|---|---|---|
| Berkas audio atau video | rekaman wawancara, rapat, pesan suara | Ya |
| Transkrip dan segmen | teks hasil transkripsi, waktu mulai/selesai | Otomatis |
| Label pembicara | "Pembicara 1", "Pembicara 2" | Hanya bila Anda memilih pisahkan pembicara |
| Metadata job | durasi, ukuran berkas, status, waktu unggah | Otomatis |
| Alamat IP | dipakai untuk kuota harian dan pencegahan penyalahgunaan | Otomatis |
| Catatan persetujuan | versi dokumen, waktu persetujuan | Ya, sebelum unggahan pertama |
| Metrik agregat | xRT, status job, proporsi segmen berkeyakinan rendah, rasio penyuntingan | Otomatis, **tanpa teks** |

Kami **tidak** meminta nama, email, atau akun. Tidak ada login.

## 3. Mengapa data diproses

- Membuat transkrip berpenanda waktu dan, bila dipilih, label pembicara.
- Menjalankan antrean, kuota harian, dan pemulihan job.
- Menjaga layanan dari penyalahgunaan (kuota per IP, Turnstile).
- Menghitung metrik kualitas agregat tanpa menyimpan teks suntingan.

Dasar pemrosesan adalah **persetujuan eksplisit** yang Anda berikan sebelum
unggahan pertama. Versi dan waktu persetujuan dicatat. Anda dapat menarik
persetujuan kapan saja (lihat bagian 8).

## 4. Di mana data disimpan

| Lokasi | Isi | Catatan |
|---|---|---|
| Cloudflare R2 | audio/video sementara | bucket privat; lokasi bucket dipilih di TK-003 **`[ISI LOKASI]`** |
| VPS pengelola | basis data job, transkrip, metadata | penyedia dan negara **`[ISI PENYEDIA/NEGARA]`** (T-08) |
| Laptop pekerja | berkas kerja sementara selama inferensi | dihapus segera setelah job selesai |
| Cloudflare Pages | antarmuka web statis | tidak menyimpan audio |

Audio dan transkrip dapat melewati batas negara karena R2 dan VPS berada di
yurisdiksi yang berbeda. Konsekuensi hukum transfer lintas negara masih
menunggu telaah (T-12).

## 5. Berapa lama disimpan

| Data | Lama simpan |
|---|---|
| Audio/video di R2 | ≤ 24 jam setelah job selesai, gagal, kedaluwarsa, atau dibatalkan |
| Berkas kerja di laptop | segera setelah job selesai |
| Transkrip dan segmen | 30 hari, atau lebih cepat bila Anda menghapusnya |
| Cadangan basis data | ≤ 7 hari; penghapusan baru hilang dari cadangan paling lambat 7 hari kemudian |
| Catatan persetujuan dan audit | dipertahankan tanpa isi pribadi sebagai bukti |

Jaring pengaman: aturan lifecycle R2 7 hari bila penghapus otomatis gagal.

## 6. Pelabelan pembicara

Bila Anda memilih "Pisahkan pembicara", sistem membuat label anonim
("Pembicara 1", "Pembicara 2", ...). Ciri suara hanya dipakai di memori selama
job berjalan dan **tidak disimpan**. Sistem tidak mengenali orang yang sama
pada rekaman berbeda dan tidak membuat sidik suara.

Apakah ciri suara sementara tetap dihitung sebagai data biometrik menurut UU
PDP masih menunggu telaah hukum (T-12). Kami akan memperbarui pemberitahuan ini
bila hasil telaah menyatakan demikian.

## 7. Berbagi data

Kami tidak menjual data dan tidak memakainya untuk melatih model. Data hanya
diproses oleh penyedia infrastruktur yang diperlukan:

- Cloudflare (R2, Pages, Turnstile, DNS/WAF),
- penyedia VPS **`[ISI NAMA]`**,
- tidak ada iklan atau analitik pihak ketiga.

## 8. Hak Anda

Anda dapat meminta akses, salinan (ekspor), penghapusan, atau menarik
persetujuan. Permintaan dipenuhi **≤ 3 × 24 jam**. Karena tidak ada akun,
permintaan diverifikasi memakai ID job atau tautan job yang Anda simpan.

Menarik persetujuan tidak membatalkan pemrosesan yang sudah selesai, tetapi
kami berhenti memproses data baru dan menghapus data yang masih tersimpan.

## 9. Anak

Layanan hanya untuk pengguna **≥ 18 tahun**. Kami tidak dengan sengaja
memproses data anak. Bila hal itu terjadi, hubungi kontak privasi untuk
penghapusan.

## 10. Keamanan dan kebocoran

Akses ke R2, VPS, dan laptop pekerja dibatasi. Bila terjadi kebocoran data yang
berisiko bagi Anda, kami memberi tahu **≤ 3 × 24 jam** dan mencatat tindakan
pemulihan. Prosedur lengkap: `docs/runbook/insiden-kebocoran.md`.

## 11. Perubahan

Perubahan penting diberi versi baru dan ditampilkan sebelum unggahan
berikutnya. Versi yang Anda setujui tercatat di basis data.

## 12. Daftar klaim yang harus diverifikasi

Lihat `docs/privasi/verifikasi-hukum.md`. Butir yang masih terbuka ditandai
`[VERIFIKASI]` dan tidak boleh dianggap nasihat hukum.
