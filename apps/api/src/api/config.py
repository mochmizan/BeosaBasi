"""Runtime configuration (env only, no secrets in the repo).

Every value has a safe development default. Production overrides come from
environment variables (see apps/api/.env.example). Tests build Settings
directly so they never touch the network, R2, or the real clock.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

MIB = 1024 * 1024
GIB = 1024 * MIB

# US-01: accepted containers (content type -> extension label).
ALLOWED_CONTENT_TYPES = {
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/m4a": "m4a",
    "audio/aac": "m4a",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/flac": "flac",
    "audio/x-flac": "flac",
    "audio/ogg": "ogg",
    "audio/opus": "opus",
    "audio/webm": "webm",
    "application/ogg": "ogg",
    "video/mp4": "mp4",
    "video/webm": "webm",
}

ALLOWED_EXTENSIONS = {"mp3", "m4a", "wav", "flac", "ogg", "opus", "mp4", "webm"}


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw not in (None, "") else default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw not in (None, "") else default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "ya", "yes", "on"}


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if raw in (None, ""):
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    # Storage / database
    db_path: Path = Path("beosabasi.db")
    s3_endpoint: str | None = None
    s3_region: str = "auto"
    s3_bucket: str = ""
    s3_key_id: str | None = None
    s3_key_secret: str | None = None
    s3_force_path_style: bool = True

    # Uploads (TK-023)
    part_size: int = 8 * MIB
    max_upload_bytes: int = 200 * MIB
    global_storage_cap_bytes: int = 8 * GIB
    upload_ttl_hours: int = 24
    presign_ttl_seconds: int = 15 * 60

    # Jobs / quota (TK-024)
    quota_minutes_per_day: float = 60.0
    diarization_multiplier: float = 2.0
    max_active_jobs: int = 2
    queue_expiry_hours: int = 72

    # Worker API (TK-025)
    worker_token: str = ""
    worker_min_version: str = "0.1.0"
    lease_seconds: int = 5 * 60
    worker_offline_seconds: int = 90
    max_attempts: int = 3
    claim_max_wait_seconds: int = 25

    # Retention (TK-028)
    audio_retention_hours: int = 24
    transcript_retention_days: int = 30

    # Rate limits (PRD 4.10)
    upload_initiations_per_hour: int = 10
    exports_per_hour: int = 60

    # Identity / HTTP
    cookie_name: str = "beosabasi_session"
    cookie_secure: bool = False
    cookie_max_age_days: int = 90
    ip_hash_salt: str = "dev-only-salt-change-me"
    trust_proxy_headers: bool = False
    cors_origins: list[str] = field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    # Turnstile (TK-003). Empty secret = dev stub (token must be present).
    turnstile_secret: str = ""

    # Observability / admin (TK-029)
    admin_token: str = ""
    sweeper_enabled: bool = True
    sweeper_interval_seconds: int = 30

    @classmethod
    def from_env(cls) -> Settings:
        db_env = _env("BEOSABASI_DB_PATH", "")
        if not db_env:
            url = _env("DATABASE_URL", "sqlite:///./beosabasi.db")
            db_env = url.removeprefix("sqlite:///") if url.startswith("sqlite:///") else url
        return cls(
            db_path=Path(db_env),
            s3_endpoint=os.getenv("S3_ENDPOINT") or None,
            s3_region=_env("S3_REGION", "auto"),
            s3_bucket=_env("S3_BUCKET", ""),
            s3_key_id=os.getenv("S3_KEY_ID") or None,
            s3_key_secret=os.getenv("S3_KEY_SECRET") or None,
            s3_force_path_style=_env_bool("S3_FORCE_PATH_STYLE", True),
            part_size=_env_int("BEOSABASI_PART_SIZE", cls.part_size),
            max_upload_bytes=_env_int("BEOSABASI_MAX_UPLOAD_BYTES", cls.max_upload_bytes),
            global_storage_cap_bytes=_env_int(
                "BEOSABASI_GLOBAL_CAP_BYTES", cls.global_storage_cap_bytes
            ),
            upload_ttl_hours=_env_int("BEOSABASI_UPLOAD_TTL_HOURS", cls.upload_ttl_hours),
            presign_ttl_seconds=_env_int(
                "BEOSABASI_PRESIGN_TTL_SECONDS", cls.presign_ttl_seconds
            ),
            quota_minutes_per_day=_env_float(
                "BEOSABASI_QUOTA_MINUTES", cls.quota_minutes_per_day
            ),
            diarization_multiplier=_env_float(
                "BEOSABASI_DIARIZATION_MULTIPLIER", cls.diarization_multiplier
            ),
            max_active_jobs=_env_int("BEOSABASI_MAX_ACTIVE_JOBS", cls.max_active_jobs),
            queue_expiry_hours=_env_int(
                "BEOSABASI_QUEUE_EXPIRY_HOURS", cls.queue_expiry_hours
            ),
            worker_token=_env("BEOSABASI_WORKER_TOKEN", ""),
            worker_min_version=_env("BEOSABASI_WORKER_MIN_VERSION", cls.worker_min_version),
            lease_seconds=_env_int("BEOSABASI_LEASE_SECONDS", cls.lease_seconds),
            worker_offline_seconds=_env_int(
                "BEOSABASI_WORKER_OFFLINE_SECONDS", cls.worker_offline_seconds
            ),
            max_attempts=_env_int("BEOSABASI_MAX_ATTEMPTS", cls.max_attempts),
            claim_max_wait_seconds=_env_int(
                "BEOSABASI_CLAIM_MAX_WAIT", cls.claim_max_wait_seconds
            ),
            audio_retention_hours=_env_int(
                "BEOSABASI_AUDIO_RETENTION_HOURS", cls.audio_retention_hours
            ),
            transcript_retention_days=_env_int(
                "BEOSABASI_TRANSCRIPT_RETENTION_DAYS", cls.transcript_retention_days
            ),
            upload_initiations_per_hour=_env_int(
                "BEOSABASI_UPLOADS_PER_HOUR", cls.upload_initiations_per_hour
            ),
            exports_per_hour=_env_int("BEOSABASI_EXPORTS_PER_HOUR", cls.exports_per_hour),
            cookie_name=_env("BEOSABASI_COOKIE_NAME", cls.cookie_name),
            cookie_secure=_env_bool("BEOSABASI_COOKIE_SECURE", False),
            cookie_max_age_days=_env_int(
                "BEOSABASI_COOKIE_MAX_AGE_DAYS", cls.cookie_max_age_days
            ),
            ip_hash_salt=_env("BEOSABASI_IP_HASH_SALT", cls.ip_hash_salt),
            trust_proxy_headers=_env_bool("BEOSABASI_TRUST_PROXY", False),
            cors_origins=_env_list(
                "BEOSABASI_CORS_ORIGINS",
                ["http://localhost:5173", "http://127.0.0.1:5173"],
            ),
            turnstile_secret=_env("BEOSABASI_TURNSTILE_SECRET", ""),
            admin_token=_env("BEOSABASI_ADMIN_TOKEN", ""),
            sweeper_enabled=_env_bool("BEOSABASI_SWEEPER", True),
            sweeper_interval_seconds=_env_int(
                "BEOSABASI_SWEEPER_INTERVAL", cls.sweeper_interval_seconds
            ),
        )
