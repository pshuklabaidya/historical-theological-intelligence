#!/usr/bin/env python3
"""Deterministic claim-aware evidence audit for early-modern commentary work."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

EVIDENCE_CLASSES = {
    "supplied_image_observation",
    "bibliography",
    "other_witness",
    "historical_translation",
    "external_authority",
    "inference_reconstruction",
}
IDENTITY_STATES = [
    "UNIDENTIFIED",
    "WORK_CANDIDATE",
    "WORK_ESTABLISHED",
    "EDITION_ESTABLISHED",
    "EXEMPLAR_ESTABLISHED",
]
HIGH_RISK = {
    "proper_name", "exact_glyph", "greek", "hebrew", "numeral", "citation",
    "signature", "rare_term", "legal_reference", "orientation", "edition_identity",
}
CHECK_KINDS = {
    "glyph_pattern", "same_page_comparison", "script_check", "lexical_check",
    "numeral_check", "citation_check", "signature_check", "legal_check",
    "bibliographic_discriminator", "copy_specific_mark", "full_text_passage",
    "physical_sequence", "explicit_pagination", "folio_mark", "running_head",
}
COPY_SPECIFIC_KINDS = {"copy_specific_mark", "shelfmark_match", "ownership_inscription", "binding_match"}
ORIENTATION_KINDS = {"explicit_pagination", "folio_mark", "physical_sequence", "running_head"}
EDITION_CLASSES = {"bibliography", "other_witness", "supplied_image_observation"}
GLYPH_DIAGNOSTIC_KINDS = {"glyph_pattern", "same_page_comparison", "glyph_atlas", "same_edition_image"}
WORK_ID_DISCRIMINATORS = {
    "explicit_author_title", "distinctive_phrase_match", "page_level_text_match",
    "sequence_match", "textual_bibliographic_match", "full_text_passage",
    "explicit_imprint_colophon", "distinctive_running_title", "verified_dossier_fact",
}
GENERIC_WORK_LEADS = {
    "theological_resemblance", "style_resemblance", "commentary_genre", "biblical_book",
    "printer_city", "printing_milieu", "generic_running_head", "generic_layout",
    "author_interest", "candidate_exclusion", "catalog_same_book",
}
MODEL_MEMORY_ORIGINS = {"model_memory", "unverified_model_recollection", "remembered_content"}
OFFLINE_WORK_DISCRIMINATORS = {
    "explicit_author_title", "explicit_imprint_colophon", "distinctive_running_title",
    "distinctive_phrase_match", "page_level_text_match", "sequence_match",
    "verified_dossier_fact", "full_text_passage",
}
IDENTITY_VERIFICATION_STATUSES = {"unavailable", "available_not_used", "completed", "not_applicable"}
PHYSICALLY_UNREADABLE = {
    "obscured", "physically_unreadable", "masked", "missing", "binding_loss",
    "ink_loss", "severe_damage", "cropped_out",
}
OBSERVATIONAL_PLACEHOLDERS = {"", "[obscured]", "[unreadable]", "[illegible]", "[missing]", "[...]", "[lacuna]"}
TEXTUAL_RELATIONSHIP_CLASSES = {
    "direct_reuse", "quotation", "verbatim_reuse", "close_verbal_parallel",
    "paraphrase", "adaptation", "loose_verbal_parallel", "conceptual_parallel",
    "related_topic", "not_verbatim_reuse", "non_reuse", "no_reuse",
}
COMPARATOR_INSPECTION_LEVELS = {"full_text_compared", "comparator_text_inspected", "primary_text_compared"}
PAGE_EVIDENCE_STATES = {"PAGE_VISIBLE", "PAGE_UNCERTAIN", "PAGE_OBSCURED", "PAGE_LOST"}
RECONSTRUCTION_STATES = {"WITNESS_RECONSTRUCTION", "CONJECTURE"}
TYPED_RELATIONSHIPS = {
    "SUPPORTS", "DERIVED_FROM", "RECONSTRUCTS", "QUALIFIES", "CONFLICTS_WITH",
    "REQUIRES", "DOES_NOT_SUPPORT",
}
TRANSCRIPTION_OUTPUT_MODES = {"diplomatic", "normalized", "scholar_view_diplomatic", "glyph_level", "transcription"}
OBSERVATIONAL_OUTPUT_LAYERS = {"observation", "diplomatic", "normalized", "translation"}
BIBLIOGRAPHICAL_CLAIM_KINDS = {
    "signature_face", "catchword_continuity", "quire_size", "gathering_structure",
    "gathering_formula", "conjugacy", "internal_quire_pagination",
}
GATHERING_EVIDENCE_KINDS = {"gathering_collation", "verified_gathering_structure", "physical_gathering"}
CONJUGACY_EVIDENCE_KINDS = {"physical_conjugacy", "verified_gathering_structure"}
QUIRE_PAGINATION_EVIDENCE_KINDS = {"verified_page_sequence", "explicit_quire_pagination", "gathering_collation"}
PHYSICAL_HISTORY_CLAIM_KINDS = {
    "ownership", "reader_identity", "annotator_identity", "named_hand", "hand_count",
    "handwriting_date", "century_assignment", "ink_composition", "provenance",
    "institutional_ownership_history", "binding_history", "acquisition_history",
    "marginalia_attribution",
}
VISIBLE_PHYSICAL_CLAIM_KINDS = {
    "visible_ink_description", "appears_handwritten", "appears_printed",
    "visually_distinct_writing_styles", "visible_date_like_text", "annotation_location",
    "writing_orientation",
}
PHYSICAL_HISTORY_EVIDENCE_KINDS = {
    "verified_provenance_record", "archival_ownership_record", "documented_hand_attribution",
    "material_analysis", "verified_binding_study", "institutional_catalog_record",
    "acquisition_record", "authenticated_ownership_inscription",
}
FINAL_RESPONSE_SPAN_ROLES = {
    "current_work_identity", "historical_name", "historical_source", "external_comparator",
    "bibliographic_candidate", "external_bibliographic_record", "scripture_reference",
    "other_named_entity", "translated_page_content", "analytical_claim", "general",
}
NONCURRENT_IDENTITY_ROLES = {
    "historical_name", "historical_source", "external_comparator", "bibliographic_candidate",
    "external_bibliographic_record", "scripture_reference", "other_named_entity",
    "translated_page_content",
}
FINALIZER_SCHEMA_VERSION = "0.2"
FINALIZER_ID = "finalize_response.py"
# These patterns identify identity-bearing prose rather than every historical
# name.  A matching span must be bound either to the current-work manifest or
# to an explicitly non-current role in final_response.spans.
IDENTITY_PROSE_PATTERNS = (
    re.compile(r"\b(?i:possibly|probably|likely|could be|may be|resembles|sounds like|"
               r"unverified candidate|attributed to)\s+(?:(?i:be)\s+)?(?P<name>[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'’-]*(?:\s+[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'’-]*){0,5})"),
    re.compile(r"\b(?i:identification|work|author)\s*:\s*(?P<name>[A-Z][^\n.;:]{0,120})"),
    re.compile(r"\b(?i:this|the)\s+(?i:page|work|commentary)\s+(?i:is|comes from|belongs to)\s+(?P<name>[A-Z][^\n.;:]{0,120})"),
    re.compile(r"(?P<name>[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'’-]*(?:\s+[A-Z][A-Za-zÀ-ÖØ-öø-ÿ'’-]*){0,4}'s\s+(?i:commentary|commentarii|work))"),
)



def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_identity_alias(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = unicodedata.normalize("NFKC", value)
    text = re.sub(r"[*_`~]+", "", text).replace("’", "'")
    text = re.sub(r"[^\w'\-]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip().casefold()


def identity_alias_variants(value: Any) -> set[str]:
    if not isinstance(value, str) or not value.strip():
        return set()
    raw = unicodedata.normalize("NFKC", value).strip()
    out = {normalize_identity_alias(raw)}
    possessive = re.match(r"^(.+?)(?:'s|’s)\s+(.+)$", raw)
    if possessive:
        out.add(normalize_identity_alias(possessive.group(1)))
        out.add(normalize_identity_alias(possessive.group(2)))
    for sep in (" - ", ": ", ", "):
        if sep in raw:
            for part in raw.split(sep):
                if len(part.strip()) >= 3:
                    out.add(normalize_identity_alias(part))
    return {x for x in out if len(x) >= 3}


def current_work_aliases(data: dict[str, Any]) -> set[str]:
    aliases: set[str] = set()
    for hypothesis in data.get("identity_hypotheses", []):
        if not isinstance(hypothesis, dict):
            continue
        for key in ("name", "author", "title", "value", "proposed_identity", "label"):
            aliases.update(identity_alias_variants(hypothesis.get(key)))
        raw_aliases = hypothesis.get("aliases", [])
        if isinstance(raw_aliases, list):
            for alias in raw_aliases:
                aliases.update(identity_alias_variants(alias))
    for claim in data.get("claims", []):
        if not isinstance(claim, dict) or claim.get("claim_type") != "work_identity":
            continue
        aliases.update(identity_alias_variants(claim.get("value")))
        raw_aliases = claim.get("aliases", [])
        if isinstance(raw_aliases, list):
            for alias in raw_aliases:
                aliases.update(identity_alias_variants(alias))
    return aliases


def alias_regex(alias: str) -> re.Pattern[str]:
    tokens = [re.escape(token) for token in alias.split() if token]
    if not tokens:
        return re.compile(r"(?!)")
    joiner = r"(?:[\s*_`~]+|\s*['’]s\s*)"
    return re.compile(r"(?<![\w])" + joiner.join(tokens) + r"(?![\w])", re.IGNORECASE)


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("top-level JSON must be an object")
    return data


def add(errors: list[str], code: str, message: str) -> None:
    errors.append(f"{code}: {message}")


def evidence_map(data: dict[str, Any], errors: list[str]) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(data.get("evidence", [])):
        if not isinstance(item, dict):
            add(errors, "EVIDENCE_SHAPE", f"evidence[{index}] is not an object")
            continue
        eid = item.get("evidence_id")
        if not eid or not isinstance(eid, str):
            add(errors, "EVIDENCE_ID", f"evidence[{index}] lacks evidence_id")
            continue
        if eid in mapped:
            add(errors, "EVIDENCE_DUPLICATE", f"duplicate evidence_id {eid}")
        eclass = item.get("evidence_class")
        if eclass not in EVIDENCE_CLASSES:
            add(errors, "EVIDENCE_CLASS", f"{eid} has invalid evidence_class {eclass!r}")
        if not item.get("independence_group"):
            add(errors, "INDEPENDENCE_GROUP", f"{eid} lacks independence_group")
        if not item.get("description"):
            add(errors, "EVIDENCE_DESCRIPTION", f"{eid} lacks description")
        mapped[eid] = item
    return mapped


def referenced(ids: Any, emap: dict[str, dict[str, Any]], errors: list[str], owner: str) -> list[dict[str, Any]]:
    if ids is None:
        return []
    if not isinstance(ids, list):
        add(errors, "EVIDENCE_REFS", f"{owner} evidence_ids must be a list")
        return []
    out = []
    for eid in ids:
        if eid not in emap:
            add(errors, "EVIDENCE_MISSING", f"{owner} references missing evidence {eid}")
        else:
            out.append(emap[eid])
    return out


def is_asserted(claim: dict[str, Any]) -> bool:
    return claim.get("status") in {"asserted", "secure", "verified", "established"} or claim.get("confidence") == "secure"


def is_work_identity_promoted(claim: dict[str, Any]) -> bool:
    """A named probable identity needs evidence, unlike a retained candidate lead."""
    return is_asserted(claim) or claim.get("status") == "probable"


def independent(items: list[dict[str, Any]]) -> int:
    return len({i.get("independence_group") for i in items if i.get("independence_group")})


def is_observational_placeholder(value: Any) -> bool:
    """Return whether a blocked region is represented as unreadable, not read."""
    return value is None or (isinstance(value, str) and value.strip().lower() in OBSERVATIONAL_PLACEHOLDERS)


def audit_claim(claim: dict[str, Any], emap: dict[str, dict[str, Any]], errors: list[str]) -> None:
    cid = claim.get("claim_id", "<unnamed>")
    ctype = claim.get("claim_type")
    ev = referenced(claim.get("evidence_ids", []), emap, errors, f"claim {cid}")
    classes = {e.get("evidence_class") for e in ev}
    kinds = {e.get("kind") for e in ev}
    asserted = is_asserted(claim)

    evidence_state = claim.get("evidence_state")
    if evidence_state and evidence_state not in PAGE_EVIDENCE_STATES | RECONSTRUCTION_STATES:
        add(errors, "CLAIM_EVIDENCE_STATE", f"{cid} has invalid typed evidence state {evidence_state!r}")
    relationship = claim.get("relationship")
    if relationship and relationship not in TYPED_RELATIONSHIPS:
        add(errors, "CLAIM_RELATIONSHIP", f"{cid} has invalid typed relationship {relationship!r}")

    if ctype in HIGH_RISK and asserted:
        if not ev:
            add(errors, "HIGH_RISK_UNSUPPORTED", f"{cid} ({ctype}) is asserted without evidence")
        if ctype in {"proper_name", "greek", "hebrew", "numeral", "citation", "signature", "rare_term", "legal_reference"}:
            if not (kinds & CHECK_KINDS):
                add(errors, "HIGH_RISK_UNCHECKED", f"{cid} ({ctype}) lacks an explicit diagnostic check")

    if ctype == "exact_glyph" and asserted:
        if "supplied_image_observation" not in classes:
            add(errors, "GLYPH_NO_IMAGE", f"{cid} lacks supplied-image evidence")
        diagnostic = bool(kinds & GLYPH_DIAGNOSTIC_KINDS)
        if not diagnostic:
            add(errors, "GLYPH_NO_DIAGNOSTIC", f"{cid} lacks a distinct glyph diagnostic")
        if kinds & {"lexical_check", "script_check", "positional_convention", "lexical_context"} and not diagnostic:
            add(errors, "GLYPH_CONTEXT_NOT_DIAGNOSTIC", f"{cid} uses lexical or positional context as a glyph diagnostic")
        if classes <= {"historical_translation", "inference_reconstruction"}:
            add(errors, "EVIDENCE_TYPE_MISUSE", f"{cid} uses translation or inference as glyph evidence")

    if ctype == "orientation" and asserted and not (kinds & ORIENTATION_KINDS):
        add(errors, "ORIENTATION_UNSUPPORTED", f"{cid} lacks page-structure or sequence evidence")

    if ctype == "work_identity" and is_work_identity_promoted(claim):
        if not (classes & {"bibliography", "other_witness", "supplied_image_observation"}):
            add(errors, "WORK_ID_UNSUPPORTED", f"{cid} lacks bibliographic, witness, or explicit supplied-page evidence")
        if not (kinds & WORK_ID_DISCRIMINATORS):
            add(errors, "WORK_ID_NOT_DISCRIMINATING", f"{cid} lacks a discriminating textual, structural, or explicit identity match")
        if kinds & GENERIC_WORK_LEADS and not (kinds & WORK_ID_DISCRIMINATORS):
            add(errors, "WORK_ID_GENERIC_LEAD", f"{cid} promotes generic resemblance from lead to identity")

    if ctype == "edition_identity" and asserted:
        if not (classes & EDITION_CLASSES) or "bibliographic_discriminator" not in kinds:
            add(errors, "EDITION_UNSUPPORTED", f"{cid} lacks edition-discriminating evidence")

    if ctype in {"exemplar_identity", "provenance"} and asserted:
        if not (kinds & COPY_SPECIFIC_KINDS):
            add(errors, "EXEMPLAR_UNSUPPORTED", f"{cid} lacks copy-specific evidence")

    if ctype == "translation_alignment" and asserted and claim.get("establishes") in {"exact_glyph", "orientation", "edition_identity", "source_proposition"}:
        add(errors, "EVIDENCE_TYPE_MISUSE", f"{cid} cannot establish {claim.get('establishes')}")

    if ctype == "source_proposition" and claim.get("status") == "verified":
        if "full_text_passage" not in kinds:
            add(errors, "PROPOSITION_UNVERIFIED", f"{cid} lacks inspected proposition-level passage")

    if ctype == "legal_reference" and asserted:
        required = {"printed_citation", "normalized_location", "proposition_found"}
        if not required.issubset(claim):
            add(errors, "LEGAL_FIELDS", f"{cid} lacks printed citation, normalized location, or proposition")


def audit_identity(data: dict[str, Any], claims: dict[str, dict[str, Any]], errors: list[str]) -> None:
    state = data.get("identity_state", "UNIDENTIFIED")
    if state not in IDENTITY_STATES:
        add(errors, "IDENTITY_STATE", f"invalid identity_state {state!r}")
        return
    selected = data.get("selected_claim_ids", [])
    if not isinstance(selected, list):
        add(errors, "IDENTITY_SELECTED", "selected_claim_ids must be a list")
        return
    selected_claims = []
    for cid in selected:
        if cid not in claims:
            add(errors, "IDENTITY_CLAIM_MISSING", f"selected identity claim {cid} is absent")
        else:
            selected_claims.append(claims[cid])
    types = {c.get("claim_type") for c in selected_claims if is_asserted(c)}
    threshold = IDENTITY_STATES.index(state)
    needs = [None, None, "work_identity", "edition_identity", "exemplar_identity"]
    for level in range(2, threshold + 1):
        if needs[level] not in types:
            add(errors, "IDENTITY_PREREQUISITE", f"{state} lacks selected asserted {needs[level]} claim")


def audit_identity_hypotheses(data: dict[str, Any], errors: list[str]) -> None:
    """Model recollection may guide a query but is never identity evidence."""
    for hypothesis in data.get("identity_hypotheses", []):
        origin = hypothesis.get("origin")
        if origin in MODEL_MEMORY_ORIGINS and hypothesis.get("user_visible") is True:
            add(errors, "MODEL_MEMORY_SURFACED", f"hypothesis {hypothesis.get('hypothesis_id', '<unnamed>')} exposes model recollection as identity")
        if origin in MODEL_MEMORY_ORIGINS and hypothesis.get("admissible_as_identity_evidence") is True:
            add(errors, "MODEL_MEMORY_NOT_EVIDENCE", f"hypothesis {hypothesis.get('hypothesis_id', '<unnamed>')} treats model recollection as identity evidence")


def audit_final_identity_output(
    data: dict[str, Any], claims: dict[str, dict[str, Any]], emap: dict[str, dict[str, Any]], errors: list[str]
) -> None:
    """Require admissible, provenance-bearing evidence for visible named identity."""
    output = data.get("output", {})
    if output.get("stage") != "final":
        return
    identity = output.get("identity", {})
    if not isinstance(identity, dict):
        add(errors, "IDENTITY_OUTPUT_SHAPE", "final identity output must be an object")
        return
    named = identity.get("proposed_identity")
    if not named:
        return
    state = identity.get("identity_state")
    if state not in set(IDENTITY_STATES) - {"UNIDENTIFIED"}:
        add(errors, "IDENTITY_OUTPUT_STATE", "named final identity lacks a promoted identity state")
    if state != data.get("identity_state"):
        add(errors, "IDENTITY_OUTPUT_STATE", "final identity state does not match checkpoint state")
    verification = identity.get("external_verification")
    if verification not in IDENTITY_VERIFICATION_STATUSES:
        add(errors, "IDENTITY_VERIFICATION_STATUS", "final named identity lacks verification availability status")
    cid = identity.get("claim_id")
    claim = claims.get(cid)
    if not cid or claim is None or claim.get("claim_type") != "work_identity":
        add(errors, "IDENTITY_OUTPUT_CLAIM", "final named identity lacks a work-identity claim")
        return
    if claim.get("value") != named:
        add(errors, "IDENTITY_OUTPUT_CLAIM", "final named identity does not match its claim")
    if claim.get("identity_origin") in MODEL_MEMORY_ORIGINS:
        add(errors, "MODEL_MEMORY_NOT_EVIDENCE", f"{cid} is promoted from model recollection")
    ev = referenced(claim.get("evidence_ids", []), emap, errors, f"final identity {cid}")
    if not ev:
        add(errors, "IDENTITY_OUTPUT_UNSUPPORTED", f"{cid} has no admissible final-output evidence")
        return
    for item in ev:
        eid = item.get("evidence_id", "<unnamed>")
        if item.get("identity_admissible") is not True:
            add(errors, "IDENTITY_EVIDENCE_INADMISSIBLE", f"{eid} is not marked admissible for identity")
        if not item.get("provenance"):
            add(errors, "IDENTITY_EVIDENCE_PROVENANCE", f"{eid} lacks identity evidence provenance")
        if item.get("kind") not in WORK_ID_DISCRIMINATORS:
            add(errors, "IDENTITY_EVIDENCE_DISCRIMINATOR", f"{eid} lacks a discriminating identity type")
        if item.get("origin") in MODEL_MEMORY_ORIGINS:
            add(errors, "MODEL_MEMORY_NOT_EVIDENCE", f"{eid} is model recollection, not identity evidence")
        if verification in {"unavailable", "available_not_used"} and item.get("kind") not in OFFLINE_WORK_DISCRIMINATORS:
            add(errors, "OFFLINE_IDENTITY_UNSUPPORTED", f"{eid} is not admissible offline work evidence")


def validated_span(span: Any, text: str, errors: list[str], owner: str) -> tuple[int, int] | None:
    """Validate one literal final-response span and return its bounds."""
    if not isinstance(span, dict):
        add(errors, "FINAL_RESPONSE_SPAN_SHAPE", f"{owner} span must be an object")
        return None
    start, end, literal = span.get("start"), span.get("end"), span.get("text")
    if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= len(text):
        add(errors, "FINAL_RESPONSE_SPAN_BOUNDS", f"{owner} span lacks valid bounds")
        return None
    if not isinstance(literal, str) or text[start:end] != literal:
        add(errors, "FINAL_RESPONSE_SPAN_TEXT", f"{owner} span text does not match final response")
        return None
    return start, end


def span_covers(bounds: tuple[int, int], target: tuple[int, int]) -> bool:
    return bounds[0] <= target[0] and target[1] <= bounds[1]


def audit_manifest_identity_entry(
    entry: dict[str, Any], text: str, claims: dict[str, dict[str, Any]],
    emap: dict[str, dict[str, Any]], data: dict[str, Any], errors: list[str], index: int,
) -> list[tuple[int, int]]:
    """Validate one current-work name that is intended for final prose."""
    owner = f"identity_manifest[{index}]"
    name = entry.get("proposed_identity")
    cid = entry.get("claim_id")
    state = entry.get("identity_state")
    verification = entry.get("external_verification")
    if not isinstance(name, str) or not name.strip():
        add(errors, "IDENTITY_MANIFEST_NAME", f"{owner} lacks proposed_identity")
    if state not in set(IDENTITY_STATES) - {"UNIDENTIFIED"}:
        add(errors, "IDENTITY_MANIFEST_STATE", f"{owner} lacks promoted identity state")
    if state != data.get("identity_state"):
        add(errors, "IDENTITY_MANIFEST_STATE", f"{owner} state does not match checkpoint state")
    if verification not in IDENTITY_VERIFICATION_STATUSES:
        add(errors, "IDENTITY_MANIFEST_VERIFICATION", f"{owner} lacks verification status")
    if entry.get("identity_admissible") is not True:
        add(errors, "IDENTITY_MANIFEST_ADMISSIBILITY", f"{owner} is not marked admissible")
    if not entry.get("provenance"):
        add(errors, "IDENTITY_MANIFEST_PROVENANCE", f"{owner} lacks provenance")
    claim = claims.get(cid)
    if not cid or claim is None or claim.get("claim_type") != "work_identity":
        add(errors, "IDENTITY_MANIFEST_CLAIM", f"{owner} lacks a work-identity claim")
        return []
    if claim.get("value") != name:
        add(errors, "IDENTITY_MANIFEST_CLAIM", f"{owner} does not match its claim")
    if claim.get("identity_origin") in MODEL_MEMORY_ORIGINS:
        add(errors, "MODEL_MEMORY_NOT_EVIDENCE", f"{cid} is promoted from model recollection")
    entry_evidence = entry.get("evidence_ids")
    if not isinstance(entry_evidence, list) or set(entry_evidence) != set(claim.get("evidence_ids", [])):
        add(errors, "IDENTITY_MANIFEST_EVIDENCE", f"{owner} evidence references do not bind the claim evidence")
    evidence = referenced(claim.get("evidence_ids", []), emap, errors, owner)
    if not evidence:
        add(errors, "IDENTITY_MANIFEST_UNSUPPORTED", f"{owner} has no evidence")
    for item in evidence:
        eid = item.get("evidence_id", "<unnamed>")
        if item.get("identity_admissible") is not True:
            add(errors, "IDENTITY_EVIDENCE_INADMISSIBLE", f"{eid} is not marked admissible for identity")
        if not item.get("provenance"):
            add(errors, "IDENTITY_EVIDENCE_PROVENANCE", f"{eid} lacks identity evidence provenance")
        if item.get("kind") not in WORK_ID_DISCRIMINATORS:
            add(errors, "IDENTITY_EVIDENCE_DISCRIMINATOR", f"{eid} lacks a discriminating identity type")
        if item.get("origin") in MODEL_MEMORY_ORIGINS:
            add(errors, "MODEL_MEMORY_NOT_EVIDENCE", f"{eid} is model recollection, not identity evidence")
        if verification in {"unavailable", "available_not_used"} and item.get("kind") not in OFFLINE_WORK_DISCRIMINATORS:
            add(errors, "OFFLINE_IDENTITY_UNSUPPORTED", f"{eid} is not admissible offline work evidence")
    spans = entry.get("output_spans")
    if not isinstance(spans, list) or not spans:
        add(errors, "IDENTITY_MANIFEST_SPANS", f"{owner} lacks an output span")
        return []
    bounds: list[tuple[int, int]] = []
    for span_index, span in enumerate(spans):
        valid = validated_span(span, text, errors, f"{owner}[{span_index}]")
        if valid is None:
            continue
        if span.get("role") != "current_work_identity":
            add(errors, "IDENTITY_MANIFEST_SPAN_ROLE", f"{owner}[{span_index}] is not current_work_identity")
        literal = span.get("text", "")
        if isinstance(name, str) and literal not in name and name not in literal:
            add(errors, "IDENTITY_MANIFEST_SPAN_BINDING", f"{owner}[{span_index}] does not bind its proposed identity")
        bounds.append(valid)
    return bounds


def identity_like_spans(text: str) -> list[tuple[int, int]]:
    """Return identity-bearing prose spans that need an explicit typed role."""
    spans: list[tuple[int, int]] = []
    for pattern in IDENTITY_PROSE_PATTERNS:
        for match in pattern.finditer(text):
            start, end = match.span("name")
            candidate = text[start:end].strip()
            if candidate and candidate.lower() not in {"unidentified", "unknown", "the present evidence"}:
                spans.append((start, end))
    return list(dict.fromkeys(spans))


def expected_identification_line(data: dict[str, Any], claims: dict[str, dict[str, Any]]) -> str:
    state = data.get("identity_state", "UNIDENTIFIED")
    output = data.get("output", {})
    identity = output.get("identity", {}) if isinstance(output.get("identity"), dict) else {}
    name = identity.get("proposed_identity")
    if name:
        if state == "WORK_CANDIDATE":
            return f"**Identification:** Candidate: {name}."
        return f"**Identification:** {name}."
    if state == "WORK_CANDIDATE":
        return "**Identification:** Work not established; candidate evidence remains unresolved."
    return "**Identification:** Work unidentified from the present evidence."


def audit_finalization_receipt(data: dict[str, Any], claims: dict[str, dict[str, Any]], errors: list[str]) -> None:
    """Bind Alpha 9 final text to a renderer-produced structured plan and hashes."""
    if data.get("schema_version") != FINALIZER_SCHEMA_VERSION:
        return
    output = data.get("output", {})
    if output.get("stage") != "final":
        return
    receipt = output.get("finalization")
    if not isinstance(receipt, dict):
        add(errors, "FINALIZER_REQUIRED", "Alpha 9 final output lacks a finalization receipt")
        return
    if receipt.get("renderer") != FINALIZER_ID or receipt.get("status") != "rendered":
        add(errors, "FINALIZER_REQUIRED", "Alpha 9 final output was not produced by the deterministic finalizer")
    if receipt.get("schema_version") != FINALIZER_SCHEMA_VERSION:
        add(errors, "FINALIZER_SCHEMA", "finalization receipt schema does not match Alpha 9")
    plan = receipt.get("plan")
    if not isinstance(plan, dict):
        add(errors, "FINALIZER_PLAN", "finalization receipt lacks the structured response plan")
        return
    if plan.get("schema_version") != FINALIZER_SCHEMA_VERSION or plan.get("work_id") != data.get("work_id"):
        add(errors, "FINALIZER_PLAN", "response plan schema or work_id does not match the checkpoint")
    plan_hash = sha256_json(plan)
    if receipt.get("plan_sha256") != plan_hash:
        add(errors, "FINALIZER_PLAN_HASH", "response plan hash does not match the embedded plan")
    response = output.get("final_response")
    if not isinstance(response, dict) or not isinstance(response.get("text"), str):
        add(errors, "FINAL_RESPONSE_SHAPE", "finalization receipt lacks rendered final response text")
        return
    text = response["text"]
    response_hash = sha256_text(text)
    if receipt.get("response_sha256") != response_hash or response.get("response_sha256") != response_hash:
        add(errors, "FINALIZER_RESPONSE_HASH", "rendered final response changed after finalization")
    if response.get("derived_by") != FINALIZER_ID or response.get("derived_from_plan_sha256") != plan_hash:
        add(errors, "FINALIZER_RESPONSE_BINDING", "final response is not bound to the renderer plan")
    manifest = response.get("identity_manifest")
    if not isinstance(manifest, dict):
        add(errors, "FINAL_RESPONSE_MANIFEST_REQUIRED", "final response lacks renderer-derived identity manifest")
    else:
        if manifest.get("derived_by") != FINALIZER_ID or manifest.get("derived_from_plan_sha256") != plan_hash:
            add(errors, "IDENTITY_MANIFEST_DERIVATION", "identity manifest is not renderer-derived from the current plan")
        if receipt.get("manifest_sha256") != sha256_json(manifest):
            add(errors, "IDENTITY_MANIFEST_HASH", "identity manifest changed after finalization")
    identity = output.get("identity")
    if not isinstance(identity, dict) or identity.get("derived_by") != FINALIZER_ID:
        add(errors, "FINALIZER_IDENTITY_BINDING", "final identity object is not renderer-derived")
    else:
        visible = plan.get("identity", {}).get("visible_claim_id") if isinstance(plan.get("identity"), dict) else None
        if identity.get("claim_id") != visible:
            add(errors, "FINALIZER_IDENTITY_BINDING", "rendered identity claim does not match the response plan")
    critical = output.get("critical_claim_audit")
    if not isinstance(critical, dict) or critical.get("derived_by") != FINALIZER_ID:
        add(errors, "FINALIZER_CRITICAL_AUDIT", "critical-claim audit marker is not renderer-derived")
    expected = expected_identification_line(data, claims)
    if not text.startswith(expected + "\n"):
        add(errors, "FINALIZER_IDENTIFICATION_MUTATION", "renderer-owned Identification line was changed or replaced")


def audit_final_response_identity_manifest(
    data: dict[str, Any], claims: dict[str, dict[str, Any]], emap: dict[str, dict[str, Any]], errors: list[str]
) -> None:
    """Validate renderer-derived identity bindings and legacy Alpha 8 manifests.

    Alpha 9 does not infer manifest completeness from identity-language regexes.
    The manifest is a product of structured rendering. Dynamic current-work
    aliases are checked independently as defense in depth. Alpha 8 schema 0.1
    retains its legacy detector for regression compatibility only.
    """
    output = data.get("output", {})
    if output.get("stage") != "final":
        return
    named_output = isinstance(output.get("identity"), dict) and output["identity"].get("proposed_identity")
    response = output.get("final_response")
    if response is None:
        if named_output or data.get("schema_version") == FINALIZER_SCHEMA_VERSION:
            add(errors, "FINAL_RESPONSE_MANIFEST_REQUIRED", "final output lacks final_response")
        return
    if not isinstance(response, dict) or not isinstance(response.get("text"), str):
        add(errors, "FINAL_RESPONSE_SHAPE", "final_response must contain final text")
        return
    text = response["text"]
    manifest = response.get("identity_manifest")
    if not isinstance(manifest, dict):
        add(errors, "FINAL_RESPONSE_MANIFEST_REQUIRED", "final_response lacks identity_manifest")
        return
    alpha9 = data.get("schema_version") == FINALIZER_SCHEMA_VERSION
    if not alpha9 and manifest.get("complete") is not True:
        add(errors, "IDENTITY_MANIFEST_INCOMPLETE", "identity manifest must be complete before final audit")
    if alpha9 and manifest.get("derived_by") != FINALIZER_ID:
        add(errors, "IDENTITY_MANIFEST_DERIVATION", "Alpha 9 identity manifest must be renderer-derived")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        add(errors, "IDENTITY_MANIFEST_SHAPE", "identity manifest entries must be a list")
        return
    manifest_bounds: list[tuple[int, int]] = []
    manifest_claim_ids: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            add(errors, "IDENTITY_MANIFEST_SHAPE", f"identity_manifest[{index}] is not an object")
            continue
        manifest_claim_ids.add(str(entry.get("claim_id", "")))
        manifest_bounds.extend(audit_manifest_identity_entry(entry, text, claims, emap, data, errors, index))
    if named_output:
        identity = output["identity"]
        if identity.get("claim_id") not in manifest_claim_ids:
            add(errors, "IDENTITY_MANIFEST_OUTPUT_MISMATCH", "output.identity is absent from final-response identity manifest")
    elif entries:
        add(errors, "IDENTITY_MANIFEST_OUTPUT_MISMATCH", "final-response identity manifest conflicts with unnamed output.identity")
    response_spans = response.get("spans", [])
    if not isinstance(response_spans, list):
        add(errors, "FINAL_RESPONSE_SPANS_SHAPE", "final_response.spans must be a list")
        response_spans = []
    noncurrent_bounds: list[tuple[int, int]] = []
    for index, span in enumerate(response_spans):
        valid = validated_span(span, text, errors, f"final_response.spans[{index}]")
        if valid is None:
            continue
        role = span.get("role")
        if role not in FINAL_RESPONSE_SPAN_ROLES:
            add(errors, "FINAL_RESPONSE_SPAN_ROLE", f"final_response.spans[{index}] has invalid role {role!r}")
        elif role == "analytical_claim":
            cid = span.get("claim_id")
            claim = claims.get(cid)
            if not isinstance(cid, str) or claim is None:
                add(errors, "ANALYTICAL_CLAIM_SPAN", f"final_response.spans[{index}] does not bind an existing analytical claim")
            else:
                span_evidence = span.get("evidence_ids", [])
                claim_evidence = claim.get("evidence_ids", [])
                if not isinstance(span_evidence, list) or set(span_evidence) != set(claim_evidence if isinstance(claim_evidence, list) else []):
                    add(errors, "ANALYTICAL_CLAIM_EVIDENCE_BINDING", f"final_response.spans[{index}] evidence does not match claim {cid}")
                if span.get("claim_type") != claim.get("claim_type"):
                    add(errors, "ANALYTICAL_CLAIM_TYPE_BINDING", f"final_response.spans[{index}] type does not match claim {cid}")
        elif role in NONCURRENT_IDENTITY_ROLES:
            noncurrent_bounds.append(valid)

    allowed_bounds = manifest_bounds + noncurrent_bounds
    if alpha9:
        # Construction-based defense: every known current-work hypothesis/claim
        # alias appearing in final prose must occur inside a renderer-derived
        # current-work or explicitly non-current span. No hedge-phrase grammar
        # is involved.
        for alias in current_work_aliases(data):
            for match in alias_regex(alias).finditer(text):
                target = match.span()
                if not any(span_covers(bounds, target) for bounds in allowed_bounds):
                    add(errors, "PRIVATE_IDENTITY_ALIAS_LEAK", f"current-work identity alias {alias!r} appears outside a typed renderer span")
    else:
        # Legacy Alpha 8 behavior retained only so frozen regression semantics
        # remain testable. Alpha 9 finalization does not depend on this recognizer.
        for target in identity_like_spans(text):
            if not any(span_covers(bounds, target) for bounds in allowed_bounds):
                add(errors, "UNBOUND_IDENTITY_PROSE", "final prose contains a named identity without an audited manifest binding")


def audit_long_s_gate(data: dict[str, Any], claims: dict[str, dict[str, Any]], errors: list[str]) -> None:
    """Block final diplomatic output until a required long-s review is complete."""
    output = data.get("output", {})
    audit = data.get("long_s_audit", {})
    glyph_claim_requires = any(
        claim.get("claim_type") == "exact_glyph"
        and claim.get("glyph_family") in {"long_s_f", "s_f"}
        and is_asserted(claim)
        for claim in claims.values()
    )
    diplomatic_final = output.get("stage") == "final" and output.get("transcription_mode") in {
        "diplomatic", "scholar_view_diplomatic", "glyph_level"
    }
    required = audit.get("required") is True or glyph_claim_requires or diplomatic_final
    if not required:
        return
    if audit.get("required") is not True:
        add(errors, "LONG_S_AUDIT_REQUIRED", "diplomatic or s/f glyph output requires a long-s audit")
        return
    if audit.get("checklist_status") != "validated":
        add(errors, "LONG_S_AUDIT_INCOMPLETE", "required long-s checklist is not validated")
    if audit.get("reviewed_against_supplied_image") is not True:
        add(errors, "LONG_S_IMAGE_REVIEW_REQUIRED", "long-s checklist lacks recorded supplied-image review")
    checks = audit.get("checks")
    if not isinstance(checks, list):
        add(errors, "LONG_S_CHECKLIST_SHAPE", "long-s audit checks must be a list")
    else:
        errors.extend(audit_long_s({"checks": checks}))


def region_evidence_state(region: dict[str, Any]) -> str | None:
    """Translate the Alpha 5 legibility representation into an explicit page state."""
    state = region.get("evidence_state")
    if state:
        return state
    if region.get("physical_visibility") in PHYSICALLY_UNREADABLE:
        return "PAGE_OBSCURED"
    return None


def audit_blocked_reconstruction(
    region: dict[str, Any], emap: dict[str, dict[str, Any]], errors: list[str]
) -> None:
    """A blocked page permits inspected witness recovery, never contextual filling."""
    recovery = region.get("reconstruction")
    if not isinstance(recovery, dict) or not recovery.get("text"):
        return
    rid = region.get("region_id", "<unnamed>")
    if recovery.get("evidence_state") != "WITNESS_RECONSTRUCTION":
        add(errors, "UNSUPPORTED_BLOCKED_RECONSTRUCTION", f"{rid}: preserve the gap; conjecture cannot recover blocked supplied-page content")
        return
    if recovery.get("relationship") != "RECONSTRUCTS":
        add(errors, "RECONSTRUCTION_RELATION", f"{rid}: witness recovery requires RECONSTRUCTS")
    kind = recovery.get("recovery_kind", "wording")
    if kind not in {"wording", "sense"}:
        add(errors, "RECONSTRUCTION_KIND", f"{rid}: recovery_kind must be wording or sense")
    items = referenced(recovery.get("evidence_ids", []), emap, errors, f"reconstruction {rid}")
    page_items = [e for e in emap.values() if e.get("evidence_class") == "supplied_image_observation"]
    page_groups = {e.get("independence_group") for e in page_items if e.get("independence_group")}
    page_roots = {v for e in page_items for v in (e.get("root_id"), e.get("source_sha256")) if v}
    quote = recovery.get("witness_passage")
    supported = False
    for item in items:
        cls = item.get("evidence_class")
        form = item.get("representation_type")
        textual = cls == "other_witness" and form in {"ORIGINAL_TEXT", "SCHOLARLY_EDITION", "DIPLOMATIC_TRANSCRIPTION", "FACSIMILE_SCAN"}
        translated = cls == "historical_translation" and form == "HISTORICAL_TRANSLATION"
        if not textual and not translated:
            continue
        if translated and kind != "sense":
            continue
        passage = item.get("passage_text")
        roots = item.get("derived_from_root_ids", [])
        if not isinstance(roots, list):
            continue
        independent = bool(page_groups) and item.get("independence_group") not in page_groups and bool(item.get("root_id")) and item["root_id"] not in page_roots and not page_roots.intersection(roots)
        if (independent and item.get("passage_inspected") is True
                and all(item.get(k) for k in ("witness_id", "source_locator", "passage_locator", "provenance", "independence_group"))
                and isinstance(passage, str) and passage.strip()
                and item.get("passage_sha256") == sha256_text(passage)
                and isinstance(quote, str) and quote.strip() and quote in passage
                and isinstance(recovery.get("alignment_note"), str) and recovery["alignment_note"].strip()):
            if kind == "wording" and recovery["text"] not in quote:
                continue
            supported = True
    if not supported:
        add(errors, "WITNESS_RECONSTRUCTION_UNSUPPORTED", f"{rid}: require an independent inspected passage, exact passage hash, witness provenance and recovery alignment; a translation supports sense only")


def audit_legibility_regions(
    data: dict[str, Any], claims: dict[str, dict[str, Any]], emap: dict[str, dict[str, Any]], errors: list[str]
) -> dict[str, str]:
    """Keep physically blocked glyphs out of observational transcription layers."""
    regions = data.get("legibility_regions", [])
    if not isinstance(regions, list):
        add(errors, "LEGIBILITY_REGION_SHAPE", "legibility_regions must be a list")
        return {}
    states: dict[str, str] = {}
    for index, region in enumerate(regions):
        if not isinstance(region, dict):
            add(errors, "LEGIBILITY_REGION_SHAPE", f"legibility_regions[{index}] is not an object")
            continue
        region_id = str(region.get("region_id", f"region[{index}]"))
        state = region_evidence_state(region)
        if state and state not in PAGE_EVIDENCE_STATES:
            add(errors, "PAGE_EVIDENCE_STATE", f"{region_id} has invalid page evidence state {state!r}")
            continue
        if state:
            states[region_id] = state
        physically_blocked = region.get("physical_visibility") in PHYSICALLY_UNREADABLE
        if not physically_blocked and state not in {"PAGE_OBSCURED", "PAGE_LOST"}:
            continue
        if state in {"PAGE_VISIBLE", "PAGE_UNCERTAIN"}:
            add(errors, "OBSCURED_TO_VISIBLE", f"{region_id} changes a physically blocked page region into {state}")
        for field in ("observational_text", "diplomatic_text", "normalized_text"):
            if field in region and not is_observational_placeholder(region.get(field)):
                add(errors, "OCCLUDED_TEXT_AS_OBSERVATION",
                    f"{region_id} is physically unreadable but {field} contains an unlabelled reading")
        if region.get("final_reading_status") in {"observed", "visible", "secure_observation"}:
            add(errors, "OCCLUDED_TEXT_AS_OBSERVATION", f"{region_id} is physically unreadable but marked observed")
        reconstruction = region.get("reconstruction")
        if reconstruction is not None:
            if not isinstance(reconstruction, dict):
                add(errors, "RECONSTRUCTION_SHAPE", f"{region_id} reconstruction must be an object")
            elif reconstruction.get("text"):
                reconstruction_state = reconstruction.get("evidence_state")
                if reconstruction_state is None and reconstruction.get("status") == "inference_reconstruction":
                    reconstruction_state = "CONJECTURE"
                if reconstruction_state not in RECONSTRUCTION_STATES:
                    add(errors, "RECONSTRUCTION_UNLABELLED", f"{region_id} reconstruction lacks a typed reconstruction state")
                if reconstruction.get("relationship") not in {None, "RECONSTRUCTS"}:
                    add(errors, "RECONSTRUCTION_RELATION", f"{region_id} reconstruction must use RECONSTRUCTS")
                if reconstruction_state == "WITNESS_RECONSTRUCTION":
                    evidence = referenced(reconstruction.get("evidence_ids", []), emap, errors, f"reconstruction {region_id}")
                    if not {item.get("evidence_class") for item in evidence} & {"other_witness", "historical_translation"}:
                        add(errors, "WITNESS_RECONSTRUCTION_UNSUPPORTED", f"{region_id} lacks registered other-witness evidence")
                audit_blocked_reconstruction(region, emap, errors)
    for claim in claims.values():
        region_id = claim.get("legibility_region_id")
        observational_claim = claim.get("claim_type") == "exact_glyph" or claim.get("claim_layer") in {
            "observation", "diplomatic", "normalized",
        }
        if region_id is not None and states.get(str(region_id)) in {"PAGE_OBSCURED", "PAGE_LOST"} and observational_claim and is_asserted(claim):
            add(errors, "OCCLUDED_GLYPH_CLAIM",
                f"{claim.get('claim_id', '<unnamed>')} asserts an observed claim in physically unreadable {region_id}")
        if region_id is not None and states.get(str(region_id)) in {"PAGE_OBSCURED", "PAGE_LOST"} and claim.get("evidence_state") == "PAGE_VISIBLE":
            add(errors, "OBSCURED_TO_VISIBLE", f"{claim.get('claim_id', '<unnamed>')} promotes {region_id} to PAGE_VISIBLE")
    return states


def audit_final_output_spans(data: dict[str, Any], region_states: dict[str, str], errors: list[str]) -> None:
    """Require typed final rendering for a page region already classified as blocked."""
    output = data.get("output", {})
    if output.get("stage") != "final" or output.get("transcription_mode") not in TRANSCRIPTION_OUTPUT_MODES | {"translation"}:
        return
    blocked = {region_id for region_id, state in region_states.items() if state in {"PAGE_OBSCURED", "PAGE_LOST"}}
    if not blocked:
        return
    spans = output.get("transcription_spans")
    if not isinstance(spans, list):
        add(errors, "OBSCURED_FINAL_OUTPUT_UNTRACKED", "final transcription with obscured regions lacks transcription_spans")
        return
    covered: set[str] = set()
    for index, span in enumerate(spans):
        if not isinstance(span, dict):
            add(errors, "FINAL_SPAN_SHAPE", f"transcription_spans[{index}] is not an object")
            continue
        region_id = str(span.get("region_id", ""))
        if region_id not in blocked:
            continue
        covered.add(region_id)
        layer = span.get("layer")
        state = span.get("evidence_state")
        text = span.get("text")
        if layer in OBSERVATIONAL_OUTPUT_LAYERS:
            if state not in {"PAGE_OBSCURED", "PAGE_LOST"} or not is_observational_placeholder(text):
                add(errors, "OBSCURED_FINAL_OUTPUT_FILLED", f"final {layer} span for {region_id} fills blocked text")
        elif layer == "reconstruction":
            if state != "WITNESS_RECONSTRUCTION":
                add(errors, "FINAL_RECONSTRUCTION_STATE", f"final reconstruction for {region_id} lacks a typed reconstruction state")
            if span.get("relationship") != "RECONSTRUCTS":
                add(errors, "FINAL_RECONSTRUCTION_RELATION", f"final reconstruction for {region_id} must use RECONSTRUCTS")
        else:
            add(errors, "FINAL_SPAN_LAYER", f"final span for {region_id} lacks an observational or reconstruction layer")
    for region_id in blocked - covered:
        add(errors, "OBSCURED_FINAL_SPAN_MISSING", f"final transcription omits typed status for {region_id}")


def audit_bibliographical_claims(
    claims: dict[str, dict[str, Any]], emap: dict[str, dict[str, Any]], errors: list[str]
) -> None:
    """License physical-book claims from their own evidence rather than printing habit."""
    for claim in claims.values():
        ctype = claim.get("claim_type")
        if ctype not in BIBLIOGRAPHICAL_CLAIM_KINDS or not is_asserted(claim):
            continue
        cid = claim.get("claim_id", "<unnamed>")
        evidence = referenced(claim.get("evidence_ids", []), emap, errors, f"bibliographical claim {cid}")
        kinds = {item.get("kind") for item in evidence}
        if ctype == "signature_face":
            if not (kinds & {"signature_mark", "signature_check"}):
                add(errors, "SIGNATURE_FACE_UNSUPPORTED", f"{cid} lacks an observed signature mark")
            if "signature_convention" not in kinds:
                add(errors, "SIGNATURE_CONVENTION_REQUIRED", f"{cid} lacks an established signature convention")
        elif ctype == "catchword_continuity":
            if "catchword" not in kinds:
                add(errors, "CATCHWORD_CONTINUITY_UNSUPPORTED", f"{cid} lacks observed catchword evidence")
        elif ctype in {"quire_size", "gathering_structure", "gathering_formula"}:
            if not (kinds & GATHERING_EVIDENCE_KINDS):
                add(errors, "GATHERING_UNSUPPORTED", f"{cid} cannot derive gathering structure from signature or printing practice alone")
        elif ctype == "conjugacy" and not (kinds & CONJUGACY_EVIDENCE_KINDS):
            add(errors, "CONJUGACY_UNSUPPORTED", f"{cid} lacks physical or verified structural evidence")
        elif ctype == "internal_quire_pagination" and not (kinds & QUIRE_PAGINATION_EVIDENCE_KINDS):
            add(errors, "QUIRE_PAGINATION_UNSUPPORTED", f"{cid} lacks a verified quire sequence or pagination witness")


def physical_history_kind(claim: dict[str, Any]) -> str | None:
    """Return a historical-physical claim kind without recasting visible description."""
    if claim.get("claim_type") == "physical_history":
        return claim.get("physical_history_kind")
    if claim.get("claim_type") in PHYSICAL_HISTORY_CLAIM_KINDS:
        return claim.get("claim_type")
    return None


def audit_physical_history_claims(
    claims: dict[str, dict[str, Any]], emap: dict[str, dict[str, Any]], errors: list[str]
) -> None:
    """Keep visual descriptions from becoming unverified object-history claims."""
    for claim in claims.values():
        cid = claim.get("claim_id", "<unnamed>")
        ctype = claim.get("claim_type")
        history_kind = physical_history_kind(claim)
        if history_kind:
            if history_kind not in PHYSICAL_HISTORY_CLAIM_KINDS:
                add(errors, "PHYSICAL_HISTORY_KIND", f"{cid} has invalid physical-history kind {history_kind!r}")
                continue
            if not is_asserted(claim):
                continue
            evidence = referenced(claim.get("evidence_ids", []), emap, errors, f"physical-history claim {cid}")
            kinds = {item.get("kind") for item in evidence}
            classes = {item.get("evidence_class") for item in evidence}
            if not evidence or not (kinds & PHYSICAL_HISTORY_EVIDENCE_KINDS):
                add(errors, "PHYSICAL_HISTORY_UNSUPPORTED",
                    f"{cid} ({history_kind}) lacks independent documentary, material, or catalog evidence")
            if classes <= {"supplied_image_observation", "inference_reconstruction"}:
                add(errors, "PHYSICAL_HISTORY_NOT_INDEPENDENT",
                    f"{cid} ({history_kind}) turns page appearance into object history")
        elif ctype == "physical_observation" and claim.get("physical_observation_kind") not in VISIBLE_PHYSICAL_CLAIM_KINDS:
            add(errors, "PHYSICAL_OBSERVATION_KIND",
                f"{cid} has invalid visible physical-observation kind {claim.get('physical_observation_kind')!r}")


def critical_output_categories(data: dict[str, Any], claims: dict[str, dict[str, Any]]) -> set[str]:
    """Identify final-output content that must traverse the centralized audit."""
    output = data.get("output", {})
    categories: set[str] = set()
    identity = output.get("identity", {})
    if isinstance(identity, dict) and identity.get("proposed_identity"):
        categories.add("work_identity")
    for claim in claims.values():
        ctype = claim.get("claim_type")
        if ctype in HIGH_RISK and is_asserted(claim):
            categories.add("high_risk_reading")
        if ctype == "work_identity" and is_work_identity_promoted(claim):
            categories.add("work_identity")
        if physical_history_kind(claim) and is_asserted(claim):
            categories.add("physical_history")
        if ctype == "physical_observation" and is_asserted(claim):
            categories.add("physical_observation")
        if ctype in BIBLIOGRAPHICAL_CLAIM_KINDS and is_asserted(claim):
            categories.add("rare_book_claim")
        if ctype == "source_proposition" and claim.get("status") == "verified":
            categories.add("source_verification")
    if data.get("legibility_regions") or output.get("transcription_spans"):
        categories.add("page_evidence")
    relationships = []
    for field in ("direct_reuse_claims", "textual_relationships"):
        values = data.get(field, [])
        if isinstance(values, list):
            relationships.extend(values)
    if any(isinstance(record, dict) and record.get("classification") in TEXTUAL_RELATIONSHIP_CLASSES
           for record in relationships):
        categories.add("textual_relationship")
    return categories


def audit_critical_pre_output_gate(data: dict[str, Any], claims: dict[str, dict[str, Any]], errors: list[str]) -> None:
    """Fail closed when final high-risk content has no recorded central audit."""
    output = data.get("output", {})
    if output.get("stage") != "final":
        return
    required = critical_output_categories(data, claims)
    if not required:
        return
    gate = output.get("critical_claim_audit")
    if not isinstance(gate, dict):
        add(errors, "CRITICAL_AUDIT_REQUIRED", "final high-risk output lacks a centralized critical-claim audit")
        return
    if gate.get("status") != "passed":
        add(errors, "CRITICAL_AUDIT_NOT_PASSED", "centralized critical-claim audit is not recorded as passed")
    if gate.get("fail_closed") is not True:
        add(errors, "CRITICAL_AUDIT_FAIL_CLOSED", "critical audit must record fail_closed: true")
    reviewed = gate.get("reviewed_categories")
    if not isinstance(reviewed, list):
        add(errors, "CRITICAL_AUDIT_CATEGORIES", "critical audit lacks reviewed_categories")
    elif not required.issubset(set(reviewed)):
        add(errors, "CRITICAL_AUDIT_CATEGORIES",
            f"critical audit omits required categories {sorted(required - set(reviewed))}")


def comparator_inspected(relation: dict[str, Any]) -> bool:
    """A textual relation needs an actually inspected comparison passage."""
    return relation.get("comparator_passage_inspected") is True or relation.get("evidence_level") in COMPARATOR_INSPECTION_LEVELS


def audit_textual_relationships(data: dict[str, Any], errors: list[str]) -> None:
    """Reject positive relation labels that have only leads, snippets, or expectations."""
    records: list[dict[str, Any]] = []
    for key in ("direct_reuse_claims", "textual_relationships"):
        values = data.get(key, [])
        if not isinstance(values, list):
            add(errors, "TEXTUAL_RELATIONSHIP_SHAPE", f"{key} must be a list")
            continue
        records.extend(item for item in values if isinstance(item, dict))
    for relation in records:
        classification = relation.get("classification")
        relation_id = relation.get("reuse_id", relation.get("relationship_id", "<unnamed>"))
        if classification in TEXTUAL_RELATIONSHIP_CLASSES and not comparator_inspected(relation):
            add(errors, "COMPARATOR_TEXT_REQUIRED",
                f"relationship {relation_id} classifies {classification} without an inspected comparator passage")
        if classification == "direct_reuse" and relation.get("evidence_level") != "full_text_compared":
            add(errors, "TOC_NOT_REUSE", f"reuse {relation_id} lacks full-text comparison")
        if classification == "direct_reuse" and relation.get("ocr_locator_used") and not relation.get("primary_text_compared"):
            add(errors, "OCR_NOT_PRIMARY_VERIFY", f"reuse {relation_id} uses OCR without primary-text comparison")


# Common publication contract. Native evidence/domain validators retain truth
# licensing; these checks establish accountability, not semantic equivalence.
PUBLICATION_SCHEMA = "hti-publication-contract-1"
PUBLICATION_STATUSES = {"SECURE": 3, "SUPPORTED": 2, "PROVISIONAL": 1, "UNRESOLVED": 0}
NONASSERTIVE_TEXT = frozenset({"", " ", "\n", "\n\n", ".", ",", ";", ":", "(", ")", "[", "]", " - ", "**", "*", "`"})
from hti_core.composition import load as _capability_registry
DOMAIN_FIELDS = {k:tuple(v) for k,v in _capability_registry()["domain_fields"].items()}


def publication_digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def publication_text_digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def publication_need(ok, code, detail=""):
    if not ok:
        raise ValueError("PUBLICATION_" + code + ": " + str(detail))


def publication_table(rows, label):
    publication_need(isinstance(rows, list), "LIST", label)
    out = {}
    for row in rows:
        publication_need(isinstance(row, dict) and isinstance(row.get("id"), str) and row["id"].strip(), "ID", label)
        publication_need(row["id"] not in out, "DUPLICATE", row["id"])
        out[row["id"]] = row
    return out


def publication_ref_key(ref):
    return publication_digest({k: v for k, v in ref.items() if k != "snapshot"})


def selected_domain_ids(checkpoint, domain):
    contract = checkpoint.get("publication_contract")
    publication_need(isinstance(contract, dict), "CONTRACT_REQUIRED")
    return {r["id"] for r in contract["scope"]["domain_outputs"] if r.get("domain") == domain}


def selected_domain_claims(checkpoint, domain):
    selected = selected_domain_ids(checkpoint, domain)
    key, _ = DOMAIN_FIELDS[domain]
    return [c for c in checkpoint.get("claims", []) if c.get("claim_type") == domain and c.get(key) in selected]


def assertion_projection(assertion):
    prefix = {"UNRESOLVED": "Unresolved: ", "PROVISIONAL": "Provisional: "}.get(assertion["status"], "")
    return prefix + assertion["projection"]


def validate_publication_contract(checkpoint, plan=None, publication=None, complete=True):
    c = checkpoint.get("publication_contract")
    publication_need(isinstance(c, dict), "CONTRACT_REQUIRED")
    fields = {"schema", "task_directory", "publication_id", "request_sha256", "work_id", "operation_plan_sha256", "assertions", "derivations", "outcomes", "anchors", "discoveries", "research_plan", "scope", "terminal"}
    publication_need(set(c) == fields and c["schema"] == PUBLICATION_SCHEMA, "CONTRACT_SHAPE")
    publication_need(c["work_id"] == checkpoint.get("work_id") and isinstance(c["task_directory"], str) and bool(c["task_directory"]), "SCOPE")
    publication_need(re.fullmatch(r"[0-9a-f]{32}", c["publication_id"] or "") and re.fullmatch(r"[0-9a-f]{64}", c["request_sha256"] or ""), "BINDING")
    if publication is not None:
        for k in ("task_directory", "publication_id", "request_sha256"):
            publication_need(c[k] == publication[k], "CURRENT_REQUEST", k)
        publication_need(publication.get("operation_plan") is not None and c["operation_plan_sha256"] == publication_digest(publication["operation_plan"]), "OPERATION_SELECTION")
    terminal = c["terminal"]
    publication_need(isinstance(terminal, dict) and set(terminal) == {"preparation_reviewed", "delivery", "success_continuation", "post_success_actions"}, "TERMINAL_SHAPE")
    from terminal_output import DESIGN_R_POLICY
    # Current staging accepts only Design R. Retained predecessor receipt
    # compatibility belongs to task status and verified transport recovery.
    publication_need(terminal == DESIGN_R_POLICY, "TERMINAL_INTENT")
    assertions = publication_table(c["assertions"], "assertions")
    derivations = publication_table(c["derivations"], "derivations")
    anchors = publication_table(c["anchors"], "anchors")
    discoveries = publication_table(c["discoveries"], "discoveries")
    items = publication_table(c["research_plan"], "research plan")
    outcomes = publication_table(c["outcomes"], "outcomes")
    scope = c["scope"]
    publication_need(isinstance(scope, dict) and set(scope) == {"mode", "assertion_ids", "source_bindings", "domain_outputs", "outcome_ids", "retained", "translation_requirement", "required_source_bindings"}, "PUBLICATION_SCOPE")
    publication_need(scope["mode"] in {"FULL", "DELTA"} and scope["translation_requirement"] in {"NONE", "FULL", "CORRECTION"}, "PUBLICATION_SCOPE")
    for label, table in (("assertion_ids", assertions), ("outcome_ids", outcomes)):
        values = scope[label]
        publication_need(isinstance(values, list) and len(values) == len(set(values)) and set(values) <= set(table), "SELECTION", label)
    for key in ("source_bindings", "domain_outputs", "retained", "required_source_bindings"):
        publication_need(isinstance(scope[key], list), "SCOPE_LIST", key)
    publication_need(scope["mode"] != "DELTA" or bool(scope["retained"]), "DELTA_REQUIRES_RETAINED")
    publication_need(all(r in scope["source_bindings"] for r in scope["required_source_bindings"]), "REQUIRED_SOURCE_OMITTED")
    seen_refs = set()
    for ref in scope["source_bindings"] + scope["domain_outputs"]:
        validate_publication_ref(ref)
        key = publication_ref_key(ref)
        publication_need(key not in seen_refs, "DUPLICATE_SELECTION")
        seen_refs.add(key)
    for a in anchors.values():
        required = {"id", "task_directory", "work_id", "kind", "question", "dimension", "source_refs", "proposition_refs", "source_form", "language", "identity_state", "identity_claim_ids", "limitations"}
        publication_need(set(a) == required and a["task_directory"] == c["task_directory"] and a["work_id"] == c["work_id"], "ANCHOR_SCOPE", a["id"])
        publication_need(a["kind"] in {"PAGE", "PASSAGE", "ARGUMENT", "PROPOSITION", "SOURCE_QUESTION"} and a["identity_state"] == checkpoint.get("identity_state", "UNIDENTIFIED"), "ANCHOR_IDENTITY", a["id"])
        publication_need(all(isinstance(a[k], str) and a[k].strip() for k in ("question", "dimension", "source_form", "language")), "ANCHOR_QUESTION", a["id"])
        publication_need(isinstance(a["limitations"], list) and isinstance(a["identity_claim_ids"], list), "ANCHOR_FIELDS")
        publication_need(set(a["identity_claim_ids"]) <= set(checkpoint.get("selected_claim_ids", [])), "ANCHOR_INDEPENDENT_IDENTITY")
        publication_need(isinstance(a["source_refs"], list) and isinstance(a["proposition_refs"], list), "ANCHOR_REFS")
        publication_need(a["kind"] == "SOURCE_QUESTION" or bool(a["source_refs"]), "ANCHOR_SOURCE_REQUIRED")
        publication_need(a["kind"] not in {"ARGUMENT", "PROPOSITION"} or bool(a["proposition_refs"]), "ANCHOR_ARGUMENT_REQUIRED")
        for ref in a["source_refs"] + a["proposition_refs"]:
            validate_publication_ref(ref)
    for d in discoveries.values():
        required = {"id", "locator", "provenance", "anchor_id", "plan_item_id", "materiality", "conclusion_effect", "access_status", "attempts", "inspection_status", "inspection", "disposition", "reason", "comparator_ref"}
        publication_need(set(d) == required and d["anchor_id"] in anchors and d["plan_item_id"] in items, "DISCOVERY_LINK", d["id"])
        publication_need(all(isinstance(d[k], str) and d[k].strip() for k in ("locator", "provenance", "materiality", "conclusion_effect")), "DISCOVERY_PROVENANCE")
        publication_need(d["access_status"] in {"UNKNOWN", "ACCESSIBLE", "ACQUIRED", "INACCESSIBLE"} and d["inspection_status"] in {"LEAD", "INSPECTED", "INACCESSIBLE"}, "DISCOVERY_STATE")
        publication_need(d["disposition"] in {"OPEN", "VERIFIED", "REJECTED", "UNRESOLVED"} and isinstance(d["attempts"], list), "DISCOVERY_DISPOSITION")
        for attempt in d["attempts"]:
            publication_need(isinstance(attempt, dict) and set(attempt) == {"route", "outcome", "provenance"} and all(isinstance(v, str) and v.strip() for v in attempt.values()), "ACCESS_ATTEMPT")
        if d["inspection_status"] == "INSPECTED":
            publication_need(isinstance(d["inspection"], dict) and set(d["inspection"]) == {"content_ref", "relevant_passage", "inspection_outcome"} and bool(d["inspection"]["relevant_passage"]) and bool(d["inspection"]["inspection_outcome"]), "INSPECTION_REQUIRED")
            validate_publication_ref(d["inspection"]["content_ref"])
            publication_need(d["inspection"]["content_ref"]["kind"] != "QUESTION", "INSPECTION_NOT_QUESTION")
        else:
            publication_need(d["inspection"] is None and d["comparator_ref"] is None and d["disposition"] != "VERIFIED", "LEAD_NOT_EVIDENCE")
        if d["comparator_ref"] is not None:
            validate_publication_ref(d["comparator_ref"])
            publication_need(d["inspection_status"] == "INSPECTED" and d["comparator_ref"]["kind"] == "DOMAIN_OUTPUT", "INSPECTED_COMPARATOR_REQUIRED")
        if d["inspection_status"] == "INACCESSIBLE" or d["access_status"] == "INACCESSIBLE":
            publication_need(bool(d["attempts"]) and bool(d["reason"]), "UNATTEMPTED_INACCESSIBLE")
        if d["disposition"] != "OPEN":
            publication_need(isinstance(d["reason"], str) and bool(d["reason"].strip()), "DISCOVERY_REASON")
    for item in items.values():
        required = {"id", "target_question", "anchor_id", "uncertain_question", "why_material", "possible_conclusion_effect", "evidence_needed", "discriminating_test", "priority", "discovery_ids", "access_attempts", "inspection_outcomes", "conclusion_effect", "completion_state", "stopping_reason", "provenance", "native_plan_ref"}
        publication_need(set(item) == required and item["anchor_id"] in anchors, "PLAN_SHAPE", item["id"])
        for k in ("target_question", "uncertain_question", "why_material", "possible_conclusion_effect", "evidence_needed", "discriminating_test", "priority", "provenance"):
            publication_need(isinstance(item[k], str) and bool(item[k].strip()), "PLAN_DECISION_CONTEXT", k)
        publication_need(isinstance(item["discovery_ids"], list) and set(item["discovery_ids"]) <= set(discoveries), "PLAN_DISCOVERIES")
        publication_need(all(discoveries[k]["plan_item_id"] == item["id"] for k in item["discovery_ids"]), "PLAN_BACKLINK")
        publication_need({d["id"] for d in discoveries.values() if d["plan_item_id"] == item["id"]} == set(item["discovery_ids"]), "PLAN_SUPPRESSED_LEAD")
        publication_need(isinstance(item["access_attempts"], list) and isinstance(item["inspection_outcomes"], list), "PLAN_ATTEMPTS")
        publication_need(item["completion_state"] in {"COMPLETED", "PARTIAL", "UNRESOLVED", "BLOCKED"} and isinstance(item["stopping_reason"], str) and bool(item["stopping_reason"].strip()), "PLAN_STOPPING")
        if item["native_plan_ref"] is not None:
            validate_publication_ref(item["native_plan_ref"])
        for did in item["discovery_ids"]:
            d = discoveries[did]
            publication_need(not (d["materiality"] == "DECISION_CHANGING" and d["access_status"] in {"ACCESSIBLE", "ACQUIRED"} and d["inspection_status"] != "INSPECTED" and not (d["reason"] and item["completion_state"] != "COMPLETED")), "CONSEQUENTIAL_INSPECTION", did)
        if item["completion_state"] == "COMPLETED":
            publication_need(bool(item["conclusion_effect"]) and all(discoveries[k]["inspection_status"] == "INSPECTED" or discoveries[k]["materiality"] != "DECISION_CHANGING" for k in item["discovery_ids"]), "PLAN_UNADJUDICATED")
    for obj in list(assertions.values()) + list(derivations.values()):
        for k in ("projection", "purpose", "source_layer", "ownership", "scope"):
            publication_need(isinstance(obj.get(k), str) and bool(obj[k].strip()), "ASSERTION_FIELD", k)
        publication_need(obj.get("projection_sha256") == publication_text_digest(obj["projection"]), "PROJECTION_HASH", obj["id"])
        publication_need(obj.get("status") in PUBLICATION_STATUSES and obj.get("currentness") == "CURRENT", "ASSERTION_CURRENT", obj["id"])
        publication_need(isinstance(obj.get("facets"), dict) and isinstance(obj.get("qualifiers"), list) and isinstance(obj.get("limitations"), list), "ASSERTION_QUALIFICATIONS")
        publication_need(isinstance(obj.get("parents"), list) and bool(obj["parents"]), "ANCESTRY_REQUIRED", obj["id"])
        for ref in obj["parents"]:
            validate_publication_ref(ref)
        if any(ref["kind"] == "QUESTION" for ref in obj["parents"]):
            publication_need(obj["status"] == "UNRESOLVED", "QUESTION_NOT_POSITIVE", obj["id"])
    for a in assertions.values():
        publication_need(a.get("form") in {"CANONICAL", "DERIVATION", "UNRESOLVED"}, "ASSERTION_FORM")
        if a["form"] == "CANONICAL":
            publication_need(len(a["parents"]) == 1 and a.get("derivation_id") is None, "CANONICAL_PARENT")
        else:
            publication_need(a.get("derivation_id") in derivations, "REVIEWED_DERIVATION_REQUIRED")
            d = derivations[a["derivation_id"]]
            for key in ("projection", "projection_sha256", "parents", "purpose", "source_layer", "ownership", "scope", "facets", "qualifiers", "limitations", "status", "currentness"):
                publication_need(a[key] == d[key], "DERIVATION_PROJECTION", a["id"])
            if a["form"] == "UNRESOLVED":
                publication_need(a["status"] == "UNRESOLVED", "UNRESOLVED_PROMOTION")
    for d in derivations.values():
        publication_need(type(d.get("revision")) is int and d["revision"] > 0, "DERIVATION_REVISION")
        publication_need(isinstance(d.get("counterevidence"), list) and isinstance(d.get("uncertainty_inheritance"), list), "DERIVATION_INHERITANCE")
        for ref in d["counterevidence"]:
            validate_publication_ref(ref)
        review = d.get("review")
        required = {"reviewer", "distinct_pass", "publication_id", "request_sha256", "payload_sha256", "parents_sha256", "purpose", "retained_qualifications", "source_ownership_fidelity", "material_changes", "unresolved_conflicts", "attestation"}
        publication_need(isinstance(review, dict) and set(review) == required, "REVIEW_REQUIRED", d["id"])
        publication_need(review["reviewer"] in {"CLAUDE", "HUMAN"} and review["distinct_pass"] is True and review["retained_qualifications"] is True and review["source_ownership_fidelity"] is True, "REVIEW_ATTESTATION")
        for k, value in (("publication_id", c["publication_id"]), ("request_sha256", c["request_sha256"]), ("payload_sha256", publication_digest({k:v for k,v in d.items() if k != "review"})), ("parents_sha256", publication_digest(d["parents"])), ("purpose", d["purpose"])):
            publication_need(review[k] == value, "REVIEW_BINDING", k)
        publication_need(isinstance(review["material_changes"], str) and isinstance(review["unresolved_conflicts"], list) and isinstance(review["attestation"], str) and bool(review["attestation"].strip()), "REVIEW_ACCOUNT")
        publication_need(not review["unresolved_conflicts"] or d["status"] in {"PROVISIONAL", "UNRESOLVED"}, "CONFLICT_NOT_SECURE")
    for o in outcomes.values():
        required = {"id", "status", "result_refs", "assertion_ids", "plan_item_ids", "reason", "blocked_by", "limitations"}
        publication_need(set(o) == required and o["status"] in {"COMPLETED", "PARTIAL", "UNRESOLVED", "BLOCKED"}, "OPERATION_TERMINAL", o["id"])
        publication_need(isinstance(o["result_refs"], list) and isinstance(o["assertion_ids"], list) and set(o["assertion_ids"]) <= set(scope["assertion_ids"]), "OPERATION_RESULTS")
        for ref in o["result_refs"]:
            validate_publication_ref(ref)
        publication_need(isinstance(o["plan_item_ids"], list) and set(o["plan_item_ids"]) <= set(items) and isinstance(o["blocked_by"], list) and set(o["blocked_by"]) <= set(outcomes) and o["id"] not in o["blocked_by"], "OPERATION_DEPENDENCY")
        publication_need(isinstance(o["limitations"], list), "OPERATION_LIMITATIONS")
        if o["status"] in {"COMPLETED", "PARTIAL"}:
            publication_need(bool(o["result_refs"]), "CURRENT_RESULT_REQUIRED", o["id"])
        if o["status"] != "COMPLETED":
            publication_need(isinstance(o["reason"], str) and bool(o["reason"].strip()), "INCOMPLETE_REASON", o["id"])
        if o["status"] != "COMPLETED":
            publication_need(any(o["reason"] in assertions[k]["projection"] and assertions[k]["status"] in {"UNRESOLVED","PROVISIONAL"} for k in o["assertion_ids"]), "GOVERNED_INCOMPLETE_REASON", o["id"])
        if o["status"] == "BLOCKED":
            publication_need(bool(o["blocked_by"]) and all(outcomes[k]["status"] != "COMPLETED" for k in o["blocked_by"]), "BLOCKED_PREREQUISITE")
        if o["status"] == "COMPLETED":
            publication_need(not o["blocked_by"] and all(items[k]["completion_state"] == "COMPLETED" for k in o["plan_item_ids"]), "UNACCOUNTED_MATERIAL_BLOCKER")
    if publication is not None:
        steps = {s["step_id"]:s for s in publication["operation_plan"]["operations"]}
        publication_need(bool(steps) and set(outcomes) == set(steps) and set(scope["outcome_ids"]) == set(steps), "SELECTED_OPERATION_OMITTED")
        for sid, step in steps.items():
            o = outcomes[sid]
            publication_need(set(o["blocked_by"]) <= set(step["depends_on"]), "UNSELECTED_BLOCKER")
            if o["status"] == "COMPLETED":
                publication_need(all(outcomes[k]["status"] == "COMPLETED" for k in step["depends_on"]), "PREREQUISITE_NOT_COMPLETE")
    if plan is not None:
        publication_need(plan.get("publication_contract_sha256") == publication_digest(c), "PLAN_CONTRACT_BINDING")
    return c


def validate_publication_ref(ref):
    publication_need(isinstance(ref, dict) and isinstance(ref.get("id"), str) and bool(ref["id"].strip()), "PARENT_REFERENCE")
    kinds = {"EVIDENCE", "CLAIM", "SOURCE_SPAN", "PROPOSITION", "PRG_RELATION", "HRG_RELATION", "CONSUMER", "DOMAIN_OUTPUT", "QUESTION", "SOURCE_STATUS", "NATIVE_PLAN"}
    publication_need(ref.get("kind") in kinds and isinstance(ref.get("snapshot"), str) and re.fullmatch(r"[0-9a-f]{64}", ref["snapshot"]), "PARENT_SNAPSHOT")
    base = {"kind", "id", "snapshot"}
    extra = {"SOURCE_SPAN": {"span_ids", "purpose"}, "DOMAIN_OUTPUT": {"domain"}, "NATIVE_PLAN": {"file", "pointer"}}.get(ref["kind"], set())
    publication_need(set(ref) == base | extra, "REFERENCE_SHAPE")
    if ref["kind"] == "SOURCE_SPAN":
        publication_need(isinstance(ref["span_ids"], list) and len(ref["span_ids"]) == len(set(ref["span_ids"])) and bool(ref["purpose"]), "SOURCE_REFERENCE")
    if ref["kind"] == "DOMAIN_OUTPUT":
        publication_need(ref["domain"] in DOMAIN_FIELDS, "DOMAIN_REFERENCE")


def audit_publication_contract(checkpoint, plan=None):
    errors = []
    try:
        validate_publication_contract(checkpoint, plan)
        output = checkpoint.get("output", {})
        if output.get("stage") == "final":
            response = output.get("final_response", {})
            text = response.get("text")
            roles = response.get("publication_roles")
            publication_need(isinstance(text, str) and isinstance(roles, list), "OUTPUT_ROLES_REQUIRED")
            position = 0
            c = checkpoint["publication_contract"]
            assertions = publication_table(c["assertions"], "assertions")
            found = []
            for role in roles:
                publication_need(isinstance(role, dict) and type(role.get("start")) is int and role["start"] == position and type(role.get("end")) is int and position < role["end"] <= len(text), "OUTPUT_ROLE_COVERAGE")
                chunk = text[position:role["end"]]
                publication_need(role.get("sha256") == publication_text_digest(chunk), "OUTPUT_ROLE_HASH")
                if role.get("kind") == "ASSERTION":
                    aid = role.get("assertion_id")
                    publication_need(aid in assertions and chunk == assertion_projection(assertions[aid]), "EXACT_ASSERTION_PROJECTION")
                    found.append(aid)
                else:
                    publication_need(role.get("kind") in {"LAYOUT", "SOURCE", "GENERATED"}, "OUTPUT_ROLE")
                    if role["kind"] == "LAYOUT":
                        from finalize_response import SECTION_HEADINGS
                        headings = {"**" + x + "**\n\n" for x in SECTION_HEADINGS.values()} | {"**Translation**\n\n","**Confidence and identity status**\n\n","**Supplied-page gaps**\n\n"}
                        publication_need(chunk in NONASSERTIVE_TEXT or chunk in headings or chunk.isspace(), "LAYOUT_NOT_ASSERTION")
                position = role["end"]
            publication_need(position == len(text) and set(found) == set(c["scope"]["assertion_ids"]) and len(found) == len(set(found)), "OUTPUT_COMPLETE_COVERAGE")
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        add(errors, "PUBLICATION_CONTRACT", str(exc))
    return errors


def audit_checkpoint(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not data.get("work_id"):
        add(errors, "WORK_ID", "work_id is required")
    emap = evidence_map(data, errors)
    claims: dict[str, dict[str, Any]] = {}
    for index, claim in enumerate(data.get("claims", [])):
        if not isinstance(claim, dict):
            add(errors, "CLAIM_SHAPE", f"claims[{index}] is not an object")
            continue
        cid = claim.get("claim_id")
        if not cid:
            add(errors, "CLAIM_ID", f"claims[{index}] lacks claim_id")
            continue
        if cid in claims:
            add(errors, "CLAIM_DUPLICATE", f"duplicate claim_id {cid}")
        claims[cid] = claim
        audit_claim(claim, emap, errors)
    audit_identity(data, claims, errors)
    audit_identity_hypotheses(data, errors)

    orientation = data.get("orientation", {})
    if orientation.get("status") in {"asserted", "secure", "established"}:
        ev = referenced(orientation.get("evidence_ids", []), emap, errors, "orientation")
        if not ({e.get("kind") for e in ev} & ORIENTATION_KINDS):
            add(errors, "ORIENTATION_UNSUPPORTED", "orientation object lacks valid structural evidence")

    provenance = data.get("provenance", {})
    if provenance.get("status") in {"asserted", "secure", "established"}:
        ev = referenced(provenance.get("evidence_ids", []), emap, errors, "provenance")
        if not ({e.get("kind") for e in ev} & COPY_SPECIFIC_KINDS):
            add(errors, "PROVENANCE_UNSUPPORTED", "provenance object lacks copy-specific evidence")

    for variant in data.get("witness_variants", []):
        if variant.get("adopted_reading") == variant.get("other_witness_reading") and variant.get("supplied_page_reading") != variant.get("other_witness_reading"):
            if not variant.get("replacement_explicit") or not variant.get("reason"):
                add(errors, "SILENT_WITNESS_OVERWRITE", f"variant {variant.get('variant_id', '<unnamed>')} silently replaces supplied reading")

    region_states = audit_legibility_regions(data, claims, emap, errors)
    audit_final_output_spans(data, region_states, errors)
    audit_bibliographical_claims(claims, emap, errors)
    audit_physical_history_claims(claims, emap, errors)
    audit_textual_relationships(data, errors)

    for escalation in data.get("full_text_escalations", []):
        available = set(escalation.get("available_resources", []))
        attempted = set(escalation.get("attempted_resources", []))
        if escalation.get("conclusion") == "full_text_unavailable" and available - attempted:
            add(errors, "FULL_TEXT_ROUTE_UNTRIED", f"escalation {escalation.get('escalation_id', '<unnamed>')} leaves accessible routes untried")
        if escalation.get("resource_available") is True and not attempted:
            add(errors, "FULL_TEXT_ESCALATION_REQUIRED", f"escalation {escalation.get('escalation_id', '<unnamed>')} has accessible text but no recorded access attempt")

    output = data.get("output", {})
    if output.get("stage") == "final" and output.get("uncertainties_visible") is False:
        unresolved = [c for c in claims.values() if c.get("confidence") in {"unresolved", "illegible", "possible"}]
        if unresolved:
            add(errors, "UNCERTAINTY_ERASED", "final output hides unresolved claims")

    audit_long_s_gate(data, claims, errors)
    audit_final_identity_output(data, claims, emap, errors)
    audit_finalization_receipt(data, claims, errors)
    audit_final_response_identity_manifest(data, claims, emap, errors)
    if data.get("publication_contract", {}).get("publication_id") or output.get("stage") == "final":
        errors.extend(audit_publication_contract(data))

    return errors


def audit_pre_output(data: dict[str, Any]) -> list[str]:
    """Run the single final gate that orchestrates all critical claim checks.

    It validates the evidence checkpoint and the serialized final-response
    identity manifest that must be assembled before high-risk output is emitted.
    """
    errors = audit_checkpoint(data)
    output = data.get("output", {})
    if output.get("stage") == "final" and output.get("final_response") is None:
        add(errors, "FINAL_RESPONSE_MANIFEST_REQUIRED",
            "central final audit requires serialized final_response before emission")
    claims = {
        claim.get("claim_id"): claim
        for claim in data.get("claims", [])
        if isinstance(claim, dict) and claim.get("claim_id")
    }
    audit_critical_pre_output_gate(data, claims, errors)
    return errors


def audit_sources(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for index, src in enumerate(data.get("sources", [])):
        sid = src.get("source_id", f"source[{index}]")
        status = src.get("status", "lead")
        if status == "proposition_verified":
            if not src.get("passage_locator") or not src.get("passage_inspected") or not src.get("proposition_found"):
                add(errors, "PROPOSITION_UNVERIFIED", f"{sid} is verified without inspected passage and proposition")
        if src.get("source_type") == "legal" and status == "proposition_verified":
            if not src.get("printed_citation") or not src.get("normalized_location"):
                add(errors, "LEGAL_FIELDS", f"{sid} lacks printed and normalized legal citations")
    if data.get("output", {}).get("stage") == "final":
        claimed = data.get("output", {}).get("all_sources_verified")
        unresolved = any(s.get("status") != "proposition_verified" for s in data.get("sources", []))
        if claimed is True and unresolved:
            add(errors, "SOURCE_OVERCLAIM", "final output says all sources verified while unresolved sources remain")
    return errors


def long_s_tokens(text: str) -> dict[str, Any]:
    tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿſẛæœÆŒ]+", text)
    checks = []
    for idx, token in enumerate(tokens, 1):
        if "ſ" in token or "ẛ" in token or "f" in token or "F" in token:
            checks.append({
                "token_id": f"T{idx:04d}",
                "visible": token,
                "diplomatic": token,
                "normalized_candidate": token.replace("ſ", "s").replace("ẛ", "s"),
                "requires_manual_check": True,
                "resolution": None,
                "evidence_ids": [],
            })
    return {"schema_version": "0.1", "checks": checks}


def audit_long_s(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    resolutions = {"long_s", "genuine_f", "round_s", "unresolved", "s", "f", "not_applicable"}
    for check in data.get("checks", []):
        resolution = check.get("resolution")
        if check.get("requires_manual_check") and resolution not in resolutions - {"unresolved"}:
            add(errors, "LONG_S_UNRESOLVED", f"{check.get('token_id', '<unnamed>')} is unresolved")
            continue
        if resolution not in resolutions:
            add(errors, "LONG_S_RESOLUTION", f"{check.get('token_id', '<unnamed>')} has invalid resolution")
            continue
        diplomatic = check.get("diplomatic", check.get("visible", ""))
        normalized = check.get("normalized", check.get("normalized_candidate", ""))
        if resolution in {"long_s", "s"}:
            if "ſ" not in diplomatic and "ẛ" not in diplomatic:
                add(errors, "LONG_S_DIPLOMATIC", f"{check.get('token_id', '<unnamed>')} does not preserve visible long s")
            if "ſ" in normalized or "ẛ" in normalized or "s" not in normalized:
                add(errors, "LONG_S_NORMALIZATION", f"{check.get('token_id', '<unnamed>')} lacks a stated long-s normalization")
        if resolution in {"genuine_f", "f"}:
            if "f" not in diplomatic and "F" not in diplomatic:
                add(errors, "GENUINE_F_DIPLOMATIC", f"{check.get('token_id', '<unnamed>')} does not preserve genuine f")
            if "f" not in normalized and "F" not in normalized:
                add(errors, "GENUINE_F_NORMALIZATION", f"{check.get('token_id', '<unnamed>')} changes genuine f")
        if resolution == "round_s":
            if "s" not in diplomatic and "S" not in diplomatic:
                add(errors, "ROUND_S_DIPLOMATIC", f"{check.get('token_id', '<unnamed>')} does not preserve round s")
            if "s" not in normalized and "S" not in normalized:
                add(errors, "ROUND_S_NORMALIZATION", f"{check.get('token_id', '<unnamed>')} changes round s")
    return errors


def emit(errors: list[str], json_output: bool = False) -> int:
    if json_output:
        print(json.dumps({"ok": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    elif errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
    else:
        print("PASS")
    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    check = sub.add_parser("check", help="audit an evidence checkpoint")
    check.add_argument("path", type=Path)
    check.add_argument("--json", action="store_true")
    pre_output = sub.add_parser("pre-output", help="run the centralized final-output critical-claim audit")
    pre_output.add_argument("path", type=Path)
    pre_output.add_argument("--json", action="store_true")
    source = sub.add_parser("source", help="audit a source checkpoint")
    source.add_argument("path", type=Path)
    source.add_argument("--json", action="store_true")
    ls = sub.add_parser("long-s", help="generate or audit long-s token checks")
    ls.add_argument("path", type=Path)
    ls.add_argument("--text", action="store_true", help="treat input as text and emit a checklist")
    ls.add_argument("--output", type=Path)
    ls.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return 2
    try:
        if args.command == "check":
            return emit(audit_checkpoint(load_json(args.path)), args.json)
        if args.command == "pre-output":
            return emit(audit_pre_output(load_json(args.path)), args.json)
        if args.command == "source":
            return emit(audit_sources(load_json(args.path)), args.json)
        if args.command == "long-s" and args.text:
            result = long_s_tokens(args.path.read_text(encoding="utf-8"))
            rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
            if args.output:
                args.output.write_text(rendered, encoding="utf-8")
            else:
                print(rendered, end="")
            return 0
        if args.command == "long-s":
            return emit(audit_long_s(load_json(args.path)), args.json)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
