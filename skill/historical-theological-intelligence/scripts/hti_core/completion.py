"""Neutral, fail-closed structured-completion mechanics.

Domain code supplies preparation, audit, rendering, assembly, and response
extraction callbacks. This module controls only their order, binding, and
successful-result exposure.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from .audit import AuditResult
from .hashing import sha256_json, sha256_text
from .manifest import NeutralManifest
from .model import ValidationError


class CompletionError(RuntimeError):
    """Raised when a guarded completion stage cannot continue safely."""


@dataclass(frozen=True)
class CompletionBindings:
    """Canonical hashes bound to isolated plan, response, and manifest values."""

    _plan: Mapping[str, Any] = field(repr=False)
    _response_text: str = field(repr=False)
    _manifest: Mapping[str, Any] | None = field(default=None, repr=False)
    plan_sha256: str = ""
    response_sha256: str = ""
    manifest_sha256: str | None = None

    @classmethod
    def create(
        cls,
        plan: Any,
        response_text: Any,
        manifest: Any | None = None,
    ) -> "CompletionBindings":
        if not isinstance(plan, dict):
            raise ValidationError("completion plan must be an object")
        if not isinstance(response_text, str):
            raise ValidationError("completion response must be text")
        manifest_payload: dict[str, Any] | None = None
        manifest_hash: str | None = None
        if manifest is not None:
            manifest_payload = NeutralManifest.from_dict(manifest).to_dict()
            manifest_hash = sha256_json(manifest_payload)
        plan_copy = copy.deepcopy(plan)
        return cls(
            plan_copy,
            response_text,
            manifest_payload,
            sha256_json(plan_copy),
            sha256_text(response_text),
            manifest_hash,
        )

    @property
    def plan(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._plan))

    @property
    def response_text(self) -> str:
        return self._response_text

    @property
    def manifest(self) -> dict[str, Any] | None:
        if self._manifest is None:
            return None
        return copy.deepcopy(dict(self._manifest))

    def validates(
        self,
        *,
        plan: Any,
        response_text: Any,
        manifest: Any | None = None,
    ) -> bool:
        if not isinstance(plan, dict) or not isinstance(response_text, str):
            return False
        if sha256_json(plan) != self.plan_sha256:
            return False
        if sha256_text(response_text) != self.response_sha256:
            return False
        if self.manifest_sha256 is None:
            return manifest is None
        if not isinstance(manifest, dict):
            return False
        return sha256_json(manifest) == self.manifest_sha256


@dataclass(frozen=True)
class CompletionReceipt:
    """Lossless binding artifact. It does not certify that audits passed."""

    _payload: Mapping[str, Any] = field(repr=False)

    @classmethod
    def create(
        cls,
        *,
        status: str,
        renderer: str,
        schema_version: str,
        bindings: CompletionBindings,
    ) -> "CompletionReceipt":
        for value, label in (
            (status, "completion status"),
            (renderer, "renderer identifier"),
            (schema_version, "completion schema version"),
        ):
            if not isinstance(value, str) or not value:
                raise ValidationError(f"{label} must be a non-empty string")
        payload: dict[str, Any] = {
            "status": status,
            "renderer": renderer,
            "schema_version": schema_version,
            "plan": bindings.plan,
            "plan_sha256": bindings.plan_sha256,
            "response_sha256": bindings.response_sha256,
        }
        if bindings.manifest_sha256 is not None:
            payload["manifest_sha256"] = bindings.manifest_sha256
        return cls(payload)

    @classmethod
    def from_dict(cls, value: Any) -> "CompletionReceipt":
        if not isinstance(value, dict):
            raise ValidationError("completion receipt must be an object")
        for key in ("status", "renderer", "schema_version"):
            if not isinstance(value.get(key), str) or not value[key]:
                raise ValidationError(f"completion receipt {key} must be a non-empty string")
        if not isinstance(value.get("plan"), dict):
            raise ValidationError("completion receipt plan must be an object")
        for key in ("plan_sha256", "response_sha256"):
            if not isinstance(value.get(key), str) or not value[key]:
                raise ValidationError(f"completion receipt {key} must be a non-empty string")
        manifest_hash = value.get("manifest_sha256")
        if manifest_hash is not None and (
            not isinstance(manifest_hash, str) or not manifest_hash
        ):
            raise ValidationError(
                "completion receipt manifest_sha256 must be a non-empty string"
            )
        return cls(copy.deepcopy(value))

    @property
    def status(self) -> str:
        return str(self._payload["status"])

    @property
    def renderer(self) -> str:
        return str(self._payload["renderer"])

    @property
    def schema_version(self) -> str:
        return str(self._payload["schema_version"])

    @property
    def plan(self) -> dict[str, Any]:
        return copy.deepcopy(self._payload["plan"])

    def to_dict(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self._payload))

    def validates(self, response_text: Any, manifest: Any | None = None) -> bool:
        payload = self._payload
        if sha256_json(payload["plan"]) != payload["plan_sha256"]:
            return False
        if not isinstance(response_text, str):
            return False
        if sha256_text(response_text) != payload["response_sha256"]:
            return False
        if "manifest_sha256" not in payload:
            return manifest is None
        if not isinstance(manifest, dict):
            return False
        return sha256_json(manifest) == payload["manifest_sha256"]


@dataclass(frozen=True)
class CompletionResult:
    """Audited successful result, exposed only after the final gate passes."""

    _state: Any = field(repr=False)
    response_text: str
    _receipt: Mapping[str, Any] | None = field(default=None, repr=False)

    @classmethod
    def create(
        cls,
        state: Any,
        response_text: Any,
        receipt: Any | None = None,
    ) -> "CompletionResult":
        if not isinstance(response_text, str):
            raise CompletionError("approved response extractor must return text")
        receipt_payload = None
        if receipt is not None:
            receipt_payload = CompletionReceipt.from_dict(receipt).to_dict()
        return cls(copy.deepcopy(state), response_text, receipt_payload)

    @property
    def state(self) -> Any:
        return copy.deepcopy(self._state)

    @property
    def receipt(self) -> dict[str, Any] | None:
        if self._receipt is None:
            return None
        return copy.deepcopy(dict(self._receipt))


PrepareCallback = Callable[[Any, dict[str, Any]], Any]
AuditCallback = Callable[[Any, dict[str, Any]], AuditResult]
RenderCallback = Callable[[Any, dict[str, Any]], Any]
AssembleCallback = Callable[[Any, dict[str, Any], Any], Any]
ExtractResponseCallback = Callable[[Any], str]
ExtractReceiptCallback = Callable[[Any], dict[str, Any] | None]


@dataclass(frozen=True)
class GuardedCompletion:
    """Order domain callbacks and stop before rendering or exposure on failure."""

    prepare: PrepareCallback
    pre_render_audit: AuditCallback
    render: RenderCallback
    assemble: AssembleCallback
    final_audit: AuditCallback
    extract_response: ExtractResponseCallback
    extract_receipt: ExtractReceiptCallback | None = None
    pre_failure_prefix: str = "pre-render audit failed: "
    final_failure_prefix: str = "final audit failed: "

    @staticmethod
    def _require_audit_result(value: Any, stage: str) -> AuditResult:
        if not isinstance(value, AuditResult):
            raise CompletionError(f"{stage} callback must return AuditResult")
        return value

    def run(self, initial_state: Any, plan: Any) -> CompletionResult:
        if not isinstance(plan, dict):
            raise CompletionError("structured completion plan must be an object")
        isolated_state = copy.deepcopy(initial_state)
        isolated_plan = copy.deepcopy(plan)

        prepared = self.prepare(isolated_state, isolated_plan)
        pre_result = self._require_audit_result(
            self.pre_render_audit(prepared, isolated_plan), "pre-render audit"
        )
        if not pre_result.passed:
            raise CompletionError(
                self.pre_failure_prefix + "; ".join(pre_result.to_v01_strings())
            )

        rendered = self.render(prepared, isolated_plan)
        assembled = self.assemble(prepared, isolated_plan, rendered)
        final_result = self._require_audit_result(
            self.final_audit(assembled, isolated_plan), "final audit"
        )
        if not final_result.passed:
            raise CompletionError(
                self.final_failure_prefix + "; ".join(final_result.to_v01_strings())
            )

        response_text = self.extract_response(assembled)
        receipt = self.extract_receipt(assembled) if self.extract_receipt else None
        return CompletionResult.create(assembled, response_text, receipt)
