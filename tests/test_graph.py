from pathlib import Path

from demagic.analyze.graph import analyze_project
from demagic.scan import scan_project


def test_call_graph_and_order(sample_repo: Path, tmp_path: Path):
    project = scan_project(sample_repo / "CustomerApp", tmp_path / ".demagic")
    analysis = analyze_project(project)

    # Prg_1 calls program 2 -> program 2 must be translated first
    assert analysis.call_graph == {"1": ["2"], "2": []}
    assert analysis.translation_order.index("2") < analysis.translation_order.index("1")

    # complexity = logic lines (proxy)
    assert analysis.complexity["1"] == 3
    assert analysis.complexity["2"] == 1

    # table usage maps program -> data object physical names
    assert analysis.table_usage["1"] == ["tbl_Customer"]
    assert set(analysis.table_usage["2"]) == {"tbl_Order", "p_GetOrderTotals"}

    # both programs are reachable (public/menu/called) -> no dead code here
    assert analysis.unreachable == []


def test_cycles_dont_hang(sample_repo: Path, tmp_path: Path):
    project = scan_project(sample_repo / "CustomerApp", tmp_path / ".demagic")
    # Inject an artificial cycle: 2 -> 1
    project.programs[1].logic_units[0].calls.append(
        type(project.programs[0].logic_units[0].calls[0])(target_obj="1"))
    analysis = analyze_project(project)
    assert sorted(analysis.translation_order) == ["1", "2"]  # all present, no hang
