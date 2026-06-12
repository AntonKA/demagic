from pathlib import Path

from pydantic_ai.models.test import TestModel

from demagic.scaffold.project_gen import scaffold_project
from demagic.scan import scan_project
from demagic.translate.runner import translate_all
from demagic.verify.checks import run_verification
from demagic.verify.report import write_report


def _full_pipeline(sample_repo: Path, tmp_path: Path):
    workdir = tmp_path / ".demagic"
    out = tmp_path / "out"
    project = scan_project(sample_repo / "CustomerApp", workdir)
    scaffold_project(project, out, workdir)
    model = TestModel(custom_output_args={
        "python_code": "def run() -> dict:\n    return {'ok': True}\n",
        "assumptions": [], "confidence": 0.9, "flags": [],
    })
    translate_all(project, workdir, out, model=model)
    return workdir, out


def test_verification_passes_after_full_pipeline(sample_repo: Path, tmp_path: Path):
    workdir, out = _full_pipeline(sample_repo, tmp_path)
    result = run_verification(workdir, out)
    assert result.pending == []          # 100% accounted for
    assert result.ruff_issues == 0
    assert result.converted > 0
    assert result.flagged >= 1           # the SP + the unknown element
    assert result.unparsed >= 1


def test_report_renders_markdown(sample_repo: Path, tmp_path: Path):
    workdir, out = _full_pipeline(sample_repo, tmp_path)
    result = run_verification(workdir, out)
    report_path = write_report(result, workdir)
    text = report_path.read_text(encoding="utf-8")
    assert "# demagic coverage report" in text
    assert "100%" in text or "accounted" in text
    assert "FutureWidget" in text        # unparsed items are surfaced loudly
