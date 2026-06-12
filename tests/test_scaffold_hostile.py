"""Tests for scaffold hardening: hostile identifiers, class collisions,
duplicate physical names, no-PK tables, menu spec output, ledger completeness.

All IR objects are constructed inline - no fixture files.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from demagic.ir.models import (
    ColumnIR,
    DataObjectIR,
    IndexIR,
    MenuEntryIR,
    ProgramHeaderIR,
    ProgramIR,
    ProjectIR,
)
from demagic.ledger.ledger import ArtifactStatus, Ledger
from demagic.scaffold.models_gen import ModelsResult, generate_models
from demagic.scaffold.project_gen import scaffold_project


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _ds(
    obj_id: str,
    magic_name: str,
    physical_name: str,
    columns: list[ColumnIR],
    indexes: list[IndexIR] | None = None,
    object_type: str = "T",
) -> DataObjectIR:
    return DataObjectIR(
        artifact_id=f"ds:{obj_id}",
        obj_id=obj_id,
        physical_name=physical_name,
        magic_name=magic_name,
        connection="MAINDB",
        object_type=object_type,
        columns=columns,
        indexes=indexes or [],
    )


def _col(name: str, db_name: str | None = None, magic_type: str = "A") -> ColumnIR:
    return ColumnIR(name=name, db_name=db_name, magic_type=magic_type)


def _unique_idx(col_name: str, name: str = "PK_test") -> IndexIR:
    return IndexIR(name=name, columns=[col_name], unique=True)


# ---------------------------------------------------------------------------
# Test 1: hostile field identifiers
# ---------------------------------------------------------------------------

def test_hostile_field_identifiers():
    """class, ##, and 2FACode columns must all produce valid Python identifiers."""
    obj = _ds(
        "1", "HosTable", "tbl_hos",
        columns=[
            _col("class", db_name="class"),          # keyword -> class_
            _col("##", db_name="##"),                 # empty after strip -> col_1
            _col("2FACode", db_name="2FACode"),       # digit-leading -> n2_facode or n2facode
        ],
        indexes=[_unique_idx("class")],
    )
    result: ModelsResult = generate_models([obj])
    code = result.code

    # Must be valid Python
    ast.parse(code)

    # 'class' is a keyword - must be escaped
    assert "class_" in code
    # '##' has no valid chars -> fallback col_<i>
    assert "col_1" in code
    # 2FACode must not appear raw (starts with digit)
    assert "2FACode" not in code
    # The sanitised form must start with 'n'
    assert any(token.startswith("n2") for token in code.split())


# ---------------------------------------------------------------------------
# Test 2: class name collision (Customer + Customers)
# ---------------------------------------------------------------------------

def test_class_name_collision():
    """Customer and Customers de-pluralize to the same name; second gets suffix 2."""
    obj_a = _ds("1", "Customer", "tbl_customer",
                columns=[_col("ID", db_name="id", magic_type="N")],
                indexes=[_unique_idx("ID")])
    obj_b = _ds("2", "Customers", "tbl_customers",
                columns=[_col("ID", db_name="id", magic_type="N")],
                indexes=[_unique_idx("ID")])
    result: ModelsResult = generate_models([obj_a, obj_b])
    code = result.code

    ast.parse(code)
    compile(code, "<string>", "exec")

    assert "class Customer(" in code
    assert "class Customer2(" in code
    # Both must appear exactly once each
    assert code.count("class Customer(") == 1
    assert code.count("class Customer2(") == 1


# ---------------------------------------------------------------------------
# Test 3: duplicate physical name
# ---------------------------------------------------------------------------

def test_duplicate_physical_name():
    """Second object with the same physical_name is skipped with a FLAGGED comment."""
    obj_a = _ds("1", "Alpha", "tbl_shared",
                columns=[_col("ID", db_name="id")],
                indexes=[_unique_idx("ID")])
    obj_b = _ds("2", "Beta", "tbl_shared",
                columns=[_col("ID", db_name="id")],
                indexes=[_unique_idx("ID")])
    result: ModelsResult = generate_models([obj_a, obj_b])
    code = result.code

    ast.parse(code)
    # Only one class for tbl_shared
    assert code.count('__tablename__ = "tbl_shared"') == 1
    # Second one is flagged
    assert "ds:2" in result.flagged
    assert "duplicate physical name" in result.flagged["ds:2"]


# ---------------------------------------------------------------------------
# Test 4: no-PK table flagged in ledger + FLAGGED comment in code
# ---------------------------------------------------------------------------

def test_no_pk_table_flagged():
    """A table with no unique index must emit a FLAGGED comment and appear in flagged dict."""
    obj = _ds("99", "NoPkTable", "tbl_nopk",
              columns=[_col("SomeCol", db_name="some_col")],
              indexes=[])  # no indexes at all
    result: ModelsResult = generate_models([obj])
    code = result.code

    ast.parse(code)
    assert "FLAGGED: no unique index" in code
    assert "ds:99" in result.flagged
    assert "primary key" in result.flagged["ds:99"].lower()


# ---------------------------------------------------------------------------
# Test 5: menus CONVERTED + menus.json exists; project artifact CONVERTED
# ---------------------------------------------------------------------------

def test_menus_and_project_ledger(tmp_path: Path):
    """menus.json written, menu entries CONVERTED, project artifact CONVERTED."""
    workdir = tmp_path / ".demagic"
    out = tmp_path / "out"

    # Build a minimal ProjectIR with menus
    menu_child = MenuEntryIR(artifact_id="menu:2", name="Sub", program="1")
    menu_root = MenuEntryIR(artifact_id="menu:1", name="Root", program="", children=[menu_child])

    ds_obj = _ds("1", "Item", "tbl_item",
                 columns=[_col("ID", db_name="id")],
                 indexes=[_unique_idx("ID")])

    prg = ProgramIR(artifact_id="prg:1", prog_id="1")
    header = ProgramHeaderIR(
        artifact_id="hdr:1", prog_id="1", description="Items", public_name="items")

    project = ProjectIR(
        artifact_id="prj:TestApp",
        name="TestApp",
        source_dir=str(tmp_path),
        data_objects=[ds_obj],
        program_headers=[header],
        programs=[prg],
        menus=[menu_root],
    )

    # Register everything in the ledger so set_status doesn't KeyError
    ledger = Ledger.load(workdir)
    ledger.register("prj:TestApp", kind="project")
    ledger.register("ds:1", kind="data_object")
    ledger.register("menu:1", kind="menu")
    ledger.register("menu:2", kind="menu")
    ledger.save()

    scaffold_project(project, out, workdir)

    # menus.json must exist
    menus_json = out / "ui-specs" / "menus.json"
    assert menus_json.exists(), "menus.json not written"
    data = json.loads(menus_json.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert data[0]["name"] == "Root"

    led = Ledger.load(workdir)
    assert led.get("menu:1").status == ArtifactStatus.CONVERTED
    assert led.get("menu:1").output_path is not None
    assert led.get("menu:2").status == ArtifactStatus.CONVERTED
    assert led.get("prj:TestApp").status == ArtifactStatus.CONVERTED
    assert led.get("prj:TestApp").output_path is not None


# ---------------------------------------------------------------------------
# Test 6: route function name sanitized; docstring with """ is safe
# ---------------------------------------------------------------------------

def test_hostile_route_and_docstring(tmp_path: Path):
    """public_name with hyphens -> valid fn name; description with triple-quote -> no syntax error."""
    workdir = tmp_path / ".demagic"
    out = tmp_path / "out"

    ds_obj = _ds("1", "Widget", "tbl_widget",
                 columns=[_col("ID", db_name="id")],
                 indexes=[_unique_idx("ID")])

    prg = ProgramIR(artifact_id="prg:1", prog_id="1")
    header = ProgramHeaderIR(
        artifact_id="hdr:1",
        prog_id="1",
        description='Shows "widgets" with special chars: """ end',
        public_name="cust-list",   # hyphen in name -> needs sanitization
    )

    project = ProjectIR(
        artifact_id="prj:HostileApp",
        name="Hostile-App 2nd",
        source_dir=str(tmp_path),
        data_objects=[ds_obj],
        program_headers=[header],
        programs=[prg],
        menus=[],
    )

    ledger = Ledger.load(workdir)
    ledger.register("prj:HostileApp", kind="project")
    ledger.register("ds:1", kind="data_object")
    ledger.save()

    scaffold_project(project, out, workdir)

    main_text = (out / "app" / "main.py").read_text(encoding="utf-8")
    ast.parse(main_text)
    compile(main_text, "<string>", "exec")

    # Route path preserved as-is
    assert "/cust-list" in main_text
    # Function name sanitized: hyphens become underscores
    assert "def cust_list" in main_text

    # pyproject name sanitized
    pyproject = (out / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "hostile-app-2nd"' in pyproject
