"""Stage 5: verify - ledger reconciliation + static checks on generated code."""
from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from demagic.ledger.ledger import ArtifactStatus, Ledger, LedgerEntry


@dataclass
class VerificationResult:
    pending: list[str] = field(default_factory=list)
    converted: int = 0
    flagged: int = 0
    unparsed: int = 0
    total: int = 0
    ruff_issues: int = 0
    ty_issues: int | None = None  # None = ty not installed (optional check)
    flagged_entries: list[LedgerEntry] = field(default_factory=list)
    unparsed_entries: list[LedgerEntry] = field(default_factory=list)


def run_ruff(target: Path) -> int:
    """Run ruff against generated code; returns issue count (0 = clean)."""
    proc = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--quiet", str(target)],
        capture_output=True, text=True)
    if proc.returncode == 0:
        return 0
    return len([line for line in proc.stdout.splitlines() if line.strip()])


def run_ty(target: Path) -> int | None:
    """Type-check generated code with ty if available; None when not installed."""
    ty = shutil.which("ty")
    if ty is None:
        return None
    proc = subprocess.run([ty, "check", str(target)], capture_output=True, text=True)
    if proc.returncode == 0:
        return 0
    return max(1, len([line for line in proc.stdout.splitlines() if line.strip()]))


def run_verification(workdir: Path, out_dir: Path) -> VerificationResult:
    ledger = Ledger.load(workdir)
    result = VerificationResult(pending=ledger.reconcile())
    for entry in ledger.all_entries():
        result.total += 1
        if entry.status == ArtifactStatus.CONVERTED:
            result.converted += 1
        elif entry.status == ArtifactStatus.FLAGGED:
            result.flagged += 1
            result.flagged_entries.append(entry)
        elif entry.status == ArtifactStatus.UNPARSED:
            result.unparsed += 1
            result.unparsed_entries.append(entry)
    result.ruff_issues = run_ruff(Path(out_dir) / "app")
    result.ty_issues = run_ty(Path(out_dir) / "app")
    return result
