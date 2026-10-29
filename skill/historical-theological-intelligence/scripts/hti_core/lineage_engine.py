"""Validated Phase 6 anchor-relative bidirectional lineage traversal.

The engine consumes a validated Phase 5 HistoricalRelationGraph. It creates
deterministic views and bounded research-plan records, never historical edges.
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
    HistoricalClaimState,
    HistoricalRelationEdge,
    HistoricalRelationError,
    HistoricalRelationGraph,
    HistoricalRelationType,
)
from .model import ValidationError
from .provenance import ProvenanceRecord


class LineageError(ValidationError):
    """Raised when a lineage request or result fails closed."""


class TraversalDirection(str, Enum):
    BACKWARD = "BACKWARD"
    FORWARD = "FORWARD"
    BIDIRECTIONAL = "BIDIRECTIONAL"


class TraversalRelationFamily(str, Enum):
    GENEALOGICAL = "GENEALOGICAL"
    ENGAGEMENT = "ENGAGEMENT"
    SHARED_CONTEXT = "SHARED_CONTEXT"
    NON_GENEALOGICAL = "NON_GENEALOGICAL"


class TraversalTreatment(str, Enum):
    LINEAGE = "LINEAGE"
    ENGAGEMENT = "ENGAGEMENT"
    CONTEXTUAL = "CONTEXTUAL"


class HistoricalPeriod(str, Enum):
    BIBLICAL_CLASSICAL = "BIBLICAL_CLASSICAL"
    PATRISTIC = "PATRISTIC"
    MEDIEVAL = "MEDIEVAL"
    RENAISSANCE_REFORMATION = "RENAISSANCE_REFORMATION"
    EARLY_MODERN = "EARLY_MODERN"
    MODERN = "MODERN"
    CONTEMPORARY = "CONTEMPORARY"
    UNRESOLVED = "UNRESOLVED"


class GapKind(str, Enum):
    NO_ESTABLISHED_RELATION = "NO_ESTABLISHED_RELATION"
    SEARCH_INCOMPLETE = "SEARCH_INCOMPLETE"
    UNRESOLVED_DISCONTINUITY = "UNRESOLVED_DISCONTINUITY"
    POSITIVE_DISAPPEARANCE = "POSITIVE_DISAPPEARANCE"
    DIMINISHED_TRANSMISSION = "DIMINISHED_TRANSMISSION"
    REVIVAL_DISCONTINUITY = "REVIVAL_DISCONTINUITY"
    CYCLE_BOUNDARY = "CYCLE_BOUNDARY"
    DEPTH_BOUNDARY = "DEPTH_BOUNDARY"
    PERIOD_BOUNDARY = "PERIOD_BOUNDARY"


class ResearchPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"


class ResearchCompletionState(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    DISMISSED = "DISMISSED"


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_PERIOD_ORDER = {
    HistoricalPeriod.BIBLICAL_CLASSICAL.value: 0,
    HistoricalPeriod.PATRISTIC.value: 1,
    HistoricalPeriod.MEDIEVAL.value: 2,
    HistoricalPeriod.RENAISSANCE_REFORMATION.value: 3,
    HistoricalPeriod.EARLY_MODERN.value: 4,
    HistoricalPeriod.MODERN.value: 5,
    HistoricalPeriod.CONTEMPORARY.value: 6,
    HistoricalPeriod.UNRESOLVED.value: 99,
}


def _object(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise LineageError(f"{label} must be an object")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LineageError(f"{label} must be non-empty text")
    return value


def _identifier(value: Any, label: str) -> str:
    value = _text(value, label)
    if not _ID.fullmatch(value):
        raise LineageError(f"{label} must be a stable identifier")
    return value


def _enum(value: Any, kind: type[Enum], label: str) -> str:
    if not isinstance(value, str):
        raise LineageError(f"{label} must be a declared string value")
    try:
        kind(value)
    except ValueError as exc:
        raise LineageError(f"invalid {label} {value!r}") from exc
    return value


def _ordered_unique(values: Any, label: str) -> tuple[str, ...]:
    if values is None:
        return ()
    if not isinstance(values, list):
        raise LineageError(f"{label} must be an ordered list")
    result = tuple(_identifier(value, f"{label} item") for value in values)
    if len(result) != len(set(result)):
        raise LineageError(f"{label} must not contain duplicates")
    return result


def _period_from_year(year: int | None) -> str:
    if year is None:
        return HistoricalPeriod.UNRESOLVED.value
    if year <= 100:
        return HistoricalPeriod.BIBLICAL_CLASSICAL.value
    if year <= 600:
        return HistoricalPeriod.PATRISTIC.value
    if year <= 1400:
        return HistoricalPeriod.MEDIEVAL.value
    if year <= 1600:
        return HistoricalPeriod.RENAISSANCE_REFORMATION.value
    if year <= 1800:
        return HistoricalPeriod.EARLY_MODERN.value
    if year <= 1945:
        return HistoricalPeriod.MODERN.value
    return HistoricalPeriod.CONTEMPORARY.value


def _node_year(raw: Mapping[str, Any]) -> int | None:
    date = raw.get("date")
    if isinstance(date, int) and not isinstance(date, bool):
        return date
    if isinstance(date, dict):
        for key in ("year", "exact_year"):
            value = date.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                return value
    return None


def _node_period(raw: Mapping[str, Any]) -> str:
    declared = raw.get("historical_period")
    if declared is not None:
        return _enum(declared, HistoricalPeriod, "historical period")
    return _period_from_year(_node_year(raw))


@dataclass(frozen=True)
class RelationTraversalRule:
    relation_type: str
    family: str
    treatment: str
    directional: bool
    lineage_by_default: bool
    discontinuity_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation_type": self.relation_type,
            "family": self.family,
            "treatment": self.treatment,
            "directional": self.directional,
            "lineage_by_default": self.lineage_by_default,
            "discontinuity_required": self.discontinuity_required,
        }


def _rule(
    relation_type: HistoricalRelationType,
    family: TraversalRelationFamily,
    treatment: TraversalTreatment,
    *,
    directional: bool = True,
    lineage: bool = True,
    discontinuity: bool = False,
) -> RelationTraversalRule:
    return RelationTraversalRule(
        relation_type.value, family.value, treatment.value,
        directional, lineage, discontinuity,
    )


RELATION_TRAVERSAL: Mapping[str, RelationTraversalRule] = {
    HistoricalRelationType.DIRECT_QUOTATION.value: _rule(
        HistoricalRelationType.DIRECT_QUOTATION,
        TraversalRelationFamily.GENEALOGICAL,
        TraversalTreatment.LINEAGE,
    ),
    HistoricalRelationType.DIRECT_DEPENDENCE.value: _rule(
        HistoricalRelationType.DIRECT_DEPENDENCE,
        TraversalRelationFamily.GENEALOGICAL,
        TraversalTreatment.LINEAGE,
    ),
    HistoricalRelationType.MEDIATED_DEPENDENCE.value: _rule(
        HistoricalRelationType.MEDIATED_DEPENDENCE,
        TraversalRelationFamily.GENEALOGICAL,
        TraversalTreatment.LINEAGE,
    ),
    HistoricalRelationType.SHARED_SOURCE.value: _rule(
        HistoricalRelationType.SHARED_SOURCE,
        TraversalRelationFamily.SHARED_CONTEXT,
        TraversalTreatment.CONTEXTUAL,
        directional=False,
        lineage=False,
    ),
    HistoricalRelationType.INHERITED_COMMONPLACE.value: _rule(
        HistoricalRelationType.INHERITED_COMMONPLACE,
        TraversalRelationFamily.SHARED_CONTEXT,
        TraversalTreatment.CONTEXTUAL,
        lineage=False,
    ),
    HistoricalRelationType.CONCEPTUAL_AFFINITY.value: _rule(
        HistoricalRelationType.CONCEPTUAL_AFFINITY,
        TraversalRelationFamily.NON_GENEALOGICAL,
        TraversalTreatment.CONTEXTUAL,
        directional=False,
        lineage=False,
    ),
    HistoricalRelationType.INDEPENDENT_CONVERGENCE.value: _rule(
        HistoricalRelationType.INDEPENDENT_CONVERGENCE,
        TraversalRelationFamily.NON_GENEALOGICAL,
        TraversalTreatment.CONTEXTUAL,
        directional=False,
        lineage=False,
    ),
    HistoricalRelationType.RECEPTION.value: _rule(
        HistoricalRelationType.RECEPTION,
        TraversalRelationFamily.ENGAGEMENT,
        TraversalTreatment.ENGAGEMENT,
    ),
    HistoricalRelationType.TRANSFORMATION.value: _rule(
        HistoricalRelationType.TRANSFORMATION,
        TraversalRelationFamily.ENGAGEMENT,
        TraversalTreatment.ENGAGEMENT,
    ),
    HistoricalRelationType.REVIVAL.value: _rule(
        HistoricalRelationType.REVIVAL,
        TraversalRelationFamily.ENGAGEMENT,
        TraversalTreatment.ENGAGEMENT,
        discontinuity=True,
    ),
    HistoricalRelationType.REJECTION.value: _rule(
        HistoricalRelationType.REJECTION,
        TraversalRelationFamily.ENGAGEMENT,
        TraversalTreatment.ENGAGEMENT,
    ),
}


if set(RELATION_TRAVERSAL) != {item.value for item in HistoricalRelationType}:
    raise RuntimeError("Phase 6 traversal semantics do not cover every Phase 5 relation")


@dataclass(frozen=True)
class LineageAnchor:
    anchor_id: str
    graph_node_id: str
    dossier_id: str
    proposition_id: str | None
    argument_id: str
    work_id: str | None
    date: Any
    historical_period: str
    evidence_state: str | None
    evidence_roots: tuple[str, ...]
    upstream_uncertainty: tuple[Mapping[str, Any], ...]

    @classmethod
    def from_dict(cls, value: Any, graph: HistoricalRelationGraph) -> "LineageAnchor":
        raw = _object(value, "lineage anchor")
        anchor_id = _identifier(raw.get("anchor_id"), "anchor_id")
        graph_node_id = raw.get("graph_node_id")
        dossier_id = raw.get("dossier_id")
        proposition_id = raw.get("proposition_id")
        if graph_node_id is not None:
            graph_node_id = _identifier(graph_node_id, "anchor graph_node_id")
            try:
                node = graph.node(graph_node_id)
            except HistoricalRelationError as exc:
                raise LineageError(f"unknown anchor graph node {graph_node_id}") from exc
            if dossier_id is not None and dossier_id != node.dossier_id:
                raise LineageError("anchor dossier_id conflicts with graph node")
            if proposition_id is not None and proposition_id != node.proposition_id:
                raise LineageError("anchor proposition_id conflicts with graph node")
        else:
            if dossier_id is None:
                raise LineageError("anchor requires graph_node_id or dossier_id")
            dossier_id = _identifier(dossier_id, "anchor dossier_id")
            if proposition_id is not None:
                proposition_id = _identifier(proposition_id, "anchor proposition_id")
            matches = [
                node for node in graph.nodes
                if node.dossier_id == dossier_id
                and (proposition_id is None or node.proposition_id == proposition_id)
            ]
            if len(matches) != 1:
                raise LineageError("anchor must resolve to exactly one Historical Relation Graph node")
            node = matches[0]
            graph_node_id = node.node_id
        node_raw = node.to_dict()
        uncertainty: list[Mapping[str, Any]] = []
        for edge in graph.edges:
            if node.node_id in {edge.source_node_id, edge.target_node_id}:
                for link in edge.to_dict().get("upstream_uncertainty", []):
                    if link.get("dossier_id") == node.dossier_id:
                        uncertainty.append(copy.deepcopy(link))
        uncertainty.sort(
            key=lambda item: (
                item.get("proposition_id", ""), item.get("interpretation_id", ""),
                item.get("relevance", ""),
            )
        )
        return cls(
            anchor_id=anchor_id,
            graph_node_id=graph_node_id,
            dossier_id=node.dossier_id,
            proposition_id=node.proposition_id,
            argument_id=str(node_raw["argument_id"]),
            work_id=node_raw.get("work_id"),
            date=copy.deepcopy(node_raw.get("date")),
            historical_period=_node_period(node_raw),
            evidence_state=node_raw.get("evidence_state"),
            evidence_roots=tuple(node.evidence_roots),
            upstream_uncertainty=tuple(uncertainty),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "anchor_id": self.anchor_id,
            "graph_node_id": self.graph_node_id,
            "dossier_id": self.dossier_id,
            "proposition_id": self.proposition_id,
            "argument_id": self.argument_id,
            "work_id": self.work_id,
            "date": copy.deepcopy(self.date),
            "historical_period": self.historical_period,
            "evidence_state": self.evidence_state,
            "evidence_roots": list(self.evidence_roots),
            "upstream_uncertainty": copy.deepcopy(list(self.upstream_uncertainty)),
        }


@dataclass(frozen=True)
class TraversalPolicy:
    direction: str = TraversalDirection.BIDIRECTIONAL.value
    maximum_depth: int = 4
    permitted_families: tuple[str, ...] = (
        TraversalRelationFamily.GENEALOGICAL.value,
        TraversalRelationFamily.ENGAGEMENT.value,
    )
    earliest_period: str | None = None
    latest_period: str | None = None
    include_unresolved: bool = True
    include_contextual: bool = False
    create_research_plan: bool = False

    @classmethod
    def from_dict(cls, value: Any | None) -> "TraversalPolicy":
        raw = {} if value is None else _object(value, "traversal policy")
        direction = _enum(
            raw.get("direction", TraversalDirection.BIDIRECTIONAL.value),
            TraversalDirection,
            "traversal direction",
        )
        maximum_depth = raw.get("maximum_depth", 4)
        if not isinstance(maximum_depth, int) or isinstance(maximum_depth, bool):
            raise LineageError("maximum_depth must be an integer")
        if maximum_depth < 1 or maximum_depth > 20:
            raise LineageError("maximum_depth must be between 1 and 20")
        supplied_families = raw.get(
            "permitted_families",
            [
                TraversalRelationFamily.GENEALOGICAL.value,
                TraversalRelationFamily.ENGAGEMENT.value,
            ],
        )
        if not isinstance(supplied_families, list) or not supplied_families:
            raise LineageError("permitted_families must be a non-empty list")
        families = tuple(
            _enum(item, TraversalRelationFamily, "traversal relation family")
            for item in supplied_families
        )
        if len(families) != len(set(families)):
            raise LineageError("permitted_families must not contain duplicates")
        earliest = raw.get("earliest_period")
        latest = raw.get("latest_period")
        if earliest is not None:
            earliest = _enum(earliest, HistoricalPeriod, "earliest period")
        if latest is not None:
            latest = _enum(latest, HistoricalPeriod, "latest period")
        if earliest == HistoricalPeriod.UNRESOLVED.value or latest == HistoricalPeriod.UNRESOLVED.value:
            raise LineageError("UNRESOLVED cannot be used as a period bound")
        if earliest and latest and _PERIOD_ORDER[earliest] > _PERIOD_ORDER[latest]:
            raise LineageError("earliest_period must not follow latest_period")
        for name in ("include_unresolved", "include_contextual", "create_research_plan"):
            if name in raw and not isinstance(raw[name], bool):
                raise LineageError(f"{name} must be boolean")
        return cls(
            direction=direction,
            maximum_depth=maximum_depth,
            permitted_families=families,
            earliest_period=earliest,
            latest_period=latest,
            include_unresolved=raw.get("include_unresolved", True),
            include_contextual=raw.get("include_contextual", False),
            create_research_plan=raw.get("create_research_plan", False),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction,
            "maximum_depth": self.maximum_depth,
            "permitted_families": list(self.permitted_families),
            "earliest_period": self.earliest_period,
            "latest_period": self.latest_period,
            "include_unresolved": self.include_unresolved,
            "include_contextual": self.include_contextual,
            "create_research_plan": self.create_research_plan,
            "phase5_validation_required_for_new_edges": True,
        }

    def admits_period(self, period: str) -> bool:
        if not self.earliest_period and not self.latest_period:
            return True
        if period == HistoricalPeriod.UNRESOLVED.value:
            return False
        rank = _PERIOD_ORDER[period]
        if self.earliest_period and rank < _PERIOD_ORDER[self.earliest_period]:
            return False
        if self.latest_period and rank > _PERIOD_ORDER[self.latest_period]:
            return False
        return True


@dataclass(frozen=True)
class LineageStep:
    edge_id: str
    relation_type: str
    family: str
    treatment: str
    from_node_id: str
    to_node_id: str
    edge_orientation: str
    confidence: str
    claim_state: str
    scope: str
    evidence_roots: tuple[str, ...]
    upstream_uncertainty: tuple[Mapping[str, Any], ...]
    unresolved_alternatives: tuple[Mapping[str, Any], ...]
    mediation_channel: str | None
    intermediary_node_id: str | None
    discontinuity_preserved: bool

    @classmethod
    def from_edge(
        cls,
        edge: HistoricalRelationEdge,
        from_node_id: str,
        to_node_id: str,
        direction: str,
    ) -> "LineageStep":
        rule = RELATION_TRAVERSAL[edge.relation_type]
        raw = edge.to_dict()
        expected = (
            edge.source_node_id,
            edge.target_node_id,
        ) if direction == TraversalDirection.FORWARD.value else (
            edge.target_node_id,
            edge.source_node_id,
        )
        if (from_node_id, to_node_id) != expected:
            raise LineageError(f"edge {edge.edge_id} orientation is invalid for {direction}")
        return cls(
            edge_id=edge.edge_id,
            relation_type=edge.relation_type,
            family=rule.family,
            treatment=rule.treatment,
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            edge_orientation="WITH_EDGE" if direction == TraversalDirection.FORWARD.value else "AGAINST_EDGE",
            confidence=edge.confidence,
            claim_state=edge.claim_state,
            scope=str(raw["scope"]),
            evidence_roots=tuple(edge.evidence_roots),
            upstream_uncertainty=tuple(copy.deepcopy(raw.get("upstream_uncertainty", []))),
            unresolved_alternatives=tuple(copy.deepcopy(raw.get("unresolved_alternatives", []))),
            mediation_channel=raw.get("mediation_channel"),
            intermediary_node_id=raw.get("intermediary_node_id"),
            discontinuity_preserved=rule.discontinuity_required,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "relation_type": self.relation_type,
            "family": self.family,
            "treatment": self.treatment,
            "from_node_id": self.from_node_id,
            "to_node_id": self.to_node_id,
            "edge_orientation": self.edge_orientation,
            "confidence": self.confidence,
            "claim_state": self.claim_state,
            "scope": self.scope,
            "evidence_roots": list(self.evidence_roots),
            "upstream_uncertainty": copy.deepcopy(list(self.upstream_uncertainty)),
            "unresolved_alternatives": copy.deepcopy(list(self.unresolved_alternatives)),
            "mediation_channel": self.mediation_channel,
            "intermediary_node_id": self.intermediary_node_id,
            "discontinuity_preserved": self.discontinuity_preserved,
        }


@dataclass(frozen=True)
class LineagePath:
    path_id: str
    anchor_id: str
    direction: str
    node_ids: tuple[str, ...]
    steps: tuple[LineageStep, ...]
    branch_ids: tuple[str, ...]
    convergence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.node_ids) != len(self.steps) + 1:
            raise LineageError("lineage path node and edge sequence lengths do not agree")
        for index, step in enumerate(self.steps):
            if (step.from_node_id, step.to_node_id) != (
                self.node_ids[index], self.node_ids[index + 1]
            ):
                raise LineageError("lineage path step endpoints do not match node sequence")

    def to_dict(self) -> dict[str, Any]:
        return {
            "path_id": self.path_id,
            "anchor_id": self.anchor_id,
            "direction": self.direction,
            "node_ids": list(self.node_ids),
            "steps": [item.to_dict() for item in self.steps],
            "branch_ids": list(self.branch_ids),
            "convergence_ids": list(self.convergence_ids),
            "summary_confidence": None,
            "creates_historical_edge": False,
        }


@dataclass(frozen=True)
class LineageGap:
    gap_id: str
    kind: str
    node_id: str
    direction: str
    rationale: str
    evidence_state: str
    related_edge_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "gap_id": self.gap_id,
            "kind": self.kind,
            "node_id": self.node_id,
            "direction": self.direction,
            "rationale": self.rationale,
            "evidence_state": self.evidence_state,
            "related_edge_id": self.related_edge_id,
            "positive_disappearance_claim": self.kind in {
                GapKind.POSITIVE_DISAPPEARANCE.value,
                GapKind.DIMINISHED_TRANSMISSION.value,
            },
        }


@dataclass(frozen=True)
class UnresolvedLineageLink:
    link_id: str
    edge_id: str
    source_node_id: str
    target_node_id: str
    direction: str
    asserted_relation_type: str
    alternatives: tuple[Mapping[str, Any], ...]
    claim_state: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "link_id": self.link_id,
            "edge_id": self.edge_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "direction": self.direction,
            "asserted_relation_type": self.asserted_relation_type,
            "alternatives": copy.deepcopy(list(self.alternatives)),
            "claim_state": self.claim_state,
            "promoted_to_established": False,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class ContextualRelation:
    edge_id: str
    relation_type: str
    node_ids: tuple[str, str]
    family: str
    confidence: str
    shared_source_node_id: str | None
    evidence_roots: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "relation_type": self.relation_type,
            "node_ids": list(self.node_ids),
            "family": self.family,
            "confidence": self.confidence,
            "shared_source_node_id": self.shared_source_node_id,
            "evidence_roots": list(self.evidence_roots),
            "ancestry_claim": False,
        }


@dataclass(frozen=True)
class BranchRecord:
    branch_id: str
    node_id: str
    direction: str
    edge_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "node_id": self.node_id,
            "direction": self.direction,
            "edge_ids": list(self.edge_ids),
        }


@dataclass(frozen=True)
class ConvergenceRecord:
    convergence_id: str
    node_id: str
    incoming_edge_ids: tuple[str, ...]
    evidence_root_sets: tuple[tuple[str, ...], ...]
    independent_streams_established: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "convergence_id": self.convergence_id,
            "node_id": self.node_id,
            "incoming_edge_ids": list(self.incoming_edge_ids),
            "evidence_root_sets": [list(item) for item in self.evidence_root_sets],
            "independent_streams_established": self.independent_streams_established,
        }


@dataclass(frozen=True)
class ResearchPlanItem:
    item_id: str
    target_question: str
    originating_anchor_id: str
    direction: str
    motivating_gap_id: str | None
    motivating_link_id: str | None
    chronological_bounds: Mapping[str, Any]
    candidate_node_id: str | None
    evidence_needed: tuple[str, ...]
    discriminating_test: str
    current_evidence_state: str
    priority: str
    completion_state: str
    provenance: Mapping[str, Any]

    def __post_init__(self) -> None:
        _identifier(self.item_id, "research-plan item_id")
        _text(self.target_question, "research-plan target question")
        _enum(self.direction, TraversalDirection, "research-plan direction")
        _enum(self.priority, ResearchPriority, "research-plan priority")
        _enum(self.completion_state, ResearchCompletionState, "research-plan completion state")
        if not self.evidence_needed:
            raise LineageError("research-plan item requires evidence_needed")
        _text(self.discriminating_test, "research-plan discriminating test")
        ProvenanceRecord.from_dict(self.provenance)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "target_question": self.target_question,
            "originating_anchor_id": self.originating_anchor_id,
            "direction": self.direction,
            "motivating_gap_id": self.motivating_gap_id,
            "motivating_link_id": self.motivating_link_id,
            "chronological_bounds": copy.deepcopy(dict(self.chronological_bounds)),
            "candidate_node_id": self.candidate_node_id,
            "candidate_status": "RESEARCH_TARGET" if self.candidate_node_id else "ANONYMOUS_TARGET",
            "evidence_needed": list(self.evidence_needed),
            "discriminating_test": self.discriminating_test,
            "current_evidence_state": self.current_evidence_state,
            "priority": self.priority,
            "completion_state": self.completion_state,
            "established_graph_fact": False,
            "creates_historical_edge": False,
            "requires_phase5_validation": True,
            "provenance": copy.deepcopy(dict(self.provenance)),
        }


@dataclass(frozen=True)
class LineageTraversalResult:
    result_id: str
    graph_id: str
    graph_sha256: str
    anchor: LineageAnchor
    policy: TraversalPolicy
    paths: tuple[LineagePath, ...]
    branches: tuple[BranchRecord, ...]
    convergences: tuple[ConvergenceRecord, ...]
    gaps: tuple[LineageGap, ...]
    unresolved_links: tuple[UnresolvedLineageLink, ...]
    contextual_relations: tuple[ContextualRelation, ...]
    research_plan: tuple[ResearchPlanItem, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1",
            "result_id": self.result_id,
            "graph_id": self.graph_id,
            "graph_sha256": self.graph_sha256,
            "anchor": self.anchor.to_dict(),
            "policy": self.policy.to_dict(),
            "paths": [item.to_dict() for item in sorted(self.paths, key=lambda x: x.path_id)],
            "branches": [item.to_dict() for item in sorted(self.branches, key=lambda x: x.branch_id)],
            "convergences": [
                item.to_dict() for item in sorted(self.convergences, key=lambda x: x.convergence_id)
            ],
            "gaps": [item.to_dict() for item in sorted(self.gaps, key=lambda x: x.gap_id)],
            "unresolved_links": [
                item.to_dict() for item in sorted(self.unresolved_links, key=lambda x: x.link_id)
            ],
            "contextual_relations": [
                item.to_dict() for item in sorted(self.contextual_relations, key=lambda x: x.edge_id)
            ],
            "research_plan": [
                item.to_dict() for item in sorted(self.research_plan, key=lambda x: x.item_id)
            ],
            "historical_graph_mutated": False,
            "new_historical_edges": [],
        }

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())

    def sha256(self) -> str:
        return sha256_json(self.to_dict())


def _edge_sort_key(edge: HistoricalRelationEdge, graph: HistoricalRelationGraph, next_id: str) -> tuple[Any, ...]:
    raw = graph.node(next_id).to_dict()
    year = _node_year(raw)
    return (
        year if year is not None else 10**9,
        _PERIOD_ORDER[_node_period(raw)],
        edge.relation_type,
        edge.edge_id,
        next_id,
    )


class BidirectionalLineageEngine:
    """Relation-aware deterministic view over one immutable historical graph."""

    def __init__(self, graph: HistoricalRelationGraph):
        if not isinstance(graph, HistoricalRelationGraph):
            raise LineageError("lineage engine requires a validated HistoricalRelationGraph")
        self.graph = graph

    def _eligible_neighbors(
        self,
        node_id: str,
        direction: str,
        policy: TraversalPolicy,
    ) -> list[tuple[HistoricalRelationEdge, str]]:
        result: list[tuple[HistoricalRelationEdge, str]] = []
        for edge in self.graph.active_edges:
            rule = RELATION_TRAVERSAL[edge.relation_type]
            if not rule.lineage_by_default or rule.family not in policy.permitted_families:
                continue
            if direction == TraversalDirection.BACKWARD.value and edge.target_node_id == node_id:
                next_id = edge.source_node_id
            elif direction == TraversalDirection.FORWARD.value and edge.source_node_id == node_id:
                next_id = edge.target_node_id
            else:
                continue
            if not policy.admits_period(_node_period(self.graph.node(next_id).to_dict())):
                continue
            result.append((edge, next_id))
        return sorted(result, key=lambda item: _edge_sort_key(item[0], self.graph, item[1]))

    def _all_directional_neighbors(
        self, node_id: str, direction: str, policy: TraversalPolicy
    ) -> list[tuple[HistoricalRelationEdge, str]]:
        result: list[tuple[HistoricalRelationEdge, str]] = []
        for edge in self.graph.active_edges:
            rule = RELATION_TRAVERSAL[edge.relation_type]
            if not rule.lineage_by_default or rule.family not in policy.permitted_families:
                continue
            if direction == TraversalDirection.BACKWARD.value and edge.target_node_id == node_id:
                result.append((edge, edge.source_node_id))
            elif direction == TraversalDirection.FORWARD.value and edge.source_node_id == node_id:
                result.append((edge, edge.target_node_id))
        return sorted(result, key=lambda item: _edge_sort_key(item[0], self.graph, item[1]))

    def _context(self, reachable: set[str], policy: TraversalPolicy) -> tuple[ContextualRelation, ...]:
        if not policy.include_contextual:
            return ()
        result: list[ContextualRelation] = []
        for edge in self.graph.active_edges:
            rule = RELATION_TRAVERSAL[edge.relation_type]
            if rule.lineage_by_default:
                continue
            if not ({edge.source_node_id, edge.target_node_id} & reachable):
                continue
            raw = edge.to_dict()
            result.append(
                ContextualRelation(
                    edge_id=edge.edge_id,
                    relation_type=edge.relation_type,
                    node_ids=(edge.source_node_id, edge.target_node_id),
                    family=rule.family,
                    confidence=edge.confidence,
                    shared_source_node_id=raw.get("shared_source_node_id"),
                    evidence_roots=tuple(edge.evidence_roots),
                )
            )
        return tuple(sorted(result, key=lambda item: item.edge_id))

    def _unresolved(
        self, reachable: set[str], directions: Iterable[str], policy: TraversalPolicy
    ) -> tuple[UnresolvedLineageLink, ...]:
        if not policy.include_unresolved:
            return ()
        result: list[UnresolvedLineageLink] = []
        for direction in directions:
            for edge in self.graph.edges:
                raw = edge.to_dict()
                alternatives = tuple(copy.deepcopy(raw.get("unresolved_alternatives", [])))
                touches = {edge.source_node_id, edge.target_node_id} & reachable
                if not touches or (edge.active and not alternatives):
                    continue
                if direction == TraversalDirection.BACKWARD.value and edge.target_node_id not in reachable:
                    continue
                if direction == TraversalDirection.FORWARD.value and edge.source_node_id not in reachable:
                    continue
                result.append(
                    UnresolvedLineageLink(
                        link_id=f"UNRESOLVED-{direction}-{edge.edge_id}",
                        edge_id=edge.edge_id,
                        source_node_id=edge.source_node_id,
                        target_node_id=edge.target_node_id,
                        direction=direction,
                        asserted_relation_type=edge.relation_type,
                        alternatives=alternatives,
                        claim_state=edge.claim_state,
                        rationale=(
                            "Alternative relation types remain unresolved."
                            if alternatives else "The historical relation claim is not active."
                        ),
                    )
                )
        unique = {item.link_id: item for item in result}
        return tuple(unique[key] for key in sorted(unique))

    def _traverse_direction(
        self,
        anchor: LineageAnchor,
        direction: str,
        policy: TraversalPolicy,
    ) -> tuple[list[LineagePath], list[BranchRecord], list[LineageGap], set[str]]:
        paths: list[LineagePath] = []
        branches: dict[str, BranchRecord] = {}
        gaps: dict[str, LineageGap] = {}
        reachable: set[str] = {anchor.graph_node_id}
        counter = 0

        def add_path(node_ids: tuple[str, ...], steps: tuple[LineageStep, ...], branch_ids: tuple[str, ...]) -> None:
            nonlocal counter
            if not steps:
                return
            counter += 1
            paths.append(
                LineagePath(
                    path_id=f"PATH-{direction}-{counter:04d}",
                    anchor_id=anchor.anchor_id,
                    direction=direction,
                    node_ids=node_ids,
                    steps=steps,
                    branch_ids=tuple(sorted(set(branch_ids))),
                    convergence_ids=(),
                )
            )

        def walk(
            current: str,
            node_ids: tuple[str, ...],
            steps: tuple[LineageStep, ...],
            branch_ids: tuple[str, ...],
        ) -> None:
            depth = len(steps)
            if depth >= policy.maximum_depth:
                add_path(node_ids, steps, branch_ids)
                gap_id = f"GAP-{direction}-DEPTH-{current}"
                gaps[gap_id] = LineageGap(
                    gap_id, GapKind.DEPTH_BOUNDARY.value, current, direction,
                    "Traversal stopped at the configured maximum depth.", "ESTABLISHED",
                )
                return
            all_neighbors = self._all_directional_neighbors(current, direction, policy)
            neighbors = self._eligible_neighbors(current, direction, policy)
            if all_neighbors and not neighbors:
                add_path(node_ids, steps, branch_ids)
                gap_id = f"GAP-{direction}-PERIOD-{current}"
                gaps[gap_id] = LineageGap(
                    gap_id, GapKind.PERIOD_BOUNDARY.value, current, direction,
                    "A graph relation lies outside the requested period bounds or has unresolved period metadata.",
                    "UNRESOLVED",
                )
                return
            if not neighbors:
                add_path(node_ids, steps, branch_ids)
                gap_id = f"GAP-{direction}-NONE-{current}"
                gaps[gap_id] = LineageGap(
                    gap_id, GapKind.NO_ESTABLISHED_RELATION.value, current, direction,
                    "No traversal-eligible established relation is currently present; this is not proof of disappearance.",
                    "UNRESOLVED",
                )
                return
            local_branch_ids = branch_ids
            if len(neighbors) > 1:
                branch_id = f"BRANCH-{direction}-{current}"
                branches[branch_id] = BranchRecord(
                    branch_id, current, direction,
                    tuple(edge.edge_id for edge, _ in neighbors),
                )
                local_branch_ids = (*branch_ids, branch_id)
            advanced = False
            for edge, next_id in neighbors:
                if next_id in node_ids:
                    gap_id = f"GAP-{direction}-CYCLE-{edge.edge_id}"
                    gaps[gap_id] = LineageGap(
                        gap_id, GapKind.CYCLE_BOUNDARY.value, current, direction,
                        "Traversal stopped before revisiting a node already present on this path.",
                        "ESTABLISHED", edge.edge_id,
                    )
                    continue
                advanced = True
                step = LineageStep.from_edge(edge, current, next_id, direction)
                reachable.add(next_id)
                if step.discontinuity_preserved:
                    gap_id = f"GAP-{direction}-REVIVAL-{edge.edge_id}"
                    gaps[gap_id] = LineageGap(
                        gap_id, GapKind.REVIVAL_DISCONTINUITY.value, next_id, direction,
                        "The validated revival relation includes a discontinuity; no continuous intermediate chain is inferred.",
                        "ESTABLISHED", edge.edge_id,
                    )
                walk(next_id, (*node_ids, next_id), (*steps, step), local_branch_ids)
            if not advanced:
                add_path(node_ids, steps, local_branch_ids)

        walk(anchor.graph_node_id, (anchor.graph_node_id,), (), ())
        return paths, list(branches.values()), list(gaps.values()), reachable

    def _convergences(self, reachable: set[str], policy: TraversalPolicy) -> tuple[ConvergenceRecord, ...]:
        incoming: dict[str, list[HistoricalRelationEdge]] = {}
        for edge in self.graph.active_edges:
            rule = RELATION_TRAVERSAL[edge.relation_type]
            if not rule.lineage_by_default or rule.family not in policy.permitted_families:
                continue
            if edge.source_node_id in reachable and edge.target_node_id in reachable:
                incoming.setdefault(edge.target_node_id, []).append(edge)
        result: list[ConvergenceRecord] = []
        for node_id, edges in incoming.items():
            if len(edges) < 2:
                continue
            edges = sorted(edges, key=lambda item: item.edge_id)
            root_sets = tuple(tuple(sorted(set(edge.evidence_roots))) for edge in edges)
            genuinely_disjoint = all(
                not (set(root_sets[left]) & set(root_sets[right]))
                for left in range(len(root_sets))
                for right in range(left + 1, len(root_sets))
            )
            result.append(
                ConvergenceRecord(
                    convergence_id=f"CONVERGENCE-{node_id}",
                    node_id=node_id,
                    incoming_edge_ids=tuple(edge.edge_id for edge in edges),
                    evidence_root_sets=root_sets,
                    independent_streams_established=genuinely_disjoint,
                )
            )
        return tuple(sorted(result, key=lambda item: item.convergence_id))

    def _attach_convergences(
        self, paths: Iterable[LineagePath], convergences: tuple[ConvergenceRecord, ...]
    ) -> tuple[LineagePath, ...]:
        by_node = {item.node_id: item.convergence_id for item in convergences}
        result = []
        for path in paths:
            ids = tuple(sorted({by_node[node] for node in path.node_ids if node in by_node}))
            result.append(
                LineagePath(
                    path.path_id, path.anchor_id, path.direction, path.node_ids,
                    path.steps, path.branch_ids, ids,
                )
            )
        return tuple(sorted(result, key=lambda item: item.path_id))

    def _research_plan(
        self,
        anchor: LineageAnchor,
        gaps: tuple[LineageGap, ...],
        links: tuple[UnresolvedLineageLink, ...],
        policy: TraversalPolicy,
    ) -> tuple[ResearchPlanItem, ...]:
        if not policy.create_research_plan:
            return ()
        items: list[ResearchPlanItem] = []
        for gap in gaps:
            if gap.kind in {GapKind.CYCLE_BOUNDARY.value, GapKind.DEPTH_BOUNDARY.value}:
                continue
            bounds = {
                "earliest_period": policy.earliest_period,
                "latest_period": policy.latest_period,
            }
            if gap.kind == GapKind.REVIVAL_DISCONTINUITY.value:
                question = "What evidence delimits the discontinuity before the validated revival?"
                needed = (
                    "period-bounded primary or reliable secondary evidence",
                    "evidence for continuity, diminished transmission, or recovery",
                )
                test = "Distinguish continuous transmission from a documented discontinuity and later recovery."
            else:
                side = "earlier antecedent" if gap.direction == TraversalDirection.BACKWARD.value else "later reception"
                question = f"What evidence, if any, establishes a {side} beyond this graph gap?"
                needed = (
                    "passage-level historical evidence",
                    "chronology and accessibility evidence",
                    "discriminating evidence required by the proposed Phase 5 relation type",
                )
                test = "Test candidates against Phase 5 chronology, access, discrimination, and alternative-relation rules."
            items.append(
                ResearchPlanItem(
                    item_id=f"PLAN-GAP-{gap.gap_id}",
                    target_question=question,
                    originating_anchor_id=anchor.anchor_id,
                    direction=gap.direction,
                    motivating_gap_id=gap.gap_id,
                    motivating_link_id=None,
                    chronological_bounds=bounds,
                    candidate_node_id=None,
                    evidence_needed=needed,
                    discriminating_test=test,
                    current_evidence_state="UNRESOLVED",
                    priority=ResearchPriority.NORMAL.value,
                    completion_state=ResearchCompletionState.OPEN.value,
                    provenance={"origin": "Phase 6 structured lineage gap"},
                )
            )
        for link in links:
            alternative_types = sorted(
                {item.get("relation_type", "UNRESOLVED") for item in link.alternatives}
            )
            wording = ", ".join(alternative_types) if alternative_types else "active and inactive relation states"
            items.append(
                ResearchPlanItem(
                    item_id=f"PLAN-LINK-{link.link_id}",
                    target_question=f"What evidence discriminates the asserted relation from {wording}?",
                    originating_anchor_id=anchor.anchor_id,
                    direction=link.direction,
                    motivating_gap_id=None,
                    motivating_link_id=link.link_id,
                    chronological_bounds={
                        "earliest_period": policy.earliest_period,
                        "latest_period": policy.latest_period,
                    },
                    candidate_node_id=None,
                    evidence_needed=(
                        "relation-specific positive evidence",
                        "counterevidence and evidence ancestry",
                        "evidence discriminating the unresolved alternatives",
                    ),
                    discriminating_test="Apply the accepted Phase 5 minimum evidence semantics to every alternative.",
                    current_evidence_state="UNRESOLVED",
                    priority=ResearchPriority.HIGH.value,
                    completion_state=ResearchCompletionState.OPEN.value,
                    provenance={"origin": "Phase 6 unresolved historical link"},
                )
            )
        unique = {item.item_id: item for item in items}
        return tuple(unique[key] for key in sorted(unique))

    def trace(self, anchor_value: Any, policy_value: Any | None = None) -> LineageTraversalResult:
        before = self.graph.sha256()
        anchor = LineageAnchor.from_dict(anchor_value, self.graph)
        policy = TraversalPolicy.from_dict(policy_value)
        directions = (
            (TraversalDirection.BACKWARD.value, TraversalDirection.FORWARD.value)
            if policy.direction == TraversalDirection.BIDIRECTIONAL.value
            else (policy.direction,)
        )
        all_paths: list[LineagePath] = []
        all_branches: list[BranchRecord] = []
        all_gaps: list[LineageGap] = []
        reachable: set[str] = {anchor.graph_node_id}
        for direction in directions:
            paths, branches, gaps, direction_reachable = self._traverse_direction(
                anchor, direction, policy
            )
            all_paths.extend(paths)
            all_branches.extend(branches)
            all_gaps.extend(gaps)
            reachable.update(direction_reachable)
        convergences = self._convergences(reachable, policy)
        paths = self._attach_convergences(all_paths, convergences)
        gaps_by_id = {item.gap_id: item for item in all_gaps}
        branches_by_id = {item.branch_id: item for item in all_branches}
        unresolved = self._unresolved(reachable, directions, policy)
        context = self._context(reachable, policy)
        gaps = tuple(gaps_by_id[key] for key in sorted(gaps_by_id))
        research = self._research_plan(anchor, gaps, unresolved, policy)
        result = LineageTraversalResult(
            result_id=f"LINEAGE-{self.graph.graph_id}-{anchor.anchor_id}",
            graph_id=self.graph.graph_id,
            graph_sha256=before,
            anchor=anchor,
            policy=policy,
            paths=paths,
            branches=tuple(branches_by_id[key] for key in sorted(branches_by_id)),
            convergences=convergences,
            gaps=gaps,
            unresolved_links=unresolved,
            contextual_relations=context,
            research_plan=research,
        )
        if self.graph.sha256() != before:
            raise LineageError("lineage traversal must not mutate the Historical Relation Graph")
        validate_lineage_result(result, self.graph)
        return result


def validate_lineage_result(
    result: LineageTraversalResult,
    graph: HistoricalRelationGraph,
) -> None:
    if result.graph_id != graph.graph_id or result.graph_sha256 != graph.sha256():
        raise LineageError("lineage result does not match its Historical Relation Graph")
    node_ids = {item.node_id for item in graph.nodes}
    edge_ids = {item.edge_id for item in graph.edges}
    for path in result.paths:
        if path.anchor_id != result.anchor.anchor_id:
            raise LineageError("lineage path anchor mismatch")
        if any(node_id not in node_ids for node_id in path.node_ids):
            raise LineageError("lineage path references an unknown historical node")
        for step in path.steps:
            if step.edge_id not in edge_ids:
                raise LineageError("lineage path references an unknown historical edge")
            edge = graph.edge(step.edge_id)
            if step.relation_type != edge.relation_type:
                raise LineageError("lineage path relation type differs from Phase 5 edge")
            if not RELATION_TRAVERSAL[step.relation_type].lineage_by_default:
                raise LineageError("contextual relation cannot appear as a lineage path step")
            expected = (
                edge.source_node_id,
                edge.target_node_id,
            ) if path.direction == TraversalDirection.FORWARD.value else (
                edge.target_node_id,
                edge.source_node_id,
            )
            if (step.from_node_id, step.to_node_id) != expected:
                raise LineageError("lineage path silently reverses a historical relation")
            if step.confidence != edge.confidence:
                raise LineageError("lineage traversal cannot change edge confidence")
            if step.evidence_roots != edge.evidence_roots:
                raise LineageError("lineage traversal cannot change evidence ancestry")
    if result.to_dict()["new_historical_edges"]:
        raise LineageError("lineage result cannot create historical edges")


@dataclass(frozen=True)
class LineageConstructionResult:
    lineage: LineageTraversalResult
    audit: AuditResult

    def __post_init__(self) -> None:
        if not self.audit.passed:
            raise LineageError("failed audit cannot produce a lineage result")

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "validated",
            "lineage": self.lineage.to_dict(),
            "lineage_sha256": self.lineage.sha256(),
            "audit": {
                "status": self.audit.status,
                "findings": self.audit.to_v01_strings(),
            },
        }


def audit_lineage_traversal(
    graph: HistoricalRelationGraph,
    anchor_value: Any,
    policy_value: Any | None = None,
) -> AuditResult:
    try:
        BidirectionalLineageEngine(graph).trace(anchor_value, policy_value)
    except ValidationError as exc:
        return AuditResult((AuditFinding("LINEAGE_TRAVERSAL_INVALID", str(exc)),))
    return AuditResult()


def construct_lineage_traversal(
    graph: HistoricalRelationGraph,
    anchor_value: Any,
    policy_value: Any | None = None,
) -> LineageConstructionResult:
    audit = audit_lineage_traversal(graph, anchor_value, policy_value)
    if not audit.passed:
        raise LineageError(audit.findings[0].to_v01_string())
    lineage = BidirectionalLineageEngine(graph).trace(anchor_value, policy_value)
    return LineageConstructionResult(lineage, audit)
