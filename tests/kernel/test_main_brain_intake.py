# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

import pytest
from agentscope.message import Msg

from copaw.kernel.main_brain_intake import (
    MainBrainIntakeContract,
    resolve_request_main_brain_intake_contract,
)


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
