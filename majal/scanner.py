"""Dataset scanner — reads files and runs quality checks."""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .checks import (
    ALL_CHECKS,
    Issue,
    Severity,
    check_duplicated_text,
)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DatasetStats:
    """Basic statistics about a dataset."""

    total_rows: int
    total_chars: int
    arabic_char_ratio: float
    avg_length: float
    min_length: int
    max_length: int
    field_counts: dict[str, int]


@dataclass
class ScanResult:
    """Complete result of scanning a dataset file."""

    file: str
    total_rows: int
    issues: list[Issue]
    fields_found: list[str]
    stats: DatasetStats | None = None


# ---------------------------------------------------------------------------
# File readers
# ---------------------------------------------------------------------------


def read_jsonl(path: Path) -> list[dict]:
    """Read a JSONL file — one JSON object per line."""
    rows: list[dict] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                rows.append(obj)
        except json.JSONDecodeError:
            continue
    return rows


def read_csv_file(path: Path) -> list[dict]:
    """Read a CSV file using :class:`csv.DictReader`."""
    rows: list[dict] = []
    with path.open(encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(row)
    return rows


def read_txt(path: Path) -> list[dict]:
    """Read a plain-text file — each line becomes ``{"text": line}``."""
    text = path.read_text(encoding="utf-8", errors="replace")
    return [{"text": line} for line in text.splitlines() if line.strip()]


_READERS: dict[str, callable] = {
    ".jsonl": read_jsonl,
    ".json": read_jsonl,  # treat .json same as .jsonl
    ".csv": read_csv_file,
    ".tsv": read_csv_file,
    ".txt": read_txt,
}


def read_dataset(path: Path | str) -> list[dict]:
    """Auto-detect format by extension and read the dataset."""
    path = Path(path)
    suffix = path.suffix.lower()
    reader = _READERS.get(suffix)
    if reader is None:
        raise ValueError(
            f"Unsupported file format: {suffix!r}. "
            f"Supported: {', '.join(sorted(_READERS))}"
        )
    return reader(path)


# ---------------------------------------------------------------------------
# Field detection
# ---------------------------------------------------------------------------

# Common field names that typically contain Arabic text.
_COMMON_TEXT_FIELDS: frozenset[str] = frozenset({
    "text", "arabic", "input", "output",
    "instruction", "response", "content",
    "prompt", "completion",
})


def _has_arabic(text: str) -> bool:
    """Return *True* if *text* contains at least one Arabic character."""
    return any("\u0600" <= ch <= "\u06FF" for ch in text)


def detect_text_fields(rows: Sequence[dict]) -> list[str]:
    """Find fields that contain Arabic text by sampling the first 10 rows.

    Returns field names sorted with common names first.
    """
    if not rows:
        return []

    sample = rows[:10]
    candidates: set[str] = set()

    for row in sample:
        for key, value in row.items():
            if not isinstance(value, str):
                continue
            if _has_arabic(value):
                candidates.add(key)

    # Sort: common field names first (in a stable order), then the rest.
    common = [f for f in _COMMON_TEXT_FIELDS if f in candidates]
    rest = sorted(candidates - _COMMON_TEXT_FIELDS)
    return common + rest


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def _arabic_char_count(text: str) -> int:
    """Count characters in the Arabic Unicode block."""
    return sum(1 for ch in text if "\u0600" <= ch <= "\u06FF")


def compute_stats(rows: Sequence[dict], fields: Sequence[str]) -> DatasetStats:
    """Compute basic statistics over *fields* in *rows*."""
    total_chars = 0
    total_arabic = 0
    lengths: list[int] = []
    field_counts: dict[str, int] = defaultdict(int)

    for row in rows:
        for fld in fields:
            value = row.get(fld, "")
            if not isinstance(value, str):
                continue
            field_counts[fld] += 1
            n = len(value)
            total_chars += n
            total_arabic += _arabic_char_count(value)
            lengths.append(n)

    arabic_ratio = total_arabic / total_chars if total_chars else 0.0
    avg_length = total_chars / len(lengths) if lengths else 0.0

    return DatasetStats(
        total_rows=len(rows),
        total_chars=total_chars,
        arabic_char_ratio=arabic_ratio,
        avg_length=avg_length,
        min_length=min(lengths) if lengths else 0,
        max_length=max(lengths) if lengths else 0,
        field_counts=dict(field_counts),
    )


# ---------------------------------------------------------------------------
# Main scanner
# ---------------------------------------------------------------------------


def scan_dataset(
    path: Path | str,
    fields: Sequence[str] | None = None,
    checks: Sequence | None = None,
    min_severity: Severity = Severity.INFO,
) -> ScanResult:
    """Scan a dataset file for Arabic text quality issues.

    Parameters
    ----------
    path:
        Path to a JSONL, CSV, or TXT file.
    fields:
        Specific fields to check. Auto-detected if *None*.
    checks:
        Specific check functions to run. Uses :data:`ALL_CHECKS` if *None*.
    min_severity:
        Minimum severity level to include in results.

    Returns
    -------
    ScanResult
        Contains all found issues, field list, and optional stats.
    """
    path = Path(path)
    rows = read_dataset(path)

    # Detect or validate fields.
    detected_fields = detect_text_fields(rows)
    active_fields = list(fields) if fields else detected_fields

    # Select checks.
    active_checks = list(checks) if checks else list(ALL_CHECKS)

    # Per-field duplicate trackers.
    seen_per_field: dict[str, set[str]] = defaultdict(set)

    issues: list[Issue] = []

    for row_idx, row in enumerate(rows, start=1):
        for fld in active_fields:
            value = row.get(fld)
            if value is None:
                continue
            if not isinstance(value, str):
                value = str(value)

            # Run standard checks.
            for check_fn in active_checks:
                issues.extend(check_fn(value, row_idx, fld))

            # Run duplicate check (needs the shared `seen` set).
            issues.extend(
                check_duplicated_text(value, row_idx, fld, seen=seen_per_field[fld])
            )

    # Filter by minimum severity.
    if min_severity > Severity.INFO:
        issues = [i for i in issues if i.severity >= min_severity]

    stats = compute_stats(rows, active_fields)

    return ScanResult(
        file=str(path),
        total_rows=len(rows),
        issues=issues,
        fields_found=active_fields,
        stats=stats,
    )


# ---------------------------------------------------------------------------
# Grouping helpers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# CLI convenience wrappers
# ---------------------------------------------------------------------------


def scan_file(
    path: str | Path,
    fields: list[str] | None = None,
    checks: list[str] | None = None,
    min_severity: str | Severity = Severity.INFO,
    limit: int | None = None,
) -> ScanResult:
    """Convenience wrapper around scan_dataset for CLI use."""
    path = Path(path)
    if isinstance(min_severity, str):
        min_severity = Severity[min_severity.upper()]
    rows = read_dataset(path)
    if limit:
        rows = rows[:limit]
    text_fields = fields or detect_text_fields(rows)
    stats = compute_stats(rows, text_fields)
    result = scan_dataset(path, fields=text_fields, checks=checks, min_severity=min_severity)
    result.stats = stats
    return result


def sample_rows(path: str | Path, n: int = 5) -> list[dict]:
    """Return n random rows from a dataset."""
    import random
    rows = read_dataset(Path(path))
    if len(rows) <= n:
        return rows
    return random.sample(rows, n)


# ---------------------------------------------------------------------------
# Grouping helpers
# ---------------------------------------------------------------------------


def group_by_check(issues: Sequence[Issue]) -> dict[str, list[Issue]]:
    """Group issues by their check name."""
    grouped: dict[str, list[Issue]] = defaultdict(list)
    for issue in issues:
        grouped[issue.check].append(issue)
    return dict(grouped)


def group_by_severity(issues: Sequence[Issue]) -> dict[Severity, list[Issue]]:
    """Group issues by severity level."""
    grouped: dict[Severity, list[Issue]] = defaultdict(list)
    for issue in issues:
        grouped[issue.severity].append(issue)
    return dict(grouped)
