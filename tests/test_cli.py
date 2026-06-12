from pathlib import Path

from typer.testing import CliRunner

from demagic.cli import app

runner = CliRunner()


def test_scan_command(sample_repo: Path, tmp_path: Path):
    result = runner.invoke(app, [
        "scan", str(sample_repo / "CustomerApp"),
        "--workdir", str(tmp_path / ".demagic")])
    assert result.exit_code == 0
    assert "CustomerApp" in result.output
    assert (tmp_path / ".demagic" / "ledger.json").exists()


def test_run_all_without_api_key_uses_explicit_failure(sample_repo: Path, tmp_path: Path):
    # run-all minus translate: scan+scaffold+verify must work offline
    result = runner.invoke(app, [
        "run-all", str(sample_repo / "CustomerApp"),
        "--out", str(tmp_path / "out"),
        "--workdir", str(tmp_path / ".demagic"),
        "--skip-translate"])
    assert result.exit_code == 1  # programs still pending -> verify gate fails loudly
    assert "pending" in result.output.lower()
