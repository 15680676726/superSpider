# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.kernel.query_execution import KernelQueryExecutionService


def test_resident_agent_signature_passes_runtime_provider_to_fingerprint_builder(
    monkeypatch,
) -> None:
    runtime_provider = object()
    service = KernelQueryExecutionService(
        session_backend=object(),
        provider_manager=runtime_provider,
    )
    captured: dict[str, object] = {}

    def _build_runtime_model_fingerprint(*, runtime_provider=None) -> str:
        captured["runtime_provider"] = runtime_provider
        return "fingerprint-a"

    monkeypatch.setattr(
        "copaw.agents.model_factory.build_runtime_model_fingerprint",
        _build_runtime_model_fingerprint,
    )
    service._resident_agent_signature(  # type: ignore[attr-defined]
        owner_agent_id="agent-1",
        actor_key=None,
        actor_fingerprint=None,
        prompt_appendix=None,
        tool_capability_ids={"tool:a"},
        skill_names={"skill:a"},
        mcp_client_keys=["mcp:a"],
        system_capability_ids={"system:a"},
    )

    assert captured["runtime_provider"] is runtime_provider


def test_resident_agent_signature_changes_when_runtime_model_fingerprint_changes(
    monkeypatch,
) -> None:
    service = KernelQueryExecutionService(session_backend=object())

    monkeypatch.setattr(
        "copaw.agents.model_factory.build_runtime_model_fingerprint",
        lambda **_: "fingerprint-a",
    )
    sig_a = service._resident_agent_signature(  # type: ignore[attr-defined]
        owner_agent_id="agent-1",
        actor_key=None,
        actor_fingerprint=None,
        prompt_appendix=None,
        tool_capability_ids={"tool:a"},
        skill_names={"skill:a"},
        mcp_client_keys=["mcp:a"],
        system_capability_ids={"system:a"},
    )

    monkeypatch.setattr(
        "copaw.agents.model_factory.build_runtime_model_fingerprint",
        lambda **_: "fingerprint-b",
    )
    sig_b = service._resident_agent_signature(  # type: ignore[attr-defined]
        owner_agent_id="agent-1",
        actor_key=None,
        actor_fingerprint=None,
        prompt_appendix=None,
        tool_capability_ids={"tool:a"},
        skill_names={"skill:a"},
        mcp_client_keys=["mcp:a"],
        system_capability_ids={"system:a"},
    )

    assert sig_a != sig_b
