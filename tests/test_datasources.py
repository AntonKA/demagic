from pathlib import Path

from demagic.parser.datasources import parse_datasources


def test_parses_tables_and_sp(sample_source: Path):
    objs = parse_datasources(sample_source / "DataSources.xml")
    assert len(objs) == 3
    by_name = {o.physical_name: o for o in objs}

    cust = by_name["tbl_Customer"]
    assert cust.object_type == "T"
    assert cust.connection == "MAINDB"
    assert [c.name for c in cust.columns] == ["CustomerID", "Name", "JoinedOn"]
    assert cust.columns[0].db_name == "customer_id"
    assert cust.columns[0].magic_type == "N"
    assert cust.indexes[0].unique is True
    assert cust.indexes[0].columns == ["CustomerID"]

    sp = by_name["p_GetOrderTotals"]
    assert sp.object_type == "S"
    assert sp.sp_params == 1


def test_artifact_ids_are_stable(sample_source: Path):
    objs = parse_datasources(sample_source / "DataSources.xml")
    assert objs[0].artifact_id == "ds:1"
