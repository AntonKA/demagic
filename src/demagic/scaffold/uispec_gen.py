"""Emit one JSON UI spec per form so any frontend can be rebuilt from it."""
from __future__ import annotations

import json
from pathlib import Path

from demagic.ir.models import MenuEntryIR, ProgramIR


def write_ui_specs(programs: list[ProgramIR], out_dir: Path) -> dict[str, str]:
    """Returns {form_artifact_id: written_path}."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}
    for prg in programs:
        for i, form in enumerate(prg.forms):
            spec = {
                "source_artifact": form.artifact_id,
                "program": prg.prog_id,
                "name": form.name,
                "controls": form.controls,
                "messages": [m.model_dump() for m in prg.messages],
            }
            path = out_dir / f"prg_{prg.prog_id}_form_{i}.json"
            path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
            written[form.artifact_id] = str(path)
    return written


def write_menu_spec(menus: list[MenuEntryIR], out_dir: Path) -> str | None:
    """Write menus.json to *out_dir* and return its path string.

    Returns None if *menus* is empty.
    """
    if not menus:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "menus.json"
    path.write_text(
        json.dumps([m.model_dump() for m in menus], indent=2), encoding="utf-8"
    )
    return str(path)
