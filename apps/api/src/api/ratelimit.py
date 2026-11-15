"""Simple DB-backed rate limiting (multiple uvicorn workers safe)."""

from __future__ import annotations

from datetime import timedelta

from api import dal
from api.errors import ApiError
from api.timeutil import iso, utcnow

PESAN = "Terlalu banyak permintaan. Tunggu sebentar lalu coba lagi."


def enforce(conn, key: str, limit: int, window_seconds: int = 3600, *,
            now=None) -> None:
    if limit <= 0:
        return
    moment = now or utcnow()
    since = iso(moment - timedelta(seconds=window_seconds))
    dal.rate_event_prune(conn, iso(moment - timedelta(seconds=window_seconds * 2)))
    if dal.rate_event_count(conn, key, since) >= limit:
        raise ApiError(429, "INTERNAL", PESAN)
    dal.rate_event_add(conn, key, iso(moment))
