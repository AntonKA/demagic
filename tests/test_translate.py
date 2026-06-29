from pathlib import Path

from pydantic_ai.models.test import TestModel

from demagic.ledger.ledger import ArtifactStatus, Ledger
from demagic.scaffold.project_gen import scaffold_project
from demagic.scan import scan_project
from demagic.translate.agent import build_context_pack
from demagic.translate.runner import translate_all


def _prepared(sample_repo: Path, tmp_path: Path):
    workdir = tmp_path / ".demagic"
    out = tmp_path / "out"
    project = scan_project(sample_repo / "CustomerApp", workdir)
    scaffold_project(project, out, workdir)
    return project, workdir, out


def test_context_pack_contains_everything(sample_repo: Path, tmp_path: Path):
    project, workdir, out = _prepared(sample_repo, tmp_path)
    pack = build_context_pack(project, project.programs[0])
    assert "Customer List" in pack
    assert "Trim(Name)" in pack
    assert "tbl_Customer" in pack          # bound table
    assert "calls program 2" in pack       # dependency info


def test_translate_all_with_test_model(sample_repo: Path, tmp_path: Path):
    project, workdir, out = _prepared(sample_repo, tmp_path)
    model = TestModel(custom_output_args={
        "python_code": "def run() -> dict:\n    return {'ok': True}\n",
        "assumptions": ["demo"], "confidence": 0.9, "flags": [],
    })
    results = translate_all(project, workdir, out, model=model)
    assert set(results) == {"1", "2"}

    svc = (out / "app" / "services" / "prg_1.py").read_text(encoding="utf-8")
    assert "return {'ok': True}" in svc
    assert "DEMAGIC-PENDING" not in svc

    led = Ledger.load(workdir)
    assert led.get("prg:1").status == ArtifactStatus.CONVERTED
    assert led.get("prg:1/lu:0").status == ArtifactStatus.CONVERTED

    # cost tracking persisted
    assert (workdir / "usage.json").exists()


def test_module_provenance_is_comments_keeps_imports_at_top(sample_repo: Path, tmp_path: Path):
    """Translated code that starts with its own docstring + import must stay
    E402-clean: demagic's provenance header is comments, not a second docstring."""
    project, workdir, out = _prepared(sample_repo, tmp_path)
    model = TestModel(custom_output_args={
        "python_code": '"""Real module docstring."""\nimport os\n\n\ndef run() -> dict:\n'
                       "    return {'cwd': os.getcwd()}\n",
        "assumptions": ["a"], "confidence": 0.9, "flags": [],
    })
    translate_all(project, workdir, out, model=model)
    svc = (out / "app" / "services" / "prg_1.py").read_text(encoding="utf-8")

    # provenance header is comments
    assert svc.splitlines()[0].startswith("# Service for Magic program")
    # the import is not pushed below a stray statement (E402 trigger)
    import ast
    tree = ast.parse(svc)
    first_import = next(i for i, n in enumerate(tree.body)
                        if isinstance(n, (ast.Import, ast.ImportFrom)))
    before = tree.body[:first_import]
    # only a single module docstring may precede imports, nothing else
    assert all(isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)
               for n in before)


def test_invalid_python_is_flagged_not_written(sample_repo: Path, tmp_path: Path):
    project, workdir, out = _prepared(sample_repo, tmp_path)
    model = TestModel(custom_output_args={
        "python_code": "def run(:\n  broken", "assumptions": [],
        "confidence": 0.2, "flags": [],
    })
    translate_all(project, workdir, out, model=model)
    led = Ledger.load(workdir)
    assert led.get("prg:1").status == ArtifactStatus.FLAGGED
    assert led.get("prg:1/lu:0").status == ArtifactStatus.FLAGGED
    svc = (out / "app" / "services" / "prg_1.py").read_text(encoding="utf-8")
    assert "DEMAGIC-PENDING" in svc  # stub untouched
