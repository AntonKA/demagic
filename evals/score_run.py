"""Score one translator run.

Reads a JSON file mapping case_name -> TranslationResult dict
({python_code, assumptions, confidence, flags}) and prints a scorecard per
case plus the total, so an optimization iteration can be compared to others.

    python -m evals.score_run <results.json>
"""
from __future__ import annotations

import json
import sys

from evals.golden_set import golden_cases
from evals.translate_eval import score_translation


def main(path: str) -> None:
    results = json.loads(open(path, encoding="utf-8").read())
    cases = {c.name: c for c in golden_cases()}
    total = 0
    for name, case in cases.items():
        card = score_translation(case, results.get(name, {}))
        total += card.score
        print(f"\n[{card.case}]  {card.score}/100")
        for check, note in card.checks.items():
            print(f"  {check:16} {note}")
    print(f"\n=== TOTAL {total}/{len(cases) * 100} "
          f"({round(100 * total / (len(cases) * 100))}%) ===")


if __name__ == "__main__":
    main(sys.argv[1])
