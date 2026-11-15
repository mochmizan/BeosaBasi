"""TK-026: transcript reads, segment edits, speakers, signed audio URL."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from api import dal, schemas
from api.config import Settings
from api.db import transaction
from api.deps import db_conn, get_settings, get_storage, identity
from api.errors import ApiError
from api.identity import Identity
from api.storage import Storage, StorageError
from api.timeutil import iso
from api.views import job_or_404, segment_model, speaker_model, transcript_model

router = APIRouter(prefix="/api/jobs", tags=["transcript"])


@router.get("/{job_id}/transcript", response_model=schemas.Transcript)
def get_transcript(job_id: str,
                   conn: sqlite3.Connection = Depends(db_conn),
                   ident: Identity = Depends(identity)) -> schemas.Transcript:
    job_or_404(conn, job_id, ident.user_id)
    return transcript_model(job_id, dal.segments_list(conn, job_id),
                            dal.speakers_list(conn, job_id))


def _segment_or_404(conn, job_id: str, urut: int) -> dict:
    for row in dal.segments_list(conn, job_id):
        if int(row["urut"]) == urut:
            return row
    raise ApiError(404, "INTERNAL", "Segmen tidak ditemukan.")


@router.patch("/{job_id}/segments/{n}", response_model=schemas.Segment)
def patch_segment(job_id: str, n: int, body: schemas.SegmentPatch,
                  conn: sqlite3.Connection = Depends(db_conn),
                  ident: Identity = Depends(identity)) -> schemas.Segment:
    job_or_404(conn, job_id, ident.user_id)
    segment = _segment_or_404(conn, job_id, n)
    if body.version != int(segment["versi"]):
        raise ApiError(409, "VERSION_CONFLICT")

    fields = body.model_fields_set
    if "text" not in fields and "speaker_id" not in fields:
        raise ApiError(400, "INVALID_FILE", "Tidak ada perubahan yang dikirim.")
    teks = body.text if "text" in fields else segment["teks"]
    if teks is None:
        teks = ""
    if len(teks) > 20000:
        raise ApiError(400, "INVALID_FILE", "Teks segmen terlalu panjang.")
    speaker_id = body.speaker_id if "speaker_id" in fields else segment["speaker_id"]
    if speaker_id is not None and dal.speakers_list(conn, job_id):
        known = {s["speaker_id"] for s in dal.speakers_list(conn, job_id)}
        if speaker_id not in known:
            raise ApiError(400, "INVALID_FILE", "Pembicara tidak dikenal.")

    with transaction(conn):
        updated = dal.segment_update(conn, job_id, n, body.version, teks, speaker_id)
        if not updated:
            raise ApiError(409, "VERSION_CONFLICT")
        if "text" in fields:
            changed = max(len(segment["teks"] or ""), len(teks))
            dal.metrics_add_edit(conn, job_id, changed)
    refreshed = _segment_or_404(conn, job_id, n)
    return segment_model(refreshed)


@router.patch("/{job_id}/speakers/{speaker_id}", response_model=schemas.Speaker)
def rename_speaker(job_id: str, speaker_id: str,
                   body: schemas.SpeakerRename,
                   conn: sqlite3.Connection = Depends(db_conn),
                   ident: Identity = Depends(identity)) -> schemas.Speaker:
    job_or_404(conn, job_id, ident.user_id)
    name = body.display_name.strip()
    if not 1 <= len(name) <= 60:
        raise ApiError(400, "INVALID_FILE",
                       "Nama pembicara harus 1 sampai 60 karakter.")
    if not dal.speaker_rename(conn, job_id, speaker_id, name):
        raise ApiError(404, "INTERNAL", "Pembicara tidak ditemukan.")
    for speaker in dal.speakers_list(conn, job_id):
        if speaker["speaker_id"] == speaker_id:
            return speaker_model(speaker)
    raise ApiError(404, "INTERNAL", "Pembicara tidak ditemukan.")


@router.get("/{job_id}/audio-url", response_model=schemas.AudioUrl)
def get_audio_url(job_id: str,
                  conn: sqlite3.Connection = Depends(db_conn),
                  ident: Identity = Depends(identity),
                  settings: Settings = Depends(get_settings),
                  storage: Storage = Depends(get_storage)) -> schemas.AudioUrl:
    job = job_or_404(conn, job_id, ident.user_id)
    if not job["r2_key"] or job["audio_dihapus_pada"] or job["state"] == "uploading":
        raise ApiError(404, "AUDIO_GONE")
    try:
        url, expires = storage.sign_get(job["r2_key"],
                                        settings.presign_ttl_seconds)
    except StorageError as exc:
        raise ApiError(404, "AUDIO_GONE") from exc
    return schemas.AudioUrl(url=url, expires_at=iso(expires))
