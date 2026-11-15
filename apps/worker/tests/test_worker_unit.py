"""TK-032/034/035: pure helpers + OOM retry, no GPU needed."""

import pytest

from worker.protect import hold_awake, may_take_job
from worker.transcribe import TranscribeError, Transcriber, confidence_from_logprob


def test_confidence_mapping():
    assert confidence_from_logprob(0.0) == pytest.approx(1.0)
    assert confidence_from_logprob(-0.693) == pytest.approx(0.5, abs=0.01)
    assert confidence_from_logprob(float("-inf")) == 0.0
    assert 0.0 <= confidence_from_logprob(-5.0) <= 1.0


def test_version_string():
    t = Transcriber(model="large-v3-turbo", compute_type="int8_float16")
    assert t.version == "large-v3-turbo:int8_float16"


def test_oom_retries_once_then_reports():
    calls = []

    class OOM(Exception):
        pass

    class T(Transcriber):
        def load(self):
            self._model = True

        def unload(self):
            self._model = None

        def _decode(self, audio):
            calls.append(1)
            raise OOM("CUDA out of memory")

    t = T()
    t._model = True
    try:
        import numpy as np
        audio = np.zeros(16000, dtype=np.float32)
    except ImportError:
        audio = None
    import worker.transcribe as tmod
    orig_read = tmod._read_wav_mono16k
    tmod._read_wav_mono16k = lambda path: audio
    try:
        with pytest.raises(TranscribeError) as exc:
            t.transcribe_wav("dummy.wav")
    finally:
        tmod._read_wav_mono16k = orig_read
    assert exc.value.code == "GPU_OOM"
    assert calls == [1, 1]


def test_protect_blocks_low_battery():
    ok, msg = may_take_job(
        min_battery=30,
        battery=lambda: (18, False),
        gpu_temp=lambda: None)
    assert not ok and "18%" in msg


def test_protect_allows_plugged():
    ok, _ = may_take_job(battery=lambda: (10, True),
                         gpu_temp=lambda: None)
    assert ok


def test_protect_blocks_hot_gpu():
    ok, _ = may_take_job(battery=lambda: (80, False),
                         gpu_temp=lambda: 91)
    assert not ok


def test_hold_awake_runs():
    with hold_awake():
        pass
