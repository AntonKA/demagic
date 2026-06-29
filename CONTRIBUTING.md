# Contributing to demagic

Thanks for helping people get off Magic xpa. Contributions of every size are
welcome — a one-line function mapping is as valuable as a new parser.

## Ways to contribute (easiest first)

1. **Add a Magic-function mapping.** Edit
   [`src/demagic/analyze/catalog.yaml`](src/demagic/analyze/catalog.yaml) to map a
   Magic built-in to its Python equivalent. Truly a one-line PR.
2. **Teach the parser a new tag.** Run `demagic scan` on a Magic app you have
   access to, open the coverage report, and pick an `unparsed` element. Add
   handling for it in `src/demagic/parser/`. (Please **don't** paste proprietary
   Magic XML into issues — the element/tag names are all we need.)
3. **Improve a generator or the translation rules.** The eval harness in
   [`evals/`](evals/) lets you measure translation quality objectively before and
   after a change.
4. **File an issue.** A coverage report showing unaccounted artifacts, a bug, or
   a rough edge in the agent workflow all help.

## Dev setup

demagic uses [uv](https://docs.astral.sh/uv/). Everything runs through it.

```bash
git clone https://github.com/AntonKA/demagic
cd demagic
uv sync --extra api          # --extra api so the optional-mode tests run too
```

Run the checks (CI runs exactly these):

```bash
uv run pytest -q             # all tests
uv run ruff check .          # lint
uv run ty check src          # type check
```

## Pull request checklist

- [ ] Tests pass (`uv run pytest -q`), lint and types clean.
- [ ] New behaviour has a test. We follow a test-first style — the existing
      tests are good examples.
- [ ] The change is focused; unrelated refactors go in a separate PR.
- [ ] No proprietary or customer data in code, tests, or fixtures. Test
      fixtures are synthetic (see `tests/fixtures/`).

## Design notes

- **The Coverage Ledger is the contract.** Anything demagic touches must end up
  `converted`, `flagged` (with a reason), or `unparsed` — never silently dropped.
  New code that produces artifacts should register and reconcile them.
- **Deterministic by default.** Only the optional `[api]` translate path calls an
  LLM. The core pipeline (scan/analyze/scaffold/verify) and the agent-driven flow
  (`pack`/`init`/reconcile) need no model and no API key — keep it that way.
- **Fixtures stay synthetic and small.** They are the fixed denominator the tests
  and eval harness measure against.

By contributing, you agree your contributions are licensed under the project's
[Apache License 2.0](LICENSE).
