# demagic

**Break the Magic spell - LLM-powered Magic xpa → Python migration with a 100% coverage ledger.**

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://python.org)

---

## The problem

Magic xpa is a proprietary metadata 4GL (fourth-generation language). Application logic lives inside binary/XML project trees that no standard Python tooling can read. There is no open-source migration path: no transpiler, no AST bridge, no community converter. Shops that want to leave Magic xpa face a choice between rewriting everything from scratch or paying proprietary vendors for opaque tooling.

`demagic` is the open-source answer. It parses the Magic xpa Source XML format, builds a typed Intermediate Representation of your application, deterministically generates a FastAPI + SQLModel target project, and uses an LLM only where semantics genuinely require judgment - translating business logic in program task bodies. Everything that touches your codebase is auditable, reproducible, and covered.

---

## The Coverage Ledger guarantee

Every artifact `demagic` discovers - every data object, program, logic unit, expression, form, and menu entry - is registered in a **Coverage Ledger** before any output is written. The pipeline cannot exit successfully until every registered artifact is one of:

- **converted** - generated output exists and passed static checks
- **flagged** - converted with caveats requiring human review (reason recorded)
- **unparsed** - the parser hit unknown XML (surfaced loudly in the report)

If anything is left `pending`, the verify stage exits with code 1 and names every gap. You cannot accidentally ship an incomplete migration.

### Pipeline

```
Source XML
    |
    v
[scan]      Parse DataSources.xml, ProgramHeaders.xml, Prg_*.xml, Menus.xml
    |       -> Pydantic IR + Coverage Ledger (every artifact registered)
    v
[analyze]   Call graph, topological translation order, complexity, dead-code candidates
    |
    v
[scaffold]  Generate FastAPI app skeleton, SQLModel classes, service stubs, UI specs
    |       -> Ledger: data objects and forms marked converted/flagged
    v
[translate] LLM fills each service stub with real Python (resumable, dep-ordered)
    |       -> Ledger: programs/logic-units/expressions marked converted/flagged
    v
[verify]    Reconcile ledger (pending == 0?), ruff check on generated code
            -> coverage-report.md
```

---

## Quickstart

```bash
# Install (includes the Anthropic provider)
uv tool install "demagic[anthropic]"

# Set your LLM provider API key
export ANTHROPIC_API_KEY=sk-ant-...

# Run the full pipeline
demagic run-all ./MyApp --out ./myapp-py --model anthropic:claude-sonnet-4-5
```

The `--out` directory will contain a ready-to-run FastAPI project with SQLModel database models, one service module per Magic program, JSON UI specs for every form, and a `coverage-report.md` proving every artifact is accounted for.

### Alternative LLM providers

`demagic` uses [Pydantic AI](https://ai.pydantic.dev/) under the hood, so any supported provider works:

```bash
# OpenAI
pip install "demagic[openai]"
export OPENAI_API_KEY=sk-...
demagic run-all ./MyApp --out ./myapp-py --model openai:gpt-4o

# Local (Ollama)
demagic run-all ./MyApp --out ./myapp-py --model ollama:llama3.1

# Via environment variable (useful in CI)
export DEMAGIC_MODEL=anthropic:claude-sonnet-4-5
demagic run-all ./MyApp --out ./myapp-py
```

---

## Stage-by-stage commands

### `demagic scan <path>`

Parses the project at `<path>` into the Intermediate Representation and registers every artifact in the Coverage Ledger. Writes `ir.json` and `ledger.json` to the workdir (default `.demagic/`).

```bash
demagic scan ./MyApp --workdir .demagic
# Scanned MyApp: 47 programs, 23 data objects
```

### `demagic analyze`

Reads `ir.json` and prints the topological translation order (dependencies first) plus dead-code candidates.

```bash
demagic analyze
# Translation order: ['12', '7', '3', '1', ...]
```

### `demagic scaffold --out <dir>`

Generates the full FastAPI + SQLModel target project structure. Each program becomes a service stub with a `DEMAGIC-PENDING` marker; each online program with a public name gets a route; each form becomes a JSON UI spec.

```bash
demagic scaffold --out ./myapp-py
# Scaffolded -> myapp-py/
```

### `demagic translate --out <dir> --model <model>`

LLM-translates each service stub in dependency order. Resumable: already-converted programs are skipped. Invalid Python output from the LLM is rejected (not written), the stub is left intact, and the artifact is flagged in the ledger with the parse error.

```bash
demagic translate --out ./myapp-py --model anthropic:claude-sonnet-4-5

# Translate a single program for iteration
demagic translate --out ./myapp-py --model anthropic:claude-sonnet-4-5 --unit prg:7
```

### `demagic verify --out <dir>`

Reconciles the ledger (pending must be zero), runs `ruff check` on the generated `app/` directory, and writes `coverage-report.md`. Exits 1 if any artifacts are still pending.

```bash
demagic verify --out ./myapp-py
# Report: .demagic/coverage-report.md
# OK: every artifact converted, flagged, or unparsed-and-surfaced
```

### `demagic report`

Prints the last coverage report to stdout.

```bash
demagic report
```

### `demagic run-all <path> --out <dir>`

Runs the full pipeline in one command. Add `--skip-translate` to run scan + scaffold + verify offline (useful for CI dry-runs without an API key - the verify gate will fail loudly on pending programs, which is the intended behavior).

```bash
demagic run-all ./MyApp --out ./myapp-py --model anthropic:claude-sonnet-4-5
```

---

## What gets converted

| Artifact | Approach | Ledger outcome |
|---|---|---|
| Database tables and views | Deterministic SQLModel class generation from DataSources.xml | `converted` |
| Indexes | Mapped to SQLModel `Field(primary_key=True)` / index metadata | `converted` |
| Program logic (task bodies, logic units, expressions) | LLM translation with context pack (bound tables, call deps, Magic exprs) | `converted` or `flagged` with reasons |
| Online programs with public names | FastAPI route stubs with service import | `converted` |
| Forms and controls | JSON UI spec (framework-agnostic; implement in React/Vue/etc.) | `converted` |
| Menu structure | Included in UI spec bundle | `converted` |
| Stored procedures | Documented as comment stubs - cannot be expressed as SQLModel classes | `flagged` |
| Embedded C# snippets | Included in LLM context pack for porting; flagged for human review | `flagged` |
| Unrecognised XML elements | Counted in `unknown_tags`, registered as `unparsed` | `unparsed` (surfaced) |
| Source files without a dedicated parser | Registered as `unparsed` with file name | `unparsed` (surfaced) |

Nothing is silently dropped. If `demagic` cannot handle something, it says so.

---

## Extending the function catalog

Magic expression translation uses a seed catalog at `src/demagic/analyze/catalog.yaml`. Each entry maps a Magic function name to a Python format template:

```yaml
Trim:    {python: "{0}.strip()"}
Round:   {python: "round({0}, {1})"}
IF:      {python: "({1} if {0} else {2})"}
```

The `{0}`, `{1}`, ... slots correspond to the Magic call arguments. Any function not in the catalog is reported as `unmapped` in the expression analysis, flagged in the ledger, and included verbatim in the LLM context pack so the model still has the information to port it.

To add a mapping, open a PR against `catalog.yaml`. Unparsed ledger entries in your own migration output are ready-made candidates - each one is a one-liner contribution.

---

## Using with Claude Code (or any AI agent)

The repo ships a Claude Code skill at [.claude/skills/demagic/SKILL.md](.claude/skills/demagic/SKILL.md). Open this repo in Claude Code and ask things like *"what's inside the Magic app at C:\apps\MyApp?"* or *"convert this Magic project to Python but don't spend money on LLM calls yet"* — the skill teaches the agent the full pipeline, how to enumerate project copies, how to read the coverage report, and the troubleshooting table. To use it from another project, copy the `.claude/skills/demagic/` folder into that project (or your `~/.claude/skills/`).

---

## Contributing

Issues and PRs welcome. The best place to start:

1. Run `demagic scan` against a Magic xpa project you have access to.
2. Open `coverage-report.md` and look for `unparsed` entries.
3. Each `unknown element <Tag>` in the report is a parser gap. Open an issue with the XML snippet and we will add a parser for it.

The fixture corpus in `tests/fixtures/sample_repo/CustomerApp/` is a clean-room synthetic app (Customers + Orders) that covers the core XML schema. New parser features should include a fixture update and a test.

```bash
uv sync --all-extras
uv run pytest -q          # 49 tests
uv run ruff check .
uv run ty check src
```

---

## License

MIT. Copyright 2026 demagic contributors.
