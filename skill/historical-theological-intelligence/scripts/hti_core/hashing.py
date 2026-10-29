"""Canonical JSON and SHA-256 helpers compatible with Version 0.1."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("sha256_text requires str")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_canonical_json(value: Any) -> str:
    return sha256_text(canonical_json(value))


def sha256_json(value: Any) -> str:
    """Released Version 0.1 function name retained for compatibility."""

    return sha256_canonical_json(value)
