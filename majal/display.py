"""Rich terminal display for majal results."""

from __future__ import annotations

import json
from collections import Counter

from rich.console import Console
from rich.table import Table
from rich.text import Text

from majal.checks import Severity, Issue, CHECK_DESCRIPTIONS

console = Console()

SEVERITY_COLORS: dict[Severity, str] = {
    Severity.ERROR: "red bold",
    Severity.WARNING: "yellow",
    Severity.INFO: "blue",
}

SEVERITY_ICONS: dict[Severity, str] = {
    Severity.ERROR: "ERR ",
    Severity.WARNING: "WARN",
    Severity.INFO: "INFO",
}


# ---------------------------------------------------------------------------
# Scan results
# ---------------------------------------------------------------------------


def display_scan(result, console: Console = console) -> None:
    """Render full scan results: header, stats, issues, and summary."""
    console.print()
    console.print("[bold magenta]majal[/bold magenta] [dim]- Arabic Dataset Inspector[/dim]")
    console.print()
    console.print(f"  [bold]File:[/bold]   {result.file}")
    console.print(f"  [bold]Rows:[/bold]   {result.total_rows}")
    console.print(f"  [bold]Fields:[/bold] {', '.join(result.fields_found)}")
    console.print()

    if result.stats:
        _render_stats_table(result.stats, console)

    if result.issues:
        _render_issues_table(result.issues, console)
    else:
        console.print("[green]No issues found.[/green]")
        console.print()

    _render_issue_summary(result.issues, console)


def _render_stats_table(stats, console: Console = console) -> None:
    """Render dataset statistics."""
    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        padding=(0, 1),
    )

    table.add_column("Metric", style="bold white")
    table.add_column("Value", justify="right", style="dim white")

    table.add_row("Total rows", str(stats.total_rows))
    table.add_row("Total chars", f"{stats.total_chars:,}")
    table.add_row("Arabic ratio", f"{stats.arabic_char_ratio:.1%}")
    table.add_row("Avg length", f"{stats.avg_length:,.0f}")
    table.add_row("Min length", str(stats.min_length))
    table.add_row("Max length", f"{stats.max_length:,}")

    console.print(table)
    console.print()


def _render_issues_table(issues: list[Issue], console: Console = console) -> None:
    """Render issues as a Rich table sorted by severity desc, then row."""
    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        padding=(0, 1),
    )

    table.add_column("Severity", style="bold", min_width=6)
    table.add_column("Row", justify="right", style="dim white")
    table.add_column("Field", style="bold white")
    table.add_column("Check", style="yellow")
    table.add_column("Message", style="dim white")
    table.add_column("Snippet", max_width=40)

    sorted_issues = sorted(issues, key=lambda i: (-i.severity, i.row))

    for issue in sorted_issues:
        color = SEVERITY_COLORS.get(issue.severity, "white")
        icon = SEVERITY_ICONS.get(issue.severity, "?")
        snippet = Text(issue.snippet[:40], overflow="ellipsis", no_wrap=True)

        table.add_row(
            f"[{color}]{icon}[/{color}]",
            str(issue.row),
            issue.field,
            issue.check,
            issue.message,
            snippet,
        )

    console.print(table)
    console.print()


def _render_issue_summary(issues: list[Issue], console: Console = console) -> None:
    """Print counts per severity and per check."""
    if not issues:
        return

    sev_counts: Counter[Severity] = Counter()
    check_counts: Counter[str] = Counter()
    for issue in issues:
        sev_counts[issue.severity] += 1
        check_counts[issue.check] += 1

    console.print("[bold]Summary:[/bold]")
    for sev in sorted(sev_counts, reverse=True):
        count = sev_counts[sev]
        color = SEVERITY_COLORS.get(sev, "white")
        icon = SEVERITY_ICONS.get(sev, "?")
        console.print(f"  [{color}]{icon}[/{color}]  {count}")

    console.print()
    for check, count in check_counts.most_common():
        console.print(f"  [dim]{check}[/dim]  {count}")
    console.print()


# ---------------------------------------------------------------------------
# Stats only
# ---------------------------------------------------------------------------


def display_stats(stats, console: Console = console) -> None:
    """Render dataset statistics without issue checking."""
    console.print()
    console.print("[bold magenta]majal[/bold magenta] [dim]- Arabic Dataset Inspector[/dim]")
    console.print()
    _render_stats_table(stats, console)


# ---------------------------------------------------------------------------
# Compact summary
# ---------------------------------------------------------------------------


def display_summary(result, console: Console = console) -> None:
    """Print a compact one-line-per-check summary."""
    issues = result.issues

    sev_counts: Counter[Severity] = Counter()
    check_counts: Counter[str] = Counter()
    for issue in issues:
        sev_counts[issue.severity] += 1
        check_counts[issue.check] += 1

    errors = sev_counts.get(Severity.ERROR, 0)
    warnings = sev_counts.get(Severity.WARNING, 0)
    infos = sev_counts.get(Severity.INFO, 0)

    console.print()
    console.print(
        f"[red bold]{errors} error(s)[/red bold], "
        f"[yellow]{warnings} warning(s)[/yellow], "
        f"[blue]{infos} info(s)[/blue]"
    )

    for check, count in check_counts.most_common():
        console.print(f"  [dim]{check}[/dim]  {count}")
    console.print()


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------


def display_json(result, console: Console = console) -> None:
    """Print scan results as JSON."""
    output = {
        "file": result.file,
        "total_rows": result.total_rows,
        "fields": result.fields_found,
        "issues": [
            {
                "check": i.check,
                "severity": i.severity.name,
                "row": i.row,
                "field": i.field,
                "message": i.message,
                "snippet": i.snippet,
            }
            for i in result.issues
        ],
    }
    if result.stats:
        output["stats"] = {
            "total_rows": result.stats.total_rows,
            "total_chars": result.stats.total_chars,
            "arabic_char_ratio": round(result.stats.arabic_char_ratio, 3),
            "avg_length": round(result.stats.avg_length, 1),
            "min_length": result.stats.min_length,
            "max_length": result.stats.max_length,
        }
    print(json.dumps(output, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Explain all checks
# ---------------------------------------------------------------------------


def display_explain(console: Console = console) -> None:
    """Explain all available checks."""
    console.print()
    console.print("[bold magenta]majal[/bold magenta] [dim]- Arabic Dataset Inspector[/dim]")
    console.print()
    console.print("[bold]Available checks:[/bold]")
    console.print()

    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        padding=(0, 1),
    )

    table.add_column("Check", style="bold white", min_width=24)
    table.add_column("Description")

    for check_name, desc in sorted(CHECK_DESCRIPTIONS.items()):
        table.add_row(check_name, desc)

    console.print(table)
    console.print()

    console.print("[bold]Auto-fixable:[/bold]")
    console.print()
    console.print("  [bold cyan]majal fix FILE[/bold cyan]         Strip invisible chars, HTML, excessive tatweel, duplicates")
    console.print("  [bold cyan]majal fix --yes FILE[/bold cyan]   Apply without confirmation")
    console.print()
