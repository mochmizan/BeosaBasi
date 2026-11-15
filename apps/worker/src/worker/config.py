"""TK-030: worker configuration (env + CLI, no secrets in repo).

Token only comes from the environment (``WORKER_TOKEN``). The ``.env``
file is local-only and never committed.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field


def _worker_id() -> str:
    return os.environ.get("WORKER_ID") or f"laptop-{uuid.uuid4().hex[:8]}"


@dataclass(frozen=True)
class WorkerConfig:
    api_url: str = "http://localhost:8000"
    token: str = ""
    worker_id: str = field(default_factory=_worker_id)
    version: str = "0.1.0"
    workdir: str = "var/work"
    model: str = "large-v3-turbo"
    compute_type: str = "int8_float16"
    beam_size: int = 5
    vad: bool = True
    language: str | None = "id"
    device: str = "cuda"
    claim_wait: int = 25
    heartbeat_seconds: float = 30.0
    min_battery_percent: int = 30
    max_gpu_temp_c: int = 85

    @classmethod
    def from_env(cls, api_url: str | None = None, **overrides) -> WorkerConfig:
        token = os.environ.get("WORKER_TOKEN", "")
        base = {
            "api_url": api_url or os.environ.get("WORKER_API_URL",
                                                 "http://localhost:8000"),
            "token": token,
            "workdir": os.environ.get("WORKER_DIR", "var/work"),
            "model": os.environ.get("WORKER_MODEL", "large-v3-turbo"),
        }
        base.update(overrides)
        return cls(**base)  # type: ignore[arg-type]

    def require_token(self) -> WorkerConfig:
        if not self.token:
            raise SystemExit("WORKER_TOKEN kosong. Set di environment, "
                             "jangan taruh di repo.")
        return self
