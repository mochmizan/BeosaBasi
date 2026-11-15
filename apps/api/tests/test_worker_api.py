"""TK-025: worker auth, claim/heartbeat/result/fail, leases, cancel."""

from __future__ import annotations

from datetime import timedelta

from conftest import WORKER_HEADERS, claim, submit_result, upload_job

from api.db import connect
from api.retention import sweep
from api.timeutil import utcnow


def test_bad_token_rejected(client, storage):
    upload_job(client, storage)
    resp = client.post("/worker/v1/jobs/claim?wait=0",
                       headers={"Authorization": "Bearer salah",
                                "X-Worker-Id": "w1"})
    assert resp.status_code == 401
    assert client.post("/worker/v1/jobs/claim?wait=0").status_code == 401


def test_ping_and_version_gate(client):
    ok = client.post("/worker/v1/ping", headers=WORKER_HEADERS,
                     json={"worker_id": "w1", "version": "0.1.0"})
    assert ok.status_code == 200
    assert ok.json() == {"ok": True, "min_version": "0.1.0",
                         "update_required": False}
    old = client.post("/worker/v1/ping", headers=WORKER_HEADERS,
                      json={"worker_id": "w1", "version": "0.0.1"})
    assert old.json()["update_required"] is True


def test_empty_queue_returns_204(client):
    resp = client.post("/worker/v1/jobs/claim?wait=0", headers=WORKER_HEADERS)
    assert resp.status_code == 204


def test_end_to_end_claim_heartbeat_result(client, storage):
    uploaded = upload_job(client, storage)
    claimed = claim(client)
    assert claimed["job_id"] == uploaded["job_id"]
    assert claimed["audio_url"].startswith("memory://get/")
    assert claimed["language"] == "id"

    beat = client.post(f"/worker/v1/jobs/{claimed['job_id']}/heartbeat",
                       headers=WORKER_HEADERS,
                       json={"stage": "transcribing", "progress_percent": 40})
    assert beat.status_code == 200
    assert beat.json()["cancel"] is False

    assert submit_result(client, claimed["job_id"]).status_code == 200
    detail = client.get(f"/api/jobs/{claimed['job_id']}").json()
    assert detail["job"]["state"] == "completed"
    assert detail["job"]["duration_seconds"] == 60.0

    transcript = client.get(
        f"/api/jobs/{claimed['job_id']}/transcript").json()
    assert len(transcript["segments"]) == 2
    assert transcript["segments"][0]["text"] == "selamat pagi semua"

    # A finished job cannot be claimed or submitted twice.
    again = submit_result(client, claimed["job_id"])
    assert again.status_code == 409


def test_claim_is_atomic_across_two_workers(client, storage):
    upload_job(client, storage)
    first = client.post("/worker/v1/jobs/claim?wait=0", headers=WORKER_HEADERS)
    second = client.post("/worker/v1/jobs/claim?wait=0",
                         headers={"Authorization": "Bearer test-token",
                                  "X-Worker-Id": "w2"})
    assert first.status_code == 200
    assert second.status_code == 204


def test_wrong_worker_cannot_heartbeat(client, storage):
    upload_job(client, storage)
    claimed = claim(client)
    other = client.post(f"/worker/v1/jobs/{claimed['job_id']}/heartbeat",
                        headers={"Authorization": "Bearer test-token",
                                 "X-Worker-Id": "w2"},
                        json={"stage": "transcribing"})
    assert other.status_code == 409


def test_cancel_signal_and_purge(client, storage, settings):
    upload_job(client, storage)
    claimed = claim(client)
    job_id = claimed["job_id"]

    assert client.delete(f"/api/jobs/{job_id}").status_code == 202
    beat = client.post(f"/worker/v1/jobs/{job_id}/heartbeat",
                       headers=WORKER_HEADERS, json={"stage": "transcribing"})
    assert beat.status_code == 200
    assert beat.json()["cancel"] is True

    result = submit_result(client, job_id)
    assert result.status_code == 200
    assert client.get(f"/api/jobs/{job_id}/transcript").json()["segments"] == []

    conn = connect(settings.db_path)
    try:
        sweep(conn, storage, settings, now=utcnow() + timedelta(minutes=2))
    finally:
        conn.close()
    assert client.get(f"/api/jobs/{job_id}").status_code == 404


def test_lease_expiry_requeues_then_fails_after_three(client, storage, settings):
    upload_job(client, storage)
    claimed = claim(client)

    conn = connect(settings.db_path)
    try:
        now = utcnow() + timedelta(seconds=settings.lease_seconds + 5)
        stats = sweep(conn, storage, settings, now=now)
        assert stats["sewa_dikembalikan"] == 1
        job = client.get(f"/api/jobs/{claimed['job_id']}").json()["job"]
        assert job["state"] == "queued"
        assert job["attempts"] == 2
    finally:
        conn.close()

    claim(client)  # attempt 3
    conn = connect(settings.db_path)
    try:
        sweep(conn, storage, settings,
              now=utcnow() + timedelta(seconds=2 * settings.lease_seconds + 10))
    finally:
        conn.close()
    job = client.get(f"/api/jobs/{claimed['job_id']}").json()["job"]
    assert job["state"] == "failed"
    assert job["error_code"] == "LEASE_LOST"


def test_fail_retryable_until_three(client, storage):
    upload_job(client, storage)
    claimed = claim(client)
    job_id = claimed["job_id"]
    for attempt in (1, 2):
        resp = client.post(f"/worker/v1/jobs/{job_id}/fail",
                           headers=WORKER_HEADERS,
                           json={"code": "FFMPEG_ERROR", "retryable": True})
        assert resp.status_code == 200
        job = client.get(f"/api/jobs/{job_id}").json()["job"]
        assert job["state"] == "queued"
        claim(client)
        assert client.get(f"/api/jobs/{job_id}").json()["job"]["attempts"] == attempt + 1

    resp = client.post(f"/worker/v1/jobs/{job_id}/fail", headers=WORKER_HEADERS,
                       json={"code": "FFMPEG_ERROR", "retryable": True})
    assert resp.status_code == 200
    job = client.get(f"/api/jobs/{job_id}").json()["job"]
    assert job["state"] == "failed"
    assert job["error_code"] == "FFMPEG_ERROR"


def test_non_retryable_fail_is_immediate(client, storage):
    upload_job(client, storage)
    claimed = claim(client)
    client.post(f"/worker/v1/jobs/{claimed['job_id']}/fail", headers=WORKER_HEADERS,
                json={"code": "CORRUPT_MEDIA", "retryable": False})
    job = client.get(f"/api/jobs/{claimed['job_id']}").json()["job"]
    assert job["state"] == "failed"
    assert job["error_code"] == "CORRUPT_MEDIA"


def test_invalid_result_rejected(client, storage):
    upload_job(client, storage)
    claimed = claim(client)
    resp = client.post(f"/worker/v1/jobs/{claimed['job_id']}/result",
                       headers=WORKER_HEADERS,
                       json={
                           "segments": [{
                               "index": 0, "start": 5.0, "end": 1.0,
                               "text": "x", "confidence": 0.5, "version": 1,
                           }],
                           "duration_seconds": 60.0,
                           "xrt": 8.0,
                           "model_version": "m",
                           "low_confidence_ratio": 0.0,
                       })
    assert resp.status_code == 400
