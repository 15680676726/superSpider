# -*- coding: utf-8 -*-
from __future__ import annotations

import json

from copaw.capabilities.models import CapabilityMount


class _FakeRuntimeProviderFacade:
    def __init__(self, *, contract: dict[str, object] | None = None, error: Exception | None = None) -> None:
        self._contract = dict(contract or {})
        self._error = error

    def resolve_runtime_provider_contract(self) -> dict[str, object]:
        if self._error is not None:
            raise self._error
        return dict(self._contract)


def _build_mount(*, mode: str = "environment") -> CapabilityMount:
    return CapabilityMount(
        id="adapter:openspace",
        name="openspace",
        summary="Governed external adapter compiled into formal CoPaw business actions.",
        kind="adapter",
        source_kind="adapter",
        risk_level="guarded",
        provider_ref="github",
        metadata={
            "provider_injection_mode": mode,
            "execution_envelope": {
                "action_timeout_sec": 180,
                "probe_timeout_sec": 15,
                "max_retries": 2,
                "retry_backoff_policy": "exponential",
            },
            "host_compatibility_requirements": {
                "required_provider_contract_kind": "cooperative_provider_runtime",
            },
        },
    )


def _resolved_runtime_contract() -> dict[str, object]:
    return {
        "provider_id": "openai",
        "provider_name": "OpenAI",
        "model": "gpt-5.2",
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-test-secret",
        "auth_mode": "api_key",
        "provenance": {
            "resolution_reason": "Using configured active model.",
            "fallback_applied": False,
            "unavailable_candidates": [],
        },
    }


def test_resolve_donor_provider_contract_uses_runtime_provider_facade_truth() -> None:
    from copaw.capabilities.donor_provider_injection import (
        resolve_donor_provider_contract,
    )

    resolved = resolve_donor_provider_contract(
        mount=_build_mount(),
        provider_runtime_facade=_FakeRuntimeProviderFacade(
            contract=_resolved_runtime_contract(),
        ),
    )

    assert resolved["provider_resolution_status"] == "resolved"
    assert resolved["provider_contract_kind"] == "cooperative_provider_runtime"
    assert resolved["provider_id"] == "openai"
    assert resolved["provider_name"] == "OpenAI"
    assert resolved["model"] == "gpt-5.2"
    assert resolved["provider_id"] != _build_mount().provider_ref


def test_build_donor_injection_payload_supports_environment_mode_and_masks_secrets() -> None:
    from copaw.capabilities.donor_provider_injection import (
        build_donor_injection_payload,
        resolve_donor_provider_contract,
    )

    resolved = resolve_donor_provider_contract(
        mount=_build_mount(mode="environment"),
        provider_runtime_facade=_FakeRuntimeProviderFacade(
            contract=_resolved_runtime_contract(),
        ),
    )

    payload = build_donor_injection_payload(provider_contract=resolved)

    assert payload["mode"] == "environment"
    assert payload["env"]["COPAW_PROVIDER_ID"] == "openai"
    assert payload["env"]["COPAW_PROVIDER_API_KEY"] == "sk-test-secret"
    assert payload["operator_payload"]["env"]["COPAW_PROVIDER_API_KEY"] != "sk-test-secret"
    assert payload["operator_payload"]["provider"]["provider_id"] == "openai"
    assert payload["operator_payload"]["provider"]["model"] == "gpt-5.2"


def test_build_donor_injection_payload_supports_argument_mode() -> None:
    from copaw.capabilities.donor_provider_injection import (
        build_donor_injection_payload,
        resolve_donor_provider_contract,
    )

    resolved = resolve_donor_provider_contract(
        mount=_build_mount(mode="argument"),
        provider_runtime_facade=_FakeRuntimeProviderFacade(
            contract=_resolved_runtime_contract(),
        ),
    )

    payload = build_donor_injection_payload(provider_contract=resolved)

    assert payload["mode"] == "argument"
    assert "--copaw-provider-id" in payload["args"]
    assert "--copaw-provider-api-key" in payload["args"]
    assert "sk-test-secret" in payload["args"]
    assert "sk-test-secret" not in json.dumps(
        payload["operator_payload"],
        ensure_ascii=False,
    )


def test_build_donor_injection_payload_supports_config_wrapper_modes() -> None:
    from copaw.capabilities.donor_provider_injection import (
        build_donor_injection_payload,
        resolve_donor_provider_contract,
    )

    resolved = resolve_donor_provider_contract(
        mount=_build_mount(mode="startup_wrapper"),
        provider_runtime_facade=_FakeRuntimeProviderFacade(
            contract=_resolved_runtime_contract(),
        ),
    )

    payload = build_donor_injection_payload(provider_contract=resolved)

    assert payload["mode"] == "config_wrapper"
    assert payload["config_wrapper"]["provider"]["provider_id"] == "openai"
    assert (
        payload["config_wrapper"]["provider"]["credentials"]["api_key"]
        == "sk-test-secret"
    )
    assert (
        payload["operator_payload"]["config_wrapper"]["provider"]["credentials"]["api_key"]
        != "sk-test-secret"
    )


def test_missing_provider_contract_returns_typed_provider_resolution_failure() -> None:
    from copaw.capabilities.donor_provider_injection import (
        build_donor_injection_payload,
        resolve_donor_provider_contract,
    )

    resolved = resolve_donor_provider_contract(
        mount=_build_mount(),
        provider_runtime_facade=_FakeRuntimeProviderFacade(
            error=ValueError("No active or fallback model configured."),
        ),
    )
    payload = build_donor_injection_payload(provider_contract=resolved)

    assert resolved["provider_resolution_status"] == "failed"
    assert resolved["error_type"] == "provider_resolution_error"
    assert payload["provider_resolution_status"] == "failed"
    assert payload["error_type"] == "provider_resolution_error"
    assert payload["env"] == {}
    assert payload["args"] == []
    assert payload["config_wrapper"] == {}


def test_build_sidecar_provider_injection_payload_applies_system_model_override() -> None:
    import copaw.capabilities.donor_provider_injection as provider_injection_module

    builder = getattr(
        provider_injection_module,
        "build_sidecar_provider_injection_payload",
        None,
    )
    assert builder is not None

    payload = builder(
        provider_runtime_facade=_FakeRuntimeProviderFacade(
            contract=_resolved_runtime_contract(),
        ),
        model_ref="gpt-5-codex",
    )

    assert payload["provider_resolution_status"] == "resolved"
    assert payload["env"]["COPAW_PROVIDER_MODEL"] == "gpt-5-codex"
    assert payload["env"]["COPAW_PROVIDER_API_KEY"] == "sk-test-secret"
