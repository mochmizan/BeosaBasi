"""Transcription benchmark harness (TK-010).

Runs the transcription pipeline over a folder of audio and writes one JSON per
clip plus a ``summary.json``, so configurations can be compared:

* ``large-v3-turbo`` vs ``large-v3``
* ``int8_float16`` vs ``float16``
* ``beam_size``, ``batch_size``, VAD on/off

Model load time is measured separately from inference. GPU memory and
temperature are sampled with ``nvidia-smi`` while a clip is transcribed.

``faster-whisper`` is imported lazily: importing this module never requires the
GPU stack, which keeps tests and ``worker doctor`` runnable on any machine.
"""

from __future__ import annotations

import json
import platform
import re
import shutil
import statistics
import subprocess
import threading
import time
import wave
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any, Protocol, Self

AUDIO_SUFFIXES = frozenset(
    {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".opus", ".mp4", ".webm"}
)
DEFAULT_MODEL = "large-v3-turbo"
SCHEMA_VERSION = 1


class BenchError(RuntimeError):
    """Raised when a benchmark run cannot start or finish."""


def _read_wav_mono16k(path: Path) -> Any:
    """WAV -> float32 numpy mono. stdlib only, no av dependency."""
    import numpy as np

    with wave.open(str(path), "rb") as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2:
            raise BenchError(f"bukan WAV mono 16-bit: {path} (jalankan via ffmpeg dulu)")
        if wav.getframerate() != 16000:
            raise BenchError(f"bukan 16 kHz: {path} (jalankan via ffmpeg dulu)")
        raw = wav.readframes(wav.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


@dataclass(frozen=True)
class BenchConfig:
    """Decode / model settings for one comparable benchmark run."""

    model: str = DEFAULT_MODEL
    compute_type: str = "int8_float16"
    beam_size: int = 5
    batch_size: int = 8
    vad: bool = True
    language: str | None = "id"
    device: str = "cuda"

    @property
    def slug(self) -> str:
        parts = [
            self.model,
            self.compute_type,
            f"beam{self.beam_size}",
            f"batch{self.batch_size}",
            "vad" if self.vad else "novad",
        ]
        return "-".join(_slugify(part) for part in parts)


@dataclass
class GpuStats:
    """Peak values observed while a clip was being transcribed."""

    peak_vram_mb: int | None = None
    peak_temp_c: int | None = None


class Transcriber(Protocol):
    """Minimal pipeline surface the harness needs."""

    def load(self) -> float:
        """Load the model and return the load time in seconds."""

    def transcribe(self, audio: Path) -> list[dict[str, Any]]:
        """Return segments with at least ``start``, ``end``, and ``text``."""

    def release(self) -> None:
        """Free model memory."""


class GpuSampler:
    """Poll ``nvidia-smi`` in a background thread.

    Sampling is best effort: without ``nvidia-smi`` the peaks stay ``None`` so a
    CPU-only machine can still smoke-test the harness with ``--fake``.
    """

    def __init__(self, interval: float = 0.2,
                 binary: str | bool | None = True) -> None:
        # True = auto-detect; explicit None/False disables sampling
        # (CPU-only smoke tests); a string forces that binary.
        if binary is True:
            binary = shutil.which("nvidia-smi")
        self.interval = interval
        self.binary = binary or None
        self._peak_vram_mb: int | None = None
        self._peak_temp_c: int | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> Self:
        if self.binary:
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(self.interval * 2, 1.0))

    def _loop(self) -> None:
        while not self._stop.is_set():
            sample = self._sample()
            if sample is not None:
                vram, temp = sample
                if vram is not None:
                    self._peak_vram_mb = max(self._peak_vram_mb or 0, vram)
                if temp is not None:
                    self._peak_temp_c = max(self._peak_temp_c or 0, temp)
            self._stop.wait(self.interval)

    def _sample(self) -> tuple[int | None, int | None] | None:
        if not self.binary:
            return None
        cmd = [
            self.binary,
            "--query-gpu=memory.used,temperature.gpu",
            "--format=csv,noheader,nounits",
        ]
        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if completed.returncode != 0:
            return None
        vrams: list[int] = []
        temps: list[int] = []
        for line in completed.stdout.splitlines():
            fields = [field.strip() for field in line.split(",")]
            if len(fields) != 2:
                continue
            try:
                vrams.append(int(float(fields[0])))
                temps.append(int(float(fields[1])))
            except ValueError:
                continue
        if not vrams:
            return None
        return max(vrams), max(temps)

    def result(self) -> GpuStats:
        return GpuStats(self._peak_vram_mb, self._peak_temp_c)


class FasterWhisperTranscriber:
    """Real pipeline: faster-whisper with VAD, no cross-segment conditioning."""

    def __init__(self, config: BenchConfig) -> None:
        self.config = config
        self._model: Any = None

    def load(self) -> float:
        try:  # expose torch's CUDA DLLs before ctranslate2 loads (Windows)
            import os as _os
            import sys as _sys

            import torch as _torch

            if _sys.platform == "win32":
                _os.add_dll_directory(
                    _os.path.join(_os.path.dirname(_torch.__file__), "lib"))
        except ImportError:
            pass
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:  # pragma: no cover - depends on host install
            raise BenchError(
                "faster-whisper belum terpasang. Jalankan `uv sync` di "
                "apps/worker atau pakai `worker bench --fake` untuk uji asap."
            ) from exc
        started = time.perf_counter()
        self._model = WhisperModel(
            self.config.model,
            device=self.config.device,
            compute_type=self.config.compute_type,
        )
        return time.perf_counter() - started

    def transcribe(self, audio: Path) -> list[dict[str, Any]]:
        if self._model is None:
            raise BenchError("model belum dimuat")
        # faster-whisper 1.2.1 passes metadata_errors to av.open, removed
        # in av 19, so file-path decode is broken. TK-031 normalizes
        # everything to WAV 16 kHz mono via the ffmpeg binary first,
        # then we feed float32 numpy here (stdlib wave, no av).
        payload: Any = _read_wav_mono16k(audio)
        segments, _info = self._model.transcribe(
            payload,
            language=self.config.language,
            beam_size=self.config.beam_size,
            vad_filter=self.config.vad,
            condition_on_previous_text=False,
        )
        return [
            {
                "index": index,
                "start": float(segment.start),
                "end": float(segment.end),
                "text": segment.text.strip(),
                "avg_logprob": float(segment.avg_logprob),
                "no_speech_prob": float(segment.no_speech_prob),
            }
            for index, segment in enumerate(segments)
        ]

    def release(self) -> None:
        self._model = None


class FakeTranscriber:
    """Deterministic stand-in used by ``worker bench --fake`` and tests."""

    def __init__(self, config: BenchConfig | None = None) -> None:
        self.config = config

    def load(self) -> float:
        return 0.0

    def transcribe(self, audio: Path) -> list[dict[str, Any]]:
        duration = audio_duration(audio) or 1.0
        return [
            {
                "index": 0,
                "start": 0.0,
                "end": duration,
                "text": "contoh transkrip",
                "avg_logprob": -0.1,
                "no_speech_prob": 0.01,
            }
        ]

    def release(self) -> None:
        return None


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "default"


def list_audio(folder: Path) -> list[Path]:
    """Return audio files in stable order; reject duplicate stems."""
    if not folder.is_dir():
        raise BenchError(f"folder tidak ditemukan: {folder}")
    clips = sorted(
        (path for path in folder.iterdir() if path.suffix.lower() in AUDIO_SUFFIXES),
        key=lambda path: path.name.lower(),
    )
    if not clips:
        raise BenchError(f"tidak ada berkas audio di {folder}")
    seen: dict[str, Path] = {}
    for path in clips:
        key = path.stem.lower()
        if key in seen:
            raise BenchError(
                f"nama klip ganda: {seen[key].name} dan {path.name} "
                "(ganti nama agar satu klip satu ID)"
            )
        seen[key] = path
    return clips


def audio_duration(path: Path) -> float | None:
    """Duration in seconds via ffprobe, falling back to the wave module."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        try:
            completed = subprocess.run(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.SubprocessError):
            completed = None
        if completed is not None and completed.returncode == 0:
            try:
                return float(completed.stdout.strip())
            except ValueError:
                pass
    if path.suffix.lower() != ".wav":
        return None
    try:
        with wave.open(str(path), "rb") as wav:
            rate = wav.getframerate()
            return wav.getnframes() / rate if rate else None
    except (OSError, wave.Error):
        return None


def _version(distribution: str) -> str | None:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return None


def environment_info() -> dict[str, Any]:
    """Versions and tool availability recorded next to the numbers."""
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "packages": {
            name: _version(name)
            for name in ("faster-whisper", "ctranslate2", "torch", "numpy")
        },
        "nvidia_smi": bool(shutil.which("nvidia-smi")),
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "ffprobe": bool(shutil.which("ffprobe")),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _metrics(seconds: list[float], duration: float | None) -> dict[str, float | None]:
    xrt = [duration / value for value in seconds] if duration else []
    return {
        "median_seconds": statistics.median(seconds),
        "worst_seconds": max(seconds),
        "median_xrt": statistics.median(xrt) if xrt else None,
        "worst_xrt": min(xrt) if xrt else None,
    }


def bench_folder(
    folder: Path,
    config: BenchConfig,
    *,
    repeats: int = 1,
    out_dir: Path | None = None,
    transcriber_factory: Callable[[BenchConfig], Transcriber] | None = None,
    sampler_factory: Callable[[], GpuSampler] | None = None,
    backend: str | None = None,
) -> dict[str, Any]:
    """Benchmark every clip in ``folder`` and write per-clip JSON + summary."""
    if repeats < 1:
        raise BenchError("--repeat harus >= 1")
    clips = list_audio(folder)
    factory = transcriber_factory or FasterWhisperTranscriber
    make_sampler = sampler_factory or GpuSampler
    transcriber = factory(config)
    load_seconds = transcriber.load()
    created_at = datetime.now(UTC).isoformat()

    clip_reports: list[dict[str, Any]] = []
    try:
        for audio in clips:
            duration = audio_duration(audio)
            runs: list[dict[str, Any]] = []
            for _ in range(repeats):
                with make_sampler() as sampler:
                    started = time.perf_counter()
                    segments = transcriber.transcribe(audio)
                    elapsed = time.perf_counter() - started
                    gpu = sampler.result()
                runs.append(
                    {
                        "seconds": round(elapsed, 6),
                        "xrt": round(duration / elapsed, 4) if duration else None,
                        "peak_vram_mb": gpu.peak_vram_mb,
                        "peak_temp_c": gpu.peak_temp_c,
                        "segment_count": len(segments),
                        "segments": segments,
                    }
                )

            seconds = [run["seconds"] for run in runs]
            metrics = _metrics(seconds, duration)
            clip_reports.append(
                {
                    "clip": audio.stem,
                    "audio": str(audio),
                    "duration_seconds": duration,
                    "load_seconds": round(load_seconds, 6),
                    "repeats": runs,
                    "median_seconds": round(metrics["median_seconds"], 6),
                    "worst_seconds": round(metrics["worst_seconds"], 6),
                    "median_xrt": metrics["median_xrt"],
                    "worst_xrt": metrics["worst_xrt"],
                    "peak_vram_mb": max(
                        (run["peak_vram_mb"] or 0 for run in runs), default=0
                    )
                    or None,
                    "peak_temp_c": max(
                        (run["peak_temp_c"] or 0 for run in runs), default=0
                    )
                    or None,
                    "segment_count": max(run["segment_count"] for run in runs),
                }
            )
    finally:
        transcriber.release()

    total_seconds = sum(
        report["duration_seconds"] or 0.0 for report in clip_reports
    )
    duration_xrt = [
        report["median_xrt"] for report in clip_reports if report["median_xrt"]
    ]
    summary = {
        "schema": SCHEMA_VERSION,
        "created_at": created_at,
        "backend": backend or _backend_name(factory),
        "folder": str(folder),
        "config": asdict(config),
        "config_slug": config.slug,
        "repeat": repeats,
        "load_seconds": round(load_seconds, 6),
        "clips": clip_reports,
        "aggregate": {
            "clip_count": len(clip_reports),
            "total_audio_seconds": round(total_seconds, 3),
            "median_xrt": round(statistics.median(duration_xrt), 4)
            if duration_xrt
            else None,
            "worst_xrt": round(min(duration_xrt), 4) if duration_xrt else None,
            "peak_vram_mb": max(
                (report["peak_vram_mb"] or 0 for report in clip_reports), default=0
            )
            or None,
            "peak_temp_c": max(
                (report["peak_temp_c"] or 0 for report in clip_reports), default=0
            )
            or None,
        },
        "environment": environment_info(),
    }

    if out_dir is not None:
        run_dir = out_dir / config.slug
        for report in clip_reports:
            _write_json(run_dir / f"{report['clip']}.json", report)
        summary["run_dir"] = str(run_dir)
        _write_json(run_dir / "summary.json", summary)

    return summary


def _backend_name(factory: Callable[[BenchConfig], Transcriber]) -> str:
    if factory is FakeTranscriber:
        return "fake"
    return "faster-whisper"


def format_summary(summary: dict[str, Any]) -> str:
    aggregate = summary["aggregate"]
    return (
        f"bench: {aggregate['clip_count']} klip, repeat={summary['repeat']}, "
        f"median xRT={aggregate['median_xrt']}, worst xRT={aggregate['worst_xrt']}, "
        f"VRAM puncak={aggregate['peak_vram_mb']} MB, "
        f"suhu puncak={aggregate['peak_temp_c']} C"
    )


def cmd_bench(args: Any) -> int:
    """CLI entry point for ``worker bench``.

    Kept as a thin wrapper so the command can be tested without spawning a
    subprocess and so both the older ``--compute`` / ``--beam`` / ``--no-vad``
    spelling and the richer flags keep working.
    """
    language = getattr(args, "language", "id")
    config = BenchConfig(
        model=getattr(args, "model", DEFAULT_MODEL),
        compute_type=getattr(args, "compute_type", None)
        or getattr(args, "compute", "int8_float16"),
        beam_size=getattr(args, "beam_size", None)
        or getattr(args, "beam", 5),
        batch_size=getattr(args, "batch_size", 8),
        vad=not getattr(args, "no_vad", False) and getattr(args, "vad", True),
        language=None if language == "auto" else language,
        device=getattr(args, "device", "cuda"),
    )
    factory = FakeTranscriber if getattr(args, "fake", False) else None
    try:
        summary = bench_folder(
            Path(args.folder),
            config,
            repeats=getattr(args, "repeat", 1),
            out_dir=Path(getattr(args, "out", "eval/results")),
            transcriber_factory=factory,
        )
    except BenchError as exc:
        print(f"worker bench: {exc}")
        return 1
    print(format_summary(summary))
    if summary.get("run_dir"):
        print(f"worker bench: hasil di {summary['run_dir']}")
    return 0
