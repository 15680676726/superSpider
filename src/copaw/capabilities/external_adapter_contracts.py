# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, Field

ProtocolSurfaceKind = Literal[
    "native_mcp",
    "app_server",
    "event_stream",
    "thread_turn_control",
    "runtime_provider",
    "api",
    "sdk",
    "cli_runtime",
    "unknown",
]
TransportKind = Literal["mcp", "http", "sdk"]
ProviderInjectionMode = Literal[
    "environment",
    "argument",
    "config_file_patch",
    "startup_wrapper",
    "none",
]
VerifiedCapabilityStage = Literal[
    "unverified",
    "installed",
    "runtime_operable",
    "adapter_probe_passed",
    "primary_action_verified",
]
ProviderResolutionStatus = Literal["pending", "resolved", "failed", "not_required"]
CompatibilityStatus = Literal[
    "unknown",
    "compatible_native",
    "compatible_via_bridge",
    "blocked_missing_dependency",
    "blocked_missing_provider_contract",
    "blocked_unsupported_host",
    "blocked_contract_violation",
]
ADAPTER_ATTRIBUTION_SCALAR_FIELDS = (
    "protocol_surface_kind",
    "transport_kind",
    "compiled_adapter_id",
    "selected_adapter_action_id",
)
ADAPTER_ATTRIBUTION_LIST_FIELDS = (
    "compiled_action_ids",
    "adapter_blockers",
)


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(values: object | None) -> list[str]:
    if isinstance(values, str):
        items: Sequence[object] = [values]
    elif isinstance(values, Sequence):
        items = values
    else:
        items = []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _string(item)
        if text is None:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(text)
    return normalized


def _int_value(value: object | None, *, default: int) -> int:
    if isinstance(value, bool) or value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = _string(value)
    if text is None:
        return default
    try:
        return int(text)
    except ValueError:
        return default


def normalize_provider_injection_mode(
    value: object | None,
) -> ProviderInjectionMode | None:
    normalized = (_string(value) or "").lower().replace("-", "_").replace(" ", "_")
    if normalized in {
        "environment",
        "argument",
        "config_file_patch",
        "startup_wrapper",
        "none",
    }:
        return normalized  # type: ignore[return-value]
    return None


def normalize_verified_stage(
    value: object | None,
) -> VerifiedCapabilityStage | None:
    normalized = (_string(value) or "").lower()
    if normalized in {
        "unverified",
        "installed",
        "runtime_operable",
        "adapter_probe_passed",
        "primary_action_verified",
    }:
        return normalized  # type: ignore[return-value]
    return None


def normalize_provider_resolution_status(
    value: object | None,
) -> ProviderResolutionStatus | None:
    normalized = (_string(value) or "").lower()
    if normalized in {"pending", "resolved", "failed", "not_required"}:
        return normalized  # type: ignore[return-value]
    return None


def normalize_compatibility_status(
    value: object | None,
) -> CompatibilityStatus | None:
    normalized = (_string(value) or "").lower()
    if normalized in {
        "unknown",
        "compatible_native",
        "compatible_via_bridge",
        "blocked_missing_dependency",
        "blocked_missing_provider_contract",
        "blocked_unsupported_host",
        "blocked_contract_violation",
    }:
        return normalized  # type: ignore[return-value]
    return None


class ExternalProtocolSurface(BaseModel):
    protocol_surface_kind: ProtocolSurfaceKind = "unknown"
    transport_kind: TransportKind | None = None
    call_surface_ref: str | None = None
    schema_ref: str | None = None
    formal_adapter_eligible: bool = False
    blockers: list[str] = Field(default_factory=list)
    hints: dict[str, Any] = Field(default_factory=dict)


class CompiledAdapterAction(BaseModel):
    action_id: str
    summary: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    transport_action_ref: str


class CompiledAdapterContract(BaseModel):
    compiled_adapter_id: str
    transport_kind: TransportKind
    call_surface_ref: str
    actions: list[CompiledAdapterAction] = Field(default_factory=list)
    promotion_blockers: list[str] = Field(default_factory=list)


class DonorExecutionEnvelope(BaseModel):
    startup_timeout_sec: int = 30
    action_timeout_sec: int = 120
    idle_timeout_sec: int = 30
    heartbeat_interval_sec: int = 10
    cancel_grace_sec: int = 5
    kill_grace_sec: int = 3
    max_retries: int = 0
    retry_backoff_policy: str = "none"
    output_size_limit: int = 65_536
    probe_kind: str = "none"
    probe_timeout_sec: int = 10


class HostCompatibilityRequirements(BaseModel):
    supported_os: list[str] = Field(default_factory=list)
    supported_architectures: list[str] = Field(default_factory=list)
    required_runtimes: list[str] = Field(default_factory=list)
    package_manager: str | None = None
    required_provider_contract_kind: str | None = None
    required_surfaces: list[str] = Field(default_factory=list)
    required_env_keys: list[str] = Field(default_factory=list)
    config_location_expectations: list[str] = Field(default_factory=list)
    workspace_policy: str | None = None
    startup_expectations: list[str] = Field(default_factory=list)


def _app_server_surface_candidate(
    payload: Mapping[str, Any],
) -> ExternalProtocolSurface | None:
    app_server_ref = _string(payload.get("app_server_ref")) or _string(
        payload.get("codex_app_server_ref"),
    )
    if app_server_ref is None:
        return None
    app_server_actions = _action_entries(
        payload.get("app_server_actions") or payload.get("thread_turn_actions"),
    )
    thread_turn_control_supported = bool(payload.get("thread_turn_control_supported"))
    event_stream_supported = bool(payload.get("event_stream_supported"))
    blockers: list[str] = []
    if not app_server_actions:
        blockers.append("no-typed-action-surface")
    if not thread_turn_control_supported:
        blockers.append("missing-thread-turn-control")
    if not event_stream_supported:
        blockers.append("missing-event-stream")
    eligible = bool(app_server_actions) and thread_turn_control_supported and event_stream_supported
    return ExternalProtocolSurface(
        protocol_surface_kind="app_server",
        transport_kind="sdk",
        call_surface_ref=app_server_ref,
        schema_ref=_string(payload.get("app_server_schema_ref")),
        formal_adapter_eligible=eligible,
        blockers=blockers,
        hints={
            "actions": app_server_actions,
            "event_return_path": "event_stream" if event_stream_supported else None,
            "lifecycle_contract_kind": (
                "thread_turn_control" if thread_turn_control_supported else None
            ),
            "runtime_provider_contract_kind": (
                _string(payload.get("runtime_provider_contract_kind"))
                or "runtime_provider"
            ),
        },
    )


def _action_entries(value: object | None) -> list[dict[str, Any]]:
    items: Sequence[object]
    if isinstance(value, list):
        items = value
    elif isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray, Mapping),
    ):
        items = value
    else:
        items = []
    normalized: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, Mapping):
            normalized.append(dict(item))
    return normalized


def _mcp_surface_candidate(
    payload: Mapping[str, Any],
) -> ExternalProtocolSurface | None:
    mcp_server_ref = _string(payload.get("mcp_server_ref"))
    if mcp_server_ref is None:
        return None
    mcp_tools = _action_entries(payload.get("mcp_tools"))
    eligible = bool(mcp_tools)
    blockers: list[str] = []
    if not eligible:
        blockers.append("no-typed-action-surface")
    return ExternalProtocolSurface(
        protocol_surface_kind="native_mcp",
        transport_kind="mcp",
        call_surface_ref=mcp_server_ref,
        formal_adapter_eligible=eligible,
        blockers=blockers,
        hints={"actions": mcp_tools},
    )


def _api_surface_candidate(
    payload: Mapping[str, Any],
) -> ExternalProtocolSurface | None:
    api_base_url = _string(payload.get("api_base_url")) or _string(
        payload.get("openapi_url"),
    )
    if api_base_url is None:
        return None
    api_actions = _action_entries(payload.get("api_actions") or payload.get("openapi_actions"))
    blockers: list[str] = []
    eligible = bool(api_actions)
    if not eligible:
        blockers.append("no-typed-action-surface")
    return ExternalProtocolSurface(
        protocol_surface_kind="api",
        transport_kind="http",
        call_surface_ref=api_base_url,
        schema_ref=_string(payload.get("openapi_url")),
        formal_adapter_eligible=eligible,
        blockers=blockers,
        hints={"actions": api_actions},
    )


def _sdk_surface_candidate(
    payload: Mapping[str, Any],
) -> ExternalProtocolSurface | None:
    sdk_entry_ref = _string(payload.get("sdk_entry_ref"))
    if sdk_entry_ref is None:
        return None
    sdk_actions = _action_entries(payload.get("sdk_actions"))
    blockers: list[str] = []
    eligible = bool(sdk_actions)
    if not eligible:
        blockers.append("no-typed-action-surface")
    return ExternalProtocolSurface(
        protocol_surface_kind="sdk",
        transport_kind="sdk",
        call_surface_ref=sdk_entry_ref,
        formal_adapter_eligible=eligible,
        blockers=blockers,
        hints={"actions": sdk_actions},
    )


def classify_external_protocol_surface(
    *,
    metadata: Mapping[str, Any] | None,
) -> ExternalProtocolSurface:
    payload = dict(metadata or {})
    candidates = [
        _mcp_surface_candidate(payload),
        _api_surface_candidate(payload),
        _app_server_surface_candidate(payload),
        _sdk_surface_candidate(payload),
    ]
    for candidate in candidates:
        if candidate is not None and candidate.formal_adapter_eligible:
            return candidate
    for candidate in candidates:
        if candidate is not None:
            return candidate

    if _string(payload.get("execute_command")) is not None:
        return ExternalProtocolSurface(
            protocol_surface_kind="cli_runtime",
            formal_adapter_eligible=False,
            blockers=["no-stable-callable-surface"],
        )

    return ExternalProtocolSurface(
        protocol_surface_kind="unknown",
        formal_adapter_eligible=False,
        blockers=["no-callable-surface-detected"],
    )


def protocol_surface_metadata(
    surface: ExternalProtocolSurface,
) -> dict[str, Any]:
    return {
        "protocol_surface_kind": surface.protocol_surface_kind,
        "transport_kind": surface.transport_kind,
        "call_surface_ref": surface.call_surface_ref,
        "schema_ref": surface.schema_ref,
        "formal_adapter_eligible": surface.formal_adapter_eligible,
        "adapter_blockers": _string_list(surface.blockers),
        "protocol_hints": dict(surface.hints),
    }


def protocol_surface_from_metadata(
    metadata: Mapping[str, Any] | None,
) -> ExternalProtocolSurface | None:
    payload = dict(metadata or {})
    protocol_surface_kind = _string(payload.get("protocol_surface_kind"))
    if protocol_surface_kind is None:
        return None
    transport_kind = _string(payload.get("transport_kind"))
    if transport_kind not in {"mcp", "http", "sdk"}:
        transport_kind = None
    return ExternalProtocolSurface(
        protocol_surface_kind=protocol_surface_kind,  # type: ignore[arg-type]
        transport_kind=transport_kind,  # type: ignore[arg-type]
        call_surface_ref=_string(payload.get("call_surface_ref")),
        schema_ref=_string(payload.get("schema_ref")),
        formal_adapter_eligible=bool(payload.get("formal_adapter_eligible")),
        blockers=_string_list(payload.get("adapter_blockers")),
        hints=dict(payload.get("protocol_hints") or {}),
    )


def donor_execution_envelope_from_metadata(
    metadata: Mapping[str, Any] | None,
) -> DonorExecutionEnvelope | None:
    payload = dict(metadata or {})
    raw = payload.get("execution_envelope")
    if isinstance(raw, Mapping):
        payload = dict(raw)
    elif raw is not None:
        return None
    if not payload:
        return None
    return DonorExecutionEnvelope(
        startup_timeout_sec=_int_value(payload.get("startup_timeout_sec"), default=30),
        action_timeout_sec=_int_value(payload.get("action_timeout_sec"), default=120),
        idle_timeout_sec=_int_value(payload.get("idle_timeout_sec"), default=30),
        heartbeat_interval_sec=_int_value(
            payload.get("heartbeat_interval_sec"),
            default=10,
        ),
        cancel_grace_sec=_int_value(payload.get("cancel_grace_sec"), default=5),
        kill_grace_sec=_int_value(payload.get("kill_grace_sec"), default=3),
        max_retries=_int_value(payload.get("max_retries"), default=0),
        retry_backoff_policy=_string(payload.get("retry_backoff_policy")) or "none",
        output_size_limit=_int_value(payload.get("output_size_limit"), default=65_536),
        probe_kind=_string(payload.get("probe_kind")) or "none",
        probe_timeout_sec=_int_value(payload.get("probe_timeout_sec"), default=10),
    )


def donor_execution_envelope_metadata(
    envelope: DonorExecutionEnvelope | Mapping[str, Any] | None,
) -> dict[str, Any]:
    if isinstance(envelope, DonorExecutionEnvelope):
        return envelope.model_dump(mode="json")
    normalized = donor_execution_envelope_from_metadata(
        {"execution_envelope": dict(envelope)}
        if isinstance(envelope, Mapping)
        else None,
    )
    return normalized.model_dump(mode="json") if normalized is not None else {}


def host_compatibility_requirements_from_metadata(
    metadata: Mapping[str, Any] | None,
) -> HostCompatibilityRequirements | None:
    payload = dict(metadata or {})
    raw = payload.get("host_compatibility_requirements")
    if isinstance(raw, Mapping):
        payload = dict(raw)
    elif raw is not None:
        return None
    if not payload:
        return None
    return HostCompatibilityRequirements(
        supported_os=_string_list(payload.get("supported_os")),
        supported_architectures=_string_list(payload.get("supported_architectures")),
        required_runtimes=_string_list(payload.get("required_runtimes")),
        package_manager=_string(payload.get("package_manager")),
        required_provider_contract_kind=_string(
            payload.get("required_provider_contract_kind"),
        ),
        required_surfaces=_string_list(payload.get("required_surfaces")),
        required_env_keys=_string_list(payload.get("required_env_keys")),
        config_location_expectations=_string_list(
            payload.get("config_location_expectations"),
        ),
        workspace_policy=_string(payload.get("workspace_policy")),
        startup_expectations=_string_list(payload.get("startup_expectations")),
    )


def host_compatibility_requirements_metadata(
    requirements: HostCompatibilityRequirements | Mapping[str, Any] | None,
) -> dict[str, Any]:
    if isinstance(requirements, HostCompatibilityRequirements):
        return requirements.model_dump(mode="json")
    normalized = host_compatibility_requirements_from_metadata(
        {"host_compatibility_requirements": dict(requirements)}
        if isinstance(requirements, Mapping)
        else None,
    )
    return normalized.model_dump(mode="json") if normalized is not None else {}


def donor_execution_contract_metadata(
    metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    payload = dict(metadata or {})
    normalized: dict[str, Any] = {}
    provider_injection_mode = normalize_provider_injection_mode(
        payload.get("provider_injection_mode"),
    )
    if provider_injection_mode is not None:
        normalized["provider_injection_mode"] = provider_injection_mode
    execution_envelope = donor_execution_envelope_from_metadata(payload)
    if execution_envelope is not None:
        normalized["execution_envelope"] = execution_envelope.model_dump(mode="json")
    host_compatibility_requirements = host_compatibility_requirements_from_metadata(
        payload,
    )
    if host_compatibility_requirements is not None:
        normalized["host_compatibility_requirements"] = (
            host_compatibility_requirements.model_dump(mode="json")
        )
    verified_stage = normalize_verified_stage(payload.get("verified_stage"))
    if verified_stage is not None:
        normalized["verified_stage"] = verified_stage
    provider_resolution_status = normalize_provider_resolution_status(
        payload.get("provider_resolution_status"),
    )
    if provider_resolution_status is not None:
        normalized["provider_resolution_status"] = provider_resolution_status
    compatibility_status = normalize_compatibility_status(
        payload.get("compatibility_status"),
    )
    if compatibility_status is not None:
        normalized["compatibility_status"] = compatibility_status
    return normalized


def adapter_attribution_metadata(
    metadata: Mapping[str, Any] | None,
) -> dict[str, Any]:
    payload = dict(metadata or {})
    normalized: dict[str, Any] = {}
    protocol_surface_kind = _string(payload.get("protocol_surface_kind"))
    if protocol_surface_kind in {
        "native_mcp",
        "app_server",
        "event_stream",
        "thread_turn_control",
        "runtime_provider",
        "api",
        "sdk",
        "cli_runtime",
        "unknown",
    }:
        normalized["protocol_surface_kind"] = protocol_surface_kind
    transport_kind = _string(payload.get("transport_kind"))
    if transport_kind in {"mcp", "http", "sdk"}:
        normalized["transport_kind"] = transport_kind
    compiled_adapter_id = _string(payload.get("compiled_adapter_id"))
    if compiled_adapter_id is not None:
        normalized["compiled_adapter_id"] = compiled_adapter_id
    selected_adapter_action_id = _string(payload.get("selected_adapter_action_id"))
    if selected_adapter_action_id is not None:
        normalized["selected_adapter_action_id"] = selected_adapter_action_id
    compiled_action_ids = _string_list(payload.get("compiled_action_ids"))
    if compiled_action_ids:
        normalized["compiled_action_ids"] = compiled_action_ids
    adapter_blockers = _string_list(
        payload.get("adapter_blockers") or payload.get("promotion_blockers"),
    )
    if adapter_blockers:
        normalized["adapter_blockers"] = adapter_blockers
    return normalized


def merge_adapter_attribution_metadata(
    *payloads: Mapping[str, Any] | None,
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for payload in payloads:
        if not isinstance(payload, Mapping):
            continue
        merged.update(dict(payload))
        merged.update(adapter_attribution_metadata(payload))
        merged.update(donor_execution_contract_metadata(payload))
    return merged


ExecutorProtocolSurface = ExternalProtocolSurface
CompiledExecutorContract = CompiledAdapterContract


def classify_executor_protocol_surface(
    metadata: Mapping[str, Any] | None = None,
) -> ExternalProtocolSurface:
    return classify_external_protocol_surface(metadata=metadata)


def derive_executor_surface(
    metadata: Mapping[str, Any] | None = None,
) -> ExternalProtocolSurface:
    return classify_external_protocol_surface(metadata=metadata)


executor_execution_contract_metadata = donor_execution_contract_metadata
executor_execution_envelope_from_metadata = donor_execution_envelope_from_metadata
executor_execution_envelope_metadata = donor_execution_envelope_metadata


__all__ = [
    "ADAPTER_ATTRIBUTION_LIST_FIELDS",
    "ADAPTER_ATTRIBUTION_SCALAR_FIELDS",
    "CompiledAdapterAction",
    "CompiledAdapterContract",
    "CompiledExecutorContract",
    "CompatibilityStatus",
    "DonorExecutionEnvelope",
    "ExecutorProtocolSurface",
    "ExternalProtocolSurface",
    "HostCompatibilityRequirements",
    "ProviderInjectionMode",
    "ProviderResolutionStatus",
    "VerifiedCapabilityStage",
    "adapter_attribution_metadata",
    "classify_external_protocol_surface",
    "classify_executor_protocol_surface",
    "derive_executor_surface",
    "donor_execution_contract_metadata",
    "donor_execution_envelope_from_metadata",
    "donor_execution_envelope_metadata",
    "executor_execution_contract_metadata",
    "executor_execution_envelope_from_metadata",
    "executor_execution_envelope_metadata",
    "host_compatibility_requirements_from_metadata",
    "host_compatibility_requirements_metadata",
    "merge_adapter_attribution_metadata",
    "normalize_compatibility_status",
    "normalize_provider_injection_mode",
    "normalize_provider_resolution_status",
    "normalize_verified_stage",
    "protocol_surface_from_metadata",
    "protocol_surface_metadata",
]
