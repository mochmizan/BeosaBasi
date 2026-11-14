"""TK-020: SQLite WAL schema + versioned migrations + DAL + atomic claim."""

import sqlite3
import threading
import uuid

import pytest

from api import dal
from api.db import connect, current_version, migrate
from api.migrations import LATEST_VERSION


@pytest.fixture()
def db_path(tmp_path):
    return str(tmp_path / "tk020.db")


def _conn(db_path):
    return connect(db_path)


def _seed_user_job(conn, i=0, state="queued"):
    uid = f"u-{uuid.uuid4().hex[:8]}-{i}"
    conn.execute("BEGIN")
    try:
        dal.create_user(conn, user_id=uid, email=f"{uid}@example.id",
                        dibuat_pada="2026-11-14T00:00:00+07:00")
        job = dal.job_create(conn, job_id=f"j-{uid}", user_id=uid, state=state,
                             dibuat_pada=f"2026-11-14T00:00:{i:02d}+07:00",
                             nama_berkas_asli="a.mp3", r2_key=f"uploads/{uid}/j",
                             ukuran_byte=100, bahasa="id")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return job


def test_migrate_up_creates_tables_indexes_and_pragmas(db_path):
    assert migrate(db_path) == LATEST_VERSION
    conn = _conn(db_path)
    try:
        assert current_version(conn) == LATEST_VERSION
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
        assert {"users", "allowlist", "consents", "jobs", "segments", "speakers",
                "workers", "usage_ledger", "audit_events", "schema_migrations"} <= tables
        indexes = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index'").fetchall()}
        assert "idx_jobs_state_dibuat" in indexes
        assert "idx_jobs_user" in indexes
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    finally:
        conn.close()


def test_migrate_down_and_up_on_clean_machine(db_path):
    assert migrate(db_path) == LATEST_VERSION
    assert migrate(db_path, 0) == 0
    conn = _conn(db_path)
    try:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
            " AND name NOT LIKE 'sqlite_%'").fetchall()}
        assert tables == {"schema_migrations"}
        assert current_version(conn) == 0
    finally:
        conn.close()
    assert migrate(db_path) == LATEST_VERSION
    conn = _conn(db_path)
    try:
        assert current_version(conn) == LATEST_VERSION
    finally:
        conn.close()


def test_foreign_keys_enforced(db_path):
    migrate(db_path)
    conn = _conn(db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO jobs (id, user_id, state, dibuat_pada)"
                " VALUES ('j-x', 'no-such-user', 'queued', '2026-11-14T00:00:00+07:00')")
    finally:
        conn.close()


def test_dal_covers_all_tables(db_path):
    migrate(db_path)
    conn = _conn(db_path)
    try:
        now = "2026-11-14T00:00:00+07:00"
        dal.allowlist_add(conn, "dina@example.id", now)
        assert dal.is_allowed(conn, "dina@example.id")
        dal.create_user(conn, user_id="u1", email="dina@example.id",
                        google_sub="g1", dibuat_pada=now)
        dal.consent_give(conn, consent_id="c1", user_id="u1",
                         versi_dokumen="privasi-2026-11-v1", diberikan_pada=now)
        assert dal.latest_consent(conn, "u1")["versi_dokumen"] == "privasi-2026-11-v1"
        dal.worker_register(conn, worker_id="w1", nama="laptop",
                            token_hash="h1", terakhir_terlihat=now, versi="0.1.0")
        assert dal.worker_by_token_hash(conn, "h1")["id"] == "w1"
        job = dal.job_create(conn, job_id="j1", user_id="u1", state="queued",
                             dibuat_pada=now, nama_berkas_asli="wawancara.mp3",
                             r2_key="uploads/u1/j1", ukuran_byte=10, bahasa="id")
        assert job["state"] == "queued"
        dal.segment_upsert(conn, job_id="j1", urut=0, mulai=0.0, selesai=1.0,
                           teks="halo", keyakinan=0.9, speaker_id="spk1")
        assert dal.segments_list(conn, "j1")[0]["teks"] == "halo"
        assert dal.segment_patch(conn, "j1", 0, 1, teks="halo semua") is True
        assert dal.segment_patch(conn, "j1", 0, 1, teks="konflik") is False
        dal.speaker_upsert(conn, job_id="j1", speaker_id="spk1",
                           label_asli="Pembicara 1", nama_tampil="Pembicara 1")
        assert dal.speaker_rename(conn, "j1", "spk1", "Dina") is True
        assert dal.speakers_list(conn, "j1")[0]["nama_tampil"] == "Dina"
        dal.ledger_add(conn, user_id="u1", tanggal_lokal="2026-11-14",
                       job_id="j1", menit=1.0, jenis="kenakan")
        assert dal.ledger_sum(conn, "u1", "2026-11-14") == pytest.approx(1.0)
        dal.audit_add(conn, waktu=now, user_id="u1", jenis="consent.given")
        assert dal.audit_list(conn, "u1")[0]["jenis"] == "consent.given"
    finally:
        conn.close()


def test_atomic_claim_one_worker_per_job(db_path):
    migrate(db_path)
    seed = _conn(db_path)
    try:
        for i in range(5):
            _seed_user_job(seed, i)
        for n in range(8):
            dal.worker_register(seed, worker_id=f"w-{n}", nama=f"pekerja-{n}",
                                token_hash=f"hash-{n}",
                                terakhir_terlihat="2026-11-14T00:00:00+07:00",
                                versi="0.1.0")
    finally:
        seed.close()

    claimed: list = []
    lock = threading.Lock()
    barrier = threading.Barrier(8)

    def worker(n):
        conn = _conn(db_path)
        try:
            barrier.wait(timeout=10)
            got = dal.claim_job(conn, worker_id=f"w-{n}",
                                lease_sampai="2026-11-14T00:05:00+07:00")
            if got is not None:
                with lock:
                    claimed.append(got["id"])
        finally:
            conn.close()

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert len(claimed) == 5  # 5 jobs, 8 racers: no double-claim, no loss
    assert len(set(claimed)) == 5

    conn = _conn(db_path)
    try:
        processing = conn.execute(
            "SELECT COUNT(*) AS c FROM jobs WHERE state = 'processing'").fetchone()["c"]
        assert processing == 5
        assert dal.claim_job(conn, worker_id="w-late",
                             lease_sampai="2026-11-14T00:05:00+07:00") is None
    finally:
        conn.close()
