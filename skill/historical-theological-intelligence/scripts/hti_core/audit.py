"""Neutral deterministic audit-result primitives compatible with Version 0.1."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from .model import ValidationError


_V01_FINDING = re.compile(r"^(?P<code>[A-Z][A-Z0-9_]*)\: (?P<message>.+)$", re.S)


@dataclass(frozen=True)
class AuditFinding:
    """One blocking Version 0.1-compatible audit finding."""

    code: str
    message: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", self.code):
            raise ValidationError("audit finding code must be an uppercase stable code")
        if not isinstance(self.message, str) or not self.message:
            raise ValidationError("audit finding message must be a non-empty string")

    @classmethod
    def from_v01_string(cls, value: Any) -> "AuditFinding":
        if not isinstance(value, str):
            raise ValidationError("v0.1 audit finding must be a string")
        match = _V01_FINDING.fullmatch(value)
        if not match:
            raise ValidationError("invalid v0.1 audit finding string")
        return cls(match.group("code"), match.group("message"))

    def to_v01_string(self) -> str:
        return f"{self.code}: {self.message}"


@dataclass(frozen=True)
class AuditResult:
    """Ordered findings with fail-closed PASS or FAIL derived from the collection."""

    findings: tuple[AuditFinding, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.findings, tuple) or any(
            not isinstance(item, AuditFinding) for item in self.findings
        ):
            raise ValidationError("audit findings must be an ordered tuple")

    @classmethod
    def from_v01_strings(cls, values: Any) -> "AuditResult":
        if not isinstance(values, list):
            raise ValidationError("v0.1 audit findings must be a list")
        return cls(tuple(AuditFinding.from_v01_string(item) for item in values))

    @property
    def passed(self) -> bool:
        return not self.findings

    @property
    def status(self) -> str:
        return "PASS" if self.passed else "FAIL"

    def to_v01_strings(self) -> list[str]:
        return [item.to_v01_string() for item in self.findings]

    def extend(self, findings: Iterable[AuditFinding]) -> "AuditResult":
        additions = tuple(findings)
        if any(not isinstance(item, AuditFinding) for item in additions):
            raise ValidationError("audit findings must contain AuditFinding objects")
        return AuditResult(self.findings + additions)
