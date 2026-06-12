"""Stage 4: translate - resumable LLM translation over the dependency order."""
from __future__ import annotations

import ast
import json
from pathlib import Path

from pydantic_ai.models import Model

from demagic.analyze.graph import analyze_project
from demagic.ir.models import ProjectIR
from demagic.ledger.ledger import ArtifactStatus, Ledger
from demagic.translate.agent import TranslationResult, build_agent, build_context_pack

_MODULE_TEMPLATE = '''\
"""Service for Magic program #{prog_id} - translated by demagic.

Assumptions:
{assumptions}
"""
{code}
'''

# Success-path ledger saves are batched; the error path still saves
# immediately so a crash never loses a FLAGGED status.
_SAVE_EVERY = 50


def translate_all(project: ProjectIR, workdir: Path, out_dir: Path,
                  model: Model | str, only_unit: str | None = None,
                  ) -> dict[str, TranslationResult]:
    ledger = Ledger.load(workdir)
    agent = build_agent(model)
    order = analyze_project(project).translation_order
    programs = {p.prog_id: p for p in project.programs}
    results: dict[str, TranslationResult] = {}
    usage_totals = {"requests": 0, "input_tokens": 0, "output_tokens": 0}
    done_since_save = 0

    for prog_id in order:
        prg = programs[prog_id]
        if only_unit and prg.artifact_id != only_unit:
            continue
        if ledger.get(prg.artifact_id).status == ArtifactStatus.CONVERTED:
            continue  # resumable: skip done work

        pack = build_context_pack(project, prg)
        run = agent.run_sync(pack)
        result = run.output
        results[prog_id] = result
        usage = run.usage  # property in pydantic-ai >= 0.4 (was method in older versions)
        usage_totals["requests"] += getattr(usage, "requests", 0) or 0
        usage_totals["input_tokens"] += getattr(usage, "input_tokens", 0) or 0
        usage_totals["output_tokens"] += getattr(usage, "output_tokens", 0) or 0

        service_path = Path(out_dir) / "app" / "services" / f"prg_{prog_id}.py"
        try:
            ast.parse(result.python_code)
        except SyntaxError as exc:
            parse_reason = f"LLM output failed ast.parse: {exc}"
            ledger.set_status(prg.artifact_id, ArtifactStatus.FLAGGED, reason=parse_reason)
            for lu in prg.logic_units:
                ledger.set_status(lu.artifact_id, ArtifactStatus.FLAGGED, reason=parse_reason)
                for expr in lu.expressions:
                    ledger.set_status(expr.artifact_id, ArtifactStatus.FLAGGED,
                                      reason=parse_reason)
            ledger.save()
            continue

        assumptions = "\n".join(f"- {a}" for a in result.assumptions) or "- none stated"
        service_path.write_text(_MODULE_TEMPLATE.format(
            prog_id=prog_id, assumptions=assumptions, code=result.python_code),
            encoding="utf-8")

        status = ArtifactStatus.FLAGGED if result.flags else ArtifactStatus.CONVERTED
        reason = "; ".join(result.flags) if result.flags else None
        ledger.set_status(prg.artifact_id, status, reason=reason,
                          output_path=str(service_path))
        for lu in prg.logic_units:
            ledger.set_status(lu.artifact_id, status, reason=reason,
                              output_path=str(service_path))
            for expr in lu.expressions:
                ledger.set_status(expr.artifact_id, status, reason=reason,
                                  output_path=str(service_path))
        # On large projects the ledger is tens of MB; a full rewrite per
        # program dominates wall time, so batch the success-path saves.
        done_since_save += 1
        if done_since_save >= _SAVE_EVERY:
            ledger.save()
            done_since_save = 0

    ledger.save()
    (Path(workdir) / "usage.json").write_text(
        json.dumps(usage_totals, indent=2), encoding="utf-8")
    return results
