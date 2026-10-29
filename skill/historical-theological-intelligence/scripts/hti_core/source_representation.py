"""Universal source representations with fail-closed claim licensing.

This module models only source form, representation ancestry, and the claims a
representation can directly license. It does not model arguments, intellectual
genealogy, historical relations, or dependency-sensitive uncertainty.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

from .audit import AuditFinding, AuditResult
from .hashing import canonical_json, sha256_json
from .model import EVIDENCE_STATES, ValidationError
from .provenance import EvidenceRoot, ProvenanceRecord
from .source_identity import SourceIdentity
from .uncertainty import UncertaintyAssessment


class RepresentationType(str, Enum):
    PAGE_IMAGE = "PAGE_IMAGE"
    ORIGINAL_TEXT = "ORIGINAL_TEXT"
    TRANSCRIPTION = "TRANSCRIPTION"
    OCR = "OCR"
    HISTORICAL_TRANSLATION = "HISTORICAL_TRANSLATION"
    MODERN_TRANSLATION = "MODERN_TRANSLATION"
    SCHOLARLY_EDITION = "SCHOLARLY_EDITION"
    PASTED_QUOTATION = "PASTED_QUOTATION"
    PRIOR_V01_TRANSLATION = "PRIOR_V01_TRANSLATION"
    SECONDARY_QUOTATION = "SECONDARY_QUOTATION"


REPRESENTATION_TYPES = frozenset(item.value for item in RepresentationType)


class SupplyStatus(str, Enum):
    """Whether the representation entered this analysis supplied or derived."""

    SUPPLIED = "SUPPLIED"
    DERIVED = "DERIVED"


class RepresentationVerification(str, Enum):
    """Verification of this representation, not verification of its source."""

    UNVERIFIED = "UNVERIFIED"
    INSPECTED = "INSPECTED"
    VERIFIED = "VERIFIED"
    LOCATOR_ONLY = "LOCATOR_ONLY"


class DerivationKind(str, Enum):
    DERIVED_FROM = "DERIVED_FROM"
    IMAGE_DERIVED_FROM = "IMAGE_DERIVED_FROM"
    TRANSCRIBED_FROM = "TRANSCRIBED_FROM"
    OCR_FROM = "OCR_FROM"
    TRANSLATED_FROM = "TRANSLATED_FROM"
    EDITED_FROM = "EDITED_FROM"
    QUOTED_FROM = "QUOTED_FROM"
    V01_TRANSLATED_FROM = "V01_TRANSLATED_FROM"


class HistoricalTranslationRole(str, Enum):
    """Dual roles without creating intellectual-historical graph edges."""

    MEDIATED_REPRESENTATION = "MEDIATED_REPRESENTATION"
    HISTORICAL_EVENT = "HISTORICAL_EVENT"


class RepresentationClaim(str, Enum):
    REPRESENTED_ARGUMENT = "REPRESENTED_ARGUMENT"
    VISIBLE_PAGE_CONTENT = "VISIBLE_PAGE_CONTENT"
    TRANSCRIBED_WORDING = "TRANSCRIBED_WORDING"
    OCR_LOCATOR = "OCR_LOCATOR"
    PROVISIONAL_TEXT = "PROVISIONAL_TEXT"
    HISTORICAL_EVENT_STATUS = "HISTORICAL_EVENT_STATUS"
    EDITION_TEXT = "EDITION_TEXT"
    EDITION_APPARATUS = "EDITION_APPARATUS"
    SUPPLIED_QUOTED_TEXT = "SUPPLIED_QUOTED_TEXT"
    SECONDARY_REPORT = "SECONDARY_REPORT"
    EXACT_ORIGINAL_WORDING = "EXACT_ORIGINAL_WORDING"
    EXACT_ORIGINAL_SPELLING = "EXACT_ORIGINAL_SPELLING"
    SOURCE_LANGUAGE_LEXICAL_IDENTITY = "SOURCE_LANGUAGE_LEXICAL_IDENTITY"
    EXACT_GLYPH_IDENTITY = "EXACT_GLYPH_IDENTITY"
    PAGE_LAYOUT = "PAGE_LAYOUT"
    PHYSICAL_CONDITION = "PHYSICAL_CONDITION"
    QUOTATION_FORM = "QUOTATION_FORM"
    DIRECT_TEXTUAL_DEPENDENCE = "DIRECT_TEXTUAL_DEPENDENCE"
    EXEMPLAR_IDENTITY = "EXEMPLAR_IDENTITY"
    PROVENANCE_IDENTITY = "PROVENANCE_IDENTITY"


class LicenseStatus(str, Enum):
    ALLOWED = "ALLOWED"
    CONDITIONAL = "CONDITIONAL"
    DENIED = "DENIED"


class RepresentationLicenseError(ValidationError):
    """Raised when a caller requires a claim that is not directly licensed."""


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{label} must be a non-empty string")
    return value


def _enum_value(value: Any, enum_type: type[Enum], label: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{label} must be a declared string value")
    try:
        enum_type(value)
    except ValueError as exc:
        raise ValidationError(f"invalid {label} {value!r}") from exc
    return value


@dataclass(frozen=True)
class RepresentationDerivation:
    """One typed parent link with lossless opaque extension retention."""

    _raw: Mapping[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, value: Any) -> "RepresentationDerivation":
        if not isinstance(value, dict):
            raise ValidationError("representation derivation must be an object")
        _nonempty(value.get("parent_representation_id"), "parent_representation_id")
        _enum_value(value.get("relation"), DerivationKind, "derivation relation")
        provenance = value.get("provenance")
        if provenance is not None:
            ProvenanceRecord.from_dict(provenance)
        return cls(copy.deepcopy(value))

    @property
    def parent_representation_id(self) -> str:
        return str(self._raw["parent_representation_id"])

    @property
    def relation(self) -> str:
        return str(self._raw["relation"])

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class SourceRepresentation:
    """Lossless typed representation whose permissions are policy-derived."""

    _raw: Mapping[str, Any] = field(repr=False)
    derivations: tuple[RepresentationDerivation, ...] = field(repr=False)

    @classmethod
    def from_dict(cls, value: Any) -> "SourceRepresentation":
        if not isinstance(value, dict):
            raise ValidationError("source representation must be an object")
        representation_id = _nonempty(value.get("representation_id"), "representation_id")
        representation_type = _enum_value(
            value.get("representation_type"), RepresentationType, "representation_type"
        )
        supply_status = _enum_value(
            value.get("supply_status"), SupplyStatus, "supply_status"
        )
        verification = _enum_value(
            value.get("verification"), RepresentationVerification, "representation verification"
        )
        language = value.get("language")
        if language is not None:
            _nonempty(language, "language")
        content = value.get("content")
        if content is not None and not isinstance(content, str):
            raise ValidationError("representation content must be text when supplied")
        provenance = value.get("provenance")
        if provenance is None:
            raise ValidationError(f"{representation_id} requires provenance")
        ProvenanceRecord.from_dict(provenance)
        source_identity = value.get("source_identity")
        if source_identity is not None:
            SourceIdentity.from_dict(source_identity)
        evidence_root_id = value.get("evidence_root_id")
        if evidence_root_id is not None:
            _nonempty(evidence_root_id, "evidence_root_id")
        evidence_state = value.get("evidence_state")
        if evidence_state is not None and evidence_state not in EVIDENCE_STATES:
            raise ValidationError(f"invalid representation evidence_state {evidence_state!r}")
        uncertainty = value.get("uncertainty")
        if uncertainty is not None:
            UncertaintyAssessment.from_dict(uncertainty)
        apparatus_present = value.get("apparatus_present")
        if apparatus_present is not None and not isinstance(apparatus_present, bool):
            raise ValidationError("apparatus_present must be boolean")

        raw_derivations = value.get("derivations", [])
        if not isinstance(raw_derivations, list):
            raise ValidationError("representation derivations must be an ordered list")
        derivations = tuple(RepresentationDerivation.from_dict(item) for item in raw_derivations)
        if supply_status == SupplyStatus.DERIVED.value and not derivations:
            raise ValidationError("derived representation requires at least one parent")
        if supply_status == SupplyStatus.SUPPLIED.value and derivations:
            raise ValidationError("supplied representation cannot declare current-workflow parents")
        if any(item.parent_representation_id == representation_id for item in derivations):
            raise ValidationError("representation cannot derive from itself")
        if verification == RepresentationVerification.LOCATOR_ONLY.value and (
            representation_type != RepresentationType.OCR.value
        ):
            raise ValidationError("LOCATOR_ONLY verification is reserved for OCR")

        raw_roles = value.get("historical_translation_roles", [])
        if not isinstance(raw_roles, list):
            raise ValidationError("historical_translation_roles must be an ordered list")
        roles: list[str] = []
        for role in raw_roles:
            roles.append(_enum_value(role, HistoricalTranslationRole, "historical translation role"))
        if len(roles) != len(set(roles)):
            raise ValidationError("historical_translation_roles must not contain duplicates")
        if representation_type == RepresentationType.HISTORICAL_TRANSLATION.value:
            if HistoricalTranslationRole.MEDIATED_REPRESENTATION.value not in roles:
                raise ValidationError(
                    "historical translation must retain its mediated-representation role"
                )
        elif roles:
            raise ValidationError(
                "historical_translation_roles are valid only for historical translations"
            )
        return cls(copy.deepcopy(value), derivations)

    @property
    def representation_id(self) -> str:
        return str(self._raw["representation_id"])

    @property
    def representation_type(self) -> str:
        return str(self._raw["representation_type"])

    @property
    def supply_status(self) -> str:
        return str(self._raw["supply_status"])

    @property
    def verification(self) -> str:
        return str(self._raw["verification"])

    @property
    def language(self) -> str | None:
        value = self._raw.get("language")
        return str(value) if value is not None else None

    @property
    def content(self) -> str | None:
        value = self._raw.get("content")
        return str(value) if value is not None else None

    @property
    def source_identity(self) -> SourceIdentity | None:
        value = self._raw.get("source_identity")
        return SourceIdentity.from_dict(value) if value is not None else None

    @property
    def provenance(self) -> ProvenanceRecord:
        return ProvenanceRecord.from_dict(self._raw["provenance"])

    @property
    def uncertainty(self) -> UncertaintyAssessment | None:
        value = self._raw.get("uncertainty")
        return UncertaintyAssessment.from_dict(value) if value is not None else None

    @property
    def evidence_state(self) -> str | None:
        value = self._raw.get("evidence_state")
        return str(value) if value is not None else None

    @property
    def evidence_root_id(self) -> str:
        value = self._raw.get("evidence_root_id")
        return str(value) if value is not None else self.representation_id

    @property
    def historical_translation_roles(self) -> tuple[str, ...]:
        return tuple(self._raw.get("historical_translation_roles", []))

    @property
    def apparatus_present(self) -> bool:
        return self._raw.get("apparatus_present") is True

    def evidence_root(self) -> EvidenceRoot:
        identity = self.source_identity
        return EvidenceRoot(
            self.evidence_root_id,
            source_id=identity.source_id if identity is not None else None,
            work_id=identity.work_id if identity is not None else None,
        )

    def licensing_profile(self) -> dict[str, dict[str, Any]]:
        """Return every direct permission decision in stable claim-value order."""

        return {
            claim.value: assess_direct_license(self, claim).to_dict()
            for claim in RepresentationClaim
        }

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))


@dataclass(frozen=True)
class LicenseDecision:
    """Auditable direct-permission decision for one representation and claim."""

    representation_id: str
    representation_type: str
    claim: str
    status: str
    code: str
    explanation: str
    conditions: tuple[str, ...] = ()
    uncertainty: Mapping[str, Any] | None = field(default=None, repr=False)

    @property
    def licensed(self) -> bool:
        return self.status == LicenseStatus.ALLOWED.value

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "representation_id": self.representation_id,
            "representation_type": self.representation_type,
            "claim": self.claim,
            "status": self.status,
            "code": self.code,
            "explanation": self.explanation,
            "conditions": list(self.conditions),
        }
        if self.uncertainty is not None:
            value["uncertainty"] = copy.deepcopy(dict(self.uncertainty))
        return value


def _decision(
    representation: SourceRepresentation,
    claim: RepresentationClaim,
    status: LicenseStatus,
    code: str,
    explanation: str,
    *conditions: str,
) -> LicenseDecision:
    uncertainty = representation.uncertainty
    return LicenseDecision(
        representation.representation_id,
        representation.representation_type,
        claim.value,
        status.value,
        code,
        explanation,
        tuple(conditions),
        uncertainty.to_dict() if uncertainty is not None else None,
    )


_TEXT_BEARING = frozenset(
    {
        RepresentationType.ORIGINAL_TEXT.value,
        RepresentationType.TRANSCRIPTION.value,
        RepresentationType.OCR.value,
        RepresentationType.HISTORICAL_TRANSLATION.value,
        RepresentationType.MODERN_TRANSLATION.value,
        RepresentationType.SCHOLARLY_EDITION.value,
        RepresentationType.PASTED_QUOTATION.value,
        RepresentationType.PRIOR_V01_TRANSLATION.value,
        RepresentationType.SECONDARY_QUOTATION.value,
    }
)

_ORIGINAL_LANGUAGE_CARRIERS = frozenset(
    {
        RepresentationType.PAGE_IMAGE.value,
        RepresentationType.ORIGINAL_TEXT.value,
        RepresentationType.TRANSCRIPTION.value,
        RepresentationType.SCHOLARLY_EDITION.value,
    }
)

_TRANSLATIONS = frozenset(
    {
        RepresentationType.HISTORICAL_TRANSLATION.value,
        RepresentationType.MODERN_TRANSLATION.value,
        RepresentationType.PRIOR_V01_TRANSLATION.value,
    }
)

_DERIVATION_RULES = {
    RepresentationType.PAGE_IMAGE.value: frozenset(
        {DerivationKind.IMAGE_DERIVED_FROM.value, DerivationKind.DERIVED_FROM.value}
    ),
    RepresentationType.ORIGINAL_TEXT.value: frozenset(
        {DerivationKind.DERIVED_FROM.value}
    ),
    RepresentationType.TRANSCRIPTION.value: frozenset(
        {DerivationKind.TRANSCRIBED_FROM.value}
    ),
    RepresentationType.OCR.value: frozenset({DerivationKind.OCR_FROM.value}),
    RepresentationType.HISTORICAL_TRANSLATION.value: frozenset(
        {DerivationKind.TRANSLATED_FROM.value}
    ),
    RepresentationType.MODERN_TRANSLATION.value: frozenset(
        {DerivationKind.TRANSLATED_FROM.value}
    ),
    RepresentationType.SCHOLARLY_EDITION.value: frozenset(
        {DerivationKind.EDITED_FROM.value, DerivationKind.DERIVED_FROM.value}
    ),
    RepresentationType.PASTED_QUOTATION.value: frozenset(
        {DerivationKind.QUOTED_FROM.value}
    ),
    RepresentationType.PRIOR_V01_TRANSLATION.value: frozenset(
        {
            DerivationKind.V01_TRANSLATED_FROM.value,
            DerivationKind.TRANSLATED_FROM.value,
        }
    ),
    RepresentationType.SECONDARY_QUOTATION.value: frozenset(
        {DerivationKind.QUOTED_FROM.value}
    ),
}


def assess_direct_license(
    representation: SourceRepresentation,
    claim: RepresentationClaim | str,
) -> LicenseDecision:
    """Compute direct permission without caller-supplied promotion switches."""

    if not isinstance(representation, SourceRepresentation):
        raise ValidationError("direct licensing requires SourceRepresentation")
    try:
        claim_value = claim if isinstance(claim, RepresentationClaim) else RepresentationClaim(claim)
    except ValueError as exc:
        raise ValidationError(f"invalid representation claim {claim!r}") from exc
    kind = representation.representation_type
    has_content = bool(representation.content)

    if claim_value in {
        RepresentationClaim.DIRECT_TEXTUAL_DEPENDENCE,
        RepresentationClaim.EXEMPLAR_IDENTITY,
        RepresentationClaim.PROVENANCE_IDENTITY,
    }:
        code = {
            RepresentationClaim.DIRECT_TEXTUAL_DEPENDENCE: "RELATIONAL_EVIDENCE_REQUIRED",
            RepresentationClaim.EXEMPLAR_IDENTITY: "EXEMPLAR_EVIDENCE_REQUIRED",
            RepresentationClaim.PROVENANCE_IDENTITY: "PROVENANCE_EVIDENCE_REQUIRED",
        }[claim_value]
        return _decision(
            representation,
            claim_value,
            LicenseStatus.DENIED,
            code,
            "A source representation alone cannot establish this claim.",
            "Supply and validate separate evidence at the required level.",
        )

    if claim_value == RepresentationClaim.REPRESENTED_ARGUMENT:
        if kind == RepresentationType.PAGE_IMAGE.value:
            if representation.evidence_state in {"PAGE_OBSCURED", "PAGE_LOST"}:
                return _decision(
                    representation,
                    claim_value,
                    LicenseStatus.DENIED,
                    "PAGE_CONTENT_NOT_VISIBLE",
                    "An obscured or lost page does not directly expose argument content.",
                )
            if representation.evidence_state is None:
                return _decision(
                    representation,
                    claim_value,
                    LicenseStatus.CONDITIONAL,
                    "PAGE_EVIDENCE_STATE_REQUIRED",
                    "Argument analysis requires an explicit page-evidence state.",
                    "Record the inherited page-evidence state.",
                )
            return _decision(
                representation,
                claim_value,
                LicenseStatus.ALLOWED,
                "VISIBLE_PAGE_ARGUMENT",
                "The argument visible on the supplied image may be analyzed subject to its evidence state.",
            )
        if kind == RepresentationType.OCR.value and (
            representation.verification == RepresentationVerification.LOCATOR_ONLY.value
        ):
            return _decision(
                representation,
                claim_value,
                LicenseStatus.DENIED,
                "OCR_IS_LOCATOR_ONLY",
                "Locator-only OCR does not directly license argument analysis.",
            )
        if kind in _TEXT_BEARING and has_content:
            code = "OCR_ARGUMENT_PROVISIONAL" if kind == RepresentationType.OCR.value else "REPRESENTED_ARGUMENT_AVAILABLE"
            return _decision(
                representation,
                claim_value,
                LicenseStatus.ALLOWED,
                code,
                "The content carried by this representation may be analyzed as represented.",
                *((
                    "Retain OCR status and verify material claims against a stronger representation.",
                ) if kind == RepresentationType.OCR.value else ()),
            )
        return _decision(
            representation,
            claim_value,
            LicenseStatus.CONDITIONAL,
            "REPRESENTED_CONTENT_REQUIRED",
            "Argument analysis requires represented content.",
            "Supply content without changing the representation type.",
        )

    if claim_value == RepresentationClaim.VISIBLE_PAGE_CONTENT:
        if kind != RepresentationType.PAGE_IMAGE.value:
            return _decision(
                representation,
                claim_value,
                LicenseStatus.DENIED,
                "PAGE_IMAGE_REQUIRED",
                "This representation does not directly expose page-image content.",
            )
        if representation.evidence_state in {"PAGE_OBSCURED", "PAGE_LOST"}:
            return _decision(
                representation,
                claim_value,
                LicenseStatus.DENIED,
                "PAGE_CONTENT_NOT_VISIBLE",
                "The inherited page state withholds a visible reading.",
            )
        if representation.evidence_state is None:
            return _decision(
                representation,
                claim_value,
                LicenseStatus.CONDITIONAL,
                "PAGE_EVIDENCE_STATE_REQUIRED",
                "Visible-page claims require an explicit inherited page state.",
            )
        return _decision(
            representation,
            claim_value,
            LicenseStatus.ALLOWED,
            "PAGE_CONTENT_VISIBLE",
            "The supplied image directly supports what is recorded as visible or uncertain on that image.",
        )

    if claim_value == RepresentationClaim.TRANSCRIBED_WORDING:
        if kind == RepresentationType.TRANSCRIPTION.value and has_content:
            return _decision(
                representation,
                claim_value,
                LicenseStatus.ALLOWED,
                "TRANSCRIBED_WORDING_AVAILABLE",
                "The transcription directly supports analysis of its transcribed wording.",
            )
        return _decision(
            representation,
            claim_value,
            LicenseStatus.DENIED,
            "TRANSCRIPTION_REQUIRED",
            "This claim requires a transcription representation.",
        )

    if claim_value == RepresentationClaim.OCR_LOCATOR:
        if kind == RepresentationType.OCR.value:
            return _decision(
                representation,
                claim_value,
                LicenseStatus.ALLOWED,
                "OCR_LOCATOR_AVAILABLE",
                "OCR may be used as a discovery locator without promoting its text.",
            )
        return _decision(
            representation,
            claim_value,
            LicenseStatus.DENIED,
            "OCR_REQUIRED",
            "This locator permission belongs only to OCR.",
        )

    if claim_value == RepresentationClaim.PROVISIONAL_TEXT:
        if kind == RepresentationType.OCR.value and has_content and (
            representation.verification != RepresentationVerification.LOCATOR_ONLY.value
        ):
            return _decision(
                representation,
                claim_value,
                LicenseStatus.ALLOWED,
                "OCR_PROVISIONAL_TEXT",
                "OCR may support provisional text analysis while remaining OCR.",
            )
        return _decision(
            representation,
            claim_value,
            LicenseStatus.DENIED,
            "PROVISIONAL_OCR_TEXT_UNAVAILABLE",
            "No non-locator OCR text is available for provisional analysis.",
        )

    if claim_value == RepresentationClaim.HISTORICAL_EVENT_STATUS:
        if (
            kind == RepresentationType.HISTORICAL_TRANSLATION.value
            and HistoricalTranslationRole.HISTORICAL_EVENT.value
            in representation.historical_translation_roles
        ):
            return _decision(
                representation,
                claim_value,
                LicenseStatus.ALLOWED,
                "HISTORICAL_TRANSLATION_EVENT_RECORDED",
                "The historical translation is explicitly recorded as a historical event object.",
                "No genealogy or dependence relation follows from this role alone.",
            )
        return _decision(
            representation,
            claim_value,
            LicenseStatus.DENIED,
            "HISTORICAL_EVENT_ROLE_REQUIRED",
            "Historical-event status must be explicitly recorded for a historical translation.",
        )

    if claim_value == RepresentationClaim.EDITION_TEXT:
        if kind == RepresentationType.SCHOLARLY_EDITION.value and has_content:
            return _decision(
                representation,
                claim_value,
                LicenseStatus.ALLOWED,
                "EDITION_TEXT_AVAILABLE",
                "The established edition representation supports claims about its carried text.",
            )
        return _decision(
            representation,
            claim_value,
            LicenseStatus.DENIED,
            "SCHOLARLY_EDITION_REQUIRED",
            "Edition-text claims require a scholarly-edition representation.",
        )

    if claim_value == RepresentationClaim.EDITION_APPARATUS:
        if kind == RepresentationType.SCHOLARLY_EDITION.value and representation.apparatus_present:
            return _decision(
                representation,
                claim_value,
                LicenseStatus.ALLOWED,
                "EDITION_APPARATUS_AVAILABLE",
                "The representation explicitly records an available scholarly apparatus.",
            )
        return _decision(
            representation,
            claim_value,
            LicenseStatus.DENIED,
            "EDITION_APPARATUS_NOT_SUPPLIED",
            "No scholarly apparatus is carried by this representation.",
        )

    if claim_value == RepresentationClaim.SUPPLIED_QUOTED_TEXT:
        if kind in {
            RepresentationType.PASTED_QUOTATION.value,
            RepresentationType.SECONDARY_QUOTATION.value,
        } and has_content:
            return _decision(
                representation,
                claim_value,
                LicenseStatus.ALLOWED,
                "SUPPLIED_QUOTATION_AVAILABLE",
                "The text actually supplied may be analyzed without resolving its upstream source.",
            )
        return _decision(
            representation,
            claim_value,
            LicenseStatus.DENIED,
            "QUOTATION_REPRESENTATION_REQUIRED",
            "This permission requires supplied quotation text.",
        )

    if claim_value == RepresentationClaim.SECONDARY_REPORT:
        if kind == RepresentationType.SECONDARY_QUOTATION.value and has_content:
            return _decision(
                representation,
                claim_value,
                LicenseStatus.ALLOWED,
                "SECONDARY_REPORT_AVAILABLE",
                "The representation supports what the inspected secondary source reports or quotes.",
            )
        return _decision(
            representation,
            claim_value,
            LicenseStatus.DENIED,
            "SECONDARY_QUOTATION_REQUIRED",
            "A secondary-report claim requires a secondary-quotation representation.",
        )

    if claim_value in {
        RepresentationClaim.EXACT_ORIGINAL_WORDING,
        RepresentationClaim.EXACT_ORIGINAL_SPELLING,
        RepresentationClaim.SOURCE_LANGUAGE_LEXICAL_IDENTITY,
        RepresentationClaim.QUOTATION_FORM,
    }:
        if kind in _TRANSLATIONS or kind in {
            RepresentationType.PASTED_QUOTATION.value,
            RepresentationType.SECONDARY_QUOTATION.value,
            RepresentationType.OCR.value,
        }:
            return _decision(
                representation,
                claim_value,
                LicenseStatus.DENIED,
                "ORIGINAL_LANGUAGE_REPRESENTATION_REQUIRED",
                "This representation does not directly establish source-language form.",
                "Inspect an appropriately licensed original-language representation.",
            )
        if kind not in _ORIGINAL_LANGUAGE_CARRIERS:
            return _decision(
                representation,
                claim_value,
                LicenseStatus.DENIED,
                "ORIGINAL_LANGUAGE_REPRESENTATION_REQUIRED",
                "This representation does not carry original-language evidence.",
            )
        if representation.verification != RepresentationVerification.VERIFIED.value:
            return _decision(
                representation,
                claim_value,
                LicenseStatus.CONDITIONAL,
                "ORIGINAL_LANGUAGE_VERIFICATION_REQUIRED",
                "The original-language carrier must be verified before this exact claim is licensed.",
            )
        if not representation.language:
            return _decision(
                representation,
                claim_value,
                LicenseStatus.CONDITIONAL,
                "SOURCE_LANGUAGE_REQUIRED",
                "The source language must be recorded for this claim.",
            )
        if kind == RepresentationType.PAGE_IMAGE.value and (
            representation.evidence_state != "PAGE_VISIBLE"
        ):
            return _decision(
                representation,
                claim_value,
                LicenseStatus.CONDITIONAL,
                "VISIBLE_PAGE_READING_REQUIRED",
                "Exact wording from an image requires a verified PAGE_VISIBLE reading.",
            )
        if not has_content and kind != RepresentationType.PAGE_IMAGE.value:
            return _decision(
                representation,
                claim_value,
                LicenseStatus.CONDITIONAL,
                "ORIGINAL_LANGUAGE_CONTENT_REQUIRED",
                "The verified original-language content must be present.",
            )
        return _decision(
            representation,
            claim_value,
            LicenseStatus.ALLOWED,
            "VERIFIED_ORIGINAL_LANGUAGE_CARRIER",
            "A verified original-language carrier directly supports this source-language claim.",
        )

    if claim_value in {
        RepresentationClaim.EXACT_GLYPH_IDENTITY,
        RepresentationClaim.PAGE_LAYOUT,
        RepresentationClaim.PHYSICAL_CONDITION,
    }:
        if kind != RepresentationType.PAGE_IMAGE.value:
            return _decision(
                representation,
                claim_value,
                LicenseStatus.DENIED,
                "PAGE_IMAGE_REQUIRED",
                "This physical or visual claim requires an inspected page image.",
            )
        if (
            representation.verification != RepresentationVerification.VERIFIED.value
            or representation.evidence_state != "PAGE_VISIBLE"
        ):
            return _decision(
                representation,
                claim_value,
                LicenseStatus.CONDITIONAL,
                "VERIFIED_VISIBLE_IMAGE_REQUIRED",
                "The supplied image must be verified and PAGE_VISIBLE for this direct claim.",
            )
        return _decision(
            representation,
            claim_value,
            LicenseStatus.ALLOWED,
            "VERIFIED_VISIBLE_IMAGE",
            "The verified visible image directly carries this visual or physical feature.",
        )

    raise ValidationError(f"no licensing rule for {claim_value.value}")


@dataclass(frozen=True)
class RepresentationRegistry:
    """Validated representation collection with ancestry and audit operations."""

    _raw: Mapping[str, Any] = field(repr=False)
    representations: tuple[SourceRepresentation, ...] = field(repr=False)
    _by_id: Mapping[str, SourceRepresentation] = field(repr=False)

    @classmethod
    def from_dict(cls, value: Any) -> "RepresentationRegistry":
        if not isinstance(value, dict):
            raise ValidationError("representation registry must be an object")
        if value.get("schema_version") != "1":
            raise ValidationError("representation registry schema_version must be 1")
        entries = value.get("representations")
        if not isinstance(entries, list):
            raise ValidationError("representation registry entries must be an ordered list")
        representations = tuple(SourceRepresentation.from_dict(item) for item in entries)
        by_id = {item.representation_id: item for item in representations}
        if len(by_id) != len(representations):
            raise ValidationError("representation ids must be unique")
        for item in representations:
            for derivation in item.derivations:
                if derivation.parent_representation_id not in by_id:
                    raise ValidationError(
                        f"{item.representation_id} references missing parent "
                        f"{derivation.parent_representation_id}"
                    )
                if derivation.relation not in _DERIVATION_RULES[item.representation_type]:
                    raise ValidationError(
                        f"{item.representation_id} has invalid {item.representation_type} "
                        f"derivation relation {derivation.relation}"
                    )

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(representation_id: str) -> None:
            if representation_id in visiting:
                raise ValidationError("representation ancestry must be acyclic")
            if representation_id in visited:
                return
            visiting.add(representation_id)
            for link in by_id[representation_id].derivations:
                visit(link.parent_representation_id)
            visiting.remove(representation_id)
            visited.add(representation_id)

        for representation_id in by_id:
            visit(representation_id)
        return cls(copy.deepcopy(value), representations, by_id)

    def get(self, representation_id: str) -> SourceRepresentation:
        try:
            return self._by_id[representation_id]
        except KeyError as exc:
            raise ValidationError(f"unknown representation {representation_id!r}") from exc

    def ancestry(self, representation_id: str) -> tuple[str, ...]:
        """Return deterministic parent-before-child ancestry without intellectual meaning."""

        self.get(representation_id)
        ordered: list[str] = []
        seen: set[str] = set()

        def collect(current: str) -> None:
            for link in self.get(current).derivations:
                collect(link.parent_representation_id)
                if link.parent_representation_id not in seen:
                    seen.add(link.parent_representation_id)
                    ordered.append(link.parent_representation_id)

        collect(representation_id)
        return tuple(ordered)

    def evidence_roots(self, representation_id: str) -> tuple[str, ...]:
        item = self.get(representation_id)
        if not item.derivations:
            return (item.evidence_root_id,)
        roots: set[str] = set()
        for link in item.derivations:
            roots.update(self.evidence_roots(link.parent_representation_id))
        return tuple(sorted(roots))

    def shares_ancestry(self, left_id: str, right_id: str) -> bool:
        return bool(set(self.evidence_roots(left_id)) & set(self.evidence_roots(right_id)))

    def are_independent(self, left_id: str, right_id: str) -> bool:
        return not self.shares_ancestry(left_id, right_id)

    def uncertainty_lineage(self, representation_id: str) -> tuple[dict[str, Any], ...]:
        """Expose recorded uncertainty without calculating propagation or confidence."""

        result: list[dict[str, Any]] = []
        for current in self.ancestry(representation_id) + (representation_id,):
            item = self.get(current)
            if item.uncertainty is not None:
                result.append(
                    {
                        "representation_id": current,
                        "uncertainty": item.uncertainty.to_dict(),
                    }
                )
        return tuple(result)

    def assess(self, representation_id: str, claim: RepresentationClaim | str) -> LicenseDecision:
        return assess_direct_license(self.get(representation_id), claim)

    def require(self, representation_id: str, claim: RepresentationClaim | str) -> LicenseDecision:
        decision = self.assess(representation_id, claim)
        if not decision.licensed:
            raise RepresentationLicenseError(
                f"{decision.code}: {decision.explanation}"
            )
        return decision

    def assess_pair(
        self,
        left_id: str,
        right_id: str,
        claim: RepresentationClaim | str,
        *,
        basis: str | None = None,
    ) -> LicenseDecision:
        try:
            claim_value = claim if isinstance(claim, RepresentationClaim) else RepresentationClaim(claim)
        except ValueError as exc:
            raise ValidationError(f"invalid representation claim {claim!r}") from exc
        left = self.get(left_id)
        right = self.get(right_id)
        if claim_value != RepresentationClaim.DIRECT_TEXTUAL_DEPENDENCE:
            raise ValidationError("pair assessment currently supports only dependence restraint")
        translated_similarity = (
            left.representation_type in _TRANSLATIONS
            and right.representation_type in _TRANSLATIONS
            and basis == "wording_similarity"
        )
        code = (
            "TRANSLATED_WORDING_SIMILARITY_NOT_DEPENDENCE"
            if translated_similarity
            else "HISTORICAL_RELATION_EVIDENCE_REQUIRED"
        )
        explanation = (
            "Similar translated wording does not directly establish textual dependence."
            if translated_similarity
            else "Representation comparison alone does not establish direct textual dependence."
        )
        return LicenseDecision(
            f"{left_id}|{right_id}",
            f"{left.representation_type}|{right.representation_type}",
            claim_value.value,
            LicenseStatus.DENIED.value,
            code,
            explanation,
            ("A later historical-relation layer requires independent discriminating evidence.",),
        )

    def audit_license_requests(
        self,
        requests: Iterable[tuple[str, RepresentationClaim | str]],
    ) -> AuditResult:
        findings: list[AuditFinding] = []
        for representation_id, claim in requests:
            decision = self.assess(representation_id, claim)
            if not decision.licensed:
                findings.append(
                    AuditFinding(
                        f"REPRESENTATION_{decision.code}",
                        f"{decision.representation_id} cannot directly license "
                        f"{decision.claim}: {decision.explanation}",
                    )
                )
        return AuditResult(tuple(findings))

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._raw))

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())

    def sha256(self) -> str:
        return sha256_json(self.to_dict())
