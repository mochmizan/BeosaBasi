"""TK-010: transcription benchmark harness (BeosaBasi worker).

Runs the transcription pipeline over a folder of audio, writes one JSON per
clip (duration, process time, xRT, VRAM peak, GPU temp, segments, model and
library versions). Model load is timed separately from inference. Repeat
mode re-runs N times for the 60-minute file and reports median/worst.

Without faster-whisper installed the harness exits 2 with the install hint
instead of fake numbers — never invent metrics.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import statistics
import subprocess
import time

AUDIO_EXTS = (".mp3", ".m4a", ".wav", ".flac", ".ogg", ".opus", ".mp4", ".webm")


def _nvidia_peak() -> tuple[float | None, float | None]:
    """Current VRAM used MiB and GPU temp C (single sample, not a true peak)."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,temperature.gpu",
             "--format=csv,noheader,nounits"],
            check=False, capture_output=True, text=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None, None
    if out.returncode != 0 or not out.stdout.strip():
        return None, None
    try:
        used, temp = out.stdout.splitlines()[0].split(",")
        return float(used.strip()), float(temp.strip())
    except ValueError:
        return None, None


def _lib_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for mod in ("faster_whisper", "ctranslate2", "torch"):
        try:
            m = __import__(mod)
            versions[mod] = getattr(m, "__version__", "?")
        except ImportError:
            versions[mod] = "missing"
    return versions


def load_model(model: str, compute_type: str):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise SystemExit(
            "faster-whisper belum dipasang. Pasang dari "
            "apps/worker/requirements.lock lalu ulangi.")
    t0 = time.monotonic()
    m = WhisperModel(model, device="cuda", compute_type=compute_type)
    return m, time.monotonic() - t0


def _read_wav_mono16k(path: str):
    """WAV -> float32 numpy mono. stdlib only, no av dependency.

    faster-whisper 1.2.1 passes metadata_errors to av.open, removed in
    av 19, so file-path decode is broken. Irrelevant in production:
    TK-031 normalizes everything to WAV 16 kHz mono via the ffmpeg
    binary first, then we feed numpy here.
    """
    import wave

    import numpy as np

    with wave.open(path, "rb") as wav:
        assert wav.getnchannels() == 1 and wav.getsampwidth() == 2, \
            "harapkan WAV mono 16-bit (keluaran normalisasi TK-031)"
        assert wav.getframerate() == 16000, "harapkan 16 kHz"
        raw = wav.readframes(wav.getnframes())
    return (np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0)


def bench_clip(model, path: str, beam_size: int, vad: bool) -> dict:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path], check=False,
        capture_output=True, text=True, timeout=30)
    duration = float(probe.stdout.strip())
    audio = _read_wav_mono16k(path)
    t0 = time.monotonic()
    segments, _info = model.transcribe(audio, beam_size=beam_size,
                                      language="id", vad_filter=vad)
    seg_list = list(segments)
    elapsed = time.monotonic() - t0
    vram, temp = _nvidia_peak()
    return {
        "file": os.path.basename(path),
        "duration_seconds": round(duration, 2),
        "process_seconds": round(elapsed, 2),
        "xrt": round(duration / max(elapsed, 1e-6), 2),
        "vram_used_mib": vram,
        "gpu_temp_c": temp,
        "segments": len(seg_list),
        "model": getattr(model, "model_name", "?"),
    }


def cmd_bench(args: argparse.Namespace) -> int:
    files = sorted(p for ext in AUDIO_EXTS
                   for p in glob.glob(os.path.join(args.folder, f"*{ext}")))
    if not files:
        print(f"tidak ada audio di {args.folder}")
        return 1
    model, load_s = load_model(args.model, args.compute)
    print(f"model {args.model} dimuat dalam {load_s:.1f} dtk "
          f"({args.compute}) — di luar waktu inferensi")
    results = []
    for path in files:
        for _ in range(max(args.repeat, 1)):
            r = bench_clip(model, path, args.beam, not args.no_vad)
            r.update({"repeat_of": args.repeat, "versions": _lib_versions(),
                      "model_load_seconds": round(load_s, 2),
                      "compute_type": args.compute, "beam_size": args.beam})
            results.append(r)
            print(f"{r['file']}: {r['duration_seconds']}s audio / "
                  f"{r['process_seconds']}s proses = xRT {r['xrt']}")
    os.makedirs(args.out, exist_ok=True)
    for r in results:
        name = f"{os.path.splitext(r['file'])[0]}.json"
        with open(os.path.join(args.out, name), "w",
                  encoding="utf-8") as f:
            json.dump(r, f, indent=2)
    xrts = [r["xrt"] for r in results]
    print(f"median xRT {statistics.median(xrts):.1f}, "
          f"terburuk {min(xrts):.1f}, n={len(results)} → {args.out}")
    return 0
