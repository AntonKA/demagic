"""Parse DataSources.xml -> list[DataObjectIR]."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from demagic.ir.models import ColumnIR, DataObjectIR, IndexIR


def _parse_column(col: ET.Element) -> ColumnIR:
    db_col = col.find(".//DbColumnName")
    attr = col.find(".//Attribute")
    return ColumnIR(
        name=col.get("name", ""),
        db_name=db_col.get("val") if db_col is not None else None,
        magic_type=attr.get("val") if attr is not None else None,
    )


def _parse_index(idx: ET.Element) -> IndexIR:
    return IndexIR(
        name=idx.get("name"),
        unique=idx.get("unique", "N") == "Y",
        columns=[c.get("name", "") for c in idx.findall(".//IndexColumn")],
    )


def parse_datasources(path: Path) -> list[DataObjectIR]:
    root = ET.parse(path).getroot()
    objects: list[DataObjectIR] = []
    for obj in root.findall(".//DataObject"):
        obj_id = obj.get("id", "")
        obj_type_el = obj.find("ObjectType")
        sp_type_el = obj.find("SPType")
        objects.append(DataObjectIR(
            artifact_id=f"ds:{obj_id}",
            obj_id=obj_id,
            physical_name=obj.get("PhysicalName", ""),
            magic_name=obj.get("name", ""),
            connection=obj.get("data_source", ""),
            object_type=obj_type_el.get("val", "") if obj_type_el is not None else "",
            sp_type=sp_type_el.get("val") if sp_type_el is not None else None,
            sp_params=len(obj.findall(".//SPParameter")),
            columns=[_parse_column(c) for c in obj.findall(".//Column")],
            indexes=[_parse_index(i) for i in obj.findall(".//Index")],
        ))
    return objects
