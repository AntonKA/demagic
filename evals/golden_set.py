"""Golden set for translate-stage evaluation.

Three synthetic Magic programs, hand-built as IR, covering the patterns seen in
real xpa applications:

  1. crud_with_call   - online CRUD: bound table, expressions, a validation
                        message, and a call to an already-translated subprogram.
  2. batch_calc       - batch job: an expression-table program doing a numeric
                        calc plus a file/string operation (the common "export"
                        shape).
  3. snippet_and_sp   - the hard case: a stored-procedure data object and an
                        embedded C# snippet that must be flagged, not dropped.

Everything here is invented (CustomerApp / Orders domain). No real application
content. These fixtures are the fixed denominator the optimization loop scores
against, so they must stay stable.
"""
from __future__ import annotations

from dataclasses import dataclass

from demagic.ir.models import (
    CallIR, ColumnIR, DataObjectIR, ExpressionIR, LogicUnitIR, MessageIR,
    ProgramHeaderIR, ProgramIR, ProjectIR,
)


@dataclass(frozen=True)
class GoldenCase:
    name: str
    project: ProjectIR
    prog_id: str
    # objective expectations the scorer checks against
    expect_tables: list[str]       # physical names the code should reference
    expect_expr_traces: list[str]  # per-expression signal the code should show
    must_flag: bool                # pack contains SP / C# / unmapped -> flags required


def _crud_with_call() -> GoldenCase:
    customers = DataObjectIR(
        artifact_id="ds:1", obj_id="1", physical_name="tbl_Customer",
        magic_name="Customers", connection="MAINDB", object_type="T",
        columns=[
            ColumnIR(name="CustomerID", db_name="customer_id", magic_type="N"),
            ColumnIR(name="Name", db_name="name", magic_type="U"),
            ColumnIR(name="JoinedOn", db_name="joined_on", magic_type="D"),
        ],
    )
    prog = ProgramIR(
        artifact_id="prg:1", prog_id="1",
        task_descriptions=["Customer List"], data_object_refs=["1"],
        logic_units=[
            LogicUnitIR(
                artifact_id="prg:1/lu:0", level="T",
                operations={"Update": 1, "Call": 1}, logic_lines=2,
                expressions=[ExpressionIR(artifact_id="prg:1/expr:0", text="Trim(Name)")],
                calls=[CallIR(target_obj="2")],
            ),
            LogicUnitIR(
                artifact_id="prg:1/lu:1", level="R",
                operations={"Verify": 1}, logic_lines=1,
                expressions=[ExpressionIR(artifact_id="prg:1/expr:1", text="CustomerID>0")],
            ),
        ],
        messages=[MessageIR(text="Customer ID must be positive", mode="E", title="Validation")],
    )
    project = ProjectIR(
        artifact_id="prj:CustomerApp", name="CustomerApp", source_dir="(synthetic)",
        data_objects=[customers],
        program_headers=[ProgramHeaderIR(
            artifact_id="prg:1", prog_id="1", description="Customer List",
            task_type="O", public_name="custlist", interactive=True)],
        programs=[prog],
    )
    return GoldenCase(
        name="crud_with_call", project=project, prog_id="1",
        expect_tables=["Customer"],  # generated SQLModel class (tablename=tbl_Customer)
        expect_expr_traces=["strip", ">"],  # Trim->.strip(), CustomerID>0 keeps a comparison
        must_flag=False,
    )


def _batch_calc() -> GoldenCase:
    orders = DataObjectIR(
        artifact_id="ds:2", obj_id="2", physical_name="tbl_Order",
        magic_name="Orders", connection="MAINDB", object_type="T",
        columns=[
            ColumnIR(name="OrderID", db_name="order_id", magic_type="N"),
            ColumnIR(name="Total", db_name="total", magic_type="N"),
        ],
    )
    prog = ProgramIR(
        artifact_id="prg:5", prog_id="5",
        task_descriptions=["Nightly Order Export"], data_object_refs=["2"],
        logic_units=[
            LogicUnitIR(
                artifact_id="prg:5/lu:exprtable", level="X",
                operations={}, logic_lines=0,
                expressions=[
                    ExpressionIR(artifact_id="prg:5/expr:0", text="Round(Total*1.1,2)"),
                    ExpressionIR(artifact_id="prg:5/expr:1", text="Trim(OrderID)"),
                    ExpressionIR(artifact_id="prg:5/expr:2", text="'orders_export.csv'"),
                ],
            ),
        ],
    )
    project = ProjectIR(
        artifact_id="prj:CustomerApp", name="CustomerApp", source_dir="(synthetic)",
        data_objects=[orders],
        program_headers=[ProgramHeaderIR(
            artifact_id="prg:5", prog_id="5", description="Nightly Order Export",
            task_type="B")],
        programs=[prog],
    )
    return GoldenCase(
        name="batch_calc", project=project, prog_id="5",
        expect_tables=["Order"],  # generated SQLModel class (tablename=tbl_Order)
        expect_expr_traces=["round", "strip", "orders_export.csv"],
        must_flag=False,
    )


def _snippet_and_sp() -> GoldenCase:
    sp = DataObjectIR(
        artifact_id="ds:3", obj_id="3", physical_name="p_GetOrderTotals",
        magic_name="GetOrderTotals", connection="MAINDB", object_type="S",
        sp_type="SELECT", sp_params=1,
    )
    prog = ProgramIR(
        artifact_id="prg:9", prog_id="9",
        task_descriptions=["Totals via SP and C#"], data_object_refs=["3"],
        logic_units=[
            LogicUnitIR(
                artifact_id="prg:9/lu:0", level="T",
                operations={"Update": 1}, logic_lines=1,
                expressions=[ExpressionIR(artifact_id="prg:9/expr:0",
                                          text="MysteryFormat(Total,'$#,##0.00')")],
            ),
        ],
        snippets=[
            "public static string ToLocal(DateTime utc) {\n"
            "  var tz = TimeZoneInfo.FindSystemTimeZoneById(\"Eastern Standard Time\");\n"
            "  return TimeZoneInfo.ConvertTimeFromUtc(utc, tz).ToString();\n}"
        ],
        dotnet_types=["System.TimeZoneInfo"],
    )
    project = ProjectIR(
        artifact_id="prj:CustomerApp", name="CustomerApp", source_dir="(synthetic)",
        data_objects=[sp],
        program_headers=[ProgramHeaderIR(
            artifact_id="prg:9", prog_id="9", description="Totals via SP and C#",
            task_type="B", has_dotnet=True)],
        programs=[prog],
    )
    return GoldenCase(
        name="snippet_and_sp", project=project, prog_id="9",
        expect_tables=["p_GetOrderTotals"],
        expect_expr_traces=["MysteryFormat"],  # unmapped -> must surface, not invent
        must_flag=True,  # SP + C# snippet + unmapped fn all demand a flag
    )


def golden_cases() -> list[GoldenCase]:
    return [_crud_with_call(), _batch_calc(), _snippet_and_sp()]
