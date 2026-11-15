"""TK-023: multipart upload flow, limits, resume, light checks."""

from __future__ import annotations

import time

from conftest import _valid_audio, init_upload, upload_job

from api.config import Settings


def test_rejects_oversize_before_upload(client):
    too_big = 200 * 1024 * 1024 + 1
    resp = init_upload(client, size=too_big)
    assert resp["status"] == 400
    assert resp["body"]["code"] == "TOO_LARGE"


def test_rejects_unsupported_type(client):
    resp = init_upload(client, content_type="text/plain")
    assert resp["status"] == 400
    assert resp["body"]["code"] == "UNSUPPORTED_TYPE"


def test_part_size_count_and_resume(client, storage):
    size = 17 * 1024 * 1024  # 3 parts of 8 MiB (last smaller)
    started = init_upload(client, size=size)
    assert started["status"] == 201
    session = started["body"]
    assert session["part_size"] == 8 * 1024 * 1024
    assert session["part_count"] == 3

    signed = client.post(f"/api/uploads/{session['job_id']}/parts",
                         json={"part_number": 1})
    assert signed.status_code == 200
    assert signed.json()["url"].startswith("memory://upload/")

    storage.put_part(session["upload_id"], 1, b"ID3" + b"\x00" * 10)
    status = client.get(f"/api/uploads/{session['job_id']}")
    assert status.json()["parts_done"] == [1]
    assert status.json()["parts_total"] == 3

    bad = client.post(f"/api/uploads/{session['job_id']}/parts",
                      json={"part_number": 99})
    assert bad.status_code == 400


def test_interrupted_upload_resumes_without_restart(client, storage):
    size = 20 * 1024 * 1024  # 3 parts
    started = init_upload(client, size=size)
    session = started["body"]
    payload = _valid_audio(size)
    part_size = session["part_size"]
    upload_id = session["upload_id"]

    first = payload[:part_size]
    etag = storage.put_part(upload_id, 1, first)
    assert client.get(f"/api/uploads/{session['job_id']}").json()["parts_done"] == [1]
    interrupted = client.post(f"/api/uploads/{session['job_id']}/complete",
                              json={"parts": [{"part_number": 1, "etag": etag}]})
    assert interrupted.status_code == 400

    parts = [{"part_number": 1, "etag": etag}]
    for number in (2, 3):
        chunk = payload[(number - 1) * part_size: number * part_size]
        parts.append({"part_number": number,
                      "etag": storage.put_part(upload_id, number, chunk)})
    resp = client.post(f"/api/uploads/{session['job_id']}/complete",
                       json={"parts": parts})
    assert resp.status_code == 200, resp.text
    assert resp.json()["state"] == "queued"


def test_complete_moves_job_to_queue(client, storage):
    started = time.monotonic()
    uploaded = upload_job(client, storage)
    assert time.monotonic() - started < 5.0  # light check budget (PRD 4.6)
    assert uploaded["status"] == 200, uploaded
    assert uploaded["body"]["state"] == "queued"
    assert uploaded["body"]["filename"] == "rapat.mp3"

    detail = client.get(f"/api/jobs/{uploaded['job_id']}")
    assert detail.status_code == 200
    assert detail.json()["job"]["state"] == "queued"
    assert detail.json()["queue_position"] == 1


def test_magic_bytes_reject_and_delete_object(client, storage):
    started = init_upload(client, size=128)
    session = started["body"]
    junk = b"not-an-audio-file" * 8
    etag = storage.put_part(session["upload_id"], 1, junk)
    resp = client.post(f"/api/uploads/{session['job_id']}/complete",
                       json={"parts": [{"part_number": 1, "etag": etag}]})
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_FILE"
    assert storage.list_keys("uploads/") == []

    job = client.get(f"/api/jobs/{session['job_id']}").json()["job"]
    assert job["state"] == "failed"
    assert job["error_code"] == "INVALID_FILE"


def test_etag_mismatch_rejected(client, storage):
    started = init_upload(client, size=128)
    session = started["body"]
    storage.put_part(session["upload_id"], 1, _valid_audio(128))
    resp = client.post(f"/api/uploads/{session['job_id']}/complete",
                       json={"parts": [{"part_number": 1, "etag": "deadbeef"}]})
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_FILE"


def test_active_job_limit(client):
    assert init_upload(client, size=1024)["status"] == 201
    assert init_upload(client, size=1024)["status"] == 201
    third = init_upload(client, size=1024)
    assert third["status"] == 403
    assert third["body"]["code"] == "TOO_MANY_ACTIVE_JOBS"


def test_upload_rate_limit(client_factory):
    client = client_factory(upload_initiations_per_hour=1)
    assert init_upload(client, size=1024)["status"] == 201
    second = init_upload(client, size=1024)
    assert second["status"] == 429


def test_missing_turnstile_token_rejected(client):
    resp = client.post("/api/uploads", json={
        "filename": "a.mp3", "size_bytes": 10, "content_type": "audio/mpeg",
        "language": "id", "turnstile_token": "",
    })
    assert resp.status_code == 400


def test_quota_remaining_shape(client):
    me = client.get("/api/me")
    assert me.status_code == 200
    body = me.json()
    assert body["quota_minutes_remaining"] == 60.0
    assert body["active_jobs"] == 0
    assert body["consent"] is None
    assert "set-cookie" in {k.lower() for k in me.headers}
    assert Settings().cookie_name in me.headers["set-cookie"]


def test_global_storage_cap(client_factory):
    client = client_factory(global_storage_cap_bytes=1000)
    resp = init_upload(client, size=2048)
    assert resp["status"] == 503


def test_storage_unavailable_is_clean(client_factory):
    from api.storage import NullStorage

    app_client = client_factory()
    app_client.app.state.storage = NullStorage()
    resp = init_upload(app_client, size=1024)
    assert resp["status"] == 503
    assert resp["body"]["message"].startswith("Penyimpanan")


def test_storage_object_key_has_no_filename(client, storage):
    uploaded = upload_job(client, storage, filename="rahasia-pribadi.mp3")
    assert uploaded["status"] == 200
    keys = [key for key, _size in storage.list_keys("uploads/")]
    assert len(keys) == 1
    assert "rahasia" not in keys[0]
    assert keys[0].startswith("uploads/")
