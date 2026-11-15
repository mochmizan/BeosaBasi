import json
from pathlib import Path

import pytest
from eval_common import load_eval_set, load_mapping
from score_wer import main as score_main
from score_wer import score_run


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _make_set(root: Path) -> Path:
    set_dir = root / "set"
    refs = set_dir / "refs"
    refs.mkdir(parents=True)
    (refs / "wawancara-01.txt").write_text("saya nggak makan nasi", encoding="utf-8")
    (refs / "wawancara-02.txt").write_text("kita rapat besok pagi", encoding="utf-8")
    (refs / "hening-01.txt").write_text("", encoding="utf-8")
    _write_json(
        set_dir / "meta.json",
        {
            "version": "test-v1",
            "clips": [
                {"id": "wawancara-01", "category": "wawancara"},
                {"id": "wawancara-02", "category": "wawancara"},
                {"id": "hening-01", "category": "hening"},
            ],
        },
    )
    return set_dir


def _make_run(root: Path) -> Path:
    run_dir = root / "run"
    _write_json(
        run_dir / "summary.json",
        {
            "config_slug": "fake-int8",
            "config": {"model": "fake"},
            "backend": "fake",
            "aggregate": {"clip_count": 3},
        },
    )
    _write_json(
        run_dir / "wawancara-01.json",
        {
            "clip": "wawancara-01",
            "segments": [{"index": 0, "start": 0.0, "end": 2.0, "text": "saya gak makan nasi"}],
        },
    )
    _write_json(
        run_dir / "wawancara-02.json",
        {
            "clip": "wawancara-02",
            "segments": [{"index": 0, "start": 0.0, "end": 2.0, "text": "kita rapat besok pagi"}],
        },
    )
    _write_json(
        run_dir / "hening-01.json",
        {
            "clip": "hening-01",
            "segments": [{"index": 0, "start": 0.0, "end": 1.0, "text": "terima kasih"}],
        },
    )
    return run_dir


def _make_mapping(root: Path) -> Path:
    path = root / "mapping.json"
    _write_json(path, {"version": "t1", "mapping": {"gak": "nggak"}})
    return path


def test_score_run_separates_strict_and_loose(tmp_path: Path):
    set_dir = _make_set(tmp_path)
    run_dir = _make_run(tmp_path)
    eval_set = load_eval_set(set_dir)
    mapping = load_mapping(_make_mapping(tmp_path))

    report = score_run(run_dir, eval_set, mapping)

    assert report["overall"]["clips"] == 2
    assert report["overall"]["strict_wer"] == pytest.approx(1 / 8)
    assert report["overall"]["loose_wer"] == pytest.approx(0.0)
    assert report["hallucination"]["clips"] == 1
    assert report["hallucination"]["pass"] is True
    assert report["repetition"]["pass"] is True
    assert report["gates"]["wer_loose_overall"] is True
    assert report["gates"]["timestamps"] is False
    assert report["timestamps"]["sample"]["segments"]


def test_score_run_flags_repetition(tmp_path: Path):
    set_dir = _make_set(tmp_path)
    run_dir = _make_run(tmp_path)
    _write_json(
        run_dir / "wawancara-02.json",
        {
            "clip": "wawancara-02",
            "segments": [
                {"index": 0, "start": 0.0, "end": 2.0, "text": "ya ya ya ya ya ya"}
            ],
        },
    )
    report = score_run(run_dir, load_eval_set(set_dir), load_mapping(_make_mapping(tmp_path)))
    assert report["repetition"]["failed"] == 1
    assert report["repetition"]["pass"] is False


def test_cli_writes_report_and_timestamp_sample(tmp_path: Path, capsys):
    set_dir = _make_set(tmp_path)
    run_dir = _make_run(tmp_path)
    mapping = _make_mapping(tmp_path)

    code = score_main(
        [
            "--results",
            str(run_dir),
            "--set",
            str(set_dir),
            "--mapping",
            str(mapping),
            "--allow-unfrozen",
            "--report",
        ]
    )

    assert code == 1  # timestamps not filled yet
    assert (run_dir / "report.json").is_file()
    assert (run_dir / "report.md").is_file()
    assert (run_dir / "timestamps.json").is_file()
    markdown = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "WER longgar" in markdown
    assert "Laporan WER" in capsys.readouterr().out


def test_cli_scores_filled_timestamps_but_requires_100(tmp_path: Path):
    set_dir = _make_set(tmp_path)
    run_dir = _make_run(tmp_path)
    mapping = _make_mapping(tmp_path)
    score_main(
        [
            "--results",
            str(run_dir),
            "--set",
            str(set_dir),
            "--mapping",
            str(mapping),
            "--allow-unfrozen",
        ]
    )
    sample = json.loads((run_dir / "timestamps.json").read_text(encoding="utf-8"))
    for row in sample["segments"]:
        row["manual_start"] = row["hyp_start"]
    sample_path = tmp_path / "filled.json"
    _write_json(sample_path, sample)

    code = score_main(
        [
            "--results",
            str(run_dir),
            "--set",
            str(set_dir),
            "--mapping",
            str(mapping),
            "--allow-unfrozen",
            "--timestamps",
            str(sample_path),
        ]
    )
    # Only two segments exist in this fixture, so the 100-segment gate cannot pass.
    assert code == 1
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    assert report["timestamps"]["rate"] == pytest.approx(1.0)
    assert report["timestamps"]["incomplete"] is True
