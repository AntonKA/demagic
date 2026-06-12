"""Pydantic AI translation agent + context pack builder."""
from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models import Model

from demagic.analyze.expressions import analyze_expression
from demagic.ir.models import ProgramIR, ProjectIR

SYSTEM_PROMPT = """\
You are a senior engineer migrating a Magic xpa (4GL) application to Python.
You receive one Magic program at a time as a structured context pack.
Produce a complete Python module body implementing the same business logic.
Rules:
- Output a `run()` function (plus helpers) - pure Python 3.12, type-annotated.
- Use the SQLModel classes named in the pack for data access (assume a
  `session` can be created via `app.db.get_session()`).
- If any behavior is ambiguous or untranslatable, still produce your best
  code AND list it in `flags` - never silently drop behavior.
- List every assumption you make in `assumptions`.
"""


class TranslationResult(BaseModel):
    python_code: str = Field(description="Complete Python module body with run()")
    assumptions: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    flags: list[str] = Field(default_factory=list,
                             description="Behaviors needing human review")


def build_agent(model: Model | str) -> "Agent[None, TranslationResult]":
    agent: Agent[None, TranslationResult] = Agent(  # ty: ignore[invalid-assignment]
        model, output_type=TranslationResult, system_prompt=SYSTEM_PROMPT)
    return agent


def build_context_pack(project: ProjectIR, prg: ProgramIR) -> str:
    headers = {h.prog_id: h for h in project.program_headers}
    objs = {o.obj_id: o for o in project.data_objects}
    header = headers.get(prg.prog_id)

    lines = [f"## Magic program #{prg.prog_id}: "
             f"{header.description if header else ''}".rstrip()]
    if header:
        lines.append(f"Task type: {header.task_type}  Public: {header.public_name or '-'}")

    lines.append("\n### Bound data objects")
    for ref in prg.data_object_refs:
        obj = objs.get(ref)
        if obj:
            cols = ", ".join(f"{c.name}:{c.magic_type}" for c in obj.columns)
            lines.append(f"- {obj.physical_name} ({obj.object_type}) cols: {cols}")

    lines.append("\n### Logic units")
    for lu in prg.logic_units:
        lines.append(f"- Unit {lu.artifact_id} level={lu.level} "
                     f"ops={lu.operations} lines={lu.logic_lines}")
        for expr in lu.expressions:
            analysis = analyze_expression(expr.text)
            note = f" [unmapped fns: {analysis.unmapped}]" if analysis.unmapped else ""
            lines.append(f"  - expr: {expr.text}{note}")
        for call in lu.calls:
            if call.target_obj:
                lines.append(f"  - calls program {call.target_obj} "
                             f"(already translated: app.services.prg_{call.target_obj})")

    if prg.messages:
        lines.append("\n### User messages")
        for m in prg.messages:
            lines.append(f"- [{m.mode}] {m.text}")
    if prg.snippets:
        lines.append("\n### Embedded C# snippets (port to Python)")
        lines.extend(s[:2000] for s in prg.snippets)
    return "\n".join(lines)
