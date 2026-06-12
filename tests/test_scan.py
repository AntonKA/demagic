from pathlib import Path

from demagic.ledger.ledger import ArtifactStatus, Ledger
from demagic.parser.menus import parse_menus
from demagic.scan import scan_project


def test_parse_menus(sample_source: Path):
    menus = parse_menus(sample_source / "Menus.xml")
    assert menus[0].name == "Customers"
    assert menus[0].program == "1"
    assert menus[1].children[0].name == "Order Totals"


def test_scan_builds_ir_and_ledger(sample_repo: Path, tmp_path: Path):
    workdir = tmp_path / ".demagic"
    project = scan_project(sample_repo / "CustomerApp", workdir)

    assert project.name == "CustomerApp"
    assert len(project.data_objects) == 3
    assert len(project.program_headers) == 2
    assert len(project.programs) == 2
    assert len(project.menus) == 2

    led = Ledger.load(workdir)
    kinds = {e.kind for e in led.all_entries()}
    assert {"project", "data_object", "program", "logic_unit",
            "expression", "form", "menu", "unparsed_xml"} <= kinds

    # The deliberate unknown element must be ledgered as unparsed
    unparsed = [e for e in led.all_entries() if e.status == ArtifactStatus.UNPARSED]
    assert any("FutureWidget" in (e.reason or "") for e in unparsed)

    # IR is persisted for later stages
    assert (workdir / "ir.json").exists()
