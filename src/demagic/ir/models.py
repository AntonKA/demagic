"""Typed Intermediate Representation of a Magic xpa application.

Every model carries an artifact_id - the stable key into the Coverage Ledger.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

# Magic attribute codes -> Python type names (used by the SQLModel generator).
_MAGIC_TYPES = {
    "A": "str", "U": "str", "N": "Decimal", "D": "date",
    "T": "time", "L": "bool", "B": "bytes",
}


def magic_type_to_python(magic_type: str | None) -> str:
    return _MAGIC_TYPES.get(magic_type or "", "str")


class ColumnIR(BaseModel):
    name: str
    db_name: str | None = None
    magic_type: str | None = None
    length: int | None = None


class IndexIR(BaseModel):
    name: str | None = None
    columns: list[str] = Field(default_factory=list)
    unique: bool = False


class DataObjectIR(BaseModel):
    artifact_id: str
    obj_id: str
    physical_name: str
    magic_name: str
    connection: str
    object_type: str  # T=table, V=view, S=stored procedure
    sp_type: str | None = None
    sp_params: int = 0
    columns: list[ColumnIR] = Field(default_factory=list)
    indexes: list[IndexIR] = Field(default_factory=list)


class ProgramHeaderIR(BaseModel):
    artifact_id: str
    prog_id: str
    description: str = ""
    task_type: str = ""  # O/B/C/R/S/P
    public_name: str = ""
    interactive: bool = False
    external: bool = False
    has_dotnet: bool = False
    is_empty: bool = False
    last_modified: str = ""


class ExpressionIR(BaseModel):
    artifact_id: str
    text: str


class CallIR(BaseModel):
    target_obj: str | None = None
    target_comp: str | None = None


class MessageIR(BaseModel):
    text: str
    mode: str = ""
    title: str = ""


class LogicUnitIR(BaseModel):
    artifact_id: str
    level: str = ""  # T=Task, R=Record, H=Handler, ...
    description: str | None = None
    expressions: list[ExpressionIR] = Field(default_factory=list)
    calls: list[CallIR] = Field(default_factory=list)
    operations: dict[str, int] = Field(default_factory=dict)
    logic_lines: int = 0


class FormIR(BaseModel):
    artifact_id: str
    name: str
    controls: list[str] = Field(default_factory=list)


class ProgramIR(BaseModel):
    artifact_id: str
    prog_id: str
    task_descriptions: list[str] = Field(default_factory=list)
    data_object_refs: list[str] = Field(default_factory=list)  # DataObjectIR.obj_id
    logic_units: list[LogicUnitIR] = Field(default_factory=list)
    forms: list[FormIR] = Field(default_factory=list)
    messages: list[MessageIR] = Field(default_factory=list)
    snippets: list[str] = Field(default_factory=list)  # embedded C# source
    dotnet_types: list[str] = Field(default_factory=list)
    unknown_tags: dict[str, int] = Field(default_factory=dict)  # tag -> count


class MenuEntryIR(BaseModel):
    artifact_id: str
    name: str = ""
    program: str = ""
    entry_point: str = ""
    children: list[MenuEntryIR] = Field(default_factory=list)


class ProjectIR(BaseModel):
    artifact_id: str
    name: str
    source_dir: str
    data_objects: list[DataObjectIR] = Field(default_factory=list)
    program_headers: list[ProgramHeaderIR] = Field(default_factory=list)
    programs: list[ProgramIR] = Field(default_factory=list)
    menus: list[MenuEntryIR] = Field(default_factory=list)
