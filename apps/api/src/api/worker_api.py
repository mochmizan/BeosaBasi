"""TK-025: worker API — claim, heartbeat, result, fail, ping (PRD 4.7).

Security: bearer token only (hash stored at rest). Claims are atomic (one
UPDATE ... RETURNING). Leases are 5 minutes; a stopped worker's job returns to
the queue and `percobaan` grows, failing after 3 attempts.
"""

from __future__ import annotations

import asyncio
import sqlite3
import time
from datetime import timedelta

from fastapi import APIRouter, Depends, Query, Response

from api import dal, schemas
from api.config import Settings
from api.db import transaction
from api.deps import db_conn, get_settings, get_storage, worker_identity
from api.errors import ApiError
from api.state import charge_quota, transition
from api.storage import Storage, StorageError
from api.timeutil import iso, utcnow
from api.views import worker_job_or_404

router = APIRouter(prefix="/worker/v1", tags=["worker"])

PESAN_GUDANG = "Penyimpanan audio sedang tidak tersedia. Coba lagi sebentar."


def _lease_until(settings: Settings) -> str:
    return iso(utcnow() + timedelta(seconds=settings.lease_seconds))


def _version_tuple(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in value.split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _version_older(actual: str, minimum: str) -> bool:
    return _version_tuple(actual) < _version_tuple(minimum)


@router.post("/jobs/claim", response_model=schemas.ClaimResponse)
async def claim_job(wait: int = Query(default=25, ge=0, le=25),
                    conn: sqlite3.Connection = Depends(db_conn),
                    worker: dict = Depends(worker_identity),
                    settings: Settings = Depends(get_settings),
                    storage: Storage = Depends(get_storage)):
    worker_id = worker["id"]
    dal.worker_register(conn, worker_id=worker_id, nama=worker_id,
                        token_hash=worker["token_hash"],
                        terakhir_terlihat=iso(utcnow()),
                        versi=worker.get("versi", ""))
    deadline = time.monotonic() + min(wait, settings.claim_max_wait_seconds)
    job = None
    last_sweep = 0.0
    while True:
        now_monotonic = time.monotonic()
        if now_monotonic - last_sweep >= 5.0:
            dal.requeue_expired_leases(conn, iso(utcnow()), settings.max_attempts)
            last_sweep = now_monotonic
        job = dal.claim_job(conn, worker_id=worker_id,
                            lease_sampai=_lease_until(settings))
        if job is not None:
            break
        if now_monotonic >= deadline:
            return Response(status_code=204)
        await asyncio.sleep(0.5)

    dal.worker_touch(conn, worker_id, iso(utcnow()))
    try:
        audio_url, expires = storage.sign_get(job["r2_key"],
                                              settings.presign_ttl_seconds)
    except StorageError as exc:
        dal.job_set_state(conn, job["id"], "queued", worker_id=None,
                          lease_sampai=None)
        raise ApiError(503, "INTERNAL", PESAN_GUDANG) from exc

    return schemas.ClaimResponse(
        job_id=job["id"],
        audio_url=audio_url,
        audio_expires_at=iso(expires),
        language=job["bahasa"],
        diarization=bool(job["diarisasi"]),
        min_speakers=job.get("min_pembicara"),
        max_speakers=job.get("maks_pembicara"),
        lease_until=job["lease_sampai"],
    )


@router.post("/jobs/{job_id}/heartbeat", response_model=schemas.HeartbeatResponse)
def heartbeat(job_id: str, body: schemas.Heartbeat,
              conn: sqlite3.Connection = Depends(db_conn),
              worker: dict = Depends(worker_identity),
              settings: Settings = Depends(get_settings),
              ) -> schemas.HeartbeatResponse:
    job = worker_job_or_404(conn, job_id)
    if job["state"] in {"cancelled", "deleted"}:
        return schemas.HeartbeatResponse(cancel=True, lease_until=job["lease_sampai"]
                                         or iso(utcnow()))
    if job["state"] != "processing" or job["worker_id"] != worker["id"]:
        raise ApiError(409, "LEASE_LOST")
    lease = _lease_until(settings)
    renewed = dal.heartbeat_renew(conn, job_id, worker["id"], lease,
                                  body.stage.value
                                  if hasattr(body.stage, "value") else str(body.stage))
    if not renewed:
        raise ApiError(409, "LEASE_LOST")
    return schemas.HeartbeatResponse(cancel=False, lease_until=lease)


def _validate_result(body: schemas.WorkerResult) -> None:
    seen: set[int] = set()
    for seg in body.segments:
        if seg.index in seen:
            raise ApiError(400, "INVALID_FILE", "Indeks segmen duplikat.")
        seen.add(seg.index)
        if seg.end < seg.start:
            raise ApiError(400, "INVALID_FILE",
                           "Penanda waktu segmen tidak valid.")
    speakers = {s.speaker_id for s in (body.speakers or [])}
    for seg in body.segments:
        if seg.speaker_id and speakers and seg.speaker_id not in speakers:
            raise ApiError(400, "INVALID_FILE",
                           "Segmen menunjuk pembicara yang tidak dikirim.")


@router.post("/jobs/{job_id}/result", response_model=schemas.Ack)
def submit_result(job_id: str, body: schemas.WorkerResult,
                  conn: sqlite3.Connection = Depends(db_conn),
                  worker: dict = Depends(worker_identity),
                  settings: Settings = Depends(get_settings)) -> schemas.Ack:
    job = worker_job_or_404(conn, job_id)
    if job["state"] in {"cancelled", "deleted"}:
        return schemas.Ack(ok=True)  # user cancelled: discard text, send nothing
    if job["state"] != "processing" or job["worker_id"] != worker["id"]:
        raise ApiError(409, "LEASE_LOST")
    _validate_result(body)

    now = utcnow()
    now_iso = iso(now)
    speakers = body.speakers or []
    diarization_available = bool(speakers) and bool(
        body.diarization_available if body.diarization_available is not None else True)
    with transaction(conn):
        dal.segment_delete_all(conn, job_id)
        for seg in sorted(body.segments, key=lambda s: s.index):
            dal.segment_upsert(
                conn,
                job_id=job_id,
                urut=seg.index,
                mulai=seg.start,
                selesai=seg.end,
                teks=seg.text,
                keyakinan=seg.confidence,
                speaker_id=seg.speaker_id,
                disunting=0,
                versi=1,
            )
        if diarization_available:
            for speaker in speakers:
                dal.speaker_upsert(
                    conn,
                    job_id=job_id,
                    speaker_id=speaker.speaker_id,
                    label_asli=speaker.label,
                    nama_tampil=speaker.display_name or speaker.label,
                )
        charge_quota(conn, job, duration_seconds=body.duration_seconds,
                     diarization_available=diarization_available,
                     settings=settings, now=now)
        total_chars = sum(len(seg.text) for seg in body.segments)
        dal.metrics_upsert(
            conn, job_id=job_id, xrt=body.xrt,
            low_confidence_ratio=body.low_confidence_ratio,
            worker_seconds=body.duration_seconds / body.xrt if body.xrt else None,
            model_version=body.model_version,
            total_chars=total_chars,
            dikirim_pada=now_iso,
        )
        transition(conn, job, "completed",
                   durasi_detik=body.duration_seconds,
                   versi_model=body.model_version,
                   selesai_pada=now_iso,
                   kode_galat=None,
                   worker_id=None,
                   lease_sampai=None)
        if job["diarisasi"] and not diarization_available:
            dal.audit_add(conn, waktu=now_iso, user_id=job["user_id"],
                          jenis="diarisasi_gagal", job_id=job_id)
        dal.audit_add(conn, waktu=now_iso, user_id=job["user_id"],
                      jenis="job_selesai", job_id=job_id)
    return schemas.Ack(ok=True)


@router.post("/jobs/{job_id}/fail", response_model=schemas.Ack)
def submit_fail(job_id: str, body: schemas.WorkerFail,
                conn: sqlite3.Connection = Depends(db_conn),
                worker: dict = Depends(worker_identity),
                settings: Settings = Depends(get_settings)) -> schemas.Ack:
    job = worker_job_or_404(conn, job_id)
    if job["state"] in {"cancelled", "deleted"}:
        return schemas.Ack(ok=True)
    if job["state"] != "processing" or job["worker_id"] != worker["id"]:
        raise ApiError(409, "LEASE_LOST")

    now_iso = iso(utcnow())
    code = body.code.value if hasattr(body.code, "value") else str(body.code)
    can_retry = body.retryable and int(job["percobaan"]) < settings.max_attempts
    with transaction(conn):
        if can_retry:
            transition(conn, job, "queued", worker_id=None, lease_sampai=None,
                       kode_galat=code)
        else:
            transition(conn, job, "failed", kode_galat=code,
                       selesai_pada=now_iso, worker_id=None, lease_sampai=None)
        dal.audit_add(conn, waktu=now_iso, user_id=job["user_id"],
                      jenis="job_gagal", job_id=job_id)
    return schemas.Ack(ok=True)


@router.post("/ping", response_model=schemas.WorkerPingResponse)
def ping(body: schemas.WorkerPing,
         conn: sqlite3.Connection = Depends(db_conn),
         worker: dict = Depends(worker_identity),
         settings: Settings = Depends(get_settings)) -> schemas.WorkerPingResponse:
    now_iso = iso(utcnow())
    token_hash = worker["token_hash"]
    if worker.get("raw_token"):
        # Shared env token: keep one unique hash per declared worker id.
        from api.identity import hash_token

        token_hash = hash_token(f"{worker['raw_token']}:{body.worker_id}")
    dal.worker_register(conn, worker_id=body.worker_id, nama=body.worker_id,
                        token_hash=token_hash,
                        terakhir_terlihat=now_iso, versi=body.version)
    update_required = _version_older(body.version, settings.worker_min_version)
    return schemas.WorkerPingResponse(ok=not update_required,
                                      min_version=settings.worker_min_version,
                                      update_required=update_required)
