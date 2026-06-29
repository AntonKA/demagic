"""Pydantic AI translation agent + context pack builder."""
from __future__ import annotations

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models import Model

from demagic.analyze.expressions import analyze_expression
from demagic.ir.models import ProgramIR, ProjectIR

SYSTEM_PROMPT = """\
You are a senior engineer migrating a Magic xpa (4GL) application to Python.
You translate one Magic program at a time from a structured context pack into a
Python service module for a FastAPI + SQLModel app.

The generated app calls your code as `from app.services.prg_<id> import run`
then `run()`. Therefore:
- Define exactly ONE entry point: `def run() -> dict:` - synchronous, with NO
  parameters. Never `async def run`, never `def run(session, ...)`.
- Acquire data access INSIDE run(): `with get_session() as session:`
  (import `from app.db import get_session`). Import models from `app.models`
  by their generated CLASS name (e.g. `Customer`), not the table name.
- Put reusable logic in module-level helpers; keep run() as the orchestrator.

Translate faithfully:
- Magic built-ins map to Python: Trim(x)->x.strip(), Round(x,n)->round(x,n),
  Left/Right/Mid->slices, Upper/Lower->.upper()/.lower().
- An expression annotated `[unmapped fns: ...]` has no known mapping: keep its
  intent, do NOT invent precise behaviour, and add a `flag`.
- A bound data object marked `(S)` is a STORED PROCEDURE: invoke it
  (session.exec(text("EXEC ..."))), don't treat it as an ORM table.
- Preserve validation messages (e.g. `[E] ...`) as raised errors or error
  entries - never silently drop them.

Traceability: above each translated piece of logic, add an inline comment
quoting the ORIGINAL Magic expression verbatim, e.g. `# Magic: Trim(Name)`. Keep
the original text in a comment even when you also flag it, so a reviewer can grep
the generated code back to the Magic source.

Honesty: if anything is ambiguous or untranslatable, still produce your best
code AND record it in `flags`; never silently drop behaviour. List every
assumption in `assumptions`.
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
