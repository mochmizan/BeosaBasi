"""TK-028: retention and deletion (PRD 4.12, K4).

Sweeps (every 30 s by default, cheap queries):
- expired worker leases -> back to queue / failed after 3 attempts (TK-025)
- uploading > 24 h -> abort multipart, drop the job
- queued > 72 h -> expired + audio deleted
- audio > 24 h after completed/failed/expired/cancelled -> delete object
- transcript > 30 days -> delete segments/speakers
- scheduled deletions (`hapus_transkrip_pada`) -> purge job row
- terminal jobs > 30 days -> purge row

All functions accept an explicit `now` so tests can advance the clock.
"""

from __future__ import annotations

import logging
from datetime import datetime

from api import dal
from api.config import Settings
from api.db import transaction
from api.state import transition
from api.storage import Storage, StorageError
from api.timeutil import days_ago, hours_ago, iso, utcnow

log = logging.getLogger("beosabasi.retention")


def purge_assets(conn, storage: Storage, job: dict) -> None:
    if job.get("r2_key"):
        try:
            storage.delete(job["r2_key"])
        except StorageError as exc:
            log.warning("hapus_objek_gagal job=%s: %s", job["id"], exc)
    dal.segment_delete_all(conn, job["id"])
    dal.speaker_delete_all(conn, job["id"])
    dal.upload_session_delete(conn, job["id"])


def purge_now(conn, storage: Storage, job: dict) -> None:
    """Delete bytes + transcript + job row (user-requested deletion)."""
    purge_assets(conn, storage, job)
    dal.job_delete(conn, job["id"])


def _abort_stale_uploads(conn, storage: Storage, settings: Settings,
                         now: datetime) -> int:
    cutoff = iso(hours_ago(now, settings.upload_ttl_hours))
    removed = 0
    for row in dal.uploads_stale(conn, cutoff):
        try:
            storage.abort_multipart(row["r2_key"], row["upload_id"])
        except StorageError as exc:
            log.warning("abort_gagal job=%s: %s", row["job_id"], exc)
        with transaction(conn):
            job = dal.job_get(conn, row["job_id"])
            if job is not None:
                purge_assets(conn, storage, job)
                dal.job_delete(conn, job["id"])
        removed += 1
    return removed


def _expire_waiting_jobs(conn, storage: Storage, settings: Settings,
                         now: datetime) -> int:
    cutoff = iso(hours_ago(now, settings.queue_expiry_hours))
    expired = 0
    for job in dal.jobs_queued_before(conn, cutoff):
        with transaction(conn):
            fresh = dal.job_get(conn, job["id"])
            if fresh is None or fresh["state"] != "queued":
                continue
            try:
                storage.delete(fresh["r2_key"])
            except StorageError as exc:
                log.warning("hapus_audio_gagal job=%s: %s", fresh["id"], exc)
            transition(conn, fresh, "expired", kode_galat="JOB_EXPIRED",
                       selesai_pada=iso(now), audio_dihapus_pada=iso(now))
            dal.upload_session_delete(conn, fresh["id"])
            dal.audit_add(conn, waktu=iso(now), user_id=fresh["user_id"],
                          jenis="job_kedaluwarsa", job_id=fresh["id"])
        expired += 1
    return expired


def _purge_due_audio(conn, storage: Storage, settings: Settings,
                     now: datetime) -> int:
    cutoff = iso(hours_ago(now, settings.audio_retention_hours))
    count = 0
    for job in dal.jobs_audio_purge_due(conn, cutoff):
        try:
            storage.delete(job["r2_key"])
        except StorageError as exc:
            log.warning("hapus_audio_gagal job=%s: %s", job["id"], exc)
            continue
        conn.execute("UPDATE jobs SET audio_dihapus_pada = ? WHERE id = ?",
                     (iso(now), job["id"]))
        count += 1
    return count


def _purge_due_transcripts(conn, settings: Settings, now: datetime) -> int:
    cutoff = iso(days_ago(now, settings.transcript_retention_days))
    count = 0
    for job in dal.jobs_transcript_purge_due(conn, cutoff):
        dal.segment_delete_all(conn, job["id"])
        dal.speaker_delete_all(conn, job["id"])
        conn.execute("UPDATE jobs SET hapus_transkrip_pada = ? WHERE id = ?",
                     (iso(now), job["id"]))
        count += 1
    return count


def _purge_scheduled_deletions(conn, storage: Storage, now: datetime) -> int:
    count = 0
    for job in dal.jobs_purge_due(conn, iso(now)):
        with transaction(conn):
            fresh = dal.job_get(conn, job["id"])
            if fresh is not None:
                purge_now(conn, storage, fresh)
        count += 1
    return count


def _purge_old_terminal_jobs(conn, storage: Storage, settings: Settings,
                             now: datetime) -> int:
    cutoff = iso(days_ago(now, settings.transcript_retention_days))
    rows = conn.execute(
        "SELECT * FROM jobs WHERE state IN ('completed','failed','expired',"
        "'cancelled') AND COALESCE(selesai_pada, dibuat_pada) < ?", (cutoff,)
    ).fetchall()
    for row in rows:
        job = dict(row)
        with transaction(conn):
            fresh = dal.job_get(conn, job["id"])
            if fresh is not None:
                purge_now(conn, storage, fresh)
    return len(rows)


def audit_k4(conn, storage: Storage, settings: Settings,
             now: datetime | None = None) -> dict[str, int]:
    """Daily K4 audit: orphan objects + audio still present past retention."""
    moment = now or utcnow()
    objects = dict(storage.list_keys("uploads/"))
    known = {row["r2_key"] for row in dal.jobs_with_audio(conn)}
    orphans = {key: size for key, size in objects.items() if key not in known}
    cutoff = iso(hours_ago(moment, settings.audio_retention_hours))
    overdue = 0
    for job in dal.jobs_audio_purge_due(conn, cutoff, limit=10_000):
        overdue += 1
    return {
        "objek_total": len(objects),
        "objek_yatim": len(orphans),
        "byte_objek_yatim": sum(orphans.values()),
        "audio_terlambat_hapus": overdue,
    }


def sweep(conn, storage: Storage, settings: Settings,
          now: datetime | None = None) -> dict[str, int]:
    moment = now or utcnow()
    stats: dict[str, int] = {}
    stats["sewa_dikembalikan"] = dal.requeue_expired_leases(
        conn, iso(moment), settings.max_attempts)
    stats["unggahan_basi"] = _abort_stale_uploads(conn, storage, settings, moment)
    stats["antrean_kedaluwarsa"] = _expire_waiting_jobs(conn, storage, settings,
                                                        moment)
    stats["audio_dihapus"] = _purge_due_audio(conn, storage, settings, moment)
    stats["transkrip_dihapus"] = _purge_due_transcripts(conn, settings, moment)
    stats["job_dihapus"] = _purge_scheduled_deletions(conn, storage, moment)
    stats["job_lama_dihapus"] = _purge_old_terminal_jobs(conn, storage, settings,
                                                          moment)
    dal.rate_event_prune(conn, iso(hours_ago(moment, 48)))
    return stats
