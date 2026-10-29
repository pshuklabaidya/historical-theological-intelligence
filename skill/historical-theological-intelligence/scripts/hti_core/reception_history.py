"""Phase 8 reception, mutation, and bounded conceptual-history analysis.

The module consumes identifiers and validated views from Phases 3-7. It does
not mutate those layers, create historical edges, or provide confessional,
novelty, controversy, or whole-work engines.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

from .audit import AuditFinding, AuditResult
from .hashing import canonical_json, sha256_json
from .historical_relations import (
    ACTIVE_CLAIM_STATES,
    HistoricalRelationGraph,
    HistoricalRelationType,
)
from .model import ValidationError
from .provenance import ProvenanceRecord


class ReceptionHistoryError(ValidationError):
    """Raised when a Phase 8 claim fails closed."""


class MutationType(str, Enum):
    RETAINS = "RETAINS"
    REFORMULATES = "REFORMULATES"
    NARROWS = "NARROWS"
    BROADENS = "BROADENS"
    RELOCATES = "RELOCATES"
    REJECTS = "REJECTS"
    REVIVES = "REVIVES"
    COMBINES = "COMBINES"
    ABANDONS = "ABANDONS"


class ComparisonMode(str, Enum):
    DIACHRONIC = "DIACHRONIC"
    SYNCHRONIC = "SYNCHRONIC"


class ComparisonDimension(str, Enum):
    LEXICAL_FORM = "LEXICAL_FORM"
    PROPOSITIONAL_CONTENT = "PROPOSITIONAL_CONTENT"
    SEMANTIC_SCOPE = "SEMANTIC_SCOPE"
    SEMANTIC_FIELD = "SEMANTIC_FIELD"
    DISTINCTION_STRUCTURE = "DISTINCTION_STRUCTURE"
    ARGUMENT_FUNCTION = "ARGUMENT_FUNCTION"
    DOCTRINAL_CONTEXT = "DOCTRINAL_CONTEXT"
    AUTHORITY_STRUCTURE = "AUTHORITY_STRUCTURE"
    APPLICATION_FUNCTION = "APPLICATION_FUNCTION"


class ContinuityState(str, Enum):
    CONTINUOUS = "CONTINUOUS"
    SUBSTANTIALLY_CONTINUOUS = "SUBSTANTIALLY_CONTINUOUS"
    PARTIALLY_CONTINUOUS = "PARTIALLY_CONTINUOUS"
    DISCONTINUOUS = "DISCONTINUOUS"
    UNRESOLVED = "UNRESOLVED"


class LexicalRelation(str, Enum):
    SAME_TERM = "SAME_TERM"
    CHANGED_TERM = "CHANGED_TERM"
    CROSS_LANGUAGE_EQUIVALENT = "CROSS_LANGUAGE_EQUIVALENT"
    NO_RELEVANT_TERM = "NO_RELEVANT_TERM"
    UNRESOLVED = "UNRESOLVED"


class TerminologyStatus(str, Enum):
    HISTORICAL_TERMINOLOGY = "HISTORICAL_TERMINOLOGY"
    RECONSTRUCTED_CONCEPTUAL_CONTENT = "RECONSTRUCTED_CONCEPTUAL_CONTENT"
    LATER_ANALYTICAL_CATEGORY = "LATER_ANALYTICAL_CATEGORY"
    LATER_ANALOGY = "LATER_ANALOGY"


class MutationAgent(str, Enum):
    ORIGINAL_AUTHOR = "ORIGINAL_AUTHOR"
    TRANSLATOR = "TRANSLATOR"
    INTERMEDIARY = "INTERMEDIARY"
    RECIPIENT = "RECIPIENT"
    UNRESOLVED = "UNRESOLVED"


class ReceptionEvidenceType(str, Enum):
    PROPOSITION_COMPARISON = "PROPOSITION_COMPARISON"
    TERMINOLOGY_COMPARISON = "TERMINOLOGY_COMPARISON"
    SEMANTIC_FIELD = "SEMANTIC_FIELD"
    ARGUMENT_FUNCTION = "ARGUMENT_FUNCTION"
    DOCTRINAL_CONTEXT = "DOCTRINAL_CONTEXT"
    HISTORICAL_ENGAGEMENT = "HISTORICAL_ENGAGEMENT"
    EXPLICIT_REJECTION = "EXPLICIT_REJECTION"
    EXPLICIT_ABANDONMENT = "EXPLICIT_ABANDONMENT"
    TRANSLATION_EVENT = "TRANSLATION_EVENT"
    TRANSMISSION_EVENT = "TRANSMISSION_EVENT"
    LINEAGE_DISCONTINUITY = "LINEAGE_DISCONTINUITY"
    COUNTEREVIDENCE = "COUNTEREVIDENCE"
    ABSENCE_ONLY = "ABSENCE_ONLY"
    SEARCH_LEAD = "SEARCH_LEAD"


class InterpretationState(str, Enum):
    CANDIDATE = "CANDIDATE"
    PREFERRED = "PREFERRED"
    ESTABLISHED = "ESTABLISHED"
    UNRESOLVED = "UNRESOLVED"
    REJECTED = "REJECTED"


class ScopeKind(str, Enum):
    PROPOSITION = "PROPOSITION"
    DISTINCTION = "DISTINCTION"
    ARGUMENT_COMPONENT = "ARGUMENT_COMPONENT"
    BOUNDED_CLUSTER = "BOUNDED_CLUSTER"


MUTATION_TYPES = frozenset(item.value for item in MutationType)
COMPARISON_DIMENSIONS = frozenset(item.value for item in ComparisonDimension)
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_NUMERIC_KEYS = frozenset({"probability", "percentage", "score", "similarity_score", "confidence_score"})
_RECEPTION_RELATIONS = frozenset({
    HistoricalRelationType.RECEPTION.value,
    HistoricalRelationType.TRANSFORMATION.value,
    HistoricalRelationType.REVIVAL.value,
    HistoricalRelationType.REJECTION.value,
})
_FORBIDDEN_POLICY_KEYS = frozenset({
    "allow_correspondence_as_reception",
    "project_later_category_backward",
    "infer_abandonment_from_absence",
    "bypass_phase5_validation",
    "enable_novelty_adjudication",
    "enable_originality_adjudication",
    "enable_hidden_interlocutors",
    "enable_pressure_field",
    "enable_whole_work_cartography",
    "enable_phase9_confessional_registry",
})


def _obj(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ReceptionHistoryError(f"{label} must be an object")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReceptionHistoryError(f"{label} must be non-empty text")
    return value


def _id(value: Any, label: str) -> str:
    value = _text(value, label)
    if not _ID.fullmatch(value):
        raise ReceptionHistoryError(f"{label} must be a stable identifier")
    return value


def _enum(value: Any, kind: type[Enum], label: str) -> str:
    if not isinstance(value, str):
        raise ReceptionHistoryError(f"{label} must be a declared string value")
    try:
        kind(value)
    except ValueError as exc:
        raise ReceptionHistoryError(f"invalid {label} {value!r}") from exc
    return value


def _ids(value: Any, label: str, *, required: bool = False) -> tuple[str, ...]:
    if value is None and not required:
        return ()
    if not isinstance(value, list):
        raise ReceptionHistoryError(f"{label} must be an ordered list")
    result = tuple(_id(item, f"{label} item") for item in value)
    if len(result) != len(set(result)):
        raise ReceptionHistoryError(f"{label} contains duplicates")
    if required and not result:
        raise ReceptionHistoryError(f"{label} must not be empty")
    return result


def _texts(value: Any, label: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ReceptionHistoryError(f"{label} must be an ordered list")
    result = tuple(_text(item, f"{label} item") for item in value)
    if len(result) != len(set(result)):
        raise ReceptionHistoryError(f"{label} contains duplicates")
    return result


def _reject_numbers(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in _NUMERIC_KEYS:
                raise ReceptionHistoryError("pseudo-precise numerical comparison or confidence is prohibited")
            _reject_numbers(item)
    elif isinstance(value, list):
        for item in value:
            _reject_numbers(item)


@dataclass(frozen=True)
class ReceptionEvidence:
    _raw: Mapping[str, Any] = field(repr=False)
    evidence_roots: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: Any, known_representations: frozenset[str]) -> "ReceptionEvidence":
        raw = _obj(value, "reception evidence")
        _reject_numbers(raw)
        _id(raw.get("evidence_id"), "evidence_id")
        _enum(raw.get("evidence_type"), ReceptionEvidenceType, "evidence_type")
        representation_ids = _ids(raw.get("representation_ids"), "representation_ids", required=True)
        unknown = set(representation_ids) - known_representations
        if unknown:
            raise ReceptionHistoryError(f"unknown source representation(s): {sorted(unknown)}")
        _text(raw.get("antecedent_span"), "antecedent_span")
        _text(raw.get("recipient_span"), "recipient_span")
        _text(raw.get("description"), "evidence description")
        roots = _ids(raw.get("evidence_roots"), "evidence_roots", required=True)
        ProvenanceRecord.from_dict(raw.get("provenance"))
        return cls(copy.deepcopy(raw), roots)

    @property
    def evidence_id(self) -> str:
        return str(self._raw["evidence_id"])

    @property
    def evidence_type(self) -> str:
        return str(self._raw["evidence_type"])

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class TerminologyItem:
    _raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, value: Any) -> "TerminologyItem":
        raw = _obj(value, "terminology item")
        _id(raw.get("term_id"), "term_id")
        _text(raw.get("term"), "term")
        _text(raw.get("language"), "term language")
        status = _enum(raw.get("status"), TerminologyStatus, "terminology status")
        if status in {TerminologyStatus.LATER_ANALYTICAL_CATEGORY.value, TerminologyStatus.LATER_ANALOGY.value} and raw.get("historical_actor_term", False):
            raise ReceptionHistoryError("later analytical categories and analogies cannot become historical actor terminology")
        ProvenanceRecord.from_dict(raw.get("provenance"))
        return cls(copy.deepcopy(raw))

    @property
    def status(self) -> str:
        return str(self._raw["status"])

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class DimensionComparison:
    _raw: Mapping[str, Any] = field(repr=False)
    evidence_ids: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: Any, known_evidence: frozenset[str]) -> "DimensionComparison":
        raw = _obj(value, "comparison dimension")
        _id(raw.get("comparison_id"), "comparison_id")
        dimension = _enum(raw.get("dimension"), ComparisonDimension, "comparison dimension")
        _enum(raw.get("continuity"), ContinuityState, "continuity")
        lexical = raw.get("lexical_relation")
        if lexical is not None:
            _enum(lexical, LexicalRelation, "lexical_relation")
        _text(raw.get("antecedent_value"), "antecedent_value")
        _text(raw.get("recipient_value"), "recipient_value")
        _text(raw.get("rationale"), "comparison rationale")
        evidence_ids = _ids(raw.get("evidence_ids"), "comparison evidence_ids", required=True)
        unknown = set(evidence_ids) - known_evidence
        if unknown:
            raise ReceptionHistoryError(f"comparison references unknown evidence {sorted(unknown)}")
        if dimension == ComparisonDimension.SEMANTIC_FIELD.value:
            if not any(_texts(raw.get(key), key) for key in ("related_terms", "contrasts", "exclusions", "definitions")):
                raise ReceptionHistoryError("semantic-field comparison requires inspected field evidence")
        return cls(copy.deepcopy(raw), evidence_ids)

    @property
    def comparison_id(self) -> str:
        return str(self._raw["comparison_id"])

    @property
    def dimension(self) -> str:
        return str(self._raw["dimension"])

    @property
    def continuity(self) -> str:
        return str(self._raw["continuity"])

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class MutationRecord:
    _raw: Mapping[str, Any] = field(repr=False)
    evidence_ids: tuple[str, ...]

    @classmethod
    def from_dict(
        cls,
        value: Any,
        known_evidence: Mapping[str, ReceptionEvidence],
        comparisons: Mapping[str, DimensionComparison],
    ) -> "MutationRecord":
        raw = _obj(value, "mutation record")
        _id(raw.get("mutation_id"), "mutation_id")
        mutation_type = _enum(raw.get("mutation_type"), MutationType, "mutation_type")
        dimension = _enum(raw.get("dimension"), ComparisonDimension, "mutation dimension")
        _enum(raw.get("agent"), MutationAgent, "mutation agent")
        evidence_ids = _ids(raw.get("evidence_ids"), "mutation evidence_ids", required=True)
        unknown = set(evidence_ids) - set(known_evidence)
        if unknown:
            raise ReceptionHistoryError(f"mutation references unknown evidence {sorted(unknown)}")
        comparison_ids = _ids(raw.get("comparison_ids"), "mutation comparison_ids", required=True)
        unknown_comparisons = set(comparison_ids) - set(comparisons)
        if unknown_comparisons:
            raise ReceptionHistoryError(f"mutation references unknown comparison {sorted(unknown_comparisons)}")
        _ids(raw.get("antecedent_component_ids"), "antecedent_component_ids", required=True)
        _ids(raw.get("recipient_component_ids"), "recipient_component_ids", required=True)
        _text(raw.get("rationale"), "mutation rationale")

        evidence_types = {known_evidence[item].evidence_type for item in evidence_ids}
        if mutation_type in {MutationType.NARROWS.value, MutationType.BROADENS.value}:
            if dimension != ComparisonDimension.SEMANTIC_SCOPE.value:
                raise ReceptionHistoryError("narrowing and broadening require semantic-scope comparison")
            if raw.get("length_only", False):
                raise ReceptionHistoryError("text length alone cannot establish narrowing or broadening")
        if mutation_type == MutationType.ABANDONS.value:
            if ReceptionEvidenceType.EXPLICIT_ABANDONMENT.value not in evidence_types:
                raise ReceptionHistoryError("abandonment requires positive evidence beyond absence")
            if ReceptionEvidenceType.ABSENCE_ONLY.value in evidence_types:
                raise ReceptionHistoryError("absence alone cannot establish abandonment")
        if mutation_type == MutationType.COMBINES.value:
            antecedents = _ids(raw.get("antecedent_component_ids"), "antecedent_component_ids", required=True)
            if len(antecedents) < 2:
                raise ReceptionHistoryError("combination requires multiple antecedent components")
        if raw.get("agent") == MutationAgent.RECIPIENT.value and evidence_types <= {ReceptionEvidenceType.TRANSLATION_EVENT.value}:
            raise ReceptionHistoryError("translation evidence alone cannot establish recipient mutation")
        return cls(copy.deepcopy(raw), evidence_ids)

    @property
    def mutation_id(self) -> str:
        return str(self._raw["mutation_id"])

    @property
    def mutation_type(self) -> str:
        return str(self._raw["mutation_type"])

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class ConceptualInterpretation:
    _raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, value: Any, evidence_ids: frozenset[str]) -> "ConceptualInterpretation":
        raw = _obj(value, "conceptual interpretation")
        _id(raw.get("interpretation_id"), "interpretation_id")
        _enum(raw.get("state"), InterpretationState, "interpretation state")
        _text(raw.get("claim"), "interpretation claim")
        positive = _ids(raw.get("evidence_ids"), "interpretation evidence_ids")
        counter = _ids(raw.get("counterevidence_ids"), "interpretation counterevidence_ids")
        unknown = (set(positive) | set(counter)) - evidence_ids
        if unknown:
            raise ReceptionHistoryError(f"interpretation references unknown evidence {sorted(unknown)}")
        _texts(raw.get("unresolved_discriminators"), "unresolved_discriminators")
        ProvenanceRecord.from_dict(raw.get("provenance"))
        return cls(copy.deepcopy(raw))

    @property
    def interpretation_id(self) -> str:
        return str(self._raw["interpretation_id"])

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class ReceptionAnalysisPolicy:
    _raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, value: Any) -> "ReceptionAnalysisPolicy":
        raw = _obj(value, "reception analysis policy")
        _enum(raw.get("comparison_mode"), ComparisonMode, "comparison_mode")
        dimensions = _ids(raw.get("dimensions"), "policy dimensions", required=True)
        for item in dimensions:
            _enum(item, ComparisonDimension, "policy dimension")
        for key in _FORBIDDEN_POLICY_KEYS:
            if raw.get(key, False):
                raise ReceptionHistoryError(f"policy cannot enable {key}")
        ordering = raw.get("deterministic_ordering", "STABLE_ID")
        if ordering not in {"STABLE_ID", "DIMENSION_THEN_ID"}:
            raise ReceptionHistoryError("unsupported deterministic ordering policy")
        return cls(copy.deepcopy(raw))

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class ReceptionConceptualProfile:
    profile_id: str
    analysis_id: str
    antecedent_ref: str
    recipient_ref: str
    scope_kind: str
    scope: str
    reception_status: str
    historical_relation_ids: tuple[str, ...]
    mutation_records: tuple[MutationRecord, ...]
    comparisons: tuple[DimensionComparison, ...]
    terminology: tuple[TerminologyItem, ...]
    counterevidence_ids: tuple[str, ...]
    interpretations: tuple[ConceptualInterpretation, ...]
    evidence_roots: tuple[str, ...]
    upstream_uncertainty: tuple[Mapping[str, Any], ...]
    unresolved_questions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "analysis_id": self.analysis_id,
            "antecedent_ref": self.antecedent_ref,
            "recipient_ref": self.recipient_ref,
            "scope_kind": self.scope_kind,
            "scope": self.scope,
            "reception_status": self.reception_status,
            "historical_relation_ids": list(self.historical_relation_ids),
            "mutation_records": [item.to_dict() for item in self.mutation_records],
            "comparisons": [item.to_dict() for item in self.comparisons],
            "terminology": [item.to_dict() for item in self.terminology],
            "counterevidence_ids": list(self.counterevidence_ids),
            "interpretations": [item.to_dict() for item in self.interpretations],
            "evidence_roots": list(self.evidence_roots),
            "upstream_uncertainty": [copy.deepcopy(dict(item)) for item in self.upstream_uncertainty],
            "unresolved_questions": list(self.unresolved_questions),
        }


@dataclass(frozen=True)
class ReceptionAnalysisResult:
    analysis_id: str
    reception_established: bool
    conceptual_comparison_only: bool
    profile: ReceptionConceptualProfile

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "reception_established": self.reception_established,
            "conceptual_comparison_only": self.conceptual_comparison_only,
            "profile": self.profile.to_dict(),
        }

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())

    def digest(self) -> str:
        return sha256_json(self.to_dict())


@dataclass(frozen=True)
class ReceptionConceptualAnalysis:
    _raw: Mapping[str, Any] = field(repr=False)
    evidence: tuple[ReceptionEvidence, ...]
    terminology: tuple[TerminologyItem, ...]
    comparisons: tuple[DimensionComparison, ...]
    mutations: tuple[MutationRecord, ...]
    interpretations: tuple[ConceptualInterpretation, ...]
    policy: ReceptionAnalysisPolicy
    licensed_relation_ids: tuple[str, ...]

    @classmethod
    def from_dict(
        cls,
        value: Any,
        *,
        known_argument_refs: Iterable[str],
        known_representation_ids: Iterable[str],
        phase5_graph: HistoricalRelationGraph | None = None,
        known_lineage_context_ids: Iterable[str] = (),
        known_transmission_profile_ids: Iterable[str] = (),
    ) -> "ReceptionConceptualAnalysis":
        raw = _obj(value, "reception and conceptual-history analysis")
        _reject_numbers(raw)
        if raw.get("schema_version") != "1":
            raise ReceptionHistoryError("analysis schema_version must be 1")
        _id(raw.get("analysis_id"), "analysis_id")
        known_refs = frozenset(known_argument_refs)
        antecedent = _id(raw.get("antecedent_ref"), "antecedent_ref")
        recipient = _id(raw.get("recipient_ref"), "recipient_ref")
        if antecedent == recipient:
            raise ReceptionHistoryError("antecedent and recipient must be distinct")
        unknown_refs = {antecedent, recipient} - known_refs
        if unknown_refs:
            raise ReceptionHistoryError(f"unknown argument reference(s): {sorted(unknown_refs)}")
        _enum(raw.get("scope_kind"), ScopeKind, "scope_kind")
        _text(raw.get("scope"), "bounded analysis scope")
        if raw.get("whole_work_scope", False):
            raise ReceptionHistoryError("whole-work theological cartography is outside Phase 8")

        lineage_ids = _ids(raw.get("lineage_context_ids"), "lineage_context_ids")
        if set(lineage_ids) - frozenset(known_lineage_context_ids):
            raise ReceptionHistoryError("unknown Phase 6 lineage context")
        transmission_ids = _ids(raw.get("transmission_profile_ids"), "transmission_profile_ids")
        if set(transmission_ids) - frozenset(known_transmission_profile_ids):
            raise ReceptionHistoryError("unknown Phase 7 transmission profile")

        evidence = tuple(
            ReceptionEvidence.from_dict(item, frozenset(known_representation_ids))
            for item in raw.get("evidence", [])
        )
        evidence_map = {item.evidence_id: item for item in evidence}
        if len(evidence_map) != len(evidence):
            raise ReceptionHistoryError("reception evidence ids must be unique")
        if not evidence:
            raise ReceptionHistoryError("analysis requires inspected evidence")

        terminology = tuple(TerminologyItem.from_dict(item) for item in raw.get("terminology", []))
        term_ids = [item.to_dict()["term_id"] for item in terminology]
        if len(term_ids) != len(set(term_ids)):
            raise ReceptionHistoryError("terminology ids must be unique")

        comparisons = tuple(
            DimensionComparison.from_dict(item, frozenset(evidence_map))
            for item in raw.get("comparisons", [])
        )
        comparison_map = {item.comparison_id: item for item in comparisons}
        if len(comparison_map) != len(comparisons):
            raise ReceptionHistoryError("comparison ids must be unique")
        if not comparisons:
            raise ReceptionHistoryError("analysis requires comparison dimensions")

        mutations = tuple(
            MutationRecord.from_dict(item, evidence_map, comparison_map)
            for item in raw.get("mutations", [])
        )
        if len({item.mutation_id for item in mutations}) != len(mutations):
            raise ReceptionHistoryError("mutation ids must be unique")

        interpretations = tuple(
            ConceptualInterpretation.from_dict(item, frozenset(evidence_map))
            for item in raw.get("competing_interpretations", [])
        )
        if len({item.interpretation_id for item in interpretations}) != len(interpretations):
            raise ReceptionHistoryError("interpretation ids must be unique")

        counter = _ids(raw.get("counterevidence_ids"), "counterevidence_ids")
        if set(counter) - set(evidence_map):
            raise ReceptionHistoryError("counterevidence references unknown evidence")
        _texts(raw.get("unresolved_questions"), "unresolved_questions")
        uncertainty = raw.get("upstream_uncertainty", [])
        if not isinstance(uncertainty, list) or not all(isinstance(item, dict) for item in uncertainty):
            raise ReceptionHistoryError("upstream_uncertainty must be an ordered list of Phase 4 views")
        ProvenanceRecord.from_dict(raw.get("provenance"))
        policy = ReceptionAnalysisPolicy.from_dict(raw.get("policy"))

        relation_ids = _ids(raw.get("historical_relation_ids"), "historical_relation_ids")
        relation_by_id = {edge.edge_id: edge for edge in phase5_graph.edges} if phase5_graph else {}
        if set(relation_ids) - set(relation_by_id):
            raise ReceptionHistoryError("analysis references an unknown Phase 5 relation")
        active = tuple(
            edge for edge_id, edge in relation_by_id.items()
            if edge_id in relation_ids and edge.claim_state in ACTIVE_CLAIM_STATES
        )
        claims_reception = bool(raw.get("claims_reception", False))
        licensed = tuple(sorted(edge.edge_id for edge in active if edge.relation_type in _RECEPTION_RELATIONS))
        if claims_reception and not licensed:
            raise ReceptionHistoryError("historical reception requires an active Phase 5 engagement relation")
        if not claims_reception and raw.get("reception_established", False):
            raise ReceptionHistoryError("conceptual correspondence cannot silently become reception")
        relation_types = {edge.relation_type for edge in active}
        mutation_types = {item.mutation_type for item in mutations}
        if MutationType.REJECTS.value in mutation_types and HistoricalRelationType.REJECTION.value not in relation_types:
            raise ReceptionHistoryError("rejection analysis requires a licensed Phase 5 REJECTION edge")
        if MutationType.REVIVES.value in mutation_types:
            if HistoricalRelationType.REVIVAL.value not in relation_types:
                raise ReceptionHistoryError("revival analysis requires a licensed Phase 5 REVIVAL edge")
            if not raw.get("preserves_lineage_discontinuity", False):
                raise ReceptionHistoryError("revival must preserve Phase 6 discontinuity")

        if any(item.status == TerminologyStatus.LATER_ANALOGY.value for item in terminology) and claims_reception:
            analogy_evidence = {
                item.evidence_id for item in evidence
                if item.evidence_type == ReceptionEvidenceType.SEARCH_LEAD.value
            }
            mutation_evidence = {
                evidence_id
                for mutation in mutations
                for evidence_id in mutation.evidence_ids
            }
            if analogy_evidence and mutation_evidence and mutation_evidence <= analogy_evidence:
                raise ReceptionHistoryError("later analogy cannot establish reception")

        return cls(
            copy.deepcopy(raw), evidence, terminology, comparisons, mutations,
            interpretations, policy, licensed,
        )

    @property
    def analysis_id(self) -> str:
        return str(self._raw["analysis_id"])

    def analyze(self) -> ReceptionAnalysisResult:
        claims_reception = bool(self._raw.get("claims_reception", False))
        roots = tuple(sorted({root for item in self.evidence for root in item.evidence_roots}))
        profile = ReceptionConceptualProfile(
            profile_id=f"reception-profile:{self.analysis_id}",
            analysis_id=self.analysis_id,
            antecedent_ref=str(self._raw["antecedent_ref"]),
            recipient_ref=str(self._raw["recipient_ref"]),
            scope_kind=str(self._raw["scope_kind"]),
            scope=str(self._raw["scope"]),
            reception_status="ESTABLISHED_OR_SUPPORTED" if claims_reception else "CONCEPTUAL_COMPARISON_ONLY",
            historical_relation_ids=self.licensed_relation_ids,
            mutation_records=tuple(sorted(self.mutations, key=lambda item: (item.mutation_type, item.mutation_id))),
            comparisons=tuple(sorted(self.comparisons, key=lambda item: (item.dimension, item.comparison_id))),
            terminology=tuple(sorted(self.terminology, key=lambda item: item.to_dict()["term_id"])),
            counterevidence_ids=tuple(sorted(self._raw.get("counterevidence_ids", []))),
            interpretations=tuple(sorted(self.interpretations, key=lambda item: item.interpretation_id)),
            evidence_roots=roots,
            upstream_uncertainty=tuple(copy.deepcopy(self._raw.get("upstream_uncertainty", []))),
            unresolved_questions=tuple(sorted(self._raw.get("unresolved_questions", []))),
        )
        return ReceptionAnalysisResult(self.analysis_id, claims_reception, not claims_reception, profile)

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class ReceptionConstructionResult:
    analysis: ReceptionConceptualAnalysis | None
    result: ReceptionAnalysisResult | None
    audit: AuditResult


def construct_reception_analysis(
    value: Any,
    *,
    known_argument_refs: Iterable[str],
    known_representation_ids: Iterable[str],
    phase5_graph: HistoricalRelationGraph | None = None,
    known_lineage_context_ids: Iterable[str] = (),
    known_transmission_profile_ids: Iterable[str] = (),
) -> ReceptionConstructionResult:
    try:
        analysis = ReceptionConceptualAnalysis.from_dict(
            value,
            known_argument_refs=known_argument_refs,
            known_representation_ids=known_representation_ids,
            phase5_graph=phase5_graph,
            known_lineage_context_ids=known_lineage_context_ids,
            known_transmission_profile_ids=known_transmission_profile_ids,
        )
        return ReceptionConstructionResult(analysis, analysis.analyze(), AuditResult(()))
    except (ReceptionHistoryError, ValidationError) as exc:
        return ReceptionConstructionResult(
            None, None,
            AuditResult((AuditFinding("PHASE8_RECEPTION_HISTORY_INVALID", str(exc)),)),
        )


def audit_reception_analysis(*args: Any, **kwargs: Any) -> AuditResult:
    return construct_reception_analysis(*args, **kwargs).audit
