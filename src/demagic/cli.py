"""demagic CLI - scan / analyze / scaffold / translate / verify / report / run-all."""
from __future__ import annotations

import os
from pathlib import Path

import typer

from demagic.analyze.graph import analyze_project
from demagic.scaffold.project_gen import scaffold_project
from demagic.scan import load_ir, scan_project
from demagic.verify.checks import run_verification
from demagic.verify.report import write_report

app = typer.Typer(help="Break the Magic spell - Magic xpa to Python converter.")

WorkdirOpt = typer.Option(Path(".demagic"), "--workdir", help="Pipeline state directory")


@app.command()
def scan(path: Path, workdir: Path = WorkdirOpt) -> None:
    """Discover and parse a Magic xpa project into IR + Coverage Ledger."""
    project = scan_project(path, workdir)
    typer.echo(f"Scanned {project.name}: {len(project.programs)} programs, "
               f"{len(project.data_objects)} data objects")


@app.command()
def analyze(workdir: Path = WorkdirOpt) -> None:
    """Call graph, translation order, complexity."""
    project = load_ir(workdir)
    analysis = analyze_project(project)
    typer.echo(f"Translation order: {analysis.translation_order}")


@app.command()
def scaffold(out: Path, workdir: Path = WorkdirOpt) -> None:
    """Generate the FastAPI + SQLModel target project and UI specs."""
    project = load_ir(workdir)
    scaffold_project(project, out, workdir)
    typer.echo(f"Scaffolded -> {out}")


@app.command()
def translate(
    out: Path,
    workdir: Path = WorkdirOpt,
    model: str | None = typer.Option(None, help="e.g. anthropic:claude-sonnet-4-5"),
    unit: str | None = typer.Option(None, help="Translate a single artifact id"),
) -> None:
    """LLM-translate program logic into the scaffolded services (resumable).

    Optional headless mode - needs the `[api]` extra. The default, no-API-key
    path is agent-driven: `demagic init` + `demagic pack` + your editor's agent.
    """
    try:
        from demagic.translate.runner import translate_all
    except ImportError:
        typer.echo(
            "Headless --model translation needs the API extra: "
            'pip install "demagic[anthropic]" (or [openai]/[api]).\n'
            "Or use the no-API-key agent flow: demagic init, then ask your editor's "
            "AI agent to convert the app (see demagic pack).", err=True)
        raise typer.Exit(2) from None
    model_name = model or os.environ.get("DEMAGIC_MODEL")
    if not model_name:
        typer.echo("Set --model or DEMAGIC_MODEL (e.g. anthropic:claude-sonnet-4-5)", err=True)
        raise typer.Exit(2)
    project = load_ir(workdir)
    results = translate_all(project, workdir, out, model=model_name, only_unit=unit)
    typer.echo(f"Translated {len(results)} programs")


@app.command()
def verify(out: Path, workdir: Path = WorkdirOpt) -> None:
    """Reconcile the ledger + static-check generated code. Exits 1 on gaps."""
    result = run_verification(workdir, out)
    report_path = write_report(result, workdir)
    typer.echo(f"Report: {report_path}")
    if result.pending:
        typer.echo(f"FAIL: {len(result.pending)} artifacts still pending", err=True)
        raise typer.Exit(1)
    typer.echo("OK: every artifact converted, flagged, or unparsed-and-surfaced")


@app.command()
def report(workdir: Path = WorkdirOpt) -> None:
    """Print the coverage report."""
    path = Path(workdir) / "coverage-report.md"
    typer.echo(path.read_text(encoding="utf-8") if path.exists()
               else "No report yet - run verify first.")


@app.command()
def pack(
    artifact: str | None = typer.Argument(None, help="Program id (e.g. prg:3 or 3); omit for all"),
    workdir: Path = WorkdirOpt,
) -> None:
    """Print translation rules + context pack(s) for an AI agent to translate.

    Use this when YOUR editor's agent is the translator (no API key): pipe the
    output to your agent, have it write run() bodies into the service stubs,
    then run `demagic verify` to reconcile.
    """
    from demagic.translate.context import SYSTEM_PROMPT, build_context_pack
    project = load_ir(workdir)
    programs = project.programs
    if artifact:
        pid = artifact.split(":")[-1]
        programs = [p for p in project.programs if p.prog_id == pid]
        if not programs:
            typer.echo(f"No program matching '{artifact}'", err=True)
            raise typer.Exit(2)
    typer.echo("# demagic translation rules\n")
    typer.echo(SYSTEM_PROMPT)
    for prg in programs:
        typer.echo("\n" + "=" * 64)
        typer.echo(f"# Write into: app/services/prg_{prg.prog_id}.py "
                   "(replace the DEMAGIC-PENDING stub)")
        typer.echo(build_context_pack(project, prg))


@app.command()
def init(
    path: Path = typer.Argument(Path("."), help="Project root to make agent-aware"),
    claude: bool = typer.Option(False, "--claude", help="Also write a Claude Code skill"),
    cursor: bool = typer.Option(False, "--cursor", help="Also write a Cursor rule"),
    copilot: bool = typer.Option(False, "--copilot", help="Also write Copilot instructions"),
    all_editors: bool = typer.Option(False, "--all", help="Write every supported format"),
) -> None:
    """Make your editor's AI agent demagic-aware (writes AGENTS.md by default)."""
    from demagic.agent_setup import init_project
    targets = {"agents"}
    if all_editors:
        targets |= {"claude", "cursor", "copilot"}
    if claude:
        targets.add("claude")
    if cursor:
        targets.add("cursor")
    if copilot:
        targets.add("copilot")
    for written in init_project(path, targets):
        typer.echo(f"wrote {written}")
    typer.echo('Done. Now tell your AI agent: "convert this Magic xpa app with demagic".')


@app.command(name="run-all")
def run_all(
    path: Path,
    out: Path = typer.Option(..., "--out"),
    workdir: Path = WorkdirOpt,
    model: str | None = typer.Option(None),
    skip_translate: bool = typer.Option(False, "--skip-translate"),
) -> None:
    """Full pipeline: scan -> analyze -> scaffold -> translate -> verify."""
    project = scan_project(path, workdir)
    analyze_project(project)
    scaffold_project(project, out, workdir)
    if not skip_translate:
        try:
            from demagic.translate.runner import translate_all
        except ImportError:
            typer.echo(
                "Headless translate needs the API extra (pip install "
                '"demagic[anthropic]"). For the no-key path, use --skip-translate '
                "then let your editor's AI agent fill the stubs (demagic init).",
                err=True)
            raise typer.Exit(2) from None
        model_name = model or os.environ.get("DEMAGIC_MODEL")
        if not model_name:
            typer.echo("Set --model or DEMAGIC_MODEL for translate", err=True)
            raise typer.Exit(2)
        translate_all(project, workdir, out, model=model_name)
    result = run_verification(workdir, out)
    write_report(result, workdir)
    if result.pending:
        typer.echo(f"FAIL: {len(result.pending)} artifacts pending", err=True)
        raise typer.Exit(1)
    typer.echo("Pipeline complete - see coverage report.")
