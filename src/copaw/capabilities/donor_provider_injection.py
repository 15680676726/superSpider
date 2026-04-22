# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .external_adapter_contracts import (
    donor_execution_envelope_from_metadata,
    host_compatibility_requirements_from_metadata,
    normalize_provider_injection_mode,
)
from .models import CapabilityMount


_CONFIG_WRAPPER_ENV_KEY = "COPAW_DONOR_PROVIDER_CONTRACT_JSON"
_SECRET_ENV_KEYS = {"COPAW_PROVIDER_API_KEY"}
_SECRET_ARG_FLAGS = {"--copaw-provider-api-key"}


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _mask_secret(value: str) -> str:
    if not value:
        return value
    if len(value) <= 8:
        return "*" * len(value)
    prefix_len = 3 if len(value) > 2 and value[2] == "-" else 2
    prefix = value[:prefix_len]
    suffix = value[-4:]
    masked_len = max(len(value) - prefix_len - 4, 4)
    return f"{prefix}{'*' * masked_len}{suffix}"


def _mask_mapping(payload: Mapping[str, object] | None) -> dict[str, object]:
    if not isinstance(payload, Mapping):
        return {}
    masked: dict[str, object] = {}
    for key, value in payload.items():
        text = _string(value)
        if text is None:
            masked[str(key)] = value
            continue
        masked[str(key)] = _mask_secret(text) if str(key) in _SECRET_ENV_KEYS else text
    return masked


def _mask_args(args: list[str]) -> list[str]:
    masked: list[str] = []
    secret_next = False
    for item in args:
        if secret_next:
            masked.append(_mask_secret(str(item)))
            secret_next = False
            continue
        if item in _SECRET_ARG_FLAGS:
            masked.append(item)
            secret_next = True
            continue
        if item.startswith("--copaw-provider-api-key="):
            prefix, _, value = item.partition("=")
            masked.append(f"{prefix}={_mask_secret(value)}")
            continue
        masked.append(str(item))
    return masked


def _masked_config_wrapper(wrapper: Mapping[str, object] | None) -> dict[str, object]:
    if not isinstance(wrapper, Mapping):
        return {}
    provider = dict(wrapper.get("provider") or {})
    credentials = dict(provider.get("credentials") or {})
    api_key = _string(credentials.get("api_key"))
    if api_key is not None:
        credentials["api_key"] = _mask_secret(api_key)
    if credentials:
        provider["credentials"] = credentials
    masked = dict(wrapper)
    if provider:
        masked["provider"] = provider
    return masked


def _provider_resolution_failure(
    *,
    provider_injection_mode: str | None,
    provider_contract_kind: str | None,
    error: str,
) -> dict[str, Any]:
    return {
        "required": True,
        "provider_resolution_status": "failed",
        "provider_injection_mode": provider_injection_mode,
        "provider_contract_kind": provider_contract_kind,
        "error_type": "provider_resolution_error",
        "error": error,
    }


def resolve_donor_provider_contract(
    *,
    mount: CapabilityMount,
    provider_runtime_facade: object | None,
) -> dict[str, Any]:
    metadata = dict(mount.metadata or {})
    provider_injection_mode = normalize_provider_injection_mode(
        metadata.get("provider_injection_mode"),
    )
    compatibility = host_compatibility_requirements_from_metadata(metadata)
    provider_contract_kind = _string(
        getattr(compatibility, "required_provider_contract_kind", None),
    )
    if provider_injection_mode in {None, "none"} or provider_contract_kind is None:
        return {
            "required": False,
            "provider_resolution_status": "not_required",
            "provider_injection_mode": provider_injection_mode,
            "provider_contract_kind": provider_contract_kind,
            "error_type": None,
            "error": None,
        }
    if provider_contract_kind != "cooperative_provider_runtime":
        return _provider_resolution_failure(
            provider_injection_mode=provider_injection_mode,
            provider_contract_kind=provider_contract_kind,
            error=(
                f"Unsupported provider contract kind '{provider_contract_kind}' for donor injection."
            ),
        )
    if provider_runtime_facade is None:
        return _provider_resolution_failure(
            provider_injection_mode=provider_injection_mode,
            provider_contract_kind=provider_contract_kind,
            error="runtime_provider facade is not attached to donor execution.",
        )
    resolve_runtime_provider_contract = getattr(
        provider_runtime_facade,
        "resolve_runtime_provider_contract",
        None,
    )
    if not callable(resolve_runtime_provider_contract):
        return _provider_resolution_failure(
            provider_injection_mode=provider_injection_mode,
            provider_contract_kind=provider_contract_kind,
            error="runtime_provider facade does not expose resolve_runtime_provider_contract().",
        )
    try:
        runtime_contract = dict(resolve_runtime_provider_contract() or {})
    except Exception as exc:
        return _provider_resolution_failure(
            provider_injection_mode=provider_injection_mode,
            provider_contract_kind=provider_contract_kind,
            error=str(exc),
        )

    execution_envelope = donor_execution_envelope_from_metadata(metadata)
    timeout_policy = {
        "action_timeout_sec": (
            execution_envelope.action_timeout_sec if execution_envelope is not None else 120
        ),
        "probe_timeout_sec": (
            execution_envelope.probe_timeout_sec if execution_envelope is not None else 10
        ),
    }
    retry_policy = {
        "max_retries": execution_envelope.max_retries if execution_envelope is not None else 0,
        "retry_backoff_policy": (
            execution_envelope.retry_backoff_policy
            if execution_envelope is not None
            else "none"
        ),
    }
    credentials: dict[str, str] = {}
    api_key = _string(runtime_contract.get("api_key"))
    if api_key is not None:
        credentials["api_key"] = api_key
    return {
        "required": True,
        "provider_resolution_status": "resolved",
        "provider_injection_mode": provider_injection_mode,
        "provider_contract_kind": provider_contract_kind,
        "provider_id": _string(runtime_contract.get("provider_id")),
        "provider_name": _string(runtime_contract.get("provider_name")),
        "model": _string(runtime_contract.get("model")),
        "base_url": _string(runtime_contract.get("base_url")),
        "auth_mode": _string(runtime_contract.get("auth_mode")) or "none",
        "credentials": credentials,
        "extra_headers": dict(runtime_contract.get("extra_headers") or {}),
        "timeout_policy": timeout_policy,
        "retry_policy": retry_policy,
        "provenance": dict(runtime_contract.get("provenance") or {}),
        "error_type": None,
        "error": None,
    }


def resolve_sidecar_provider_contract(
    *,
    provider_runtime_facade: object | None,
    model_ref: str | None = None,
    provider_injection_mode: str | None = "environment",
) -> dict[str, Any]:
    normalized_mode = normalize_provider_injection_mode(provider_injection_mode)
    provider_contract_kind = "cooperative_provider_runtime"
    if normalized_mode in {None, "none"}:
        return {
            "required": False,
            "provider_resolution_status": "not_required",
            "provider_injection_mode": normalized_mode,
            "provider_contract_kind": provider_contract_kind,
            "error_type": None,
            "error": None,
        }
    if provider_runtime_facade is None:
        return _provider_resolution_failure(
            provider_injection_mode=normalized_mode,
            provider_contract_kind=provider_contract_kind,
            error="runtime_provider facade is not attached to sidecar execution.",
        )
    resolve_runtime_provider_contract = getattr(
        provider_runtime_facade,
        "resolve_runtime_provider_contract",
        None,
    )
    if not callable(resolve_runtime_provider_contract):
        return _provider_resolution_failure(
            provider_injection_mode=normalized_mode,
            provider_contract_kind=provider_contract_kind,
            error="runtime_provider facade does not expose resolve_runtime_provider_contract().",
        )
    try:
        runtime_contract = dict(resolve_runtime_provider_contract() or {})
    except Exception as exc:
        return _provider_resolution_failure(
            provider_injection_mode=normalized_mode,
            provider_contract_kind=provider_contract_kind,
            error=str(exc),
        )
    effective_model_ref = _string(model_ref) or _string(runtime_contract.get("model"))
    credentials: dict[str, str] = {}
    api_key = _string(runtime_contract.get("api_key"))
    if api_key is not None:
        credentials["api_key"] = api_key
    return {
        "required": True,
        "provider_resolution_status": "resolved",
        "provider_injection_mode": normalized_mode,
        "provider_contract_kind": provider_contract_kind,
        "provider_id": _string(runtime_contract.get("provider_id")),
        "provider_name": _string(runtime_contract.get("provider_name")),
        "model": effective_model_ref,
        "base_url": _string(runtime_contract.get("base_url")),
        "auth_mode": _string(runtime_contract.get("auth_mode")) or "none",
        "credentials": credentials,
        "extra_headers": dict(runtime_contract.get("extra_headers") or {}),
        "timeout_policy": {
            "action_timeout_sec": 120,
            "probe_timeout_sec": 10,
        },
        "retry_policy": {
            "max_retries": 0,
            "retry_backoff_policy": "none",
        },
        "provenance": dict(runtime_contract.get("provenance") or {}),
        "error_type": None,
        "error": None,
    }


def _environment_payload(provider_contract: Mapping[str, Any]) -> dict[str, str]:
    env = {
        "COPAW_PROVIDER_CONTRACT_KIND": str(
            provider_contract.get("provider_contract_kind") or "",
        ),
        "COPAW_PROVIDER_ID": str(provider_contract.get("provider_id") or ""),
        "COPAW_PROVIDER_NAME": str(provider_contract.get("provider_name") or ""),
        "COPAW_PROVIDER_MODEL": str(provider_contract.get("model") or ""),
        "COPAW_PROVIDER_BASE_URL": str(provider_contract.get("base_url") or ""),
        "COPAW_PROVIDER_AUTH_MODE": str(provider_contract.get("auth_mode") or "none"),
        "COPAW_PROVIDER_ACTION_TIMEOUT_SEC": str(
            dict(provider_contract.get("timeout_policy") or {}).get("action_timeout_sec") or "",
        ),
        "COPAW_PROVIDER_PROBE_TIMEOUT_SEC": str(
            dict(provider_contract.get("timeout_policy") or {}).get("probe_timeout_sec") or "",
        ),
        "COPAW_PROVIDER_MAX_RETRIES": str(
            dict(provider_contract.get("retry_policy") or {}).get("max_retries") or "",
        ),
        "COPAW_PROVIDER_RETRY_BACKOFF_POLICY": str(
            dict(provider_contract.get("retry_policy") or {}).get("retry_backoff_policy") or "",
        ),
    }
    api_key = _string(dict(provider_contract.get("credentials") or {}).get("api_key"))
    if api_key is not None:
        env["COPAW_PROVIDER_API_KEY"] = api_key
    return {key: value for key, value in env.items() if value}


def _argument_payload(provider_contract: Mapping[str, Any]) -> list[str]:
    env = _environment_payload(provider_contract)
    mapping = (
        ("COPAW_PROVIDER_CONTRACT_KIND", "--copaw-provider-contract-kind"),
        ("COPAW_PROVIDER_ID", "--copaw-provider-id"),
        ("COPAW_PROVIDER_NAME", "--copaw-provider-name"),
        ("COPAW_PROVIDER_MODEL", "--copaw-provider-model"),
        ("COPAW_PROVIDER_BASE_URL", "--copaw-provider-base-url"),
        ("COPAW_PROVIDER_AUTH_MODE", "--copaw-provider-auth-mode"),
        ("COPAW_PROVIDER_API_KEY", "--copaw-provider-api-key"),
        ("COPAW_PROVIDER_ACTION_TIMEOUT_SEC", "--copaw-provider-action-timeout-sec"),
        ("COPAW_PROVIDER_PROBE_TIMEOUT_SEC", "--copaw-provider-probe-timeout-sec"),
        ("COPAW_PROVIDER_MAX_RETRIES", "--copaw-provider-max-retries"),
        ("COPAW_PROVIDER_RETRY_BACKOFF_POLICY", "--copaw-provider-retry-backoff-policy"),
    )
    args: list[str] = []
    for env_key, arg_key in mapping:
        value = env.get(env_key)
        if value is None:
            continue
        args.extend((arg_key, value))
    return args


def _config_wrapper_payload(provider_contract: Mapping[str, Any]) -> dict[str, object]:
    return {
        "provider": {
            "provider_contract_kind": provider_contract.get("provider_contract_kind"),
            "provider_id": provider_contract.get("provider_id"),
            "provider_name": provider_contract.get("provider_name"),
            "model": provider_contract.get("model"),
            "base_url": provider_contract.get("base_url"),
            "auth_mode": provider_contract.get("auth_mode"),
            "credentials": dict(provider_contract.get("credentials") or {}),
            "extra_headers": dict(provider_contract.get("extra_headers") or {}),
        },
        "timeout_policy": dict(provider_contract.get("timeout_policy") or {}),
        "retry_policy": dict(provider_contract.get("retry_policy") or {}),
        "provenance": dict(provider_contract.get("provenance") or {}),
    }


def build_donor_injection_payload(
    *,
    provider_contract: Mapping[str, Any] | None,
) -> dict[str, Any]:
    resolved_contract = dict(provider_contract or {})
    resolution_status = _string(resolved_contract.get("provider_resolution_status")) or "not_required"
    provider_injection_mode = normalize_provider_injection_mode(
        resolved_contract.get("provider_injection_mode"),
    )
    payload: dict[str, Any] = {
        "provider_resolution_status": resolution_status,
        "mode": None,
        "env": {},
        "args": [],
        "config_wrapper": {},
        "operator_payload": {
            "provider_resolution_status": resolution_status,
            "mode": None,
            "provider": {
                "provider_contract_kind": resolved_contract.get("provider_contract_kind"),
                "provider_id": resolved_contract.get("provider_id"),
                "provider_name": resolved_contract.get("provider_name"),
                "model": resolved_contract.get("model"),
                "base_url": resolved_contract.get("base_url"),
                "auth_mode": resolved_contract.get("auth_mode"),
                "provenance": dict(resolved_contract.get("provenance") or {}),
            },
            "env": {},
            "args": [],
            "config_wrapper": {},
        },
        "error_type": resolved_contract.get("error_type"),
        "error": resolved_contract.get("error"),
    }
    if resolution_status != "resolved" or provider_injection_mode is None:
        return payload

    env = _environment_payload(resolved_contract)
    args = _argument_payload(resolved_contract)
    config_wrapper = _config_wrapper_payload(resolved_contract)
    if provider_injection_mode == "environment":
        payload["mode"] = "environment"
        payload["env"] = env
        payload["operator_payload"]["mode"] = "environment"
        payload["operator_payload"]["env"] = _mask_mapping(env)
    elif provider_injection_mode == "argument":
        payload["mode"] = "argument"
        payload["args"] = args
        payload["operator_payload"]["mode"] = "argument"
        payload["operator_payload"]["args"] = _mask_args(args)
    elif provider_injection_mode in {"config_file_patch", "startup_wrapper"}:
        payload["mode"] = "config_wrapper"
        payload["config_wrapper"] = config_wrapper
        payload["operator_payload"]["mode"] = "config_wrapper"
        payload["operator_payload"]["config_wrapper"] = _masked_config_wrapper(
            config_wrapper,
        )
    return payload


def build_sidecar_provider_injection_payload(
    *,
    provider_runtime_facade: object | None,
    model_ref: str | None = None,
    provider_injection_mode: str | None = "environment",
) -> dict[str, Any]:
    resolved = resolve_sidecar_provider_contract(
        provider_runtime_facade=provider_runtime_facade,
        model_ref=model_ref,
        provider_injection_mode=provider_injection_mode,
    )
    return build_donor_injection_payload(provider_contract=resolved)


__all__ = [
    "build_sidecar_provider_injection_payload",
    "build_donor_injection_payload",
    "resolve_sidecar_provider_contract",
    "resolve_donor_provider_contract",
    "_CONFIG_WRAPPER_ENV_KEY",
]
