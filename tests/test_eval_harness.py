"""Guard the translate-stage eval harness so it can't silently rot.

These don't call any LLM - they check the scorer behaves, so the harness stays
trustworthy for prompt optimization.
"""
from __future__ import annotations

from evals.golden_set import golden_cases
from evals.translate_eval import score_translation


def test_golden_set_builds():
    cases = golden_cases()
    assert [c.name for c in cases] == ["crud_with_call", "batch_calc", "snippet_and_sp"]
    for c in cases:
        prg = next(p for p in c.project.programs if p.prog_id == c.prog_id)
        assert prg.artifact_id  # IR is well-formed


def test_scorer_separates_good_from_hollow():
    case = golden_cases()[0]  # crud_with_call
    good = {
        "python_code": (
            "from app.db import get_session\n"
            "from app.models import Customer\n\n"
            "def run() -> dict:\n"
            "    with get_session() as session:\n"
            "        for c in session.query(Customer).all():\n"
            "            c.name = c.name.strip()  # Magic: Trim(Name)\n"
            "            if not c.customer_id > 0:  # Magic: CustomerID>0\n"
            "                raise ValueError('Customer ID must be positive')\n"
            "    return {'ok': True}\n"
        ),
        "flags": [],
    }
    hollow = {"python_code": "def run():\n    pass\n", "flags": []}
    assert score_translation(case, good).score > score_translation(case, hollow).score


def test_async_run_is_not_scaffold_compatible():
    """The route calls run() synchronously; an async run() must not pass."""
    case = golden_cases()[0]
    async_run = {"python_code": "async def run() -> dict:\n    return {}\n", "flags": []}
    card = score_translation(case, async_run)
    assert card.checks["scaffold_run"].startswith("0/")


def test_run_with_required_args_is_not_scaffold_compatible():
    case = golden_cases()[0]
    bad = {"python_code": "def run(session, app) -> dict:\n    return {}\n", "flags": []}
    assert score_translation(case, bad).checks["scaffold_run"].startswith("0/")
