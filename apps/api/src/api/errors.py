"""Standard error envelope (contract: {code, message} in Bahasa Indonesia)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# Human-friendly Indonesian messages (contracts/worker-protocol.md, TK-001).
PESAN: dict[str, str] = {
    "INVALID_FILE": (
        "Berkas tidak dikenali. Unggah MP3, M4A, WAV, FLAC, OGG/Opus, MP4, atau WebM."
    ),
    "UNSUPPORTED_TYPE": "Tipe berkas belum didukung.",
    "TOO_LARGE": "Berkas melebihi 200 MB.",
    "TOO_LONG": "Audio melebihi 90 menit.",
    "NO_AUDIO_STREAM": "Berkas tidak berisi audio.",
    "CORRUPT_MEDIA": "Berkas rusak dan tidak bisa diproses. Coba ekspor ulang.",
    "QUOTA_EXCEEDED": "Kuota hari ini habis. Coba lagi setelah tengah malam WIB.",
    "TOO_MANY_ACTIVE_JOBS": (
        "Maksimal 2 pekerjaan bersamaan. Tunggu satu selesai dulu."
    ),
    "CONSENT_REQUIRED": "Beri persetujuan privasi dulu sebelum mengunggah.",
    "ALLOWLIST_REQUIRED": "Akun belum terdaftar di pilot tertutup.",
    "WORKER_OFFLINE": (
        "Pemrosesan tertunda karena perangkat mati. Job aman dan jalan otomatis "
        "saat perangkat aktif."
    ),
    "LEASE_LOST": "Pekerjaan dihentikan karena dibatalkan.",
    "GPU_OOM": "Perangkat kehabisan memori GPU. Coba berkas lebih pendek.",
    "DIARIZATION_FAILED": (
        "Label pembicara tidak tersedia, transkrip tetap diberikan. "
        "Kuota tambahan dikembalikan."
    ),
    "FFMPEG_ERROR": "Gagal menyiapkan audio. Coba format lain.",
    "JOB_TIMEOUT": "Pemrosesan terlalu lama dan dihentikan.",
    "JOB_EXPIRED": "Pekerjaan kedaluwarsa karena perangkat lama mati. Unggah ulang.",
    "VERSION_CONFLICT": "Segmen diubah di tempat lain. Muat ulang lalu sunting lagi.",
    "AUDIO_GONE": (
        "Audio sudah dihapus sesuai kebijakan retensi. Transkrip tetap bisa disunting."
    ),
    "INTERNAL": "Terjadi galat. Coba lagi, lapor bila berulang.",
}


class ApiError(Exception):
    """Raised by routers; turned into the contract error envelope."""

    def __init__(self, status_code: int, code: str, message: str | None = None) -> None:
        super().__init__(message or PESAN.get(code, PESAN["INTERNAL"]))
        self.status_code = status_code
        self.code = code
        self.message = message or PESAN.get(code, PESAN["INTERNAL"])


def error_body(code: str, message: str | None = None) -> dict[str, str]:
    return {"code": code, "message": message or PESAN.get(code, PESAN["INTERNAL"])}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code,
                            content=error_body(exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Do not echo the payload: it may contain filenames or transcript text.
        errors = exc.errors()
        first = errors[0].get("loc", []) if errors else []
        # Contract caps size at 200 MB; give the specific PRD message instead
        # of a generic validation complaint.
        if any(e.get("loc", [])[-1:] == ["size_bytes"]
               and e.get("type") == "less_than_equal" for e in errors):
            return JSONResponse(status_code=400,
                                content=error_body("TOO_LARGE"))
        lokasi = ".".join(str(p) for p in first if p not in ("body", "query", "path"))
        pesan = "Badan permintaan tidak valid"
        if lokasi:
            pesan = f"Badan permintaan tidak valid pada {lokasi}."
        return JSONResponse(status_code=400,
                            content=error_body("INVALID_FILE", pesan))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {401: "INTERNAL", 404: "INTERNAL", 409: "VERSION_CONFLICT"}.get(
            exc.status_code, "INTERNAL"
        )
        detail = exc.detail if isinstance(exc.detail, str) else None
        return JSONResponse(status_code=exc.status_code,
                            content=error_body(code, detail))
