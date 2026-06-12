import ast
import json
from pathlib import Path

from demagic.ledger.ledger import ArtifactStatus, Ledger
from demagic.scaffold.project_gen import scaffold_project
from demagic.scan import scan_project


def test_scaffold_generates_project(sample_repo: Path, tmp_path: Path):
    workdir = tmp_path / ".demagic"
    out = tmp_path / "out"
    project = scan_project(sample_repo / "CustomerApp", workdir)
    scaffold_project(project, out, workdir)

    # generated app skeleton
    assert (out / "pyproject.toml").exists()
    assert (out / "app" / "models.py").exists()
    assert (out / "app" / "main.py").exists()
    ast.parse((out / "app" / "models.py").read_text(encoding="utf-8"))
    ast.parse((out / "app" / "main.py").read_text(encoding="utf-8"))

    # one service stub per program
    svc = (out / "app" / "services" / "prg_1.py").read_text(encoding="utf-8")
    assert "Customer List" in svc
    assert "DEMAGIC-PENDING" in svc  # marker replaced by translate stage

    # public online program -> route; batch program -> no route
    main = (out / "app" / "main.py").read_text(encoding="utf-8")
    assert "/custlist" in main

    # UI spec emitted per form, ledger marks the form converted
    spec = json.loads((out / "ui-specs" / "prg_1_form_0.json").read_text(encoding="utf-8"))
    assert spec["name"] == "Customer Browser"
    assert "btnRefresh" in spec["controls"]

    led = Ledger.load(workdir)
    assert led.get("prg:1/form:0").status == ArtifactStatus.CONVERTED
    # data objects are converted by scaffold; SPs get flagged
    assert led.get("ds:1").status == ArtifactStatus.CONVERTED
    assert led.get("ds:3").status == ArtifactStatus.FLAGGED
