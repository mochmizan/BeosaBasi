"""TK-029: structured logs + admin metrics without storing transcript text.

Access logs carry method, path, status, duration, and the hashed IP only.
No query strings, no filenames, no bodies, no transcript text (AI-10).
"""

from __future__ import annotations

import json
import logging
import secrets
import sqlite3
import statistics
import time
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from api import dal
from api.config import Settings
from api.deps import db_conn, get_settings, get_storage
from api.errors import ApiError, error_body
from api.retention import audit_k4
from api.storage import Storage, StorageError
from api.timeutil import iso, utcnow

log = logging.getLogger("beosabasi.access")

ALLOWED_EXTRA = ("metode", "jalur", "status", "ms", "ip_hash", "pekerja")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "waktu": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "pesan": record.getMessage(),
            "logger": record.name,
        }
        for key in ALLOWED_EXTRA:
            value = record.__dict__.get(key)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["galat"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if any(isinstance(h.formatter, JsonFormatter) for h in root.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.handlers = [handler]
    root.setLevel(level)


def access_log(request: Request, status_code: int, elapsed_ms: float) -> None:
    log.info(
        "permintaan",
        extra={
            "metode": request.method,
            "jalur": request.url.path,
            "status": status_code,
            "ms": round(elapsed_ms, 1),
            "ip_hash": getattr(request.state, "ip_hash", None),
        },
    )


router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_admin(request: Request, settings: Settings) -> None:
    if not settings.admin_token:
        raise ApiError(404, "INTERNAL", "Halaman admin tidak aktif.")
    token = request.headers.get("x-admin-token", "")
    if not secrets.compare_digest(token, settings.admin_token):
        raise ApiError(401, "INTERNAL", "Token admin tidak valid.")


def metrics_payload(conn, storage: Storage, settings: Settings) -> dict[str, Any]:
    now = utcnow()
    cutoff = iso(now - timedelta(seconds=settings.worker_offline_seconds))
    counts = dal.jobs_count_by_state(conn)
    completed = counts.get("completed", 0)
    failed = counts.get("failed", 0)
    finished = completed + failed
    metrics = dal.metrics_all(conn)
    xrts = [m["xrt"] for m in metrics if m.get("xrt")]
    ratios = [m["edit_chars"] / m["total_chars"] for m in metrics
              if m.get("total_chars")]
    try:
        stored = sum(size for _key, size in storage.list_keys("uploads/"))
        audit = audit_k4(conn, storage, settings, now)
    except StorageError:
        stored = None
        audit = None
    return {
        "waktu": iso(now),
        "job_per_status": counts,
        "antrean": counts.get("queued", 0),
        "median_xrt": statistics.median(xrts) if xrts else None,
        "tingkat_gagal": round(failed / finished, 4) if finished else None,
        "median_rasio_sunting": statistics.median(ratios) if ratios else None,
        "pekerja": [
            {
                "id": w["id"],
                "versi": w["versi"],
                "terakhir_terlihat": w["terakhir_terlihat"],
                "aktif": w["terakhir_terlihat"] >= cutoff,
            }
            for w in dal.workers_list(conn)
        ],
        "penyimpanan": {
            "terpakai_byte": stored,
            "database_byte": dal.job_storage_bytes(conn),
            "plafon_byte": settings.global_storage_cap_bytes,
        },
        "audit_k4": audit,
    }


@router.get("/metrics")
def get_metrics(request: Request,
                conn: sqlite3.Connection = Depends(db_conn),
                settings: Settings = Depends(get_settings),
                storage: Storage = Depends(get_storage)) -> JSONResponse:
    try:
        _require_admin(request, settings)
    except ApiError as exc:
        return JSONResponse(status_code=exc.status_code,
                            content=error_body(exc.code, exc.message))
    return JSONResponse(content=metrics_payload(conn, storage, settings))


def install_middleware(app) -> None:
    @app.middleware("http")
    async def _timing(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        access_log(request, response.status_code,
                   (time.perf_counter() - started) * 1000)
        return response
