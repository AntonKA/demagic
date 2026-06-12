from pathlib import Path

from demagic.parser.program import parse_program


def test_parses_logic_units_and_expressions(sample_source: Path):
    prg = parse_program(sample_source / "Prg_1.xml")
    assert prg.prog_id == "1"
    assert prg.data_object_refs == ["1"]
    assert len(prg.logic_units) == 2

    task_unit = prg.logic_units[0]
    assert task_unit.level == "T"
    assert task_unit.expressions[0].text == "Trim(Name)"
    assert task_unit.calls[0].target_obj == "2"
    assert task_unit.operations == {"Update": 1, "Call": 1}
    assert task_unit.logic_lines == 2

    record_unit = prg.logic_units[1]
    assert record_unit.level == "R"
    assert prg.messages[0].text == "Customer ID must be positive"


def test_captures_forms(sample_source: Path):
    prg = parse_program(sample_source / "Prg_1.xml")
    assert prg.forms[0].name == "Customer Browser"
    assert "btnRefresh" in prg.forms[0].controls


def test_unknown_elements_are_captured_not_dropped(sample_source: Path):
    prg = parse_program(sample_source / "Prg_1.xml")
    assert prg.unknown_tags.get("FutureWidget") == 1


def test_expression_artifact_ids_unique(sample_source: Path):
    prg = parse_program(sample_source / "Prg_1.xml")
    ids = [e.artifact_id for lu in prg.logic_units for e in lu.expressions]
    assert len(ids) == len(set(ids))
