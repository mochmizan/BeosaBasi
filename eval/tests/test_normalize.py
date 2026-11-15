import json
from pathlib import Path

import pytest
from eval_common import (
    EvalError,
    Mapping,
    find_repeats,
    load_mapping,
    normalize_text,
    score_timestamp_sample,
    tokenize,
    wer,
    word_errors,
)


def test_normalize_lowercases_and_drops_punctuation():
    assert normalize_text("Selamat pagi, dunia!") == "selamat pagi dunia"


def test_normalize_drops_fillers_but_keeps_nonstandard_forms():
    assert normalize_text("Eh, nggak apa-apa hmm udah makan") == "nggak apa apa udah makan"


def test_normalize_keeps_english_loanwords():
    assert normalize_text("Meeting online pakai Zoom") == "meeting online pakai zoom"


def test_normalize_collapses_whitespace():
    assert normalize_text("  halo \t dunia\n") == "halo dunia"


def test_tokenize_empty():
    assert tokenize("   ,,, ") == []


def test_word_errors_counts_substitution_insertion_deletion():
    assert word_errors("saya makan nasi", "saya makan nasi") == 0
    assert word_errors("saya makan nasi", "saya minum nasi") == 1
    assert word_errors("saya makan nasi", "saya makan nasi enak") == 1
    assert word_errors("saya makan nasi enak", "saya makan nasi") == 1


def test_wer_empty_reference_convention():
    assert wer("", "") == 0.0
    assert wer("", "halo dunia") == 1.0
    assert wer("halo dunia", "halo dunia") == 0.0


def test_wer_is_edit_distance_over_reference_words():
    assert wer("satu dua tiga empat", "satu dua tiga") == pytest.approx(0.25)


def _write_mapping(path: Path, mapping: dict[str, str], version: str = "t1") -> Path:
    path.write_text(
        json.dumps({"version": version, "mapping": mapping}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def test_mapping_applies_longest_key(tmp_path: Path):
    mapping = load_mapping(_write_mapping(tmp_path / "t1.json", {"dua belas": "12x"}))
    assert mapping.apply(["dua", "belas", "pagi"]) == ["12x", "pagi"]


def test_mapping_rejects_chains(tmp_path: Path):
    with pytest.raises(EvalError, match="berantai"):
        load_mapping(_write_mapping(tmp_path / "t1.json", {"a": "b", "b": "c"}))


def test_mapping_rejects_empty_entry(tmp_path: Path):
    with pytest.raises(EvalError, match="kosong"):
        load_mapping(_write_mapping(tmp_path / "t1.json", {"...": "x"}))


def test_mapping_identity():
    assert Mapping(version="x", entries={}).apply(["a", "b"]) == ["a", "b"]


def test_find_repeats_flags_more_than_five():
    tokens = ["halo"] + ["ya"] * 6 + ["dunia"]
    findings = find_repeats(tokens)
    assert any(item["n"] == 1 and item["ngram"] == "ya" and item["run"] == 6 for item in findings)


def test_find_repeats_allows_exactly_five():
    assert find_repeats(["ya"] * 5) == []


def test_find_repeats_bigram():
    tokens = ["a", "b"] * 6
    findings = find_repeats(tokens)
    assert any(item["n"] == 2 and item["run"] == 6 for item in findings)


def test_timestamp_score_requires_100_and_within_collar():
    payload = {
        "collar_seconds": 1.0,
        "segments": [
            {"hyp_start": 10.0, "manual_start": 10.4},
            {"hyp_start": 20.0, "manual_start": 21.5},
        ]
        + [{"hyp_start": float(i), "manual_start": float(i)} for i in range(98)],
    }
    result = score_timestamp_sample(payload)
    assert result["scored"] == 100
    assert result["within_collar"] == 99
    assert result["rate"] == pytest.approx(0.99)
    assert result["pass"] is True


def test_timestamp_incomplete_sample_does_not_pass():
    payload = {"segments": [{"hyp_start": 1.0, "manual_start": 1.0}]}
    result = score_timestamp_sample(payload)
    assert result["incomplete"] is True
    assert result["pass"] is False
