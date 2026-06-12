import ast
from pathlib import Path

from demagic.parser.datasources import parse_datasources
from demagic.scaffold.models_gen import generate_models


def test_generates_valid_sqlmodel_code(sample_source: Path):
    objs = parse_datasources(sample_source / "DataSources.xml")
    code = generate_models(objs)

    ast.parse(code)  # must be syntactically valid Python
    assert "class Customer(SQLModel, table=True):" in code
    assert '__tablename__ = "tbl_Customer"' in code
    assert "customer_id" in code
    assert "joined_on: date | None" in code
    assert "total: Decimal | None" in code


def test_stored_procedures_become_comments_not_classes(sample_source: Path):
    objs = parse_datasources(sample_source / "DataSources.xml")
    code = generate_models(objs)
    assert "class GetOrderTotals" not in code
    assert "p_GetOrderTotals" in code  # documented as a flagged SP stub
