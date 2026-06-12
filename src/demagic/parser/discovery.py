"""Marker-based project discovery.

A Magic xpa project is any directory containing a *.xpaproj file, or a
Source/ subdirectory holding DataSources.xml or Prg_*.xml. Repository
layouts vary wildly between shops - never assume structure above the
project directory.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DiscoveredProject:
    name: str
    root: Path
    source_dir: Path
    prg_count: int
    fingerprint: str  # equal fingerprints == near-certain duplicate copies


def _fingerprint(source_dir: Path) -> str:
    """Cheap content fingerprint: names + sizes of all Source XML files."""
    h = hashlib.sha256()
    for f in sorted(source_dir.glob("*.xml")):
        h.update(f.name.encode())
        h.update(str(f.stat().st_size).encode())
    return h.hexdigest()[:16]


def _find_source_dir(project_root: Path) -> Path | None:
    candidates = [project_root / "Source", project_root]
    for c in candidates:
        if (c / "DataSources.xml").exists() or list(c.glob("Prg_*.xml")):
            return c
    return None


def discover_projects(base: Path) -> list[DiscoveredProject]:
    base = Path(base)
    projects: list[DiscoveredProject] = []

    markers = list(base.rglob("*.xpaproj"))
    marker_roots: set[Path] = {m.parent for m in markers}
    # Also catch bare Source dirs with no .xpaproj next to them (DataSources.xml present)
    for ds in base.rglob("DataSources.xml"):
        root = ds.parent.parent if ds.parent.name == "Source" else ds.parent
        marker_roots.add(root)
    # Also catch Prg-only projects (no DataSources.xml, just Prg_*.xml)
    for prg in base.rglob("Prg_*.xml"):
        parent = prg.parent
        root = parent.parent if parent.name == "Source" else parent
        marker_roots.add(root)

    for root in sorted(marker_roots):
        source_dir = _find_source_dir(root)
        if source_dir is None:
            continue
        prg_count = len(list(source_dir.glob("Prg_*.xml")))
        projects.append(DiscoveredProject(
            name=root.name, root=root, source_dir=source_dir,
            prg_count=prg_count, fingerprint=_fingerprint(source_dir),
        ))
    return projects
