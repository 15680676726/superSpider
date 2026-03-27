# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.kernel.query_execution import KernelQueryExecutionService


def test_resident_agent_signature_changes_when_runtime_model_fingerprint_changes(
    monkeypatch,
) -> None:
    service = KernelQueryExecutionService(session_backend=object())

    monkeypatch.setattr(
        "copaw.agents.model_factory.build_runtime_model_fingerprint",
        lambda: "fingerprint-a",
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
        lambda: "fingerprint-b",
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

