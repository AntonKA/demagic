"""Parse Menus.xml -> list[MenuEntryIR] (recursive tree)."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from demagic.ir.models import MenuEntryIR


def _parse_entry(elem: ET.Element, counter: list[int]) -> MenuEntryIR:
    idx = counter[0]
    counter[0] += 1
    entry = MenuEntryIR(
        artifact_id=f"menu:{idx}",
        name=elem.get("name", elem.get("Name", elem.get("Description", ""))),
        program=elem.get("program", elem.get("Program", elem.get("ProgramNumber", ""))),
        entry_point=elem.get("EntryPoint", elem.get("PublicName", "")),
    )
    for child in elem:
        tag = child.tag.split("}", 1)[-1]
        if tag == "MenuEntry":
            entry.children.append(_parse_entry(child, counter))
    return entry


def parse_menus(path: Path) -> list[MenuEntryIR]:
    if not path.exists():
        return []
    root = ET.parse(path).getroot()
    counter = [0]
    entries: list[MenuEntryIR] = []

    # Walk only direct trees under container tags to avoid double-counting
    def collect(elem: ET.Element) -> None:
        for child in elem:
            tag = child.tag.split("}", 1)[-1]
            if tag == "MenuEntry":
                entries.append(_parse_entry(child, counter))
            else:
                collect(child)
    collect(root)
    return entries
