"""Tests for scan resilience: never-crash guarantee, ledger completeness, I1-I4."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from demagic.ledger.ledger import ArtifactStatus, Ledger
from demagic.scan import scan_project

FIXTURE_APP = Path(__file__).parent / "fixtures" / "sample_repo" / "CustomerApp"


# ---------------------------------------------------------------------------
# C1 / C2  — malformed XML must never crash scan
# ---------------------------------------------------------------------------

def test_malformed_datasources_xml_does_not_crash(tmp_path: Path):
    """C2a: garbage DataSources.xml → ProjectIR returned, ledger has UNPARSED entry."""
    app = tmp_path / "CustomerApp"
    shutil.copytree(FIXTURE_APP, app)
    (app / "Source" / "DataSources.xml").write_bytes(b"<<< not xml >>>")

    workdir = tmp_path / ".demagic"
    project = scan_project(app, workdir)

    assert project is not None
    assert project.data_objects == []

    led = Ledger.load(workdir)
    entry = led.get("src:DataSources.xml")
    assert entry.status == ArtifactStatus.UNPARSED
    assert "XML parse error" in (entry.reason or "")


def test_empty_datasources_xml_does_not_crash(tmp_path: Path):
    """C2b: 0-byte DataSources.xml → same outcome as malformed."""
    app = tmp_path / "CustomerApp"
    shutil.copytree(FIXTURE_APP, app)
    (app / "Source" / "DataSources.xml").write_bytes(b"")

    workdir = tmp_path / ".demagic"
    project = scan_project(app, workdir)

    assert project.data_objects == []

    led = Ledger.load(workdir)
    entry = led.get("src:DataSources.xml")
    assert entry.status == ArtifactStatus.UNPARSED
    assert "XML parse error" in (entry.reason or "")


def test_malformed_prg_xml_does_not_crash(tmp_path: Path):
    """C2c: malformed Prg_1.xml → ProgramIR with <XML PARSE ERROR>, ledger UNPARSED."""
    app = tmp_path / "CustomerApp"
    shutil.copytree(FIXTURE_APP, app)
    (app / "Source" / "Prg_1.xml").write_bytes(b"<broken>")

    workdir = tmp_path / ".demagic"
    project = scan_project(app, workdir)

    prg1 = next((p for p in project.programs if p.prog_id == "1"), None)
    assert prg1 is not None
    assert "<XML PARSE ERROR>" in prg1.unknown_tags

    led = Ledger.load(workdir)
    # The unknown tag triggers an unparsed ledger entry
    entry = led.get("prg:1/unparsed:<XML PARSE ERROR>")
    assert entry.status == ArtifactStatus.UNPARSED


# ---------------------------------------------------------------------------
# I1 — program headers must be ledgered even when Prg_*.xml is missing
# ---------------------------------------------------------------------------

def test_missing_prg_file_still_ledgered(tmp_path: Path):
    """I1: delete Prg_2.xml — ledger still has prg:2 (pending), reconcile reports it."""
    app = tmp_path / "CustomerApp"
    shutil.copytree(FIXTURE_APP, app)
    (app / "Source" / "Prg_2.xml").unlink()

    workdir = tmp_path / ".demagic"
    scan_project(app, workdir)

    led = Ledger.load(workdir)
    entry = led.get("prg:2")
    assert entry is not None
    assert entry.status == ArtifactStatus.PENDING

    pending = led.reconcile()
    assert "prg:2" in pending


# ---------------------------------------------------------------------------
# I2 — missing / duplicate ids must produce distinct artifact_ids
# ---------------------------------------------------------------------------

def test_datasources_missing_and_duplicate_ids(tmp_path: Path):
    """I2: DataSources.xml with a missing id and duplicate ids → 4 distinct artifact_ids."""
    xml = """\
<Application>
  <DataObjects>
    <DataObject id="" name="NoId" PhysicalName="tbl_noid" data_source="DB">
      <ObjectType val="T"/>
    </DataObject>
    <DataObject id="5" name="First" PhysicalName="tbl_first" data_source="DB">
      <ObjectType val="T"/>
    </DataObject>
    <DataObject id="5" name="Dup1" PhysicalName="tbl_dup1" data_source="DB">
      <ObjectType val="T"/>
    </DataObject>
    <DataObject id="5" name="Dup2" PhysicalName="tbl_dup2" data_source="DB">
      <ObjectType val="T"/>
    </DataObject>
  </DataObjects>
</Application>
"""
    ds_path = tmp_path / "DataSources.xml"
    ds_path.write_text(xml, encoding="utf-8")

    from demagic.parser.datasources import parse_datasources
    objs = parse_datasources(ds_path)

    assert len(objs) == 4
    aids = [o.artifact_id for o in objs]
    assert len(aids) == len(set(aids)), f"Duplicate artifact_ids: {aids}"
    # Empty id falls back to positional index
    assert aids[0] == "ds:idx0"
    # First occurrence of id=5 keeps clean form
    assert aids[1] == "ds:5"
    # Subsequent duplicates get #N suffix
    assert aids[2] == "ds:5#2"
    assert aids[3] == "ds:5#3"


# ---------------------------------------------------------------------------
# I3 — Prg-only projects (no DataSources.xml) must be discovered
# ---------------------------------------------------------------------------

def test_prg_only_project_discovered(tmp_path: Path):
    """I3: project with only Source/Prg_1.xml (no DataSources.xml) is discovered."""
    from demagic.parser.discovery import discover_projects

    src = tmp_path / "PrgOnlyApp" / "Source"
    src.mkdir(parents=True)
    (src / "Prg_1.xml").write_text("<Application/>", encoding="utf-8")

    projects = discover_projects(tmp_path)
    assert len(projects) == 1
    assert projects[0].name == "PrgOnlyApp"
    assert projects[0].prg_count == 1


# ---------------------------------------------------------------------------
# I4 — multiple candidates under project_root must raise ValueError
# ---------------------------------------------------------------------------

def test_multiple_projects_raises(tmp_path: Path):
    """I4: two copied projects under tmp → scan_project raises ValueError with both names."""
    shutil.copytree(FIXTURE_APP, tmp_path / "App_A")
    shutil.copytree(FIXTURE_APP, tmp_path / "App_B")

    workdir = tmp_path / ".demagic"
    with pytest.raises(ValueError, match="App_A"):
        scan_project(tmp_path, workdir)
