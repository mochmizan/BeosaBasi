"""DB row -> contract model mapping. Keeps route handlers free of column names."""

from __future__ import annotations

from fastapi import Request

from api import dal, schemas
from api.errors import ApiError


def job_model(row: dict) -> schemas.Job:
    return schemas.Job(
        job_id=row["id"],
        state=row["state"],
        stage=row.get("stage"),
        filename=row.get("nama_berkas_asli", ""),
        size_bytes=int(row.get("ukuran_byte") or 0),
        duration_seconds=row.get("durasi_detik"),
        language=row.get("bahasa") or "id",
        diarization=bool(row.get("diarisasi")),
        billed_minutes=float(row.get("menit_dikenakan") or 0.0),
        attempts=int(row.get("percobaan") or 0),
        error_code=row.get("kode_galat") or None,
        created_at=row["dibuat_pada"],
        finished_at=row.get("selesai_pada"),
    )


def job_summary_model(row: dict) -> schemas.JobSummary:
    return schemas.JobSummary(**job_model(row).model_dump())


def segment_model(row: dict) -> schemas.Segment:
    return schemas.Segment(
        index=int(row["urut"]),
        start=float(row["mulai"]),
        end=float(row["selesai"]),
        text=row["teks"],
        confidence=float(row["keyakinan"]),
        speaker_id=row.get("speaker_id"),
        edited=bool(row.get("disunting")),
        version=int(row["versi"]),
    )


def speaker_model(row: dict) -> schemas.Speaker:
    return schemas.Speaker(
        speaker_id=row["speaker_id"],
        label=row["label_asli"],
        display_name=row["nama_tampil"],
    )


def transcript_model(job_id: str, segments: list[dict],
                     speakers: list[dict]) -> schemas.Transcript:
    return schemas.Transcript(
        job_id=job_id,
        segments=[segment_model(s) for s in segments],
        speakers=[speaker_model(s) for s in speakers],
    )


def job_or_404(conn, job_id: str, user_id: str) -> dict:
    job = dal.job_get(conn, job_id)
    if job is None or job["user_id"] != user_id:
        raise ApiError(404, "INTERNAL", "Pekerjaan tidak ditemukan.")
    return job


def worker_job_or_404(conn, job_id: str) -> dict:
    job = dal.job_get(conn, job_id)
    if job is None:
        raise ApiError(404, "INTERNAL", "Pekerjaan tidak ditemukan.")
    return job


def request_ip_hash(request: Request) -> str:
    return request.state.ip_hash
