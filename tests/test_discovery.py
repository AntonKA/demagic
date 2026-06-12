import shutil
from pathlib import Path

from demagic.parser.discovery import discover_projects


def test_discovers_project_by_marker(sample_repo: Path):
    projects = discover_projects(sample_repo)
    assert len(projects) == 1
    p = projects[0]
    assert p.name == "CustomerApp"
    assert p.source_dir.name == "Source"
    assert p.prg_count == 2
    assert len(p.fingerprint) == 16


def test_duplicate_projects_share_fingerprint(sample_repo: Path, tmp_path: Path):
    # Simulate the date-stamped-copies pattern common in Magic shops
    shutil.copytree(sample_repo / "CustomerApp", tmp_path / "App010126")
    shutil.copytree(sample_repo / "CustomerApp", tmp_path / "App150326")
    projects = discover_projects(tmp_path)
    assert len(projects) == 2
    assert projects[0].fingerprint == projects[1].fingerprint


def test_no_projects_in_empty_tree(tmp_path: Path):
    assert discover_projects(tmp_path) == []


def test_discovers_prg_only_project(tmp_path: Path):
    """I3: project with only Source/Prg_1.xml (no DataSources.xml) is discovered."""
    src = tmp_path / "PrgOnlyApp" / "Source"
    src.mkdir(parents=True)
    (src / "Prg_1.xml").write_text("<Application/>", encoding="utf-8")

    projects = discover_projects(tmp_path)
    assert len(projects) == 1
    assert projects[0].name == "PrgOnlyApp"
    assert projects[0].prg_count == 1
