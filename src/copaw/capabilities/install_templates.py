# -*- coding: utf-8 -*-
"""Unified capability-market install template surfaces for V5."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..adapters.desktop import (
    DesktopAutomationError,
    DesktopMCPTemplate,
    WindowsDesktopHost,
    list_desktop_mcp_templates,
)
from ..agents.tools.browser_control import (
    browser_use,
    get_browser_runtime_snapshot,
    get_browser_support_snapshot,
)
from .browser_runtime import BrowserRuntimeService, BrowserSessionStartOptions


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _utc_now().isoformat()


def _tool_response_text(response: object) -> str:
    content = getattr(response, "content", None)
    if not isinstance(content, list) or not content:
        return ""
    block = content[0]
    if isinstance(block, dict):
        return str(block.get("text") or "")
    return str(getattr(block, "text", "") or "")


def _parse_tool_response_json(response: object) -> dict[str, Any]:
    text = _tool_response_text(response)
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"ok": False, "raw_text": text}
    return payload if isinstance(payload, dict) else {"ok": False, "raw_text": text}


def _list_installed_mcp_clients(capability_service: object | None) -> dict[str, bool]:
    if capability_service is None:
        return {}
    lister = getattr(capability_service, "list_mcp_client_infos", None)
    if not callable(lister):
        return {}
    try:
        payload = lister()
    except Exception:
        return {}
    installed: dict[str, bool] = {}
    if not isinstance(payload, list):
        return installed
    for item in payload:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if key:
            installed[key] = bool(item.get("enabled"))
    return installed


def _get_capability_mount(
    capability_service: object | None,
    capability_id: str,
) -> object | None:
    if capability_service is None:
        return None
    getter = getattr(capability_service, "get_capability", None)
    if not callable(getter):
        return None
    try:
        return getter(capability_id)
    except Exception:
        return None


def _mount_enabled(capability_service: object | None, capability_id: str) -> bool | None:
    mount = _get_capability_mount(capability_service, capability_id)
    if mount is None:
        return None
    return bool(getattr(mount, "enabled", False))


def _count_pending_decisions(
    decision_request_repository: object | None,
    *tokens: str,
) -> int:
    if decision_request_repository is None:
        return 0
    lister = getattr(decision_request_repository, "list_decision_requests", None)
    if not callable(lister):
        return 0
    try:
        payload = lister()
    except Exception:
        return 0
    normalized_tokens = [token.strip().lower() for token in tokens if token.strip()]
    pending = 0
    for decision in payload or []:
        status = str(getattr(decision, "status", "") or "").strip().lower()
        if status not in {"open", "reviewing"}:
            continue
        summary = str(getattr(decision, "summary", "") or "").lower()
        if normalized_tokens and not any(token in summary for token in normalized_tokens):
            continue
        pending += 1
    return pending


def _find_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def _desktop_pywin32_ready() -> bool:
    return all(
        _find_module(module_name)
        for module_name in ("win32gui", "win32api", "win32con", "win32process")
    )


class ExecutionErrorDetail(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    code: str
    summary: str
    detail: str = ""
    retryable: bool = False
    source: str = ""


class InstallTemplateConfigField(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    key: str
    label: str
    field_type: str = "string"
    required: bool = False
    secret: bool = False
    description: str = ""
    default: Any = None
    choices: list[str] = Field(default_factory=list)


class InstallTemplateConfigSchema(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    scope: Literal["install", "runtime", "none"] = "none"
    fields: list[InstallTemplateConfigField] = Field(default_factory=list)


class InstallTemplateLifecycleAction(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    action: str
    label: str
    summary: str = ""
    available: bool = True
    risk_level: str = "auto"


class InstallTemplateManifest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    template_id: str
    version: str = "builtin-v1"
    install_kind: str
    source_kind: str
    capability_ids: list[str] = Field(default_factory=list)
    supported_platforms: list[str] = Field(default_factory=list)
    environment_requirements: list[str] = Field(default_factory=list)
    evidence_contract: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class InstallTemplateHostPolicy(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    host_kind: str
    expected_platform: str
    requires_interactive_session: bool = False
    supported: bool = False
    ready: bool = False
    reason: str = ""


class InstallTemplateExecutionStrategy(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    risk_level: str
    admission_mode: str
    allowlist_scope: str
    approval_forwarding_supported: bool = True
    pending_approval_count: int = 0
    target_capability_ids: list[str] = Field(default_factory=list)
    host_policy: InstallTemplateHostPolicy
    routes: dict[str, str] = Field(default_factory=dict)


class InstallTemplateDoctorCheck(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    key: str
    label: str
    status: Literal["pass", "warn", "fail", "info"] = "info"
    message: str = ""
    detail: str = ""


class InstallTemplateDoctorReport(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    template_id: str
    status: Literal["ready", "degraded", "blocked"] = "blocked"
    summary: str = ""
    checked_at: str = Field(default_factory=_iso_now)
    checks: list[InstallTemplateDoctorCheck] = Field(default_factory=list)
    host_policy: InstallTemplateHostPolicy
    runtime: dict[str, Any] = Field(default_factory=dict)
    support: dict[str, Any] = Field(default_factory=dict)
    error: ExecutionErrorDetail | None = None


class InstallTemplateExampleRunRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    template_id: str
    status: Literal["success", "error"] = "error"
    started_at: str
    finished_at: str
    summary: str = ""
    operations: list[str] = Field(default_factory=list)
    runtime: dict[str, Any] = Field(default_factory=dict)
    support: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    error: ExecutionErrorDetail | None = None


def normalize_install_template_config(
    schema: InstallTemplateConfigSchema | None,
    config: dict[str, Any] | None,
) -> dict[str, Any]:
    if schema is None or not list(schema.fields or []):
        return {}
    payload = dict(config or {})
    field_map = {field.key: field for field in list(schema.fields or [])}
    unknown_keys = sorted(key for key in payload.keys() if key not in field_map)
    if unknown_keys:
        raise ValueError(
            "Unknown install template config fields: " + ", ".join(unknown_keys)
        )
    normalized: dict[str, Any] = {}
    for field in list(schema.fields or []):
        value = payload[field.key] if field.key in payload else field.default
        normalized[field.key] = _normalize_install_template_config_value(field, value)
        if field.required and normalized[field.key] in (None, "", []):
            raise ValueError(f"Install template field '{field.key}' is required")
    return normalized


def _normalize_install_template_config_value(
    field: InstallTemplateConfigField,
    value: Any,
) -> Any:
    field_type = str(field.field_type or "string").strip().lower()
    if field_type == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off", ""}:
                return False
        if value is None:
            return False
        return bool(value)
    if field_type == "string[]":
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, tuple):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            trimmed = value.strip()
            if not trimmed:
                return []
            if trimmed.startswith("["):
                try:
                    parsed = json.loads(trimmed)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            return [item.strip() for item in trimmed.split(",") if item.strip()]
        return [str(value).strip()] if str(value).strip() else []
    if field_type == "choice":
        text = "" if value is None else str(value).strip()
        if text and field.choices and text not in set(field.choices):
            raise ValueError(
                f"Install template field '{field.key}' must be one of: "
                + ", ".join(field.choices)
            )
        return text
    if field_type == "number":
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Install template field '{field.key}' must be a number"
            ) from exc
    if value is None:
        return ""
    return str(value)


class CapabilityInstallTemplateSpec(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str
    name: str
    description: str = ""
    install_kind: str = "mcp-template"
    source_kind: str = "mcp"
    platform: str = ""
    default_client_key: str | None = None
    default_capability_id: str | None = None
    capability_tags: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    risk_level: str = "guarded"
    capability_budget_cost: int = 1
    default_assignment_policy: str = "selected-agents-only"
    installed: bool = False
    enabled: bool | None = None
    ready: bool = False
    manifest: InstallTemplateManifest | None = None
    config_schema: InstallTemplateConfigSchema | None = None
    lifecycle: list[InstallTemplateLifecycleAction] = Field(default_factory=list)
    execution_strategy: InstallTemplateExecutionStrategy | None = None
    host_policy: InstallTemplateHostPolicy | None = None
    runtime: dict[str, Any] = Field(default_factory=dict)
    support: dict[str, Any] = Field(default_factory=dict)
    routes: dict[str, str] = Field(default_factory=dict)


def _desktop_host_policy() -> InstallTemplateHostPolicy:
    supported = sys.platform == "win32" and _desktop_pywin32_ready()
    reason = ""
    if sys.platform != "win32":
        reason = "desktop-windows adapter requires a Windows host"
    elif not _desktop_pywin32_ready():
        reason = "Win32 desktop dependencies are not available on this host"
    return InstallTemplateHostPolicy(
        host_kind="local-desktop",
        expected_platform="windows",
        requires_interactive_session=True,
        supported=supported,
        ready=supported,
        reason=reason,
    )


def _browser_host_policy(playwright_ready: bool) -> InstallTemplateHostPolicy:
    return InstallTemplateHostPolicy(
        host_kind="local-browser-runtime",
        expected_platform="cross-platform",
        requires_interactive_session=False,
        supported=playwright_ready,
        ready=playwright_ready,
        reason="" if playwright_ready else "Playwright runtime is not ready on this host",
    )


def _desktop_manifest(template: DesktopMCPTemplate) -> InstallTemplateManifest:
    return InstallTemplateManifest(
        template_id=template.template_id,
        version="builtin-v1",
        install_kind="mcp-template",
        source_kind="mcp",
        capability_ids=[f"mcp:{template.default_client_key}"],
        supported_platforms=[template.platform],
        environment_requirements=["desktop", "interactive-session"],
        evidence_contract=["desktop-action", "desktop-window", "desktop-screenshot"],
        tags=list(template.capability_tags),
    )


def _browser_manifest() -> InstallTemplateManifest:
    return InstallTemplateManifest(
        template_id="browser-local",
        version="builtin-v1",
        install_kind="builtin-runtime",
        source_kind="tool",
        capability_ids=["tool:browser_use"],
        supported_platforms=["windows", "linux", "darwin"],
        environment_requirements=["browser", "network"],
        evidence_contract=["browser-action", "browser-artifact"],
        tags=["browser", "playwright", "runtime"],
    )


def _builtin_capability_state(
    capability_service: object | None,
    capability_id: str,
) -> tuple[bool, bool | None]:
    mount = _get_capability_mount(capability_service, capability_id)
    if mount is None:
        return False, None
    return True, bool(getattr(mount, "enabled", False))


def _windows_cooperative_host_policy(
    *,
    host_kind: str,
    reason: str = "",
) -> InstallTemplateHostPolicy:
    supported = sys.platform == "win32"
    return InstallTemplateHostPolicy(
        host_kind=host_kind,
        expected_platform="windows",
        requires_interactive_session=True,
        supported=supported,
        ready=supported,
        reason=reason if reason else ("" if supported else "Windows host is required"),
    )


def _browser_companion_manifest() -> InstallTemplateManifest:
    return InstallTemplateManifest(
        template_id="browser-companion",
        version="builtin-v1",
        install_kind="builtin-runtime",
        source_kind="system",
        capability_ids=["system:browser_companion_runtime"],
        supported_platforms=["windows", "linux", "darwin"],
        environment_requirements=["browser", "environment", "session"],
        evidence_contract=["browser-companion", "runtime-event", "environment-session"],
        tags=["browser", "companion", "cooperative", "phase2"],
    )


def _document_bridge_manifest() -> InstallTemplateManifest:
    return InstallTemplateManifest(
        template_id="document-office-bridge",
        version="builtin-v1",
        install_kind="builtin-runtime",
        source_kind="system",
        capability_ids=["system:document_bridge_runtime"],
        supported_platforms=["windows"],
        environment_requirements=["document", "workspace", "environment", "session"],
        evidence_contract=["document-bridge", "runtime-event", "environment-session"],
        tags=["document", "office", "bridge", "cooperative", "phase2"],
    )


def _host_watchers_manifest() -> InstallTemplateManifest:
    return InstallTemplateManifest(
        template_id="host-watchers",
        version="builtin-v1",
        install_kind="builtin-runtime",
        source_kind="system",
        capability_ids=["system:host_watchers_runtime"],
        supported_platforms=["windows"],
        environment_requirements=["environment", "session", "runtime-events"],
        evidence_contract=["host-watcher", "runtime-event", "environment-session"],
        tags=["watchers", "downloads", "notifications", "cooperative", "phase2"],
    )


def _windows_app_adapters_manifest() -> InstallTemplateManifest:
    return InstallTemplateManifest(
        template_id="windows-app-adapters",
        version="builtin-v1",
        install_kind="builtin-runtime",
        source_kind="system",
        capability_ids=["system:windows_app_adapter_runtime"],
        supported_platforms=["windows"],
        environment_requirements=["desktop", "environment", "session"],
        evidence_contract=["windows-app-adapter", "runtime-event", "environment-session"],
        tags=["windows", "desktop", "adapters", "cooperative", "phase2"],
    )


_COOPERATIVE_READY_STATUSES = {
    "active",
    "attached",
    "available",
    "connected",
    "healthy",
    "ready",
    "running",
}

_COOPERATIVE_TEMPLATE_METADATA_KEYS: dict[str, tuple[str, ...]] = {
    "browser-companion": (
        "browser_companion_transport_ref",
        "browser_companion_status",
        "browser_companion_available",
        "provider_session_ref",
    ),
    "document-office-bridge": (
        "document_bridge_ref",
        "document_bridge_status",
        "document_bridge_available",
        "document_bridge_supported_families",
    ),
    "host-watchers": (
        "filesystem_watcher_status",
        "filesystem_watcher_available",
        "download_watcher_status",
        "download_watcher_available",
        "download_policy",
        "notification_watcher_status",
        "notification_watcher_available",
    ),
    "windows-app-adapters": (
        "windows_app_adapter_refs",
        "app_adapter_refs",
        "app_identity",
        "control_channel",
    ),
}


def _metadata_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _string_value(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _bool_value(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return None


def _string_list_value(value: object) -> list[str]:
    if isinstance(value, str):
        normalized = value.strip()
        return [normalized] if normalized else []
    if isinstance(value, (list, tuple, set)):
        items = [str(item).strip() for item in value]
        return [item for item in items if item]
    return []


def _metadata_value_present(value: object) -> bool:
    if isinstance(value, bool):
        return True
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def _status_ready(status: object) -> bool:
    normalized = _string_value(status)
    return bool(normalized and normalized.lower() in _COOPERATIVE_READY_STATUSES)


def _cooperative_template_matches_metadata(
    template_id: str,
    metadata: dict[str, Any],
) -> bool:
    keys = _COOPERATIVE_TEMPLATE_METADATA_KEYS.get(template_id, ())
    return any(_metadata_value_present(metadata.get(key)) for key in keys)


def _cooperative_template_available(
    template_id: str,
    metadata: dict[str, Any],
) -> bool:
    if template_id == "browser-companion":
        available = _bool_value(metadata.get("browser_companion_available"))
        if isinstance(available, bool):
            return available
        return bool(
            _string_value(metadata.get("browser_companion_transport_ref"))
            or _status_ready(metadata.get("browser_companion_status"))
        )
    if template_id == "document-office-bridge":
        available = _bool_value(metadata.get("document_bridge_available"))
        if isinstance(available, bool):
            return available
        return bool(
            _string_value(metadata.get("document_bridge_ref"))
            or _status_ready(metadata.get("document_bridge_status"))
        )
    if template_id == "host-watchers":
        explicit_values = [
            _bool_value(metadata.get("filesystem_watcher_available")),
            _bool_value(metadata.get("download_watcher_available")),
            _bool_value(metadata.get("notification_watcher_available")),
        ]
        if any(value is True for value in explicit_values):
            return True
        return any(
            _status_ready(metadata.get(key))
            for key in (
                "filesystem_watcher_status",
                "download_watcher_status",
                "notification_watcher_status",
            )
        )
    if template_id == "windows-app-adapters":
        return bool(
            _string_list_value(metadata.get("windows_app_adapter_refs"))
            or _string_list_value(metadata.get("app_adapter_refs"))
        )
    return False


def _safe_environment_call(
    environment_service: object | None,
    method_name: str,
    *args: object,
    **kwargs: object,
) -> Any:
    if environment_service is None:
        return None
    method = getattr(environment_service, method_name, None)
    if not callable(method):
        return None
    try:
        return method(*args, **kwargs)
    except Exception:
        return None


def _cooperative_template_runtime_context(
    template_id: str,
    *,
    environment_service: object | None,
    session_mount_id: str | None = None,
    environment_id: str | None = None,
    detail_limit: int = 20,
) -> dict[str, Any]:
    sessions = _safe_environment_call(
        environment_service,
        "list_sessions",
        limit=None,
    )
    environments = _safe_environment_call(
        environment_service,
        "list_environments",
        limit=None,
    )
    session_list = list(sessions or []) if isinstance(sessions, list) else []
    environment_list = (
        list(environments or []) if isinstance(environments, list) else []
    )

    matched_sessions: list[object] = []
    ready_session_count = 0
    for session in session_list:
        metadata = _metadata_dict(getattr(session, "metadata", None))
        if not _cooperative_template_matches_metadata(template_id, metadata):
            continue
        matched_sessions.append(session)
        if _cooperative_template_available(template_id, metadata):
            ready_session_count += 1

    matched_environments: list[object] = []
    ready_environment_count = 0
    for environment in environment_list:
        metadata = _metadata_dict(getattr(environment, "metadata", None))
        if not _cooperative_template_matches_metadata(template_id, metadata):
            continue
        matched_environments.append(environment)
        if _cooperative_template_available(template_id, metadata):
            ready_environment_count += 1

    explicit_session = (
        _safe_environment_call(environment_service, "get_session", session_mount_id)
        if session_mount_id
        else None
    )
    explicit_environment = (
        _safe_environment_call(environment_service, "get_environment", environment_id)
        if environment_id
        else None
    )

    primary_session = explicit_session
    if primary_session is None:
        ready_sessions = [
            session
            for session in matched_sessions
            if _cooperative_template_available(
                template_id,
                _metadata_dict(getattr(session, "metadata", None)),
            )
        ]
        primary_session = ready_sessions[0] if ready_sessions else (
            matched_sessions[0] if matched_sessions else None
        )

    primary_environment = explicit_environment
    if primary_environment is None and primary_session is not None:
        primary_environment = _safe_environment_call(
            environment_service,
            "get_environment",
            str(getattr(primary_session, "environment_id", "") or ""),
        )
    if primary_environment is None:
        ready_environments = [
            environment
            for environment in matched_environments
            if _cooperative_template_available(
                template_id,
                _metadata_dict(getattr(environment, "metadata", None)),
            )
        ]
        primary_environment = ready_environments[0] if ready_environments else (
            matched_environments[0] if matched_environments else None
        )

    if primary_session is None and primary_environment is not None:
        environment_session_id = str(getattr(primary_environment, "id", "") or "")
        linked_sessions = [
            session
            for session in matched_sessions
            if str(getattr(session, "environment_id", "") or "") == environment_session_id
        ]
        if linked_sessions:
            primary_session = linked_sessions[0]

    primary_session_id = (
        str(getattr(primary_session, "id", "") or "") if primary_session is not None else None
    )
    primary_environment_id = (
        str(getattr(primary_environment, "id", "") or "")
        if primary_environment is not None
        else None
    )
    session_detail = (
        _safe_environment_call(
            environment_service,
            "get_session_detail",
            primary_session_id,
            limit=detail_limit,
        )
        if primary_session_id
        else None
    )
    environment_detail = (
        _safe_environment_call(
            environment_service,
            "get_environment_detail",
            primary_environment_id,
            limit=detail_limit,
        )
        if primary_environment_id
        else None
    )
    projection = {}
    if isinstance(session_detail, dict):
        session_projection = session_detail.get("cooperative_adapter_availability")
        if isinstance(session_projection, dict):
            projection = dict(session_projection)
    if not projection and isinstance(environment_detail, dict):
        environment_projection = environment_detail.get("cooperative_adapter_availability")
        if isinstance(environment_projection, dict):
            projection = dict(environment_projection)

    return {
        "runtime_surface_available": environment_service is not None,
        "session_mount_id": primary_session_id,
        "environment_id": primary_environment_id,
        "active_session_count": len(matched_sessions),
        "ready_session_count": ready_session_count,
        "active_environment_count": len(matched_environments),
        "ready_environment_count": ready_environment_count,
        "session_ids": [
            str(getattr(session, "id", "") or "")
            for session in matched_sessions
            if str(getattr(session, "id", "") or "")
        ],
        "environment_ids": [
            str(getattr(environment, "id", "") or "")
            for environment in matched_environments
            if str(getattr(environment, "id", "") or "")
        ],
        "session_detail": session_detail if isinstance(session_detail, dict) else {},
        "environment_detail": (
            environment_detail if isinstance(environment_detail, dict) else {}
        ),
        "projection": projection,
    }


def _cooperative_template_routes(template_id: str) -> dict[str, str]:
    return {
        "detail": f"/api/capability-market/install-templates/{template_id}",
        "install": f"/api/capability-market/install-templates/{template_id}/install",
        "doctor": f"/api/capability-market/install-templates/{template_id}/doctor",
        "example_run": (
            f"/api/capability-market/install-templates/{template_id}/example-run"
        ),
        "runtime_center": "/api/runtime-center/surface",
        "environments": "/api/runtime-center/environments",
        "sessions": "/api/runtime-center/sessions",
    }


def _cooperative_execution_routes() -> dict[str, str]:
    return {
        "decisions": "/api/runtime-center/decisions",
        "agents": "/api/runtime-center/agents",
        "actors": "/api/runtime-center/actors",
        "environments": "/api/runtime-center/environments",
        "sessions": "/api/runtime-center/sessions",
    }


def list_install_templates(
    *,
    capability_service: object | None = None,
    decision_request_repository: object | None = None,
    browser_runtime_service: BrowserRuntimeService | None = None,
    environment_service: object | None = None,
    include_runtime: bool = False,
) -> list[CapabilityInstallTemplateSpec]:
    installed_clients = _list_installed_mcp_clients(capability_service)
    templates: list[CapabilityInstallTemplateSpec] = []
    for template in list_desktop_mcp_templates():
        templates.append(
            _build_desktop_install_template(
                template,
                installed_clients=installed_clients,
                decision_request_repository=decision_request_repository,
                include_runtime=include_runtime,
            ),
        )
    templates.append(
        _build_browser_install_template(
            capability_service=capability_service,
            decision_request_repository=decision_request_repository,
            browser_runtime_service=browser_runtime_service,
            include_runtime=include_runtime,
        ),
    )
    templates.extend(
        [
            _build_browser_companion_install_template(
                capability_service=capability_service,
                decision_request_repository=decision_request_repository,
                browser_runtime_service=browser_runtime_service,
                environment_service=environment_service,
                include_runtime=include_runtime,
            ),
            _build_document_bridge_install_template(
                capability_service=capability_service,
                decision_request_repository=decision_request_repository,
                environment_service=environment_service,
                include_runtime=include_runtime,
            ),
            _build_host_watchers_install_template(
                capability_service=capability_service,
                decision_request_repository=decision_request_repository,
                environment_service=environment_service,
                include_runtime=include_runtime,
            ),
            _build_windows_app_adapters_install_template(
                capability_service=capability_service,
                decision_request_repository=decision_request_repository,
                environment_service=environment_service,
                include_runtime=include_runtime,
            ),
        ],
    )
    return templates


def get_install_template(
    template_id: str,
    *,
    capability_service: object | None = None,
    decision_request_repository: object | None = None,
    browser_runtime_service: BrowserRuntimeService | None = None,
    environment_service: object | None = None,
    include_runtime: bool = True,
) -> CapabilityInstallTemplateSpec | None:
    for template in list_install_templates(
        capability_service=capability_service,
        decision_request_repository=decision_request_repository,
        browser_runtime_service=browser_runtime_service,
        environment_service=environment_service,
        include_runtime=include_runtime,
    ):
        if template.id == template_id:
            return template
    return None


def match_install_template_capability_ids(
    *,
    template_id: str,
    capability_ids: list[str],
) -> bool:
    normalized_targets = {item.strip().lower() for item in capability_ids if item.strip()}
    if not normalized_targets:
        return False
    template = get_install_template(template_id, include_runtime=False)
    if template is None or template.manifest is None:
        return False
    normalized_capabilities = {
        item.strip().lower()
        for item in template.manifest.capability_ids
        if item.strip()
    }
    if normalized_capabilities & normalized_targets:
        return True
    normalized_tags = {
        item.strip().lower()
        for item in template.capability_tags
        if item.strip()
    }
    for capability_id in normalized_targets:
        tokens = {
            token
            for token in capability_id.replace(":", " ").replace("_", " ").split()
            if token
        }
        if tokens & normalized_tags:
            return True
    return False


def build_install_template_doctor(
    template_id: str,
    *,
    capability_service: object | None = None,
    browser_runtime_service: BrowserRuntimeService | None = None,
    environment_service: object | None = None,
) -> InstallTemplateDoctorReport | None:
    if template_id == "desktop-windows":
        return _desktop_doctor(capability_service=capability_service)
    if template_id == "browser-local":
        return _browser_doctor(
            capability_service=capability_service,
            browser_runtime_service=browser_runtime_service,
        )
    if template_id == "browser-companion":
        return _browser_companion_doctor(
            capability_service=capability_service,
            browser_runtime_service=browser_runtime_service,
            environment_service=environment_service,
        )
    if template_id == "document-office-bridge":
        return _document_bridge_doctor(
            capability_service=capability_service,
            environment_service=environment_service,
        )
    if template_id == "host-watchers":
        return _host_watchers_doctor(
            capability_service=capability_service,
            environment_service=environment_service,
        )
    if template_id == "windows-app-adapters":
        return _windows_app_adapters_doctor(
            capability_service=capability_service,
            environment_service=environment_service,
        )
    return None


async def run_install_template_example(
    template_id: str,
    *,
    capability_service: object | None = None,
    browser_runtime_service: BrowserRuntimeService | None = None,
    environment_service: object | None = None,
    config: dict[str, Any] | None = None,
) -> InstallTemplateExampleRunRecord | None:
    if template_id == "desktop-windows":
        return await _desktop_example_run(capability_service=capability_service)
    if template_id == "browser-local":
        return await _browser_example_run(
            capability_service=capability_service,
            browser_runtime_service=browser_runtime_service,
            config=config,
        )
    if template_id == "browser-companion":
        return await _browser_companion_example_run(
            capability_service=capability_service,
            browser_runtime_service=browser_runtime_service,
            environment_service=environment_service,
            config=config,
        )
    if template_id == "document-office-bridge":
        return await _document_bridge_example_run(
            capability_service=capability_service,
            environment_service=environment_service,
            config=config,
        )
    if template_id == "host-watchers":
        return await _host_watchers_example_run(
            capability_service=capability_service,
            environment_service=environment_service,
            config=config,
        )
    if template_id == "windows-app-adapters":
        return await _windows_app_adapters_example_run(
            capability_service=capability_service,
            environment_service=environment_service,
            config=config,
        )
    return None


def _build_desktop_install_template(
    template: DesktopMCPTemplate,
    *,
    installed_clients: dict[str, bool],
    decision_request_repository: object | None = None,
    include_runtime: bool = False,
) -> CapabilityInstallTemplateSpec:
    enabled = installed_clients.get(template.default_client_key)
    installed = enabled is not None
    host_policy = _desktop_host_policy()
    ready = bool(enabled) and host_policy.ready
    manifest = _desktop_manifest(template)
    pending_approvals = _count_pending_decisions(
        decision_request_repository,
        template.template_id,
        template.default_client_key,
        f"mcp:{template.default_client_key}",
    )
    return CapabilityInstallTemplateSpec(
        id=template.template_id,
        name=template.name,
        description=template.description,
        install_kind="mcp-template",
        source_kind="mcp",
        platform=template.platform,
        default_client_key=template.default_client_key,
        default_capability_id=f"mcp:{template.default_client_key}",
        capability_tags=list(template.capability_tags),
        notes=list(template.notes),
        risk_level="guarded",
        capability_budget_cost=1,
        default_assignment_policy="selected-agents-only",
        installed=installed,
        enabled=enabled,
        ready=ready,
        manifest=manifest,
        config_schema=InstallTemplateConfigSchema(
            scope="install",
            fields=[
                InstallTemplateConfigField(
                    key="command",
                    label="Launch command",
                    field_type="string",
                    required=True,
                    default=str(template.client.get("command") or ""),
                    description="Command used to start the local desktop MCP server.",
                ),
                InstallTemplateConfigField(
                    key="args",
                    label="Launch arguments",
                    field_type="string[]",
                    required=True,
                    default=list(template.client.get("args") or []),
                    description="Arguments passed to the desktop MCP server command.",
                ),
                InstallTemplateConfigField(
                    key="enabled",
                    label="Enable after install",
                    field_type="boolean",
                    required=False,
                    default=bool(template.client.get("enabled", True)),
                    description="Whether the MCP client should be enabled immediately.",
                ),
            ],
        ),
        lifecycle=[
            InstallTemplateLifecycleAction(
                action="install",
                label="Install desktop adapter",
                summary="Write the desktop MCP client config and surface it in the unified capability graph.",
                risk_level="guarded",
            ),
            InstallTemplateLifecycleAction(
                action="enable",
                label="Enable installed adapter",
                summary="Enable a disabled existing client without reinstalling it.",
                risk_level="guarded",
            ),
            InstallTemplateLifecycleAction(
                action="doctor",
                label="Run integration doctor",
                summary="Check Windows host readiness, pywin32 availability, and install state.",
                risk_level="auto",
            ),
            InstallTemplateLifecycleAction(
                action="example-run",
                label="Run host smoke",
                summary="Enumerate the current desktop windows through the local host wrapper.",
                risk_level="guarded",
            ),
        ],
        execution_strategy=InstallTemplateExecutionStrategy(
            risk_level="guarded",
            admission_mode="guarded",
            allowlist_scope="per-agent capability governance",
            approval_forwarding_supported=True,
            pending_approval_count=pending_approvals,
            target_capability_ids=manifest.capability_ids,
            host_policy=host_policy,
            routes={
                "decisions": "/api/runtime-center/decisions",
                "agents": "/api/runtime-center/agents",
                "actors": "/api/runtime-center/actors",
            },
        ),
        host_policy=host_policy,
        runtime={},
        support={"pywin32_ready": _desktop_pywin32_ready()} if include_runtime else {},
        routes={
            "detail": f"/api/capability-market/install-templates/{template.template_id}",
            "install": f"/api/capability-market/install-templates/{template.template_id}/install",
            "doctor": f"/api/capability-market/install-templates/{template.template_id}/doctor",
            "example_run": (
                f"/api/capability-market/install-templates/{template.template_id}/example-run"
            ),
        },
    )


def _build_browser_install_template(
    *,
    capability_service: object | None = None,
    decision_request_repository: object | None = None,
    browser_runtime_service: BrowserRuntimeService | None = None,
    include_runtime: bool = False,
) -> CapabilityInstallTemplateSpec:
    support = get_browser_support_snapshot()
    runtime: dict[str, Any] = {}
    enabled = _mount_enabled(capability_service, "tool:browser_use")
    installed = _get_capability_mount(capability_service, "tool:browser_use") is not None
    host_policy = _browser_host_policy(bool(support.get("playwright_ready")))
    ready = bool(enabled) and host_policy.ready
    manifest = _browser_manifest()
    profiles: list[dict[str, Any]] = []
    if include_runtime:
        runtime = (
            browser_runtime_service.runtime_snapshot()
            if browser_runtime_service is not None
            else get_browser_runtime_snapshot()
        )
        profiles = (
            [
                profile.model_dump(mode="json")
                for profile in browser_runtime_service.list_profiles()
            ]
            if browser_runtime_service is not None
            else []
        )
    pending_approvals = _count_pending_decisions(
        decision_request_repository,
        "browser-local",
        "tool:browser_use",
        "browser",
    )
    return CapabilityInstallTemplateSpec(
        id="browser-local",
        name="Local Browser Runtime",
        description=(
            "Productized built-in browser runtime with Playwright-backed local browsing, "
            "runtime introspection, and safe smoke checks."
        ),
        install_kind="builtin-runtime",
        source_kind="tool",
        platform="cross-platform",
        default_client_key=None,
        default_capability_id="tool:browser_use",
        capability_tags=["browser", "playwright", "runtime", "network"],
        notes=[
            "No external MCP installation is required; this surface wraps the built-in browser runtime.",
            "Defaults to a visible local browser window, while still supporting headless background execution when explicitly requested.",
            "Example run starts and stops a safe managed browser only when none is already running.",
        ],
        risk_level="guarded",
        capability_budget_cost=1,
        default_assignment_policy="selected-agents-only",
        installed=installed,
        enabled=enabled,
        ready=ready,
        manifest=manifest,
        config_schema=InstallTemplateConfigSchema(
            scope="runtime",
            fields=[
                InstallTemplateConfigField(
                    key="profile_id",
                    label="Default profile id",
                    field_type="string",
                    required=False,
                    default="browser-local-default",
                    description="Stable profile id used by the capability market and browser session controls.",
                ),
                InstallTemplateConfigField(
                    key="profile_label",
                    label="Profile label",
                    field_type="string",
                    required=False,
                    default="Default browser runtime",
                    description="Human-readable label shown in the browser product surface.",
                ),
                InstallTemplateConfigField(
                    key="entry_url",
                    label="Entry URL",
                    field_type="string",
                    required=False,
                    default="",
                    description="Optional URL to open when a managed browser session starts.",
                ),
                InstallTemplateConfigField(
                    key="headed",
                    label="Visible browser window",
                    field_type="boolean",
                    required=False,
                    default=True,
                    description="Launch the browser in a visible window by default; turn this off only when you explicitly want background headless mode.",
                ),
                InstallTemplateConfigField(
                    key="reuse_running_session",
                    label="Reuse running browser session",
                    field_type="boolean",
                    required=False,
                    default=True,
                    description="Avoid interrupting an already running managed browser runtime.",
                ),
                InstallTemplateConfigField(
                    key="persist_login_state",
                    label="Persist login state",
                    field_type="boolean",
                    required=False,
                    default=True,
                    description="Persist Playwright storage state per saved profile so login checkpoints can be reused.",
                ),
                InstallTemplateConfigField(
                    key="allowed_hosts",
                    label="Allowed hosts",
                    field_type="string[]",
                    required=False,
                    default=[],
                    description="Optional browser host allowlist. When set, navigation outside these hosts is blocked for sessions started from this profile.",
                ),
                InstallTemplateConfigField(
                    key="blocked_hosts",
                    label="Blocked hosts",
                    field_type="string[]",
                    required=False,
                    default=[],
                    description="Optional browser host blocklist. Matching hosts are always blocked for sessions started from this profile.",
                ),
                InstallTemplateConfigField(
                    key="action_timeout_seconds",
                    label="Action timeout seconds",
                    field_type="number",
                    required=False,
                    default=None,
                    description="Optional default timeout for browser actions started from this profile.",
                ),
            ],
        ),
        lifecycle=[
            InstallTemplateLifecycleAction(
                action="enable",
                label="Enable browser runtime",
                summary="Re-enable the built-in browser capability when it has been disabled by governance.",
                risk_level="guarded",
            ),
            InstallTemplateLifecycleAction(
                action="doctor",
                label="Run browser doctor",
                summary="Check Playwright availability, runtime state, and host browser support.",
                risk_level="auto",
            ),
            InstallTemplateLifecycleAction(
                action="example-run",
                label="Run browser smoke",
                summary="Start and stop a safe local browser runtime smoke session.",
                risk_level="guarded",
            ),
        ],
        execution_strategy=InstallTemplateExecutionStrategy(
            risk_level="guarded",
            admission_mode="guarded",
            allowlist_scope="per-agent capability governance",
            approval_forwarding_supported=True,
            pending_approval_count=pending_approvals,
            target_capability_ids=manifest.capability_ids,
            host_policy=host_policy,
            routes={
                "decisions": "/api/runtime-center/decisions",
                "agents": "/api/runtime-center/agents",
                "actors": "/api/runtime-center/actors",
            },
        ),
        host_policy=host_policy,
        runtime=runtime if include_runtime else {},
        support=(
            {
                **support,
                "profile_count": len(profiles),
                "profiles": profiles,
            }
            if include_runtime
            else {}
        ),
        routes={
            "detail": "/api/capability-market/install-templates/browser-local",
            "install": "/api/capability-market/install-templates/browser-local/install",
            "doctor": "/api/capability-market/install-templates/browser-local/doctor",
            "example_run": "/api/capability-market/install-templates/browser-local/example-run",
            "profiles": "/api/capability-market/install-templates/browser-local/profiles",
            "sessions": "/api/capability-market/install-templates/browser-local/sessions",
            "session_start": (
                "/api/capability-market/install-templates/browser-local/sessions/start"
            ),
        },
    )


def _build_browser_companion_install_template(
    *,
    capability_service: object | None = None,
    decision_request_repository: object | None = None,
    browser_runtime_service: BrowserRuntimeService | None = None,
    environment_service: object | None = None,
    include_runtime: bool = False,
) -> CapabilityInstallTemplateSpec:
    installed, enabled = _builtin_capability_state(
        capability_service,
        "system:browser_companion_runtime",
    )
    browser_support = get_browser_support_snapshot()
    host_policy = _browser_host_policy(bool(browser_support.get("playwright_ready")))
    manifest = _browser_companion_manifest()
    runtime_context = _cooperative_template_runtime_context(
        "browser-companion",
        environment_service=environment_service,
    )
    snapshot: dict[str, Any] = {}
    browser_runtime: dict[str, Any] = {}
    if include_runtime and runtime_context["session_mount_id"]:
        snapshot_payload = _safe_environment_call(
            environment_service,
            "browser_companion_snapshot",
            session_mount_id=runtime_context["session_mount_id"],
            environment_id=runtime_context["environment_id"],
        )
        if isinstance(snapshot_payload, dict):
            snapshot = dict(snapshot_payload)
    if (
        include_runtime
        and browser_runtime_service is not None
        and (
            runtime_context["session_mount_id"] is not None
            or runtime_context["environment_id"] is not None
        )
    ):
        browser_runtime = browser_runtime_service.runtime_snapshot(
            environment_id=runtime_context["environment_id"],
            session_mount_id=runtime_context["session_mount_id"],
        )
    ready = bool(enabled) and host_policy.ready
    pending_approvals = _count_pending_decisions(
        decision_request_repository,
        "browser-companion",
        "system:browser_companion_runtime",
        "browser companion",
    )
    return CapabilityInstallTemplateSpec(
        id="browser-companion",
        name="Browser Companion Runtime",
        description=(
            "Productized cooperative browser companion surface that reads canonical "
            "environment/session projections, continuity transport anchors, and "
            "browser runtime state."
        ),
        install_kind="builtin-runtime",
        source_kind="system",
        platform="cross-platform",
        default_client_key=None,
        default_capability_id="system:browser_companion_runtime",
        capability_tags=["browser", "companion", "cooperative", "phase2"],
        notes=[
            "Built on top of canonical EnvironmentService browser/session projections instead of a parallel state cache.",
            "Best used when a managed browser runtime or continuity seat is already mounted and needs cooperative-native execution hints.",
            "Doctor and example-run stay read-only unless a browser runtime service is explicitly provided for inspection.",
        ],
        risk_level="guarded",
        capability_budget_cost=1,
        default_assignment_policy="selected-agents-only",
        installed=installed,
        enabled=enabled,
        ready=ready,
        manifest=manifest,
        config_schema=InstallTemplateConfigSchema(
            scope="runtime",
            fields=[
                InstallTemplateConfigField(
                    key="session_mount_id",
                    label="Session mount id",
                    field_type="string",
                    required=False,
                    default="",
                    description="Optional canonical session mount to inspect for browser companion availability.",
                ),
                InstallTemplateConfigField(
                    key="environment_id",
                    label="Environment id",
                    field_type="string",
                    required=False,
                    default="",
                    description="Optional environment mount id used to resolve browser companion context when no session id is provided.",
                ),
            ],
        ),
        lifecycle=[
            InstallTemplateLifecycleAction(
                action="enable",
                label="Enable browser companion runtime",
                summary="Re-enable the cooperative browser companion capability when governance has disabled it.",
                risk_level="guarded",
            ),
            InstallTemplateLifecycleAction(
                action="doctor",
                label="Run browser companion doctor",
                summary="Inspect canonical browser companion projection, browser support, and runtime continuity state.",
                risk_level="auto",
            ),
            InstallTemplateLifecycleAction(
                action="example-run",
                label="Read browser companion runtime",
                summary="Resolve a live browser companion snapshot from EnvironmentService and optionally include browser runtime state.",
                risk_level="guarded",
            ),
        ],
        execution_strategy=InstallTemplateExecutionStrategy(
            risk_level="guarded",
            admission_mode="guarded",
            allowlist_scope="per-agent capability governance",
            approval_forwarding_supported=True,
            pending_approval_count=pending_approvals,
            target_capability_ids=manifest.capability_ids,
            host_policy=host_policy,
            routes=_cooperative_execution_routes(),
        ),
        host_policy=host_policy,
        runtime=(
            {
                "session_mount_id": runtime_context["session_mount_id"],
                "environment_id": runtime_context["environment_id"],
                "cooperative_adapter_availability": runtime_context["projection"],
                "browser_companion": snapshot,
                "browser_runtime": browser_runtime,
            }
            if include_runtime
            else {}
        ),
        support=(
            {
                "runtime_surface_available": runtime_context["runtime_surface_available"],
                "active_session_count": runtime_context["active_session_count"],
                "ready_session_count": runtime_context["ready_session_count"],
                "active_environment_count": runtime_context["active_environment_count"],
                "ready_environment_count": runtime_context["ready_environment_count"],
                "session_ids": runtime_context["session_ids"],
                "environment_ids": runtime_context["environment_ids"],
                "playwright_ready": bool(browser_support.get("playwright_ready")),
                "default_browser_kind": str(
                    browser_support.get("default_browser_kind") or ""
                ),
                "default_browser_path": str(
                    browser_support.get("default_browser_path") or ""
                ),
            }
            if include_runtime
            else {}
        ),
        routes=_cooperative_template_routes("browser-companion"),
    )


def _build_document_bridge_install_template(
    *,
    capability_service: object | None = None,
    decision_request_repository: object | None = None,
    environment_service: object | None = None,
    include_runtime: bool = False,
) -> CapabilityInstallTemplateSpec:
    installed, enabled = _builtin_capability_state(
        capability_service,
        "system:document_bridge_runtime",
    )
    host_policy = _windows_cooperative_host_policy(
        host_kind="cooperative-document-host",
    )
    manifest = _document_bridge_manifest()
    runtime_context = _cooperative_template_runtime_context(
        "document-office-bridge",
        environment_service=environment_service,
    )
    snapshot: dict[str, Any] = {}
    if include_runtime and runtime_context["session_mount_id"]:
        snapshot_payload = _safe_environment_call(
            environment_service,
            "document_bridge_snapshot",
            session_mount_id=runtime_context["session_mount_id"],
            document_family=None,
        )
        if isinstance(snapshot_payload, dict):
            snapshot = dict(snapshot_payload)
    ready = bool(enabled) and host_policy.ready
    pending_approvals = _count_pending_decisions(
        decision_request_repository,
        "document-office-bridge",
        "system:document_bridge_runtime",
        "document bridge",
        "office bridge",
    )
    return CapabilityInstallTemplateSpec(
        id="document-office-bridge",
        name="Document Office Bridge",
        description=(
            "Productized cooperative Office/document bridge surface that resolves "
            "supported document families and preferred execution path from the "
            "canonical environment/session projection."
        ),
        install_kind="builtin-runtime",
        source_kind="system",
        platform="windows",
        default_client_key=None,
        default_capability_id="system:document_bridge_runtime",
        capability_tags=["document", "office", "bridge", "cooperative", "phase2"],
        notes=[
            "Reads canonical document bridge state from EnvironmentService; it does not mirror document availability into a second store.",
            "Document family hints are resolved through the runtime facade so semantic-writing flows and native document paths share one contract.",
            "Best suited to live Office/document sessions already mounted into the runtime center.",
        ],
        risk_level="guarded",
        capability_budget_cost=1,
        default_assignment_policy="selected-agents-only",
        installed=installed,
        enabled=enabled,
        ready=ready,
        manifest=manifest,
        config_schema=InstallTemplateConfigSchema(
            scope="runtime",
            fields=[
                InstallTemplateConfigField(
                    key="session_mount_id",
                    label="Session mount id",
                    field_type="string",
                    required=False,
                    default="",
                    description="Optional session mount id used to inspect a specific document bridge registration.",
                ),
                InstallTemplateConfigField(
                    key="document_family",
                    label="Document family",
                    field_type="choice",
                    required=False,
                    default="documents",
                    choices=["documents", "spreadsheets", "presentations"],
                    description="Optional document family to resolve through the cooperative execution path contract.",
                ),
            ],
        ),
        lifecycle=[
            InstallTemplateLifecycleAction(
                action="enable",
                label="Enable document bridge runtime",
                summary="Re-enable the document bridge capability when governance has disabled it.",
                risk_level="guarded",
            ),
            InstallTemplateLifecycleAction(
                action="doctor",
                label="Run document bridge doctor",
                summary="Inspect cooperative document bridge registration, supported families, and execution-path hints.",
                risk_level="auto",
            ),
            InstallTemplateLifecycleAction(
                action="example-run",
                label="Read document bridge runtime",
                summary="Resolve a canonical document bridge snapshot for a target Office/document session.",
                risk_level="guarded",
            ),
        ],
        execution_strategy=InstallTemplateExecutionStrategy(
            risk_level="guarded",
            admission_mode="guarded",
            allowlist_scope="per-agent capability governance",
            approval_forwarding_supported=True,
            pending_approval_count=pending_approvals,
            target_capability_ids=manifest.capability_ids,
            host_policy=host_policy,
            routes=_cooperative_execution_routes(),
        ),
        host_policy=host_policy,
        runtime=(
            {
                "session_mount_id": runtime_context["session_mount_id"],
                "environment_id": runtime_context["environment_id"],
                "cooperative_adapter_availability": runtime_context["projection"],
                "document_bridge": snapshot,
            }
            if include_runtime
            else {}
        ),
        support=(
            {
                "runtime_surface_available": runtime_context["runtime_surface_available"],
                "active_session_count": runtime_context["active_session_count"],
                "ready_session_count": runtime_context["ready_session_count"],
                "active_environment_count": runtime_context["active_environment_count"],
                "ready_environment_count": runtime_context["ready_environment_count"],
                "session_ids": runtime_context["session_ids"],
                "environment_ids": runtime_context["environment_ids"],
            }
            if include_runtime
            else {}
        ),
        routes=_cooperative_template_routes("document-office-bridge"),
    )


def _build_host_watchers_install_template(
    *,
    capability_service: object | None = None,
    decision_request_repository: object | None = None,
    environment_service: object | None = None,
    include_runtime: bool = False,
) -> CapabilityInstallTemplateSpec:
    installed, enabled = _builtin_capability_state(
        capability_service,
        "system:host_watchers_runtime",
    )
    host_policy = _windows_cooperative_host_policy(
        host_kind="cooperative-host-watchers",
    )
    manifest = _host_watchers_manifest()
    runtime_context = _cooperative_template_runtime_context(
        "host-watchers",
        environment_service=environment_service,
    )
    snapshot: dict[str, Any] = {}
    if include_runtime and runtime_context["session_mount_id"]:
        snapshot_payload = _safe_environment_call(
            environment_service,
            "host_watchers_snapshot",
            runtime_context["session_mount_id"],
        )
        if isinstance(snapshot_payload, dict):
            snapshot = dict(snapshot_payload)
    ready = bool(enabled) and host_policy.ready
    pending_approvals = _count_pending_decisions(
        decision_request_repository,
        "host-watchers",
        "system:host_watchers_runtime",
        "host watcher",
    )
    return CapabilityInstallTemplateSpec(
        id="host-watchers",
        name="Host Watchers Runtime",
        description=(
            "Productized cooperative watcher surface for filesystem, download, and "
            "notification runtime observations backed by canonical session/environment "
            "metadata."
        ),
        install_kind="builtin-runtime",
        source_kind="system",
        platform="windows",
        default_client_key=None,
        default_capability_id="system:host_watchers_runtime",
        capability_tags=["watchers", "downloads", "notifications", "cooperative", "phase2"],
        notes=[
            "Host watcher availability and download policy are read from EnvironmentService runtime projections rather than duplicated into template-local state.",
            "Latest download/notification signals remain runtime events; the install template only surfaces the canonical observation summary.",
            "Useful for cooperative host seats that need download-complete and notification awareness in the runtime center.",
        ],
        risk_level="auto",
        capability_budget_cost=1,
        default_assignment_policy="selected-agents-only",
        installed=installed,
        enabled=enabled,
        ready=ready,
        manifest=manifest,
        config_schema=InstallTemplateConfigSchema(
            scope="runtime",
            fields=[
                InstallTemplateConfigField(
                    key="session_mount_id",
                    label="Session mount id",
                    field_type="string",
                    required=False,
                    default="",
                    description="Optional session mount id used to inspect a specific watcher runtime.",
                ),
                InstallTemplateConfigField(
                    key="watcher_family",
                    label="Watcher family",
                    field_type="choice",
                    required=False,
                    default="downloads",
                    choices=["filesystem", "downloads", "notifications"],
                    description="Optional watcher family to focus the example-run on.",
                ),
            ],
        ),
        lifecycle=[
            InstallTemplateLifecycleAction(
                action="enable",
                label="Enable host watchers runtime",
                summary="Re-enable the host watcher runtime when governance has disabled it.",
                risk_level="auto",
            ),
            InstallTemplateLifecycleAction(
                action="doctor",
                label="Run host watcher doctor",
                summary="Inspect canonical filesystem, download, and notification watcher availability.",
                risk_level="auto",
            ),
            InstallTemplateLifecycleAction(
                action="example-run",
                label="Read host watcher runtime",
                summary="Resolve a live watcher snapshot and verify the requested watcher family is available.",
                risk_level="auto",
            ),
        ],
        execution_strategy=InstallTemplateExecutionStrategy(
            risk_level="auto",
            admission_mode="auto",
            allowlist_scope="per-agent capability governance",
            approval_forwarding_supported=True,
            pending_approval_count=pending_approvals,
            target_capability_ids=manifest.capability_ids,
            host_policy=host_policy,
            routes=_cooperative_execution_routes(),
        ),
        host_policy=host_policy,
        runtime=(
            {
                "session_mount_id": runtime_context["session_mount_id"],
                "environment_id": runtime_context["environment_id"],
                "cooperative_adapter_availability": runtime_context["projection"],
                "host_watchers": snapshot,
            }
            if include_runtime
            else {}
        ),
        support=(
            {
                "runtime_surface_available": runtime_context["runtime_surface_available"],
                "active_session_count": runtime_context["active_session_count"],
                "ready_session_count": runtime_context["ready_session_count"],
                "active_environment_count": runtime_context["active_environment_count"],
                "ready_environment_count": runtime_context["ready_environment_count"],
                "session_ids": runtime_context["session_ids"],
                "environment_ids": runtime_context["environment_ids"],
            }
            if include_runtime
            else {}
        ),
        routes=_cooperative_template_routes("host-watchers"),
    )


def _build_windows_app_adapters_install_template(
    *,
    capability_service: object | None = None,
    decision_request_repository: object | None = None,
    environment_service: object | None = None,
    include_runtime: bool = False,
) -> CapabilityInstallTemplateSpec:
    installed, enabled = _builtin_capability_state(
        capability_service,
        "system:windows_app_adapter_runtime",
    )
    host_policy = _windows_cooperative_host_policy(
        host_kind="cooperative-windows-apps",
    )
    manifest = _windows_app_adapters_manifest()
    runtime_context = _cooperative_template_runtime_context(
        "windows-app-adapters",
        environment_service=environment_service,
    )
    snapshot: dict[str, Any] = {}
    if include_runtime and runtime_context["session_mount_id"]:
        snapshot_payload = _safe_environment_call(
            environment_service,
            "windows_app_adapter_snapshot",
            session_mount_id=runtime_context["session_mount_id"],
        )
        if isinstance(snapshot_payload, dict):
            snapshot = dict(snapshot_payload)
    ready = bool(enabled) and host_policy.ready
    pending_approvals = _count_pending_decisions(
        decision_request_repository,
        "windows-app-adapters",
        "system:windows_app_adapter_runtime",
        "windows app adapter",
    )
    return CapabilityInstallTemplateSpec(
        id="windows-app-adapters",
        name="Windows App Adapters",
        description=(
            "Productized cooperative Windows app adapter surface that reads canonical "
            "desktop-app adapter identity, control channel, and preferred execution "
            "path from EnvironmentService."
        ),
        install_kind="builtin-runtime",
        source_kind="system",
        platform="windows",
        default_client_key=None,
        default_capability_id="system:windows_app_adapter_runtime",
        capability_tags=["windows", "desktop", "adapters", "cooperative", "phase2"],
        notes=[
            "Tracks canonical Windows app adapter refs and control channels from EnvironmentService rather than a parallel adapter registry.",
            "Intended for high-value native app surfaces such as Office or file explorer where cooperative-native execution is preferred.",
            "Doctor and example-run are read-only projections over the current mounted desktop session.",
        ],
        risk_level="guarded",
        capability_budget_cost=1,
        default_assignment_policy="selected-agents-only",
        installed=installed,
        enabled=enabled,
        ready=ready,
        manifest=manifest,
        config_schema=InstallTemplateConfigSchema(
            scope="runtime",
            fields=[
                InstallTemplateConfigField(
                    key="session_mount_id",
                    label="Session mount id",
                    field_type="string",
                    required=False,
                    default="",
                    description="Optional session mount id used to inspect a specific Windows app adapter registration.",
                ),
                InstallTemplateConfigField(
                    key="adapter_ref",
                    label="Adapter ref",
                    field_type="string",
                    required=False,
                    default="",
                    description="Optional adapter ref that must be present in the runtime projection during example-run.",
                ),
            ],
        ),
        lifecycle=[
            InstallTemplateLifecycleAction(
                action="enable",
                label="Enable Windows app adapters",
                summary="Re-enable the cooperative Windows app adapter capability when governance has disabled it.",
                risk_level="guarded",
            ),
            InstallTemplateLifecycleAction(
                action="doctor",
                label="Run Windows app adapter doctor",
                summary="Inspect canonical Windows app adapter refs, app identity, and control channel.",
                risk_level="auto",
            ),
            InstallTemplateLifecycleAction(
                action="example-run",
                label="Read Windows app adapter runtime",
                summary="Resolve a live desktop app adapter projection for a mounted Windows session.",
                risk_level="guarded",
            ),
        ],
        execution_strategy=InstallTemplateExecutionStrategy(
            risk_level="guarded",
            admission_mode="guarded",
            allowlist_scope="per-agent capability governance",
            approval_forwarding_supported=True,
            pending_approval_count=pending_approvals,
            target_capability_ids=manifest.capability_ids,
            host_policy=host_policy,
            routes=_cooperative_execution_routes(),
        ),
        host_policy=host_policy,
        runtime=(
            {
                "session_mount_id": runtime_context["session_mount_id"],
                "environment_id": runtime_context["environment_id"],
                "cooperative_adapter_availability": runtime_context["projection"],
                "windows_app_adapters": snapshot,
            }
            if include_runtime
            else {}
        ),
        support=(
            {
                "runtime_surface_available": runtime_context["runtime_surface_available"],
                "active_session_count": runtime_context["active_session_count"],
                "ready_session_count": runtime_context["ready_session_count"],
                "active_environment_count": runtime_context["active_environment_count"],
                "ready_environment_count": runtime_context["ready_environment_count"],
                "session_ids": runtime_context["session_ids"],
                "environment_ids": runtime_context["environment_ids"],
            }
            if include_runtime
            else {}
        ),
        routes=_cooperative_template_routes("windows-app-adapters"),
    )


def _doctor_report_status(
    checks: list[InstallTemplateDoctorCheck],
) -> Literal["ready", "degraded", "blocked"]:
    statuses = [item.status for item in checks]
    if "fail" in statuses:
        return "blocked"
    if "warn" in statuses:
        return "degraded"
    return "ready"


def _install_template_error_record(
    *,
    template_id: str,
    started_at: datetime,
    summary: str,
    operations: list[str],
    runtime: dict[str, Any] | None = None,
    support: dict[str, Any] | None = None,
    code: str,
    detail: str = "",
    retryable: bool,
    source: str,
) -> InstallTemplateExampleRunRecord:
    finished_at = _utc_now()
    return InstallTemplateExampleRunRecord(
        template_id=template_id,
        status="error",
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
        summary=summary,
        operations=operations,
        runtime=runtime or {},
        support=support or {},
        error=ExecutionErrorDetail(
            code=code,
            summary=summary,
            detail=detail,
            retryable=retryable,
            source=source,
        ),
    )


def _cooperative_missing_environment_report(
    *,
    template_id: str,
    host_policy: InstallTemplateHostPolicy,
    support: dict[str, Any] | None = None,
) -> InstallTemplateDoctorReport:
    checks = [
        InstallTemplateDoctorCheck(
            key="runtime_surface",
            label="Runtime surface",
            status="fail",
            message="EnvironmentService runtime projection is not available",
            detail="Doctor requires the canonical EnvironmentService facade to read cooperative adapter state.",
        ),
    ]
    return InstallTemplateDoctorReport(
        template_id=template_id,
        status="blocked",
        summary="Canonical runtime projection is unavailable",
        checks=checks,
        host_policy=host_policy,
        runtime={},
        support=support or {},
        error=ExecutionErrorDetail(
            code="environment-service-missing",
            summary="EnvironmentService runtime projection is required",
            detail="Wire environment_service into the install template surface before using this cooperative doctor.",
            retryable=True,
            source="environment-service",
        ),
    )


def _cooperative_browser_companion_support(
    runtime_context: dict[str, Any],
    browser_support: dict[str, Any],
) -> dict[str, Any]:
    return {
        "runtime_surface_available": runtime_context["runtime_surface_available"],
        "active_session_count": runtime_context["active_session_count"],
        "ready_session_count": runtime_context["ready_session_count"],
        "active_environment_count": runtime_context["active_environment_count"],
        "ready_environment_count": runtime_context["ready_environment_count"],
        "session_ids": runtime_context["session_ids"],
        "environment_ids": runtime_context["environment_ids"],
        "playwright_ready": bool(browser_support.get("playwright_ready")),
        "default_browser_kind": str(browser_support.get("default_browser_kind") or ""),
        "default_browser_path": str(browser_support.get("default_browser_path") or ""),
    }


def _cooperative_template_support(runtime_context: dict[str, Any]) -> dict[str, Any]:
    return {
        "runtime_surface_available": runtime_context["runtime_surface_available"],
        "active_session_count": runtime_context["active_session_count"],
        "ready_session_count": runtime_context["ready_session_count"],
        "active_environment_count": runtime_context["active_environment_count"],
        "ready_environment_count": runtime_context["ready_environment_count"],
        "session_ids": runtime_context["session_ids"],
        "environment_ids": runtime_context["environment_ids"],
    }


def _cooperative_runtime_snapshot(
    template_id: str,
    *,
    environment_service: object | None,
    runtime_context: dict[str, Any],
    browser_runtime_service: BrowserRuntimeService | None = None,
    document_family: str | None = None,
) -> dict[str, Any]:
    session_mount_id = _string_value(runtime_context.get("session_mount_id"))
    environment_id = _string_value(runtime_context.get("environment_id"))
    projection = dict(runtime_context.get("projection") or {})

    if template_id == "browser-companion":
        snapshot_payload = _safe_environment_call(
            environment_service,
            "browser_companion_snapshot",
            session_mount_id=session_mount_id,
            environment_id=environment_id,
        )
        runtime = {
            "session_mount_id": session_mount_id,
            "environment_id": environment_id,
            "cooperative_adapter_availability": projection,
            "browser_companion": (
                dict(snapshot_payload) if isinstance(snapshot_payload, dict) else {}
            ),
        }
        if browser_runtime_service is not None and (
            session_mount_id is not None or environment_id is not None
        ):
            runtime["browser_runtime"] = browser_runtime_service.runtime_snapshot(
                environment_id=environment_id,
                session_mount_id=session_mount_id,
            )
        return runtime
    if template_id == "document-office-bridge":
        snapshot_payload = (
            _safe_environment_call(
                environment_service,
                "document_bridge_snapshot",
                session_mount_id=session_mount_id,
                document_family=document_family,
            )
            if session_mount_id is not None
            else None
        )
        return {
            "session_mount_id": session_mount_id,
            "environment_id": environment_id,
            "cooperative_adapter_availability": projection,
            "document_bridge": (
                dict(snapshot_payload) if isinstance(snapshot_payload, dict) else {}
            ),
        }
    if template_id == "host-watchers":
        snapshot_payload = (
            _safe_environment_call(
                environment_service,
                "host_watchers_snapshot",
                session_mount_id,
            )
            if session_mount_id is not None
            else None
        )
        return {
            "session_mount_id": session_mount_id,
            "environment_id": environment_id,
            "cooperative_adapter_availability": projection,
            "host_watchers": (
                dict(snapshot_payload) if isinstance(snapshot_payload, dict) else {}
            ),
        }
    if template_id == "windows-app-adapters":
        snapshot_payload = (
            _safe_environment_call(
                environment_service,
                "windows_app_adapter_snapshot",
                session_mount_id=session_mount_id,
            )
            if session_mount_id is not None
            else None
        )
        return {
            "session_mount_id": session_mount_id,
            "environment_id": environment_id,
            "cooperative_adapter_availability": projection,
            "windows_app_adapters": (
                dict(snapshot_payload) if isinstance(snapshot_payload, dict) else {}
            ),
        }
    return {
        "session_mount_id": session_mount_id,
        "environment_id": environment_id,
        "cooperative_adapter_availability": projection,
    }


def _browser_companion_doctor(
    *,
    capability_service: object | None = None,
    browser_runtime_service: BrowserRuntimeService | None = None,
    environment_service: object | None = None,
) -> InstallTemplateDoctorReport:
    browser_support = get_browser_support_snapshot()
    host_policy = _browser_host_policy(bool(browser_support.get("playwright_ready")))
    runtime_context = _cooperative_template_runtime_context(
        "browser-companion",
        environment_service=environment_service,
    )
    support = _cooperative_browser_companion_support(runtime_context, browser_support)
    if environment_service is None:
        return _cooperative_missing_environment_report(
            template_id="browser-companion",
            host_policy=host_policy,
            support=support,
        )

    runtime = _cooperative_runtime_snapshot(
        "browser-companion",
        environment_service=environment_service,
        runtime_context=runtime_context,
        browser_runtime_service=browser_runtime_service,
    )
    enabled = _mount_enabled(capability_service, "system:browser_companion_runtime")
    projection = dict(runtime_context.get("projection") or {})
    companion = dict(runtime.get("browser_companion") or {})
    available = _bool_value(companion.get("available"))
    if available is None:
        available = _bool_value((projection.get("browser_companion") or {}).get("available"))
    checks = [
        InstallTemplateDoctorCheck(
            key="capability",
            label="Capability state",
            status="pass" if enabled else "warn",
            message=(
                "system:browser_companion_runtime is enabled"
                if enabled
                else "system:browser_companion_runtime is disabled or unavailable"
            ),
        ),
        InstallTemplateDoctorCheck(
            key="playwright",
            label="Browser host support",
            status="pass" if browser_support.get("playwright_ready") else "fail",
            message=(
                "Managed browser runtime is ready"
                if browser_support.get("playwright_ready")
                else str(browser_support.get("playwright_error") or "Managed browser runtime is not ready")
            ),
        ),
        InstallTemplateDoctorCheck(
            key="session_projection",
            label="Canonical session projection",
            status="pass" if runtime_context["active_session_count"] else "warn",
            message=(
                f"{runtime_context['active_session_count']} browser companion session(s) found"
                if runtime_context["active_session_count"]
                else "No browser companion projection is currently mounted"
            ),
        ),
        InstallTemplateDoctorCheck(
            key="companion_channel",
            label="Companion channel",
            status="pass" if available else "warn",
            message=(
                str(companion.get("transport_ref") or "Browser companion is attached")
                if available
                else str(
                    (projection.get("current_gap_or_blocker") or companion.get("status") or "Browser companion is not currently available")
                )
            ),
        ),
        InstallTemplateDoctorCheck(
            key="preferred_path",
            label="Preferred execution path",
            status="info",
            message=str(
                projection.get("preferred_execution_path")
                or companion.get("preferred_execution_path")
                or "semantic-operator-second"
            ),
            detail=str(projection.get("current_gap_or_blocker") or ""),
        ),
    ]
    report_status = _doctor_report_status(checks)
    return InstallTemplateDoctorReport(
        template_id="browser-companion",
        status=report_status,
        summary=(
            "Browser companion runtime is healthy"
            if report_status == "ready"
            else "Browser companion runtime needs session or host attention"
        ),
        checks=checks,
        host_policy=host_policy,
        runtime=runtime,
        support=support,
    )


def _document_bridge_doctor(
    *,
    capability_service: object | None = None,
    environment_service: object | None = None,
) -> InstallTemplateDoctorReport:
    host_policy = _windows_cooperative_host_policy(
        host_kind="cooperative-document-host",
    )
    runtime_context = _cooperative_template_runtime_context(
        "document-office-bridge",
        environment_service=environment_service,
    )
    support = _cooperative_template_support(runtime_context)
    if environment_service is None:
        return _cooperative_missing_environment_report(
            template_id="document-office-bridge",
            host_policy=host_policy,
            support=support,
        )

    runtime = _cooperative_runtime_snapshot(
        "document-office-bridge",
        environment_service=environment_service,
        runtime_context=runtime_context,
    )
    enabled = _mount_enabled(capability_service, "system:document_bridge_runtime")
    bridge = dict(runtime.get("document_bridge") or {}).get("document_bridge")
    if not isinstance(bridge, dict):
        bridge = {}
    projection = dict(runtime_context.get("projection") or {})
    projection_bridge = dict(projection.get("document_bridge") or {})
    families = _string_list_value(bridge.get("supported_families")) or _string_list_value(
        projection_bridge.get("supported_families")
    )
    available = _bool_value(bridge.get("available"))
    if available is None:
        available = _bool_value(projection_bridge.get("available"))
    checks = [
        InstallTemplateDoctorCheck(
            key="capability",
            label="Capability state",
            status="pass" if enabled else "warn",
            message=(
                "system:document_bridge_runtime is enabled"
                if enabled
                else "system:document_bridge_runtime is disabled or unavailable"
            ),
        ),
        InstallTemplateDoctorCheck(
            key="session_projection",
            label="Canonical session projection",
            status="pass" if runtime_context["active_session_count"] else "warn",
            message=(
                f"{runtime_context['active_session_count']} document bridge session(s) found"
                if runtime_context["active_session_count"]
                else "No document bridge projection is currently mounted"
            ),
        ),
        InstallTemplateDoctorCheck(
            key="bridge_state",
            label="Bridge availability",
            status="pass" if available else "warn",
            message=(
                str(projection_bridge.get("bridge_ref") or "Document bridge is ready")
                if available
                else str(
                    bridge.get("adapter_gap_or_blocker")
                    or projection.get("current_gap_or_blocker")
                    or "Document bridge is not currently ready"
                )
            ),
        ),
        InstallTemplateDoctorCheck(
            key="supported_families",
            label="Supported families",
            status="info",
            message=", ".join(families) if families else "No supported families advertised",
        ),
    ]
    report_status = _doctor_report_status(checks)
    return InstallTemplateDoctorReport(
        template_id="document-office-bridge",
        status=report_status,
        summary=(
            "Document bridge runtime is healthy"
            if report_status == "ready"
            else "Document bridge runtime needs session or adapter attention"
        ),
        checks=checks,
        host_policy=host_policy,
        runtime=runtime,
        support=support,
    )


def _host_watchers_doctor(
    *,
    capability_service: object | None = None,
    environment_service: object | None = None,
) -> InstallTemplateDoctorReport:
    host_policy = _windows_cooperative_host_policy(
        host_kind="cooperative-host-watchers",
    )
    runtime_context = _cooperative_template_runtime_context(
        "host-watchers",
        environment_service=environment_service,
    )
    support = _cooperative_template_support(runtime_context)
    if environment_service is None:
        return _cooperative_missing_environment_report(
            template_id="host-watchers",
            host_policy=host_policy,
            support=support,
        )

    runtime = _cooperative_runtime_snapshot(
        "host-watchers",
        environment_service=environment_service,
        runtime_context=runtime_context,
    )
    enabled = _mount_enabled(capability_service, "system:host_watchers_runtime")
    watchers = dict(runtime.get("host_watchers") or {}).get("watchers")
    if not isinstance(watchers, dict):
        watchers = {}
    available_families = _string_list_value(
        (runtime.get("host_watchers") or {}).get("available_families")
    )
    checks = [
        InstallTemplateDoctorCheck(
            key="capability",
            label="Capability state",
            status="pass" if enabled else "warn",
            message=(
                "system:host_watchers_runtime is enabled"
                if enabled
                else "system:host_watchers_runtime is disabled or unavailable"
            ),
        ),
        InstallTemplateDoctorCheck(
            key="session_projection",
            label="Canonical session projection",
            status="pass" if runtime_context["active_session_count"] else "warn",
            message=(
                f"{runtime_context['active_session_count']} watcher session(s) found"
                if runtime_context["active_session_count"]
                else "No host watcher projection is currently mounted"
            ),
        ),
        InstallTemplateDoctorCheck(
            key="watcher_families",
            label="Available watcher families",
            status="pass" if available_families else "warn",
            message=(
                ", ".join(available_families)
                if available_families
                else "No watcher family is currently available"
            ),
            detail=str(
                (runtime.get("host_watchers") or {}).get("adapter_gap_or_blocker") or ""
            ),
        ),
        InstallTemplateDoctorCheck(
            key="download_policy",
            label="Download policy",
            status="info",
            message=str(
                ((watchers.get("downloads") or {}).get("download_policy"))
                or "No download policy published"
            ),
        ),
    ]
    report_status = _doctor_report_status(checks)
    return InstallTemplateDoctorReport(
        template_id="host-watchers",
        status=report_status,
        summary=(
            "Host watcher runtime is healthy"
            if report_status == "ready"
            else "Host watcher runtime needs session or watcher attention"
        ),
        checks=checks,
        host_policy=host_policy,
        runtime=runtime,
        support=support,
    )


def _windows_app_adapters_doctor(
    *,
    capability_service: object | None = None,
    environment_service: object | None = None,
) -> InstallTemplateDoctorReport:
    host_policy = _windows_cooperative_host_policy(
        host_kind="cooperative-windows-apps",
    )
    runtime_context = _cooperative_template_runtime_context(
        "windows-app-adapters",
        environment_service=environment_service,
    )
    support = _cooperative_template_support(runtime_context)
    if environment_service is None:
        return _cooperative_missing_environment_report(
            template_id="windows-app-adapters",
            host_policy=host_policy,
            support=support,
        )

    runtime = _cooperative_runtime_snapshot(
        "windows-app-adapters",
        environment_service=environment_service,
        runtime_context=runtime_context,
    )
    enabled = _mount_enabled(capability_service, "system:windows_app_adapter_runtime")
    adapters = dict(runtime.get("windows_app_adapters") or {}).get("windows_app_adapters")
    if not isinstance(adapters, dict):
        adapters = {}
    adapter_refs = _string_list_value(adapters.get("adapter_refs"))
    checks = [
        InstallTemplateDoctorCheck(
            key="capability",
            label="Capability state",
            status="pass" if enabled else "warn",
            message=(
                "system:windows_app_adapter_runtime is enabled"
                if enabled
                else "system:windows_app_adapter_runtime is disabled or unavailable"
            ),
        ),
        InstallTemplateDoctorCheck(
            key="session_projection",
            label="Canonical session projection",
            status="pass" if runtime_context["active_session_count"] else "warn",
            message=(
                f"{runtime_context['active_session_count']} Windows app adapter session(s) found"
                if runtime_context["active_session_count"]
                else "No Windows app adapter projection is currently mounted"
            ),
        ),
        InstallTemplateDoctorCheck(
            key="adapter_refs",
            label="Adapter refs",
            status="pass" if adapter_refs else "warn",
            message=(
                ", ".join(adapter_refs)
                if adapter_refs
                else "No Windows app adapter ref is currently available"
            ),
            detail=str(
                (runtime.get("windows_app_adapters") or {}).get("adapter_gap_or_blocker")
                or ""
            ),
        ),
        InstallTemplateDoctorCheck(
            key="control_channel",
            label="Control channel",
            status="info",
            message=str(adapters.get("control_channel") or "No control channel published"),
            detail=str(adapters.get("app_identity") or ""),
        ),
    ]
    report_status = _doctor_report_status(checks)
    return InstallTemplateDoctorReport(
        template_id="windows-app-adapters",
        status=report_status,
        summary=(
            "Windows app adapter runtime is healthy"
            if report_status == "ready"
            else "Windows app adapter runtime needs session or adapter attention"
        ),
        checks=checks,
        host_policy=host_policy,
        runtime=runtime,
        support=support,
    )


def _desktop_doctor(
    *,
    capability_service: object | None = None,
) -> InstallTemplateDoctorReport:
    installed_clients = _list_installed_mcp_clients(capability_service)
    enabled = installed_clients.get("desktop_windows")
    host_policy = _desktop_host_policy()
    pywin32_ready = _desktop_pywin32_ready()
    checks = [
        InstallTemplateDoctorCheck(
            key="platform",
            label="Host platform",
            status="pass" if sys.platform == "win32" else "fail",
            message="Windows host detected" if sys.platform == "win32" else "This host is not Windows",
        ),
        InstallTemplateDoctorCheck(
            key="pywin32",
            label="Win32 dependencies",
            status="pass" if pywin32_ready else "fail",
            message=(
                "pywin32 desktop dependencies are available"
                if pywin32_ready
                else "pywin32 desktop dependencies are missing"
            ),
        ),
        InstallTemplateDoctorCheck(
            key="install_state",
            label="Install state",
            status="pass" if enabled else "warn",
            message=(
                "Desktop MCP client is installed and enabled"
                if enabled
                else "Desktop MCP client is installed but disabled"
                if enabled is False
                else "Desktop MCP client is not installed yet"
            ),
        ),
        InstallTemplateDoctorCheck(
            key="server_module",
            label="Adapter module",
            status="pass" if _find_module("copaw.adapters.desktop.windows_mcp_server") else "fail",
            message=(
                "Desktop MCP server module is importable"
                if _find_module("copaw.adapters.desktop.windows_mcp_server")
                else "Desktop MCP server module is missing"
            ),
        ),
    ]
    statuses = [item.status for item in checks]
    if "fail" in statuses:
        report_status: Literal["ready", "degraded", "blocked"] = "blocked"
    elif "warn" in statuses:
        report_status = "degraded"
    else:
        report_status = "ready"
    return InstallTemplateDoctorReport(
        template_id="desktop-windows",
        status=report_status,
        summary=(
            "Windows desktop adapter is ready"
            if report_status == "ready"
            else "Windows desktop adapter needs host or install attention"
        ),
        checks=checks,
        host_policy=host_policy,
        support={
            "installed_client_key": "desktop_windows",
            "installed": enabled is not None,
            "enabled": enabled,
            "pywin32_ready": pywin32_ready,
        },
        runtime={},
    )


def _browser_doctor(
    *,
    capability_service: object | None = None,
    browser_runtime_service: BrowserRuntimeService | None = None,
) -> InstallTemplateDoctorReport:
    support = get_browser_support_snapshot()
    runtime = (
        browser_runtime_service.runtime_snapshot()
        if browser_runtime_service is not None
        else get_browser_runtime_snapshot()
    )
    profiles = (
        browser_runtime_service.list_profiles()
        if browser_runtime_service is not None
        else []
    )
    enabled = _mount_enabled(capability_service, "tool:browser_use")
    host_policy = _browser_host_policy(bool(support.get("playwright_ready")))
    checks = [
        InstallTemplateDoctorCheck(
            key="capability",
            label="Capability state",
            status="pass" if enabled else "warn",
            message=(
                "tool:browser_use is installed and enabled"
                if enabled
                else "tool:browser_use is currently disabled or unavailable"
            ),
        ),
        InstallTemplateDoctorCheck(
            key="playwright",
            label="Playwright runtime",
            status="pass" if support.get("playwright_ready") else "fail",
            message=(
                "Playwright runtime is ready"
                if support.get("playwright_ready")
                else str(support.get("playwright_error") or "Playwright runtime is not ready")
            ),
        ),
        InstallTemplateDoctorCheck(
            key="browser_support",
            label="Default browser support",
            status="info",
            message=str(support.get("default_browser_kind") or "playwright-managed"),
            detail=str(support.get("default_browser_path") or ""),
        ),
        InstallTemplateDoctorCheck(
            key="runtime",
            label="Managed runtime state",
            status="info",
            message=(
                "Browser runtime is currently running"
                if runtime.get("running")
                else "Browser runtime is currently stopped"
            ),
        ),
        InstallTemplateDoctorCheck(
            key="profiles",
            label="Saved profiles",
            status="info",
            message=f"{len(profiles)} saved profile(s)",
        ),
        InstallTemplateDoctorCheck(
            key="sessions",
            label="Active sessions",
            status="info",
            message=f"{int(runtime.get('session_count') or 0)} active session(s)",
        ),
    ]
    statuses = [item.status for item in checks]
    if "fail" in statuses:
        report_status: Literal["ready", "degraded", "blocked"] = "blocked"
    elif "warn" in statuses:
        report_status = "degraded"
    else:
        report_status = "ready"
    return InstallTemplateDoctorReport(
        template_id="browser-local",
        status=report_status,
        summary=(
            "Browser runtime is ready"
            if report_status == "ready"
            else "Browser runtime needs capability or host attention"
        ),
        checks=checks,
        host_policy=host_policy,
        runtime=runtime,
        support={
            **support,
            "profile_count": len(profiles),
            "profiles": [profile.model_dump(mode="json") for profile in profiles],
        },
    )


async def _desktop_example_run(
    *,
    capability_service: object | None = None,
) -> InstallTemplateExampleRunRecord:
    started_at = _utc_now()
    enabled = _list_installed_mcp_clients(capability_service).get("desktop_windows")
    if enabled is None:
        finished_at = _utc_now()
        return InstallTemplateExampleRunRecord(
            template_id="desktop-windows",
            status="error",
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            summary="Desktop adapter is not installed",
            operations=["check-install-state"],
            error=ExecutionErrorDetail(
                code="dependency-missing",
                summary="Install the desktop template before running the smoke check",
                retryable=True,
                source="install-template",
            ),
        )
    if enabled is False:
        finished_at = _utc_now()
        return InstallTemplateExampleRunRecord(
            template_id="desktop-windows",
            status="error",
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            summary="Desktop adapter is installed but disabled",
            operations=["check-enable-state"],
            error=ExecutionErrorDetail(
                code="capability-disabled",
                summary="Enable the installed desktop adapter before running the smoke check",
                retryable=True,
                source="install-template",
            ),
        )
    try:
        payload = WindowsDesktopHost().list_windows(limit=1)
        finished_at = _utc_now()
        return InstallTemplateExampleRunRecord(
            template_id="desktop-windows",
            status="success",
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            summary="Desktop host smoke succeeded",
            operations=["list-windows"],
            payload=payload if isinstance(payload, dict) else {},
            support={"installed": True, "enabled": True},
        )
    except DesktopAutomationError as exc:
        finished_at = _utc_now()
        return InstallTemplateExampleRunRecord(
            template_id="desktop-windows",
            status="error",
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            summary="Desktop host smoke failed",
            operations=["list-windows"],
            error=ExecutionErrorDetail(
                code="host-unavailable",
                summary=str(exc),
                detail=str(exc),
                retryable=True,
                source="desktop-host",
            ),
        )
    except Exception as exc:  # pragma: no cover
        finished_at = _utc_now()
        return InstallTemplateExampleRunRecord(
            template_id="desktop-windows",
            status="error",
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            summary="Desktop host smoke failed",
            operations=["list-windows"],
            error=ExecutionErrorDetail(
                code="runtime-exception",
                summary=str(exc),
                detail=str(exc),
                retryable=False,
                source="desktop-host",
            ),
        )


async def _browser_example_run(
    *,
    capability_service: object | None = None,
    browser_runtime_service: BrowserRuntimeService | None = None,
    config: dict[str, Any] | None = None,
) -> InstallTemplateExampleRunRecord:
    started_at = _utc_now()
    support = get_browser_support_snapshot()
    runtime_before = (
        browser_runtime_service.runtime_snapshot()
        if browser_runtime_service is not None
        else get_browser_runtime_snapshot()
    )
    enabled = _mount_enabled(capability_service, "tool:browser_use")
    normalized_config = dict(config or {})
    session_id = str(normalized_config.get("session_id") or "browser-local-example").strip() or "browser-local-example"
    if not enabled:
        finished_at = _utc_now()
        return InstallTemplateExampleRunRecord(
            template_id="browser-local",
            status="error",
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            summary="Browser runtime is disabled or unavailable",
            operations=["check-capability-state"],
            runtime=runtime_before,
            support=support,
            error=ExecutionErrorDetail(
                code="capability-disabled",
                summary="Enable tool:browser_use before running the browser smoke check",
                retryable=True,
                source="capability",
            ),
        )
    if not support.get("playwright_ready"):
        finished_at = _utc_now()
        return InstallTemplateExampleRunRecord(
            template_id="browser-local",
            status="error",
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            summary="Playwright runtime is not ready",
            operations=["check-playwright"],
            runtime=runtime_before,
            support=support,
            error=ExecutionErrorDetail(
                code="dependency-missing",
                summary=str(support.get("playwright_error") or "Playwright runtime is not ready"),
                retryable=True,
                source="browser-runtime",
            ),
        )
    operations: list[str] = []
    active_session_ids = {
        str(item.get("session_id") or "")
        for item in list(runtime_before.get("sessions") or [])
        if str(item.get("session_id") or "").strip()
    }
    session_already_running = session_id in active_session_ids
    runtime_after = dict(runtime_before)
    try:
        if browser_runtime_service is not None:
            start_payload = await browser_runtime_service.start_session(
                BrowserSessionStartOptions(
                    session_id=session_id,
                    profile_id=str(normalized_config.get("profile_id") or "").strip() or None,
                    headed=(
                        bool(normalized_config.get("headed"))
                        if "headed" in normalized_config
                        else None
                    ),
                    entry_url=str(normalized_config.get("entry_url") or "").strip() or None,
                    reuse_running_session=(
                        bool(normalized_config.get("reuse_running_session"))
                        if "reuse_running_session" in normalized_config
                        else None
                    ),
                    persist_login_state=(
                        bool(normalized_config.get("persist_login_state"))
                        if "persist_login_state" in normalized_config
                        else None
                    ),
                    navigation_guard={
                        "allowed_hosts": list(normalized_config.get("allowed_hosts") or []),
                        "blocked_hosts": list(normalized_config.get("blocked_hosts") or []),
                    }
                    if (
                        normalized_config.get("allowed_hosts")
                        or normalized_config.get("blocked_hosts")
                    )
                    else None,
                    action_timeout_seconds=normalized_config.get("action_timeout_seconds"),
                )
            )
            start_result = dict(start_payload.get("result") or {})
            if not start_result.get("ok"):
                raise RuntimeError(str(start_result.get("error") or "Browser start failed"))
            operations.append("attach" if start_payload.get("status") == "attached" else "start")
            if not session_already_running:
                stop_payload = await browser_runtime_service.stop_session(session_id)
                stop_result = dict(stop_payload.get("result") or {})
                if not stop_result.get("ok"):
                    raise RuntimeError(str(stop_result.get("error") or "Browser stop failed"))
                operations.append("stop")
            runtime_after = browser_runtime_service.runtime_snapshot()
        else:
            if not session_already_running:
                start_response = await browser_use(
                    action="start",
                    session_id=session_id,
                    headed=bool(normalized_config.get("headed", True)),
                )
                operations.append("start")
                start_payload = _parse_tool_response_json(start_response)
                if not start_payload.get("ok"):
                    raise RuntimeError(str(start_payload.get("error") or "Browser start failed"))
                stop_response = await browser_use(action="stop", session_id=session_id)
                operations.append("stop")
                stop_payload = _parse_tool_response_json(stop_response)
                if not stop_payload.get("ok"):
                    raise RuntimeError(str(stop_payload.get("error") or "Browser stop failed"))
                runtime_after = get_browser_runtime_snapshot()
            else:
                operations.append("reuse-running-runtime")
        finished_at = _utc_now()
        return InstallTemplateExampleRunRecord(
            template_id="browser-local",
            status="success",
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            summary=(
                "Browser runtime smoke completed"
                if not session_already_running
                else "Browser runtime session is already running and healthy"
            ),
            operations=operations,
            runtime={
                "before": runtime_before,
                "after": runtime_after,
            },
            support=support,
        )
    except Exception as exc:
        finished_at = _utc_now()
        return InstallTemplateExampleRunRecord(
            template_id="browser-local",
            status="error",
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            summary="Browser runtime smoke failed",
            operations=operations or ["start"],
            runtime={
                "before": runtime_before,
                "after": (
                    browser_runtime_service.runtime_snapshot()
                    if browser_runtime_service is not None
                    else get_browser_runtime_snapshot()
                ),
            },
            support=support,
            error=ExecutionErrorDetail(
                code="runtime-exception",
                summary=str(exc),
                detail=str(exc),
                retryable=True,
                source="browser-runtime",
            ),
        )


async def _browser_companion_example_run(
    *,
    capability_service: object | None = None,
    browser_runtime_service: BrowserRuntimeService | None = None,
    environment_service: object | None = None,
    config: dict[str, Any] | None = None,
) -> InstallTemplateExampleRunRecord:
    started_at = _utc_now()
    normalized_config = dict(config or {})
    browser_support = get_browser_support_snapshot()
    requested_session_mount_id = _string_value(normalized_config.get("session_mount_id"))
    requested_environment_id = _string_value(normalized_config.get("environment_id"))
    runtime_context = _cooperative_template_runtime_context(
        "browser-companion",
        environment_service=environment_service,
        session_mount_id=requested_session_mount_id,
        environment_id=requested_environment_id,
    )
    support = _cooperative_browser_companion_support(runtime_context, browser_support)
    operations = ["resolve-runtime-context"]
    if not _mount_enabled(capability_service, "system:browser_companion_runtime"):
        return _install_template_error_record(
            template_id="browser-companion",
            started_at=started_at,
            summary="Browser companion runtime is disabled or unavailable",
            operations=["check-capability-state"],
            support=support,
            code="capability-disabled",
            detail="Enable system:browser_companion_runtime before reading the browser companion runtime.",
            retryable=True,
            source="capability",
        )
    if environment_service is None:
        return _install_template_error_record(
            template_id="browser-companion",
            started_at=started_at,
            summary="EnvironmentService runtime projection is unavailable",
            operations=operations,
            support=support,
            code="environment-service-missing",
            detail="Example run requires the canonical EnvironmentService facade to resolve browser companion state.",
            retryable=True,
            source="environment-service",
        )
    runtime = _cooperative_runtime_snapshot(
        "browser-companion",
        environment_service=environment_service,
        runtime_context=runtime_context,
        browser_runtime_service=browser_runtime_service,
    )
    operations.append("read-browser-companion-snapshot")
    if browser_runtime_service is not None:
        operations.append("read-browser-runtime")
    companion = dict(runtime.get("browser_companion") or {})
    available = _bool_value(companion.get("available"))
    if available is None:
        available = _bool_value(
            ((runtime_context.get("projection") or {}).get("browser_companion") or {}).get(
                "available"
            )
        )
    if runtime_context["session_mount_id"] is None and runtime_context["environment_id"] is None:
        return _install_template_error_record(
            template_id="browser-companion",
            started_at=started_at,
            summary="No browser companion session is currently mounted",
            operations=operations,
            runtime=runtime,
            support=support,
            code="runtime-unavailable",
            detail="Mount a browser environment/session through EnvironmentService before running this example.",
            retryable=True,
            source="environment-service",
        )
    if not available:
        return _install_template_error_record(
            template_id="browser-companion",
            started_at=started_at,
            summary="Browser companion is not currently available",
            operations=operations,
            runtime=runtime,
            support=support,
            code="adapter-unavailable",
            detail=str(
                (runtime_context.get("projection") or {}).get("current_gap_or_blocker")
                or companion.get("status")
                or "Browser companion did not report availability."
            ),
            retryable=True,
            source="environment-service",
        )
    finished_at = _utc_now()
    return InstallTemplateExampleRunRecord(
        template_id="browser-companion",
        status="success",
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
        summary="Browser companion runtime projection is healthy",
        operations=operations,
        runtime=runtime,
        support=support,
        payload={
            "session_mount_id": runtime_context["session_mount_id"],
            "environment_id": runtime_context["environment_id"],
            "transport_ref": companion.get("transport_ref"),
            "provider_session_ref": companion.get("provider_session_ref"),
        },
    )


async def _document_bridge_example_run(
    *,
    capability_service: object | None = None,
    environment_service: object | None = None,
    config: dict[str, Any] | None = None,
) -> InstallTemplateExampleRunRecord:
    started_at = _utc_now()
    normalized_config = dict(config or {})
    document_family = _string_value(normalized_config.get("document_family")) or "documents"
    requested_session_mount_id = _string_value(normalized_config.get("session_mount_id"))
    runtime_context = _cooperative_template_runtime_context(
        "document-office-bridge",
        environment_service=environment_service,
        session_mount_id=requested_session_mount_id,
    )
    support = _cooperative_template_support(runtime_context)
    operations = ["resolve-runtime-context"]
    if not _mount_enabled(capability_service, "system:document_bridge_runtime"):
        return _install_template_error_record(
            template_id="document-office-bridge",
            started_at=started_at,
            summary="Document bridge runtime is disabled or unavailable",
            operations=["check-capability-state"],
            support=support,
            code="capability-disabled",
            detail="Enable system:document_bridge_runtime before reading the document bridge runtime.",
            retryable=True,
            source="capability",
        )
    if environment_service is None:
        return _install_template_error_record(
            template_id="document-office-bridge",
            started_at=started_at,
            summary="EnvironmentService runtime projection is unavailable",
            operations=operations,
            support=support,
            code="environment-service-missing",
            detail="Example run requires the canonical EnvironmentService facade to resolve document bridge state.",
            retryable=True,
            source="environment-service",
        )
    if runtime_context["session_mount_id"] is None:
        return _install_template_error_record(
            template_id="document-office-bridge",
            started_at=started_at,
            summary="No document bridge session is currently mounted",
            operations=operations,
            support=support,
            code="runtime-unavailable",
            detail="Mount a document/workspace session through EnvironmentService before running this example.",
            retryable=True,
            source="environment-service",
        )
    runtime = _cooperative_runtime_snapshot(
        "document-office-bridge",
        environment_service=environment_service,
        runtime_context=runtime_context,
        document_family=document_family,
    )
    operations.append("read-document-bridge-snapshot")
    snapshot = dict(runtime.get("document_bridge") or {})
    bridge = dict(snapshot.get("document_bridge") or {})
    available = _bool_value(bridge.get("available"))
    if available is None:
        available = _bool_value(
            ((runtime_context.get("projection") or {}).get("document_bridge") or {}).get(
                "available"
            )
        )
    blocker = _string_value(snapshot.get("adapter_gap_or_blocker"))
    if blocker or not available:
        return _install_template_error_record(
            template_id="document-office-bridge",
            started_at=started_at,
            summary="Document bridge is not currently ready",
            operations=operations,
            runtime=runtime,
            support=support,
            code="adapter-unavailable",
            detail=str(
                blocker
                or (runtime_context.get("projection") or {}).get("current_gap_or_blocker")
                or "Document bridge did not report availability."
            ),
            retryable=True,
            source="environment-service",
        )
    finished_at = _utc_now()
    return InstallTemplateExampleRunRecord(
        template_id="document-office-bridge",
        status="success",
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
        summary="Document bridge runtime projection is healthy",
        operations=operations,
        runtime=runtime,
        support=support,
        payload={
            "session_mount_id": runtime_context["session_mount_id"],
            "environment_id": runtime_context["environment_id"],
            "document_family": snapshot.get("document_family") or document_family,
            "supported_families": bridge.get("supported_families") or [],
        },
    )


async def _host_watchers_example_run(
    *,
    capability_service: object | None = None,
    environment_service: object | None = None,
    config: dict[str, Any] | None = None,
) -> InstallTemplateExampleRunRecord:
    started_at = _utc_now()
    normalized_config = dict(config or {})
    watcher_family = _string_value(normalized_config.get("watcher_family")) or "downloads"
    requested_session_mount_id = _string_value(normalized_config.get("session_mount_id"))
    runtime_context = _cooperative_template_runtime_context(
        "host-watchers",
        environment_service=environment_service,
        session_mount_id=requested_session_mount_id,
    )
    support = _cooperative_template_support(runtime_context)
    operations = ["resolve-runtime-context"]
    if not _mount_enabled(capability_service, "system:host_watchers_runtime"):
        return _install_template_error_record(
            template_id="host-watchers",
            started_at=started_at,
            summary="Host watchers runtime is disabled or unavailable",
            operations=["check-capability-state"],
            support=support,
            code="capability-disabled",
            detail="Enable system:host_watchers_runtime before reading the watcher runtime.",
            retryable=True,
            source="capability",
        )
    if environment_service is None:
        return _install_template_error_record(
            template_id="host-watchers",
            started_at=started_at,
            summary="EnvironmentService runtime projection is unavailable",
            operations=operations,
            support=support,
            code="environment-service-missing",
            detail="Example run requires the canonical EnvironmentService facade to resolve watcher state.",
            retryable=True,
            source="environment-service",
        )
    if runtime_context["session_mount_id"] is None:
        return _install_template_error_record(
            template_id="host-watchers",
            started_at=started_at,
            summary="No watcher session is currently mounted",
            operations=operations,
            support=support,
            code="runtime-unavailable",
            detail="Mount a session with watcher metadata through EnvironmentService before running this example.",
            retryable=True,
            source="environment-service",
        )
    runtime = _cooperative_runtime_snapshot(
        "host-watchers",
        environment_service=environment_service,
        runtime_context=runtime_context,
    )
    operations.append("read-host-watchers-snapshot")
    snapshot = dict(runtime.get("host_watchers") or {})
    watchers = dict(snapshot.get("watchers") or {})
    family_key = "downloads" if watcher_family == "downloads" else watcher_family
    family_snapshot = watchers.get(family_key)
    available = None
    if isinstance(family_snapshot, dict):
        available = _bool_value(family_snapshot.get("available"))
    available_families = _string_list_value(snapshot.get("available_families"))
    if available is not True:
        return _install_template_error_record(
            template_id="host-watchers",
            started_at=started_at,
            summary=f"Watcher family '{watcher_family}' is not currently available",
            operations=operations,
            runtime=runtime,
            support=support,
            code="adapter-unavailable",
            detail=str(
                snapshot.get("adapter_gap_or_blocker")
                or f"Available families: {', '.join(available_families) or 'none'}"
            ),
            retryable=True,
            source="environment-service",
        )
    finished_at = _utc_now()
    return InstallTemplateExampleRunRecord(
        template_id="host-watchers",
        status="success",
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
        summary="Host watcher runtime projection is healthy",
        operations=operations,
        runtime=runtime,
        support=support,
        payload={
            "session_mount_id": runtime_context["session_mount_id"],
            "environment_id": runtime_context["environment_id"],
            "watcher_family": watcher_family,
            "available_families": available_families,
        },
    )


async def _windows_app_adapters_example_run(
    *,
    capability_service: object | None = None,
    environment_service: object | None = None,
    config: dict[str, Any] | None = None,
) -> InstallTemplateExampleRunRecord:
    started_at = _utc_now()
    normalized_config = dict(config or {})
    expected_adapter_ref = _string_value(normalized_config.get("adapter_ref"))
    requested_session_mount_id = _string_value(normalized_config.get("session_mount_id"))
    runtime_context = _cooperative_template_runtime_context(
        "windows-app-adapters",
        environment_service=environment_service,
        session_mount_id=requested_session_mount_id,
    )
    support = _cooperative_template_support(runtime_context)
    operations = ["resolve-runtime-context"]
    if not _mount_enabled(capability_service, "system:windows_app_adapter_runtime"):
        return _install_template_error_record(
            template_id="windows-app-adapters",
            started_at=started_at,
            summary="Windows app adapter runtime is disabled or unavailable",
            operations=["check-capability-state"],
            support=support,
            code="capability-disabled",
            detail="Enable system:windows_app_adapter_runtime before reading the Windows app adapter runtime.",
            retryable=True,
            source="capability",
        )
    if environment_service is None:
        return _install_template_error_record(
            template_id="windows-app-adapters",
            started_at=started_at,
            summary="EnvironmentService runtime projection is unavailable",
            operations=operations,
            support=support,
            code="environment-service-missing",
            detail="Example run requires the canonical EnvironmentService facade to resolve Windows app adapter state.",
            retryable=True,
            source="environment-service",
        )
    if runtime_context["session_mount_id"] is None:
        return _install_template_error_record(
            template_id="windows-app-adapters",
            started_at=started_at,
            summary="No Windows app adapter session is currently mounted",
            operations=operations,
            support=support,
            code="runtime-unavailable",
            detail="Mount a desktop session with app adapter metadata through EnvironmentService before running this example.",
            retryable=True,
            source="environment-service",
        )
    runtime = _cooperative_runtime_snapshot(
        "windows-app-adapters",
        environment_service=environment_service,
        runtime_context=runtime_context,
    )
    operations.append("read-windows-app-adapter-snapshot")
    snapshot = dict(runtime.get("windows_app_adapters") or {})
    adapters = dict(snapshot.get("windows_app_adapters") or {})
    adapter_refs = _string_list_value(adapters.get("adapter_refs"))
    if not adapter_refs:
        return _install_template_error_record(
            template_id="windows-app-adapters",
            started_at=started_at,
            summary="No Windows app adapter is currently available",
            operations=operations,
            runtime=runtime,
            support=support,
            code="adapter-unavailable",
            detail=str(
                snapshot.get("adapter_gap_or_blocker")
                or "The runtime projection does not currently expose any Windows app adapter refs."
            ),
            retryable=True,
            source="environment-service",
        )
    if expected_adapter_ref is not None and expected_adapter_ref not in set(adapter_refs):
        return _install_template_error_record(
            template_id="windows-app-adapters",
            started_at=started_at,
            summary=f"Windows app adapter '{expected_adapter_ref}' is not currently mounted",
            operations=operations,
            runtime=runtime,
            support=support,
            code="adapter-mismatch",
            detail=f"Available adapter refs: {', '.join(adapter_refs)}",
            retryable=True,
            source="environment-service",
        )
    finished_at = _utc_now()
    return InstallTemplateExampleRunRecord(
        template_id="windows-app-adapters",
        status="success",
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
        summary="Windows app adapter runtime projection is healthy",
        operations=operations,
        runtime=runtime,
        support=support,
        payload={
            "session_mount_id": runtime_context["session_mount_id"],
            "environment_id": runtime_context["environment_id"],
            "adapter_refs": adapter_refs,
            "app_identity": adapters.get("app_identity"),
            "control_channel": adapters.get("control_channel"),
        },
    )
