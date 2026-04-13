from copaw.industry.identity import EXECUTION_CORE_AGENT_ID, EXECUTION_CORE_ROLE_ID
from copaw.industry.models import (
    IndustryDraftPlan,
    IndustryExecutionCoreIdentity,
    IndustryInstanceDetail,
    IndustryProfile,
    IndustryRoleBlueprint,
    IndustryTeamBlueprint,
)
from copaw.industry.service_activation import _IndustryActivationMixin


class _DummyActivationService(_IndustryActivationMixin):
    pass


def _business_role() -> IndustryRoleBlueprint:
    return IndustryRoleBlueprint(
        role_id="growth-focus",
        agent_id="agent-growth",
        name="Growth Focus",
        role_name="成长推进执行位",
        role_summary="推进成长任务。",
        mission="完成成长执行闭环。",
        goal_kind="growth-focus",
        agent_class="business",
        employment_mode="career",
        activation_mode="persistent",
        suspendable=False,
        risk_level="guarded",
        environment_constraints=[],
        allowed_capabilities=["system:dispatch_query"],
        evidence_expectations=["growth summary"],
    )


def test_build_draft_from_instance_detail_rehydrates_execution_core_role() -> None:
    service = _DummyActivationService()
    detail = IndustryInstanceDetail(
        instance_id="industry:test",
        label="测试行业",
        summary="测试摘要",
        owner_scope="buddy:test",
        profile=IndustryProfile(industry="Trading", company_name="Test"),
        team=IndustryTeamBlueprint(
            team_id="industry:test",
            label="测试行业",
            summary="测试摘要",
            agents=[_business_role()],
        ),
        execution_core_identity=IndustryExecutionCoreIdentity(
            binding_id="industry:test:execution-core",
            agent_id=EXECUTION_CORE_AGENT_ID,
            role_id=EXECUTION_CORE_ROLE_ID,
            industry_instance_id="industry:test",
            identity_label="测试行业 / Spider Mesh 执行中枢",
            industry_label="测试行业",
            industry_summary="测试摘要",
            role_name="Spider Mesh 执行中枢",
            role_summary="负责拆解、分派、监督和回收证据。",
            mission="只做主脑调度，不直接执行叶子任务。",
            thinking_axes=["测试"],
            environment_constraints=[],
            allowed_capabilities=[],
            delegation_policy=["delegate"],
            direct_execution_policy=["no-direct-leaf"],
            evidence_expectations=[],
        ),
    )

    draft = service._build_draft_from_instance_detail(detail)

    assert isinstance(draft, IndustryDraftPlan)
    assert [role.role_id for role in draft.team.agents] == [
        EXECUTION_CORE_ROLE_ID,
        "growth-focus",
    ]
    execution_core = draft.team.agents[0]
    assert execution_core.agent_id == EXECUTION_CORE_AGENT_ID
    assert execution_core.role_name == "Spider Mesh 执行中枢"
    assert execution_core.mission == "只做主脑调度，不直接执行叶子任务。"


def test_build_draft_from_instance_detail_seeds_goal_when_detail_has_none() -> None:
    service = _DummyActivationService()
    detail = IndustryInstanceDetail(
        instance_id="industry:test",
        label="测试行业",
        summary="测试摘要",
        owner_scope="buddy:test",
        profile=IndustryProfile(industry="Trading", company_name="Test"),
        team=IndustryTeamBlueprint(
            team_id="industry:test",
            label="测试行业",
            summary="测试摘要",
            agents=[_business_role()],
        ),
        execution_core_identity=IndustryExecutionCoreIdentity(
            binding_id="industry:test:execution-core",
            agent_id=EXECUTION_CORE_AGENT_ID,
            role_id=EXECUTION_CORE_ROLE_ID,
            industry_instance_id="industry:test",
            identity_label="测试行业 / Spider Mesh 执行中枢",
            industry_label="测试行业",
            industry_summary="测试摘要",
            role_name="Spider Mesh 执行中枢",
            role_summary="负责拆解、分派、监督和回收证据。",
            mission="只做主脑调度，不直接执行叶子任务。",
            thinking_axes=["测试"],
            environment_constraints=[],
            allowed_capabilities=[],
            delegation_policy=["delegate"],
            direct_execution_policy=["no-direct-leaf"],
            evidence_expectations=[],
        ),
    )

    draft = service._build_draft_from_instance_detail(detail)

    assert len(draft.goals) == 1
    assert draft.goals[0].owner_agent_id == "agent-growth"
    assert draft.goals[0].kind == "growth-focus"
