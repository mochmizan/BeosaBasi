"""TK-031: media validation + normalization (PRD AI-01, AI-02, R-05).

ffprobe first (container, duration, audio streams), then ffmpeg to WAV
16 kHz mono. ffmpeg runs with a timeout, protocol whitelist, no network.
Browser MediaRecorder WebM/Opus files may omit container header duration
("N/A"), so normalize() falls back to measuring the decoded WAV duration.
Error codes match contracts/worker-protocol.md (subset used by /fail).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import wave

MAX_DURATION_SECONDS = 90 * 60
FFMPEG_TIMEOUT_SECONDS = 10 * 60
PROBE_TIMEOUT_SECONDS = 60
# ffprobe format_name -> us. Only playlist container families we accept
# (R-05). The server re-checks the container at complete; this is the
# worker-side fast reject. Extension is ignored: work files are extensionless.
ALLOWED_FORMATS = frozenset({
    "wav", "mp3", "flac", "ogg", "opus",
    "mov", "mp4", "m4a",  # MP4/M4A family
    "matroska", "webm",  # WebM/Opus family
})


class MediaError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def _tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise MediaError("FFMPEG_ERROR", f"{name} tidak ditemukan di PATH.")
    return path


def _parse_duration(info: dict) -> float | None:
    raw = info.get("format", {}).get("duration")
    if raw not in (None, "", "N/A"):
        try:
            return float(raw)
        except ValueError:
            pass
    for stream in info.get("streams", []):
        s_dur = stream.get("duration")
        if s_dur not in (None, "", "N/A"):
            try:
                return float(s_dur)
            except ValueError:
                continue
    return None


def probe(path: str, *, allow_unknown_duration: bool = False) -> dict:
    """Return {duration, has_audio, format}. Raises MediaError otherwise."""
    try:
        out = subprocess.run(
            [_tool("ffprobe"), "-v", "error", "-show_entries",
             "format=format_name,duration:stream=codec_type,duration",
             "-of", "json", path],
            check=False, capture_output=True, text=True,
            timeout=PROBE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        raise MediaError("CORRUPT_MEDIA",
                         "media tidak bisa dibaca dalam 60 detik.") from exc
    if out.returncode != 0:
        raise MediaError("CORRUPT_MEDIA", "berkas media rusak / tak dikenal.")
    try:
        info = json.loads(out.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise MediaError("CORRUPT_MEDIA", "berkas media rusak.") from exc
    fmt = (info.get("format", {}).get("format_name", "") or "").split(",")[0]
    if fmt not in ALLOWED_FORMATS:
        raise MediaError("UNSUPPORTED_TYPE",
                         f"format {fmt or '(tak dikenal)'} tidak didukung.")
    streams = info.get("streams", [])
    if not any(s.get("codec_type") == "audio" for s in streams):
        raise MediaError("NO_AUDIO_STREAM", "tidak ada aliran audio.")
    duration = _parse_duration(info)
    if duration is None:
        if allow_unknown_duration and fmt in {"matroska", "webm", "ogg", "opus"}:
            return {"duration": 0.0, "has_audio": True, "format": fmt}
        raise MediaError("CORRUPT_MEDIA", "durasi tak terbaca.")
    if duration <= 0:
        if allow_unknown_duration and fmt in {"matroska", "webm", "ogg", "opus"}:
            return {"duration": 0.0, "has_audio": True, "format": fmt}
        raise MediaError("CORRUPT_MEDIA", "durasi audio nol.")
    if duration > MAX_DURATION_SECONDS:
        raise MediaError("TOO_LONG",
                         f"durasi {duration / 60:.0f} menit melebihi 90 menit.")
    return {"duration": duration, "has_audio": True, "format": fmt}


def normalize(src: str, dest: str) -> dict:
    """ffmpeg -> WAV 16 kHz mono. Returns probe info of the source."""
    info = probe(src, allow_unknown_duration=True)
    cmd = [_tool("ffmpeg"), "-y", "-v", "error",
           "-protocol_whitelist", "file,pipe",
           "-i", src, "-ac", "1", "-ar", "16000", "-sample_fmt", "s16",
           dest]
    try:
        out = subprocess.run(cmd, check=False, capture_output=True, text=True,
                             timeout=FFMPEG_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        raise MediaError("FFMPEG_ERROR",
                         "normalisasi lewat 10 menit.", retryable=True) from exc
    if out.returncode != 0:
        raise MediaError("FFMPEG_ERROR", "ffmpeg gagal membaca berkas.")
    if info["duration"] <= 0:
        try:
            with wave.open(dest, "rb") as wav:
                frames = wav.getnframes()
                rate = wav.getframerate() or 16000
                info["duration"] = frames / float(rate)
        except Exception as exc:
            raise MediaError("CORRUPT_MEDIA", "durasi WAV hasil nol.") from exc
    if info["duration"] <= 0:
        raise MediaError("CORRUPT_MEDIA", "durasi audio nol.")
    if info["duration"] > MAX_DURATION_SECONDS:
        raise MediaError(
            "TOO_LONG",
            f"durasi {info['duration'] / 60:.0f} menit melebihi 90 menit.",
        )
    return info
