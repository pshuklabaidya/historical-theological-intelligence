#!/usr/bin/env python3
"""Non-destructive original inspection and planned evidentiary views."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageFilter, ImageOps, ImageStat

import image_inspection
import task_state

SCHEMA = "hti-image-inspection-1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def require_input(path: Path) -> None:
    if not path.is_file():
        raise SystemExit(f"Input image not found: {path}")


def require_safe_output(output: Path, inputs: Iterable[Path]) -> None:
    if any(output.resolve() == p.resolve() for p in inputs):
        raise SystemExit("Refusing to overwrite an original image")
    if output.exists():
        raise SystemExit(f"Refusing to overwrite an existing file: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)


def inspect_record(path: Path) -> dict:
    require_input(path)
    with Image.open(path) as opened:
        gray = ImageOps.exif_transpose(opened).convert("L")
        stat = ImageStat.Stat(gray)
        edge = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES))
        width, height = gray.size
        orientation = "portrait" if height > width else "landscape" if width > height else "square"
        indicators = []
        if min(width, height) < 1000:
            indicators.append("low pixel dimension")
        if stat.mean[0] < 70:
            indicators.append("globally dark")
        if stat.stddev[0] < 25:
            indicators.append("low global contrast")
        if orientation == "landscape" and width / max(height, 1) > 1.25:
            indicators.append("possible two-page opening")
        return {"filename": path.name, "path": str(path), "sha256": sha256(path), "format": opened.format,
                "width": width, "height": height, "orientation": orientation,
                "brightness_mean": round(stat.mean[0], 2), "contrast_stddev": round(stat.stddev[0], 2),
                "edge_energy": round(edge.var[0], 2), "advisory_indicators": indicators,
                "visual_confirmation_required": True}


def cmd_inspect(a: argparse.Namespace) -> None:
    output = Path(a.output)
    require_safe_output(output, [])
    output.write_text(json.dumps({"schema": "early-modern-latin-image-manifest-v0.1", "created_utc": utc_now(),
                                  "images": [inspect_record(Path(p)) for p in a.images]}, indent=2) + "\n", encoding="utf-8")
    print(output)



def cmd_view(a: argparse.Namespace) -> None:
    directory = task_state.resolve(a.state_dir)
    print(image_inspection.view(directory, a.question_id, a.region_id))


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    x = sub.add_parser("inspect")
    x.add_argument("images", nargs="+")
    x.add_argument("--output", required=True)
    x.set_defaults(func=cmd_inspect)
    x = sub.add_parser("view")
    x.add_argument("--state-dir")
    x.add_argument("--question-id", required=True)
    x.add_argument("--region-id", required=True)
    x.set_defaults(func=cmd_view)
    for command in ("rotate", "crop", "enlarge", "enhance", "split", "lines", "perspective", "montage"):
        x = sub.add_parser(command)
        x.add_argument("arguments", nargs=argparse.REMAINDER)
        x.set_defaults(func=None)
    return p


def main() -> int:
    p = parser()
    args = p.parse_args()
    if args.func is None:
        p.exit(2, "inspection error: register finite evidentiary regions and use view; every view starts from the original image\n")
    try:
        args.func(args)
    except Exception as exc:
        p.exit(2, f"inspection error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
