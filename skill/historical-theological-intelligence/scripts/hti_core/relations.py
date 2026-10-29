"""Generic evidence relations already present in Version 0.1."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

from .model import ValidationError, validate_evidence_references


class GenericEvidenceRelation(str, Enum):
    SUPPORTS = "SUPPORTS"
    DERIVED_FROM = "DERIVED_FROM"
    RECONSTRUCTS = "RECONSTRUCTS"
    QUALIFIES = "QUALIFIES"
    CONFLICTS_WITH = "CONFLICTS_WITH"
    REQUIRES = "REQUIRES"
    DOES_NOT_SUPPORT = "DOES_NOT_SUPPORT"


V01_TYPED_RELATIONSHIPS = frozenset(item.value for item in GenericEvidenceRelation)


@dataclass(frozen=True)
class EvidenceRelation:
    """Lossless relation wrapper with explicit endpoint and evidence references."""

    _raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(
        cls,
        value: Any,
        endpoint_ids: Iterable[str],
        evidence_ids: Iterable[str],
    ) -> "EvidenceRelation":
        if not isinstance(value, dict):
            raise ValidationError("evidence relation must be an object")
        relation_id = value.get("relation_id")
        if not isinstance(relation_id, str) or not relation_id:
            raise ValidationError("relation_id must be a non-empty string")
        relation_type = value.get("relation_type")
        if relation_type not in V01_TYPED_RELATIONSHIPS:
            raise ValidationError(f"{relation_id} has invalid relation_type {relation_type!r}")
        endpoints = set(endpoint_ids)
        for key in ("source_ref", "target_ref"):
            endpoint = value.get(key)
            if not isinstance(endpoint, str) or endpoint not in endpoints:
                raise ValidationError(f"{relation_id} has invalid {key} {endpoint!r}")
        validate_evidence_references(
            value.get("evidence_ids", []), evidence_ids, f"relation {relation_id}"
        )
        return cls(copy.deepcopy(value))

    @property
    def relation_type(self) -> str:
        return str(self._raw["relation_type"])

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))
