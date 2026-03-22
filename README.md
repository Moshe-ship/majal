# majal (مجال) — Arabic Dataset Inspector

> Scan your training data for Arabic-specific quality issues before they wreck your model.

## Why

Built from experience training Arabic LLMs ([Aamil](https://github.com/Moshe-ship/Aamil) project). Bad data = bad models. Encoding issues, invisible characters, dialect mixing, transliteration leaks — majal catches them all.

## Install

```bash
pip install majal
```

## Quick Start

```bash
# Scan for issues
majal scan data.jsonl

# Get dataset statistics
majal stats data.jsonl

# Auto-fix what can be fixed
majal fix data.jsonl
```

## Commands

| Command | Description |
|---------|-------------|
| `scan` | Find quality issues. Rich table output with severity, position, and context. |
| `stats` | Dataset statistics — language breakdown, token counts, field analysis. |
| `fix` | Auto-fix issues. Shows diff preview before writing. Use `--yes` to skip prompt. |
| `explain` | Learn about each check. Visual examples, severity rationale. |
| `sample` | Random sample from dataset with quality annotations. |

## Checks

| Category | Check | Severity | Description |
|----------|-------|----------|-------------|
| Encoding | `mojibake` | ERROR | Garbled Arabic from encoding mismatches (UTF-8 read as Windows-1256) |
| Encoding | `mixed-encoding` | ERROR | Different encodings within the same example |
| Encoding | `bom-artifact` | WARN | Byte Order Mark remnants in text |
| Invisible | `zwsp-injection` | ERROR | Zero-width spaces breaking Arabic word boundaries |
| Invisible | `bidi-override` | ERROR | Bidirectional override characters corrupting text flow |
| Invisible | `invisible-control` | WARN | Control characters that survive copy-paste silently |
| Content | `empty-response` | ERROR | Empty or whitespace-only response fields |
| Content | `truncated-text` | WARN | Text cut off mid-sentence or mid-word |
| Content | `duplicate-example` | WARN | Near-duplicate training examples (fuzzy match) |
| Content | `low-quality` | INFO | Very short, repetitive, or boilerplate responses |
| Arabic | `dialect-mixing` | WARN | MSA and dialect mixed within the same example |
| Arabic | `transliteration-leak` | ERROR | Romanized Arabic (e.g. "7abibi") in Arabic-expected fields |
| Arabic | `tashkeel-inconsistency` | INFO | Inconsistent diacritics within the dataset |
| Arabic | `broken-shaping` | ERROR | Arabic letters not joining correctly (presentation forms) |
| Format | `field-mismatch` | ERROR | Missing or unexpected fields in structured data |
| Format | `json-escape-error` | ERROR | Broken JSON escaping corrupting Arabic text |

## Supported Formats

- **JSONL** — one JSON object per line (instruction/response, messages, etc.)
- **CSV** — auto-detects text columns
- **TXT** — one example per line or paragraph-separated

Auto-detects text fields. Override with `--field`.

## As a Library

```python
from majal import scan_dataset

results = scan_dataset("data.jsonl")
for issue in results.issues:
    print(f"[{issue.severity}] {issue.check}: {issue.message}")
    print(f"  Line {issue.line}: {issue.context}")
```

---

مقدمة من [مجتمع الذكاء الاصطناعي السعودي](https://x.com/i/communities/2032184341682643429) للعرب أولا وللعالم أجمع

MIT License — [Musa the Carpenter](https://github.com/Moshe-ship)
