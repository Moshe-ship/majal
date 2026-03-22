"""CLI entry point for majal."""

from __future__ import annotations

import argparse
import sys
from typing import NoReturn

from majal.display import (
    console,
    display_explain,
    display_json,
    display_scan,
    display_stats,
)


# ── Subcommand handlers ────────────────────────────────────────────


def _cmd_scan(args: argparse.Namespace) -> int:
    """Run the scan subcommand."""
    from majal.scanner import scan_file

    result = scan_file(
        args.file,
        fields=_parse_list(args.fields),
        min_severity=args.severity,
        checks=_parse_list(args.checks),
        limit=args.limit,
    )

    if args.json:
        display_json(result)
    else:
        display_scan(result)

    from majal.checks import Severity
    errors = sum(1 for i in result.issues if i.severity == Severity.ERROR)
    return 1 if errors else 0


def _cmd_stats(args: argparse.Namespace) -> int:
    """Run the stats subcommand — show dataset statistics only."""
    from majal.scanner import read_dataset, detect_text_fields, compute_stats

    rows = read_dataset(args.file)
    fields = detect_text_fields(rows)
    stats = compute_stats(rows, fields)
    display_stats(stats)
    return 0


def _cmd_fix(args: argparse.Namespace) -> int:
    """Run the fix subcommand — auto-fix common issues."""
    from majal.fixer import fix_file

    output = args.output
    if output is None:
        # Default output path: FILE.cleaned.jsonl
        base = args.file
        if base.endswith(".jsonl"):
            output = base[:-6] + ".cleaned.jsonl"
        elif base.endswith(".csv"):
            output = base[:-4] + ".cleaned.csv"
        elif base.endswith(".txt"):
            output = base[:-4] + ".cleaned.txt"
        else:
            output = base + ".cleaned"

    # Dry-run first to show what would change.
    changes = fix_file(args.file, dry_run=True)

    if not changes:
        console.print("[green]No fixable issues found.[/green]")
        return 0

    console.print(f"[bold]{len(changes)} fixable issue(s) found:[/bold]")
    for change in changes:
        console.print(f"  [dim]{change}[/dim]")

    if not args.yes:
        console.print()
        console.print(f"[bold]Output would be written to:[/bold] {output}")
        try:
            answer = console.input("\n[bold]Apply fixes? [y/N] [/bold]")
        except EOFError:
            answer = ""
        if answer.strip().lower() not in ("y", "yes"):
            console.print("[dim]Aborted.[/dim]")
            return 0

    # Actually fix.
    fix_file(args.file, output=output, dry_run=False)
    console.print(f"[green]Cleaned file written to {output}[/green]")
    return 0


def _cmd_explain(_args: argparse.Namespace) -> int:
    """Run the explain subcommand — show all available checks."""
    display_explain()
    return 0


def _cmd_sample(args: argparse.Namespace) -> int:
    """Run the sample subcommand — show random rows."""
    from majal.scanner import sample_rows

    rows = sample_rows(args.file, n=args.n)

    console.print()
    console.print("[bold magenta]majal[/bold magenta] [dim]- Arabic Dataset Inspector[/dim]")
    console.print()

    for idx, row in enumerate(rows, 1):
        console.print(f"[bold cyan]--- Row {idx} ---[/bold cyan]")
        if isinstance(row, dict):
            for key, value in row.items():
                console.print(f"  [bold]{key}:[/bold] {value}")
        else:
            console.print(f"  {row}")
        console.print()

    return 0


# ── Helpers ────────────────────────────────────────────────────────


def _parse_list(value: str | None) -> list[str] | None:
    """Parse a comma-separated string into a list, or None."""
    if value is None:
        return None
    parts = [p.strip() for p in value.split(",") if p.strip()]
    return parts or None


# ── Argument parser construction ───────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="majal",
        description=(
            "Arabic Dataset Inspector \u2014 scan training data for "
            "Arabic-specific quality issues."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_get_version()}",
    )

    subparsers = parser.add_subparsers(dest="command")

    # ── scan ──
    scan_parser = subparsers.add_parser(
        "scan", help="Scan a dataset file for quality issues (default)"
    )
    scan_parser.add_argument(
        "file",
        help="Dataset file to scan (JSONL, CSV, or TXT)",
    )
    scan_parser.add_argument(
        "--fields",
        default=None,
        help="Comma-separated fields to check (auto-detect if not given)",
    )
    scan_parser.add_argument(
        "--severity",
        choices=["error", "warning", "info"],
        default="info",
        help="Minimum severity to report (default: info)",
    )
    scan_parser.add_argument(
        "--checks",
        default=None,
        help="Comma-separated check IDs to run (all by default)",
    )
    scan_parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output results as JSON",
    )
    scan_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only scan first N rows",
    )

    # ── stats ──
    stats_parser = subparsers.add_parser(
        "stats", help="Show dataset statistics only (no issue checking)"
    )
    stats_parser.add_argument(
        "file",
        help="Dataset file to analyze",
    )

    # ── fix ──
    fix_parser = subparsers.add_parser(
        "fix", help="Auto-fix common issues in a dataset file"
    )
    fix_parser.add_argument(
        "file",
        help="Dataset file to fix",
    )
    fix_parser.add_argument(
        "--output",
        default=None,
        help="Output path (default: FILE.cleaned.jsonl)",
    )
    fix_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Show what would change without writing (default)",
    )
    fix_parser.add_argument(
        "--yes",
        action="store_true",
        default=False,
        help="Skip confirmation prompt and apply fixes",
    )

    # ── explain ──
    subparsers.add_parser(
        "explain", help="Explain all available checks"
    )

    # ── sample ──
    sample_parser = subparsers.add_parser(
        "sample", help="Show random rows from a dataset file"
    )
    sample_parser.add_argument(
        "file",
        help="Dataset file to sample from",
    )
    sample_parser.add_argument(
        "--n",
        type=int,
        default=5,
        help="Number of rows to show (default: 5)",
    )

    return parser


def _get_version() -> str:
    """Return the package version string."""
    from majal import __version__

    return __version__


# ── Entry point ────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> NoReturn:
    """Main entry point for the majal CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Default to scan when no subcommand is given.
    if args.command is None:
        args = parser.parse_args(["scan", *(argv or sys.argv[1:])])

    dispatch = {
        "scan": _cmd_scan,
        "stats": _cmd_stats,
        "fix": _cmd_fix,
        "explain": _cmd_explain,
        "sample": _cmd_sample,
    }

    try:
        handler = dispatch[args.command]
        code = handler(args)
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")
        code = 130
    except BrokenPipeError:
        # Silently handle piping to head/less.
        code = 0

    sys.exit(code)
