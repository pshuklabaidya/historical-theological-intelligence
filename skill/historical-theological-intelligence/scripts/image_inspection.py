"""Finite evidence-question inspection plans rooted in original image bytes."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from datetime import datetime, timezone

import task_state

SCHEMA = "hti-image-inspection-1"
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
PARAMETERS = {"box", "scale", "rotation", "contrast", "sharpness", "brightness", "quad"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".bmp", ".gif"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".inspection-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def invalidate_response(directory: Path) -> None:
    for key in ("completion_receipt", "response"):
        task_state.path(directory, key).unlink(missing_ok=True)


def load(directory: Path) -> dict:
    value = json.loads(task_state.path(directory, "inspection").read_text())
    if value.get("schema") != SCHEMA or value.get("task_directory") != str(directory.resolve()):
        raise ValueError("inspection state belongs to a different task or schema")
    if not isinstance(value.get("questions"), dict) or not isinstance(value.get("sources"), dict):
        raise ValueError("invalid inspection state")
    for q in value["questions"].values():
        if q.get("plan_sha256") != plan_hash(q):
            raise ValueError("registered inspection plan changed; do not refill regions")
    return value


def plan_hash(question: dict) -> str:
    value = {k: question[k] for k in ("question", "relevance", "source_sha256")}
    value["regions"] = {rid: {k: r[k] for k in ("reason", "parameters")}
                        for rid, r in question["regions"].items()}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode("utf-8")).hexdigest()


def require_text(value, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} requires an explicit evidentiary reason")
    return value.strip()


def identifier(value) -> str:
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError("question and region IDs require simple unique identifiers")
    return value


def normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def validate_parameters(parameters: dict, size: tuple[int, int]) -> None:
    if not isinstance(parameters, dict) or not parameters or set(parameters) - PARAMETERS:
        raise ValueError("region requires supported view parameters")
    width, height = size
    box = parameters.get("box", [0, 0, width, height])
    if not isinstance(box, list) or len(box) != 4 or any(type(n) is not int for n in box):
        raise ValueError("box requires four original-image pixel coordinates")
    if not (0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height):
        raise ValueError("region lies outside the original image")
    for key in ("scale", "rotation", "contrast", "sharpness", "brightness"):
        value = parameters.get(key, 0 if key == "rotation" else 1)
        if type(value) not in (float, int) or not math.isfinite(value) or (key != "rotation" and value <= 0):
            raise ValueError(f"invalid {key}")
    quad = parameters.get("quad")
    if quad is not None:
        if "box" in parameters or not isinstance(quad, list) or len(quad) != 8:
            raise ValueError("quad requires eight original coordinates and cannot combine with box")
        if any(type(n) not in (int, float) or not math.isfinite(n) for n in quad):
            raise ValueError("invalid perspective coordinates")
        if any(not (0 <= quad[i] <= width and 0 <= quad[i+1] <= height) for i in range(0, 8, 2)):
            raise ValueError("perspective region lies outside original")
        if any(math.dist(quad[i:i+2], quad[j:j+2]) == 0 for i, j in ((0, 2), (6, 4), (0, 6), (2, 4))):
            raise ValueError("degenerate perspective region")


def ensure_original(source: dict) -> Path:
    path = Path(source["path"])
    if not path.is_file() or sha(path) != source["sha256"]:
        raise ValueError("original image bytes changed or are unavailable")
    if path.with_suffix(path.suffix + ".provenance.json").exists():
        raise ValueError("an inspection derivative cannot be a source image")
    return path


def register(directory: Path, plan: dict) -> None:
    """Append a distinct question's finite plan; never refill an existing plan."""
    from PIL import Image, ImageOps
    state_path = task_state.path(directory, "inspection")
    data = load(directory) if state_path.exists() else {
        "schema": SCHEMA, "task_directory": str(directory.resolve()), "sources": {}, "questions": {}}
    data = copy.deepcopy(data)
    path = Path(require_text(plan.get("source"), "source")).resolve(strict=True)
    fingerprint = sha(path)
    if path.with_suffix(path.suffix + ".provenance.json").exists():
        raise ValueError("crop-of-crop or derivative-as-original registration is prohibited")
    for question in data["questions"].values():
        for region in question["regions"].values():
            if region.get("output_sha256") == fingerprint or region.get("output_path") == str(path):
                raise ValueError("a renamed or copied derivative cannot become an original")
    with Image.open(path) as im:
        size = ImageOps.exif_transpose(im).size
    source = {"path": str(path), "sha256": fingerprint, "size": list(size)}
    if fingerprint in data["sources"] and data["sources"][fingerprint] != source:
        raise ValueError("reuse the registered original path")
    data["sources"][fingerprint] = source
    questions = plan.get("questions")
    if not isinstance(questions, list) or not questions:
        raise ValueError("plan requires explicit evidentiary questions")
    existing_texts = {normalized(q["question"]) for q in data["questions"].values()}
    existing_views = {(q["source_sha256"], json.dumps(r["parameters"], sort_keys=True))
                      for q in data["questions"].values() for r in q["regions"].values()}
    for item in questions:
        qid = identifier(item.get("question_id"))
        question = require_text(item.get("question"), "question")
        relevance = require_text(item.get("relevance"), "relevance")
        if qid in data["questions"] or normalized(question) in existing_texts:
            raise ValueError("question already registered; its inspection budget cannot be replenished")
        regions = item.get("regions")
        if not isinstance(regions, list) or not regions:
            raise ValueError("question requires a finite region plan before inspection")
        registered = {}
        for region in regions:
            rid = identifier(region.get("region_id"))
            if rid in registered:
                raise ValueError("duplicate region ID")
            reason = require_text(region.get("reason"), "region reason")
            parameters = region.get("parameters")
            validate_parameters(parameters, size)
            view_key = (fingerprint, json.dumps(parameters, sort_keys=True))
            if view_key in existing_views:
                raise ValueError("view already planned; reuse its existing observation instead")
            existing_views.add(view_key)
            registered[rid] = {"reason": reason, "parameters": copy.deepcopy(parameters), "status": "PLANNED"}
        data["questions"][qid] = {"question": question, "relevance": relevance,
                                  "source_sha256": fingerprint, "status": "OPEN", "regions": registered}
        data["questions"][qid]["plan_sha256"] = plan_hash(data["questions"][qid])
        existing_texts.add(normalized(question))
    invalidate_response(directory)
    write(state_path, data)


def view(directory: Path, qid: str, rid: str) -> Path:
    from PIL import Image, ImageEnhance, ImageOps
    data = load(directory)
    question = data["questions"][qid]
    region = question["regions"][rid]
    if question["status"] != "OPEN" or region["status"] != "PLANNED":
        raise ValueError("inspection is finished or this view is consumed; reuse the existing view")
    source = data["sources"][question["source_sha256"]]
    original = ensure_original(source)
    parameters = region["parameters"]
    validate_parameters(parameters, tuple(source["size"]))
    output_dir = directory / "inspection-views"
    output_dir.mkdir(exist_ok=True)
    output = output_dir / f"{identifier(qid)}--{identifier(rid)}.png"
    if output.exists():
        raise ValueError("view file already exists; retain it instead of overwriting")
    # Reserve the region before doing image work. An interrupted attempt cannot
    # silently restart or grow the plan. Its question can close UNRESOLVED.
    region["status"] = "ATTEMPTED"
    invalidate_response(directory)
    write(task_state.path(directory, "inspection"), data)
    with Image.open(original) as im:
        result = ImageOps.exif_transpose(im).convert("RGB")
        quad = parameters.get("quad")
        if quad is not None:
            width = round(max(math.dist(quad[0:2], quad[2:4]), math.dist(quad[6:8], quad[4:6])))
            height = round(max(math.dist(quad[0:2], quad[6:8]), math.dist(quad[2:4], quad[4:6])))
            result = result.transform((max(1, width), max(1, height)), Image.Transform.QUAD, quad,
                                      resample=Image.Resampling.BICUBIC)
        elif "box" in parameters:
            result = result.crop(parameters["box"])
        if parameters.get("rotation", 0):
            result = result.rotate(parameters["rotation"], expand=True, resample=Image.Resampling.BICUBIC,
                                   fillcolor="white")
        for key, enhancer in (("contrast", ImageEnhance.Contrast), ("sharpness", ImageEnhance.Sharpness),
                              ("brightness", ImageEnhance.Brightness)):
            result = enhancer(result).enhance(parameters.get(key, 1))
        scale = parameters.get("scale", 1)
        result = result.resize((max(1, round(result.width*scale)), max(1, round(result.height*scale))),
                               Image.Resampling.LANCZOS)
        result.save(output)
    ensure_original(source)
    provenance = {"schema": SCHEMA, "created_utc": datetime.now(timezone.utc).isoformat(),
                  "operation": "planned-original-view", "question_id": qid,
                  "region_id": rid, "question": question["question"], "region_reason": region["reason"],
                  "original": source, "parameters": parameters, "output": {"path": str(output), "sha256": sha(output)},
                  "independent_evidence": False, "ancestry_sha256": source["sha256"]}
    sidecar = output.with_suffix(output.suffix + ".provenance.json")
    write(sidecar, provenance)
    region.update(status="INSPECTABLE", output_path=str(output), output_sha256=sha(output),
                  provenance_sha256=sha(sidecar))
    write(task_state.path(directory, "inspection"), data)
    return output


def close(directory: Path, qid: str, outcome: str, finding: str) -> None:
    if outcome not in {"RESOLVED", "UNRESOLVED"}:
        raise ValueError("outcome must be RESOLVED or UNRESOLVED")
    data = load(directory)
    q = data["questions"][qid]
    if q["status"] != "OPEN":
        raise ValueError("question is already closed")
    if outcome == "RESOLVED" and any(r["status"] == "ATTEMPTED" for r in q["regions"].values()):
        raise ValueError("an interrupted view attempt remains unresolved")
    q.update(status=outcome, finding=require_text(finding, "finding"))
    for r in q["regions"].values():
        if r["status"] == "PLANNED":
            r["status"] = "UNUSED"
    invalidate_response(directory)
    write(task_state.path(directory, "inspection"), data)


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings(v)


def validate_completion(directory: Path, checkpoint: dict, *, rendered_text: str | None = None) -> None:
    # Unplanned image files cannot silently bypass the region operation. An
    # original kept inside task state must be explicitly registered as supplied
    # image evidence with its exact path and hash, or in the inspection plan.
    present = {p.resolve() for p in directory.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES}
    supplied = set()
    for e in checkpoint.get("evidence", []):
        if e.get("evidence_class") != "supplied_image_observation":
            continue
        provenance = e.get("provenance", {})
        if isinstance(provenance, dict) and provenance.get("path") and provenance.get("sha256"):
            path = Path(provenance["path"])
            if path.is_file() and sha(path) == provenance["sha256"] and not path.with_suffix(path.suffix + ".provenance.json").exists():
                supplied.add(path.resolve())
    if not task_state.path(directory, "inspection").exists():
        if present - supplied:
            raise ValueError("unregistered image view in task state; use a finite evidentiary-question plan")
        return
    data = load(directory)
    managed = {Path(s["path"]).resolve() for s in data["sources"].values()} | supplied
    for qid, q in data["questions"].items():
        for rid, r in q["regions"].items():
            if r["status"] in {"INSPECTABLE", "ATTEMPTED"}:
                managed.add((directory / "inspection-views" / f"{identifier(qid)}--{identifier(rid)}.png").resolve())
    if present - managed:
        raise ValueError("unregistered image view in task state; do not extend or bypass the finite plan")
    evidence = checkpoint.get("evidence", [])
    for fingerprint, source in data["sources"].items():
        ensure_original(source)
        originals = [e for e in evidence if e.get("evidence_class") == "supplied_image_observation"
                     and (fingerprint in set(strings(e)) or source["path"] in set(strings(e)))]
        if not originals and len(data["sources"]) == 1:
            originals = [e for e in evidence if e.get("evidence_id") == "E-SUPPLIED-PAGE"
                         and e.get("evidence_class") == "supplied_image_observation"]
        groups = {e.get("independence_group") for e in originals}
        for q in data["questions"].values():
            if q["source_sha256"] != fingerprint:
                continue
            if q["status"] not in {"RESOLVED", "UNRESOLVED"} or not q.get("finding"):
                raise ValueError("close every inspection question as RESOLVED or UNRESOLVED before completion")
            if q["status"] == "UNRESOLVED" and rendered_text is not None:
                if normalized(q["finding"]) not in normalized(rendered_text):
                    raise ValueError("an unresolved inspection finding must remain visible in the response plan: " + q["finding"])
            for region in q["regions"].values():
                if region["status"] == "INSPECTABLE":
                    output = Path(region["output_path"])
                    sidecar = output.with_suffix(output.suffix + ".provenance.json")
                    if sha(output) != region["output_sha256"] or sha(sidecar) != region["provenance_sha256"]:
                        raise ValueError("inspection view or provenance bytes changed")
                    provenance = json.loads(sidecar.read_text())
                    if (provenance.get("original") != source or provenance.get("parameters") != region["parameters"] or
                            provenance.get("independent_evidence") is not False or
                            provenance.get("ancestry_sha256") != fingerprint):
                        raise ValueError("inspection provenance does not match its original and planned region")
                    markers = {str(output), region["output_sha256"]}
                    for e in evidence:
                        if markers & set(strings(e)):
                            if (e.get("evidence_class") != "supplied_image_observation" or
                                    e.get("independence_group") not in groups or
                                    e.get("independent_evidence") is True):
                                raise ValueError("derivatives share their original evidence group; they are not witnesses")
                elif region["status"] not in {"UNUSED", "ATTEMPTED"}:
                    raise ValueError("invalid inspection region state")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["register", "close"])
    p.add_argument("--state-dir")
    p.add_argument("--plan", type=Path)
    p.add_argument("--question-id")
    p.add_argument("--outcome", choices=["RESOLVED", "UNRESOLVED"])
    p.add_argument("--finding")
    a = p.parse_args()
    try:
        directory = task_state.resolve(a.state_dir)
        if a.command == "register":
            if not a.plan:
                raise ValueError("register requires --plan")
            register(directory, json.loads(a.plan.read_text()))
        else:
            close(directory, a.question_id, a.outcome, a.finding)
    except Exception as exc:
        p.exit(2, f"inspection error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
