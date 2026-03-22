"""Arabic dataset quality checks."""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import IntEnum


# ---------------------------------------------------------------------------
# Severity & Issue
# ---------------------------------------------------------------------------


class Severity(IntEnum):
    INFO = 1
    WARNING = 2
    ERROR = 3


@dataclass(frozen=True)
class Issue:
    """A single quality issue found in a dataset row."""

    check: str  # check ID e.g. "encoding_mixed"
    severity: Severity
    row: int  # 1-based row number
    field: str  # which field (e.g. "text", "arabic", "output")
    message: str  # human-readable description
    snippet: str  # the problematic text snippet (max 80 chars)


def _snippet(text: str, max_len: int = 80) -> str:
    """Truncate *text* to *max_len* characters for display."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "\u2026"


# ---------------------------------------------------------------------------
# Encoding checks
# ---------------------------------------------------------------------------

# Common mojibake sequences produced when UTF-8 bytes are decoded as Latin-1.
_MOJIBAKE_RE = re.compile(r"[\xc3\xc2][\x80-\xbf]|Ã.|Â.|Ù.|Ø.")


def check_encoding_mixed(text: str, row: int, field: str) -> list[Issue]:
    """Detect mixed-encoding artifacts (mojibake from UTF-8 read as Latin-1)."""
    matches = _MOJIBAKE_RE.findall(text)
    if not matches:
        return []
    sample = ", ".join(dict.fromkeys(matches))  # unique, order-preserved
    return [
        Issue(
            check="encoding_mixed",
            severity=Severity.ERROR,
            row=row,
            field=field,
            message=f"Mojibake detected — possible UTF-8 / Latin-1 mixup: {_snippet(sample, 40)}",
            snippet=_snippet(text),
        )
    ]


def check_encoding_replacement(text: str, row: int, field: str) -> list[Issue]:
    """Detect U+FFFD replacement characters."""
    count = text.count("\ufffd")
    if count == 0:
        return []
    return [
        Issue(
            check="encoding_replacement",
            severity=Severity.ERROR,
            row=row,
            field=field,
            message=f"Found {count} U+FFFD replacement character(s)",
            snippet=_snippet(text),
        )
    ]


# ---------------------------------------------------------------------------
# Invisible character checks
# ---------------------------------------------------------------------------

# Bidi overrides and isolates.
_BIDI_OVERRIDES: frozenset[int] = frozenset(
    range(0x202A, 0x202F)  # LRE, RLE, PDF, LRO, RLO
) | frozenset(
    range(0x2066, 0x206A)  # LRI, RLI, FSI, PDI
)

# Zero-width characters (excluding U+200E LRM and U+200F RLM).
_ZERO_WIDTH: frozenset[int] = frozenset({0x200B, 0x200C, 0x200D, 0xFEFF})

_INVISIBLE_BAD: frozenset[int] = _BIDI_OVERRIDES | _ZERO_WIDTH

_INVISIBLE_NAMES: dict[int, str] = {
    0x202A: "LRE",
    0x202B: "RLE",
    0x202C: "PDF",
    0x202D: "LRO",
    0x202E: "RLO",
    0x2066: "LRI",
    0x2067: "RLI",
    0x2068: "FSI",
    0x2069: "PDI",
    0x200B: "ZWSP",
    0x200C: "ZWNJ",
    0x200D: "ZWJ",
    0xFEFF: "BOM",
}


def check_invisible_chars(text: str, row: int, field: str) -> list[Issue]:
    """Detect problematic invisible characters (allows LRM/RLM)."""
    found: list[str] = []
    for ch in text:
        cp = ord(ch)
        if cp in _INVISIBLE_BAD:
            name = _INVISIBLE_NAMES.get(cp, f"U+{cp:04X}")
            found.append(name)
    if not found:
        return []
    unique = ", ".join(dict.fromkeys(found))
    return [
        Issue(
            check="invisible_chars",
            severity=Severity.WARNING,
            row=row,
            field=field,
            message=f"Invisible character(s) found: {unique}",
            snippet=_snippet(text),
        )
    ]


# ---------------------------------------------------------------------------
# Content quality checks
# ---------------------------------------------------------------------------


def check_empty_or_whitespace(text: str, row: int, field: str) -> list[Issue]:
    """Detect empty or whitespace-only text."""
    if text.strip():
        return []
    label = "empty" if len(text) == 0 else "whitespace-only"
    return [
        Issue(
            check="empty_or_whitespace",
            severity=Severity.ERROR,
            row=row,
            field=field,
            message=f"Field is {label}",
            snippet=repr(text)[:80],
        )
    ]


def check_too_short(text: str, row: int, field: str) -> list[Issue]:
    """Detect text shorter than 3 characters."""
    if len(text.strip()) >= 3:
        return []
    return [
        Issue(
            check="too_short",
            severity=Severity.WARNING,
            row=row,
            field=field,
            message=f"Text is very short ({len(text.strip())} chars)",
            snippet=_snippet(text),
        )
    ]


def check_too_long(text: str, row: int, field: str) -> list[Issue]:
    """Detect text longer than 10 000 characters."""
    if len(text) <= 10_000:
        return []
    return [
        Issue(
            check="too_long",
            severity=Severity.INFO,
            row=row,
            field=field,
            message=f"Text is very long ({len(text):,} chars)",
            snippet=_snippet(text),
        )
    ]


def check_duplicated_text(
    text: str, row: int, field: str, *, seen: set[str]
) -> list[Issue]:
    """Detect exact duplicate text across rows."""
    stripped = text.strip()
    if stripped in seen:
        return [
            Issue(
                check="duplicated_text",
                severity=Severity.WARNING,
                row=row,
                field=field,
                message="Exact duplicate of a previous row",
                snippet=_snippet(text),
            )
        ]
    seen.add(stripped)
    return []


# ---------------------------------------------------------------------------
# Arabic-specific checks
# ---------------------------------------------------------------------------


def _arabic_char_count(text: str) -> int:
    """Count characters in the Arabic Unicode block (U+0600–U+06FF)."""
    return sum(1 for ch in text if "\u0600" <= ch <= "\u06FF")


def _letter_count(text: str) -> int:
    """Count non-space, non-punctuation characters (rough)."""
    return sum(1 for ch in text if ch.isalpha())


def check_no_arabic(text: str, row: int, field: str) -> list[Issue]:
    """Detect text with zero Arabic characters."""
    if _arabic_char_count(text) > 0:
        return []
    return [
        Issue(
            check="no_arabic",
            severity=Severity.WARNING,
            row=row,
            field=field,
            message="No Arabic characters found",
            snippet=_snippet(text),
        )
    ]


def check_low_arabic_ratio(text: str, row: int, field: str) -> list[Issue]:
    """Detect text where less than 30% of letters are Arabic."""
    letters = _letter_count(text)
    if letters == 0:
        return []
    ratio = _arabic_char_count(text) / letters
    if ratio >= 0.30:
        return []
    return [
        Issue(
            check="low_arabic_ratio",
            severity=Severity.INFO,
            row=row,
            field=field,
            message=f"Low Arabic ratio ({ratio:.0%} of letters)",
            snippet=_snippet(text),
        )
    ]


# Dialect marker keyword lists.
_DIALECT_MARKERS: dict[str, tuple[str, ...]] = {
    "Egyptian": ("إيه", "ده", "دي", "النهاردة", "كده", "عايز", "ازاي"),
    "Gulf": ("شلون", "وايد", "يالله", "حق", "شخبارك", "إنزين"),
    "Levantine": ("كتير", "هلق", "شو", "كيفك", "هيك"),
    "Moroccan": ("ديال", "بغيت", "فين", "واش", "بزاف"),
}


def check_mixed_dialects(text: str, row: int, field: str) -> list[Issue]:
    """Detect markers from multiple Arabic dialects in the same text."""
    detected: list[str] = []
    for dialect, markers in _DIALECT_MARKERS.items():
        if any(m in text for m in markers):
            detected.append(dialect)
    if len(detected) < 2:
        return []
    return [
        Issue(
            check="mixed_dialects",
            severity=Severity.WARNING,
            row=row,
            field=field,
            message=f"Mixed dialect markers: {', '.join(detected)}",
            snippet=_snippet(text),
        )
    ]


# Tashkeel (Arabic diacritics) codepoints.
_TASHKEEL: frozenset[int] = frozenset(range(0x064B, 0x0653))


def _tashkeel_per_word(text: str) -> list[int]:
    """Return the count of tashkeel marks per word."""
    counts: list[int] = []
    for word in text.split():
        counts.append(sum(1 for ch in word if ord(ch) in _TASHKEEL))
    return counts


def check_tashkeel_inconsistency(text: str, row: int, field: str) -> list[Issue]:
    """Detect inconsistent diacritization (some words fully diacritized, most not)."""
    counts = _tashkeel_per_word(text)
    if not counts:
        return []
    total_tashkeel = sum(counts)
    if total_tashkeel == 0:
        return []
    words_with = sum(1 for c in counts if c >= 2)
    words_without = sum(1 for c in counts if c == 0)
    # Inconsistent when some words have heavy tashkeel but most don't.
    if words_with >= 1 and words_without >= 1 and words_with / len(counts) < 0.5:
        return [
            Issue(
                check="tashkeel_inconsistency",
                severity=Severity.INFO,
                row=row,
                field=field,
                message=f"Inconsistent tashkeel — {words_with}/{len(counts)} words diacritized",
                snippet=_snippet(text),
            )
        ]
    return []


_TATWEEL = "\u0640"


def check_tatweel_excessive(text: str, row: int, field: str) -> list[Issue]:
    """Detect excessive tatweel (kashida) usage."""
    if _TATWEEL not in text:
        return []
    # Check for 3+ consecutive tatweels.
    consecutive = _TATWEEL * 3 in text
    # Check overall ratio.
    total_chars = len(text.replace(" ", ""))
    if total_chars == 0:
        return []
    ratio = text.count(_TATWEEL) / total_chars
    if not consecutive and ratio <= 0.05:
        return []
    detail = []
    if consecutive:
        detail.append("3+ consecutive")
    if ratio > 0.05:
        detail.append(f"ratio {ratio:.1%}")
    return [
        Issue(
            check="tatweel_excessive",
            severity=Severity.WARNING,
            row=row,
            field=field,
            message=f"Excessive tatweel ({', '.join(detail)})",
            snippet=_snippet(text),
        )
    ]


# ---------------------------------------------------------------------------
# Format checks
# ---------------------------------------------------------------------------

_HTML_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")


def check_html_tags(text: str, row: int, field: str) -> list[Issue]:
    """Detect HTML tags in text."""
    match = _HTML_TAG_RE.search(text)
    if not match:
        return []
    return [
        Issue(
            check="html_tags",
            severity=Severity.WARNING,
            row=row,
            field=field,
            message=f"HTML tag found: {match.group()!r}",
            snippet=_snippet(text),
        )
    ]


_URL_RE = re.compile(r"https?://\S+|www\.\S+")


def check_urls(text: str, row: int, field: str) -> list[Issue]:
    """Detect URLs in text."""
    match = _URL_RE.search(text)
    if not match:
        return []
    return [
        Issue(
            check="urls",
            severity=Severity.INFO,
            row=row,
            field=field,
            message=f"URL found: {_snippet(match.group(), 60)}",
            snippet=_snippet(text),
        )
    ]


_TRANSLIT_WORDS: frozenset[str] = frozenset({
    "inshallah", "insha'allah", "insha allah",
    "wallah", "wallahi",
    "yallah", "yalla",
    "habibi", "habibti",
    "mashallah", "masha'allah", "masha allah",
    "alhamdulillah", "alhamdu lillah",
    "bismillah",
    "subhanallah",
    "jazakallah",
    "assalamu", "salam", "salaam",
    "sheikh", "shaykh",
    "akhbar", "ahlan", "shukran",
})

_TRANSLIT_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in sorted(_TRANSLIT_WORDS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def check_transliteration_leak(text: str, row: int, field: str) -> list[Issue]:
    """Detect Arabic text written in Latin transliteration."""
    match = _TRANSLIT_RE.search(text)
    if not match:
        return []
    return [
        Issue(
            check="transliteration_leak",
            severity=Severity.WARNING,
            row=row,
            field=field,
            message=f"Transliteration detected: {match.group()!r}",
            snippet=_snippet(text),
        )
    ]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

# All simple checks that take (text, row, field) -> list[Issue].
ALL_CHECKS: list = [
    check_encoding_mixed,
    check_encoding_replacement,
    check_invisible_chars,
    check_empty_or_whitespace,
    check_too_short,
    check_too_long,
    # check_duplicated_text is special — requires `seen` kwarg.
    check_no_arabic,
    check_low_arabic_ratio,
    check_mixed_dialects,
    check_tashkeel_inconsistency,
    check_tatweel_excessive,
    check_html_tags,
    check_urls,
    check_transliteration_leak,
]

CHECK_DESCRIPTIONS: dict[str, str] = {
    "encoding_mixed": "Detect mojibake from UTF-8 / Latin-1 encoding mixup",
    "encoding_replacement": "Detect U+FFFD replacement characters",
    "invisible_chars": "Detect bidi overrides and zero-width characters (allows LRM/RLM)",
    "empty_or_whitespace": "Detect empty or whitespace-only fields",
    "too_short": "Detect text shorter than 3 characters",
    "too_long": "Detect text longer than 10 000 characters",
    "duplicated_text": "Detect exact duplicate rows",
    "no_arabic": "Detect text with zero Arabic characters",
    "low_arabic_ratio": "Detect text where less than 30% of letters are Arabic",
    "mixed_dialects": "Detect markers from multiple Arabic dialects in one text",
    "tashkeel_inconsistency": "Detect inconsistent diacritization across words",
    "tatweel_excessive": "Detect excessive tatweel (kashida) usage",
    "html_tags": "Detect HTML tags in text",
    "urls": "Detect URLs in text",
    "transliteration_leak": "Detect Arabic written in Latin transliteration",
}
