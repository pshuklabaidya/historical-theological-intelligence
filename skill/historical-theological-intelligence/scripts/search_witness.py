#!/usr/bin/env python3
"""Search text only through an explicit witness registry entry."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--registry", required=True, type=Path)
    p.add_argument("--witness-id", required=True)
    p.add_argument("query")
    p.add_argument("--regex", action="store_true")
    p.add_argument("--case-sensitive", action="store_true")
    p.add_argument("--context", type=int, default=1)
    p.add_argument("--max-results", type=int, default=20)
    p.add_argument("--state-dir")
    args = p.parse_args()
    data = json.loads(args.registry.read_text(encoding="utf-8"))
    items = [w for w in data.get("witnesses", []) if w.get("witness_id") == args.witness_id]
    if len(items) != 1:
        print(f"ERROR: witness {args.witness_id!r} is not uniquely registered", file=sys.stderr)
        return 2
    witness = items[0]
    if witness.get("work_id", data.get("work_id")) != data.get("work_id"):
        print("ERROR: witness belongs to another work", file=sys.stderr)
        return 2
    if witness.get("access_status", "available") != "available":
        print("ERROR: registered witness text is not available", file=sys.stderr)
        return 2
    text_path = Path(witness.get("text_path", ""))
    if not text_path.is_absolute():
        text_path = args.registry.parent / text_path
    if not text_path.is_file():
        print(f"ERROR: registered text not found: {text_path}", file=sys.stderr)
        return 2
    from specialization_resources import authorize_path
    installed = authorize_path(text_path, args.state_dir)
    if installed and (installed['work_id'] != data.get('work_id') or installed['witness_id'] != args.witness_id):
        print('ERROR: installed witness scope or identity substitution', file=sys.stderr)
        return 2
    if installed and not (0 <= args.context <= 15 and 1 <= args.max_results <= 20):
        print('ERROR: installed witness search must remain bounded', file=sys.stderr)
        return 2
    flags = 0 if args.case_sensitive else re.IGNORECASE
    pattern = re.compile(args.query if args.regex else re.escape(args.query), flags)
    lines = text_path.read_text(encoding="utf-8").splitlines()
    hits = []
    for index, line in enumerate(lines):
        if pattern.search(line):
            start, end = max(0, index - args.context), min(len(lines), index + args.context + 1)
            hits.append({"line": index + 1, "context_start": start + 1, "context": lines[start:end]})
            if len(hits) >= args.max_results:
                break
    result = {"work_id": data.get("work_id"), "witness_id": args.witness_id, "query": args.query, "hits": hits}
    if installed:
        result.update(witness=installed, independence_group=installed['evidence_root_id'], exact_original_wording=False, independent_latin_corroboration=False)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
