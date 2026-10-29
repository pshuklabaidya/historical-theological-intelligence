#!/usr/bin/env python3
"""Construction-based final-response renderer for Early-Modern Latin Commentary.

The model supplies a structured response plan. This script validates evidence,
renders identity from audited state, derives all identity/entity spans, binds the
rendered text to a finalization receipt, and emits text only after the central
evidence audit passes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import evidence_audit
from hti_core.audit import AuditResult
from hti_core.completion import (
    CompletionBindings,
    CompletionError,
    CompletionReceipt,
    GuardedCompletion,
)
from hti_core.hashing import canonical_json, sha256_json, sha256_text

PLAN_SCHEMA_VERSION = "0.2"
RENDERER_ID = "finalize_response.py"

TOP_LEVEL_FIELDS = {
    "schema_version", "work_id", "mode", "identity", "translation",
    "sections", "confidence", "entities", "publication_contract_sha256",
}
IDENTITY_FIELDS = {"visible_claim_id", "external_verification"}
ENTITY_ROLES = {
    "historical_name",
    "historical_source",
    "external_comparator",
    "external_bibliographic_record",
    "bibliographic_candidate",
    "scripture_reference",
    "other_named_entity",
}
ENTITY_SCOPES = {
    "page_content",
    "historical_source",
    "external_comparator",
    "external_bibliographic_record",
    "scripture",
    "other_noncurrent",
}
ROLE_SCOPES = {
    "historical_name": {"page_content", "historical_source", "other_noncurrent"},
    "historical_source": {"historical_source"},
    "external_comparator": {"external_comparator"},
    "external_bibliographic_record": {"external_bibliographic_record"},
    "bibliographic_candidate": {"external_bibliographic_record"},
    "scripture_reference": {"scripture"},
    "other_named_entity": {"other_noncurrent"},
}
SECTION_HEADINGS = {
    "textual_uncertainties": "Textual uncertainties",
    "notes": "Notes",
    "diplomatic_latin": "Diplomatic Latin",
    "normalized_latin": "Normalized Latin",
    "witness_comparison": "Witness comparison",
    "source_notes": "Source notes",
    "rare_book_notes": "Rare-book notes",
    "citation": "Citation",
    "pastoral_study": "Pastoral study",
    "exegetical_method": "Exegetical method",
    "theological_loci": "Theological loci",
    "research": "Research notes",
}
SEGMENT_KINDS = {"text", "entity", "term", "page_text", "claim_text", "specialization_projection", "linebreak", "assertion_projection", "source_status"}

# Established ordinary prose and technical labels may be capitalized away from
# sentence starts. Other discriminating capitalization in analysis prose must
# enter through a typed entity segment. This guard does not infer identity
# from sentence-initial capitalization.
SAFE_CAPITALIZED_TOKENS = {
    "A", "An", "And", "As", "At", "Because", "But", "By", "Confidence",
    "For", "From", "High", "However", "If", "Illegible", "In", "It", "Latin",
    "Low", "Medium", "No", "Note", "Notes", "On", "Overall", "Page", "Probable",
    "Secure", "Status", "Text", "Textual", "The", "This", "Translation", "Uncertain",
    "Unknown", "Work", "Greek", "Hebrew", "English", "Scripture", "Biblical",
    "Edition", "Exemplar", "Source", "Sources", "Witness", "Witnesses", "Reading",
    "Readings", "Printed", "Manuscript", "Modern", "Diplomatic", "Normalized",
    "Rare", "Book", "Historical", "External", "Current", "Identity", "Candidate",
    "Established", "Evidence", "Image", "Visible", "Reconstruction", "Conjecture",
    # Routine Scripture / textual / grammatical labels are not, by themselves,
    # claims about the identity of the supplied work. Keeping these low-friction
    # prevents ordinary notes from requiring a typed entity solely because a
    # familiar label is capitalized. Current-work aliases are still checked
    # independently before this allow-list is considered.
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua",
    "Judges", "Ruth", "Samuel", "Kings", "Chronicles", "Ezra", "Nehemiah",
    "Esther", "Job", "Psalm", "Psalms", "Proverbs", "Ecclesiastes", "Song",
    "Songs", "Isaiah", "Jeremiah", "Lamentations", "Ezekiel", "Daniel", "Hosea",
    "Joel", "Amos", "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk",
    "Zephaniah", "Haggai", "Zechariah", "Malachi", "Matthew", "Mark", "Luke",
    "John", "Acts", "Romans", "Corinthians", "Galatians", "Ephesians",
    "Philippians", "Colossians", "Thessalonians", "Timothy", "Titus", "Philemon",
    "Hebrews", "James", "Peter", "Jude", "Revelation", "Apocalypse",
    "Vulgate", "Septuagint", "LXX", "Masoretic", "Aramaic", "Syriac", "Qal",
    "Niphal", "Piel", "Pual", "Hiphil", "Hophal", "Hithpael", "Sabbath",
    "Lord", "Day", "Church",
    # Ordinary divine names and theological titles are not, by themselves,
    # historical-source or current-work identity claims. Current-work alias
    # detection runs before this allow-list, so this does not license an
    # otherwise forbidden current-work alias.
    "God", "Christ", "Jesus", "Father", "Son", "Spirit", "Holy", "Trinity",
    "Messiah", "Apostle", "Prophet", "Christian", "Christians", "Epistle",
    "Sophistae", "Sophists",
}
MARKDOWN_CHARS_RE = re.compile(r"[*_`~]+")
NAMED_MARKDOWN_CHARS_RE = re.compile(r"[*_~]+")
WORD_RE = re.compile(r"\b[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]*\b")
QUOTED_SPAN_RE = re.compile(
    r'`[^`\n]*`|"[^"\n]*"|“[^”\n]*”|‘[^’\n]*’|(?<!\w)\'[^\'\n]+\'(?!\w)'
)


class FinalizationError(ValueError):
    pass


def normalize_alias(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    value = MARKDOWN_CHARS_RE.sub("", value)
    value = value.replace("’", "'")
    value = re.sub(r"[^\w'\-]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip().casefold()


def alias_variants(value: Any) -> set[str]:
    if not isinstance(value, str) or not value.strip():
        return set()
    raw = unicodedata.normalize("NFKC", value).strip()
    out = {normalize_alias(raw)}
    # Derive useful author/title aliases without relying on identity wording.
    possessive = re.match(r"^(.+?)(?:'s|’s)\s+(.+)$", raw)
    if possessive:
        out.add(normalize_alias(possessive.group(1)))
        out.add(normalize_alias(possessive.group(2)))
    for sep in (" - ", ": ", ", "):
        if sep in raw:
            for part in raw.split(sep):
                if len(part.strip()) >= 3:
                    out.add(normalize_alias(part))
    return {x for x in out if len(x) >= 3}


def collect_identity_aliases(checkpoint: dict[str, Any]) -> set[str]:
    aliases: set[str] = set()
    for hypothesis in checkpoint.get("identity_hypotheses", []):
        if not isinstance(hypothesis, dict):
            continue
        for key in ("name", "author", "title", "value", "proposed_identity", "label"):
            aliases.update(alias_variants(hypothesis.get(key)))
        for alias in hypothesis.get("aliases", []) if isinstance(hypothesis.get("aliases"), list) else []:
            aliases.update(alias_variants(alias))
    for claim in checkpoint.get("claims", []):
        if not isinstance(claim, dict) or claim.get("claim_type") != "work_identity":
            continue
        aliases.update(alias_variants(claim.get("value")))
        for alias in claim.get("aliases", []) if isinstance(claim.get("aliases"), list) else []:
            aliases.update(alias_variants(alias))
    return aliases


def contains_alias(text: str, aliases: set[str]) -> str | None:
    raw = unicodedata.normalize("NFKC", MARKDOWN_CHARS_RE.sub("", text))
    for alias in sorted(aliases, key=len, reverse=True):
        tokens = [re.escape(token) for token in alias.split() if token]
        if not tokens:
            continue
        joiner = r"(?:\s+|\s*['’]s\s*)"
        pattern = re.compile(
            r"(?<![\w])" + joiner.join(tokens) + r"(?:['’]s)?(?![\w])",
            re.IGNORECASE,
        )
        if pattern.search(raw):
            return alias
    return None


def sentence_boundary_before(text: str) -> bool:
    """Locate a lexical sentence start behind punctuation and presentation syntax."""
    prefix = text.rstrip(" \t")
    # Opening punctuation can precede the first word. It cannot erase prose
    # before it: "This cites (Augustine" still has a substantive prefix.
    while prefix and prefix[-1] in '([{"“‘«':
        prefix = prefix[:-1].rstrip(" \t")
    if not prefix or re.search(r"\n[ \t]*\n[ \t]*$", prefix):
        return True

    # A list, blockquote, or heading marker starts a new lexical line. A bare
    # line break inside prose does not by itself establish a new sentence.
    line = prefix.rsplit("\n", 1)[-1]
    if re.fullmatch(
        r"[ \t]*(?:(?:>[ \t]*)+)?"
        r"(?:(?:[-+*•‣◦]|[0-9]+[.)])|#{1,6})|[ \t]*(?:>[ \t]*)+",
        line,
    ):
        return True

    prefix = prefix.rstrip()

    # Closing punctuation and a short citation marker may follow the actual
    # sentence-ending mark. Peel only these suffixes, never intervening prose.
    while prefix:
        footnote = re.search(r"\[\^?[0-9]{1,3}\]$", prefix)
        if footnote:
            prefix = prefix[:footnote.start()].rstrip()
        elif prefix[-1] in ')]}"”’»':
            prefix = prefix[:-1].rstrip()
        else:
            break
    if not prefix or prefix[-1] not in ".!?":
        return False
    if prefix[-1] != ".":
        return True
    # Personal titles, initials, and bounded scholarly abbreviations are
    # non-terminal. Internal-dot initials are identified by their structure.
    if re.search(
        r"(?i)\b(?:st|dr|mr|mrs|ms|rev|prof|fr|cf|etc|viz|ca|ed|trans|"
        r"vol|p|pp|ch|chap|no|nos|sec|fig|ibid|[a-z])\.$",
        prefix,
    ):
        return False
    if re.search(r"\b(?:[A-Za-z]\.)(?:[A-Za-z]\.)+$", prefix):
        return False
    return True


def _quoted_spans(text: str) -> list[tuple[int, int]]:
    return [(match.start(), match.end()) for match in QUOTED_SPAN_RE.finditer(text)]


def _inside_any_span(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(start >= left and end <= right for left, right in spans)


def untyped_named_tokens(
    text: str, *, preceding_text: str = "", allow_sentence_initial: bool = False
) -> list[str]:
    plain = NAMED_MARKDOWN_CHARS_RE.sub("", unicodedata.normalize("NFKC", text))
    quoted = _quoted_spans(plain)
    found: list[str] = []
    for match in WORD_RE.finditer(plain):
        token = match.group(0)
        # Current-work aliases are checked before this function. A capitalized
        # token occurring only inside a short quotation is therefore treated as
        # quoted wording rather than as an independent named-referent claim.
        if _inside_any_span(match.start(), match.end(), quoted):
            continue
        # Capitalization at a sentence start is not evidence of a name.
        # Registered current-work aliases are checked independently, while
        # later capitals in a multiword name remain discriminating.
        if allow_sentence_initial and sentence_boundary_before(
            preceding_text + plain[:match.start()]
        ):
            continue
        safe_token = re.sub(r"(?:['’]s)$", "", token)
        if safe_token in SAFE_CAPITALIZED_TOKENS:
            continue
        # Hyphenated descriptive compounds headed by an already-safe generic
        # label (for example Greek-attested or Vulgate-affiliated) do not create
        # a new named referent. Current-work aliases are checked before this.
        if "-" in safe_token:
            head, tail = safe_token.split("-", 1)
            if head in SAFE_CAPITALIZED_TOKENS and tail and tail[0].islower():
                continue
        # An isolated one-letter page or apparatus label is not enough to
        # establish a historical named referent. Current-work aliases are
        # checked before this low-risk exemption.
        if len(token) == 1:
            continue
        if re.fullmatch(r"[A-Z](?:-[A-Z])+", token):
            continue
        # Roman numerals are not named entities.
        if re.fullmatch(r"[IVXLCDM]+", token):
            continue
        found.append(token)
    return list(dict.fromkeys(found))


def validate_analysis_text(
    text: str, aliases: set[str], owner: str, *, preceding_text: str = ""
) -> None:
    leaked = contains_alias(text, aliases)
    if leaked:
        raise FinalizationError(f"{owner}: raw analysis text contains current-work identity alias {leaked!r}; use a typed entity only when the referent is genuinely non-current")
    names = untyped_named_tokens(
        text, preceding_text=preceding_text, allow_sentence_initial=True
    )
    if names:
        raise FinalizationError(f"{owner}: untyped named referent(s) {', '.join(names)}; render names through typed entity segments")


def collect_named_referent_issues(plan: dict[str, Any], aliases: set[str]) -> list[str]:
    """Collect all raw-name issues so one repair pass can address them together."""
    issues: list[str] = []

    def inspect_segments(segments: Any, owner: str) -> None:
        if not isinstance(segments, list):
            return
        preceding = ""
        for index, segment in enumerate(segments):
            if not isinstance(segment, dict):
                continue
            kind = segment.get("kind")
            if kind in {"text", "term"} and isinstance(segment.get("text"), str):
                text = segment["text"]
                leaked = contains_alias(text, aliases)
                if leaked:
                    issues.append(f"{owner}[{index}] current-work identity alias {leaked!r}")
                names = untyped_named_tokens(
                    text,
                    preceding_text=preceding,
                    allow_sentence_initial=(kind == "text"),
                )
                if names:
                    label = "named referent(s)" if kind == "text" else "named-looking technical token(s)"
                    issues.append(f"{owner}[{index}] {label} {', '.join(names)}")
                preceding += text
            elif kind == "linebreak":
                preceding += "\n"
            elif kind == "entity":
                preceding += " X"
            elif isinstance(segment.get("text"), str):
                preceding += segment["text"]

    for s_index, section in enumerate(plan.get("sections", [])):
        if not isinstance(section, dict):
            continue
        for b_index, block in enumerate(section.get("blocks", [])) if isinstance(section.get("blocks"), list) else []:
            if isinstance(block, dict):
                inspect_segments(
                    block.get("segments"),
                    f"sections[{s_index}].blocks[{b_index}].segments",
                )
    confidence = plan.get("confidence")
    if isinstance(confidence, dict):
        inspect_segments(confidence.get("segments"), "confidence.segments")
    return issues


def claim_map(checkpoint: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        c.get("claim_id"): c
        for c in checkpoint.get("claims", [])
        if isinstance(c, dict) and c.get("claim_id")
    }


def evidence_map(checkpoint: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        e.get("evidence_id"): e
        for e in checkpoint.get("evidence", [])
        if isinstance(e, dict) and e.get("evidence_id")
    }


def validate_plan_shape(plan: dict[str, Any], checkpoint: dict[str, Any]) -> None:
    evidence_audit.validate_publication_contract(checkpoint, plan)
    unknown = set(plan) - TOP_LEVEL_FIELDS
    if unknown:
        raise FinalizationError(f"response plan has unsupported top-level field(s): {', '.join(sorted(unknown))}")
    if plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        raise FinalizationError(f"response plan schema_version must be {PLAN_SCHEMA_VERSION}")
    if plan.get("work_id") != checkpoint.get("work_id"):
        raise FinalizationError("response plan work_id does not match checkpoint")
    mode = plan.get("mode")
    if not isinstance(mode, str) or not mode:
        raise FinalizationError("response plan mode is required")
    identity = plan.get("identity", {})
    if not isinstance(identity, dict):
        raise FinalizationError("response plan identity must be an object")
    unknown_identity = set(identity) - IDENTITY_FIELDS
    if unknown_identity:
        raise FinalizationError(f"response plan identity has unsupported field(s): {', '.join(sorted(unknown_identity))}")
    if mode == "ordinary_translation":
        translation = plan.get("translation")
        if not isinstance(translation, dict) or not isinstance(translation.get("text"), str) or not translation.get("text").strip():
            raise FinalizationError("ordinary_translation requires non-empty translation.text")
    if not isinstance(plan.get("entities", []), list):
        raise FinalizationError("response plan entities must be a list")
    if not isinstance(plan.get("sections", []), list):
        raise FinalizationError("response plan sections must be a list")


def validate_entity(entity: dict[str, Any], checkpoint: dict[str, Any], aliases: set[str], seen: set[str]) -> None:
    eid = entity.get("entity_id")
    if not isinstance(eid, str) or not eid:
        raise FinalizationError("every entity requires entity_id")
    if eid in seen:
        raise FinalizationError(f"duplicate entity_id {eid}")
    seen.add(eid)
    role = entity.get("role")
    if role not in ENTITY_ROLES:
        raise FinalizationError(f"entity {eid} has invalid role {role!r}")
    scope = entity.get("scope")
    if scope not in ENTITY_SCOPES:
        raise FinalizationError(f"entity {eid} has invalid non-current scope {scope!r}")
    if scope not in ROLE_SCOPES.get(role, set()):
        raise FinalizationError(f"entity {eid} role {role!r} is incompatible with scope {scope!r}")
    display = entity.get("display")
    if not isinstance(display, str) or not display.strip():
        raise FinalizationError(f"entity {eid} requires display text")
    if entity.get("current_work_referent") is not False:
        raise FinalizationError(f"entity {eid} must explicitly declare current_work_referent: false")
    leaked = contains_alias(display, aliases)
    if leaked:
        raise FinalizationError(
            f"entity {eid} display contains current-work identity alias {leaked!r}; "
            "a non-current entity cannot substitute for renderer-owned Identification"
        )
    if role in {"external_comparator", "external_bibliographic_record", "bibliographic_candidate"}:
        target = entity.get("target_work_id")
        if not isinstance(target, str) or not target or target == checkpoint.get("work_id"):
            raise FinalizationError(f"entity {eid} must identify a non-current target_work_id")
    if role == "bibliographic_candidate" and entity.get("candidate_scope") != "external_work":
        raise FinalizationError(f"entity {eid} bibliographic_candidate must declare candidate_scope: external_work")
    evidence_ids = entity.get("evidence_ids", [])
    if not isinstance(evidence_ids, list):
        raise FinalizationError(f"entity {eid} evidence_ids must be a list")
    if not evidence_ids:
        raise FinalizationError(f"entity {eid} requires evidence_ids; a role label alone cannot license a named referent")
    emap = evidence_map(checkpoint)
    missing = [x for x in evidence_ids if x not in emap]
    if missing:
        raise FinalizationError(f"entity {eid} references missing evidence {', '.join(missing)}")


@dataclass
class RenderBuffer:
    parts: list[str]
    length: int = 0
    roles: list = None

    def append(self, text: str, role: dict | None = None) -> tuple[int, int]:
        if not text:
            return self.length, self.length
        if role is None:
            headings = {"**" + x + "**\n\n" for x in SECTION_HEADINGS.values()} | {"**Translation**\n\n", "**Confidence and identity status**\n\n", "**Supplied-page gaps**\n\n"}
            if text not in evidence_audit.NONASSERTIVE_TEXT and text not in headings and not text.isspace():
                raise FinalizationError("UNBOUND_SUBSTANTIVE_TEXT: use an exact governed assertion projection")
            role = {"kind": "LAYOUT"}
        if self.roles is None:
            self.roles = []
        start = self.length
        self.parts.append(text)
        self.length += len(text)
        self.roles.append({**role, "start": start, "end": self.length, "sha256": sha256_text(text)})
        return start, self.length

    def text(self) -> str:
        return "".join(self.parts)


def render_segments(
    buffer: RenderBuffer,
    segments: Any,
    entities: dict[str, dict[str, Any]],
    aliases: set[str],
    spans: list[dict[str, Any]],
    owner: str,
) -> None:
    if not isinstance(segments, list):
        raise FinalizationError(f"{owner} segments must be a list")
    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise FinalizationError(f"{owner}[{index}] must be an object")
        kind = segment.get("kind")
        if kind not in SEGMENT_KINDS:
            raise FinalizationError(f"{owner}[{index}] has invalid kind {kind!r}")
        if kind == "linebreak":
            buffer.append("\n")
            continue
        if kind == "entity":
            raise FinalizationError("ENTITY_NOT_ASSERTION: license the bounded passage containing the name")
            eid = segment.get("entity_id")
            entity = entities.get(eid)
            if entity is None:
                raise FinalizationError(f"{owner}[{index}] references unknown entity {eid!r}")
            display = entity["display"]
            start, end = buffer.append(display)
            spans.append({
                "start": start,
                "end": end,
                "text": display,
                "role": entity["role"],
                "entity_id": eid,
                "scope": entity["scope"],
                "evidence_ids": list(entity.get("evidence_ids", [])),
                "target_work_id": entity.get("target_work_id"),
            })
            continue
        if kind in {"assertion_projection", "claim_text"}:
            if kind == "assertion_projection":
                if set(segment) != {"kind", "assertion_id"}:
                    raise FinalizationError("ASSERTION_PROJECTION_SHAPE")
                assertion = assertion_map_current.get(segment["assertion_id"])
            else:
                matches = [a for a in assertion_map_current.values() if a.get("claim_id") == segment.get("claim_id")]
                assertion = matches[0] if len(matches) == 1 else None
            if assertion is None or assertion["id"] not in selected_assertions_current:
                raise FinalizationError("GOVERNED_ASSERTION_REQUIRED")
            if kind == "claim_text" and segment.get("text") != assertion["projection"]:
                raise FinalizationError("CANONICAL_PAYLOAD_CHANGE: a changed scholarly passage needs current reviewed derivation")
            text = assertion["projection"]
            leaked = contains_alias(text, aliases)
            if leaked:
                raise FinalizationError("ASSERTION_CURRENT_WORK_ALIAS: renderer-owned Identification controls identity")
            names = untyped_named_tokens(text, preceding_text=buffer.text(), allow_sentence_initial=True)
            licenses = set()
            for eid in assertion.get("entity_ids", []):
                if eid not in entities:
                    raise FinalizationError("ASSERTION_ENTITY_REFERENCE")
                licenses.update(re.findall(r"\b[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]*\b", entities[eid]["display"]))
            claim = claim_map_current.get(assertion.get("claim_id"), {})
            for eid in claim.get("entity_ids", []) + ([claim["entity_id"]] if claim.get("entity_id") else []):
                if eid in entities:
                    licenses.update(re.findall(r"\b[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]*\b", entities[eid]["display"]))
            if any(n not in licenses for n in names):
                raise FinalizationError("ASSERTION_NAMED_REFERENT: bind names with independently licensed entities")
            exact = evidence_audit.assertion_projection(assertion)
            start, end = buffer.append(exact, {"kind": "ASSERTION", "assertion_id": assertion["id"]})
            if claim:
                spans.append({"start": start, "end": end, "text": exact, "role": "analytical_claim", "claim_id": claim["claim_id"], "claim_type": claim.get("claim_type"), "analytical_status": claim.get("analytical_status", claim.get("status")), "evidence_ids": claim.get("evidence_ids", [])})
            continue
        if kind == "source_status":
            if set(segment) != {"kind", "status_id"} or segment["status_id"] not in source_status_current:
                raise FinalizationError("SOURCE_STATUS_REFERENCE")
            buffer.append(source_status_current[segment["status_id"]], {"kind": "GENERATED", "generator": "compact_source_status", "status_id": segment["status_id"]})
            continue
        projection = None
        if kind == "specialization_projection":
            import specialization_core
            if set(segment) != {"kind", "claim_id", "profile"} or segment["profile"] != specialization_core.PROFILE:
                raise FinalizationError("SPECIALIZATION_PROJECTION_SEGMENT")
            claim = claim_map_current.get(segment["claim_id"])
            if claim is None or claim.get("origin") not in {"specialization", "specialization_fact", "specialization_inference"} or set(claim.get("specialization_ref", {})) != {"record_id", "claim_id"}:
                raise FinalizationError("SPECIALIZATION_PROJECTION_REFERENCE")
            value = claim.get("value")
            projection = specialization_core.correction_projection(value)
            # Apply inherited identity/named-referent gates to every substantive
            # field. Fixed renderer labels and audited internal location IDs are
            # not new named referents or current-work identity assertions.
            text = "\n".join([value["claim"], value["scope"], value["correction"]["replaced"], value["correction"]["with"], value["depends_on_wording"]["phrase"], value["depends_on_wording"]["reading"], value["witness_comparison"]["note"]])
            kind = "claim_text"
        else:
            text = segment.get("text")
        if not isinstance(text, str):
            raise FinalizationError(f"{owner}[{index}] requires text")
        if kind == "text":
            validate_analysis_text(
                text, aliases, f"{owner}[{index}]", preceding_text=buffer.text()
            )
            buffer.append(text)
        elif kind == "term":
            if text not in evidence_audit.NONASSERTIVE_TEXT:
                raise FinalizationError("TERM_NOT_ASSERTION")
            leaked = contains_alias(text, aliases)
            if leaked:
                raise FinalizationError(f"{owner}[{index}]: technical-term segment contains current-work identity alias {leaked!r}")
            names = untyped_named_tokens(text)
            if names:
                raise FinalizationError(f"{owner}[{index}]: technical-term segment contains named-looking token(s) {', '.join(names)}")
            buffer.append(text)
        elif kind == "claim_text":
            claim_id = segment.get("claim_id")
            claim = claim_map_current.get(claim_id)
            if not isinstance(claim_id, str) or claim is None:
                raise FinalizationError(f"{owner}[{index}]: claim_text references unknown claim {claim_id!r}")
            leaked = contains_alias(text, aliases)
            if leaked:
                raise FinalizationError(
                    f"{owner}[{index}]: analytical claim text contains current-work identity alias {leaked!r}; renderer-owned Identification controls current-work identity"
                )
            evidence_ids = claim.get("evidence_ids", [])
            if not isinstance(evidence_ids, list):
                raise FinalizationError(f"{owner}[{index}]: claim {claim_id} evidence_ids must be a list")
            missing = [x for x in evidence_ids if x not in evidence_map_current]
            if missing:
                raise FinalizationError(f"{owner}[{index}] claim {claim_id} references missing evidence {', '.join(missing)}")
            named_text = text
            if projection is not None:
                # Exact bound source-location identifiers are administrative,
                # not historical names. Alias checks above still use all text.
                for location_id in (value["correction"]["applies_to"]["representation_id"],
                                    value["correction"]["applies_to"]["span_id"]):
                    named_text = re.sub(r"(?<![\w])" + re.escape(location_id) + r"(?![\w])", "source", named_text)
            names = untyped_named_tokens(named_text, preceding_text=buffer.text(), allow_sentence_initial=True)
            licensed_tokens: set[str] = set()
            entity_ids: list[str] = []
            if isinstance(claim.get("entity_id"), str):
                entity_ids.append(claim["entity_id"])
            if isinstance(claim.get("entity_ids"), list):
                entity_ids.extend(eid for eid in claim["entity_ids"] if isinstance(eid, str))
            for entity_id in dict.fromkeys(entity_ids):
                if entity_id not in entities:
                    continue
                entity = entities[entity_id]
                for field in ("display", "page_token", "page_name_form"):
                    value = entity.get(field)
                    if isinstance(value, str):
                        licensed_tokens.update(untyped_named_tokens(value))
                        licensed_tokens.update(re.findall(r"\b[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]*\b", value))
            unlicensed = [name for name in names if name not in licensed_tokens]
            if unlicensed:
                raise FinalizationError(
                    f"{owner}[{index}]: analytical claim contains untyped named referent(s) {', '.join(unlicensed)}; register the referent in entities and bind it with entity_id/entity_ids"
                )
            status = claim.get("analytical_status", claim.get("status"))
            if projection is not None:
                if status not in {"asserted", "verified", "secure"}:
                    raise FinalizationError("SPECIALIZATION_PROJECTION_OUTPUT_STATUS")
                text = projection
            prefix = "Inference: " if status == "inference" else ("Unresolved: " if status == "unresolved" else "")
            matches = [a for a in assertion_map_current.values() if a.get("claim_id") == claim_id and a["id"] in selected_assertions_current]
            if len(matches) != 1 or matches[0]["projection"] != text or matches[0]["form"] != "CANONICAL":
                raise FinalizationError("SPECIALIZATION_GOVERNED_PROJECTION_REQUIRED")
            start = buffer.length
            if prefix:
                buffer.append(prefix)
            buffer.append(text, {"kind": "ASSERTION", "assertion_id": matches[0]["id"]})
            end = buffer.length
            rendered_claim_text = prefix + text
            spans.append({
                "start": start,
                "end": end,
                "text": rendered_claim_text,
                "role": "analytical_claim",
                "claim_id": claim_id,
                "claim_type": claim.get("claim_type"),
                "analytical_status": claim.get("analytical_status", claim.get("status")),
                "evidence_ids": list(evidence_ids),
            })
            if projection is not None:
                spans[-1].update(projection_profile=specialization_core.PROFILE,
                                 specialization_ref=claim["specialization_ref"],
                                 value_sha256=specialization_core.digest(claim["value"]))
        elif kind == "page_text":
            evidence_ids = segment.get("evidence_ids")
            if not isinstance(evidence_ids, list) or not evidence_ids:
                raise FinalizationError(f"{owner}[{index}]: page_text outside the translation requires evidence_ids")
            emap = evidence_map_current
            missing = [x for x in evidence_ids if x not in emap]
            if missing:
                raise FinalizationError(f"{owner}[{index}] page_text references missing evidence {', '.join(missing)}")
            start, end = buffer.append(text, {"kind": "SOURCE"})
            spans.append({"start": start, "end": end, "text": text, "role": "translated_page_content", "evidence_ids": evidence_ids})


# Set for render_segments while rendering one checkpoint. Kept module-local to
# avoid threading a large map through every small helper in this compact CLI.
evidence_map_current: dict[str, dict[str, Any]] = {}
claim_map_current: dict[str, dict[str, Any]] = {}
assertion_map_current = {}
selected_assertions_current = set()
source_status_current = {}


def render_blocks(
    buffer: RenderBuffer,
    blocks: Any,
    entities: dict[str, dict[str, Any]],
    aliases: set[str],
    spans: list[dict[str, Any]],
    owner: str,
) -> None:
    if not isinstance(blocks, list):
        raise FinalizationError(f"{owner} blocks must be a list")
    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            raise FinalizationError(f"{owner}[{index}] must be an object")
        if set(block) - {"segments"}:
            raise FinalizationError(f"{owner}[{index}] has unsupported field(s)")
        render_segments(buffer, block.get("segments"), entities, aliases, spans, f"{owner}[{index}].segments")
        if index != len(blocks) - 1:
            buffer.append("\n\n")


def identity_render_data(checkpoint: dict[str, Any], plan: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any] | None]:
    state = checkpoint.get("identity_state", "UNIDENTIFIED")
    claims = claim_map(checkpoint)
    identity_plan = plan.get("identity", {})
    cid = identity_plan.get("visible_claim_id")
    verification = identity_plan.get("external_verification", "not_applicable")
    if verification not in evidence_audit.IDENTITY_VERIFICATION_STATUSES:
        raise FinalizationError("identity.external_verification has invalid value")
    if cid is None:
        if state in {"WORK_ESTABLISHED", "EDITION_ESTABLISHED", "EXEMPLAR_ESTABLISHED"}:
            raise FinalizationError(f"{state} final output requires a visible audited work_identity claim")
        if state == "WORK_CANDIDATE":
            line = "**Identification:** Work not established; candidate evidence remains unresolved."
        else:
            line = "**Identification:** Work unidentified from the present evidence."
        output_identity = {
            "proposed_identity": None,
            "identity_state": state,
            "claim_id": None,
            "external_verification": "not_applicable",
            "derived_by": RENDERER_ID,
        }
        return line, output_identity, None
    if state == "UNIDENTIFIED":
        raise FinalizationError("UNIDENTIFIED output cannot expose a visible current-work claim")
    claim = claims.get(cid)
    if claim is None or claim.get("claim_type") != "work_identity":
        raise FinalizationError("identity.visible_claim_id must reference a work_identity claim")
    if not evidence_audit.is_work_identity_promoted(claim):
        raise FinalizationError("visible work identity must be probable or asserted, not a retained lead")
    name = claim.get("value")
    if not isinstance(name, str) or not name.strip():
        raise FinalizationError("visible work_identity claim lacks a name")
    if state == "WORK_CANDIDATE":
        line = f"**Identification:** Candidate: {name}."
    else:
        line = f"**Identification:** {name}."
    output_identity = {
        "proposed_identity": name,
        "identity_state": state,
        "claim_id": cid,
        "external_verification": verification,
        "derived_by": RENDERER_ID,
    }
    return line, output_identity, claim



def derived_transcription_mode(plan: dict[str, Any]) -> str:
    kinds = {section.get("kind") for section in plan.get("sections", []) if isinstance(section, dict)}
    if "diplomatic_latin" in kinds:
        return "scholar_view_diplomatic" if plan.get("mode") == "scholar_view" else "diplomatic"
    if "normalized_latin" in kinds:
        return "normalized"
    return "translation"


def blocked_page_publication(checkpoint: dict[str, Any], plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Bind every blocked region to a literal gap in each supplied-page layer."""
    blocked = [r for r in checkpoint.get("legibility_regions", [])
               if isinstance(r, dict) and (evidence_audit.region_evidence_state(r) in {"PAGE_OBSCURED", "PAGE_LOST"}
                   or r.get("physical_visibility") in evidence_audit.PHYSICALLY_UNREADABLE)]
    if not blocked:
        return []
    recovery_errors: list[str] = []
    emap = evidence_map(checkpoint)
    for region in blocked:
        evidence_audit.audit_blocked_reconstruction(region, emap, recovery_errors)
    if recovery_errors:
        raise FinalizationError("blocked-page recovery audit failed: " + "; ".join(recovery_errors))
    layers = {}
    translation = plan.get("translation", {})
    if isinstance(translation, dict) and translation.get("text"):
        layers["translation"] = translation["text"]
    for kind in ("diplomatic_latin", "normalized_latin"):
        sections = [s for s in plan.get("sections", []) if isinstance(s, dict) and s.get("kind") == kind]
        if len(sections) > 1:
            raise FinalizationError(f"BLOCKED_LAYER_AMBIGUOUS: {kind} occurs more than once")
        if sections:
            paragraphs = []
            for block in sections[0].get("blocks", []):
                parts = []
                for segment in block.get("segments", []):
                    if segment.get("kind") == "linebreak":
                        parts.append("\n")
                    elif segment.get("kind") == "page_text" and isinstance(segment.get("text"), str):
                        parts.append(segment["text"])
                    else:
                        raise FinalizationError(f"BLOCKED_LAYER_UNTYPED: {kind} requires page_text or linebreak segments")
                paragraphs.append("".join(parts))
            layers[kind] = "\n\n".join(paragraphs)
    if not layers and checkpoint["publication_contract"]["scope"]["translation_requirement"] == "NONE":
        return []
    if not layers:
        raise FinalizationError("BLOCKED_LAYER_MISSING: preserve a visible supplied-page gap")
    result = []
    occupied: dict[str, list[tuple[int, int]]] = {}
    seen = set()
    for region in blocked:
        rid = region.get("region_id")
        if not isinstance(rid, str) or not rid or rid in seen:
            raise FinalizationError("BLOCKED_REGION_ID: blocked regions require unique region_id values")
        seen.add(rid)
        spans = region.get("output_spans")
        if not isinstance(spans, list):
            raise FinalizationError(f"BLOCKED_OUTPUT_BINDING_REQUIRED: {rid} requires output_spans in every published page layer")
        covered = set()
        for span in spans:
            if not isinstance(span, dict) or set(span) != {"field", "start", "end"}:
                raise FinalizationError(f"BLOCKED_OUTPUT_SPAN_SHAPE: {rid}")
            field, start, end = span["field"], span["start"], span["end"]
            if field not in layers or type(start) is not int or type(end) is not int or not 0 <= start < end <= len(layers[field]):
                raise FinalizationError(f"BLOCKED_OUTPUT_SPAN_RANGE: {rid}")
            text = layers[field][start:end]
            if not text.strip() or not evidence_audit.is_observational_placeholder(text):
                raise FinalizationError(f"BLOCKED_OUTPUT_FILLED: {rid} {field} must retain a gap, not recovered or conjectural content")
            if any(start < b and a < end for a, b in occupied.get(field, [])):
                raise FinalizationError(f"BLOCKED_OUTPUT_SPAN_OVERLAP: {rid}")
            occupied.setdefault(field, []).append((start, end))
            covered.add(field)
            result.append({"region_id":rid,"layer":{"diplomatic_latin":"diplomatic","normalized_latin":"normalized"}.get(field,field),
                           "evidence_state":evidence_audit.region_evidence_state(region),"text":text,"field":field,"start":start,"end":end})
        if covered != set(layers):
            raise FinalizationError(f"BLOCKED_OUTPUT_LAYER_MISSING: {rid} requires gaps in {sorted(set(layers)-covered)}")
    return result



def compact_source_status(checkpoint):
    # Deterministic projections of already validated token/source status.
    import complete_scholar_view_task as compact
    tokens = {t["token_id"]: t for t in checkpoint.get("foreign_language_tokens", [])}
    summary = compact.foreign_uncertainty_summary(tokens)
    return {"foreign_language_tokens": summary} if summary else {"foreign_language_tokens": "No additional textual uncertainty is recorded in the structured task."}


def render_plan(checkpoint: dict[str, Any], plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    global evidence_map_current, claim_map_current, assertion_map_current, selected_assertions_current, source_status_current
    validate_plan_shape(plan, checkpoint)
    blocked_spans = blocked_page_publication(checkpoint, plan)
    aliases = collect_identity_aliases(checkpoint)
    evidence_map_current = evidence_map(checkpoint)
    claim_map_current = claim_map(checkpoint)
    contract = checkpoint["publication_contract"]
    assertion_map_current = evidence_audit.publication_table(contract["assertions"], "assertions")
    selected_assertions_current = set(contract["scope"]["assertion_ids"])
    source_status_current = compact_source_status(checkpoint)

    entities: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    for entity in plan.get("entities", []):
        if not isinstance(entity, dict):
            raise FinalizationError("every entity must be an object")
        validate_entity(entity, checkpoint, aliases, seen)
        entities[entity["entity_id"]] = entity

    named_issues = collect_named_referent_issues(plan, aliases)
    if named_issues:
        raise FinalizationError(
            "response plan named-referent issues (reported together): " + "; ".join(named_issues)
        )

    buffer = RenderBuffer([])
    response_spans: list[dict[str, Any]] = []
    manifest_entries: list[dict[str, Any]] = []

    identification_line, output_identity, visible_claim = identity_render_data(checkpoint, plan)
    id_start, id_end = buffer.append(identification_line, {"kind": "GENERATED", "generator": "identity"})
    if visible_claim is not None:
        name = output_identity["proposed_identity"]
        local = identification_line.index(name)
        start = id_start + local
        end = start + len(name)
        claim_evidence = list(visible_claim.get("evidence_ids", []))
        emap = evidence_map_current
        provenance = [emap[e].get("provenance") for e in claim_evidence if e in emap and emap[e].get("provenance")]
        manifest_entries.append({
            "claim_id": visible_claim.get("claim_id"),
            "proposed_identity": name,
            "identity_state": checkpoint.get("identity_state"),
            "evidence_ids": claim_evidence,
            "identity_admissible": True,
            "provenance": provenance,
            "external_verification": output_identity["external_verification"],
            "output_spans": [{"start": start, "end": end, "text": name, "role": "current_work_identity"}],
        })
    buffer.append("\n\n")

    translation = plan.get("translation")
    if isinstance(translation, dict) and isinstance(translation.get("text"), str) and translation.get("text").strip():
        buffer.append("**Translation**\n\n")
        text = translation["text"]
        start, end = buffer.append(text, {"kind": "SOURCE", "field": "translation"})
        response_spans.append({"start": start, "end": end, "text": text, "role": "translated_page_content"})
        buffer.append("\n\n")

    sections = plan.get("sections", [])
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            raise FinalizationError(f"sections[{index}] must be an object")
        if set(section) - {"kind", "blocks"}:
            raise FinalizationError(f"sections[{index}] has unsupported field(s)")
        kind = section.get("kind")
        if kind not in SECTION_HEADINGS:
            raise FinalizationError(f"sections[{index}] has unsupported kind {kind!r}")
        buffer.append(f"**{SECTION_HEADINGS[kind]}**\n\n")
        render_blocks(buffer, section.get("blocks"), entities, aliases, response_spans, f"sections[{index}].blocks")
        buffer.append("\n\n")

    if blocked_spans:
        buffer.append("**Supplied-page gaps**\n\n")
        for region in checkpoint.get("legibility_regions", []):
            if not any(s["region_id"] == region.get("region_id") for s in blocked_spans):
                continue
            recovery = region.get("reconstruction")
            if isinstance(recovery, dict) and recovery.get("text"):
                buffer.append("The supplied-page wording remains unreadable. Witness recovery below is separate from the visible text and does not fill its diplomatic or normalized gap.\n\n", {"kind": "GENERATED", "generator": "source_gap"})
                kind = recovery.get("recovery_kind", "wording")
                label = "Witness-supported sense; exact missing wording unresolved" if kind == "sense" else "Witness-supported reconstruction; not visible supplied-page text"
                start, end = buffer.append(label + ": " + recovery["text"], {"kind": "SOURCE", "region_id": region["region_id"]})
                response_spans.append({"start":start,"end":end,"text":label + ": " + recovery["text"],"role":"translated_page_content","evidence_ids":recovery["evidence_ids"]})
                witnesses = [evidence_map_current[eid] for eid in recovery["evidence_ids"]]
                buffer.append("\nWitness locator: " + "; ".join(str(w.get("witness_id")) + " - " + str(w.get("source_locator")) + " - " + str(w.get("passage_locator")) for w in witnesses) + "\n\n", {"kind": "GENERATED", "generator": "witness_locator"})
            else:
                buffer.append("The obscured supplied-page span remains unreadable. Missing wording and meaning are unresolved; unsupported guessing is refused. Secure visible text on either side is retained.\n\n", {"kind": "GENERATED", "generator": "source_gap"})

    confidence = plan.get("confidence")
    if confidence is not None:
        if not isinstance(confidence, dict) or set(confidence) - {"segments"}:
            raise FinalizationError("confidence must contain only segments")
        buffer.append("**Confidence and identity status**\n\n")
        render_segments(buffer, confidence.get("segments"), entities, aliases, response_spans, "confidence.segments")
        buffer.append(f"\nIdentity state: {checkpoint.get('identity_state', 'UNIDENTIFIED')}", {"kind": "GENERATED", "generator": "identity_status"})
        buffer.append("\n")

    text = buffer.text()
    if not text.endswith("\n"):
        buffer.append("\n")
        text = buffer.text()

    plan_hash = sha256_json(plan)
    manifest = {
        "derived_by": RENDERER_ID,
        "derived_from_plan_sha256": plan_hash,
        "entries": manifest_entries,
    }
    final_response = {
        "text": text,
        "spans": response_spans,
        "publication_roles": buffer.roles,
        "identity_manifest": manifest,
        "derived_by": RENDERER_ID,
        "derived_from_plan_sha256": plan_hash,
        "response_sha256": sha256_text(text),
    }
    bindings = CompletionBindings.create(plan, text, manifest)
    receipt = CompletionReceipt.create(
        status="rendered",
        renderer=RENDERER_ID,
        schema_version=PLAN_SCHEMA_VERSION,
        bindings=bindings,
    ).to_dict()
    rendered = {"identity": output_identity, "final_response": final_response, "finalization": receipt}
    if blocked_spans:
        rendered["transcription_spans"] = blocked_spans
    return rendered, receipt


def finalize(checkpoint: dict[str, Any], plan: dict[str, Any]) -> tuple[dict[str, Any], str]:
    def prepare(working: dict[str, Any], structured_plan: dict[str, Any]) -> dict[str, Any]:
        if working.get("schema_version") != PLAN_SCHEMA_VERSION:
            raise CompletionError(
                f"Alpha 9 finalization requires checkpoint schema_version {PLAN_SCHEMA_VERSION}"
            )
        output = working.setdefault("output", {})
        output["stage"] = "draft"
        output["transcription_mode"] = derived_transcription_mode(structured_plan)
        output.pop("final_response", None)
        output.pop("finalization", None)
        output.pop("critical_claim_audit", None)
        return working

    def pre_render_audit(
        working: dict[str, Any], structured_plan: dict[str, Any]
    ) -> AuditResult:
        return AuditResult.from_v01_strings(evidence_audit.audit_checkpoint(working) + evidence_audit.audit_publication_contract(working, structured_plan))

    def render(
        working: dict[str, Any], structured_plan: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        return render_plan(working, structured_plan)

    def assemble(
        working: dict[str, Any],
        structured_plan: dict[str, Any],
        rendered_result: tuple[dict[str, Any], dict[str, Any]],
    ) -> dict[str, Any]:
        rendered, _ = rendered_result
        output = working["output"]
        output.update(rendered)
        output["stage"] = "final"
        claims = claim_map(working)
        categories = sorted(evidence_audit.critical_output_categories(working, claims))
        output["critical_claim_audit"] = {
            "status": "passed",
            "fail_closed": True,
            "reviewed_categories": categories,
            "derived_by": RENDERER_ID,
        }
        return working

    def final_audit(
        working: dict[str, Any], structured_plan: dict[str, Any]
    ) -> AuditResult:
        return AuditResult.from_v01_strings(evidence_audit.audit_pre_output(working))

    controller = GuardedCompletion(
        prepare=prepare,
        pre_render_audit=pre_render_audit,
        render=render,
        assemble=assemble,
        final_audit=final_audit,
        extract_response=lambda working: working["output"]["final_response"]["text"],
        extract_receipt=lambda working: working["output"]["finalization"],
        pre_failure_prefix="checkpoint evidence audit failed before rendering: ",
        final_failure_prefix="final pre-output audit failed: ",
    )
    try:
        result = controller.run(checkpoint, plan)
    except CompletionError as exc:
        raise FinalizationError(str(exc)) from exc
    return result.state, result.response_text


def load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FinalizationError(f"cannot read {label} {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise FinalizationError(f"{label} must be a JSON object")
    return value


def atomic_write(path: Path, text: str) -> None:
    if path.exists():
        raise FinalizationError(f"refusing to overwrite existing finalization artifact {path}")
    if not path.parent.exists():
        raise FinalizationError(f"output directory does not exist: {path.parent}")
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        finally:
            raise


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("response_plan", type=Path)
    parser.add_argument("--output", type=Path, help="write the audited final response text here")
    parser.add_argument("--checkpoint-output", type=Path, help="write the finalized audited checkpoint here")
    args = parser.parse_args()
    try:
        checkpoint = load_object(args.checkpoint, "checkpoint")
        plan = load_object(args.response_plan, "response plan")
        if args.output and args.checkpoint_output and args.output.resolve() == args.checkpoint_output.resolve():
            raise FinalizationError("--output and --checkpoint-output must be different paths")
        # Refuse stale destinations before any write. This prevents a previous
        # artifact from being mistaken for the current finalization result.
        for path in (args.output, args.checkpoint_output):
            if path is not None and path.exists():
                raise FinalizationError(f"refusing to overwrite existing finalization artifact {path}")
        finalized, text = finalize(checkpoint, plan)
        # Commit the audit record first, then the user-visible response. A write
        # failure therefore cannot leave a new response without its receipt.
        if args.checkpoint_output:
            write_json_atomic(args.checkpoint_output, finalized)
        if args.output:
            atomic_write(args.output, text)
        # Alpha 10 emission contract: successful stdout is always the exact
        # approved user-facing response, whether or not forensic artifacts are
        # also written. Do not print status, paths, hashes, or acknowledgements.
        print(text, end="")
        return 0
    except (FinalizationError, OSError) as exc:
        print(f"FAIL\n- {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
