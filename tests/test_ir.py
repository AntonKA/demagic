from demagic.ir.models import (
    ColumnIR, DataObjectIR, ExpressionIR, LogicUnitIR, MenuEntryIR,
    ProgramHeaderIR, ProgramIR, ProjectIR, magic_type_to_python,
)


def test_data_object_ir_roundtrip():
    obj = DataObjectIR(
        artifact_id="ds:1", obj_id="1", physical_name="tbl_customer",
        magic_name="Customers", connection="MAINDB", object_type="T",
        columns=[ColumnIR(name="CustomerID", db_name="customer_id", magic_type="N")],
    )
    data = obj.model_dump()
    assert DataObjectIR.model_validate(data) == obj


def test_magic_type_mapping():
    assert magic_type_to_python("A") == "str"
    assert magic_type_to_python("U") == "str"
    assert magic_type_to_python("N") == "Decimal"
    assert magic_type_to_python("D") == "date"
    assert magic_type_to_python("T") == "time"
    assert magic_type_to_python("L") == "bool"
    assert magic_type_to_python("B") == "bytes"
    assert magic_type_to_python("?") == "str"  # unknown degrades to str


def test_project_ir_aggregates():
    prj = ProjectIR(
        artifact_id="prj:demo", name="demo", source_dir="/tmp/demo/Source",
        data_objects=[], program_headers=[
            ProgramHeaderIR(artifact_id="prg:1", prog_id="1", description="Customer List",
                            task_type="O", public_name="custlist"),
        ],
        programs=[ProgramIR(artifact_id="prg:1", prog_id="1", logic_units=[
            LogicUnitIR(artifact_id="prg:1/lu:0", level="T",
                        expressions=[ExpressionIR(artifact_id="prg:1/expr:0", text="Trim(A)")]),
        ])],
        menus=[MenuEntryIR(artifact_id="menu:0", name="Customers", program="1")],
    )
    assert prj.programs[0].logic_units[0].expressions[0].text == "Trim(A)"
