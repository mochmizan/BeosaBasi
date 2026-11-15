"""TK-026 / TK-027: transcript editing, speakers, audio URL, exports."""

from __future__ import annotations

import re
from datetime import timedelta

from conftest import completed_job, upload_job

from api.db import connect
from api.retention import sweep
from api.timeutil import utcnow


def _job(client, storage) -> str:
    return completed_job(client, storage, diarization=True)


def test_transcript_and_speakers(client, storage):
    job_id = _job(client, storage)
    body = client.get(f"/api/jobs/{job_id}/transcript").json()
    assert body["job_id"] == job_id
    assert [s["index"] for s in body["segments"]] == [0, 1]
    assert {s["speaker_id"] for s in body["segments"]} == {"spk1", "spk2"}
    assert {s["speaker_id"] for s in body["speakers"]} == {"spk1", "spk2"}


def test_edit_keeps_timestamps_and_persists(client, storage):
    job_id = _job(client, storage)
    before = client.get(f"/api/jobs/{job_id}/transcript").json()["segments"][0]

    patched = client.patch(f"/api/jobs/{job_id}/segments/0",
                           json={"text": "halo dunia", "version": 1})
    assert patched.status_code == 200
    after = patched.json()
    assert after["text"] == "halo dunia"
    assert after["start"] == before["start"]
    assert after["end"] == before["end"]
    assert after["version"] == 2
    assert after["edited"] is True

    reloaded = client.get(f"/api/jobs/{job_id}/transcript").json()
    assert reloaded["segments"][0]["text"] == "halo dunia"


def test_stale_version_conflicts(client, storage):
    job_id = _job(client, storage)
    assert client.patch(f"/api/jobs/{job_id}/segments/0",
                        json={"text": "a", "version": 1}).status_code == 200
    conflict = client.patch(f"/api/jobs/{job_id}/segments/0",
                            json={"text": "b", "version": 1})
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "VERSION_CONFLICT"


def test_move_segment_and_rename_speaker(client, storage):
    job_id = _job(client, storage)
    moved = client.patch(f"/api/jobs/{job_id}/segments/1",
                         json={"speaker_id": "spk1", "version": 1})
    assert moved.status_code == 200
    assert moved.json()["speaker_id"] == "spk1"

    renamed = client.patch(f"/api/jobs/{job_id}/speakers/spk1",
                           json={"display_name": "Dina"})
    assert renamed.status_code == 200
    assert renamed.json()["display_name"] == "Dina"

    speakers = client.get(f"/api/jobs/{job_id}/transcript").json()["speakers"]
    assert {s["display_name"] for s in speakers} == {"Dina", "Pembicara 2"}


def test_unknown_speaker_and_segment(client, storage):
    job_id = _job(client, storage)
    assert client.patch(f"/api/jobs/{job_id}/segments/99",
                        json={"text": "x", "version": 1}).status_code == 404
    assert client.patch(f"/api/jobs/{job_id}/segments/0",
                        json={"speaker_id": "hantu", "version": 1}).status_code == 400
    assert client.patch(f"/api/jobs/{job_id}/speakers/hantu",
                        json={"display_name": "X"}).status_code == 404


def test_audio_url_and_retention(client, storage, settings):
    job_id = _job(client, storage)
    url = client.get(f"/api/jobs/{job_id}/audio-url")
    assert url.status_code == 200
    assert url.json()["url"].startswith("memory://get/")

    conn = connect(settings.db_path)
    try:
        sweep(conn, storage, settings, now=utcnow() + timedelta(hours=25))
    finally:
        conn.close()

    gone = client.get(f"/api/jobs/{job_id}/audio-url")
    assert gone.status_code == 404
    assert gone.json()["code"] == "AUDIO_GONE"
    # Editing and export still work without audio.
    assert client.patch(f"/api/jobs/{job_id}/segments/0",
                        json={"text": "tetap bisa disunting",
                              "version": 1}).status_code == 200
    assert client.get(f"/api/jobs/{job_id}/export?format=txt").status_code == 200


def test_transcript_expires_after_30_days(client, storage, settings):
    job_id = _job(client, storage)
    conn = connect(settings.db_path)
    try:
        sweep(conn, storage, settings, now=utcnow() + timedelta(days=31))
    finally:
        conn.close()
    assert client.get(f"/api/jobs/{job_id}/transcript").status_code == 404
    assert client.get(f"/api/jobs/{job_id}/export?format=txt").status_code == 404


def test_export_srt_vtt_txt_docx(client, storage):
    job_id = _job(client, storage)
    client.patch(f"/api/jobs/{job_id}/segments/0",
                 json={"text": "halo dunia", "version": 1})
    client.patch(f"/api/jobs/{job_id}/speakers/spk1",
                 json={"display_name": "Dina"})

    txt = client.get(f"/api/jobs/{job_id}/export?format=txt")
    assert txt.status_code == 200
    assert "Dina: halo dunia" in txt.text
    assert "[00:00:00]" in txt.text

    srt = client.get(f"/api/jobs/{job_id}/export?format=srt")
    assert srt.status_code == 200
    assert re.search(r"1\n00:00:00,000 --> 00:00:04,200\nDina: halo dunia",
                     srt.text)
    assert "2\n00:00:04,200 --> 00:00:09,800\n" in srt.text

    vtt = client.get(f"/api/jobs/{job_id}/export?format=vtt")
    assert vtt.status_code == 200
    assert vtt.text.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:04.200" in vtt.text

    docx = client.get(f"/api/jobs/{job_id}/export?format=docx")
    assert docx.status_code == 200
    assert docx.content[:2] == b"PK"
    assert "wordprocessingml" in docx.headers["content-type"]


def test_export_before_complete_and_bad_format(client, storage):
    uploaded = upload_job(client, storage)
    assert client.get(f"/api/jobs/{uploaded['job_id']}/export?format=txt"
                      ).status_code == 409
    job_id = _job(client, storage)
    assert client.get(f"/api/jobs/{job_id}/export?format=pdf").status_code == 400


def test_cross_tenant_access_denied(client, storage):
    job_id = _job(client, storage)
    with client_factory_scope(client) as other:
        assert other.get(f"/api/jobs/{job_id}").status_code == 404
        assert other.get(f"/api/jobs/{job_id}/transcript").status_code == 404
        assert other.patch(f"/api/jobs/{job_id}/segments/0",
                           json={"text": "x", "version": 1}).status_code == 404


class client_factory_scope:
    """Open a second anonymous client (new cookie jar) against the same app."""

    def __init__(self, client):
        self.client = client

    def __enter__(self):
        from fastapi.testclient import TestClient

        self._client = TestClient(self.client.app)
        self._client.__enter__()
        return self._client

    def __exit__(self, *exc):
        self._client.__exit__(*exc)
