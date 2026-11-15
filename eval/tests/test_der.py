from pathlib import Path

import pytest
from score_der import build_report, frame_der, read_rttm


def _write_rttm(path: Path, turns: list[tuple[float, float, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"SPEAKER {path.stem} 1 {start:.3f} {end - start:.3f} <NA> <NA> {speaker} <NA> <NA>"
        for start, end, speaker in turns
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_read_rttm_ignores_other_records(tmp_path: Path):
    path = tmp_path / "a.rttm"
    path.write_text(
        "SPEAKER a 1 0.0 1.0 <NA> <NA> spk1 <NA> <NA>\n"
        "SPKR-INFO a 1 <NA> <NA> <NA> unknown spk1 <NA> <NA>\n",
        encoding="utf-8",
    )
    turns = read_rttm(path)
    assert len(turns) == 1
    assert turns[0].speaker == "spk1"


def test_perfect_diarization_scores_zero(tmp_path: Path):
    turns = [(0.0, 5.0, "a"), (5.0, 10.0, "b")]
    _write_rttm(tmp_path / "ref" / "clip.rttm", turns)
    _write_rttm(tmp_path / "hyp" / "clip.rttm", turns)
    report = build_report(tmp_path / "ref", tmp_path / "hyp", engine="frame")
    assert report["overall"]["der"] == pytest.approx(0.0, abs=1e-6)
    assert report["speaker_count"]["exact_rate"] == 1.0
    assert report["all_gates_pass"] is True


def test_swapped_labels_are_resolved_by_mapping(tmp_path: Path):
    _write_rttm(
        tmp_path / "ref" / "clip.rttm",
        [(0.0, 5.0, "a"), (5.0, 10.0, "b")],
    )
    _write_rttm(
        tmp_path / "hyp" / "clip.rttm",
        [(0.0, 5.0, "y"), (5.0, 10.0, "x")],
    )
    report = build_report(tmp_path / "ref", tmp_path / "hyp", engine="frame")
    assert report["overall"]["der"] == pytest.approx(0.0, abs=1e-6)


def test_empty_hypothesis_is_all_miss(tmp_path: Path):
    _write_rttm(tmp_path / "ref" / "clip.rttm", [(0.0, 10.0, "a")])
    (tmp_path / "hyp").mkdir()
    report = build_report(tmp_path / "ref", tmp_path / "hyp", engine="frame")
    assert report["overall"]["der"] == pytest.approx(1.0, abs=1e-3)
    assert report["missing_hypothesis"] == ["clip"]
    assert report["overall"]["pass"] is False


def test_collar_ignores_small_boundary_shift(tmp_path: Path):
    _write_rttm(tmp_path / "ref" / "clip.rttm", [(0.0, 10.0, "a")])
    _write_rttm(tmp_path / "hyp" / "clip.rttm", [(0.2, 10.0, "a")])
    report = build_report(tmp_path / "ref", tmp_path / "hyp", engine="frame", collar=0.25)
    assert report["overall"]["der"] == pytest.approx(0.0, abs=1e-6)


def test_large_boundary_shift_is_counted(tmp_path: Path):
    _write_rttm(tmp_path / "ref" / "clip.rttm", [(0.0, 10.0, "a")])
    _write_rttm(tmp_path / "hyp" / "clip.rttm", [(2.0, 10.0, "a")])
    report = build_report(tmp_path / "ref", tmp_path / "hyp", engine="frame", collar=0.25)
    assert report["overall"]["der"] == pytest.approx(0.2, abs=0.02)


def test_frame_der_without_reference_returns_none():
    assert frame_der([], [])["der"] is None


def test_speaker_count_accuracy_counts_within_one(tmp_path: Path):
    _write_rttm(
        tmp_path / "ref" / "clip.rttm",
        [(0.0, 3.0, "a"), (3.0, 6.0, "b"), (6.0, 9.0, "c")],
    )
    _write_rttm(
        tmp_path / "hyp" / "clip.rttm",
        [(0.0, 3.0, "x"), (3.0, 6.0, "y")],
    )
    report = build_report(tmp_path / "ref", tmp_path / "hyp", engine="frame")
    assert report["speaker_count"]["exact"] == 0
    assert report["speaker_count"]["within_one"] == 1
    assert report["speaker_count"]["within_one_rate"] == 1.0
