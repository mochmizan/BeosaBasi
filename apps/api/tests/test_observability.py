"""TK-029: admin metrics, JSON logs without filenames or transcript text."""

from __future__ import annotations

import json
import logging

from conftest import completed_job, upload_job

ADMIN = {"X-Admin-Token": "test-admin"}


def test_metrics_requires_token(client):
    assert client.get("/api/admin/metrics").status_code == 401
    assert client.get("/api/admin/metrics",
                      headers={"X-Admin-Token": "salah"}).status_code == 401


def test_metrics_disabled_without_admin_token(client_factory):
    assert client_factory(admin_token="").get("/api/admin/metrics").status_code == 404


def test_metrics_payload(client, storage):
    completed_job(client, storage, duration=60.0)
    metrics = client.get("/api/admin/metrics", headers=ADMIN).json()
    assert metrics["job_per_status"]["completed"] == 1
    assert metrics["median_xrt"] == 8.0
    assert metrics["penyimpanan"]["terpakai_byte"] > 0
    assert isinstance(metrics["pekerja"], list)


def test_logs_never_contain_filename_or_text(client, caplog):
    caplog.set_level(logging.INFO)
    uploaded = upload_job(client, client.app.state.storage,
                          filename="rahasia-pribadi.mp3")
    claimed = client.post("/worker/v1/jobs/claim?wait=0",
                          headers={"Authorization": "Bearer test-token",
                                   "X-Worker-Id": "w1"}).json()
    from conftest import submit_result

    submit_result(client, claimed["job_id"], text="isi transkrip sangat rahasia")
    client.get(f"/api/jobs/{uploaded['job_id']}/transcript")

    dumped = "\n".join(json.dumps(record.__dict__, default=str, ensure_ascii=False)
                       for record in caplog.records)
    assert "rahasia-pribadi" not in dumped
    assert "sangat rahasia" not in dumped
    # Access logs still carry the useful observability fields.
    assert any(record.getMessage() == "permintaan" for record in caplog.records)


def test_orphan_objects_visible_in_admin_storage(client, storage):
    storage.put_object("uploads/ops/nyasar", b"x")
    metrics = client.get("/api/admin/metrics", headers=ADMIN).json()
    assert metrics["penyimpanan"]["terpakai_byte"] == 1
    assert metrics["audit_k4"]["objek_yatim"] == 1
    assert metrics["audit_k4"]["byte_objek_yatim"] == 1
