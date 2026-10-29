"""Source ancestry, structure, ownership, coverage and permission substrate.
All records live in the selected task, never in the installed package.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re

from hti_core.source_representation import RepresentationRegistry

SCHEMA = "hti-source-integrity-1"
TYPES = frozenset({"SUPPLIED_PAGE_IMAGE", "FACSIMILE_SCAN", "RAW_OCR", "CORRECTED_OCR",
    "DIPLOMATIC_TRANSCRIPTION", "NORMALIZED_TRANSCRIPTION", "WITNESS_RECONSTRUCTION",
    "HISTORICAL_TRANSLATION", "MODERN_TRANSLATION", "SCHOLARLY_EDITION", "SECONDARY_QUOTATION",
    "EXTRACTED_PROPOSITION", "DERIVED_SUMMARY", "ORIGINAL_TEXT", "PASTED_QUOTATION"})
IMAGE_TYPES = frozenset({"SUPPLIED_PAGE_IMAGE", "FACSIMILE_SCAN"})
REGION_CLASSES = frozenset({"MAIN_BODY", "RUNNING_HEAD", "PAGE_NUMBER", "SIGNATURE", "CATCHWORD",
    "PRINTED_MARGIN_NOTE", "PRINTED_MARGIN_REFERENCE", "SPEAKER_LABEL", "QUOTATION_MARKER",
    "SECTION_HEADING", "FOOTNOTE_OR_NOTE", "MANUSCRIPT_ANNOTATION", "DECORATION_OR_ORNAMENT",
    "UNKNOWN_REGION"})
PARATEXT_LABELS = {"RUNNING_HEAD":"Running head", "PAGE_NUMBER":"Page number",
    "SIGNATURE":"Signature", "CATCHWORD":"Catchword", "PRINTED_MARGIN_NOTE":"Margin note",
    "PRINTED_MARGIN_REFERENCE":"Margin reference", "SPEAKER_LABEL":"Speaker label",
    "MANUSCRIPT_ANNOTATION":"Manuscript annotation", "DECORATION_OR_ORNAMENT":"Decoration",
    "UNKNOWN_REGION":"Unclassified region"}
LAYERS = frozenset({"LAYOUT", "TRANSCRIPTION", "NORMALIZATION", "TRANSLATION",
    "PROPOSITION_OWNERSHIP", "HISTORICAL_RELATION"})
RISKS = frozenset({"NEGATION", "MODAL", "ADVERSATIVE_CONCESSIVE", "QUANTIFIER", "SCOPE_TERM",
    "SPEAKER_MARKER", "QUOTATION_BOUNDARY", "TECHNICAL_TERM", "PROPER_NAME", "BIBLICAL_LEMMA",
    "ORIGINAL_LANGUAGE_FORM", "CITATION_LOCATOR", "PARATEXT_BODY_BOUNDARY"})
PROVISIONAL_PURPOSES = frozenset({"DISCOVERY", "SEARCH_LEAD", "SOURCE_NOMINATION", "TOPIC_NOMINATION",
    "POSSIBLE_PARALLEL_NOMINATION", "PROVISIONAL_TEXT"})
PURPOSES = PROVISIONAL_PURPOSES | frozenset({"REPRESENTED_ARGUMENT", "VISIBLE_CONTENT",
    "TRANSCRIBED_WORDING", "EXACT_ORIGINAL_WORDING", "SECURE_PROPOSITION_OWNERSHIP",
    "SECURE_AUTHOR_POSITION", "DIRECT_DEPENDENCE", "EDITION_FACT", "SPECIALIZATION_FACT"})
STATES = frozenset({"VISIBLE", "UNCERTAIN", "OBSCURED", "LOST", "RECONSTRUCTED", "CONJECTURAL"})
RELATIONS = frozenset({"DERIVED_FROM", "OCR_FROM", "CORRECTED_FROM", "TRANSCRIBED_FROM",
    "NORMALIZED_FROM", "RECONSTRUCTED_FROM", "TRANSLATED_FROM", "EXTRACTED_FROM", "SUMMARIZED_FROM"})


class IntegrityError(ValueError):
    pass


def need(condition, code, detail):
    if not condition:
        raise IntegrityError(code + ": " + str(detail))


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def ids(items, label):
    need(isinstance(items, list), "LIST_REQUIRED", label)
    result = []
    for item in items:
        need(isinstance(item, str) and bool(item.strip()), "ID_REQUIRED", label)
        result.append(item)
    need(len(result) == len(set(result)), "DUPLICATE_ID", label)
    return result


def indexed(items, label):
    need(isinstance(items, list), "LIST_REQUIRED", label)
    out = {}
    for item in items:
        need(isinstance(item, dict), "OBJECT_REQUIRED", label)
        key = item.get("id")
        need(isinstance(key, str) and bool(key.strip()), "ID_REQUIRED", label)
        need(key not in out, "DUPLICATE_ID", key)
        out[key] = item
    return out


class IntegrityRegistry:
    def __init__(self, value):
        need(isinstance(value, dict) and value.get("schema_version") == SCHEMA, "SCHEMA", SCHEMA)
        self.raw = copy.deepcopy(value)
        self.work_id = value.get("work_id")
        need(isinstance(self.work_id, str) and bool(self.work_id.strip()), "WORK_REQUIRED", self.work_id)
        self.nodes = indexed(self.raw.get("representations"), "representations")
        self.risks = indexed(self.raw.get("risks"), "risks")
        self.uses = self.raw.get("uses")
        self.bindings = self.raw.get("output_bindings")
        need(isinstance(self.uses, list) and isinstance(self.bindings, list), "LIST_REQUIRED", "uses/output_bindings")
        self.notices = []
        self._validate()
        self.argument = ArgumentIntegrity(self, self.raw["argument_integrity"]) if "argument_integrity" in self.raw else None

    def spans(self, node):
        return indexed(self.nodes[node].get("spans", []), node + " spans")

    def parent_snapshot(self, node, span_ids):
        """Span-local binding; a changed unrelated span need not stale this edge."""
        n = self.nodes[node]
        spans = self.spans(node)
        selected = ids(span_ids, "parent span_ids")
        need(set(selected) <= spans.keys(), "UNKNOWN_SPAN", (node, selected))
        regions = {x["id"]: x for x in n.get("regions", [])}
        relevant_regions = sorted({spans[s].get("region_id") for s in selected if spans[s].get("region_id")})
        payload = {"type": n["type"], "work_id": n.get("work_id", self.work_id),
                   "verification": n.get("verification", {}),
                   "spans": [spans[s] for s in selected],
                   "regions": [regions[k] for k in relevant_regions if k in regions]}
        if not selected:
            payload["source_sha256"] = n.get("source_sha256")
            payload["content"] = n.get("content")
        return digest(payload)

    def _validate(self):
        for key, node in self.nodes.items():
            need(node.get("type") in TYPES, "REPRESENTATION_TYPE", key)
            need(node.get("work_id", self.work_id) == self.work_id, "CROSS_WORK", key)
            need(type(node.get("revision")) is int and node["revision"] > 0, "REVISION", key)
            parents = node.get("parents")
            need(isinstance(parents, list), "PARENTS_REQUIRED", key)
            need(node.get("supply_status") in {"SUPPLIED", "DERIVED"}, "SUPPLY_STATUS", key)
            need(bool(parents) == (node["supply_status"] == "DERIVED"), "DIRECT_ANCESTRY_REQUIRED", key)
            need(isinstance(node.get("provenance"), dict) and node["provenance"].get("origin"), "PROVENANCE", key)
            if node["supply_status"] == "SUPPLIED":
                need(isinstance(node["provenance"].get("root_id"), str) and node["provenance"]["root_id"], "ROOT_REQUIRED", key)
            if node["type"] not in IMAGE_TYPES:
                need(isinstance(node.get("content"), str), "TEXT_CONTENT", key)
            spans = self.spans(key)
            if node["type"] not in IMAGE_TYPES:
                need(bool(spans) or not node["content"], "CONTENT_SPANS_REQUIRED", key)
                separator=node.get("separator", "\n")
                need(separator in {"", " ", "\n", "\n\n"}, "SPAN_SEPARATOR", key)
                need(node["content"]==separator.join(s["text"] for s in spans.values()), "CONTENT_SPAN_MISMATCH", key)
            for span in spans.values():
                need(span.get("state") in STATES and isinstance(span.get("text"), str), "SPAN_STATE", (key, span["id"]))
                need(span.get("source_class") in REGION_CLASSES, "SPAN_CLASS", (key, span["id"]))
                if node["type"] in {"MODERN_TRANSLATION", "HISTORICAL_TRANSLATION"} and span["source_class"] in PARATEXT_LABELS and span["state"] in {"VISIBLE","UNCERTAIN"}:
                    label=PARATEXT_LABELS[span["source_class"]]+": "
                    need(span["text"].startswith(label),"PARATEXT_LABEL_REQUIRED",(key,span["id"],label))
                    need(node.get("separator","\n") in {"\n","\n\n"},"PARATEXT_BLOCK_SEPARATOR",key)
                if span["state"] in {"OBSCURED", "LOST"}:
                    need(span["text"] in {"", "[obscured]", "[unreadable]", "[missing]", "[...]"}, "UNREADABLE_FABRICATION", span["id"])
                if span["state"] != "VISIBLE":
                    need(isinstance(span.get("uncertainty"), str) and span["uncertainty"].strip(), "UNCERTAINTY_REQUIRED", span["id"])
                    self.notices.append(span["uncertainty"])
            verification = node.get("verification", {})
            need(isinstance(verification, dict) and set(verification) <= LAYERS, "LAYER_VERIFICATION", key)
            for layer, review in verification.items():
                need(isinstance(review, dict) and review.get("status") in {"UNREVIEWED", "VERIFIED", "REVIEWED", "ADJUDICATED"}, "REVIEW_STATE", (key, layer))
                if review["status"] != "UNREVIEWED":
                    basis = ids(review.get("basis"), "review basis")
                    need(bool(basis) and set(basis) <= self.nodes.keys() and bool(review.get("note")), "REVIEW_BASIS", (key, layer))
                    allowed = {"LAYOUT": IMAGE_TYPES, "TRANSCRIPTION": IMAGE_TYPES | {"ORIGINAL_TEXT", "CORRECTED_OCR", "DIPLOMATIC_TRANSCRIPTION", "SCHOLARLY_EDITION"},
                               "NORMALIZATION": {"NORMALIZED_TRANSCRIPTION"}, "TRANSLATION": {"HISTORICAL_TRANSLATION", "MODERN_TRANSLATION"},
                               "PROPOSITION_OWNERSHIP": {"EXTRACTED_PROPOSITION"}, "HISTORICAL_RELATION": {"EXTRACTED_PROPOSITION", "DERIVED_SUMMARY"}}
                    need(node["type"] in allowed[layer], "REVIEW_LAYER_MISMATCH", (key, layer))
            if node["type"] in IMAGE_TYPES:
                need(re.fullmatch(r"[0-9a-f]{64}", node.get("source_sha256", "")) is not None, "IMAGE_HASH", key)
                regions = indexed(node.get("regions"), "page regions")
                need(bool(regions), "PAGE_STRUCTURE_REQUIRED", key)
                for region in regions.values():
                    need(region.get("class") in REGION_CLASSES, "REGION_CLASS", region["id"])
                for span in spans.values():
                    region = regions.get(span.get("region_id"))
                    need(region is not None and region["class"] == span["source_class"], "SPAN_REGION_CLASS", span["id"])
                order = node.get("reading_order")
                need(isinstance(order, dict), "READING_ORDER_REQUIRED", key)
                groups = order.get("sequences")
                need(isinstance(groups, list) and all(isinstance(g, list) for g in groups), "ORDER_SEQUENCES", key)
                ordered = [x for group in groups for x in ids(group, "sequence")]
                unresolved = ids(order.get("unresolved_regions"), "unresolved regions")
                need(set(ordered + unresolved) <= regions.keys() and not set(ordered) & set(unresolved), "READING_ORDER_REFERENCE", key)
                need(len(ordered) == len(set(ordered)), "ORDER_DUPLICATION", key)
                required = {x["id"] for x in regions.values() if x["class"] in {"MAIN_BODY", "SPEAKER_LABEL", "QUOTATION_MARKER", "UNKNOWN_REGION"}}
                need(required <= set(ordered + unresolved), "STRUCTURE_NOT_ACCOUNTED", key)
                if unresolved:
                    need(bool(order.get("uncertainty")), "ORDER_UNCERTAINTY_REQUIRED", key)
                    self.notices.append(order["uncertainty"])
            for edge in parents:
                need(isinstance(edge, dict) and edge.get("id") in self.nodes and edge["id"] != key, "PARENT_REFERENCE", key)
                need(edge.get("relation") in RELATIONS, "DERIVATION_RELATION", key)
                need(type(edge.get("revision")) is int and edge["revision"] > 0, "PARENT_REVISION", key)
                need(edge["revision"] <= self.nodes[edge["id"]]["revision"], "FUTURE_PARENT_REVISION", key)
                need(re.fullmatch(r"[0-9a-f]{64}", edge.get("snapshot", "")) is not None, "PARENT_SNAPSHOT", key)
                ids(edge.get("span_ids"), "parent span_ids")
                self.parent_snapshot(edge["id"], edge["span_ids"])
                if node["type"] in IMAGE_TYPES:
                    need(self.nodes[edge["id"]]["type"] in IMAGE_TYPES,"IMAGE_PARENT_REQUIRED",key)
                if node["type"]=="CORRECTED_OCR":
                    need(self.nodes[edge["id"]]["type"] in {"RAW_OCR","CORRECTED_OCR"},"OCR_CORRECTION_PARENT_REQUIRED",key)
            evidence = ids(node.get("evidence_ids", []), "evidence_ids")
            need(len(evidence) == len(set(evidence)), "EVIDENCE_BINDING", key)
        visiting, done = set(), set()
        def visit(key):
            need(key not in visiting, "ANCESTRY_CYCLE", key)
            if key in done: return
            visiting.add(key)
            for edge in self.nodes[key]["parents"]: visit(edge["id"])
            visiting.remove(key);done.add(key)
        for key in self.nodes: visit(key)
        for key in self.nodes: self._links(key)
        for risk in self.risks.values():
            node = risk.get("representation_id")
            need(node in self.nodes and risk.get("category") in RISKS, "SEMANTIC_RISK", risk["id"])
            scope = ids(risk.get("span_ids"), "risk span_ids")
            need(bool(scope) and set(scope) <= self.spans(node).keys(), "RISK_SPAN", risk["id"])
            need(risk.get("status") in {"UNRESOLVED", "REVIEWED", "RETAINED_UNCERTAIN"}, "RISK_STATUS", risk["id"])
            need(bool(risk.get("finding")), "RISK_FINDING", risk["id"])
            if risk["status"] == "REVIEWED":
                need(bool(ids(risk.get("basis"), "risk basis")) and set(risk["basis"]) <= self.nodes.keys(), "RISK_BASIS", risk["id"])
            else: self.notices.append(risk["finding"])
        for use in self.uses:
            need(isinstance(use, dict) and use.get("representation_id") in self.nodes and use.get("purpose") in PURPOSES, "USE_REQUEST", use)
            need(set(ids(use.get("span_ids", []), "use span_ids")) <= self.spans(use["representation_id"]).keys(), "USE_SPAN", use)

    def _links(self, key):
        node = self.nodes[key];targets = self.spans(key)
        links = node.get("span_links", [])
        need(isinstance(links, list), "SPAN_LINKS", key)
        declared = {(e["id"], s) for e in node["parents"] for s in e["span_ids"]}
        seen = set();target_sources = {};source_targets = {}
        for link in links:
            need(isinstance(link, dict), "SPAN_LINK", key)
            source = (link.get("parent_id"), link.get("source_span_id"))
            need(source in declared, "UNDECLARED_SPAN_ANCESTRY", (key, source))
            parent_span = self.spans(source[0])[source[1]]
            source_current = all(edge["snapshot"] == self.parent_snapshot(edge["id"],edge["span_ids"])
                                 for edge in node["parents"] if edge["id"]==source[0] and source[1] in edge["span_ids"])
            status = link.get("status")
            need(status in {"PRESERVED", "TRANSFORMED", "UNRESOLVED", "OMITTED", "DUPLICATED"}, "SPAN_DISPOSITION", key)
            seen.add(source)
            if status in {"OMITTED", "UNRESOLVED"}:
                need(bool(link.get("reason")), "SPAN_LIMIT_REQUIRED", source)
                self.notices.append(link["reason"])
            target_id = link.get("target_span_id")
            if status == "OMITTED":
                need(target_id is None, "OMITTED_TARGET", key);continue
            need(target_id in targets, "TARGET_SPAN", (key, target_id))
            target = targets[target_id]
            target_sources.setdefault(target_id, set()).add(source)
            source_targets.setdefault(source, []).append(link)
            if source_current:
                need(parent_span["source_class"] == target["source_class"], "PARATEXT_IN_BODY", (key, source))
            if source_current and parent_span["state"] != "VISIBLE":
                need(target["state"] == parent_span["state"] or node["type"] == "WITNESS_RECONSTRUCTION" and target["state"] in {"RECONSTRUCTED","CONJECTURAL"}, "UNCERTAIN_PROMOTION", key)
            if source_current and status == "PRESERVED":
                need(target["text"] == parent_span["text"], "SILENT_TEXT_CHANGE", (key, source))
            if status in {"TRANSFORMED", "DUPLICATED"}:
                need(bool(link.get("reason")), "TRANSFORMATION_REASON", key)
                need(not re.search(r"remembered|model.memory|guessed", str(link["reason"]), re.I), "MEMORY_REPLACEMENT", key)
                if node["type"] == "DIPLOMATIC_TRANSCRIPTION":
                    need(target["text"] == parent_span["text"], "DIPLOMATIC_CHANGE", key)
                if node["type"] == "CORRECTED_OCR":
                    need(bool(link.get("basis")) and all(x in self.nodes and self.nodes[x]["type"] in IMAGE_TYPES | {"ORIGINAL_TEXT", "SCHOLARLY_EDITION"} for x in link["basis"]), "CORRECTION_BASIS", key)
                if status == "DUPLICATED": self.notices.append(link["reason"])
            script = target.get("language")
            unexpected_script = node.get("language") == "English" and re.search(r"[\u0370-\u03ff\u1f00-\u1fff\u0590-\u05ff]",target["text"])
            if node["type"] in {"MODERN_TRANSLATION", "HISTORICAL_TRANSLATION"} and (unexpected_script or script and script != node.get("language")):
                need(bool(link.get("reason")), "UNEXPECTED_SOURCE_LANGUAGE", key)
                self.notices.append(link["reason"])
        need(declared <= seen, "UNACCOUNTED_DERIVATION_SPAN", (key, sorted(declared - seen)))
        for source, mappings in source_targets.items():
            if len({m["target_span_id"] for m in mappings}) > 1:
                need(all(m["status"]=="DUPLICATED" for m in mappings), "DUPLICATED_TARGET_UNEXPLAINED", (key,source))
        if node["parents"]:
            for span_id in targets:
                need(span_id in target_sources, "TARGET_WITHOUT_ANCESTRY", (key, span_id))

    def roots(self, key):
        node = self.nodes[key]
        if not node["parents"]:
            return {"image:"+node["source_sha256"] if node["type"] in IMAGE_TYPES else node["provenance"]["root_id"]}
        return set().union(*(self.roots(p["id"]) for p in node["parents"]))

    def independent(self, left, right):
        need(left in self.nodes and right in self.nodes, "UNKNOWN_REPRESENTATION", (left, right))
        return not self.roots(left) & self.roots(right)

    def stale(self, key):
        return any(e["snapshot"] != self.parent_snapshot(e["id"], e["span_ids"]) or self.stale(e["id"])
                   for e in self.nodes[key]["parents"])

    def affected(self, key, span_ids=None):
        need(key in self.nodes, "UNKNOWN_REPRESENTATION", key)
        scope = set(span_ids if span_ids is not None else self.spans(key))
        need(scope <= self.spans(key).keys(), "UNKNOWN_SPAN", scope)
        changed = {key: scope};result=[]
        while True:
            added=False
            for child, node in self.nodes.items():
                if child in changed: continue
                selected = {(edge["id"],s) for edge in node["parents"] if edge["id"] in changed
                            for s in edge["span_ids"] if not changed[edge["id"]] or s in changed[edge["id"]]}
                if selected:
                    targets={link["target_span_id"] for link in node.get("span_links", [])
                             if (link["parent_id"],link["source_span_id"]) in selected and link.get("target_span_id")}
                    changed[child]=targets;result.append(child);added=True
            if not added: return result

    def has_review(self, key, layer):
        return self.nodes[key].get("verification", {}).get(layer, {}).get("status") in {"VERIFIED", "REVIEWED", "ADJUDICATED"}

    def original_form_path(self, key, trail=frozenset()):
        if key in trail: return False
        trail=trail | {key}
        node=self.nodes[key]
        if node["type"] not in IMAGE_TYPES | {"ORIGINAL_TEXT","CORRECTED_OCR","DIPLOMATIC_TRANSCRIPTION","SCHOLARLY_EDITION"}:
            return False
        if not node["parents"]: return True
        if node["type"]=="CORRECTED_OCR" and self.has_review(key,"TRANSCRIPTION"):
            basis=node["verification"]["TRANSCRIPTION"]["basis"]
            return bool(basis) and all(b!=key and self.original_form_path(b,trail) for b in basis)
        return all(self.original_form_path(edge["id"],trail) for edge in node["parents"])

    def dependency_scope(self,key,span_ids=()):
        selected=set(span_ids) or set(self.spans(key))
        need(selected <= self.spans(key).keys(),"UNKNOWN_SPAN",(key,selected))
        scopes={key:selected};queue=[key]
        while queue:
            current=queue.pop();node=self.nodes[current]
            for edge in node["parents"]:
                upstream={link["source_span_id"] for link in node.get("span_links",[])
                          if link["parent_id"]==edge["id"] and
                          (link.get("target_span_id") in scopes[current] or link["status"]=="OMITTED")}
                if not edge["span_ids"]: upstream=set(self.spans(edge["id"]))
                previous=scopes.get(edge["id"],set())
                if edge["id"] not in scopes or not upstream <= previous:
                    scopes[edge["id"]]=previous|upstream;queue.append(edge["id"])
        return scopes

    def permit(self, key, purpose, span_ids=()):
        return self._permit(key,purpose,span_ids)

    def _permit(self, key, purpose, span_ids=(), bound_argument=False):
        need(key in self.nodes and purpose in PURPOSES, "LICENSE_REQUEST", (key,purpose))
        need(bound_argument or not self.stale(key), "REVALIDATION_REQUIRED", key)
        lineage = {key}
        def collect(node):
            for edge in self.nodes[node]["parents"]:
                if edge["id"] not in lineage: lineage.add(edge["id"]);collect(edge["id"])
        collect(key)
        def provisional(node):
            current = self.nodes[node]
            if re.search(r"model[_ ]memory|remembered|recollection",str(current["provenance"]["origin"]),re.I): return True
            if current["type"] == "RAW_OCR": return True
            if current["type"] == "CORRECTED_OCR" and self.has_review(node,"TRANSCRIPTION"):
                ancestors=set()
                def gather(n):
                    for edge in self.nodes[n]["parents"]:
                        if edge["id"] not in ancestors: ancestors.add(edge["id"]);gather(edge["id"])
                gather(node)
                basis=current["verification"]["TRANSCRIPTION"]["basis"]
                if all(b in ancestors and self.nodes[b]["type"] in IMAGE_TYPES | {"ORIGINAL_TEXT","SCHOLARLY_EDITION"} and not provisional(b) for b in basis):
                    return False
            return any(provisional(edge["id"]) for edge in current["parents"])
        weak = provisional(key)
        if purpose in PROVISIONAL_PURPOSES: return True
        need(not weak, "PROVISIONAL_QUARANTINE", (key,purpose))
        if purpose in {"DIRECT_DEPENDENCE", "EDITION_FACT", "SPECIALIZATION_FACT"}:
            need(False, "SEPARATE_EVIDENCE_REQUIRED", purpose)
        if purpose in {"SECURE_PROPOSITION_OWNERSHIP", "SECURE_AUTHOR_POSITION"}:
            need(self.has_review(key,"PROPOSITION_OWNERSHIP"), "OWNERSHIP_LAYER_REQUIRED", key)
        if purpose in {"EXACT_ORIGINAL_WORDING", "TRANSCRIBED_WORDING"}:
            need(self.nodes[key]["type"] in IMAGE_TYPES | {"ORIGINAL_TEXT", "CORRECTED_OCR", "DIPLOMATIC_TRANSCRIPTION", "SCHOLARLY_EDITION"}
                 and self.has_review(key,"TRANSCRIPTION"), "TRANSCRIPTION_LAYER_REQUIRED", key)
            need(self.original_form_path(key),"MEDIATED_WORDING_NOT_ORIGINAL",key)
            basis=self.nodes[key]["verification"]["TRANSCRIPTION"]["basis"]
            need(all(self.original_form_path(b) for b in basis),"TRANSCRIPTION_BASIS_REQUIRED",key)
        scopes=self.dependency_scope(key,span_ids)
        selected=scopes[key]
        if purpose in {"EXACT_ORIGINAL_WORDING", "TRANSCRIBED_WORDING", "SECURE_PROPOSITION_OWNERSHIP", "SECURE_AUTHOR_POSITION"}:
            need(not any(link["status"] in {"OMITTED","UNRESOLVED"} for n in lineage for link in self.nodes[n].get("span_links",[])), "LOSSY_STRONG_CLAIM", key)
        for risk in self.risks.values():
            if set(risk["span_ids"]) & scopes.get(risk["representation_id"],set()) and risk["status"] != "REVIEWED" and purpose in {
                "EXACT_ORIGINAL_WORDING", "TRANSCRIBED_WORDING", "SECURE_PROPOSITION_OWNERSHIP", "SECURE_AUTHOR_POSITION"}:
                need(False,"SEMANTIC_RISK_UNRESOLVED",risk["id"])
        if purpose in {"EXACT_ORIGINAL_WORDING", "TRANSCRIBED_WORDING", "SECURE_PROPOSITION_OWNERSHIP", "SECURE_AUTHOR_POSITION"}:
            need(all(self.spans(key)[s]["state"] == "VISIBLE" for s in selected), "UNCERTAIN_STRONG_CLAIM", key)
        return True

    def audit(self):
        for use in self.uses: self.permit(use["representation_id"], use["purpose"], use.get("span_ids", []))
        result = {"status":"PASS", "representations":len(self.nodes),
                "stale_representations":[n for n in self.nodes if self.stale(n)],
                "notices":list(dict.fromkeys(self.notices))}
        if self.argument: result["argument_integrity"] = self.argument.audit()
        return result


OWNERS = frozenset({"AUTHOR", "OPPONENT", "QUOTED_AUTHORITY", "SCRIPTURE", "EDITORIAL", "UNKNOWN"})
VOICE_ROLES = frozenset({"AUTHOR_ASSERTION", "OPPONENT_ASSERTION", "QUOTATION", "OBJECTION",
    "CONCESSION", "DISTINCTION", "REPLY", "REJECTION", "CONCLUSION", "APPLICATION",
    "REPORTED_SPEECH", "SCRIPTURE_LEMMA", "EDITORIAL_OR_PARATEXTUAL_MATERIAL", "UNRESOLVED_VOICE"})
COVERAGE_STATES = frozenset({"REPRESENTED", "NON_PROPOSITIONAL_RETAINED", "QUOTATION",
    "INTERLOCUTOR_MATERIAL", "PARATEXT_EXCLUDED", "OBSCURED", "LOST", "UNCERTAIN",
    "INTENTIONALLY_OMITTED", "UNRESOLVED", "DUPLICATE_ACCOUNTED"})
REPRESENTED_STATES = frozenset({"REPRESENTED", "NON_PROPOSITIONAL_RETAINED", "QUOTATION",
    "INTERLOCUTOR_MATERIAL", "DUPLICATE_ACCOUNTED"})


class ArgumentIntegrity:
    """Ownership and coverage extension of the existing source registry.

    Native PRG types remain in hti_core.argument_architecture. These records
    bind their source and voice semantics without creating another graph.
    """
    def __init__(self, registry, value):
        self.r = registry
        need(isinstance(value, dict), "ARGUMENT_INTEGRITY_OBJECT", value)
        self.raw = value
        self.scopes = indexed(value.get("coverage_scopes"), "coverage_scopes")
        self.coverage = indexed(value.get("coverage"), "coverage")
        self.props = indexed(value.get("propositions"), "propositions")
        self.consumers = indexed(value.get("consumers"), "consumers")
        self.prg = value.get("prg")
        self.notices = []
        self._validate()

    def ref(self, ref):
        need(isinstance(ref, dict) and ref.get("representation_id") in self.r.nodes, "ARGUMENT_SOURCE_REFERENCE", ref)
        spans = ids(ref.get("span_ids"), "argument source span_ids")
        need(bool(spans) and set(spans) <= self.r.spans(ref["representation_id"]).keys(), "ARGUMENT_SOURCE_SPANS", ref)
        need(re.fullmatch(r"[0-9a-f]{64}", ref.get("snapshot", "")) is not None, "ARGUMENT_SOURCE_SNAPSHOT", ref)
        return ref["representation_id"], spans

    def ref_current(self, ref):
        key, spans = self.ref(ref)
        return ref["snapshot"] == self.r.parent_snapshot(key, spans)

    def local_source_snapshot(self, key):
        scopes = self.r.dependency_scope(key)
        return {n: self.r.parent_snapshot(n, sorted(s)) for n,s in sorted(scopes.items())}

    def proposition_snapshot(self, key):
        p = self.props[key]
        return digest({"record":{k:v for k,v in p.items() if k != "snapshot"},
                       "source":self.local_source_snapshot(p["representation_id"]),
                       "speaker_basis":[self.r.parent_snapshot(ref["representation_id"], ref["span_ids"])
                                        for ref in p["speaker_evidence"]]})

    def proposition_current(self, key):
        return self.source_current(self.props[key]["representation_id"]) and self.props[key]["snapshot"] == self.proposition_snapshot(key) and all(
            self.ref_current(ref) for ref in self.props[key]["speaker_evidence"])

    def source_current(self,key):
        # A multi-span parent's changed sibling must not invalidate this span.
        scopes=self.r.dependency_scope(key)
        for child,selected in scopes.items():
            for edge in self.r.nodes[child]["parents"]:
                relevant={link["source_span_id"] for link in self.r.nodes[child].get("span_links",[])
                          if link["parent_id"]==edge["id"] and (link.get("target_span_id") in selected or link["status"]=="OMITTED")}
                if not edge["span_ids"]:
                    if edge["snapshot"]!=self.r.parent_snapshot(edge["id"],[]):return False
                elif relevant:
                    bindings=edge.get("span_snapshots",{})
                    if bindings:
                        if any(bindings.get(s)!=self.r.parent_snapshot(edge["id"],[s]) for s in relevant):return False
                    elif edge["snapshot"]!=self.r.parent_snapshot(edge["id"],edge["span_ids"]):return False
                for link in self.r.nodes[child].get("span_links",[]):
                    if link["parent_id"]!=edge["id"] or link.get("target_span_id") not in selected:continue
                    origin=self.r.spans(edge["id"])[link["source_span_id"]]
                    target=self.r.spans(child)[link["target_span_id"]]
                    if origin["source_class"]!=target["source_class"]:return False
                    if origin["state"]!="VISIBLE" and target["state"]!=origin["state"] and not (self.r.nodes[child]["type"]=="WITNESS_RECONSTRUCTION" and target["state"] in {"RECONSTRUCTED","CONJECTURAL"}):return False
                    if link["status"]=="PRESERVED" and origin["text"]!=target["text"]:return False
        return True

    def scope_snapshot(self, key):
        source = self.scopes[key]["representation_id"]
        n = self.r.nodes[source]
        return digest({"source":self.r.parent_snapshot(source, sorted(self.r.spans(source))),
                       "reading_order":n.get("reading_order"),
                       "inventory":list(self.r.spans(source)),
                       "coverage":[c for c in self.coverage.values() if c["scope_id"] == key]})

    def _validate(self):
        for key,scope in self.scopes.items():
            need(scope.get("representation_id") in self.r.nodes, "COVERAGE_SOURCE", key)
            source = scope["representation_id"]
            need(bool(self.r.spans(source)), "COVERAGE_INVENTORY_REQUIRED", source)
            if self.r.nodes[source]["type"] in IMAGE_TYPES:
                body_regions={x["id"] for x in self.r.nodes[source]["regions"] if x["class"]=="MAIN_BODY"}
                need(body_regions <= {s.get("region_id") for s in self.r.spans(source).values()}, "BODY_REGION_UNINVENTORIED", source)
        seen = set()
        for key,row in self.coverage.items():
            scope = row.get("scope_id")
            need(scope in self.scopes, "COVERAGE_SCOPE", key)
            source=self.scopes[scope]["representation_id"]
            span=row.get("source_span_id")
            need(span in self.r.spans(source), "COVERAGE_SPAN", key)
            token=(scope,span)
            need(token not in seen, "DUPLICATED_SOURCE_COVERAGE", token);seen.add(token)
            actual=self.r.spans(source)[span]
            need(row.get("source_class")==actual["source_class"], "COVERAGE_CLASS", key)
            status=row.get("status")
            need(status in COVERAGE_STATES, "COVERAGE_DISPOSITION", key)
            need(isinstance(row.get("targets"),list), "COVERAGE_TARGETS", key)
            if status=="PARATEXT_EXCLUDED":
                need(actual["source_class"] != "MAIN_BODY", "BODY_AS_PARATEXT", key)
            elif actual["source_class"] != "MAIN_BODY":
                need(status in {"NON_PROPOSITIONAL_RETAINED","QUOTATION","UNCERTAIN","UNRESOLVED"}, "PARATEXT_BODY_COVERAGE", key)
            if status in REPRESENTED_STATES:
                need(bool(row["targets"]), "COVERAGE_TARGET_REQUIRED", key)
            else:
                need(isinstance(row.get("reason"),str) and row["reason"].strip(), "COVERAGE_REASON", key)
                if status != "PARATEXT_EXCLUDED":self.notices.append(row["reason"])
            if status in {"OBSCURED","LOST"}:
                need(actual["state"] in {"OBSCURED","LOST"}, "COVERAGE_UNREADABLE_STATE", key)
            targets=[]
            for target in row["targets"]:
                n,spans=self.ref(target)
                need(self.ref_current(target), "COVERAGE_REVALIDATION_REQUIRED", key)
                dep=self.r.dependency_scope(n,spans)
                need(span in dep.get(source,set()), "COVERAGE_TARGET_ANCESTRY", key)
                targets.extend((n,s) for s in spans)
            need(len(targets)==len(set(targets)), "COVERAGE_TARGET_LOOP", key)
            if len(targets)>1 and status != "DUPLICATE_ACCOUNTED":
                need(bool(row.get("split_reason")), "COVERAGE_SPLIT_REQUIRED", key)
            if status=="DUPLICATE_ACCOUNTED":
                canonical=self.coverage.get(row.get("duplicate_of"))
                need(canonical is not None and canonical["id"] != key and canonical["status"] in REPRESENTED_STATES and canonical["status"] != "DUPLICATE_ACCOUNTED",
                     "COVERAGE_DUPLICATE_BASIS", key)
                need(bool(row.get("reason")), "COVERAGE_REASON", key)
                self.notices.append(row["reason"])
        for key,scope in self.scopes.items():
            body={s["id"] for s in self.r.spans(scope["representation_id"]).values() if s["source_class"]=="MAIN_BODY"}
            need(body <= {span for sc,span in seen if sc==key}, "UNACCOUNTED_BODY_SPAN", sorted(body-{span for sc,span in seen if sc==key}))
        canonical={}
        source_components={}
        for key,p in self.props.items():
            n=p.get("representation_id")
            need(n in self.r.nodes and self.r.nodes[n]["type"]=="EXTRACTED_PROPOSITION", "PROPOSITION_REPRESENTATION", key)
            need(p.get("owner") in OWNERS and p.get("role") in VOICE_ROLES, "PROPOSITION_VOICE", key)
            need(p.get("status") in {"ESTABLISHED","PROVISIONAL","UNRESOLVED"}, "OWNERSHIP_STATUS", key)
            need(p.get("stance") in {"ASSERTS","REPORTS","REJECTS","QUALIFIES","CONCEDES","UNRESOLVED"}, "AUTHOR_STANCE", key)
            need(isinstance(p.get("speaker_evidence"),list), "SPEAKER_EVIDENCE", key)
            for ref in p["speaker_evidence"]:self.ref(ref)
            need(re.fullmatch(r"[0-9a-f]{64}",p.get("snapshot","")) is not None,"PROPOSITION_SNAPSHOT",key)
            if p["status"]=="ESTABLISHED":
                need(p["owner"]!="UNKNOWN" and p["role"]!="UNRESOLVED_VOICE" and bool(p.get("speaker")) and bool(p["speaker_evidence"]), "OWNERSHIP_BASIS_REQUIRED", key)
            else:
                need(bool(p.get("uncertainty")), "OWNERSHIP_UNCERTAINTY", key);self.notices.append(p["uncertainty"])
            if p["owner"]=="UNKNOWN":need(p["status"]!="ESTABLISHED", "UNKNOWN_OWNERSHIP", key)
            required_owner={"AUTHOR_ASSERTION":"AUTHOR","OPPONENT_ASSERTION":"OPPONENT","SCRIPTURE_LEMMA":"SCRIPTURE","EDITORIAL_OR_PARATEXTUAL_MATERIAL":"EDITORIAL"}.get(p["role"])
            if required_owner and p["status"]=="ESTABLISHED":need(p["owner"]==required_owner,"VOICE_OWNER_CONFLICT",key)
            if p["role"] in {"QUOTATION","OBJECTION","REPORTED_SPEECH"}:
                need(p["stance"]!="ASSERTS", "REPORTED_AS_ASSERTION", key)
            if p["role"]=="CONCESSION":need(bool(p.get("qualification")) and p["stance"] in {"CONCEDES","QUALIFIES"}, "CONCESSION_SCOPE_REQUIRED", key)
            if p["role"]=="DISTINCTION":need(len(ids(p.get("distinction_parts"),"distinction parts"))>=2,"DISTINCTION_PARTS_REQUIRED",key)
            if p["role"] in {"REPLY","REJECTION"}:
                targets=ids(p.get("responds_to"),"reply targets")
                need(bool(targets) and set(targets)<=self.props.keys() and key not in targets,"REPLY_TARGET_REQUIRED",key)
            if p.get("repeat_of"):
                need(p["repeat_of"] in self.props and p["repeat_of"]!=key and not self.props[p["repeat_of"]].get("repeat_of") and p["role"] in {"QUOTATION","REPORTED_SPEECH"}, "PROPOSITION_REPEAT_BASIS",key)
            content=self.r.nodes[n]["content"]
            origin=self.r.dependency_scope(n)
            root_spans=sorted((evidence_root,s) for source,ss in origin.items() if not self.r.nodes[source]["parents"] for evidence_root in self.r.roots(source) for s in ss)
            token=(tuple(root_spans),re.sub(r"\s+"," ",content).strip().casefold())
            origin_token=tuple(root_spans)
            if origin_token in source_components and not p.get("repeat_of"):
                need(bool(p.get("split_reason")) and content != self.r.nodes[self.props[source_components[origin_token]]["representation_id"]]["content"],
                     "REPEATED_SOURCE_COMPONENT",key)
            else:source_components[origin_token]=key
            if token in canonical:
                need(p.get("repeat_of")==canonical[token], "DUPLICATED_PROPOSITION", key)
            else:canonical[token]=key
            scopes=self.r.dependency_scope(n)
            controls=[]
            for source,span_ids in scopes.items():
                if self.r.nodes[source]["type"]=="EXTRACTED_PROPOSITION":continue
                for span in self.r.spans(source).values():
                    controlled=span.get("controls_span_ids",[])
                    if controlled:
                        need(set(ids(controlled,"controlled spans"))<=self.r.spans(source).keys(),"VOICE_CONTROL_REFERENCE",span["id"])
                    if span["id"] in span_ids or set(controlled)&span_ids:
                        if span.get("voice") or controlled:controls.append((source,span))
            if p["status"]=="ESTABLISHED" and self.proposition_current(key):
                basis={(ref["representation_id"],s) for ref in p["speaker_evidence"] for s in ref["span_ids"]}
                for source,span in controls:
                    if span.get("controls_span_ids"):need((source,span["id"]) in basis,"DISCOURSE_APPARATUS_UNBOUND",key)
                    voice=span.get("voice")
                    if voice:
                        need(isinstance(voice,dict) and all(p.get(k)==v for k,v in voice.items() if k in {"owner","speaker","role","stance"}), "SOURCE_VOICE_CONFLICT", key)
            # An established review remains layer-scoped and OCR-quarantined.
            if self.proposition_current(key) and p["status"]=="ESTABLISHED":
                self.r._permit(n,"SECURE_PROPOSITION_OWNERSHIP",bound_argument=True)
        for key,c in self.consumers.items():
            need(c.get("kind") in {"CLAIM","PRG_RELATION","ARGUMENT_COMPLETENESS"},"CONSUMER_KIND",key)
            need(c.get("status") in {"CURRENT","REVALIDATION_REQUIRED"},"CONSUMER_STATUS",key)
            need(c.get("purpose") in {"REPRESENTED_ARGUMENT","AUTHOR_POSITION","ARGUMENT_COMPLETENESS","EXACT_ORIGINAL_WORDING"},"CONSUMER_PURPOSE",key)
            need(isinstance(c.get("dependencies"),list) and bool(c["dependencies"]),"CONSUMER_DEPENDENCIES",key)
            for dep in c["dependencies"]:
                need(isinstance(dep,dict) and dep.get("kind") in {"proposition","coverage","consumer"},"CONSUMER_REFERENCE",key)
                table={"proposition":self.props,"coverage":self.scopes,"consumer":self.consumers}[dep["kind"]]
                need(dep.get("id") in table and re.fullmatch(r"[0-9a-f]{64}",dep.get("snapshot","")) is not None,"CONSUMER_BINDING",key)
            if c["kind"]=="ARGUMENT_COMPLETENESS" or c["purpose"]=="ARGUMENT_COMPLETENESS":need(any(d["kind"]=="coverage" for d in c["dependencies"]),"COMPLETENESS_SCOPE_REQUIRED",key)
        # Validate consumer acyclicity without interpreting later domain claims.
        def visit(k,trail):
            need(k not in trail,"CONSUMER_CYCLE",k)
            for d in self.consumers[k]["dependencies"]:
                if d["kind"]=="consumer":visit(d["id"],trail|{k})
        for k in self.consumers:visit(k,set())
        if any("historical_explanation" in c for c in self.consumers.values()):
            from hti_core.historical_explanation import records, validate_consumer
            for c in records(self).values(): validate_consumer(self, c)

    def complete(self,scope):
        source=self.scopes[scope]["representation_id"]
        return all(c["status"] in REPRESENTED_STATES for c in self.coverage.values()
                   if c["scope_id"]==scope and self.r.spans(source)[c["source_span_id"]]["source_class"]=="MAIN_BODY")

    def consumer_snapshot(self,key):
        c=self.consumers[key]
        refs=[]
        for d in c["dependencies"]:
            value={"proposition":self.proposition_snapshot,"coverage":self.scope_snapshot,"consumer":self.consumer_snapshot}[d["kind"]](d["id"])
            refs.append({"kind":d["kind"],"id":d["id"],"snapshot":value})
        return digest({"record":{k:v for k,v in c.items() if k!="dependencies"},"dependencies":refs})

    def consumer_current(self,key):
        if self.consumers[key]["status"] != "CURRENT":return False
        for d in self.consumers[key]["dependencies"]:
            fn={"proposition":self.proposition_snapshot,"coverage":self.scope_snapshot,"consumer":self.consumer_snapshot}[d["kind"]]
            if d["snapshot"]!=fn(d["id"]):return False
            if d["kind"]=="proposition" and not self.proposition_current(d["id"]):return False
            if d["kind"]=="consumer" and (self.consumers[d["id"]]["status"] != "CURRENT" or not self.consumer_current(d["id"])):return False
        return True

    def permit_proposition(self,key,author_position=False):
        need(key in self.props and self.proposition_current(key),"PROPOSITION_REVALIDATION_REQUIRED",key)
        p=self.props[key]
        purpose="SECURE_PROPOSITION_OWNERSHIP" if p["status"]=="ESTABLISHED" else "PROVISIONAL_TEXT"
        self.r._permit(p["representation_id"],purpose,bound_argument=True)
        if author_position:
            need(p["status"]=="ESTABLISHED" and p["owner"]=="AUTHOR" and p["stance"]=="ASSERTS" and
                 p["role"] in {"AUTHOR_ASSERTION","REPLY","REJECTION","CONCLUSION","APPLICATION"} and not p.get("repeat_of"),
                 "NOT_AUTHOR_POSITION",key)
        return True

    def audit(self):
        return {"accounted":True,"complete_scopes":[k for k in self.scopes if self.complete(k)],
                "stale_propositions":[k for k in self.props if not self.proposition_current(k)],
                "stale_consumers":[k for k in self.consumers if not self.consumer_current(k)],
                "notices":list(dict.fromkeys(self.notices))}

    def validate_publication(self,directory,rendered_text,checkpoint):
        # Every supplied root used in output has an inventoried body scope.
        used=set()
        def roots(key):
            n=self.r.nodes[key]
            if not n["parents"]:used.add(key)
            for edge in n["parents"]:roots(edge["id"])
        for b in self.r.bindings:roots(b["representation_id"])
        for p in self.props.values():roots(p["representation_id"])
        covered={s["representation_id"] for s in self.scopes.values()}
        need(used<=covered,"BODY_COVERAGE_SCOPE_REQUIRED",sorted(used-covered))
        need({n for n,v in self.r.nodes.items() if v["type"]=="EXTRACTED_PROPOSITION"} <= {p["representation_id"] for p in self.props.values()},"UNREGISTERED_PROPOSITION","Record every extracted proposition")
        selected = checkpoint["publication_contract"]["scope"]["source_bindings"]
        selected_nodes = {r["id"] for r in selected if r["kind"] == "SOURCE_SPAN"}
        for c in self.coverage.values():
            if c["status"] in REPRESENTED_STATES:
                for ref in c["targets"]:
                    n,spans=self.ref(ref)
                    if n in selected_nodes:
                        selected_spans = set().union(*(set(r["span_ids"]) or set(self.r.spans(n)) for r in selected if r["id"] == n))
                        need(all(self.r.spans(n)[s]["text"] in rendered_text for s in spans if s in selected_spans),"COVERED_TARGET_NOT_VISIBLE",c["id"])
        if any(not r["span_ids"] for r in selected):
            for notice in self.notices:need(notice in rendered_text,"ARGUMENT_LIMIT_NOT_VISIBLE",notice)
        for key,c in self.consumers.items():
            if c["status"]!="CURRENT":continue
            need(self.consumer_current(key),"DOWNSTREAM_REVALIDATION_REQUIRED",key)
            if c["purpose"]=="EXACT_ORIGINAL_WORDING":need(False,"PROPOSITION_NOT_ORIGINAL_WORDING",key)
            if c["purpose"]=="AUTHOR_POSITION":
                def prop_basis(consumer):
                    direct={d["id"] for d in self.consumers[consumer]["dependencies"] if d["kind"]=="proposition"}
                    for d in self.consumers[consumer]["dependencies"]:
                        if d["kind"]=="consumer":direct |= prop_basis(d["id"])
                    return direct
                propdeps=prop_basis(key)
                need(bool(propdeps),"AUTHOR_POSITION_PROPOSITION_REQUIRED",key)
                for p in propdeps:self.permit_proposition(p,author_position=True)
            if c["kind"]=="ARGUMENT_COMPLETENESS" or c["purpose"]=="ARGUMENT_COMPLETENESS":
                need(all(self.complete(d["id"]) for d in c["dependencies"] if d["kind"]=="coverage"),"FALSE_ARGUMENT_COMPLETENESS",key)
        for claim in checkpoint.get("claims",[]):
            if claim.get("claim_type") in {"source_proposition","author_position"} and claim.get("status") not in {"unresolved","possible","candidate"}:
                props=ids(claim.get("proposition_ids"),"claim proposition_ids")
                need(bool(props) and set(props)<=self.props.keys(),"CLAIM_PROPOSITION_BINDING",claim.get("claim_id"))
                for p in props:self.permit_proposition(p,author_position=claim["claim_type"]=="author_position")
        dossier=directory/"hti-argument-dossier.json"
        if self.props or dossier.exists():
            need(dossier.is_file() and (directory/"hti-source-registry.json").is_file(),"NATIVE_DOSSIER_REQUIRED",directory)
            native = self.validate_native(json.loads(dossier.read_text()),json.loads((directory/"hti-source-registry.json").read_text()))
        explanatory = {k:c for k,c in self.consumers.items() if "historical_explanation" in c}
        if explanatory:
            from hti_core.historical_explanation import validate_publication
            graph_path = directory / "hti-historical-graph.json"
            need(graph_path.is_file(), "EXPLANATION_HRG_REQUIRED", directory)
            from hti_core.historical_relations import HistoricalRelationGraph
            from hti_core.dependency_uncertainty import DependencyUncertaintyAnalysis
            request_path = directory / "hti-dependency-uncertainty-request.json"
            need(request_path.is_file(), "EXPLANATION_UNCERTAINTY_REQUIRED", directory)
            import task_state
            publication = task_state.require_ready(directory)
            draft = task_state.current_draft(directory, publication)
            need({graph_path.name,request_path.name} <= set(draft["inputs"]), "EXPLANATION_CURRENT_STAGING_REQUIRED", directory)
            analysis = DependencyUncertaintyAnalysis.from_dict(json.loads(request_path.read_text()), native)
            graph = HistoricalRelationGraph.from_dict(json.loads(graph_path.read_text()), [native], {native.dossier_id:analysis}, self.r)
            bound = {b["consumer_id"] for b in graph.to_dict().get("explanation_bindings", [])}
            need(bound == set(explanatory), "EXPLANATION_GRAPH_BINDINGS", sorted(explanatory))
        from evidence_audit import selected_domain_ids
        if selected_domain_ids(checkpoint, "historical_explanation"):
            from hti_core.historical_explanation import validate_publication
            validate_publication(self, checkpoint, rendered_text)

    def affected(self,source,span_ids):
        need(source in self.r.nodes and set(span_ids)<=self.r.spans(source).keys(),"ARGUMENT_SOURCE_SPANS",source)
        affected=set()
        for key,p in self.props.items():
            scopes=self.r.dependency_scope(p["representation_id"])
            basis=set()
            for ref in p["speaker_evidence"]:basis |= self.r.dependency_scope(ref["representation_id"],ref["span_ids"]).get(source,set())
            if set(span_ids)&(scopes.get(source,set())|basis):affected.add(key)
        scopes={k for k,s in self.scopes.items() if set(span_ids)&self.r.dependency_scope(s["representation_id"]).get(source,set())}
        consumers=set()
        while True:
            more={k for k,c in self.consumers.items() if any(
                d["kind"]=="proposition" and d["id"] in affected or d["kind"]=="coverage" and d["id"] in scopes or
                d["kind"]=="consumer" and d["id"] in consumers for d in c["dependencies"])}
            if more<=consumers:break
            consumers|=more
        return {"propositions":sorted(affected),"coverage_scopes":sorted(scopes),"consumers":sorted(consumers)}

    def validate_native(self,raw,legacy):
        from hti_core.argument_architecture import ArgumentDossier
        dossier=ArgumentDossier.from_dict(raw,RepresentationRegistry.from_dict(legacy))
        need(dossier._raw.get("work_id")==self.r.work_id,"ARGUMENT_WORK_MISMATCH",dossier.dossier_id)
        need(isinstance(self.prg,dict) and self.prg.get("dossier_id")==dossier.dossier_id and self.prg.get("dossier_sha256")==digest(raw),"NATIVE_PRG_BINDING",dossier.dossier_id)
        native={p.proposition_id:p.to_dict() for p in dossier.propositions}
        need(set(native)==set(self.props),"NATIVE_PROPOSITION_SET",dossier.dossier_id)
        for key,p in self.props.items():
            self.permit_proposition(key)
            n=native[key]
            need(n["content"]==self.r.nodes[p["representation_id"]]["content"],"NATIVE_PROPOSITION_CONTENT",key)
            scopes=self.r.dependency_scope(p["representation_id"])
            for link in n["source_links"]:
                source=link["representation_id"];span=link.get("source_span")
                need(isinstance(span,dict) and bool(ids(span.get("span_ids"),"native source spans")) and
                     set(span["span_ids"])<=scopes.get(source,set()),"NATIVE_SOURCE_SPAN_BINDING",key)
            functions=set(n["argument_functions"])
            need(not (p["owner"]!="AUTHOR" and functions&{"PREMISE","SUPPORT","FINAL_CONCLUSION","INTERMEDIATE_CONCLUSION"} and n.get("argument_scope")!="REPORTED_ARGUMENT"),"NONAUTHOR_AS_AUTHOR_PREMISE",key)
            if p.get("repeat_of"):need(not functions&{"PREMISE","SUPPORT","FINAL_CONCLUSION","INTERMEDIATE_CONCLUSION"},"REPEAT_AS_INDEPENDENT_PREMISE",key)
            if p["role"]=="OBJECTION":need("OBJECTION" in functions and not functions&{"FINAL_CONCLUSION","INTERMEDIATE_CONCLUSION"},"OBJECTION_AS_CONCLUSION",key)
            if p["role"] in {"REPLY","REJECTION"}:need("RESPONSE" in functions,"REPLY_FUNCTION",key)
            if p["role"]=="CONCESSION":need("QUALIFICATION" in functions and not functions&{"PREMISE","FINAL_CONCLUSION"},"CONCESSION_AS_COMMITMENT",key)
            if p["role"]=="DISTINCTION":
                need("DISTINCTION" in functions,"DISTINCTION_FLATTENED",key)
                need(set(p["distinction_parts"]) <= self.props.keys(),"DISTINCTION_PART_REFERENCE",key)
                need(any(r.relation_type=="DISTINGUISHES" and {r.source_proposition_id,r.target_proposition_id} <= set(p["distinction_parts"]+[key]) for r in dossier.relations),"DISTINCTION_RELATION_REQUIRED",key)
        for rel in dossier.relations:
            edge=rel.to_dict();s=self.props[edge["source_proposition_id"]];t=self.props[edge["target_proposition_id"]]
            if edge["relation_type"] in {"SUPPORTS","CONCLUDES_FROM","PRESUPPOSES","REQUIRES","DEPENDS_ON"} and s["owner"]!="AUTHOR" and t["owner"]=="AUTHOR":
                need(s["role"] in {"QUOTATION","SCRIPTURE_LEMMA"} and "AUTHORITY" in native[s["id"]]["argument_functions"],"OPPONENT_SUPPORT_AS_AUTHOR_PREMISE",rel.relation_id)
            need(not (s.get("repeat_of") and edge["relation_type"] in {"SUPPORTS","CONCLUDES_FROM"}),"REPEAT_AS_INDEPENDENT_SUPPORT",rel.relation_id)
            matches=[c for c in self.consumers.values() if c["kind"]=="PRG_RELATION" and c.get("relation_id")==rel.relation_id]
            need(len(matches)==1 and matches[0].get("relation_snapshot")==digest(edge),"PRG_RELATION_BINDING",rel.relation_id)
            deps={d["id"] for d in matches[0]["dependencies"] if d["kind"]=="proposition"}
            need({edge["source_proposition_id"],edge["target_proposition_id"]}<=deps,"PRG_ENDPOINT_DEPENDENCIES",rel.relation_id)
            need(matches[0]["status"]=="CURRENT" and self.consumer_current(matches[0]["id"]),"PRG_RELATION_REVALIDATION_REQUIRED",rel.relation_id)
        for key,p in self.props.items():
            if p["role"] in {"REPLY","REJECTION"}:
                for target in p["responds_to"]:
                    need(any({r.source_proposition_id,r.target_proposition_id}=={key,target} and r.relation_type in {"CONTRADICTS","QUALIFIES","DOES_NOT_SUPPORT","INTERPRETS"} for r in dossier.relations),"PRG_REPLY_DISCONNECTED",key)
        if self.prg.get("coverage_complete"):
            need(self.prg.get("coverage_snapshots")=={k:self.scope_snapshot(k) for k in self.scopes},"PRG_COMPLETENESS_REVALIDATION_REQUIRED",dossier.dossier_id)
            need(bool(self.scopes) and all(self.complete(k) for k in self.scopes),"FALSE_ARGUMENT_COMPLETENESS",dossier.dossier_id)
        return dossier


# Current publication resolution only. Native representation, ownership, PRG,
# relation and uncertainty algorithms above remain unchanged.
def publication_native(directory, registry):
    need(registry.argument is not None, "PUBLICATION_ARGUMENT_REQUIRED", directory)
    return registry.argument.validate_native(json.loads((directory / "hti-argument-dossier.json").read_text()), json.loads((directory / "hti-source-registry.json").read_text()))


def publication_graph(directory, registry):
    from hti_core.historical_relations import HistoricalRelationGraph
    from hti_core.dependency_uncertainty import DependencyUncertaintyAnalysis
    native = publication_native(directory, registry)
    p = directory / "hti-dependency-uncertainty-request.json"
    analyses = {native.dossier_id: DependencyUncertaintyAnalysis.from_dict(json.loads(p.read_text()), native)} if p.exists() else {}
    return HistoricalRelationGraph.from_dict(json.loads((directory / "hti-historical-graph.json").read_text()), [native], analyses, registry)


def publication_domain_output(directory, registry, domain, key, checkpoint):
    # Constructors retain their native licenses; adapters additionally bind the
    # selected result to this actual source substrate before byte publication.
    if domain == "historical_explanation":
        from hti_core.historical_explanation import records, render_consumer, validate_consumer
        publication_graph(directory, registry)
        record = records(registry.argument)[key]
        validate_consumer(registry.argument, record)
        need(registry.argument.consumer_current(key), "PUBLICATION_EXPLANATION_STALE", key)
        return render_consumer(registry.argument, record), record["historical_explanation"]
    file = {"cartography": "hti-cartography.json", "novelty": "hti-novelty.json", "historical_infrastructure": "hti-historical-infrastructure.json", "historical_sensitivity": "hti-historical-sensitivity.json", "specialization_onboarding": "hti-specialization-onboarding.json"}[domain]
    path = directory / file
    need(not path.is_symlink() and path.is_file(), "PUBLICATION_DOMAIN_INPUT", file)
    value = json.loads(path.read_text())
    if domain == "cartography":
        from hti_core.cartography import Cartography
        obj = Cartography(value)
        outputs = obj.current_outputs()
    elif domain == "novelty":
        from hti_core.novelty import Novelty
        obj = Novelty(value)
        if obj.anchor_mode:
            obj.validate_anchor(checkpoint, registry)
            return obj.current_outputs()[key], {"status": "UNRESOLVED", "limitations": ["Work identity and historical priority remain unresolved."]}
        outputs = obj.current_outputs()
    elif domain == "historical_infrastructure":
        from hti_core.historical_infrastructure import Infrastructure
        obj = Infrastructure(value); outputs = obj.current_outputs()
    elif domain == "historical_sensitivity":
        from hti_core.historical_sensitivity import Sensitivity
        obj = Sensitivity(value)
        need(key == obj.scenario["id"], "PUBLICATION_DOMAIN_ID", key)
        return obj.render(), {"status": "PROVISIONAL", "limitations": ["Hypothetical sensitivity result; canonical evidence is unchanged."]}
    else:
        from hti_core.specialization_onboarding import validate, render
        validate(value, checkpoint, registry)
        need(key == value["id"], "PUBLICATION_DOMAIN_ID", key)
        return render(value, checkpoint, registry), {"status": "SUPPORTED"}
    need(key in outputs, "PUBLICATION_CURRENT_DOMAIN_RESULT", key)
    metadata = {"status": "SUPPORTED", "limitations": []}
    if domain == "novelty":
        claim = obj.claims[key.removeprefix("novelty:")]
        metadata.update(status="UNRESOLVED" if claim["classification"] == "UNRESOLVED" else "PROVISIONAL" if claim["confidence"] in {"possible","probable"} else "SUPPORTED", limitations=claim["limitations"], classification=claim["classification"], confidence=claim["confidence"])
    return outputs[key], metadata



def publication_native_operation(directory, checkpoint, registry, claim):
    """Project existing typed result APIs, not a second operation ontology."""
    operation = claim.get("operation")
    source = claim.get("native_input")
    need(isinstance(source, dict), "PUBLICATION_NATIVE_OPERATION_INPUT", operation)
    native = publication_native(directory, registry)
    graph = publication_graph(directory, registry) if operation != "TRACE_CONFESSIONAL_LOCUS" else None
    if operation == "TRACE_LINEAGE":
        from hti_core.lineage_engine import construct_lineage_traversal
        need(set(source) == {"anchor", "policy"}, "PUBLICATION_LINEAGE_INPUT", operation)
        result = construct_lineage_traversal(graph, source["anchor"], source["policy"]).lineage.to_dict()
    elif operation in {"ANALYZE_SOURCE_TRANSMISSION", "ADJUDICATE_IMMEDIATE_SOURCE"}:
        from hti_core.source_transmission import construct_source_transmission
        built = construct_source_transmission(source, known_representation_ids=registry.nodes, known_proposition_ids=registry.argument.props, phase5_graph=graph)
        need(built.audit.passed, "PUBLICATION_TRANSMISSION_RESULT", operation)
        result = built.adjudication.to_dict()
    elif operation in {"ANALYZE_RECEPTION", "COMPARE_CONCEPTS"}:
        from hti_core.reception_history import construct_reception_analysis
        refs = {native.dossier_id} | set(registry.argument.props) | {n.node_id for n in graph.nodes}
        built = construct_reception_analysis(source, known_argument_refs=refs, known_representation_ids=registry.nodes, phase5_graph=graph)
        need(built.audit.passed, "PUBLICATION_RECEPTION_RESULT", operation)
        result = built.result.to_dict()
    elif operation in {"TRACE_CONFESSIONAL_LOCUS", "COMPARE_CONFESSIONAL_FORMULATIONS"}:
        from hti_core.confessional_registry import ConfessionalRegistry, LocusRegistry, LocusTraceProfile, construct_confessional_comparison
        resources = Path(__file__).resolve().parents[1] / "resources/confessional-registry"
        confessions = ConfessionalRegistry.from_dict(json.loads((resources / "initial-registry.json").read_text()))
        loci = LocusRegistry.from_dict(json.loads((resources / "loci.json").read_text()))
        if operation == "TRACE_CONFESSIONAL_LOCUS":
            result = LocusTraceProfile.from_dict(source, registry=confessions, loci=loci).to_dict()
        else:
            built = construct_confessional_comparison(source, registry=confessions, loci=loci, licensed_phase5_edges=[e.edge_id for e in graph.active_edges])
            need(built.audit.passed, "PUBLICATION_CONFESSIONAL_RESULT", operation)
            result = built.comparison.to_dict()
    else:
        need(False, "PUBLICATION_UNKNOWN_NATIVE_OPERATION", operation)
    need(claim.get("value") == result, "PUBLICATION_NATIVE_OPERATION_EQUALITY", operation)
    return canonical(result)



def validate_domain_parent(directory, checkpoint, registry, domain, result_id, output):
    import evidence_audit as gate
    # This ephemeral binding projects an already constructed native output. It
    # creates no dossier, identity, search or persistence evidence.
    projected = copy.deepcopy(checkpoint)
    projected["publication_contract"]["scope"]["domain_outputs"] = [{"kind":"DOMAIN_OUTPUT","domain":domain,"id":result_id,"snapshot":gate.publication_text_digest(output)}]
    field, hash_field = gate.DOMAIN_FIELDS[domain]
    projected["claims"] = [c for c in projected.get("claims", []) if c.get("claim_type") != domain] + [{"claim_id":"native-output-binding","claim_type":domain,field:result_id,hash_field:gate.publication_text_digest(output)}]
    if domain == "historical_explanation":
        from hti_core.historical_explanation import validate_publication
        validate_publication(registry.argument, projected, output)
    else:
        module = __import__("hti_core." + domain, fromlist=["validate_completion"])
        module.validate_completion(directory, projected, output, registry)


def resolve_publication_parent(directory, checkpoint, registry, ref, purpose="REPRESENTED_ARGUMENT"):
    import evidence_audit as gate
    gate.validate_publication_ref(ref)
    kind, key = ref["kind"], ref["id"]
    value = None; projection = None; snapshot = None
    license = {"status": "UNRESOLVED", "facets": {}, "limitations": [], "ownership": None, "source_layer": None}
    if kind == "SOURCE_SPAN":
        need(key in registry.nodes, "PUBLICATION_SOURCE_REFERENCE", key)
        registry.permit(key, ref["purpose"], ref["span_ids"])
        need(purpose not in {"EXACT_ORIGINAL_WORDING", "SECURE_AUTHOR_POSITION", "DIRECT_DEPENDENCE", "EDITION_FACT", "SPECIALIZATION_FACT"} or ref["purpose"] == purpose, "PUBLICATION_PURPOSE_CEILING", purpose)
        need(purpose not in {"AUTHOR_POSITION", "SECURE_PROPOSITION_OWNERSHIP"}, "PUBLICATION_NATIVE_OWNERSHIP_REQUIRED", key)
        selected = ref["span_ids"] or list(registry.spans(key))
        node = registry.nodes[key]
        value = {"spans": [registry.spans(key)[s] for s in selected], "type": node["type"]}
        projection = node.get("separator", "\n").join(s["text"] for s in value["spans"])
        snapshot = registry.parent_snapshot(key, ref["span_ids"])
        provisional = ref["purpose"] in PROVISIONAL_PURPOSES or any(s["state"] != "VISIBLE" for s in value["spans"])
        license.update(status="PROVISIONAL" if provisional else "SUPPORTED", source_layer=node["type"], limitations=[s["uncertainty"] for s in value["spans"] if s.get("uncertainty")])
    elif kind == "PROPOSITION":
        native = publication_native(directory, registry)
        registry.argument.permit_proposition(key, author_position=purpose in {"AUTHOR_POSITION", "SECURE_AUTHOR_POSITION"})
        need(purpose != "EXACT_ORIGINAL_WORDING", "PUBLICATION_PROPOSITION_NOT_WORDING", key)
        value = next(p.to_dict() for p in native.propositions if p.proposition_id == key)
        record = registry.argument.props[key]
        projection = value["content"]; snapshot = registry.argument.proposition_snapshot(key)
        license.update(status="SUPPORTED" if record["status"] == "ESTABLISHED" else "PROVISIONAL", ownership=record["owner"], source_layer="PROPOSITION_OWNERSHIP", facets={"owner": record["owner"], "role": record["role"], "stance": record["stance"]})
    elif kind in {"PRG_RELATION", "HRG_RELATION"}:
        if kind == "PRG_RELATION":
            native = publication_native(directory, registry)
            value = next(r.to_dict() for r in native.relations if r.relation_id == key)
        else:
            graph = publication_graph(directory, registry)
            edge = graph.edge(key)
            need(edge.active, "PUBLICATION_INACTIVE_RELATION", key)
            value = edge.to_dict()
        snapshot = digest(value); projection = canonical(value)
        license.update(status="PROVISIONAL" if value.get("uncertainty_constrained") or value.get("confidence") in {"possible", "unresolved", "uncertain"} else "SUPPORTED", facets={k: value[k] for k in ("relation_type", "chronology", "access", "confidence") if k in value})
    elif kind == "CONSUMER":
        publication_native(directory, registry)
        value = registry.argument.consumers[key]
        need(registry.argument.consumer_current(key), "PUBLICATION_CONSUMER_STALE", key)
        snapshot = registry.argument.consumer_snapshot(key); projection = value.get("content")
        license.update(status="SUPPORTED", source_layer="PROPOSITION_OWNERSHIP")
    elif kind == "DOMAIN_OUTPUT":
        projection, value = publication_domain_output(directory, registry, ref["domain"], key, checkpoint)
        snapshot = gate.publication_text_digest(projection)
        license.update(status=value.get("status", "SUPPORTED") if value.get("status") in gate.PUBLICATION_STATUSES else "SUPPORTED", facets={k:value[k] for k in ("classification", "chronology", "access", "confidence") if k in value}, limitations=value.get("limitations", []))
    elif kind == "QUESTION":
        value = gate.publication_table(checkpoint["publication_contract"]["anchors"], "anchors")[key]
        need(value["work_id"] == registry.work_id and value["task_directory"] == str(directory.resolve()), "PUBLICATION_QUESTION_SCOPE", key)
        snapshot = digest(value)
        license["limitations"] = value["limitations"]
    elif kind == "EVIDENCE":
        value = next(e for e in checkpoint.get("evidence", []) if e.get("evidence_id") == key)
        snapshot = digest(value); projection = value.get("passage_text", value.get("value"))
        bound = [n for n in registry.nodes.values() if key in n.get("evidence_ids", [])]
        if bound:
            need(len(bound) == 1, "PUBLICATION_EVIDENCE_OWNER", key)
            actual_purpose = "PROVISIONAL_TEXT" if value.get("passage_inspected") is not True else "VISIBLE_CONTENT"
            registry.permit(bound[0]["id"], actual_purpose)
            need(purpose in {"DISCOVERY", "SEARCH_LEAD", "SOURCE_NOMINATION", "TOPIC_NOMINATION", "POSSIBLE_PARALLEL_NOMINATION", "PROVISIONAL_TEXT", "VISIBLE_CONTENT", "REPRESENTED_ARGUMENT"}, "PUBLICATION_EVIDENCE_PURPOSE", purpose)
        else:
            need(value.get("evidence_class") in {"bibliography", "external_authority"}, "PUBLICATION_EVIDENCE_UNBOUND", key)
        license["status"] = "SUPPORTED" if value.get("passage_inspected") is True and value.get("proposition_found") is True else "PROVISIONAL"
        license["limitations"] = value.get("limitations", [])
        # Only explicit inspected structured facets, never a date inferred from
        # a locator, title, access date or an uninspected discovery.
        if license["status"] == "SUPPORTED":
            license["facets"] = value.get("verified_facets", {})
    elif kind == "CLAIM":
        value = next(cl for cl in checkpoint.get("claims", []) if cl.get("claim_id") == key)
        snapshot = digest(value); projection = value.get("value")
        if value.get("origin") in {"specialization", "specialization_fact", "specialization_inference"} and not isinstance(projection, str):
            # Ordinary licensed strings retain their exact visibility path.
            # Non-string values must satisfy the bounded correction profile.
            import specialization_core
            projection = specialization_core.correction_projection(value["value"])
        domain = value.get("claim_type")
        if domain == "native_operation_result":
            projection = publication_native_operation(directory, checkpoint, registry, value)
        elif domain in gate.DOMAIN_FIELDS:
            field, hash_field = gate.DOMAIN_FIELDS[domain]
            projection, native_value = publication_domain_output(directory, registry, domain, value[field], checkpoint)
            need(value.get(hash_field) == gate.publication_text_digest(projection), "PUBLICATION_CLAIM_DOMAIN_HASH", key)
        else:
            need(value.get("evidence_ids") or value.get("proposition_ids") or value.get("specialization_ref"), "PUBLICATION_CLAIM_ANCESTRY", key)
            need(domain in {"work_identity", "edition_identity", "exemplar_identity", "orientation", "provenance", "textual_reading", "exact_glyph", "source_proposition", "author_position", "variant_reading", "witness_reading", "source_attribution", "historical_referent", "page_named_identification", "feature_function", "foreign_token_gloss"} or bool(value.get("specialization_ref")), "PUBLICATION_REDERIVATION_REQUIRED", domain)
            for pid in value.get("proposition_ids", []):
                registry.argument.permit_proposition(pid, author_position=domain == "author_position")
            if value.get("proposition_ids"):
                claim_owners = {registry.argument.props[pid]["owner"] for pid in value["proposition_ids"]}
                license["ownership"] = next(iter(claim_owners)) if len(claim_owners) == 1 else "MULTIPLE_REPORTED"
                license["source_layer"] = "PROPOSITION_OWNERSHIP"
            for eid in value.get("evidence_ids", []):
                evidence = next(e for e in checkpoint["evidence"] if e.get("evidence_id") == eid)
                bindings = [n["id"] for n in registry.nodes.values() if eid in n.get("evidence_ids", [])]
                for node in bindings:
                    registry.permit(node, {"exact_glyph":"EXACT_ORIGINAL_WORDING", "textual_reading":"TRANSCRIBED_WORDING", "author_position":"SECURE_AUTHOR_POSITION", "source_proposition":"SECURE_PROPOSITION_OWNERSHIP"}.get(domain, "PROVISIONAL_TEXT"))
        status = value.get("analytical_status", value.get("status"))
        license["status"] = "UNRESOLVED" if status in {"unresolved", "illegible"} else "PROVISIONAL" if status in {"possible", "candidate", "inference", "probable"} else "SUPPORTED"
        license["facets"] = {k:value[k] for k in ("relation_type", "chronology", "owner") if k in value}
        license["limitations"] = value.get("limitations", [])
        if domain in gate.DOMAIN_FIELDS:
            license["status"] = native_value.get("status", license["status"]) if native_value.get("status") in gate.PUBLICATION_STATUSES else license["status"]
            license["limitations"] = list(dict.fromkeys(license["limitations"] + native_value.get("limitations", [])))
    elif kind == "SOURCE_STATUS":
        from finalize_response import compact_source_status
        need(key == "foreign_language_tokens", "PUBLICATION_STATUS_ID", key)
        value = checkpoint.get(key, []); snapshot = digest(value)
        projection = compact_source_status(checkpoint)[key]; license["status"] = "SUPPORTED"
    else:  # Existing ResearchPlanItem export, not a graph fact or edge.
        allowed = {"hti-historical-graph.json", "hti-argument-dossier.json", "hti-dependency-uncertainty-request.json", "evidence-checkpoint.json"}
        need(ref["file"] in allowed, "PUBLICATION_NATIVE_PLAN_FILE", ref["file"])
        path = directory / ref["file"]
        need(not path.is_symlink() and path.is_file(), "PUBLICATION_NATIVE_PLAN_INPUT", path)
        value = json.loads(path.read_text())
        parts = [p for p in ref["pointer"].split("/") if p]
        if ref["file"] == "evidence-checkpoint.json":
            need(len(parts) == 5 and parts[0] == "claims" and parts[2:4] == ["value", "research_plan"], "PUBLICATION_NATIVE_PLAN_POINTER", ref)
            native_claim = value["claims"][int(parts[1])]
            need(native_claim.get("claim_type") == "native_operation_result" and native_claim.get("operation") == "TRACE_LINEAGE", "PUBLICATION_NATIVE_PLAN_RESULT", key)
            publication_native_operation(directory, checkpoint, registry, native_claim)
        for part in parts:
            value = value[int(part)] if isinstance(value, list) else value[part]
        need(isinstance(value, dict) and value.get("item_id", value.get("id")) == key and value.get("established_graph_fact") is False and value.get("creates_historical_edge") is False, "PUBLICATION_NATIVE_PLAN_NOT_EVIDENCE", key)
        snapshot = digest(value)
    need(snapshot == ref["snapshot"], "PUBLICATION_PARENT_REVALIDATION_REQUIRED", (kind, key))
    if kind == "DOMAIN_OUTPUT" or kind == "CLAIM" and value.get("claim_type") in gate.DOMAIN_FIELDS:
        domain = ref["domain"] if kind == "DOMAIN_OUTPUT" else value["claim_type"]
        result_id = key if kind == "DOMAIN_OUTPUT" else value[gate.DOMAIN_FIELDS[domain][0]]
        validate_domain_parent(directory, checkpoint, registry, domain, result_id, projection)
    return {"value": value, "projection": projection, **license}


def validate_current_publication(directory, checkpoint, plan, registry, rendered_text):
    import task_state
    publication = task_state.descriptor(directory)
    if publication and publication.get("schema") == "hti-publication-3":
        from hti_core.composition import validate_state
        validate_state(directory, checkpoint, publication)
    import evidence_audit as gate
    import task_state
    pub = task_state.require_ready(directory)
    c = gate.validate_publication_contract(checkpoint, plan, pub)
    from finalize_response import finalize
    projected_state, expected_output = finalize(checkpoint, plan)
    need(rendered_text == expected_output, "PUBLICATION_EXACT_RENDERED_STATE", directory)
    scope = c["scope"]
    assertions = gate.publication_table(c["assertions"], "assertions")
    outcomes = gate.publication_table(c["outcomes"], "outcomes")
    for a in c["anchors"]:
        for ref in a["source_refs"] + a["proposition_refs"]:
            resolve_publication_parent(directory, checkpoint, registry, ref)
    for d in c["discoveries"]:
        if d["inspection_status"] == "INSPECTED":
            content = resolve_publication_parent(directory, checkpoint, registry, d["inspection"]["content_ref"], "VISIBLE_CONTENT")
            need(d["inspection"]["relevant_passage"] in (content["projection"] or ""), "PUBLICATION_INSPECTION_CONTENT", d["id"])
        if d["comparator_ref"]:
            resolve_publication_parent(directory, checkpoint, registry, d["comparator_ref"])
    for item in c["research_plan"]:
        if item["native_plan_ref"]:
            resolve_publication_parent(directory, checkpoint, registry, item["native_plan_ref"])
    for obj in c["assertions"] + c["derivations"]:
        parents = [resolve_publication_parent(directory, checkpoint, registry, ref, obj["purpose"]) for ref in obj["parents"]]
        for ref in obj.get("counterevidence", []):
            resolve_publication_parent(directory, checkpoint, registry, ref, "PROVISIONAL_TEXT")
        ceiling = max(gate.PUBLICATION_STATUSES[p["status"]] for p in parents)
        need(gate.PUBLICATION_STATUSES[obj["status"]] <= ceiling, "PUBLICATION_EVIDENCE_STRENGTH_CEILING", obj["id"])
        inherited = set(x for p in parents for x in p["limitations"])
        need(inherited <= set(obj["limitations"]) and (not inherited or inherited <= set(obj.get("uncertainty_inheritance", obj["limitations"]))), "PUBLICATION_UNCERTAINTY_INHERITANCE", obj["id"])
        for k, value in obj["facets"].items():
            need(any(p["facets"].get(k) == value for p in parents), "PUBLICATION_UNLICENSED_FACET", (obj["id"], k))
            # Inspected evidence is not itself a native identity, genealogy,
            # whole-work or originality adjudication. Reuse the typed domain.
            if k in {"historical_dependence", "earliest_known_occurrence", "originality", "whole_work", "work_identity", "edition_identity", "exemplar_identity"} or k == "relation_type" and value != "CONCEPTUAL_AFFINITY":
                licensed = False
                for ref, parent in zip(obj["parents"], parents):
                    if parent["facets"].get(k) != value:continue
                    if ref["kind"] in {"HRG_RELATION", "PRG_RELATION", "DOMAIN_OUTPUT"}:licensed = True
                    if ref["kind"] == "CLAIM" and parent["value"].get("claim_type") in set(gate.DOMAIN_FIELDS) | {"native_operation_result", "work_identity", "edition_identity", "exemplar_identity"}:licensed = True
                need(licensed, "PUBLICATION_NATIVE_FACET_REQUIRED", (obj["id"], k))
        if obj["source_layer"] in TYPES | LAYERS:
            need(any(p["source_layer"] == obj["source_layer"] for p in parents), "PUBLICATION_SOURCE_LAYER_CHANGE", obj["id"])
        owners = {p["ownership"] for p in parents if p["ownership"] is not None}
        if obj["ownership"] in OWNERS - {"UNKNOWN"}:
            need(obj["ownership"] in owners, "PUBLICATION_NATIVE_OWNERSHIP_REQUIRED", obj["id"])
        need(not owners or obj["ownership"] in owners or obj["ownership"] == "MULTIPLE_REPORTED", "PUBLICATION_OWNERSHIP_CHANGE", obj["id"])
        if obj.get("form") == "CANONICAL":
            need(obj["projection"] == parents[0]["projection"], "PUBLICATION_CANONICAL_PAYLOAD", obj["id"])
    for ref in scope["source_bindings"] + scope["domain_outputs"]:
        actual = resolve_publication_parent(directory, checkpoint, registry, ref, ref.get("purpose", "REPRESENTED_ARGUMENT"))
        need(bool(actual["projection"]) and actual["projection"] in rendered_text, "PUBLICATION_SELECTED_SOURCE_NOT_VISIBLE", ref["id"])
    literal_projections = [resolve_publication_parent(directory, checkpoint, registry, ref, ref.get("purpose", "VISIBLE_CONTENT"))["projection"] for ref in scope["source_bindings"]]
    for role in projected_state["output"]["final_response"]["publication_roles"]:
        if role["kind"] != "SOURCE":continue
        chunk = rendered_text[role["start"]:role["end"]]
        if role.get("region_id"):
            recovery = next(r["reconstruction"] for r in checkpoint.get("legibility_regions", []) if r["region_id"] == role["region_id"])
            need(chunk.endswith(": " + recovery["text"]), "PUBLICATION_LITERAL_RECOVERY", role)
        else:
            need(any(projection and chunk in projection for projection in literal_projections), "PUBLICATION_UNBOUND_SOURCE_TEXT", role)
    for retained in scope["retained"]:
        need(isinstance(retained, dict) and set(retained) == {"publication_id", "receipt_sha256", "response_sha256", "source_refs"} and re.fullmatch(r"[0-9a-f]{32}", retained["publication_id"] or ""), "PUBLICATION_RETAINED_BINDING", retained)
        folder = task_state.history_root(directory) / retained["publication_id"]
        need(not folder.is_symlink() and folder.is_dir(), "PUBLICATION_RETAINED_HISTORY", folder)
        receipt = folder / "completion-receipt.json"; response = folder / "validated-response.md"
        need(not receipt.is_symlink() and not response.is_symlink() and receipt.is_file() and response.is_file(), "PUBLICATION_RETAINED_RECEIPT", folder)
        raw = json.loads(receipt.read_text())
        need(raw.get("task_directory") == str(directory.resolve()) and raw.get("publication_id") == retained["publication_id"] and raw.get("status") == "COMPLETE" and raw.get("response_sha256") == retained["response_sha256"] == hashlib.sha256(response.read_bytes()).hexdigest() and retained["receipt_sha256"] == hashlib.sha256(receipt.read_bytes()).hexdigest(), "PUBLICATION_RETAINED_IDENTITY", folder)
        need(isinstance(retained["source_refs"], list) and bool(retained["source_refs"]), "PUBLICATION_RETAINED_CURRENT_SOURCE", folder)
        prior_source = folder / "source-integrity.json"
        expected_source = raw.get("inputs", {}).get("source-integrity.json")
        if prior_source.is_file():
            need(not prior_source.is_symlink() and hashlib.sha256(prior_source.read_bytes()).hexdigest() == expected_source, "PUBLICATION_RETAINED_SUBSTRATE_HASH", folder)
            historical_registry = IntegrityRegistry(json.loads(prior_source.read_text()))
        else:
            # Historical C005 receipts can prove unchanged current substrate
            # directly; never fabricate a missing historical snapshot.
            current_source = directory / "source-integrity.json"
            need(hashlib.sha256(current_source.read_bytes()).hexdigest() == expected_source, "PUBLICATION_RETAINED_SUBSTRATE_MISSING", folder)
            historical_registry = registry
        need(historical_registry.work_id == registry.work_id, "PUBLICATION_RETAINED_WORK", folder)
        for ref in retained["source_refs"]:
            need(ref.get("kind") == "SOURCE_SPAN" and ref["id"] in historical_registry.nodes, "PUBLICATION_RETAINED_SOURCE_REF", ref)
            need(historical_registry.parent_snapshot(ref["id"], ref["span_ids"]) == ref["snapshot"], "PUBLICATION_RETAINED_SOURCE_CHANGED", ref["id"])
            resolve_publication_parent(directory, checkpoint, registry, ref, ref["purpose"])
    from hti_core.composition import load, record_validator
    operation_registry = load()["operations"]
    domain_ops = {op:v["domain"] for op,v in operation_registry.items() if v["domain"]}
    source_ops = {op for op,v in operation_registry.items() if v["result_kind"] == "SOURCE_SPAN"}
    graph_ops = {op for op,v in operation_registry.items() if v["result_kind"] == "HRG_RELATION_OR_NATIVE_OPERATION_RESULT"}
    for step in pub["operation_plan"]["operations"]:
        o = outcomes[step["step_id"]]
        actual = [resolve_publication_parent(directory, checkpoint, registry, ref) for ref in o["result_refs"]]
        if o["status"] == "COMPLETED":
            need(all(p["status"] != "UNRESOLVED" for p in actual), "PUBLICATION_UNRESOLVED_RESULT_NOT_COMPLETE", o["id"])
        if o["status"] in {"COMPLETED", "PARTIAL"}:
            op = step["operation"]
            if op in domain_ops:
                need(any(r["kind"] == "DOMAIN_OUTPUT" and r["domain"] == domain_ops[op] and r in scope["domain_outputs"] for r in o["result_refs"]), "PUBLICATION_NATIVE_OPERATION_RESULT", op)
            elif op in source_ops:
                layers = {"TRANSLATE": {"MODERN_TRANSLATION", "HISTORICAL_TRANSLATION"}, "SCHOLARLY_TRANSLATE": {"MODERN_TRANSLATION", "HISTORICAL_TRANSLATION"}, "TRANSCRIBE_DIPLOMATIC": {"DIPLOMATIC_TRANSCRIPTION"}, "NORMALIZE_LATIN": {"NORMALIZED_TRANSCRIPTION"}}[op]
                need(any(r["kind"] == "SOURCE_SPAN" and r in scope["source_bindings"] and registry.nodes[r["id"]]["type"] in layers for r in o["result_refs"]), "PUBLICATION_SOURCE_OPERATION_RESULT", op)
            elif op == "BUILD_ARGUMENT_DOSSIER":
                need(any(r["kind"] == "PROPOSITION" for r in o["result_refs"]), "PUBLICATION_ARGUMENT_RESULT", op)
            elif op in graph_ops:
                if op == "ASSESS_HISTORICAL_RELATION" or o["status"] == "PARTIAL":
                    need(any(r["kind"] == "HRG_RELATION" for r in o["result_refs"]), "PUBLICATION_HISTORICAL_RESULT", op)
                else:
                    need(any(r["kind"] == "CLAIM" and p["value"].get("claim_type") == "native_operation_result" and p["value"].get("operation") == op for r,p in zip(o["result_refs"],actual)), "PUBLICATION_TYPED_OPERATION_RESULT", op)
            else:
                need(o["assertion_ids"] or any(r in scope["source_bindings"] for r in o["result_refs"]), "PUBLICATION_GOVERNED_OPERATION_RESULT", op)
                if op == "IDENTIFY_WORK" and o["status"] == "COMPLETED":
                    need(checkpoint.get("identity_state") in {"WORK_ESTABLISHED", "EDITION_ESTABLISHED", "EXEMPLAR_ESTABLISHED"} and bool(checkpoint.get("selected_claim_ids")), "PUBLICATION_IDENTITY_NOT_ESTABLISHED", op)
                if op == "VERIFY_SOURCE" and o["status"] == "COMPLETED":
                    need(any(r["kind"] == "EVIDENCE" and p["value"].get("passage_inspected") is True and p["value"].get("proposition_found") is True for r,p in zip(o["result_refs"], actual)), "PUBLICATION_SOURCE_NOT_INSPECTED", op)
        if o["status"] != "COMPLETED":
            need(o["reason"] in rendered_text, "PUBLICATION_INCOMPLETE_LIMIT_NOT_VISIBLE", o["id"])
    translation_steps = [outcomes[s["step_id"]] for s in pub["operation_plan"]["operations"] if s["operation"] in {"TRANSLATE", "SCHOLARLY_TRANSLATE"}]
    if any(o["status"] in {"COMPLETED", "PARTIAL"} for o in translation_steps):
        need(scope["translation_requirement"] in {"FULL", "CORRECTION"} and bool(scope["required_source_bindings"]), "PUBLICATION_TRANSLATION_SCOPE_REQUIRED", scope)
        if scope["translation_requirement"] == "FULL":
            for ref in scope["required_source_bindings"]:
                need(ref["kind"] == "SOURCE_SPAN" and not ref["span_ids"] and registry.nodes[ref["id"]]["type"] in {"MODERN_TRANSLATION", "HISTORICAL_TRANSLATION"}, "PUBLICATION_FULL_TRANSLATION_BINDING", ref)
        else:
            need(any(a["purpose"] == "CORRECTION" for a in assertions.values() if a["id"] in scope["assertion_ids"]), "PUBLICATION_CORRECTION_ACCOUNT_REQUIRED", scope)
    record_validator("source_integrity:validate_current_publication")
    return c


def validate_completion(directory, checkpoint, rendered_text):
    marker=(directory/".hti-state").read_text().strip()
    path=directory/"source-integrity.json"
    need(marker in {"1","2","3"}, "TASK_CONTRACT_VERSION", marker)
    if marker=="1" and not path.exists(): return
    need(path.is_file(), "SOURCE_INTEGRITY_REQUIRED", "Fill source-integrity.json in the task directory")
    registry=IntegrityRegistry(json.loads(path.read_text()))
    if marker=="3":need(registry.argument is not None,"ARGUMENT_INTEGRITY_REQUIRED","Fill the argument_integrity extension")
    need(registry.work_id==checkpoint.get("work_id"), "TASK_WORK_MISMATCH", registry.work_id)
    need(registry.raw.get("task_directory")==str(directory.resolve()), "TASK_DIRECTORY_MISMATCH", directory)
    result=registry.audit()
    image_hash=checkpoint.get("locus",{}).get("image_sha256")
    if image_hash:
        need(any(n["type"] in IMAGE_TYPES and n["source_sha256"]==image_hash for n in registry.nodes.values()), "PAGE_ANCHOR_MISSING", image_hash)
    bound={eid:key for key,n in registry.nodes.items() for eid in n.get("evidence_ids",[])}
    all_bindings=[eid for n in registry.nodes.values() for eid in n.get("evidence_ids",[])]
    need(len(bound)==len(all_bindings), "AMBIGUOUS_EVIDENCE_BINDING", "One representation per evidence id")
    evidence=checkpoint.get("evidence",[])
    for item in evidence:
        if item.get("evidence_class") in {"supplied_image_observation","other_witness","historical_translation","inference_reconstruction"}:
            need(item.get("evidence_id") in bound,"SOURCE_EVIDENCE_UNBOUND",item.get("evidence_id"))
    # Witness independence is verified from registered ancestry, not labels.
    emap={e.get("evidence_id"):e for e in evidence}
    import evidence_audit
    page_nodes={bound[e["evidence_id"]] for e in evidence if e.get("evidence_class")=="supplied_image_observation" and e.get("evidence_id") in bound}
    for region in checkpoint.get("legibility_regions",[]):
        if not isinstance(region,dict) or evidence_audit.region_evidence_state(region) not in {"PAGE_OBSCURED","PAGE_LOST"}:continue
        recovery=region.get("reconstruction")
        if not isinstance(recovery,dict) or not recovery.get("text"):continue
        support=[]
        for eid in recovery.get("evidence_ids",[]):
            if eid not in bound or eid not in emap:continue
            key=bound[eid];item=emap[eid];node=registry.nodes[key]
            allowed={"ORIGINAL_TEXT","SCHOLARLY_EDITION","DIPLOMATIC_TRANSCRIPTION","FACSIMILE_SCAN"}
            if recovery.get("recovery_kind")=="sense":allowed.add("HISTORICAL_TRANSLATION")
            if node["type"] not in allowed or registry.stale(key):continue
            if not page_nodes or not all(registry.independent(key,p) for p in page_nodes):continue
            passage=item.get("passage_text")
            content=node.get("content", "\n".join(s["text"] for s in registry.spans(key).values()))
            if isinstance(passage,str) and passage and passage in content:support.append(key)
        need(bool(support),"BLOCKED_WITNESS_ANCESTRY",region.get("region_id"))
    purposes={"exact_glyph":"EXACT_ORIGINAL_WORDING","textual_reading":"TRANSCRIBED_WORDING",
              "source_proposition":"SECURE_PROPOSITION_OWNERSHIP","author_position":"SECURE_AUTHOR_POSITION",
              "direct_dependence":"DIRECT_DEPENDENCE"}
    for claim in checkpoint.get("claims",[]):
        if claim.get("status") in {"unresolved","possible","candidate"}: continue
        purpose=purposes.get(claim.get("claim_type"))
        if purpose:
            for eid in claim.get("evidence_ids",[]):
                need(eid in bound,"CLAIM_SOURCE_UNBOUND",eid)
                registry.permit(bound[eid],purpose,claim.get("source_span_ids",[]))
    plan_path=directory/"final-response-plan.json"
    plan=json.loads(plan_path.read_text()) if plan_path.exists() else {}
    contract=validate_current_publication(directory,checkpoint,plan,registry,rendered_text)
    selected_nodes={r["id"] for r in contract["scope"]["source_bindings"]}
    translation=(plan.get("translation") or {}).get("text","")
    translation_bound=False
    for binding in registry.bindings:
        need(isinstance(binding,dict) and binding.get("representation_id") in registry.nodes, "OUTPUT_BINDING", binding)
        node=registry.nodes[binding["representation_id"]]
        if node["id"] not in selected_nodes:continue
        selected_refs=[r for r in contract["scope"]["source_bindings"] if r["id"]==node["id"]]
        if all(r["span_ids"] for r in selected_refs):continue
        need(bool(node.get("content")) and node["content"] in rendered_text,"OUTPUT_REPRESENTATION_MISMATCH",node["id"])
        need(not registry.stale(node["id"]),"OUTPUT_REVALIDATION_REQUIRED",node["id"])
        need(binding.get("field") in {"translation","rendered_source_layer"},"OUTPUT_FIELD",binding)
        if binding["field"]=="translation":
            need(node["type"] in {"MODERN_TRANSLATION","HISTORICAL_TRANSLATION"} and node["content"]==translation,"TRANSLATION_BINDING_MISMATCH",node["id"])
            translation_bound=True
    if registry.nodes:
        need(bool(registry.bindings),"OUTPUT_BINDING_REQUIRED","Bind each supplied-source response layer")
        if translation.strip(): need(translation_bound,"TRANSLATION_BINDING_REQUIRED","Bind the full translation field")
    if any(not r["span_ids"] for r in contract["scope"]["source_bindings"]):
        for notice in result["notices"]:
            need(notice in rendered_text,"SOURCE_LIMIT_NOT_VISIBLE",notice)
    legacy=directory/"hti-source-registry.json"
    if legacy.exists():
        old=RepresentationRegistry.from_dict(json.loads(legacy.read_text()))
        compatible={"PAGE_IMAGE":IMAGE_TYPES,"ORIGINAL_TEXT":{"ORIGINAL_TEXT"},
            "TRANSCRIPTION":{"DIPLOMATIC_TRANSCRIPTION","NORMALIZED_TRANSCRIPTION","CORRECTED_OCR","WITNESS_RECONSTRUCTION"},
            "OCR":{"RAW_OCR"},"HISTORICAL_TRANSLATION":{"HISTORICAL_TRANSLATION"},
            "MODERN_TRANSLATION":{"MODERN_TRANSLATION"},"PRIOR_V01_TRANSLATION":{"MODERN_TRANSLATION"},
            "SCHOLARLY_EDITION":{"SCHOLARLY_EDITION"},"PASTED_QUOTATION":{"PASTED_QUOTATION"},
            "SECONDARY_QUOTATION":{"SECONDARY_QUOTATION"}}
        for node in old.representations:
            need(node.representation_id in registry.nodes,"LEGACY_REPRESENTATION_UNBOUND",node.representation_id)
            current=registry.nodes[node.representation_id]
            need(current["type"] in compatible[node.representation_type],"LEGACY_REPRESENTATION_TYPE",node.representation_id)
            need({p.parent_representation_id for p in node.derivations} <= {p["id"] for p in current["parents"]},"LEGACY_ANCESTRY_MISMATCH",node.representation_id)
            if node.source_identity and node.source_identity.work_id:
                need(node.source_identity.work_id==registry.work_id,"LEGACY_CROSS_WORK",node.representation_id)
    if registry.argument:registry.argument.validate_publication(directory,rendered_text,checkpoint)
    from hti_core.composition import dispatch_validators
    dispatch_validators(directory, checkpoint, rendered_text, registry)
    return result


def main():
    import task_state
    p=argparse.ArgumentParser();p.add_argument("command",choices=["interface","audit","snapshot","affected","argument-interface","proposition-snapshot","coverage-snapshot","consumer-snapshot","affected-argument","explanation-render"])
    p.add_argument("--state-dir");p.add_argument("--representation");p.add_argument("--spans",nargs="*",default=[])
    a=p.parse_args()
    try:
        if a.command=="argument-interface":
            print(json.dumps({"owners":sorted(OWNERS),"roles":sorted(VOICE_ROLES),"coverage_states":sorted(COVERAGE_STATES),
                "envelope":["coverage_scopes","coverage","propositions","consumers","prg"],
                "scope_fields":["id","representation_id"],
                "coverage_fields":["id","scope_id","source_span_id","source_class","status","targets","reason when limited","split_reason when atomized","duplicate_of when repeated"],
                "source_binding_fields":["representation_id","span_ids","snapshot"],
                "proposition_fields":["id","representation_id","owner","speaker","role","stance","status","speaker_evidence","snapshot","uncertainty unless established","responds_to for reply/rejection","qualification for concession","distinction_parts for distinction","repeat_of for repeated proposition"],
                "consumer_fields":["id","kind","purpose","status","dependencies","relation_id and relation_snapshot for native PRG relation"],
                "dependency_fields":["kind: proposition, coverage or consumer","id","snapshot"],
                "prg_fields":["dossier_id","dossier_sha256","coverage_complete","coverage_snapshots when completeness asserted"],
                "binding":"Use zero SHA-256 placeholders only while obtaining snapshots; they remain stale until explicit review and binding."},indent=2));return 0
        if a.command=="interface":
            print(json.dumps({"schema_version":SCHEMA,"representation_types":sorted(TYPES),
                "region_classes":sorted(REGION_CLASSES),"verification_layers":sorted(LAYERS),
                "translated_paratext_labels":PARATEXT_LABELS,
                "semantic_risks":sorted(RISKS),"purposes":sorted(PURPOSES),"span_states":sorted(STATES),
                "derivation_relations":sorted(RELATIONS),
                "representation_fields":["id","type","revision","supply_status","provenance","parents","spans","verification","evidence_ids"],
                "supplied_provenance":{"origin":"supplied source kind","root_id":"underlying evidence identity"},
                "image_fields":["source_sha256","regions (id, class)","reading_order (sequences, unresolved_regions, uncertainty when unresolved)"],
                "text_fields":["content","separator (default LF; content equals joined span texts)","language"],
                "span_fields":["id","text","state","source_class","region_id for image","uncertainty unless VISIBLE","language when needed"],
                "parent_fields":["id","relation","revision","span_ids","snapshot"],
                "span_link_fields":["parent_id","source_span_id","target_span_id","status","reason unless PRESERVED","basis for corrected OCR"],
                "span_link_statuses":["PRESERVED","TRANSFORMED","UNRESOLVED","OMITTED","DUPLICATED"],
                "verification_record":{"status":"UNREVIEWED, VERIFIED, REVIEWED or ADJUDICATED","basis":"inspected representation IDs","note":"what was reviewed"},
                "risk_fields":["id","representation_id","span_ids","category","status","finding","basis when REVIEWED"],
                "risk_statuses":["UNRESOLVED","REVIEWED","RETAINED_UNCERTAIN"],
                "use_fields":["representation_id","purpose","span_ids"],
                "output_binding_fields":["representation_id","field: translation or rendered_source_layer"],
                "publication":"Each bound content occurs verbatim in the helper response; unresolved notices also occur verbatim."},indent=2))
            return 0
        directory=task_state.resolve(a.state_dir)
        raw=json.loads((directory/"source-integrity.json").read_text())
        if a.command in {"snapshot","affected"}:raw.pop("argument_integrity",None)
        registry=IntegrityRegistry(raw)
        if a.command=="audit": value=registry.audit()
        elif a.command=="snapshot": value={"snapshot":registry.parent_snapshot(a.representation,a.spans), "span_snapshots":{s:registry.parent_snapshot(a.representation,[s]) for s in a.spans}}
        elif a.command=="affected": value={"affected_representations":registry.affected(a.representation,a.spans or None)}
        else:
            need(registry.argument is not None,"ARGUMENT_INTEGRITY_REQUIRED",a.command)
            if a.command=="affected-argument":value=registry.argument.affected(a.representation,a.spans)
            elif a.command=="explanation-render":
                from hti_core.historical_explanation import render_consumer, records
                value={k:render_consumer(registry.argument,c) for k,c in records(registry.argument).items() if c["status"]=="CURRENT"}
            else:
                fn={"proposition-snapshot":registry.argument.proposition_snapshot,"coverage-snapshot":registry.argument.scope_snapshot,"consumer-snapshot":registry.argument.consumer_snapshot}[a.command]
                value={"snapshot":fn(a.representation)}
        print(json.dumps(value,ensure_ascii=False,indent=2));return 0
    except Exception as exc:
        print("source integrity error: "+str(exc),file=__import__('sys').stderr);return 2


if __name__=="__main__":raise SystemExit(main())
