// Pesan galat standar berbahasa Indonesia (TK-040).
// Sumber: contracts/worker-protocol.md tabel KodeGalat + contracts/openapi.yaml.
// Dipakai seluruh halaman web agar pesan konsisten.

import type { KodeGalat } from "../api-types";

export const PESAN_GALAT: Record<KodeGalat, string> = {
  INVALID_FILE: "Berkas tidak dikenali. Unggah MP3, M4A, WAV, FLAC, OGG/Opus, MP4, atau WebM.",
  UNSUPPORTED_TYPE: "Tipe berkas belum didukung.",
  TOO_LARGE: "Berkas melebihi 200 MB.",
  TOO_LONG: "Audio melebihi 90 menit.",
  NO_AUDIO_STREAM: "Berkas tidak berisi audio.",
  CORRUPT_MEDIA: "Berkas rusak dan tidak bisa diproses. Coba ekspor ulang.",
  QUOTA_EXCEEDED: "Kuota hari ini habis. Coba lagi setelah tengah malam WIB.",
  TOO_MANY_ACTIVE_JOBS: "Maksimal 2 pekerjaan bersamaan. Tunggu satu selesai dulu.",
  CONSENT_REQUIRED: "Beri persetujuan privasi dulu sebelum mengunggah.",
  ALLOWLIST_REQUIRED: "Akun belum terdaftar di pilot tertutup.",
  WORKER_OFFLINE: "Pemrosesan tertunda karena perangkat mati. Job aman dan jalan otomatis saat perangkat aktif.",
  LEASE_LOST: "Pekerjaan dihentikan karena dibatalkan.",
  GPU_OOM: "Perangkat kehabisan memori GPU. Coba berkas lebih pendek.",
  DIARIZATION_FAILED: "Label pembicara tidak tersedia, transkrip tetap diberikan. Kuota tambahan dikembalikan.",
  FFMPEG_ERROR: "Gagal menyiapkan audio. Coba format lain.",
  JOB_TIMEOUT: "Pemrosesan terlalu lama dan dihentikan.",
  JOB_EXPIRED: "Pekerjaan kedaluwarsa karena perangkat lama mati. Unggah ulang.",
  VERSION_CONFLICT: "Segmen diubah di tempat lain. Muat ulang lalu sunting lagi.",
  AUDIO_GONE: "Audio sudah dihapus sesuai kebijakan retensi. Transkrip tetap bisa disunting.",
  INTERNAL: "Terjadi galat. Coba lagi, lapor bila berulang.",
};

export const PESAN_JARINGAN =
  "Tidak dapat menghubungi server. Periksa koneksi lalu coba lagi.";

export function pesanUntukKode(code: KodeGalat | undefined | null): string {
  if (code !== undefined && code !== null && code in PESAN_GALAT) {
    return PESAN_GALAT[code];
  }
  return PESAN_GALAT.INTERNAL;
}

/** Pesan baku untuk status HTTP tanpa badan galat kontrak. */
export function pesanUntukStatus(status: number): string {
  if (status === 401) return "Sesi berakhir. Masuk kembali.";
  if (status === 403) return "Akses ditolak untuk akun ini.";
  if (status === 404) return "Tidak ditemukan.";
  if (status === 409) return PESAN_GALAT.VERSION_CONFLICT;
  if (status >= 500) return PESAN_GALAT.INTERNAL;
  return PESAN_GALAT.INTERNAL;
}

/** Galat API: selalu membawa pesan Indonesia siap tampil. */
export class ApiError extends Error {
  readonly status: number;
  readonly code?: KodeGalat;

  constructor(status: number, message: string, code?: KodeGalat) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

/** Ubah nilai tak dikenal (catch) menjadi pesan Indonesia. */
export function pesanGalat(value: unknown): string {
  if (value instanceof ApiError) return value.message;
  if (value instanceof Error) return value.message;
  return PESAN_GALAT.INTERNAL;
}
