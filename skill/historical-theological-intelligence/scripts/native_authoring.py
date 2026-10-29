"""Mechanical commentary preparation and full nonpublishing preflight.

No scholarship, review attestation, identity promotion or terminal outcome is
inferred here. Existing kernel/native validators remain authoritative.
"""
from __future__ import annotations
import argparse
import copy
import json
import sys
from pathlib import Path

import evidence_audit as gate
import task_state
import terminal_output

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def initialize(directory, work_id):
    pub = task_state.require_active(directory)
    task_state.validate_selection(pub)
    if pub["route"] != "commentary":
        raise ValueError("COMMENTARY_ROUTE_REQUIRED: use the existing Scholar adapter for Scholar View")
    if not isinstance(work_id, str) or not work_id.strip():
        raise ValueError("WORK_REQUIRED: an isolation token does not establish historical identity")
    checkpoint = load(ROOT / "resources/templates/evidence-checkpoint.json")
    contract = checkpoint.pop("publication_contract")
    checkpoint["work_id"] = work_id
    plan = load(ROOT / "resources/templates/final-response-plan.json")
    plan.update(work_id=work_id, mode="research", translation=None)
    plan.pop("publication_contract_sha256")
    contract.update(task_directory=str(directory.resolve()), work_id=work_id,
                    publication_id=pub["publication_id"], request_sha256=pub["request_sha256"],
                    operation_plan_sha256=gate.publication_digest(pub["operation_plan"]))
    contract["scope"]["translation_requirement"] = "NONE"
    # None is deliberately nonterminal. The author must adjudicate every step.
    contract["outcomes"] = [dict(id=s["step_id"], status=None, result_refs=[],
        assertion_ids=[], plan_item_ids=[], reason="", blocked_by=[], limitations=[])
        for s in pub["operation_plan"]["operations"]]
    contract["scope"]["outcome_ids"] = [o["id"] for o in contract["outcomes"]]
    return {"schema": "hti-commentary-authoring-1", "checkpoint": checkpoint,
            "plan": plan, "contract": contract, "sections": []}


def source_ref(registry, representation_id, span_ids, purpose):
    """Capture an explicitly selected current source; never refresh a review."""
    registry.permit(representation_id, purpose, span_ids)
    return dict(kind="SOURCE_SPAN", id=representation_id, span_ids=list(span_ids),
                purpose=purpose, snapshot=registry.parent_snapshot(representation_id, span_ids))


def projection(record_id, text, parents, *, purpose, source_layer, ownership,
               scope, status, facets=None, qualifiers=None, limitations=None,
               form="CANONICAL", derivation_id=None, entity_ids=None):
    """Construct syntax only. Licensing and exact projection are checked later."""
    return dict(id=record_id, projection=text, projection_sha256=gate.publication_text_digest(text),
                parents=copy.deepcopy(parents), purpose=purpose, source_layer=source_layer,
                ownership=ownership, scope=scope, status=status, currentness="CURRENT",
                facets=copy.deepcopy(facets or {}), qualifiers=list(qualifiers or []),
                limitations=list(limitations or []), form=form, derivation_id=derivation_id,
                entity_ids=list(entity_ids or []))


def review_packet(derivation, publication):
    """Unsigned binding for an ACTUAL separate review of this exact payload."""
    return dict(reviewer=None, distinct_pass=False, publication_id=publication["publication_id"],
                request_sha256=publication["request_sha256"],
                payload_sha256=gate.publication_digest({k:v for k,v in derivation.items() if k != "review"}),
                parents_sha256=gate.publication_digest(derivation["parents"]),
                purpose=derivation["purpose"], retained_qualifications=False,
                source_ownership_fidelity=False, material_changes="", unresolved_conflicts=[], attestation="")


def assemble(directory, bundle):
    pub = task_state.require_active(directory)
    task_state.validate_selection(pub)
    if pub["route"] != "commentary":
        raise ValueError("COMMENTARY_ROUTE_REQUIRED")
    if set(bundle) != {"schema", "checkpoint", "plan", "contract", "sections"} or bundle["schema"] != "hti-commentary-authoring-1":
        raise ValueError("AUTHORING_SHAPE")
    checkpoint, plan, contract = (copy.deepcopy(bundle[k]) for k in ("checkpoint", "plan", "contract"))
    if "publication_contract" in checkpoint or "publication_contract_sha256" in plan or plan.get("sections"):
        raise ValueError("AUTHORING_DUPLICATE_CONTRACT_OR_SECTIONS")
    for key in ("task_directory", "publication_id", "request_sha256"):
        if contract[key] != pub[key]:
            raise ValueError("AUTHORING_STALE_PUBLICATION: " + key)
    if contract["operation_plan_sha256"] != gate.publication_digest(pub["operation_plan"]):
        raise ValueError("AUTHORING_STALE_SELECTION")
    if not (checkpoint["work_id"] == plan["work_id"] == contract["work_id"]):
        raise ValueError("AUTHORING_WORK_MISMATCH")
    sections = []
    for section in bundle["sections"]:
        if set(section) != {"kind", "assertion_ids"} or not isinstance(section["assertion_ids"], list):
            raise ValueError("AUTHORING_SECTION_SHAPE")
        sections.append({"kind": section["kind"], "blocks": [
            {"segments": [{"kind": "assertion_projection", "assertion_id": aid}]}
            for aid in section["assertion_ids"]]})
    plan["sections"] = sections
    checkpoint["publication_contract"] = contract
    plan["publication_contract_sha256"] = gate.publication_digest(contract)
    # Never fill a review, terminal policy attestation or selected outcome.
    gate.validate_publication_contract(checkpoint, plan, pub)
    errors = gate.audit_checkpoint(checkpoint)
    if errors:
        raise ValueError("AUTHORING_CHECKPOINT: " + "; ".join(errors))
    return checkpoint, plan


def prepare(directory, bundle):
    checkpoint, plan = assemble(directory, bundle)
    task_state.research_entry(directory)
    task_state.save(task_state.path(directory, "checkpoint"), checkpoint)
    task_state.save(task_state.path(directory, "plan"), plan)
    # Identity is independently rederived; never relabel evidence to satisfy it.
    import specialization_resources
    specialization_resources.prepare_current(directory)
    task_state.stage_publication(directory)
    return preflight(directory)


def preflight(directory):
    """Same native completion gates, with zero response/receipt commit or stdout."""
    import finalize_response
    import source_integrity
    import specialization_core
    import image_inspection
    from hti_core.composition import begin_validation, record_validator, composition_receipt
    pub = task_state.require_ready(directory)
    if pub["route"] != "commentary":
        raise ValueError("COMMENTARY_ROUTE_REQUIRED")
    for key in ("response", "completion_receipt"):
        if task_state.path(directory, key).exists():
            raise ValueError("AUTHORING_REFUSES_COMMITTED_STATE")
    inputs = terminal_output.capture(directory, ("checkpoint", "plan"))
    checkpoint = load(task_state.path(directory, "checkpoint"))
    plan = load(task_state.path(directory, "plan"))
    _, text = finalize_response.finalize(checkpoint, plan)
    begin_validation()
    source_integrity.validate_completion(directory, checkpoint, rendered_text=text)
    record_validator("source_integrity:validate_completion")
    specialization_core.validate_completion(directory, checkpoint, rendered_text=text)
    record_validator("specialization_core:validate_completion")
    image_inspection.validate_completion(directory, checkpoint, rendered_text=text)
    record_validator("image_inspection:validate_completion")
    for name, expected in inputs.items():
        p = directory / name
        if p.is_symlink() or terminal_output.digest(p.read_bytes()) != expected:
            raise ValueError("AUTHORING_INPUT_CHANGED_DURING_PREFLIGHT: " + name)
    composition = composition_receipt(directory, checkpoint, pub)
    payload = text.encode("utf-8")
    if not payload:
        raise ValueError("AUTHORING_EMPTY_RESPONSE")
    return dict(status="READY_UNCOMMITTED", response_bytes=len(payload),
                preview_sha256=terminal_output.digest(payload),
                transport_mode=terminal_output.transport_mode(payload),
                validators_run=composition["validators_run"],
                next_command='python3 scripts/complete_commentary_task.py --state-dir "' + str(directory) + '"')



NATIVE_TRANSACTION_KEYS = frozenset({
    "source_registry",
    "argument_dossier",
    "dependency_uncertainty",
    "historical_graph",
    "reception_analyses",
})


def _transaction_object(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"TRANSACTION_{label.upper()}_OBJECT_REQUIRED")
    return copy.deepcopy(value)


def _transaction_list(value, label):
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"TRANSACTION_{label.upper()}_LIST_REQUIRED")
    return copy.deepcopy(value)


def _replace_task_marker(value, directory):
    """Expand only the explicit task marker; never rewrite scholarly content."""
    if isinstance(value, dict):
        return {k: _replace_task_marker(v, directory) for k, v in value.items()}
    if isinstance(value, list):
        return [_replace_task_marker(v, directory) for v in value]
    if value == "$HTI_STATE_DIR":
        return str(directory.resolve())
    return value


def _integrity_parent_snapshot(raw, node_id, span_ids, source):
    nodes = {item["id"]: item for item in raw.get("representations", [])}
    if node_id not in nodes:
        raise ValueError("TRANSACTION_INTEGRITY_PARENT_NOT_FOUND: " + str(node_id))
    node = nodes[node_id]
    spans = {item["id"]: item for item in node.get("spans", [])}
    selected = list(span_ids or [])
    if len(selected) != len(set(selected)) or not set(selected) <= set(spans):
        raise ValueError("TRANSACTION_INTEGRITY_PARENT_SPANS: " + str((node_id, selected)))
    regions = {item["id"]: item for item in node.get("regions", [])}
    relevant = sorted({spans[s].get("region_id") for s in selected if spans[s].get("region_id")})
    value = {
        "type": node["type"],
        "work_id": node.get("work_id", raw.get("work_id")),
        "verification": node.get("verification", {}),
        "spans": [spans[s] for s in selected],
        "regions": [regions[k] for k in relevant if k in regions],
    }
    if not selected:
        value["source_sha256"] = node.get("source_sha256")
        value["content"] = node.get("content")
    return source.digest(value)


def _normalize_source_integrity(raw, directory, work_id, dossier_raw=None):
    """Fill only deterministic ancestry/binding hashes in explicit source state."""
    import source_integrity as source
    value = _replace_task_marker(_transaction_object(raw, "source_integrity"), directory)
    value["work_id"] = work_id
    value["task_directory"] = str(directory.resolve())

    # Source ancestry hashes are mechanical functions of the authored parent state.
    for node in value.get("representations", []):
        for edge in node.get("parents", []):
            edge["snapshot"] = _integrity_parent_snapshot(value, edge["id"], edge.get("span_ids", []), source)
            if edge.get("span_ids") and ("span_snapshots" in edge or len(edge["span_ids"]) > 1):
                edge["span_snapshots"] = {
                    sid: _integrity_parent_snapshot(value, edge["id"], [sid], source)
                    for sid in edge["span_ids"]
                }

    # Validate the complete source ancestry before adding argument bindings.
    base_value = copy.deepcopy(value)
    argument = base_value.pop("argument_integrity", None)
    base_registry = source.IntegrityRegistry(base_value)
    if argument is None:
        return value, base_registry
    if dossier_raw is None:
        raise ValueError("TRANSACTION_DOSSIER_REQUIRED_FOR_ARGUMENT_INTEGRITY")

    argument = copy.deepcopy(argument)
    scopes = {item["id"]: item for item in argument.get("coverage_scopes", [])}
    coverage = {item["id"]: item for item in argument.get("coverage", [])}
    props = {item["id"]: item for item in argument.get("propositions", [])}
    consumers = {item["id"]: item for item in argument.get("consumers", [])}
    relations = {item["relation_id"]: item for item in dossier_raw.get("relations", [])}

    def bind_source_ref(ref):
        if not isinstance(ref, dict):
            raise ValueError("TRANSACTION_SOURCE_REF_OBJECT_REQUIRED")
        rid = ref.get("representation_id")
        spans = ref.get("span_ids")
        if not isinstance(rid, str) or not isinstance(spans, list):
            raise ValueError("TRANSACTION_SOURCE_REF_FIELDS")
        ref["snapshot"] = base_registry.parent_snapshot(rid, spans)
        return ref

    # Coverage and speaker/source evidence are authored; only their snapshots are compiled.
    for row in coverage.values():
        for ref in row.get("targets", []):
            bind_source_ref(ref)
    for prop in props.values():
        for ref in prop.get("speaker_evidence", []):
            bind_source_ref(ref)
    for consumer in consumers.values():
        explanation = consumer.get("historical_explanation")
        if isinstance(explanation, dict):
            for item in list(explanation.get("evidence", [])) + list(explanation.get("counterevidence", [])):
                for ref in item.get("source_refs", []):
                    bind_source_ref(ref)

    def scope_snapshot(key):
        scope = scopes[key]
        rid = scope["representation_id"]
        node = base_registry.nodes[rid]
        return source.digest({
            "source": base_registry.parent_snapshot(rid, sorted(base_registry.spans(rid))),
            "reading_order": node.get("reading_order"),
            "inventory": list(base_registry.spans(rid)),
            "coverage": [row for row in coverage.values() if row["scope_id"] == key],
        })

    def proposition_snapshot(key):
        prop = props[key]
        local = {
            rid: base_registry.parent_snapshot(rid, sorted(span_ids))
            for rid, span_ids in sorted(base_registry.dependency_scope(prop["representation_id"]).items())
        }
        speaker = [
            base_registry.parent_snapshot(ref["representation_id"], ref["span_ids"])
            for ref in prop.get("speaker_evidence", [])
        ]
        return source.digest({
            "record": {k: v for k, v in prop.items() if k != "snapshot"},
            "source": local,
            "speaker_basis": speaker,
        })

    for key, prop in props.items():
        prop["snapshot"] = proposition_snapshot(key)

    # PRG bindings are mechanical projections of the validated authored dossier.
    prg = argument.get("prg")
    if not isinstance(prg, dict):
        raise ValueError("TRANSACTION_ARGUMENT_PRG_REQUIRED")
    prg["dossier_id"] = dossier_raw.get("dossier_id")
    prg["dossier_sha256"] = source.digest(dossier_raw)
    if prg.get("coverage_complete") or "coverage_snapshots" in prg:
        prg["coverage_snapshots"] = {key: scope_snapshot(key) for key in scopes}

    for consumer in consumers.values():
        if consumer.get("kind") == "PRG_RELATION":
            relation_id = consumer.get("relation_id")
            if relation_id not in relations:
                raise ValueError("TRANSACTION_PRG_RELATION_NOT_FOUND: " + str(relation_id))
            consumer["relation_snapshot"] = source.digest(relations[relation_id])

    visiting = set()
    memo = {}
    def consumer_snapshot(key):
        if key in memo:
            return memo[key]
        if key in visiting:
            raise ValueError("TRANSACTION_CONSUMER_CYCLE: " + key)
        if key not in consumers:
            raise ValueError("TRANSACTION_CONSUMER_NOT_FOUND: " + key)
        visiting.add(key)
        consumer = consumers[key]
        refs = []
        for dep in consumer.get("dependencies", []):
            kind, rid = dep.get("kind"), dep.get("id")
            if kind == "proposition":
                snap = props[rid]["snapshot"]
            elif kind == "coverage":
                snap = scope_snapshot(rid)
            elif kind == "consumer":
                snap = consumer_snapshot(rid)
            else:
                raise ValueError("TRANSACTION_CONSUMER_DEPENDENCY_KIND: " + str(kind))
            dep["snapshot"] = snap
            refs.append({"kind": kind, "id": rid, "snapshot": snap})
        value2 = source.digest({
            "record": {k: v for k, v in consumer.items() if k != "dependencies"},
            "dependencies": refs,
        })
        visiting.remove(key)
        memo[key] = value2
        return value2

    for key in consumers:
        consumer_snapshot(key)

    value["argument_integrity"] = argument
    registry = source.IntegrityRegistry(value)
    return value, registry


def _save_transaction_native(directory, payload, work_id):
    """Construct existing native objects from explicit scholarly inputs."""
    import source_integrity as source
    from hti_core.source_representation import RepresentationRegistry
    from hti_core.argument_architecture import construct_argument_dossier
    from hti_core.dependency_uncertainty import construct_dependency_uncertainty, DependencyUncertaintyAnalysis
    from hti_core.historical_relations import construct_historical_relation_graph
    from hti_core.reception_history import construct_reception_analysis

    native = _transaction_object(payload.get("native"), "native")
    unknown = set(native) - NATIVE_TRANSACTION_KEYS
    if unknown:
        raise ValueError("TRANSACTION_NATIVE_FIELDS: " + ", ".join(sorted(unknown)))
    for required in ("source_registry", "argument_dossier", "historical_graph"):
        if required not in native:
            raise ValueError("TRANSACTION_NATIVE_REQUIRED: " + required)

    source_registry_raw = _transaction_object(native["source_registry"], "source_registry")
    representation_registry = RepresentationRegistry.from_dict(source_registry_raw)
    task_state.save(directory / "hti-source-registry.json", source_registry_raw)

    dossier_raw = _transaction_object(native["argument_dossier"], "argument_dossier")
    built_dossier = construct_argument_dossier(dossier_raw, representation_registry)
    task_state.save(directory / "hti-argument-dossier.json", dossier_raw)
    task_state.save(task_state.path(directory, "validated_dossier"), built_dossier.to_dict())

    uncertainty_analyses = {}
    if native.get("dependency_uncertainty") is not None:
        dep_raw = _transaction_object(native["dependency_uncertainty"], "dependency_uncertainty")
        built_dep = construct_dependency_uncertainty(dep_raw, built_dossier.dossier)
        task_state.save(directory / "hti-dependency-uncertainty-request.json", dep_raw)
        task_state.save(directory / "hti-validated-dependency-uncertainty.json", built_dep.to_dict())
        uncertainty_analyses[built_dossier.dossier.dossier_id] = DependencyUncertaintyAnalysis.from_dict(dep_raw, built_dossier.dossier)

    if "source_integrity" not in payload:
        raise ValueError("TRANSACTION_SOURCE_INTEGRITY_REQUIRED")
    integrity_raw, integrity_registry = _normalize_source_integrity(
        payload["source_integrity"], directory, work_id, dossier_raw=dossier_raw
    )
    task_state.save(task_state.path(directory, "integrity"), integrity_raw)

    graph_raw = _transaction_object(native["historical_graph"], "historical_graph")
    built_graph = construct_historical_relation_graph(
        graph_raw, [built_dossier.dossier], uncertainty_analyses, integrity_registry
    )
    task_state.save(directory / "hti-historical-graph.json", graph_raw)

    receptions = native.get("reception_analyses", {})
    if receptions is None:
        receptions = {}
    if not isinstance(receptions, dict):
        raise ValueError("TRANSACTION_RECEPTION_ANALYSES_OBJECT_REQUIRED")
    if receptions:
        known_refs = {built_dossier.dossier.dossier_id}
        known_refs.update(p.proposition_id for p in built_dossier.dossier.propositions)
        known_refs.update(n.node_id for n in built_graph.graph.nodes)
        known_representations = [r.representation_id for r in representation_registry.representations]
        compiled = {}
        for analysis_id, analysis_raw in receptions.items():
            if not isinstance(analysis_id, str) or not analysis_id:
                raise ValueError("TRANSACTION_RECEPTION_ANALYSIS_ID")
            authored = _transaction_object(analysis_raw, "reception_analysis")
            built = construct_reception_analysis(
                authored,
                known_argument_refs=known_refs,
                known_representation_ids=known_representations,
                phase5_graph=built_graph.graph,
            )
            if not built.audit.passed or built.result is None:
                detail = built.audit.findings[0].to_v01_string() if built.audit.findings else analysis_id
                raise ValueError("TRANSACTION_RECEPTION_INVALID: " + detail)
            if built.result.analysis_id != analysis_id:
                raise ValueError("TRANSACTION_RECEPTION_ID_MISMATCH: " + analysis_id)
            compiled[analysis_id] = {"input": authored, "result": built.result.to_dict()}
        task_state.save(directory / "hti-reception-analyses.json", compiled)

    # Re-run the unchanged publication-native adapters against the compiled files.
    source.publication_native(directory, integrity_registry)
    source.publication_graph(directory, integrity_registry)
    return integrity_registry


def _transaction_parent(directory, checkpoint, registry, spec, anchors):
    """Compile a compact authored parent selector into the exact current snapshot."""
    import source_integrity as source
    kind = spec.get("kind") if isinstance(spec, dict) else None
    rid = spec.get("id") if isinstance(spec, dict) else None
    if not isinstance(kind, str) or not isinstance(rid, str):
        raise ValueError("TRANSACTION_PARENT_KIND_ID_REQUIRED")
    if kind == "SOURCE_SPAN":
        spans = spec.get("span_ids")
        purpose = spec.get("purpose", "VISIBLE_CONTENT")
        if not isinstance(spans, list) or not spans:
            raise ValueError("TRANSACTION_SOURCE_SPANS_REQUIRED: " + rid)
        return source_ref(registry, rid, spans, purpose)
    if kind == "PROPOSITION":
        if registry.argument is None:
            raise ValueError("TRANSACTION_ARGUMENT_INTEGRITY_REQUIRED")
        return {"kind": kind, "id": rid, "snapshot": registry.argument.proposition_snapshot(rid)}
    if kind == "COVERAGE":
        if registry.argument is None:
            raise ValueError("TRANSACTION_ARGUMENT_INTEGRITY_REQUIRED")
        return {"kind": kind, "id": rid, "snapshot": registry.argument.scope_snapshot(rid)}
    if kind == "CONSUMER":
        if registry.argument is None:
            raise ValueError("TRANSACTION_ARGUMENT_INTEGRITY_REQUIRED")
        return {"kind": kind, "id": rid, "snapshot": registry.argument.consumer_snapshot(rid)}
    if kind == "PRG_RELATION":
        value = load(task_state.path(directory, "validated_dossier"))
        dossier = value.get("dossier", value)
        relation = next((x for x in dossier.get("relations", []) if x.get("relation_id") == rid), None)
        if relation is None:
            raise ValueError("TRANSACTION_PRG_RELATION_NOT_FOUND: " + rid)
        return {"kind": kind, "id": rid, "snapshot": source.digest(relation)}
    if kind == "HRG_RELATION":
        graph = source.publication_graph(directory, registry)
        return {"kind": kind, "id": rid, "snapshot": source.digest(graph.edge(rid).to_dict())}
    if kind == "DOMAIN_OUTPUT":
        domain = spec.get("domain")
        if not isinstance(domain, str) or not domain:
            raise ValueError("TRANSACTION_DOMAIN_REQUIRED: " + rid)
        projection_text, _ = source.publication_domain_output(directory, registry, domain, rid, checkpoint)
        return {"kind": kind, "domain": domain, "id": rid, "snapshot": gate.publication_text_digest(projection_text)}
    if kind == "CLAIM":
        obj = next((x for x in checkpoint.get("claims", []) if x.get("claim_id") == rid), None)
        if obj is None:
            raise ValueError("TRANSACTION_CLAIM_NOT_FOUND: " + rid)
        return {"kind": kind, "id": rid, "snapshot": source.digest(obj)}
    if kind == "EVIDENCE":
        obj = next((x for x in checkpoint.get("evidence", []) if x.get("evidence_id") == rid), None)
        if obj is None:
            raise ValueError("TRANSACTION_EVIDENCE_NOT_FOUND: " + rid)
        return {"kind": kind, "id": rid, "snapshot": source.digest(obj)}
    if kind == "QUESTION":
        obj = next((x for x in anchors if x.get("id") == rid), None)
        if obj is None:
            raise ValueError("TRANSACTION_QUESTION_NOT_FOUND: " + rid)
        return {"kind": kind, "id": rid, "snapshot": source.digest(obj)}
    raise ValueError("TRANSACTION_PARENT_KIND_NOT_SUPPORTED: " + str(kind))


def _transaction_review(derivation, pub, authored):
    """Bind an explicitly attested separate review to exact compiled bytes."""
    if not isinstance(authored, dict):
        raise ValueError("TRANSACTION_REVIEW_REQUIRED: " + derivation["id"])
    required = {"reviewer", "distinct_pass", "retained_qualifications",
                "source_ownership_fidelity", "material_changes",
                "unresolved_conflicts", "attestation"}
    if set(authored) != required:
        raise ValueError("TRANSACTION_REVIEW_FIELDS: " + derivation["id"])
    if authored.get("distinct_pass") is not True:
        raise ValueError("TRANSACTION_DISTINCT_REVIEW_REQUIRED: " + derivation["id"])
    if not isinstance(authored.get("reviewer"), str) or not authored["reviewer"].strip():
        raise ValueError("TRANSACTION_REVIEWER_REQUIRED: " + derivation["id"])
    if not isinstance(authored.get("attestation"), str) or not authored["attestation"].strip():
        raise ValueError("TRANSACTION_REVIEW_ATTESTATION_REQUIRED: " + derivation["id"])
    result = review_packet(derivation, pub)
    result.update(copy.deepcopy(authored))
    return result


def transaction_interface():
    """Compact public payload shape. It exposes no hidden constructor source."""
    return {
        "schema": "hti-native-authoring-transaction-1",
        "command": "python3 scripts/native_authoring.py transaction --state-dir TASK --payload PAYLOAD.json",
        "required_before_transaction": [
            "active commentary publication", "reviewed selected operation plan",
            "actual scholarly research", "explicit scholarly source/native objects required by the selected closure"
        ],
        "payload_top_level": [
            "schema", "work_id", "source_integrity", "native", "checkpoint",
            "plan", "anchors", "discoveries", "research_plan", "source_assertions", "assertions",
            "derivations", "outcomes", "scope", "sections", "preparation_reviewed"
        ],
        "parent_selector": {
            "kind": "SOURCE_SPAN | PROPOSITION | COVERAGE | CONSUMER | PRG_RELATION | HRG_RELATION | DOMAIN_OUTPUT | CLAIM | EVIDENCE | QUESTION",
            "id": "EXPLICIT_EXISTING_ID",
            "span_ids": ["required only for SOURCE_SPAN"],
            "purpose": "required source-use purpose for SOURCE_SPAN"
        },
        "derivation": {
            "id": "DERIVATION_ID", "assertion_id": "ASSERTION_ID", "projection": "REVIEWED_PROSE",
            "parents": ["parent selectors"], "purpose": "REPRESENTED_ARGUMENT", "source_layer": "EXPLICIT_LAYER",
            "ownership": "EXPLICIT_OWNER", "scope": "EXPLICIT_SCOPE", "status": "SUPPORTED|PROVISIONAL|UNRESOLVED",
            "facets": {}, "qualifiers": [], "limitations": [], "form": "DERIVATION|UNRESOLVED",
            "entity_ids": [], "revision": 1, "counterevidence": [], "uncertainty_inheritance": [],
            "review": {"reviewer": "ACTUAL_REVIEWER", "distinct_pass": True,
                       "retained_qualifications": True, "source_ownership_fidelity": True,
                       "material_changes": "EXPLICIT", "unresolved_conflicts": [],
                       "attestation": "ACTUAL SEPARATE REVIEW OF THIS PROSE AND THESE PARENTS"}
        },
        "source_assertion": {
            "id": "ASSERTION_ID", "representation_id": "REGISTERED_SOURCE_ID", "span_ids": ["SPAN_ID"],
            "purpose": "VISIBLE_CONTENT", "source_layer": "EXPLICIT_SOURCE_LAYER", "ownership": "UNKNOWN",
            "scope": "EXPLICIT_SCOPE", "status": "SUPPORTED", "entity_ids": []
        },
        "native": {"source_registry": "hti representation registry", "argument_dossier": "authored dossier", "dependency_uncertainty": "optional authored request", "historical_graph": "authored HRG", "reception_analyses": {"ANALYSIS_ID": "authored reception input"}},
        "authority": "The transaction runs the existing native constructors and computes hashes, snapshots, bindings, section wiring and preflight only. It never invents scholarship, signs a review, promotes identity, chooses an outcome, or weakens an existing validator."
    }



def bootstrap_interface():
    return {
        "schema": "hti-native-authoring-bootstrap-1",
        "command": "python3 scripts/native_authoring.py bootstrap --state-dir TASK --payload BOOTSTRAP.json",
        "payload": {"schema": "hti-native-authoring-bootstrap-1", "work_id": "ISOLATION_TOKEN",
                    "source_integrity": "explicit hti-source-integrity-1 object with at least one actual representation"},
        "effect": "Bind the explicit initial source representation to the owned task so task_state.py compose can resolve the natural-language anchor. No work identity or scholarly conclusion is inferred."
    }


def bootstrap(directory, payload):
    """Bind an explicit initial source representation before composition."""
    import source_integrity as source
    pub = task_state.require_active(directory)
    if pub.get("operation_plan") is not None:
        raise ValueError("BOOTSTRAP_BEFORE_SELECTION_ONLY")
    if not isinstance(payload, dict) or payload.get("schema") != "hti-native-authoring-bootstrap-1":
        raise ValueError("BOOTSTRAP_SCHEMA")
    if set(payload) != {"schema", "work_id", "source_integrity"}:
        raise ValueError("BOOTSTRAP_FIELDS")
    work_id = payload.get("work_id")
    if not isinstance(work_id, str) or not work_id.strip():
        raise ValueError("BOOTSTRAP_WORK_ID_REQUIRED")
    raw, registry = _normalize_source_integrity(payload.get("source_integrity"), directory, work_id)
    if not registry.nodes:
        raise ValueError("BOOTSTRAP_REPRESENTATION_REQUIRED")
    task_state.save(task_state.path(directory, "integrity"), raw)
    return {"status": "ANCHOR_BOUND", "work_id": work_id,
            "anchor_id": next(iter(registry.nodes)),
            "next_command": 'python3 scripts/task_state.py compose --state-dir "' + str(directory) + '"'}

def compile_transaction(directory, payload):
    """Compile one explicit scholarly payload into current native publication state."""
    import source_integrity as source
    pub = task_state.require_active(directory)
    task_state.validate_selection(pub)
    if pub["route"] != "commentary":
        raise ValueError("COMMENTARY_ROUTE_REQUIRED")
    if not isinstance(payload, dict) or payload.get("schema") != "hti-native-authoring-transaction-1":
        raise ValueError("TRANSACTION_SCHEMA")
    allowed = set(transaction_interface()["payload_top_level"])
    unknown = set(payload) - allowed
    if unknown:
        raise ValueError("TRANSACTION_UNKNOWN_FIELDS: " + ", ".join(sorted(unknown)))
    work_id = payload.get("work_id")
    if not isinstance(work_id, str) or not work_id.strip():
        raise ValueError("TRANSACTION_WORK_ID_REQUIRED")
    registry = _save_transaction_native(directory, payload, work_id)
    bundle = initialize(directory, work_id)
    checkpoint = bundle["checkpoint"]
    cp = _transaction_object(payload.get("checkpoint", {}), "checkpoint")
    allowed_cp = {"identity_state", "selected_claim_ids", "identity_hypotheses", "orientation",
                  "provenance", "evidence", "claims", "witness_variants", "legibility_regions",
                  "direct_reuse_claims", "textual_relationships", "full_text_escalations",
                  "long_s_audit", "output", "locus"}
    if set(cp) - allowed_cp:
        raise ValueError("TRANSACTION_CHECKPOINT_FIELDS: " + ", ".join(sorted(set(cp)-allowed_cp)))
    for key, value in cp.items():
        checkpoint[key] = copy.deepcopy(value)
    checkpoint["work_id"] = work_id
    plan = bundle["plan"]
    pp = _transaction_object(payload.get("plan", {}), "plan")
    allowed_plan = {"mode", "identity", "translation", "confidence", "entities"}
    if set(pp) - allowed_plan:
        raise ValueError("TRANSACTION_PLAN_FIELDS: " + ", ".join(sorted(set(pp)-allowed_plan)))
    for key, value in pp.items():
        plan[key] = copy.deepcopy(value)
    plan["work_id"] = work_id
    contract = bundle["contract"]
    # Anchors may use compact parent selectors and are bound to this publication mechanically.
    anchors = []
    for raw in _transaction_list(payload.get("anchors"), "anchors"):
        item = _transaction_object(raw, "anchor")
        item["task_directory"] = str(directory.resolve())
        item["work_id"] = work_id
        item["source_refs"] = [_transaction_parent(directory, checkpoint, registry, x, anchors) for x in item.get("source_refs", [])]
        item["proposition_refs"] = [_transaction_parent(directory, checkpoint, registry, x, anchors) for x in item.get("proposition_refs", [])]
        anchors.append(item)
    contract["anchors"] = anchors
    contract["discoveries"] = _transaction_list(payload.get("discoveries"), "discoveries")
    contract["research_plan"] = _transaction_list(payload.get("research_plan"), "research_plan")
    assertions = []
    for raw in _transaction_list(payload.get("source_assertions"), "source_assertions"):
        item = _transaction_object(raw, "source_assertion")
        rid = item.pop("representation_id")
        spans = item.pop("span_ids")
        purpose = item.pop("purpose", "VISIBLE_CONTENT")
        ref = source_ref(registry, rid, spans, purpose)
        if "projection" in item:
            text = item.pop("projection")
        else:
            node = registry.nodes[rid]
            separator = node.get("separator", "\n")
            text = separator.join(registry.spans(rid)[sid]["text"] for sid in spans)
        assertion_id = item.pop("id")
        assertions.append(projection(assertion_id, text, [ref], purpose=purpose,
            source_layer=item.pop("source_layer"), ownership=item.pop("ownership"),
            scope=item.pop("scope"), status=item.pop("status"), facets=item.pop("facets", None),
            qualifiers=item.pop("qualifiers", None), limitations=item.pop("limitations", None),
            form=item.pop("form", "CANONICAL"), entity_ids=item.pop("entity_ids", None)))
        if item:
            raise ValueError("TRANSACTION_SOURCE_ASSERTION_FIELDS: " + assertion_id + ": " + ", ".join(sorted(item)))
    for raw in _transaction_list(payload.get("assertions"), "assertions"):
        item = _transaction_object(raw, "assertion")
        aid = item.pop("id"); text = item.pop("projection")
        parents = [_transaction_parent(directory, checkpoint, registry, x, anchors) for x in item.pop("parents")]
        assertions.append(projection(aid, text, parents, purpose=item.pop("purpose"), source_layer=item.pop("source_layer"),
            ownership=item.pop("ownership"), scope=item.pop("scope"), status=item.pop("status"),
            facets=item.pop("facets", None), qualifiers=item.pop("qualifiers", None),
            limitations=item.pop("limitations", None), form=item.pop("form", "CANONICAL"),
            derivation_id=item.pop("derivation_id", None), entity_ids=item.pop("entity_ids", None)))
        if item:
            raise ValueError("TRANSACTION_ASSERTION_FIELDS: " + aid + ": " + ", ".join(sorted(item)))
    derivations = []
    for raw in _transaction_list(payload.get("derivations"), "derivations"):
        item = _transaction_object(raw, "derivation")
        did = item.pop("id"); aid = item.pop("assertion_id"); text = item.pop("projection")
        parent_specs = item.pop("parents")
        parents = [_transaction_parent(directory, checkpoint, registry, x, anchors) for x in parent_specs]
        form = item.pop("form", "DERIVATION")
        entity_ids = item.pop("entity_ids", [])
        p = projection(did, text, parents, purpose=item.pop("purpose"), source_layer=item.pop("source_layer"),
            ownership=item.pop("ownership"), scope=item.pop("scope"), status=item.pop("status"),
            facets=item.pop("facets", None), qualifiers=item.pop("qualifiers", None),
            limitations=item.pop("limitations", None), form="DERIVATION", entity_ids=entity_ids)
        deriv = {k: v for k, v in p.items() if k not in ("form", "derivation_id", "entity_ids")}
        deriv.update(revision=item.pop("revision", 1), counterevidence=item.pop("counterevidence", []),
                     uncertainty_inheritance=item.pop("uncertainty_inheritance", []))
        deriv["review"] = _transaction_review(deriv, pub, item.pop("review"))
        assertion = copy.deepcopy(p)
        assertion.update(id=aid, form=form, derivation_id=did, entity_ids=entity_ids)
        if item:
            raise ValueError("TRANSACTION_DERIVATION_FIELDS: " + did + ": " + ", ".join(sorted(item)))
        derivations.append(deriv); assertions.append(assertion)
    contract["assertions"] = assertions
    contract["derivations"] = derivations
    outcomes = []
    for raw in _transaction_list(payload.get("outcomes"), "outcomes"):
        item = _transaction_object(raw, "outcome")
        item["result_refs"] = [_transaction_parent(directory, checkpoint, registry, x, anchors) for x in item.get("result_refs", [])]
        outcomes.append(item)
    contract["outcomes"] = outcomes
    scope = _transaction_object(payload.get("scope", {}), "scope")
    for key, default in (("source_bindings", []), ("required_source_bindings", []), ("domain_outputs", [])):
        scope[key] = [_transaction_parent(directory, checkpoint, registry, x, anchors) for x in scope.get(key, default)]
    contract["scope"].update(scope)
    contract["terminal"]["preparation_reviewed"] = payload.get("preparation_reviewed") is True
    bundle["checkpoint"] = checkpoint
    bundle["plan"] = plan
    bundle["contract"] = contract
    bundle["sections"] = _transaction_list(payload.get("sections"), "sections")
    target = directory / "commentary-authoring.json"
    task_state.save(target, bundle)
    return bundle


def _transaction_input_findings(payload):
    """Collect independent structural authoring failures before any task mutation."""
    findings = []
    def add(code, location, detail):
        findings.append({"code": code, "location": location, "detail": detail})
    if not isinstance(payload, dict):
        add("TRANSACTION_PAYLOAD_OBJECT_REQUIRED", "/", type(payload).__name__)
        return findings
    if payload.get("schema") != "hti-native-authoring-transaction-1":
        add("TRANSACTION_SCHEMA", "/schema", payload.get("schema"))
    allowed = set(transaction_interface()["payload_top_level"])
    for key in sorted(set(payload) - allowed):
        add("TRANSACTION_UNKNOWN_FIELD", "/" + key, key)
    if not isinstance(payload.get("work_id"), str) or not payload.get("work_id", "").strip():
        add("TRANSACTION_WORK_ID_REQUIRED", "/work_id", payload.get("work_id"))
    native = payload.get("native")
    if not isinstance(native, dict):
        add("TRANSACTION_NATIVE_OBJECT_REQUIRED", "/native", type(native).__name__)
    else:
        for key in sorted(set(native) - NATIVE_TRANSACTION_KEYS):
            add("TRANSACTION_NATIVE_FIELD", "/native/" + key, key)
        for key in ("source_registry", "argument_dossier", "historical_graph"):
            if key not in native:
                add("TRANSACTION_NATIVE_REQUIRED", "/native/" + key, key)

    # Reject current-work aliases in author-controlled non-current entities and
    # assertion projections before any task mutation. This is an authoring-layer
    # gate only: it does not promote identity or replace renderer-owned identity.
    checkpoint = payload.get("checkpoint")
    aliases = gate.current_work_aliases(checkpoint) if isinstance(checkpoint, dict) else set()
    def has_current_alias(value):
        normalized = gate.normalize_identity_alias(value)
        padded = " " + normalized + " "
        return next((alias for alias in sorted(aliases, key=len, reverse=True)
                     if " " + alias + " " in padded), None)
    plan = payload.get("plan")
    if isinstance(plan, dict):
        entities = plan.get("entities", [])
        if isinstance(entities, list):
            for i, entity in enumerate(entities):
                if not isinstance(entity, dict):
                    continue
                leaked = has_current_alias(entity.get("display"))
                if leaked:
                    add("TRANSACTION_CURRENT_WORK_ALIAS_ENTITY",
                        f"/plan/entities/{i}/display",
                        {"entity_id": entity.get("entity_id"), "alias": leaked})
    assertions = payload.get("assertions", [])
    if isinstance(assertions, list):
        for i, assertion in enumerate(assertions):
            if not isinstance(assertion, dict):
                continue
            leaked = has_current_alias(assertion.get("projection"))
            if leaked:
                add("TRANSACTION_CURRENT_WORK_ALIAS_ASSERTION",
                    f"/assertions/{i}/projection",
                    {"assertion_id": assertion.get("id"), "alias": leaked})

    derivations = payload.get("derivations", [])
    if not isinstance(derivations, list):
        add("TRANSACTION_DERIVATIONS_LIST_REQUIRED", "/derivations", type(derivations).__name__)
    else:
        review_fields = {"reviewer", "distinct_pass", "retained_qualifications",
                         "source_ownership_fidelity", "material_changes",
                         "unresolved_conflicts", "attestation"}
        for i, derivation in enumerate(derivations):
            loc = f"/derivations/{i}"
            if not isinstance(derivation, dict):
                add("TRANSACTION_DERIVATION_OBJECT_REQUIRED", loc, type(derivation).__name__)
                continue
            review = derivation.get("review")
            if not isinstance(review, dict):
                add("TRANSACTION_REVIEW_REQUIRED", loc + "/review", derivation.get("id"))
                continue
            missing = sorted(review_fields - set(review))
            extra = sorted(set(review) - review_fields)
            if missing or extra:
                add("TRANSACTION_REVIEW_FIELDS", loc + "/review", {"missing": missing, "extra": extra})
            if review.get("distinct_pass") is not True:
                add("TRANSACTION_DISTINCT_REVIEW_REQUIRED", loc + "/review/distinct_pass", review.get("distinct_pass"))
            if not isinstance(review.get("reviewer"), str) or not review.get("reviewer", "").strip():
                add("TRANSACTION_REVIEWER_REQUIRED", loc + "/review/reviewer", review.get("reviewer"))
            if not isinstance(review.get("attestation"), str) or not review.get("attestation", "").strip():
                add("TRANSACTION_REVIEW_ATTESTATION_REQUIRED", loc + "/review/attestation", review.get("attestation"))
    return findings


def transact(directory, payload):
    """Compile, prepare and preflight in one bounded public operation."""
    findings = _transaction_input_findings(payload)
    if findings:
        return {
            "status": "NEEDS_CORRECTION",
            "findings": findings,
            "instruction": "Correct every listed authored-input defect. No response or receipt was committed."
        }
    try:
        bundle = compile_transaction(directory, payload)
    except Exception as exc:
        return {
            "status": "NEEDS_CORRECTION",
            "findings": [{"code": "TRANSACTION_COMPILE_GATE", "location": "/", "detail": str(exc)}],
            "instruction": "Correct the explicit scholarly payload or source/native state named by the compile gate. No response or receipt was committed."
        }
    try:
        result = prepare(directory, bundle)
        result["transaction"] = "COMPILED_AND_PREFLIGHTED"
        return result
    except Exception as exc:
        # Return all currently detectable author corrections without weakening the failed gate.
        diagnostics = diagnose(directory, load(directory / "commentary-authoring.json"))
        return {
            "status": "NEEDS_CORRECTION",
            "preparation_error": str(exc),
            "diagnostics": diagnostics,
            "bundle": str(directory / "commentary-authoring.json"),
            "instruction": "Correct only the explicit scholarly payload or source/native state identified by diagnostics, preserve actual evidence and review, then rerun transaction. No response or receipt was committed."
        }

def interface():
    """Public syntax and correction obligations, without a task or source reads."""
    import inspect
    import finalize_response as renderer
    return dict(
        schema="hti-authoring-interface-1",
        commands={"initialize": "--state-dir TASK --work-id ISOLATION_TOKEN",
                  "diagnose": "--state-dir TASK [--bundle TASK/commentary-authoring.json]",
                  "prepare": "--state-dir TASK [--bundle TASK/commentary-authoring.json]",
                  "check": "--state-dir TASK"},
        python_signatures={name: str(inspect.signature(fn)) for name, fn in
                           [("source_ref", source_ref), ("projection", projection),
                            ("review_packet", review_packet)]},
        sections=[dict(kind="research", assertion_ids=["EXPLICIT_ASSERTION_ID"])],
        section_kinds=sorted(renderer.SECTION_HEADINGS),
        entity=dict(entity_id="EXPLICIT_ID", role="historical_name",
                    scope="historical_source", display="EVIDENCE_SUPPORTED_NONCURRENT_NAME",
                    current_work_referent=False, evidence_ids=["ACTUAL_EVIDENCE_ID"]),
        entity_roles={k: sorted(v) for k, v in renderer.ROLE_SCOPES.items()},
        entity_obligation="Only genuinely non-current referents. Never rename identity or register a current-work alias as non-current to pass a gate. Bind entity_ids on each assertion that uses the licensed name.",
        outcomes=dict(statuses=["COMPLETED", "PARTIAL", "UNRESOLVED", "BLOCKED"],
                      fields=["id", "status", "result_refs", "assertion_ids", "plan_item_ids", "reason", "blocked_by", "limitations"],
                      obligation="Author adjudicates each selected step. COMPLETED/PARTIAL need actual valid typed results; other statuses need a visible reviewed reason; BLOCKED names incomplete prerequisites. Execution exhaustion proves no historical conclusion."),
        source_binding=dict(representation_id="ACTUAL_REGISTERED_ID", field="rendered_source_layer"),
        source_obligation="Bind actual response layers and account for supplied roots used by bindings/propositions. Use source_integrity.py argument-interface for coverage fields. Do not infer REPRESENTED, reviewed text or completed research from registration.",
        review_obligation="review_packet returns unsigned bindings only. Changed prose/parents require an actual new separate review. Never reuse an old signature or relabel identity to pass diagnostics.",
        publication_scope="Keep all retained source/native accounting. Select the passages actually published; research does not require a complete source appendix. Every selected source binding must remain visible. Translation requirements remain mandatory.",
        authority="Diagnostics neither publish nor certify readiness. prepare must pass every current kernel/native gate; then invoke complete_commentary_task.py with the exact owned task. No helper assigns outcomes or signs reviews.")


def diagnose(directory, bundle):
    """Read-only obligations for the compact bundle; never a publication bypass."""
    import re
    import finalize_response as renderer
    import source_integrity as source
    from hti_core import composition
    pub = task_state.require_active(directory)
    task_state.validate_selection(pub)
    if pub["route"] != "commentary":
        raise ValueError("COMMENTARY_ROUTE_REQUIRED")
    for key in ("response", "completion_receipt"):
        if task_state.path(directory, key).exists():
            raise ValueError("AUTHORING_REFUSES_COMMITTED_STATE")
    # Exact ownership/shape is checked by the same assembly path. A stale
    # publication or selection is fatal, never an invitation to refresh it.
    if not isinstance(bundle, dict) or set(bundle) != {"schema", "checkpoint", "plan", "contract", "sections"}:
        raise ValueError("AUTHORING_SHAPE")
    for key in ("task_directory", "publication_id", "request_sha256"):
        if bundle["contract"].get(key) != pub[key]:
            raise ValueError("AUTHORING_STALE_PUBLICATION: " + key)
    if bundle["contract"].get("operation_plan_sha256") != gate.publication_digest(pub["operation_plan"]):
        raise ValueError("AUTHORING_STALE_SELECTION")
    findings = []
    def issue(code, location, detail, obligation):
        findings.append(dict(code=code, location=location, detail=detail, obligation=obligation))
    checkpoint = copy.deepcopy(bundle["checkpoint"])
    checkpoint["publication_contract"] = copy.deepcopy(bundle["contract"])
    plan = None
    try:
        checkpoint, plan = assemble(directory, bundle)
    except Exception as exc:
        issue("ASSEMBLY_GATE", "/", str(exc), "Correct the exact contract/checkpoint obligation; no review or outcome is inferred.")
    aliases = renderer.collect_identity_aliases(checkpoint)
    entities = {}
    seen = set()
    for i, entity in enumerate(bundle["plan"].get("entities", [])):
        try:
            renderer.validate_entity(entity, checkpoint, aliases, seen)
            entities[entity["entity_id"]] = entity
        except Exception as exc:
            issue("ENTITY_GATE", "/plan/entities/" + str(i), str(exc), "Use inspected evidence for genuinely non-current referents; preserve renderer-owned identity.")
    claims = renderer.claim_map(checkpoint)
    selected = set(bundle["contract"].get("scope", {}).get("assertion_ids", []))
    for i, assertion in enumerate(bundle["contract"].get("assertions", [])):
        if assertion.get("id") not in selected:
            continue
        location = "/contract/assertions/" + str(i)
        text = assertion.get("projection")
        if not isinstance(text, str):
            continue
        alias = renderer.contains_alias(text, aliases)
        if alias:
            issue("ASSERTION_CURRENT_WORK_ALIAS", location,
                  dict(assertion_id=assertion.get("id"), alias=alias),
                  "Preserve the identity evidence. Rephrase the current-work reference without its name and review changed prose; do not alter identity to evade the guard.")
        licenses = set()
        refs = list(assertion.get("entity_ids", []))
        claim = claims.get(assertion.get("claim_id"), {})
        refs += claim.get("entity_ids", []) + ([claim["entity_id"]] if claim.get("entity_id") else [])
        for eid in refs:
            if eid not in entities:
                issue("ASSERTION_ENTITY_REFERENCE", location, dict(assertion_id=assertion.get("id"), entity_id=eid), "Bind a valid independently evidenced entity.")
            else:
                licenses.update(re.findall(r"\b[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’\-]*\b", entities[eid]["display"]))
        names = renderer.untyped_named_tokens(text, allow_sentence_initial=True)
        unlicensed = [n for n in names if n not in licenses]
        if unlicensed:
            issue("ASSERTION_NAMED_REFERENT", location,
                  dict(assertion_id=assertion.get("id"), tokens=unlicensed),
                  "Identify actual non-current referents and bind evidenced entities; mark genuinely quoted words as quotations in a reviewed derivation. Source prose is not automatically an entity licence. Do not disguise current-work names or fabricate entities.")
    rendered = None
    if plan is not None:
        try:
            _, rendered = renderer.finalize(checkpoint, plan)
        except Exception as exc:
            issue("RENDERER_GATE", "/plan", str(exc), "Apply the listed author corrections, then rerun diagnostics and full prepare.")
        try:
            composition.validate_state(directory, checkpoint, pub)
        except Exception as exc:
            issue("NATIVE_STATE_GATE", "/contract/outcomes", str(exc), "Retain actual state. Repair from evidence or explicitly adjudicate a truthful incomplete outcome and its visible reviewed reason.")
    inventory = []
    try:
        registry = source.IntegrityRegistry(load(task_state.path(directory, "integrity")))
        if registry.nodes and not registry.bindings:
            issue("OUTPUT_BINDING_REQUIRED", "source-integrity.json/output_bindings", [], "Explicitly bind each actual source response layer; use interface for fields.")
        covered = {s["representation_id"] for s in registry.argument.scopes.values()} if registry.argument else set()
        used = set()
        def roots(key):
            node = registry.nodes[key]
            if not node["parents"]:
                used.add(key)
            for parent in node["parents"]:
                roots(parent["id"])
        for binding in registry.bindings:
            roots(binding["representation_id"])
        if registry.argument:
            for prop in registry.argument.props.values():
                roots(prop["representation_id"])
        for rid in sorted(used - covered):
            issue("BODY_COVERAGE_SCOPE_REQUIRED", "source-integrity.json/argument_integrity", rid,
                  "Account for the actual inventoried spans through source_integrity.py argument-interface. No successful disposition is implied.")
        for rid, node in registry.nodes.items():
            if not node["parents"]:
                inventory.append(dict(representation_id=rid, type=node["type"],
                                      bound=any(b["representation_id"] == rid for b in registry.bindings),
                                      coverage_scope_present=rid in covered,
                                      spans=[dict(id=s["id"], state=s["state"], source_class=s["source_class"]) for s in registry.spans(rid).values()]))
        for group in ("assertions", "derivations"):
            for i, obj in enumerate(bundle["contract"].get(group, [])):
                for j, ref in enumerate(obj.get("parents", [])):
                    try:
                        source.resolve_publication_parent(directory, checkpoint, registry, ref, obj["purpose"])
                    except Exception as exc:
                        issue("PARENT_GATE", f"/contract/{group}/{i}/parents/{j}", str(exc), "Use actual current evidence or a newly reviewed limited assertion; never refresh parent snapshots without revalidation.")
    except Exception as exc:
        issue("SOURCE_REGISTRY_GATE", "source-integrity.json", str(exc), "Correct the current source registry without changing observational evidence.")
    # If a prior prepare staged exactly this bundle, reuse the full existing
    # nonpublishing gate. Never stage or refresh inputs merely to diagnose them.
    full_preflight = "PREPARE_REQUIRED"
    if plan is not None:
        try:
            current_checkpoint = load(task_state.path(directory, "checkpoint"))
            current_plan = load(task_state.path(directory, "plan"))
            if current_checkpoint == checkpoint and current_plan == plan:
                preflight(directory)
                full_preflight = "PASSED_UNCOMMITTED"
        except Exception as exc:
            full_preflight = "FAILED"
            issue("FULL_PREFLIGHT_GATE", "/", str(exc), "Correct this exact existing gate; diagnostics never bypass full preparation or infer successful native state.")
    outcome_requirements = []
    operation_registry = composition.load()["operations"]
    outcomes = {o["id"]: o for o in bundle["contract"].get("outcomes", [])}
    for step in pub["operation_plan"]["operations"]:
        spec = operation_registry[step["operation"]]
        outcome = outcomes.get(step["step_id"], {})
        outcome_requirements.append(dict(step_id=step["step_id"], operation=step["operation"],
            status=outcome.get("status"), result_kind=spec["result_kind"],
            actual_ref_kinds=[r.get("kind") for r in outcome.get("result_refs", [])],
            required_state=spec["requires_state"],
            obligation="For graph operations, PARTIAL requires an actual HRG_RELATION ref; a native-operation CLAIM alone does not satisfy that status. All refs and outcomes remain author-adjudicated." if spec["result_kind"] == "HRG_RELATION_OR_NATIVE_OPERATION_RESULT" else "Use the registry's actual typed result; missing state requires a truthful incomplete outcome, never a placeholder."))
    return dict(status="DIAGNOSTICS_ONLY", ready_to_publish=False,
                full_preflight_required=True, full_preflight=full_preflight, outcome_requirements=outcome_requirements, task_directory=str(directory.resolve()),
                publication_id=pub["publication_id"], findings=findings,
                source_inventory=inventory, outcome_statuses=[dict(id=o.get("id"), status=o.get("status")) for o in bundle["contract"].get("outcomes", [])],
                next_command='python3 scripts/native_authoring.py prepare --state-dir "' + str(directory) + '"',
                authority="No state written, outcome assigned, review signed, response or receipt committed. Diagnostics are advisory; every existing completion gate remains mandatory.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["initialize", "prepare", "check", "interface", "diagnose", "transaction-interface", "bootstrap-interface", "bootstrap", "transaction"])
    parser.add_argument("--state-dir")
    parser.add_argument("--work-id")
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--payload", type=Path)
    args = parser.parse_args()
    if args.command == "interface":
        print(json.dumps(interface(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "transaction-interface":
        print(json.dumps(transaction_interface(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "bootstrap-interface":
        print(json.dumps(bootstrap_interface(), ensure_ascii=False, indent=2))
        return 0
    directory = task_state.resolve(args.state_dir)
    try:
        if args.command == "bootstrap":
            if not args.payload:
                raise ValueError("--payload is required for bootstrap")
            result = bootstrap(directory, load(args.payload))
        elif args.command == "initialize":
            if not args.work_id:
                raise ValueError("--work-id is required")
            target = directory / "commentary-authoring.json"
            if target.exists() or target.is_symlink():
                raise ValueError("AUTHORING_ALREADY_EXISTS: retain the owned bundle")
            task_state.save(target, initialize(directory, args.work_id))
            result = dict(status="AUTHORING_REQUIRED", bundle=str(target))
        elif args.command in {"prepare", "diagnose", "transaction"}:
            target = (args.payload if args.command == "transaction" else args.bundle) or directory / "commentary-authoring.json"
            if target.is_symlink():
                raise ValueError("AUTHORING_INPUT_MUST_NOT_BE_SYMLINK")
            if args.command != "transaction" and target.resolve().parent != directory:
                raise ValueError("AUTHORING_BUNDLE_MUST_BELONG_TO_CURRENT_TASK")
            if args.command == "prepare":
                result = prepare(directory, load(target))
            elif args.command == "diagnose":
                result = diagnose(directory, load(target))
            else:
                if not args.payload:
                    raise ValueError("--payload is required for transaction")
                result = transact(directory, load(args.payload))
        else:
            result = preflight(directory)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps(dict(status="UNFINISHED", error=str(exc),
            instruction="Correct the identified structured input; retain actual evidence and review. No response or receipt was committed.")), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
