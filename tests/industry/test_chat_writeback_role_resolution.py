from __future__ import annotations

from copaw.industry.identity import EXECUTION_CORE_ROLE_ID
from copaw.industry.models import IndustryRoleBlueprint, IndustryTeamBlueprint
from copaw.industry.service_strategy import _IndustryStrategyMixin
from copaw.state.models_industry import IndustryInstanceRecord


def _role(
    *,
    role_id: str,
    agent_id: str,
    role_name: str,
    allowed_capabilities: list[str] | None = None,
) -> IndustryRoleBlueprint:
    return IndustryRoleBlueprint(
        role_id=role_id,
        agent_id=agent_id,
        name=role_name,
        role_name=role_name,
        role_summary=f"{role_name} summary",
        mission=f"{role_name} mission",
        goal_kind=role_id,
        employment_mode="career",
        activation_mode="persistent",
        reports_to=EXECUTION_CORE_ROLE_ID,
        risk_level="guarded",
        allowed_capabilities=list(allowed_capabilities or []),
        environment_constraints=[],
        evidence_expectations=["report back"],
    )


class _FakeCapabilityService:
    def __init__(self) -> None:
        self.calls: list[str | None] = []

    def list_accessible_capabilities(self, *, agent_id: str | None, enabled_only: bool = False):
        _ = enabled_only
        self.calls.append(agent_id)
        return []


class _Harness(_IndustryStrategyMixin):
    def __init__(self, capability_service: _FakeCapabilityService) -> None:
        self._capability_service = capability_service


def test_chat_writeback_role_resolution_reuses_team_surface_capability_scan() -> None:
    capability_service = _FakeCapabilityService()
    harness = _Harness(capability_service)
    team = IndustryTeamBlueprint(
        team_id="team-1",
        label="Team",
        summary="Team",
        agents=[
            _role(
                role_id="researcher",
                agent_id="agent-researcher",
                role_name="Researcher",
                allowed_capabilities=["tool:read_file"],
            ),
            _role(
                role_id="operator",
                agent_id="agent-operator",
                role_name="Operator",
                allowed_capabilities=["tool:write_file"],
            ),
        ],
    )
    record = IndustryInstanceRecord(
        instance_id="industry-1",
        label="Industry",
        owner_scope="industry:test",
        draft_payload={"goals": []},
    )

    (
        capability_ids,
        capability_mounts,
        environment_texts,
        role_surface_context,
    ) = harness._collect_team_surface_context(team=team)

    assert capability_ids
    assert environment_texts == ["Researcher summary", "Researcher mission", "Researcher", "Operator summary", "Operator mission", "Operator"]
    assert capability_mounts == []

    harness._resolve_chat_writeback_target_role(
        record=record,
        team=team,
        message_text="整理桌面文件并归档",
        requested_surfaces=["file", "desktop"],
        role_surface_context=role_surface_context,
    )

    assert capability_service.calls == [
        "agent-researcher",
        "agent-operator",
    ]
