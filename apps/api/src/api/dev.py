"""DEV-ONLY seeding endpoint for the local fake worker (TK-002).

Active only when BEOSABASI_FAKE=1. Unlike the old in-memory fake, this seeds a
real `queued` job in SQLite and writes a self-made silent WAV to storage, so
`worker demo` exercises the real claim/heartbeat/result/transcript routers.
No user audio is involved.
"""

from __future__ import annotations

import io
import sqlite3
import uuid
import wave

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api import dal, schemas
from api.db import transaction
from api.deps import db_conn, get_storage, identity
from api.errors import ApiError
from api.identity import Identity
from api.storage import Storage, StorageError
from api.timeutil import iso, utcnow
from api.views import job_model

router = APIRouter(tags=["dev"])

SAMPLE_RATE = 16000


def _silent_wav(seconds: float = 1.0) -> bytes:
    buffer = io.BytesIO()
    frames = b"\x00\x00" * int(SAMPLE_RATE * seconds)
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(frames)
    return buffer.getvalue()


class DevJobSeed(BaseModel):
    language: str = "id"
    diarization: bool = False
    duration_seconds: float = 60.0


@router.post("/dev/jobs", response_model=schemas.Job, status_code=201)
def dev_seed_job(seed: DevJobSeed,
                 conn: sqlite3.Connection = Depends(db_conn),
                 ident: Identity = Depends(identity),
                 storage: Storage = Depends(get_storage)) -> schemas.Job:
    """Create one real queued job with self-made silence (no R2/GPU needed)."""
    job_id = str(uuid.uuid4())
    key = f"dev/{ident.user_id}/{job_id}.wav"
    payload = _silent_wav()
    try:
        storage.put_object(key, payload, "audio/wav")
    except StorageError as exc:
        raise ApiError(503, "INTERNAL",
                       "Penyimpanan lokal belum siap. Jalankan dev-up dulu.") from exc
    now_iso = iso(utcnow())
    try:
        with transaction(conn):
            dal.job_create(
                conn, job_id=job_id, user_id=ident.user_id, state="queued",
                dibuat_pada=now_iso, nama_berkas_asli="contoh-hening.wav",
                r2_key=key, ukuran_byte=len(payload), bahasa=seed.language,
                durasi_detik=seed.duration_seconds,
                diarisasi=1 if seed.diarization else 0,
            )
    except Exception:
        try:
            storage.delete(key)
        except StorageError:
            pass
        raise
    return job_model(dal.job_get(conn, job_id) or {})
