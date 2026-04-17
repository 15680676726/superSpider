# -*- coding: utf-8 -*-
from __future__ import annotations
from types import SimpleNamespace

import pytest
from agentscope.message import Msg

from copaw.kernel.main_brain_intake import (
    MainBrainIntakeContract,
    resolve_main_brain_intake_contract,
    resolve_request_main_brain_intake_contract,
)
from copaw.kernel import query_execution_writeback as writeback_module


@pytest.mark.asyncio
async def test_request_main_brain_intake_contract_materializes_writeback_from_requested_actions():
    request = SimpleNamespace(
        requested_actions=["writeback_backlog"],
    )
    msgs = [
        Msg(
            name="user",
            role="user",
            content="把这条需求写回 backlog，后续继续推进。",
        )
    ]

    contract = await resolve_request_main_brain_intake_contract(
        request=request,
        msgs=msgs,
    )

    assert contract is not None
    assert contract.message_text == "把这条需求写回 backlog，后续继续推进。"
    assert contract.writeback_requested is True
    assert contract.has_active_writeback_plan is True
    assert contract.writeback_plan is not None
    assert contract.writeback_plan.classifications == ["strategy", "backlog"]
    assert contract.should_route_to_orchestrate is True


@pytest.mark.asyncio
async def test_request_main_brain_intake_contract_prefers_attached_contract():
    attached = MainBrainIntakeContract(
        message_text="attached",
        decision=None,
        intent_kind="execute-task",
        writeback_requested=True,
        writeback_plan=SimpleNamespace(active=True, classifications=["strategy", "backlog"]),
        should_kickoff=True,
    )
    request = SimpleNamespace(
        requested_actions=["writeback_backlog"],
        _copaw_main_brain_intake_contract=attached,
    )

    contract = await resolve_request_main_brain_intake_contract(
        request=request,
        msgs=[Msg(name="user", role="user", content="ignored")],
    )

    assert contract is attached


@pytest.mark.asyncio
async def test_request_main_brain_intake_contract_materializes_explicit_orchestrate_backlog_writeback():
    contract = await resolve_request_main_brain_intake_contract(
        request=SimpleNamespace(interaction_mode="orchestrate"),
        msgs=[
            Msg(
                name="user",
                role="user",
                content=(
                    "Delegate this to the right specialist and write it back "
                    "into the formal backlog before execution."
                ),
            ),
        ],
    )

    assert contract is not None
    assert contract.writeback_requested is True
    assert contract.has_active_writeback_plan is True
    assert contract.should_kickoff is False
    assert contract.should_route_to_orchestrate is True


class _FakeStructuredDecisionModel:
    stream = False

    async def __call__(self, *, messages, structured_model=None, **kwargs):
        _ = (messages, kwargs)
        assert structured_model is not None
        return SimpleNamespace(
            metadata=structured_model(
                intent_kind="execute-task",
                intent_confidence=0.98,
                intent_signals=["model-actionable"],
                should_writeback=True,
                approved_targets=["backlog"],
                kickoff_allowed=True,
                confidence=0.98,
                rationale="model-driven",
            ),
        )


@pytest.mark.asyncio
async def test_main_brain_intake_contract_for_content_creation_request_keeps_writeback_and_kickoff(
    monkeypatch,
):
    writeback_module.clear_chat_writeback_decision_cache()
    monkeypatch.setattr(
        writeback_module,
        "_CHAT_WRITEBACK_DECISION_MODEL_FACTORY",
        lambda: _FakeStructuredDecisionModel(),
        raising=False,
    )

    contract = await resolve_main_brain_intake_contract(
        text="现在去写一篇短篇小说，保存成实际文件，并完成后主动告诉我结果。",
    )

    assert contract is not None
    assert contract.intent_kind == "execute-task"
    assert contract.writeback_requested is True
    assert contract.has_active_writeback_plan is True
    assert contract.should_kickoff is True
    assert contract.should_route_to_orchestrate is True


@pytest.mark.asyncio
async def test_main_brain_intake_contract_raises_when_decision_model_is_unavailable(
    monkeypatch,
):
    writeback_module.clear_chat_writeback_decision_cache()
    monkeypatch.setattr(
        writeback_module,
        "_CHAT_WRITEBACK_DECISION_MODEL_FACTORY",
        lambda: None,
        raising=False,
    )

    with pytest.raises(RuntimeError, match="unavailable"):
        await resolve_main_brain_intake_contract(
            text="现在去写一篇短篇小说，保存成实际文件，完成后主动告诉我结果。",
        )
