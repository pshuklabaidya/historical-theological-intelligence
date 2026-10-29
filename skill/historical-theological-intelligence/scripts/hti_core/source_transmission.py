"""Phase 7 source-transmission forensics and immediate-source adjudication.

The module consumes identifiers and validated views from Phases 2-6. It never
mutates those layers or creates a Historical Relation Graph edge.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

from .audit import AuditFinding, AuditResult
from .hashing import canonical_json, sha256_json
from .historical_relations import AccessState, ChronologyState, HistoricalRelationGraph
from .model import ValidationError
from .provenance import ProvenanceRecord


class SourceTransmissionError(ValidationError):
    """Raised when a forensic claim fails closed."""


class ForensicFeatureType(str, Enum):
    DISTINCTIVE_WORDING = "DISTINCTIVE_WORDING"
    SHARED_OMISSION = "SHARED_OMISSION"
    SHARED_CORRUPTION = "SHARED_CORRUPTION"
    SHARED_MISTRANSLATION = "SHARED_MISTRANSLATION"
    SHARED_ERRONEOUS_ATTRIBUTION = "SHARED_ERRONEOUS_ATTRIBUTION"
    UNUSUAL_ORDERING = "UNUSUAL_ORDERING"
    UNUSUAL_AUTHORITY_SEQUENCE = "UNUSUAL_AUTHORITY_SEQUENCE"
    DISTINCTIVE_TRUNCATION = "DISTINCTIVE_TRUNCATION"
    SHARED_TEXTUAL_VARIANT = "SHARED_TEXTUAL_VARIANT"
    EDITION_SPECIFIC_FEATURE = "EDITION_SPECIFIC_FEATURE"
    CITATION_ANOMALY = "CITATION_ANOMALY"
    TRANSLATION_SIGNATURE = "TRANSLATION_SIGNATURE"
    EDITORIAL_FEATURE = "EDITORIAL_FEATURE"
    ACCESS_DOCUMENTATION = "ACCESS_DOCUMENTATION"
    COMMON_AGREEMENT = "COMMON_AGREEMENT"
    SHARED_CANONICAL_SOURCE = "SHARED_CANONICAL_SOURCE"
    MACHINE_SIMILARITY = "MACHINE_SIMILARITY"
    NGRAM_OVERLAP = "NGRAM_OVERLAP"
    SEQUENCE_SIMILARITY = "SEQUENCE_SIMILARITY"


class FeatureSignificance(str, Enum):
    COMMON = "COMMON"
    POTENTIALLY_DISCRIMINATING = "POTENTIALLY_DISCRIMINATING"
    DISCRIMINATING = "DISCRIMINATING"
    HIGH_RISK_REQUIRES_CORROBORATION = "HIGH_RISK_REQUIRES_CORROBORATION"
    UNRESOLVED = "UNRESOLVED"


class InspectionStatus(str, Enum):
    PRIMARY_PASSAGE_INSPECTED = "PRIMARY_PASSAGE_INSPECTED"
    BROADER_CONTEXT_INSPECTED = "BROADER_CONTEXT_INSPECTED"
    OCR_LOCATOR_ONLY = "OCR_LOCATOR_ONLY"
    METADATA_LEAD_ONLY = "METADATA_LEAD_ONLY"
    SECONDARY_REPORT_ONLY = "SECONDARY_REPORT_ONLY"
    BROADER_CONTEXT_REQUIRED = "BROADER_CONTEXT_REQUIRED"
    UNINSPECTED = "UNINSPECTED"


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    PROVISIONAL = "PROVISIONAL"
    UNRESOLVED = "UNRESOLVED"
    CONTRADICTED = "CONTRADICTED"


class TransmissionChannel(str, Enum):
    DIRECT_CONSULTATION = "DIRECT_CONSULTATION"
    THEOLOGIAN_INTERMEDIARY = "THEOLOGIAN_INTERMEDIARY"
    FLORILEGIUM = "FLORILEGIUM"
    COMMONPLACE_BOOK = "COMMONPLACE_BOOK"
    EPITOME = "EPITOME"
    INDEX = "INDEX"
    ANTHOLOGY = "ANTHOLOGY"
    CATENA = "CATENA"
    COMMENTARY = "COMMENTARY"
    HISTORICAL_TRANSLATION = "HISTORICAL_TRANSLATION"
    EDITORIAL_APPARATUS = "EDITORIAL_APPARATUS"
    SHARED_SOURCE_TRADITION = "SHARED_SOURCE_TRADITION"
    OTHER_INFORMATION_SYSTEM = "OTHER_INFORMATION_SYSTEM"
    UNRESOLVED = "UNRESOLVED"


class HypothesisKind(str, Enum):
    DIRECT_CONSULTATION = "DIRECT_CONSULTATION"
    MEDIATED_DEPENDENCE = "MEDIATED_DEPENDENCE"
    SHARED_SOURCE = "SHARED_SOURCE"
    EDITION_USE = "EDITION_USE"
    TRANSLATION_MEDIATION = "TRANSLATION_MEDIATION"
    INHERITED_COMMONPLACE = "INHERITED_COMMONPLACE"


class HypothesisState(str, Enum):
    CANDIDATE = "CANDIDATE"
    PLAUSIBLE = "PLAUSIBLE"
    SUPPORTED = "SUPPORTED"
    PREFERRED = "PREFERRED"
    ESTABLISHED = "ESTABLISHED"
    UNRESOLVED = "UNRESOLVED"
    REJECTED = "REJECTED"


class ScopeKind(str, Enum):
    QUOTATION = "QUOTATION"
    PROPOSITION = "PROPOSITION"
    DISTINCTION = "DISTINCTION"
    ARGUMENT_COMPONENT = "ARGUMENT_COMPONENT"
    BOUNDED_CLUSTER = "BOUNDED_CLUSTER"


FORENSIC_FEATURE_TYPES = frozenset(item.value for item in ForensicFeatureType)
_DISCOVERY_ONLY = frozenset({
    ForensicFeatureType.MACHINE_SIMILARITY.value,
    ForensicFeatureType.NGRAM_OVERLAP.value,
    ForensicFeatureType.SEQUENCE_SIMILARITY.value,
})
_NON_DISCRIMINATING = frozenset({
    ForensicFeatureType.COMMON_AGREEMENT.value,
    ForensicFeatureType.SHARED_CANONICAL_SOURCE.value,
})
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_NUMERIC_KEYS = frozenset({"probability", "percentage", "score", "likelihood_ratio", "confidence_score"})


def _obj(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise SourceTransmissionError(f"{label} must be an object")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SourceTransmissionError(f"{label} must be non-empty text")
    return value


def _id(value: Any, label: str) -> str:
    value = _text(value, label)
    if not _ID.fullmatch(value):
        raise SourceTransmissionError(f"{label} must be a stable identifier")
    return value


def _enum(value: Any, kind: type[Enum], label: str) -> str:
    if not isinstance(value, str):
        raise SourceTransmissionError(f"{label} must be a declared string value")
    try:
        kind(value)
    except ValueError as exc:
        raise SourceTransmissionError(f"invalid {label} {value!r}") from exc
    return value


def _ids(value: Any, label: str, *, required: bool = False) -> tuple[str, ...]:
    if value is None and not required:
        return ()
    if not isinstance(value, list):
        raise SourceTransmissionError(f"{label} must be an ordered list")
    result = tuple(_id(item, f"{label} item") for item in value)
    if len(result) != len(set(result)):
        raise SourceTransmissionError(f"{label} contains duplicates")
    if required and not result:
        raise SourceTransmissionError(f"{label} must not be empty")
    return result


def _reject_numbers(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in _NUMERIC_KEYS:
                raise SourceTransmissionError("pseudo-precise numerical confidence is prohibited")
            _reject_numbers(item)
    elif isinstance(value, list):
        for item in value:
            _reject_numbers(item)


@dataclass(frozen=True)
class ForensicEvidence:
    _raw: Mapping[str, Any] = field(repr=False)
    evidence_roots: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: Any, known_representations: frozenset[str]) -> "ForensicEvidence":
        raw = _obj(value, "forensic evidence")
        _reject_numbers(raw)
        _id(raw.get("evidence_id"), "evidence_id")
        feature = _enum(raw.get("feature_type"), ForensicFeatureType, "feature_type")
        significance = _enum(raw.get("significance"), FeatureSignificance, "significance")
        inspection = _enum(raw.get("inspection_status"), InspectionStatus, "inspection_status")
        _enum(raw.get("verification_status"), VerificationStatus, "verification_status")
        sources = _ids(raw.get("source_representation_ids"), "source representations", required=True)
        comparators = _ids(raw.get("comparator_representation_ids"), "comparator representations", required=True)
        unknown = (set(sources) | set(comparators)) - known_representations
        if unknown:
            raise SourceTransmissionError(f"unknown source representation(s): {sorted(unknown)}")
        _text(raw.get("source_span"), "source_span")
        _text(raw.get("comparator_span"), "comparator_span")
        _text(raw.get("description"), "evidence description")
        roots = _ids(raw.get("evidence_roots"), "evidence roots", required=True)
        ProvenanceRecord.from_dict(raw.get("provenance"))
        if feature in _DISCOVERY_ONLY and not raw.get("candidate_discovery_only", False):
            raise SourceTransmissionError("machine or sequence similarity must remain candidate discovery only")
        if feature in _NON_DISCRIMINATING and significance == FeatureSignificance.DISCRIMINATING.value:
            raise SourceTransmissionError("common agreement or shared canonical source is not discriminating")
        if inspection in {InspectionStatus.OCR_LOCATOR_ONLY.value, InspectionStatus.METADATA_LEAD_ONLY.value} and significance == FeatureSignificance.DISCRIMINATING.value:
            raise SourceTransmissionError("locator or metadata evidence cannot be discriminating proof")
        return cls(copy.deepcopy(raw), roots)

    @property
    def evidence_id(self) -> str:
        return str(self._raw["evidence_id"])

    @property
    def feature_type(self) -> str:
        return str(self._raw["feature_type"])

    @property
    def qualifying(self) -> bool:
        return (
            self._raw["verification_status"] == VerificationStatus.VERIFIED.value
            and self._raw["inspection_status"] in {
                InspectionStatus.PRIMARY_PASSAGE_INSPECTED.value,
                InspectionStatus.BROADER_CONTEXT_INSPECTED.value,
            }
            and self._raw["significance"] in {
                FeatureSignificance.DISCRIMINATING.value,
                FeatureSignificance.POTENTIALLY_DISCRIMINATING.value,
            }
            and self.feature_type not in _DISCOVERY_ONLY | _NON_DISCRIMINATING
        )

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class ImmediateSourceHypothesis:
    _raw: Mapping[str, Any] = field(repr=False)
    evidence_ids: tuple[str, ...]
    counterevidence_ids: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: Any, evidence_ids: frozenset[str], phase5_relation_ids: frozenset[str]) -> "ImmediateSourceHypothesis":
        raw = _obj(value, "source hypothesis")
        _reject_numbers(raw)
        _id(raw.get("hypothesis_id"), "hypothesis_id")
        _enum(raw.get("kind"), HypothesisKind, "hypothesis kind")
        _enum(raw.get("channel"), TransmissionChannel, "transmission channel")
        _enum(raw.get("requested_state", HypothesisState.CANDIDATE.value), HypothesisState, "requested_state")
        _enum(raw.get("chronology_state"), ChronologyState, "chronology_state")
        _enum(raw.get("accessibility_state"), AccessState, "accessibility_state")
        _enum(raw.get("scope_kind"), ScopeKind, "scope_kind")
        _text(raw.get("scope"), "hypothesis scope")
        for key in ("named_authority", "ultimate_antecedent", "proposed_immediate_source", "proposed_intermediary", "shared_source"):
            item = raw.get(key)
            if item is not None:
                _text(item, key)
        evid = _ids(raw.get("evidence_ids"), "hypothesis evidence_ids")
        counter = _ids(raw.get("counterevidence_ids"), "hypothesis counterevidence_ids")
        unknown = (set(evid) | set(counter)) - evidence_ids
        if unknown:
            raise SourceTransmissionError(f"hypothesis references unknown evidence {sorted(unknown)}")
        relation_id = raw.get("phase5_relation_id")
        if relation_id is not None and _id(relation_id, "phase5_relation_id") not in phase5_relation_ids:
            raise SourceTransmissionError("hypothesis references an unvalidated Phase 5 relation")
        plan_ids = _ids(raw.get("phase6_research_plan_ids"), "Phase 6 research plan ids")
        if set(plan_ids) & set(evid):
            raise SourceTransmissionError("Phase 6 research-plan items are not forensic evidence")
        alternatives = _ids(raw.get("unresolved_alternative_ids"), "unresolved alternative ids")
        if raw.get("confidence") is not None:
            _text(raw.get("confidence"), "qualitative confidence")
        ProvenanceRecord.from_dict(raw.get("provenance"))
        return cls(copy.deepcopy(raw), evid, counter)

    @property
    def hypothesis_id(self) -> str:
        return str(self._raw["hypothesis_id"])

    @property
    def kind(self) -> str:
        return str(self._raw["kind"])

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class ForensicPolicy:
    _raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, value: Any) -> "ForensicPolicy":
        raw = _obj(value, "forensic policy")
        _enum(raw.get("target_scope_kind"), ScopeKind, "target_scope_kind")
        required = raw.get("minimum_independent_discriminating_roots", 2)
        if not isinstance(required, int) or isinstance(required, bool) or required < 1:
            raise SourceTransmissionError("minimum roots must be a positive integer")
        if raw.get("allow_similarity_as_proof", False):
            raise SourceTransmissionError("policy cannot promote similarity to proof")
        if raw.get("allow_uninspected_comparator", False):
            raise SourceTransmissionError("policy cannot disable comparator inspection")
        if raw.get("bypass_phase5_validation", False):
            raise SourceTransmissionError("policy cannot bypass Phase 5 validation")
        return cls(copy.deepcopy(raw))

    @property
    def minimum_roots(self) -> int:
        return int(self._raw.get("minimum_independent_discriminating_roots", 2))

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class HypothesisAdjudication:
    hypothesis_id: str
    state: str
    qualifying_evidence_ids: tuple[str, ...]
    independent_evidence_roots: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    unresolved_reasons: tuple[str, ...]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "state": self.state,
            "qualifying_evidence_ids": list(self.qualifying_evidence_ids),
            "independent_evidence_roots": list(self.independent_evidence_roots),
            "rejection_reasons": list(self.rejection_reasons),
            "unresolved_reasons": list(self.unresolved_reasons),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class SourceTransmissionProfile:
    profile_id: str
    investigation_id: str
    anchor_proposition_id: str
    scope_kind: str
    scope: str
    named_authorities: tuple[str, ...]
    ultimate_antecedents: tuple[str, ...]
    immediate_source_status: str
    adjudications: tuple[HypothesisAdjudication, ...]
    evidence_roots: tuple[str, ...]
    research_gaps: tuple[str, ...]
    upstream_uncertainty: tuple[Mapping[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "investigation_id": self.investigation_id,
            "anchor_proposition_id": self.anchor_proposition_id,
            "scope_kind": self.scope_kind,
            "scope": self.scope,
            "named_authorities": list(self.named_authorities),
            "ultimate_antecedents": list(self.ultimate_antecedents),
            "immediate_source_status": self.immediate_source_status,
            "adjudications": [item.to_dict() for item in self.adjudications],
            "evidence_roots": list(self.evidence_roots),
            "research_gaps": list(self.research_gaps),
            "upstream_uncertainty": [copy.deepcopy(dict(item)) for item in self.upstream_uncertainty],
        }


@dataclass(frozen=True)
class ForensicAdjudicationResult:
    investigation_id: str
    adjudications: tuple[HypothesisAdjudication, ...]
    profile: SourceTransmissionProfile | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "investigation_id": self.investigation_id,
            "adjudications": [item.to_dict() for item in self.adjudications],
            "profile": self.profile.to_dict() if self.profile else None,
        }

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())

    def digest(self) -> str:
        return sha256_json(self.to_dict())


@dataclass(frozen=True)
class SourceTransmissionInvestigation:
    _raw: Mapping[str, Any] = field(repr=False)
    evidence: tuple[ForensicEvidence, ...]
    hypotheses: tuple[ImmediateSourceHypothesis, ...]
    policy: ForensicPolicy

    @classmethod
    def from_dict(
        cls,
        value: Any,
        *,
        known_representation_ids: Iterable[str],
        known_proposition_ids: Iterable[str],
        phase5_graph: HistoricalRelationGraph | None = None,
    ) -> "SourceTransmissionInvestigation":
        raw = _obj(value, "source-transmission investigation")
        _reject_numbers(raw)
        if raw.get("schema_version") != "1":
            raise SourceTransmissionError("investigation schema_version must be 1")
        _id(raw.get("investigation_id"), "investigation_id")
        anchor = _id(raw.get("anchor_proposition_id"), "anchor_proposition_id")
        if anchor not in frozenset(known_proposition_ids):
            raise SourceTransmissionError("unknown anchor proposition")
        _enum(raw.get("scope_kind"), ScopeKind, "scope_kind")
        _text(raw.get("scope"), "investigation scope")
        evidence = tuple(
            ForensicEvidence.from_dict(item, frozenset(known_representation_ids))
            for item in raw.get("evidence", [])
        )
        evidence_map = {item.evidence_id: item for item in evidence}
        if len(evidence_map) != len(evidence):
            raise SourceTransmissionError("forensic evidence ids must be unique")
        relation_ids = frozenset()
        if phase5_graph is not None:
            relation_ids = frozenset(edge.edge_id for edge in phase5_graph.active_edges)
        hypotheses = tuple(
            ImmediateSourceHypothesis.from_dict(item, frozenset(evidence_map), relation_ids)
            for item in raw.get("hypotheses", [])
        )
        if len({item.hypothesis_id for item in hypotheses}) != len(hypotheses):
            raise SourceTransmissionError("hypothesis ids must be unique")
        hypothesis_ids = {item.hypothesis_id for item in hypotheses}
        for item in hypotheses:
            unknown = set(item._raw.get("unresolved_alternative_ids", [])) - hypothesis_ids
            if unknown:
                raise SourceTransmissionError(f"unknown unresolved hypothesis alternatives {sorted(unknown)}")
        policy = ForensicPolicy.from_dict(raw.get("policy"))
        uncertainty = raw.get("upstream_uncertainty", [])
        if not isinstance(uncertainty, list) or not all(isinstance(item, dict) for item in uncertainty):
            raise SourceTransmissionError("upstream_uncertainty must be an ordered list of Phase 4 views")
        ProvenanceRecord.from_dict(raw.get("provenance"))
        return cls(copy.deepcopy(raw), evidence, hypotheses, policy)

    @property
    def investigation_id(self) -> str:
        return str(self._raw["investigation_id"])

    def _adjudicate_one(self, hypothesis: ImmediateSourceHypothesis) -> HypothesisAdjudication:
        evidence_map = {item.evidence_id: item for item in self.evidence}
        selected = tuple(evidence_map[item] for item in hypothesis.evidence_ids)
        qualifying = tuple(sorted(item.evidence_id for item in selected if item.qualifying))
        roots = tuple(sorted({root for item in selected if item.qualifying for root in item.evidence_roots}))
        rejected: list[str] = list(hypothesis._raw.get("rejection_reasons", []))
        unresolved: list[str] = []
        chronology = hypothesis._raw["chronology_state"]
        access = hypothesis._raw["accessibility_state"]
        if chronology == ChronologyState.CONTRADICTED.value:
            rejected.append("chronology incompatible")
        if access in {AccessState.CONTRADICTED.value, AccessState.IMPOSSIBLE.value}:
            rejected.append("access contradicted")
        if any(item._raw["inspection_status"] == InspectionStatus.BROADER_CONTEXT_REQUIRED.value for item in selected):
            unresolved.append("broader comparator context remains required")
        if not qualifying:
            unresolved.append("no verified discriminating feature")
        if len(roots) < self.policy.minimum_roots:
            unresolved.append("independent discriminating evidence roots below establishment threshold")
        if rejected:
            state = HypothesisState.REJECTED.value
        elif unresolved:
            state = HypothesisState.UNRESOLVED.value
        elif hypothesis._raw.get("phase5_relation_id") is None and hypothesis.kind in {
            HypothesisKind.DIRECT_CONSULTATION.value,
            HypothesisKind.MEDIATED_DEPENDENCE.value,
            HypothesisKind.SHARED_SOURCE.value,
        }:
            state = HypothesisState.SUPPORTED.value
            unresolved.append("Phase 5 historical relation validation required for establishment")
        else:
            requested = hypothesis._raw.get("requested_state", HypothesisState.SUPPORTED.value)
            state = HypothesisState.ESTABLISHED.value if requested == HypothesisState.ESTABLISHED.value else HypothesisState.SUPPORTED.value
        rationale = "fail-closed forensic adjudication from inspected discriminating evidence"
        return HypothesisAdjudication(hypothesis.hypothesis_id, state, qualifying, roots, tuple(sorted(set(rejected))), tuple(sorted(set(unresolved))), rationale)

    def adjudicate(self, *, generate_profile: bool = True) -> ForensicAdjudicationResult:
        adjudications = tuple(sorted((self._adjudicate_one(item) for item in self.hypotheses), key=lambda item: item.hypothesis_id))
        viable = [item for item in adjudications if item.state in {HypothesisState.SUPPORTED.value, HypothesisState.ESTABLISHED.value}]
        if len(viable) > 1 and not any(item.state == HypothesisState.ESTABLISHED.value for item in viable):
            strongest = max(len(item.independent_evidence_roots) for item in viable)
            winners = [item for item in viable if len(item.independent_evidence_roots) == strongest]
            if len(winners) == 1:
                target = winners[0].hypothesis_id
                adjudications = tuple(
                    HypothesisAdjudication(item.hypothesis_id, HypothesisState.PREFERRED.value if item.hypothesis_id == target else item.state, item.qualifying_evidence_ids, item.independent_evidence_roots, item.rejection_reasons, item.unresolved_reasons, item.rationale)
                    for item in adjudications
                )
        profile = self._profile(adjudications) if generate_profile else None
        return ForensicAdjudicationResult(self.investigation_id, adjudications, profile)

    def _profile(self, adjudications: tuple[HypothesisAdjudication, ...]) -> SourceTransmissionProfile:
        named = tuple(sorted({str(item._raw["named_authority"]) for item in self.hypotheses if item._raw.get("named_authority")}))
        ultimate = tuple(sorted({str(item._raw["ultimate_antecedent"]) for item in self.hypotheses if item._raw.get("ultimate_antecedent")}))
        established = [item for item in adjudications if item.state == HypothesisState.ESTABLISHED.value]
        preferred = [item for item in adjudications if item.state == HypothesisState.PREFERRED.value]
        if established:
            status = "ESTABLISHED"
        elif preferred:
            status = "PREFERRED_NOT_ESTABLISHED"
        elif any(item.state == HypothesisState.SUPPORTED.value for item in adjudications):
            status = "SUPPORTED_ALTERNATIVES"
        else:
            status = "UNRESOLVED"
        roots = tuple(sorted({root for item in adjudications for root in item.independent_evidence_roots}))
        gaps = tuple(sorted({reason for item in adjudications for reason in item.unresolved_reasons}))
        return SourceTransmissionProfile(
            profile_id=f"profile:{self.investigation_id}",
            investigation_id=self.investigation_id,
            anchor_proposition_id=str(self._raw["anchor_proposition_id"]),
            scope_kind=str(self._raw["scope_kind"]),
            scope=str(self._raw["scope"]),
            named_authorities=named,
            ultimate_antecedents=ultimate,
            immediate_source_status=status,
            adjudications=adjudications,
            evidence_roots=roots,
            research_gaps=gaps,
            upstream_uncertainty=tuple(copy.deepcopy(self._raw.get("upstream_uncertainty", []))),
        )

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class SourceTransmissionConstructionResult:
    investigation: SourceTransmissionInvestigation | None
    adjudication: ForensicAdjudicationResult | None
    audit: AuditResult


def construct_source_transmission(
    value: Any,
    *,
    known_representation_ids: Iterable[str],
    known_proposition_ids: Iterable[str],
    phase5_graph: HistoricalRelationGraph | None = None,
) -> SourceTransmissionConstructionResult:
    try:
        investigation = SourceTransmissionInvestigation.from_dict(
            value,
            known_representation_ids=known_representation_ids,
            known_proposition_ids=known_proposition_ids,
            phase5_graph=phase5_graph,
        )
        result = investigation.adjudicate(generate_profile=bool(value.get("generate_profile", True)))
        return SourceTransmissionConstructionResult(investigation, result, AuditResult(()))
    except (SourceTransmissionError, ValidationError) as exc:
        finding = AuditFinding("PHASE7_SOURCE_TRANSMISSION_INVALID", str(exc))
        return SourceTransmissionConstructionResult(None, None, AuditResult((finding,)))


def audit_source_transmission(*args: Any, **kwargs: Any) -> AuditResult:
    return construct_source_transmission(*args, **kwargs).audit
