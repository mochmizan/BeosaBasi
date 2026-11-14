"""Data-access layer for TK-020 (PRD 4.4). Thin helpers over sqlite3.

Conventions: callers own the connection (see api.db.connect, which sets
WAL + foreign_keys + busy_timeout). All helpers take a live connection and
return dicts / lists of dicts. Timestamps are ISO-8601 strings.
"""

from __future__ import annotations

import sqlite3

MAX_ATTEMPTS = 3


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


# -- users ---------------------------------------------------------------


def create_user(conn: sqlite3.Connection, *, user_id: str, email: str,
                google_sub: str | None = None, status: str = "aktif",
                dibuat_pada: str) -> dict:
    conn.execute(
        "INSERT INTO users (id, email, google_sub, status, dibuat_pada)"
        " VALUES (?, ?, ?, ?, ?)",
        (user_id, email, google_sub, status, dibuat_pada),
    )
    return get_user(conn, user_id)


def get_user(conn: sqlite3.Connection, user_id: str) -> dict | None:
    return _row_to_dict(conn.execute("SELECT * FROM users WHERE id = ?",
                                     (user_id,)).fetchone())


def get_user_by_email(conn: sqlite3.Connection, email: str) -> dict | None:
    return _row_to_dict(conn.execute("SELECT * FROM users WHERE email = ?",
                                     (email,)).fetchone())


def set_user_status(conn: sqlite3.Connection, user_id: str, status: str) -> None:
    conn.execute("UPDATE users SET status = ? WHERE id = ?", (status, user_id))


# -- allowlist -----------------------------------------------------------


def allowlist_add(conn: sqlite3.Connection, email: str, ditambahkan_pada: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO allowlist (email, ditambahkan_pada) VALUES (?, ?)",
        (email, ditambahkan_pada),
    )


def allowlist_remove(conn: sqlite3.Connection, email: str) -> None:
    conn.execute("DELETE FROM allowlist WHERE email = ?", (email,))


def is_allowed(conn: sqlite3.Connection, email: str) -> bool:
    return conn.execute("SELECT 1 FROM allowlist WHERE email = ?",
                        (email,)).fetchone() is not None


# -- consents ------------------------------------------------------------


def consent_give(conn: sqlite3.Connection, *, consent_id: str, user_id: str,
                 versi_dokumen: str, diberikan_pada: str) -> dict:
    conn.execute(
        "INSERT INTO consents (id, user_id, versi_dokumen, diberikan_pada)"
        " VALUES (?, ?, ?, ?)",
        (consent_id, user_id, versi_dokumen, diberikan_pada),
    )
    return _row_to_dict(conn.execute("SELECT * FROM consents WHERE id = ?",
                                     (consent_id,)).fetchone())


def consent_withdraw(conn: sqlite3.Connection, consent_id: str,
                     ditarik_pada: str) -> None:
    conn.execute("UPDATE consents SET ditarik_pada = ? WHERE id = ?",
                 (ditarik_pada, consent_id))


def latest_consent(conn: sqlite3.Connection, user_id: str) -> dict | None:
    return _row_to_dict(conn.execute(
        "SELECT * FROM consents WHERE user_id = ? ORDER BY diberikan_pada DESC LIMIT 1",
        (user_id,)).fetchone())


# -- jobs (incl. atomic claim per PRD 4.7) -------------------------------


def job_create(conn: sqlite3.Connection, *, job_id: str, user_id: str,
               state: str = "uploading", dibuat_pada: str, **fields) -> dict:
    cols = ["id", "user_id", "state", "dibuat_pada", *fields.keys()]
    vals = [job_id, user_id, state, dibuat_pada, *fields.values()]
    placeholders = ", ".join("?" for _ in cols)
    conn.execute(f"INSERT INTO jobs ({', '.join(cols)}) VALUES ({placeholders})", vals)
    return job_get(conn, job_id)


def job_get(conn: sqlite3.Connection, job_id: str) -> dict | None:
    return _row_to_dict(conn.execute("SELECT * FROM jobs WHERE id = ?",
                                     (job_id,)).fetchone())


def jobs_by_user(conn: sqlite3.Connection, user_id: str,
                 limit: int = 50) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM jobs WHERE user_id = ? ORDER BY dibuat_pada DESC LIMIT ?",
        (user_id, limit)).fetchall()
    return [dict(r) for r in rows]


def job_set_state(conn: sqlite3.Connection, job_id: str, state: str,
                  **fields) -> None:
    sets = ["state = ?", *(f"{k} = ?" for k in fields)]
    conn.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id = ?",
                 (state, *fields.values(), job_id))


def claim_job(conn: sqlite3.Connection, *, worker_id: str,
              lease_sampai: str) -> dict | None:
    """Atomically claim oldest queued job (PRD 4.7). One UPDATE = one winner."""
    row = conn.execute(
        "UPDATE jobs SET state = 'processing', worker_id = ?,"
        " lease_sampai = ?, percobaan = percobaan + 1"
        " WHERE id = (SELECT id FROM jobs WHERE state = 'queued'"
        " ORDER BY dibuat_pada, id LIMIT 1)"
        " RETURNING *",
        (worker_id, lease_sampai),
    ).fetchone()
    return _row_to_dict(row)


def heartbeat_renew(conn: sqlite3.Connection, job_id: str, worker_id: str,
                    lease_sampai: str, stage: str | None = None) -> bool:
    cur = conn.execute(
        "UPDATE jobs SET lease_sampai = ?,"
        " stage = COALESCE(?, stage)"
        " WHERE id = ? AND worker_id = ? AND state = 'processing'",
        (lease_sampai, stage, job_id, worker_id),
    )
    return cur.rowcount == 1


def requeue_expired_leases(conn: sqlite3.Connection, now_iso: str,
                           max_attempts: int = MAX_ATTEMPTS) -> int:
    """Return processing jobs with dead leases to queued (or failed past max)."""
    cur = conn.execute(
        "UPDATE jobs SET percobaan = percobaan + 1,"
        " state = CASE WHEN percobaan + 1 >= ? THEN 'failed' ELSE 'queued' END,"
        " worker_id = CASE WHEN percobaan + 1 >= ? THEN worker_id ELSE NULL END,"
        " lease_sampai = CASE WHEN percobaan + 1 >= ? THEN lease_sampai ELSE NULL END,"
        " kode_galat = CASE WHEN percobaan + 1 >= ? THEN 'LEASE_LOST' ELSE kode_galat END"
        " WHERE state = 'processing' AND lease_sampai IS NOT NULL"
        " AND lease_sampai < ?",
        (max_attempts, max_attempts, max_attempts, max_attempts, now_iso),
    )
    return cur.rowcount


# -- segments ------------------------------------------------------------


def segment_upsert(conn: sqlite3.Connection, *, job_id: str, urut: int,
                   mulai: float, selesai: float, teks: str, keyakinan: float,
                   speaker_id: str | None = None, disunting: int = 0,
                   versi: int = 1) -> None:
    conn.execute(
        "INSERT INTO segments (job_id, urut, mulai, selesai, teks, keyakinan,"
        " speaker_id, disunting, versi) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
        " ON CONFLICT (job_id, urut) DO UPDATE SET mulai = excluded.mulai,"
        " selesai = excluded.selesai, teks = excluded.teks,"
        " keyakinan = excluded.keyakinan, speaker_id = excluded.speaker_id,"
        " disunting = excluded.disunting, versi = excluded.versi",
        (job_id, urut, mulai, selesai, teks, keyakinan, speaker_id,
         disunting, versi),
    )


def segments_list(conn: sqlite3.Connection, job_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM segments WHERE job_id = ? ORDER BY urut", (job_id,)).fetchall()]


def segment_patch(conn: sqlite3.Connection, job_id: str, urut: int,
                  expected_version: int, *, teks: str | None = None,
                  speaker_id: str | None = None) -> bool:
    """Optimistic-concurrency edit (contract 409 on version mismatch)."""
    cur = conn.execute(
        "UPDATE segments SET teks = COALESCE(?, teks),"
        " speaker_id = COALESCE(?, speaker_id), disunting = 1, versi = versi + 1"
        " WHERE job_id = ? AND urut = ? AND versi = ?",
        (teks, speaker_id, job_id, urut, expected_version),
    )
    return cur.rowcount == 1


# -- speakers ------------------------------------------------------------


def speaker_upsert(conn: sqlite3.Connection, *, job_id: str, speaker_id: str,
                   label_asli: str, nama_tampil: str) -> None:
    conn.execute(
        "INSERT INTO speakers (job_id, speaker_id, label_asli, nama_tampil)"
        " VALUES (?, ?, ?, ?)"
        " ON CONFLICT (job_id, speaker_id) DO UPDATE SET"
        " label_asli = excluded.label_asli, nama_tampil = excluded.nama_tampil",
        (job_id, speaker_id, label_asli, nama_tampil),
    )


def speakers_list(conn: sqlite3.Connection, job_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM speakers WHERE job_id = ? ORDER BY speaker_id",
        (job_id,)).fetchall()]


def speaker_rename(conn: sqlite3.Connection, job_id: str, speaker_id: str,
                   nama_tampil: str) -> bool:
    cur = conn.execute(
        "UPDATE speakers SET nama_tampil = ? WHERE job_id = ? AND speaker_id = ?",
        (nama_tampil, job_id, speaker_id),
    )
    return cur.rowcount == 1


# -- workers -------------------------------------------------------------


def worker_register(conn: sqlite3.Connection, *, worker_id: str, nama: str,
                    token_hash: str, terakhir_terlihat: str,
                    versi: str) -> None:
    conn.execute(
        "INSERT INTO workers (id, nama, token_hash, terakhir_terlihat, versi)"
        " VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT (id) DO UPDATE SET nama = excluded.nama,"
        " token_hash = excluded.token_hash,"
        " terakhir_terlihat = excluded.terakhir_terlihat, versi = excluded.versi",
        (worker_id, nama, token_hash, terakhir_terlihat, versi),
    )


def worker_ping(conn: sqlite3.Connection, worker_id: str,
                terakhir_terlihat: str, versi: str) -> bool:
    cur = conn.execute(
        "UPDATE workers SET terakhir_terlihat = ?, versi = ? WHERE id = ?",
        (terakhir_terlihat, versi, worker_id),
    )
    return cur.rowcount == 1


def worker_by_token_hash(conn: sqlite3.Connection, token_hash: str) -> dict | None:
    return _row_to_dict(conn.execute("SELECT * FROM workers WHERE token_hash = ?",
                                     (token_hash,)).fetchone())


# -- usage_ledger --------------------------------------------------------


def ledger_add(conn: sqlite3.Connection, *, user_id: str, tanggal_lokal: str,
               job_id: str | None, menit: float, jenis: str) -> int:
    cur = conn.execute(
        "INSERT INTO usage_ledger (user_id, tanggal_lokal, job_id, menit, jenis)"
        " VALUES (?, ?, ?, ?, ?)",
        (user_id, tanggal_lokal, job_id, menit, jenis),
    )
    return cur.lastrowid


def ledger_sum(conn: sqlite3.Connection, user_id: str, tanggal_lokal: str) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(CASE WHEN jenis = 'kenakan' THEN menit"
        " WHEN jenis = 'kembalikan' THEN -menit ELSE 0 END), 0) AS total"
        " FROM usage_ledger WHERE user_id = ? AND tanggal_lokal = ?",
        (user_id, tanggal_lokal)).fetchone()
    return float(row["total"])


# -- audit_events --------------------------------------------------------


def audit_add(conn: sqlite3.Connection, *, waktu: str, user_id: str | None,
              jenis: str, job_id: str | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO audit_events (waktu, user_id, jenis, job_id)"
        " VALUES (?, ?, ?, ?)",
        (waktu, user_id, jenis, job_id),
    )
    return cur.lastrowid


def audit_list(conn: sqlite3.Connection, user_id: str | None = None,
               limit: int = 100) -> list[dict]:
    if user_id is None:
        rows = conn.execute("SELECT * FROM audit_events ORDER BY id DESC LIMIT ?",
                            (limit,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM audit_events WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit)).fetchall()
    return [dict(r) for r in rows]
