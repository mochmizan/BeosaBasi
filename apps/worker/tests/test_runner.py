"""TK-030/033: runner loop against a fake HTTP transport (no GPU, no API)."""

import httpx

from worker.client import WorkerClient
from worker.config import WorkerConfig
from worker.runner import Runner
from worker.transcribe import Transcriber


def _config(tmp_path, **over) -> WorkerConfig:
    base = {"api_url": "http://test", "token": "t",
            "workdir": str(tmp_path / "work"),
            "heartbeat_seconds": 1000.0}
    base.update(over)
    return WorkerConfig(**base)


def _transport(claim=None, fail_log=None):
    posted: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        posted.append(request.url.path)
        if request.url.path == "/worker/v1/ping":
            return httpx.Response(200, json={"ok": True})
        if request.url.path == "/worker/v1/jobs/claim":
            if claim is None:
                return httpx.Response(204)
            return httpx.Response(200, json=claim)
        if request.url.path.endswith("/heartbeat"):
            return httpx.Response(200, json={"cancel": False,
                                             "lease_until": "x"})
        if request.url.path.endswith("/result"):
            return httpx.Response(200, json={"ok": True})
        if request.url.path.endswith("/fail"):
            (fail_log or []).append(request.url.path)
            return httpx.Response(200, json={"ok": True})
        raise AssertionError(request.url.path)

    return handler, posted


def _claim():
    return {"job_id": "00000000-0000-4000-8000-000000000001",
            "audio_url": "http://test/blob",
            "audio_expires_at": "2026-11-02T08:00:00+07:00", "language": "id",
            "diarization": False, "min_speakers": None, "max_speakers": None,
            "lease_until": "2026-11-02T08:05:00+07:00"}


class StubTranscriber(Transcriber):
    def load(self):
        self._model = True

    def transcribe_wav(self, wav_path: str):
        return ([{"index": 0, "start": 0.0, "end": 1.0, "text": "halo",
                  "confidence": 0.9}],
                {"duration": 1.0, "xrt": 2.0,
                 "low_confidence_ratio": 0.0,
                 "model_version": "stub"})


def test_run_once_empty_queue(tmp_path):
    handler, _ = _transport(claim=None)
    http = httpx.Client(transport=httpx.MockTransport(handler),
                        base_url="http://test")
    runner = Runner(_config(tmp_path), client=WorkerClient(
        _config(tmp_path), client=http))
    assert runner.run(once=True) == 0


def test_process_one_submits_and_cleans(tmp_path, capsys):
    handler, posted = _transport(claim=_claim())
    http = httpx.Client(transport=httpx.MockTransport(handler),
                        base_url="http://test")
    config = _config(tmp_path)

    class DlClient(WorkerClient):
        def download(self, url: str, dest: str) -> str:
            import wave
            with wave.open(dest, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(b"\x00\x00" * 16000)
            return dest

    runner = Runner(config, client=DlClient(config, client=http),
                    transcriber=StubTranscriber())
    # bypass ffmpeg: stub normalize by pre-seeding wav via download is wav already
    import worker.runner as rmod
    orig_normalize = rmod.normalize
    rmod.normalize = lambda src, dest: (__import__("shutil").copy(src, dest)
                                       or {"duration": 1.0})
    try:
        assert runner.process_one(_claim()) == "ok"
    finally:
        rmod.normalize = orig_normalize
    assert "/worker/v1/jobs/00000000-0000-4000-8000-000000000001/result" in posted
    assert runner.workdir_report() == []
    # TK-033: no transcript text or file names in logs.
    out = capsys.readouterr().out
    assert "halo" not in out
    assert ".wav" not in out and "audio.bin" not in out


def test_mid_job_cancel_leaves_no_files(tmp_path):
    calls = {"beat": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/worker/v1/ping":
            return httpx.Response(200, json={"ok": True})
        if request.url.path == "/worker/v1/jobs/claim":
            return httpx.Response(200, json=_claim())
        if request.url.path.endswith("/heartbeat"):
            calls["beat"] += 1
            return httpx.Response(200, json={
                "cancel": calls["beat"] >= 2, "lease_until": "x"})
        if request.url.path.endswith("/result"):
            raise AssertionError("cancelled job must not submit")
        if request.url.path.endswith("/fail"):
            return httpx.Response(200, json={"ok": True})
        raise AssertionError(request.url.path)

    http = httpx.Client(transport=httpx.MockTransport(handler),
                        base_url="http://test")
    config = WorkerConfig(api_url="http://test", token="t",
                          workdir=str(tmp_path / "work"),
                          heartbeat_seconds=0.2)

    class SlowTranscriber(Transcriber):
        def load(self):
            self._model = True

        def transcribe_wav(self, wav_path: str):
            import time as _t
            _t.sleep(5.0)
            return ([], {"duration": 1.0, "xrt": 1.0,
                         "low_confidence_ratio": 0.0,
                         "model_version": "slow"})

    class DlClient(WorkerClient):
        def download(self, url: str, dest: str) -> str:
            import wave
            with wave.open(dest, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(b"\x00\x00" * 16000)
            return dest

    import worker.runner as rmod
    orig_normalize = rmod.normalize
    rmod.normalize = lambda src, dest: (__import__("shutil").copy(src, dest)
                                       or {"duration": 1.0})
    runner = Runner(config, client=DlClient(config, client=http),
                    transcriber=SlowTranscriber())
    try:
        import threading
        th = threading.Thread(target=runner.process_one, args=(_claim(),))
        th.start()
        th.join(timeout=20.0)
        assert not th.is_alive(), "process_one hung"
    finally:
        rmod.normalize = orig_normalize
    # heartbeat cancel stops the job before submit; workdir is clean
    assert runner.workdir_report() == []


def test_cancel_cleans_workdir(tmp_path):
    handler, _ = _transport(claim=_claim())
    http = httpx.Client(transport=httpx.MockTransport(handler),
                        base_url="http://test")
    config = _config(tmp_path)

    class FailDownloadClient(WorkerClient):
        def download(self, url: str, dest: str) -> str:
            raise RuntimeError("jaringan putus")

    runner = Runner(config, client=FailDownloadClient(config, client=http),
                    transcriber=StubTranscriber())
    try:
        runner.process_one(_claim())
        raise AssertionError("harusnya melempar")
    except RuntimeError:
        pass
    assert runner.workdir_report() == []
