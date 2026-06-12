"""Stage 1: scan - parse a project into IR and register every artifact."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from demagic.ir.models import ProjectIR
from demagic.ledger.ledger import ArtifactStatus, Ledger
from demagic.parser.datasources import parse_datasources
from demagic.parser.discovery import discover_projects
from demagic.parser.menus import parse_menus
from demagic.parser.program import parse_program
from demagic.parser.program_headers import parse_program_headers

IR_FILENAME = "ir.json"

# Source files with a dedicated parser. Every OTHER *.xml in Source/ is
# registered as unparsed so the 100% guarantee covers files, not just elements.
_HANDLED_FILES = {"DataSources.xml", "ProgramHeaders.xml", "Menus.xml"}


def scan_project(project_root: Path, workdir: Path) -> ProjectIR:
    project_root = Path(project_root)
    candidates = discover_projects(project_root)
    if not candidates:
        raise FileNotFoundError(f"No Magic xpa project found under {project_root}")
    if len(candidates) > 1:
        desc = ", ".join(f"{c.name}({c.fingerprint})" for c in candidates)
        raise ValueError(
            f"Multiple projects found under {project_root}: {desc}. "
            "Point at a single project directory."
        )
    discovered = candidates[0]
    src = discovered.source_dir

    ledger = Ledger.load(workdir)

    # --- DataSources.xml ---
    ds_path = src / "DataSources.xml"
    if ds_path.exists():
        try:
            data_objects = parse_datasources(ds_path)
        except ET.ParseError as exc:
            data_objects = []
            aid = "src:DataSources.xml"
            ledger.register(aid, kind="unparsed_xml")
            ledger.set_status(aid, ArtifactStatus.UNPARSED,
                              reason=f"XML parse error: {exc}")
    else:
        data_objects = []

    # --- ProgramHeaders.xml ---
    ph_path = src / "ProgramHeaders.xml"
    if ph_path.exists():
        try:
            program_headers = parse_program_headers(ph_path)
        except ET.ParseError as exc:
            program_headers = []
            aid = "src:ProgramHeaders.xml"
            ledger.register(aid, kind="unparsed_xml")
            ledger.set_status(aid, ArtifactStatus.UNPARSED,
                              reason=f"XML parse error: {exc}")
    else:
        program_headers = []

    # --- Prg_*.xml ---
    programs = []
    for p in sorted(src.glob("Prg_*.xml")):
        programs.append(parse_program(p))

    # --- Menus.xml ---
    menus_path = src / "Menus.xml"
    if menus_path.exists():
        try:
            menus = parse_menus(menus_path)
        except ET.ParseError as exc:
            menus = []
            aid = "src:Menus.xml"
            ledger.register(aid, kind="unparsed_xml")
            ledger.set_status(aid, ArtifactStatus.UNPARSED,
                              reason=f"XML parse error: {exc}")
    else:
        menus = []

    project = ProjectIR(
        artifact_id=f"prj:{discovered.name}",
        name=discovered.name,
        source_dir=str(src),
        data_objects=data_objects,
        program_headers=program_headers,
        programs=programs,
        menus=menus,
    )

    _register_all(project, ledger, program_headers)
    for f in sorted(src.glob("*.xml")):
        if f.name in _HANDLED_FILES or f.name.startswith("Prg_"):
            continue
        aid = f"src:{f.name}"
        # Only register if not already registered (e.g. parse-error path above)
        ledger.register(aid, kind="unparsed_xml")
        if ledger.get(aid).status == ArtifactStatus.PENDING:
            ledger.set_status(aid, ArtifactStatus.UNPARSED,
                              reason=f"Source file {f.name} has no dedicated parser yet")
    ledger.save()

    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / IR_FILENAME).write_text(project.model_dump_json(indent=2), encoding="utf-8")
    return project


def _register_menu(entry, ledger: Ledger) -> None:
    ledger.register(entry.artifact_id, kind="menu")
    for child in entry.children:
        _register_menu(child, ledger)


def _register_all(project: ProjectIR, ledger: Ledger, program_headers) -> None:
    ledger.register(project.artifact_id, kind="project")
    for obj in project.data_objects:
        ledger.register(obj.artifact_id, kind="data_object")
    # Register all program headers so reconcile() can detect missing Prg_*.xml
    for hdr in program_headers:
        ledger.register(hdr.artifact_id, kind="program")
    for prg in project.programs:
        ledger.register(prg.artifact_id, kind="program")
        for lu in prg.logic_units:
            ledger.register(lu.artifact_id, kind="logic_unit")
            for expr in lu.expressions:
                ledger.register(expr.artifact_id, kind="expression")
        for form in prg.forms:
            ledger.register(form.artifact_id, kind="form")
        for tag, count in prg.unknown_tags.items():
            aid = f"{prg.artifact_id}/unparsed:{tag}"
            ledger.register(aid, kind="unparsed_xml")
            ledger.set_status(aid, ArtifactStatus.UNPARSED,
                              reason=f"unknown element <{tag}> x{count} in Prg_{prg.prog_id}.xml")
    for menu in project.menus:
        _register_menu(menu, ledger)


def load_ir(workdir: Path) -> ProjectIR:
    return ProjectIR.model_validate_json(
        (Path(workdir) / IR_FILENAME).read_text(encoding="utf-8"))
