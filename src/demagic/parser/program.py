"""Parse Prg_N.xml -> ProgramIR.

Walks the task tree recursively. Tags it understands become IR; every tag it
does NOT understand is counted in ProgramIR.unknown_tags so the scan stage can
register them as `unparsed` ledger entries. The parser never raises on
unknown content.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from demagic.ir.models import (
    CallIR, ExpressionIR, FormIR, LogicUnitIR, MessageIR, ProgramIR,
)

# Tags handled by this parser, plus pure structural containers we descend
# through without extracting anything. Anything else -> unknown_tags.
_KNOWN = {
    "Application", "Task", "Header", "DataView", "DB", "Forms", "Form",
    "FormName", "Control", "ControlName", "LogicUnits", "LogicUnit", "Level",
    "LogicLine", "OperationType", "ExpSyntax", "CallTask", "TaskID", "STP",
    "SnippetCode", "DotNetType", "Columns", "Column", "LNK", "EVNT",
}


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def parse_program(path: Path) -> ProgramIR:
    prog_id = path.stem.replace("Prg_", "")
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

    def walk(elem: ET.Element, current_lu: LogicUnitIR | None,
             current_form: FormIR | None) -> None:
        nonlocal expr_counter
        for child in elem:
            tag = _local(child.tag)
            if tag not in _KNOWN:
                prg.unknown_tags[tag] = prg.unknown_tags.get(tag, 0) + 1
                continue  # do not descend into unknown structure; it is ledgered

            if tag == "Header":
                desc = child.get("Description", "")
                if desc:
                    prg.task_descriptions.append(desc)
            elif tag == "DB":
                obj = child.get("obj", "")
                if obj and obj not in prg.data_object_refs:
                    prg.data_object_refs.append(obj)
            elif tag == "LogicUnit":
                lu = new_logic_unit(child.find("Level"))
                prg.logic_units.append(lu)
                walk(child, lu, current_form)
                continue
            elif tag == "LogicLine" and current_lu is not None:
                current_lu.logic_lines += 1
            elif tag == "OperationType" and current_lu is not None:
                val = child.get("val", "")
                if val:
                    current_lu.operations[val] = current_lu.operations.get(val, 0) + 1
            elif tag == "ExpSyntax" and current_lu is not None:
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
            elif tag == "Form":
                form = FormIR(
                    artifact_id=f"prg:{prog_id}/form:{len(prg.forms)}", name="")
                prg.forms.append(form)
                walk(child, current_lu, form)
                continue
            elif tag == "FormName" and current_form is not None:
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

            walk(child, current_lu, current_form)

    walk(root, None, None)
    return prg
