import ast
from pathlib import Path

from demagic.ir.models import DataObjectIR
from demagic.parser.datasources import parse_datasources
from demagic.scaffold.models_gen import generate_models


def test_generates_valid_sqlmodel_code(sample_source: Path):
    objs = parse_datasources(sample_source / "DataSources.xml")
    result = generate_models(objs)
    code = result.code

    ast.parse(code)  # must be syntactically valid Python
    assert "class Customer(SQLModel, table=True):" in code
    assert '__tablename__ = "tbl_Customer"' in code
    assert "customer_id" in code
    assert "joined_on: date | None" in code
    assert "total: Decimal | None" in code


def test_stored_procedures_become_comments_not_classes(sample_source: Path):
    objs = parse_datasources(sample_source / "DataSources.xml")
    result = generate_models(objs)
    code = result.code
    assert "class GetOrderTotals" not in code
    assert "p_GetOrderTotals" in code  # documented as a flagged SP stub


def test_empty_object_list_yields_no_sqlmodel_import():
    """No generated classes -> no sqlmodel import (avoids F401 on real SP-only projects)."""
    result = generate_models([])
    code = result.code
    ast.parse(code)  # syntactically valid
    assert "from sqlmodel" not in code
    assert result.converted == []


def test_sp_only_object_list_yields_no_sqlmodel_import():
    """All stored procedures -> no classes -> no sqlmodel import."""
    sp = DataObjectIR(
        artifact_id="obj:99",
        obj_id="99",
        physical_name="p_DoThing",
        magic_name="DoThing",
        connection="MainDB",
        object_type="S",
        sp_params=2,
    )
    result = generate_models([sp])
    code = result.code
    ast.parse(code)
    assert "from sqlmodel" not in code
    assert result.converted == []
    assert "obj:99" in result.flagged
