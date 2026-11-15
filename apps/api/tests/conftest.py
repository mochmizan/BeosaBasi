"""Shared fixtures: real FastAPI app + SQLite tmp DB + in-memory storage."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.config import Settings
from api.storage import MemoryStorage

WORKER_HEADERS = {"Authorization": "Bearer test-token", "X-Worker-Id": "w1"}


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(
        db_path=tmp_path / "test.db",
        sweeper_enabled=False,
        worker_token="test-token",
        admin_token="test-admin",
        ip_hash_salt="test-salt",
        presign_ttl_seconds=900,
    )


@pytest.fixture()
def storage() -> MemoryStorage:
    return MemoryStorage()


@pytest.fixture()
def app(settings: Settings, storage: MemoryStorage):
    return create_app(settings=settings, storage=storage)


@pytest.fixture()
def client(app):
    with TestClient(app) as test_client:
        yield test_client


def make_client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings=settings, storage=MemoryStorage()))


@pytest.fixture()
def client_factory(settings: Settings):
    clients: list[TestClient] = []

    def build(**overrides) -> TestClient:
        made = TestClient(create_app(settings=replace(settings, **overrides),
                                     storage=MemoryStorage()))
        clients.append(made)
        return made

    yield build
    for made in clients:
        made.close()


def init_upload(client: TestClient, *, size: int = 1024,
                filename: str = "rapat.mp3",
                content_type: str = "audio/mpeg",
                diarization: bool = False,
                language: str = "id") -> dict:
    payload = {
        "filename": filename,
        "size_bytes": size,
        "content_type": content_type,
        "language": language,
        "diarization": diarization,
        "turnstile_token": "stub-token",
    }
    if diarization:
        payload["min_speakers"] = 1
        payload["max_speakers"] = 4
    resp = client.post("/api/uploads", json=payload)
    return {"status": resp.status_code, "body": resp.json()}


def _valid_audio(size: int) -> bytes:
    head = b"ID3\x04\x00\x00\x00\x00\x00\x00"
    return (head + b"\x00" * max(size - len(head), 0))[:size]


def upload_job(client: TestClient, storage: MemoryStorage, *,
               size: int = 2048, filename: str = "rapat.mp3",
               content_type: str = "audio/mpeg",
               diarization: bool = False,
               data: bytes | None = None) -> dict:
    """Run the whole multipart flow and return the completed Job payload."""
    started = init_upload(client, size=size, filename=filename,
                          content_type=content_type, diarization=diarization)
    assert started["status"] == 201, started
    session = started["body"]
    payload = data if data is not None else _valid_audio(size)
    upload_id = session["upload_id"]
    part_size = session["part_size"]
    parts = []
    for number in range(1, session["part_count"] + 1):
        chunk = payload[(number - 1) * part_size: number * part_size]
        etag = storage.put_part(upload_id, number, chunk)
        parts.append({"part_number": number, "etag": etag})
    resp = client.post(f"/api/uploads/{session['job_id']}/complete",
                       json={"parts": parts})
    return {"status": resp.status_code, "body": resp.json(),
            "job_id": session["job_id"]}


def claim(client: TestClient) -> dict:
    resp = client.post("/worker/v1/jobs/claim?wait=0", headers=WORKER_HEADERS)
    assert resp.status_code == 200, resp.text
    return resp.json()


def submit_result(client: TestClient, job_id: str, *, duration: float = 60.0,
                  diarization: bool = False, xrt: float = 8.0,
                  text: str = "selamat pagi semua") -> dict:
    segments = [{
        "index": 0, "start": 0.0, "end": 4.2, "text": text,
        "confidence": 0.93,
        "speaker_id": "spk1" if diarization else None,
        "edited": False, "version": 1,
    }, {
        "index": 1, "start": 4.2, "end": 9.8, "text": "terima kasih",
        "confidence": 0.91,
        "speaker_id": "spk2" if diarization else None,
        "edited": False, "version": 1,
    }]
    speakers = ([{"speaker_id": "spk1", "label": "Pembicara 1",
                  "display_name": "Pembicara 1"},
                 {"speaker_id": "spk2", "label": "Pembicara 2",
                  "display_name": "Pembicara 2"}] if diarization else [])
    resp = client.post(f"/worker/v1/jobs/{job_id}/result", headers=WORKER_HEADERS,
                       json={
                           "segments": segments,
                           "speakers": speakers,
                           "diarization_available": diarization,
                           "duration_seconds": duration,
                           "xrt": xrt,
                           "model_version": "fake-test",
                           "low_confidence_ratio": 0.1,
                       })
    return resp


def completed_job(client: TestClient, storage: MemoryStorage, *,
                  duration: float = 60.0, diarization: bool = False,
                  text: str = "selamat pagi semua") -> str:
    uploaded = upload_job(client, storage, diarization=diarization)
    assert uploaded["status"] == 200, uploaded
    claimed = claim(client)
    resp = submit_result(client, claimed["job_id"], duration=duration,
                         diarization=diarization, text=text)
    assert resp.status_code == 200, resp.text
    return claimed["job_id"]
