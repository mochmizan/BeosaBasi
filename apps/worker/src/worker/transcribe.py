"""TK-032 transcribe stage + TK-035 OOM retry (PRD 3.1, AI-03..AI-09).

Parameters are provisional until TK-013/TK-014 finalize them. VRAM is
freed after every stage; CUDA OOM unloads, reloads, retries once,
then the job fails with GPU_OOM so the server can requeue or fail it.
"""

from __future__ import annotations

import math
import os
import sys
import time
from pathlib import Path
from typing import Any

from worker.bench import _read_wav_mono16k

MODEL_VERSION_FALLBACK = "large-v3-turbo:int8_float16"
LOW_CONF_THRESHOLD = 0.5


class TranscribeError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def confidence_from_logprob(avg_logprob: float) -> float:
    """Map avg_logprob (-inf..0) to 0..1. Pure, unit-tested."""
    try:
        return max(0.0, min(1.0, math.exp(float(avg_logprob))))
    except (TypeError, ValueError, OverflowError):
        return 0.0


class Transcriber:
    def __init__(self, model: str = "large-v3-turbo",
                 compute_type: str = "int8_float16",
                 beam_size: int = 5, vad: bool = True,
                 language: str | None = "id",
                 device: str = "cuda") -> None:
        self.model_name = model
        self.compute_type = compute_type
        self.beam_size = beam_size
        self.vad = vad
        self.language = language
        self.device = device
        self._model: Any = None

    @property
    def version(self) -> str:
        return f"{self.model_name}:{self.compute_type}"

    def load(self) -> None:
        try:
            import torch
        except ImportError:
            pass
        else:
            if sys.platform == "win32":
                os.add_dll_directory(
                    os.path.join(os.path.dirname(torch.__file__), "lib"))
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise TranscribeError("FFMPEG_ERROR",
                                  "faster-whisper belum terpasang.") from exc
        self._model = WhisperModel(self.model_name, device=self.device,
                                   compute_type=self.compute_type)

    def unload(self) -> None:
        self._model = None
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

    def _decode(self, audio: Any) -> list[dict]:
        segments, _info = self._model.transcribe(
            audio, language=self.language, beam_size=self.beam_size,
            vad_filter=self.vad,
            condition_on_previous_text=False,
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            no_speech_threshold=0.6)
        out = []
        for i, seg in enumerate(segments):
            out.append({"index": i, "start": float(seg.start),
                        "end": float(seg.end), "text": seg.text.strip(),
                        "confidence": confidence_from_logprob(seg.avg_logprob)})
        return out

    def transcribe_wav(self, wav_path: str) -> tuple[list[dict], dict]:
        """Returns (segments, stats). Raises TranscribeError."""
        if self._model is None:
            raise TranscribeError("FFMPEG_ERROR", "model belum dimuat.")
        audio = _read_wav_mono16k(Path(wav_path))
        duration = len(audio) / 16000.0
        t0 = time.monotonic()
        try:
            segments = self._decode(audio)
        except Exception as exc:
            if _is_oom(exc):
                # faster-whisper has no batch knob: free VRAM, reload,
                # retry once, then report GPU_OOM.
                self.unload()
                self.load()
                try:
                    segments = self._decode(audio)
                except Exception as exc2:
                    if _is_oom(exc2):
                        raise TranscribeError(
                            "GPU_OOM", "VRAM habis bahkan setelah muat ulang. "
                            "Tutup aplikasi lain / pakai model lebih kecil.",
                            retryable=True) from exc2
                    raise TranscribeError("FFMPEG_ERROR",
                                          "transkripsi gagal.") from exc2
            else:
                raise TranscribeError("FFMPEG_ERROR",
                                      "transkripsi gagal.") from exc
        elapsed = max(time.monotonic() - t0, 0.01)
        self.unload()
        low = sum(1 for s in segments if s["confidence"] < LOW_CONF_THRESHOLD)
        stats = {"duration": duration,
                 "xrt": duration / elapsed if duration else 0.0,
                 "low_confidence_ratio": (low / len(segments)
                                          if segments else 0.0),
                 "model_version": self.version}
        return segments, stats


def _is_oom(exc: BaseException) -> bool:
    name = type(exc).__name__
    if "OutOfMemory" in name or "out of memory" in str(exc).lower():
        return True
    try:
        import torch
        return isinstance(exc, torch.cuda.OutOfMemoryError)
    except ImportError:
        return False
