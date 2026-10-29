#!/usr/bin/env python3
"""Complete Scholar View from one compact public task file.

This is a production-interface adapter. It expands a compact Scholar View task
into the canonical evidence checkpoint and response plan, then delegates to the
unchanged evidence audit and final renderer. It does not weaken or bypass any
validation gate.
"""
from __future__ import annotations

import argparse
import copy
import difflib
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

import evidence_audit
import finalize_response
import task_state
import terminal_output

TASK: Path
CHECKPOINT: Path
RESPONSE_PLAN: Path
LONG_S_CHECK: Path

TASK_SCHEMA_VERSION = "0.1"
PAGE_EVIDENCE_ID = "E-SUPPLIED-PAGE"
WORK_IDENTITY_CLAIM_ID = "C-WORK-IDENTITY"
SECTION_ORDER = [
    "supplied_text",
    "rare_book_notes",
    "diplomatic_latin",
    "normalized_latin",
    "textual_uncertainties",
    "witness_comparison",
    "source_notes",
    "theological_loci",
    "exegetical_method",
    "notes",
    "citation",
    "research",
]
REQUIRED_SECTIONS = {
    "rare_book_notes",
    "diplomatic_latin",
    "normalized_latin",
    "textual_uncertainties",
    "theological_loci",
    "exegetical_method",
}
ENTITY_MARKER_RE = re.compile(r"\{\{entity:([A-Za-z0-9_.-]+)\}\}")
CLAIM_MARKER_RE = re.compile(r"\{\{claim:([A-Za-z0-9_.-]+)\}\}")
STRUCTURED_MARKER_RE = re.compile(r"\{\{(entity|claim):([A-Za-z0-9_.-]+)\}\}")
SCRIPT_TOKEN_RE = re.compile(r"[\u0370-\u03FF\u1F00-\u1FFF\u0590-\u05FF]+")
BACKTICK_OR_QUOTE_RE = re.compile(
    r"`([^`\n]+)`|\"([^\"\n]+)\"|“([^”\n]+)”|‘([^’\n]+)’|(?<!\w)'([^'\n]+)'(?!\w)"
)
RARE_BOOK_FUNCTION_RE = re.compile(
    r"\b(?:used\s+for|serves?\s+as|functions?\s+as|keyed\s+to|cross[- ]referenc(?:e|es|ed|ing))\b",
    re.IGNORECASE,
)
ANALYTICAL_CLAIM_TYPES = {
    "textual_reading",
    "variant_reading",
    "witness_reading",
    "source_attribution",
    "historical_referent",
    "page_named_identification",
    "feature_function",
    "foreign_token_gloss",
}
ANALYTICAL_CLAIM_STATUSES = {"supported", "inference", "unresolved"}
FOREIGN_LANGUAGES = {"greek", "hebrew"}
FOREIGN_READING_STATUSES = {"secure", "probable", "uncertain", "unresolved"}
GLOSS_STATUSES = {"verified", "unresolved", "inconsistent"}
REFERENT_IDENTIFICATION_STATUSES = {
    "explicit_page_name",
    "independently_verified",
    "inferred",
    "unresolved",
}
WITNESS_STATUSES = {"completed", "unavailable", "declined"}
FOREIGN_SOURCE_LAYERS = {"supplied_page", "supplied_text", "comparator", "external_authority"}
WORK_IDENTITY_EVIDENCE_CLASSES = {"bibliography", "other_witness", "supplied_image_observation"}
LONG_S_RESOLUTIONS = {"long_s", "genuine_f", "round_s"}


class CompactTaskError(ValueError):
    pass


def allowed(values: set[str] | list[str]) -> str:
    return ", ".join(sorted(values))


def interface_contract() -> dict[str, Any]:
    """Expose the complete compact public vocabulary without implementation archaeology."""
    role_scopes = {role: sorted(scopes) for role, scopes in sorted(finalize_response.ROLE_SCOPES.items())}
    return {
        "schema_version": TASK_SCHEMA_VERSION,
        "source_anchor": "For non-image Scholar View bind representation_id and evidence_id to the actual primary source in source-integrity.json; supply sections.supplied_text exactly, no photographed diplomatic or physical apparatus, and a governed PARTIAL outcome with visible unavailable-image limitations. Image tasks retain exact locus/image and E-SUPPLIED-PAGE binding.",
        "literal_unicode": "Use literal UTF-8 scholarly text. Do not hand-encode ordinary text with remembered Unicode escape sequences.",
        "evidence_classes": sorted(evidence_audit.EVIDENCE_CLASSES),
        "identity_states": list(evidence_audit.IDENTITY_STATES),
        "identity_verification_statuses": sorted(evidence_audit.IDENTITY_VERIFICATION_STATUSES),
        "identity_evidence_kinds": sorted(evidence_audit.WORK_ID_DISCRIMINATORS),
        "work_identity_evidence_classes": sorted(WORK_IDENTITY_EVIDENCE_CLASSES),
        "identity_contract": {
            "established_requires": ["name", "evidence_ids", "external_verification"],
            "each_identity_evidence_requires": ["identity_admissible: true", "provenance", "discriminating kind"],
            "evidence_classes": sorted(WORK_IDENTITY_EVIDENCE_CLASSES),
        },
        "entity_roles": sorted(finalize_response.ENTITY_ROLES),
        "entity_scopes": sorted(finalize_response.ENTITY_SCOPES),
        "entity_role_scopes": role_scopes,
        "entity_contract": {
            "required": ["entity_id", "role", "scope", "display", "evidence_ids"],
            "page_referent_when_display_differs": ["page_token or page_name_form", "identification_status", "identification_evidence_ids when independently_verified"],
            "page_referent_field_rule": "explicit_page_name uses page_name_form; independently_verified uses page_token plus identification_evidence_ids; inferred/unresolved use the visible page_token that prompted the inference.",
            "comparator_requires": ["distinct target_work_id"],
        },
        "witness_statuses": sorted(WITNESS_STATUSES),
        "comparator_characterization_contract": {
            "completed_requires": "witness_comparison.comparisons[]: supplied_text, comparator_text, evidence_id, characterization; the comparator evidence records the exact inspected_passage.",
            "orthographic_only": "Conservative token equality after case, accent, long-s, u/v, i/j, and ligature normalization; never infer semantic equivalence. An orthography-only claim across a passage requires comparison_scope: entire_claimed_passage, claimed_passage copied from the supplied transcription, and full matching comparator evidence; every comparison must be orthographic_only.",
            "other_values": ["substantive_difference", "unresolved"],
        },
        "analytical_claim_types": sorted(ANALYTICAL_CLAIM_TYPES),
        "analytical_claim_statuses": sorted(ANALYTICAL_CLAIM_STATUSES),
        "analytical_claim_contract": {
            "required": ["claim_id", "claim_type", "status", "text", "evidence_ids"],
            "textual_reading_requires": ["reading"],
            "historical_referent_requires": ["entity_id"],
            "foreign_token_gloss_requires": ["token_id"],
            "evidence_free_inference_requires": ["basis"],
            "entity_markers_in_text": "Supported. Registered {{entity:ENTITY-ID}} markers are resolved before claim validation and recorded as entity_ids.",
            "claim_marker_semantics": "{{claim:CLAIM-ID}} expands to the full rendered claim text. Use the marker as the claim phrase or sentence, not as a citation after duplicate prose.",
        },
        "foreign_languages": sorted(FOREIGN_LANGUAGES),
        "foreign_source_layers": sorted(FOREIGN_SOURCE_LAYERS),
        "foreign_reading_statuses": sorted(FOREIGN_READING_STATUSES),
        "foreign_gloss_statuses": sorted(GLOSS_STATUSES),
        "foreign_language_token_contract": {
            "required": ["token_id", "language", "form", "source_layer", "reading_status", "reading_evidence_ids"],
            "optional_alternate_forms": "alternate_forms may list diacritic-only alternatives for the same underlying letter sequence. They are aliases of one token record, not additional supplied-page witnesses or separate lexemes.",
            "alternate_form_rule": "Every alternate form must reduce to exactly the same underlying letters as form after Unicode decomposition and removal of combining marks.",
            "supplied_page_requires": [f"reading_evidence_ids includes {PAGE_EVIDENCE_ID}", "checked_against_supplied_image: true"],
            "gloss_requires": ["gloss", "gloss_status", "gloss_evidence_ids", "gloss_checked_against_token: true"],
            "nonsecure_verified_gloss_requires": ["gloss_preserves_uncertainty: true"],
            "evidence_role_rule": "reading_evidence_ids establish form or reading; gloss_evidence_ids establish meaning. Translation evidence may support a gloss but does not establish the supplied-page glyph.",
        },
        "referent_identification_statuses": sorted(REFERENT_IDENTIFICATION_STATUSES),
        "long_s_review_contract": {
            "reviewed_against_supplied_image": "Set true only after a supplied-image s/f review and after visually adjudicating every item that --prepare-long-s reports as requiring review.",
            "checklist_file": "Automatically located in the selected task directory; omit this field from long_s_review.",
            "resolution_values": sorted(LONG_S_RESOLUTIONS),
            "ownership": "The helper derives token IDs, ordering, normalized pairings, and ordinary resolution categories. Do not hand-populate the checklist.",
            "workflow": "Run --prepare-long-s. If manual_review_required is nonzero, inspect only those reported cross-layer s/f mismatches against the supplied image, correct diplomatic or normalized text, and rerun. The prepared checklist hashes bind review to the exact diplomatic and normalized Latin. Unrelated non-Latin edits do not invalidate it; a Latin edit requires --prepare-long-s again.",
        },
        "textual_uncertainty_contract": {
            "model_authors": "Concrete non-foreign textual uncertainties only; use [] when none are present.",
            "foreign_reading_status": "Do not restate foreign-token certainty in free prose. The adapter derives a canonical summary from foreign_language_tokens[].reading_status.",
        },
        "selected_claim_ids_contract": "Identity selection only. Ordinary WORK_ESTABLISHED Scholar View should leave selected_claim_ids empty; the helper adds the work-identity claim automatically. Analytical claims are selected by actual {{claim:CLAIM-ID}} marker use and do not belong in selected_claim_ids.",
        "analytical_quote_rule": "Quotation marks in analytical sections are reserved for literal supplied-page wording. English glosses or paraphrases should be unquoted or rendered through a licensed analytical claim; the preflight reports all currently detectable quoted-form problems together.",
        "validation_diagnostics": "Final completion runs an aggregate preflight first and reports independent current blockers together where dependencies permit; fix the reported batch before rerunning.",
        "rare_book_rule": "Visible features may be described directly. Explicit functional language such as used for, serves as, functions as, keyed to, or cross-referencing must be rendered through a typed feature_function analytical claim. Bibliographical format (folio/quarto/etc.), binding history, provenance, or other non-visible conclusions require separately licensed evidence; apparent physical size does not establish bibliographical format.",
        "examples": {
            "evidence": {"evidence_id": "EV-1", "evidence_class": "other_witness", "kind": "full_text_passage", "independence_group": "witness:1", "description": "Inspected comparator passage.", "passage_inspected": True, "inspected_passage": "Exact passage copied from inspected witness."},
            "entity": {"entity_id": "ENTITY-1", "role": "historical_name", "scope": "other_noncurrent", "display": "Historical Name", "evidence_ids": ["EV-1"]},
            "foreign_language_token": {"token_id": "FT-1", "language": "greek", "form": "ἀλλά", "source_layer": "supplied_page", "reading_status": "secure", "reading_evidence_ids": [PAGE_EVIDENCE_ID], "checked_against_supplied_image": True, "gloss": "rather", "gloss_status": "verified", "gloss_evidence_ids": ["EV-1"], "gloss_checked_against_token": True},
            "analytical_claim": {"claim_id": "CLAIM-1", "claim_type": "witness_reading", "status": "supported", "text": "The inspected comparator has the same reading.", "evidence_ids": ["EV-1"]},
        },
        "publication_contract": {"schema": evidence_audit.PUBLICATION_SCHEMA, "mandatory": True, "review": "Carry actual distinct-pass attestation; the adapter never invents review.", "entities": "Resolve names in the reviewed payload and bind entity_ids; standalone entities never license a sentence.", "passage_marker": "{{assertion:ASSERTION-ID}}", "terminal": "DESIGN_R_PUBLISHER_SELECTED / RELAY_COMMITTED_RESPONSE_AND_STOP; one bound Read only in READ_COMMITTED_FILE mode", "retained_scope": "Research delta retains source accounting and publishes selected material only."},
        "markers": {"entity": "{{entity:ENTITY-ID}}", "claim": "{{claim:CLAIM-ID}}", "assertion": "{{assertion:ASSERTION-ID}}"},
    }

def normalized_match(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).replace("’", "'")
    return re.sub(r"\s+", " ", value).strip().casefold()


def page_corpus(task: dict[str, Any]) -> str:
    sections = task.get("sections", {})
    parts: list[str] = []
    for kind in ("diplomatic_latin", "normalized_latin", "supplied_text"):
        parts.extend(as_paragraphs(sections.get(kind, []), f"sections.{kind}"))
    return "\n\n".join(parts)


def page_contains(task: dict[str, Any], value: str) -> bool:
    needle = normalized_match(value)
    return bool(needle) and needle in normalized_match(page_corpus(task))


def script_family(ch: str) -> str | None:
    try:
        name = unicodedata.name(ch)
    except ValueError:
        return None
    for family in ("LATIN", "CYRILLIC", "GREEK", "HEBREW"):
        if family in name:
            return family
    return None


def suspicious_mixed_script_tokens(text: str) -> list[str]:
    found: list[str] = []
    for token in re.findall(r"[^\W\d_]+", unicodedata.normalize("NFKC", text), flags=re.UNICODE):
        families = {family for ch in token if (family := script_family(ch))}
        if "CYRILLIC" in families and len(families) > 1:
            found.append(token)
    return list(dict.fromkeys(found))


def scan_suspicious_unicode(task: dict[str, Any]) -> None:
    """Diagnose mixed-script codepoint mistakes without silently rewriting text."""
    values: list[tuple[str, str]] = [("translation", task.get("translation", ""))]
    sections = task.get("sections", {})
    if isinstance(sections, dict):
        for kind, raw in sections.items():
            try:
                paragraphs = as_paragraphs(raw, f"sections.{kind}")
            except CompactTaskError:
                continue
            values.extend((f"sections.{kind}", paragraph) for paragraph in paragraphs)
    for index, claim in enumerate(task.get("analytical_claims", [])) if isinstance(task.get("analytical_claims", []), list) else []:
        if isinstance(claim, dict) and isinstance(claim.get("text"), str):
            values.append((f"analytical_claims[{index}].text", claim["text"]))
    for index, entity in enumerate(task.get("entities", [])) if isinstance(task.get("entities", []), list) else []:
        if isinstance(entity, dict) and isinstance(entity.get("display"), str):
            values.append((f"entities[{index}].display", entity["display"]))
    for record in task.get("publication_contract", {}).get("assertions", []):
        values.append(("publication assertion " + record.get("id", ""), record.get("projection", "")))
    issues: list[str] = []
    for owner, text in values:
        if not isinstance(text, str):
            continue
        tokens = suspicious_mixed_script_tokens(text)
        if tokens:
            issues.append(f"{owner}: {', '.join(tokens)}")
    if issues:
        raise CompactTaskError(
            "suspicious mixed Latin/Cyrillic codepoint substitution detected - inspect the source and use literal UTF-8; "
            + "; ".join(issues)
        )


def current_work_aliases_from_task(task: dict[str, Any]) -> set[str]:
    aliases: set[str] = set()
    identity = task.get("identity", {})
    if isinstance(identity, dict):
        aliases.update(finalize_response.alias_variants(identity.get("name")))
        raw_aliases = identity.get("aliases", [])
        if isinstance(raw_aliases, list):
            for alias in raw_aliases:
                aliases.update(finalize_response.alias_variants(alias))
    pseudo = {
        "identity_hypotheses": task.get("identity_hypotheses", []),
        "claims": task.get("claims", []),
    }
    aliases.update(finalize_response.collect_identity_aliases(pseudo))
    return aliases


def evidence_lookup(evidence: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["evidence_id"]: item for item in evidence}


def referenced_evidence(
    ids: Any, evidence: list[dict[str, Any]], owner: str, *, allow_empty: bool = False
) -> list[dict[str, Any]]:
    if not isinstance(ids, list) or (not ids and not allow_empty):
        suffix = " (empty is allowed for an explicitly licensed inference)" if allow_empty else ""
        raise CompactTaskError(f"{owner}.evidence_ids must be a list{' or may be empty' if allow_empty else ' with at least one item'}{suffix}")
    emap = evidence_lookup(evidence)
    missing = [eid for eid in ids if eid not in emap]
    if missing:
        raise CompactTaskError(f"{owner}.evidence_ids reference missing evidence: {', '.join(missing)}")
    return [emap[eid] for eid in ids]


def load_task() -> dict[str, Any]:
    try:
        value = json.loads(TASK.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompactTaskError(f"cannot read compact Scholar View task {TASK}: {exc}") from exc
    if not isinstance(value, dict):
        raise CompactTaskError("compact Scholar View task must be a JSON object")
    if value.get("schema_version") != TASK_SCHEMA_VERSION:
        raise CompactTaskError(f"schema_version must be {TASK_SCHEMA_VERSION}")
    if not isinstance(value.get("work_id"), str) or not value["work_id"].strip():
        raise CompactTaskError("work_id is required")
    if not isinstance(value.get("translation", ""), str) or (value.get("publication_contract", {}).get("scope", {}).get("translation_requirement") != "NONE" and not value.get("translation", "").strip()):
        raise CompactTaskError("the current requested translation must be non-empty; research delta may omit retained translation")
    if not isinstance(value.get("sections"), dict):
        raise CompactTaskError("sections must be an object keyed by Scholar View section kind")
    return value


def as_paragraphs(value: Any, owner: str) -> list[str]:
    if isinstance(value, str):
        if not value.strip():
            return []
        return [value]
    if isinstance(value, list) and all(isinstance(x, str) for x in value):
        return [x for x in value if x.strip()]
    raise CompactTaskError(f"{owner} must be a string or list of strings")


def source_profile(task: dict[str, Any]) -> dict[str, Any]:
    """Resolve the current primary source from registered evidence, not a mode flag."""
    import source_integrity
    directory = task_state.resolve(task.get("publication_contract", {}).get("task_directory"))
    path = directory / "source-integrity.json"
    if path.is_symlink() or not path.is_file():
        raise CompactTaskError("SOURCE_ANCHOR_REQUIRED: register the actual supplied source in source-integrity.json")
    registry = source_integrity.IntegrityRegistry(json.loads(path.read_text(encoding="utf-8")))
    if registry.work_id != task["work_id"] or registry.raw.get("task_directory") != str(directory.resolve()):
        raise CompactTaskError("source anchor must belong to this current task and work")
    locus = task.get("locus") or {}
    image_hash = locus.get("image_sha256")
    anchor = task.get("source_anchor")
    if image_hash:
        nodes = [n for n in registry.nodes.values() if n["type"] in source_integrity.IMAGE_TYPES and n.get("source_sha256") == image_hash]
        if len(nodes) != 1 or PAGE_EVIDENCE_ID not in nodes[0].get("evidence_ids", []):
            raise CompactTaskError("supplied-image locus requires its exact registered image and E-SUPPLIED-PAGE binding")
        if anchor and anchor.get("representation_id") != nodes[0]["id"]:
            raise CompactTaskError("source anchor conflicts with the supplied-image locus")
        return {"image": True, "node": nodes[0], "evidence_id": PAGE_EVIDENCE_ID, "registry": registry}
    if not isinstance(anchor, dict) or set(anchor) != {"representation_id", "evidence_id"}:
        raise CompactTaskError("non-image Scholar View requires source_anchor representation_id and evidence_id")
    node = registry.nodes.get(anchor["representation_id"])
    if node is None or node["type"] in source_integrity.IMAGE_TYPES or anchor["evidence_id"] not in node.get("evidence_ids", []):
        raise CompactTaskError("non-image source anchor must bind an actual registered text representation and its evidence")
    if registry.stale(node["id"]):
        raise CompactTaskError("non-image source anchor is stale; revalidate its actual ancestry")
    if locus.get("page_id") is not None:
        raise CompactTaskError("a non-image source anchor has no supplied-page locus")
    if task.get("long_s_review", {}).get("reviewed_against_supplied_image") is True:
        raise CompactTaskError("non-image source cannot attest supplied-image long-s review")
    sections = task.get("sections", {})
    if sections.get("diplomatic_latin") or sections.get("rare_book_notes"):
        raise CompactTaskError("non-image source cannot publish photographed diplomatic Latin or physical page apparatus")
    if sections.get("normalized_latin") and node["type"] != "NORMALIZED_TRANSCRIPTION":
        raise CompactTaskError("display supplied_text at its actual layer; normalization needs its own registered derivation")
    if any(e.get("evidence_class") == "supplied_image_observation" for e in task.get("evidence", [])):
        raise CompactTaskError("non-image primary source cannot manufacture supplied-image observation")
    return {"image": False, "node": node, "evidence_id": anchor["evidence_id"], "registry": registry}


def required_sections(task: dict[str, Any]) -> set[str]:
    if source_profile(task)["image"]:
        return REQUIRED_SECTIONS
    return {"supplied_text", "textual_uncertainties", "theological_loci", "exegetical_method"}


def validate_partial_scholar(task: dict[str, Any]) -> None:
    profile = source_profile(task)
    if profile["image"]:
        return
    if task["sections"].get("supplied_text") != profile["node"]["content"]:
        raise CompactTaskError("supplied_text must reproduce the exact registered primary text, without promoting its layer")
    pub = task_state.descriptor(TASK.parent)
    steps = [s["step_id"] for s in (pub or {}).get("operation_plan", {}).get("operations", []) if s["operation"] == "SCHOLARLY_TRANSLATE"]
    outcomes = {o["id"]: o for o in task.get("publication_contract", {}).get("outcomes", [])}
    if not steps or any(outcomes.get(k, {}).get("status") != "PARTIAL" for k in steps):
        raise CompactTaskError("non-image Scholar apparatus remains unavailable: SCHOLARLY_TRANSLATE requires governed useful PARTIAL, not COMPLETED or total BLOCKED")
    for k in steps:
        o = outcomes[k]
        if not o.get("result_refs") or not o.get("reason") or not o.get("limitations"):
            raise CompactTaskError("PARTIAL Scholar completion requires current results and explicit unavailable-image limitations")


def copy_evidence(task: dict[str, Any]) -> list[dict[str, Any]]:
    supplied = {
        "evidence_id": PAGE_EVIDENCE_ID,
        "evidence_class": "supplied_image_observation",
        "kind": "full_text_passage",
        "independence_group": f"supplied-page:{task['work_id']}",
        "description": "The user-supplied page image controlling observational claims for this Scholar View task.",
        "provenance": {"source": "user_supplied_page"},
        "identity_admissible": False,
    }
    profile = source_profile(task)
    if not profile["image"]:
        # Primary supplied text remains typed at its actual representation layer.
        node = profile["node"]
        supplied = {"evidence_id": profile["evidence_id"], "evidence_class": "other_witness",
                    "kind": "full_text_passage", "independence_group": "primary-source:" + task["work_id"],
                    "description": "The primary supplied text representation: " + node["type"],
                    "provenance": node["provenance"], "representation_type": node["type"],
                    "identity_admissible": False, "passage_inspected": True, "inspected_passage": node["content"]}
    items = task.get("evidence", [])
    if not isinstance(items, list):
        raise CompactTaskError("evidence must be a list")
    evidence = [supplied] + copy.deepcopy(items)
    ids: set[str] = set()
    for index, item in enumerate(evidence):
        if not isinstance(item, dict):
            raise CompactTaskError(f"evidence[{index}] must be an object")
        eid = item.get("evidence_id")
        if not isinstance(eid, str) or not eid:
            raise CompactTaskError(f"evidence[{index}] requires evidence_id")
        if eid in ids:
            raise CompactTaskError(f"duplicate evidence_id {eid}")
        ids.add(eid)
        if item.get("evidence_class") not in evidence_audit.EVIDENCE_CLASSES:
            raise CompactTaskError(f"evidence {eid} has invalid evidence_class {item.get('evidence_class')!r}; allowed: {allowed(evidence_audit.EVIDENCE_CLASSES)}")
        if not item.get("independence_group"):
            raise CompactTaskError(f"evidence {eid} requires independence_group")
        if not item.get("description"):
            raise CompactTaskError(f"evidence {eid} requires description")
    return evidence


def build_identity(
    task: dict[str, Any], evidence: list[dict[str, Any]], claims: list[dict[str, Any]]
) -> tuple[str, list[str], dict[str, Any], str | None]:
    identity = task.get("identity", {})
    if not isinstance(identity, dict):
        raise CompactTaskError("identity must be an object")
    state = identity.get("state", "UNIDENTIFIED")
    if state not in evidence_audit.IDENTITY_STATES:
        raise CompactTaskError(f"identity.state has invalid value {state!r}; allowed: {allowed(evidence_audit.IDENTITY_STATES)}")
    verification = identity.get("external_verification", "not_applicable")
    if verification not in evidence_audit.IDENTITY_VERIFICATION_STATUSES:
        raise CompactTaskError(f"identity.external_verification has invalid value {verification!r}; allowed: {allowed(evidence_audit.IDENTITY_VERIFICATION_STATUSES)}")
    selected = list(task.get("selected_claim_ids", []))
    if not all(isinstance(x, str) and x for x in selected):
        raise CompactTaskError("selected_claim_ids must be a list of non-empty strings")
    visible_claim_id: str | None = None
    name = identity.get("name")
    evidence_ids = identity.get("evidence_ids", [])
    evidence_map = {e["evidence_id"]: e for e in evidence}

    if state in {"WORK_ESTABLISHED", "EDITION_ESTABLISHED", "EXEMPLAR_ESTABLISHED"}:
        if not isinstance(name, str) or not name.strip():
            raise CompactTaskError(f"{state} requires identity.name")
        if not isinstance(evidence_ids, list) or not evidence_ids:
            raise CompactTaskError(f"{state} requires identity.evidence_ids")
        missing = [eid for eid in evidence_ids if eid not in evidence_map]
        if missing:
            raise CompactTaskError(f"identity.evidence_ids reference missing evidence: {', '.join(missing)}")
        for eid in evidence_ids:
            item = evidence_map[eid]
            if item.get("evidence_class") not in WORK_IDENTITY_EVIDENCE_CLASSES:
                raise CompactTaskError(
                    f"identity evidence {eid} has evidence_class {item.get('evidence_class')!r}; promoted work identity accepts: "
                    f"{allowed(WORK_IDENTITY_EVIDENCE_CLASSES)}"
                )
            if item.get("identity_admissible") is not True or not item.get("provenance") or item.get("kind") not in evidence_audit.WORK_ID_DISCRIMINATORS:
                raise CompactTaskError(
                    f"identity evidence {eid} must set identity_admissible: true, carry provenance, and use a discriminating kind; "
                    f"allowed kinds: {allowed(evidence_audit.WORK_ID_DISCRIMINATORS)}"
                )
        claim = {
            "claim_id": WORK_IDENTITY_CLAIM_ID,
            "claim_type": "work_identity",
            "work_id": task["work_id"],
            "subject_id": task["work_id"],
            "origin": "general_identity",
            "value": name,
            "status": "established",
            "confidence": identity.get("confidence", "secure"),
            "identity_origin": identity.get("origin", "external_research"),
            "evidence_ids": list(evidence_ids),
            "aliases": list(identity.get("aliases", [])) if isinstance(identity.get("aliases", []), list) else [],
        }
        claims.append(claim)
        if WORK_IDENTITY_CLAIM_ID not in selected:
            selected.append(WORK_IDENTITY_CLAIM_ID)
        visible_claim_id = WORK_IDENTITY_CLAIM_ID
    elif state == "WORK_CANDIDATE" and identity.get("show_candidate") is True:
        if not isinstance(name, str) or not name.strip() or not isinstance(evidence_ids, list) or not evidence_ids:
            raise CompactTaskError("visible WORK_CANDIDATE requires identity.name and identity.evidence_ids")
        missing = [eid for eid in evidence_ids if eid not in evidence_map]
        if missing:
            raise CompactTaskError(f"identity.evidence_ids reference missing evidence: {', '.join(missing)}")
        for eid in evidence_ids:
            item = evidence_map[eid]
            if item.get("evidence_class") not in WORK_IDENTITY_EVIDENCE_CLASSES:
                raise CompactTaskError(
                    f"identity evidence {eid} has evidence_class {item.get('evidence_class')!r}; promoted work identity accepts: "
                    f"{allowed(WORK_IDENTITY_EVIDENCE_CLASSES)}"
                )
            if item.get("identity_admissible") is not True or not item.get("provenance") or item.get("kind") not in evidence_audit.WORK_ID_DISCRIMINATORS:
                raise CompactTaskError(
                    f"identity evidence {eid} must set identity_admissible: true, carry provenance, and use a discriminating kind; "
                    f"allowed kinds: {allowed(evidence_audit.WORK_ID_DISCRIMINATORS)}"
                )
        claims.append({
            "claim_id": WORK_IDENTITY_CLAIM_ID,
            "claim_type": "work_identity",
            "work_id": task["work_id"],
            "value": name,
            "status": "probable",
            "confidence": identity.get("confidence", "probable"),
            "identity_origin": identity.get("origin", "external_research"),
            "evidence_ids": list(evidence_ids),
            "aliases": list(identity.get("aliases", [])) if isinstance(identity.get("aliases", []), list) else [],
        })
        visible_claim_id = WORK_IDENTITY_CLAIM_ID

    if state in {"EDITION_ESTABLISHED", "EXEMPLAR_ESTABLISHED"}:
        # Higher identity states retain the existing canonical claim semantics.
        # The compact adapter only supplies the work claim; callers add the
        # required edition/exemplar claim(s) in task.claims and select them.
        needed = "edition_identity" if state == "EDITION_ESTABLISHED" else "exemplar_identity"
        if not any(c.get("claim_type") == needed and evidence_audit.is_asserted(c) for c in claims):
            raise CompactTaskError(
                f"{state} requires an asserted {needed} in task.claims; compact Scholar View does not infer it"
            )

    output_identity = {
        "proposed_identity": None,
        "identity_state": state,
        "claim_id": None,
        "external_verification": "not_applicable",
    }
    return state, selected, output_identity, visible_claim_id


def diplomatic_text(task: dict[str, Any]) -> str:
    return "\n\n".join(as_paragraphs(task["sections"].get("diplomatic_latin"), "sections.diplomatic_latin"))


def normalized_text(task: dict[str, Any]) -> str:
    return "\n\n".join(as_paragraphs(task["sections"].get("normalized_latin"), "sections.normalized_latin"))


def _is_latin_letter(ch: str) -> bool:
    if ch in {"ſ", "ẛ"}:
        return True
    if not ch.isalpha():
        return False
    try:
        return "LATIN" in unicodedata.name(ch)
    except ValueError:
        return False


def _latin_word_tokens(text: str) -> list[str]:
    """Tokenize Latin words without dropping historical precomposed/combining marks."""
    tokens: list[str] = []
    current: list[str] = []
    for ch in text:
        if _is_latin_letter(ch):
            current.append(ch)
            continue
        if current and unicodedata.category(ch).startswith("M"):
            current.append(ch)
            continue
        if current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tokens


def _alignment_key(token: str) -> str:
    value = token.replace("ſ", "s").replace("ẛ", "s").replace("Æ", "AE").replace("Œ", "OE").replace("æ", "ae").replace("œ", "oe")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch)).casefold()
    return value.translate(str.maketrans({"v": "u", "j": "i"}))


def _sf_signature(token: str) -> str:
    out: list[str] = []
    for ch in token:
        if ch in {"ſ", "ẛ", "s", "S"}:
            out.append("s")
        elif ch in {"f", "F"}:
            out.append("f")
    return "".join(out)


def _derived_sf_resolution(token: str) -> str:
    if "ſ" in token or "ẛ" in token:
        return "long_s"
    if "f" in token or "F" in token:
        return "genuine_f"
    return "round_s"


def _aligned_normalized_tokens(diplomatic: list[str], normalized: list[str]) -> dict[int, int]:
    matcher = difflib.SequenceMatcher(
        a=[_alignment_key(token) for token in diplomatic],
        b=[_alignment_key(token) for token in normalized],
        autojunk=False,
    )
    mapping: dict[int, int] = {}
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal" or (tag == "replace" and (i2 - i1) == (j2 - j1)):
            for offset in range(i2 - i1):
                mapping[i1 + offset] = j1 + offset
    return mapping


def _stable_long_s_ids(tokens: list[str]) -> dict[int, str]:
    bases: list[str] = []
    for index, token in enumerate(tokens):
        left = max(0, index - 2)
        right = min(len(tokens), index + 3)
        context = "|".join(_alignment_key(value) for value in tokens[left:right])
        material = f"{_alignment_key(token)}|{_sf_signature(token)}|{context}"
        bases.append(hashlib.sha256(material.encode("utf-8")).hexdigest()[:12])
    totals = {base: bases.count(base) for base in set(bases)}
    seen: dict[str, int] = {}
    out: dict[int, str] = {}
    for index, base in enumerate(bases):
        seen[base] = seen.get(base, 0) + 1
        suffix = f"-{seen[base]}" if totals[base] > 1 else ""
        out[index] = f"LS-{base}{suffix}"
    return out


def scholar_long_s_payload(task: dict[str, Any]) -> dict[str, Any]:
    diplomatic = diplomatic_text(task)
    normalized = normalized_text(task)
    dtokens = _latin_word_tokens(diplomatic)
    ntokens = _latin_word_tokens(normalized)
    aligned = _aligned_normalized_tokens(dtokens, ntokens)
    ids = _stable_long_s_ids(dtokens)
    checks: list[dict[str, Any]] = []
    for index, token in enumerate(dtokens):
        if not any(ch in token for ch in ("ſ", "ẛ", "s", "S", "f", "F")):
            continue
        nindex = aligned.get(index)
        normalized_token = ntokens[nindex] if nindex is not None else None
        signature_matches = normalized_token is not None and _sf_signature(token) == _sf_signature(normalized_token)
        resolution = _derived_sf_resolution(token) if signature_matches else None
        reason = "derived_from_cross_layer_agreement" if signature_matches else (
            "s_f_cross_layer_mismatch" if normalized_token is not None else "normalized_token_unaligned"
        )
        checks.append({
            "token_id": ids[index],
            "visible": token,
            "diplomatic": token,
            "normalized_candidate": token.replace("ſ", "s").replace("ẛ", "s"),
            "normalized": normalized_token if normalized_token is not None else token.replace("ſ", "s").replace("ẛ", "s"),
            "requires_manual_check": not signature_matches,
            "resolution": resolution,
            "review_reason": reason,
            "evidence_ids": [],
        })
    return {
        "schema_version": "0.2",
        "generation_mode": "cross_layer_derived",
        "diplomatic_sha256": hashlib.sha256(diplomatic.encode("utf-8")).hexdigest(),
        "normalized_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        "checks": checks,
        "manual_review_required": sum(1 for check in checks if check["requires_manual_check"]),
    }


def _long_s_manual_summary(payload: dict[str, Any]) -> str:
    items = [check for check in payload.get("checks", []) if check.get("requires_manual_check")]
    return "; ".join(
        f"{check.get('token_id')}: diplomatic={check.get('diplomatic')!r}, normalized={check.get('normalized')!r}, reason={check.get('review_reason')}"
        for check in items
    )


def prepare_long_s_checklist(task: dict[str, Any]) -> int:
    if not source_profile(task)["image"]:
        print("No supplied-image long-s review applies; retain the text source layer and governed PARTIAL limitations.")
        return 0
    if not diplomatic_text(task).strip():
        raise CompactTaskError("sections.diplomatic_latin is required before preparing the long-s checklist")
    if not normalized_text(task).strip():
        raise CompactTaskError("sections.normalized_latin is required before preparing the long-s checklist")
    payload = scholar_long_s_payload(task)
    write_json(LONG_S_CHECK, payload)
    count = len(payload.get("checks", []))
    manual = payload.get("manual_review_required", 0)
    if manual:
        print(
            f"Prepared {count} helper-owned s/f checks at {LONG_S_CHECK}; {manual} require visual review against the supplied image. "
            "Correct the diplomatic/normalized text for the reported mismatch(es), then rerun --prepare-long-s. Do not hand-populate checklist resolutions. "
            + _long_s_manual_summary(payload)
        )
    else:
        print(
            f"Prepared {count} helper-owned s/f checks at {LONG_S_CHECK}; manual_review_required=0. "
            "After the supplied-image s/f review is complete, set long_s_review.reviewed_against_supplied_image to true and run final completion."
        )
    return 0


def load_long_s_audit(task: dict[str, Any]) -> dict[str, Any]:
    if not source_profile(task)["image"]:
        return {"required": False, "checklist_status": "not_required", "reviewed_against_supplied_image": False, "checks": []}
    review = task.get("long_s_review", {})
    if not isinstance(review, dict) or review.get("reviewed_against_supplied_image") is not True:
        raise CompactTaskError(
            "Scholar View diplomatic Latin requires long_s_review.reviewed_against_supplied_image: true after the supplied-image s/f review "
            "and after visually adjudicating every mismatch reported by --prepare-long-s"
        )
    path_value = review.get("checklist_file", str(LONG_S_CHECK))
    if not isinstance(path_value, str) or not path_value.strip():
        raise CompactTaskError("long_s_review.checklist_file must be a path string")
    path = Path(path_value)
    if path.resolve() != LONG_S_CHECK.resolve():
        raise CompactTaskError("long_s_review.checklist_file must belong to this task directory; omit the field to use the helper-owned checklist")
    if not path.exists():
        raise CompactTaskError("long-s/f review checkpoint is missing; run --prepare-long-s before final completion")
    try:
        prepared = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CompactTaskError(f"long-s/f review checkpoint is unreadable: {exc}") from exc
    if not isinstance(prepared, dict) or prepared.get("generation_mode") != "cross_layer_derived":
        raise CompactTaskError("long-s/f review checkpoint is from an older interface; rerun --prepare-long-s")

    current = scholar_long_s_payload(task)
    if (
        prepared.get("diplomatic_sha256") != current.get("diplomatic_sha256")
        or prepared.get("normalized_sha256") != current.get("normalized_sha256")
    ):
        raise CompactTaskError(
            "diplomatic or normalized Latin changed after the prepared supplied-image s/f review; rerun --prepare-long-s, "
            "adjudicate any reported mismatch, then reconfirm long_s_review.reviewed_against_supplied_image"
        )
    if current.get("manual_review_required"):
        raise CompactTaskError(
            "long-s/f cross-layer review still requires supplied-image adjudication; correct the diplomatic/normalized text and rerun. "
            + _long_s_manual_summary(current)
        )
    # The serialized checklist is helper-owned. Re-derive it from the exact
    # reviewed Latin rather than trusting model-authored token state.
    write_json(path, current)
    errors = evidence_audit.audit_long_s(current)
    if errors:
        raise CompactTaskError("derived long-s checklist is not validated: " + "; ".join(errors))
    return {
        "required": True,
        "checklist_status": "validated",
        "reviewed_against_supplied_image": True,
        "checks": copy.deepcopy(current["checks"]),
    }

def validate_witness_contract(task: dict[str, Any], evidence: list[dict[str, Any]], sections: dict[str, Any]) -> None:
    witness = task.get("witness_comparison", {})
    if not isinstance(witness, dict):
        raise CompactTaskError("witness_comparison must be an object")
    status = witness.get("status")
    if status not in WITNESS_STATUSES:
        raise CompactTaskError(f"witness_comparison.status has invalid value {status!r}; allowed: {allowed(WITNESS_STATUSES)}")
    if status == "completed":
        ids = witness.get("evidence_ids", [])
        if not isinstance(ids, list) or not ids:
            raise CompactTaskError("completed witness comparison requires witness_comparison.evidence_ids")
        emap = {e["evidence_id"]: e for e in evidence}
        missing = [eid for eid in ids if eid not in emap]
        if missing:
            raise CompactTaskError(f"witness comparison references missing evidence: {', '.join(missing)}")
        comparators = [emap[eid] for eid in ids]
        if not any(e.get("evidence_class") in {"other_witness", "historical_translation"} for e in comparators):
            raise CompactTaskError("witness comparison needs other_witness or historical_translation evidence")
        profile = source_profile(task)
        bound = {eid:n["id"] for n in profile["registry"].nodes.values() for eid in n.get("evidence_ids", [])}
        if not all(e["evidence_id"] in bound and profile["registry"].independent(profile["node"]["id"], bound[e["evidence_id"]]) for e in comparators):
            raise CompactTaskError("witness comparison requires independently rooted evidence, not the primary supplied text or its derivative")
        supplied_group = f"supplied-page:{task['work_id']}"
        if not any(e.get("independence_group") != supplied_group for e in comparators):
            raise CompactTaskError("witness comparison requires a comparator independent of the supplied page")
        if not all(e.get("passage_inspected") is True for e in comparators):
            raise CompactTaskError("each comparator evidence item used here must record passage_inspected: true")
        if not as_paragraphs(sections.get("witness_comparison", []), "sections.witness_comparison"):
            raise CompactTaskError("completed witness comparison requires a witness_comparison section")
        comparisons = witness.get("comparisons", [])
        if not isinstance(comparisons, list) or not comparisons:
            raise CompactTaskError("completed witness comparison requires comparisons with inspected supplied and comparator passages")
        for index, comparison in enumerate(comparisons):
            owner = f"witness_comparison.comparisons[{index}]"
            if not isinstance(comparison, dict):
                raise CompactTaskError(f"{owner} must be an object")
            supplied_text = comparison.get("supplied_text")
            comparator_text = comparison.get("comparator_text")
            eid = comparison.get("evidence_id")
            characterization = comparison.get("characterization")
            if not all(isinstance(s, str) and s.strip() for s in (supplied_text, comparator_text)):
                raise CompactTaskError(f"{owner} requires exact supplied_text and comparator_text excerpts")
            if eid not in ids or eid not in emap or emap[eid].get("evidence_class") not in {"other_witness", "historical_translation"}:
                raise CompactTaskError(f"{owner}.evidence_id must bind the inspected independent comparator")
            inspected = emap[eid].get("inspected_passage")
            if not isinstance(inspected, str) or comparator_text not in inspected:
                raise CompactTaskError(f"{owner}.comparator_text must occur in evidence[{eid}].inspected_passage")
            if not page_contains(task, supplied_text):
                raise CompactTaskError(f"{owner}.supplied_text must occur in the supplied-page diplomatic or normalized transcription")
            if characterization not in {"orthographic_only", "substantive_difference", "unresolved"}:
                raise CompactTaskError(f"{owner}.characterization must be orthographic_only, substantive_difference, or unresolved")
            if characterization == "orthographic_only" and comparator_tokens(supplied_text) != comparator_tokens(comparator_text):
                raise CompactTaskError(f"{owner}: orthographic_only is contradicted by the recorded lexical sequence; describe the differences")
        prose = " ".join(
            paragraph for section_name, value in sections.items()
            if section_name not in {"diplomatic_latin", "normalized_latin"}
            for paragraph in as_paragraphs(value, f"sections.{section_name}")
        )
        prose += " " + " ".join(str(c.get("text", "")) for c in task.get("analytical_claims", []) if isinstance(c, dict))
        if re.search(r"orthograph|spellings?\s+only|mere(?:ly)?\s+(?:spelling|typograph)", prose, re.I):
            if any(c["characterization"] != "orthographic_only" for c in comparisons) or witness.get("comparison_scope") != "entire_claimed_passage":
                raise CompactTaskError("an orthography-only characterization requires orthographic_only for every comparison and comparison_scope: entire_claimed_passage; otherwise describe bounded differences")
            scope_text = witness.get("claimed_passage")
            if not isinstance(scope_text, str) or not scope_text.strip() or not page_contains(task, scope_text):
                raise CompactTaskError("entire_claimed_passage requires claimed_passage copied from the supplied transcription")
            for comparison in comparisons:
                if normalized_match(comparison["supplied_text"]) != normalized_match(scope_text):
                    raise CompactTaskError("orthography-only claim must compare the entire declared supplied passage, not a selected matching excerpt")
                if comparison["comparator_text"].strip() != emap[comparison["evidence_id"]]["inspected_passage"].strip():
                    raise CompactTaskError("orthography-only claim must compare the full recorded independent passage")
    else:
        limitation = witness.get("limitation")
        if not isinstance(limitation, str) or not limitation.strip():
            raise CompactTaskError(f"witness comparison status {status} requires a limitation string")
        # For graceful degradation, the rendered section is controlled by the
        # explicit limitation rather than any stale comparator prose left in a
        # copied template.
        sections["witness_comparison"] = limitation


def comparator_tokens(value: str) -> list[str]:
    """Conservative spelling normalization, never a semantic equivalence test."""
    value = unicodedata.normalize("NFKD", value.casefold().replace("ſ", "s").replace("æ", "ae").replace("œ", "oe"))
    value = "".join(c for c in value if not unicodedata.combining(c))
    tokens = re.findall(r"[^\W\d_]+", value, re.UNICODE)
    return [token.replace("v", "u").replace("j", "i") for token in tokens]


def build_entities(
    task: dict[str, Any], evidence: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    values = task.get("entities", [])
    if not isinstance(values, list):
        raise CompactTaskError("entities must be a list")
    emap = evidence_lookup(evidence)
    entities: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    corpus = page_corpus(task)
    for index, raw in enumerate(values):
        if not isinstance(raw, dict):
            raise CompactTaskError(f"entities[{index}] must be an object")
        eid = raw.get("entity_id")
        if not isinstance(eid, str) or not eid:
            raise CompactTaskError(f"entities[{index}] requires entity_id")
        if eid in by_id:
            raise CompactTaskError(f"duplicate entity_id {eid}")
        role = raw.get("role")
        scope = raw.get("scope")
        if role not in finalize_response.ENTITY_ROLES:
            raise CompactTaskError(f"entity {eid} has invalid role {role!r}; allowed: {allowed(finalize_response.ENTITY_ROLES)}")
        if scope not in finalize_response.ENTITY_SCOPES:
            raise CompactTaskError(f"entity {eid} has invalid scope {scope!r}; allowed: {allowed(finalize_response.ENTITY_SCOPES)}")
        if scope not in finalize_response.ROLE_SCOPES.get(role, set()):
            raise CompactTaskError(f"entity {eid} role {role!r} is incompatible with scope {scope!r}")
        display = raw.get("display")
        if not isinstance(display, str) or not display.strip():
            raise CompactTaskError(f"entity {eid} requires display text")
        ev = raw.get("evidence_ids", [])
        if not isinstance(ev, list) or not ev:
            raise CompactTaskError(f"entity {eid} requires evidence_ids")
        missing = [x for x in ev if x not in emap]
        if missing:
            raise CompactTaskError(f"entity {eid} references missing evidence: {', '.join(missing)}")

        entity = {
            "entity_id": eid,
            "role": role,
            "scope": scope,
            "display": display,
            "current_work_referent": False,
            "evidence_ids": list(ev),
        }
        for optional in (
            "target_work_id", "candidate_scope", "page_token", "page_name_form",
            "identification_status", "identification_evidence_ids",
        ):
            if optional in raw:
                entity[optional] = copy.deepcopy(raw[optional])

        # A visible token is not automatically an identified historical person.
        # If the display differs from what is visibly printed, require an explicit
        # licensing state and keep inference/unresolved referents out of direct prose.
        if role == "historical_name" and scope == "page_content":
            page_token = raw.get("page_token")
            page_name_form = raw.get("page_name_form")
            visible_form = page_name_form if isinstance(page_name_form, str) and page_name_form.strip() else page_token
            display_visible = normalized_match(display) in normalized_match(corpus)
            visible_form_ok = isinstance(visible_form, str) and visible_form.strip() and normalized_match(visible_form) in normalized_match(corpus)
            if not display_visible:
                status = raw.get("identification_status")
                if status not in REFERENT_IDENTIFICATION_STATUSES:
                    raise CompactTaskError(
                        f"entity {eid}: visible page token does not by itself license identified referent {display!r}; "
                        f"set identification_status to one of: {allowed(REFERENT_IDENTIFICATION_STATUSES)}"
                    )
                if status == "explicit_page_name":
                    if not isinstance(page_name_form, str) or not page_name_form.strip() or normalized_match(page_name_form) not in normalized_match(corpus):
                        raise CompactTaskError(
                            f"entity {eid}: explicit_page_name requires a page_name_form visibly naming the referent in diplomatic/normalized text; a generic token such as Apostoli is insufficient"
                        )
                elif status == "independently_verified":
                    if not isinstance(page_token, str) or not page_token.strip() or normalized_match(page_token) not in normalized_match(corpus):
                        raise CompactTaskError(f"entity {eid}: independently_verified page referent requires its visible page_token")
                    ident_ids = raw.get("identification_evidence_ids", [])
                    if not isinstance(ident_ids, list) or not ident_ids:
                        raise CompactTaskError(f"entity {eid}: independently_verified requires identification_evidence_ids")
                    missing_ident = [x for x in ident_ids if x not in emap]
                    if missing_ident:
                        raise CompactTaskError(f"entity {eid}: identification_evidence_ids reference missing evidence: {', '.join(missing_ident)}")
                    if not any(
                        emap[x].get("evidence_class") in {"bibliography", "other_witness", "historical_translation", "external_authority"}
                        and x != PAGE_EVIDENCE_ID
                        and (emap[x].get("passage_inspected") is True or emap[x].get("kind") in {"full_text_passage", "explicit_author_title"})
                        for x in ident_ids
                    ):
                        raise CompactTaskError(
                            f"entity {eid}: independently_verified referent requires inspected or proposition-bearing non-page evidence"
                        )
                elif status in {"inferred", "unresolved"} and not visible_form_ok:
                    raise CompactTaskError(
                        f"entity {eid}: {status} page referent requires the visible page_token that prompted the inference"
                    )
        entities.append(entity)
        by_id[eid] = entity
    return entities, by_id


def _foreign_base_letters(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    return "".join(ch for ch in decomposed if unicodedata.category(ch).startswith("L")).casefold()


def build_foreign_language_tokens(
    task: dict[str, Any], evidence: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    values = task.get("foreign_language_tokens", [])
    if not isinstance(values, list):
        raise CompactTaskError("foreign_language_tokens must be a list")
    result: dict[str, dict[str, Any]] = {}
    corpus = page_corpus(task)
    for index, raw in enumerate(values):
        owner = f"foreign_language_tokens[{index}]"
        if not isinstance(raw, dict):
            raise CompactTaskError(f"{owner} must be an object")
        tid = raw.get("token_id")
        if not isinstance(tid, str) or not tid:
            raise CompactTaskError(f"{owner} requires token_id")
        if tid in result:
            raise CompactTaskError(f"duplicate foreign-language token_id {tid}")
        language = raw.get("language")
        if language not in FOREIGN_LANGUAGES:
            raise CompactTaskError(f"{owner}.language has invalid value {language!r}; allowed: {allowed(FOREIGN_LANGUAGES)}")
        form = raw.get("form")
        if not isinstance(form, str) or not form.strip():
            raise CompactTaskError(f"{owner}.form is required")
        reading_status = raw.get("reading_status")
        if reading_status not in FOREIGN_READING_STATUSES:
            raise CompactTaskError(f"{owner}.reading_status has invalid value {reading_status!r}; allowed: {allowed(FOREIGN_READING_STATUSES)}")
        source_layer = raw.get("source_layer")
        if source_layer not in FOREIGN_SOURCE_LAYERS:
            raise CompactTaskError(f"{owner}.source_layer has invalid value {source_layer!r}; allowed: {allowed(FOREIGN_SOURCE_LAYERS)}")
        legacy_ids = raw.get("evidence_ids", [])
        reading_ids = raw.get("reading_evidence_ids", legacy_ids)
        reading_items = referenced_evidence(reading_ids, evidence, owner + ".reading_evidence")
        if source_layer == "supplied_page":
            if PAGE_EVIDENCE_ID not in reading_ids:
                raise CompactTaskError(f"{owner}: supplied_page token reading_evidence_ids must include {PAGE_EVIDENCE_ID}")
            if normalized_match(form) not in normalized_match(corpus):
                raise CompactTaskError(f"{owner}: form {form!r} is not present in diplomatic/normalized supplied-page text")
            if raw.get("checked_against_supplied_image") is not True:
                raise CompactTaskError(f"{owner}: supplied-page Greek/Hebrew token requires checked_against_supplied_image: true")
        elif source_layer == "supplied_text":
            profile = source_profile(task)
            if profile["image"] or profile["evidence_id"] not in reading_ids or form not in profile["node"]["content"]:
                raise CompactTaskError(f"{owner}: supplied_text token must bind its actual non-image primary form")
            if raw.get("checked_against_supplied_image") is True:
                raise CompactTaskError(f"{owner}: supplied text cannot attest image glyph inspection")
            if profile["node"]["type"] == "RAW_OCR" and reading_status == "secure":
                raise CompactTaskError(f"{owner}: raw OCR token remains provisional")
        elif source_layer == "comparator":
            if not any(i.get("evidence_class") in {"other_witness", "historical_translation"} and i.get("passage_inspected") is True for i in reading_items):
                raise CompactTaskError(f"{owner}: comparator token requires an inspected other_witness or historical_translation reading_evidence item")
        else:
            if not any(i.get("evidence_class") in {"external_authority", "bibliography"} for i in reading_items):
                raise CompactTaskError(f"{owner}: external_authority token requires external_authority or bibliography reading_evidence")
        record = copy.deepcopy(raw)
        alternate_forms = raw.get("alternate_forms", [])
        if not isinstance(alternate_forms, list) or not all(isinstance(x, str) and x.strip() for x in alternate_forms):
            raise CompactTaskError(f"{owner}.alternate_forms must be a list of non-empty strings when supplied")
        base_letters = _foreign_base_letters(form)
        seen_alternates: set[str] = set()
        cleaned_alternates: list[str] = []
        for alternate in alternate_forms:
            normalized_alternate = unicodedata.normalize("NFC", alternate)
            if _foreign_base_letters(normalized_alternate) != base_letters:
                raise CompactTaskError(
                    f"{owner}: alternate form {alternate!r} changes the underlying letter sequence of {form!r}; "
                    "alternate_forms may differ only by diacritics, not by lexeme"
                )
            key = unicodedata.normalize("NFC", normalized_alternate)
            if key == unicodedata.normalize("NFC", form) or key in seen_alternates:
                continue
            seen_alternates.add(key)
            cleaned_alternates.append(normalized_alternate)
        record["alternate_forms"] = cleaned_alternates
        record["reading_evidence_ids"] = list(reading_ids)
        record["evidence_ids"] = list(dict.fromkeys(list(legacy_ids) + list(reading_ids)))
        gloss = raw.get("gloss")
        if gloss is not None:
            if not isinstance(gloss, str) or not gloss.strip():
                raise CompactTaskError(f"{owner}.gloss must be a non-empty string when supplied")
            gloss_status = raw.get("gloss_status")
            if gloss_status not in GLOSS_STATUSES:
                raise CompactTaskError(f"{owner}.gloss_status has invalid value {gloss_status!r}; allowed: {allowed(GLOSS_STATUSES)}")
            gloss_ids = raw.get("gloss_evidence_ids")
            if not isinstance(gloss_ids, list) or not gloss_ids:
                raise CompactTaskError(f"{owner}: a supplied gloss requires non-empty gloss_evidence_ids")
            referenced_evidence(gloss_ids, evidence, owner + ".gloss_evidence")
            record["gloss_evidence_ids"] = list(gloss_ids)
            record["evidence_ids"] = list(dict.fromkeys(record["evidence_ids"] + list(gloss_ids)))
            if raw.get("gloss_checked_against_token") is not True:
                raise CompactTaskError(f"{owner}: a supplied gloss requires gloss_checked_against_token: true")
            if gloss_status == "inconsistent":
                raise CompactTaskError(f"{owner}: token {form!r} and proposed gloss {gloss!r} remain inconsistent; correct the reading/gloss or leave the claim unresolved")
            if gloss_status == "verified" and reading_status != "secure" and raw.get("gloss_preserves_uncertainty") is not True:
                raise CompactTaskError(f"{owner}: {reading_status} token cannot carry a secure gloss unless gloss_preserves_uncertainty: true")
        result[tid] = record
    return result

def direct_entity_use_allowed(entity: dict[str, Any]) -> bool:
    return entity.get("identification_status") not in {"inferred", "unresolved"}


def resolve_claim_entity_markers(text: str, entities: dict[str, dict[str, Any]], owner: str) -> tuple[str, list[str]]:
    if CLAIM_MARKER_RE.search(text):
        raise CompactTaskError(f"{owner}: analytical claim text cannot contain nested claim markers")
    used: list[str] = []
    def repl(match: re.Match[str]) -> str:
        eid = match.group(1)
        entity = entities.get(eid)
        if entity is None:
            raise CompactTaskError(f"{owner}: unknown entity marker {eid!r} inside analytical claim text")
        used.append(eid)
        return entity["display"]
    return ENTITY_MARKER_RE.sub(repl, text), used


def build_analytical_claims(
    task: dict[str, Any], evidence: list[dict[str, Any]], entities: dict[str, dict[str, Any]],
    foreign_tokens: dict[str, dict[str, Any]], existing_claim_ids: set[str] | None = None,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    values = task.get("analytical_claims", [])
    if not isinstance(values, list):
        raise CompactTaskError("analytical_claims must be a list")
    emap = evidence_lookup(evidence)
    ids = set(existing_claim_ids or set())
    render_records: dict[str, dict[str, Any]] = {}
    canonical: list[dict[str, Any]] = []
    for index, raw in enumerate(values):
        owner = f"analytical_claims[{index}]"
        if not isinstance(raw, dict):
            raise CompactTaskError(f"{owner} must be an object")
        cid = raw.get("claim_id")
        if not isinstance(cid, str) or not cid:
            raise CompactTaskError(f"{owner} requires claim_id")
        if cid in ids:
            raise CompactTaskError(f"duplicate claim_id {cid}")
        ids.add(cid)
        ctype = raw.get("claim_type")
        if ctype not in ANALYTICAL_CLAIM_TYPES:
            raise CompactTaskError(f"{owner}.claim_type has invalid value {ctype!r}; allowed: {allowed(ANALYTICAL_CLAIM_TYPES)}")
        status = raw.get("status")
        if status not in ANALYTICAL_CLAIM_STATUSES:
            raise CompactTaskError(f"{owner}.status has invalid value {status!r}; allowed: {allowed(ANALYTICAL_CLAIM_STATUSES)}")
        text = raw.get("text")
        if not isinstance(text, str) or not text.strip():
            raise CompactTaskError(f"{owner}.text is required")
        text, marker_entity_ids = resolve_claim_entity_markers(text, entities, owner + ".text")
        ev_ids = raw.get("evidence_ids", [])
        allow_empty = status in {"inference", "unresolved"}
        items = referenced_evidence(ev_ids, evidence, owner, allow_empty=allow_empty)
        if status == "supported" and not items:
            raise CompactTaskError(f"{owner}: supported analytical claim requires evidence")
        if status == "inference" and not items and not isinstance(raw.get("basis"), str):
            raise CompactTaskError(f"{owner}: evidence-free inference requires a concise basis string")
        if "entity_id" in raw and raw.get("entity_id") not in entities:
            raise CompactTaskError(f"{owner}: entity_id must reference a registered entity")
        entity_ids = list(raw.get("entity_ids", [])) if isinstance(raw.get("entity_ids", []), list) else []
        if isinstance(raw.get("entity_id"), str):
            entity_ids.append(raw["entity_id"])
        entity_ids.extend(marker_entity_ids)
        entity_ids = list(dict.fromkeys(entity_ids))
        missing_entity_ids = [eid for eid in entity_ids if eid not in entities]
        if missing_entity_ids:
            raise CompactTaskError(f"{owner}: entity_ids reference missing registered entities: {', '.join(missing_entity_ids)}")

        if ctype == "textual_reading":
            reading = raw.get("reading")
            if not isinstance(reading, str) or not reading.strip():
                raise CompactTaskError(f"{owner}: textual_reading requires reading")
            if status == "supported" and PAGE_EVIDENCE_ID in ev_ids and not page_contains(task, reading):
                raise CompactTaskError(
                    f"{owner}: supplied-page reading {reading!r} is absent from diplomatic/normalized transcription; "
                    "do not promote it from analytical prose"
                )
        elif ctype in {"variant_reading", "witness_reading"} and status == "supported":
            if not any(i.get("evidence_class") in {"other_witness", "historical_translation"} and i.get("passage_inspected") is True for i in items):
                raise CompactTaskError(f"{owner}: supported {ctype} requires an inspected comparator witness")
        elif ctype in {"historical_referent", "page_named_identification"}:
            eid = raw.get("entity_id")
            entity = entities.get(eid)
            if entity is None:
                raise CompactTaskError(f"{owner}: {ctype} requires a registered entity_id")
            if status == "supported" and not direct_entity_use_allowed(entity):
                raise CompactTaskError(f"{owner}: inferred/unresolved referent cannot be promoted to supported")
            if status == "inference" and entity.get("identification_status") not in {"inferred", "independently_verified", "explicit_page_name", None}:
                raise CompactTaskError(f"{owner}: entity referent state is incompatible with inference")
        elif ctype == "feature_function" and status == "supported":
            external = [
                i for i in items
                if i.get("evidence_id") != PAGE_EVIDENCE_ID
                and (i.get("passage_inspected") is True or i.get("kind") == "full_text_passage")
            ]
            if not external and raw.get("function_established_on_page") is not True:
                raise CompactTaskError(
                    f"{owner}: observed page feature does not by itself establish its function; use status inference or provide establishing evidence"
                )
        elif ctype == "foreign_token_gloss":
            tid = raw.get("token_id")
            token = foreign_tokens.get(tid)
            if token is None:
                raise CompactTaskError(f"{owner}: foreign_token_gloss requires a registered token_id")
            gloss_evidence_ids = token.get("gloss_evidence_ids", [])
            if not set(ev_ids).issubset(set(gloss_evidence_ids)):
                raise CompactTaskError(f"{owner}: foreign-token gloss claim evidence_ids must come from the token's gloss_evidence_ids, not its reading evidence")
            if status == "supported":
                if token.get("reading_status") != "secure" or token.get("gloss_status") != "verified":
                    raise CompactTaskError(
                        f"{owner}: supported foreign-token gloss requires secure token reading and verified gloss; otherwise use inference/unresolved"
                    )

        record = copy.deepcopy(raw)
        record["text"] = text
        record["rendered_text"] = text
        if entity_ids:
            record["entity_ids"] = entity_ids
        render_records[cid] = record
        canonical_claim = {
            "claim_id": cid,
            "claim_type": ctype,
            "claim_layer": "analysis",
            "status": {"supported": "verified", "inference": "inference", "unresolved": "unresolved"}[status],
            "confidence": raw.get("confidence", "secure" if status == "supported" else "uncertain"),
            "value": text,
            "evidence_ids": list(ev_ids),
            "analytical_status": status,
        }
        for optional in ("reading", "entity_id", "token_id", "basis", "function_established_on_page"):
            if optional in raw:
                canonical_claim[optional] = copy.deepcopy(raw[optional])
        if entity_ids:
            canonical_claim["entity_ids"] = list(entity_ids)
        canonical.append(canonical_claim)
    return render_records, canonical


def analytical_plain_text_checks(
    text: str, owner: str, task: dict[str, Any], foreign_tokens: dict[str, dict[str, Any]], aliases: set[str],
    *, registered_claim_status: str | None = None,
) -> None:
    issues: list[str] = []
    leaked = finalize_response.contains_alias(text, aliases)
    if leaked:
        issues.append(
            f"{owner}: current-work alias {leaked!r} is not allowed in analytical prose; renderer-owned Identification supplies current-work identity"
        )

    # A quoted multiword form absent from the supplied transcription is treated
    # as a textual/historical claim, not as decorative prose. A registered
    # analytical claim has already supplied the required provenance.
    if registered_claim_status is None:
        for match in BACKTICK_OR_QUOTE_RE.finditer(text):
            quoted = next((group for group in match.groups() if group is not None), "").strip()
            words = re.findall(r"[^\W\d_]+", quoted, flags=re.UNICODE)
            if len(words) >= 2 and not page_contains(task, quoted):
                issues.append(
                    f"{owner}: quoted form {quoted!r} is absent from diplomatic/normalized supplied-page text; "
                    "quotation marks in analytical sections are reserved for literal supplied-page wording; "
                    "use unquoted paraphrase/gloss or register the claim in analytical_claims and insert {{claim:CLAIM-ID}}"
                )

    if owner.startswith("sections.rare_book_notes") and registered_claim_status is None and RARE_BOOK_FUNCTION_RE.search(text):
        issues.append(
            f"{owner}: explicit rare-book function language must be rendered through a typed feature_function analytical_claim; "
            "plain rare_book_notes may describe visible presence/location but may not establish function"
        )

    by_form: dict[str, dict[str, Any]] = {}
    for token in foreign_tokens.values():
        forms = [token.get("form")] + list(token.get("alternate_forms", []))
        for form in forms:
            if isinstance(form, str):
                by_form[unicodedata.normalize("NFKC", form)] = token
    for visible in SCRIPT_TOKEN_RE.findall(unicodedata.normalize("NFKC", text)):
        token = by_form.get(visible)
        if token is None:
            issues.append(
                f"{owner}: analytical Greek/Hebrew token {visible!r} lacks foreign_language_tokens registration"
            )
            continue
        if token.get("reading_status") != "secure" and registered_claim_status not in {"inference", "unresolved"}:
            issues.append(
                f"{owner}: {token.get('reading_status')} foreign-language token {visible!r} cannot appear as unqualified analytical prose; "
                "render it through an inference or unresolved analytical_claim"
            )
    if issues:
        raise CompactTaskError("; ".join(issues))


def _entity_occurrence_regex(display: str) -> re.Pattern[str]:
    return re.compile(r"(?<![\\w])" + re.escape(display) + r"(?P<poss>['’]s)?(?![\\w])", re.IGNORECASE)


def auto_entity_segments(
    text: str, entities: dict[str, dict[str, Any]], owner: str, *, allow_inferred: bool
) -> list[dict[str, Any]]:
    if not text:
        return []
    by_display: dict[str, list[dict[str, Any]]] = {}
    for entity in entities.values():
        display = entity.get("display")
        if isinstance(display, str) and display.strip():
            by_display.setdefault(normalized_match(display), []).append(entity)
    candidates = [group[0] for group in by_display.values() if len(group) == 1]
    candidates.sort(key=lambda e: len(e["display"]), reverse=True)

    out: list[dict[str, Any]] = []
    cursor = 0
    while cursor < len(text):
        best: tuple[int, int, dict[str, Any], str] | None = None
        for entity in candidates:
            match = _entity_occurrence_regex(entity["display"]).search(text, cursor)
            if match is None:
                continue
            candidate = (match.start(), match.end(), entity, match.group("poss") or "")
            if best is None or candidate[0] < best[0] or (candidate[0] == best[0] and candidate[1] > best[1]):
                best = candidate
        if best is None:
            out.append({"kind": "text", "text": text[cursor:]})
            break
        start, end, entity, possessive = best
        if start > cursor:
            out.append({"kind": "text", "text": text[cursor:start]})
        if not allow_inferred and not direct_entity_use_allowed(entity):
            raise CompactTaskError(
                f"{owner}: entity {entity['entity_id']} is {entity.get('identification_status')} and cannot render as a page-supported named referent; "
                "use it only inside an inference/unresolved analytical_claim"
            )
        out.append({"kind": "entity", "entity_id": entity["entity_id"]})
        if possessive:
            out.append({"kind": "text", "text": possessive})
        cursor = end
    return out or [{"kind": "text", "text": text}]


def segments_for_text(
    text: str, entities: dict[str, dict[str, Any]], analytical_claims: dict[str, dict[str, Any]],
    foreign_tokens: dict[str, dict[str, Any]], aliases: set[str], task: dict[str, Any], owner: str,
    *, page_text: bool = False, allow_inferred_entities: bool = False,
    registered_claim_status: str | None = None,
) -> list[dict[str, Any]]:
    if page_text:
        if STRUCTURED_MARKER_RE.search(text):
            raise CompactTaskError(f"{owner}: entity/claim markers are not allowed inside page-text transcription sections")
        return [{"kind": "page_text", "text": text, "evidence_ids": [source_profile(task)["evidence_id"]]}]

    contract = task.get("publication_contract")
    if not isinstance(contract, dict):
        raise CompactTaskError("PUBLICATION_CONTRACT_REQUIRED")
    assertions = evidence_audit.publication_table(contract['assertions'], 'assertions')
    tokens = re.compile(r"\{\{(assertion|claim):([A-Za-z0-9_.-]+)\}\}")
    output = [];cursor = 0
    summary = foreign_uncertainty_summary(foreign_tokens) or "No additional textual uncertainty is recorded in the structured task."
    if owner.startswith('sections.textual_uncertainties') and text == summary:
        return [{"kind":"source_status","status_id":"foreign_language_tokens"}]
    for match in tokens.finditer(text):
        chunk = text[cursor:match.start()]
        if chunk and not chunk.isspace() and chunk not in evidence_audit.NONASSERTIVE_TEXT:
            raise CompactTaskError(owner + ": unbound substantive prose; use a whole bounded {{assertion:ID}} passage")
        if chunk:output.append({"kind":"text","text":chunk})
        if match.group(1) == 'assertion':
            a = assertions.get(match.group(2))
        else:
            matches = [a for a in assertions.values() if a.get('claim_id') == match.group(2)]
            a = matches[0] if len(matches) == 1 else None
        if a is None or a['id'] not in contract['scope']['assertion_ids']:
            raise CompactTaskError(owner + ": current governed assertion required")
        analytical_plain_text_checks(a['projection'], owner, task, foreign_tokens, aliases,
            registered_claim_status={'PROVISIONAL':'inference','UNRESOLVED':'unresolved'}.get(a['status'],'supported'))
        output.append({"kind":"assertion_projection","assertion_id":a['id']});cursor = match.end()
    chunk = text[cursor:]
    if chunk and not chunk.isspace() and chunk not in evidence_audit.NONASSERTIVE_TEXT:
        raise CompactTaskError(owner + ": substantive text/entity/term cannot escape governance")
    if chunk:output.append({"kind":"text","text":chunk})
    return output



def foreign_uncertainty_summary(foreign_tokens: dict[str, dict[str, Any]]) -> str | None:
    if not foreign_tokens:
        return None
    counts = {status: 0 for status in sorted(FOREIGN_READING_STATUSES)}
    for token in foreign_tokens.values():
        status = token.get("reading_status")
        if status in counts:
            counts[status] += 1
    nonsecure = [(status, counts[status]) for status in ("probable", "uncertain", "unresolved") if counts[status]]
    if not nonsecure:
        return "Structured foreign-language reading status: all registered readings are secure."
    parts = [f"{count} {status}" for status, count in nonsecure]
    return "Structured foreign-language reading status: " + ", ".join(parts) + ". These readings are not secure."

def _dedupe_errors(errors: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for error in errors:
        value = error.strip()
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def collect_preflight_errors(task: dict[str, Any]) -> list[str]:
    """Collect independent current Scholar View blockers before fail-fast construction."""
    errors: list[str] = []

    def capture(label: str, fn):
        try:
            return fn(), None
        except CompactTaskError as exc:
            errors.append(f"{label}: {exc}")
            return None, exc

    capture("unicode", lambda: scan_suspicious_unicode(task))
    evidence, evidence_error = capture("evidence", lambda: copy_evidence(task))

    sections = task.get("sections", {})
    if isinstance(sections, dict):
        nonempty_required = required_sections(task) - {"textual_uncertainties"}
        delta = task.get("publication_contract", {}).get("scope", {}).get("mode") == "DELTA"
        if delta:nonempty_required = set()
        missing_required: list[str] = []
        for kind in sorted(nonempty_required):
            try:
                if not as_paragraphs(sections.get(kind, []), f"sections.{kind}"):
                    missing_required.append(kind)
            except CompactTaskError as exc:
                errors.append(f"sections.{kind}: {exc}")
        if not delta and "textual_uncertainties" not in sections:
            missing_required.append("textual_uncertainties")
        if missing_required:
            errors.append("sections: missing required Scholar View section(s): " + ", ".join(sorted(set(missing_required))))

        # Review validity depends only on the two Latin layers and can be checked
        # before unrelated plan construction, avoiding delayed stale-review discovery.
        if sections.get("diplomatic_latin") and sections.get("normalized_latin"):
            capture("long_s_review", lambda: load_long_s_audit(task))
    else:
        errors.append("sections: sections must be an object keyed by Scholar View section kind")

    if evidence_error is not None or evidence is None:
        return _dedupe_errors(errors)

    temp_claims = copy.deepcopy(task.get("claims", []))
    if isinstance(temp_claims, list):
        capture("identity", lambda: build_identity(task, evidence, temp_claims))
    else:
        errors.append("claims: claims must be a list")

    if isinstance(sections, dict):
        capture("witness_comparison", lambda: validate_witness_contract(task, evidence, copy.deepcopy(sections)))

    # Validate entity records independently so one malformed entity does not
    # conceal unrelated malformed entities in the same submission.
    entity_values = task.get("entities", [])
    entity_errors = False
    if isinstance(entity_values, list):
        ids = [raw.get("entity_id") for raw in entity_values if isinstance(raw, dict) and isinstance(raw.get("entity_id"), str)]
        duplicates = sorted({eid for eid in ids if ids.count(eid) > 1})
        for eid in duplicates:
            errors.append(f"entities: duplicate entity_id {eid}")
            entity_errors = True
        for index, raw in enumerate(entity_values):
            clone = copy.deepcopy(task)
            clone["entities"] = [raw]
            _, err = capture(f"entities[{index}]", lambda clone=clone: build_entities(clone, evidence))
            entity_errors = entity_errors or err is not None
    else:
        errors.append("entities: entities must be a list")
        entity_errors = True

    token_values = task.get("foreign_language_tokens", [])
    token_errors = False
    if isinstance(token_values, list):
        ids = [raw.get("token_id") for raw in token_values if isinstance(raw, dict) and isinstance(raw.get("token_id"), str)]
        duplicates = sorted({tid for tid in ids if ids.count(tid) > 1})
        for tid in duplicates:
            errors.append(f"foreign_language_tokens: duplicate foreign-language token_id {tid}")
            token_errors = True
        for index, raw in enumerate(token_values):
            clone = copy.deepcopy(task)
            clone["foreign_language_tokens"] = [raw]
            _, err = capture(f"foreign_language_tokens[{index}]", lambda clone=clone: build_foreign_language_tokens(clone, evidence))
            token_errors = token_errors or err is not None
    else:
        errors.append("foreign_language_tokens: foreign_language_tokens must be a list")
        token_errors = True

    entities = entity_map = foreign_tokens = None
    if not entity_errors:
        built, _ = capture("entities", lambda: build_entities(task, evidence))
        if built is not None:
            entities, entity_map = built
    if not token_errors:
        foreign_tokens, _ = capture("foreign_language_tokens", lambda: build_foreign_language_tokens(task, evidence))

    analytical_values = task.get("analytical_claims", [])
    analytical_errors = False
    analytical_claims = None
    if entity_map is not None and foreign_tokens is not None:
        existing_claim_ids = {
            c.get("claim_id") for c in task.get("claims", [])
            if isinstance(c, dict) and isinstance(c.get("claim_id"), str)
        }
        existing_claim_ids.add(WORK_IDENTITY_CLAIM_ID)
        if isinstance(analytical_values, list):
            ids = [raw.get("claim_id") for raw in analytical_values if isinstance(raw, dict) and isinstance(raw.get("claim_id"), str)]
            duplicates = sorted({cid for cid in ids if ids.count(cid) > 1})
            for cid in duplicates:
                errors.append(f"analytical_claims: duplicate analytical claim_id {cid}")
                analytical_errors = True
            for index, raw in enumerate(analytical_values):
                clone = copy.deepcopy(task)
                clone["analytical_claims"] = [raw]
                _, err = capture(
                    f"analytical_claims[{index}]",
                    lambda clone=clone: build_analytical_claims(
                        clone, evidence, entity_map, foreign_tokens, existing_claim_ids=existing_claim_ids
                    ),
                )
                analytical_errors = analytical_errors or err is not None
        else:
            errors.append("analytical_claims: analytical_claims must be a list")
            analytical_errors = True
        if not analytical_errors:
            built, _ = capture(
                "analytical_claims",
                lambda: build_analytical_claims(task, evidence, entity_map, foreign_tokens, existing_claim_ids=existing_claim_ids),
            )
            if built is not None:
                analytical_claims, _canonical = built

    # Once dependencies are valid, scan every section independently so all
    # current quote/token/function/marker blockers are surfaced in one call.
    if isinstance(sections, dict) and entity_map is not None and foreign_tokens is not None and analytical_claims is not None:
        aliases = current_work_aliases_from_task(task)
        for kind in SECTION_ORDER:
            if kind not in sections:
                continue
            try:
                paragraphs = as_paragraphs(sections[kind], f"sections.{kind}")
            except CompactTaskError:
                continue
            page_text = kind in {"diplomatic_latin", "normalized_latin", "supplied_text"}
            for index, paragraph in enumerate(paragraphs):
                capture(
                    f"sections.{kind}[{index}]",
                    lambda paragraph=paragraph, kind=kind, index=index, page_text=page_text: segments_for_text(
                        paragraph, entity_map, analytical_claims, foreign_tokens, aliases, task,
                        f"sections.{kind}[{index}]", page_text=page_text,
                    ),
                )
        confidence = task.get("confidence")
        if isinstance(confidence, str) and confidence.strip():
            capture(
                "confidence",
                lambda: segments_for_text(confidence, entity_map, analytical_claims, foreign_tokens, aliases, task, "confidence"),
            )

    return _dedupe_errors(errors)


def build_plan(task: dict[str, Any], visible_claim_id: str | None, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    sections = copy.deepcopy(task["sections"])
    # The adapter owns the structured foreign-language status summary. The
    # model supplies only concrete non-foreign uncertainties here, avoiding a
    # second free-prose copy of token certainty state that can go stale.
    nonempty_required = required_sections(task) - {"textual_uncertainties"}
    delta = task.get("publication_contract", {}).get("scope", {}).get("mode") == "DELTA"
    if delta:nonempty_required = set()
    missing_required = [k for k in sorted(nonempty_required) if not as_paragraphs(sections.get(k, []), f"sections.{k}")]
    if not delta and "textual_uncertainties" not in sections:
        missing_required.append("textual_uncertainties")
    if missing_required:
        raise CompactTaskError("missing required Scholar View section(s): " + ", ".join(sorted(set(missing_required))))
    if not delta or "witness_comparison" in sections:
        validate_witness_contract(task, evidence, sections)

    entities, entity_map = build_entities(task, evidence)
    foreign_tokens = build_foreign_language_tokens(task, evidence)
    uncertainties = as_paragraphs(sections.get("textual_uncertainties", []), "sections.textual_uncertainties")
    foreign_summary = foreign_uncertainty_summary(foreign_tokens)
    if foreign_summary and foreign_summary not in uncertainties:
        uncertainties.append(foreign_summary)
    if not uncertainties:
        uncertainties.append("No additional textual uncertainty is recorded in the structured task.")
    if not delta or "textual_uncertainties" in sections:
        sections["textual_uncertainties"] = uncertainties
    existing_claim_ids = {
        c.get("claim_id") for c in task.get("claims", [])
        if isinstance(c, dict) and isinstance(c.get("claim_id"), str)
    }
    existing_claim_ids.add(WORK_IDENTITY_CLAIM_ID)
    analytical_claims, _ = build_analytical_claims(
        task, evidence, entity_map, foreign_tokens, existing_claim_ids=existing_claim_ids
    )
    aliases = current_work_aliases_from_task(task)

    plan_sections: list[dict[str, Any]] = []
    for kind in SECTION_ORDER:
        if kind not in sections:
            continue
        if delta and task["publication_contract"]["scope"]["translation_requirement"] == "NONE" and kind in {"diplomatic_latin", "normalized_latin"}:
            continue
        paragraphs = as_paragraphs(sections[kind], f"sections.{kind}")
        if not paragraphs:
            continue
        page_text = kind in {"diplomatic_latin", "normalized_latin", "supplied_text"}
        blocks = [
            {"segments": segments_for_text(
                paragraph, entity_map, analytical_claims, foreign_tokens, aliases, task,
                f"sections.{kind}[{index}]", page_text=page_text,
            )}
            for index, paragraph in enumerate(paragraphs)
        ]
        plan_sections.append({"kind": "notes" if kind == "supplied_text" else kind, "blocks": blocks})

    confidence_value = task.get("confidence")
    confidence_segments = None
    if confidence_value is not None:
        if not isinstance(confidence_value, str) or not confidence_value.strip():
            raise CompactTaskError("confidence must be a governed non-empty string or omitted")
        confidence_segments = segments_for_text(confidence_value, entity_map, analytical_claims, foreign_tokens, aliases, task, "confidence")

    identity = task.get("identity", {})
    return {
        "schema_version": "0.2",
        "work_id": task["work_id"],
        "mode": "research_delta" if delta else "ordinary_translation",
        "publication_contract_sha256": evidence_audit.publication_digest(task["publication_contract"]),
        "identity": {
            "visible_claim_id": visible_claim_id,
            "external_verification": identity.get("external_verification", "not_applicable"),
        },
        "translation": {"text": task.get("translation", "")} if task["publication_contract"]["scope"]["translation_requirement"] != "NONE" else None,
        "sections": plan_sections,
        "confidence": {"segments": confidence_segments} if confidence_segments is not None else None,
        "entities": entities,
    }


def build_checkpoint(task: dict[str, Any], evidence: list[dict[str, Any]], plan: dict[str, Any]) -> dict[str, Any]:
    claims = copy.deepcopy(task.get("claims", []))
    if not isinstance(claims, list) or not all(isinstance(c, dict) for c in claims):
        raise CompactTaskError("claims must be a list of objects")
    _, entity_map = build_entities(task, evidence)
    foreign_tokens = build_foreign_language_tokens(task, evidence)
    existing_claim_ids = {
        c.get("claim_id") for c in claims
        if isinstance(c.get("claim_id"), str)
    }
    existing_claim_ids.add(WORK_IDENTITY_CLAIM_ID)
    _, analytical_canonical = build_analytical_claims(
        task, evidence, entity_map, foreign_tokens, existing_claim_ids=existing_claim_ids
    )
    claims.extend(analytical_canonical)
    state, selected, output_identity, visible_claim_id = build_identity(task, evidence, claims)
    # build_plan needs the renderer-owned visible claim choice; verify consistency
    if plan["identity"]["visible_claim_id"] != visible_claim_id:
        raise CompactTaskError("internal compact-task identity mismatch")

    validate_partial_scholar(task)
    long_s_audit = load_long_s_audit(task)
    locus = task.get("locus", {})
    if locus is None:
        locus = {}
    if not isinstance(locus, dict):
        raise CompactTaskError("locus must be an object")

    return {
        "schema_version": "0.2",
        "work_id": task["work_id"],
        "identity_state": state,
        "publication_contract": copy.deepcopy(task.get("publication_contract")),
        "selected_claim_ids": selected,
        "identity_hypotheses": copy.deepcopy(task.get("identity_hypotheses", [])),
        "orientation": copy.deepcopy(task.get("orientation", {"status": "unknown", "label": None, "evidence_ids": []})),
        "provenance": copy.deepcopy(task.get("provenance", {"status": "unknown", "claim": None, "evidence_ids": []})),
        "evidence": evidence,
        "claims": claims,
        "witness_variants": copy.deepcopy(task.get("witness_variants", [])),
        "legibility_regions": copy.deepcopy(task.get("legibility_regions", [])),
        "direct_reuse_claims": copy.deepcopy(task.get("direct_reuse_claims", [])),
        "textual_relationships": copy.deepcopy(task.get("textual_relationships", [])),
        "full_text_escalations": copy.deepcopy(task.get("full_text_escalations", [])),
        "long_s_audit": long_s_audit,
        "foreign_language_tokens": copy.deepcopy(list(foreign_tokens.values())),
        "output": {
            "stage": "draft",
            "transcription_mode": "translation",
            "uncertainties_visible": True,
            "transcription_spans": copy.deepcopy(task.get("transcription_spans", [])),
            "identity": output_identity,
            "final_response": None,
            "finalization": None,
            "critical_claim_audit": {
                "status": "not_required",
                "fail_closed": True,
                "reviewed_categories": [],
            },
        },
        "locus": {
            "page_id": locus.get("page_id"),
            "image_sha256": locus.get("image_sha256"),
        },
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prepare_licensed_resources(task: dict[str, Any], directory: Path) -> dict[str, Any]:
    """Build only general identity state before loading eligible resources.

    No translation, source verification or final publication is implied.
    The resource adapter still audits identity ancestry and exact scope.
    """
    import specialization_resources
    context_path = directory / "specialization-context.json"
    if context_path.exists():
        old = json.loads(context_path.read_text(encoding="utf-8"))
        if old.get("storage_state") not in {"INSTALLED_READ_ONLY", "NO_PERSISTENT_STATE"} or old.get("uses"):
            raise CompactTaskError("SPECIALIZATION_RECONCILIATION_REQUIRED: existing or used state")
    evidence = copy_evidence(task)
    claims = copy.deepcopy(task.get("claims", []))
    state, selected, _, _ = build_identity(task, evidence, claims)
    checkpoint = json.loads((Path(__file__).resolve().parents[1] / "resources/templates/evidence-checkpoint.json").read_text(encoding="utf-8"))
    checkpoint.update(work_id=task["work_id"], identity_state=state, selected_claim_ids=selected,
                      evidence=evidence, claims=claims, locus=copy.deepcopy(task.get("locus", checkpoint["locus"])))
    import specialization_core
    binding = specialization_core.derive_binding(checkpoint)
    context = specialization_resources.empty_primary() if binding is None else specialization_resources.materialize(checkpoint, binding)
    write_json(CHECKPOINT, checkpoint)
    write_json(directory / "identity-binding.json", binding)
    write_json(context_path, context)
    return {"state": context["storage_state"], "resources_prepared": True,
            "structured_completion": "UNFINISHED"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--prepare-long-s",
        action="store_true",
        help="generate the unresolved long-s/f checklist from compact-task diplomatic Latin",
    )
    parser.add_argument(
        "--show-interface",
        action="store_true",
        help="print accepted compact-interface enums and marker forms without reading implementation source",
    )
    parser.add_argument("--prepare-resources", action="store_true",
                        help="prepare licensed installed resources from general compact-task identity; no publication")
    parser.add_argument("--state-dir", help="directory created by scripts/task_state.py new")
    args = parser.parse_args()
    if args.show_interface:
        sys.stdout.write(json.dumps(interface_contract(), ensure_ascii=False, indent=2) + "\n")
        return 0
    try:
        if args.prepare_resources and args.prepare_long_s:
            raise CompactTaskError("preparation operations must be separate")
        directory = task_state.resolve(args.state_dir)
        if args.prepare_resources or args.prepare_long_s:
            task_state.research_entry(directory)
        else:
            terminal_output.begin(directory)
            inputs = terminal_output.capture(directory, ("scholar",))
        global TASK, CHECKPOINT, RESPONSE_PLAN, LONG_S_CHECK
        TASK = task_state.path(directory, "scholar")
        CHECKPOINT = task_state.path(directory, "checkpoint")
        RESPONSE_PLAN = task_state.path(directory, "plan")
        LONG_S_CHECK = task_state.path(directory, "long_s")
        task = load_task()
        if args.prepare_resources:
            sys.stdout.write(json.dumps(prepare_licensed_resources(task, directory), ensure_ascii=False) + "\n")
            return 0
        if args.prepare_long_s:
            scan_suspicious_unicode(task)
            return prepare_long_s_checklist(task)

        preflight_errors = collect_preflight_errors(task)
        if preflight_errors:
            joined = "\n- ".join(preflight_errors)
            raise CompactTaskError(
                f"aggregate preflight found {len(preflight_errors)} blocking issue(s); fix this batch before rerunning:\n- {joined}"
            )
        evidence = copy_evidence(task)

        # Identity construction determines the plan-visible claim. Build it on a
        # temporary claim list, then rebuild canonically in build_checkpoint.
        temp_claims = copy.deepcopy(task.get("claims", []))
        if not isinstance(temp_claims, list):
            raise CompactTaskError("claims must be a list")
        _, _, _, visible_claim_id = build_identity(task, evidence, temp_claims)
        plan = build_plan(task, visible_claim_id, evidence)
        checkpoint = build_checkpoint(task, evidence, plan)

        # Persist canonical state before finalization so a retry or Continue can
        # resume without reconstructing research or transcription work.
        write_json(CHECKPOINT, checkpoint)
        write_json(RESPONSE_PLAN, plan)
        inputs.update(terminal_output.capture(directory, ("checkpoint", "plan", "long_s") if source_profile(task)["image"] else ("scholar", "checkpoint", "plan")))

        _, text = finalize_response.finalize(checkpoint, plan)
        terminal_output.publish(directory, text, checkpoint, inputs)
    except CompactTaskError as exc:
        print(f"scholar-view completion error: {exc}", file=sys.stderr)
        return 2
    except finalize_response.FinalizationError as exc:
        message = str(exc)
        if "named-referent" in message or "named-looking token" in message:
            message += (
                "; compact-task fix: register the historical/comparator referent once in entities; the adapter "
                "reuses registered displays and possessives automatically, and {{entity:ENTITY-ID}} remains available for ambiguous cases"
            )
        print(f"scholar-view completion error: {message}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"scholar-view completion error: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
