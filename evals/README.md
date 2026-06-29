# Translate-stage evaluation harness

A small, deterministic, zero-API-cost harness for measuring and improving the
quality of the LLM translate stage (the prompt in
`src/demagic/translate/agent.py`).

The translate stage is the one part of demagic whose output quality depends on a
prompt rather than on deterministic code. This harness lets you change that
prompt and get an objective number back, without spending API tokens on every
tweak.

## Pieces

- **`golden_set.py`** - three synthetic Magic programs (built as IR, no real
  application content) covering the patterns seen in real xpa apps: CRUD with a
  subprogram call, a batch expression-table calc, and the hard case (a stored
  procedure plus an embedded C# snippet). Each carries objective expectations.
- **`translate_eval.py`** - scores one candidate translation 0-100 on checks
  that need no LLM and no human judgement:

  | Check | Pts | What it verifies |
  |---|---|---|
  | valid_python | 30 | output parses with `ast.parse` |
  | scaffold_run | 15 | exposes `def run()` - sync, zero args - the way the generated FastAPI route calls it |
  | real_body | 15 | not a hollow `pass` / `NotImplementedError` stub |
  | table_coverage | 15 | references the generated model **class** name (e.g. `Customer`), or the SP physical name |
  | expr_trace | 15 | leaves a trace of each Magic expression in the code |
  | flag_honesty | 10 | flags the un-translatable (SP / C# / unmapped fn) instead of hiding it |

- **`score_run.py`** - scores a JSON file of `{case_name: TranslationResult}`.

## Running it

Score a translator's output:

```bash
python -m evals.score_run path/to/results.json
```

Self-test the scorer (separates a good translation from a hollow stub):

```bash
python -m evals.translate_eval
```

## Optimization loop (how the current prompt was tuned)

1. Generate the three context packs with `build_context_pack`.
2. Hand them to any model (a cheap local model, or an agent) with the candidate
   system prompt; collect `{case: {python_code, flags, ...}}` as JSON.
3. `score_run` it. Inspect the per-check breakdown.
4. Fix the lowest-scoring check in the prompt, repeat.

The current `SYSTEM_PROMPT` reached 300/300 on this set. The biggest wins were
pinning the `run()` contract (sync, no args, class-name imports) so generated
code actually wires into the scaffold, and requiring `# Magic:` source comments
for traceability. If you add a golden case and the score drops, that gap is a
real prompt weakness worth fixing - contributions welcome.
