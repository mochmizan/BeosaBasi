"""TK-030 run loop + TK-033 hygiene (PRD 4.7, 4.8, AI-10).

claim -> download -> normalize -> transcribe -> submit, with a 30 s
heartbeat thread. Cancel from the server stops work and deletes files.
Workdir is per-job and removed in ``finally``; logs never carry
transcript text or file names.
"""

from __future__ import annotations

import shutil
import signal
import threading
import time
import uuid
from pathlib import Path

from worker.client import WorkerAuthError, WorkerClient, WorkerVersionError, with_backoff
from worker.config import WorkerConfig
from worker.media import MediaError, normalize
from worker.protect import hold_awake, may_take_job
from worker.transcribe import TranscribeError, Transcriber


class Cancelled(Exception):
    pass


class Runner:
    def __init__(self, config: WorkerConfig,
                 client: WorkerClient | None = None,
                 transcriber: Transcriber | None = None) -> None:
        self.config = config
        self.client = client or WorkerClient(config)
        self.transcriber = transcriber
        self._stop = threading.Event()
        self._cancel = threading.Event()
        self._stage = "probing"
        self._progress = 0.0

    def stop(self) -> None:
        self._stop.set()

    def workdir_report(self) -> list[str]:
        """Leftover files for the K4 audit (TK-033). Empty is healthy."""
        root = Path(self.config.workdir)
        if not root.exists():
            return []
        return sorted(str(p) for p in root.iterdir())

    # -- heartbeat --

    def _beat(self, job_id: str) -> None:
        while not self._stop.wait(self.config.heartbeat_seconds):
            try:
                if self.client.heartbeat(job_id, self._stage, self._progress):
                    self._cancel.set()
                    return
            except Exception:  # noqa: BLE001, S112 - heartbeat never kills jobs
                continue

    def _check_cancel(self) -> None:
        if self._cancel.is_set():
            raise Cancelled()

    # -- one job --

    def process_one(self, claim: dict) -> str:
        job_id = str(claim["job_id"])
        job_dir = Path(self.config.workdir) / f"job-{uuid.uuid4().hex[:8]}"
        job_dir.mkdir(parents=True, exist_ok=True)
        beat = threading.Thread(target=self._beat, args=(job_id,),
                                daemon=True)
        self._cancel.clear()
        self._stage, self._progress = "probing", 0.0
        beat.start()
        try:
            with hold_awake():
                return self._process(job_id, claim, str(job_dir))
        finally:
            self._stop.set()
            beat.join(timeout=5.0)
            self._stop.clear()
            shutil.rmtree(job_dir, ignore_errors=True)
            leftovers = [p for p in Path(self.config.workdir).iterdir()] \
                if Path(self.config.workdir).exists() else []
            if leftovers:
                print(f"worker: {len(leftovers)} berkas sisa dibiarkan "
                      f"(audit K4): {[p.name for p in leftovers[:3]]}")

    def _process(self, job_id: str, claim: dict, job_dir: str) -> str:
        self._check_cancel()
        raw = str(Path(job_dir) / "audio.bin")
        self.client.download(str(claim["audio_url"]), raw)
        self._check_cancel()

        wav = str(Path(job_dir) / "audio.wav")
        try:
            normalize(raw, wav)
        except MediaError as exc:
            self.client.submit_fail(job_id, exc.code, exc.retryable,
                                    detail=str(exc)[:200])
            return f"gagal-media:{exc.code}"
        self._check_cancel()

        self._stage, self._progress = "transcribing", 0.4
        transcriber = self.transcriber or Transcriber(
            model=self.config.model, compute_type=self.config.compute_type,
            beam_size=self.config.beam_size,
            vad=self.config.vad, language=self.config.language,
            device=self.config.device)
        try:
            transcriber.load()
            segments, stats = transcriber.transcribe_wav(wav)
        except TranscribeError as exc:
            self.client.submit_fail(job_id, exc.code, exc.retryable,
                                    detail=str(exc)[:200])
            return f"gagal-transkripsi:{exc.code}"
        self._check_cancel()

        # TK-051 diarization lands here; until then deliver transcript only.
        self._stage, self._progress = "merging", 0.9
        result = {
            "segments": [
                {"index": s["index"], "start": s["start"], "end": s["end"],
                 "text": s["text"], "confidence": s["confidence"],
                 "speaker_id": None, "edited": False, "version": 1}
                for s in segments
            ],
            "speakers": [],
            "diarization_available": False,
            "duration_seconds": stats["duration"],
            "xrt": stats["xrt"],
            "model_version": stats["model_version"],
            "low_confidence_ratio": stats["low_confidence_ratio"],
        }
        self.client.submit_result(job_id, result)
        print(f"worker: selesai {job_id} "
              f"({len(segments)} segmen, xrt={stats['xrt']:.1f})")
        return "ok"

    # -- loop --

    def run(self, once: bool = False) -> int:
        try:
            self.client.ping()
        except (WorkerAuthError, WorkerVersionError) as exc:
            print(f"worker: {exc}")
            return 1
        except Exception as exc:  # noqa: BLE001
            print(f"worker: tidak bisa hubungi {self.config.api_url} ({exc}). "
                  "Jalankan `make dev-up` dulu.")
            return 1
        fails = 0
        while not self._stop.is_set():
            ok, reason = may_take_job(self.config.min_battery_percent,
                                      self.config.max_gpu_temp_c)
            if not ok:
                print(f"worker: jeda — {reason}")
                time.sleep(60.0)
                continue
            try:
                claim = self.client.claim()
            except Exception as exc:  # noqa: BLE001
                fails += 1
                print(f"worker: claim gagal ({exc}), mundur {fails}")
                with_backoff(min(fails, 5))
                continue
            fails = 0
            if claim is None:
                if once:
                    return 0
                time.sleep(2.0)
                continue
            try:
                print(f"worker: claimed {claim['job_id']}")
                self.process_one(claim)
            except Cancelled:
                print(f"worker: dibatalkan {claim['job_id']}, berkas dibersihkan")
            except Exception as exc:  # noqa: BLE001
                try:
                    self.client.submit_fail(str(claim["job_id"]), "FFMPEG_ERROR",
                                            True, detail="galat tak terduga")
                except Exception:  # noqa: BLE001, S110 - best effort fail report
                    pass
                print(f"worker: galat {claim['job_id']} ({exc})")
            if once:
                return 0
        return 0


def install_signal_handlers(runner: Runner) -> None:
    def handler(_signum, _frame) -> None:
        print("worker: berhenti rapi, job kembali antre via lease.")
        runner.stop()
    signal.signal(signal.SIGINT, handler)
    try:
        signal.signal(signal.SIGTERM, handler)
    except (AttributeError, ValueError):
        pass
