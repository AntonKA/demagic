"""`demagic init` - make a project's AI coding agent demagic-aware.

Writes agent instructions so that whatever editor the user runs (Claude Code,
Cursor, Copilot, Aider, Codex, Cline, Zed...) knows how to drive demagic and
do the translation with its OWN model and tokens - no separate API key.

AGENTS.md is the default (the cross-agent standard); editor-specific files are
opt-in. Writes are idempotent: the demagic block is delimited by markers and
replaced in place on re-run, so existing instructions are never clobbered.
"""
from __future__ import annotations

from pathlib import Path

from demagic.translate.context import SYSTEM_PROMPT

START = "<!-- demagic:start -->"
END = "<!-- demagic:end -->"


def _workflow() -> str:
    return f"""\
## Working with demagic (Magic xpa -> Python)

[demagic](https://github.com/AntonKA/demagic) converts a Magic xpa application
(its Source XML export) into a FastAPI + SQLModel Python project. A **Coverage
Ledger** guarantees every artifact ends up converted, flagged (with a reason),
or unparsed - nothing is silently dropped.

You (the AI agent) are the translation engine. The deterministic stages are
free; you do the business-logic translation using your own model, so the user
spends no extra API tokens.

### The loop

0. **Make sure demagic is installed** (no API key needed): if the `demagic`
   command is missing, run `uv tool install demagic` (or `pipx install demagic`,
   or `pip install demagic`).

1. **Scaffold (free, no key):**
   `demagic run-all <magic-project-dir> --out <out-dir> --workdir .demagic --skip-translate`
   This generates `<out-dir>/app/` (SQLModel models, FastAPI routes) and one
   stub per program at `<out-dir>/app/services/prg_<id>.py`. Each stub carries a
   `DEMAGIC-PENDING` marker and a comment summary of the Magic logic. Expect
   exit code 1 ("N artifacts pending") - that is normal here.

2. **Get context:** `demagic pack` prints the translation rules plus a context
   pack for every pending program (or `demagic pack <id>` for one). Read it.

3. **Translate:** for each `prg_<id>.py` stub, replace the body with real Python
   following the rules below. Remove the `DEMAGIC-PENDING` marker. If something
   is genuinely untranslatable, still write your best effort AND leave a
   `# DEMAGIC-FLAG: <reason>` comment in the file - never silently drop behaviour.

4. **Close the ledger:** `demagic verify <out-dir> --workdir .demagic`
   reconciles your edited files (marker gone + valid Python => converted; a
   `# DEMAGIC-FLAG:` line => flagged) and exits 0 once everything is accounted
   for. `demagic report --workdir .demagic` shows the coverage summary.

### Translation rules (follow exactly)

{SYSTEM_PROMPT}

### Notes

- Point demagic at ONE project directory (the folder with the `.xpaproj` or
  `Source/`). It refuses a tree of many copies.
- A data object marked `(S)` in a pack is a stored procedure; `[unmapped fns:..]`
  means no known mapping - keep intent, flag it, don't invent behaviour.
- Never paste proprietary Magic XML into public issues - tag names are enough.
"""


def _agents_md() -> str:
    return f"# AGENTS.md\n\n{START}\n{_workflow()}{END}\n"


def _cursor_mdc() -> str:
    return (
        "---\n"
        "description: Convert Magic xpa applications to Python with demagic\n"
        "alwaysApply: false\n"
        "---\n\n"
        f"{_workflow()}"
    )


def _claude_skill() -> str:
    return (
        "---\n"
        "name: demagic\n"
        "description: >-\n"
        "  Convert Magic xpa / uniPaaS / eDeveloper applications to Python with the\n"
        "  demagic CLI. Use when the user mentions Magic xpa, .xpaproj, Prg_*.xml /\n"
        "  DataSources.xml exports, or migrating a Magic app.\n"
        "---\n\n"
        f"{_workflow()}"
    )


def _copilot_md() -> str:
    return f"{START}\n{_workflow()}{END}\n"


def _upsert_block(path: Path, block: str) -> None:
    """Insert or replace the demagic marker block in an existing file."""
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if START in existing and END in existing:
        head, _, rest = existing.partition(START)
        _, _, tail = rest.partition(END)
        new = f"{head}{block}{tail}"
    elif existing.strip():
        new = f"{existing.rstrip()}\n\n{block}\n"
    else:
        new = block if block.endswith("\n") else block + "\n"
    path.write_text(new, encoding="utf-8")


def init_project(root: Path, targets: set[str]) -> list[str]:
    """Write the requested agent instruction files under *root*. Returns paths."""
    root = Path(root)
    written: list[str] = []

    if "agents" in targets:
        p = root / "AGENTS.md"
        block = f"{START}\n{_workflow()}{END}\n"
        _upsert_block(p, block if p.exists() else _agents_md())
        written.append(str(p))

    if "cursor" in targets:
        p = root / ".cursor" / "rules" / "demagic.mdc"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_cursor_mdc(), encoding="utf-8")
        written.append(str(p))

    if "claude" in targets:
        p = root / ".claude" / "skills" / "demagic" / "SKILL.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_claude_skill(), encoding="utf-8")
        written.append(str(p))

    if "copilot" in targets:
        p = root / ".github" / "copilot-instructions.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        _upsert_block(p, _copilot_md())
        written.append(str(p))

    return written
