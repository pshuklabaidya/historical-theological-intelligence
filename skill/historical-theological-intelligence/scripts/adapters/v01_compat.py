"""Lossless Version 0.1 checkpoint adaptation to neutral evidence primitives."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Mapping

import evidence_audit
import finalize_response
from hti_core.audit import AuditResult
from hti_core.completion import CompletionReceipt
from hti_core.manifest import NeutralManifest
from hti_core.model import EvidenceRecord, TypedClaim, ValidationError
from hti_core.source_identity import V01SourceRecord
from hti_core.source_representation import SourceRepresentation
from hti_core.hashing import sha256_json
from hti_core.uncertainty import UncertaintyAssessment


class CompatibilityError(ValidationError):
    """Raised when input is not valid under released Version 0.1 behavior."""


def _require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CompatibilityError(f"{label} must be an object")
    return value


def _raise_audit_errors(errors: list[str], label: str) -> None:
    if errors:
        raise CompatibilityError(f"{label} is invalid: " + "; ".join(errors))


@dataclass(frozen=True)
class V01Checkpoint:
    """A validated, lossless view of one Version 0.1 evidence checkpoint."""

    _raw: Mapping[str, Any] = field(repr=False)
    evidence: tuple[EvidenceRecord, ...]
    claims: tuple[TypedClaim, ...]
    uncertainty_assessments: tuple[UncertaintyAssessment, ...]

    @classmethod
    def from_dict(cls, value: Any) -> "V01Checkpoint":
        source = _require_object(value, "v0.1 checkpoint")
        evidence_values = source.get("evidence", [])
        claim_values = source.get("claims", [])
        if not isinstance(evidence_values, list):
            raise CompatibilityError("v0.1 checkpoint evidence must be a list")
        if not isinstance(claim_values, list):
            raise CompatibilityError("v0.1 checkpoint claims must be a list")
        _raise_audit_errors(evidence_audit.audit_checkpoint(source), "v0.1 checkpoint")

        evidence = tuple(EvidenceRecord.from_dict(item) for item in evidence_values)
        evidence_ids = {item.evidence_id for item in evidence}
        if len(evidence_ids) != len(evidence):
            raise CompatibilityError("v0.1 checkpoint contains duplicate evidence ids")
        claims = tuple(
            TypedClaim.from_dict(
                item,
                evidence_ids,
                require_claim_type=False,
                allow_none_evidence_ids=True,
            )
            for item in claim_values
        )
        if len({item.claim_id for item in claims}) != len(claims):
            raise CompatibilityError("v0.1 checkpoint contains duplicate claim ids")
        try:
            uncertainty_assessments = tuple(
                UncertaintyAssessment.from_dict(item)
                for item in claim_values
                if "confidence" in item
            )
        except ValidationError as exc:
            raise CompatibilityError(str(exc)) from exc
        return cls(copy.deepcopy(source), evidence, claims, uncertainty_assessments)

    @property
    def work_id(self) -> str:
        return str(self._raw["work_id"])

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class V01SourceCheckpoint:
    """A validated, lossless view of one Version 0.1 source checkpoint."""

    _raw: Mapping[str, Any] = field(repr=False)
    sources: tuple[V01SourceRecord, ...]

    @classmethod
    def from_dict(cls, value: Any) -> "V01SourceCheckpoint":
        source = _require_object(value, "v0.1 source checkpoint")
        if not source.get("work_id"):
            raise CompatibilityError("v0.1 source checkpoint requires work_id")
        sources = source.get("sources", [])
        if not isinstance(sources, list) or any(not isinstance(item, dict) for item in sources):
            raise CompatibilityError("v0.1 source checkpoint sources must be a list of objects")
        _raise_audit_errors(evidence_audit.audit_sources(source), "v0.1 source checkpoint")
        try:
            adapted_sources = tuple(
                V01SourceRecord.from_dict(item, work_id=str(source["work_id"]))
                for item in sources
            )
        except ValidationError as exc:
            raise CompatibilityError(str(exc)) from exc
        return cls(copy.deepcopy(source), adapted_sources)

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class V01ResponsePlan:
    """A lossless response plan accepted by the Version 0.1 finalizer."""

    _raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, value: Any, checkpoint: Any) -> "V01ResponsePlan":
        source = _require_object(value, "v0.1 response plan")
        checkpoint_value = _require_object(checkpoint, "v0.1 checkpoint")
        try:
            finalize_response.validate_plan_shape(source, checkpoint_value)
        except finalize_response.FinalizationError as exc:
            raise CompatibilityError(str(exc)) from exc
        return cls(copy.deepcopy(source))

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class V01FinalizationReceipt:
    """A lossless Version 0.1 receipt with verified content bindings."""

    _raw: Mapping[str, Any] = field(repr=False)
    receipt: CompletionReceipt

    @classmethod
    def from_dict(
        cls,
        value: Any,
        *,
        response_text: Any,
        identity_manifest: Any,
    ) -> "V01FinalizationReceipt":
        source = _require_object(value, "v0.1 finalization receipt")
        try:
            receipt = CompletionReceipt.from_dict(source)
        except ValidationError as exc:
            raise CompatibilityError(str(exc)) from exc
        if receipt.status != "rendered":
            raise CompatibilityError("v0.1 finalization receipt status must be rendered")
        if receipt.renderer != finalize_response.RENDERER_ID:
            raise CompatibilityError(
                f"v0.1 finalization receipt renderer must be {finalize_response.RENDERER_ID}"
            )
        if receipt.schema_version != finalize_response.PLAN_SCHEMA_VERSION:
            raise CompatibilityError(
                "v0.1 finalization receipt schema_version must be "
                + finalize_response.PLAN_SCHEMA_VERSION
            )
        if not receipt.validates(response_text, identity_manifest):
            raise CompatibilityError("v0.1 finalization receipt bindings are invalid")
        return cls(copy.deepcopy(source), receipt)

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class V01FinalizedCheckpoint:
    """A lossless finalized checkpoint accepted by the Version 0.1 audit."""

    _raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, value: Any) -> "V01FinalizedCheckpoint":
        source = _require_object(value, "v0.1 finalized checkpoint")
        _raise_audit_errors(
            evidence_audit.audit_pre_output(source), "v0.1 finalized checkpoint"
        )
        return cls(copy.deepcopy(source))

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class V01PriorTranslationRepresentation:
    """A validated v0.1 translation plan exposed as a Phase 2 representation."""

    _raw_plan: Mapping[str, Any] = field(repr=False)
    representation: SourceRepresentation

    @classmethod
    def from_plan(
        cls,
        value: Any,
        checkpoint: Any,
        *,
        representation_id: str,
        source_id: str | None = None,
        language: str | None = None,
        evidence_root_id: str | None = None,
    ) -> "V01PriorTranslationRepresentation":
        plan = V01ResponsePlan.from_dict(value, checkpoint)
        plan_payload = plan.to_dict()
        checkpoint_payload = _require_object(checkpoint, "v0.1 checkpoint")
        representation_payload: dict[str, Any] = {
            "representation_id": representation_id,
            "representation_type": "PRIOR_V01_TRANSLATION",
            "supply_status": "SUPPLIED",
            "verification": "VERIFIED",
            "content": plan_payload["translation"]["text"],
            "provenance": {
                "origin": "validated_v01_response_plan",
                "work_id": checkpoint_payload.get("work_id"),
                "plan_sha256": sha256_json(plan_payload),
            },
            "derivations": [],
        }
        if source_id is not None:
            representation_payload["source_identity"] = {"source_id": source_id}
        if language is not None:
            representation_payload["language"] = language
        if evidence_root_id is not None:
            representation_payload["evidence_root_id"] = evidence_root_id
        try:
            representation = SourceRepresentation.from_dict(representation_payload)
        except ValidationError as exc:
            raise CompatibilityError(str(exc)) from exc
        return cls(copy.deepcopy(plan_payload), representation)

    def to_v01_plan(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw_plan))


def checkpoint_from_v01(value: Any) -> V01Checkpoint:
    return V01Checkpoint.from_dict(value)


def checkpoint_to_v01(value: V01Checkpoint) -> dict[str, Any]:
    if not isinstance(value, V01Checkpoint):
        raise CompatibilityError("checkpoint_to_v01 requires V01Checkpoint")
    return value.to_dict()


def source_checkpoint_from_v01(value: Any) -> V01SourceCheckpoint:
    return V01SourceCheckpoint.from_dict(value)


def source_checkpoint_to_v01(value: V01SourceCheckpoint) -> dict[str, Any]:
    if not isinstance(value, V01SourceCheckpoint):
        raise CompatibilityError("source_checkpoint_to_v01 requires V01SourceCheckpoint")
    return value.to_dict()


def response_plan_from_v01(value: Any, checkpoint: Any) -> V01ResponsePlan:
    return V01ResponsePlan.from_dict(value, checkpoint)


def response_plan_to_v01(value: V01ResponsePlan) -> dict[str, Any]:
    if not isinstance(value, V01ResponsePlan):
        raise CompatibilityError("response_plan_to_v01 requires V01ResponsePlan")
    return value.to_dict()


def finalization_receipt_from_v01(
    value: Any,
    *,
    response_text: Any,
    identity_manifest: Any,
) -> V01FinalizationReceipt:
    return V01FinalizationReceipt.from_dict(
        value,
        response_text=response_text,
        identity_manifest=identity_manifest,
    )


def finalization_receipt_to_v01(value: V01FinalizationReceipt) -> dict[str, Any]:
    if not isinstance(value, V01FinalizationReceipt):
        raise CompatibilityError(
            "finalization_receipt_to_v01 requires V01FinalizationReceipt"
        )
    return value.to_dict()


def finalized_checkpoint_from_v01(value: Any) -> V01FinalizedCheckpoint:
    return V01FinalizedCheckpoint.from_dict(value)


def finalized_checkpoint_to_v01(value: V01FinalizedCheckpoint) -> dict[str, Any]:
    if not isinstance(value, V01FinalizedCheckpoint):
        raise CompatibilityError(
            "finalized_checkpoint_to_v01 requires V01FinalizedCheckpoint"
        )
    return value.to_dict()


def prior_translation_from_v01_plan(
    value: Any,
    checkpoint: Any,
    *,
    representation_id: str,
    source_id: str | None = None,
    language: str | None = None,
    evidence_root_id: str | None = None,
) -> V01PriorTranslationRepresentation:
    return V01PriorTranslationRepresentation.from_plan(
        value,
        checkpoint,
        representation_id=representation_id,
        source_id=source_id,
        language=language,
        evidence_root_id=evidence_root_id,
    )


def prior_translation_plan_to_v01(
    value: V01PriorTranslationRepresentation,
) -> dict[str, Any]:
    if not isinstance(value, V01PriorTranslationRepresentation):
        raise CompatibilityError(
            "prior_translation_plan_to_v01 requires V01PriorTranslationRepresentation"
        )
    return value.to_v01_plan()


def uncertainty_from_v01(value: Any) -> UncertaintyAssessment:
    try:
        return UncertaintyAssessment.from_dict(value)
    except ValidationError as exc:
        raise CompatibilityError(str(exc)) from exc


def uncertainty_to_v01(value: UncertaintyAssessment) -> dict[str, Any]:
    if not isinstance(value, UncertaintyAssessment):
        raise CompatibilityError("uncertainty_to_v01 requires UncertaintyAssessment")
    return value.to_dict()


def audit_result_from_v01(value: Any) -> AuditResult:
    try:
        return AuditResult.from_v01_strings(value)
    except ValidationError as exc:
        raise CompatibilityError(str(exc)) from exc


def audit_result_to_v01(value: AuditResult) -> list[str]:
    if not isinstance(value, AuditResult):
        raise CompatibilityError("audit_result_to_v01 requires AuditResult")
    return value.to_v01_strings()


def manifest_from_v01(
    value: Any,
    *,
    kind: str | None = None,
    manifest_id: str | None = None,
) -> NeutralManifest:
    try:
        return NeutralManifest.from_dict(value, kind=kind, manifest_id=manifest_id)
    except ValidationError as exc:
        raise CompatibilityError(str(exc)) from exc


def manifest_to_v01(value: NeutralManifest) -> dict[str, Any]:
    if not isinstance(value, NeutralManifest):
        raise CompatibilityError("manifest_to_v01 requires NeutralManifest")
    return value.to_dict()
