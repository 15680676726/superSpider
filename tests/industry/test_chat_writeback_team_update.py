import asyncio
from types import SimpleNamespace

from copaw.industry.models import IndustryRoleBlueprint
from copaw.industry.service_lifecycle import _IndustryLifecycleMixin
from copaw.state.models_industry import IndustryInstanceRecord


class _FakeDispatcher:
    def __init__(self) -> None:
        self.submitted = None

    def submit(self, task):
        self.submitted = task
        return SimpleNamespace(
            phase="executing",
            success=True,
            summary="submitted",
            decision_request_id=None,
            output={"success": True, "summary": "ok"},
        )

    async def execute_task(self, task_id: str):
        _ = task_id
        return SimpleNamespace(
            phase="completed",
            success=True,
            summary="completed",
            decision_request_id=None,
            output={"success": True, "summary": "ok"},
        )


class _Harness:
    _submit_chat_writeback_team_update = (
        _IndustryLifecycleMixin._submit_chat_writeback_team_update
    )

    def __init__(self, dispatcher: _FakeDispatcher) -> None:
        self._dispatcher = dispatcher

    def _get_industry_kernel_dispatcher(self):
        return self._dispatcher

    def _chat_writeback_control_thread_id(
        self,
        *,
        instance_id: str,
        session_id: str | None,
    ) -> str:
        return session_id or f"industry-chat:{instance_id}:execution-core"


def test_submit_chat_writeback_team_update_disables_auto_dispatch() -> None:
    dispatcher = _FakeDispatcher()
    harness = _Harness(dispatcher)
    role = IndustryRoleBlueprint(
        role_id="temporary-local-ops-worker",
        agent_id="agent-temp",
        name="Temp Worker",
        role_name="临时执行位",
        role_summary="负责本地文件/桌面执行。",
        mission="完成本地执行任务。",
        goal_kind="temporary-local-ops-worker",
        agent_class="business",
        employment_mode="temporary",
        activation_mode="on-demand",
        suspendable=True,
        risk_level="guarded",
        environment_constraints=["desktop"],
        allowed_capabilities=[],
        evidence_expectations=["result"],
    )
    record = IndustryInstanceRecord(
        instance_id="industry:test",
        label="Test",
        owner_scope="buddy:test",
    )

    asyncio.run(
        harness._submit_chat_writeback_team_update(
            record=record,
            role=role,
            owner_agent_id="copaw-agent-runner",
            session_id="thread-1",
            risk_level="guarded",
            human_confirmation_required=False,
        ),
    )

    assert dispatcher.submitted is not None
    assert dispatcher.submitted.payload["auto_dispatch"] is False
    assert dispatcher.submitted.payload["execute"] is False
