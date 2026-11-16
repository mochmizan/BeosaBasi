"""TK-031: defect media rejected fast; good media normalizes."""

import shutil
import subprocess
import wave

import pytest

from worker import media
from worker.media import MediaError, normalize, probe

needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe tidak ada")


def _wav(path, seconds=1):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * 16000 * seconds)


@needs_ffmpeg
def test_probe_rejects_no_audio_stream(tmp_path):
    # valid container, no audio: 1x1 mp4 without audio track
    mp4 = tmp_path / "bisU.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "color=c=black:s=16x16:d=1",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(mp4)],
                   check=True, timeout=60)
    with pytest.raises(MediaError) as exc:
        probe(str(mp4))
    assert exc.value.code == "NO_AUDIO_STREAM"


@needs_ffmpeg
def test_probe_rejects_corrupt(tmp_path):
    bad = tmp_path / "rusak.mp3"
    bad.write_bytes(b"\xff\xfe\x00bukan-audio")
    with pytest.raises(MediaError) as exc:
        probe(str(bad))
    assert exc.value.code in {"CORRUPT_MEDIA", "NO_AUDIO_STREAM"}


def test_probe_rejects_type(tmp_path):
    # valid container outside the allowlist: avi with audio
    avi = tmp_path / "video.avi"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "color=c=blue:s=16x16:d=1",
                    "-f", "lavfi", "-i", "sine=frequency=440:d=1:r=16000",
                    "-c:v", "mpeg4", "-c:a", "mp3", str(avi)],
                   check=True, timeout=60)
    with pytest.raises(MediaError) as exc:
        probe(str(avi))
    assert exc.value.code == "UNSUPPORTED_TYPE"


def test_probe_extensionless_wav_ok(tmp_path):
    src = tmp_path / "ok.wav"
    _wav(src)
    raw = tmp_path / "audio.bin"
    raw.write_bytes(src.read_bytes())
    info = probe(str(raw))
    assert info["duration"] == pytest.approx(1.0, abs=0.05)


@needs_ffmpeg
def test_normalize_good_wav(tmp_path):
    src = tmp_path / "ok.wav"
    _wav(src)
    dest = tmp_path / "norm.wav"
    info = normalize(str(src), str(dest))
    assert info["duration"] == pytest.approx(1.0, abs=0.05)
    with wave.open(str(dest), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getframerate() == 16000


def test_probe_rejects_too_long(monkeypatch, tmp_path):
    src = tmp_path / "ok.wav"
    _wav(src)
    monkeypatch.setattr(media, "MAX_DURATION_SECONDS", 0.5)
    with pytest.raises(MediaError) as exc:
        probe(str(src))
    assert exc.value.code == "TOO_LONG"



@needs_ffmpeg
def test_normalize_webm_with_missing_format_duration(monkeypatch, tmp_path):
    src = tmp_path / "ok.wav"
    _wav(src, seconds=2)
    dest = tmp_path / "norm.wav"
    orig_parse = media._parse_duration
    monkeypatch.setattr(media, "_parse_duration", lambda _info: None)
    monkeypatch.setattr(
        media,
        "probe",
        lambda path, allow_unknown_duration=False: {
            "duration": 0.0,
            "has_audio": True,
            "format": "webm",
        }
        if allow_unknown_duration
        else orig_parse({}),
    )
    info = normalize(str(src), str(dest))
    assert info["duration"] == pytest.approx(2.0, abs=0.05)
