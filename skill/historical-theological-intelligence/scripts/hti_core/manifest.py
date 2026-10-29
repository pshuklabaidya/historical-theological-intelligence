"""Neutral manifest mechanics without shared domain semantics."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Mapping

from .hashing import canonical_json, sha256_json
from .model import ValidationError


@dataclass(frozen=True)
class NeutralManifest:
    """Lossless manifest payload with optional opaque identity and kind."""

    _payload: Mapping[str, Any] = field(repr=False)
    kind: str | None = None
    manifest_id: str | None = None

    @classmethod
    def from_dict(
        cls,
        value: Any,
        *,
        kind: str | None = None,
        manifest_id: str | None = None,
    ) -> "NeutralManifest":
        if not isinstance(value, dict):
            raise ValidationError("manifest payload must be an object")
        supplied_kind = value.get("manifest_kind")
        if supplied_kind is not None:
            if not isinstance(supplied_kind, str) or not supplied_kind:
                raise ValidationError("manifest_kind must be a non-empty string")
            if kind is not None and kind != supplied_kind:
                raise ValidationError("supplied manifest kind conflicts with payload")
            kind = supplied_kind
        if kind is not None and (not isinstance(kind, str) or not kind):
            raise ValidationError("manifest kind must be a non-empty string")
        supplied_id = value.get("manifest_id")
        if supplied_id is not None:
            if not isinstance(supplied_id, str) or not supplied_id:
                raise ValidationError("manifest_id must be a non-empty string")
            if manifest_id is not None and manifest_id != supplied_id:
                raise ValidationError("supplied manifest id conflicts with payload")
            manifest_id = supplied_id
        if manifest_id is not None and (
            not isinstance(manifest_id, str) or not manifest_id
        ):
            raise ValidationError("manifest id must be a non-empty string")
        entries = value.get("entries")
        if entries is not None and not isinstance(entries, (list, dict)):
            raise ValidationError("manifest entries must be an ordered list or keyed object")
        return cls(copy.deepcopy(value), kind, manifest_id)

    @property
    def entries(self) -> list[Any] | dict[str, Any] | None:
        return copy.deepcopy(self._payload.get("entries"))

    @property
    def derivation_metadata(self) -> dict[str, Any]:
        return {
            key: copy.deepcopy(value)
            for key, value in self._payload.items()
            if key == "derivation" or key.startswith("derived_")
        }

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._payload))

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())

    def sha256(self) -> str:
        return sha256_json(self.to_dict())
