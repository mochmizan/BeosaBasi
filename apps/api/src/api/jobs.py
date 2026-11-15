"""TK-024: job lifecycle, quota, queue position/ETA, deletion (PRD 4.5)."""

from __future__ import annotations

import sqlite3
from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from fastapi import Response as HttpResponse

from api import dal, schemas
from api.config import Settings
from api.db import transaction
from api.deps import db_conn, get_settings, get_storage, identity
from api.errors import ApiError
from api.identity import Identity
from api.retention import purge_assets, purge_now
from api.state import eta_seconds, quota_remaining, transition
from api.storage import Storage, StorageError
from api.timeutil import iso, utcnow
from api.views import job_model, job_or_404, job_summary_model

router = APIRouter(prefix="/api", tags=["jobs"])


def _worker_active(conn, settings: Settings, now=None) -> bool:
    moment = now or utcnow()
    cutoff = iso(moment - timedelta(seconds=settings.worker_offline_seconds))
    return any(w["terakhir_terlihat"] >= cutoff for w in dal.workers_list(conn))


def _encode_cursor(row: dict) -> str:
    return f"{row['dibuat_pada']}|{row['id']}"


def _decode_cursor(cursor: str) -> tuple[str, str]:
    if "|" not in cursor:
        raise ApiError(400, "INVALID_FILE", "Kursor tidak valid.")
    created, job_id = cursor.split("|", 1)
    if not created or not job_id:
        raise ApiError(400, "INVALID_FILE", "Kursor tidak valid.")
    return created, job_id


@router.get("/me", response_model=schemas.Me)
def get_me(conn: sqlite3.Connection = Depends(db_conn),
           ident: Identity = Depends(identity),
           settings: Settings = Depends(get_settings)) -> schemas.Me:
    return schemas.Me(
        user_id=ident.user_id,
        email="anonim@tanpa-login.invalid",
        quota_minutes_remaining=round(
            quota_remaining(conn, ident.ip_hash, settings), 1),
        active_jobs=dal.job_active_count(conn, ident.user_id),
        consent=None,
    )


@router.delete("/me", response_model=schemas.Accepted, status_code=202)
def delete_me(response: HttpResponse,
              conn: sqlite3.Connection = Depends(db_conn),
              ident: Identity = Depends(identity),
              settings: Settings = Depends(get_settings),
              storage: Storage = Depends(get_storage)) -> schemas.Accepted:
    moment = utcnow()
    for job in dal.jobs_for_user_all(conn, ident.user_id):
        session = dal.upload_session_get(conn, job["id"])
        if session is not None and not session["selesai_pada"]:
            try:
                storage.abort_multipart(job["r2_key"], session["upload_id"])
            except StorageError:
                pass
        with transaction(conn):
            fresh = dal.job_get(conn, job["id"])
            if fresh is not None:
                purge_now(conn, storage, fresh)
        dal.audit_add(conn, waktu=iso(moment), user_id=None,
                      jenis="akun_dihapus")
    dal.anon_session_delete_user(conn, ident.user_id)
    dal.user_delete(conn, ident.user_id)
    response.delete_cookie(settings.cookie_name, path="/")
    return schemas.Accepted(scheduled=True, purge_at=iso(moment))


@router.get("/jobs", response_model=schemas.JobList)
def list_jobs(status: str | None = Query(default=None),
              limit: int = Query(default=20, ge=1, le=50),
              cursor: str | None = Query(default=None),
              conn: sqlite3.Connection = Depends(db_conn),
              ident: Identity = Depends(identity)) -> schemas.JobList:
    if status is not None and status not in set(schemas.JobState):
        raise ApiError(400, "INVALID_FILE", "Status tidak dikenal.")
    created, cursor_id = _decode_cursor(cursor) if cursor else (None, None)
    rows = dal.jobs_page(conn, ident.user_id, limit=limit + 1, status=status,
                         cursor_created=created, cursor_id=cursor_id)
    has_more = len(rows) > limit
    page = rows[:limit]
    return schemas.JobList(
        jobs=[job_summary_model(row) for row in page],
        next_cursor=_encode_cursor(page[-1]) if has_more and page else None,
    )


@router.get("/jobs/{job_id}", response_model=schemas.JobDetail)
def get_job(job_id: str,
            conn: sqlite3.Connection = Depends(db_conn),
            ident: Identity = Depends(identity),
            settings: Settings = Depends(get_settings)) -> schemas.JobDetail:
    job = job_or_404(conn, job_id, ident.user_id)
    position = None
    if job["state"] == "queued":
        position = dal.job_queue_ahead(conn, job) + 1
    return schemas.JobDetail(
        job=job_model(job),
        queue_position=position,
        eta_seconds=eta_seconds(conn, job),
        worker_active=_worker_active(conn, settings),
    )


@router.delete("/jobs/{job_id}", response_model=schemas.Accepted, status_code=202)
def delete_job(job_id: str,
               conn: sqlite3.Connection = Depends(db_conn),
               ident: Identity = Depends(identity),
               storage: Storage = Depends(get_storage)) -> schemas.Accepted:
    job = job_or_404(conn, job_id, ident.user_id)
    moment = utcnow()
    now_iso = iso(moment)

    if job["state"] == "processing":
        # Let the worker learn about the cancellation at its next heartbeat
        # (contract: cancel=true), then purge shortly after.
        purge_at = iso(moment + timedelta(seconds=90))
        with transaction(conn):
            transition(conn, job, "cancelled", selesai_pada=now_iso,
                       hapus_transkrip_pada=purge_at)
            dal.audit_add(conn, waktu=now_iso, user_id=ident.user_id,
                          jenis="job_dibatalkan", job_id=job_id)
        return schemas.Accepted(scheduled=True, purge_at=purge_at)

    session = dal.upload_session_get(conn, job_id)
    if session is not None and not session["selesai_pada"]:
        try:
            storage.abort_multipart(job["r2_key"], session["upload_id"])
        except StorageError:
            pass
    with transaction(conn):
        dal.audit_add(conn, waktu=now_iso, user_id=ident.user_id,
                      jenis="job_dihapus", job_id=job_id)
        fresh = dal.job_get(conn, job_id)
        if fresh is not None:
            purge_assets(conn, storage, fresh)
            dal.job_delete(conn, job_id)
    return schemas.Accepted(scheduled=True, purge_at=now_iso)
