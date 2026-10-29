#!/usr/bin/env python3
"""Token-level collation with configurable labels and optional orthographic folding."""

from __future__ import annotations

import argparse
import difflib
import json
import re
import unicodedata
from pathlib import Path


def normalize(text: str, ignore_orthography: bool) -> list[str]:
    text = unicodedata.normalize("NFKC", text)
    if ignore_orthography:
        table = str.maketrans({"v": "u", "V": "u", "j": "i", "J": "i", "æ": "ae", "Æ": "ae", "œ": "oe", "Œ": "oe", "ſ": "s"})
        text = text.translate(table).lower()
        return re.findall(r"[a-zà-öø-ÿ]+", text)
    return re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)


def collate(a: str, b: str, ignore_orthography: bool) -> list[dict]:
    at, bt = normalize(a, ignore_orthography), normalize(b, ignore_orthography)
    matcher = difflib.SequenceMatcher(a=at, b=bt, autojunk=False)
    variants = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            variants.append({"operation": tag, "a_range": [i1, i2], "b_range": [j1, j2], "a": at[i1:i2], "b": bt[j1:j2]})
    return variants


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("a", type=Path)
    p.add_argument("b", type=Path)
    p.add_argument("--a-label", default="witness-a")
    p.add_argument("--b-label", default="witness-b")
    p.add_argument("--ignore-orthography", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--state-dir")
    args = p.parse_args()
    from specialization_resources import authorize_path
    a_source = authorize_path(args.a, args.state_dir)
    b_source = authorize_path(args.b, args.state_dir)
    variants = collate(args.a.read_text(encoding="utf-8"), args.b.read_text(encoding="utf-8"), args.ignore_orthography)
    result = {"a_label": args.a_label, "b_label": args.b_label, "ignore_orthography": args.ignore_orthography, "variant_count": len(variants), "variants": variants}
    if a_source or b_source:
        result['installed_sources'] = {'a': a_source, 'b': b_source}
        result['independent_latin_corroboration'] = False
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{args.a_label} vs {args.b_label}: {len(variants)} variant block(s)")
        for v in variants:
            print(f"- {v['operation']}: {' '.join(v['a'])!r} -> {' '.join(v['b'])!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
