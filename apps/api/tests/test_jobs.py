"""TK-024: state machine, quota, queue position/ETA, expiry, deletion."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from conftest import completed_job, init_upload, upload_job

from api import dal
from api.db import connect
from api.retention import sweep
from api.state import IllegalTransition, ensure_transition
from api.timeutil import iso, utcnow


def _me_user(client) -> str:
    return client.get("/api/me").json()["user_id"]


def _seed_queued(settings, user_id: str, *, hours_old: float = 0.0,
                 key: str | None = None) -> dict:
    conn = connect(settings.db_path)
    try:
        job_id = str(uuid.uuid4())
        created = iso(utcnow() - timedelta(hours=hours_old))
        job = dal.job_create(
            conn, job_id=job_id, user_id=user_id, state="queued",
            dibuat_pada=created, nama_berkas_asli="uji.mp3",
            r2_key=key or f"uploads/{user_id}/{job_id}", ukuran_byte=12000,
            bahasa="id",
        )
        return job
    finally:
        conn.close()


@pytest.mark.parametrize("dari,ke", [
    ("uploading", "completed"),
    ("queued", "completed"),
    ("completed", "processing"),
    ("expired", "queued"),
    ("deleted", "queued"),
])
def test_illegal_transitions_rejected(dari, ke):
    with pytest.raises(IllegalTransition):
        ensure_transition(dari, ke)


@pytest.mark.parametrize("dari,ke", [
    ("uploading", "queued"),
    ("queued", "processing"),
    ("processing", "completed"),
    ("processing", "queued"),
    ("queued", "expired"),
    ("completed", "deleted"),
])
def test_legal_transitions_allowed(dari, ke):
    ensure_transition(dari, ke)


def test_queue_position_and_eta(client, settings):
    user_id = _me_user(client)
    _seed_queued(settings, user_id, hours_old=2)
    second = _seed_queued(settings, user_id, hours_old=1)
    detail = client.get(f"/api/jobs/{second['id']}").json()
    assert detail["queue_position"] == 2
    assert detail["eta_seconds"] > 0
    assert detail["worker_active"] is False


def test_worker_offline_flag_flips_when_pinged(client):
    me = client.get("/api/me").json()
    user = me["user_id"]
    conn = connect(client.app.state.settings.db_path)
    try:
        dal.worker_register(conn, worker_id="w9", nama="laptop",
                            token_hash="hash9", terakhir_terlihat=iso(utcnow()),
                            versi="0.1.0")
    finally:
        conn.close()
    job = _seed_queued(client.app.state.settings, user)
    assert client.get(f"/api/jobs/{job['id']}").json()["worker_active"] is True


def test_quota_blocks_new_upload_with_reset_time(client_factory):
    client = client_factory(quota_minutes_per_day=1.0)
    completed_job(client, client.app.state.storage, duration=120.0)
    resp = init_upload(client, size=1024)
    assert resp["status"] == 403
    assert resp["body"]["code"] == "QUOTA_EXCEEDED"
    assert "WIB" in resp["body"]["message"]
    assert "00:00" in resp["body"]["message"]


def test_diarization_charges_double_quota(client, storage):
    uploaded = upload_job(client, storage, diarization=True)
    claimed = client.post("/worker/v1/jobs/claim?wait=0",
                          headers={"Authorization": "Bearer test-token",
                                   "X-Worker-Id": "w1"}).json()
    from conftest import submit_result

    assert submit_result(client, claimed["job_id"], duration=60.0,
                         diarization=True).status_code == 200
    job = client.get(f"/api/jobs/{uploaded['job_id']}").json()["job"]
    assert job["billed_minutes"] == 2.0
    assert client.get("/api/me").json()["quota_minutes_remaining"] == 58.0


def test_diarization_failure_charges_single(client, storage):
    upload_job(client, storage, diarization=True)
    claimed = client.post("/worker/v1/jobs/claim?wait=0",
                          headers={"Authorization": "Bearer test-token",
                                   "X-Worker-Id": "w1"}).json()
    from conftest import submit_result

    assert submit_result(client, claimed["job_id"], duration=60.0,
                         diarization=False).status_code == 200
    job = client.get(f"/api/jobs/{claimed['job_id']}").json()["job"]
    assert job["billed_minutes"] == 1.0


def test_queued_job_expires_after_72h(client, settings, storage):
    user_id = _me_user(client)
    job = _seed_queued(settings, user_id, hours_old=73)
    storage.put_object(job["r2_key"], b"ID3" + b"\x00" * 10)

    conn = connect(settings.db_path)
    try:
        stats = sweep(conn, storage, settings, now=utcnow())
        fresh = dal.job_get(conn, job["id"])
    finally:
        conn.close()

    assert stats["antrean_kedaluwarsa"] == 1
    assert fresh["state"] == "expired"
    assert fresh["kode_galat"] == "JOB_EXPIRED"
    assert fresh["audio_dihapus_pada"] is not None
    assert storage.head(job["r2_key"]) is None


def test_delete_job_purges_immediately(client, storage):
    uploaded = upload_job(client, storage)
    assert client.delete(f"/api/jobs/{uploaded['job_id']}").status_code == 202
    assert client.get(f"/api/jobs/{uploaded['job_id']}").status_code == 404
    assert storage.list_keys("uploads/") == []


def test_delete_account_removes_everything(client, storage):
    uploaded = upload_job(client, storage)
    assert storage.list_keys("uploads/")
    assert client.delete("/api/me").status_code == 202
    assert client.get(f"/api/jobs/{uploaded['job_id']}").status_code == 404
    assert storage.list_keys("uploads/") == []
    fresh = client.get("/api/me").json()
    assert fresh["active_jobs"] == 0


def test_list_jobs_pagination(client, settings):
    user_id = _me_user(client)
    for hour in range(3):
        _seed_queued(settings, user_id, hours_old=hour + 1)
    first = client.get("/api/jobs?limit=2").json()
    assert len(first["jobs"]) == 2
    assert first["next_cursor"] is not None
    second = client.get(f"/api/jobs?limit=2&cursor={first['next_cursor']}").json()
    assert len(second["jobs"]) == 1
    assert second["next_cursor"] is None


def test_stale_upload_aborted_after_24h(client, settings, storage):
    started = init_upload(client, size=1024)
    session = started["body"]
    old = iso(utcnow() - timedelta(hours=25))
    conn = connect(settings.db_path)
    try:
        conn.execute("UPDATE jobs SET dibuat_pada = ? WHERE id = ?",
                     (old, session["job_id"]))
        conn.execute("UPDATE upload_sessions SET dibuat_pada = ? WHERE job_id = ?",
                     (old, session["job_id"]))
        stats = sweep(conn, storage, settings, now=utcnow())
    finally:
        conn.close()
    assert stats["unggahan_basi"] == 1
    assert client.get(f"/api/jobs/{session['job_id']}").status_code == 404
    assert storage.upload_ids() == []


def test_list_jobs_rejects_unknown_status(client):
    assert client.get("/api/jobs?status=ngawur").status_code == 400
