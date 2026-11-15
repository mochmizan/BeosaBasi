"""Freeze a test set: validate it, then record hashes (TK-011/TK-012).

The audio and transcripts live in the git-ignored ``eval/data/`` directory.
Only the hashes are committed, in ``eval/manifests/``, so the set cannot change
after the first benchmark without the manifest check failing.

    python eval/scripts/freeze_set.py --set eval/data/id-v1
    python eval/scripts/freeze_set.py --set eval/data/id-v1 --check

A frozen set is never rewritten silently: use ``--force`` and bump the set
version when a real change is intentional.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from eval_common import (
    CATEGORIES,
    SILENCE_CATEGORIES,
    SPEECH_CATEGORIES,
    EvalError,
    configure_stdio,
    load_eval_set,
    load_mapping,
    now_iso,
    read_json,
    verify_manifest,
    write_json,
    write_manifest,
)

EVAL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_DIR = EVAL_ROOT / "manifests"
DEFAULT_MAPPING = EVAL_ROOT / "mapping" / "id-v1.json"

DEFAULT_EXPECTED = {**{category: 12 for category in SPEECH_CATEGORIES}, "hening": 20}


def _files_to_hash(set_dir: Path) -> list[Path]:
    files: list[Path] = []
    meta = set_dir / "meta.json"
    if meta.is_file():
        files.append(meta)
    for name in ("refs", "audio"):
        directory = set_dir / name
        if directory.is_dir():
            files.extend(
                path
                for path in directory.rglob("*")
                if path.is_file() and path.suffix not in {".sha256", ".jsonl"}
            )
    return files


def validate_counts(eval_set: Any, expected: dict[str, int]) -> list[str]:
    problems: list[str] = []
    counts: dict[str, int] = {}
    for clip in eval_set.clips:
        counts[clip.category] = counts.get(clip.category, 0) + 1
    for category in SPEECH_CATEGORIES:
        if category not in expected:
            continue
        actual = counts.get(category, 0)
        if actual != expected[category]:
            problems.append(f"kategori {category}: {actual} klip, seharusnya {expected[category]}")
    silence_wanted = expected.get("hening", 20)
    silence = sum(counts.get(category, 0) for category in SILENCE_CATEGORIES)
    if silence != silence_wanted:
        problems.append(f"klip hening/derau: {silence}, seharusnya {silence_wanted}")
    unknown = set(counts) - set(CATEGORIES)
    if unknown:
        problems.append(f"kategori tak dikenal: {', '.join(sorted(unknown))}")
    return problems


def validate_consent(set_dir: Path, clip_ids: set[str]) -> list[str]:
    index_path = set_dir / "consent" / "index.json"
    if not index_path.is_file():
        return ["indeks persetujuan belum ada (consent/index.json)"]
    payload = read_json(index_path)
    speakers = payload.get("speakers") if isinstance(payload, dict) else None
    if not isinstance(speakers, list) or not speakers:
        return ["consent/index.json tidak berisi daftar 'speakers'"]
    problems: list[str] = []
    for entry in speakers:
        if not isinstance(entry, dict) or not entry.get("id"):
            problems.append("entri persetujuan tanpa 'id'")
            continue
        speaker = entry["id"]
        form = entry.get("form")
        if not form:
            problems.append(f"{speaker}: 'form' belum diisi")
        elif not (set_dir / str(form)).is_file():
            problems.append(f"{speaker}: berkas formulir tidak ditemukan ({form})")
        if not entry.get("signed_at"):
            problems.append(f"{speaker}: 'signed_at' belum diisi")
        for clip_id in entry.get("clip_ids", []) or []:
            if str(clip_id) not in clip_ids:
                problems.append(f"{speaker}: clip_id tidak dikenal ({clip_id})")
    return problems


def _manifest_path(args: argparse.Namespace, version: str) -> Path:
    if args.manifest:
        return Path(args.manifest)
    return Path(args.manifest_dir) / f"{version}.sha256"


def run_check(set_dir: Path, manifest: Path, mapping_path: Path) -> int:
    problems = verify_manifest(manifest, set_dir)
    mapping_manifest = mapping_path.with_suffix(".sha256")
    if mapping_manifest.is_file():
        problems.extend(verify_manifest(mapping_manifest, mapping_path.parent))
    else:
        problems.append(f"hash mapping tidak ditemukan: {mapping_manifest}")
    if problems:
        for problem in problems:
            print(f"freeze_set: {problem}", file=sys.stderr)
        return 1
    print(f"freeze_set: OK ({manifest})")
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description="Bekukan set uji (hash + versi)")
    parser.add_argument("--set", required=True, help="Folder set uji (meta.json + refs/)")
    parser.add_argument("--mapping", default=str(DEFAULT_MAPPING))
    parser.add_argument("--manifest", default=None, help="Path manifest .sha256")
    parser.add_argument("--manifest-dir", default=str(DEFAULT_MANIFEST_DIR))
    parser.add_argument("--check", action="store_true", help="Verifikasi saja")
    parser.add_argument("--force", action="store_true", help="Timpa manifest yang sudah ada")
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Jangan gagal bila jumlah klip belum 60 + 20",
    )
    parser.add_argument(
        "--allow-missing-audio",
        action="store_true",
        help="Izinkan set tanpa folder audio (hanya untuk uji skrip)",
    )
    parser.add_argument(
        "--strict-consent",
        action="store_true",
        help="Gagal bila formulir persetujuan belum lengkap",
    )
    args = parser.parse_args(argv)

    set_dir = Path(args.set)
    mapping_path = Path(args.mapping)
    try:
        eval_set = load_eval_set(set_dir)
        mapping = load_mapping(mapping_path)
    except EvalError as exc:
        print(f"freeze_set: {exc}", file=sys.stderr)
        return 2

    manifest = _manifest_path(args, eval_set.version)
    if args.check:
        return run_check(set_dir, manifest, mapping_path)

    meta_path = set_dir / "meta.json"
    expected = DEFAULT_EXPECTED
    if meta_path.is_file():
        meta = read_json(meta_path)
        if isinstance(meta, dict) and isinstance(meta.get("expected"), dict):
            expected = {str(key): int(value) for key, value in meta["expected"].items()}

    problems: list[str] = []
    if not args.allow_partial:
        problems.extend(validate_counts(eval_set, expected))
    consent_problems = validate_consent(set_dir, {clip.id for clip in eval_set.clips})
    if consent_problems:
        print(
            f"freeze_set: peringatan persetujuan ({len(consent_problems)} masalah)",
            file=sys.stderr,
        )
        for problem in consent_problems:
            print(f"  - {problem}", file=sys.stderr)
        if args.strict_consent:
            problems.extend(consent_problems)

    audio_files = [
        path for path in (set_dir / "audio").rglob("*") if path.is_file()
    ] if (set_dir / "audio").is_dir() else []
    if not audio_files and not args.allow_missing_audio:
        problems.append("folder audio/ kosong atau tidak ada")

    if problems:
        for problem in problems:
            print(f"freeze_set: {problem}", file=sys.stderr)
        print("freeze_set: set belum beku", file=sys.stderr)
        return 1

    if manifest.is_file() and not args.force:
        existing = verify_manifest(manifest, set_dir)
        if not existing:
            print(f"freeze_set: sudah beku dan tidak berubah ({manifest})")
            return 0
        print(
            "freeze_set: manifest sudah ada dan isinya berbeda. Naikkan versi set "
            "atau pakai --force bila perubahan memang disengaja.",
            file=sys.stderr,
        )
        for problem in existing:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    files = _files_to_hash(set_dir)
    write_manifest(manifest, set_dir, files)
    write_manifest(mapping_path.with_suffix(".sha256"), mapping_path.parent, [mapping_path])

    counts: dict[str, int] = {}
    for clip in eval_set.clips:
        counts[clip.category] = counts.get(clip.category, 0) + 1
    metadata = {
        "schema": 1,
        "version": eval_set.version,
        "frozen_at": now_iso(),
        "set_dir": str(set_dir),
        "manifest": str(manifest),
        "mapping": mapping.as_dict(),
        "counts": counts,
        "hashed_files": len(files),
        "audio_files": len(audio_files),
        "consent_problems": consent_problems,
    }
    write_json(manifest.with_suffix(".json"), metadata)

    print(
        f"freeze_set: {eval_set.version} beku — {len(files)} berkas, "
        f"{len(eval_set.clips)} klip"
    )
    print(f"freeze_set: manifest {manifest}")
    print(f"freeze_set: metadata {manifest.with_suffix('.json')}")
    if consent_problems:
        print(
            f"freeze_set: {len(consent_problems)} masalah persetujuan belum selesai "
            "(lihat peringatan di atas)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
