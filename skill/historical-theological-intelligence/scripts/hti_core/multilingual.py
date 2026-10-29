"""Phase 10 multilingual hardening for the accepted HTI architecture.

This module preserves source form while attaching language, script,
normalization, translation, and comparison state to existing object references.
It does not create a multilingual genealogy graph, infer historical relations,
or treat translations and transliterations as original-language witnesses.
"""

from __future__ import annotations

import copy
import json
import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping

from .hashing import canonical_json, sha256_json
from .model import ValidationError
from .provenance import ProvenanceRecord


class MultilingualError(ValidationError):
    """Raised when multilingual state or licensing fails closed."""


class LanguageValidationStatus(str, Enum):
    VALIDATED_V02 = "VALIDATED_V02"
    BEST_EFFORT = "BEST_EFFORT"
    UNRESOLVED = "UNRESOLVED"


class LanguageIdentificationStatus(str, Enum):
    SUPPLIED = "SUPPLIED"
    VERIFIED = "VERIFIED"
    PROBABLE = "PROBABLE"
    UNRESOLVED = "UNRESOLVED"


class TextDirection(str, Enum):
    LTR = "LTR"
    RTL = "RTL"
    MIXED = "MIXED"


class RepresentationLanguageRole(str, Enum):
    ORIGINAL = "ORIGINAL"
    TRANSCRIPTION = "TRANSCRIPTION"
    OCR = "OCR"
    HISTORICAL_TRANSLATION = "HISTORICAL_TRANSLATION"
    MODERN_TRANSLATION = "MODERN_TRANSLATION"
    TRANSLITERATION = "TRANSLITERATION"
    MODERNIZATION = "MODERNIZATION"
    NORMALIZED_COMPARISON = "NORMALIZED_COMPARISON"


class TranslationEventRole(str, Enum):
    REPRESENTATION = "REPRESENTATION"
    HISTORICAL_EVENT = "HISTORICAL_EVENT"


class ClaimLicense(str, Enum):
    REPRESENTED_MEANING = "REPRESENTED_MEANING"
    ORIGINAL_WORDING = "ORIGINAL_WORDING"
    ORIGINAL_LEXICAL_IDENTITY = "ORIGINAL_LEXICAL_IDENTITY"
    ORIGINAL_SPELLING = "ORIGINAL_SPELLING"
    ORIGINAL_MORPHOLOGY = "ORIGINAL_MORPHOLOGY"
    QUOTATION_FORM = "QUOTATION_FORM"
    HISTORICAL_TRANSMISSION = "HISTORICAL_TRANSMISSION"


class ComparisonKind(str, Enum):
    SAME_LANGUAGE = "SAME_LANGUAGE"
    CROSS_LANGUAGE = "CROSS_LANGUAGE"


class RelationLicenseStatus(str, Enum):
    NOT_CLAIMED = "NOT_CLAIMED"
    WITHHELD = "WITHHELD"
    PHASE5_LICENSED = "PHASE5_LICENSED"
    UNRESOLVED = "UNRESOLVED"


VALIDATED_LANGUAGE_IDS = (
    "en", "la", "grc", "he", "de", "fr", "nl",
)

VALIDATED_LANGUAGE_NAMES = (
    "English", "Latin", "Greek", "Hebrew", "German", "French", "Dutch",
)

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_FORBIDDEN_POLICY_KEYS = frozenset({
    "translation_is_original", "transliteration_is_original",
    "normalization_establishes_identity", "language_transition_is_mediation",
    "same_language_is_dependence", "similarity_is_dependence",
    "modern_translation_is_historical_witness", "auto_promote_languages",
    "enable_phase11", "enable_phase12", "enable_work_specialization",
})


def _obj(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise MultilingualError(f"{label} must be an object")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MultilingualError(f"{label} must be non-empty text")
    return value


def _id(value: Any, label: str) -> str:
    result = _text(value, label).strip()
    if not _ID.fullmatch(result):
        raise MultilingualError(f"{label} must be a stable identifier")
    return result


def _enum(value: Any, kind: type[Enum], label: str) -> str:
    if not isinstance(value, str):
        raise MultilingualError(f"{label} must be a declared string value")
    try:
        kind(value)
    except ValueError as exc:
        raise MultilingualError(f"invalid {label} {value!r}") from exc
    return value


def _texts(value: Any, label: str, *, required: bool = False) -> tuple[str, ...]:
    if value is None:
        value = []
    if not isinstance(value, list):
        raise MultilingualError(f"{label} must be an ordered list")
    result = tuple(_text(item, f"{label} item") for item in value)
    if len(result) != len(set(result)):
        raise MultilingualError(f"{label} contains duplicates")
    if required and not result:
        raise MultilingualError(f"{label} must not be empty")
    return result


def _ids(value: Any, label: str, *, required: bool = False) -> tuple[str, ...]:
    return tuple(_id(item, f"{label} item") for item in _texts(value, label, required=required))


@dataclass(frozen=True)
class LanguageProfile:
    _raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, value: Any) -> "LanguageProfile":
        raw = _obj(value, "language profile")
        _id(raw.get("language_id"), "language_id")
        _text(raw.get("name"), "language name")
        _text(raw.get("canonical_tag"), "canonical language tag")
        _texts(raw.get("scripts"), "scripts", required=True)
        _enum(raw.get("direction"), TextDirection, "text direction")
        _enum(raw.get("validation_status"), LanguageValidationStatus, "validation status")
        _text(raw.get("normalization_policy"), "normalization policy")
        _text(raw.get("transliteration_policy"), "transliteration policy")
        _text(raw.get("verification_status"), "verification status")
        ProvenanceRecord.from_dict(raw.get("provenance"))
        return cls(copy.deepcopy(raw))

    @property
    def language_id(self) -> str:
        return str(self._raw["language_id"])

    @property
    def name(self) -> str:
        return str(self._raw["name"])

    @property
    def validation_status(self) -> str:
        return str(self._raw["validation_status"])

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class LanguageRegistry:
    schema_version: str
    profiles: tuple[LanguageProfile, ...]

    @classmethod
    def from_dict(cls, value: Any, *, require_locked_set: bool = True) -> "LanguageRegistry":
        raw = _obj(value, "language registry")
        if raw.get("schema_version") != "1":
            raise MultilingualError("language registry schema_version must be 1")
        profiles = tuple(LanguageProfile.from_dict(item) for item in raw.get("profiles", []))
        ids = [item.language_id for item in profiles]
        if len(ids) != len(set(ids)):
            raise MultilingualError("duplicate language identity")
        tags = [item.to_dict()["canonical_tag"].casefold() for item in profiles]
        if len(tags) != len(set(tags)):
            raise MultilingualError("duplicate canonical language tag")
        validated = tuple(sorted(
            item.language_id for item in profiles
            if item.validation_status == LanguageValidationStatus.VALIDATED_V02.value
        ))
        if require_locked_set and validated != tuple(sorted(VALIDATED_LANGUAGE_IDS)):
            raise MultilingualError("VALIDATED_V02 status must identify exactly the seven locked languages")
        return cls("1", tuple(sorted(profiles, key=lambda item: item.language_id)))

    @classmethod
    def load(cls, path: Path | None = None) -> "LanguageRegistry":
        if path is None:
            path = Path(__file__).resolve().parents[2] / "resources" / "languages" / "language-profiles.json"
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    @property
    def validated_ids(self) -> tuple[str, ...]:
        return tuple(item.language_id for item in self.profiles if item.validation_status == "VALIDATED_V02")

    def resolve(self, value: str) -> LanguageProfile:
        key = _text(value, "language lookup").casefold().strip()
        matches = [item for item in self.profiles if key in {
            item.language_id.casefold(), item.name.casefold(),
            str(item.to_dict()["canonical_tag"]).casefold(),
            *(alias.casefold() for alias in item.to_dict().get("aliases", [])),
        }]
        if len(matches) != 1:
            raise MultilingualError(f"language lookup must resolve uniquely: {value}")
        return matches[0]

    def with_extension(self, profile: LanguageProfile) -> "LanguageRegistry":
        if profile.validation_status == LanguageValidationStatus.VALIDATED_V02.value:
            raise MultilingualError("extension languages cannot acquire VALIDATED_V02 status")
        return LanguageRegistry.from_dict({
            "schema_version": "1",
            "profiles": [item.to_dict() for item in self.profiles] + [profile.to_dict()],
        })

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "profiles": [item.to_dict() for item in self.profiles]}

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())


@dataclass(frozen=True)
class LanguageSpan:
    span_id: str
    representation_id: str
    language_id: str
    script: str
    direction: str
    identification_status: str
    content: str
    locator: str
    evidence_root_ids: tuple[str, ...]
    provenance: Mapping[str, Any]
    uncertainty: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: Any, *, registry: LanguageRegistry) -> "LanguageSpan":
        raw = _obj(value, "language span")
        span_id = _id(raw.get("span_id"), "span_id")
        representation_id = _id(raw.get("representation_id"), "representation_id")
        language_id = registry.resolve(_text(raw.get("language_id"), "language_id")).language_id
        script = _text(raw.get("script"), "script")
        profile = registry.resolve(language_id)
        if script not in profile.to_dict()["scripts"]:
            raise MultilingualError(f"script {script!r} is not declared for {language_id}")
        direction = _enum(raw.get("direction"), TextDirection, "span direction")
        identification_status = _enum(
            raw.get("identification_status"), LanguageIdentificationStatus,
            "language identification status",
        )
        content = raw.get("content")
        if not isinstance(content, str):
            raise MultilingualError("span content must be text")
        locator = _text(raw.get("locator"), "span locator")
        roots = _ids(raw.get("evidence_root_ids"), "evidence_root_ids", required=True)
        provenance = copy.deepcopy(_obj(raw.get("provenance"), "span provenance"))
        ProvenanceRecord.from_dict(provenance)
        uncertainty = _texts(raw.get("uncertainty"), "span uncertainty")
        return cls(span_id, representation_id, language_id, script, direction,
                   identification_status, content, locator, roots, provenance, uncertainty)

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id, "representation_id": self.representation_id,
            "language_id": self.language_id, "script": self.script,
            "direction": self.direction, "identification_status": self.identification_status,
            "content": self.content, "locator": self.locator,
            "evidence_root_ids": list(self.evidence_root_ids),
            "provenance": copy.deepcopy(dict(self.provenance)),
            "uncertainty": list(self.uncertainty),
        }


@dataclass(frozen=True)
class MultilingualRepresentation:
    representation_id: str
    underlying_source_language_id: str
    representation_language_id: str
    role: str
    source_form: str
    parent_representation_ids: tuple[str, ...]
    evidence_root_ids: tuple[str, ...]
    original_script_inspected: bool
    original_text: str | None
    derivative_text: str | None
    uncertainty: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: Any, *, registry: LanguageRegistry) -> "MultilingualRepresentation":
        raw = _obj(value, "multilingual representation")
        representation_id = _id(raw.get("representation_id"), "representation_id")
        source_language = registry.resolve(_text(
            raw.get("underlying_source_language_id"), "underlying source language"
        )).language_id
        representation_language = registry.resolve(_text(
            raw.get("representation_language_id"), "representation language"
        )).language_id
        role = _enum(raw.get("role"), RepresentationLanguageRole, "representation language role")
        source_form = _text(raw.get("source_form"), "source form")
        parents = _ids(raw.get("parent_representation_ids"), "parent representation IDs")
        roots = _ids(raw.get("evidence_root_ids"), "evidence root IDs", required=True)
        inspected = raw.get("original_script_inspected")
        if not isinstance(inspected, bool):
            raise MultilingualError("original_script_inspected must be boolean")
        original_text = raw.get("original_text")
        derivative_text = raw.get("derivative_text")
        if original_text is not None and not isinstance(original_text, str):
            raise MultilingualError("original_text must be text")
        if derivative_text is not None and not isinstance(derivative_text, str):
            raise MultilingualError("derivative_text must be text")
        derivative_roles = {
            "TRANSCRIPTION", "OCR", "HISTORICAL_TRANSLATION", "MODERN_TRANSLATION",
            "TRANSLITERATION", "MODERNIZATION", "NORMALIZED_COMPARISON",
        }
        if role in derivative_roles and not parents:
            raise MultilingualError("derivative multilingual representation requires parent ancestry")
        if role == "ORIGINAL" and parents:
            raise MultilingualError("original multilingual representation cannot declare derivative parents")
        if role == "TRANSLITERATION" and source_language == representation_language:
            # The language is unchanged but the script representation is derivative.
            pass
        uncertainty = _texts(raw.get("uncertainty"), "representation uncertainty")
        return cls(representation_id, source_language, representation_language, role,
                   source_form, parents, roots, inspected, original_text,
                   derivative_text, uncertainty)

    def licenses(self, claim: ClaimLicense | str) -> bool:
        claim_value = claim.value if isinstance(claim, ClaimLicense) else ClaimLicense(claim).value
        if claim_value == ClaimLicense.REPRESENTED_MEANING.value:
            return self.role not in {"OCR", "TRANSLITERATION", "NORMALIZED_COMPARISON"}
        if claim_value in {
            ClaimLicense.ORIGINAL_WORDING.value, ClaimLicense.ORIGINAL_LEXICAL_IDENTITY.value,
            ClaimLicense.ORIGINAL_SPELLING.value, ClaimLicense.ORIGINAL_MORPHOLOGY.value,
            ClaimLicense.QUOTATION_FORM.value,
        }:
            return self.role == "ORIGINAL" and self.original_script_inspected and self.original_text is not None
        if claim_value == ClaimLicense.HISTORICAL_TRANSMISSION.value:
            return False
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "representation_id": self.representation_id,
            "underlying_source_language_id": self.underlying_source_language_id,
            "representation_language_id": self.representation_language_id,
            "role": self.role, "source_form": self.source_form,
            "parent_representation_ids": list(self.parent_representation_ids),
            "evidence_root_ids": list(self.evidence_root_ids),
            "original_script_inspected": self.original_script_inspected,
            "original_text": self.original_text, "derivative_text": self.derivative_text,
            "uncertainty": list(self.uncertainty),
        }


@dataclass(frozen=True)
class NormalizationRecord:
    normalization_id: str
    source_span_id: str
    original_text: str
    comparison_text: str
    unicode_form: str
    operations: tuple[str, ...]
    evidence_root_ids: tuple[str, ...]
    evidence_bearing_features_preserved: bool

    @classmethod
    def from_dict(cls, value: Any) -> "NormalizationRecord":
        raw = _obj(value, "normalization record")
        normalization_id = _id(raw.get("normalization_id"), "normalization_id")
        source_span_id = _id(raw.get("source_span_id"), "source_span_id")
        original_text = raw.get("original_text")
        comparison_text = raw.get("comparison_text")
        if not isinstance(original_text, str) or not isinstance(comparison_text, str):
            raise MultilingualError("normalization strings must be text")
        unicode_form = _text(raw.get("unicode_form"), "unicode form")
        if unicode_form not in {"NFC", "NFD", "NFKC", "NFKD", "NONE"}:
            raise MultilingualError("unsupported Unicode normalization form")
        operations = _texts(raw.get("operations"), "normalization operations")
        roots = _ids(raw.get("evidence_root_ids"), "normalization evidence roots", required=True)
        preserved = raw.get("evidence_bearing_features_preserved")
        if not isinstance(preserved, bool):
            raise MultilingualError("evidence_bearing_features_preserved must be boolean")
        return cls(normalization_id, source_span_id, original_text, comparison_text,
                   unicode_form, operations, roots, preserved)

    @classmethod
    def create(cls, *, normalization_id: str, source_span_id: str, original_text: str,
               evidence_root_ids: Iterable[str], unicode_form: str = "NFC",
               casefold: bool = False, operations: Iterable[str] = ()) -> "NormalizationRecord":
        comparison = original_text if unicode_form == "NONE" else unicodedata.normalize(unicode_form, original_text)
        recorded = list(operations)
        if unicode_form != "NONE":
            recorded.append(f"UNICODE_{unicode_form}")
        if casefold:
            comparison = comparison.casefold()
            recorded.append("CASEFOLD_CANDIDATE_ONLY")
        return cls.from_dict({
            "normalization_id": normalization_id, "source_span_id": source_span_id,
            "original_text": original_text, "comparison_text": comparison,
            "unicode_form": unicode_form, "operations": sorted(set(recorded)),
            "evidence_root_ids": sorted(set(evidence_root_ids)),
            "evidence_bearing_features_preserved": comparison == original_text,
        })

    def to_dict(self) -> dict[str, Any]:
        return {
            "normalization_id": self.normalization_id, "source_span_id": self.source_span_id,
            "original_text": self.original_text, "comparison_text": self.comparison_text,
            "unicode_form": self.unicode_form, "operations": list(self.operations),
            "evidence_root_ids": list(self.evidence_root_ids),
            "evidence_bearing_features_preserved": self.evidence_bearing_features_preserved,
        }


@dataclass(frozen=True)
class TranslationAlignment:
    alignment_id: str
    source_representation_id: str
    target_representation_id: str
    source_span_ids: tuple[str, ...]
    target_span_ids: tuple[str, ...]
    translator: str | None
    date: str | None
    roles: tuple[str, ...]
    omissions: tuple[str, ...]
    expansions: tuple[str, ...]
    mistranslations: tuple[str, ...]
    paraphrases: tuple[str, ...]
    unresolved: tuple[str, ...]
    evidence_root_ids: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: Any) -> "TranslationAlignment":
        raw = _obj(value, "translation alignment")
        alignment_id = _id(raw.get("alignment_id"), "alignment_id")
        source_id = _id(raw.get("source_representation_id"), "source representation ID")
        target_id = _id(raw.get("target_representation_id"), "target representation ID")
        if source_id == target_id:
            raise MultilingualError("translation alignment endpoints must differ")
        source_spans = _ids(raw.get("source_span_ids"), "source span IDs", required=True)
        target_spans = _ids(raw.get("target_span_ids"), "target span IDs", required=True)
        translator = raw.get("translator")
        date = raw.get("date")
        if translator is not None:
            translator = _text(translator, "translator")
        if date is not None:
            date = _text(date, "translation date")
        roles_raw = _texts(raw.get("roles"), "translation roles", required=True)
        roles = tuple(_enum(item, TranslationEventRole, "translation event role") for item in roles_raw)
        return cls(
            alignment_id, source_id, target_id, source_spans, target_spans,
            translator, date, tuple(sorted(roles)),
            _texts(raw.get("omissions"), "omissions"),
            _texts(raw.get("expansions"), "expansions"),
            _texts(raw.get("mistranslations"), "mistranslations"),
            _texts(raw.get("paraphrases"), "paraphrases"),
            _texts(raw.get("unresolved"), "unresolved alignment"),
            _ids(raw.get("evidence_root_ids"), "alignment evidence roots", required=True),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "alignment_id": self.alignment_id,
            "source_representation_id": self.source_representation_id,
            "target_representation_id": self.target_representation_id,
            "source_span_ids": list(self.source_span_ids), "target_span_ids": list(self.target_span_ids),
            "translator": self.translator, "date": self.date, "roles": list(self.roles),
            "omissions": list(self.omissions), "expansions": list(self.expansions),
            "mistranslations": list(self.mistranslations), "paraphrases": list(self.paraphrases),
            "unresolved": list(self.unresolved), "evidence_root_ids": list(self.evidence_root_ids),
        }


@dataclass(frozen=True)
class MultilingualComparison:
    comparison_id: str
    source_span_ids: tuple[str, ...]
    comparator_span_ids: tuple[str, ...]
    source_language_id: str
    comparator_language_id: str
    kind: str
    conceptual_correspondence: str
    lexical_correspondence: str
    divergences: tuple[str, ...]
    omissions: tuple[str, ...]
    expansions: tuple[str, ...]
    relation_status: str
    phase5_edge_ids: tuple[str, ...]
    phase7_investigation_ids: tuple[str, ...]
    phase8_analysis_ids: tuple[str, ...]
    phase9_comparison_ids: tuple[str, ...]
    evidence_root_ids: tuple[str, ...]
    uncertainty: tuple[str, ...]
    wording_claims_withheld: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: Any, *, registry: LanguageRegistry) -> "MultilingualComparison":
        raw = _obj(value, "multilingual comparison")
        comparison_id = _id(raw.get("comparison_id"), "comparison_id")
        source_spans = _ids(raw.get("source_span_ids"), "source span IDs", required=True)
        comparator_spans = _ids(raw.get("comparator_span_ids"), "comparator span IDs", required=True)
        source_language = registry.resolve(_text(raw.get("source_language_id"), "source language")).language_id
        comparator_language = registry.resolve(_text(raw.get("comparator_language_id"), "comparator language")).language_id
        kind = _enum(raw.get("kind"), ComparisonKind, "comparison kind")
        if kind == "SAME_LANGUAGE" and source_language != comparator_language:
            raise MultilingualError("same-language comparison requires matching language IDs")
        if kind == "CROSS_LANGUAGE" and source_language == comparator_language:
            raise MultilingualError("cross-language comparison requires distinct language IDs")
        relation_status = _enum(raw.get("relation_status"), RelationLicenseStatus, "relation status")
        phase5 = _ids(raw.get("phase5_edge_ids"), "Phase 5 edge IDs")
        if relation_status == "PHASE5_LICENSED" and not phase5:
            raise MultilingualError("licensed historical relation requires Phase 5 edge reference")
        if relation_status != "PHASE5_LICENSED" and phase5:
            raise MultilingualError("Phase 5 edge references require PHASE5_LICENSED status")
        return cls(
            comparison_id, source_spans, comparator_spans, source_language,
            comparator_language, kind,
            _text(raw.get("conceptual_correspondence"), "conceptual correspondence"),
            _text(raw.get("lexical_correspondence"), "lexical correspondence"),
            _texts(raw.get("divergences"), "divergences"),
            _texts(raw.get("omissions"), "omissions"),
            _texts(raw.get("expansions"), "expansions"), relation_status, phase5,
            _ids(raw.get("phase7_investigation_ids"), "Phase 7 investigation IDs"),
            _ids(raw.get("phase8_analysis_ids"), "Phase 8 analysis IDs"),
            _ids(raw.get("phase9_comparison_ids"), "Phase 9 comparison IDs"),
            _ids(raw.get("evidence_root_ids"), "comparison evidence roots", required=True),
            _texts(raw.get("uncertainty"), "comparison uncertainty"),
            _texts(raw.get("wording_claims_withheld"), "withheld wording claims"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "comparison_id": self.comparison_id,
            "source_span_ids": list(self.source_span_ids),
            "comparator_span_ids": list(self.comparator_span_ids),
            "source_language_id": self.source_language_id,
            "comparator_language_id": self.comparator_language_id,
            "kind": self.kind, "conceptual_correspondence": self.conceptual_correspondence,
            "lexical_correspondence": self.lexical_correspondence,
            "divergences": list(self.divergences), "omissions": list(self.omissions),
            "expansions": list(self.expansions), "relation_status": self.relation_status,
            "phase5_edge_ids": list(self.phase5_edge_ids),
            "phase7_investigation_ids": list(self.phase7_investigation_ids),
            "phase8_analysis_ids": list(self.phase8_analysis_ids),
            "phase9_comparison_ids": list(self.phase9_comparison_ids),
            "evidence_root_ids": list(self.evidence_root_ids),
            "uncertainty": list(self.uncertainty),
            "wording_claims_withheld": list(self.wording_claims_withheld),
        }


@dataclass(frozen=True)
class MultilingualPolicy:
    source_language_id: str
    representation_language_id: str
    permit_normalization: bool = True
    permit_transliteration: bool = True
    permit_cross_language_comparison: bool = True
    require_original_for_wording_claims: bool = True
    deterministic_ordering: bool = True

    @classmethod
    def from_dict(cls, value: Any, *, registry: LanguageRegistry) -> "MultilingualPolicy":
        raw = _obj(value, "multilingual policy")
        forbidden = sorted(key for key in raw if key in _FORBIDDEN_POLICY_KEYS and raw[key])
        if forbidden:
            raise MultilingualError(f"policy cannot disable multilingual safeguards: {forbidden}")
        source = registry.resolve(_text(raw.get("source_language_id"), "policy source language")).language_id
        representation = registry.resolve(_text(
            raw.get("representation_language_id"), "policy representation language"
        )).language_id
        values: dict[str, bool] = {}
        for key, default in {
            "permit_normalization": True, "permit_transliteration": True,
            "permit_cross_language_comparison": True,
            "require_original_for_wording_claims": True,
            "deterministic_ordering": True,
        }.items():
            item = raw.get(key, default)
            if not isinstance(item, bool):
                raise MultilingualError(f"{key} must be boolean")
            values[key] = item
        if not values["require_original_for_wording_claims"]:
            raise MultilingualError("caller policy cannot waive original-language wording licensing")
        if not values["deterministic_ordering"]:
            raise MultilingualError("caller policy cannot disable deterministic ordering")
        return cls(source, representation, **values)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_language_id": self.source_language_id,
            "representation_language_id": self.representation_language_id,
            "permit_normalization": self.permit_normalization,
            "permit_transliteration": self.permit_transliteration,
            "permit_cross_language_comparison": self.permit_cross_language_comparison,
            "require_original_for_wording_claims": self.require_original_for_wording_claims,
            "deterministic_ordering": self.deterministic_ordering,
        }


@dataclass(frozen=True)
class MultilingualAnalysis:
    analysis_id: str
    anchor_ref: str
    registry: LanguageRegistry
    policy: MultilingualPolicy
    representations: tuple[MultilingualRepresentation, ...]
    spans: tuple[LanguageSpan, ...]
    normalizations: tuple[NormalizationRecord, ...]
    translation_alignments: tuple[TranslationAlignment, ...]
    comparisons: tuple[MultilingualComparison, ...]
    unresolved_language_states: tuple[str, ...]
    research_gaps: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: Any, *, registry: LanguageRegistry | None = None) -> "MultilingualAnalysis":
        raw = _obj(value, "multilingual analysis")
        registry = registry or LanguageRegistry.load()
        analysis_id = _id(raw.get("analysis_id"), "analysis_id")
        anchor_ref = _id(raw.get("anchor_ref"), "anchor_ref")
        policy = MultilingualPolicy.from_dict(raw.get("policy"), registry=registry)
        representations = tuple(sorted(
            (MultilingualRepresentation.from_dict(item, registry=registry)
             for item in raw.get("representations", [])),
            key=lambda item: item.representation_id,
        ))
        if not representations:
            raise MultilingualError("multilingual analysis requires representations")
        rep_ids = {item.representation_id for item in representations}
        for item in representations:
            missing = set(item.parent_representation_ids) - rep_ids
            if missing:
                raise MultilingualError(f"representation ancestry references missing parents: {sorted(missing)}")
        spans = tuple(sorted(
            (LanguageSpan.from_dict(item, registry=registry) for item in raw.get("spans", [])),
            key=lambda item: item.span_id,
        ))
        if not spans:
            raise MultilingualError("multilingual analysis requires language spans")
        span_ids = {item.span_id for item in spans}
        if len(span_ids) != len(spans):
            raise MultilingualError("duplicate language span IDs")
        if any(item.representation_id not in rep_ids for item in spans):
            raise MultilingualError("language span references missing representation")
        normalizations = tuple(sorted(
            (NormalizationRecord.from_dict(item) for item in raw.get("normalizations", [])),
            key=lambda item: item.normalization_id,
        ))
        if any(item.source_span_id not in span_ids for item in normalizations):
            raise MultilingualError("normalization references missing source span")
        alignments = tuple(sorted(
            (TranslationAlignment.from_dict(item) for item in raw.get("translation_alignments", [])),
            key=lambda item: item.alignment_id,
        ))
        for item in alignments:
            if item.source_representation_id not in rep_ids or item.target_representation_id not in rep_ids:
                raise MultilingualError("translation alignment references missing representation")
            if not set(item.source_span_ids + item.target_span_ids) <= span_ids:
                raise MultilingualError("translation alignment references missing span")
        comparisons = tuple(sorted(
            (MultilingualComparison.from_dict(item, registry=registry)
             for item in raw.get("comparisons", [])),
            key=lambda item: item.comparison_id,
        ))
        for item in comparisons:
            if not set(item.source_span_ids + item.comparator_span_ids) <= span_ids:
                raise MultilingualError("comparison references missing span")
            if item.kind == "CROSS_LANGUAGE" and not policy.permit_cross_language_comparison:
                raise MultilingualError("policy does not permit cross-language comparison")
        return cls(
            analysis_id, anchor_ref, registry, policy, representations, spans,
            normalizations, alignments, comparisons,
            tuple(sorted(_texts(raw.get("unresolved_language_states"), "unresolved language states"))),
            tuple(sorted(_texts(raw.get("research_gaps"), "research gaps"))),
        )

    def evidence_root_count(self) -> int:
        roots: set[str] = set()
        for item in self.representations:
            roots.update(item.evidence_root_ids)
        for item in self.spans:
            roots.update(item.evidence_root_ids)
        for item in self.translation_alignments:
            roots.update(item.evidence_root_ids)
        for item in self.comparisons:
            roots.update(item.evidence_root_ids)
        return len(roots)

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_id": self.analysis_id, "anchor_ref": self.anchor_ref,
            "validated_language_ids": list(self.registry.validated_ids),
            "policy": self.policy.to_dict(),
            "representations": [item.to_dict() for item in self.representations],
            "spans": [item.to_dict() for item in self.spans],
            "normalizations": [item.to_dict() for item in self.normalizations],
            "translation_alignments": [item.to_dict() for item in self.translation_alignments],
            "comparisons": [item.to_dict() for item in self.comparisons],
            "unresolved_language_states": list(self.unresolved_language_states),
            "research_gaps": list(self.research_gaps),
        }

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())

    def digest(self) -> str:
        return sha256_json(self.to_dict())


def construct_multilingual_analysis(value: Any, *, registry: LanguageRegistry | None = None) -> MultilingualAnalysis:
    """Validate and construct deterministic Phase 10 state without mutating upstream objects."""
    return MultilingualAnalysis.from_dict(value, registry=registry)


def validate_claim_license(representation: MultilingualRepresentation, claim: ClaimLicense | str) -> None:
    """Fail closed when derivative source form cannot license an original-language claim."""
    if not representation.licenses(claim):
        claim_value = claim.value if isinstance(claim, ClaimLicense) else str(claim)
        raise MultilingualError(
            f"{representation.representation_id} does not license {claim_value}"
        )

