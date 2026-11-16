"""TK-030: HTTP client for the worker API (PRD 4.7).

Claim is atomic server-side; 204 means the queue is empty. Heartbeat
returns the cancel flag — on True the worker stops and deletes work files.
Connection errors back off; auth/version errors fail fast.
"""

from __future__ import annotations

import time

import httpx

from worker.config import WorkerConfig

VERSION = "0.1.0"


class WorkerAuthError(RuntimeError):
    """Token ditolak — perbaiki WORKER_TOKEN."""


class WorkerVersionError(RuntimeError):
    """Versi pekerja ditolak — perbarui dulu."""


class WorkerClient:
    def __init__(self, config: WorkerConfig,
                 client: httpx.Client | None = None) -> None:
        self.config = config
        self._client = client or httpx.Client(
            base_url=config.api_url, timeout=60.0,
            headers={
                "Authorization": f"Bearer {config.token}",
                "X-Worker-Id": config.worker_id,
            })

    def close(self) -> None:
        self._client.close()

    def ping(self) -> dict:
        resp = self._client.post("/worker/v1/ping",
                                 json={"worker_id": self.config.worker_id,
                                       "version": VERSION})
        if resp.status_code == 401:
            raise WorkerAuthError("token pekerja ditolak")
        resp.raise_for_status()
        body = resp.json()
        if body.get("update_required"):
            raise WorkerVersionError("versi pekerja ditolak")
        return body

    def claim(self, wait: int | None = None) -> dict | None:
        resp = self._client.post("/worker/v1/jobs/claim",
                                 params={"wait": wait or self.config.claim_wait})
        if resp.status_code == 204:
            return None
        if resp.status_code == 401:
            raise WorkerAuthError("token pekerja ditolak")
        resp.raise_for_status()
        return resp.json()

    def heartbeat(self, job_id: str, stage: str,
                  progress: float | None = None) -> bool:
        """Return True when the server asks for cancel."""
        payload: dict = {"stage": stage}
        if progress is not None:
            payload["progress_percent"] = progress
        resp = self._client.post(f"/worker/v1/jobs/{job_id}/heartbeat",
                                 json=payload)
        resp.raise_for_status()
        return bool(resp.json().get("cancel", False))

    def submit_result(self, job_id: str, result: dict) -> None:
        resp = self._client.post(f"/worker/v1/jobs/{job_id}/result",
                                 json=result)
        resp.raise_for_status()

    def submit_fail(self, job_id: str, code: str,
                    retryable: bool, detail: str = "") -> None:
        resp = self._client.post(
            f"/worker/v1/jobs/{job_id}/fail",
            json={"code": code, "retryable": retryable, "detail": detail})
        resp.raise_for_status()

    def download(self, url: str, dest: str) -> str:
        """Stream audio to dest. No transcript text ever touches logs."""
        with self._client.stream("GET", url, timeout=300.0) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as fh:
                fh.writelines(resp.iter_bytes(1 << 20))
        return dest


def with_backoff(attempt: int, base: float = 1.0, cap: float = 30.0) -> None:
    time.sleep(min(cap, base * (2 ** attempt)))
