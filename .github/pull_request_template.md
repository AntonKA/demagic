## What this changes

<!-- One or two sentences. Link the issue it closes, e.g. "Closes #12". -->

## Checklist

- [ ] Tests pass (`uv run pytest -q`), lint and types clean (`uv run ruff check .`, `uv run ty check src`).
- [ ] New behaviour has a test.
- [ ] The change is focused; unrelated refactors go in a separate PR.
- [ ] No proprietary or customer data in code, tests or fixtures (fixtures stay synthetic, see `tests/fixtures/`).
- [ ] Anything new that produces artifacts registers them in the Coverage Ledger.
