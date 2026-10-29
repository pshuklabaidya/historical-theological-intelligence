"""Validated Argument Dossiers and internal proposition-relation graphs.

This module implements Phase 3 argument architecture only. It composes with
the Phase 2 representation registry for every source permission decision. It
does not propagate uncertainty or model historical, witness, reception,
confessional, or intellectual-genealogy relations.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

from .audit import AuditFinding, AuditResult
from .hashing import canonical_json, sha256_json
from .model import EVIDENCE_STATES, ValidationError
from .provenance import ProvenanceRecord
from .source_identity import SourceIdentity
from .source_representation import (
    RepresentationClaim,
    RepresentationRegistry,
    SourceRepresentation,
)
from .uncertainty import UncertaintyAssessment


class ArgumentArchitectureError(ValidationError):
    """Raised when candidate argument architecture fails closed."""


class PropositionType(str, Enum):
    TEXTUAL_READING = "TEXTUAL_READING"
    GRAMMATICAL_CLAIM = "GRAMMATICAL_CLAIM"
    LEXICAL_CLAIM = "LEXICAL_CLAIM"
    PHILOLOGICAL_CLAIM = "PHILOLOGICAL_CLAIM"
    SCRIPTURE_CROSS_REFERENCE = "SCRIPTURE_CROSS_REFERENCE"
    PATRISTIC_AUTHORITY = "PATRISTIC_AUTHORITY"
    MEDIEVAL_AUTHORITY = "MEDIEVAL_AUTHORITY"
    SCHOLASTIC_DISTINCTION = "SCHOLASTIC_DISTINCTION"
    THEOLOGICAL_PREMISE = "THEOLOGICAL_PREMISE"
    HISTORICAL_PREMISE = "HISTORICAL_PREMISE"
    INFERENCE = "INFERENCE"
    CONCLUSION = "CONCLUSION"
    APPLICATION = "APPLICATION"
    UNCLASSIFIED = "UNCLASSIFIED"


class ArgumentFunction(str, Enum):
    PREMISE = "PREMISE"
    SUPPORT = "SUPPORT"
    AUTHORITY = "AUTHORITY"
    QUALIFICATION = "QUALIFICATION"
    DISTINCTION = "DISTINCTION"
    OBJECTION = "OBJECTION"
    RESPONSE = "RESPONSE"
    INTERMEDIATE_CONCLUSION = "INTERMEDIATE_CONCLUSION"
    FINAL_CONCLUSION = "FINAL_CONCLUSION"
    APPLICATION = "APPLICATION"
    CONTEXT = "CONTEXT"
    UNCLASSIFIED = "UNCLASSIFIED"


class ExpressionMode(str, Enum):
    DIRECTLY_STATED = "DIRECTLY_STATED"
    NORMALIZED = "NORMALIZED"
    INFERRED = "INFERRED"
    RECONSTRUCTED = "RECONSTRUCTED"


class LogicalRelationType(str, Enum):
    SUPPORTS = "SUPPORTS"
    DEPENDS_ON = "DEPENDS_ON"
    QUALIFIES = "QUALIFIES"
    DISTINGUISHES = "DISTINGUISHES"
    CONTRADICTS = "CONTRADICTS"
    INTERPRETS = "INTERPRETS"
    PRESUPPOSES = "PRESUPPOSES"
    CONCLUDES_FROM = "CONCLUDES_FROM"
    REQUIRES = "REQUIRES"
    DOES_NOT_SUPPORT = "DOES_NOT_SUPPORT"
    UNCLASSIFIED = "UNCLASSIFIED"


class StructuralStatus(str, Enum):
    ESTABLISHED = "ESTABLISHED"
    PROVISIONAL = "PROVISIONAL"
    UNRESOLVED = "UNRESOLVED"


class InterpretationStatus(str, Enum):
    PROPOSED = "PROPOSED"
    PROVISIONALLY_PREFERRED = "PROVISIONALLY_PREFERRED"
    UNRESOLVED = "UNRESOLVED"
    REJECTED = "REJECTED"


class UnresolvedQuestionType(str, Enum):
    PROPOSITION_BOUNDARY = "PROPOSITION_BOUNDARY"
    PROPOSITION_TYPE = "PROPOSITION_TYPE"
    RELATION_DIRECTION = "RELATION_DIRECTION"
    SOURCE_ATTRIBUTION = "SOURCE_ATTRIBUTION"
    ARGUMENT_FUNCTION = "ARGUMENT_FUNCTION"
    SOURCE_SPAN = "SOURCE_SPAN"
    INTERPRETATION_DISCRIMINATION = "INTERPRETATION_DISCRIMINATION"
    OTHER = "OTHER"


class StructuralDecisionType(str, Enum):
    PROPOSITION_CONSTRUCTION = "PROPOSITION_CONSTRUCTION"
    RELATION_CONSTRUCTION = "RELATION_CONSTRUCTION"
    INTERPRETATION_CONSTRUCTION = "INTERPRETATION_CONSTRUCTION"
    RECONSTRUCTION = "RECONSTRUCTION"
    CLASSIFICATION = "CLASSIFICATION"
    BOUNDARY = "BOUNDARY"
    OTHER = "OTHER"


PROPOSITION_TYPES = frozenset(item.value for item in PropositionType)
ARGUMENT_FUNCTIONS = frozenset(item.value for item in ArgumentFunction)
LOGICAL_RELATION_TYPES = frozenset(item.value for item in LogicalRelationType)

HISTORICAL_RELATION_TYPES = frozenset(
    {
        "DIRECT_QUOTATION",
        "DIRECT_DEPENDENCE",
        "MEDIATED_DEPENDENCE",
        "SHARED_SOURCE",
        "INHERITED_COMMONPLACE",
        "CONCEPTUAL_AFFINITY",
        "INDEPENDENT_CONVERGENCE",
        "RECEPTION",
        "TRANSFORMATION",
        "REVIVAL",
        "REJECTION",
    }
)

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_FORBIDDEN_DOSSIER_FIELDS = frozenset(
    {
        "historical_relations",
        "confessional_relations",
        "uncertainty_propagation",
        "lineage",
        "reception_relations",
        "source_transmission",
    }
)
_DIRECT_OBSERVATION_STATES = frozenset(
    {"PAGE_VISIBLE", "PAGE_PROBABLE", "PAGE_UNCERTAIN", "WITNESS_READING"}
)


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ArgumentArchitectureError(f"{label} must be an object")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ArgumentArchitectureError(f"{label} must be a non-empty string")
    return value


def _identifier(value: Any, label: str) -> str:
    value = _text(value, label)
    if not _ID.fullmatch(value):
        raise ArgumentArchitectureError(f"{label} must be a stable identifier")
    return value


def _enum(value: Any, kind: type[Enum], label: str) -> str:
    if not isinstance(value, str):
        raise ArgumentArchitectureError(f"{label} must be a declared string value")
    try:
        kind(value)
    except ValueError as exc:
        raise ArgumentArchitectureError(f"invalid {label} {value!r}") from exc
    return value


def _ordered_ids(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ArgumentArchitectureError(f"{label} must be an ordered list")
    ids = tuple(_identifier(item, f"{label} item") for item in value)
    if len(ids) != len(set(ids)):
        raise ArgumentArchitectureError(f"{label} must not contain duplicate ids")
    return ids


def _optional_uncertainty(value: Any, label: str) -> None:
    if value is not None:
        try:
            UncertaintyAssessment.from_dict(value)
        except ValidationError as exc:
            raise ArgumentArchitectureError(f"invalid {label}: {exc}") from exc


def _reject_numeric_confidence(value: Any) -> None:
    """Keep Phase 3 qualitative and refuse Phase 4-style probability fields."""

    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in {
                "probability",
                "confidence_probability",
                "confidence_score",
                "propagated_confidence",
            }:
                raise ArgumentArchitectureError(
                    "numerical or propagated confidence is outside Phase 3"
                )
            _reject_numeric_confidence(item)
    elif isinstance(value, list):
        for item in value:
            _reject_numeric_confidence(item)


@dataclass(frozen=True)
class PropositionSourceLink:
    """One representation-licensed source basis for a proposition."""

    _raw: Mapping[str, Any] = field(repr=False)
    decision: Mapping[str, Any] = field(repr=False)
    representation_type: str
    supply_status: str
    ancestry: tuple[str, ...]
    evidence_roots: tuple[str, ...]

    @classmethod
    def from_dict(
        cls,
        value: Any,
        registry: RepresentationRegistry,
        representation_scope: Iterable[str],
    ) -> "PropositionSourceLink":
        raw = _object(value, "proposition source link")
        representation_id = _identifier(raw.get("representation_id"), "representation_id")
        if representation_id not in set(representation_scope):
            raise ArgumentArchitectureError(
                f"representation {representation_id!r} is outside dossier representation_scope"
            )
        claim = _enum(raw.get("representation_claim"), RepresentationClaim, "representation_claim")
        provenance = raw.get("provenance")
        if provenance is None:
            raise ArgumentArchitectureError("proposition source link requires provenance")
        ProvenanceRecord.from_dict(provenance)
        source_span = raw.get("source_span")
        if source_span is not None and not isinstance(source_span, (str, dict)):
            raise ArgumentArchitectureError("source_span must be text or an object")
        if isinstance(source_span, str) and not source_span.strip():
            raise ArgumentArchitectureError("source_span text must be non-empty")
        evidence_state = raw.get("evidence_state")
        if evidence_state is not None and evidence_state not in EVIDENCE_STATES:
            raise ArgumentArchitectureError(
                f"invalid proposition source-link evidence_state {evidence_state!r}"
            )
        _optional_uncertainty(raw.get("uncertainty"), "source-link uncertainty")
        try:
            decision = registry.require(representation_id, claim)
            representation = registry.get(representation_id)
        except ValidationError as exc:
            raise ArgumentArchitectureError(
                f"representation licensing failed for {representation_id}: {exc}"
            ) from exc
        if evidence_state is not None and evidence_state.startswith("PAGE_"):
            if representation.representation_type != "PAGE_IMAGE":
                raise ArgumentArchitectureError(
                    "page evidence states require a PAGE_IMAGE representation"
                )
            if (
                representation.evidence_state is not None
                and evidence_state != representation.evidence_state
            ):
                raise ArgumentArchitectureError(
                    "source-link page state must match the representation page state"
                )
        return cls(
            copy.deepcopy(raw),
            decision.to_dict(),
            representation.representation_type,
            representation.supply_status,
            registry.ancestry(representation_id),
            registry.evidence_roots(representation_id),
        )

    @property
    def representation_id(self) -> str:
        return str(self._raw["representation_id"])

    @property
    def representation_claim(self) -> str:
        return str(self._raw["representation_claim"])

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))

    def audit_view(self) -> dict[str, Any]:
        return {
            "representation_id": self.representation_id,
            "representation_type": self.representation_type,
            "supply_status": self.supply_status,
            "ancestry": list(self.ancestry),
            "evidence_roots": list(self.evidence_roots),
            "license_decision": copy.deepcopy(dict(self.decision)),
        }


@dataclass(frozen=True)
class Proposition:
    """Typed proposition whose content and argument function remain separate."""

    _raw: Mapping[str, Any] = field(repr=False)
    source_links: tuple[PropositionSourceLink, ...] = field(repr=False)

    @classmethod
    def from_dict(
        cls,
        value: Any,
        dossier_id: str,
        registry: RepresentationRegistry,
        representation_scope: Iterable[str],
    ) -> "Proposition":
        raw = _object(value, "proposition")
        proposition_id = _identifier(raw.get("proposition_id"), "proposition_id")
        if raw.get("dossier_id") != dossier_id:
            raise ArgumentArchitectureError(
                f"proposition {proposition_id} has invalid dossier ownership"
            )
        _text(raw.get("content"), f"proposition {proposition_id} content")
        _enum(raw.get("proposition_type"), PropositionType, "proposition_type")
        functions = raw.get("argument_functions")
        if not isinstance(functions, list) or not functions:
            raise ArgumentArchitectureError(
                f"proposition {proposition_id} requires argument_functions"
            )
        parsed_functions = [
            _enum(item, ArgumentFunction, "argument_function") for item in functions
        ]
        if len(parsed_functions) != len(set(parsed_functions)):
            raise ArgumentArchitectureError("argument_functions must not contain duplicates")
        mode = _enum(raw.get("expression_mode"), ExpressionMode, "expression_mode")
        evidence_state = raw.get("evidence_state")
        if evidence_state is not None and evidence_state not in EVIDENCE_STATES:
            raise ArgumentArchitectureError(
                f"proposition {proposition_id} has invalid evidence_state {evidence_state!r}"
            )
        if mode == ExpressionMode.RECONSTRUCTED.value and evidence_state in _DIRECT_OBSERVATION_STATES:
            raise ArgumentArchitectureError(
                "reconstructed proposition cannot carry a direct-observation evidence state"
            )
        provenance = raw.get("provenance")
        if provenance is None:
            raise ArgumentArchitectureError(f"proposition {proposition_id} requires provenance")
        ProvenanceRecord.from_dict(provenance)
        _optional_uncertainty(raw.get("uncertainty"), "proposition uncertainty")
        raw_links = raw.get("source_links")
        if not isinstance(raw_links, list) or not raw_links:
            raise ArgumentArchitectureError(
                f"proposition {proposition_id} requires at least one source link"
            )
        links = tuple(
            PropositionSourceLink.from_dict(item, registry, representation_scope)
            for item in raw_links
        )
        return cls(copy.deepcopy(raw), links)

    @property
    def proposition_id(self) -> str:
        return str(self._raw["proposition_id"])

    @property
    def dossier_id(self) -> str:
        return str(self._raw["dossier_id"])

    @property
    def proposition_type(self) -> str:
        return str(self._raw["proposition_type"])

    @property
    def expression_mode(self) -> str:
        return str(self._raw["expression_mode"])

    @property
    def argument_functions(self) -> tuple[str, ...]:
        return tuple(self._raw["argument_functions"])

    def to_dict(self) -> dict[str, Any]:
        value = copy.deepcopy(dict(self._raw))
        value["source_links"] = [item.to_dict() for item in self.source_links]
        return value

    def source_audit(self) -> list[dict[str, Any]]:
        return [item.audit_view() for item in self.source_links]


@dataclass(frozen=True)
class PropositionRelation:
    """One internal logical edge, never a historical or witness relation."""

    _raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, value: Any, dossier_id: str) -> "PropositionRelation":
        raw = _object(value, "proposition relation")
        relation_id = _identifier(raw.get("relation_id"), "relation_id")
        if raw.get("dossier_id") != dossier_id:
            raise ArgumentArchitectureError(
                f"relation {relation_id} has invalid dossier ownership"
            )
        relation_type = raw.get("relation_type")
        if relation_type in HISTORICAL_RELATION_TYPES:
            raise ArgumentArchitectureError(
                f"relation {relation_id} uses a future Historical Relation Graph type"
            )
        _enum(relation_type, LogicalRelationType, "logical relation type")
        _identifier(raw.get("source_proposition_id"), "source_proposition_id")
        _identifier(raw.get("target_proposition_id"), "target_proposition_id")
        _enum(raw.get("status"), StructuralStatus, "relation status")
        _text(raw.get("construction_basis"), f"relation {relation_id} construction_basis")
        provenance = raw.get("provenance")
        if provenance is None:
            raise ArgumentArchitectureError(f"relation {relation_id} requires provenance")
        ProvenanceRecord.from_dict(provenance)
        _optional_uncertainty(raw.get("uncertainty"), "relation uncertainty")
        return cls(copy.deepcopy(raw))

    @property
    def relation_id(self) -> str:
        return str(self._raw["relation_id"])

    @property
    def source_proposition_id(self) -> str:
        return str(self._raw["source_proposition_id"])

    @property
    def target_proposition_id(self) -> str:
        return str(self._raw["target_proposition_id"])

    @property
    def relation_type(self) -> str:
        return str(self._raw["relation_type"])

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class Counterevidence:
    _raw: Mapping[str, Any] = field(repr=False)
    source_links: tuple[PropositionSourceLink, ...] = field(repr=False)

    @classmethod
    def from_dict(
        cls,
        value: Any,
        dossier_id: str,
        registry: RepresentationRegistry,
        representation_scope: Iterable[str],
    ) -> "Counterevidence":
        raw = _object(value, "counterevidence")
        counterevidence_id = _identifier(raw.get("counterevidence_id"), "counterevidence_id")
        if raw.get("dossier_id") != dossier_id:
            raise ArgumentArchitectureError(
                f"counterevidence {counterevidence_id} has invalid dossier ownership"
            )
        _text(raw.get("content"), f"counterevidence {counterevidence_id} content")
        provenance = raw.get("provenance")
        if provenance is None:
            raise ArgumentArchitectureError(
                f"counterevidence {counterevidence_id} requires provenance"
            )
        ProvenanceRecord.from_dict(provenance)
        links_value = raw.get("source_links", [])
        if not isinstance(links_value, list):
            raise ArgumentArchitectureError("counterevidence source_links must be a list")
        links = tuple(
            PropositionSourceLink.from_dict(item, registry, representation_scope)
            for item in links_value
        )
        for key in ("proposition_ids", "relation_ids", "interpretation_ids"):
            _ordered_ids(raw.get(key, []), f"counterevidence {key}")
        return cls(copy.deepcopy(raw), links)

    @property
    def counterevidence_id(self) -> str:
        return str(self._raw["counterevidence_id"])

    def to_dict(self) -> dict[str, Any]:
        value = copy.deepcopy(dict(self._raw))
        value["source_links"] = [item.to_dict() for item in self.source_links]
        return value


@dataclass(frozen=True)
class UnresolvedQuestion:
    _raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, value: Any, dossier_id: str) -> "UnresolvedQuestion":
        raw = _object(value, "unresolved question")
        question_id = _identifier(raw.get("question_id"), "question_id")
        if raw.get("dossier_id") != dossier_id:
            raise ArgumentArchitectureError(
                f"unresolved question {question_id} has invalid dossier ownership"
            )
        _enum(raw.get("question_type"), UnresolvedQuestionType, "question_type")
        _text(raw.get("question"), f"unresolved question {question_id}")
        _ordered_ids(raw.get("subject_ids", []), "unresolved question subject_ids")
        provenance = raw.get("provenance")
        if provenance is None:
            raise ArgumentArchitectureError(
                f"unresolved question {question_id} requires provenance"
            )
        ProvenanceRecord.from_dict(provenance)
        return cls(copy.deepcopy(raw))

    @property
    def question_id(self) -> str:
        return str(self._raw["question_id"])

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class CompetingInterpretation:
    _raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, value: Any, dossier_id: str) -> "CompetingInterpretation":
        raw = _object(value, "competing interpretation")
        interpretation_id = _identifier(raw.get("interpretation_id"), "interpretation_id")
        if raw.get("dossier_id") != dossier_id:
            raise ArgumentArchitectureError(
                f"interpretation {interpretation_id} has invalid dossier ownership"
            )
        _text(raw.get("label"), f"interpretation {interpretation_id} label")
        _enum(raw.get("status"), InterpretationStatus, "interpretation status")
        _text(raw.get("rationale"), f"interpretation {interpretation_id} rationale")
        _ordered_ids(raw.get("proposition_ids", []), "interpretation proposition_ids")
        _ordered_ids(raw.get("relation_ids", []), "interpretation relation_ids")
        _ordered_ids(raw.get("counterevidence_ids", []), "interpretation counterevidence_ids")
        _ordered_ids(raw.get("unresolved_question_ids", []), "interpretation unresolved_question_ids")
        provenance = raw.get("provenance")
        if provenance is None:
            raise ArgumentArchitectureError(
                f"interpretation {interpretation_id} requires provenance"
            )
        ProvenanceRecord.from_dict(provenance)
        return cls(copy.deepcopy(raw))

    @property
    def interpretation_id(self) -> str:
        return str(self._raw["interpretation_id"])

    def ids(self, field_name: str) -> tuple[str, ...]:
        return tuple(self._raw.get(field_name, []))

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class StructuralAuditRecord:
    _raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, value: Any, dossier_id: str) -> "StructuralAuditRecord":
        raw = _object(value, "structural audit record")
        _identifier(raw.get("audit_id"), "audit_id")
        if raw.get("dossier_id") != dossier_id:
            raise ArgumentArchitectureError("structural audit record has invalid dossier ownership")
        _identifier(raw.get("subject_id"), "structural audit subject_id")
        _enum(raw.get("decision_type"), StructuralDecisionType, "structural decision type")
        _text(raw.get("rationale"), "structural audit rationale")
        provenance = raw.get("provenance")
        if provenance is None:
            raise ArgumentArchitectureError("structural audit record requires provenance")
        ProvenanceRecord.from_dict(provenance)
        return cls(copy.deepcopy(raw))

    @property
    def audit_id(self) -> str:
        return str(self._raw["audit_id"])

    @property
    def subject_id(self) -> str:
        return str(self._raw["subject_id"])

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


def _unique(items: Iterable[Any], attribute: str, label: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in items:
        identity = getattr(item, attribute)
        if identity in result:
            raise ArgumentArchitectureError(f"duplicate {label} {identity}")
        result[identity] = item
    return result


@dataclass(frozen=True)
class PropositionRelationGraph:
    """Deterministic dossier-local view of internal argument architecture."""

    dossier_id: str
    propositions: tuple[Proposition, ...]
    relations: tuple[PropositionRelation, ...]

    def __post_init__(self) -> None:
        _identifier(self.dossier_id, "graph dossier_id")
        proposition_ids = {item.proposition_id for item in self.propositions}
        if len(proposition_ids) != len(self.propositions):
            raise ArgumentArchitectureError("graph proposition ids must be unique")
        relation_ids = {item.relation_id for item in self.relations}
        if len(relation_ids) != len(self.relations):
            raise ArgumentArchitectureError("graph relation ids must be unique")
        for proposition in self.propositions:
            if proposition.dossier_id != self.dossier_id:
                raise ArgumentArchitectureError("graph contains a cross-dossier proposition")
        for relation in self.relations:
            if relation._raw.get("dossier_id") != self.dossier_id:
                raise ArgumentArchitectureError("graph contains a cross-dossier relation")
            if relation.source_proposition_id not in proposition_ids:
                raise ArgumentArchitectureError("graph contains a dangling source endpoint")
            if relation.target_proposition_id not in proposition_ids:
                raise ArgumentArchitectureError("graph contains a dangling target endpoint")

    def to_dict(self) -> dict[str, Any]:
        return {
            "dossier_id": self.dossier_id,
            "propositions": [
                item.to_dict()
                for item in sorted(self.propositions, key=lambda x: x.proposition_id)
            ],
            "relations": [
                item.to_dict()
                for item in sorted(self.relations, key=lambda x: x.relation_id)
            ],
        }

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())


@dataclass(frozen=True)
class ArgumentDossier:
    """One isolated historically located argument or argument-component."""

    _raw: Mapping[str, Any] = field(repr=False)
    _registry: RepresentationRegistry = field(repr=False)
    propositions: tuple[Proposition, ...]
    relations: tuple[PropositionRelation, ...]
    interpretations: tuple[CompetingInterpretation, ...]
    counterevidence: tuple[Counterevidence, ...]
    unresolved_questions: tuple[UnresolvedQuestion, ...]
    audit_trail: tuple[StructuralAuditRecord, ...]

    @classmethod
    def from_dict(
        cls, value: Any, registry: RepresentationRegistry
    ) -> "ArgumentDossier":
        raw = _object(value, "argument dossier")
        _reject_numeric_confidence(raw)
        if raw.get("schema_version") != "1":
            raise ArgumentArchitectureError("argument dossier schema_version must be 1")
        forbidden = _FORBIDDEN_DOSSIER_FIELDS & set(raw)
        if forbidden:
            raise ArgumentArchitectureError(
                "Phase 3 dossier contains later-phase fields: " + ", ".join(sorted(forbidden))
            )
        dossier_id = _identifier(raw.get("dossier_id"), "dossier_id")
        _identifier(raw.get("argument_id"), "argument_id")
        work_id = raw.get("work_id")
        if work_id is not None:
            _identifier(work_id, "work_id")
        anchor_id = _identifier(raw.get("anchor_representation_id"), "anchor_representation_id")
        scope = _ordered_ids(raw.get("representation_scope"), "representation_scope")
        if anchor_id not in scope:
            raise ArgumentArchitectureError("anchor representation must be in representation_scope")
        for representation_id in scope:
            representation = registry.get(representation_id)
            identity = representation.source_identity
            if (
                work_id is not None
                and identity is not None
                and identity.work_id is not None
                and identity.work_id != work_id
            ):
                raise ArgumentArchitectureError(
                    f"representation {representation_id} belongs to another work"
                )
        anchor = registry.get(anchor_id)
        if raw.get("source_representation_type") != anchor.representation_type:
            raise ArgumentArchitectureError(
                "source_representation_type must match the anchor representation"
            )
        for label in ("language", "date", "historical_context"):
            item = raw.get(label)
            if item is not None and not isinstance(item, (str, dict)):
                raise ArgumentArchitectureError(f"{label} must be text or an object")
            if isinstance(item, str) and not item.strip():
                raise ArgumentArchitectureError(f"{label} text must be non-empty")
        source_identifications = raw.get("source_identifications", [])
        if not isinstance(source_identifications, list):
            raise ArgumentArchitectureError("source_identifications must be a list")
        for identity in source_identifications:
            SourceIdentity.from_dict(identity)

        raw_propositions = raw.get("propositions")
        raw_relations = raw.get("relations")
        raw_interpretations = raw.get("interpretations", [])
        raw_counterevidence = raw.get("counterevidence", [])
        raw_questions = raw.get("unresolved_questions", [])
        raw_audit = raw.get("audit_trail")
        for items, label in (
            (raw_propositions, "propositions"),
            (raw_relations, "relations"),
            (raw_interpretations, "interpretations"),
            (raw_counterevidence, "counterevidence"),
            (raw_questions, "unresolved_questions"),
            (raw_audit, "audit_trail"),
        ):
            if not isinstance(items, list):
                raise ArgumentArchitectureError(f"{label} must be an ordered list")
        if not raw_propositions:
            raise ArgumentArchitectureError("argument dossier requires at least one proposition")

        propositions = tuple(
            Proposition.from_dict(item, dossier_id, registry, scope)
            for item in raw_propositions
        )
        relations = tuple(
            PropositionRelation.from_dict(item, dossier_id) for item in raw_relations
        )
        counterevidence = tuple(
            Counterevidence.from_dict(item, dossier_id, registry, scope)
            for item in raw_counterevidence
        )
        questions = tuple(
            UnresolvedQuestion.from_dict(item, dossier_id) for item in raw_questions
        )
        interpretations = tuple(
            CompetingInterpretation.from_dict(item, dossier_id)
            for item in raw_interpretations
        )
        audit_trail = tuple(
            StructuralAuditRecord.from_dict(item, dossier_id) for item in raw_audit
        )

        proposition_by_id = _unique(propositions, "proposition_id", "proposition id")
        relation_by_id = _unique(relations, "relation_id", "relation id")
        interpretation_by_id = _unique(
            interpretations, "interpretation_id", "interpretation id"
        )
        counterevidence_by_id = _unique(
            counterevidence, "counterevidence_id", "counterevidence id"
        )
        question_by_id = _unique(questions, "question_id", "question id")
        audit_by_id = _unique(audit_trail, "audit_id", "audit id")
        del audit_by_id

        for relation in relations:
            if relation.source_proposition_id not in proposition_by_id:
                raise ArgumentArchitectureError(
                    f"relation {relation.relation_id} has dangling source endpoint"
                )
            if relation.target_proposition_id not in proposition_by_id:
                raise ArgumentArchitectureError(
                    f"relation {relation.relation_id} has dangling target endpoint"
                )

        for interpretation in interpretations:
            for item_id in interpretation.ids("proposition_ids"):
                if item_id not in proposition_by_id:
                    raise ArgumentArchitectureError(
                        f"interpretation {interpretation.interpretation_id} references missing proposition"
                    )
            for item_id in interpretation.ids("relation_ids"):
                if item_id not in relation_by_id:
                    raise ArgumentArchitectureError(
                        f"interpretation {interpretation.interpretation_id} references missing relation"
                    )
            for item_id in interpretation.ids("counterevidence_ids"):
                if item_id not in counterevidence_by_id:
                    raise ArgumentArchitectureError(
                        f"interpretation {interpretation.interpretation_id} references missing counterevidence"
                    )
            for item_id in interpretation.ids("unresolved_question_ids"):
                if item_id not in question_by_id:
                    raise ArgumentArchitectureError(
                        f"interpretation {interpretation.interpretation_id} references missing question"
                    )

        subject_ids = (
            set(proposition_by_id)
            | set(relation_by_id)
            | set(interpretation_by_id)
            | set(counterevidence_by_id)
            | set(question_by_id)
        )
        for item in counterevidence:
            for field_name, allowed in (
                ("proposition_ids", proposition_by_id),
                ("relation_ids", relation_by_id),
                ("interpretation_ids", interpretation_by_id),
            ):
                for item_id in item._raw.get(field_name, []):
                    if item_id not in allowed:
                        raise ArgumentArchitectureError(
                            f"counterevidence {item.counterevidence_id} references missing subject"
                        )
        for question in questions:
            for item_id in question._raw.get("subject_ids", []):
                if item_id not in subject_ids:
                    raise ArgumentArchitectureError(
                        f"unresolved question {question.question_id} references missing subject"
                    )
        for audit in audit_trail:
            if audit.subject_id not in subject_ids:
                raise ArgumentArchitectureError(
                    f"audit {audit.audit_id} references missing subject"
                )
        covered = {item.subject_id for item in audit_trail}
        required_audit = set(proposition_by_id) | set(relation_by_id) | set(interpretation_by_id)
        missing_audit = required_audit - covered
        if missing_audit:
            raise ArgumentArchitectureError(
                "major structural decisions lack audit records: "
                + ", ".join(sorted(missing_audit))
            )

        return cls(
            copy.deepcopy(raw),
            registry,
            propositions,
            relations,
            interpretations,
            counterevidence,
            questions,
            audit_trail,
        )

    @property
    def dossier_id(self) -> str:
        return str(self._raw["dossier_id"])

    @property
    def argument_id(self) -> str:
        return str(self._raw["argument_id"])

    @property
    def anchor_representation_id(self) -> str:
        return str(self._raw["anchor_representation_id"])

    @property
    def anchor_representation(self) -> SourceRepresentation:
        return self._registry.get(self.anchor_representation_id)

    @property
    def graph(self) -> PropositionRelationGraph:
        return PropositionRelationGraph(self.dossier_id, self.propositions, self.relations)

    def proposition(self, proposition_id: str) -> Proposition:
        for proposition in self.propositions:
            if proposition.proposition_id == proposition_id:
                return proposition
        raise ArgumentArchitectureError(f"unknown proposition {proposition_id!r}")

    def shares_source_ancestry(self, left_id: str, right_id: str) -> bool:
        left = self.proposition(left_id)
        right = self.proposition(right_id)
        return any(
            self._registry.shares_ancestry(a.representation_id, b.representation_id)
            for a in left.source_links
            for b in right.source_links
        )

    def to_dict(self) -> dict[str, Any]:
        value = copy.deepcopy(dict(self._raw))
        value["propositions"] = [
            item.to_dict() for item in sorted(self.propositions, key=lambda x: x.proposition_id)
        ]
        value["relations"] = [
            item.to_dict() for item in sorted(self.relations, key=lambda x: x.relation_id)
        ]
        value["interpretations"] = [
            item.to_dict()
            for item in sorted(self.interpretations, key=lambda x: x.interpretation_id)
        ]
        value["counterevidence"] = [
            item.to_dict()
            for item in sorted(self.counterevidence, key=lambda x: x.counterevidence_id)
        ]
        value["unresolved_questions"] = [
            item.to_dict()
            for item in sorted(self.unresolved_questions, key=lambda x: x.question_id)
        ]
        value["audit_trail"] = [
            item.to_dict() for item in sorted(self.audit_trail, key=lambda x: x.audit_id)
        ]
        return value

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())

    def sha256(self) -> str:
        return sha256_json(self.to_dict())


@dataclass(frozen=True)
class DossierCollection:
    """Validated collection that prevents accidental cross-dossier reuse."""

    dossiers: tuple[ArgumentDossier, ...]

    @classmethod
    def from_dict(
        cls, value: Any, registry: RepresentationRegistry
    ) -> "DossierCollection":
        raw = _object(value, "dossier collection")
        if raw.get("schema_version") != "1":
            raise ArgumentArchitectureError("dossier collection schema_version must be 1")
        entries = raw.get("dossiers")
        if not isinstance(entries, list):
            raise ArgumentArchitectureError("dossier collection dossiers must be a list")
        dossiers = tuple(ArgumentDossier.from_dict(item, registry) for item in entries)
        _unique(dossiers, "dossier_id", "dossier id")
        seen: dict[str, str] = {}
        for dossier in dossiers:
            for item in (*dossier.propositions, *dossier.relations, *dossier.interpretations):
                identifier = (
                    getattr(item, "proposition_id", None)
                    or getattr(item, "relation_id", None)
                    or getattr(item, "interpretation_id", None)
                )
                if identifier in seen:
                    raise ArgumentArchitectureError(
                        f"structural id {identifier} is reused across dossiers"
                    )
                seen[identifier] = dossier.dossier_id
        return cls(dossiers)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1",
            "dossiers": [
                item.to_dict() for item in sorted(self.dossiers, key=lambda x: x.dossier_id)
            ],
        }


@dataclass(frozen=True)
class ArgumentConstructionResult:
    dossier: ArgumentDossier
    audit: AuditResult

    def __post_init__(self) -> None:
        if not self.audit.passed:
            raise ArgumentArchitectureError("failed audit cannot produce a dossier result")

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "validated",
            "dossier": self.dossier.to_dict(),
            "dossier_sha256": self.dossier.sha256(),
            "audit": {"status": self.audit.status, "findings": self.audit.to_v01_strings()},
        }


def audit_argument_dossier(
    value: Any, registry: RepresentationRegistry
) -> AuditResult:
    """Return one deterministic blocking finding for malformed architecture."""

    try:
        ArgumentDossier.from_dict(value, registry)
    except ValidationError as exc:
        return AuditResult((AuditFinding("ARGUMENT_DOSSIER_INVALID", str(exc)),))
    return AuditResult()


def construct_argument_dossier(
    value: Any, registry: RepresentationRegistry
) -> ArgumentConstructionResult:
    """Validate structured decomposition before exposing an accepted result."""

    audit = audit_argument_dossier(value, registry)
    if not audit.passed:
        raise ArgumentArchitectureError(audit.findings[0].to_v01_string())
    dossier = ArgumentDossier.from_dict(value, registry)
    return ArgumentConstructionResult(dossier, audit)
