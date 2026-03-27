# -*- coding: utf-8 -*-
from __future__ import annotations

from agentscope.message import Msg

from copaw.kernel.main_brain_intake import resolve_main_brain_intake_contract_sync
from copaw.kernel.query_execution_confirmation import (
    build_query_resume_request,
    runtime_decision_actions,
)
from copaw.kernel.query_execution_writeback import (
    build_chat_writeback_plan_from_model_decision,
)


class _FakeDecision:
    def __init__(self) -> None:
        self.approved_targets = ["backlog"]
        self.strategy = None
        self.goal = type(
            "GoalPayload",
            (),
            {
                "title": None,
                "summary": "月入10万且零亏损",
                "plan_steps": [],
            },
        )()
        self.schedule = None


def test_runtime_decision_actions_stay_aligned_with_runtime_center() -> None:
    assert runtime_decision_actions("decision-1", status="open") == {
        "review": "/api/runtime-center/decisions/decision-1/review",
        "approve": "/api/runtime-center/decisions/decision-1/approve",
        "reject": "/api/runtime-center/decisions/decision-1/reject",
    }
    assert runtime_decision_actions("decision-1", status="reviewing") == {
        "approve": "/api/runtime-center/decisions/decision-1/approve",
        "reject": "/api/runtime-center/decisions/decision-1/reject",
    }


def test_build_query_resume_request_preserves_runtime_context() -> None:
    request = build_query_resume_request(
        request_context={
            "session_id": "session-1",
            "user_id": "operator-1",
            "channel": "console",
            "industry_instance_id": "industry-1",
            "industry_role_id": "customer-support",
            "session_kind": "industry-control-thread",
        },
        owner_agent_id="agent-1",
    )

    assert request.session_id == "session-1"
    assert request.user_id == "operator-1"
    assert request.channel == "console"
    assert request.industry_instance_id == "industry-1"
    assert request.industry_role_id == "customer-support"
    assert request.session_kind == "industry-control-thread"


def test_build_chat_writeback_plan_from_model_decision_still_structures_fuzzy_goal() -> None:
    plan = build_chat_writeback_plan_from_model_decision(
        text="月入10万且零亏损",
        decision=_FakeDecision(),
    )

    assert plan is not None
    assert plan.goal is not None
    assert plan.goal.title == "月度收益目标校准"
    assert "目标结果：月入10万且零亏损" in plan.goal.summary
    assert plan.goal.plan_steps


def test_main_brain_intake_sync_keeps_formal_execution_resolution_alive() -> None:
    contract = resolve_main_brain_intake_contract_sync(
        msgs=[Msg(name="user", role="user", content="确认继续，帮我把这个目标推进下去")],
    )

    assert contract is not None
    assert contract.intent_kind == "execute-task"
    assert contract.should_kickoff is True
    assert contract.should_route_to_orchestrate is True
