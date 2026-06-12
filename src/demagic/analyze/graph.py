"""Stage 2: analyze - call graph, translation order, complexity, table usage."""
from __future__ import annotations

from dataclasses import dataclass, field
from graphlib import CycleError, TopologicalSorter

from demagic.ir.models import ProjectIR


@dataclass
class ProjectAnalysis:
    call_graph: dict[str, list[str]] = field(default_factory=dict)
    translation_order: list[str] = field(default_factory=list)  # prog_ids, deps first
    complexity: dict[str, int] = field(default_factory=dict)
    table_usage: dict[str, list[str]] = field(default_factory=dict)
    unreachable: list[str] = field(default_factory=list)  # dead-code candidates


def analyze_project(project: ProjectIR) -> ProjectAnalysis:
    analysis = ProjectAnalysis()
    obj_names = {o.obj_id: o.physical_name for o in project.data_objects}
    known_progs = {p.prog_id for p in project.programs}

    for prg in project.programs:
        callees = sorted({
            c.target_obj for lu in prg.logic_units for c in lu.calls
            if c.target_obj and c.target_obj in known_progs and c.target_obj != prg.prog_id
        })
        analysis.call_graph[prg.prog_id] = callees
        analysis.complexity[prg.prog_id] = sum(lu.logic_lines for lu in prg.logic_units)
        analysis.table_usage[prg.prog_id] = [
            obj_names[ref] for ref in prg.data_object_refs if ref in obj_names]

    sorter = TopologicalSorter(analysis.call_graph)
    try:
        analysis.translation_order = list(sorter.static_order())
    except CycleError:
        # Recursive program groups exist in real apps. Fall back to
        # complexity order (simplest first) - still deterministic.
        analysis.translation_order = sorted(
            analysis.call_graph, key=lambda p: analysis.complexity.get(p, 0))

    # Dead-code candidates: never called, not public, not on any menu.
    called = {c for callees in analysis.call_graph.values() for c in callees}
    public = {h.prog_id for h in project.program_headers if h.public_name}
    menu_progs: set[str] = set()

    def collect_menu(entry) -> None:
        if entry.program:
            menu_progs.add(entry.program)
        for child in entry.children:
            collect_menu(child)

    for menu in project.menus:
        collect_menu(menu)
    analysis.unreachable = sorted(
        p for p in analysis.call_graph
        if p not in called and p not in public and p not in menu_progs)
    return analysis
