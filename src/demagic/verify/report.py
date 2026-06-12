"""Render the coverage report - the artifact that proves the 100% claim."""
from __future__ import annotations

from pathlib import Path

from demagic.verify.checks import VerificationResult

# Real apps can have 100k+ pending/unparsed artifacts; listing every id makes
# the report unreadable (and `demagic report` flood the terminal). The counts
# in the metric table stay exact - only the per-id listings are capped.
_MAX_LISTED = 100


def _capped(items: list[str]) -> list[str]:
    if len(items) <= _MAX_LISTED:
        return items
    return items[:_MAX_LISTED] + [f"- ... and {len(items) - _MAX_LISTED} more (see ledger.json)"]


def write_report(result: VerificationResult, workdir: Path) -> Path:
    accounted = result.total - len(result.pending)
    pct = (100 * accounted / result.total) if result.total else 100.0
    lines = [
        "# demagic coverage report",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Total artifacts | {result.total} |",
        f"| Accounted for | {accounted} ({pct:.0f}%) |",
        f"| Converted | {result.converted} |",
        f"| Flagged for review | {result.flagged} |",
        f"| Unparsed XML | {result.unparsed} |",
        f"| Pending (MUST be 0) | {len(result.pending)} |",
        f"| Ruff issues in generated code | {result.ruff_issues} |",
        f"| ty issues in generated code | "
        f"{'n/a (ty not installed)' if result.ty_issues is None else result.ty_issues} |",
        "",
    ]
    if result.pending:
        lines += ["## PENDING - pipeline incomplete", ""]
        lines += _capped([f"- `{aid}`" for aid in result.pending]) + [""]
    if result.flagged_entries:
        lines += ["## Flagged for human review", ""]
        lines += _capped(
            [f"- `{e.artifact_id}`: {e.reason}" for e in result.flagged_entries]) + [""]
    if result.unparsed_entries:
        lines += ["## Unparsed XML (parser gaps - please open an issue!)", ""]
        lines += _capped(
            [f"- `{e.artifact_id}`: {e.reason}" for e in result.unparsed_entries]) + [""]

    path = Path(workdir) / "coverage-report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
