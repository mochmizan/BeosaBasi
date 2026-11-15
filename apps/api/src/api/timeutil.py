"""Time helpers. Quota days use UTC+7 (WIB), storage stays UTC ISO-8601."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

WIB = timezone(timedelta(hours=7), name="WIB")


def utcnow() -> datetime:
    return datetime.now(UTC)


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def local_date(moment: datetime) -> str:
    """Quota ledger day key, e.g. 2026-11-15 (UTC+7)."""
    return moment.astimezone(WIB).date().isoformat()


def next_reset(moment: datetime) -> datetime:
    """Next midnight WIB (quota reset) after `moment`."""
    wib = moment.astimezone(WIB)
    tomorrow = (wib + timedelta(days=1)).date()
    return datetime.combine(tomorrow, datetime.min.time(), tzinfo=WIB)


def hours_ago(moment: datetime, hours: float) -> datetime:
    return moment - timedelta(hours=hours)


def days_ago(moment: datetime, days: float) -> datetime:
    return moment - timedelta(days=days)


def seconds_between(start: datetime, end: datetime) -> float:
    return max((end - start).total_seconds(), 0.0)
