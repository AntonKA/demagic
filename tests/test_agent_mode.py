"""Agent-driven (no-API-key) flow: init, pack, and reconcile-from-disk."""
from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from demagic.agent_setup import init_project
from demagic.cli import app
from demagic.ledger.ledger import ArtifactStatus, Ledger
from demagic.scaffold.project_gen import scaffold_project
from demagic.scan import scan_project
from demagic.verify.reconcile import reconcile_from_disk

runner = CliRunner()


# --- demagic init -----------------------------------------------------------

def test_init_writes_agents_md(tmp_path: Path):
    written = init_project(tmp_path, {"agents"})
    agents = tmp_path / "AGENTS.md"
    assert str(agents) in written
    text = agents.read_text(encoding="utf-8")
    assert "demagic" in text
    assert "DEMAGIC-PENDING" in text          # the workflow is described
    assert "def run() -> dict:" in text        # the tuned rules are embedded


def test_init_is_idempotent_and_preserves_existing(tmp_path: Path):
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# My project rules\n\nUse tabs.\n", encoding="utf-8")
    init_project(tmp_path, {"agents"})
    init_project(tmp_path, {"agents"})  # twice
    text = agents.read_text(encoding="utf-8")
    assert "Use tabs." in text                 # existing content kept
    assert text.count("<!-- demagic:start -->") == 1  # block not duplicated


def test_init_optional_editor_files(tmp_path: Path):
    written = init_project(tmp_path, {"agents", "cursor", "claude", "copilot"})
    assert (tmp_path / ".cursor" / "rules" / "demagic.mdc").exists()
    assert (tmp_path / ".claude" / "skills" / "demagic" / "SKILL.md").exists()
    assert (tmp_path / ".github" / "copilot-instructions.md").exists()
    assert len(written) == 4


# --- demagic pack -----------------------------------------------------------

def test_pack_emits_rules_and_context(sample_repo: Path, tmp_path: Path):
    workdir = tmp_path / ".demagic"
    scan_project(sample_repo / "CustomerApp", workdir)
    result = runner.invoke(app, ["pack", "1", "--workdir", str(workdir)])
    assert result.exit_code == 0
    assert "translation rules" in result.output
    assert "Customer List" in result.output     # the program's context
    assert "app/services/prg_1.py" in result.output


# --- reconcile-from-disk ----------------------------------------------------

def test_agent_edit_reconciles_to_converted(sample_repo: Path, tmp_path: Path):
    workdir, out = tmp_path / ".demagic", tmp_path / "out"
    project = scan_project(sample_repo / "CustomerApp", workdir)
    scaffold_project(project, out, workdir)

    # agent replaces the stub with real Python (marker removed)
    svc = out / "app" / "services" / "prg_1.py"
    svc.write_text('"""Customer List."""\n\n\ndef run() -> dict:\n    return {"ok": True}\n',
                   encoding="utf-8")

    n = reconcile_from_disk(workdir, out)
    assert n >= 1
    led = Ledger.load(workdir)
    assert led.get("prg:1").status == ArtifactStatus.CONVERTED
    assert led.get("prg:1/lu:0").status == ArtifactStatus.CONVERTED


def test_agent_flag_comment_reconciles_to_flagged(sample_repo: Path, tmp_path: Path):
    workdir, out = tmp_path / ".demagic", tmp_path / "out"
    project = scan_project(sample_repo / "CustomerApp", workdir)
    scaffold_project(project, out, workdir)

    svc = out / "app" / "services" / "prg_1.py"
    svc.write_text(
        "def run() -> dict:\n"
        "    # DEMAGIC-FLAG: external SOAP call needs the WSDL to verify\n"
        '    return {"ok": True}\n',
        encoding="utf-8")

    reconcile_from_disk(workdir, out)
    led = Ledger.load(workdir)
    entry = led.get("prg:1")
    assert entry.status == ArtifactStatus.FLAGGED
    assert "WSDL" in (entry.reason or "")


def test_untouched_stub_stays_pending(sample_repo: Path, tmp_path: Path):
    workdir, out = tmp_path / ".demagic", tmp_path / "out"
    project = scan_project(sample_repo / "CustomerApp", workdir)
    scaffold_project(project, out, workdir)
    # do not edit anything
    reconcile_from_disk(workdir, out)
    led = Ledger.load(workdir)
    assert led.get("prg:1").status == ArtifactStatus.PENDING
