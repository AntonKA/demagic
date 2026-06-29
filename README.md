<div align="center">

<img src="assets/banner.png" alt="demagic - break the Magic spell" width="100%">

# demagic

### Drag your legacy Magic xpa apps into modern Python — and account for every line.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-22d3ee.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-818cf8.svg)](https://python.org)
[![Coverage Ledger](https://img.shields.io/badge/coverage-100%25_accounted-34d399.svg)](#the-coverage-ledger-the-whole-point)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-e879f9.svg)](#contributing)
[![Tests](https://img.shields.io/badge/tests-59_passing-22d3ee.svg)](tests/)

[Quickstart](#quickstart) · [What it converts](#what-actually-gets-converted) · [How it works](#how-it-works) · [Roadmap](#roadmap) · [Legal](#legal--trademarks)

</div>

---

## The problem nobody open-sourced a fix for

Thousands of businesses still run on **Magic xpa** (and its ancestors **uniPaaS** and **eDeveloper**) — a proprietary, metadata-driven 4GL where the application doesn't live in readable source files. It lives in XML project trees that no standard tool can parse, no IDE can refactor, and no LLM was trained to understand. The developers who knew it are retiring. The runtime licenses keep renewing.

When a shop finally decides to leave, they hit a wall: **rewrite everything by hand from a system nobody fully remembers, or pay a proprietary vendor for opaque, black-box "modernization."** There was no open-source path off Magic. No transpiler. No AST bridge. Nothing.

**`demagic` is that path.** It reads the Magic xpa Source XML, builds a typed model of your application, deterministically generates a modern **FastAPI + SQLModel** project, and calls an LLM *only* where real semantic judgment is needed — translating the business logic inside program tasks. Everything else is deterministic, reproducible, and auditable.

> Legacy modernization is usually sold as magic. This one shows its work.

---

## The Coverage Ledger (the whole point)

Most "AI migration" tools convert what they understand and quietly skip the rest — so you ship a system that's secretly full of holes. demagic refuses to do that.

Before it writes a single file, demagic registers **every artifact** it discovers — every data object, program, logic unit, expression, form, and menu entry — in a **Coverage Ledger**. The pipeline cannot exit successfully until each one is reconciled to exactly one of:

| Status | Meaning |
| --- | --- |
| ✅ **converted** | generated output exists and passed static checks (`ruff` + `ty`) |
| ⚠️ **flagged** | converted with caveats — a specific, recorded reason a human must review |
| 🔍 **unparsed** | the parser hit XML it doesn't model yet — surfaced loudly, never hidden |

If anything is left `pending`, **`verify` exits non-zero and names every gap.** You cannot accidentally ship an incomplete migration. The coverage report *is* the deliverable — it tells you precisely how much is done and exactly what's left, with a reason for every item.

That's the honesty other converters skip: **demagic is upfront about the 40% it can't fully automate, instead of pretending it did 100%.**

---

## What a conversion actually looks like

A Magic program that browses a data source, in the Source XML, becomes a clean SQLModel service — with the original Magic expressions preserved as comments so you can always trace back:

```python
# Service for Magic program #4 - translated by demagic.
"""Browse action items - list rows from the data source."""
from app.db import get_session
from app.models import Customer
from sqlmodel import select


def run() -> dict:
    with get_session() as session:
        # Magic: Trim(Name)
        rows = [c for c in session.exec(select(Customer)).all() if c.customer_id > 0]
    return {"count": len(rows), "items": rows}
```

Meanwhile a 70-logic-unit monster full of Win32 calls, raw SOAP, and embedded C# gets its data layer translated and **everything else flagged with reasons** — not silently mangled. That split, made explicit, is the product.

---

## Quickstart

```bash
# install (the [anthropic] extra ships the default model provider)
uv tool install "demagic[anthropic]"
export ANTHROPIC_API_KEY=...          # only the translate stage needs a key

# convert one project, end to end
demagic run-all ./MyMagicApp --out ./myapp-python --model anthropic:claude-sonnet-4-5
```

No API key yet? Run everything except the LLM step for free — it still produces the data model, API surface, UI specs, and a full coverage report:

```bash
demagic run-all ./MyMagicApp --out ./myapp-python --skip-translate
```

> Point demagic at **one** project folder (the one holding the `.xpaproj` or `Source/`). Other providers work too — `--model openai:gpt-5.2`, `--model ollama:qwen3`, or set `DEMAGIC_MODEL`.

---

## What actually gets converted

| Magic concept | Becomes | How |
| --- | --- | --- |
| Data sources / tables | SQLModel classes | deterministic |
| Programs / public tasks | FastAPI routes + service modules | deterministic scaffold |
| Task / record logic & expressions | Python in `run()` | **LLM**, validated + ledgered |
| Forms & menus | structured JSON UI specs | deterministic |
| Stored procedures, embedded C#, unmapped functions | **flagged** for human review | recorded with reasons |
| XML the parser doesn't know yet | **unparsed** ledger entries | surfaced as issues to file |

**Domain-agnostic by design.** Magic xpa powers line-of-business systems across finance, insurance, healthcare, manufacturing, retail, government, utilities, and logistics. demagic works from the Source XML *structure*, not any schema or industry — it converts an insurance policy engine the same way it converts a shop-floor scheduler. The bundled example (a simple customers-and-orders schema) is just a neutral illustration.

---

## How it works

Five stages. Only stage 4 spends tokens; the rest are pure, deterministic Python.

```
 scan ──▶ analyze ──▶ scaffold ──▶ translate ──▶ verify
  │          │           │            │            │
  XML →    call graph,  SQLModel +   LLM business  ledger reconcile
  typed IR  ordering,   FastAPI +    logic, with   + ruff + ty +
  + ledger  dead code   UI specs     ast.parse gate coverage report
```

`scan` parses every Magic Source file into a typed Intermediate Representation and registers each artifact. `analyze` builds the call graph and a dependency-first translation order. `scaffold` generates the runnable target project. `translate` ports the business logic (resumable — re-runs skip finished programs and track token usage). `verify` proves the ledger is complete and the generated code passes static checks.

Per-stage commands (`demagic scan|analyze|scaffold|translate|verify|report`) give you fine control; `run-all` does the whole thing.

---

## Extending

The Magic-function-to-Python mapping lives in [`src/demagic/analyze/catalog.yaml`](src/demagic/analyze/catalog.yaml) — adding a mapping is a one-line PR and the cheapest way to contribute. Any function not in the catalog is flagged, never silently guessed. Frequent `unparsed` tags in your coverage report are the parser's roadmap — each one is a ready-made issue.

---

## Roadmap

- [ ] LLM critique pass (a second model adversarially re-reviewing each translation)
- [ ] Dedicated parsers for `Models.xml`, `Comps.xml`, `Rights.xml`, `Events.xml`
- [ ] Alembic migration generation from indexes / foreign keys
- [ ] HTML coverage report + a generated frontend from the UI specs
- [ ] `bulk` mode across a repo of date-stamped project copies
- [ ] PyPI release

---

## Contributing

Issues and PRs welcome. The best on-ramp: run `demagic scan` against a Magic app you have access to, open the coverage report, and find an `unparsed` tag or an unmapped function. Each is a small, self-contained contribution. (Please don't paste proprietary Magic XML into issues — the element/tag names are all we need.)

---

## Legal & Trademarks

demagic is an **independent, community-built open-source project**. It is **not affiliated with, endorsed by, sponsored by, or connected to Magic Software Enterprises Ltd.** or any of its subsidiaries.

"Magic xpa", "uniPaaS", and "eDeveloper" are trademarks of Magic Software Enterprises Ltd.; "Python" is a trademark of the Python Software Foundation; all other marks belong to their respective owners. These names are used here **solely to describe what the tool does** (nominative fair use), not to imply any association.

demagic **does not include, embed, modify, decompile, or redistribute any Magic Software product, runtime, binary, or source code.** It operates only on the Source XML that *you* export from *your own licensed* Magic xpa application — your own application metadata, which you own. See [`NOTICE`](NOTICE) for full details.

---

## License

[Apache License 2.0](LICENSE) — permissive, with an explicit patent grant and trademark clause. Use it freely, including commercially.

<div align="center">

---

Built by **Anton** · [GitHub](https://github.com/AntonKA) · [X / Twitter](https://x.com/antonamosh) · [LinkedIn](https://www.linkedin.com/in/antonalemoush/)

If demagic saves you from a hand-rewrite, a ⭐ helps others find it.

</div>
