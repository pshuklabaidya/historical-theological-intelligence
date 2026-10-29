"""Dependency-sensitive qualitative uncertainty over Phase 3 argument graphs.

The module derives consequences without changing proposition content, source
permissions, representation ancestry, or graph ownership. It implements no
historical relations and assigns no numerical confidence.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

from .argument_architecture import (
    HISTORICAL_RELATION_TYPES,
    ArgumentDossier,
    CompetingInterpretation,
    LogicalRelationType,
    Proposition,
    PropositionRelation,
)
from .audit import AuditFinding, AuditResult
from .hashing import canonical_json, sha256_json
from .model import EVIDENCE_STATES, ValidationError
from .provenance import ProvenanceRecord
from .uncertainty import UncertaintyAssessment


class DependencyUncertaintyError(ValidationError):
    """Raised when an uncertainty request fails closed."""


class UncertaintyOriginType(str, Enum):
    PAGE_READING = "PAGE_READING"
    OBSCURED_TEXT = "OBSCURED_TEXT"
    RECONSTRUCTED_TEXT = "RECONSTRUCTED_TEXT"
    TRANSLATION = "TRANSLATION"
    LEXICAL = "LEXICAL"
    GRAMMATICAL = "GRAMMATICAL"
    REPRESENTATION_LIMITATION = "REPRESENTATION_LIMITATION"
    OCR = "OCR"
    TRANSCRIPTION = "TRANSCRIPTION"
    BIBLIOGRAPHIC_IDENTITY = "BIBLIOGRAPHIC_IDENTITY"
    SOURCE_ATTRIBUTION = "SOURCE_ATTRIBUTION"
    PROPOSITION_RECONSTRUCTION = "PROPOSITION_RECONSTRUCTION"
    PROPOSITION_CLASSIFICATION = "PROPOSITION_CLASSIFICATION"
    RELATION_DIRECTION = "RELATION_DIRECTION"
    COMPETING_INTERPRETATION = "COMPETING_INTERPRETATION"
    OTHER = "OTHER"


class UncertaintySubjectKind(str, Enum):
    PROPOSITION = "PROPOSITION"
    RELATION = "RELATION"
    REPRESENTATION = "REPRESENTATION"
    INTERPRETATION = "INTERPRETATION"


class DependencyEffect(str, Enum):
    CRITICAL = "CRITICAL"
    CONTRIBUTORY = "CONTRIBUTORY"
    SCOPE_MODIFYING = "SCOPE_MODIFYING"
    NON_PROPAGATING = "NON_PROPAGATING"
    UNRESOLVED = "UNRESOLVED"


class PropagationDirection(str, Enum):
    SOURCE_TO_TARGET = "SOURCE_TO_TARGET"
    TARGET_TO_SOURCE = "TARGET_TO_SOURCE"
    NONE = "NONE"


class RootEffect(str, Enum):
    CRITICAL = "CRITICAL"
    WEAKENING = "WEAKENING"
    SCOPE_MODIFYING = "SCOPE_MODIFYING"
    LOCAL = "LOCAL"
    IRRELEVANT = "IRRELEVANT"
    UNRESOLVED = "UNRESOLVED"


class TargetUncertaintyState(str, Enum):
    UNAFFECTED = "UNAFFECTED"
    LOCAL_UNCERTAINTY = "LOCAL_UNCERTAINTY"
    QUALIFIED = "QUALIFIED"
    WEAKENED = "WEAKENED"
    MATERIALLY_UNCERTAIN = "MATERIALLY_UNCERTAIN"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class RelationPropagationSemantics:
    relation_type: str
    direction: str
    effect: str
    rationale: str

    def to_dict(self) -> dict[str, str]:
        return {
            "relation_type": self.relation_type,
            "direction": self.direction,
            "effect": self.effect,
            "rationale": self.rationale,
        }


RELATION_PROPAGATION: Mapping[str, RelationPropagationSemantics] = {
    LogicalRelationType.SUPPORTS.value: RelationPropagationSemantics(
        "SUPPORTS", "SOURCE_TO_TARGET", "CONTRIBUTORY",
        "Support contributes to the target without asserting strict necessity.",
    ),
    LogicalRelationType.DEPENDS_ON.value: RelationPropagationSemantics(
        "DEPENDS_ON", "TARGET_TO_SOURCE", "CRITICAL",
        "The source proposition explicitly depends on the target proposition.",
    ),
    LogicalRelationType.QUALIFIES.value: RelationPropagationSemantics(
        "QUALIFIES", "SOURCE_TO_TARGET", "SCOPE_MODIFYING",
        "A qualification can alter the scope of the target without independently establishing it.",
    ),
    LogicalRelationType.DISTINGUISHES.value: RelationPropagationSemantics(
        "DISTINGUISHES", "SOURCE_TO_TARGET", "SCOPE_MODIFYING",
        "A distinction constrains the target's interpretation or scope.",
    ),
    LogicalRelationType.CONTRADICTS.value: RelationPropagationSemantics(
        "CONTRADICTS", "NONE", "NON_PROPAGATING",
        "Contradiction is opposition, not an evidentiary dependency.",
    ),
    LogicalRelationType.INTERPRETS.value: RelationPropagationSemantics(
        "INTERPRETS", "SOURCE_TO_TARGET", "SCOPE_MODIFYING",
        "An interpretive proposition can qualify how the target is understood.",
    ),
    LogicalRelationType.PRESUPPOSES.value: RelationPropagationSemantics(
        "PRESUPPOSES", "TARGET_TO_SOURCE", "CRITICAL",
        "The source proposition structurally presupposes the target proposition.",
    ),
    LogicalRelationType.CONCLUDES_FROM.value: RelationPropagationSemantics(
        "CONCLUDES_FROM", "TARGET_TO_SOURCE", "CRITICAL",
        "The source conclusion is inferentially derived from the target premise.",
    ),
    LogicalRelationType.REQUIRES.value: RelationPropagationSemantics(
        "REQUIRES", "TARGET_TO_SOURCE", "CRITICAL",
        "The source proposition cannot retain its support without the target proposition.",
    ),
    LogicalRelationType.DOES_NOT_SUPPORT.value: RelationPropagationSemantics(
        "DOES_NOT_SUPPORT", "NONE", "NON_PROPAGATING",
        "An explicit absence of support creates no positive dependency path.",
    ),
    LogicalRelationType.UNCLASSIFIED.value: RelationPropagationSemantics(
        "UNCLASSIFIED", "SOURCE_TO_TARGET", "UNRESOLVED",
        "Unclassified relation semantics cannot justify a determinate propagation effect.",
    ),
}


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_CONTENT_ORIGINS = frozenset(
    {
        UncertaintyOriginType.PAGE_READING.value,
        UncertaintyOriginType.OBSCURED_TEXT.value,
        UncertaintyOriginType.RECONSTRUCTED_TEXT.value,
        UncertaintyOriginType.TRANSLATION.value,
        UncertaintyOriginType.LEXICAL.value,
        UncertaintyOriginType.GRAMMATICAL.value,
        UncertaintyOriginType.REPRESENTATION_LIMITATION.value,
        UncertaintyOriginType.OCR.value,
        UncertaintyOriginType.TRANSCRIPTION.value,
        UncertaintyOriginType.PROPOSITION_RECONSTRUCTION.value,
        UncertaintyOriginType.RELATION_DIRECTION.value,
        UncertaintyOriginType.COMPETING_INTERPRETATION.value,
        UncertaintyOriginType.OTHER.value,
    }
)


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise DependencyUncertaintyError(f"{label} must be a stable identifier")
    return value


def _enum(value: Any, kind: type[Enum], label: str) -> str:
    if not isinstance(value, str):
        raise DependencyUncertaintyError(f"{label} must be a declared string value")
    try:
        kind(value)
    except ValueError as exc:
        raise DependencyUncertaintyError(f"invalid {label} {value!r}") from exc
    return value


def _reject_probabilities(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).lower()
            if normalized in {
                "probability", "confidence_probability", "confidence_score",
                "numeric_confidence", "propagated_confidence", "percentage",
            }:
                raise DependencyUncertaintyError(
                    "numerical probability or confidence is outside Phase 4"
                )
            _reject_probabilities(item)
    elif isinstance(value, list):
        for item in value:
            _reject_probabilities(item)


def _ordered_ids(value: Any, label: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise DependencyUncertaintyError(f"{label} must be an ordered list")
    result = tuple(_identifier(item, f"{label} item") for item in value)
    if len(result) != len(set(result)):
        raise DependencyUncertaintyError(f"{label} must not contain duplicates")
    return result


@dataclass(frozen=True)
class UncertaintyRoot:
    """One auditable qualitative uncertainty origin."""

    _raw: Mapping[str, Any] = field(repr=False)
    evidence_roots: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: Any, dossier: ArgumentDossier) -> "UncertaintyRoot":
        if not isinstance(value, dict):
            raise DependencyUncertaintyError("uncertainty root must be an object")
        _reject_probabilities(value)
        root_id = _identifier(value.get("root_id"), "root_id")
        if value.get("dossier_id") != dossier.dossier_id:
            raise DependencyUncertaintyError(
                f"uncertainty root {root_id} has invalid dossier ownership"
            )
        subject_kind = _enum(
            value.get("subject_kind"), UncertaintySubjectKind, "uncertainty subject kind"
        )
        subject_id = _identifier(value.get("subject_id"), "uncertainty subject_id")
        _enum(value.get("origin_type"), UncertaintyOriginType, "uncertainty origin type")
        rationale = value.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            raise DependencyUncertaintyError(f"uncertainty root {root_id} requires rationale")
        provenance = value.get("provenance")
        if provenance is None:
            raise DependencyUncertaintyError(f"uncertainty root {root_id} requires provenance")
        ProvenanceRecord.from_dict(provenance)
        evidence_state = value.get("evidence_state")
        if evidence_state is not None and evidence_state not in EVIDENCE_STATES:
            raise DependencyUncertaintyError(
                f"uncertainty root {root_id} has invalid evidence_state {evidence_state!r}"
            )
        assessment = value.get("uncertainty")
        if assessment is not None:
            UncertaintyAssessment.from_dict(assessment)

        proposition_by_id = {item.proposition_id: item for item in dossier.propositions}
        relation_by_id = {item.relation_id: item for item in dossier.relations}
        interpretation_by_id = {
            item.interpretation_id: item for item in dossier.interpretations
        }
        scope = set(dossier.to_dict().get("representation_scope", []))
        if subject_kind == UncertaintySubjectKind.PROPOSITION.value:
            if subject_id not in proposition_by_id:
                raise DependencyUncertaintyError(f"unknown uncertainty proposition {subject_id!r}")
            roots = _proposition_evidence_roots(proposition_by_id[subject_id])
        elif subject_kind == UncertaintySubjectKind.RELATION.value:
            if subject_id not in relation_by_id:
                raise DependencyUncertaintyError(f"unknown uncertainty relation {subject_id!r}")
            relation = relation_by_id[subject_id]
            roots = tuple(sorted(set(
                _proposition_evidence_roots(proposition_by_id[relation.source_proposition_id])
            ) | set(
                _proposition_evidence_roots(proposition_by_id[relation.target_proposition_id])
            )))
        elif subject_kind == UncertaintySubjectKind.REPRESENTATION.value:
            if subject_id not in scope:
                raise DependencyUncertaintyError(
                    f"uncertainty representation {subject_id!r} is outside dossier scope"
                )
            roots = tuple(sorted({
                evidence_root
                for proposition in dossier.propositions
                for link in proposition.source_links
                if subject_id == link.representation_id or subject_id in link.ancestry
                for evidence_root in link.evidence_roots
            }))
        else:
            if subject_id not in interpretation_by_id:
                raise DependencyUncertaintyError(
                    f"unknown uncertainty interpretation {subject_id!r}"
                )
            roots = tuple(sorted({
                evidence_root
                for proposition_id in interpretation_by_id[subject_id].ids("proposition_ids")
                for evidence_root in _proposition_evidence_roots(proposition_by_id[proposition_id])
            }))

        interpretation_ids = _ordered_ids(
            value.get("interpretation_ids", []), "uncertainty interpretation_ids"
        )
        for interpretation_id in interpretation_ids:
            if interpretation_id not in interpretation_by_id:
                raise DependencyUncertaintyError(
                    f"uncertainty root {root_id} names unknown interpretation {interpretation_id}"
                )
        normalized = copy.deepcopy(value)
        if subject_kind == UncertaintySubjectKind.INTERPRETATION.value:
            if interpretation_ids and subject_id not in interpretation_ids:
                raise DependencyUncertaintyError(
                    "interpretation uncertainty must include its subject interpretation"
                )
            if not interpretation_ids:
                normalized["interpretation_ids"] = [subject_id]
        return cls(normalized, roots)

    @property
    def root_id(self) -> str:
        return str(self._raw["root_id"])

    @property
    def dossier_id(self) -> str:
        return str(self._raw["dossier_id"])

    @property
    def subject_kind(self) -> str:
        return str(self._raw["subject_kind"])

    @property
    def subject_id(self) -> str:
        return str(self._raw["subject_id"])

    @property
    def origin_type(self) -> str:
        return str(self._raw["origin_type"])

    @property
    def interpretation_ids(self) -> tuple[str, ...]:
        return tuple(self._raw.get("interpretation_ids", []))

    @property
    def content_relevant(self) -> bool:
        return self.origin_type in _CONTENT_ORIGINS

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


def _proposition_evidence_roots(proposition: Proposition) -> tuple[str, ...]:
    return tuple(sorted({root for link in proposition.source_links for root in link.evidence_roots}))


@dataclass(frozen=True)
class DependencyArc:
    relation_id: str
    upstream_proposition_id: str
    downstream_proposition_id: str
    relation_type: str
    effect: str
    interpretation_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation_id": self.relation_id,
            "upstream_proposition_id": self.upstream_proposition_id,
            "downstream_proposition_id": self.downstream_proposition_id,
            "relation_type": self.relation_type,
            "effect": self.effect,
            "interpretation_ids": list(self.interpretation_ids),
        }


@dataclass(frozen=True)
class DependencyPath:
    proposition_ids: tuple[str, ...]
    relation_ids: tuple[str, ...]
    effects: tuple[str, ...]

    @property
    def aggregate_effect(self) -> str:
        if not self.effects:
            return DependencyEffect.CRITICAL.value
        if DependencyEffect.UNRESOLVED.value in self.effects:
            return DependencyEffect.UNRESOLVED.value
        if DependencyEffect.CONTRIBUTORY.value in self.effects:
            return DependencyEffect.CONTRIBUTORY.value
        if DependencyEffect.SCOPE_MODIFYING.value in self.effects:
            return DependencyEffect.SCOPE_MODIFYING.value
        return DependencyEffect.CRITICAL.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposition_ids": list(self.proposition_ids),
            "relation_ids": list(self.relation_ids),
            "effects": list(self.effects),
            "aggregate_effect": self.aggregate_effect,
        }


@dataclass(frozen=True)
class RootImpact:
    root_id: str
    originating_subject_kind: str
    originating_subject_id: str
    origin_type: str
    effect: str
    paths: tuple[DependencyPath, ...]
    evidence_roots: tuple[str, ...]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_id": self.root_id,
            "originating_subject_kind": self.originating_subject_kind,
            "originating_subject_id": self.originating_subject_id,
            "origin_type": self.origin_type,
            "effect": self.effect,
            "paths": [item.to_dict() for item in self.paths],
            "evidence_roots": list(self.evidence_roots),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class SupportBranch:
    proposition_id: str
    relation_id: str
    relation_type: str
    effect: str
    evidence_roots: tuple[str, ...]
    dependency_ancestry: tuple[str, ...]
    affected_root_ids: tuple[str, ...]
    secure: bool
    genuinely_independent: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposition_id": self.proposition_id,
            "relation_id": self.relation_id,
            "relation_type": self.relation_type,
            "effect": self.effect,
            "evidence_roots": list(self.evidence_roots),
            "dependency_ancestry": list(self.dependency_ancestry),
            "affected_root_ids": list(self.affected_root_ids),
            "secure": self.secure,
            "genuinely_independent": self.genuinely_independent,
        }


@dataclass(frozen=True)
class UncertaintyAuditRecord:
    root_id: str
    target_proposition_id: str
    effect: str
    dependency_paths: tuple[DependencyPath, ...]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_id": self.root_id,
            "target_proposition_id": self.target_proposition_id,
            "effect": self.effect,
            "dependency_paths": [item.to_dict() for item in self.dependency_paths],
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class PropositionUncertaintyResult:
    dossier_id: str
    target_proposition_id: str
    interpretation_id: str | None
    state: str
    root_impacts: tuple[RootImpact, ...]
    support_branches: tuple[SupportBranch, ...]
    active_root_ids: tuple[str, ...]
    surviving_independent_support: bool
    audit_trail: tuple[UncertaintyAuditRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dossier_id": self.dossier_id,
            "target_proposition_id": self.target_proposition_id,
            "interpretation_id": self.interpretation_id,
            "state": self.state,
            "active_root_ids": list(self.active_root_ids),
            "root_impacts": [item.to_dict() for item in self.root_impacts],
            "support_branches": [item.to_dict() for item in self.support_branches],
            "surviving_independent_support": self.surviving_independent_support,
            "audit_trail": [item.to_dict() for item in self.audit_trail],
        }

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())


@dataclass(frozen=True)
class InterpretationUncertaintySummary:
    target_proposition_id: str
    results: tuple[PropositionUncertaintyResult, ...]
    survives_all_viable_interpretations: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_proposition_id": self.target_proposition_id,
            "results": [item.to_dict() for item in self.results],
            "survives_all_viable_interpretations": self.survives_all_viable_interpretations,
        }


class DependencyUncertaintyAnalysis:
    """Cycle-safe relation-aware analysis for one isolated dossier."""

    def __init__(self, dossier: ArgumentDossier, roots: Iterable[UncertaintyRoot]):
        self.dossier = dossier
        self.roots = tuple(roots)
        by_id = {item.root_id: item for item in self.roots}
        if len(by_id) != len(self.roots):
            raise DependencyUncertaintyError("uncertainty root ids must be unique")
        if any(item.dossier_id != dossier.dossier_id for item in self.roots):
            raise DependencyUncertaintyError("cross-dossier uncertainty root")
        self._root_by_id = by_id
        self._proposition_by_id = {
            item.proposition_id: item for item in dossier.propositions
        }
        self._relation_by_id = {item.relation_id: item for item in dossier.relations}
        self._interpretation_by_id = {
            item.interpretation_id: item for item in dossier.interpretations
        }
        relation_owners: dict[str, list[str]] = {}
        proposition_owners: dict[str, list[str]] = {}
        for interpretation in dossier.interpretations:
            for relation_id in interpretation.ids("relation_ids"):
                relation_owners.setdefault(relation_id, []).append(
                    interpretation.interpretation_id
                )
            for proposition_id in interpretation.ids("proposition_ids"):
                proposition_owners.setdefault(proposition_id, []).append(
                    interpretation.interpretation_id
                )
        self._relation_owners = {
            key: tuple(sorted(value)) for key, value in relation_owners.items()
        }
        self._proposition_owners = {
            key: tuple(sorted(value)) for key, value in proposition_owners.items()
        }
        self._arcs = tuple(self._build_arc(item) for item in dossier.relations)

    @classmethod
    def from_dict(
        cls, value: Any, dossier: ArgumentDossier
    ) -> "DependencyUncertaintyAnalysis":
        if not isinstance(value, dict):
            raise DependencyUncertaintyError("uncertainty analysis must be an object")
        _reject_probabilities(value)
        if value.get("schema_version") != "1":
            raise DependencyUncertaintyError("uncertainty analysis schema_version must be 1")
        if value.get("dossier_id") != dossier.dossier_id:
            raise DependencyUncertaintyError("uncertainty analysis has invalid dossier ownership")
        roots_value = value.get("uncertainty_roots")
        if not isinstance(roots_value, list):
            raise DependencyUncertaintyError("uncertainty_roots must be an ordered list")
        roots = tuple(UncertaintyRoot.from_dict(item, dossier) for item in roots_value)
        return cls(dossier, roots)

    def _build_arc(self, relation: PropositionRelation) -> DependencyArc:
        semantics = RELATION_PROPAGATION[relation.relation_type]
        status = relation.to_dict().get("status")
        effect = (
            DependencyEffect.UNRESOLVED.value
            if status == "UNRESOLVED" and semantics.effect != DependencyEffect.NON_PROPAGATING.value
            else semantics.effect
        )
        if semantics.direction == PropagationDirection.TARGET_TO_SOURCE.value:
            upstream, downstream = relation.target_proposition_id, relation.source_proposition_id
        else:
            upstream, downstream = relation.source_proposition_id, relation.target_proposition_id
        return DependencyArc(
            relation.relation_id,
            upstream,
            downstream,
            relation.relation_type,
            effect,
            self._relation_owners.get(relation.relation_id, ()),
        )

    def relation_semantics(self) -> tuple[dict[str, str], ...]:
        return tuple(
            RELATION_PROPAGATION[key].to_dict() for key in sorted(RELATION_PROPAGATION)
        )

    def _context_arcs(self, interpretation_id: str | None) -> tuple[DependencyArc, ...]:
        if interpretation_id is not None and interpretation_id not in self._interpretation_by_id:
            raise DependencyUncertaintyError(f"unknown interpretation {interpretation_id!r}")
        result = []
        for arc in self._arcs:
            if arc.effect == DependencyEffect.NON_PROPAGATING.value:
                continue
            if not arc.interpretation_ids or interpretation_id in arc.interpretation_ids:
                result.append(arc)
        return tuple(sorted(result, key=lambda item: item.relation_id))

    def _active_roots(
        self, root_ids: Iterable[str] | None, interpretation_id: str | None
    ) -> tuple[UncertaintyRoot, ...]:
        if root_ids is None:
            selected = self.roots
        else:
            ids = tuple(root_ids)
            missing = set(ids) - set(self._root_by_id)
            if missing:
                raise DependencyUncertaintyError(
                    "unknown uncertainty roots: " + ", ".join(sorted(missing))
                )
            selected = tuple(self._root_by_id[item] for item in ids)
        return tuple(
            item for item in selected
            if not item.interpretation_ids or interpretation_id in item.interpretation_ids
        )

    def _root_seeds(
        self, root: UncertaintyRoot, interpretation_id: str | None
    ) -> tuple[str, ...]:
        if root.subject_kind == UncertaintySubjectKind.PROPOSITION.value:
            return (root.subject_id,)
        if root.subject_kind == UncertaintySubjectKind.RELATION.value:
            arc = next(item for item in self._arcs if item.relation_id == root.subject_id)
            return (arc.downstream_proposition_id,)
        if root.subject_kind == UncertaintySubjectKind.REPRESENTATION.value:
            return tuple(sorted(
                proposition.proposition_id
                for proposition in self.dossier.propositions
                if any(
                    root.subject_id == link.representation_id
                    or root.subject_id in link.ancestry
                    for link in proposition.source_links
                )
                and (
                    not self._proposition_owners.get(proposition.proposition_id)
                    or interpretation_id in self._proposition_owners[proposition.proposition_id]
                )
            ))
        interpretation = self._interpretation_by_id[root.subject_id]
        return tuple(sorted(interpretation.ids("proposition_ids")))

    def _paths(
        self, seed: str, target: str, interpretation_id: str | None
    ) -> tuple[DependencyPath, ...]:
        if seed == target:
            return (DependencyPath((seed,), (), ()),)
        adjacency: dict[str, list[DependencyArc]] = {}
        for arc in self._context_arcs(interpretation_id):
            adjacency.setdefault(arc.upstream_proposition_id, []).append(arc)
        paths: list[DependencyPath] = []

        def walk(current: str, nodes: tuple[str, ...], arcs: tuple[DependencyArc, ...]) -> None:
            for arc in adjacency.get(current, []):
                next_id = arc.downstream_proposition_id
                if next_id in nodes:
                    continue
                next_nodes = nodes + (next_id,)
                next_arcs = arcs + (arc,)
                if next_id == target:
                    paths.append(DependencyPath(
                        next_nodes,
                        tuple(item.relation_id for item in next_arcs),
                        tuple(item.effect for item in next_arcs),
                    ))
                else:
                    walk(next_id, next_nodes, next_arcs)

        walk(seed, (seed,), ())
        return tuple(sorted(
            paths,
            key=lambda item: (item.proposition_ids, item.relation_ids, item.effects),
        ))

    def _root_impact(
        self,
        root: UncertaintyRoot,
        target: str,
        interpretation_id: str | None,
    ) -> RootImpact:
        seeds = self._root_seeds(root, interpretation_id)
        paths = tuple(
            path for seed in seeds for path in self._paths(seed, target, interpretation_id)
        )
        if not root.content_relevant:
            effect = RootEffect.IRRELEVANT.value
            rationale = "This uncertainty concerns classification or metadata, not proposition content."
        elif not paths:
            effect = RootEffect.IRRELEVANT.value
            rationale = "No dependency path connects this uncertainty to the target proposition."
        elif root.origin_type in {
            UncertaintyOriginType.RELATION_DIRECTION.value,
            UncertaintyOriginType.COMPETING_INTERPRETATION.value,
        }:
            effect = RootEffect.UNRESOLVED.value
            rationale = "The target depends on unresolved structural semantics."
        elif all(not path.relation_ids for path in paths):
            effect = RootEffect.LOCAL.value
            rationale = "The uncertainty is local to the target proposition."
        else:
            effects = {path.aggregate_effect for path in paths}
            if DependencyEffect.UNRESOLVED.value in effects:
                effect = RootEffect.UNRESOLVED.value
                rationale = "At least one relevant path has unresolved dependency semantics."
            elif DependencyEffect.CRITICAL.value in effects:
                effect = RootEffect.CRITICAL.value
                rationale = "A critical dependency path carries this uncertainty to the target."
            elif DependencyEffect.CONTRIBUTORY.value in effects:
                effect = RootEffect.WEAKENING.value
                rationale = "A contributory support path carries weakening uncertainty to the target."
            else:
                effect = RootEffect.SCOPE_MODIFYING.value
                rationale = "A qualification or interpretive path carries scope uncertainty to the target."
        return RootImpact(
            root.root_id,
            root.subject_kind,
            root.subject_id,
            root.origin_type,
            effect,
            paths,
            root.evidence_roots,
            rationale,
        )

    def _dependency_ancestry(
        self, proposition_id: str, interpretation_id: str | None
    ) -> tuple[str, ...]:
        reverse: dict[str, list[str]] = {}
        for arc in self._context_arcs(interpretation_id):
            reverse.setdefault(arc.downstream_proposition_id, []).append(
                arc.upstream_proposition_id
            )
        seen: set[str] = set()
        pending = [proposition_id]
        while pending:
            current = pending.pop()
            if current in seen:
                continue
            seen.add(current)
            pending.extend(sorted(reverse.get(current, []), reverse=True))
        return tuple(sorted(seen))

    def _branch_evidence_roots(
        self, proposition_ids: Iterable[str]
    ) -> tuple[str, ...]:
        return tuple(sorted({
            root
            for proposition_id in proposition_ids
            for root in _proposition_evidence_roots(self._proposition_by_id[proposition_id])
        }))

    def _support_branches(
        self,
        target: str,
        impacts: tuple[RootImpact, ...],
        interpretation_id: str | None,
    ) -> tuple[SupportBranch, ...]:
        incoming = tuple(
            item for item in self._context_arcs(interpretation_id)
            if item.downstream_proposition_id == target
            and item.effect in {
                DependencyEffect.CRITICAL.value,
                DependencyEffect.CONTRIBUTORY.value,
            }
        )
        affected_by_branch: dict[str, set[str]] = {}
        for impact in impacts:
            if impact.effect == RootEffect.IRRELEVANT.value:
                continue
            for path in impact.paths:
                if path.relation_ids:
                    affected_by_branch.setdefault(path.relation_ids[-1], set()).add(
                        impact.root_id
                    )
        uncertain_arcs = {
            arc.relation_id for arc in incoming if affected_by_branch.get(arc.relation_id)
        }
        uncertain_ancestry = {
            arc.relation_id: set(self._dependency_ancestry(
                arc.upstream_proposition_id, interpretation_id
            ))
            for arc in incoming if arc.relation_id in uncertain_arcs
        }
        uncertain_roots = {
            arc.relation_id: set(self._branch_evidence_roots(
                uncertain_ancestry[arc.relation_id]
            ))
            for arc in incoming if arc.relation_id in uncertain_arcs
        }
        branches: list[SupportBranch] = []
        for arc in incoming:
            ancestry = self._dependency_ancestry(
                arc.upstream_proposition_id, interpretation_id
            )
            evidence_roots = self._branch_evidence_roots(ancestry)
            affected = tuple(sorted(affected_by_branch.get(arc.relation_id, set())))
            secure = not affected and arc.effect not in {
                DependencyEffect.UNRESOLVED.value,
                DependencyEffect.NON_PROPAGATING.value,
            }
            independent = False
            if secure and uncertain_arcs:
                independent = all(
                    not (set(ancestry) & uncertain_ancestry[relation_id])
                    and not (set(evidence_roots) & uncertain_roots[relation_id])
                    for relation_id in uncertain_arcs
                )
            branches.append(SupportBranch(
                arc.upstream_proposition_id,
                arc.relation_id,
                arc.relation_type,
                arc.effect,
                evidence_roots,
                ancestry,
                affected,
                secure,
                independent,
            ))
        return tuple(sorted(branches, key=lambda item: item.relation_id))

    def analyze(
        self,
        target_proposition_id: str,
        *,
        active_root_ids: Iterable[str] | None = None,
        interpretation_id: str | None = None,
    ) -> PropositionUncertaintyResult:
        if target_proposition_id not in self._proposition_by_id:
            raise DependencyUncertaintyError(
                f"unknown target proposition {target_proposition_id!r}"
            )
        roots = self._active_roots(active_root_ids, interpretation_id)
        impacts = tuple(sorted(
            (
                self._root_impact(root, target_proposition_id, interpretation_id)
                for root in roots
            ),
            key=lambda item: item.root_id,
        ))
        branches = self._support_branches(
            target_proposition_id, impacts, interpretation_id
        )
        independent = any(item.secure and item.genuinely_independent for item in branches)
        relevant = {item.effect for item in impacts if item.effect != RootEffect.IRRELEVANT.value}
        if not relevant:
            state = TargetUncertaintyState.UNAFFECTED.value
        elif RootEffect.UNRESOLVED.value in relevant and not independent:
            state = TargetUncertaintyState.UNRESOLVED.value
        elif RootEffect.CRITICAL.value in relevant:
            state = (
                TargetUncertaintyState.WEAKENED.value
                if independent else TargetUncertaintyState.MATERIALLY_UNCERTAIN.value
            )
        elif RootEffect.WEAKENING.value in relevant or (
            RootEffect.UNRESOLVED.value in relevant and independent
        ):
            state = TargetUncertaintyState.WEAKENED.value
        elif RootEffect.SCOPE_MODIFYING.value in relevant:
            state = TargetUncertaintyState.QUALIFIED.value
        else:
            state = TargetUncertaintyState.LOCAL_UNCERTAINTY.value
        audit = tuple(
            UncertaintyAuditRecord(
                item.root_id,
                target_proposition_id,
                item.effect,
                item.paths,
                item.rationale,
            )
            for item in impacts
        )
        return PropositionUncertaintyResult(
            self.dossier.dossier_id,
            target_proposition_id,
            interpretation_id,
            state,
            impacts,
            branches,
            tuple(sorted(item.root_id for item in roots)),
            independent,
            audit,
        )

    def analyze_viable_interpretations(
        self,
        target_proposition_id: str,
        *,
        active_root_ids: Iterable[str] | None = None,
    ) -> InterpretationUncertaintySummary:
        viable = tuple(
            item for item in self.dossier.interpretations
            if item.to_dict().get("status") != "REJECTED"
            and target_proposition_id in item.ids("proposition_ids")
        )
        if viable:
            results = tuple(
                self.analyze(
                    target_proposition_id,
                    active_root_ids=active_root_ids,
                    interpretation_id=item.interpretation_id,
                )
                for item in sorted(viable, key=lambda value: value.interpretation_id)
            )
        else:
            results = (self.analyze(
                target_proposition_id, active_root_ids=active_root_ids
            ),)
        blocked = {
            TargetUncertaintyState.MATERIALLY_UNCERTAIN.value,
            TargetUncertaintyState.UNRESOLVED.value,
        }
        return InterpretationUncertaintySummary(
            target_proposition_id,
            results,
            all(item.state not in blocked for item in results),
        )

    def future_consumer_view(
        self, target_proposition_id: str, *, interpretation_id: str | None = None
    ) -> dict[str, Any]:
        """Return neutral upstream uncertainty without creating a later graph."""

        result = self.analyze(target_proposition_id, interpretation_id=interpretation_id)
        return {
            "dossier_id": result.dossier_id,
            "proposition_id": result.target_proposition_id,
            "uncertainty_state": result.state,
            "active_root_ids": list(result.active_root_ids),
            "audit_trail": [item.to_dict() for item in result.audit_trail],
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1",
            "dossier_id": self.dossier.dossier_id,
            "uncertainty_roots": [
                item.to_dict() for item in sorted(self.roots, key=lambda value: value.root_id)
            ],
            "relation_semantics": list(self.relation_semantics()),
        }


@dataclass(frozen=True)
class DependencyUncertaintyResult:
    analysis: DependencyUncertaintyAnalysis
    results: tuple[PropositionUncertaintyResult, ...]
    audit: AuditResult

    def __post_init__(self) -> None:
        if not self.audit.passed:
            raise DependencyUncertaintyError(
                "failed uncertainty audit cannot produce an accepted result"
            )

    def to_dict(self) -> dict[str, Any]:
        value = {
            "status": "validated",
            "analysis": self.analysis.to_dict(),
            "results": [item.to_dict() for item in self.results],
            "audit": {
                "status": self.audit.status,
                "findings": self.audit.to_v01_strings(),
            },
        }
        value["result_sha256"] = sha256_json(value["results"])
        return value

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())


def audit_dependency_uncertainty(
    value: Any, dossier: ArgumentDossier
) -> AuditResult:
    try:
        analysis = DependencyUncertaintyAnalysis.from_dict(value, dossier)
        targets = value.get("targets", []) if isinstance(value, dict) else []
        if not isinstance(targets, list) or not targets:
            raise DependencyUncertaintyError("uncertainty analysis requires targets")
        for target in targets:
            if not isinstance(target, dict):
                raise DependencyUncertaintyError("uncertainty target must be an object")
            analysis.analyze(
                target.get("target_proposition_id"),
                active_root_ids=target.get("active_root_ids"),
                interpretation_id=target.get("interpretation_id"),
            )
    except ValidationError as exc:
        return AuditResult((AuditFinding("DEPENDENCY_UNCERTAINTY_INVALID", str(exc)),))
    return AuditResult()


def construct_dependency_uncertainty(
    value: Any, dossier: ArgumentDossier
) -> DependencyUncertaintyResult:
    audit = audit_dependency_uncertainty(value, dossier)
    if not audit.passed:
        raise DependencyUncertaintyError(audit.findings[0].to_v01_string())
    analysis = DependencyUncertaintyAnalysis.from_dict(value, dossier)
    results = tuple(
        analysis.analyze(
            item["target_proposition_id"],
            active_root_ids=item.get("active_root_ids"),
            interpretation_id=item.get("interpretation_id"),
        )
        for item in value["targets"]
    )
    return DependencyUncertaintyResult(analysis, results, audit)


if HISTORICAL_RELATION_TYPES & set(RELATION_PROPAGATION):
    raise RuntimeError("historical relation types cannot enter Phase 4 propagation")
