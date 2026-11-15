"""TK-027: exports TXT, SRT, VTT, DOCX (US-04).

Always built from current DB rows, so edits and speaker names are reflected.
Works after audio deletion. SRT/VTT follow the standard timestamp formats and
the `Nama:` prefix for every cue that has a speaker.
"""

from __future__ import annotations

import io
import sqlite3

from fastapi import APIRouter, Depends, Query, Response

from api import dal, ratelimit
from api.config import Settings
from api.deps import db_conn, get_settings, identity
from api.errors import ApiError
from api.identity import Identity
from api.views import job_or_404

router = APIRouter(prefix="/api/jobs", tags=["export"])

MEDIA_TYPES = {
    "txt": "text/plain; charset=utf-8",
    "srt": "application/x-subrip; charset=utf-8",
    "vtt": "text/vtt; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document",
}


def _clock(seconds: float, *, millis_sep: str) -> str:
    total_ms = max(round(seconds * 1000), 0)
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{millis_sep}{ms:03d}"


def _lines(segments: list[dict], speakers: dict[str, str]) -> list[tuple[float, float, str]]:
    out: list[tuple[float, float, str]] = []
    for seg in segments:
        name = speakers.get(seg.get("speaker_id") or "", "")
        text = (seg.get("teks") or "").strip()
        label = f"{name}: {text}" if name else text
        out.append((float(seg["mulai"]), float(seg["selesai"]), label))
    return out


def render_txt(segments: list[dict], speakers: dict[str, str]) -> str:
    rows = _lines(segments, speakers)
    if not rows:
        return ""
    return "\n".join(f"[{_clock(start, millis_sep='.')[:8]}] {text}"
                     for start, _end, text in rows) + "\n"


def render_srt(segments: list[dict], speakers: dict[str, str]) -> str:
    rows = _lines(segments, speakers)
    blocks = []
    for index, (start, end, text) in enumerate(rows, start=1):
        end = max(end, start)
        blocks.append(
            f"{index}\n"
            f"{_clock(start, millis_sep=',')} --> {_clock(end, millis_sep=',')}\n"
            f"{text}\n"
        )
    return "\n".join(blocks)


def render_vtt(segments: list[dict], speakers: dict[str, str]) -> str:
    rows = _lines(segments, speakers)
    parts = ["WEBVTT", ""]
    for start, end, text in rows:
        end = max(end, start)
        parts.append(
            f"{_clock(start, millis_sep='.')} --> {_clock(end, millis_sep='.')}\n"
            f"{text}\n"
        )
    return "\n".join(parts)


def render_docx(segments: list[dict], speakers: dict[str, str]) -> bytes:
    from docx import Document

    document = Document()
    document.add_heading("Transkrip BeosaBasi", level=1)
    for start, _end, text in _lines(segments, speakers):
        document.add_paragraph(f"[{_clock(start, millis_sep='.')[:8]}] {text}")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


@router.get("/{job_id}/export")
def export_transcript(job_id: str,
                      format: str = Query(...),
                      conn: sqlite3.Connection = Depends(db_conn),
                      ident: Identity = Depends(identity),
                      settings: Settings = Depends(get_settings)) -> Response:
    if format not in MEDIA_TYPES:
        raise ApiError(400, "INVALID_FILE",
                       "Format ekspor harus txt, srt, vtt, atau docx.")
    ratelimit.enforce(conn, f"export:{ident.ip_hash}", settings.exports_per_hour)
    job = job_or_404(conn, job_id, ident.user_id)
    segments = dal.segments_list(conn, job_id)
    if not segments:
        if job["state"] in {"uploading", "queued", "processing"}:
            raise ApiError(409, "INTERNAL",
                           "Transkrip belum tersedia. Tunggu proses selesai.")
        raise ApiError(404, "INTERNAL", "Transkrip tidak ditemukan.")

    speakers = {s["speaker_id"]: s["nama_tampil"]
                for s in dal.speakers_list(conn, job_id)}
    if format == "txt":
        body: bytes = render_txt(segments, speakers).encode("utf-8")
    elif format == "srt":
        body = render_srt(segments, speakers).encode("utf-8")
    elif format == "vtt":
        body = render_vtt(segments, speakers).encode("utf-8")
    else:
        body = render_docx(segments, speakers)

    filename = f"transkrip-{job_id[:8]}.{format}"
    return Response(
        content=body,
        media_type=MEDIA_TYPES[format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
