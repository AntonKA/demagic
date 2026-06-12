"""Parse Prg_N.xml -> ProgramIR.

Walks the task tree recursively. Tags it understands become IR; every tag it
does NOT understand is counted in ProgramIR.unknown_tags so the scan stage can
register them as `unparsed` ledger entries. The parser never raises on
unknown content, and always descends into unknown containers — unknown structural
wrappers are the norm in real xpa 4.x exports.

Real xpa 4.x schema (verified against corpus):
  Application > Header (app metadata)
              > ProgramsRepository > Programs > Task
                  > Header (Description=, ISN_2=, ...)
                  > Resource > DB id=... > DataObject obj=...
                              > Columns > Column ...
                  > Information > DB comp=... (task-level DB ref)
                  > TaskLogic > LogicUnit > Level, LogicLines > LogicLine > ...
                  > TaskForms > FormEntry > PropertyList > FormName id=311
                                           > Control > PropertyList > ControlName id=46
                  > Expressions > Expression > ExpSyntax (program-level expression table)
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from demagic.ir.models import (
    CallIR, ExpressionIR, FormIR, LogicUnitIR, MessageIR, ProgramIR,
)

# Tags that trigger specific extraction logic in the walker.
# Unknown tags are still descended into — they are just also counted in
# unknown_tags so the ledger can report them.
_EXTRACT_TAGS = {
    "Header", "DB", "DataObject",
    "LogicUnit", "Level", "LogicLines", "LogicLine", "OperationType",
    "ExpSyntax", "CallTask", "TaskID", "STP",
    "Form", "FormEntry", "FormName", "Control", "ControlName",
    "SnippetCode", "DotNetType",
    "Expressions", "Expression",
}

# Purely structural containers — we descend but don't count as unknown.
_STRUCTURAL = {
    "Application", "Task", "DataView", "Forms", "LogicUnits",
    "Columns", "Column", "LNK", "EVNT", "PropertyList",
    "ProgramsRepository", "Programs",
    "Resource", "Information", "TaskLogic", "TaskForms",
    "Arguments", "Argument",
    "ReturnValue", "ParametersAttributes",
    "Key", "Sort", "BOX", "WIN", "SIDE_WIN", "TaskProperties",
    "VarRange", "Locate", "Range",
    "FieldRanges", "FLD_RNG",
    "ItemIsn",
}


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def parse_program(path: Path) -> ProgramIR:
    prog_id = path.stem.removeprefix("Prg_")
    prg = ProgramIR(artifact_id=f"prg:{prog_id}", prog_id=prog_id)
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        prg.unknown_tags["<XML PARSE ERROR>"] = 1
        prg.task_descriptions.append(f"PARSE ERROR: {exc}")
        return prg

    expr_counter = 0

    def new_logic_unit(level_el: ET.Element | None) -> LogicUnitIR:
        idx = len(prg.logic_units)
        return LogicUnitIR(
            artifact_id=f"prg:{prog_id}/lu:{idx}",
            level=level_el.get("val", "") if level_el is not None else "",
        )

    def get_exprtable_lu() -> LogicUnitIR:
        """Lazily create the synthetic logic unit that holds program-level expressions."""
        lu = LogicUnitIR(artifact_id=f"prg:{prog_id}/lu:exprtable", level="X")
        prg.logic_units.append(lu)
        return lu

    # Sentinel: holds the exprtable LU once created (avoids repeated search).
    _exprtable_lu: list[LogicUnitIR] = []

    def walk(elem: ET.Element, current_lu: LogicUnitIR | None,
             current_form: FormIR | None, in_exprtable: bool = False) -> None:
        nonlocal expr_counter
        for child in elem:
            tag = _local(child.tag)

            # Count truly unknown tags (not structural containers, not extract tags).
            if tag not in _EXTRACT_TAGS and tag not in _STRUCTURAL:
                prg.unknown_tags[tag] = prg.unknown_tags.get(tag, 0) + 1
                # Always descend — unknown structural wrappers are common.
                walk(child, current_lu, current_form, in_exprtable)
                continue

            if tag == "Header":
                desc = child.get("Description", "")
                if desc:
                    prg.task_descriptions.append(desc)

            elif tag == "DB":
                # Two forms:
                #   old/fixture: <DB obj="1" comp="0"/>
                #   real 4.x:   <DB id="1"> <DataObject comp="-1" obj="1679"/> </DB>
                obj = child.get("obj", "")
                if obj and obj not in prg.data_object_refs:
                    prg.data_object_refs.append(obj)
                # Child DataObject tags handled by the DataObject branch below
                # via normal recursion.

            elif tag == "DataObject":
                obj = child.get("obj", "")
                if obj and obj not in prg.data_object_refs:
                    prg.data_object_refs.append(obj)

            elif tag == "Expressions":
                # Program-level expression table (after TaskForms in real schema).
                # Walk children directly as exprtable mode; don't recurse further.
                walk(child, current_lu, current_form, in_exprtable=True)
                continue

            elif tag == "Expression" and in_exprtable:
                # Individual expression in the Expressions table.
                syntax = child.find("ExpSyntax")
                if syntax is not None:
                    val = syntax.get("val", "")
                    if val:
                        if not _exprtable_lu:
                            _exprtable_lu.append(get_exprtable_lu())
                        _exprtable_lu[0].expressions.append(ExpressionIR(
                            artifact_id=f"prg:{prog_id}/expr:{expr_counter}",
                            text=val,
                        ))
                        expr_counter += 1
                continue  # Expression children already handled above

            elif tag == "LogicUnit":
                lu = new_logic_unit(child.find("Level"))
                prg.logic_units.append(lu)
                walk(child, lu, current_form, in_exprtable)
                continue

            elif tag == "LogicLine" and current_lu is not None:
                current_lu.logic_lines += 1

            elif tag == "OperationType" and current_lu is not None:
                val = child.get("val", "")
                if val:
                    current_lu.operations[val] = current_lu.operations.get(val, 0) + 1

            elif tag == "ExpSyntax" and current_lu is not None and not in_exprtable:
                # Inline expression under a LogicLine (original schema).
                val = child.get("val", "")
                if val:
                    current_lu.expressions.append(ExpressionIR(
                        artifact_id=f"prg:{prog_id}/expr:{expr_counter}", text=val))
                    expr_counter += 1

            elif tag == "CallTask" and current_lu is not None:
                task_id = child.find("TaskID")
                current_lu.calls.append(CallIR(
                    target_obj=task_id.get("obj") if task_id is not None else None,
                    target_comp=task_id.get("comp") if task_id is not None else None,
                ))

            elif tag == "STP":
                txt = child.get("TXT", "")
                if txt:
                    prg.messages.append(MessageIR(
                        text=txt, mode=child.get("Mode", ""),
                        title=child.get("TitleTxt", "")))

            elif tag in ("Form", "FormEntry"):
                # Form: legacy fixture schema  (<Forms><Form>)
                # FormEntry: real xpa 4.x schema (<TaskForms><FormEntry>)
                form = FormIR(
                    artifact_id=f"prg:{prog_id}/form:{len(prg.forms)}", name="")
                prg.forms.append(form)
                walk(child, current_lu, form, in_exprtable)
                continue

            elif tag == "FormName" and current_form is not None:
                # Both schemas: <FormName valUnicode="..."/> or attribute on PropertyList child
                current_form.name = child.get("valUnicode", child.get("val", ""))

            elif tag == "ControlName" and current_form is not None:
                val = child.get("val", "")
                if val:
                    current_form.controls.append(val)

            elif tag == "SnippetCode":
                val = child.get("val", "")
                if val:
                    prg.snippets.append(val)

            elif tag == "DotNetType":
                val = child.get("val", "")
                if val:
                    prg.dotnet_types.append(val)

            walk(child, current_lu, current_form, in_exprtable)

    walk(root, None, None)
    return prg
