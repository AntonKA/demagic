"""File/ISAM data sources must not produce dotted SQL table names."""
from __future__ import annotations

import ast

from demagic.ir.models import ColumnIR, DataObjectIR
from demagic.scaffold.models_gen import generate_models


def _obj(physical: str) -> DataObjectIR:
    return DataObjectIR(
        artifact_id=f"ds:{physical}", obj_id="1", physical_name=physical,
        magic_name="ActionItems", connection="FILE", object_type="T",
        columns=[ColumnIR(name="NodeId", db_name="node_id", magic_type="A")],
    )


def test_file_source_tablename_sanitised_and_flagged():
    result = generate_models([_obj("ActionItems.xml")])
    ast.parse(result.code)
    assert '__tablename__ = "ActionItems"' in result.code
    assert '"ActionItems.xml"' not in result.code  # the dotted name is gone
    assert "# source: ActionItems.xml" in result.code
    reason = result.flagged["ds:ActionItems.xml"]
    assert "file/non-SQL source" in reason
    assert "ActionItems.xml" in reason


def test_normal_tablename_unchanged():
    result = generate_models([_obj("change_entries")])
    assert '__tablename__ = "change_entries"' in result.code
    assert "# source:" not in result.code  # nothing rewritten
