"""Auto-fix common Arabic dataset quality issues."""
from __future__ import annotations

import json
import re
from pathlib import Path


# Invisible chars to strip (same as checks.py, excluding LRM/RLM)
_STRIP_CODEPOINTS: set[int] = {
    0x202A, 0x202B, 0x202C, 0x202D, 0x202E,  # bidi overrides
    0x2066, 0x2067, 0x2068, 0x2069,            # isolates
    0x200B, 0x200C, 0x200D, 0xFEFF,            # zero-width
}


def _clean_text(text: str) -> str:
    """Apply all auto-fixable cleanups to a text string."""
    # Strip invisible chars
    text = "".join(ch for ch in text if ord(ch) not in _STRIP_CODEPOINTS)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Remove excessive tatweel (more than 1 in a row)
    text = re.sub("\u0640{2,}", "\u0640", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fix_dataset(
    path: Path,
    output: Path | None = None,
    dry_run: bool = True,
) -> tuple[int, int, int, Path]:
    """Fix a dataset file. Returns (total_rows, fixed_rows, removed_duplicates, output_path)."""
    path = Path(path)
    rows: list[dict] = []

    # Read
    if path.suffix in (".jsonl", ".json"):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    elif path.suffix in (".csv", ".tsv"):
        import csv
        delimiter = "\t" if path.suffix == ".tsv" else ","
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            rows = list(reader)
    else:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            rows = [{"text": line.strip()} for line in f if line.strip()]

    total = len(rows)
    fixed = 0
    seen: set[str] = set()
    cleaned: list[dict] = []

    for row in rows:
        changed = False
        # Clean text fields
        for key, val in row.items():
            if isinstance(val, str) and any("\u0600" <= c <= "\u06FF" for c in val):
                new_val = _clean_text(val)
                if new_val != val:
                    row[key] = new_val
                    changed = True

        # Skip empty rows
        text_vals = [v for v in row.values() if isinstance(v, str) and v.strip()]
        if not text_vals:
            continue

        # Skip duplicates
        fingerprint = "|".join(str(v) for v in row.values())
        if fingerprint in seen:
            continue
        seen.add(fingerprint)

        if changed:
            fixed += 1
        cleaned.append(row)

    removed = total - len(cleaned)
    out_path = output or path.with_suffix(".cleaned.jsonl")

    if not dry_run:
        with open(out_path, "w", encoding="utf-8") as f:
            for row in cleaned:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return total, fixed, removed, out_path


def fix_file(
    path: str | Path,
    output: str | Path | None = None,
    dry_run: bool = True,
) -> list[str] | None:
    """CLI convenience wrapper. In dry-run mode, returns list of change descriptions.
    In write mode, writes the cleaned file and returns None."""
    path = Path(path)
    out = Path(output) if output else None

    total, fixed, removed, out_path = fix_dataset(path, output=out, dry_run=True)

    if fixed == 0 and removed == 0:
        return []

    changes = []
    if fixed > 0:
        changes.append(f"{fixed} row(s) cleaned (invisible chars, HTML, tatweel)")
    if removed > 0:
        changes.append(f"{removed} row(s) removed (duplicates/empty)")

    if not dry_run:
        fix_dataset(path, output=out, dry_run=False)

    return changes
