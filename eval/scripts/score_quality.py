"""Hallucination, repetition, and timestamp calibration (TK-014).

Reads a benchmark run plus the frozen test set and reports the three PRD 3.4.4
quality gates. ``--calibrate`` additionally sweeps post-hoc filters over the
segment statistics that ``worker bench`` already records
(``no_speech_prob`` and ``avg_logprob``) and shows the trade-off between
silence suppression and speech retention.

That sweep is a *proxy*: the real calibration changes VAD and decoding
parameters in ``faster-whisper`` and re-runs the audio. The chosen values are
still recorded here and handed to TK-032.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from eval_common import (
    REPEAT_MAX_RUN,
    SILENCE_MAX_WORDS,
    SILENCE_PASS_THRESHOLD,
    TIMESTAMP_PASS_THRESHOLD,
    EvalError,
    EvalSet,
    build_timestamp_sample,
    configure_stdio,
    find_repeats,
    gate,
    load_eval_set,
    load_run,
    now_iso,
    pct,
    read_json,
    resolve_run_dir,
    score_timestamp_sample,
    tokenize,
    write_json,
    write_text,
)

NO_SPEECH_THRESHOLDS = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
LOGPROB_THRESHOLDS = (-1.2, -1.0, -0.8, -0.6, -0.5, -0.4, -0.3, -0.2)


def _clip_segments(run: dict[str, Any], clip_id: str) -> list[dict[str, Any]]:
    payload = run["clips"].get(clip_id)
    if payload is None:
        return []
    segments = payload.get("segments", [])
    return segments if isinstance(segments, list) else []


def _word_count(segments: list[dict[str, Any]]) -> int:
    return len(tokenize(" ".join(str(segment.get("text", "")) for segment in segments)))


def _retention(
    segments: list[dict[str, Any]], keep: Any
) -> tuple[int, int]:
    kept = [segment for segment in segments if keep(segment)]
    return _word_count(kept), _word_count(segments)


def _sweep(
    run: dict[str, Any],
    eval_set: EvalSet,
    *,
    key: str,
    thresholds: tuple[float, ...],
    keep_when_above: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    silence_ids = [clip.id for clip in eval_set.silence_clips()]
    speech_ids = [clip.id for clip in eval_set.speech_clips()]

    for threshold in thresholds:
        def keep(segment: dict[str, Any], value: float = threshold) -> bool:
            raw = segment.get(key)
            if raw is None:
                # Missing statistics must not silently drop speech.
                return True
            numeric = float(raw)
            return numeric >= value if keep_when_above else numeric < value

        silence_pass = 0
        for clip_id in silence_ids:
            if _word_count([s for s in _clip_segments(run, clip_id) if keep(s)]) <= (
                SILENCE_MAX_WORDS
            ):
                silence_pass += 1
        silence_rate = silence_pass / len(silence_ids) if silence_ids else None

        kept_words = 0
        total_words = 0
        for clip_id in speech_ids:
            kept, total = _retention(_clip_segments(run, clip_id), keep)
            kept_words += kept
            total_words += total
        retention = kept_words / total_words if total_words else None

        rows.append(
            {
                key: threshold,
                "silence_pass": silence_pass,
                "silence_clips": len(silence_ids),
                "silence_rate": silence_rate,
                "silence_gate": gate(silence_rate, SILENCE_PASS_THRESHOLD),
                "speech_word_retention": retention,
            }
        )
    return rows


def _recommend(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    viable = [
        row
        for row in rows
        if row["silence_gate"] and (row["speech_word_retention"] or 0) >= 0.98
    ]
    if viable:
        return max(viable, key=lambda row: row["speech_word_retention"] or 0)
    passing = [row for row in rows if row["silence_gate"]]
    if passing:
        return max(passing, key=lambda row: row["speech_word_retention"] or 0)
    return None


def build_report(
    run_dir: Path,
    eval_set: EvalSet,
    *,
    timestamp_payload: dict[str, Any] | None = None,
    calibrate: bool = False,
) -> dict[str, Any]:
    run = load_run(run_dir)

    silence_rows = []
    for clip in eval_set.silence_clips():
        segments = _clip_segments(run, clip.id)
        text = " ".join(str(segment.get("text", "")) for segment in segments).strip()
        words = tokenize(text)
        silence_rows.append(
            {
                "id": clip.id,
                "category": clip.category,
                "word_count": len(words),
                "pass": len(words) <= SILENCE_MAX_WORDS,
                "text": text,
            }
        )
    silence_passed = sum(1 for row in silence_rows if row["pass"])
    silence_rate = silence_passed / len(silence_rows) if silence_rows else None

    repeat_rows = []
    for clip in eval_set.clips:
        tokens = tokenize(
            " ".join(str(segment.get("text", "")) for segment in _clip_segments(run, clip.id))
        )
        repeats = find_repeats(tokens)
        if repeats:
            repeat_rows.append({"id": clip.id, "repeats": repeats})

    if timestamp_payload is None:
        sample_clips = [
            {"id": clip.id, "category": clip.category, "segments": _clip_segments(run, clip.id)}
            for clip in eval_set.clips
        ]
        sample = build_timestamp_sample(sample_clips)
        timestamps: dict[str, Any] = {
            "sample": sample,
            "scored": False,
            "pass": False,
            "note": "Isi manual_start lalu jalankan ulang dengan --timestamps.",
        }
    else:
        timestamps = {
            "scored": True,
            **score_timestamp_sample(timestamp_payload),
        }

    calibration: dict[str, Any] = {}
    if calibrate:
        no_speech = _sweep(
            run,
            eval_set,
            key="no_speech_prob",
            thresholds=NO_SPEECH_THRESHOLDS,
            keep_when_above=False,
        )
        logprob = _sweep(
            run,
            eval_set,
            key="avg_logprob",
            thresholds=LOGPROB_THRESHOLDS,
            keep_when_above=True,
        )
        calibration = {
            "no_speech_prob": {
                "direction": "buang segmen bila no_speech_prob >= ambang",
                "rows": no_speech,
                "recommended": _recommend(no_speech),
            },
            "avg_logprob": {
                "direction": "buang segmen bila avg_logprob <= ambang",
                "rows": logprob,
                "recommended": _recommend(logprob),
            },
            "note": (
                "Sapuan ini bekerja pada statistik segmen yang sudah ada. "
                "Kalibrasi final tetap harus menjalankan ulang audio dengan "
                "vad_filter dan min_silence_duration_ms yang dipilih."
            ),
        }

    return {
        "schema": 1,
        "generated_at": now_iso(),
        "run": {
            "dir": str(run_dir),
            "config_slug": run["summary"].get("config_slug"),
            "config": run["summary"].get("config"),
        },
        "set": {"version": eval_set.version, "dir": str(eval_set.directory)},
        "hallucination": {
            "clips": len(silence_rows),
            "passed": silence_passed,
            "rate": silence_rate,
            "max_words": SILENCE_MAX_WORDS,
            "threshold": SILENCE_PASS_THRESHOLD,
            "pass": gate(silence_rate, SILENCE_PASS_THRESHOLD),
            "rows": silence_rows,
        },
        "repetition": {
            "clips": len(eval_set.clips),
            "failed": len(repeat_rows),
            "max_run": REPEAT_MAX_RUN,
            "pass": not repeat_rows,
            "offenders": repeat_rows,
        },
        "timestamps": timestamps,
        "calibration": calibration,
        "all_gates_pass": (
            gate(silence_rate, SILENCE_PASS_THRESHOLD)
            and not repeat_rows
            and bool(timestamps.get("pass"))
        ),
    }


def render_markdown(report: dict[str, Any]) -> str:
    silence = report["hallucination"]
    repetition = report["repetition"]
    timestamps = report["timestamps"]
    lines = [
        f"# Laporan kualitas — {report['set']['version']}",
        "",
        f"- Run: `{report['run']['config_slug']}`",
        f"- Dibuat: {report['generated_at']}",
        "",
        "## Gerbang",
        "",
        "| Metrik | Ambang | Hasil | Status |",
        "|---|---|---|---|",
        (f"| Klip hening ≤ {SILENCE_MAX_WORDS} kata | ≥ {pct(SILENCE_PASS_THRESHOLD, 0)} | "
        f"{pct(silence['rate'])} ({silence['passed']}/{silence['clips']}) | "
        f"{'LULUS' if silence['pass'] else 'GAGAL'} |"),
        (f"| Pengulangan > {REPEAT_MAX_RUN}x | 0 klip | {repetition['failed']} klip | "
        f"{'LULUS' if repetition['pass'] else 'GAGAL'} |"),
        (f"| Penanda waktu ±1 dtk | ≥ {pct(TIMESTAMP_PASS_THRESHOLD, 0)} | "
        f"{pct(timestamps.get('rate'))} | "
        f"{'LULUS' if timestamps.get('pass') else 'BELUM/GAGAL'} |"),
        "",
        "## Klip hening",
        "",
        "| Klip | Kata | Status | Teks |",
        "|---|---|---|---|",
    ]
    for row in silence["rows"]:
        lines.append(
            f"| {row['id']} | {row['word_count']} | "
            f"{'lulus' if row['pass'] else 'gagal'} | {row['text'][:80]} |"
        )

    lines += ["", "## Pengulangan", ""]
    if not repetition["offenders"]:
        lines.append("Tidak ada n-gram berulang > 5 kali.")
    else:
        for offender in repetition["offenders"]:
            for repeat in offender["repeats"]:
                lines.append(
                    f"- `{offender['id']}`: n={repeat['n']} "
                    f"`{repeat['ngram']}` x{repeat['run']}"
                )

    lines += ["", "## Penanda waktu", ""]
    if not timestamps.get("scored"):
        lines.append("Sampel manual belum dinilai; lihat `timestamps.json`.")
    else:
        lines.append(
            f"{timestamps['within_collar']}/{timestamps['scored']} dalam "
            f"±{timestamps['collar_seconds']} dtk ({pct(timestamps['rate'])})."
        )

    calibration = report.get("calibration") or {}
    if calibration:
        lines += ["", "## Kalibrasi ambang (proxy)", "", calibration["note"], ""]
        for key, title in (
            ("no_speech_prob", "no_speech_prob"),
            ("avg_logprob", "avg_logprob"),
        ):
            block = calibration[key]
            lines += [
                f"### {title}",
                "",
                f"{block['direction']}",
                "",
                "| Ambang | Hening lulus | Retensi kata ucapan |",
                "|---|---|---|",
            ]
            for row in block["rows"]:
                lines.append(
                    f"| {row[key]} | {row['silence_pass']}/{row['silence_clips']} "
                    f"({pct(row['silence_rate'])}) | "
                    f"{pct(row['speech_word_retention'])} |"
                )
            recommended = block.get("recommended")
            if recommended:
                lines += ["", f"Rekomendasi: ambang **{recommended[key]}**."]
            else:
                lines += ["", "Tidak ada ambang yang memenuhi kedua syarat."]
            lines.append("")

    lines += [
        "---",
        "",
        "Dihasilkan oleh `eval/scripts/score_quality.py`.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(
        description="Halusinasi, pengulangan, penanda waktu (TK-014)"
    )
    parser.add_argument("--results", required=True)
    parser.add_argument("--set", required=True)
    parser.add_argument("--out", default=None)
    parser.add_argument("--timestamps", default=None)
    parser.add_argument("--report", action="store_true")
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Sapukan ambang no_speech_prob/avg_logprob (proxy)",
    )
    args = parser.parse_args(argv)

    try:
        run_dir = resolve_run_dir(Path(args.results))
        eval_set = load_eval_set(Path(args.set))
    except EvalError as exc:
        print(f"score_quality: {exc}", file=sys.stderr)
        return 2

    timestamp_payload = read_json(Path(args.timestamps)) if args.timestamps else None
    report = build_report(
        run_dir, eval_set, timestamp_payload=timestamp_payload, calibrate=args.calibrate
    )
    out_dir = Path(args.out) if args.out else run_dir
    write_json(out_dir / "quality.json", report)
    markdown = render_markdown(report)
    write_text(out_dir / "quality.md", markdown)
    if report["timestamps"].get("sample") is not None:
        write_json(out_dir / "timestamps.json", report["timestamps"]["sample"])

    print(
        f"score_quality: hening {pct(report['hallucination']['rate'])}, "
        f"pengulangan {report['repetition']['failed']} klip, "
        f"penanda waktu {pct(report['timestamps'].get('rate'))}"
    )
    print(f"score_quality: laporan di {out_dir / 'quality.md'}")
    if args.report:
        print()
        print(markdown)
    return 0 if report["all_gates_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
