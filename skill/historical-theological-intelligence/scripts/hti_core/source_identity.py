"""Neutral source identity and Version 0.1 verification-stage primitives."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from .model import ValidationError


class SourceVerificationStage(str, Enum):
    """Exact source-verification stages documented by released Version 0.1."""

    LEAD = "lead"
    WORK_IDENTIFIED = "work_identified"
    LOCATION_IDENTIFIED = "location_identified"
    PASSAGE_INSPECTED = "passage_inspected"
    PROPOSITION_VERIFIED = "proposition_verified"


V01_SOURCE_VERIFICATION_STAGES = frozenset(
    item.value for item in SourceVerificationStage
)

# Verification facts are intentionally excluded from the identity view. Source
# locators and citation forms remain identity data and retain their exact keys.
_VERIFICATION_FIELDS = frozenset(
    {"status", "passage_inspected", "proposition_found"}
)


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{label} must be a non-empty string")
    return value


@dataclass(frozen=True)
class SourceIdentity:
    """Opaque, lossless identity data kept separate from verification state."""

    _raw: Mapping[str, Any] = field(repr=False)
    _bound_work_id: str | None = field(default=None, repr=False)

    @classmethod
    def from_dict(
        cls,
        value: Any,
        *,
        work_id: str | None = None,
    ) -> "SourceIdentity":
        if not isinstance(value, dict):
            raise ValidationError("source identity must be an object")
        _nonempty_string(value.get("source_id"), "source_id")
        item_work_id = value.get("work_id", work_id)
        if item_work_id is not None:
            _nonempty_string(item_work_id, "work_id")
        identity_data = {
            key: copy.deepcopy(item)
            for key, item in value.items()
            if key not in _VERIFICATION_FIELDS
        }
        return cls(identity_data, item_work_id)

    @property
    def source_id(self) -> str:
        return str(self._raw["source_id"])

    @property
    def work_id(self) -> str | None:
        value = self._raw.get("work_id", self._bound_work_id)
        return str(value) if value is not None else None

    def field(self, name: str, default: Any = None) -> Any:
        """Return one opaque identity, locator, or extension field."""

        return copy.deepcopy(self._raw.get(name, default))

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class SourceVerificationAssessment:
    """A verification stage plus its recorded evidence facts, without promotion."""

    _raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_source_record(cls, value: Any) -> "SourceVerificationAssessment":
        if not isinstance(value, dict):
            raise ValidationError("source record must be an object")
        stage = value.get("status", SourceVerificationStage.LEAD.value)
        if stage not in V01_SOURCE_VERIFICATION_STAGES:
            raise ValidationError(f"invalid v0.1 source verification stage {stage!r}")
        verification_data = {
            key: copy.deepcopy(item)
            for key, item in value.items()
            if key in _VERIFICATION_FIELDS
        }
        return cls(verification_data)

    @property
    def stage(self) -> str:
        return str(self._raw.get("status", SourceVerificationStage.LEAD.value))

    @property
    def passage_inspected(self) -> bool:
        return self._raw.get("passage_inspected") is True

    @property
    def proposition_found(self) -> Any:
        return copy.deepcopy(self._raw.get("proposition_found"))

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class V01SourceRecord:
    """Lossless Version 0.1 source entry with separate identity and verification."""

    _raw: Mapping[str, Any] = field(repr=False)
    identity: SourceIdentity
    verification: SourceVerificationAssessment

    @classmethod
    def from_dict(
        cls,
        value: Any,
        *,
        work_id: str | None = None,
    ) -> "V01SourceRecord":
        if not isinstance(value, dict):
            raise ValidationError("v0.1 source record must be an object")
        identity = SourceIdentity.from_dict(value, work_id=work_id)
        verification = SourceVerificationAssessment.from_source_record(value)
        if verification.stage == SourceVerificationStage.PROPOSITION_VERIFIED.value:
            if (
                not value.get("passage_locator")
                or value.get("passage_inspected") is not True
                or not value.get("proposition_found")
            ):
                raise ValidationError(
                    f"{identity.source_id} is verified without inspected passage and proposition"
                )
            if value.get("source_type") == "legal" and (
                not value.get("printed_citation")
                or not value.get("normalized_location")
            ):
                raise ValidationError(
                    f"{identity.source_id} lacks printed and normalized legal citations"
                )
        return cls(copy.deepcopy(value), identity, verification)

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))
