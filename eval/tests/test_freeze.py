import json
from pathlib import Path

from eval_common import load_eval_set
from freeze_set import main as freeze_main
from freeze_set import validate_consent, validate_counts


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _make_set(root: Path) -> tuple[Path, Path]:
    set_dir = root / "set"
    refs = set_dir / "refs"
    refs.mkdir(parents=True)
    (refs / "wawancara-01.txt").write_text("halo dunia", encoding="utf-8")
    (refs / "hening-01.txt").write_text("", encoding="utf-8")
    _write_json(
        set_dir / "meta.json",
        {
            "version": "freeze-v1",
            "clips": [
                {"id": "wawancara-01", "category": "wawancara"},
                {"id": "hening-01", "category": "hening"},
            ],
        },
    )
    mapping = root / "mapping.json"
    _write_json(mapping, {"version": "t1", "mapping": {"gak": "nggak"}})
    return set_dir, mapping


def test_freeze_writes_manifest_and_check_detects_change(tmp_path: Path):
    set_dir, mapping = _make_set(tmp_path)
    manifest = tmp_path / "manifests" / "freeze-v1.sha256"
    args = [
        "--set",
        str(set_dir),
        "--mapping",
        str(mapping),
        "--manifest",
        str(manifest),
        "--allow-partial",
        "--allow-missing-audio",
    ]

    assert freeze_main(args) == 0
    assert manifest.is_file()
    assert (tmp_path / "manifests" / "freeze-v1.json").is_file()
    assert freeze_main([*args, "--check"]) == 0

    (set_dir / "refs" / "wawancara-01.txt").write_text("halo semuanya", encoding="utf-8")
    assert freeze_main([*args, "--check"]) == 1
    # A changed set is not silently re-frozen.
    assert freeze_main(args) == 1


def test_freeze_force_accepts_intentional_change(tmp_path: Path):
    set_dir, mapping = _make_set(tmp_path)
    manifest = tmp_path / "manifests" / "freeze-v1.sha256"
    args = [
        "--set",
        str(set_dir),
        "--mapping",
        str(mapping),
        "--manifest",
        str(manifest),
        "--allow-partial",
        "--allow-missing-audio",
    ]
    assert freeze_main(args) == 0
    (set_dir / "refs" / "wawancara-01.txt").write_text("halo semuanya", encoding="utf-8")
    assert freeze_main([*args, "--force"]) == 0
    assert freeze_main([*args, "--check"]) == 0


def test_validate_counts_reports_missing_clips(tmp_path: Path):
    set_dir, _ = _make_set(tmp_path)
    problems = validate_counts(load_eval_set(set_dir), {"wawancara": 12, "hening": 20})
    assert any("wawancara" in problem for problem in problems)
    assert any("hening" in problem for problem in problems)


def test_validate_consent_requires_index(tmp_path: Path):
    set_dir, _ = _make_set(tmp_path)
    problems = validate_consent(set_dir, {"wawancara-01"})
    assert any("consent/index.json" in problem for problem in problems)


def test_validate_consent_checks_form_and_signed_at(tmp_path: Path):
    set_dir, _ = _make_set(tmp_path)
    _write_json(
        set_dir / "consent" / "index.json",
        {
            "speakers": [
                {"id": "spk-01", "form": "consent/spk-01.pdf", "signed_at": "2026-11-01"},
                {"id": "spk-02"},
            ]
        },
    )
    problems = validate_consent(set_dir, {"wawancara-01"})
    assert any("spk-01" in problem and "tidak ditemukan" in problem for problem in problems)
    assert any("spk-02" in problem and "'form'" in problem for problem in problems)
    assert any("spk-02" in problem and "signed_at" in problem for problem in problems)
