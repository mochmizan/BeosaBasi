"""TK-002 dev seed now feeds the real routers (worker demo stays working)."""

from __future__ import annotations

from conftest import WORKER_HEADERS, submit_result
from fastapi.testclient import TestClient

from api.app import create_app
from api.config import Settings
from api.storage import MemoryStorage


def test_dev_seed_round_trip_through_real_routes(tmp_path, monkeypatch):
    monkeypatch.setenv("BEOSABASI_FAKE", "1")
    settings = Settings(
        db_path=tmp_path / "dev.db",
        sweeper_enabled=False,
        worker_token="test-token",
        ip_hash_salt="test-salt",
    )
    storage = MemoryStorage()
    with TestClient(create_app(settings=settings, storage=storage)) as client:
        seeded = client.post("/dev/jobs", json={"language": "id",
                                                "diarization": True})
        assert seeded.status_code == 201
        job_id = seeded.json()["job_id"]
        assert seeded.json()["state"] == "queued"
        keys = [key for key, _size in storage.list_keys("dev/")]
        assert len(keys) == 1

        claimed = client.post("/worker/v1/jobs/claim?wait=0",
                              headers=WORKER_HEADERS)
        assert claimed.status_code == 200
        assert claimed.json()["job_id"] == job_id

        assert submit_result(client, job_id, diarization=True).status_code == 200
        transcript = client.get(f"/api/jobs/{job_id}/transcript").json()
        assert len(transcript["segments"]) == 2
        assert len(transcript["speakers"]) == 2
