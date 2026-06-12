"""Stage 1: scan - parse a project into IR and register every artifact."""
from __future__ import annotations

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
    discovered = candidates[0]
    src = discovered.source_dir

    ds_path = src / "DataSources.xml"
    ph_path = src / "ProgramHeaders.xml"
    project = ProjectIR(
        artifact_id=f"prj:{discovered.name}",
        name=discovered.name,
        source_dir=str(src),
        data_objects=parse_datasources(ds_path) if ds_path.exists() else [],
        program_headers=parse_program_headers(ph_path) if ph_path.exists() else [],
        programs=[parse_program(p) for p in sorted(src.glob("Prg_*.xml"))],
        menus=parse_menus(src / "Menus.xml"),
    )

    ledger = Ledger.load(workdir)
    _register_all(project, ledger)
    for f in sorted(src.glob("*.xml")):
        if f.name in _HANDLED_FILES or f.name.startswith("Prg_"):
            continue
        aid = f"src:{f.name}"
        ledger.register(aid, kind="unparsed_xml")
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


def _register_all(project: ProjectIR, ledger: Ledger) -> None:
    ledger.register(project.artifact_id, kind="project")
    for obj in project.data_objects:
        ledger.register(obj.artifact_id, kind="data_object")
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
