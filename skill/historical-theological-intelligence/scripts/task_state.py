"""Isolated, durable scratch directories for one structured task.

Create once per user task. Reuse the returned directory for retries and Continue.
No command discovers another task's state or silently deletes stale files.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
import hashlib
import re
import uuid
from pathlib import Path

ROOT = Path(tempfile.gettempdir()) / "historical-theological-intelligence-tasks"
FILES = {
    "specialization": "specialization-context.json",
    "checkpoint": "evidence-checkpoint.json",
    "plan": "final-response-plan.json",
    "scholar": "scholar-view-task.json",
    "long_s": "long-s-check.json",
    "registry": "hti-source-registry.json",
    "integrity": "source-integrity.json",
    "dossier": "hti-argument-dossier.json",
    "historical_graph": "hti-historical-graph.json",
    "cartography": "hti-cartography.json",
    "novelty": "hti-novelty.json",
    "infrastructure": "hti-historical-infrastructure.json",
    "sensitivity": "hti-historical-sensitivity.json",
    "onboarding": "hti-specialization-onboarding.json",
    "validated_dossier": "hti-validated-argument-dossier.json",
    "uncertainty_request": "hti-dependency-uncertainty-request.json",
    "validated_uncertainty": "hti-validated-dependency-uncertainty.json",
    "inspection": "image-inspection.json",
    "response": "validated-response.md",
    "completion_receipt": "completion-receipt.json",
    "publication": "publication-turn.json",
    "draft": "publication-draft.json",
}


def create() -> Path:
    ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="task-", dir=ROOT))
    (directory / ".hti-state").write_text("3\n", encoding="ascii")
    template = Path(__file__).resolve().parents[1] / "resources/templates/source-integrity.json"
    integrity = json.loads(template.read_text(encoding="utf-8"))
    integrity["task_directory"] = str(directory.resolve())
    (directory / FILES["integrity"]).write_text(json.dumps(integrity, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(directory, 0o700)
    return directory


def resolve(value: str | None) -> Path:
    value = value or os.environ.get("HTI_STATE_DIR")
    if not value:
        raise ValueError("task state is required: create with 'python3 scripts/task_state.py new', then pass --state-dir DIRECTORY on every invocation, including Continue")
    if Path(value).is_symlink():
        raise ValueError("task directory must not be a symlink")
    directory = Path(value).resolve(strict=True)
    current = os.environ.get("HTI_STATE_DIR")
    if current and directory != Path(current).resolve(strict=True):
        raise ValueError("--state-dir must match the exact current HTI_STATE_DIR; retain explicitly linked same-task state")
    if not directory.is_dir() or directory.parent != ROOT.resolve() or not (directory / ".hti-state").is_file() or (directory / ".hti-state").is_symlink():
        raise ValueError("--state-dir must be a previously created HTI task directory")
    return directory


def path(directory: Path, key: str) -> Path:
    target = directory / FILES[key]
    if target.is_symlink():
        raise ValueError("task files must not be symlinks")
    return target


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save(path: Path, value: dict) -> None:
    if path.is_symlink():
        raise ValueError("publication files must not be symlinks")
    fd, temporary = tempfile.mkstemp(prefix=".hti-publication-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def descriptor(directory: Path) -> dict | None:
    p = path(directory, "publication")
    if not p.exists():
        return None
    value = json.loads(p.read_text())
    fields = {"schema", "task_directory", "publication_id", "sequence", "request", "request_sha256", "route", "previous"}
    if value.get("schema") in {"hti-publication-2", "hti-publication-3"}:
        fields |= {"operation_plan", "selection_review"}
    if value.get("schema") == "hti-publication-3": fields.add("composition")
    if set(value) != fields or value["schema"] not in {"hti-publication-1", "hti-publication-2", "hti-publication-3"} or value["task_directory"] != str(directory.resolve()):
        raise ValueError("publication must belong to this exact task")
    if not re.fullmatch(r"[0-9a-f]{32}", value["publication_id"]) or type(value["sequence"]) is not int or value["sequence"] < 1:
        raise ValueError("invalid publication identity")
    if value["route"] not in {"commentary", "scholar"} or not isinstance(value["request"], str) or not value["request"].strip() or digest(value["request"].encode()) != value["request_sha256"]:
        raise ValueError("publication request/route binding is invalid")
    if value["schema"] in {"hti-publication-2", "hti-publication-3"} and value["operation_plan"] is not None:
        validate_selection(value, verify_current=not path(directory, "completion_receipt").exists())
    previous = value["previous"]
    if previous is not None:
        if set(previous) != {"history_id", "artifacts"} or not re.fullmatch(r"(?:[0-9a-f]{32}|legacy-[0-9a-f]{16})", previous["history_id"]):
            raise ValueError("invalid publication history relation")
        if not isinstance(previous["artifacts"], dict) or not set(previous["artifacts"]) <= {FILES[k] for k in ("publication", "draft", "response", "completion_receipt", "checkpoint", "plan", "integrity")}:
            raise ValueError("invalid historical artifacts")
    return value


def history_root(directory: Path) -> Path:
    target = directory / "publication-history"
    if target.is_symlink():
        raise ValueError("publication history must remain inside the owned task")
    return target


def historical_residue(directory: Path, pub: dict, name: str) -> bool:
    previous = pub["previous"]
    if previous is None or name not in previous["artifacts"]:
        return False
    archived = history_root(directory) / previous["history_id"]
    if archived.is_symlink() or (archived / name).is_symlink():
        raise ValueError("historical publication path escape")
    current = directory / name
    if current.is_symlink():
        raise ValueError("current publication path escape")
    return current.is_file() and archived.is_dir() and (archived / name).is_file() and digest(current.read_bytes()) == previous["artifacts"][name] == digest((archived / name).read_bytes())


def current_draft(directory: Path, pub: dict) -> dict | None:
    p = path(directory, "draft")
    if not p.exists() or historical_residue(directory, pub, p.name):
        return None
    d = json.loads(p.read_text())
    fields = {"schema", "task_directory", "publication_id", "publication_sha256", "request_sha256", "route", "inputs"}
    if set(d) != fields or d["schema"] != "hti-publication-draft-1" or d["task_directory"] != str(directory.resolve()) or d["publication_id"] != pub["publication_id"] or d["request_sha256"] != pub["request_sha256"] or d["route"] != pub["route"] or d["publication_sha256"] != digest(path(directory, "publication").read_bytes()):
        raise ValueError("draft does not bind the current publication")
    allowed = {FILES[k] for k in ("checkpoint", "plan", "scholar", "integrity", "specialization", "inspection", "long_s", "dossier", "registry", "historical_graph", "uncertainty_request", "cartography", "novelty", "infrastructure", "sensitivity", "onboarding")} | {"source-checkpoint.json"}
    required = {FILES[k] for k in (("checkpoint", "plan") if pub["route"] == "commentary" else ("scholar",))}
    if not isinstance(d["inputs"], dict) or not required <= set(d["inputs"]) <= allowed:
        raise ValueError("invalid staged structured inputs")
    for name, expected in d["inputs"].items():
        p = directory / name
        if p.is_symlink():
            raise ValueError("staged input path escape")
        if not p.is_file() or digest(p.read_bytes()) != expected:
            return None
    return d


def status(directory: Path) -> dict:
    pub = descriptor(directory)
    rp = path(directory, "completion_receipt")
    if pub is None:
        if rp.exists():
            receipt = json.loads(rp.read_text())
            if receipt.get("task_directory") != str(directory.resolve()) or receipt.get("schema") != "hti-terminal-output-1":
                raise ValueError("foreign or unknown legacy receipt")
            return {"status": "LEGACY_COMPLETE", "publication_id": None}
        return {"status": "NO_PUBLICATION", "publication_id": None}
    draft = current_draft(directory, pub)
    if rp.exists() and not historical_residue(directory, pub, rp.name):
        receipt = json.loads(rp.read_text())
        if receipt.get("schema") not in {"hti-terminal-output-2", "hti-terminal-output-3", "hti-terminal-output-4"} or receipt.get("status") != "COMPLETE" or receipt.get("task_directory") != str(directory.resolve()) or receipt.get("publication_id") != pub["publication_id"] or receipt.get("request_sha256") != pub["request_sha256"] or receipt.get("route") != pub["route"]:
            raise ValueError("receipt does not complete the current publication")
        bindings = receipt.get("inputs", {})
        if draft is None or not isinstance(bindings, dict) or not set(draft["inputs"]) <= set(bindings) or bindings.get(FILES["publication"]) != digest(path(directory, "publication").read_bytes()) or bindings.get(FILES["draft"]) != digest(path(directory, "draft").read_bytes()):
            raise ValueError("current completion has stale publication/draft bindings")
        for name, expected in bindings.items():
            p = directory / name
            if Path(name).name != name or p.is_symlink() or not p.is_file() or digest(p.read_bytes()) != expected:
                raise ValueError("current completion inputs changed")
        response = path(directory, "response")
        if receipt.get("response_file") != response.name or not response.is_file() or len(response.read_bytes()) != receipt.get("response_bytes") or digest(response.read_bytes()) != receipt.get("response_sha256"):
            raise ValueError("current completion output changed")
        if receipt["schema"] in {"hti-terminal-output-3", "hti-terminal-output-4"}:
            import terminal_output
            if receipt.get("direct_output_ceiling") != terminal_output.DIRECT_OUTPUT_CEILING or receipt.get("transport_mode") != terminal_output.transport_mode(response.read_bytes()):
                raise ValueError("current completion transport binding changed")
        if receipt["schema"] == "hti-terminal-output-4":
            from hti_core.composition import verify_receipt
            verify_receipt(directory, pub, receipt)
        return {"status": "COMPLETE", "publication_id": pub["publication_id"], "sequence": pub["sequence"], "route": pub["route"]}
    return {"status": "READY" if draft else "OPEN", "publication_id": pub["publication_id"], "sequence": pub["sequence"], "route": pub["route"]}


def require_active(directory: Path) -> dict:
    current = status(directory)
    if current["status"] == "COMPLETE":
        raise ValueError("CURRENT_PUBLICATION_ALREADY_COMMITTED: do not rerun the helper, restage or create a new publication to deliver this answer. "
                         "If delivery of this same committed response failed, a later Continue may run task_state.py replay --transport-recovery "
                         "in this exact task before a transport stub; direct responses replay exact bytes, large responses replay the same one-Read stub. "
                         "After a stub only its single exact Read is allowed. Only a genuinely new substantive request opens a fresh publication.")
    if current["status"] not in {"OPEN", "READY"}:
        raise ValueError("FRESH_PUBLICATION_REQUIRED: open a substantive publication in this same task with 'python3 scripts/task_state.py begin-publication --state-dir DIRECTORY --route commentary|scholar --request CURRENT_REQUEST'; prior completion is historical")
    return descriptor(directory)


def require_ready(directory: Path) -> dict:
    pub = require_active(directory)
    if current_draft(directory, pub) is None:
        raise ValueError("CURRENT_DRAFT_REQUIRED: prepare current structured inputs, then run task_state.py stage-publication in this same task")
    return pub


def cleanup_previous(directory: Path, pub: dict) -> None:
    for key in ("draft", "response", "completion_receipt"):
        p = path(directory, key)
        if historical_residue(directory, pub, p.name):
            p.unlink()


def open_publication(directory: Path, request: str, route: str) -> dict:
    if not isinstance(request, str) or not request.strip() or route not in {"commentary", "scholar"}:
        raise ValueError("current substantive request and selected route are required")
    old = descriptor(directory)
    prior_status = status(directory)  # Reject foreign or corrupted current state before turnover.
    if old is not None:
        cleanup_previous(directory, old)
    previous = None
    rp = path(directory, "completion_receipt")
    if old is not None or rp.exists():
        history_id = old["publication_id"] if old else "legacy-" + digest(rp.read_bytes())[:16]
        root = history_root(directory)
        root.mkdir(exist_ok=True)
        folder = root / history_id
        if folder.is_symlink():
            raise ValueError("publication history path escape")
        folder.mkdir(exist_ok=True)
        artifacts = {}
        archived_keys = ["publication", "draft", "response", "completion_receipt"]
        if prior_status["status"] == "COMPLETE":
            # Preserve the actual input-bound substrate, not a current-state
            # reconstruction of old evidence. This uses existing owned history.
            archived_keys += ["checkpoint", "plan", "integrity"]
        for key in archived_keys:
            p = path(directory, key)
            if p.exists():
                data = p.read_bytes(); target = folder / p.name
                if target.is_symlink() or (target.exists() and target.read_bytes() != data):
                    raise ValueError("historical publication collision")
                if not target.exists():
                    fd, tmp = tempfile.mkstemp(prefix=".hti-history-", dir=folder)
                    try:
                        with os.fdopen(fd, "wb") as stream:
                            stream.write(data); stream.flush(); os.fsync(stream.fileno())
                        os.replace(tmp, target)
                    finally:
                        if os.path.exists(tmp): os.unlink(tmp)
                artifacts[p.name] = digest(data)
        previous = {"history_id": history_id, "artifacts": artifacts}
    pub = {"schema": "hti-publication-3", "composition": None, "operation_plan": None, "selection_review": None, "task_directory": str(directory.resolve()), "publication_id": uuid.uuid4().hex, "sequence": old["sequence"] + 1 if old else 1, "request": request, "request_sha256": digest(request.encode()), "route": route, "previous": previous}
    # History is durable before the new descriptor. Exact old residues are
    # recognizable after interruption between commit and cleanup.
    save(path(directory, "publication"), pub)
    cleanup_previous(directory, pub)
    return status(directory)



def validate_selection(pub, verify_current=True):
    from hti_core.natural_language_routing import validate_operation_plan
    if pub.get("schema") not in {"hti-publication-2", "hti-publication-3"} or not isinstance(pub.get("operation_plan"), dict):
        raise ValueError("CURRENT_OPERATION_SELECTION_REQUIRED: review the existing OperationID plan against the exact request before research")
    plan = pub["operation_plan"]
    validate_operation_plan(plan)
    if plan.get("request_text") != pub["request"] or not plan.get("operations"):
        raise ValueError("operation selection must bind the exact current request")
    review = pub.get("selection_review")
    if not isinstance(review, dict) or set(review) != {"reviewer", "request_sha256", "selection_reviewed"} or review["reviewer"] not in {"CLAUDE", "HUMAN"} or review["request_sha256"] != pub["request_sha256"] or review["selection_reviewed"] is not True:
        raise ValueError("actual current-request operation review is required")
    if pub.get("schema") == "hti-publication-3":
        from hti_core.composition import validate_binding
        if verify_current: validate_binding(pub)


def bind_operations(directory, selection):
    pub = require_active(directory)
    if pub.get("schema") not in {"hti-publication-2", "hti-publication-3"} or pub.get("operation_plan") is not None or path(directory, "draft").exists():
        raise ValueError("operation selection is immutable within an active publication; a changed request opens a fresh publication")
    if not isinstance(selection, dict) or not {"operation_plan", "selection_review"} <= set(selection) <= {"operation_plan", "selection_review", "composition_facts"}:
        raise ValueError("selection requires the existing operation plan and its review attestation")
    updated = {**pub, **{k:v for k,v in selection.items() if k != "composition_facts"}}
    if pub.get("schema") == "hti-publication-3":
        from hti_core.composition import describe
        updated["composition"] = describe(selection["operation_plan"],selection.get("composition_facts",{}))
    validate_selection(updated)
    save(path(directory, "publication"), updated)
    return status(directory)


def stage_publication(directory: Path) -> dict:
    pub = require_active(directory)
    cleanup_previous(directory, pub)
    validate_selection(pub)
    import evidence_audit
    structured = json.loads(path(directory, "checkpoint" if pub["route"] == "commentary" else "scholar").read_text())
    if pub["route"] == "scholar":
        import complete_scholar_view_task as adapter
        adapter.TASK = path(directory,"scholar")
        adapter.CHECKPOINT = path(directory,"checkpoint")
        adapter.RESPONSE_PLAN = path(directory,"plan")
        adapter.LONG_S_CHECK = path(directory,"long_s")
        evidence = adapter.copy_evidence(structured)
        claims = list(structured.get("claims", []))
        _, _, _, visible = adapter.build_identity(structured, evidence, claims)
        plan = adapter.build_plan(structured, visible, evidence)
        structured = adapter.build_checkpoint(structured, evidence, plan)
    else:
        plan = json.loads(path(directory, "plan").read_text())
    evidence_audit.validate_publication_contract(structured, plan, pub)
    from hti_core.composition import validate_state
    if pub.get("schema") != "hti-publication-3": raise ValueError("FRESH_COMPOSITION_PUBLICATION_REQUIRED")
    validate_state(directory, structured, pub)
    keys = ("checkpoint", "plan") if pub["route"] == "commentary" else ("scholar",)
    names = [FILES[k] for k in keys]
    names += [FILES[k] for k in ("integrity", "specialization", "inspection", "long_s", "dossier", "registry", "historical_graph", "uncertainty_request", "cartography", "novelty", "infrastructure", "sensitivity", "onboarding") if path(directory, k).exists()]
    if (directory / "source-checkpoint.json").exists(): names.append("source-checkpoint.json")
    inputs = {}
    for name in names:
        p = directory / name
        if p.is_symlink(): raise ValueError("structured input path escape")
        data = p.read_bytes(); json.loads(data); inputs[name] = digest(data)
    save(path(directory, "draft"), {"schema": "hti-publication-draft-1", "task_directory": str(directory.resolve()), "publication_id": pub["publication_id"], "publication_sha256": digest(path(directory, "publication").read_bytes()), "request_sha256": pub["request_sha256"], "route": pub["route"], "inputs": inputs})
    return status(directory)


def research_entry(directory: Path) -> None:
    pub = require_active(directory)
    validate_selection(pub)
    cleanup_previous(directory, pub)
    # Scholarly access requires restaging even if a current source is reread.
    path(directory, "draft").unlink(missing_ok=True)


def history(directory: Path) -> list[dict]:
    root = history_root(directory)
    if not root.exists(): return []
    result = []
    for folder in sorted(root.iterdir()):
        if folder.is_symlink() or not folder.is_dir() or not re.fullmatch(r"(?:[0-9a-f]{32}|legacy-[0-9a-f]{16})", folder.name):
            raise ValueError("invalid contained publication history")
        entries = {}
        for p in folder.iterdir():
            if p.is_symlink() or not p.is_file() or p.name not in {FILES[k] for k in ("publication", "draft", "response", "completion_receipt", "checkpoint", "plan", "integrity")}:
                raise ValueError("invalid historical artifact")
            if p.name in {FILES["checkpoint"], FILES["plan"]}:
                receipt = json.loads((folder / FILES["completion_receipt"]).read_text())
                source = json.loads((folder / FILES["integrity"]).read_text())
                if digest(p.read_bytes()) != receipt.get("inputs", {}).get(p.name) or json.loads(p.read_text()).get("work_id") != source.get("work_id"):
                    raise ValueError("historical substrate is not input-bound")
            elif p.suffix == ".json" and json.loads(p.read_text()).get("task_directory") != str(directory.resolve()):
                raise ValueError("foreign historical publication")
            entries[p.name] = digest(p.read_bytes())
        result.append({"history_id": folder.name, "artifacts": entries})
    return result


def verified_response(directory: Path, output: bytes | None = None) -> bytes:
    if status(directory)["status"] != "COMPLETE":
        raise ValueError("current successful publication is required")
    payload = path(directory, "response").read_bytes()
    if output is not None and output != payload:
        raise ValueError("output is not the exact current validated response")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["compose", "new", "files", "begin-publication", "stage-publication", "resume-publication", "select-operations", "status", "history", "verify", "replay"])
    parser.add_argument("--state-dir")
    parser.add_argument("--request")
    parser.add_argument("--selection", type=Path, help="reviewed existing OperationID plan; internal authoring, not a user requirement")
    parser.add_argument("--route", choices=["commentary", "scholar"])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--transport-recovery", action="store_true", help="attest failed delivery; replay identical committed bytes only")
    args = parser.parse_args()
    if args.command == "new":
        print(create())
    else:
        directory = resolve(args.state_dir)
        if args.command == "compose":
            from hti_core.composition import compose_request
            print(json.dumps(compose_request(args.request or descriptor(directory)["request"],directory),indent=2))
        elif args.command == "files":
            for key, name in FILES.items(): print(f"{key}: {directory / name}")
        elif args.command == "begin-publication":
            print(json.dumps(open_publication(directory, args.request, args.route)))
        elif args.command == "select-operations":
            if not args.selection or args.selection.is_symlink(): raise ValueError("regular selection input required")
            print(json.dumps(bind_operations(directory, json.loads(args.selection.read_text()))))
        elif args.command == "stage-publication":
            print(json.dumps(stage_publication(directory)))
        elif args.command == "resume-publication":
            pub = require_active(directory); cleanup_previous(directory, pub)
            print(json.dumps(status(directory)))
        elif args.command == "status": print(json.dumps(status(directory)))
        elif args.command == "history": print(json.dumps(history(directory)))
        elif args.command == "verify":
            if args.output and args.output.is_symlink(): raise ValueError("output must not be a symlink")
            verified_response(directory, args.output.read_bytes() if args.output else None)
            print(json.dumps(status(directory)))
        elif args.command == "replay":
            if not args.transport_recovery:raise ValueError("TRANSPORT_RECOVERY_ONLY: normal successful publication has no following workflow")
            import sys
            import terminal_output
            terminal_output.recover(directory)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError) as exc:
        import sys
        print(f"task state error: {exc}", file=sys.stderr)
        raise SystemExit(2)
