from pathlib import Path

from demagic.parser.program import parse_program


def test_parses_logic_units_and_expressions(sample_source: Path):
    prg = parse_program(sample_source / "Prg_1.xml")
    assert prg.prog_id == "1"
    assert prg.data_object_refs == ["1"]
    # 2 task-level logic units + 1 synthetic exprtable unit for the Expressions table
    assert len(prg.logic_units) == 3

    task_unit = prg.logic_units[0]
    assert task_unit.level == "T"
    assert task_unit.expressions[0].text == "Trim(Name)"
    assert task_unit.calls[0].target_obj == "2"
    assert task_unit.operations == {"Update": 1, "Call": 1}
    assert task_unit.logic_lines == 2

    record_unit = prg.logic_units[1]
    assert record_unit.level == "R"
    assert prg.messages[0].text == "Customer ID must be positive"

    # Synthetic exprtable unit holds the program-level Expressions table
    exprtable = prg.logic_units[2]
    assert exprtable.artifact_id == "prg:1/lu:exprtable"
    assert exprtable.level == "X"
    assert exprtable.expressions[0].text == "Upper(Name)"


def test_captures_forms(sample_source: Path):
    prg = parse_program(sample_source / "Prg_1.xml")
    assert prg.forms[0].name == "Customer Browser"
    assert "btnRefresh" in prg.forms[0].controls


def test_unknown_elements_are_captured_not_dropped(sample_source: Path):
    prg = parse_program(sample_source / "Prg_1.xml")
    assert prg.unknown_tags.get("FutureWidget") == 1
    # Structural containers (ProgramsRepository, TaskLogic, etc.) must NOT appear
    # in unknown_tags — they are descended through silently.
    assert "ProgramsRepository" not in prg.unknown_tags
    assert "TaskLogic" not in prg.unknown_tags
    assert "TaskForms" not in prg.unknown_tags


def test_expression_artifact_ids_unique(sample_source: Path):
    prg = parse_program(sample_source / "Prg_1.xml")
    ids = [e.artifact_id for lu in prg.logic_units for e in lu.expressions]
    assert len(ids) == len(set(ids))


def test_unknown_wrapper_with_known_content_extracted(sample_source: Path):
    """Regression: unknown wrapper element containing a known tag.

    ProgramsRepository, TaskLogic, TaskForms are treated as structural containers
    and their known children are extracted correctly.  Also verify that a truly
    unknown element (FutureWidget) is recorded in unknown_tags but its absence
    of known children does not suppress the rest of parsing.
    """
    prg = parse_program(sample_source / "Prg_1.xml")
    # Content inside structural wrappers was extracted
    assert len(prg.logic_units) > 0        # TaskLogic > LogicUnit reached
    assert len(prg.forms) > 0              # TaskForms > FormEntry reached
    assert len(prg.data_object_refs) > 0   # Resource > DB > DataObject reached
    # The unknown leaf element is recorded
    assert "FutureWidget" in prg.unknown_tags
