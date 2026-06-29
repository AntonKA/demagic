"""Objective scorer for translate-stage output.

Given a Magic program (as a GoldenCase) and a candidate TranslationResult
(python_code / assumptions / confidence / flags), produce a 0-100 score from
checks that need no LLM and no human judgement, so the optimization loop can
compare prompt variants deterministically and for free.

The checks encode what a *good* Magic->Python translation must do, and -
critically for demagic's honesty contract - that the un-translatable parts are
flagged rather than silently invented or dropped.

Run directly to self-test the scorer on a good vs a hollow translation:
    python -m evals.translate_eval
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

from evals.golden_set import GoldenCase

# Point budget per check; sums to 100.
_W_VALID = 30      # parses as Python at all
_W_RUN = 15        # exposes a scaffold-compatible run() entry point
_W_BODY = 15       # not a hollow stub
_W_TABLES = 15     # references the bound data objects
_W_EXPR = 15       # leaves a trace of each Magic expression
_W_FLAG = 10       # flags the un-translatable instead of hiding it

_HOLLOW = {"pass", "...", "raise NotImplementedError", "return None", "return {}"}


@dataclass
class ScoreCard:
    case: str
    score: int = 0
    checks: dict[str, str] = field(default_factory=dict)  # check -> "pts/max note"


def _scaffold_compatible_run(code: str) -> bool:
    """True if the module exposes `run()` the way the scaffold calls it.

    demagic's generated FastAPI route does `from app.services.prg_N import run`
    then `return run()` - synchronously, with no arguments. A run() that is
    async, or requires positional arguments (session, app, ...), will not wire
    into the generated app, so it is not a real translation even if it parses.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    for node in tree.body:  # top-level only
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "run":
            return False  # route calls it synchronously
        if isinstance(node, ast.FunctionDef) and node.name == "run":
            a = node.args
            required = [p for p in a.args if p.arg != "self"]
            # zero required positional args (defaults / *args / **kwargs are fine)
            n_defaulted = len(a.defaults)
            return (len(required) - n_defaulted) <= 0 and not a.posonlyargs
    return False


def _body_is_real(code: str) -> bool:
    """True if run()/module has substantive statements beyond a hollow stub."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    # collect statements inside run() if present, else module level
    run_fn = next((n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == "run"), None)
    body = run_fn.body if run_fn else tree.body
    meaningful = [s for s in body if not isinstance(s, ast.Expr)
                  or not isinstance(getattr(s, "value", None), ast.Constant)]
    # strip a lone docstring; require >=2 real statements OR one non-trivial call/assign
    real = [s for s in meaningful
            if not (isinstance(s, ast.Pass)
                    or (isinstance(s, ast.Raise)
                        and "NotImplementedError" in ast.dump(s)))]
    return len(real) >= 2


def score_translation(case: GoldenCase, result: dict) -> ScoreCard:
    code = (result or {}).get("python_code", "") or ""
    flags = (result or {}).get("flags", []) or []
    card = ScoreCard(case=case.name)
    low = code.lower()

    # 1. valid Python (hard gate for the structural checks below)
    try:
        ast.parse(code)
        valid = True
        card.score += _W_VALID
        card.checks["valid_python"] = f"{_W_VALID}/{_W_VALID} parses"
    except SyntaxError as exc:
        valid = False
        card.checks["valid_python"] = f"0/{_W_VALID} SyntaxError: {exc.msg}"

    # 2. scaffold-compatible run() (sync, zero required args - the route calls run())
    has_run = valid and _scaffold_compatible_run(code)
    card.score += _W_RUN if has_run else 0
    card.checks["scaffold_run"] = f"{_W_RUN if has_run else 0}/{_W_RUN}"

    # 3. real body, not a hollow stub
    real = valid and _body_is_real(code)
    card.score += _W_BODY if real else 0
    card.checks["real_body"] = f"{_W_BODY if real else 0}/{_W_BODY}"

    # 4. data-object coverage: references the generated model CLASS name (for
    #    tables) or the physical name (for SPs), as a whole word so the `Order`
    #    class isn't confused with an `order_id` variable. Case-sensitive,
    #    because the class is `Order`, not the loop var `order`.
    if case.expect_tables:
        hit = sum(1 for t in case.expect_tables
                  if re.search(rf"\b{re.escape(t)}\b", code))
        pts = round(_W_TABLES * hit / len(case.expect_tables))
        card.score += pts
        card.checks["table_coverage"] = f"{pts}/{_W_TABLES} {hit}/{len(case.expect_tables)}"

    # 5. expression trace (proportional)
    if case.expect_expr_traces:
        hit = sum(1 for tok in case.expect_expr_traces if tok.lower() in low)
        pts = round(_W_EXPR * hit / len(case.expect_expr_traces))
        card.score += pts
        card.checks["expr_trace"] = f"{pts}/{_W_EXPR} {hit}/{len(case.expect_expr_traces)}"

    # 6. flag honesty: un-translatable content must be surfaced, not hidden
    if case.must_flag:
        ok = len(flags) > 0
        card.score += _W_FLAG if ok else 0
        card.checks["flag_honesty"] = f"{_W_FLAG if ok else 0}/{_W_FLAG} flags={len(flags)}"
    else:
        # no penalty either way, but reward not crying wolf
        card.score += _W_FLAG
        card.checks["flag_honesty"] = f"{_W_FLAG}/{_W_FLAG} n/a"

    return card


def _selftest() -> None:
    from evals.golden_set import golden_cases
    case = golden_cases()[0]  # crud_with_call
    good = {
        "python_code": (
            "from app.db import get_session\n"
            "from app.models import Customer\n\n"
            "def run() -> dict:\n"
            "    with get_session() as session:\n"
            "        rows = session.query(Customer).all()\n"
            "        for c in rows:\n"
            "            c.name = c.name.strip()\n"
            "            if not c.customer_id > 0:\n"
            "                raise ValueError('Customer ID must be positive')\n"
            "        from app.services.prg_2 import run as run_2\n"
            "        run_2()\n"
            "    return {'count': len(rows)}\n"
        ),
        "flags": [],
    }
    hollow = {"python_code": "def run():\n    pass\n", "flags": []}
    g = score_translation(case, good).score
    h = score_translation(case, hollow).score
    print(f"good={g}  hollow={h}  (good must exceed hollow)")
    assert g > h, "scorer fails to separate good from hollow"
    assert g >= 85, f"good translation should score high, got {g}"
    print("selftest OK")


if __name__ == "__main__":
    _selftest()
