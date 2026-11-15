"""Shared helpers for the BeosaBasi evaluation scripts.

Everything here is stdlib-only except ``jiwer``, which is used when installed
and replaced by a pure-Python Levenshtein implementation otherwise.

Normalization follows PRD 3.4.3:

* lowercase
* punctuation removed
* fillers (``eh``, ``hmm``, ...) dropped
* nonstandard forms kept as spoken (``nggak``, ``udah``)
* English loanwords keep their spelling
* strict score = no mapping, loose score = versioned mapping list applied to
  both reference and hypothesis
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

# PRD 3.4.3 names "eh" and "hmm"; the rest are the same class of hesitation
# noise seen in Indonesian speech. Keep this list small and documented.
FILLERS = frozenset(
    {
        "eh",
        "ehm",
        "emm",
        "em",
        "hmm",
        "hmmm",
        "hm",
        "mmm",
        "uhm",
        "uh",
        "erm",
    }
)

# 5 x 12 clips plus 20 silence/noise clips (PRD 3.4.1, TK-011).
SPEECH_CATEGORIES = ("wawancara", "rapat", "pesan-suara", "berderau", "campur-id-en")
SILENCE_CATEGORIES = ("hening", "derau-murni")
CATEGORIES = SPEECH_CATEGORIES + SILENCE_CATEGORIES

WER_LOOSE_THRESHOLD = 0.15
CATEGORY_LIMITATION_THRESHOLD = 0.30
SILENCE_PASS_THRESHOLD = 0.95
SILENCE_MAX_WORDS = 2
REPEAT_MAX_RUN = 5
TIMESTAMP_COLLAR_SECONDS = 1.0
TIMESTAMP_PASS_THRESHOLD = 0.95
TIMESTAMP_SAMPLE_SIZE = 100

SCHEMA_VERSION = 1


class EvalError(RuntimeError):
    """Raised when an evaluation input is missing or malformed."""


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------


def normalize_text(text: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace, drop fillers."""
    decomposed = unicodedata.normalize("NFKC", text).lower()
    cleaned = "".join(char if char.isalnum() else " " for char in decomposed)
    tokens = [token for token in cleaned.split() if token not in FILLERS]
    return " ".join(tokens)


def tokenize(text: str) -> list[str]:
    normalized = normalize_text(text)
    return normalized.split() if normalized else []


@dataclass(frozen=True)
class Mapping:
    """Versioned spelling-variant map (PRD 3.4.3).

    Keys and values are token tuples, so multi-word forms such as
    ``"dua belas"`` are supported. The longest key wins, which makes the map
    deterministic and avoids chained rewrites.
    """

    version: str
    entries: dict[tuple[str, ...], tuple[str, ...]]
    path: Path | None = None
    sha256: str | None = None

    @property
    def max_key_len(self) -> int:
        return max((len(key) for key in self.entries), default=0)

    def apply(self, tokens: Iterable[str]) -> list[str]:
        source = list(tokens)
        output: list[str] = []
        index = 0
        max_len = self.max_key_len
        while index < len(source):
            for size in range(min(max_len, len(source) - index), 0, -1):
                key = tuple(source[index : index + size])
                if key in self.entries:
                    output.extend(self.entries[key])
                    index += size
                    break
            else:
                output.append(source[index])
                index += 1
        return output

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "entries": len(self.entries),
            "sha256": self.sha256,
            "path": str(self.path) if self.path else None,
        }


IDENTITY_MAPPING = Mapping(version="none", entries={})


def load_mapping(path: Path) -> Mapping:
    """Load and validate ``eval/mapping/<version>.json``."""
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise EvalError(f"mapping harus objek JSON: {path}")
    version = payload.get("version")
    if not isinstance(version, str) or not version:
        raise EvalError(f"mapping tanpa 'version': {path}")
    raw = payload.get("mapping")
    if not isinstance(raw, dict) or not raw:
        raise EvalError(f"mapping tanpa 'mapping' yang berisi: {path}")

    entries: dict[tuple[str, ...], tuple[str, ...]] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise EvalError(f"entri mapping harus string: {key!r} -> {value!r}")
        clean_key = tuple(normalize_text(key).split())
        clean_value = tuple(normalize_text(value).split())
        if not clean_key or not clean_value:
            raise EvalError(f"entri mapping kosong setelah normalisasi: {key!r}")
        if clean_key in entries and entries[clean_key] != clean_value:
            raise EvalError(f"kunci mapping ganda: {key!r}")
        entries[clean_key] = clean_value

    keys = set(entries)
    for key, value in entries.items():
        if value in keys and value != key:
            raise EvalError(
                "mapping berantai tidak didukung: "
                f"{' '.join(key)!r} -> {' '.join(value)!r} juga kunci lain"
            )

    return Mapping(version=version, entries=entries, path=path, sha256=sha256_file(path))


# ---------------------------------------------------------------------------
# WER
# ---------------------------------------------------------------------------


def _levenshtein(reference: Sequence[str], hypothesis: Sequence[str]) -> int:
    if not reference:
        return len(hypothesis)
    if not hypothesis:
        return len(reference)
    previous = list(range(len(hypothesis) + 1))
    for i, ref_token in enumerate(reference, start=1):
        current = [i]
        for j, hyp_token in enumerate(hypothesis, start=1):
            cost = 0 if ref_token == hyp_token else 1
            current.append(
                min(
                    previous[j] + 1,  # deletion
                    current[j - 1] + 1,  # insertion
                    previous[j - 1] + cost,  # substitution
                )
            )
        previous = current
    return previous[-1]


def _jiwer_edits(reference: str, hypothesis: str) -> int | None:
    """Word edit count from jiwer, or ``None`` when jiwer is unavailable."""
    try:
        import jiwer  # type: ignore[import-not-found]
        from jiwer.transforms import (  # type: ignore[import-not-found]
            Compose,
            ReduceToListOfListOfWords,
        )
    except ImportError:
        return None
    try:
        # Identity word transform: this module already normalized the text, so
        # jiwer must not lowercase, strip, or otherwise rewrite it again.
        transform = Compose([ReduceToListOfListOfWords()])
        output = jiwer.process_words(
            reference,
            hypothesis,
            reference_transform=transform,
            hypothesis_transform=transform,
        )
    except (AttributeError, TypeError, ValueError):
        return None
    return int(output.substitutions + output.deletions + output.insertions)


def word_errors(reference: str, hypothesis: str) -> int:
    """Word-level edit distance between two normalized strings."""
    ref_tokens = reference.split()
    hyp_tokens = hypothesis.split()
    if not ref_tokens:
        return len(hyp_tokens)
    if not hyp_tokens:
        return len(ref_tokens)
    edits = _jiwer_edits(reference, hypothesis)
    if edits is None:
        edits = _levenshtein(ref_tokens, hyp_tokens)
    return edits


def wer(reference: str, hypothesis: str) -> float:
    """WER with the PRD convention: empty reference scores 0 or 1."""
    ref_tokens = reference.split()
    if not ref_tokens:
        return 0.0 if not hypothesis.split() else 1.0
    return word_errors(reference, hypothesis) / len(ref_tokens)


# ---------------------------------------------------------------------------
# Repetition and timestamps
# ---------------------------------------------------------------------------


def find_repeats(
    tokens: Sequence[str], *, max_run: int = REPEAT_MAX_RUN, max_n: int = 5
) -> list[dict[str, Any]]:
    """Return n-grams repeated more than ``max_run`` times consecutively.

    For ``n=1`` a run is the same token repeated; for ``n=2`` it is
    ``a b a b a b ...``. Only maximal runs are reported.
    """
    findings: list[dict[str, Any]] = []
    seen: set[tuple[int, tuple[str, ...]]] = set()
    for n in range(1, max_n + 1):
        index = 0
        limit = len(tokens) - n
        while index <= limit:
            gram = tuple(tokens[index : index + n])
            if len(gram) < n:
                break
            run = 1
            cursor = index + n
            while cursor + n <= len(tokens) and tuple(tokens[cursor : cursor + n]) == gram:
                run += 1
                cursor += n
            if run > max_run and (n, gram) not in seen:
                seen.add((n, gram))
                findings.append(
                    {
                        "n": n,
                        "ngram": " ".join(gram),
                        "run": run,
                        "start_index": index,
                    }
                )
            index = cursor if run > 1 else index + 1
    return findings


def _similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left, right).ratio()


def match_reference_start(
    reference_segments: Sequence[dict[str, Any]],
    hypothesis_segment: dict[str, Any],
    cursor: int,
) -> tuple[float | None, int]:
    """Pick the most similar reference segment near ``cursor``.

    Returns ``(reference_start, next_cursor)``. Used only to prefill the manual
    timestamp worksheet; the score comes from the human ``manual_start`` field.
    """
    if not reference_segments:
        return None, cursor
    window = range(cursor, min(cursor + 3, len(reference_segments)))
    best_index = cursor
    best_score = -1.0
    hyp_text = str(hypothesis_segment.get("text", ""))
    for index in window:
        score = _similarity(hyp_text, str(reference_segments[index].get("text", "")))
        if score > best_score:
            best_score = score
            best_index = index
    start = reference_segments[best_index].get("start")
    return (float(start) if start is not None else None), min(best_index + 1, len(reference_segments))


def build_timestamp_sample(
    clips: Sequence[dict[str, Any]], *, sample_size: int = TIMESTAMP_SAMPLE_SIZE
) -> dict[str, Any]:
    """Evenly sample segments across clips for the manual ±1 s check."""
    candidates: list[dict[str, Any]] = []
    for clip in clips:
        for segment in clip["segments"]:
            candidates.append(
                {
                    "clip": clip["id"],
                    "category": clip["category"],
                    "segment_index": segment.get("index", 0),
                    "hyp_start": round(float(segment.get("start", 0.0)), 3),
                    "hyp_end": round(float(segment.get("end", 0.0)), 3),
                    "hyp_text": str(segment.get("text", "")).strip(),
                    "manual_start": None,
                    "notes": "",
                }
            )
    if len(candidates) > sample_size:
        step = len(candidates) / sample_size
        candidates = [candidates[int(index * step)] for index in range(sample_size)]
    return {
        "schema": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "collar_seconds": TIMESTAMP_COLLAR_SECONDS,
        "instructions": (
            "Putar audio, isi 'manual_start' dengan waktu mulai segmen menurut "
            "pendengaran (detik), lalu jalankan ulang dengan --timestamps."
        ),
        "segments": candidates,
    }


def score_timestamp_sample(payload: dict[str, Any]) -> dict[str, Any]:
    collar = float(payload.get("collar_seconds", TIMESTAMP_COLLAR_SECONDS))
    rows = payload.get("segments", [])
    scored = [row for row in rows if isinstance(row.get("manual_start"), (int, float))]
    within = [
        abs(float(row["hyp_start"]) - float(row["manual_start"])) <= collar
        for row in scored
    ]
    passed = sum(1 for value in within if value)
    total = len(scored)
    rate = passed / total if total else None
    return {
        "collar_seconds": collar,
        "sample_size": len(rows),
        "scored": total,
        "within_collar": passed,
        "rate": rate,
        "threshold": TIMESTAMP_PASS_THRESHOLD,
        "pass": (
            rate is not None
            and total >= TIMESTAMP_SAMPLE_SIZE
            and rate >= TIMESTAMP_PASS_THRESHOLD
        ),
        "incomplete": total < TIMESTAMP_SAMPLE_SIZE,
        "failures": [
            row
            for row, ok in zip(scored, within, strict=True)
            if not ok
        ],
    }


# ---------------------------------------------------------------------------
# Set / run loading
# ---------------------------------------------------------------------------


@dataclass
class SetClip:
    id: str
    category: str
    ref_path: Path
    text: str
    segments: list[dict[str, Any]] = field(default_factory=list)
    speakers: int | None = None
    duration_seconds: float | None = None

    @property
    def is_silence(self) -> bool:
        return self.category in SILENCE_CATEGORIES


@dataclass
class EvalSet:
    version: str
    directory: Path
    clips: list[SetClip]

    def by_id(self) -> dict[str, SetClip]:
        return {clip.id: clip for clip in self.clips}

    def speech_clips(self) -> list[SetClip]:
        return [clip for clip in self.clips if not clip.is_silence]

    def silence_clips(self) -> list[SetClip]:
        return [clip for clip in self.clips if clip.is_silence]


def _read_segment_file(path: Path) -> list[dict[str, Any]]:
    payload = read_json(path)
    if isinstance(payload, list):
        segments = payload
    elif isinstance(payload, dict):
        segments = payload.get("segments", [])
    else:
        raise EvalError(f"berkas segmen tidak valid: {path}")
    if not isinstance(segments, list):
        raise EvalError(f"'segments' harus list: {path}")
    return segments


def load_eval_set(set_dir: Path) -> EvalSet:
    """Read ``meta.json`` + ``refs/`` from an evaluation set directory."""
    meta_path = set_dir / "meta.json"
    if not meta_path.is_file():
        raise EvalError(f"meta.json tidak ditemukan: {meta_path}")
    meta = read_json(meta_path)
    version = str(meta.get("version", set_dir.name))
    raw_clips = meta.get("clips")
    if isinstance(raw_clips, dict):
        items = [{"id": key, **value} for key, value in raw_clips.items()]
    elif isinstance(raw_clips, list):
        items = raw_clips
    else:
        raise EvalError(f"'clips' harus list atau objek di {meta_path}")

    clips: list[SetClip] = []
    for item in items:
        if not isinstance(item, dict) or not item.get("id"):
            raise EvalError(f"entri klip tanpa 'id' di {meta_path}")
        clip_id = str(item["id"])
        category = str(item.get("category", "lain"))
        if category not in CATEGORIES:
            raise EvalError(
                f"kategori tidak dikenal untuk {clip_id}: {category!r} "
                f"(pilihan: {', '.join(CATEGORIES)})"
            )
        ref_rel = str(item.get("ref", f"refs/{clip_id}.txt"))
        ref_path = set_dir / ref_rel
        segments: list[dict[str, Any]] = []
        if ref_path.is_file():
            text = ref_path.read_text(encoding="utf-8").strip()
            json_path = ref_path.with_suffix(".json")
            if json_path.is_file():
                segments = _read_segment_file(json_path)
        else:
            json_path = ref_path.with_suffix(".json")
            if not json_path.is_file():
                raise EvalError(f"transkrip acuan tidak ditemukan: {ref_path}")
            segments = _read_segment_file(json_path)
            text = " ".join(str(seg.get("text", "")) for seg in segments).strip()
        clips.append(
            SetClip(
                id=clip_id,
                category=category,
                ref_path=ref_path,
                text=text,
                segments=segments,
                speakers=item.get("speakers"),
                duration_seconds=item.get("duration_seconds"),
            )
        )
    if not clips:
        raise EvalError(f"set tanpa klip: {set_dir}")
    return EvalSet(version=version, directory=set_dir, clips=clips)


def resolve_run_dir(path: Path) -> Path:
    """Accept a run dir, a version dir with one run, or a version dir with many."""
    if (path / "summary.json").is_file():
        return path
    runs = sorted(
        child for child in path.iterdir() if child.is_dir() and (child / "summary.json").is_file()
    ) if path.is_dir() else []
    if len(runs) == 1:
        return runs[0]
    if len(runs) > 1:
        names = ", ".join(run.name for run in runs)
        raise EvalError(
            f"{path} berisi beberapa run ({names}); pilih satu dengan --results "
            f"{path / runs[0].name}"
        )
    raise EvalError(f"tidak ada summary.json di {path}")


def load_run(run_dir: Path) -> dict[str, Any]:
    """Load bench output: summary.json plus per-clip JSON files."""
    summary = read_json(run_dir / "summary.json")
    clips: dict[str, dict[str, Any]] = {}
    for path in sorted(run_dir.glob("*.json")):
        if path.name == "summary.json":
            continue
        payload = read_json(path)
        clip_id = str(payload.get("clip", path.stem))
        clips[clip_id] = payload
    return {"dir": run_dir, "summary": summary, "clips": clips}


# ---------------------------------------------------------------------------
# Hashing / frozen manifests
# ---------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def read_manifest(path: Path) -> dict[str, str]:
    """Read ``sha256sum`` style output: ``<hash>  <relative/path>``."""
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            raise EvalError(f"baris manifest tidak valid di {path}: {line!r}")
        digest, name = parts
        entries[name.strip().lstrip("*")] = digest.lower()
    return entries


def verify_manifest(manifest: Path, base: Path) -> list[str]:
    """Return a list of human-readable problems (empty means OK)."""
    problems: list[str] = []
    if not manifest.is_file():
        return [f"manifest tidak ditemukan: {manifest}"]
    for name, expected in read_manifest(manifest).items():
        target = base / name
        if not target.is_file():
            problems.append(f"hilang: {name}")
            continue
        actual = sha256_file(target)
        if actual != expected:
            problems.append(f"berubah: {name} (sha256 {actual[:12]} != {expected[:12]})")
    return problems


def write_manifest(manifest: Path, base: Path, files: Sequence[Path]) -> None:
    lines = []
    for path in sorted(files, key=lambda item: item.as_posix()):
        relative = path.relative_to(base).as_posix()
        lines.append(f"{sha256_file(path)}  {relative}")
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# JSON / formatting
# ---------------------------------------------------------------------------


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EvalError(f"JSON tidak valid di {path}: {exc}") from exc


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def pct(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.{digits}f}%"


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def configure_stdio() -> None:
    """Avoid UnicodeEncodeError on Windows consoles using a legacy code page."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue


def gate(value: float | None, threshold: float, *, higher_is_better: bool = True) -> bool:
    if value is None:
        return False
    return value >= threshold if higher_is_better else value <= threshold


def relpath(path: Path, start: Path) -> str:
    try:
        return path.resolve().relative_to(start.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


_WHITESPACE = re.compile(r"\s+")


def squash(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip()
