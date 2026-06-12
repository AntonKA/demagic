"""Generate SQLModel classes from DataObjectIR.

One class per table/view. Stored procedures cannot be expressed as SQLModel
classes - they are emitted as documented stubs and flagged in the ledger by
the scaffold stage.
"""
from __future__ import annotations

import keyword
import re
from typing import NamedTuple

from demagic.ir.models import DataObjectIR, magic_type_to_python

_PY_IMPORTS = {
    "Decimal": "from decimal import Decimal",
    "date": "from datetime import date",
    "time": "from datetime import time",
}


def _safe_identifier(name: str, fallback: str) -> str:
    """Return a valid Python identifier derived from *name*.

    Rules applied in order:
    1. Replace all non-alphanumeric/underscore runs with ``_``.
    2. Strip leading/trailing underscores.
    3. If empty after stripping, return *fallback*.
    4. Prepend ``n`` if the first character is a digit.
    5. Append ``_`` if the result is a Python keyword (case-insensitive check
       covers ``class``, ``import``, ``return``, etc.).
    """
    s = re.sub(r"[^0-9A-Za-z_]+", "_", name).strip("_")
    if not s:
        return fallback
    if s[0].isdigit():
        s = f"n{s}"
    if keyword.iskeyword(s.lower()):
        s = f"{s}_"
    return s


def _class_name(magic_name: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z]+", " ", magic_name).title().replace(" ", "")
    # De-pluralize: strip trailing 's' only when len > 3 and not ending in 'ss'/'us'
    if len(cleaned) > 3 and cleaned.endswith("s") and not cleaned.endswith(("ss", "us")):
        singular = cleaned[:-1]
    else:
        singular = cleaned
    return _safe_identifier(singular, "Unnamed")


def _field_name(col_name: str, index: int) -> str:
    s = re.sub(r"[^0-9A-Za-z]+", "_", col_name)
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", s).lower()
    raw = re.sub(r"_+", "_", s).strip("_")
    return _safe_identifier(raw, f"col_{index}")


class ModelsResult(NamedTuple):
    code: str
    converted: list[str]
    flagged: dict[str, str]


def generate_models(objects: list[DataObjectIR]) -> ModelsResult:
    lines: list[str] = []
    needed_imports: set[str] = set()
    bodies: list[str] = []

    converted: list[str] = []
    flagged: dict[str, str] = {}

    # Track used class names and physical names to detect collisions
    used_class_names: dict[str, int] = {}
    seen_physical_names: set[str] = set()

    for obj in objects:
        if obj.object_type == "S" or obj.sp_type:
            bodies.append(
                f"# FLAGGED: stored procedure {obj.physical_name} "
                f"({obj.sp_params} params) - port manually or via translate stage.\n")
            flagged[obj.artifact_id] = (
                f"stored procedure {obj.physical_name} - not expressible as SQLModel"
            )
            continue

        # Duplicate physical name -> skip with comment
        if obj.physical_name in seen_physical_names:
            bodies.append(
                f"# FLAGGED: duplicate physical name {obj.physical_name} "
                f"(artifact {obj.artifact_id}) - only the first occurrence is emitted.\n"
            )
            flagged[obj.artifact_id] = f"duplicate physical name {obj.physical_name}"
            continue
        seen_physical_names.add(obj.physical_name)

        # Deduplicate class names
        base_cls = _class_name(obj.magic_name or obj.physical_name)
        if base_cls in used_class_names:
            used_class_names[base_cls] += 1
            cls = f"{base_cls}{used_class_names[base_cls]}"
        else:
            used_class_names[base_cls] = 1
            cls = base_cls

        # Determine PK columns: prefer index whose name contains PK/primary;
        # fall back to the first unique index.
        pk_index = None
        for idx in obj.indexes:
            if idx.unique:
                name_lower = (idx.name or "").lower()
                if "pk" in name_lower or "primary" in name_lower:
                    pk_index = idx
                    break
        if pk_index is None:
            for idx in obj.indexes:
                if idx.unique:
                    pk_index = idx
                    break

        pk_cols: set[str] = set(pk_index.columns) if pk_index else set()

        has_pk = bool(pk_cols)
        body = [f"class {cls}(SQLModel, table=True):",
                f'    __tablename__ = "{obj.physical_name}"',
                ""]

        if not has_pk:
            body.insert(
                2,
                "    # FLAGGED: no unique index in Magic source - "
                "define a primary key before use",
            )
            flagged[obj.artifact_id] = (
                f"table {obj.physical_name} has no unique index; primary key undefined"
            )

        for i, col in enumerate(obj.columns):
            py_type = magic_type_to_python(col.magic_type)
            if py_type in _PY_IMPORTS:
                needed_imports.add(_PY_IMPORTS[py_type])
            fname = _field_name(col.db_name or col.name, i)
            if col.name in pk_cols:
                body.append(
                    f"    {fname}: {py_type} | None = Field(default=None, primary_key=True)"
                )
            else:
                body.append(f"    {fname}: {py_type} | None = None")

        bodies.append("\n".join(body) + "\n")
        if obj.artifact_id not in flagged:
            converted.append(obj.artifact_id)

    lines.append('"""Database models generated by demagic from DataSources.xml."""')
    lines.extend(sorted(needed_imports))
    # Emit sqlmodel import when at least one class body was generated
    # (includes flagged-but-generated classes such as tables with no PK).
    # Omit entirely when only SP stubs or nothing was generated (avoids F401).
    has_class = any("(SQLModel, table=True)" in b for b in bodies)
    if has_class:
        field_needed = any("Field(default=None, primary_key=True)" in b for b in bodies)
        if field_needed:
            lines.append("from sqlmodel import Field, SQLModel")
        else:
            lines.append("from sqlmodel import SQLModel")
    lines.append("")
    lines.append("")
    lines.append("\n\n".join(bodies))
    code = "\n".join(lines)
    return ModelsResult(code=code, converted=converted, flagged=flagged)
