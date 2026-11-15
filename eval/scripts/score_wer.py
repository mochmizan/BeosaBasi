"""WER + quality report for one benchmark run (TK-012, feeds TK-013/TK-014).

One command produces ``report.json`` and ``report.md``:

    python eval/scripts/score_wer.py \
        --results eval/results/v1/turbo-int8-float16-beam5-batch8-vad \
        --set eval/data/id-v1

Strict WER uses no spelling map; loose WER applies the frozen
``eval/mapping/id-v1.json`` to both reference and hypothesis (PRD 3.4.3).
The mapping hash and the set manifest are verified before scoring so results
cannot be produced against a silently edited test set.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from eval_common import (
    CATEGORY_LIMITATION_THRESHOLD,
    SILENCE_MAX_WORDS,
    SILENCE_PASS_THRESHOLD,
    TIMESTAMP_PASS_THRESHOLD,
    WER_LOOSE_THRESHOLD,
    EvalError,
    EvalSet,
    Mapping,
    build_timestamp_sample,
    configure_stdio,
    find_repeats,
    gate,
    load_eval_set,
    load_mapping,
    load_run,
    now_iso,
    pct,
    read_json,
    resolve_run_dir,
    score_timestamp_sample,
    tokenize,
    verify_manifest,
    word_errors,
    write_json,
    write_text,
)

EVAL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAPPING = EVAL_ROOT / "mapping" / "id-v1.json"


def _hypothesis_text(clip_payload: dict[str, Any] | None) -> str:
    if not clip_payload:
        return ""
    segments = clip_payload.get("segments", [])
    return " ".join(str(segment.get("text", "")) for segment in segments)


def _score_pair(
    ref_tokens: list[str], hyp_tokens: list[str], mapping: Mapping
) -> tuple[int, int]:
    strict_edits = word_errors(" ".join(ref_tokens), " ".join(hyp_tokens))
    loose_edits = word_errors(
        " ".join(mapping.apply(ref_tokens)), " ".join(mapping.apply(hyp_tokens))
    )
    return strict_edits, loose_edits


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ref_words = sum(row["ref_words"] for row in rows)
    hyp_words = sum(row["hyp_words"] for row in rows)
    strict_edits = sum(row["strict_edits"] for row in rows)
    loose_edits = sum(row["loose_edits"] for row in rows)
    return {
        "clips": len(rows),
        "ref_words": ref_words,
        "hyp_words": hyp_words,
        "strict_edits": strict_edits,
        "loose_edits": loose_edits,
        "strict_wer": strict_edits / ref_words if ref_words else None,
        "loose_wer": loose_edits / ref_words if ref_words else None,
    }


def _frozen_status(
    eval_set: EvalSet,
    mapping: Mapping,
    *,
    require: bool,
    manifest: Path | None = None,
) -> dict[str, Any]:
    problems: list[str] = []
    checked: list[str] = []

    set_manifest = manifest or (EVAL_ROOT / "manifests" / f"{eval_set.version}.sha256")
    if set_manifest.is_file():
        problems.extend(verify_manifest(set_manifest, eval_set.directory))
        checked.append(str(set_manifest))
    elif require:
        problems.append(f"manifest set tidak ditemukan: {set_manifest}")

    if mapping.path is not None:
        mapping_manifest = mapping.path.with_suffix(".sha256")
        if mapping_manifest.is_file():
            problems.extend(verify_manifest(mapping_manifest, mapping.path.parent))
            checked.append(str(mapping_manifest))
        elif require:
            problems.append(f"hash mapping tidak ditemukan: {mapping_manifest}")

    return {
        "checked": checked,
        "ok": not problems,
        "problems": problems,
    }


def score_run(
    run_dir: Path,
    eval_set: EvalSet,
    mapping: Mapping,
    *,
    timestamp_payload: dict[str, Any] | None = None,
    frozen: dict[str, Any] | None = None,
) -> dict[str, Any]:
    run = load_run(run_dir)
    eval_set.by_id()
    clip_rows: list[dict[str, Any]] = []
    missing: list[str] = []

    for clip in eval_set.clips:
        if clip.is_silence:
            continue
        payload = run["clips"].get(clip.id)
        if payload is None:
            missing.append(clip.id)
        ref_tokens = tokenize(clip.text)
        hyp_tokens = tokenize(_hypothesis_text(payload))
        strict_edits, loose_edits = _score_pair(ref_tokens, hyp_tokens, mapping)
        clip_rows.append(
            {
                "id": clip.id,
                "category": clip.category,
                "ref_words": len(ref_tokens),
                "hyp_words": len(hyp_tokens),
                "strict_edits": strict_edits,
                "loose_edits": loose_edits,
                "strict_wer": strict_edits / len(ref_tokens) if ref_tokens else None,
                "loose_wer": loose_edits / len(ref_tokens) if ref_tokens else None,
                "found": payload is not None,
            }
        )

    categories: dict[str, Any] = {}
    for category in sorted({row["category"] for row in clip_rows}):
        category_rows = [row for row in clip_rows if row["category"] == category]
        summary = _aggregate(category_rows)
        summary["limitation"] = (
            summary["loose_wer"] is not None
            and summary["loose_wer"] > CATEGORY_LIMITATION_THRESHOLD
        )
        categories[category] = summary

    overall = _aggregate(clip_rows)

    hallucination_rows = []
    for clip in eval_set.silence_clips():
        payload = run["clips"].get(clip.id)
        words = tokenize(_hypothesis_text(payload))
        hallucination_rows.append(
            {
                "id": clip.id,
                "category": clip.category,
                "word_count": len(words),
                "pass": len(words) <= SILENCE_MAX_WORDS,
                "text": _hypothesis_text(payload).strip(),
            }
        )
    silence_passed = sum(1 for row in hallucination_rows if row["pass"])
    hallucination = {
        "clips": len(hallucination_rows),
        "passed": silence_passed,
        "rate": silence_passed / len(hallucination_rows) if hallucination_rows else None,
        "max_words": SILENCE_MAX_WORDS,
        "threshold": SILENCE_PASS_THRESHOLD,
        "pass": gate(
            silence_passed / len(hallucination_rows) if hallucination_rows else None,
            SILENCE_PASS_THRESHOLD,
        ),
        "failures": [row for row in hallucination_rows if not row["pass"]],
    }

    repetition_rows = []
    for clip in eval_set.clips:
        payload = run["clips"].get(clip.id)
        tokens = tokenize(_hypothesis_text(payload))
        repeats = find_repeats(tokens)
        if repeats:
            repetition_rows.append({"id": clip.id, "repeats": repeats})
    repetition = {
        "clips": len(eval_set.clips),
        "failed": len(repetition_rows),
        "pass": not repetition_rows,
        "offenders": repetition_rows,
    }

    if timestamp_payload is None:
        timestamp_clips = []
        for clip in eval_set.clips:
            payload = run["clips"].get(clip.id)
            if payload is None:
                continue
            timestamp_clips.append(
                {
                    "id": clip.id,
                    "category": clip.category,
                    "segments": payload.get("segments", []),
                }
            )
        timestamp_payload = build_timestamp_sample(timestamp_clips)
        timestamps = {
            "sample": timestamp_payload,
            "scored": False,
            "pass": False,
            "note": "Isi manual_start lalu jalankan ulang dengan --timestamps.",
        }
    else:
        timestamps = {
            "sample_file": str(timestamp_payload.get("_path", "")),
            "scored": True,
            **score_timestamp_sample(timestamp_payload),
        }

    gates = {
        "wer_loose_overall": gate(
            overall["loose_wer"], WER_LOOSE_THRESHOLD, higher_is_better=False
        ),
        "hallucination_silence": hallucination["pass"],
        "repetition": repetition["pass"],
        "timestamps": bool(timestamps.get("pass")),
    }

    return {
        "schema": 1,
        "generated_at": now_iso(),
        "run": {
            "dir": str(run_dir),
            "config_slug": run["summary"].get("config_slug"),
            "config": run["summary"].get("config"),
            "backend": run["summary"].get("backend"),
            "aggregate": run["summary"].get("aggregate"),
            "created_at": run["summary"].get("created_at"),
        },
        "set": {
            "version": eval_set.version,
            "dir": str(eval_set.directory),
            "clips": len(eval_set.clips),
            "speech_clips": len(eval_set.speech_clips()),
            "silence_clips": len(eval_set.silence_clips()),
            "missing_results": missing,
        },
        "mapping": mapping.as_dict(),
        "frozen": frozen or {"checked": [], "ok": False, "problems": []},
        "overall": overall,
        "categories": categories,
        "clips": clip_rows,
        "hallucination": hallucination,
        "repetition": repetition,
        "timestamps": timestamps,
        "gates": gates,
        "all_gates_pass": all(gates.values()),
    }


def render_markdown(report: dict[str, Any]) -> str:
    run = report["run"]
    overall = report["overall"]
    lines = [
        f"# Laporan WER — {report['set']['version']}",
        "",
        f"- Run: `{run['config_slug']}` ({run['backend']})",
        f"- Dibuat: {report['generated_at']}",
        (f"- Set: {report['set']['clips']} klip "
        f"({report['set']['speech_clips']} ucapan, {report['set']['silence_clips']} hening)"),
        (f"- Mapping: `{report['mapping']['version']}` "
        f"({report['mapping']['entries']} entri, sha256 "
        f"{(report['mapping']['sha256'] or 'n/a')[:12]})"),
        (
            "- Manifest beku: "
            + (
                "OK"
                if report["frozen"]["ok"] and report["frozen"]["checked"]
                else "BELUM DIPERIKSA"
                if report["frozen"]["ok"]
                else "GAGAL"
            )
        ),
        "",
        "## Gerbang PRD 3.4.4",
        "",
        "| Gerbang | Ambang | Hasil | Status |",
        "|---|---|---|---|",
        (f"| WER longgar keseluruhan | ≤ {pct(WER_LOOSE_THRESHOLD, 0)} | "
        f"{pct(overall['loose_wer'])} | {'LULUS' if report['gates']['wer_loose_overall'] else 'GAGAL'} |"),
        (f"| Halusinasi klip hening | ≥ {pct(SILENCE_PASS_THRESHOLD, 0)} | "
        f"{pct(report['hallucination']['rate'])} "
        f"({report['hallucination']['passed']}/{report['hallucination']['clips']}) | "
        f"{'LULUS' if report['gates']['hallucination_silence'] else 'GAGAL'} |"),
        (f"| Pengulangan n-gram | 0 klip | {report['repetition']['failed']} klip | "
        f"{'LULUS' if report['gates']['repetition'] else 'GAGAL'} |"),
        (f"| Penanda waktu ±1 dtk | ≥ {pct(TIMESTAMP_PASS_THRESHOLD, 0)} | "
        f"{pct(report['timestamps'].get('rate'))} | "
        f"{'LULUS' if report['gates']['timestamps'] else 'BELUM/GAGAL'} |"),
        "",
        "## Ringkasan",
        "",
        "| Cakupan | Klip | Kata acuan | WER ketat | WER longgar |",
        "|---|---|---|---|---|",
        (f"| Keseluruhan | {overall['clips']} | {overall['ref_words']} | "
        f"{pct(overall['strict_wer'])} | {pct(overall['loose_wer'])} |"),
    ]
    for category, summary in report["categories"].items():
        marker = " ⚠️" if summary["limitation"] else ""
        lines.append(
            f"| {category}{marker} | {summary['clips']} | {summary['ref_words']} | "
            f"{pct(summary['strict_wer'])} | {pct(summary['loose_wer'])} |"
        )

    if report["set"]["missing_results"]:
        missing = ", ".join(report["set"]["missing_results"])
        lines += ["", f"> Hasil tidak ditemukan untuk: {missing} (dihitung sebagai hipotesis kosong)."]

    lines += ["", "## Halusinasi pada klip hening", ""]
    if not report["hallucination"]["clips"]:
        lines.append("Tidak ada klip hening di set ini.")
    else:
        lines += [
            "| Klip | Kata | Status | Teks |",
            "|---|---|---|---|",
        ]
        for row in report["hallucination"]["failures"] or [
            {"id": "(semua lulus)", "word_count": "-", "pass": True, "text": ""}
        ]:
            lines.append(
                f"| {row['id']} | {row['word_count']} | "
                f"{'lulus' if row['pass'] else 'gagal'} | {row['text'][:80]} |"
            )

    lines += ["", "## Pengulangan", ""]
    if not report["repetition"]["offenders"]:
        lines.append("Tidak ada n-gram yang berulang > 5 kali berturut-turut.")
    else:
        for offender in report["repetition"]["offenders"]:
            for repeat in offender["repeats"]:
                lines.append(
                    f"- `{offender['id']}`: n={repeat['n']} "
                    f"`{repeat['ngram']}` x{repeat['run']}"
                )

    lines += ["", "## Penanda waktu", ""]
    timestamps = report["timestamps"]
    if not timestamps.get("scored"):
        lines.append(
            "Sampel manual belum dinilai. Berkas: `timestamps.json` "
            "(isi `manual_start` lalu jalankan ulang dengan `--timestamps`)."
        )
    else:
        lines.append(
            f"{timestamps['within_collar']}/{timestamps['scored']} segmen dalam "
            f"±{timestamps['collar_seconds']} dtk ({pct(timestamps['rate'])})."
        )
        if timestamps.get("incomplete"):
            lines.append(
                f"> Sampel baru {timestamps['scored']} dari "
                f"{timestamps['sample_size']} segmen; gerbang butuh 100."
            )

    lines += [
        "",
        "## Per klip",
        "",
        "| Klip | Kategori | Kata acuan | WER ketat | WER longgar |",
        "|---|---|---|---|---|",
    ]
    for row in report["clips"]:
        lines.append(
            f"| {row['id']} | {row['category']} | {row['ref_words']} | "
            f"{pct(row['strict_wer'])} | {pct(row['loose_wer'])} |"
        )

    lines += [
        "",
        "---",
        "",
        ("Dihasilkan oleh `eval/scripts/score_wer.py`. Jangan menyunting angka "
        "secara manual; jalankan ulang skrip setelah memperbaiki masukan."),
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description="Hitung WER ketat/longgar + gerbang QA")
    parser.add_argument("--results", required=True, help="Folder run benchmark (summary.json)")
    parser.add_argument("--set", required=True, help="Folder set uji (meta.json + refs/)")
    parser.add_argument("--mapping", default=str(DEFAULT_MAPPING))
    parser.add_argument(
        "--set-manifest",
        default=None,
        help="Default: eval/manifests/<versi>.sha256",
    )
    parser.add_argument("--out", default=None, help="Default: folder run")
    parser.add_argument("--timestamps", default=None, help="Sampel manual yang sudah diisi")
    parser.add_argument("--report", action="store_true", help="Cetak Markdown ke stdout")
    parser.add_argument(
        "--check-frozen",
        action="store_true",
        help="Hanya verifikasi manifest set + mapping, lalu keluar",
    )
    parser.add_argument(
        "--allow-unfrozen",
        action="store_true",
        help="Jangan gagal bila manifest beku belum ada",
    )
    parser.add_argument(
        "--require-frozen",
        action="store_true",
        help="Gagal bila manifest beku tidak ada",
    )
    args = parser.parse_args(argv)

    try:
        run_dir = resolve_run_dir(Path(args.results))
        eval_set = load_eval_set(Path(args.set))
        mapping = load_mapping(Path(args.mapping))
        frozen = _frozen_status(
            eval_set,
            mapping,
            require=args.require_frozen,
            manifest=Path(args.set_manifest) if args.set_manifest else None,
        )
    except EvalError as exc:
        print(f"score_wer: {exc}", file=sys.stderr)
        return 2

    if args.check_frozen:
        if frozen["ok"]:
            print("score_wer: manifest beku OK")
            return 0
        for problem in frozen["problems"]:
            print(f"score_wer: {problem}", file=sys.stderr)
        return 1

    if not frozen["ok"] and not args.allow_unfrozen:
        for problem in frozen["problems"]:
            print(f"score_wer: {problem}", file=sys.stderr)
        print(
            "score_wer: set/mapping belum beku atau berubah. Jalankan "
            "`python eval/scripts/freeze_set.py` atau pakai --allow-unfrozen.",
            file=sys.stderr,
        )
        return 1

    timestamp_payload = None
    if args.timestamps:
        timestamp_payload = read_json(Path(args.timestamps))
        timestamp_payload["_path"] = args.timestamps

    report = score_run(
        run_dir, eval_set, mapping, timestamp_payload=timestamp_payload, frozen=frozen
    )
    out_dir = Path(args.out) if args.out else run_dir
    write_json(out_dir / "report.json", report)
    markdown = render_markdown(report)
    write_text(out_dir / "report.md", markdown)

    sample = report["timestamps"].get("sample")
    if sample is not None:
        write_json(out_dir / "timestamps.json", sample)

    print(
        f"score_wer: WER longgar {pct(report['overall']['loose_wer'])} "
        f"(ketat {pct(report['overall']['strict_wer'])}), "
        f"{sum(1 for value in report['gates'].values() if value)}/"
        f"{len(report['gates'])} gerbang lulus"
    )
    print(f"score_wer: laporan di {out_dir / 'report.md'}")
    if args.report:
        print()
        print(markdown)
    return 0 if report["all_gates_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
