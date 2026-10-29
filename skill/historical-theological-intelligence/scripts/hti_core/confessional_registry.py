"""Phase 9 confessional-creedal registry, doctrinal comparison, and locus tracing.

This module creates a doctrinal relation layer over bounded propositions. It
does not infer historical dependence from correspondence, chronology, or
confessional succession, and it never mutates Phase 3, Phase 5, Phase 8, or
textual-witness state.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

from .audit import AuditFinding, AuditResult
from .hashing import canonical_json, sha256_json
from .model import ValidationError
from .provenance import ProvenanceRecord


class ConfessionalRegistryError(ValidationError):
    """Raised when Phase 9 evidence or structure fails closed."""


class DocumentType(str, Enum):
    CREED = "CREED"
    CONCILIAR_DEFINITION = "CONCILIAR_DEFINITION"
    CONFESSION = "CONFESSION"
    CATECHISM = "CATECHISM"
    CANONS = "CANONS"


class DatingStatus(str, Enum):
    ESTABLISHED = "ESTABLISHED"
    BOUNDED = "BOUNDED"
    DISPUTED = "DISPUTED"


class LocatorKind(str, Enum):
    CLAUSE = "CLAUSE"
    PARAGRAPH = "PARAGRAPH"
    ARTICLE = "ARTICLE"
    CHAPTER_SECTION = "CHAPTER_SECTION"
    QUESTION_ANSWER = "QUESTION_ANSWER"
    HEAD_ARTICLE = "HEAD_ARTICLE"
    DEFINITION_SECTION = "DEFINITION_SECTION"


class DoctrinalRelationType(str, Enum):
    DOCTRINAL_CORRESPONDENCE = "DOCTRINAL_CORRESPONDENCE"
    QUALIFICATION = "QUALIFICATION"
    DISTINCTION = "DISTINCTION"
    DEVELOPMENT = "DEVELOPMENT"
    CODIFICATION = "CODIFICATION"
    EXCLUSION_OF_ALTERNATIVE = "EXCLUSION_OF_ALTERNATIVE"
    TENSION = "TENSION"
    CONTRADICTION = "CONTRADICTION"
    LATER_ANALOGY = "LATER_ANALOGY"
    HISTORICALLY_DEMONSTRATED_DEPENDENCE = "HISTORICALLY_DEMONSTRATED_DEPENDENCE"


class DependenceStatus(str, Enum):
    NOT_CLAIMED = "NOT_CLAIMED"
    WITHHELD = "WITHHELD"
    UNRESOLVED = "UNRESOLVED"
    LICENSED = "LICENSED"
    REJECTED_CHRONOLOGY = "REJECTED_CHRONOLOGY"


class StatementStatus(str, Enum):
    EXPLICIT_FORMULATION = "EXPLICIT_FORMULATION"
    EXPLICIT_QUALIFICATION = "EXPLICIT_QUALIFICATION"
    EXPLICIT_EXCLUSION = "EXPLICIT_EXCLUSION"
    EXPLICIT_CONTRADICTION = "EXPLICIT_CONTRADICTION"
    NO_LOCATED_STATEMENT = "NO_LOCATED_STATEMENT"
    TEXTUAL_SILENCE = "TEXTUAL_SILENCE"
    SEARCH_INCOMPLETE = "SEARCH_INCOMPLETE"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    RELEVANCE_UNRESOLVED = "RELEVANCE_UNRESOLVED"
    NOT_RELEVANT = "NOT_RELEVANT"


class ComparisonDirection(str, Enum):
    SYNCHRONIC = "SYNCHRONIC"
    DIACHRONIC = "DIACHRONIC"


INITIAL_REGISTRY_IDS = (
    "apostles-creed", "nicene-constantinopolitan-creed", "chalcedonian-definition",
    "athanasian-creed", "scots-confession", "french-gallican-confession",
    "belgic-confession", "heidelberg-catechism", "second-helvetic-confession",
    "canons-of-dort", "westminster-confession", "westminster-larger-catechism",
    "westminster-shorter-catechism",
)

CORE_LOCUS_IDS = (
    "trinity", "christology", "covenant", "justification",
    "sacraments", "law", "providence", "ecclesiology",
)

DOCTRINAL_RELATION_TYPES = frozenset(item.value for item in DoctrinalRelationType)
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_FORBIDDEN_POLICY_KEYS = frozenset({
    "correspondence_implies_dependence", "chronology_implies_influence",
    "silence_implies_exclusion", "translation_is_original", "bypass_phase5",
    "rank_confessions", "enable_phase10", "enable_work_specialization",
    "enable_novelty", "enable_whole_work_cartography",
})


def _obj(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ConfessionalRegistryError(f"{label} must be an object")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfessionalRegistryError(f"{label} must be non-empty text")
    return value.strip()


def _id(value: Any, label: str) -> str:
    value = _text(value, label)
    if not _ID.fullmatch(value):
        raise ConfessionalRegistryError(f"{label} must be a stable identifier")
    return value


def _enum(value: Any, kind: type[Enum], label: str) -> str:
    if not isinstance(value, str):
        raise ConfessionalRegistryError(f"{label} must be a declared string value")
    try:
        kind(value)
    except ValueError as exc:
        raise ConfessionalRegistryError(f"invalid {label} {value!r}") from exc
    return value


def _texts(value: Any, label: str, *, required: bool = False) -> tuple[str, ...]:
    if value is None:
        value = []
    if not isinstance(value, list):
        raise ConfessionalRegistryError(f"{label} must be an ordered list")
    result = tuple(_text(item, f"{label} item") for item in value)
    if len(result) != len(set(result)):
        raise ConfessionalRegistryError(f"{label} contains duplicates")
    if required and not result:
        raise ConfessionalRegistryError(f"{label} must not be empty")
    return result


def _ids(value: Any, label: str, *, required: bool = False) -> tuple[str, ...]:
    return tuple(_id(item, f"{label} item") for item in _texts(value, label, required=required))


@dataclass(frozen=True)
class RegistryEntry:
    _raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, value: Any) -> "RegistryEntry":
        raw = _obj(value, "registry entry")
        _id(raw.get("registry_id"), "registry_id")
        _text(raw.get("canonical_title"), "canonical_title")
        _texts(raw.get("aliases"), "aliases")
        _enum(raw.get("document_type"), DocumentType, "document_type")
        date = _obj(raw.get("dating"), "dating")
        _text(date.get("display"), "dating display")
        _enum(date.get("status"), DatingStatus, "dating status")
        _texts(raw.get("source_languages"), "source_languages", required=True)
        version = _obj(raw.get("textual_form"), "textual_form")
        _id(version.get("version_id"), "version_id")
        _text(version.get("description"), "textual form description")
        if "translation" in version and version["translation"] is not None:
            _text(version["translation"], "translation identity")
        sources = raw.get("sources")
        if not isinstance(sources, list) or not sources:
            raise ConfessionalRegistryError("registry source provenance is required")
        for source in sources:
            source = _obj(source, "registry source")
            _id(source.get("source_id"), "source_id")
            _text(source.get("citation"), "source citation")
            _text(source.get("url"), "source URL")
            _text(source.get("accessed"), "source access date")
        schemas = raw.get("locator_schemas")
        if not isinstance(schemas, list) or not schemas:
            raise ConfessionalRegistryError("locator_schemas must not be empty")
        for schema in schemas:
            schema = _obj(schema, "locator schema")
            _enum(schema.get("kind"), LocatorKind, "locator kind")
            _texts(schema.get("parts"), "locator parts", required=True)
        smoke = raw.get("smoke_verification")
        if not isinstance(smoke, list) or not smoke:
            raise ConfessionalRegistryError("each registry entry requires direct-text smoke verification")
        for item in smoke:
            item = _obj(item, "smoke verification")
            _text(item.get("citation"), "smoke citation")
            _text(item.get("text"), "smoke text")
            _id(item.get("source_id"), "smoke source_id")
        ProvenanceRecord.from_dict(raw.get("audit_provenance"))
        return cls(copy.deepcopy(raw))

    @property
    def registry_id(self) -> str:
        return str(self._raw["registry_id"])

    @property
    def aliases(self) -> tuple[str, ...]:
        return tuple(self._raw.get("aliases", []))

    @property
    def locator_kinds(self) -> frozenset[str]:
        return frozenset(item["kind"] for item in self._raw["locator_schemas"])

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class ConfessionalRegistry:
    schema_version: str
    entries: tuple[RegistryEntry, ...]

    @classmethod
    def from_dict(cls, value: Any, *, require_initial: bool = True) -> "ConfessionalRegistry":
        raw = _obj(value, "confessional registry")
        if raw.get("schema_version") != "1":
            raise ConfessionalRegistryError("registry schema_version must be 1")
        entries = tuple(RegistryEntry.from_dict(item) for item in raw.get("entries", []))
        ids = [item.registry_id for item in entries]
        if len(ids) != len(set(ids)):
            raise ConfessionalRegistryError("duplicate registry IDs")
        if require_initial and not set(INITIAL_REGISTRY_IDS) <= set(ids):
            missing = sorted(set(INITIAL_REGISTRY_IDS) - set(ids))
            raise ConfessionalRegistryError(f"missing locked initial registry entries: {missing}")
        aliases: dict[str, str] = {}
        for entry in entries:
            for alias in (entry.registry_id, *entry.aliases):
                key = alias.casefold().strip()
                if key in aliases and aliases[key] != entry.registry_id:
                    raise ConfessionalRegistryError(f"ambiguous registry alias: {alias}")
                aliases[key] = entry.registry_id
        return cls("1", tuple(sorted(entries, key=lambda item: item.registry_id)))

    @classmethod
    def load(cls, path: Path | None = None) -> "ConfessionalRegistry":
        if path is None:
            path = Path(__file__).resolve().parents[2] / "resources" / "confessional-registry" / "initial-registry.json"
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def resolve(self, name: str) -> RegistryEntry:
        key = _text(name, "registry lookup").casefold()
        matches = [item for item in self.entries if key in {
            item.registry_id.casefold(), item.to_dict()["canonical_title"].casefold(),
            *(alias.casefold() for alias in item.aliases),
        }]
        if len(matches) != 1:
            raise ConfessionalRegistryError("registry lookup must resolve uniquely")
        return matches[0]

    def extend(self, entry: RegistryEntry) -> "ConfessionalRegistry":
        before = {item.registry_id: item.to_dict() for item in self.entries}
        result = ConfessionalRegistry.from_dict({"schema_version": "1", "entries": [item.to_dict() for item in self.entries] + [entry.to_dict()]})
        after = {item.registry_id: item.to_dict() for item in result.entries}
        if any(after[key] != value for key, value in before.items()):
            raise ConfessionalRegistryError("extension mutated an existing registry entry")
        return result

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "entries": [item.to_dict() for item in self.entries]}

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())


@dataclass(frozen=True)
class RegistryLocator:
    document_id: str
    kind: str
    parts: Mapping[str, str]
    human_citation: str

    @classmethod
    def from_dict(cls, value: Any, registry: ConfessionalRegistry) -> "RegistryLocator":
        raw = _obj(value, "registry locator")
        document_id = _id(raw.get("document_id"), "locator document_id")
        entry = registry.resolve(document_id)
        kind = _enum(raw.get("kind"), LocatorKind, "locator kind")
        if kind not in entry.locator_kinds:
            raise ConfessionalRegistryError("locator kind is not licensed for this registry document")
        parts = _obj(raw.get("parts"), "locator parts")
        if not parts or not all(isinstance(k, str) and isinstance(v, str) and v.strip() for k, v in parts.items()):
            raise ConfessionalRegistryError("locator parts must contain named non-empty strings")
        human = _text(raw.get("human_citation"), "human_citation")
        return cls(document_id, kind, copy.deepcopy(parts), human)

    def to_dict(self) -> dict[str, Any]:
        return {"document_id": self.document_id, "kind": self.kind, "parts": dict(sorted(self.parts.items())), "human_citation": self.human_citation}


@dataclass(frozen=True)
class LocusDescriptor:
    locus_id: str
    label: str
    aliases: tuple[str, ...]
    description: str
    parent_id: str | None
    provenance: Mapping[str, Any]

    @classmethod
    def from_dict(cls, value: Any) -> "LocusDescriptor":
        raw = _obj(value, "locus descriptor")
        locus_id = _id(raw.get("locus_id"), "locus_id")
        label = _text(raw.get("label"), "locus label")
        aliases = _texts(raw.get("aliases"), "locus aliases")
        description = _text(raw.get("description"), "locus description")
        parent = raw.get("parent_id")
        if parent is not None:
            parent = _id(parent, "parent_id")
        provenance = ProvenanceRecord.from_dict(raw.get("provenance")).to_dict()
        return cls(locus_id, label, aliases, description, parent, provenance)


@dataclass(frozen=True)
class LocusRegistry:
    loci: tuple[LocusDescriptor, ...]

    @classmethod
    def from_dict(cls, value: Any, *, require_core: bool = True) -> "LocusRegistry":
        raw = _obj(value, "locus registry")
        loci = tuple(LocusDescriptor.from_dict(item) for item in raw.get("loci", []))
        ids = [item.locus_id for item in loci]
        if len(ids) != len(set(ids)):
            raise ConfessionalRegistryError("duplicate locus IDs")
        if require_core and not set(CORE_LOCUS_IDS) <= set(ids):
            raise ConfessionalRegistryError("required core loci are missing")
        alias_owner: dict[str, str] = {}
        for item in loci:
            for alias in (item.locus_id, item.label, *item.aliases):
                key = alias.casefold()
                if key in alias_owner and alias_owner[key] != item.locus_id:
                    raise ConfessionalRegistryError("ambiguous locus alias")
                alias_owner[key] = item.locus_id
        return cls(tuple(sorted(loci, key=lambda item: item.locus_id)))

    @classmethod
    def load(cls, path: Path | None = None) -> "LocusRegistry":
        if path is None:
            path = Path(__file__).resolve().parents[2] / "resources" / "confessional-registry" / "loci.json"
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))


@dataclass(frozen=True)
class ConfessionalProposition:
    _raw: Mapping[str, Any] = field(repr=False)
    locators: tuple[RegistryLocator, ...]

    @classmethod
    def from_dict(cls, value: Any, registry: ConfessionalRegistry, loci: LocusRegistry) -> "ConfessionalProposition":
        raw = _obj(value, "confessional proposition")
        _id(raw.get("proposition_id"), "proposition_id")
        doc_id = _id(raw.get("document_id"), "document_id")
        registry.resolve(doc_id)
        locators = tuple(RegistryLocator.from_dict(item, registry) for item in raw.get("locators", []))
        if not locators or any(item.document_id != doc_id for item in locators):
            raise ConfessionalRegistryError("proposition locators must belong to its registry document")
        _text(raw.get("bounded_text"), "bounded proposition text")
        _id(raw.get("representation_id"), "representation_id")
        _text(raw.get("source_form"), "source_form")
        locus_ids = _ids(raw.get("locus_ids"), "locus_ids", required=True)
        if set(locus_ids) - {item.locus_id for item in loci.loci}:
            raise ConfessionalRegistryError("unresolved locus classification must be explicit, not an unknown ID")
        _texts(raw.get("argument_functions"), "argument_functions")
        ProvenanceRecord.from_dict(raw.get("provenance"))
        return cls(copy.deepcopy(raw), tuple(sorted(locators, key=lambda item: (item.document_id, item.kind, item.human_citation))))

    @property
    def proposition_id(self) -> str:
        return str(self._raw["proposition_id"])

    @property
    def document_id(self) -> str:
        return str(self._raw["document_id"])

    def to_dict(self) -> dict[str, Any]:
        result = copy.deepcopy(dict(self._raw))
        result["locators"] = [item.to_dict() for item in self.locators]
        return result


@dataclass(frozen=True)
class DoctrinalEvidence:
    _raw: Mapping[str, Any] = field(repr=False)
    evidence_roots: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: Any) -> "DoctrinalEvidence":
        raw = _obj(value, "doctrinal evidence")
        _id(raw.get("evidence_id"), "evidence_id")
        _text(raw.get("evidence_type"), "evidence_type")
        _text(raw.get("description"), "evidence description")
        _ids(raw.get("representation_ids"), "representation_ids", required=True)
        roots = _ids(raw.get("evidence_roots"), "evidence_roots", required=True)
        ProvenanceRecord.from_dict(raw.get("provenance"))
        return cls(copy.deepcopy(raw), roots)

    @property
    def evidence_id(self) -> str:
        return str(self._raw["evidence_id"])

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class DoctrinalRelationClaim:
    _raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(
        cls,
        value: Any,
        *,
        proposition_ids: frozenset[str],
        evidence_ids: frozenset[str],
        licensed_phase5_edges: frozenset[str],
    ) -> "DoctrinalRelationClaim":
        raw = _obj(value, "doctrinal relation claim")
        _id(raw.get("relation_id"), "relation_id")
        relation = _enum(raw.get("relation_type"), DoctrinalRelationType, "relation_type")
        source = _id(raw.get("source_proposition_id"), "source_proposition_id")
        target = _id(raw.get("target_proposition_id"), "target_proposition_id")
        if source == target or {source, target} - proposition_ids:
            raise ConfessionalRegistryError("doctrinal relation endpoints must be distinct known propositions")
        _text(raw.get("bounded_scope"), "bounded relation scope")
        _text(raw.get("confidence"), "qualitative confidence")
        positive = _ids(raw.get("positive_evidence_ids"), "positive_evidence_ids", required=True)
        counter = _ids(raw.get("counterevidence_ids"), "counterevidence_ids")
        if (set(positive) | set(counter)) - evidence_ids:
            raise ConfessionalRegistryError("doctrinal relation references unknown evidence")
        _texts(raw.get("upstream_uncertainty"), "upstream_uncertainty")
        statement_status = _enum(raw.get("statement_status"), StatementStatus, "statement_status")
        if relation in {DoctrinalRelationType.EXCLUSION_OF_ALTERNATIVE.value, DoctrinalRelationType.CONTRADICTION.value}:
            required = StatementStatus.EXPLICIT_EXCLUSION.value if relation == DoctrinalRelationType.EXCLUSION_OF_ALTERNATIVE.value else StatementStatus.EXPLICIT_CONTRADICTION.value
            if statement_status != required:
                raise ConfessionalRegistryError("silence, absence, or search failure cannot establish exclusion or contradiction")
        if relation == DoctrinalRelationType.CONTRADICTION.value:
            _text(raw.get("matched_subject_scope"), "matched_subject_scope")
            _texts(raw.get("qualification_checks"), "qualification_checks", required=True)
        if relation == DoctrinalRelationType.TENSION.value:
            _text(raw.get("discriminating_issue"), "tension discriminating issue")
        phase5_ids = _ids(raw.get("phase5_edge_ids"), "phase5_edge_ids")
        if relation == DoctrinalRelationType.HISTORICALLY_DEMONSTRATED_DEPENDENCE.value:
            if not phase5_ids or set(phase5_ids) - licensed_phase5_edges:
                raise ConfessionalRegistryError("historical dependence requires licensed Phase 5 edge references")
            if raw.get("chronology_status") == "INCOMPATIBLE":
                raise ConfessionalRegistryError("impossible chronology blocks historical dependence")
        elif phase5_ids and set(phase5_ids) - licensed_phase5_edges:
            raise ConfessionalRegistryError("unknown Phase 5 edge reference")
        if raw.get("chronology_only", False) or raw.get("similarity_only", False):
            if relation == DoctrinalRelationType.HISTORICALLY_DEMONSTRATED_DEPENDENCE.value:
                raise ConfessionalRegistryError("chronology or similarity alone cannot establish dependence")
        _ids(raw.get("phase7_profile_ids"), "phase7_profile_ids")
        _ids(raw.get("phase8_analysis_ids"), "phase8_analysis_ids")
        ProvenanceRecord.from_dict(raw.get("provenance"))
        return cls(copy.deepcopy(raw))

    @property
    def relation_id(self) -> str:
        return str(self._raw["relation_id"])

    @property
    def relation_type(self) -> str:
        return str(self._raw["relation_type"])

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class Phase9AnalysisPolicy:
    _raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, value: Any) -> "Phase9AnalysisPolicy":
        raw = _obj(value, "Phase 9 analysis policy")
        _id(raw.get("locus_id"), "policy locus_id")
        _enum(raw.get("comparison_direction"), ComparisonDirection, "comparison_direction")
        _ids(raw.get("document_subset"), "document_subset")
        for key in _FORBIDDEN_POLICY_KEYS:
            if raw.get(key, False):
                raise ConfessionalRegistryError(f"policy cannot enable {key}")
        if raw.get("deterministic_ordering", "DOCUMENT_DATE_LOCATOR_ID") != "DOCUMENT_DATE_LOCATOR_ID":
            raise ConfessionalRegistryError("unsupported deterministic ordering")
        return cls(copy.deepcopy(raw))


@dataclass(frozen=True)
class ConfessionalFormulationComparison:
    comparison_id: str
    locus_id: str
    propositions: tuple[ConfessionalProposition, ...]
    evidence: tuple[DoctrinalEvidence, ...]
    relations: tuple[DoctrinalRelationClaim, ...]
    dependence_status: str
    counterevidence_ids: tuple[str, ...]
    competing_interpretations: tuple[Mapping[str, Any], ...]
    unresolved_questions: tuple[str, ...]
    policy: Phase9AnalysisPolicy
    provenance: Mapping[str, Any]

    @classmethod
    def from_dict(
        cls,
        value: Any,
        *,
        registry: ConfessionalRegistry,
        loci: LocusRegistry,
        licensed_phase5_edges: Iterable[str] = (),
    ) -> "ConfessionalFormulationComparison":
        raw = _obj(value, "confessional formulation comparison")
        if raw.get("schema_version") != "1":
            raise ConfessionalRegistryError("comparison schema_version must be 1")
        comparison_id = _id(raw.get("comparison_id"), "comparison_id")
        locus_id = _id(raw.get("locus_id"), "locus_id")
        if locus_id not in {item.locus_id for item in loci.loci}:
            raise ConfessionalRegistryError("unknown locus")
        propositions = tuple(ConfessionalProposition.from_dict(item, registry, loci) for item in raw.get("propositions", []))
        prop_ids = [item.proposition_id for item in propositions]
        if len(propositions) < 2 or len(prop_ids) != len(set(prop_ids)):
            raise ConfessionalRegistryError("comparison requires at least two uniquely identified propositions")
        evidence = tuple(DoctrinalEvidence.from_dict(item) for item in raw.get("evidence", []))
        evidence_ids = [item.evidence_id for item in evidence]
        if not evidence or len(evidence_ids) != len(set(evidence_ids)):
            raise ConfessionalRegistryError("comparison requires uniquely identified evidence")
        relations = tuple(DoctrinalRelationClaim.from_dict(
            item,
            proposition_ids=frozenset(prop_ids),
            evidence_ids=frozenset(evidence_ids),
            licensed_phase5_edges=frozenset(licensed_phase5_edges),
        ) for item in raw.get("relations", []))
        if not relations or len({item.relation_id for item in relations}) != len(relations):
            raise ConfessionalRegistryError("comparison requires uniquely identified doctrinal relations")
        dependence_status = _enum(raw.get("historical_dependence_status"), DependenceStatus, "historical_dependence_status")
        has_licensed = any(item.relation_type == DoctrinalRelationType.HISTORICALLY_DEMONSTRATED_DEPENDENCE.value for item in relations)
        if dependence_status == DependenceStatus.LICENSED.value and not has_licensed:
            raise ConfessionalRegistryError("licensed dependence status requires a licensed dependence relation")
        if dependence_status != DependenceStatus.LICENSED.value and has_licensed:
            raise ConfessionalRegistryError("demonstrated dependence relation requires LICENSED status")
        counter = _ids(raw.get("counterevidence_ids"), "counterevidence_ids")
        if set(counter) - set(evidence_ids):
            raise ConfessionalRegistryError("counterevidence references unknown evidence")
        interpretations = raw.get("competing_interpretations", [])
        if not isinstance(interpretations, list) or not all(isinstance(item, dict) for item in interpretations):
            raise ConfessionalRegistryError("competing_interpretations must be an ordered list")
        unresolved = _texts(raw.get("unresolved_questions"), "unresolved_questions")
        policy = Phase9AnalysisPolicy.from_dict(raw.get("policy"))
        provenance = ProvenanceRecord.from_dict(raw.get("provenance")).to_dict()
        return cls(
            comparison_id, locus_id,
            tuple(sorted(propositions, key=lambda item: (item.document_id, item.proposition_id))),
            tuple(sorted(evidence, key=lambda item: item.evidence_id)),
            tuple(sorted(relations, key=lambda item: (item.relation_type, item.relation_id))),
            dependence_status, tuple(sorted(counter)),
            tuple(sorted((copy.deepcopy(item) for item in interpretations), key=lambda item: str(item.get("interpretation_id", "")))),
            tuple(sorted(unresolved)), policy, provenance,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1", "comparison_id": self.comparison_id,
            "locus_id": self.locus_id,
            "propositions": [item.to_dict() for item in self.propositions],
            "evidence": [item.to_dict() for item in self.evidence],
            "relations": [item.to_dict() for item in self.relations],
            "historical_dependence_status": self.dependence_status,
            "counterevidence_ids": list(self.counterevidence_ids),
            "competing_interpretations": [copy.deepcopy(item) for item in self.competing_interpretations],
            "unresolved_questions": list(self.unresolved_questions),
            "policy": self.policy._raw,
            "provenance": copy.deepcopy(dict(self.provenance)),
        }

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())

    def digest(self) -> str:
        return sha256_json(self.to_dict())


@dataclass(frozen=True)
class LocusTraceEntry:
    _raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, value: Any, registry: ConfessionalRegistry, loci: LocusRegistry) -> "LocusTraceEntry":
        raw = _obj(value, "locus trace entry")
        _id(raw.get("entry_id"), "entry_id")
        _id(raw.get("proposition_id"), "proposition_id")
        registry.resolve(_id(raw.get("document_id"), "document_id"))
        _id(raw.get("locus_id"), "locus_id")
        _text(raw.get("chronology_key"), "chronology_key")
        _enum(raw.get("statement_status"), StatementStatus, "statement_status")
        _enum(raw.get("historical_dependence_status"), DependenceStatus, "historical_dependence_status")
        _texts(raw.get("relation_ids"), "relation_ids")
        _texts(raw.get("unresolved_gaps"), "unresolved_gaps")
        ProvenanceRecord.from_dict(raw.get("provenance"))
        return cls(copy.deepcopy(raw))

    @property
    def entry_id(self) -> str:
        return str(self._raw["entry_id"])

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class LocusTraceProfile:
    trace_id: str
    locus_id: str
    anchor_ref: str
    entries: tuple[LocusTraceEntry, ...]
    comparison_ids: tuple[str, ...]
    omitted_non_relevant_documents: tuple[str, ...]
    unresolved_questions: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: Any, *, registry: ConfessionalRegistry, loci: LocusRegistry) -> "LocusTraceProfile":
        raw = _obj(value, "locus trace profile")
        trace_id = _id(raw.get("trace_id"), "trace_id")
        locus_id = _id(raw.get("locus_id"), "locus_id")
        if locus_id not in {item.locus_id for item in loci.loci}:
            raise ConfessionalRegistryError("unknown trace locus")
        anchor = _id(raw.get("anchor_ref"), "anchor_ref")
        entries = tuple(LocusTraceEntry.from_dict(item, registry, loci) for item in raw.get("entries", []))
        if not entries or len({item.entry_id for item in entries}) != len(entries):
            raise ConfessionalRegistryError("trace requires uniquely identified relevant entries")
        comparison_ids = _ids(raw.get("comparison_ids"), "comparison_ids")
        omitted = _ids(raw.get("omitted_non_relevant_documents"), "omitted_non_relevant_documents")
        for document_id in omitted:
            registry.resolve(document_id)
        unresolved = _texts(raw.get("unresolved_questions"), "unresolved_questions")
        if raw.get("force_all_registry_documents", False):
            raise ConfessionalRegistryError("a bounded locus trace must not mechanically force all registry documents")
        return cls(trace_id, locus_id, anchor, tuple(sorted(entries, key=lambda item: (item.to_dict()["chronology_key"], item.entry_id))), tuple(sorted(comparison_ids)), tuple(sorted(omitted)), tuple(sorted(unresolved)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id, "locus_id": self.locus_id,
            "anchor_ref": self.anchor_ref,
            "entries": [item.to_dict() for item in self.entries],
            "comparison_ids": list(self.comparison_ids),
            "omitted_non_relevant_documents": list(self.omitted_non_relevant_documents),
            "unresolved_questions": list(self.unresolved_questions),
        }

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())


@dataclass(frozen=True)
class Phase9ConstructionResult:
    comparison: ConfessionalFormulationComparison | None
    audit: AuditResult


def construct_confessional_comparison(value: Any, *, registry: ConfessionalRegistry, loci: LocusRegistry, licensed_phase5_edges: Iterable[str] = ()) -> Phase9ConstructionResult:
    try:
        result = ConfessionalFormulationComparison.from_dict(value, registry=registry, loci=loci, licensed_phase5_edges=licensed_phase5_edges)
        return Phase9ConstructionResult(result, AuditResult(()))
    except (ConfessionalRegistryError, ValidationError) as exc:
        return Phase9ConstructionResult(None, AuditResult((AuditFinding("PHASE9_CONFESSIONAL_COMPARISON_INVALID", str(exc)),)))


def audit_confessional_comparison(*args: Any, **kwargs: Any) -> AuditResult:
    return construct_confessional_comparison(*args, **kwargs).audit
