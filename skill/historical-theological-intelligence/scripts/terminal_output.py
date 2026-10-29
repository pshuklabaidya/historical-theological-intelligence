"""One final publication operation for every structured response route."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

import image_inspection
import source_integrity
import task_state
import specialization_core


DIRECT_OUTPUT_CEILING = 24000
DELIVERY_FAILURE_NOTICE = "Delivery is unfinished. Continue to recover the preserved response."
DESIGN_R_POLICY = {"preparation_reviewed": True, "delivery": "DESIGN_R_PUBLISHER_SELECTED",
                   "success_continuation": "RELAY_COMMITTED_RESPONSE_AND_STOP",
                   "post_success_actions": ["ONE_BOUND_READ_IF_READ_COMMITTED_FILE"]}


def transport_mode(payload: bytes) -> str:
    return "DIRECT_STDOUT" if len(payload) <= DIRECT_OUTPUT_CEILING else "READ_COMMITTED_FILE"


def transport_bytes(directory: Path, payload: bytes, publication_id: str) -> bytes:
    if transport_mode(payload) == "DIRECT_STDOUT":
        return payload
    response = task_state.path(directory, "response")
    if response.resolve().parent != directory.resolve():
        raise ValueError("committed response must remain in the current owned task")
    stub = {"schema": "hti-terminal-transport-1", "transport_mode": "READ_COMMITTED_FILE",
            "response_path": str(response.resolve()), "response_sha256": digest(payload),
            "response_bytes": len(payload), "publication_id": publication_id,
            "instruction": "Make exactly one Read of response_path with allow_large=true and no offset or limit. "
            "Then relay the complete file body exactly, removing only host-added Read presentation decoration, and stop. "
            "No second Read, Bash, cat, replay, helper, research, source inspection, restaging, rerendering, new publication, "
            "narration or substantive editing is permitted after this stub. If Read errors, is refused, or explicitly "
            "reports truncation/incompleteness, issue no more tool and return only failure_notice, never partial content. "
            "If the host interrupts the final relay or injects an output-token-limit continuation, do not resume mid-body "
            "or narrate the commit: issue no further tool and return only failure_notice. A later user Continue "
            "recovers this same immutable commit.",
            "failure_notice": DELIVERY_FAILURE_NOTICE}
    return (json.dumps(stub, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def emit(payload: bytes) -> None:
    if hasattr(sys.stdout, "buffer"):
        sys.stdout.buffer.write(payload)
        sys.stdout.buffer.flush()
    else:
        sys.stdout.write(payload.decode("utf-8"))
        sys.stdout.flush()


def recover(directory: Path) -> None:
    # Recovery reads only the verified current commit; it never renders or writes.
    payload = task_state.verified_response(directory)
    emit(transport_bytes(directory, payload, task_state.descriptor(directory)["publication_id"]))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".hti-write-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def begin(directory: Path) -> None:
    """A failed retry cannot leave a former answer marked as current success."""
    task_state.require_ready(directory)
    for key in ("completion_receipt", "response"):
        task_state.path(directory, key).unlink(missing_ok=True)


def capture(directory: Path, input_keys: tuple[str, ...]) -> dict[str, str]:
    publication = task_state.require_ready(directory)
    if ("scholar" in input_keys and publication["route"] != "scholar") or (input_keys == ("checkpoint", "plan") and publication["route"] != "commentary"):
        raise ValueError("completion operation must match the current selected route")
    inputs = {task_state.FILES[key]: digest(task_state.path(directory, key).read_bytes()) for key in input_keys}
    inputs.update(task_state.current_draft(directory, publication)["inputs"])
    for key in ("publication", "draft"):
        p = task_state.path(directory, key)
        inputs[p.name] = digest(p.read_bytes())
    marker = (directory / ".hti-state").read_text().strip()
    if marker not in {"1", "2", "3"}:
        raise ValueError("unknown task contract version")
    integrity = task_state.path(directory, "integrity")
    if marker in {"2", "3"} or integrity.exists():
        if not integrity.is_file():
            raise ValueError("SOURCE_INTEGRITY_REQUIRED: fill source-integrity.json in the task directory")
        inputs[integrity.name] = digest(integrity.read_bytes())
        inputs[".hti-state"] = digest((directory / ".hti-state").read_bytes())
        legacy = task_state.path(directory, "registry")
        if legacy.exists():
            inputs[legacy.name] = digest(legacy.read_bytes())
        dossier = task_state.path(directory, "dossier")
        if dossier.exists():
            inputs[dossier.name] = digest(dossier.read_bytes())
    specialization = directory / "specialization-context.json"
    if specialization.exists():
        inputs[specialization.name] = digest(specialization.read_bytes())
    return inputs


def publish(directory: Path, text: str, checkpoint: dict, expected_inputs: dict[str, str]) -> None:
    """Finish all checks and file writes before emitting exactly one payload.

    The caller supplies the already validated renderer output. This function
    never edits or renders it again. A receipt is internal state, not stdout.
    """
    inputs = dict(expected_inputs)
    publication = task_state.require_ready(directory)
    for key in ("publication", "draft"):
        p = task_state.path(directory, key)
        if inputs.get(p.name) != digest(p.read_bytes()):
            raise ValueError("current publication was not captured by completion")
    from hti_core.composition import begin_validation, record_validator, composition_receipt
    begin_validation()
    source_integrity.validate_completion(directory, checkpoint, rendered_text=text)
    record_validator("source_integrity:validate_completion")
    if (directory / "specialization-context.json").exists() and "specialization-context.json" not in inputs:
        raise ValueError("specialization context appeared after input capture; retry completion")
    specialization_core.validate_completion(directory, checkpoint, rendered_text=text)
    record_validator("specialization_core:validate_completion")
    inspection_path = task_state.path(directory, "inspection")
    if inspection_path.exists():
        inputs[inspection_path.name] = digest(inspection_path.read_bytes())
    image_inspection.validate_completion(directory, checkpoint, rendered_text=text)
    record_validator("image_inspection:validate_completion")
    payload = text.encode("utf-8")
    if not payload:
        raise ValueError("completion produced no response")
    for name, expected in inputs.items():
        if Path(name).name != name or (directory / name).is_symlink() or digest((directory / name).read_bytes()) != expected:
            raise ValueError("structured input changed during completion; rerun the same operation")
    receipt = {
        "schema": "hti-terminal-output-4",
        "composition": composition_receipt(directory,checkpoint,publication),
        "transport_mode": transport_mode(payload),
        "direct_output_ceiling": DIRECT_OUTPUT_CEILING,
        "status": "COMPLETE",
        "task_directory": str(directory.resolve()),
        "publication_id": publication["publication_id"],
        "request_sha256": publication["request_sha256"],
        "route": publication["route"],
        "inputs": inputs,
        "response_file": task_state.FILES["response"],
        "response_sha256": digest(payload),
        "response_bytes": len(payload),
        "encoding": "utf-8",
    }
    committed = False
    try:
        atomic_write(task_state.path(directory, "response"), payload)
        atomic_write(task_state.path(directory, "completion_receipt"),
                     (json.dumps(receipt, indent=2) + "\n").encode("utf-8"))
        committed = True
        # Substantive state is frozen. Only the publisher-selected transport remains.
        emit(transport_bytes(directory, payload, publication["publication_id"]))
    except Exception:
        # A committed validated response survives transport failure for exact
        # replay of this publication. An incomplete write is not success.
        if not committed:
            for key in ("completion_receipt", "response"):
                task_state.path(directory, key).unlink(missing_ok=True)
        raise
