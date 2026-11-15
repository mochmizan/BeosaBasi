"""Job state machine, quota billing, and queue ETA (TK-024).

Legal transitions per PRD 4.5 (plus `deleted` as the terminal purge state).
Anything else raises IllegalTransition and unit tests prove it is rejected.
"""

from __future__ import annotations

import statistics

from api import dal
from api.config import Settings
from api.timeutil import local_date, utcnow

ACTIVE_STATES = {"uploading", "queued", "processing"}
TERMINAL_STATES = {"completed", "failed", "expired", "cancelled", "deleted"}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "uploading": {"queued", "cancelled", "expired", "failed", "deleted"},
    "queued": {"processing", "cancelled", "expired", "failed", "deleted"},
    "processing": {"completed", "failed", "cancelled", "queued", "deleted"},
    "completed": {"deleted"},
    "failed": {"queued", "deleted"},
    "expired": {"deleted"},
    "cancelled": {"deleted"},
    "deleted": set(),
}

DEFAULT_XRT = 8.0  # PRD K2/target until TK-013 measures the laptop


class IllegalTransition(Exception):
    def __init__(self, dari: str, ke: str) -> None:
        super().__init__(f"transisi ilegal: {dari} -> {ke}")
        self.dari = dari
        self.ke = ke


def ensure_transition(dari: str, ke: str) -> None:
    if ke not in ALLOWED_TRANSITIONS.get(dari, set()):
        raise IllegalTransition(dari, ke)


def transition(conn, job: dict, ke: str, **fields) -> None:
    """Validate and persist one state change (caller owns the transaction)."""
    ensure_transition(job["state"], ke)
    dal.job_set_state(conn, job["id"], ke, **fields)
    job["state"] = ke
    job.update(fields)


def quota_remaining(conn, ip_hash: str, settings: Settings,
                    now=None) -> float:
    used = dal.ledger_sum_by_ip(conn, ip_hash, local_date(now or utcnow()))
    return max(settings.quota_minutes_per_day - used, 0.0)


def billed_minutes(duration_seconds: float, diarization: bool,
                   diarization_available: bool, settings: Settings) -> float:
    multiplier = settings.diarization_multiplier if (
        diarization and diarization_available) else 1.0
    return max(duration_seconds, 0.0) / 60.0 * multiplier


def charge_quota(conn, job: dict, *, duration_seconds: float,
                 diarization_available: bool, settings: Settings,
                 now=None) -> float:
    """Charge actual audio minutes once, when the worker result arrives."""
    billed = billed_minutes(duration_seconds, bool(job["diarisasi"]),
                            diarization_available, settings)
    moment = now or utcnow()
    dal.ledger_add(
        conn,
        user_id=job["user_id"],
        tanggal_lokal=local_date(moment),
        job_id=job["id"],
        menit=billed,
        jenis="kenakan",
    )
    dal.job_set_state(conn, job["id"], job["state"], menit_dikenakan=billed)
    job["menit_dikenakan"] = billed
    return billed


def estimate_xrt(conn) -> float:
    values = [m["xrt"] for m in dal.metrics_all(conn) if m.get("xrt")]
    return statistics.median(values) if values else DEFAULT_XRT


def eta_seconds(conn, job: dict) -> float | None:
    """Estimated seconds until this job finishes, from queue audio + xRT."""
    if job["state"] not in ACTIVE_STATES:
        return None
    if job["state"] == "uploading":
        return None
    ahead = dal.audio_seconds_ahead(conn, job)
    return ahead / max(estimate_xrt(conn), 0.1)
