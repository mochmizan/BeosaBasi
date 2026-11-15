import json
from pathlib import Path

import pytest

from worker.bench import (
    BenchConfig,
    BenchError,
    FakeTranscriber,
    GpuSampler,
    _metrics,
    _slugify,
    audio_duration,
    bench_folder,
    list_audio,
)
from worker.cli import make_sample_wav


def test_slug_is_filesystem_safe():
    config = BenchConfig(model="large-v3", compute_type="int8_float16")
    assert config.slug == "large-v3-int8-float16-beam5-batch8-vad"
    assert _slugify("  Large V3 / turbo ") == "large-v3-turbo"


def test_list_audio_filters_sorts_and_rejects_duplicates(tmp_path: Path):
    (tmp_path / "b.wav").write_bytes(b"")
    (tmp_path / "a.mp3").write_bytes(b"")
    (tmp_path / "notes.txt").write_text("x")
    assert [path.name for path in list_audio(tmp_path)] == ["a.mp3", "b.wav"]

    (tmp_path / "b.mp3").write_bytes(b"")
    with pytest.raises(BenchError, match="nama klip ganda"):
        list_audio(tmp_path)


def test_list_audio_requires_audio(tmp_path: Path):
    with pytest.raises(BenchError, match="tidak ada berkas audio"):
        list_audio(tmp_path)


def test_audio_duration_reads_wav(tmp_path: Path):
    path = tmp_path / "dua-detik.wav"
    make_sample_wav(str(path), seconds=2)
    assert audio_duration(path) == pytest.approx(2.0, abs=0.01)


def test_metrics_median_and_worst():
    metrics = _metrics([4.0, 2.0, 8.0], duration=40.0)
    assert metrics["median_seconds"] == 4.0
    assert metrics["worst_seconds"] == 8.0
    assert metrics["median_xrt"] == 10.0
    # "worst" is the lowest throughput, i.e. the slowest run.
    assert metrics["worst_xrt"] == 5.0


def test_gpu_sampler_without_binary_is_noop():
    with GpuSampler(binary=None) as sampler:
        pass
    assert sampler.result().peak_vram_mb is None


def test_bench_folder_writes_per_clip_and_summary(tmp_path: Path):
    folder = tmp_path / "clips"
    folder.mkdir()
    make_sample_wav(str(folder / "klip-1.wav"), seconds=1)
    make_sample_wav(str(folder / "klip-2.wav"), seconds=2)

    summary = bench_folder(
        folder,
        BenchConfig(model="fake"),
        repeats=2,
        out_dir=tmp_path / "results",
        transcriber_factory=FakeTranscriber,
        sampler_factory=lambda: GpuSampler(binary=None),
    )

    assert summary["backend"] == "fake"
    assert summary["aggregate"]["clip_count"] == 2
    assert summary["aggregate"]["total_audio_seconds"] == pytest.approx(3.0, abs=0.05)
    assert summary["aggregate"]["median_xrt"] is not None

    run_dir = tmp_path / "results" / summary["config_slug"]
    for name in ("klip-1.json", "klip-2.json", "summary.json"):
        assert (run_dir / name).is_file()

    clip = json.loads((run_dir / "klip-1.json").read_text(encoding="utf-8"))
    assert clip["clip"] == "klip-1"
    assert len(clip["repeats"]) == 2
    assert clip["segment_count"] == 1
    assert clip["peak_vram_mb"] is None
    assert clip["median_xrt"] > 0

    on_disk = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert on_disk["config"]["model"] == "fake"
    assert on_disk["environment"]["python"]


def test_bench_folder_validates_repeat(tmp_path: Path):
    with pytest.raises(BenchError, match="repeat"):
        bench_folder(tmp_path, BenchConfig(), repeats=0)
