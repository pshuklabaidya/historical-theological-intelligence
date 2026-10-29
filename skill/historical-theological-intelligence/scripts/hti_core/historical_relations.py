"""Validated Phase 5 Historical Relation Graph.

The graph links accepted Phase 3 dossiers or propositions through typed
historical claims. It composes with Phase 4 uncertainty views and never copies
argument content, mutates upstream evidence, or performs lineage traversal.
"""

from __future__ import annotations

import copy
import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

from .argument_architecture import (
    HISTORICAL_RELATION_TYPES as PHASE3_RESERVED_HISTORICAL_TYPES,
    LOGICAL_RELATION_TYPES,
    ArgumentDossier,
)
from .audit import AuditFinding, AuditResult
from .dependency_uncertainty import (
    DependencyUncertaintyAnalysis,
    TargetUncertaintyState,
)
from .hashing import canonical_json, sha256_json
from .model import EVIDENCE_STATES, ValidationError
from .provenance import ProvenanceRecord
from .relations import V01_TYPED_RELATIONSHIPS
from .source_representation import DerivationKind
from .uncertainty import V01_QUALITATIVE_CONFIDENCE


class HistoricalRelationError(ValidationError):
    """Raised when a Historical Relation Graph claim fails closed."""


class HistoricalRelationType(str, Enum):
    DIRECT_QUOTATION = "DIRECT_QUOTATION"
    DIRECT_DEPENDENCE = "DIRECT_DEPENDENCE"
    MEDIATED_DEPENDENCE = "MEDIATED_DEPENDENCE"
    SHARED_SOURCE = "SHARED_SOURCE"
    INHERITED_COMMONPLACE = "INHERITED_COMMONPLACE"
    CONCEPTUAL_AFFINITY = "CONCEPTUAL_AFFINITY"
    INDEPENDENT_CONVERGENCE = "INDEPENDENT_CONVERGENCE"
    RECEPTION = "RECEPTION"
    TRANSFORMATION = "TRANSFORMATION"
    REVIVAL = "REVIVAL"
    REJECTION = "REJECTION"


class HistoricalClaimState(str, Enum):
    CANDIDATE = "CANDIDATE"
    SUPPORTED = "SUPPORTED"
    ESTABLISHED = "ESTABLISHED"
    UNRESOLVED = "UNRESOLVED"
    REJECTED = "REJECTED"


class HistoricalNodeKind(str, Enum):
    ARGUMENT = "ARGUMENT"
    ARGUMENT_COMPONENT = "ARGUMENT_COMPONENT"
    PROPOSITION = "PROPOSITION"


class RelationScope(str, Enum):
    PHRASE = "PHRASE"
    PROPOSITION = "PROPOSITION"
    ARGUMENT_COMPONENT = "ARGUMENT_COMPONENT"
    ARGUMENT = "ARGUMENT"
    UNRESOLVED = "UNRESOLVED"


class ChronologyState(str, Enum):
    COMPATIBLE = "COMPATIBLE"
    POSSIBLE = "POSSIBLE"
    UNRESOLVED = "UNRESOLVED"
    CONTRADICTED = "CONTRADICTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class AccessState(str, Enum):
    ESTABLISHED = "ESTABLISHED"
    PLAUSIBLE = "PLAUSIBLE"
    UNRESOLVED = "UNRESOLVED"
    CONTRADICTED = "CONTRADICTED"
    IMPOSSIBLE = "IMPOSSIBLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EvidenceInspectionLevel(str, Enum):
    PRIMARY_PASSAGE = "PRIMARY_PASSAGE"
    PRIMARY_METADATA = "PRIMARY_METADATA"
    OCR_LOCATOR = "OCR_LOCATOR"
    SECONDARY_REPORT = "SECONDARY_REPORT"
    FIXTURE_STIPULATION = "FIXTURE_STIPULATION"
    INFERENCE = "INFERENCE"


class HistoricalEvidenceKind(str, Enum):
    QUOTATION_MATCH = "QUOTATION_MATCH"
    DISTINCTIVE_WORDING = "DISTINCTIVE_WORDING"
    UNUSUAL_ORDERING = "UNUSUAL_ORDERING"
    SHARED_OMISSION = "SHARED_OMISSION"
    SHARED_MISTRANSLATION = "SHARED_MISTRANSLATION"
    SHARED_ERRONEOUS_CITATION = "SHARED_ERRONEOUS_CITATION"
    SHARED_TEXTUAL_VARIANT = "SHARED_TEXTUAL_VARIANT"
    DISTINCTIVE_ABBREVIATION = "DISTINCTIVE_ABBREVIATION"
    AUTHORITY_SEQUENCE = "AUTHORITY_SEQUENCE"
    EDITION_FEATURE = "EDITION_FEATURE"
    DOCUMENTED_ACCESS = "DOCUMENTED_ACCESS"
    DOCUMENTED_ENGAGEMENT = "DOCUMENTED_ENGAGEMENT"
    NAMED_INTERMEDIARY = "NAMED_INTERMEDIARY"
    SHARED_SOURCE_IDENTIFICATION = "SHARED_SOURCE_IDENTIFICATION"
    TRADITIONAL_DISTRIBUTION = "TRADITIONAL_DISTRIBUTION"
    SUBSTANTIVE_CORRESPONDENCE = "SUBSTANTIVE_CORRESPONDENCE"
    INDEPENDENT_ACCESS = "INDEPENDENT_ACCESS"
    COMMON_PROBLEM_OR_CANONICAL_SOURCE = "COMMON_PROBLEM_OR_CANONICAL_SOURCE"
    DISCRIMINATING_DIFFERENCE = "DISCRIMINATING_DIFFERENCE"
    TRANSFORMATION_CHANGE = "TRANSFORMATION_CHANGE"
    DISCONTINUITY_AND_RECOVERY = "DISCONTINUITY_AND_RECOVERY"
    EXPLICIT_REJECTION = "EXPLICIT_REJECTION"
    CHRONOLOGY = "CHRONOLOGY"
    ACCESSIBILITY = "ACCESSIBILITY"
    OTHER = "OTHER"


class DiscoverySignal(str, Enum):
    MACHINE_SIMILARITY = "MACHINE_SIMILARITY"
    EMBEDDING_SIMILARITY = "EMBEDDING_SIMILARITY"
    NGRAM_OVERLAP = "NGRAM_OVERLAP"
    STYLOMETRIC_PROXIMITY = "STYLOMETRIC_PROXIMITY"
    CITATION_NETWORK_PROXIMITY = "CITATION_NETWORK_PROXIMITY"
    KEYWORD_OVERLAP = "KEYWORD_OVERLAP"
    THEMATIC_SIMILARITY = "THEMATIC_SIMILARITY"
    GENERIC_AGREEMENT = "GENERIC_AGREEMENT"
    SHARED_BIBLICAL_TEXT = "SHARED_BIBLICAL_TEXT"
    CHRONOLOGY_ONLY = "CHRONOLOGY_ONLY"
    FAILURE_TO_FIND = "FAILURE_TO_FIND"


class UncertaintyRelevance(str, Enum):
    CRITICAL = "CRITICAL"
    RELEVANT = "RELEVANT"
    IRRELEVANT = "IRRELEVANT"
    UNRESOLVED = "UNRESOLVED"


HISTORICAL_RELATION_TYPES = frozenset(item.value for item in HistoricalRelationType)
SYMMETRIC_HISTORICAL_RELATIONS = frozenset(
    {
        HistoricalRelationType.SHARED_SOURCE.value,
        HistoricalRelationType.CONCEPTUAL_AFFINITY.value,
        HistoricalRelationType.INDEPENDENT_CONVERGENCE.value,
    }
)
DIRECTIONAL_HISTORICAL_RELATIONS = HISTORICAL_RELATION_TYPES - SYMMETRIC_HISTORICAL_RELATIONS
ACTIVE_CLAIM_STATES = frozenset(
    {HistoricalClaimState.SUPPORTED.value, HistoricalClaimState.ESTABLISHED.value}
)

_DEPENDENCE_FEATURES = frozenset(
    {
        HistoricalEvidenceKind.DISTINCTIVE_WORDING.value,
        HistoricalEvidenceKind.UNUSUAL_ORDERING.value,
        HistoricalEvidenceKind.SHARED_OMISSION.value,
        HistoricalEvidenceKind.SHARED_MISTRANSLATION.value,
        HistoricalEvidenceKind.SHARED_ERRONEOUS_CITATION.value,
        HistoricalEvidenceKind.SHARED_TEXTUAL_VARIANT.value,
        HistoricalEvidenceKind.DISTINCTIVE_ABBREVIATION.value,
        HistoricalEvidenceKind.AUTHORITY_SEQUENCE.value,
        HistoricalEvidenceKind.EDITION_FEATURE.value,
    }
)
_ENGAGEMENT_TYPES = frozenset(
    {
        HistoricalRelationType.RECEPTION.value,
        HistoricalRelationType.TRANSFORMATION.value,
        HistoricalRelationType.REVIVAL.value,
        HistoricalRelationType.REJECTION.value,
    }
)
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_NUMERIC_CONFIDENCE_KEYS = frozenset(
    {
        "probability", "percentage", "confidence_score", "confidence_probability",
        "numeric_confidence", "relation_probability",
    }
)


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise HistoricalRelationError(f"{label} must be an object")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HistoricalRelationError(f"{label} must be non-empty text")
    return value


def _identifier(value: Any, label: str) -> str:
    value = _text(value, label)
    if not _ID.fullmatch(value):
        raise HistoricalRelationError(f"{label} must be a stable identifier")
    return value


def _enum(value: Any, kind: type[Enum], label: str) -> str:
    if not isinstance(value, str):
        raise HistoricalRelationError(f"{label} must be a declared string value")
    try:
        kind(value)
    except ValueError as exc:
        raise HistoricalRelationError(f"invalid {label} {value!r}") from exc
    return value


def _reject_numeric_confidence(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in _NUMERIC_CONFIDENCE_KEYS:
                raise HistoricalRelationError(
                    "numerical confidence is outside the Historical Relation Graph"
                )
            _reject_numeric_confidence(item)
    elif isinstance(value, list):
        for item in value:
            _reject_numeric_confidence(item)


def _ordered_ids(value: Any, label: str, *, required: bool = False) -> tuple[str, ...]:
    if value is None and not required:
        return ()
    if not isinstance(value, list):
        raise HistoricalRelationError(f"{label} must be an ordered list")
    result = tuple(_identifier(item, f"{label} item") for item in value)
    if len(result) != len(set(result)):
        raise HistoricalRelationError(f"{label} must not contain duplicate identifiers")
    return result


def _unique(items: Iterable[Any], attribute: str, label: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in items:
        identity = getattr(item, attribute)
        if identity in result:
            raise HistoricalRelationError(f"duplicate {label} {identity}")
        result[identity] = item
    return result


def _dossier_map(dossiers: Iterable[ArgumentDossier] | Mapping[str, ArgumentDossier]) -> dict[str, ArgumentDossier]:
    entries = tuple(dossiers.values()) if isinstance(dossiers, Mapping) else tuple(dossiers)
    result = {item.dossier_id: item for item in entries}
    if len(result) != len(entries):
        raise HistoricalRelationError("dossier ids must be unique")
    return result


def _contains_phrase(span_text: Any, phrase: str) -> bool:
    if not isinstance(span_text, str):
        return False
    normalized_phrase = " ".join(unicodedata.normalize("NFC", phrase).casefold().split())
    normalized_span = " ".join(unicodedata.normalize("NFC", span_text).casefold().split())
    return normalized_phrase in normalized_span


def _span_contains_text(source_span: Any, phrase: str) -> bool:
    """A literal string or explicit text field can verify the quoted phrase."""
    return _contains_phrase(source_span.get("text") if isinstance(source_span, dict) else source_span, phrase)


def _source_locator(source_span: Any) -> str | None:
    if isinstance(source_span, str):
        return source_span
    if isinstance(source_span, dict):
        locator = source_span.get("locator")
        return locator if isinstance(locator, str) and locator.strip() else None
    return None


def _canonical_locator(source_span: Any) -> str | None:
    locator = _source_locator(source_span)
    return " ".join(unicodedata.normalize("NFC", locator).split()) if locator else None


@dataclass(frozen=True)
class HistoricalNodeReference:
    """Reference to a Phase 3 argument, component, or proposition."""

    _raw: Mapping[str, Any] = field(repr=False)
    evidence_roots: tuple[str, ...]

    @classmethod
    def from_dict(
        cls, value: Any, dossiers: Mapping[str, ArgumentDossier]
    ) -> "HistoricalNodeReference":
        raw = _object(value, "historical node")
        node_id = _identifier(raw.get("node_id"), "historical node_id")
        dossier_id = _identifier(raw.get("dossier_id"), "historical node dossier_id")
        if dossier_id not in dossiers:
            raise HistoricalRelationError(f"node {node_id} references unknown dossier {dossier_id}")
        dossier = dossiers[dossier_id]
        kind = _enum(raw.get("node_kind"), HistoricalNodeKind, "historical node kind")
        proposition_id = raw.get("proposition_id")
        if proposition_id is not None:
            proposition_id = _identifier(proposition_id, "historical node proposition_id")
            try:
                proposition = dossier.proposition(proposition_id)
            except ValidationError as exc:
                raise HistoricalRelationError(
                    f"node {node_id} references unknown proposition {proposition_id}"
                ) from exc
            if kind == HistoricalNodeKind.ARGUMENT.value:
                raise HistoricalRelationError("argument node cannot carry a proposition_id")
            roots = tuple(
                sorted({root for link in proposition.source_links for root in link.evidence_roots})
            )
        else:
            if kind != HistoricalNodeKind.ARGUMENT.value:
                raise HistoricalRelationError(
                    "argument-component or proposition node requires proposition_id"
                )
            roots = tuple(
                sorted(
                    {
                        root
                        for proposition in dossier.propositions
                        for link in proposition.source_links
                        for root in link.evidence_roots
                    }
                )
            )
        if raw.get("argument_id") != dossier.argument_id:
            raise HistoricalRelationError(f"node {node_id} argument_id does not match dossier")
        if raw.get("anchor_representation_id") != dossier.anchor_representation_id:
            raise HistoricalRelationError(
                f"node {node_id} anchor representation does not match dossier"
            )
        work_id = raw.get("work_id")
        dossier_work_id = dossier.to_dict().get("work_id")
        if work_id is not None:
            _identifier(work_id, "historical node work_id")
            if dossier_work_id is not None and work_id != dossier_work_id:
                raise HistoricalRelationError(f"node {node_id} work identity conflicts with dossier")
        evidence_state = raw.get("evidence_state")
        if evidence_state is not None and evidence_state not in EVIDENCE_STATES:
            raise HistoricalRelationError(f"node {node_id} has invalid evidence_state")
        for label in ("date", "historical_location", "historical_context"):
            item = raw.get(label)
            if item is not None and not isinstance(item, (str, dict)):
                raise HistoricalRelationError(f"node {node_id} {label} must be text or an object")
        provenance = raw.get("provenance")
        if provenance is None:
            raise HistoricalRelationError(f"node {node_id} requires provenance")
        ProvenanceRecord.from_dict(provenance)
        supplied_roots = raw.get("evidence_roots")
        if supplied_roots is not None and _ordered_ids(supplied_roots, "node evidence_roots") != roots:
            raise HistoricalRelationError(
                f"node {node_id} evidence roots must match its Phase 3 source links"
            )
        return cls(copy.deepcopy(raw), roots)

    @property
    def node_id(self) -> str:
        return str(self._raw["node_id"])

    @property
    def dossier_id(self) -> str:
        return str(self._raw["dossier_id"])

    @property
    def proposition_id(self) -> str | None:
        value = self._raw.get("proposition_id")
        return str(value) if value is not None else None

    def to_dict(self) -> dict[str, Any]:
        value = copy.deepcopy(dict(self._raw))
        value["evidence_roots"] = list(self.evidence_roots)
        return value


@dataclass(frozen=True)
class HistoricalEvidenceItem:
    """One provenance-bearing historical evidence assertion."""

    _raw: Mapping[str, Any] = field(repr=False)
    evidence_roots: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: Any, label: str) -> "HistoricalEvidenceItem":
        raw = _object(value, label)
        _identifier(raw.get("evidence_id"), f"{label} evidence_id")
        _enum(raw.get("kind"), HistoricalEvidenceKind, f"{label} kind")
        _enum(
            raw.get("inspection_level"), EvidenceInspectionLevel,
            f"{label} inspection_level",
        )
        _text(raw.get("description"), f"{label} description")
        roots = _ordered_ids(raw.get("evidence_roots"), f"{label} evidence_roots", required=True)
        if not roots:
            raise HistoricalRelationError(f"{label} requires at least one evidence root")
        provenance = raw.get("provenance")
        if provenance is None:
            raise HistoricalRelationError(f"{label} requires provenance")
        ProvenanceRecord.from_dict(provenance)
        return cls(copy.deepcopy(raw), roots)

    @property
    def evidence_id(self) -> str:
        return str(self._raw["evidence_id"])

    @property
    def kind(self) -> str:
        return str(self._raw["kind"])

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class ChronologyAssessment:
    _raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, value: Any) -> "ChronologyAssessment":
        raw = _object(value, "chronology assessment")
        state = _enum(raw.get("state"), ChronologyState, "chronology state")
        antecedent = raw.get("antecedent_year")
        recipient = raw.get("recipient_year")
        for year, label in ((antecedent, "antecedent_year"), (recipient, "recipient_year")):
            if year is not None and (not isinstance(year, int) or isinstance(year, bool)):
                raise HistoricalRelationError(f"{label} must be an integer year")
        if antecedent is not None and recipient is not None and antecedent > recipient:
            if state != ChronologyState.CONTRADICTED.value:
                raise HistoricalRelationError("impossible chronology must be marked CONTRADICTED")
        _text(raw.get("rationale"), "chronology rationale")
        ProvenanceRecord.from_dict(raw.get("provenance"))
        return cls(copy.deepcopy(raw))

    @property
    def state(self) -> str:
        return str(self._raw["state"])

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class AccessAssessment:
    _raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, value: Any) -> "AccessAssessment":
        raw = _object(value, "access assessment")
        _enum(raw.get("state"), AccessState, "access state")
        channel = raw.get("channel")
        if channel is not None:
            _text(channel, "access channel")
        _text(raw.get("rationale"), "access rationale")
        ProvenanceRecord.from_dict(raw.get("provenance"))
        return cls(copy.deepcopy(raw))

    @property
    def state(self) -> str:
        return str(self._raw["state"])

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class HistoricalRelationAlternative:
    _raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, value: Any) -> "HistoricalRelationAlternative":
        raw = _object(value, "historical relation alternative")
        _identifier(raw.get("alternative_id"), "alternative_id")
        _enum(raw.get("relation_type"), HistoricalRelationType, "alternative relation type")
        _enum(raw.get("claim_state"), HistoricalClaimState, "alternative claim state")
        _text(raw.get("rationale"), "alternative rationale")
        ProvenanceRecord.from_dict(raw.get("provenance"))
        return cls(copy.deepcopy(raw))

    @property
    def alternative_id(self) -> str:
        return str(self._raw["alternative_id"])

    @property
    def relation_type(self) -> str:
        return str(self._raw["relation_type"])

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class HistoricalUncertaintyLink:
    """Validated Phase 4 result attached without changing relation confidence."""

    _raw: Mapping[str, Any] = field(repr=False)
    phase4_view: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(
        cls,
        value: Any,
        analyses: Mapping[str, DependencyUncertaintyAnalysis],
        endpoint_dossiers: frozenset[str],
    ) -> "HistoricalUncertaintyLink":
        raw = _object(value, "historical uncertainty link")
        dossier_id = _identifier(raw.get("dossier_id"), "uncertainty dossier_id")
        if dossier_id not in endpoint_dossiers:
            raise HistoricalRelationError("historical uncertainty crosses unrelated dossiers")
        if dossier_id not in analyses:
            raise HistoricalRelationError(
                f"uncertainty link requires Phase 4 analysis for dossier {dossier_id}"
            )
        proposition_id = _identifier(raw.get("proposition_id"), "uncertainty proposition_id")
        interpretation_id = raw.get("interpretation_id")
        if interpretation_id is not None:
            interpretation_id = _identifier(interpretation_id, "uncertainty interpretation_id")
        relevance = _enum(
            raw.get("relevance"), UncertaintyRelevance, "uncertainty relevance"
        )
        _text(raw.get("rationale"), "uncertainty relevance rationale")
        view = analyses[dossier_id].future_consumer_view(
            proposition_id, interpretation_id=interpretation_id
        )
        declared = raw.get("uncertainty_state")
        if declared is not None and declared != view["uncertainty_state"]:
            raise HistoricalRelationError("declared upstream uncertainty does not match Phase 4")
        if relevance == UncertaintyRelevance.IRRELEVANT.value and not raw.get("rationale"):
            raise HistoricalRelationError("irrelevant uncertainty requires rationale")
        return cls(copy.deepcopy(raw), copy.deepcopy(view))

    @property
    def state(self) -> str:
        return str(self.phase4_view["uncertainty_state"])

    @property
    def relevance(self) -> str:
        return str(self._raw["relevance"])

    def to_dict(self) -> dict[str, Any]:
        value = copy.deepcopy(dict(self._raw))
        value["uncertainty_state"] = self.state
        value["active_root_ids"] = list(self.phase4_view["active_root_ids"])
        value["phase4_audit_trail"] = copy.deepcopy(self.phase4_view["audit_trail"])
        return value


@dataclass(frozen=True)
class HistoricalRelationEdge:
    """One typed and evidence-licensed historical relation claim."""

    _raw: Mapping[str, Any] = field(repr=False)
    positive_evidence: tuple[HistoricalEvidenceItem, ...]
    discriminating_features: tuple[HistoricalEvidenceItem, ...]
    counterevidence: tuple[HistoricalEvidenceItem, ...]
    alternatives: tuple[HistoricalRelationAlternative, ...]
    chronology: ChronologyAssessment
    access: AccessAssessment
    upstream_uncertainty: tuple[HistoricalUncertaintyLink, ...]
    evidence_roots: tuple[str, ...]

    @classmethod
    def from_dict(
        cls,
        value: Any,
        nodes: Mapping[str, HistoricalNodeReference],
        analyses: Mapping[str, DependencyUncertaintyAnalysis],
        dossiers: Mapping[str, ArgumentDossier],
    ) -> "HistoricalRelationEdge":
        raw = _object(value, "historical relation edge")
        _reject_numeric_confidence(raw)
        edge_id = _identifier(raw.get("edge_id"), "historical edge_id")
        relation_type = _enum(
            raw.get("relation_type"), HistoricalRelationType, "historical relation type"
        )
        confidence = raw.get("confidence")
        if confidence not in V01_QUALITATIVE_CONFIDENCE:
            raise HistoricalRelationError(f"invalid qualitative confidence {confidence!r}")
        claim_state = _enum(raw.get("claim_state"), HistoricalClaimState, "claim state")
        scope = _enum(raw.get("scope"), RelationScope, "relation scope")
        source_id = _identifier(raw.get("source_node_id"), "historical source_node_id")
        target_id = _identifier(raw.get("target_node_id"), "historical target_node_id")
        if source_id == target_id:
            raise HistoricalRelationError(f"edge {edge_id} requires distinct endpoints")
        if source_id not in nodes or target_id not in nodes:
            raise HistoricalRelationError(f"edge {edge_id} has an invalid endpoint")
        if relation_type in SYMMETRIC_HISTORICAL_RELATIONS and source_id > target_id:
            raise HistoricalRelationError(
                f"symmetric edge {edge_id} endpoints must use canonical lexical order"
            )
        _text(raw.get("audit_rationale"), f"edge {edge_id} audit_rationale")
        ProvenanceRecord.from_dict(raw.get("provenance"))

        def parse_items(field_name: str) -> tuple[HistoricalEvidenceItem, ...]:
            entries = raw.get(field_name, [])
            if not isinstance(entries, list):
                raise HistoricalRelationError(f"edge {edge_id} {field_name} must be a list")
            parsed = tuple(
                HistoricalEvidenceItem.from_dict(item, f"edge {edge_id} {field_name}")
                for item in entries
            )
            _unique(parsed, "evidence_id", f"{field_name} evidence id")
            return parsed

        positive = parse_items("positive_evidence")
        discriminating = parse_items("discriminating_features")
        counter = parse_items("counterevidence")
        all_evidence = (*positive, *discriminating, *counter)
        all_ids = [item.evidence_id for item in all_evidence]
        if len(all_ids) != len(set(all_ids)):
            raise HistoricalRelationError(f"edge {edge_id} reuses an evidence id")

        raw_alternatives = raw.get("unresolved_alternatives", [])
        if not isinstance(raw_alternatives, list):
            raise HistoricalRelationError("unresolved_alternatives must be a list")
        alternatives = tuple(
            HistoricalRelationAlternative.from_dict(item) for item in raw_alternatives
        )
        _unique(alternatives, "alternative_id", "historical alternative id")
        if any(item.relation_type == relation_type for item in alternatives):
            raise HistoricalRelationError("alternative must differ from the asserted relation type")

        chronology = ChronologyAssessment.from_dict(raw.get("chronology"))
        access = AccessAssessment.from_dict(raw.get("access"))
        raw_signals = raw.get("discovery_signals", [])
        if not isinstance(raw_signals, list):
            raise HistoricalRelationError("discovery_signals must be a list")
        signals = tuple(_enum(item, DiscoverySignal, "discovery signal") for item in raw_signals)
        if len(signals) != len(set(signals)):
            raise HistoricalRelationError("discovery_signals must not contain duplicates")

        endpoint_dossiers = frozenset(
            {nodes[source_id].dossier_id, nodes[target_id].dossier_id}
        )
        raw_uncertainty = raw.get("upstream_uncertainty", [])
        if not isinstance(raw_uncertainty, list):
            raise HistoricalRelationError("upstream_uncertainty must be a list")
        uncertainty = tuple(
            HistoricalUncertaintyLink.from_dict(item, analyses, endpoint_dossiers)
            for item in raw_uncertainty
        )
        uncertainty_keys = [
            (item.to_dict()["dossier_id"], item.to_dict()["proposition_id"], item.to_dict().get("interpretation_id"))
            for item in uncertainty
        ]
        if len(uncertainty_keys) != len(set(uncertainty_keys)):
            raise HistoricalRelationError("duplicate upstream uncertainty link")

        roots = tuple(sorted({root for item in all_evidence for root in item.evidence_roots}))
        supplied_roots = raw.get("evidence_roots")
        if supplied_roots is not None and _ordered_ids(
            supplied_roots, "historical edge evidence_roots"
        ) != roots:
            raise HistoricalRelationError(
                f"edge {edge_id} evidence_roots must equal its evidence ancestry"
            )

        result = cls(
            copy.deepcopy(raw), positive, discriminating, counter, alternatives,
            chronology, access, uncertainty, roots,
        )
        result._validate_semantics(nodes, signals, scope, claim_state)
        result._validate_endpoint_integrity(nodes, dossiers, scope)
        return result

    def _validate_endpoint_integrity(
        self,
        nodes: Mapping[str, HistoricalNodeReference],
        dossiers: Mapping[str, ArgumentDossier],
        scope: str,
    ) -> None:
        # Phrase/proposition claims must not borrow an unrelated proposition's
        # passage merely because it is on the same page or evidence root.
        if not self.active:
            return
        narrow_scope = scope in {RelationScope.PHRASE.value, RelationScope.PROPOSITION.value}
        proposition_quotation = (
            self.relation_type == HistoricalRelationType.DIRECT_QUOTATION.value
            and any(nodes[node_id].to_dict()["node_kind"] == HistoricalNodeKind.PROPOSITION.value
                    for node_id in (self.source_node_id, self.target_node_id))
        )
        if not narrow_scope and not proposition_quotation:
            return
        endpoint_ids = {self.source_node_id, self.target_node_id}
        for node_id in endpoint_ids:
            if nodes[node_id].proposition_id is None:
                raise HistoricalRelationError(
                    f"edge {self.edge_id} {scope} requires a validated proposition at each endpoint"
                )

        covered: set[str] = set()
        quotation_pairs: list[set[str]] = []
        for item in (*self.positive_evidence, *self.discriminating_features):
            evidence = item.to_dict()
            anchors = evidence.get("endpoint_spans", [])
            if not isinstance(anchors, list):
                raise HistoricalRelationError(f"edge {self.edge_id} endpoint_spans must be a list")
            matched_text = evidence.get("matched_text")
            if matched_text is not None:
                matched_text = _text(matched_text, "endpoint matched_text")
            quoted = (self.relation_type == HistoricalRelationType.DIRECT_QUOTATION.value
                      and item in self.positive_evidence
                      and item.kind == HistoricalEvidenceKind.QUOTATION_MATCH.value)
            if quoted and matched_text is None:
                raise HistoricalRelationError(
                    f"edge {self.edge_id} quotation evidence requires matched_text at both endpoints"
                )
            if quoted and evidence["inspection_level"] == EvidenceInspectionLevel.OCR_LOCATOR.value:
                raise HistoricalRelationError(
                    f"edge {self.edge_id} OCR locator cannot verify inspected quotation text"
                )
            item_covered: set[str] = set()
            item_roots: set[str] = set()
            for anchor in anchors:
                binding = _object(anchor, "endpoint span binding")
                node_id = _identifier(binding.get("node_id"), "endpoint span node_id")
                representation_id = _identifier(
                    binding.get("representation_id"), "endpoint span representation_id"
                )
                if node_id not in endpoint_ids:
                    raise HistoricalRelationError(
                        f"edge {self.edge_id} endpoint span names a non-endpoint node"
                    )
                span = binding.get("source_span")
                node = nodes[node_id]
                dossier = dossiers[node.dossier_id]
                literal_match = matched_text is not None and _span_contains_text(span, matched_text)
                recorded_links = [
                    (proposition.proposition_id, link)
                    for proposition in dossier.propositions
                    for link in proposition.source_links
                    if link.representation_id == representation_id
                ]
                exact_links = [
                    pair for pair in recorded_links
                    if span is not None and pair[1].to_dict().get("source_span") == span
                ]
                if not any(proposition_id == node.proposition_id for proposition_id, _ in exact_links):
                    raise HistoricalRelationError(
                        f"edge {self.edge_id} endpoint span is not a recorded source span "
                        f"of proposition {node.proposition_id}"
                    )
                locator = _canonical_locator(span) if quoted and not literal_match else None
                candidates = [
                    pair for pair in recorded_links
                    if _canonical_locator(pair[1].to_dict().get("source_span")) == locator
                ] if locator else exact_links
                shared_span = quoted and len(candidates) != 1
                if shared_span:
                    declared_provenance = binding.get("source_link_provenance")
                    if not isinstance(declared_provenance, dict):
                        raise HistoricalRelationError(
                            f"edge {self.edge_id} shared endpoint span lacks unique source-link provenance"
                        )
                    candidates = [
                        (proposition_id, link) for proposition_id, link in candidates
                        if link.to_dict().get("provenance") == declared_provenance
                    ]
                    if (len(candidates) != 1 or candidates[0][0] != node.proposition_id
                            or candidates[0] not in exact_links):
                        raise HistoricalRelationError(
                            f"edge {self.edge_id} shared endpoint span does not uniquely bind proposition {node.proposition_id}"
                        )
                    provenance_locator = declared_provenance.get("locator")
                    if not isinstance(provenance_locator, str) or not provenance_locator.strip() \
                            or _canonical_locator(provenance_locator) == _canonical_locator(span) \
                            or binding.get("observation_locator") != provenance_locator:
                        raise HistoricalRelationError(
                            f"edge {self.edge_id} shared endpoint span needs its distinct observed source-link locator"
                        )
                else:
                    candidates = [pair for pair in candidates if pair[0] == node.proposition_id]
                _, link = candidates[0]
                if quoted and matched_text is not None and (shared_span or not literal_match) \
                        and not _contains_phrase(dossier.proposition(node.proposition_id).to_dict()["content"], matched_text):
                    raise HistoricalRelationError(
                        f"edge {self.edge_id} quotation is not represented in proposition "
                        f"{node.proposition_id}; refine its validated content or source link"
                    )
                if matched_text is not None and not literal_match:
                    if not quoted:
                        raise HistoricalRelationError(
                            f"edge {self.edge_id} matched text is outside the recorded source span "
                            f"of proposition {node.proposition_id}"
                        )
                    observed_locator = binding.get("observation_locator")
                    acceptable_locators = {_source_locator(span)}
                    if shared_span:
                        acceptable_locators.add(link.to_dict()["provenance"].get("locator"))
                    if (item.to_dict().get("inspection_level") == EvidenceInspectionLevel.OCR_LOCATOR.value
                            or not isinstance(observed_locator, str) or not observed_locator.strip()
                            or observed_locator not in acceptable_locators):
                        raise HistoricalRelationError(
                            f"edge {self.edge_id} matched text is outside the recorded source span "
                            f"of proposition {node.proposition_id}; locator evidence requires a bounded observation"
                        )
                item_roots.update(link.evidence_roots)
                item_covered.add(node_id)
            covered.update(item_covered)
            if quoted:
                quotation_pairs.append(item_covered)
                if self.relation_type == HistoricalRelationType.DIRECT_QUOTATION.value \
                        and item_covered != endpoint_ids:
                    raise HistoricalRelationError(
                        f"edge {self.edge_id} quotation evidence must bind both endpoint propositions"
                    )
                if item_covered == endpoint_ids and set(item.evidence_roots) != item_roots:
                    raise HistoricalRelationError(
                        f"edge {self.edge_id} quotation evidence roots must equal both endpoint source-link ancestries"
                    )
        if covered != endpoint_ids:
            raise HistoricalRelationError(
                f"edge {self.edge_id} lacks positive evidence bound to each proposition's recorded source span"
            )
        if self.relation_type == HistoricalRelationType.DIRECT_QUOTATION.value and not any(
            pair == endpoint_ids for pair in quotation_pairs
        ):
            raise HistoricalRelationError(
                f"edge {self.edge_id} DIRECT_QUOTATION requires one quotation match bound to both endpoints"
            )

    def _validate_semantics(
        self,
        nodes: Mapping[str, HistoricalNodeReference],
        discovery_signals: tuple[str, ...],
        scope: str,
        claim_state: str,
    ) -> None:
        del nodes
        relation_type = self.relation_type
        active = claim_state in ACTIVE_CLAIM_STATES
        feature_kinds = {item.kind for item in (*self.positive_evidence, *self.discriminating_features)}
        discriminating_kinds = {item.kind for item in self.discriminating_features}

        if active and not self.positive_evidence:
            raise HistoricalRelationError("active historical relation requires positive evidence")
        if active and not self.evidence_roots:
            raise HistoricalRelationError("active historical relation requires evidence ancestry")
        if claim_state == HistoricalClaimState.ESTABLISHED.value and scope == RelationScope.UNRESOLVED.value:
            raise HistoricalRelationError("established historical relation requires bounded scope")
        if active and discovery_signals and not feature_kinds:
            raise HistoricalRelationError("discovery signals cannot establish a relation")

        if relation_type in DIRECTIONAL_HISTORICAL_RELATIONS and active:
            if self.chronology.state == ChronologyState.CONTRADICTED.value:
                raise HistoricalRelationError("impossible chronology rejects directed relation")
            if self.chronology.state == ChronologyState.NOT_APPLICABLE.value:
                raise HistoricalRelationError("directed relation requires chronology assessment")
        if relation_type in {
            HistoricalRelationType.DIRECT_QUOTATION.value,
            HistoricalRelationType.DIRECT_DEPENDENCE.value,
            HistoricalRelationType.MEDIATED_DEPENDENCE.value,
            *_ENGAGEMENT_TYPES,
        } and active:
            if self.access.state in {
                AccessState.CONTRADICTED.value,
                AccessState.IMPOSSIBLE.value,
                AccessState.NOT_APPLICABLE.value,
            }:
                raise HistoricalRelationError("historical engagement requires possible access")

        if not active:
            return
        if relation_type == HistoricalRelationType.DIRECT_QUOTATION.value:
            if HistoricalEvidenceKind.QUOTATION_MATCH.value not in feature_kinds:
                raise HistoricalRelationError("DIRECT_QUOTATION requires quotation evidence")
        elif relation_type == HistoricalRelationType.DIRECT_DEPENDENCE.value:
            if not (_DEPENDENCE_FEATURES & discriminating_kinds):
                raise HistoricalRelationError(
                    "DIRECT_DEPENDENCE requires discriminating correspondence"
                )
        elif relation_type == HistoricalRelationType.MEDIATED_DEPENDENCE.value:
            channel = self._raw.get("mediation_channel")
            intermediary = self._raw.get("intermediary_node_id")
            if not channel and not intermediary:
                raise HistoricalRelationError(
                    "MEDIATED_DEPENDENCE requires explicit mediation"
                )
            if not (
                HistoricalEvidenceKind.NAMED_INTERMEDIARY.value in feature_kinds
                or _DEPENDENCE_FEATURES & discriminating_kinds
            ):
                raise HistoricalRelationError(
                    "MEDIATED_DEPENDENCE requires evidence for the mediation claim"
                )
        elif relation_type == HistoricalRelationType.SHARED_SOURCE.value:
            shared = self._raw.get("shared_source_node_id")
            if not shared:
                raise HistoricalRelationError("SHARED_SOURCE requires shared_source_node_id")
            if HistoricalEvidenceKind.SHARED_SOURCE_IDENTIFICATION.value not in feature_kinds:
                raise HistoricalRelationError("SHARED_SOURCE requires identified shared-source evidence")
        elif relation_type == HistoricalRelationType.INHERITED_COMMONPLACE.value:
            if HistoricalEvidenceKind.TRADITIONAL_DISTRIBUTION.value not in feature_kinds:
                raise HistoricalRelationError(
                    "INHERITED_COMMONPLACE requires evidence of broad transmission"
                )
        elif relation_type == HistoricalRelationType.CONCEPTUAL_AFFINITY.value:
            if HistoricalEvidenceKind.SUBSTANTIVE_CORRESPONDENCE.value not in feature_kinds:
                raise HistoricalRelationError(
                    "CONCEPTUAL_AFFINITY requires substantive argumentative correspondence"
                )
        elif relation_type == HistoricalRelationType.INDEPENDENT_CONVERGENCE.value:
            allowed = {
                HistoricalEvidenceKind.INDEPENDENT_ACCESS.value,
                HistoricalEvidenceKind.COMMON_PROBLEM_OR_CANONICAL_SOURCE.value,
                HistoricalEvidenceKind.DISCRIMINATING_DIFFERENCE.value,
            }
            if not (allowed & feature_kinds):
                raise HistoricalRelationError(
                    "INDEPENDENT_CONVERGENCE requires positive independence evidence"
                )
        elif relation_type == HistoricalRelationType.RECEPTION.value:
            if HistoricalEvidenceKind.DOCUMENTED_ENGAGEMENT.value not in feature_kinds:
                raise HistoricalRelationError("RECEPTION requires historical engagement evidence")
        elif relation_type == HistoricalRelationType.TRANSFORMATION.value:
            required = {
                HistoricalEvidenceKind.DOCUMENTED_ENGAGEMENT.value,
                HistoricalEvidenceKind.TRANSFORMATION_CHANGE.value,
            }
            if not required <= feature_kinds:
                raise HistoricalRelationError("TRANSFORMATION requires reception and demonstrated change")
        elif relation_type == HistoricalRelationType.REVIVAL.value:
            required = {
                HistoricalEvidenceKind.DOCUMENTED_ENGAGEMENT.value,
                HistoricalEvidenceKind.DISCONTINUITY_AND_RECOVERY.value,
            }
            if not required <= feature_kinds:
                raise HistoricalRelationError("REVIVAL requires engagement and recovery after discontinuity")
        elif relation_type == HistoricalRelationType.REJECTION.value:
            required = {
                HistoricalEvidenceKind.DOCUMENTED_ENGAGEMENT.value,
                HistoricalEvidenceKind.EXPLICIT_REJECTION.value,
            }
            if not required <= feature_kinds:
                raise HistoricalRelationError("REJECTION requires engagement and explicit rejection")

    @property
    def edge_id(self) -> str:
        return str(self._raw["edge_id"])

    @property
    def relation_type(self) -> str:
        return str(self._raw["relation_type"])

    @property
    def confidence(self) -> str:
        return str(self._raw["confidence"])

    @property
    def claim_state(self) -> str:
        return str(self._raw["claim_state"])

    @property
    def source_node_id(self) -> str:
        return str(self._raw["source_node_id"])

    @property
    def target_node_id(self) -> str:
        return str(self._raw["target_node_id"])

    @property
    def active(self) -> bool:
        return self.claim_state in ACTIVE_CLAIM_STATES

    @property
    def uncertainty_constrained(self) -> bool:
        blocked = {
            TargetUncertaintyState.MATERIALLY_UNCERTAIN.value,
            TargetUncertaintyState.UNRESOLVED.value,
        }
        return any(
            item.relevance in {
                UncertaintyRelevance.CRITICAL.value,
                UncertaintyRelevance.RELEVANT.value,
                UncertaintyRelevance.UNRESOLVED.value,
            }
            and item.state in blocked
            for item in self.upstream_uncertainty
        )

    @property
    def independent_evidence_root_count(self) -> int:
        return len(set(self.evidence_roots))

    def to_dict(self) -> dict[str, Any]:
        value = copy.deepcopy(dict(self._raw))
        value["positive_evidence"] = [
            item.to_dict() for item in sorted(self.positive_evidence, key=lambda x: x.evidence_id)
        ]
        value["discriminating_features"] = [
            item.to_dict()
            for item in sorted(self.discriminating_features, key=lambda x: x.evidence_id)
        ]
        value["counterevidence"] = [
            item.to_dict() for item in sorted(self.counterevidence, key=lambda x: x.evidence_id)
        ]
        value["unresolved_alternatives"] = [
            item.to_dict() for item in sorted(self.alternatives, key=lambda x: x.alternative_id)
        ]
        value["chronology"] = self.chronology.to_dict()
        value["access"] = self.access.to_dict()
        value["upstream_uncertainty"] = [
            item.to_dict()
            for item in sorted(
                self.upstream_uncertainty,
                key=lambda x: (
                    x.to_dict()["dossier_id"], x.to_dict()["proposition_id"],
                    x.to_dict().get("interpretation_id") or "",
                ),
            )
        ]
        value["evidence_roots"] = list(self.evidence_roots)
        value["uncertainty_constrained"] = self.uncertainty_constrained
        return value


@dataclass(frozen=True)
class HistoricalRelationGraph:
    """Deterministic cross-dossier historical graph without traversal engines."""

    _raw: Mapping[str, Any] = field(repr=False)
    nodes: tuple[HistoricalNodeReference, ...]
    edges: tuple[HistoricalRelationEdge, ...]

    @classmethod
    def from_dict(
        cls,
        value: Any,
        dossiers: Iterable[ArgumentDossier] | Mapping[str, ArgumentDossier],
        uncertainty_analyses: Mapping[str, DependencyUncertaintyAnalysis] | None = None,
        explanation_registry: Any = None,
    ) -> "HistoricalRelationGraph":
        raw = _object(value, "Historical Relation Graph")
        _reject_numeric_confidence(raw)
        if raw.get("schema_version") != "1":
            raise HistoricalRelationError("Historical Relation Graph schema_version must be 1")
        _identifier(raw.get("graph_id"), "historical graph_id")
        dossier_by_id = _dossier_map(dossiers)
        analyses = dict(uncertainty_analyses or {})
        for dossier_id, analysis in analyses.items():
            if dossier_id not in dossier_by_id or analysis.dossier is not dossier_by_id[dossier_id]:
                raise HistoricalRelationError("Phase 4 analysis must match a graph dossier object")
        raw_nodes = raw.get("nodes")
        raw_edges = raw.get("edges")
        if not isinstance(raw_nodes, list) or not raw_nodes:
            raise HistoricalRelationError("Historical Relation Graph requires nodes")
        if not isinstance(raw_edges, list):
            raise HistoricalRelationError("Historical Relation Graph edges must be a list")
        nodes = tuple(HistoricalNodeReference.from_dict(item, dossier_by_id) for item in raw_nodes)
        node_by_id = _unique(nodes, "node_id", "historical node id")
        edges = tuple(
            HistoricalRelationEdge.from_dict(item, node_by_id, analyses, dossier_by_id)
            for item in raw_edges
        )
        _unique(edges, "edge_id", "historical edge id")
        for edge in edges:
            shared = edge._raw.get("shared_source_node_id")
            intermediary = edge._raw.get("intermediary_node_id")
            for referenced, label in ((shared, "shared source"), (intermediary, "intermediary")):
                if referenced is not None and referenced not in node_by_id:
                    raise HistoricalRelationError(
                        f"edge {edge.edge_id} references unknown {label} node {referenced}"
                    )
            if shared in {edge.source_node_id, edge.target_node_id}:
                raise HistoricalRelationError("shared source must differ from recipient endpoints")
        if "explanation_bindings" in raw:
            from .historical_explanation import records, validate_consumer
            bindings = raw["explanation_bindings"]
            if not isinstance(bindings, list) or explanation_registry is None or explanation_registry.argument is None:
                raise HistoricalRelationError("explanation bindings require the existing source integrity registry")
            consumers = records(explanation_registry.argument)
            seen = set()
            for binding in bindings:
                if not isinstance(binding,dict) or set(binding)!={"consumer_id","anchor_node_ids","snapshot"}:
                    raise HistoricalRelationError("invalid explanation consumer binding")
                key = binding["consumer_id"]
                if key not in consumers or key in seen:
                    raise HistoricalRelationError("missing or duplicate explanation consumer")
                seen.add(key); c=consumers[key]
                validate_consumer(explanation_registry.argument,c)
                if binding["snapshot"] != explanation_registry.argument.consumer_snapshot(key):
                    raise HistoricalRelationError("explanation consumer binding requires revalidation")
                anchors=_ordered_ids(binding["anchor_node_ids"],"explanation anchor nodes",required=True)
                if not anchors or not set(anchors)<=node_by_id.keys():
                    raise HistoricalRelationError("explanation requires existing graph anchors")
                props=set(c["historical_explanation"]["anchor_proposition_ids"])
                if {node_by_id[n].proposition_id for n in anchors} != props:
                    raise HistoricalRelationError("explanation anchors must match graph propositions")
                for n in anchors:
                    node=node_by_id[n]; dossier=dossier_by_id[node.dossier_id]
                    if dossier.to_dict().get("work_id") != explanation_registry.work_id:
                        raise HistoricalRelationError("explanation crosses current work")
                    proposition = dossier.proposition(node.proposition_id).to_dict()
                    integrity_prop = explanation_registry.argument.props[node.proposition_id]
                    if proposition["content"] != explanation_registry.nodes[integrity_prop["representation_id"]]["content"]:
                        raise HistoricalRelationError("explanation graph proposition differs from current ownership record")
                    for link in proposition["source_links"]:
                        scope = explanation_registry.dependency_scope(integrity_prop["representation_id"])
                        span = link.get("source_span")
                        if not isinstance(span,dict) or not set(span.get("span_ids",[])) <= scope.get(link["representation_id"],set()):
                            raise HistoricalRelationError("explanation graph source ancestry differs from current proposition")
                    if node.dossier_id not in analyses:
                        raise HistoricalRelationError("explanation requires current dependency uncertainty analysis")
                    state=analyses[node.dossier_id].future_consumer_view(node.proposition_id)["uncertainty_state"]
                    if c["status"]=="CURRENT" and state!="UNAFFECTED" and c["historical_explanation"]["confidence"] not in {"possible","unresolved"}:
                        raise HistoricalRelationError("upstream dependency uncertainty limits explanation confidence")
                    if c["status"]=="CURRENT" and state!="UNAFFECTED" and not c["historical_explanation"]["limitations"]:
                        raise HistoricalRelationError("upstream dependency uncertainty must remain visible")
        return cls(copy.deepcopy(raw), nodes, edges)

    @property
    def graph_id(self) -> str:
        return str(self._raw["graph_id"])

    @property
    def active_edges(self) -> tuple[HistoricalRelationEdge, ...]:
        return tuple(item for item in self.edges if item.active)

    @property
    def inactive_claims(self) -> tuple[HistoricalRelationEdge, ...]:
        return tuple(item for item in self.edges if not item.active)

    def node(self, node_id: str) -> HistoricalNodeReference:
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        raise HistoricalRelationError(f"unknown historical node {node_id!r}")

    def edge(self, edge_id: str) -> HistoricalRelationEdge:
        for edge in self.edges:
            if edge.edge_id == edge_id:
                return edge
        raise HistoricalRelationError(f"unknown historical edge {edge_id!r}")

    def to_dict(self) -> dict[str, Any]:
        value = {
            "schema_version": "1",
            "graph_id": self.graph_id,
            "nodes": [item.to_dict() for item in sorted(self.nodes, key=lambda x: x.node_id)],
            "edges": [item.to_dict() for item in sorted(self.edges, key=lambda x: x.edge_id)],
        }
        if "explanation_bindings" in self._raw:
            value["explanation_bindings"] = copy.deepcopy(self._raw["explanation_bindings"])
        return value

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())

    def sha256(self) -> str:
        return sha256_json(self.to_dict())


@dataclass(frozen=True)
class HistoricalRelationConstructionResult:
    graph: HistoricalRelationGraph
    audit: AuditResult

    def __post_init__(self) -> None:
        if not self.audit.passed:
            raise HistoricalRelationError("failed audit cannot produce a historical graph")

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "validated",
            "graph": self.graph.to_dict(),
            "graph_sha256": self.graph.sha256(),
            "audit": {
                "status": self.audit.status,
                "findings": self.audit.to_v01_strings(),
            },
        }


def audit_historical_relation_graph(
    value: Any,
    dossiers: Iterable[ArgumentDossier] | Mapping[str, ArgumentDossier],
    uncertainty_analyses: Mapping[str, DependencyUncertaintyAnalysis] | None = None,
    explanation_registry: Any = None,
) -> AuditResult:
    try:
        HistoricalRelationGraph.from_dict(value, dossiers, uncertainty_analyses, explanation_registry)
    except ValidationError as exc:
        return AuditResult((AuditFinding("HISTORICAL_RELATION_GRAPH_INVALID", str(exc)),))
    return AuditResult()


def construct_historical_relation_graph(
    value: Any,
    dossiers: Iterable[ArgumentDossier] | Mapping[str, ArgumentDossier],
    uncertainty_analyses: Mapping[str, DependencyUncertaintyAnalysis] | None = None,
    explanation_registry: Any = None,
) -> HistoricalRelationConstructionResult:
    audit = audit_historical_relation_graph(value, dossiers, uncertainty_analyses, explanation_registry)
    if not audit.passed:
        raise HistoricalRelationError(audit.findings[0].to_v01_string())
    graph = HistoricalRelationGraph.from_dict(value, dossiers, uncertainty_analyses, explanation_registry)
    return HistoricalRelationConstructionResult(graph, audit)


if HISTORICAL_RELATION_TYPES != PHASE3_RESERVED_HISTORICAL_TYPES:
    raise RuntimeError("Phase 5 historical ontology diverges from Phase 3 reservation")
if HISTORICAL_RELATION_TYPES & set(LOGICAL_RELATION_TYPES):
    raise RuntimeError("historical and proposition relation types must remain separate")
if HISTORICAL_RELATION_TYPES & set(V01_TYPED_RELATIONSHIPS):
    raise RuntimeError("historical and Dynamic Witness Graph relations must remain separate")
if HISTORICAL_RELATION_TYPES & {item.value for item in DerivationKind}:
    raise RuntimeError("historical and representation ancestry relations must remain separate")
