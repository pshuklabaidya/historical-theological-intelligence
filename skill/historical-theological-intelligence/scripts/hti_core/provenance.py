"""Neutral provenance, evidence-root, and independence primitives."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .model import EvidenceRecord, ValidationError


@dataclass(frozen=True)
class EvidenceRoot:
    """Opaque root identity for evidence derived from one underlying source."""

    root_id: str
    source_id: str | None = None
    work_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.root_id, str) or not self.root_id:
            raise ValidationError("root_id must be a non-empty string")


@dataclass(frozen=True)
class ProvenanceRecord:
    """Lossless provenance wrapper without historical or bibliographic inference."""

    _raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, value: Any) -> "ProvenanceRecord":
        if not isinstance(value, dict):
            raise ValidationError("provenance must be an object")
        return cls(copy.deepcopy(value))

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


def independent_evidence_count(records: Iterable[EvidenceRecord | Mapping[str, Any]]) -> int:
    """Count distinct v0.1 independence groups, never derivative renderings."""

    groups: set[Any] = set()
    for record in records:
        value = record.to_dict() if isinstance(record, EvidenceRecord) else record
        if not isinstance(value, Mapping):
            raise ValidationError("evidence item must be an object")
        group = value.get("independence_group")
        if group:
            groups.add(group)
    return len(groups)
