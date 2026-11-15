"""Diarization error rate report (TK-053, PRD 3.4.9).

Compares reference and hypothesis RTTM files. Uses ``pyannote.metrics`` when it
is installed (collar 0.25 s) and otherwise falls back to a frame-based DER with
the same collar, so the report can be produced before the pyannote stack is
available on Windows.

    python eval/scripts/score_der.py \
        --ref eval/data/spk-v1/ref-rttm \
        --hyp eval/results/spk-v1/community-1/rttm

Both directories use one ``<clip>.rttm`` per clip. A missing hypothesis file is
scored as an empty hypothesis (100% DER) and listed in the report.
"""

from __future__ import annotations

import argparse
import itertools
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from eval_common import EvalError, configure_stdio, now_iso, pct, write_json, write_text

FRAME_STEP = 0.01
DEFAULT_COLLAR = 0.25
DER_THRESHOLD = 0.25
SPEAKER_EXACT_THRESHOLD = 0.75
SPEAKER_WITHIN_ONE_THRESHOLD = 0.90
MAX_BRUTE_FORCE_SPEAKERS = 7


@dataclass(frozen=True)
class Turn:
    start: float
    end: float
    speaker: str

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


def read_rttm(path: Path) -> list[Turn]:
    """Read speaker turns from an RTTM file, ignoring other record types."""
    if not path.is_file():
        raise EvalError(f"RTTM tidak ditemukan: {path}")
    turns: list[Turn] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        fields = line.split()
        if len(fields) < 8 or fields[0].upper() not in {"SPEAKER", "SPKR"}:
            continue
        try:
            start = float(fields[3])
            duration = float(fields[4])
        except ValueError:
            continue
        if duration <= 0:
            continue
        turns.append(Turn(start=start, end=start + duration, speaker=fields[7]))
    return turns


def _active_frames(
    turns: list[Turn], start: float, frames: int, step: float
) -> list[frozenset[str]]:
    add: dict[int, list[str]] = defaultdict(list)
    remove: dict[int, list[str]] = defaultdict(list)
    for turn in turns:
        first = max(0, int((turn.start - start) / step))
        last = min(frames, math.ceil((turn.end - start) / step))
        if last > first:
            add[first].append(turn.speaker)
            remove[last].append(turn.speaker)

    counts: Counter[str] = Counter()
    active: list[frozenset[str]] = []
    for index in range(frames):
        for speaker in remove.get(index, ()):
            counts[speaker] -= 1
            if counts[speaker] <= 0:
                del counts[speaker]
        for speaker in add.get(index, ()):
            counts[speaker] += 1
        active.append(frozenset(counts))
    return active


def _collar_mask(
    turns: list[Turn], start: float, frames: int, step: float, collar: float
) -> list[bool]:
    """True where a frame is inside the collar of a reference boundary."""
    mask = [False] * frames
    radius = math.ceil(collar / step)
    for turn in turns:
        for boundary in (turn.start, turn.end):
            center = round((boundary - start) / step)
            for index in range(max(0, center - radius), min(frames, center + radius + 1)):
                mask[index] = True
    return mask


def _map_speakers(
    reference: list[frozenset[str]],
    hypothesis: list[frozenset[str]],
    ignored: list[bool],
) -> dict[str, str | None]:
    ref_speakers = sorted({speaker for frame in reference for speaker in frame})
    hyp_speakers = sorted({speaker for frame in hypothesis for speaker in frame})
    if not ref_speakers or not hyp_speakers:
        return {speaker: None for speaker in hyp_speakers}

    overlap: dict[tuple[str, str], int] = defaultdict(int)
    for ref_frame, hyp_frame, skip in zip(reference, hypothesis, ignored, strict=True):
        if skip:
            continue
        for ref_speaker in ref_frame:
            for hyp_speaker in hyp_frame:
                overlap[(ref_speaker, hyp_speaker)] += 1

    mapping: dict[str, str | None] = {speaker: None for speaker in hyp_speakers}
    if max(len(ref_speakers), len(hyp_speakers)) > MAX_BRUTE_FORCE_SPEAKERS:
        # Greedy fallback for pathological files; still injective.
        used: set[str] = set()
        for ref_speaker in ref_speakers:
            candidates = [
                (overlap[(ref_speaker, hyp_speaker)], hyp_speaker)
                for hyp_speaker in hyp_speakers
                if hyp_speaker not in used
            ]
            if candidates:
                _, best = max(candidates)
                mapping[best] = ref_speaker
                used.add(best)
        return mapping

    best_score = -1
    if len(ref_speakers) <= len(hyp_speakers):
        for assignment in itertools.permutations(hyp_speakers, len(ref_speakers)):
            score = sum(overlap[(ref, hyp)] for ref, hyp in zip(ref_speakers, assignment))
            if score > best_score:
                best_score = score
                mapping = {speaker: None for speaker in hyp_speakers}
                for ref_speaker, hyp_speaker in zip(ref_speakers, assignment):
                    mapping[hyp_speaker] = ref_speaker
    else:
        for assignment in itertools.permutations(ref_speakers, len(hyp_speakers)):
            score = sum(overlap[(ref, hyp)] for hyp, ref in zip(hyp_speakers, assignment))
            if score > best_score:
                best_score = score
                mapping = {
                    hyp_speaker: ref_speaker
                    for hyp_speaker, ref_speaker in zip(hyp_speakers, assignment)
                }
    return mapping


def frame_der(
    reference: list[Turn], hypothesis: list[Turn], *, collar: float = DEFAULT_COLLAR
) -> dict[str, Any]:
    """Frame-based DER with NIST-style collar and optimal speaker mapping."""
    if not reference:
        return {
            "der": None,
            "miss": 0.0,
            "false_alarm": 0.0,
            "speaker_error": 0.0,
            "ref_speech_seconds": 0.0,
            "ref_speakers": 0,
            "hyp_speakers": 0,
            "overlap_ratio": 0.0,
            "engine": "frame",
        }

    start = min(turn.start for turn in reference + hypothesis) if hypothesis else min(
        turn.start for turn in reference
    )
    end = max(turn.end for turn in reference + hypothesis) if hypothesis else max(
        turn.end for turn in reference
    )
    frames = max(1, math.ceil((end - start) / FRAME_STEP))
    ref_frames = _active_frames(reference, start, frames, FRAME_STEP)
    hyp_frames = _active_frames(hypothesis, start, frames, FRAME_STEP)
    ignored = _collar_mask(reference, start, frames, FRAME_STEP, collar)
    mapping = _map_speakers(ref_frames, hyp_frames, ignored)

    ref_speech = 0
    miss = 0
    false_alarm = 0
    speaker_error = 0
    overlap_frames = 0
    for ref_frame, hyp_frame, skip in zip(ref_frames, hyp_frames, ignored, strict=True):
        if not ref_frame:
            if hyp_frame and not skip:
                false_alarm += 1
            continue
        if skip:
            continue
        ref_speech += 1
        if len(ref_frame) > 1:
            overlap_frames += 1
        if not hyp_frame:
            miss += 1
            continue
        mapped = {mapping.get(speaker) for speaker in hyp_frame}
        mapped.discard(None)
        if mapped != set(ref_frame):
            speaker_error += 1

    total_error = miss + false_alarm + speaker_error
    return {
        "der": total_error / ref_speech if ref_speech else None,
        "miss": miss / ref_speech if ref_speech else None,
        "false_alarm": false_alarm / ref_speech if ref_speech else None,
        "speaker_error": speaker_error / ref_speech if ref_speech else None,
        "ref_speech_seconds": ref_speech * FRAME_STEP,
        "ref_speakers": len({turn.speaker for turn in reference}),
        "hyp_speakers": len({turn.speaker for turn in hypothesis}),
        "overlap_ratio": overlap_frames / ref_speech if ref_speech else 0.0,
        "engine": "frame",
    }


def pyannote_der(
    ref_path: Path, hyp_path: Path, *, collar: float = DEFAULT_COLLAR
) -> dict[str, Any] | None:
    """DER via pyannote.metrics, or ``None`` when the package is unavailable."""
    try:
        from pyannote.core import Annotation  # type: ignore[import-not-found]
        from pyannote.metrics.diarization import (  # type: ignore[import-not-found]
            DiarizationErrorRate,
        )
    except ImportError:
        return None

    reference = Annotation.from_rttm(str(ref_path))
    if hyp_path.is_file():
        hypothesis = Annotation.from_rttm(str(hyp_path))
    else:
        hypothesis = Annotation(uri=reference.uri)
    metric = DiarizationErrorRate(collar=collar, skip_overlap=False)
    components = metric.compute_components(reference, hypothesis)
    total = components.get("total", 0.0)
    reference_duration = sum(segment.duration for segment in reference.get_timeline())
    return {
        "der": metric(reference, hypothesis),
        "miss": components["missed detection"] / total if total else None,
        "false_alarm": components["false alarm"] / total if total else None,
        "speaker_error": components["confusion"] / total if total else None,
        "ref_speech_seconds": reference_duration,
        "ref_speakers": len(reference.labels()),
        "hyp_speakers": len(hypothesis.labels()),
        "overlap_ratio": 0.0,
        "engine": "pyannote",
    }


def _overlap_bucket(ratio: float) -> str:
    if ratio < 0.05:
        return "rendah (<5%)"
    if ratio < 0.15:
        return "sedang (5-15%)"
    return "tinggi (>15%)"


def _group(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    groups: dict[str, Any] = {}
    for name in sorted({str(row[key]) for row in rows}):
        members = [row for row in rows if str(row[key]) == name]
        errors = sum(row["errors"] for row in members)
        speech = sum(row["ref_speech_seconds"] for row in members)
        groups[name] = {
            "clips": len(members),
            "ref_speech_seconds": round(speech, 2),
            "der": errors / speech if speech else None,
        }
    return groups


def build_report(
    ref_dir: Path, hyp_dir: Path, *, collar: float = DEFAULT_COLLAR, engine: str = "auto"
) -> dict[str, Any]:
    ref_files = sorted(ref_dir.glob("*.rttm"))
    if not ref_files:
        raise EvalError(f"tidak ada RTTM acuan di {ref_dir}")
    rows: list[dict[str, Any]] = []
    missing: list[str] = []

    for ref_path in ref_files:
        clip_id = ref_path.stem
        hyp_path = hyp_dir / f"{clip_id}.rttm"
        if not hyp_path.is_file():
            missing.append(clip_id)
        reference = read_rttm(ref_path)
        hypothesis = read_rttm(hyp_path) if hyp_path.is_file() else []

        result = None
        if engine in {"auto", "pyannote"}:
            result = pyannote_der(ref_path, hyp_path, collar=collar)
            if result is None and engine == "pyannote":
                raise EvalError(
                    "pyannote.metrics tidak terpasang; pakai --engine frame atau auto"
                )
        if result is None:
            result = frame_der(reference, hypothesis, collar=collar)
            result["overlap_ratio"] = result.get("overlap_ratio", 0.0)

        errors = (result["der"] or 0.0) * (result["ref_speech_seconds"] or 0.0)
        rows.append(
            {
                "clip": clip_id,
                "missing_hypothesis": not hyp_path.is_file(),
                "errors": errors,
                "speaker_count_ok": result["ref_speakers"] == result["hyp_speakers"],
                "speaker_count_delta": result["hyp_speakers"] - result["ref_speakers"],
                **result,
                "overlap_bucket": _overlap_bucket(result.get("overlap_ratio", 0.0)),
            }
        )

    total_errors = sum(row["errors"] for row in rows)
    total_speech = sum(row["ref_speech_seconds"] or 0.0 for row in rows)
    exact = sum(1 for row in rows if row["speaker_count_ok"])
    within_one = sum(1 for row in rows if abs(row["speaker_count_delta"]) <= 1)
    der = total_errors / total_speech if total_speech else None
    exact_rate = exact / len(rows)
    within_rate = within_one / len(rows)

    return {
        "schema": 1,
        "generated_at": now_iso(),
        "ref_dir": str(ref_dir),
        "hyp_dir": str(hyp_dir),
        "collar_seconds": collar,
        "engine": rows[0]["engine"] if rows else engine,
        "overall": {
            "clips": len(rows),
            "ref_speech_seconds": round(total_speech, 2),
            "der": der,
            "threshold": DER_THRESHOLD,
            "pass": der is not None and der <= DER_THRESHOLD,
        },
        "speaker_count": {
            "exact": exact,
            "within_one": within_one,
            "exact_rate": exact_rate,
            "within_one_rate": within_rate,
            "exact_threshold": SPEAKER_EXACT_THRESHOLD,
            "within_one_threshold": SPEAKER_WITHIN_ONE_THRESHOLD,
            "pass": exact_rate >= SPEAKER_EXACT_THRESHOLD
            and within_rate >= SPEAKER_WITHIN_ONE_THRESHOLD,
        },
        "by_speaker_count": _group(rows, "ref_speakers"),
        "by_overlap": _group(rows, "overlap_bucket"),
        "missing_hypothesis": missing,
        "clips": rows,
        "all_gates_pass": (
            der is not None
            and der <= DER_THRESHOLD
            and exact_rate >= SPEAKER_EXACT_THRESHOLD
            and within_rate >= SPEAKER_WITHIN_ONE_THRESHOLD
        ),
    }


def render_markdown(report: dict[str, Any]) -> str:
    overall = report["overall"]
    speakers = report["speaker_count"]
    lines = [
        "# Laporan DER (pelabelan pembicara)",
        "",
        f"- Acuan: `{report['ref_dir']}`",
        f"- Hipotesis: `{report['hyp_dir']}`",
        f"- Collar: {report['collar_seconds']} dtk",
        f"- Mesin: {report['engine']}",
        f"- Dibuat: {report['generated_at']}",
        "",
        "## Gerbang PRD 3.4.9",
        "",
        "| Metrik | Ambang | Hasil | Status |",
        "|---|---|---|---|",
        (f"| DER keseluruhan | ≤ {pct(DER_THRESHOLD, 0)} | {pct(overall['der'])} | "
        f"{'LULUS' if overall['pass'] else 'GAGAL'} |"),
        (f"| Jumlah pembicara tepat | ≥ {pct(SPEAKER_EXACT_THRESHOLD, 0)} | "
        f"{pct(speakers['exact_rate'])} ({speakers['exact']}/{overall['clips']}) | "
        f"{'LULUS' if speakers['exact_rate'] >= SPEAKER_EXACT_THRESHOLD else 'GAGAL'} |"),
        (f"| Jumlah pembicara ±1 | ≥ {pct(SPEAKER_WITHIN_ONE_THRESHOLD, 0)} | "
        f"{pct(speakers['within_one_rate'])} ({speakers['within_one']}/{overall['clips']}) | "
        f"{'LULUS' if speakers['within_one_rate'] >= SPEAKER_WITHIN_ONE_THRESHOLD else 'GAGAL'} |"),
        "",
        "## Per jumlah pembicara",
        "",
        "| Pembicara | Klip | Durasi ucapan | DER |",
        "|---|---|---|---|",
    ]
    for count, group in report["by_speaker_count"].items():
        lines.append(
            f"| {count} | {group['clips']} | {group['ref_speech_seconds']} dtk | "
            f"{pct(group['der'])} |"
        )

    lines += [
        "",
        "## Per tingkat tumpang tindih",
        "",
        "| Tumpang tindih | Klip | Durasi ucapan | DER |",
        "|---|---|---|---|",
    ]
    for bucket, group in report["by_overlap"].items():
        lines.append(
            f"| {bucket} | {group['clips']} | {group['ref_speech_seconds']} dtk | "
            f"{pct(group['der'])} |"
        )

    if report["missing_hypothesis"]:
        lines += [
            "",
            "> Hipotesis hilang (dihitung sebagai DER 100%): "
            + ", ".join(report["missing_hypothesis"]),
        ]

    lines += [
        "",
        "## Per klip",
        "",
        "| Klip | Pembicara acuan | Pembicara hip. | DER | Miss | FA | Speaker |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in report["clips"]:
        lines.append(
            f"| {row['clip']} | {row['ref_speakers']} | {row['hyp_speakers']} | "
            f"{pct(row['der'])} | {pct(row['miss'])} | {pct(row['false_alarm'])} | "
            f"{pct(row['speaker_error'])} |"
        )

    lines += [
        "",
        "---",
        "",
        "Dihasilkan oleh `eval/scripts/score_der.py`.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description="DER + akurasi jumlah pembicara (TK-053)")
    parser.add_argument("--ref", required=True, help="Folder RTTM acuan")
    parser.add_argument("--hyp", required=True, help="Folder RTTM hipotesis")
    parser.add_argument("--out", default=None)
    parser.add_argument("--collar", type=float, default=DEFAULT_COLLAR)
    parser.add_argument("--engine", choices=("auto", "pyannote", "frame"), default="auto")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = build_report(
            Path(args.ref), Path(args.hyp), collar=args.collar, engine=args.engine
        )
    except EvalError as exc:
        print(f"score_der: {exc}", file=sys.stderr)
        return 2

    out_dir = Path(args.out) if args.out else Path(args.hyp)
    write_json(out_dir / "der.json", report)
    markdown = render_markdown(report)
    write_text(out_dir / "der.md", markdown)

    print(
        f"score_der: DER {pct(report['overall']['der'])} "
        f"({report['engine']}), jumlah pembicara tepat "
        f"{pct(report['speaker_count']['exact_rate'])}"
    )
    print(f"score_der: laporan di {out_dir / 'der.md'}")
    if args.report:
        print()
        print(markdown)
    return 0 if report["all_gates_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
