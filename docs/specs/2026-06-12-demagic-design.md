# demagic — Design Spec

**Date:** 2026-06-12
**Status:** Approved (pending implementation plan)
**License:** Apache-2.0 (originally drafted as MIT; switched to Apache-2.0 at
publish for its explicit patent + trademark clauses, given the project sits
adjacent to a commercial vendor's ecosystem)
**Repo:** standalone public repo `demagic` (this directory)

## One-liner

Break the Magic spell — LLM-powered Magic xpa → Python migration with a 100% coverage guarantee.

## Problem

Magic xpa (and its ancestors eDeveloper / uniPaaS) is a metadata-driven 4GL: applications are
XML task trees with logic units, a proprietary expression language, data views bound directly
to tables, and form definitions — not textual source code. No open-source converter exists;
commercial vendors sell migration *services* with partial automation. Teams stuck on Magic
need a way off that is honest about what was converted and what was not.

## Goals

1. Convert Magic xpa applications (Source XML format, xpa 3.x/4.x) to a modern Python stack.
2. **100% functional coverage guarantee:** every artifact (program, task, logic unit,
   expression, data view, form, menu item) is either converted or explicitly flagged with a
   reason. Nothing is silently dropped — including XML the parser doesn't recognize.
3. LLM-driven semantic translation, deterministic everything else.
4. Generic: works on any Magic xpa repository layout, any project structure.
5. Publishable, community-extensible, star-worthy.

## Non-goals (v1)

- Older binary formats (eDeveloper `.mcf`) — XML export exists in Magic Studio; document the
  export path instead.
- Generating a working frontend. Forms become structured **UI specs**, not rendered UIs.
- Guaranteeing behavioral equivalence without human review — the tool guarantees *coverage*
  and *traceability*, and verifies what it can statically.

## Target stack (generated output)

| Concern | Choice | Why (2026) |
|---|---|---|
| API framework | FastAPI | Default greenfield choice; best LLM training coverage |
| Models/ORM | SQLModel (SQLAlchemy 2.x underneath) | One generated class per table = ORM model + Pydantic schema; less generated code to get wrong |
| Migrations | Alembic | Standard |
| Project tooling | uv + `pyproject.toml` (PEP 621) + `uv.lock` | Converted app runs with `uv run` out of the box |

## demagic's own stack

Python 3.12+ · uv (uv_build backend) · Typer CLI · Pydantic v2 (IR) ·
**Pydantic AI** (translate stage — provider-agnostic: Anthropic / OpenAI / Gemini / Ollama by
swapping the `Model`; schema-validated structured outputs) · ruff + ty (lint/type, both for
this repo and as the verify stage on generated code) · pytest.

## Architecture — 5-stage pipeline

All state lives in a `.demagic/` workdir next to the scanned source (ledger, IR cache,
run logs, cost tracking). Every stage is idempotent and resumable.

### 1. `scan` — deterministic parse → IR + ledger

- **Project discovery:** walk any directory tree; a project = directory containing
  `*.xpaproj`, or a `Source/` dir containing `DataSources.xml` / `Prg_*.xml`. Never assume
  layout (validated against a corpus with 4 different root layouts and 86 projects).
- **Duplicate fingerprinting:** Magic shops keep date-stamped copies of the same app.
  Fingerprint each project (program count + content hashes of Source XML) and group
  near-duplicates; recommend the newest/most complete copy for conversion. User overrides
  with `--project`.
- **Parse Source XML** into a typed Pydantic IR:
  `Comps.xml`, `DataSources.xml`, `DataSourcesIndex.xml`, `Helps.xml`, `Menus.xml`,
  `Models.xml`, `ProgramHeaders.xml`, `Prg_*.xml` (+ `Rights.xml`, `Events.xml` when present).
- **Coverage Ledger:** every artifact gets a stable unique ID and a status:
  `pending | converted | flagged | unparsed`. Unknown XML elements/attributes are recorded
  as `unparsed` entries with their XPath — this is what makes the 100% claim honest.
  Parser never crashes on unknown input.

### 2. `analyze` — deterministic analysis

- Call graph (program → subprogram calls), table-usage map, dead-code detection,
  complexity scoring per unit.
- Topological ordering: units are translated dependencies-first so the LLM always sees
  already-converted callees.
- Magic expression tokenizer backed by a **YAML function catalog** (`Trim`, `Date`,
  `CndRange`, …) mapping Magic functions → Python equivalents. Community-extensible;
  unmapped functions become ledger flags, not failures.

### 3. `scaffold` — deterministic code generation

- SQLModel classes from `DataSources.xml` (tables, columns, indexes, types).
- FastAPI app skeleton + route stubs per program (REST endpoints named from program names).
- **UI specs:** one JSON + Markdown spec per form (fields, layout tree, events, bound data)
  so any frontend can be rebuilt from them. Counts as covered in the ledger.
- Generated project skeleton: `pyproject.toml`, Alembic env, `tests/`, README mapping
  every generated file back to its Magic source IDs.

### 4. `translate` — LLM semantic translation (Pydantic AI)

- Per unit (task / logic unit), build a **context pack**: IR slice, data view, called
  subprograms (already translated), expression listing with catalog pre-translations.
- One Pydantic AI agent; structured output schema:
  `{python_code, assumptions[], confidence, flags[]}` — responses failing validation are
  retried, then flagged. Generated code must pass `ast.parse` before being written.
- Deterministic expression pre-translation where catalog rules exist; LLM handles control
  flow and semantics.
- Resumable: re-runs skip `converted` units. Per-run cost tracking. `--unit` to target one.
- Provider/model chosen via config/env (`DEMAGIC_MODEL=anthropic:claude-...`, etc.).
  API keys via env vars only.

### 5. `verify` — the 100% guarantee

- **Ledger reconciliation:** zero `pending` allowed; every artifact is
  `converted`, `flagged` (with reason), or `unparsed` (surfaced loudly).
- ruff + ty against the generated project.
- LLM critique pass per unit (second agent: "does this Python preserve the Magic
  semantics?") — failures downgrade the unit to `flagged`.
- **Coverage report** (Markdown + HTML): N% auto-converted, M flagged with reasons,
  per-program drill-down. This report is the README screenshot.

## CLI

```
demagic scan <path>          # discover + parse → IR + ledger
demagic analyze              # graphs, ordering, complexity
demagic scaffold             # models, API stubs, UI specs
demagic translate [--unit U] # LLM conversion, resumable
demagic verify               # ledger + static + semantic checks
demagic report               # coverage report
demagic run-all <path>       # full pipeline
```

## Repo layout

```
src/demagic/
  parser/      # XML → IR
  ir/          # Pydantic IR models
  ledger/      # Coverage Ledger
  analyze/     # call graph, ordering, expression tokenizer + catalog (YAML)
  scaffold/    # SQLModel/FastAPI/UI-spec generators (Jinja2 templates)
  translate/   # Pydantic AI agents + prompt templates
  verify/      # reconciliation, static checks, critique, report
  cli.py
tests/         # pytest; fixtures = synthetic clean-room Magic project
docs/          # this spec, architecture, contributing
examples/      # synthetic sample app + its converted output
```

## Error handling

- Parser: malformed/unknown XML → `unparsed` ledger entry with XPath, never a crash.
- Translate: provider errors retried with backoff; persistent failure → `flagged`.
- All LLM output schema-validated (Pydantic AI) + `ast.parse` gate before write.
- CLI exits non-zero if verify finds ledger gaps.

## Testing

- pytest; unit tests for parser/IR/ledger against synthetic fixtures.
- Golden-file tests for scaffold output.
- Mock Pydantic AI model (`TestModel`) for translate tests — no API calls in CI.
- **Private validation corpus:** real Magic codebases referenced via `DEMAGIC_CORPUS` env
  var for local validation only. Never committed, never in fixtures, no references in code,
  docs, or tests.

## Hard constraints

- **Clean-room:** zero proprietary XML, names, or data in the public repo. Test fixtures
  are synthetic.
- Credentials via env vars only.
- Apache-2.0 license. GitHub topics: `magic-xpa`, `legacy-migration`, `transpiler`, `llm`,
  `modernization`, `fastapi`.

## Success criteria (v1)

1. `demagic run-all` on the synthetic example completes all 5 stages with a clean ledger.
2. On a real-world corpus project: scan/analyze/scaffold complete deterministically;
   translate+verify produce a coverage report with zero unaccounted artifacts.
3. Generated example project passes `uv run ruff check` and `uv run ty check` and serves
   its FastAPI routes.
4. README with demo GIF + coverage report screenshot; installable via `uv tool install demagic`.
