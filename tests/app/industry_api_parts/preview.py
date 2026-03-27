# -*- coding: utf-8 -*-
from __future__ import annotations

from .shared import *  # noqa: F401,F403
import copaw.capabilities.capability_discovery as capability_discovery
from copaw.industry.service_recommendation_pack import _enrich_draft_role_capability_families

PREVIEW_DEFERRED_CAPABILITY_MESSAGE = (
    "预览阶段只生成角色、目标与节奏草案；技能、MCP 与工作流将在身份创建后由主脑结合学习上下文继续配置。"
)


def _assert_preview_defers_capability_planning(payload) -> None:
    pack = payload["recommendation_pack"]
    assert pack["items"] == []
    assert pack["sections"] == []
    assert pack["summary"] == PREVIEW_DEFERRED_CAPABILITY_MESSAGE
    assert PREVIEW_DEFERRED_CAPABILITY_MESSAGE in pack["warnings"]


def test_industry_preview_returns_editable_draft(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    response = client.post(
        "/industry/v1/preview",
        json={
            "industry": "Industrial Equipment",
            "company_name": "Northwind Robotics",
            "product": "factory monitoring copilots",
            "business_model": "B2B software and implementation services",
            "region": "North America",
            "target_customers": ["plant operations leaders", "maintenance managers"],
            "goals": ["launch two pilot deployments"],
            "constraints": ["stay within the current tool set"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["can_activate"] is True
    assert payload["draft"]["team"]["label"] == "Northwind Robotics AI Draft"
    assert payload["draft"]["team"]["topology"] == "lead-plus-support"
    assert payload["draft"]["generation_summary"]
    assert len(payload["draft"]["goals"]) == 3
    assert len(payload["draft"]["schedules"]) == 5
    schedule_titles = {item["title"] for item in payload["draft"]["schedules"]}
    assert any("Morning Review" in title for title in schedule_titles)
    assert any("Evening Review" in title for title in schedule_titles)
    assert any("Research" in title for title in schedule_titles)
    assert {agent["role_id"] for agent in payload["draft"]["team"]["agents"]}.issuperset(
        {"execution-core", "researcher"},
    )
    execution_core = next(
        agent
        for agent in payload["draft"]["team"]["agents"]
        if agent["role_id"] == "execution-core"
    )
    assert execution_core["agent_id"] == "copaw-agent-runner"
    assert any(
        agent["agent_class"] == "business"
        for agent in payload["draft"]["team"]["agents"]
    )
    draft_generator_check = next(
        check for check in payload["readiness_checks"] if check["key"] == "draft-generator"
    )
    assert draft_generator_check["status"] == "ready"
    assert draft_generator_check["context"]["provider_id"] == "fake-provider"
    assert draft_generator_check["context"]["model"] == "fake-industry-draft"
    _assert_preview_defers_capability_planning(payload)


def test_industry_preview_defers_desktop_template_matching_for_desktop_role(
    tmp_path,
) -> None:
    app = _build_industry_app(
        tmp_path,
        draft_generator=DesktopIndustryDraftGenerator(),
    )
    client = TestClient(app)

    response = client.post(
        "/industry/v1/preview",
        json={
            "industry": "Customer Operations",
            "company_name": "Northwind Robotics",
            "product": "desktop follow-up workflows",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    target_role = next(
        agent
        for agent in payload["draft"]["team"]["agents"]
        if agent["role_id"] == "solution-lead"
    )
    assert target_role["role_name"] == "桌面交付"
    _assert_preview_defers_capability_planning(payload)


def test_industry_preview_defers_browser_runtime_matching_for_browser_role(
    tmp_path,
) -> None:
    app = _build_industry_app(
        tmp_path,
        draft_generator=BrowserIndustryDraftGenerator(),
    )
    client = TestClient(app)

    response = client.post(
        "/industry/v1/preview",
        json={
            "industry": "Customer Operations",
            "company_name": "Northwind Robotics",
            "product": "browser onboarding workflows",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    target_role = next(
        agent
        for agent in payload["draft"]["team"]["agents"]
        if agent["role_id"] == "solution-lead"
    )
    assert target_role["role_name"] == "平台实施"
    assert "browser" in target_role["preferred_capability_families"]
    _assert_preview_defers_capability_planning(payload)


def test_industry_preview_defers_hub_skill_matching_for_matching_role(
    tmp_path,
) -> None:
    app = _build_industry_app(
        tmp_path,
        draft_generator=HubSkillIndustryDraftGenerator(),
        enable_hub_recommendations=True,
    )
    client = TestClient(app)

    with patch(
        "copaw.industry.service.search_hub_skills",
        return_value=[
            HubSkillResult(
                slug="salesforce-assist",
                name="salesforce",
                description="Salesforce CRM operations",
                version="1.0.0",
                source_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/salesforce-assist.zip",
                source_label="SkillHub 商店",
            ),
        ],
    ) as mock_search:
        response = client.post(
            "/industry/v1/preview",
            json={
                "industry": "Revenue Operations",
                "company_name": "Northwind Robotics",
                "product": "sales pipeline execution",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    target_role = next(
        agent
        for agent in payload["draft"]["team"]["agents"]
        if agent["role_id"] == "solution-lead"
    )
    assert target_role["role_name"] == "客户运营"
    mock_search.assert_not_called()
    _assert_preview_defers_capability_planning(payload)


def test_industry_preview_skips_hub_search_even_if_facade_search_is_patched(
    tmp_path,
) -> None:
    app = _build_industry_app(
        tmp_path,
        draft_generator=HubSkillIndustryDraftGenerator(),
        enable_hub_recommendations=True,
    )
    client = TestClient(app)

    with patch.object(
        capability_discovery,
        "search_hub_skills",
        return_value=[],
    ) as mock_facade_search, patch(
        "copaw.industry.service.search_hub_skills",
        return_value=[
            HubSkillResult(
                slug="salesforce-assist",
                name="salesforce",
                description="Salesforce CRM operations",
                version="1.0.0",
                source_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/salesforce-assist.zip",
                source_label="SkillHub 商店",
            ),
        ],
    ) as mock_service_search:
        response = client.post(
            "/industry/v1/preview",
            json={
                "industry": "Revenue Operations",
                "company_name": "Northwind Robotics",
                "product": "sales pipeline execution",
            },
        )

    assert response.status_code == 200
    mock_facade_search.assert_not_called()
    mock_service_search.assert_not_called()
    _assert_preview_defers_capability_planning(response.json())


def test_industry_preview_skips_hub_skill_secondary_family_queries(
    tmp_path,
) -> None:
    app = _build_industry_app(
        tmp_path,
        draft_generator=HubSkillIndustryDraftGenerator(),
        enable_hub_recommendations=True,
    )
    client = TestClient(app)
    queries: list[str] = []

    def _search_hub_skills(query: str, limit: int = 20) -> list[HubSkillResult]:
        queries.append(query)
        if query not in {"crm", "customer service"}:
            return []
        return [
            HubSkillResult(
                slug="salesforce-assist",
                name="salesforce",
                description="Salesforce CRM operations",
                version="1.0.0",
                source_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/salesforce-assist.zip",
                source_label="SkillHub 商店",
            ),
        ]

    with patch(
        "copaw.industry.service.search_hub_skills",
        side_effect=_search_hub_skills,
    ):
        response = client.post(
            "/industry/v1/preview",
            json={
                "industry": "Revenue Operations",
                "company_name": "Northwind Robotics",
                "product": "sales pipeline execution",
            },
        )

    assert response.status_code == 200
    assert queries == []
    _assert_preview_defers_capability_planning(response.json())


def test_industry_bootstrap_executes_hub_skill_install_plan(
    tmp_path,
) -> None:
    app = _build_industry_app(
        tmp_path,
        draft_generator=HubSkillIndustryDraftGenerator(),
        enable_hub_recommendations=True,
    )
    client = TestClient(app)
    original_get_capability = app.state.capability_service.get_capability

    def _patched_get_capability(capability_id: str):
        if capability_id == "skill:salesforce":
            existing = original_get_capability(capability_id)
            if existing is not None:
                return existing
            return CapabilityMount(
                id="skill:salesforce",
                name="salesforce",
                summary="Salesforce CRM operations",
                kind="skill-bundle",
                source_kind="skill",
                risk_level="guarded",
                risk_description="Imported hub skill",
                enabled=True,
            )
        return original_get_capability(capability_id)

    with (
        patch(
            "copaw.capabilities.skill_service.install_skill_from_hub",
            return_value=SimpleNamespace(
                name="salesforce",
                enabled=True,
                source_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/salesforce-assist.zip",
            ),
        ),
        patch.object(
            app.state.capability_service._system_handler._team,
            "_get_capability",
            side_effect=_patched_get_capability,
        ),
    ):
        preview = client.post(
            "/industry/v1/preview",
            json={
                "industry": "Revenue Operations",
                "company_name": "Northwind Robotics",
                "product": "sales pipeline execution",
            },
        )
        assert preview.status_code == 200
        preview_payload = preview.json()
        draft = preview_payload["draft"]
        target_role = next(
            agent
            for agent in draft["team"]["agents"]
            if agent["role_id"] == "solution-lead"
        )
        _assert_preview_defers_capability_planning(preview_payload)

        response = client.post(
            "/industry/v1/bootstrap",
            json={
                "profile": preview_payload["profile"],
                "draft": draft,
                "install_plan": [
                    {
                        "install_kind": "hub-skill",
                        "template_id": "salesforce-assist",
                        "bundle_url": "https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/salesforce-assist.zip",
                        "version": "1.0.0",
                        "source_kind": "hub-search",
                        "source_label": "SkillHub 商店",
                        "capability_assignment_mode": "merge",
                        "target_agent_ids": [target_role["agent_id"]],
                    }
                ],
                "auto_activate": True,
                "auto_dispatch": False,
                "execute": False,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["install_results"][0]["install_kind"] == "hub-skill"
    assert payload["install_results"][0]["template_id"] == "salesforce-assist"
    assert payload["install_results"][0]["client_key"] == "salesforce"
    assert payload["install_results"][0]["source_url"] == "https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/salesforce-assist.zip"
    assert payload["install_results"][0]["capability_ids"] == ["skill:salesforce"]
    assert payload["install_results"][0]["status"] == "installed"
    assert payload["install_results"][0]["installed"] is True
    assert payload["install_results"][0]["assignment_results"][0]["status"] == "assigned"

    override = app.state.agent_profile_override_repository.get_override(
        target_role["agent_id"],
    )
    assert override is not None
    assert "skill:salesforce" in (override.capabilities or [])


def test_industry_preview_defers_skillhub_curated_matching_for_matching_role(
    tmp_path,
) -> None:
    app = _build_industry_app(
        tmp_path,
        draft_generator=HubSkillIndustryDraftGenerator(),
        enable_curated_catalog=True,
    )
    client = TestClient(app)

    with patch(
        "copaw.industry.service.search_curated_skill_catalog",
        return_value=CuratedSkillCatalogSearchResponse(
            sources=[
                CuratedSkillCatalogSource(
                    source_id="skillhub-featured-crm",
                    label="SkillHub 精选·客户协作",
                    source_kind="skillhub-curated",
                    query="crm",
                    notes=["来自 SkillHub 商店的客户协作精选。"],
                ),
            ],
            items=[
                CuratedSkillCatalogEntry(
                    candidate_id="salesforce-curated",
                    source_id="skillhub-featured-crm",
                    source_label="SkillHub 精选·客户协作",
                    source_kind="skillhub-curated",
                    source_repo_url="https://lightmake.site",
                    discovery_kind="skillhub-preset",
                    manifest_status="skillhub-curated",
                    title="CRM 协作工具",
                    description="Curated Salesforce workflow skill",
                    bundle_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/salesforce-curated.zip",
                    version="1.0.0",
                    install_name="salesforce",
                    tags=["crm", "salesforce"],
                    capability_tags=["skill", "skillhub-curated"],
                    review_required=False,
                    review_summary="来自 SkillHub 精选，可直接安装并分配给指定智能体。",
                    review_notes=["客户协作精选。"],
                    routes={"source_repo": "https://lightmake.site"},
                ),
            ],
            warnings=[],
        ),
    ) as mock_curated_search:
        response = client.post(
            "/industry/v1/preview",
            json={
                "industry": "Revenue Operations",
                "company_name": "Northwind Robotics",
                "product": "sales pipeline execution",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    mock_curated_search.assert_not_called()
    _assert_preview_defers_capability_planning(payload)


def test_standardize_recommendation_items_keeps_standard_package_for_large_team() -> None:
    target_roles = [
        IndustryRoleBlueprint(
            role_id=f"role-{index}",
            agent_id=f"agent-{index}",
            name=f"Role {index}",
            role_name=f"Role {index}",
            role_summary="Owns a specialist execution surface.",
            mission="Execute assigned work and return evidence.",
            goal_kind=f"goal-{index}",
            agent_class="business",
        )
        for index in range(5)
    ]
    items = [
        IndustryCapabilityRecommendation(
            recommendation_id=f"{role.agent_id}-skill-{slot}",
            install_kind="hub-skill",
            template_id=f"{role.agent_id}-skill-{slot}",
            title=f"Skill {role.agent_id}-{slot}",
            description="SkillHub recommendation",
            capability_ids=[f"skill:{role.agent_id}-{slot}"],
            capability_tags=["skill"],
            suggested_role_ids=[role.role_id],
            target_agent_ids=[role.agent_id],
            source_kind="hub-search",
            source_label="SkillHub 商店",
        )
        for role in target_roles
        for slot in range(2)
    ]

    selected = _standardize_recommendation_items(items, target_roles)

    assert len(selected) == 10
    target_counts = {role.agent_id: 0 for role in target_roles}
    for item in selected:
        for agent_id in item.target_agent_ids:
            target_counts[agent_id] += 1
    assert all(count == 2 for count in target_counts.values())


def test_build_skillhub_query_candidates_uses_role_intent_without_agent_id_noise() -> None:
    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Customer Operations",
            company_name="Northwind",
            product="service delivery",
            goals=["build customer service, content knowledge, and workflow automation"],
            operator_requirements=["customer follow-up", "knowledge content"],
        )
    )
    role = IndustryRoleBlueprint(
        role_id="customer-service-lead",
        agent_id="industry-customer-service-lead-9f3b2d10",
        name="Customer Service Lead",
        role_name="Customer Service Lead",
        role_summary="Handles customer service and knowledge content.",
        mission="Own customer replies and workflow follow-up.",
        goal_kind="customer-service",
        agent_class="business",
    )

    queries = _build_skillhub_query_candidates(
        profile=profile,
        role=role,
        goal_context=["prepare support knowledge base and automate follow-up"],
    )
    query_texts = [item.query for item in queries]

    assert "customer service" in query_texts
    assert "content strategy" in query_texts
    assert "workflow automation" not in query_texts
    assert not any("industry-customer-service-lead" in item for item in query_texts)


def test_build_skillhub_query_candidates_for_execution_core_only_returns_orchestration_queries() -> None:
    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Customer Operations",
            company_name="Northwind",
            product="service delivery",
            goals=["build research insight, content knowledge, and workflow automation"],
            operator_requirements=["research insight", "conversation optimization"],
            experience_notes="Previous cycles relied on research summaries and SOP review.",
        )
    )
    role = IndustryRoleBlueprint(
        role_id="execution-core",
        agent_id="copaw-agent-runner",
        name="Spider Mesh Main Brain",
        role_name="Spider Mesh Main Brain",
        role_summary="Break goals into sub-tasks, coordinate researchers, and synthesize status.",
        mission="Plan next steps, assign work, review evidence, and summarize the operating loop.",
        goal_kind="execution-core",
        agent_class="system",
        environment_constraints=["Needs runtime context, research findings, and conversation history."],
        evidence_expectations=["Weekly operating plan", "research summary", "assignment checklist"],
    )

    family_ids = _role_capability_family_ids(
        profile=profile,
        role=role,
        goal_context=["Review research findings and produce the next workflow brief."],
    )
    queries = _build_skillhub_query_candidates(
        profile=profile,
        role=role,
        goal_context=["Review research findings and produce the next workflow brief."],
    )
    family_queries = [item.query for item in queries if item.kind == "family"]

    assert family_ids[0] == "workflow"
    assert set(family_ids).issubset({"workflow", "research", "content"})
    assert "workflow automation" in family_queries
    assert "industry research" in family_queries
    assert "content strategy" in family_queries
    assert "browser automation" not in family_queries
    assert "customer service" not in family_queries


def test_role_capability_family_ids_use_history_environment_and_output_signals() -> None:
    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Professional Services",
            company_name="Northwind",
            product="client delivery",
            channels=["customer workspace"],
            goals=["publish one weekly customer knowledge summary"],
            constraints=["keep the follow-up loop inside the existing customer systems"],
            operator_requirements=[
                "historically keep customer follow-up in Salesforce",
                "deliver weekly knowledge summary",
            ],
            experience_notes=(
                "Past tasks centered on Salesforce follow-up routines and knowledge-base summaries."
            ),
        )
    )
    role = IndustryRoleBlueprint(
        role_id="operations-specialist",
        agent_id="operations-specialist",
        name="Operations Specialist",
        role_name="Operations Specialist",
        role_summary="Generic coordinator role without a preset specialty.",
        mission="Keep the loop stable and close the next operating step.",
        goal_kind="operations",
        agent_class="business",
        environment_constraints=[
            "Requires Salesforce customer records and the knowledge library context."
        ],
        evidence_expectations=["Weekly knowledge summary", "customer follow-up log"],
    )

    family_ids = _role_capability_family_ids(
        profile=profile,
        role=role,
        goal_context=[
            "Continue the Salesforce follow-up routine and turn the notes into a weekly knowledge summary."
        ],
    )
    queries = _build_skillhub_query_candidates(
        profile=profile,
        role=role,
        goal_context=[
            "Continue the Salesforce follow-up routine and turn the notes into a weekly knowledge summary."
        ],
    )
    family_queries = [item.query for item in queries if item.kind == "family"]

    assert family_ids == ["crm"]
    assert "content strategy" in family_queries


def test_role_capability_family_ids_limit_generic_role_to_primary_and_secondary() -> None:
    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Professional Services",
            goals=[
                "build customer response, content delivery, workflow automation, and reporting",
            ],
            operator_requirements=[
                "customer follow-up",
                "knowledge articles",
                "process SOP",
                "weekly analysis",
            ],
            notes="Need someone to keep the service loop moving with repeatable execution.",
        )
    )
    role = IndustryRoleBlueprint(
        role_id="service-operations-lead",
        agent_id="service-operations-lead",
        name="Service Operations Lead",
        role_name="Service Operations Lead",
        role_summary="Owns customer delivery, content updates, workflow refinement, and reporting follow-up.",
        mission="Keep the operating loop moving and make sure the customer-facing process closes.",
        goal_kind="service-operations",
        agent_class="business",
    )

    family_ids = _role_capability_family_ids(
        profile=profile,
        role=role,
        goal_context=["maintain SOPs, update knowledge content, and review weekly operating signals"],
    )

    assert len(family_ids) == 2
    assert family_ids == ["content", "workflow"]


def test_role_capability_family_ids_prefer_explicit_role_override() -> None:
    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Advisory",
            goals=["support customer follow-up and structured execution"],
        )
    )
    role = IndustryRoleBlueprint(
        role_id="client-success",
        agent_id="client-success",
        name="Client Success",
        role_name="Client Success",
        role_summary="Generic role summary that should not widen the family set.",
        mission="Close the loop.",
        goal_kind="client-success",
        agent_class="business",
        preferred_capability_families=[
            "customer service",
            "workflow automation",
        ],
    )

    family_ids = _role_capability_family_ids(
        profile=profile,
        role=role,
        goal_context=["keep the handoff process stable"],
    )
    queries = _build_skillhub_query_candidates(
        profile=profile,
        role=role,
        goal_context=["keep the handoff process stable"],
    )

    assert family_ids == ["crm", "workflow"]
    family_queries = [item.query for item in queries if item.kind == "family"]
    assert family_queries[:2] == ["customer service", "crm"]


def test_skillhub_family_queries_use_generic_surface_defaults_instead_of_app_names() -> None:
    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Operations",
            goals=["keep local delivery and reporting stable"],
        )
    )
    role = IndustryRoleBlueprint(
        role_id="delivery-ops",
        agent_id="delivery-ops",
        name="Delivery Ops",
        role_name="Delivery Ops",
        role_summary="Owns local client execution, window-based handoff, and spreadsheet reporting.",
        mission="Keep local execution and tabular reporting stable.",
        goal_kind="delivery-ops",
        agent_class="business",
        preferred_capability_families=[
            "desktop automation",
            "data analysis",
            "email automation",
        ],
    )

    queries = _build_skillhub_query_candidates(
        profile=profile,
        role=role,
        goal_context=[
            "Use the local client, manage window-based steps, and maintain structured reports.",
        ],
    )
    family_queries = [item.query for item in queries if item.kind == "family"]
    joined = " | ".join(family_queries).lower()

    assert "desktop automation" in family_queries
    assert "data analysis" in family_queries
    assert "email automation" in family_queries
    for forbidden in (
        "wechat",
        "excel",
        "word",
        "outlook",
        "企业微信",
        "微信",
        "飞书",
        "钉钉",
    ):
        assert forbidden not in joined



def test_enrich_draft_role_capability_families_expands_store_scene_bundle_queries() -> None:
    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="E-commerce Operations",
            company_name="Northwind",
            product="store operations",
            goals=[
                "keep listing updates, customer follow-up, content refresh, and order workflow moving",
            ],
            operator_requirements=[
                "customer replies",
                "content updates",
                "order workflow",
                "store dashboard actions",
            ],
        )
    )
    draft = FakeIndustryDraftGenerator().build_draft(profile, "industry-v1-store-ops")
    for role in draft.team.agents:
        if role.role_id != "solution-lead":
            continue
        role.role_summary = (
            "Owns store listing updates, customer follow-up, content refresh, and workflow automation."
        )
        role.mission = (
            "Keep the store loop moving across browser actions, customer replies, content updates, and SOP handoff."
        )
        role.environment_constraints = ["需要通过网页后台处理店铺与订单流程。"]
        role.evidence_expectations = ["客户跟进记录", "内容更新记录", "流程复盘"]
    for goal in draft.goals:
        if goal.kind != "solution":
            continue
        goal.plan_steps = [
            "Update listings in the store dashboard.",
            "Reply to customer issues and follow up on orders.",
            "Refresh content and SOP flow for the next cycle.",
        ]

    enriched = _enrich_draft_role_capability_families(profile=profile, draft=draft)
    role = next(agent for agent in enriched.team.agents if agent.role_id == "solution-lead")
    queries = _build_skillhub_query_candidates(
        profile=profile,
        role=role,
        goal_context=[
            "Update listings in the store dashboard.",
            "Reply to customer issues and follow up on orders.",
            "Refresh content and SOP flow for the next cycle.",
        ],
    )
    family_queries = [item.query for item in queries if item.kind == "family"]

    assert role.role_name == "店铺运营"
    assert {"browser", "crm", "content", "workflow"}.issubset(
        set(role.preferred_capability_families)
    )
    assert "browser automation" in family_queries
    assert "customer service" in family_queries
    assert "content strategy" in family_queries
    assert "workflow automation" in family_queries


def test_industry_preview_keeps_multi_scene_role_family_hints_without_preview_matching(
    tmp_path,
) -> None:
    class StoreOpsIndustryDraftGenerator(FakeIndustryDraftGenerator):
        def build_draft(self, profile, owner_scope):
            draft = super().build_draft(profile, owner_scope)
            for role in draft.team.agents:
                if role.role_id != "solution-lead":
                    continue
                role.role_summary = (
                    "Owns store listing updates, customer follow-up, content refresh, and browser-based operating workflows."
                )
                role.mission = (
                    "Close the customer and store operating loop through dashboard actions, content maintenance, and SOP follow-up."
                )
            for goal in draft.goals:
                if goal.kind != "solution":
                    continue
                goal.plan_steps = [
                    "Update listings and store settings in the dashboard.",
                    "Reply to customer issues and push the next follow-up action.",
                    "Refresh content and workflow SOP for the next cycle.",
                ]
            return draft

    app = _build_industry_app(
        tmp_path,
        draft_generator=StoreOpsIndustryDraftGenerator(),
        enable_curated_catalog=True,
    )
    client = TestClient(app)

    def _entry(
        *,
        candidate_id: str,
        source_id: str,
        source_label: str,
        title: str,
        description: str,
        bundle_url: str,
        tags: list[str],
        capability_tags: list[str],
    ) -> CuratedSkillCatalogEntry:
        return CuratedSkillCatalogEntry(
            candidate_id=candidate_id,
            source_id=source_id,
            source_label=source_label,
            source_kind="skillhub-curated",
            source_repo_url="https://lightmake.site",
            discovery_kind="skillhub-preset",
            manifest_status="skillhub-curated",
            title=title,
            description=description,
            bundle_url=bundle_url,
            version="1.0.0",
            install_name=candidate_id,
            tags=tags,
            capability_tags=capability_tags,
            review_required=False,
            review_summary="来自 SkillHub 精选，可直接安装并分配给指定智能体。",
            review_notes=[source_label],
            routes={},
        )

    def _curated_search(
        query: str,
        limit: int = 20,
    ) -> CuratedSkillCatalogSearchResponse:
        _ = limit
        normalized = query.lower()
        source_id = "skillhub-search:store-ops"
        source_label = "SkillHub 精选·店铺运营"
        items: list[CuratedSkillCatalogEntry] = []
        if "customer service" in normalized:
            items.append(
                _entry(
                    candidate_id="customer-service-reply",
                    source_id="skillhub-featured-customer",
                    source_label="SkillHub 精选·客户协作",
                    title="客服回复模板",
                    description="Customer service reply workflows.",
                    bundle_url="https://skillhub.example.com/customer-service-reply.zip",
                    tags=["customer-service"],
                    capability_tags=["skill", "crm"],
                )
            )
        if "content strategy" in normalized:
            items.append(
                _entry(
                    candidate_id="content-strategy",
                    source_id="skillhub-featured-content",
                    source_label="SkillHub 精选·内容处理",
                    title="内容策略助手",
                    description="Content planning and editorial workflow support.",
                    bundle_url="https://skillhub.example.com/content-strategy.zip",
                    tags=["content"],
                    capability_tags=["skill", "content"],
                )
            )
        if "workflow automation" in normalized:
            items.append(
                _entry(
                    candidate_id="automation-workflows",
                    source_id="skillhub-featured-workflow",
                    source_label="SkillHub 精选·流程自动化",
                    title="流程自动化工作台",
                    description="Design and implement automation workflows.",
                    bundle_url="https://skillhub.example.com/automation-workflows.zip",
                    tags=["workflow"],
                    capability_tags=["skill", "workflow"],
                )
            )
        if "browser automation" in normalized or normalized == "browser":
            items.append(
                _entry(
                    candidate_id="browser-use-pro",
                    source_id="skillhub-featured-browser",
                    source_label="SkillHub 精选·网页执行",
                    title="网页自动化执行器",
                    description="Automate browser login and form actions.",
                    bundle_url="https://skillhub.example.com/browser-use-pro.zip",
                    tags=["browser"],
                    capability_tags=["skill", "browser"],
                )
            )
        return CuratedSkillCatalogSearchResponse(
            sources=[
                CuratedSkillCatalogSource(
                    source_id=source_id,
                    label=source_label,
                    source_kind="skillhub-curated",
                    query=query,
                    notes=[],
                )
            ],
            items=items,
            warnings=[],
        )

    with patch(
        "copaw.industry.service.search_curated_skill_catalog",
        side_effect=_curated_search,
    ) as mock_curated_search:
        response = client.post(
            "/industry/v1/preview",
            json={
                "industry": "E-commerce Operations",
                "company_name": "Northwind",
                "product": "store operations",
                "goals": [
                    "keep listing updates, customer follow-up, content refresh, and order workflow moving",
                ],
                "operator_requirements": [
                    "customer replies",
                    "content updates",
                    "order workflow",
                    "store dashboard actions",
                ],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    target_role = next(
        agent for agent in payload["draft"]["team"]["agents"] if agent["role_id"] == "solution-lead"
    )
    assert target_role["role_name"] == "店铺运营"
    assert {"content", "workflow", "browser"}.issubset(
        set(target_role["preferred_capability_families"])
    )
    mock_curated_search.assert_not_called()
    _assert_preview_defers_capability_planning(payload)


def test_industry_preview_defers_capability_pack_for_core_and_support_roles(
    tmp_path,
) -> None:
    app = _build_industry_app(
        tmp_path,
        draft_generator=FakeIndustryDraftGenerator(),
        enable_hub_recommendations=True,
        enable_curated_catalog=True,
    )
    client = TestClient(app)

    def _hub_search(query: str, limit: int = 20) -> list[HubSkillResult]:
        _ = limit
        normalized = query.lower()
        if "customer service" in normalized:
            return [
                HubSkillResult(
                    slug="customer-service-reply",
                    name="客服回复模板",
                    description="Customer service reply workflows.",
                    version="1.0.0",
                    source_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/customer-service-reply.zip",
                    source_label="SkillHub 商店",
                )
            ]
        if "content strategy" in normalized:
            return [
                HubSkillResult(
                    slug="content-strategy",
                    name="内容策略助手",
                    description="Content planning and editorial workflow support.",
                    version="1.0.0",
                    source_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/content-strategy.zip",
                    source_label="SkillHub 商店",
                )
            ]
        if "browser automation" in normalized or normalized == "browser":
            return [
                HubSkillResult(
                    slug="browser-use",
                    name="网页自动化执行器",
                    description="Automate browser login and form actions.",
                    version="1.0.0",
                    source_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/browser-use.zip",
                    source_label="SkillHub 商店",
                )
            ]
        if "workflow automation" in normalized:
            return [
                HubSkillResult(
                    slug="automation-workflows",
                    name="流程自动化工作台",
                    description="Design and implement automation workflows.",
                    version="1.0.0",
                    source_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/automation-workflows.zip",
                    source_label="SkillHub 商店",
                )
            ]
        if "industry research" in normalized or normalized == "research":
            return [
                HubSkillResult(
                    slug="deep-research-pro",
                    name="多源深度研究智能体",
                    description="Collect research signals and summarize findings.",
                    version="1.0.0",
                    source_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/deep-research-pro.zip",
                    source_label="SkillHub 商店",
                )
            ]
        return []

    def _curated_search(
        query: str,
        limit: int = 20,
    ) -> CuratedSkillCatalogSearchResponse:
        _ = limit
        normalized = query.lower()
        items: list[CuratedSkillCatalogEntry] = []
        source_id = "skillhub-search:mock"
        source_label = "SkillHub 精选检索"
        if "customer service" in normalized:
            source_id = "skillhub-featured-customer"
            source_label = "SkillHub 精选·客户协作"
            items.append(
                CuratedSkillCatalogEntry(
                    candidate_id="customer-service-reply",
                    source_id=source_id,
                    source_label=source_label,
                    source_kind="skillhub-curated",
                    source_repo_url="https://lightmake.site",
                    discovery_kind="skillhub-preset",
                    manifest_status="skillhub-curated",
                    title="客服回复模板",
                    description="Customer service reply workflows.",
                    bundle_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/customer-service-reply.zip",
                    version="1.0.0",
                    install_name="customer-service-reply",
                    tags=["customer-service"],
                    capability_tags=["skill", "crm"],
                    review_required=False,
                    review_summary="来自 SkillHub 精选，可直接安装并分配给指定智能体。",
                    review_notes=["客户协作精选。"],
                    routes={},
                )
            )
        elif "industry research" in normalized or normalized == "research":
            source_id = "skillhub-featured-research"
            source_label = "SkillHub 精选·研究分析"
            items.append(
                CuratedSkillCatalogEntry(
                    candidate_id="deep-research-pro",
                    source_id=source_id,
                    source_label=source_label,
                    source_kind="skillhub-curated",
                    source_repo_url="https://lightmake.site",
                    discovery_kind="skillhub-preset",
                    manifest_status="skillhub-curated",
                    title="多源深度研究智能体",
                    description="Collect research signals and summarize findings.",
                    bundle_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/deep-research-pro.zip",
                    version="1.0.0",
                    install_name="deep-research-pro",
                    tags=["research"],
                    capability_tags=["skill", "research"],
                    review_required=False,
                    review_summary="来自 SkillHub 精选，可直接安装并分配给指定智能体。",
                    review_notes=["研究分析精选。"],
                    routes={},
                )
            )
        elif "content strategy" in normalized:
            source_id = "skillhub-featured-content"
            source_label = "SkillHub 精选·内容处理"
            items.append(
                CuratedSkillCatalogEntry(
                    candidate_id="content-strategy",
                    source_id=source_id,
                    source_label=source_label,
                    source_kind="skillhub-curated",
                    source_repo_url="https://lightmake.site",
                    discovery_kind="skillhub-preset",
                    manifest_status="skillhub-curated",
                    title="内容策略助手",
                    description="Content planning and editorial workflow support.",
                    bundle_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/content-strategy.zip",
                    version="1.0.0",
                    install_name="content-strategy",
                    tags=["content"],
                    capability_tags=["skill", "content"],
                    review_required=False,
                    review_summary="来自 SkillHub 精选，可直接安装并分配给指定智能体。",
                    review_notes=["内容处理精选。"],
                    routes={},
                )
            )
        elif "workflow automation" in normalized:
            source_id = "skillhub-featured-workflow"
            source_label = "SkillHub 精选·流程自动化"
            items.append(
                CuratedSkillCatalogEntry(
                    candidate_id="automation-workflows",
                    source_id=source_id,
                    source_label=source_label,
                    source_kind="skillhub-curated",
                    source_repo_url="https://lightmake.site",
                    discovery_kind="skillhub-preset",
                    manifest_status="skillhub-curated",
                    title="流程自动化工作台",
                    description="Design and implement automation workflows.",
                    bundle_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/automation-workflows.zip",
                    version="1.0.0",
                    install_name="automation-workflows",
                    tags=["workflow"],
                    capability_tags=["skill", "workflow"],
                    review_required=False,
                    review_summary="来自 SkillHub 精选，可直接安装并分配给指定智能体。",
                    review_notes=["流程自动化精选。"],
                    routes={},
                )
            )
        elif "browser automation" in normalized or normalized == "browser":
            source_id = "skillhub-featured-browser"
            source_label = "SkillHub 精选·网页执行"
            items.append(
                CuratedSkillCatalogEntry(
                    candidate_id="browser-use",
                    source_id=source_id,
                    source_label=source_label,
                    source_kind="skillhub-curated",
                    source_repo_url="https://lightmake.site",
                    discovery_kind="skillhub-preset",
                    manifest_status="skillhub-curated",
                    title="网页自动化执行器",
                    description="Automate browser login and form actions.",
                    bundle_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/browser-use.zip",
                    version="1.0.0",
                    install_name="browser-use",
                    tags=["browser"],
                    capability_tags=["skill", "browser"],
                    review_required=False,
                    review_summary="来自 SkillHub 精选，可直接安装并分配给指定智能体。",
                    review_notes=["网页执行精选。"],
                    routes={},
                )
            )
        return CuratedSkillCatalogSearchResponse(
            sources=[
                CuratedSkillCatalogSource(
                    source_id=source_id,
                    label=source_label,
                    source_kind="skillhub-curated",
                    query=query,
                    notes=[],
                )
            ],
            items=items,
            warnings=[],
        )

    with patch(
        "copaw.industry.service.search_hub_skills",
        side_effect=_hub_search,
    ) as mock_hub_search, patch(
        "copaw.industry.service.search_curated_skill_catalog",
        side_effect=_curated_search,
    ) as mock_curated_search:
        response = client.post(
            "/industry/v1/preview",
            json={
                "industry": "Customer Operations",
                "company_name": "Northwind",
                "product": "service delivery",
                "goals": [
                    "build customer service, content knowledge, research insight, and workflow automation",
                ],
                "operator_requirements": [
                    "customer service",
                    "research insight",
                    "workflow automation",
                ],
            },
        )

    assert response.status_code == 200
    payload = response.json()
    execution_core = next(
        agent
        for agent in payload["draft"]["team"]["agents"]
        if agent["role_id"] == "execution-core"
    )
    solution_lead = next(
        agent
        for agent in payload["draft"]["team"]["agents"]
        if agent["role_id"] == "solution-lead"
    )
    assert set(execution_core["preferred_capability_families"]).issubset(
        {"workflow", "research", "content"}
    )
    assert solution_lead["preferred_capability_families"]
    mock_hub_search.assert_not_called()
    mock_curated_search.assert_not_called()
    _assert_preview_defers_capability_planning(payload)


def test_industry_preview_skips_cross_domain_remote_skill_filtering_until_post_create(
    tmp_path,
) -> None:
    app = _build_industry_app(
        tmp_path,
        draft_generator=HubSkillIndustryDraftGenerator(),
        enable_hub_recommendations=True,
    )
    client = TestClient(app)

    with patch(
        "copaw.industry.service.search_hub_skills",
        return_value=[
            HubSkillResult(
                slug="stock-trading-automation",
                name="Trading workflow CRM",
                description=(
                    "Workflow automation for stock trading, investment lead routing, "
                    "and finance CRM follow-up."
                ),
                version="1.0.0",
                source_url="https://skillhub.example.com/stock-trading-automation.zip",
                source_label="SkillHub 商店",
            ),
            HubSkillResult(
                slug="salesforce-followup",
                name="Salesforce follow-up",
                description="CRM follow-up workflows for store customer operations.",
                version="1.0.0",
                source_url="https://skillhub.example.com/salesforce-followup.zip",
                source_label="SkillHub 商店",
            ),
        ],
    ) as mock_hub_search:
        response = client.post(
            "/industry/v1/preview",
            json={
                "industry": "Ecommerce",
                "company_name": "Northwind",
                "product": "store operations",
                "goals": ["customer follow-up", "order pipeline hygiene"],
            },
        )

    assert response.status_code == 200
    mock_hub_search.assert_not_called()
    _assert_preview_defers_capability_planning(response.json())


def test_industry_preview_skips_generic_browser_remote_skill_dedup_until_post_create(
    tmp_path,
) -> None:
    app = _build_industry_app(
        tmp_path,
        draft_generator=BrowserIndustryDraftGenerator(),
        enable_hub_recommendations=True,
        enable_curated_catalog=True,
    )
    client = TestClient(app)

    curated_response = CuratedSkillCatalogSearchResponse(
        sources=[],
        items=[
            CuratedSkillCatalogEntry(
                candidate_id="browser-use",
                source_id="skillhub-featured-browser",
                source_label="SkillHub 精选",
                source_kind="skillhub-curated",
                source_repo_url="https://lightmake.site",
                discovery_kind="skillhub-preset",
                manifest_status="skillhub-curated",
                title="Browser Use",
                description="Generic browser automation runtime for login and forms.",
                bundle_url="https://skillhub.example.com/browser-use.zip",
                version="1.0.0",
                install_name="browser-use",
                tags=["browser"],
                capability_tags=["skill", "browser"],
                review_required=False,
                review_summary="Ready to install.",
                review_notes=[],
                routes={},
            )
        ],
        warnings=[],
    )

    with patch(
        "copaw.industry.service.search_hub_skills",
        return_value=[
            HubSkillResult(
                slug="browser-use",
                name="Browser Use",
                description="Generic browser automation runtime for login and forms.",
                version="1.0.0",
                source_url="https://skillhub.example.com/browser-use.zip",
                source_label="SkillHub 商店",
            )
        ],
    ) as mock_hub_search, patch(
        "copaw.industry.service.search_curated_skill_catalog",
        return_value=curated_response,
    ) as mock_curated_search:
        response = client.post(
            "/industry/v1/preview",
            json={
                "industry": "Store Operations",
                "company_name": "Northwind",
                "product": "merchant portal setup",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    solution_role = next(
        agent
        for agent in payload["draft"]["team"]["agents"]
        if agent["role_id"] == "solution-lead"
    )
    assert "browser" in solution_role["preferred_capability_families"]
    mock_hub_search.assert_not_called()
    mock_curated_search.assert_not_called()
    _assert_preview_defers_capability_planning(payload)


def test_industry_preview_backfills_role_capability_family_anchors(tmp_path) -> None:
    app = _build_industry_app(
        tmp_path,
        draft_generator=BrowserIndustryDraftGenerator(),
    )
    client = TestClient(app)

    response = client.post(
        "/industry/v1/preview",
        json={
            "industry": "Merchant Operations",
            "company_name": "Northwind",
            "product": "portal onboarding",
        },
    )

    assert response.status_code == 200
    draft = response.json()["draft"]
    execution_core = next(
        agent for agent in draft["team"]["agents"] if agent["role_id"] == "execution-core"
    )
    solution_role = next(
        agent for agent in draft["team"]["agents"] if agent["role_id"] == "solution-lead"
    )
    assert execution_core["preferred_capability_families"][0] == "workflow"
    assert set(execution_core["preferred_capability_families"]).issubset({"workflow", "research", "content"})
    assert "browser" in solution_role["preferred_capability_families"]


def test_industry_bootstrap_requires_review_ack_for_reviewed_curated_skill(
    tmp_path,
) -> None:
    app = _build_industry_app(
        tmp_path,
        draft_generator=HubSkillIndustryDraftGenerator(),
        enable_curated_catalog=True,
    )
    client = TestClient(app)

    with patch(
        "copaw.industry.service.search_curated_skill_catalog",
        return_value=CuratedSkillCatalogSearchResponse(
            sources=[],
            items=[
                CuratedSkillCatalogEntry(
                    candidate_id="salesforce-curated",
                    source_id="skillhub-featured-crm",
                    source_label="SkillHub 精选·客户协作",
                    source_kind="skillhub-curated",
                    source_repo_url="https://lightmake.site",
                    discovery_kind="skillhub-preset",
                    manifest_status="skillhub-curated",
                    title="CRM 协作工具",
                    description="Curated Salesforce workflow skill",
                    bundle_url="https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/salesforce-curated.zip",
                    version="1.0.0",
                    install_name="salesforce",
                    tags=["crm", "salesforce"],
                    capability_tags=["skill", "skillhub-curated"],
                    review_required=True,
                    review_summary="Review before install.",
                    review_notes=["Curated review gate."],
                    routes={},
                ),
            ],
            warnings=[],
        ),
    ):
        preview = client.post(
            "/industry/v1/preview",
            json={
                "industry": "Revenue Operations",
                "company_name": "Northwind Robotics",
                "product": "sales pipeline execution",
            },
        )
        assert preview.status_code == 200
        preview_payload = preview.json()
        draft = preview_payload["draft"]
        target_role = next(
            agent
            for agent in draft["team"]["agents"]
            if agent["role_id"] == "solution-lead"
        )
        _assert_preview_defers_capability_planning(preview_payload)

        response = client.post(
            "/industry/v1/bootstrap",
            json={
                "profile": preview_payload["profile"],
                "draft": draft,
                "install_plan": [
                    {
                        "install_kind": "hub-skill",
                        "template_id": "salesforce-curated",
                        "bundle_url": "https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/salesforce-curated.zip",
                        "source_kind": "skillhub-curated",
                        "source_label": "SkillHub 精选·客户协作",
                        "review_acknowledged": False,
                        "capability_assignment_mode": "merge",
                        "target_agent_ids": [target_role["agent_id"]],
                    }
                ],
                "auto_activate": True,
                "auto_dispatch": False,
                "execute": False,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["install_results"][0]["status"] == "failed"
    assert "安装前需要操作方确认" in payload["install_results"][0]["detail"]


def test_canonicalize_industry_draft_defaults_execution_core_to_delegation_first_identity() -> None:
    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Operations",
            company_name="Northwind",
            goals=["stabilize delivery"],
        ),
    )
    raw_draft = IndustryDraftPlan(
        team=IndustryTeamBlueprint(
            team_id="",
            label="Northwind AI Draft",
            summary="Editable draft.",
            topology="solo",
            agents=[
                IndustryRoleBlueprint(
                    role_id="execution-core",
                    agent_id="copaw-agent-runner",
                    name="白泽执行中枢",
                    role_name="白泽执行中枢",
                    role_summary="",
                    mission="",
                    goal_kind="execution-core",
                    agent_class="business",
                    activation_mode="persistent",
                    suspendable=False,
                    reports_to=None,
                    risk_level="guarded",
                    environment_constraints=[],
                    allowed_capabilities=[],
                    evidence_expectations=[],
                ),
                IndustryRoleBlueprint(
                    role_id="solution-lead",
                    agent_id="",
                    name="Northwind Solution Lead",
                    role_name="Solution Lead",
                    role_summary="Shapes the next rollout design.",
                    mission="Turn the brief into a rollout-ready solution.",
                    goal_kind="solution",
                    agent_class="business",
                    activation_mode="persistent",
                    suspendable=False,
                    reports_to="execution-core",
                    risk_level="guarded",
                    environment_constraints=[],
                    allowed_capabilities=[],
                    evidence_expectations=[],
                ),
            ],
        ),
        goals=[
            IndustryDraftGoal(
                goal_id="execution-core-goal",
                kind="execution-core",
                owner_agent_id="copaw-agent-runner",
                title="Operate Northwind",
                summary="Drive the next operating move.",
                plan_steps=["Review the brief", "Assign the next move"],
            ),
        ],
        schedules=[],
        generation_summary="AI draft.",
    )

    canonicalized = canonicalize_industry_draft(
        profile,
        raw_draft,
        owner_scope="industry-v1-northwind",
    )

    execution_core = next(
        agent
        for agent in canonicalized.team.agents
        if agent.role_id == "execution-core"
    )
    assert "main-brain control role" in execution_core.role_summary
    assert "delegation" in execution_core.role_summary
    assert "route work to the correct specialist" in execution_core.mission
    assert "strategy aligned with execution" in execution_core.mission


def test_canonicalize_industry_draft_injects_researcher_and_default_loops_for_signal_heavy_brief() -> None:
    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="E-commerce Operations",
            company_name="Northwind Commerce",
            product="marketplace growth service",
            channels=["JD", "Douyin"],
            goals=["monitor competitors", "improve customer service conversion"],
            operator_requirements=["必须包含客服聊天闭环", "需要持续同行监控"],
        ),
    )
    raw_draft = IndustryDraftPlan(
        team=IndustryTeamBlueprint(
            team_id="",
            label="Northwind Commerce AI Draft",
            summary="Editable draft.",
            topology="solo",
            agents=[
                IndustryRoleBlueprint(
                    role_id="execution-core",
                    agent_id="copaw-agent-runner",
                    name="白泽执行中枢",
                    role_name="白泽执行中枢",
                    role_summary="",
                    mission="",
                    goal_kind="execution-core",
                    agent_class="business",
                    activation_mode="persistent",
                    suspendable=False,
                    reports_to=None,
                    risk_level="guarded",
                    environment_constraints=[],
                    allowed_capabilities=[],
                    evidence_expectations=[],
                ),
                IndustryRoleBlueprint(
                    role_id="store-ops",
                    agent_id="",
                    name="Northwind Store Ops",
                    role_name="店铺运营",
                    role_summary="Owns store operations.",
                    mission="Handle storefront operations and execution follow-up.",
                    goal_kind="store-ops",
                    agent_class="business",
                    activation_mode="persistent",
                    suspendable=False,
                    reports_to="execution-core",
                    risk_level="guarded",
                    environment_constraints=[],
                    allowed_capabilities=[],
                    evidence_expectations=[],
                ),
            ],
        ),
        goals=[
            IndustryDraftGoal(
                goal_id="execution-core-goal",
                kind="execution-core",
                owner_agent_id="copaw-agent-runner",
                title="Operate Northwind Commerce",
                summary="Drive the next operating move.",
                plan_steps=["Review the brief", "Assign the next move"],
            ),
        ],
        schedules=[],
        generation_summary="AI draft.",
    )

    canonicalized = canonicalize_industry_draft(
        profile,
        raw_draft,
        owner_scope="industry-v1-northwind-commerce",
    )

    assert any(agent.role_id == "researcher" for agent in canonicalized.team.agents)
    schedule_titles = {schedule.title for schedule in canonicalized.schedules}
    assert any("Morning Review" in title for title in schedule_titles)
    assert any("Evening Review" in title for title in schedule_titles)
    assert any("Research Signal Loop" in title for title in schedule_titles)


def test_industry_bootstrap_reinjects_default_researcher_when_missing_from_draft(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    preview_response = client.post(
        "/industry/v1/preview",
        json={
            "industry": "Writing Studio",
            "company_name": "Northwind Editorial",
            "product": "ghostwriting services",
            "goals": ["Ship one strong client draft per week"],
        },
    )
    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    draft = preview_payload["draft"]

    draft["team"]["topology"] = "solo"
    draft["team"]["agents"] = [
        agent
        for agent in draft["team"]["agents"]
        if agent["role_id"] != "researcher"
    ]
    researcher_agent_ids = {
        agent["agent_id"]
        for agent in preview_payload["draft"]["team"]["agents"]
        if agent["role_id"] == "researcher"
    }
    draft["goals"] = [
        goal
        for goal in draft["goals"]
        if goal["owner_agent_id"] not in researcher_agent_ids
        and goal["kind"] != "researcher"
    ]
    draft["schedules"] = [
        schedule
        for schedule in draft["schedules"]
        if schedule["owner_agent_id"] not in researcher_agent_ids
    ]

    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": preview_payload["profile"],
            "draft": draft,
            "auto_dispatch": False,
            "execute": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["team"]["topology"] == "solo"
    assert {agent["role_id"] for agent in payload["team"]["agents"]} == {
        "execution-core",
        "researcher",
        "solution-lead",
    }


