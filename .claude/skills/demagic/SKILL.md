---
name: demagic
description: >-
  Convert Magic xpa (uniPaaS / eDeveloper) applications to modern Python using
  the demagic CLI. Use this skill whenever the user mentions Magic xpa, uniPaaS,
  eDeveloper, .xpaproj files, Prg_*.xml / DataSources.xml / ProgramHeaders.xml
  source exports, "Magic 4GL", migrating or modernizing a Magic application,
  converting Magic code to Python/FastAPI, or asks what is inside a Magic
  project — even if they don't name the demagic tool. Also use it to interpret
  demagic coverage reports, ledgers, and translate-stage failures.
---

# demagic — Magic xpa → Python conversion

demagic converts Magic xpa applications (their XML Source export) into a
FastAPI + SQLModel Python project. It is **domain-agnostic** — it works from the
Source XML structure, not any schema or industry, so it handles a Magic app from
any field (finance, insurance, healthcare, manufacturing, retail, government,
logistics) identically. It is a 5-stage pipeline with one core guarantee: a
**Coverage Ledger** tracks every artifact (program, logic unit, expression,
form, menu, table), and each one must end the run as `converted`, `flagged`
(with a reason), or `unparsed` (surfaced loudly). Nothing is ever silently
dropped — the verify stage exits non-zero if anything is unaccounted.

Stages: `scan` (XML → typed IR + ledger) → `analyze` (call graph,
dependency-first order, dead code) → `scaffold` (SQLModel models, FastAPI
stubs, UI specs) → `translate` (LLM, resumable) → `verify` (ledger
reconciliation + static checks + coverage report).

## Setup

```bash
uv tool install "demagic[anthropic]"        # or [openai]
export ANTHROPIC_API_KEY=...                # only needed for translate
```

Working from this repo instead: `uv sync --all-extras`, then prefix commands
with `uv run`.

## Core workflow

Always point demagic at **one project directory** (the folder holding the
`.xpaproj` or the `Source/` dir), not at a repository of many projects —
Magic shops keep dozens of date-stamped copies, and `scan` deliberately
refuses to guess between them (it raises an error listing every candidate
with a content fingerprint; duplicate fingerprints mean identical copies).

To enumerate candidates in a big tree first:

```bash
uv run python -c "
from demagic.parser.discovery import discover_projects
from pathlib import Path
for p in discover_projects(Path(r'<repo-root>')):
    print(p.fingerprint, f'{p.prg_count:>5} programs', p.name, p.root)"
```

Each result is a `DiscoveredProject` with `name`, `root` (path), `source_dir`,
`prg_count`, and `fingerprint`. Equal fingerprints = identical copies; to pick
the newest among differing copies, sort by the Source dir's mtime
(`max(f.stat().st_mtime for f in p.source_dir.glob('*.xml'))`). Then run:

```bash
demagic run-all <project-dir> --out <target-dir> --workdir <state-dir> \
    --model anthropic:claude-sonnet-4-5
```

Run the offline stages first when the user just wants to understand an app or
check conversion feasibility — no API key needed, seconds even on
multi-thousand-program projects:

```bash
demagic run-all <project-dir> --out <target-dir> --workdir <state-dir> --skip-translate
```

Expect **exit code 1** with `N artifacts pending` in this mode: programs
await translation, and the verify gate is honest about it. That is success
for an offline run. Exit code 2 means no model was configured for translate.

## Stage-by-stage (when you need finer control)

| Command | What it does | When to run alone |
|---|---|---|
| `demagic scan <dir> --workdir W` | Parse XML → `W/ir.json` + `W/ledger.json` | Inventory questions ("what's in this app?") |
| `demagic analyze --workdir W` | Call graph, translation order | Inspect dependencies / dead code |
| `demagic scaffold <out> --workdir W` | Models, API stubs, `ui-specs/*.json` | Preview generated structure |
| `demagic translate <out> --workdir W --model M` | LLM translation, resumable | Re-run after failures; `--unit prg:N` for one program |
| `demagic verify <out> --workdir W` | Reconcile ledger + ruff/ty + report | After any stage, to see where things stand |
| `demagic report --workdir W` | Print `coverage-report.md` | Quick status |
| `demagic run-all <dir> --out O --workdir W --skip-translate` | Full offline pipeline | Feasibility check, no API key |

For "what's inside this app?" questions, read `W/ir.json` directly — it is a
`ProjectIR` with `data_objects` (tables/views/SPs with columns and the
`connection` alias), `program_headers` (id, description, task type O/B/C/R,
public name), `programs` (logic units, expressions, calls, forms, messages,
C# `snippets`), and `menus`. Aggregating those fields answers most inventory
questions without any extra tooling.

`translate` is resumable: re-running skips programs already `converted`, so
interrupting a long run costs nothing. Token usage accumulates in
`W/usage.json`. Model strings follow Pydantic AI naming —
`anthropic:claude-sonnet-4-5`, `openai:gpt-5.2`, `ollama:qwen3` — set via
`--model` or the `DEMAGIC_MODEL` env var.

## Reading the coverage report

`W/coverage-report.md` is the deliverable that proves (or disproves) the
conversion. Interpret its sections for the user:

- **Pending (MUST be 0)** — artifacts no stage has handled. Non-zero after a
  full run means the pipeline is incomplete (usually translate was skipped or
  interrupted). Never present a non-zero-pending run as a finished conversion.
- **Flagged for review** — converted-with-doubts or deliberately not
  auto-convertible. On offline runs this list is dominated by data-layer
  findings (tables without a unique index, duplicate physical names, stored
  procedures); after translate it also includes LLM output that failed
  validation and expressions using unmapped Magic functions. Each entry
  carries a reason; these are the human worklist.
- **Unparsed XML** — elements or Source files the parsers don't understand
  yet. Entries are per (file, tag) pair, so one unknown tag appearing in
  every program inflates the count — the distinct tag names (visible in the
  entries) are the real measure. These are parser gaps in demagic itself, not
  problems with the user's app — encourage opening a GitHub issue with the
  tag names (no app content needed, just the element names).

Per-id listings in the report are capped at 100 entries per section (counts
stay exact); the full detail is always in `W/ledger.json`.

## Extending

- **Magic function catalog:** `src/demagic/analyze/catalog.yaml` maps Magic
  functions (`Trim`, `Round`, …) to Python. Unmapped functions don't fail —
  they're flagged — but adding mappings improves translation quality. PRs to
  the catalog are the cheapest way to contribute.
- **Unparsed tags:** frequent `unparsed` entries (form property elements,
  logic-line modifiers) are the parser roadmap; each distinct tag is a
  ready-made issue.

## Troubleshooting

| Symptom | Meaning | Action |
|---|---|---|
| `ValueError: multiple projects found` | Pointed at a tree of project copies | Point at ONE project dir (use the discovery snippet above) |
| Exit 1, `N artifacts pending` | Translate skipped/incomplete | Run `translate`, or accept for offline analysis |
| Exit 2 from translate/run-all | No model configured | Set `--model` or `DEMAGIC_MODEL` + provider API key |
| `ty issues: n/a` in report | ty not installed in the env | Optional check; `uv tool install ty` if wanted |
| Translation flagged `failed ast.parse` | LLM emitted invalid Python | Re-run `translate` (resumes only failures); try a stronger model |
| Huge `ledger.json` (100+ MB) | Normal for 1000+ program apps | Nothing to do; saves are batched |

## Safety rails

- `scan`/`analyze`/`scaffold`/`verify` are read-only with respect to the
  Magic source — they never modify the input directory.
- Never copy a user's proprietary Magic XML into demagic's test fixtures or
  issues; report only element/tag names.
- Generated code is a starting point: flagged artifacts and UI specs need
  human follow-up, and the report says exactly which ones.
