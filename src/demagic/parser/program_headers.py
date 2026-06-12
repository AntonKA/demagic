"""Parse ProgramHeaders.xml -> list[ProgramHeaderIR]."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from demagic.ir.models import ProgramHeaderIR


def _child_val(header: ET.Element, tag: str, attr: str = "val") -> str:
    el = header.find(tag)
    return el.get(attr, "") if el is not None else ""


def parse_program_headers(path: Path) -> list[ProgramHeaderIR]:
    root = ET.parse(path).getroot()
    headers: list[ProgramHeaderIR] = []
    for prog in root.findall(".//Program"):
        header = prog.find("Header")
        if header is None:
            continue
        prog_id = header.get("id", "")
        headers.append(ProgramHeaderIR(
            artifact_id=f"prg:{prog_id}",
            prog_id=prog_id,
            description=header.get("Description", ""),
            task_type=_child_val(header, "TaskType"),
            public_name=_child_val(header, "Public"),
            interactive=_child_val(header, "Interactive") == "Y",
            external=_child_val(header, "External") == "Y",
            has_dotnet=_child_val(header, "DotNetObjectExists") == "Y",
            is_empty=header.get("ISEMPTY_TSK", "") == "1",
            last_modified=_child_val(header, "LastModified", attr="date"),
        ))
    return headers
