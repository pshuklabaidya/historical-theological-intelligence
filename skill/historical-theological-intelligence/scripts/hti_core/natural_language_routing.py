"""Phase 11 natural-language control plane for Historical-Theological Intelligence.

The router creates inspectable operation plans over accepted Phase 1-10
capabilities. It does not establish identities, readings, historical relations,
transmission paths, conceptual continuity, or confessional relations.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

from .hashing import canonical_json, sha256_json
from .model import ValidationError


class RoutingError(ValidationError):
    """Raised when a request or operation plan fails closed."""


class IntentFamily(str, Enum):
    SPECIALIZATION_ONBOARDING = "SPECIALIZATION_ONBOARDING"
    HISTORICAL_ACCESS_NETWORK = "HISTORICAL_ACCESS_NETWORK"
    HISTORICAL_SENSITIVITY = "HISTORICAL_SENSITIVITY"
    NOVELTY_ANALYSIS = "NOVELTY_ANALYSIS"
    ORIGINALITY_ADJUDICATION = "ORIGINALITY_ADJUDICATION"
    NOVELTY_LEDGER_AUDIT = "NOVELTY_LEDGER_AUDIT"
    WHOLE_WORK_CARTOGRAPHY = "WHOLE_WORK_CARTOGRAPHY"
    DEVELOPMENTAL_CARTOGRAPHY = "DEVELOPMENTAL_CARTOGRAPHY"
    COMPARATIVE_CARTOGRAPHY = "COMPARATIVE_CARTOGRAPHY"
    INTERLOCUTOR_RECONSTRUCTION = "INTERLOCUTOR_RECONSTRUCTION"
    PRESSURE_FIELD_ANALYSIS = "PRESSURE_FIELD_ANALYSIS"
    SIMPLE_TRANSLATION = "SIMPLE_TRANSLATION"
    SCHOLARLY_TRANSLATION = "SCHOLARLY_TRANSLATION"
    TEXTUAL_WITNESS_ANALYSIS = "TEXTUAL_WITNESS_ANALYSIS"
    IDENTITY_INVESTIGATION = "IDENTITY_INVESTIGATION"
    SOURCE_AUTHORITY_VERIFICATION = "SOURCE_AUTHORITY_VERIFICATION"
    ARGUMENT_RECONSTRUCTION = "ARGUMENT_RECONSTRUCTION"
    HISTORICAL_RELATION = "HISTORICAL_RELATION"
    HISTORICAL_LINEAGE = "HISTORICAL_LINEAGE"
    SOURCE_TRANSMISSION = "SOURCE_TRANSMISSION"
    IMMEDIATE_SOURCE_ADJUDICATION = "IMMEDIATE_SOURCE_ADJUDICATION"
    RECEPTION_HISTORY = "RECEPTION_HISTORY"
    CONCEPTUAL_HISTORY = "CONCEPTUAL_HISTORY"
    CONFESSIONAL_LOCUS_TRACE = "CONFESSIONAL_LOCUS_TRACE"
    CONFESSIONAL_FORMULATION_COMPARISON = "CONFESSIONAL_FORMULATION_COMPARISON"
    RARE_BOOK_ANALYSIS = "RARE_BOOK_ANALYSIS"
    MARGINALIA_ANALYSIS = "MARGINALIA_ANALYSIS"
    PASTORAL_STUDY = "PASTORAL_STUDY"
    CITATION_READY_OUTPUT = "CITATION_READY_OUTPUT"
    COMPOSITE_REQUEST = "COMPOSITE_REQUEST"
    DIPLOMATIC_TRANSCRIPTION = "DIPLOMATIC_TRANSCRIPTION"
    NORMALIZED_LATIN = "NORMALIZED_LATIN"
    PAGE_ORDER_RECONSTRUCTION = "PAGE_ORDER_RECONSTRUCTION"
    SCRIPTURE_APPARATUS = "SCRIPTURE_APPARATUS"
    ORIGINAL_LANGUAGE_ANALYSIS = "ORIGINAL_LANGUAGE_ANALYSIS"
    CROSS_WORK_SEARCH = "CROSS_WORK_SEARCH"
    LOCUS_DETECTION = "LOCUS_DETECTION"
    EXEGETICAL_METHOD = "EXEGETICAL_METHOD"
    RESEARCH_STATE = "RESEARCH_STATE"


class OperationID(str, Enum):
    ONBOARD_SPECIALIZATION = "ONBOARD_SPECIALIZATION"
    ASSESS_ACCESS_NETWORK = "ASSESS_ACCESS_NETWORK"
    TEST_HISTORICAL_SENSITIVITY = "TEST_HISTORICAL_SENSITIVITY"
    ASSESS_NOVELTY = "ASSESS_NOVELTY"
    ADJUDICATE_ORIGINALITY = "ADJUDICATE_ORIGINALITY"
    AUDIT_NOVELTY_LEDGER = "AUDIT_NOVELTY_LEDGER"
    MAP_WHOLE_WORK = "MAP_WHOLE_WORK"
    MAP_DEVELOPMENT = "MAP_DEVELOPMENT"
    COMPARE_WORK_MAPS = "COMPARE_WORK_MAPS"
    RECONSTRUCT_INTERLOCUTOR = "RECONSTRUCT_INTERLOCUTOR"
    ANALYZE_PRESSURE_FIELD = "ANALYZE_PRESSURE_FIELD"
    TRANSLATE = "TRANSLATE"
    SCHOLARLY_TRANSLATE = "SCHOLARLY_TRANSLATE"
    TRANSCRIBE_DIPLOMATIC = "TRANSCRIBE_DIPLOMATIC"
    NORMALIZE_LATIN = "NORMALIZE_LATIN"
    COMPARE_WITNESSES = "COMPARE_WITNESSES"
    IDENTIFY_WORK = "IDENTIFY_WORK"
    VERIFY_SOURCE = "VERIFY_SOURCE"
    BUILD_ARGUMENT_DOSSIER = "BUILD_ARGUMENT_DOSSIER"
    ASSESS_HISTORICAL_RELATION = "ASSESS_HISTORICAL_RELATION"
    TRACE_LINEAGE = "TRACE_LINEAGE"
    ANALYZE_SOURCE_TRANSMISSION = "ANALYZE_SOURCE_TRANSMISSION"
    ADJUDICATE_IMMEDIATE_SOURCE = "ADJUDICATE_IMMEDIATE_SOURCE"
    ANALYZE_RECEPTION = "ANALYZE_RECEPTION"
    COMPARE_CONCEPTS = "COMPARE_CONCEPTS"
    TRACE_CONFESSIONAL_LOCUS = "TRACE_CONFESSIONAL_LOCUS"
    COMPARE_CONFESSIONAL_FORMULATIONS = "COMPARE_CONFESSIONAL_FORMULATIONS"
    ANALYZE_RARE_BOOK = "ANALYZE_RARE_BOOK"
    ANALYZE_MARGINALIA = "ANALYZE_MARGINALIA"
    BUILD_PASTORAL_STUDY = "BUILD_PASTORAL_STUDY"
    RENDER_CITATION_READY = "RENDER_CITATION_READY"
    RECONSTRUCT_PAGE_ORDER = "RECONSTRUCT_PAGE_ORDER"
    BUILD_SCRIPTURE_APPARATUS = "BUILD_SCRIPTURE_APPARATUS"
    ANALYZE_ORIGINAL_LANGUAGE = "ANALYZE_ORIGINAL_LANGUAGE"
    SEARCH_CROSS_WORK = "SEARCH_CROSS_WORK"
    DETECT_LOCUS = "DETECT_LOCUS"
    ANALYZE_EXEGETICAL_METHOD = "ANALYZE_EXEGETICAL_METHOD"
    UPDATE_RESEARCH_STATE = "UPDATE_RESEARCH_STATE"


class Direction(str, Enum):
    NONE = "NONE"
    BACKWARD = "BACKWARD"
    FORWARD = "FORWARD"
    BIDIRECTIONAL = "BIDIRECTIONAL"


class EntityRole(str, Enum):
    CURRENT_WORK_CANDIDATE = "CURRENT_WORK_CANDIDATE"
    CURRENT_AUTHOR_CANDIDATE = "CURRENT_AUTHOR_CANDIDATE"
    HISTORICAL_AUTHORITY = "HISTORICAL_AUTHORITY"
    COMPARATOR_AUTHOR = "COMPARATOR_AUTHOR"
    SOURCE_CANDIDATE = "SOURCE_CANDIDATE"
    RECIPIENT = "RECIPIENT"
    CONFESSIONAL_DOCUMENT = "CONFESSIONAL_DOCUMENT"
    LOCUS = "LOCUS"
    EDITION_CANDIDATE = "EDITION_CANDIDATE"
    EXEMPLAR_CANDIDATE = "EXEMPLAR_CANDIDATE"


class AmbiguityState(str, Enum):
    RESOLVED = "RESOLVED"
    BOUNDED_INTERPRETATION = "BOUNDED_INTERPRETATION"
    REQUIRES_CLARIFICATION = "REQUIRES_CLARIFICATION"
    UNRESOLVED = "UNRESOLVED"


class ResearchDisposition(str, Enum):
    CURRENT_EVIDENCE_ONLY = "CURRENT_EVIDENCE_ONLY"
    EXTERNAL_RESEARCH_ALLOWED = "EXTERNAL_RESEARCH_ALLOWED"
    EXTERNAL_RESEARCH_REQUIRED = "EXTERNAL_RESEARCH_REQUIRED"
    EXTERNAL_RESEARCH_DECLINED = "EXTERNAL_RESEARCH_DECLINED"


class OutputDepth(str, Enum):
    MINIMAL = "MINIMAL"
    STANDARD = "STANDARD"
    DETAILED = "DETAILED"
    SCHOLARLY = "SCHOLARLY"


class AnchorKind(str, Enum):
    PAGE = "PAGE"
    PASSAGE = "PASSAGE"
    ARGUMENT = "ARGUMENT"
    DISTINCTION = "DISTINCTION"
    PROPOSITION = "PROPOSITION"
    LOCUS = "LOCUS"
    WORK = "WORK"
    SOURCE_QUESTION = "SOURCE_QUESTION"


SAFETY_GUARDS = (
    "ANTI_FABRICATION",
    "SOURCE_FORM_LICENSING",
    "UNCERTAINTY_PRESERVATION",
    "IDENTITY_SAFETY",
    "WORK_ISOLATION",
    "RELATION_CONFIDENCE_SEPARATION",
    "ROUTING_IS_NOT_EVIDENCE",
)


LINEAGE_OPERATIONS = frozenset({OperationID.TRACE_LINEAGE.value})
OPERATIONS_REQUIRING_ANCHOR = frozenset({
    item.value for item in OperationID
    if item not in {OperationID.UPDATE_RESEARCH_STATE, OperationID.ONBOARD_SPECIALIZATION}
})


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RoutingError(f"{label} must be non-empty text")
    return value.strip()


def _unique_sorted(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


@dataclass(frozen=True)
class NamedEntity:
    text: str
    role: EntityRole
    established: bool = False
    provenance: str = "request_text"

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "NamedEntity":
        text = _text(value.get("text"), "entity text")
        try:
            role = EntityRole(value.get("role"))
        except ValueError as exc:
            raise RoutingError("entity role must be declared") from exc
        established = value.get("established", False)
        if not isinstance(established, bool):
            raise RoutingError("entity established must be boolean")
        return cls(text, role, established, _text(value.get("provenance", "request_text"), "entity provenance"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "role": self.role.value,
            "established": self.established,
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class ContextAnchor:
    anchor_id: str
    kind: AnchorKind
    work_id: str | None = None
    label: str | None = None
    active: bool = True
    provenance: str = "conversation_state"

    def to_dict(self) -> dict[str, Any]:
        return {
            "anchor_id": self.anchor_id,
            "kind": self.kind.value,
            "work_id": self.work_id,
            "label": self.label,
            "active": self.active,
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class ConversationContext:
    current_work_id: str | None = None
    anchors: tuple[ContextAnchor, ...] = ()
    supplied_anchor: ContextAnchor | None = None

    def effective_anchors(self, kinds: Iterable[AnchorKind] | None = None) -> tuple[ContextAnchor, ...]:
        allowed = set(kinds) if kinds is not None else None
        candidates = [item for item in self.anchors if item.active]
        if self.supplied_anchor is not None:
            candidates.append(self.supplied_anchor)
        if self.current_work_id:
            candidates = [
                item for item in candidates
                if item.work_id in {None, self.current_work_id}
            ]
        if allowed is not None:
            candidates = [item for item in candidates if item.kind in allowed]
        deduped = {item.anchor_id: item for item in candidates}
        return tuple(deduped[key] for key in sorted(deduped))


@dataclass(frozen=True)
class PresentationModifiers:
    depth: OutputDepth = OutputDepth.STANDARD
    format: str = "prose"
    show_source_text: bool = False
    suppress_optional_commentary: bool = False
    citation_ready: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "depth": self.depth.value,
            "format": self.format,
            "show_source_text": self.show_source_text,
            "suppress_optional_commentary": self.suppress_optional_commentary,
            "citation_ready": self.citation_ready,
        }


@dataclass(frozen=True)
class ScopeModifiers:
    direction: Direction = Direction.NONE
    periods: tuple[str, ...] = ()
    document_subset: tuple[str, ...] = ()
    author_subset: tuple[str, ...] = ()
    unit_scope: str = "current_anchor"

    def to_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction.value,
            "periods": list(self.periods),
            "document_subset": list(self.document_subset),
            "author_subset": list(self.author_subset),
            "unit_scope": self.unit_scope,
        }


@dataclass(frozen=True)
class OperationStep:
    step_id: str
    operation: OperationID
    depends_on: tuple[str, ...] = ()
    anchor_id: str | None = None
    direction: Direction = Direction.NONE
    phase_owner: str = "v0.1"
    prerequisite_only: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "operation": self.operation.value,
            "depends_on": list(self.depends_on),
            "anchor_id": self.anchor_id,
            "direction": self.direction.value,
            "phase_owner": self.phase_owner,
            "prerequisite_only": self.prerequisite_only,
        }


@dataclass(frozen=True)
class RoutingPolicy:
    least_sufficient_operations: bool = True
    reuse_unique_context: bool = True
    clarification_only_when_material: bool = True
    deterministic_ordering: bool = True
    mandatory_safeguards: tuple[str, ...] = SAFETY_GUARDS

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None = None) -> "RoutingPolicy":
        if value is None:
            return cls()
        forbidden_true = {
            "disable_anti_fabrication",
            "disable_source_form_licensing",
            "disable_uncertainty",
            "promote_identity_from_mention",
            "treat_routing_as_evidence",
            "enable_phase12",
            "enable_phase13",
            "enable_phase14",
            "enable_work_specialization",
        }
        if any(value.get(key) is True for key in forbidden_true):
            raise RoutingError("routing policy cannot disable evidence safeguards or enable later phases")
        safeguards = tuple(value.get("mandatory_safeguards", SAFETY_GUARDS))
        if set(safeguards) != set(SAFETY_GUARDS):
            raise RoutingError("mandatory safeguards cannot be removed or replaced")
        return cls(
            bool(value.get("least_sufficient_operations", True)),
            bool(value.get("reuse_unique_context", True)),
            bool(value.get("clarification_only_when_material", True)),
            bool(value.get("deterministic_ordering", True)),
            tuple(SAFETY_GUARDS),
        )


@dataclass(frozen=True)
class StructuredIntentRecord:
    request_text: str
    primary_intent: IntentFamily
    secondary_intents: tuple[IntentFamily, ...]
    operations: tuple[OperationStep, ...]
    anchor_id: str | None
    entities: tuple[NamedEntity, ...]
    presentation: PresentationModifiers
    scope: ScopeModifiers
    research: ResearchDisposition
    negative_constraints: tuple[str, ...]
    ambiguity: AmbiguityState
    clarification_question: str | None
    unresolved_referents: tuple[str, ...]
    context_provenance: tuple[str, ...]
    audit_rationale: tuple[str, ...]
    safeguards: tuple[str, ...] = SAFETY_GUARDS
    schema_version: str = "1"

    def validate(self) -> None:
        _text(self.request_text, "request text")
        if set(self.safeguards) != set(SAFETY_GUARDS):
            raise RoutingError("operation plan omits mandatory safeguards")
        if self.ambiguity == AmbiguityState.REQUIRES_CLARIFICATION and not self.clarification_question:
            raise RoutingError("material ambiguity requires a clarification question")
        if self.clarification_question and "phase" in self.clarification_question.casefold():
            raise RoutingError("clarification must ask about the historical question, not an internal phase")
        step_ids = [item.step_id for item in self.operations]
        if len(step_ids) != len(set(step_ids)):
            raise RoutingError("duplicate operation step ID")
        known = set(step_ids)
        by_id = {item.step_id: item for item in self.operations}
        for step in self.operations:
            if any(dep not in known for dep in step.depends_on):
                raise RoutingError(f"operation {step.step_id} has missing dependency")
            if step.operation.value in OPERATIONS_REQUIRING_ANCHOR and not step.anchor_id:
                if self.ambiguity != AmbiguityState.REQUIRES_CLARIFICATION and not (
                    self.ambiguity == AmbiguityState.UNRESOLVED
                    and "research_discovery_required" in self.audit_rationale
                ):
                    raise RoutingError(f"operation {step.step_id} requires a resolved anchor")
            if step.operation.value in LINEAGE_OPERATIONS and step.direction == Direction.NONE:
                raise RoutingError("lineage operation requires direction")
            if step.operation.value not in LINEAGE_OPERATIONS and step.direction != Direction.NONE:
                raise RoutingError(f"direction is invalid for {step.operation.value}")
            if step.phase_owner in {"Phase12", "Phase13", "Phase14", "v0.3"}:
                raise RoutingError("later-phase operation is prohibited")
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(step_id: str) -> None:
            if step_id in visiting:
                raise RoutingError("operation dependencies must be acyclic")
            if step_id in visited:
                return
            visiting.add(step_id)
            for dep in by_id[step_id].depends_on:
                visit(dep)
            visiting.remove(step_id)
            visited.add(step_id)

        for step_id in step_ids:
            visit(step_id)
        positions = {step_id: index for index, step_id in enumerate(step_ids)}
        for step in self.operations:
            if any(positions[dep] >= positions[step.step_id] for dep in step.depends_on):
                raise RoutingError("operation sequence must place prerequisites first")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "request_text": self.request_text,
            "primary_intent": self.primary_intent.value,
            "secondary_intents": [item.value for item in self.secondary_intents],
            "operations": [item.to_dict() for item in self.operations],
            "anchor_id": self.anchor_id,
            "entities": [item.to_dict() for item in self.entities],
            "presentation": self.presentation.to_dict(),
            "scope": self.scope.to_dict(),
            "research": self.research.value,
            "negative_constraints": list(self.negative_constraints),
            "ambiguity": self.ambiguity.value,
            "clarification_question": self.clarification_question,
            "unresolved_referents": list(self.unresolved_referents),
            "context_provenance": list(self.context_provenance),
            "audit_rationale": list(self.audit_rationale),
            "safeguards": list(self.safeguards),
        }

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())

    def digest(self) -> str:
        return sha256_json(self.to_dict())


_CONFESSIONS = ("heidelberg", "belgic", "westminster", "scots confession", "helvetic", "dort")
_PERIODS = ("patristic", "medieval", "reformation", "early-modern", "modern", "contemporary")


def _contains_any(text: str, phrases: Sequence[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def _presentation(text: str) -> PresentationModifiers:
    depth = OutputDepth.STANDARD
    if _contains_any(text, ("briefly", "brief answer", "short answer")):
        depth = OutputDepth.MINIMAL
    if _contains_any(text, ("in detail", "detailed", "full apparatus")):
        depth = OutputDepth.DETAILED
    if _contains_any(text, ("scholar view", "scholarly")):
        depth = OutputDepth.SCHOLARLY
    fmt = "table" if re.search(r"\btable\b", text) else "prose"
    return PresentationModifiers(
        depth=depth,
        format=fmt,
        show_source_text=_contains_any(text, ("show the latin", "show me the latin", "show the greek", "show me the greek", "show the hebrew", "show me the hebrew", "show original")),
        suppress_optional_commentary=_contains_any(text, ("no commentary", "just the translation", "just translate")),
        citation_ready=_contains_any(text, ("citation-ready", "citation ready", "bibliographic note")),
    )


def _scope(text: str) -> ScopeModifiers:
    if _contains_any(text, ("backward and forward", "forwards and backwards", "both directions", "bidirectional")):
        direction = Direction.BIDIRECTIONAL
    elif _contains_any(text, ("afterward", "afterwards", "what happens later", "what happens to this later", "trace it forward", "trace this forward", "who takes this up", "later reception", "backward and forward")):
        direction = Direction.FORWARD
    elif _contains_any(text, ("where did", "come from", "antecedent", "backward", "trace backward", "drawing on", "earlier comparators")):
        direction = Direction.BACKWARD
    else:
        direction = Direction.NONE
    periods = _unique_sorted(item for item in _PERIODS if item in text)
    documents = _unique_sorted(item.title() for item in _CONFESSIONS if item in text)
    if "only this page" in text or "page only" in text:
        unit = "page"
    elif "this proposition" in text or "proposition only" in text:
        unit = "proposition"
    elif "this distinction" in text:
        unit = "distinction"
    elif "this locus" in text:
        unit = "locus"
    else:
        unit = "current_anchor"
    return ScopeModifiers(direction, periods, documents, (), unit)


def _negative_constraints(text: str) -> tuple[str, ...]:
    constraints: list[str] = []
    if _contains_any(text, ("don't research externally", "do not research externally", "no external research")):
        constraints.append("NO_EXTERNAL_RESEARCH")
    if _contains_any(text, ("don't make an influence claim", "do not make an influence claim", "without assuming influence", "no genealogy")):
        constraints.append("NO_GENEALOGY")
    if _contains_any(text, ("don't identify the work", "do not identify the work")):
        constraints.append("NO_IDENTITY_EXPANSION")
    if _contains_any(text, ("just tell me whether the wording differs", "wording only")):
        constraints.append("WORDING_ONLY")
    for flag, phrases in {
        'NO_ONBOARDING': ('no onboarding', 'without onboarding', 'do not add this book', 'do not recover my specialized library', "don't recover my specialized library", 'don’t recover my specialized library', 'never recover my specialized library'),
        'NO_ACCESS_NETWORK': ('no network analysis', 'without network analysis', 'do not construct network'),
        'NO_SENSITIVITY': ('no sensitivity analysis', 'without sensitivity analysis', 'do not run sensitivity'),
        'NO_NOVELTY': ('no novelty analysis', 'without novelty analysis', 'do not assess novelty', 'no originality analysis'),
        'NO_CARTOGRAPHY': ('no cartography', 'without cartography', 'do not produce cartography'),
        'NO_WHOLE_WORK_CARTOGRAPHY': ('no whole-work cartography', 'without whole-work cartography', 'do not produce whole-work cartography'),
        'NO_DEVELOPMENTAL_CARTOGRAPHY': ('no developmental cartography', 'without developmental cartography', 'do not produce developmental cartography'),
        'NO_COMPARATIVE_CARTOGRAPHY': ('no comparative cartography', 'without comparative cartography', 'do not produce comparative cartography'),
    }.items():
        if _contains_any(text, phrases): constraints.append(flag)
    return tuple(sorted(constraints))


def _candidate_intents(text: str) -> list[IntentFamily]:
    intents: list[IntentFamily] = []
    if _contains_any(text, ("i just acquired this book", "add this book to my specialized library", "add this repeatedly used work", "improve this specialization", "update this specialization", "onboard this book")) or re.search(r"\brecover my specialized library\b", text):
        intents.append(IntentFamily.SPECIALIZATION_ONBOARDING)
    translation = bool(re.search(r"\btranslate\b|\btranslation\b|what does (?:(?:this|the) page|this) say|give me the english", text))
    scholarly = _contains_any(text, ("scholar view", "textual uncertainties", "textual problems", "important variants", "show me the latin"))
    if translation:
        intents.append(IntentFamily.SCHOLARLY_TRANSLATION if scholarly else IntentFamily.SIMPLE_TRANSLATION)
    elif scholarly and _contains_any(text, ("show me the latin", "scholar view")):
        intents.append(IntentFamily.SCHOLARLY_TRANSLATION)
    if _contains_any(text, ("compare these two witnesses", "compare the witnesses", "compare these two readings", "collate", "witness comparison", "historical translation comparison")):
        intents.append(IntentFamily.TEXTUAL_WITNESS_ANALYSIS)
    if _contains_any(text, ("what book is this", "what work is this", "what page is this from", "identify this work", "which edition", "is this calvin", "is this luther", "is this aquinas")) and not translation:
        intents.append(IntentFamily.IDENTITY_INVESTIGATION)
    if _contains_any(text, ("identify and verify", "verify the citation", "identify this citation", "identify the citation", "source citation", "verify this source")):
        intents.append(IntentFamily.SOURCE_AUTHORITY_VERIFICATION)
    if _contains_any(text, ("what is this argument made of", "what is the argument", "break down", "premises and conclusion", "how does this argument work", "argument dossier", "proposition-relation graph", "tell me what the argument is", "reconstruct the argument")):
        intents.append(IntentFamily.ARGUMENT_RECONSTRUCTION)
    if _contains_any(text, ("does ", " inherit this", "influence", "copied this", "depends on", "direct quotation", "historical relation")) and _contains_any(text, ("inherit", "influence", "copied", "depends", "quotation", "historical relation")):
        intents.append(IntentFamily.HISTORICAL_RELATION)
    trace_lineage = _contains_any(text, ("trace this argument", "trace this distinction", "trace the distinction", "trace it backward", "trace that backward", "trace it forward", "where did this distinction come from", "trace the ancestry", "what are the antecedents", "start with ")) or bool(re.search(r"trace (?:this |the )?[a-z-]+ argument", text))
    # A named distinction in a bare question is an unresolved research target,
    # including the compact anchor-question wording used without a page.
    trace_lineage = trace_lineage or bool(re.search(r"\bwhere did (?:the|a) distinction\b.+\bcome from\b", text)) or (
        "anchor question:" in text and "distinction" in text and "earlier comparators" in text
    )
    if trace_lineage and "trace the letters" not in text:
        intents.append(IntentFamily.HISTORICAL_LINEAGE)
    if _contains_any(text, ("how did ", " reach this author", "reach him", "source-transmission profile", "could this have come through")) and not translation:
        intents.append(IntentFamily.SOURCE_TRANSMISSION)
    if _contains_any(text, ("immediate source", "actually consult", "direct or mediated", "real source or only the named authority", "exact immediate source")):
        intents.append(IntentFamily.IMMEDIATE_SOURCE_ADJUDICATION)
    if _contains_any(text, ("where did he get this from", "what about its sources", "what are its sources", "track down his source")):
        intents.append(IntentFamily.SOURCE_AUTHORITY_VERIFICATION)
    if _contains_any(text, ("what happened to this argument afterward", "what happens to this later", "who takes this up", "how does this change afterward", "reception profile", "later reception", "backward and forward")):
        intents.append(IntentFamily.RECEPTION_HISTORY)
    if _contains_any(text, ("same doctrine", "same concept", "same idea", "same thing in both authors", "term mean the same", "different terminology", "narrowed or broadened", "conceptual history", "compare these concepts", "compare the concepts")):
        intents.append(IntentFamily.CONCEPTUAL_HISTORY)
    if _contains_any(text, ("trace this locus through", "trace this through the confessions", "reformed confessions", "reformed standards", "locus trace")):
        intents.append(IntentFamily.CONFESSIONAL_LOCUS_TRACE)
    if _contains_any(text, ("compare heidelberg", "compare the confessional formulations", "confessional formulation", "contradiction or qualification", "compare this with westminster", "compare that with westminster")):
        intents.append(IntentFamily.CONFESSIONAL_FORMULATION_COMPARISON)
    if _contains_any(text, ("signatures and catchwords", "rare-book", "rare book", "physical evidence")):
        intents.append(IntentFamily.RARE_BOOK_ANALYSIS)
    if _contains_any(text, ("handwritten note", "marginalia", "marginal note")):
        intents.append(IntentFamily.MARGINALIA_ANALYSIS)
    if "pastoral study" in text:
        intents.append(IntentFamily.PASTORAL_STUDY)
    if _contains_any(text, ("citation-ready", "citation ready", "bibliographic note")):
        intents.append(IntentFamily.CITATION_READY_OUTPUT)
    if "diplomatic transcription" in text or "transcribe diplomatically" in text:
        intents.append(IntentFamily.DIPLOMATIC_TRANSCRIPTION)
    if "normalized latin" in text or "normalize the latin" in text:
        intents.append(IntentFamily.NORMALIZED_LATIN)
    if _contains_any(text, ("reconstruct page order", "page-order reconstruction", "page order")):
        intents.append(IntentFamily.PAGE_ORDER_RECONSTRUCTION)
    if _contains_any(text, ("scripture apparatus", "biblical apparatus")):
        intents.append(IntentFamily.SCRIPTURE_APPARATUS)
    if _contains_any(text, ("explain this hebrew word", "explain this greek word", "hebrew analysis", "greek analysis")):
        intents.append(IntentFamily.ORIGINAL_LANGUAGE_ANALYSIS)
    if _contains_any(text, ("search another work", "cross-work search", "other works by")):
        intents.append(IntentFamily.CROSS_WORK_SEARCH)
    if _contains_any(text, ("detect the locus", "detect the theological locus", "theological locus detection")):
        intents.append(IntentFamily.LOCUS_DETECTION)
    if _contains_any(text, ("exegetical method", "method of exegesis")):
        intents.append(IntentFamily.EXEGETICAL_METHOD)
    if _contains_any(text, ("research ledger", "research index", "persistent project state")):
        intents.append(IntentFamily.RESEARCH_STATE)
    if not intents and "same word" in text:
        intents.append(IntentFamily.ORIGINAL_LANGUAGE_ANALYSIS)
    if _contains_any(text, ("who is this argument responding to", "aimed at a particular theologian", "opponent behind", "interlocutor", "hidden controversy", "what controversy is behind")):
        intents.append(IntentFamily.INTERLOCUTOR_RECONSTRUCTION)
    if _contains_any(text, ("pressure field", "pressure-field", "what pressures", "why is he arguing this way here")):
        intents.append(IntentFamily.PRESSURE_FIELD_ANALYSIS)
    if _contains_any(text, ("whole-work", "whole work", "characteristic is this of the commentary", "central is this distinction", "patterns recur across this work")):
        intents.append(IntentFamily.WHOLE_WORK_CARTOGRAPHY)
    if _contains_any(text, ("developmental cartography", "treatment change across", "change across these securely dated works", "changes across securely dated works")):
        intents.append(IntentFamily.DEVELOPMENTAL_CARTOGRAPHY)
    if _contains_any(text, ("comparative cartography", "compare how these two authors", "compare these work maps", "compare how these authors structure")):
        intents.append(IntentFamily.COMPARATIVE_CARTOGRAPHY)
    if _contains_any(text, ("have had access", "could he access", "could this author access", "historical route could have carried", "owning this book", "access to this source", "access network", "book possession", "historical transmission infrastructure")):
        intents.append(IntentFamily.HISTORICAL_ACCESS_NETWORK)
    if _contains_any(text, ("dependence claim rely on this intermediary", "source attribution is wrong", "conclusions survive", "evidence is removed", "what changes if that source identification is wrong", "sensitivity testing", "sensitivity analysis", "what if the strongest passage", "what if the proposed intermediary", "what if the unusual phrase", "what if apparent independent corroboration")):
        intents.append(IntentFamily.HISTORICAL_SENSITIVITY)
    if _contains_any(text, ("actually unusual", "how rare is this", "found anything earlier", "wording unusual", "underlying idea unusual", "novelty detection", "novelty analysis")):
        intents.append(IntentFamily.NOVELTY_ANALYSIS)
    if _contains_any(text, ("strongest novelty claim", "originality adjudication", "is this original", "apparently novel", "earliest known occurrence")):
        intents.append(IntentFamily.ORIGINALITY_ADJUDICATION)
    if _contains_any(text, ("what did you search", "novelty ledger", "search before calling", "audit the novelty")):
        intents.append(IntentFamily.NOVELTY_LEDGER_AUDIT)
    return list(dict.fromkeys(intents))


def _anchor_kinds_for(intents: Sequence[IntentFamily]) -> tuple[AnchorKind, ...]:
    if any(item in intents for item in (IntentFamily.CONFESSIONAL_LOCUS_TRACE, IntentFamily.LOCUS_DETECTION)):
        return (AnchorKind.LOCUS, AnchorKind.PROPOSITION, AnchorKind.ARGUMENT)
    if any(item in intents for item in (IntentFamily.HISTORICAL_RELATION, IntentFamily.HISTORICAL_LINEAGE, IntentFamily.RECEPTION_HISTORY, IntentFamily.SOURCE_TRANSMISSION, IntentFamily.IMMEDIATE_SOURCE_ADJUDICATION)):
        return (AnchorKind.ARGUMENT, AnchorKind.DISTINCTION, AnchorKind.PROPOSITION, AnchorKind.SOURCE_QUESTION)
    if IntentFamily.ARGUMENT_RECONSTRUCTION in intents:
        return (AnchorKind.PASSAGE, AnchorKind.PAGE, AnchorKind.ARGUMENT)
    return tuple(AnchorKind)


def _resolve_anchor(
    text: str,
    intents: Sequence[IntentFamily],
    context: ConversationContext,
) -> tuple[str | None, AmbiguityState, str | None, tuple[str, ...], tuple[str, ...]]:
    candidates = context.effective_anchors(_anchor_kinds_for(intents))
    if context.supplied_anchor is not None:
        return context.supplied_anchor.anchor_id, AmbiguityState.RESOLVED, None, (), ("supplied_anchor",)
    anaphoric = bool(re.search(r"\b(this|that|it|its|his)\b", text))
    if len(candidates) == 1:
        return candidates[0].anchor_id, AmbiguityState.RESOLVED, None, (), ("unique_active_anchor",)
    if len(candidates) > 1 and anaphoric:
        noun = "argument or distinction" if any(item.kind in {AnchorKind.ARGUMENT, AnchorKind.DISTINCTION} for item in candidates) else "source"
        return None, AmbiguityState.REQUIRES_CLARIFICATION, f"Which active {noun} do you want me to use?", ("ambiguous_anaphor",), ("conversation_state",)
    if len(candidates) > 1:
        return None, AmbiguityState.REQUIRES_CLARIFICATION, "Which supplied source or argument should I use?", ("multiple_active_anchors",), ("conversation_state",)
    return None, AmbiguityState.UNRESOLVED, None, ("missing_anchor",), ("conversation_state",)


def _operation_for(intent: IntentFamily) -> OperationID:
    return {
        IntentFamily.SPECIALIZATION_ONBOARDING: OperationID.ONBOARD_SPECIALIZATION,
        IntentFamily.HISTORICAL_ACCESS_NETWORK: OperationID.ASSESS_ACCESS_NETWORK,
        IntentFamily.HISTORICAL_SENSITIVITY: OperationID.TEST_HISTORICAL_SENSITIVITY,
        IntentFamily.NOVELTY_ANALYSIS: OperationID.ASSESS_NOVELTY,
        IntentFamily.ORIGINALITY_ADJUDICATION: OperationID.ADJUDICATE_ORIGINALITY,
        IntentFamily.NOVELTY_LEDGER_AUDIT: OperationID.AUDIT_NOVELTY_LEDGER,
        IntentFamily.WHOLE_WORK_CARTOGRAPHY: OperationID.MAP_WHOLE_WORK,
        IntentFamily.DEVELOPMENTAL_CARTOGRAPHY: OperationID.MAP_DEVELOPMENT,
        IntentFamily.COMPARATIVE_CARTOGRAPHY: OperationID.COMPARE_WORK_MAPS,
        IntentFamily.INTERLOCUTOR_RECONSTRUCTION: OperationID.RECONSTRUCT_INTERLOCUTOR,
        IntentFamily.PRESSURE_FIELD_ANALYSIS: OperationID.ANALYZE_PRESSURE_FIELD,
        IntentFamily.SIMPLE_TRANSLATION: OperationID.TRANSLATE,
        IntentFamily.SCHOLARLY_TRANSLATION: OperationID.SCHOLARLY_TRANSLATE,
        IntentFamily.TEXTUAL_WITNESS_ANALYSIS: OperationID.COMPARE_WITNESSES,
        IntentFamily.IDENTITY_INVESTIGATION: OperationID.IDENTIFY_WORK,
        IntentFamily.SOURCE_AUTHORITY_VERIFICATION: OperationID.VERIFY_SOURCE,
        IntentFamily.ARGUMENT_RECONSTRUCTION: OperationID.BUILD_ARGUMENT_DOSSIER,
        IntentFamily.HISTORICAL_RELATION: OperationID.ASSESS_HISTORICAL_RELATION,
        IntentFamily.HISTORICAL_LINEAGE: OperationID.TRACE_LINEAGE,
        IntentFamily.SOURCE_TRANSMISSION: OperationID.ANALYZE_SOURCE_TRANSMISSION,
        IntentFamily.IMMEDIATE_SOURCE_ADJUDICATION: OperationID.ADJUDICATE_IMMEDIATE_SOURCE,
        IntentFamily.RECEPTION_HISTORY: OperationID.ANALYZE_RECEPTION,
        IntentFamily.CONCEPTUAL_HISTORY: OperationID.COMPARE_CONCEPTS,
        IntentFamily.CONFESSIONAL_LOCUS_TRACE: OperationID.TRACE_CONFESSIONAL_LOCUS,
        IntentFamily.CONFESSIONAL_FORMULATION_COMPARISON: OperationID.COMPARE_CONFESSIONAL_FORMULATIONS,
        IntentFamily.RARE_BOOK_ANALYSIS: OperationID.ANALYZE_RARE_BOOK,
        IntentFamily.MARGINALIA_ANALYSIS: OperationID.ANALYZE_MARGINALIA,
        IntentFamily.PASTORAL_STUDY: OperationID.BUILD_PASTORAL_STUDY,
        IntentFamily.CITATION_READY_OUTPUT: OperationID.RENDER_CITATION_READY,
        IntentFamily.DIPLOMATIC_TRANSCRIPTION: OperationID.TRANSCRIBE_DIPLOMATIC,
        IntentFamily.NORMALIZED_LATIN: OperationID.NORMALIZE_LATIN,
        IntentFamily.PAGE_ORDER_RECONSTRUCTION: OperationID.RECONSTRUCT_PAGE_ORDER,
        IntentFamily.SCRIPTURE_APPARATUS: OperationID.BUILD_SCRIPTURE_APPARATUS,
        IntentFamily.ORIGINAL_LANGUAGE_ANALYSIS: OperationID.ANALYZE_ORIGINAL_LANGUAGE,
        IntentFamily.CROSS_WORK_SEARCH: OperationID.SEARCH_CROSS_WORK,
        IntentFamily.LOCUS_DETECTION: OperationID.DETECT_LOCUS,
        IntentFamily.EXEGETICAL_METHOD: OperationID.ANALYZE_EXEGETICAL_METHOD,
        IntentFamily.RESEARCH_STATE: OperationID.UPDATE_RESEARCH_STATE,
    }[intent]


_PHASE_OWNER = {
    OperationID.ONBOARD_SPECIALIZATION: "v0.3-Stage12",
    OperationID.ASSESS_ACCESS_NETWORK: "v0.3-Stage11",
    OperationID.TEST_HISTORICAL_SENSITIVITY: "v0.3-Stage11",
    OperationID.ASSESS_NOVELTY: "v0.3-Stage10",
    OperationID.ADJUDICATE_ORIGINALITY: "v0.3-Stage10",
    OperationID.AUDIT_NOVELTY_LEDGER: "v0.3-Stage10",
    OperationID.MAP_WHOLE_WORK: "v0.3-Stage9",
    OperationID.MAP_DEVELOPMENT: "v0.3-Stage9",
    OperationID.COMPARE_WORK_MAPS: "v0.3-Stage9",
    OperationID.RECONSTRUCT_INTERLOCUTOR: "v0.3-Stage8",
    OperationID.ANALYZE_PRESSURE_FIELD: "v0.3-Stage8",
    OperationID.BUILD_ARGUMENT_DOSSIER: "Phase3",
    OperationID.ASSESS_HISTORICAL_RELATION: "Phase5",
    OperationID.TRACE_LINEAGE: "Phase6",
    OperationID.ANALYZE_SOURCE_TRANSMISSION: "Phase7",
    OperationID.ADJUDICATE_IMMEDIATE_SOURCE: "Phase7",
    OperationID.ANALYZE_RECEPTION: "Phase8",
    OperationID.COMPARE_CONCEPTS: "Phase8",
    OperationID.TRACE_CONFESSIONAL_LOCUS: "Phase9",
    OperationID.COMPARE_CONFESSIONAL_FORMULATIONS: "Phase9",
}


def _build_operations(
    intents: Sequence[IntentFamily],
    anchor_id: str | None,
    direction: Direction,
    ambiguity: AmbiguityState,
) -> tuple[OperationStep, ...]:
    requested = [item for item in intents if item != IntentFamily.COMPOSITE_REQUEST]
    operations: list[OperationID] = []
    for intent in requested:
        operation = _operation_for(intent)
        if operation not in operations:
            operations.append(operation)
    if OperationID.ANALYZE_SOURCE_TRANSMISSION in operations or OperationID.ADJUDICATE_IMMEDIATE_SOURCE in operations:
        if OperationID.ASSESS_HISTORICAL_RELATION not in operations:
            insertion = min(
                index for index, item in enumerate(operations)
                if item in {OperationID.ANALYZE_SOURCE_TRANSMISSION, OperationID.ADJUDICATE_IMMEDIATE_SOURCE}
            )
            operations.insert(insertion, OperationID.ASSESS_HISTORICAL_RELATION)
    if any(op in operations for op in (OperationID.ASSESS_ACCESS_NETWORK, OperationID.TEST_HISTORICAL_SENSITIVITY, OperationID.RECONSTRUCT_INTERLOCUTOR, OperationID.ANALYZE_PRESSURE_FIELD, OperationID.MAP_WHOLE_WORK, OperationID.MAP_DEVELOPMENT, OperationID.COMPARE_WORK_MAPS, OperationID.ASSESS_NOVELTY, OperationID.ADJUDICATE_ORIGINALITY, OperationID.AUDIT_NOVELTY_LEDGER)) and OperationID.BUILD_ARGUMENT_DOSSIER not in operations:
        operations.append(OperationID.BUILD_ARGUMENT_DOSSIER)
    priority = {item: index for index, item in enumerate((
        OperationID.TRANSLATE, OperationID.SCHOLARLY_TRANSLATE,
        OperationID.TRANSCRIBE_DIPLOMATIC, OperationID.NORMALIZE_LATIN,
        OperationID.COMPARE_WITNESSES, OperationID.IDENTIFY_WORK,
        OperationID.VERIFY_SOURCE, OperationID.BUILD_ARGUMENT_DOSSIER,
        OperationID.ASSESS_HISTORICAL_RELATION, OperationID.TRACE_LINEAGE,
        OperationID.ANALYZE_SOURCE_TRANSMISSION, OperationID.ADJUDICATE_IMMEDIATE_SOURCE,
        OperationID.ANALYZE_RECEPTION, OperationID.COMPARE_CONCEPTS,
        OperationID.DETECT_LOCUS, OperationID.TRACE_CONFESSIONAL_LOCUS,
        OperationID.COMPARE_CONFESSIONAL_FORMULATIONS, OperationID.ANALYZE_ORIGINAL_LANGUAGE,
        OperationID.RECONSTRUCT_PAGE_ORDER, OperationID.BUILD_SCRIPTURE_APPARATUS,
        OperationID.SEARCH_CROSS_WORK, OperationID.ANALYZE_EXEGETICAL_METHOD,
        OperationID.ANALYZE_RARE_BOOK, OperationID.ANALYZE_MARGINALIA,
        OperationID.BUILD_PASTORAL_STUDY, OperationID.RENDER_CITATION_READY,
        OperationID.UPDATE_RESEARCH_STATE, OperationID.ONBOARD_SPECIALIZATION,
        OperationID.RECONSTRUCT_INTERLOCUTOR, OperationID.ANALYZE_PRESSURE_FIELD,
        OperationID.MAP_WHOLE_WORK, OperationID.MAP_DEVELOPMENT, OperationID.COMPARE_WORK_MAPS,
        OperationID.ASSESS_NOVELTY, OperationID.ADJUDICATE_ORIGINALITY, OperationID.AUDIT_NOVELTY_LEDGER,
        OperationID.ASSESS_ACCESS_NETWORK, OperationID.TEST_HISTORICAL_SENSITIVITY,
    ))}
    operations.sort(key=lambda item: priority[item])
    step_id = {operation: f"op-{index + 1:02d}-{operation.value.casefold().replace('_', '-')}" for index, operation in enumerate(operations)}
    dependencies: dict[OperationID, list[OperationID]] = {item: [] for item in operations}
    translation_ops = [item for item in operations if item in {OperationID.TRANSLATE, OperationID.SCHOLARLY_TRANSLATE}]
    if OperationID.BUILD_ARGUMENT_DOSSIER in operations and translation_ops:
        dependencies[OperationID.BUILD_ARGUMENT_DOSSIER].append(translation_ops[0])
    for op in (OperationID.ASSESS_ACCESS_NETWORK, OperationID.TEST_HISTORICAL_SENSITIVITY, OperationID.RECONSTRUCT_INTERLOCUTOR, OperationID.ANALYZE_PRESSURE_FIELD, OperationID.MAP_WHOLE_WORK, OperationID.MAP_DEVELOPMENT, OperationID.COMPARE_WORK_MAPS, OperationID.ASSESS_NOVELTY, OperationID.ADJUDICATE_ORIGINALITY, OperationID.AUDIT_NOVELTY_LEDGER):
        if op in operations: dependencies[op].append(OperationID.BUILD_ARGUMENT_DOSSIER)
    if OperationID.TRACE_LINEAGE in operations and OperationID.BUILD_ARGUMENT_DOSSIER in operations:
        dependencies[OperationID.TRACE_LINEAGE].append(OperationID.BUILD_ARGUMENT_DOSSIER)
    if OperationID.ASSESS_HISTORICAL_RELATION in operations and OperationID.BUILD_ARGUMENT_DOSSIER in operations:
        dependencies[OperationID.ASSESS_HISTORICAL_RELATION].append(OperationID.BUILD_ARGUMENT_DOSSIER)
    if OperationID.ANALYZE_SOURCE_TRANSMISSION in operations:
        dependencies[OperationID.ANALYZE_SOURCE_TRANSMISSION].append(OperationID.ASSESS_HISTORICAL_RELATION)
    if OperationID.ADJUDICATE_IMMEDIATE_SOURCE in operations:
        prior = OperationID.ANALYZE_SOURCE_TRANSMISSION if OperationID.ANALYZE_SOURCE_TRANSMISSION in operations else OperationID.ASSESS_HISTORICAL_RELATION
        dependencies[OperationID.ADJUDICATE_IMMEDIATE_SOURCE].append(prior)
    if OperationID.TRACE_CONFESSIONAL_LOCUS in operations and OperationID.DETECT_LOCUS in operations:
        dependencies[OperationID.TRACE_CONFESSIONAL_LOCUS].append(OperationID.DETECT_LOCUS)
    if OperationID.RENDER_CITATION_READY in operations:
        dependencies[OperationID.RENDER_CITATION_READY].extend(item for item in operations if item != OperationID.RENDER_CITATION_READY)
    steps = []
    for operation in operations:
        step_direction = direction if operation == OperationID.TRACE_LINEAGE else Direction.NONE
        if operation == OperationID.TRACE_LINEAGE and step_direction == Direction.NONE:
            step_direction = Direction.BIDIRECTIONAL
        steps.append(OperationStep(
            step_id=step_id[operation],
            operation=operation,
            depends_on=tuple(step_id[item] for item in dependencies[operation]),
            anchor_id=anchor_id,
            direction=step_direction,
            phase_owner=_PHASE_OWNER.get(operation, "v0.1"),
            prerequisite_only=operation == OperationID.ASSESS_HISTORICAL_RELATION and all(
                _operation_for(item) != operation for item in requested
            ),
        ))
    from .composition import augment_steps
    return augment_steps(steps, anchor_id, direction, _PHASE_OWNER, OperationStep, OperationID, Direction)


def _research(text: str, intents: Sequence[IntentFamily], constraints: Sequence[str]) -> ResearchDisposition:
    if "NO_EXTERNAL_RESEARCH" in constraints:
        return ResearchDisposition.EXTERNAL_RESEARCH_DECLINED
    if _contains_any(text, ("scholar view",)):
        return ResearchDisposition.EXTERNAL_RESEARCH_ALLOWED
    if any(item in intents for item in (
        IntentFamily.SOURCE_AUTHORITY_VERIFICATION,
        IntentFamily.HISTORICAL_RELATION,
        IntentFamily.HISTORICAL_LINEAGE,
        IntentFamily.SOURCE_TRANSMISSION,
        IntentFamily.IMMEDIATE_SOURCE_ADJUDICATION,
        IntentFamily.CROSS_WORK_SEARCH,
        IntentFamily.INTERLOCUTOR_RECONSTRUCTION, IntentFamily.PRESSURE_FIELD_ANALYSIS,
        IntentFamily.WHOLE_WORK_CARTOGRAPHY, IntentFamily.DEVELOPMENTAL_CARTOGRAPHY, IntentFamily.COMPARATIVE_CARTOGRAPHY,
    )):
        return ResearchDisposition.EXTERNAL_RESEARCH_ALLOWED
    return ResearchDisposition.CURRENT_EVIDENCE_ONLY


def _infer_entities(text: str, supplied: Iterable[NamedEntity]) -> tuple[NamedEntity, ...]:
    entities = list(supplied)
    for name in _CONFESSIONS:
        if name in text:
            entities.append(NamedEntity(name.title(), EntityRole.CONFESSIONAL_DOCUMENT, False, "request_mention"))
    unique: dict[tuple[str, str], NamedEntity] = {}
    for item in entities:
        unique[(item.role.value, item.text.casefold())] = item
    return tuple(unique[key] for key in sorted(unique))


def route_request(
    request_text: str,
    *,
    context: ConversationContext | None = None,
    entities: Iterable[NamedEntity] = (),
    policy: RoutingPolicy | None = None,
) -> StructuredIntentRecord:
    """Interpret one request into a bounded, deterministic operation plan.

    Request grammar selects questions and operations only. All substantive
    claims remain subject to the accepted Phase 1-10 evidence architecture.
    """

    raw = _text(request_text, "request text")
    text = re.sub(r"\s+", " ", raw.casefold()).strip()
    context = context or ConversationContext()
    policy = policy or RoutingPolicy()
    if not policy.least_sufficient_operations:
        raise RoutingError("least-sufficient operation selection cannot be disabled")
    intents = _candidate_intents(text)
    if not intents:
        raise RoutingError("request intent is unresolved")
    scope = _scope(text)
    constraints = _negative_constraints(text)
    if "NO_GENEALOGY" in constraints:
        intents = [item for item in intents if item not in {
            IntentFamily.HISTORICAL_RELATION,
            IntentFamily.HISTORICAL_LINEAGE,
            IntentFamily.SOURCE_TRANSMISSION,
            IntentFamily.IMMEDIATE_SOURCE_ADJUDICATION,
        }]
    if "NO_ONBOARDING" in constraints:
        intents = [item for item in intents if item != IntentFamily.SPECIALIZATION_ONBOARDING]
    if "NO_ACCESS_NETWORK" in constraints:
        intents = [item for item in intents if item != IntentFamily.HISTORICAL_ACCESS_NETWORK]
    if "NO_SENSITIVITY" in constraints:
        intents = [item for item in intents if item != IntentFamily.HISTORICAL_SENSITIVITY]
    if "NO_NOVELTY" in constraints:
        intents = [item for item in intents if item not in {IntentFamily.NOVELTY_ANALYSIS, IntentFamily.ORIGINALITY_ADJUDICATION, IntentFamily.NOVELTY_LEDGER_AUDIT}]
    cartographic_constraints = {
        IntentFamily.WHOLE_WORK_CARTOGRAPHY: 'NO_WHOLE_WORK_CARTOGRAPHY',
        IntentFamily.DEVELOPMENTAL_CARTOGRAPHY: 'NO_DEVELOPMENTAL_CARTOGRAPHY',
        IntentFamily.COMPARATIVE_CARTOGRAPHY: 'NO_COMPARATIVE_CARTOGRAPHY',
    }
    intents = [item for item in intents if item not in cartographic_constraints or
               'NO_CARTOGRAPHY' not in constraints and cartographic_constraints[item] not in constraints]
    if not intents: raise RoutingError('requested operation was explicitly excluded')
    anchor_id, ambiguity, clarification, unresolved, provenance = _resolve_anchor(text, intents, context)
    presentation = _presentation(text)
    secondary = tuple(intents[1:])
    primary = intents[0]
    if len(intents) > 1:
        secondary = tuple(intents)
        primary = IntentFamily.COMPOSITE_REQUEST
    operations = _build_operations(intents, anchor_id, scope.direction, ambiguity)
    rationale = ["least_sufficient_operations"]
    # A self-contained historical question may start with a research target but
    # no supplied source. The operations remain pending until source discovery
    # produces validated representations; this control state is not evidence.
    if (ambiguity == AmbiguityState.UNRESOLVED and anchor_id is None
            and not re.search(r"\b(this|that|it|its|his)\b", text)
            and len(text.split()) >= 4):
        rationale.append("research_discovery_required")
    if primary == IntentFamily.COMPOSITE_REQUEST:
        rationale.append("dependency_ordered_composition")
    if ambiguity == AmbiguityState.REQUIRES_CLARIFICATION:
        rationale.append("material_referent_ambiguity")
    if any(token in text for token in ("copied", "influenced", "depends on", "direct quotation", "prove")):
        rationale.append("request_presupposition_not_adopted")
    record = StructuredIntentRecord(
        request_text=raw,
        primary_intent=primary,
        secondary_intents=secondary,
        operations=operations,
        anchor_id=anchor_id,
        entities=_infer_entities(text, entities),
        presentation=presentation,
        scope=scope,
        research=_research(text, intents, constraints),
        negative_constraints=constraints,
        ambiguity=ambiguity,
        clarification_question=clarification,
        unresolved_referents=unresolved,
        context_provenance=provenance,
        audit_rationale=tuple(rationale),
    )
    record.validate()
    return record


def validate_operation_plan(value: StructuredIntentRecord | Mapping[str, Any]) -> None:
    """Validate a typed plan or a deliberately minimal serialized plan.

    Mapping validation is strict enough for execution boundaries and is useful
    for rejecting unknown operation IDs, cycles, later phases, and safety
    disable attempts before an external caller constructs a typed record.
    """

    if isinstance(value, StructuredIntentRecord):
        value.validate()
        return
    if not isinstance(value, Mapping):
        raise RoutingError("operation plan must be a structured record")
    safeguards = tuple(value.get("safeguards", ()))
    if set(safeguards) != set(SAFETY_GUARDS):
        raise RoutingError("operation plan omits mandatory safeguards")
    raw_steps = value.get("operations")
    if not isinstance(raw_steps, list):
        raise RoutingError("operations must be an ordered list")
    steps: list[OperationStep] = []
    for item in raw_steps:
        if not isinstance(item, Mapping):
            raise RoutingError("operation step must be an object")
        try:
            operation = OperationID(item.get("operation"))
            direction = Direction(item.get("direction", "NONE"))
        except ValueError as exc:
            raise RoutingError("unknown operation or direction") from exc
        phase_owner = str(item.get("phase_owner", "v0.1"))
        steps.append(OperationStep(
            step_id=_text(item.get("step_id"), "step_id"),
            operation=operation,
            depends_on=tuple(item.get("depends_on", ())),
            anchor_id=item.get("anchor_id"),
            direction=direction,
            phase_owner=phase_owner,
        ))
    shadow = StructuredIntentRecord(
        request_text=str(value.get("request_text", "serialized plan")),
        primary_intent=IntentFamily.SIMPLE_TRANSLATION,
        secondary_intents=(), operations=tuple(steps),
        anchor_id=value.get("anchor_id"), entities=(),
        presentation=PresentationModifiers(), scope=ScopeModifiers(),
        research=ResearchDisposition.CURRENT_EVIDENCE_ONLY,
        negative_constraints=(), ambiguity=AmbiguityState.RESOLVED,
        clarification_question=None, unresolved_referents=(),
        context_provenance=("serialized_plan",), audit_rationale=("validation",),
        safeguards=safeguards,
    )
    shadow.validate()


def partial_completion(
    plan: StructuredIntentRecord,
    outcomes: Mapping[str, str],
) -> dict[str, Any]:
    """Serialize independent operation outcomes without masking unresolved work."""

    plan.validate()
    allowed = {item.step_id for item in plan.operations}
    if any(key not in allowed for key in outcomes):
        raise RoutingError("partial completion references an unknown operation")
    normalized = []
    for step in plan.operations:
        status = outcomes.get(step.step_id, "NOT_RUN")
        if status not in {"COMPLETED", "UNRESOLVED", "BLOCKED", "NOT_RUN"}:
            raise RoutingError("invalid partial-completion status")
        normalized.append({"step_id": step.step_id, "status": status})
    return {"plan_sha256": plan.digest(), "outcomes": normalized}
