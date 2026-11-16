"""TK-023: anonymous multipart uploads straight to R2/Garage (PRD 4.6).

Limits are checked before any upload starts: 200 MB, 90 min implied by size
and checked by the worker, 8 MiB parts, allowed containers. Object keys never
contain the original filename. Completion performs the light check (size +
magic bytes) and moves the job to `queued`.
"""

from __future__ import annotations

import math
import sqlite3
import uuid

import httpx
from fastapi import APIRouter, Depends
from fastapi import Response as HttpResponse

from api import dal, ratelimit, schemas
from api.config import ALLOWED_CONTENT_TYPES, ALLOWED_EXTENSIONS, Settings
from api.db import transaction
from api.deps import db_conn, get_settings, get_storage, identity
from api.errors import ApiError
from api.identity import Identity
from api.state import quota_remaining, transition
from api.storage import PartInfo, Storage, StorageError, extension_of, sniff_container
from api.timeutil import iso, next_reset, utcnow
from api.views import job_model, job_or_404

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

PESAN_GUDANG = "Penyimpanan audio sedang tidak tersedia. Coba lagi sebentar."


def _normalize_mime(content_type: str) -> str:
    """Strip codec parameters (e.g. audio/webm;codecs=opus -> audio/webm)."""
    return (content_type or "").split(";", 1)[0].strip().lower()


def _verify_turnstile(token: str, settings: Settings) -> None:
    if not token or not token.strip():
        raise ApiError(400, "INVALID_FILE", "Verifikasi Turnstile diperlukan.")
    if not settings.turnstile_secret:
        return  # dev stub (TK-002): a token must be present but is not checked
    try:
        resp = httpx.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={"secret": settings.turnstile_secret, "response": token},
            timeout=5.0,
        )
        ok = bool(resp.json().get("success"))
    except (httpx.HTTPError, ValueError) as exc:
        raise ApiError(503, "INTERNAL", "Verifikasi Turnstile tidak tersedia. "
                                        "Coba lagi.") from exc
    if not ok:
        raise ApiError(403, "INTERNAL",
                       "Verifikasi Turnstile gagal. Muat ulang halaman lalu coba lagi.")


def _validate_init(body: schemas.UploadInit, settings: Settings) -> str:
    extension = extension_of(body.filename)
    if extension not in ALLOWED_EXTENSIONS:
        raise ApiError(400, "UNSUPPORTED_TYPE")
    mime = _normalize_mime(body.content_type)
    if mime not in ALLOWED_CONTENT_TYPES:
        raise ApiError(400, "UNSUPPORTED_TYPE")
    if body.size_bytes > settings.max_upload_bytes:
        raise ApiError(400, "TOO_LARGE",
                       f"Berkas melebihi {settings.max_upload_bytes // (1024 * 1024)} MB.")
    if body.size_bytes <= 0:
        raise ApiError(400, "INVALID_FILE", "Berkas kosong.")
    if body.language not in {"id", "en", "auto"}:
        raise ApiError(400, "INVALID_FILE", "Pilihan bahasa tidak dikenal.")
    for value in (body.min_speakers, body.max_speakers):
        if value is not None and not 1 <= value <= 8:
            raise ApiError(400, "INVALID_FILE", "Jumlah pembicara harus 1 sampai 8.")
    if (body.min_speakers and body.max_speakers
            and body.min_speakers > body.max_speakers):
        raise ApiError(400, "INVALID_FILE",
                       "Jumlah pembicara minimum melebihi maksimum.")
    return mime


@router.post("", response_model=schemas.UploadSession, status_code=201)
def init_upload(body: schemas.UploadInit, response: HttpResponse,
                conn: sqlite3.Connection = Depends(db_conn),
                ident: Identity = Depends(identity),
                settings: Settings = Depends(get_settings),
                storage: Storage = Depends(get_storage)) -> schemas.UploadSession:
    del response
    mime = _validate_init(body, settings)
    _verify_turnstile(body.turnstile_token, settings)
    ratelimit.enforce(conn, f"upload:{ident.ip_hash}",
                      settings.upload_initiations_per_hour)

    remaining = quota_remaining(conn, ident.ip_hash, settings)
    if remaining <= 0:
        reset = next_reset(utcnow()).strftime("%d-%m-%Y %H:%M WIB")
        raise ApiError(403, "QUOTA_EXCEEDED",
                       f"Kuota hari ini habis. Kuota pulih pada {reset}.")
    if dal.job_active_count(conn, ident.user_id) >= settings.max_active_jobs:
        raise ApiError(403, "TOO_MANY_ACTIVE_JOBS",
                       f"Maksimal {settings.max_active_jobs} pekerjaan bersamaan. "
                       "Tunggu satu selesai dulu.")
    if dal.job_storage_bytes(conn) + body.size_bytes > settings.global_storage_cap_bytes:
        raise ApiError(503, "INTERNAL",
                       "Penyimpanan sementara penuh. Coba lagi beberapa saat lagi.")

    job_id = str(uuid.uuid4())
    key = f"uploads/{ident.user_id}/{job_id}"
    part_size = settings.part_size
    part_count = max(1, math.ceil(body.size_bytes / part_size))
    try:
        upload_id = storage.create_multipart(key, mime)
    except StorageError as exc:
        raise ApiError(503, "INTERNAL", PESAN_GUDANG) from exc

    now_iso = iso(utcnow())
    try:
        with transaction(conn):
            dal.job_create(
                conn,
                job_id=job_id,
                user_id=ident.user_id,
                state="uploading",
                dibuat_pada=now_iso,
                nama_berkas_asli=body.filename,
                r2_key=key,
                ukuran_byte=body.size_bytes,
                bahasa=body.language,
                diarisasi=1 if body.diarization else 0,
                min_pembicara=body.min_speakers,
                maks_pembicara=body.max_speakers,
            )
            dal.upload_session_create(
                conn, job_id=job_id, upload_id=upload_id,
                part_size=part_size, part_count=part_count,
                dibuat_pada=now_iso,
            )
            dal.audit_add(conn, waktu=now_iso, user_id=ident.user_id,
                          jenis="unggah_dimulai", job_id=job_id)
    except Exception:
        try:
            storage.abort_multipart(key, upload_id)
        except StorageError:
            pass
        raise
    return schemas.UploadSession(job_id=job_id, upload_id=upload_id,
                                 part_size=part_size, part_count=part_count)


@router.post("/{job_id}/parts", response_model=schemas.PartSignResponse)
def sign_part(job_id: str, body: schemas.PartSignRequest,
              conn: sqlite3.Connection = Depends(db_conn),
              ident: Identity = Depends(identity),
              settings: Settings = Depends(get_settings),
              storage: Storage = Depends(get_storage)) -> schemas.PartSignResponse:
    job = job_or_404(conn, job_id, ident.user_id)
    session = dal.upload_session_get(conn, job_id)
    if session is None or job["state"] != "uploading":
        raise ApiError(409, "INTERNAL", "Unggahan ini sudah selesai atau dibatalkan.")
    if not 1 <= body.part_number <= int(session["part_count"]):
        raise ApiError(400, "INVALID_FILE", "Nomor potongan di luar rentang.")
    try:
        url, expires = storage.sign_part(job["r2_key"], session["upload_id"],
                                         body.part_number,
                                         settings.presign_ttl_seconds)
    except StorageError as exc:
        raise ApiError(503, "INTERNAL", PESAN_GUDANG) from exc
    return schemas.PartSignResponse(url=url, expires_at=iso(expires))


@router.get("/{job_id}", response_model=schemas.UploadStatus)
def upload_status(job_id: str,
                  conn: sqlite3.Connection = Depends(db_conn),
                  ident: Identity = Depends(identity),
                  storage: Storage = Depends(get_storage)) -> schemas.UploadStatus:
    job = job_or_404(conn, job_id, ident.user_id)
    session = dal.upload_session_get(conn, job_id)
    if session is None:
        raise ApiError(404, "INTERNAL", "Sesi unggah tidak ditemukan.")
    if session["selesai_pada"]:
        done = list(range(1, int(session["part_count"]) + 1))
    else:
        try:
            done = [p.part_number for p in
                    storage.list_parts(job["r2_key"], session["upload_id"])]
        except StorageError as exc:
            raise ApiError(503, "INTERNAL", PESAN_GUDANG) from exc
    return schemas.UploadStatus(job_id=job_id, state=job["state"],
                                parts_done=done,
                                parts_total=int(session["part_count"]))


def _fail_after_complete(conn, storage: Storage, job: dict, code: str,
                         message: str) -> None:
    """Light check failed after CompleteMultipartUpload: drop bytes, fail job."""
    now_iso = iso(utcnow())
    try:
        storage.delete(job["r2_key"])
    except StorageError:
        pass
    with transaction(conn):
        dal.upload_session_delete(conn, job["id"])
        transition(conn, job, "failed", kode_galat=code, selesai_pada=now_iso,
                   audio_dihapus_pada=now_iso)
        dal.audit_add(conn, waktu=now_iso, user_id=job["user_id"],
                      jenis="unggah_ditolak", job_id=job["id"])
    raise ApiError(400, code, message)


@router.post("/{job_id}/complete", response_model=schemas.Job)
def complete_upload(job_id: str, body: schemas.UploadComplete,
                    conn: sqlite3.Connection = Depends(db_conn),
                    ident: Identity = Depends(identity),
                    settings: Settings = Depends(get_settings),
                    storage: Storage = Depends(get_storage)) -> schemas.Job:
    job = job_or_404(conn, job_id, ident.user_id)
    session = dal.upload_session_get(conn, job_id)
    if session is None or job["state"] != "uploading":
        raise ApiError(409, "INTERNAL", "Unggahan ini sudah selesai atau dibatalkan.")

    try:
        actual = {p.part_number: p for p in
                  storage.list_parts(job["r2_key"], session["upload_id"])}
    except StorageError as exc:
        raise ApiError(503, "INTERNAL", PESAN_GUDANG) from exc
    if not actual:
        raise ApiError(400, "INVALID_FILE",
                       "Belum ada potongan yang terunggah. Ulangi unggahan.")

    received: dict[int, str] = {}
    for part in body.parts:
        received[part.part_number] = part.etag.strip().strip('"')
    expected = set(range(1, int(session["part_count"]) + 1))
    if set(received) != expected:
        raise ApiError(400, "INVALID_FILE",
                       "Daftar potongan tidak lengkap. Lanjutkan unggahan dulu.")
    chosen: list[PartInfo] = []
    for number in sorted(expected):
        server = actual.get(number)
        if server is None:
            raise ApiError(400, "INVALID_FILE",
                           "Potongan belum terunggah. Lanjutkan unggahan dulu.")
        if server.etag.strip('"') != received[number]:
            raise ApiError(400, "INVALID_FILE",
                           "Potongan tidak cocok. Ulangi unggahan dari potongan terakhir.")
        chosen.append(server)

    try:
        storage.complete_multipart(job["r2_key"], session["upload_id"], chosen)
        info = storage.head(job["r2_key"])
    except StorageError as exc:
        raise ApiError(503, "INTERNAL", PESAN_GUDANG) from exc
    if info is None:
        raise ApiError(503, "INTERNAL", PESAN_GUDANG)
    if info.size > settings.max_upload_bytes:
        _fail_after_complete(conn, storage, job, "TOO_LARGE",
                             "Berkas melebihi batas 200 MB.")
    if info.size != int(job["ukuran_byte"]):
        _fail_after_complete(conn, storage, job, "INVALID_FILE",
                             "Ukuran berkas tidak cocok dengan yang didaftarkan.")
    try:
        prefix = storage.read_prefix(job["r2_key"], 65536)
    except StorageError as exc:
        raise ApiError(503, "INTERNAL", PESAN_GUDANG) from exc
    if sniff_container(prefix) is None:
        _fail_after_complete(
            conn, storage, job, "INVALID_FILE",
            "Berkas tidak dikenali. Unggah MP3, M4A, WAV, FLAC, OGG/Opus, "
            "MP4, atau WebM.",
        )

    now_iso = iso(utcnow())
    with transaction(conn):
        dal.upload_session_complete(conn, job_id, now_iso)
        transition(conn, job, "queued", kode_galat=None)
        dal.audit_add(conn, waktu=now_iso, user_id=job["user_id"],
                      jenis="unggah_selesai", job_id=job_id)
    refreshed = dal.job_get(conn, job_id)
    return job_model(refreshed or job)
