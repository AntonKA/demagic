"""Magic expression analysis against the function catalog.

Deterministic pre-pass: identifies which Magic functions an expression uses
and whether the catalog can map them. Unmapped functions become ledger flags
downstream - never silent failures.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

_CATALOG_PATH = Path(__file__).parent / "catalog.yaml"
_FN_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9_]*)\s*\(")


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, dict]:
    return yaml.safe_load(_CATALOG_PATH.read_text(encoding="utf-8"))


@dataclass
class ExpressionAnalysis:
    text: str
    functions: list[str] = field(default_factory=list)   # known, in catalog
    unmapped: list[str] = field(default_factory=list)    # not in catalog


def analyze_expression(text: str) -> ExpressionAnalysis:
    catalog = load_catalog()
    result = ExpressionAnalysis(text=text)
    for match in _FN_RE.finditer(text):
        name = match.group(1)
        bucket = result.functions if name in catalog else result.unmapped
        if name not in bucket:
            bucket.append(name)
    return result
