"""Coverage Ledger - the 100% guarantee.

Every artifact discovered during scan is registered here and must end the
pipeline as converted, flagged (with reason), or unparsed (with location).
"""
from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class ArtifactStatus(str, Enum):
    PENDING = "pending"
    CONVERTED = "converted"
    FLAGGED = "flagged"
    UNPARSED = "unparsed"


class LedgerEntry(BaseModel):
    artifact_id: str
    kind: str
    status: ArtifactStatus = ArtifactStatus.PENDING
    reason: str | None = None
    output_path: str | None = None  # generated file this artifact landed in


class LedgerData(BaseModel):
    artifacts: dict[str, LedgerEntry] = Field(default_factory=dict)


class Ledger:
    FILENAME = "ledger.json"

    def __init__(self, workdir: Path, data: LedgerData | None = None) -> None:
        self.workdir = Path(workdir)
        self._data = data or LedgerData()

    @classmethod
    def load(cls, workdir: Path) -> "Ledger":
        path = Path(workdir) / cls.FILENAME
        if path.exists():
            data = LedgerData.model_validate(json.loads(path.read_text(encoding="utf-8")))
            return cls(workdir, data)
        return cls(workdir)

    def save(self) -> None:
        self.workdir.mkdir(parents=True, exist_ok=True)
        path = self.workdir / self.FILENAME
        path.write_text(self._data.model_dump_json(indent=2), encoding="utf-8")

    def register(self, artifact_id: str, kind: str) -> None:
        if artifact_id not in self._data.artifacts:
            self._data.artifacts[artifact_id] = LedgerEntry(artifact_id=artifact_id, kind=kind)

    def set_status(self, artifact_id: str, status: ArtifactStatus,
                   reason: str | None = None, output_path: str | None = None) -> None:
        entry = self._data.artifacts[artifact_id]
        update = {"status": status, "reason": reason, "output_path": output_path}
        self._data.artifacts[artifact_id] = entry.model_copy(update=update)

    def get(self, artifact_id: str) -> LedgerEntry:
        return self._data.artifacts[artifact_id]

    def all_entries(self) -> list[LedgerEntry]:
        return list(self._data.artifacts.values())

    def pending_count(self) -> int:
        return sum(1 for e in self._data.artifacts.values()
                   if e.status == ArtifactStatus.PENDING)

    def reconcile(self) -> list[str]:
        """Return artifact_ids still pending. Empty list == 100% accounted for."""
        return [e.artifact_id for e in self._data.artifacts.values()
                if e.status == ArtifactStatus.PENDING]
