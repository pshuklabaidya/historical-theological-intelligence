#!/usr/bin/env python3
"""Initialize, validate, transition, and index commentary research state."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

from evidence_audit import IDENTITY_STATES, audit_checkpoint, audit_sources

TEMPLATES = [
    "work-dossier.json", "edition-registry.json", "exemplar-registry.json",
    "witness-registry.json", "evidence-checkpoint.json", "source-checkpoint.json",
    "image-manifest.json", "glyph-atlas.md", "research-ledger.jsonl", "research-index.md",
]
JSON_FILES = TEMPLATES[:7]


def templates_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "resources" / "templates"


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def replace_work_id(value: Any, work_id: str) -> Any:
    if isinstance(value, dict):
        return {k: replace_work_id(v, work_id) for k, v in value.items()}
    if isinstance(value, list):
        return [replace_work_id(v, work_id) for v in value]
    if value == "WORK-ID":
        return work_id
    return value


def init_state(directory: Path, work_id: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    if not work_id or any(c.isspace() for c in work_id):
        raise ValueError("work_id must be non-empty and contain no spaces")
    for name in TEMPLATES:
        target = directory / name
        if target.exists():
            raise ValueError(f"refusing to overwrite {target}")
        source = templates_dir() / name
        if name.endswith(".json"):
            data = replace_work_id(read_json(source), work_id)
            if name == "work-dossier.json":
                data["updated_at"] = now()
            write_json(target, data)
        else:
            text = source.read_text(encoding="utf-8").replace("WORK-ID", work_id)
            if name.endswith(".jsonl"):
                event = json.loads(text)
                event["timestamp"] = now()
                text = json.dumps(event, ensure_ascii=False) + "\n"
            target.write_text(text, encoding="utf-8")


def validate_state(directory: Path) -> list[str]:
    errors: list[str] = []
    template_mode = directory.resolve() == templates_dir().resolve()
    for name in TEMPLATES:
        if not (directory / name).is_file():
            errors.append(f"MISSING: {name}")
    if errors:
        return errors
    parsed: dict[str, dict[str, Any]] = {}
    for name in JSON_FILES:
        try:
            parsed[name] = read_json(directory / name)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"JSON: {name}: {exc}")
    if not parsed:
        return errors
    work_ids = {data.get("work_id") for data in parsed.values()}
    if None in work_ids or len(work_ids) != 1:
        errors.append(f"WORK_ISOLATION: inconsistent work_id values {sorted(map(str, work_ids))}")
    work_id = next(iter(work_ids - {None}), None)
    if work_id == "WORK-ID" and not template_mode:
        errors.append("WORK_ID: placeholder work_id remains")

    dossier = parsed.get("work-dossier.json", {})
    checkpoint = parsed.get("evidence-checkpoint.json", {})
    if dossier.get("identity_state") != checkpoint.get("identity_state"):
        errors.append("IDENTITY_SYNC: dossier and evidence checkpoint states differ")
    errors.extend(f"EVIDENCE: {e}" for e in audit_checkpoint(checkpoint))
    errors.extend(f"SOURCE: {e}" for e in audit_sources(parsed.get("source-checkpoint.json", {})))

    for filename, plural, singular in [
        ("edition-registry.json", "editions", "edition"),
        ("exemplar-registry.json", "exemplars", "exemplar"),
        ("witness-registry.json", "witnesses", "witness"),
    ]:
        seen = set()
        for item in parsed.get(filename, {}).get(plural, []):
            item_id = item.get(f"{singular}_id")
            if not item_id:
                errors.append(f"REGISTRY_ID: {filename} item lacks {singular}_id")
            elif item_id in seen:
                errors.append(f"REGISTRY_DUPLICATE: {filename} duplicates {item_id}")
            seen.add(item_id)
            if item.get("work_id", work_id) != work_id:
                errors.append(f"WORK_ISOLATION: {filename} item {item_id} belongs to another work")

    witness_ids = {w.get("witness_id") for w in parsed.get("witness-registry.json", {}).get("witnesses", [])}
    for edge in parsed.get("witness-registry.json", {}).get("edges", []):
        if edge.get("from") not in witness_ids or edge.get("to") not in witness_ids:
            errors.append(f"WITNESS_EDGE: edge {edge.get('edge_id', '<unnamed>')} references an unregistered witness")

    for line_no, line in enumerate((directory / "research-ledger.jsonl").read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"LEDGER_JSON: line {line_no}: {exc}")
            continue
        if event.get("work_id") != work_id:
            errors.append(f"WORK_ISOLATION: ledger line {line_no} belongs to {event.get('work_id')}")
        if not event.get("event_type") or (not event.get("timestamp") and not template_mode):
            errors.append(f"LEDGER_FIELDS: line {line_no} lacks event_type or timestamp")
        if event.get("event_type") in {"historical_infrastructure_snapshot", "historical_sensitivity_snapshot"}:
            try:
                validate_historical_snapshot(event["event_type"], event["details"], work_id)
            except (ValueError, KeyError, TypeError) as exc:
                errors.append(f"HISTORICAL_LEDGER: line {line_no}: {exc}")
        if event.get("event_type") == "research_plan_snapshot":
            try:
                from evidence_audit import publication_digest, validate_publication_contract
                details=event["details"]; contract=details["publication_contract"]
                if set(details)!={"publication_contract","sha256"} or details["sha256"]!=publication_digest(contract) or contract["work_id"]!=work_id:
                    raise ValueError("plan snapshot identity")
                historical_states={a["identity_state"] for a in contract["anchors"]}
                if len(historical_states)>1:raise ValueError("historical anchor identity mismatch")
                validate_publication_contract({"work_id":work_id,"identity_state":next(iter(historical_states), "UNIDENTIFIED"),"selected_claim_ids":list({cid for a in contract["anchors"] for cid in a["identity_claim_ids"]}),"publication_contract":contract})
            except (ValueError,KeyError,TypeError) as exc:
                errors.append(f"RESEARCH_PLAN_LEDGER: line {line_no}: {exc}")
        if event.get("event_type") == "novelty_snapshot":
            try:
                from hti_core.novelty import Novelty
                from hti_core.cartography import fingerprint
                details = event["details"]
                if set(details) != {"novelty", "sha256"} or details["sha256"] != fingerprint(details["novelty"]):
                    raise ValueError("snapshot hash")
                obj = Novelty(details["novelty"])
                validate_task_snapshot(directory, details["novelty"], historical=True)
                if obj.scope_work_ids() - {work_id}:
                    raise ValueError("novelty work isolation")
            except (ValueError, KeyError, TypeError) as exc:
                errors.append(f"NOVELTY_LEDGER: line {line_no}: {exc}")
    return errors


def claim_map(dossier: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {c.get("claim_id"): c for c in dossier.get("claims", []) if c.get("claim_id")}


def transition(directory: Path, new_state: str, claim_ids: list[str]) -> None:
    if new_state not in IDENTITY_STATES:
        raise ValueError(f"invalid state {new_state}")
    dossier_path = directory / "work-dossier.json"
    checkpoint_path = directory / "evidence-checkpoint.json"
    dossier = read_json(dossier_path)
    checkpoint = read_json(checkpoint_path)
    old_state = dossier.get("identity_state", "UNIDENTIFIED")
    if IDENTITY_STATES.index(new_state) > IDENTITY_STATES.index(old_state) + 1:
        raise ValueError(f"cannot skip from {old_state} to {new_state}")
    claims = claim_map(dossier)
    for cid in claim_ids:
        if cid not in claims:
            raise ValueError(f"claim {cid} does not exist in dossier")
    selected = list(dict.fromkeys(dossier.get("selected_claim_ids", []) + claim_ids))
    types = {claims[c].get("claim_type") for c in selected if c in claims and claims[c].get("status") in {"asserted", "secure", "verified", "established"}}
    required = {
        "WORK_ESTABLISHED": "work_identity",
        "EDITION_ESTABLISHED": "edition_identity",
        "EXEMPLAR_ESTABLISHED": "exemplar_identity",
    }.get(new_state)
    if required and required not in types:
        raise ValueError(f"{new_state} requires selected asserted {required} claim")
    dossier["identity_state"] = new_state
    dossier["selected_claim_ids"] = selected
    dossier["updated_at"] = now()
    checkpoint["identity_state"] = new_state
    checkpoint["selected_claim_ids"] = selected
    checkpoint["claims"] = copy.deepcopy(dossier.get("claims", []))
    checkpoint["evidence"] = copy.deepcopy(dossier.get("evidence", []))
    audit_errors = audit_checkpoint(checkpoint)
    if audit_errors:
        raise ValueError("transition fails evidence audit: " + "; ".join(audit_errors))
    write_json(dossier_path, dossier)
    write_json(checkpoint_path, checkpoint)
    append_event(directory, "identity_transition", {"from": old_state, "to": new_state, "claim_ids": claim_ids})



def validate_task_snapshot(directory, novelty=None, contract=None, historical=False):
    """Unknown anchors remain in owned task state; persistence admission is unchanged."""
    if novelty and novelty.get("schema_version") == "hti-novelty-anchor-1":
        import task_state
        owned = task_state.resolve(str(directory))
        if novelty["investigation"]["task_directory"] != str(owned.resolve()):
            raise ValueError("unknown novelty anchor cannot be admitted as a verified-work persistent snapshot")
        from source_integrity import IntegrityRegistry
        from hti_core.novelty import Novelty
        checkpoint = read_json(directory / "evidence-checkpoint.json")
        if not historical:
            Novelty(novelty).validate_anchor(checkpoint, IntegrityRegistry(read_json(directory / "source-integrity.json")))
        # Historical bytes remain provenance, never current research licenses.
    if contract is not None:
        import task_state
        from evidence_audit import validate_publication_contract
        owned = task_state.resolve(str(directory))
        checkpoint = read_json(owned / "evidence-checkpoint.json")
        if checkpoint.get("publication_contract") != contract:
            raise ValueError("research-plan snapshot must match current accountable task state")
        validate_publication_contract(checkpoint, publication=task_state.descriptor(owned))


def append_novelty(directory: Path, value: dict[str, Any]) -> None:
    from hti_core.novelty import Novelty
    from hti_core.cartography import fingerprint
    obj = Novelty(value)
    work_id = read_json(directory / "work-dossier.json")["work_id"]
    if obj.scope_work_ids() - {work_id}:
        raise ValueError("novelty research object belongs to another work")
    validate_task_snapshot(directory, value)
    append_event(directory, "novelty_snapshot", {"novelty": value, "sha256": fingerprint(value)})


def append_event(directory: Path, event_type: str, details: dict[str, Any]) -> None:
    dossier = read_json(directory / "work-dossier.json")
    if event_type in {"historical_infrastructure_snapshot", "historical_sensitivity_snapshot"}:
        validate_historical_snapshot(event_type, details, dossier["work_id"])
    if event_type == "novelty_snapshot":
        from hti_core.novelty import Novelty
        from hti_core.cartography import fingerprint
        if set(details) != {"novelty", "sha256"} or details["sha256"] != fingerprint(details["novelty"]):
            raise ValueError("invalid novelty ledger snapshot")
        obj = Novelty(details["novelty"])
        validate_task_snapshot(directory, details["novelty"])
        if obj.scope_work_ids() - {dossier["work_id"]}:
            raise ValueError("novelty ledger work isolation")
    if event_type == "research_plan_snapshot":
        from evidence_audit import publication_digest
        if set(details) != {"publication_contract", "sha256"} or details["sha256"] != publication_digest(details["publication_contract"]):
            raise ValueError("invalid discriminating-plan snapshot")
        validate_task_snapshot(directory, contract=details["publication_contract"])
    event = {"schema_version": "0.1", "event_type": event_type, "work_id": dossier["work_id"], "timestamp": now(), "details": details}
    with (directory / "research-ledger.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def make_index(directory: Path) -> str:
    dossier = read_json(directory / "work-dossier.json")
    editions = read_json(directory / "edition-registry.json").get("editions", [])
    exemplars = read_json(directory / "exemplar-registry.json").get("exemplars", [])
    witnesses = read_json(directory / "witness-registry.json").get("witnesses", [])
    claims = dossier.get("claims", [])
    lines = [
        "# Research Index", "", f"Work ID: `{dossier['work_id']}`", "",
        f"Identity state: `{dossier.get('identity_state', 'UNIDENTIFIED')}`", "",
        "## Counts", "", f"- Claims: {len(claims)}", f"- Editions: {len(editions)}",
        f"- Exemplars: {len(exemplars)}", f"- Witnesses: {len(witnesses)}", "",
        "## Active claims", "",
    ]
    active = [c for c in claims if c.get("status") not in {"rejected", "superseded"}]
    if active:
        lines.extend(f"- `{c.get('claim_id')}` - {c.get('claim_type')}: {c.get('value', '')}" for c in active)
    else:
        lines.append("- None")
    lines.append("")
    for entry in (directory / "research-ledger.jsonl").read_text().splitlines():
        event = json.loads(entry)
        if event.get("event_type") in {"historical_infrastructure_snapshot", "historical_sensitivity_snapshot"}:
            lines.append("- Retained historical analytical snapshot: " + event["details"]["sha256"] + "; requires current evidence validation before reuse; sensitivity remains hypothetical.")
        if event.get("event_type") == "research_plan_snapshot":
            contract = event["details"]["publication_contract"]
            lines.append("- Retained decision-question snapshot: " + event["details"]["sha256"] + "; historical state, not fresh result authorization.")
            for item in contract["research_plan"]:
                lines.append("  - " + item["target_question"] + ": " + item["completion_state"] + "; " + item["stopping_reason"])
        if event.get("event_type") == "novelty_snapshot":
            lines.append("- Retained novelty audit snapshot: " + event["details"]["sha256"] + "; requires current evidence validation before reuse.")
    rendered = "\n".join(lines)
    (directory / "research-index.md").write_text(rendered, encoding="utf-8")
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p_init = sub.add_parser("init")
    p_init.add_argument("directory", type=Path)
    p_init.add_argument("--work-id", required=True)
    p_validate = sub.add_parser("validate")
    p_validate.add_argument("directory", type=Path)
    p_transition = sub.add_parser("transition")
    p_transition.add_argument("directory", type=Path)
    p_transition.add_argument("state", choices=IDENTITY_STATES)
    p_transition.add_argument("--claim-id", action="append", default=[])
    p_append = sub.add_parser("append")
    p_append.add_argument("directory", type=Path)
    p_append.add_argument("event_type")
    p_append.add_argument("--details", default="{}")
    p_novelty = sub.add_parser("novelty")
    p_novelty.add_argument("directory", type=Path)
    p_novelty.add_argument("document", type=Path)
    p_index = sub.add_parser("index")
    p_index.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "init":
            init_state(args.directory, args.work_id)
            print(f"initialized {args.directory}")
        elif args.command == "validate":
            errors = validate_state(args.directory)
            if errors:
                print("FAIL")
                print("\n".join(f"- {e}" for e in errors))
                return 1
            print("PASS")
        elif args.command == "transition":
            transition(args.directory, args.state, args.claim_id)
            print(args.state)
        elif args.command == "append":
            details = json.loads(args.details)
            if not isinstance(details, dict):
                raise ValueError("--details must decode to an object")
            append_event(args.directory, args.event_type, details)
            print("appended")
        elif args.command == "novelty":
            append_novelty(args.directory, read_json(args.document))
            print("appended novelty audit snapshot")
        elif args.command == "index":
            print(make_index(args.directory), end="")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def validate_historical_snapshot(event_type, details, work_id):
    from hti_core.cartography import fingerprint
    from hti_core.historical_infrastructure import Infrastructure
    from hti_core.historical_sensitivity import Sensitivity
    if set(details) != {"document", "sha256"} or details["sha256"] != fingerprint(details["document"]):
        raise ValueError("historical snapshot hash")
    scenario = event_type == "historical_sensitivity_snapshot"
    obj = Sensitivity(details["document"]) if scenario else Infrastructure(details["document"])
    network = obj.network if scenario else obj
    if scenario and obj.scenario["work_id"] != work_id:
        raise ValueError("historical scenario work isolation")
    for records in [network.records, network.paths, network.bindings]:
        if any(network.evidence.registries[r["anchor_dataset_id"]].work_id != work_id for r in records.values()):
            raise ValueError("historical network work isolation")


def append_historical(directory, value, sensitivity=False):
    from hti_core.cartography import fingerprint
    append_event(directory, "historical_sensitivity_snapshot" if sensitivity else "historical_infrastructure_snapshot", {"document": value, "sha256": fingerprint(value)})
