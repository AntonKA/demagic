"""Reconcile agent-edited service files back into the Coverage Ledger.

This is what lets an editor's AI agent (Claude Code, Cursor, Copilot, Aider...)
do the translation with its own model and tokens, then close the ledger without
demagic ever calling an LLM API itself:

  1. scaffold drops a stub per program carrying a DEMAGIC-PENDING marker.
  2. the agent replaces the stub body with real Python.
  3. `demagic verify` runs this pass: a pending program whose service file no
     longer has the marker and parses as Python is marked converted - or
     flagged if the agent left a `# DEMAGIC-FLAG: <reason>` line.
"""
from __future__ import annotations

import ast
from pathlib import Path

from demagic.ledger.ledger import ArtifactStatus, Ledger
from demagic.scaffold.project_gen import PENDING_MARKER
from demagic.scan import IR_FILENAME, load_ir

FLAG_MARKER = "# DEMAGIC-FLAG"


def reconcile_from_disk(workdir: Path, out_dir: Path) -> int:
    """Mark pending programs converted/flagged from their on-disk service file.

    Returns the number of programs reconciled. A no-op when no IR exists or no
    pending program has been edited.
    """
    workdir, out_dir = Path(workdir), Path(out_dir)
    if not (workdir / IR_FILENAME).exists():
        return 0
    project = load_ir(workdir)
    ledger = Ledger.load(workdir)
    reconciled = 0

    for prg in project.programs:
        if ledger.get(prg.artifact_id).status != ArtifactStatus.PENDING:
            continue
        svc = out_dir / "app" / "services" / f"prg_{prg.prog_id}.py"
        if not svc.exists():
            continue
        text = svc.read_text(encoding="utf-8")
        if PENDING_MARKER in text:
            continue  # still an untranslated stub
        try:
            ast.parse(text)
        except SyntaxError:
            continue  # agent's edit is not valid Python yet - leave pending

        flags = [ln.split(FLAG_MARKER, 1)[1].lstrip(": ").rstrip()
                 for ln in text.splitlines() if FLAG_MARKER in ln]
        if flags:
            status, reason = ArtifactStatus.FLAGGED, "; ".join(f for f in flags if f)
        else:
            status, reason = ArtifactStatus.CONVERTED, None

        ledger.set_status(prg.artifact_id, status, reason=reason, output_path=str(svc))
        for lu in prg.logic_units:
            ledger.set_status(lu.artifact_id, status, reason=reason, output_path=str(svc))
            for expr in lu.expressions:
                ledger.set_status(expr.artifact_id, status, reason=reason,
                                  output_path=str(svc))
        reconciled += 1

    if reconciled:
        ledger.save()
    return reconciled
