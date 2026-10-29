"""Version-neutral evidence classes, states, records, and typed claims."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping


class ValidationError(ValueError):
    """Raised when a neutral primitive violates its declared schema."""


class EvidenceClass(str, Enum):
    """Released Version 0.1 evidence classes with their exact stored values."""

    SUPPLIED_PAGE_OBSERVATION = "supplied_image_observation"
    BIBLIOGRAPHIC_EVIDENCE = "bibliography"
    OTHER_WITNESS = "other_witness"
    HISTORICAL_TRANSLATION = "historical_translation"
    EXTERNAL_AUTHORITY = "external_authority"
    INFERENCE_OR_RECONSTRUCTION = "inference_reconstruction"


V01_EVIDENCE_CLASSES = frozenset(item.value for item in EvidenceClass)


class EvidenceState(str, Enum):
    """Semantic evidence-state distinctions protected by the v0.1 contract."""

    PAGE_VISIBLE = "PAGE_VISIBLE"
    PAGE_PROBABLE = "PAGE_PROBABLE"
    PAGE_UNCERTAIN = "PAGE_UNCERTAIN"
    PAGE_OBSCURED = "PAGE_OBSCURED"
    PAGE_LOST = "PAGE_LOST"
    WITNESS_READING = "WITNESS_READING"
    WITNESS_RECONSTRUCTION = "WITNESS_RECONSTRUCTION"
    INFERENCE = "INFERENCE"
    CONJECTURE = "CONJECTURE"


EVIDENCE_STATES = frozenset(item.value for item in EvidenceState)

# These exact subsets are the values accepted by the released Alpha 12 audit.
# The compatibility adapter must not broaden them.
V01_PAGE_EVIDENCE_STATES = frozenset(
    {"PAGE_VISIBLE", "PAGE_UNCERTAIN", "PAGE_OBSCURED", "PAGE_LOST"}
)
V01_RECONSTRUCTION_STATES = frozenset({"WITNESS_RECONSTRUCTION", "CONJECTURE"})
V01_CLAIM_EVIDENCE_STATES = V01_PAGE_EVIDENCE_STATES | V01_RECONSTRUCTION_STATES
OBSERVATIONAL_PLACEHOLDERS = frozenset(
    {"", "[obscured]", "[unreadable]", "[illegible]", "[missing]", "[...]", "[lacuna]"}
)


def _require_nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{label} must be a non-empty string")
    return value


def validate_evidence_references(
    references: Any,
    available_evidence_ids: Iterable[str],
    owner: str = "object",
    *,
    allow_none: bool = False,
) -> tuple[str, ...]:
    """Validate references without coercing or silently dropping malformed ids."""

    if references is None and allow_none:
        return ()
    if not isinstance(references, list):
        raise ValidationError(f"{owner} evidence_ids must be a list")
    available = set(available_evidence_ids)
    normalized: list[str] = []
    for evidence_id in references:
        _require_nonempty_string(evidence_id, f"{owner} evidence_id")
        if evidence_id not in available:
            raise ValidationError(f"{owner} references missing evidence {evidence_id}")
        normalized.append(evidence_id)
    return tuple(normalized)


def validate_page_state_transition(source_state: str, target_state: str) -> None:
    """Reject the released contract's forbidden obscured-to-visible promotion."""

    if source_state not in EVIDENCE_STATES or target_state not in EVIDENCE_STATES:
        raise ValidationError("source_state and target_state must be declared evidence states")
    if source_state in {"PAGE_OBSCURED", "PAGE_LOST"} and target_state == "PAGE_VISIBLE":
        raise ValidationError(f"{source_state} cannot become PAGE_VISIBLE")


def validate_obscured_representation(
    page_state: str,
    supplied_page_text: Any,
    *,
    reconstruction_state: str | None = None,
    reconstruction_text: Any = None,
) -> None:
    """Keep reconstruction separate from the supplied-page observational layer."""

    if page_state not in V01_PAGE_EVIDENCE_STATES:
        raise ValidationError(f"invalid v0.1 page state {page_state!r}")
    if page_state not in {"PAGE_OBSCURED", "PAGE_LOST"}:
        return
    placeholder = supplied_page_text is None or (
        isinstance(supplied_page_text, str)
        and supplied_page_text.strip().lower() in OBSERVATIONAL_PLACEHOLDERS
    )
    if not placeholder:
        raise ValidationError("obscured supplied-page text cannot contain a visible reading")
    if reconstruction_text:
        if reconstruction_state not in V01_RECONSTRUCTION_STATES:
            raise ValidationError("reconstruction requires a v0.1 reconstruction state")


@dataclass(frozen=True)
class EvidenceRecord:
    """Lossless wrapper for one released v0.1 evidence object."""

    _raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, value: Any) -> "EvidenceRecord":
        if not isinstance(value, dict):
            raise ValidationError("evidence record must be an object")
        evidence_id = _require_nonempty_string(value.get("evidence_id"), "evidence_id")
        evidence_class = value.get("evidence_class")
        if evidence_class not in V01_EVIDENCE_CLASSES:
            raise ValidationError(f"{evidence_id} has invalid evidence_class {evidence_class!r}")
        if not value.get("independence_group"):
            raise ValidationError(f"{evidence_id} lacks independence_group")
        if not value.get("description"):
            raise ValidationError(f"{evidence_id} lacks description")
        return cls(copy.deepcopy(value))

    @property
    def evidence_id(self) -> str:
        return str(self._raw["evidence_id"])

    @property
    def evidence_class(self) -> str:
        return str(self._raw["evidence_class"])

    @property
    def independence_group(self) -> str:
        return str(self._raw["independence_group"])

    @property
    def evidence_root(self) -> Any:
        return self._raw.get("evidence_root")

    @property
    def provenance(self) -> Any:
        return copy.deepcopy(self._raw.get("provenance"))

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class TypedClaim:
    """Lossless typed claim wrapper with v0.1-compatible state validation."""

    _raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(
        cls,
        value: Any,
        available_evidence_ids: Iterable[str],
        *,
        require_claim_type: bool = True,
        allow_none_evidence_ids: bool = False,
    ) -> "TypedClaim":
        if not isinstance(value, dict):
            raise ValidationError("claim must be an object")
        claim_id = _require_nonempty_string(value.get("claim_id"), "claim_id")
        if require_claim_type:
            _require_nonempty_string(value.get("claim_type"), f"claim {claim_id} claim_type")
        validate_evidence_references(
            value.get("evidence_ids", []),
            available_evidence_ids,
            f"claim {claim_id}",
            allow_none=allow_none_evidence_ids,
        )
        evidence_state = value.get("evidence_state")
        if evidence_state and evidence_state not in V01_CLAIM_EVIDENCE_STATES:
            raise ValidationError(
                f"claim {claim_id} has invalid v0.1 evidence_state {evidence_state!r}"
            )
        relationship = value.get("relationship")
        if relationship:
            from .relations import V01_TYPED_RELATIONSHIPS

            if relationship not in V01_TYPED_RELATIONSHIPS:
                raise ValidationError(
                    f"claim {claim_id} has invalid v0.1 relationship {relationship!r}"
                )
        return cls(copy.deepcopy(value))

    @property
    def claim_id(self) -> str:
        return str(self._raw["claim_id"])

    @property
    def evidence_ids(self) -> tuple[str, ...]:
        value = self._raw.get("evidence_ids")
        return tuple(value) if isinstance(value, list) else ()

    @property
    def work_id(self) -> Any:
        return self._raw.get("work_id")

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))
