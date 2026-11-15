"""SQLite connection + versioned migrate for TK-020 (PRD 4.4, D-14).

Pragmas (applied on every connection):
- foreign_keys=ON (relational integrity)
- journal_mode=WAL (one writer + concurrent readers on small VPS)
- busy_timeout=5000 (wait on lock instead of instant SQLITE_BUSY)
- synchronous=NORMAL (safe with WAL for this scale)
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from api.migrations import LATEST_VERSION, MIGRATIONS

BUSY_TIMEOUT_MS = 5000


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30.0, isolation_level=None,
                           check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[None]:
    """One writer at a time. Never nest these calls."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def _ensure_ledger(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )


def current_version(conn: sqlite3.Connection) -> int:
    _ensure_ledger(conn)
    row = conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
    return int(row["v"]) if row and row["v"] is not None else 0


def _record(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
        (version, utcnow_iso()),
    )


def _unrecord(conn: sqlite3.Connection, version: int) -> None:
    conn.execute("DELETE FROM schema_migrations WHERE version = ?", (version,))


def migrate(db_path: str | Path, target: int | None = None) -> int:
    """Migrate up/down to target (default: latest). Returns resulting version."""
    want = LATEST_VERSION if target is None else int(target)
    if want < 0 or want > LATEST_VERSION:
        raise ValueError(f"target must be 0..{LATEST_VERSION}, got {target}")
    conn = connect(db_path)
    try:
        current = current_version(conn)
        by_version = {v: (up, down) for v, up, down in MIGRATIONS}
        while current < want:
            nxt = current + 1
            up, _ = by_version[nxt]
            conn.executescript(up)
            _record(conn, nxt)
            current = nxt
        while current > want:
            _, down = by_version[current]
            conn.executescript(down)
            _unrecord(conn, current)
            current -= 1
        return current
    finally:
        conn.close()
