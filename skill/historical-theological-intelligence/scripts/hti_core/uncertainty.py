"""Qualitative uncertainty assessments separate from evidence and relations."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from .model import EVIDENCE_STATES, ValidationError


class QualitativeConfidence(str, Enum):
    """Exact qualitative confidence vocabulary used by Version 0.1."""

    SECURE = "secure"
    PROBABLE = "probable"
    POSSIBLE = "possible"
    UNRESOLVED = "unresolved"
    ILLEGIBLE = "illegible"


V01_QUALITATIVE_CONFIDENCE = frozenset(item.value for item in QualitativeConfidence)


@dataclass(frozen=True)
class UncertaintyAssessment:
    """Lossless assessment record that does not propagate or promote evidence."""

    _raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, value: Any) -> "UncertaintyAssessment":
        if not isinstance(value, dict):
            raise ValidationError("uncertainty assessment must be an object")
        confidence = value.get("confidence")
        if confidence not in V01_QUALITATIVE_CONFIDENCE:
            raise ValidationError(f"invalid qualitative confidence {confidence!r}")
        evidence_state = value.get("evidence_state")
        if evidence_state is not None and evidence_state not in EVIDENCE_STATES:
            raise ValidationError(f"invalid evidence_state {evidence_state!r}")
        provenance = value.get("provenance")
        if provenance is not None and not isinstance(provenance, dict):
            raise ValidationError("uncertainty provenance must be an object")
        return cls(copy.deepcopy(value))

    @property
    def confidence(self) -> str:
        return str(self._raw["confidence"])

    @property
    def evidence_state(self) -> str | None:
        value = self._raw.get("evidence_state")
        return str(value) if value is not None else None

    @property
    def relation_type(self) -> str | None:
        value = self._raw.get("relation_type")
        return str(value) if value is not None else None

    @property
    def provenance(self) -> Any:
        return copy.deepcopy(self._raw.get("provenance"))

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))
