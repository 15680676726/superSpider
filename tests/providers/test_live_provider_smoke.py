# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import os

import pytest

from copaw.providers.provider_manager import ModelSlotConfig, ProviderManager


_SMOKE_TOKEN = "COPAW_PROVIDER_SMOKE_OK"


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _provider_ids() -> list[str]:
    raw = os.getenv("COPAW_LIVE_PROVIDER_IDS", "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _model_env_name(provider_id: str) -> str:
    normalized = provider_id.upper().replace("-", "_")
    return f"COPAW_LIVE_PROVIDER_MODEL_{normalized}"


def _timeout_env(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _response_to_text(response: object) -> str:
    content = getattr(response, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
            else:
                text = getattr(block, "text", None)
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
        return "\n".join(parts).strip()
    return ""


async def _materialize_response(response: object) -> object:
    if not hasattr(response, "__aiter__"):
        return response
    last_item: object | None = None
    async for item in response:  # type: ignore[misc]
        last_item = item
    return last_item if last_item is not None else response


async def _run_generation_round_trip(
    *,
    manager: ProviderManager,
    provider_id: str,
    model_id: str,
    timeout_seconds: float,
) -> str:
    chat_model = manager.build_chat_model_for_slot(
        ModelSlotConfig(provider_id=provider_id, model=model_id),
    )
    response = await asyncio.wait_for(
        chat_model(
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Reply with only this token and nothing else: "
                        f"{_SMOKE_TOKEN}"
                    ),
                },
            ],
        ),
        timeout=timeout_seconds,
    )
    materialized = await asyncio.wait_for(
        _materialize_response(response),
        timeout=timeout_seconds,
    )
    return _response_to_text(materialized)


def test_live_provider_smoke_response_to_text_accepts_string_content() -> None:
    response = type("Response", (), {"content": f" {_SMOKE_TOKEN} "})()

    assert _response_to_text(response) == _SMOKE_TOKEN


def test_live_provider_smoke_response_to_text_accepts_block_content() -> None:
    response = type(
        "Response",
        (),
        {
            "content": [
                {"type": "text", "text": "alpha"},
                type("Block", (), {"text": "beta"})(),
                {"type": "tool_use", "id": "ignored"},
            ],
        },
    )()

    assert _response_to_text(response) == "alpha\nbeta"


@pytest.mark.skipif(
    not _env_flag("COPAW_RUN_LIVE_PROVIDER_SMOKE"),
    reason="Set COPAW_RUN_LIVE_PROVIDER_SMOKE=1 to run live provider smoke coverage.",
)
async def test_live_provider_connection_and_model_round_trip() -> None:
    provider_ids = _provider_ids()
    if not provider_ids:
        pytest.skip("Set COPAW_LIVE_PROVIDER_IDS to one or more configured providers.")

    manager = ProviderManager.get_instance()
    connection_timeout = _timeout_env(
        "COPAW_LIVE_PROVIDER_CONNECTION_TIMEOUT_SECONDS",
        10.0,
    )
    discover_timeout = _timeout_env(
        "COPAW_LIVE_PROVIDER_DISCOVER_TIMEOUT_SECONDS",
        15.0,
    )
    model_timeout = _timeout_env(
        "COPAW_LIVE_PROVIDER_MODEL_TIMEOUT_SECONDS",
        20.0,
    )
    generation_timeout = _timeout_env(
        "COPAW_LIVE_PROVIDER_GENERATION_TIMEOUT_SECONDS",
        45.0,
    )

    for provider_id in provider_ids:
        provider = manager.get_provider(provider_id)
        assert provider is not None, f"Provider '{provider_id}' is not configured"

        ok = await provider.check_connection(timeout=connection_timeout)
        assert ok is True, f"Provider '{provider_id}' connection check failed"

        models = await provider.fetch_models(timeout=discover_timeout)
        explicit_model = os.getenv(_model_env_name(provider_id), "").strip()
        model_id = explicit_model or (models[0].id if models else "")
        if not model_id:
            pytest.fail(
                (
                    f"Provider '{provider_id}' returned no models. "
                    f"Set {_model_env_name(provider_id)} to an explicit model id."
                ),
            )

        model_ok = await provider.check_model_connection(model_id, timeout=model_timeout)
        assert model_ok is True, (
            f"Provider '{provider_id}' could not run model '{model_id}'"
        )
        response_text = await _run_generation_round_trip(
            manager=manager,
            provider_id=provider_id,
            model_id=model_id,
            timeout_seconds=generation_timeout,
        )
        assert response_text, (
            f"Provider '{provider_id}' returned an empty generation for '{model_id}'"
        )
        assert _SMOKE_TOKEN.lower() in response_text.lower(), (
            f"Provider '{provider_id}' generated an unexpected response for "
            f"'{model_id}': {response_text!r}"
        )
