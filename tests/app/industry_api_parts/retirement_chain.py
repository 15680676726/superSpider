# -*- coding: utf-8 -*-
from __future__ import annotations

from .shared import *  # noqa: F401,F403
from copaw.capabilities.install_templates import InstallTemplateExampleRunRecord
from copaw.industry import IndustryBootstrapInstallItem
from copaw.learning import CapabilityAcquisitionProposal, InstallBindingPlan, OnboardingRun
from copaw.sop_kernel import FixedSopBindingCreateRequest
from copaw.state import DecisionRequestRecord


def test_industry_delete_retired_instance_removes_persisted_runtime_state(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    first_profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Industrial Automation",
            company_name="Northwind Robotics",
            product="factory monitoring copilots",
            goals=["launch two pilot deployments"],
        ),
    )
    first_draft = FakeIndustryDraftGenerator().build_draft(
        first_profile,
        "industry-v1-northwind-robotics",
    )
    first_response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": first_profile.model_dump(mode="json"),
            "draft": first_draft.model_dump(mode="json"),
            "auto_activate": True,
        },
    )
    assert first_response.status_code == 200
    first_payload = first_response.json()
    first_instance_id = first_payload["team"]["team_id"]
    first_goal_ids = [item["goal"]["id"] for item in first_payload["goals"]]
    first_schedule_ids = [item["schedule_id"] for item in first_payload["schedules"]]

    second_profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Social Commerce",
            company_name="Harbor Studio",
            product="XHS content growth services",
            goals=["build the first growth pipeline"],
        ),
    )
    second_draft = FakeIndustryDraftGenerator().build_draft(
        second_profile,
        "industry-v1-harbor-studio",
    )
    second_response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": second_profile.model_dump(mode="json"),
            "draft": second_draft.model_dump(mode="json"),
            "auto_activate": True,
        },
    )
    assert second_response.status_code == 200
    second_instance_id = second_response.json()["team"]["team_id"]

    retired = client.get("/industry/v1/instances?status=retired")
    assert retired.status_code == 200
    assert [item["instance_id"] for item in retired.json()] == [first_instance_id]

    delete_response = client.delete(f"/industry/v1/instances/{first_instance_id}")
    assert delete_response.status_code == 200
    delete_payload = delete_response.json()
    assert delete_payload["deleted"] is True
    assert delete_payload["instance_id"] == first_instance_id
    assert delete_payload["deleted_counts"]["instances"] == 1
    assert delete_payload["deleted_counts"]["goals"] == len(first_goal_ids)
    assert delete_payload["deleted_counts"]["schedules"] == len(first_schedule_ids)

    assert app.state.industry_instance_repository.get_instance(first_instance_id) is None
    assert client.get("/industry/v1/instances?status=retired").json() == []
    assert [item["instance_id"] for item in client.get("/industry/v1/instances").json()] == [
        second_instance_id
    ]
    assert all(app.state.goal_service.get_goal(goal_id) is None for goal_id in first_goal_ids)
    assert all(
        app.state.schedule_repository.get_schedule(schedule_id) is None
        for schedule_id in first_schedule_ids
    )
    assert app.state.agent_thread_binding_repository.list_bindings(
        industry_instance_id=first_instance_id,
        active_only=False,
        limit=None,
    ) == []
    assert (
        client.get(f"/industry/v1/instances/{first_instance_id}").status_code == 404
    )


def test_industry_delete_active_instance_clears_current_team(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Industrial Automation",
            company_name="Northwind Robotics",
            product="factory monitoring copilots",
            goals=["launch two pilot deployments"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )
    bootstrap_response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_activate": True,
        },
    )
    assert bootstrap_response.status_code == 200
    payload = bootstrap_response.json()
    instance_id = payload["team"]["team_id"]
    owner_scope = app.state.industry_instance_repository.get_instance(instance_id).owner_scope
    solution_agent_id = next(
        agent["agent_id"]
        for agent in payload["team"]["agents"]
        if agent["role_id"] == "solution-lead"
    )
    goal_ids = [item["goal"]["id"] for item in payload["goals"]]
    schedule_ids = [item["schedule_id"] for item in payload["schedules"]]
    execution_core_goal = next(
        item for item in payload["goals"] if item["owner_agent_id"] == "copaw-agent-runner"
    )
    execution_core_goal_id = execution_core_goal["goal"]["id"]
    goal_detail_response = client.get(f"/goals/{execution_core_goal_id}/detail")
    assert goal_detail_response.status_code == 200
    goal_tasks = goal_detail_response.json().get("tasks") or []
    if goal_tasks:
        task_id = goal_tasks[0]["task"]["id"]
    else:
        fallback_tasks = app.state.task_repository.list_tasks(
            goal_id=execution_core_goal_id,
            limit=None,
        )
        if fallback_tasks:
            task_id = fallback_tasks[0].id
        else:
            synthetic_task = app.state.task_repository.upsert_task(
                TaskRecord(
                    goal_id=execution_core_goal_id,
                    title="Synthetic execution-core task",
                    summary="Anchor evidence and learning records for delete-instance cleanup.",
                    task_type="goal-step",
                    owner_agent_id="copaw-agent-runner",
                    current_risk_level="guarded",
                ),
            )
            task_id = synthetic_task.id

    base_evidence = app.state.evidence_ledger.append(
        EvidenceRecord(
            task_id=task_id,
            actor_ref="copaw-agent-runner",
            environment_ref=f"session:console:industry:{instance_id}",
            capability_ref="system:dispatch_query",
            risk_level="guarded",
            action_summary="industry delete preflight",
            result_summary="captured evidence before deleting the industry team",
        ),
    )
    proposal = app.state.learning_service.create_proposal(
        title="Tighten operating loop",
        description="Delete this proposal with the industry team.",
        source_agent_id="copaw-agent-runner",
        goal_id=execution_core_goal_id,
        task_id=task_id,
        agent_id="copaw-agent-runner",
        evidence_refs=[base_evidence.id],
    )
    patch_payload = app.state.learning_service.create_patch(
        kind="plan_patch",
        title="Refocus the next move",
        description="Delete this patch with the industry team.",
        goal_id=execution_core_goal_id,
        task_id=task_id,
        agent_id="copaw-agent-runner",
        proposal_id=proposal.id,
        evidence_refs=[base_evidence.id],
        source_evidence_id=base_evidence.id,
        risk_level="confirm",
    )
    created_patch = patch_payload["patch"]
    patch_decision = patch_payload["decision_request"]
    assert patch_decision is not None
    approved_patch = app.state.learning_service.approve_patch(
        created_patch.id,
        approved_by="tester",
    )
    assert approved_patch.id == created_patch.id
    patch_evidence = app.state.evidence_ledger.list_records(
        task_ids=[created_patch.id],
        limit=None,
    )[0]
    growth = app.state.learning_service.engine.record_growth(
        GrowthEvent(
            agent_id="copaw-agent-runner",
            goal_id=execution_core_goal_id,
            task_id=task_id,
            change_type="patch_applied",
            description="Delete this growth event with the industry team.",
            source_patch_id=created_patch.id,
            source_evidence_id=patch_evidence.id,
        ),
    )
    assert app.state.decision_request_repository.list_decision_requests(
        task_id=created_patch.id,
    )
    acquisition_evidence = app.state.evidence_ledger.append(
        EvidenceRecord(
            task_id=f"learning-acquisition:{instance_id}",
            actor_ref="copaw-main-brain",
            capability_ref="learning:install-capability",
            risk_level="guarded",
            action_summary="industry acquisition preflight",
            result_summary="captured acquisition evidence before deleting the industry team",
        ),
    )
    acquisition_proposal = app.state.learning_service.engine.save_acquisition_proposal(
        CapabilityAcquisitionProposal(
            proposal_key=(
                f"{instance_id}:install:solution-lead:"
                f"{solution_agent_id}:browser-local:browser-local-default"
            ),
            industry_instance_id=instance_id,
            owner_scope=owner_scope,
            target_agent_id=solution_agent_id,
            target_role_id="solution-lead",
            acquisition_kind="install-capability",
            title="Install governed browser runtime",
            summary="Delete this acquisition proposal with the industry team.",
            install_item=IndustryBootstrapInstallItem(
                install_kind="builtin-runtime",
                template_id="browser-local",
                client_key="browser-local-default",
                capability_ids=[],
                target_agent_ids=[solution_agent_id],
                target_role_ids=["solution-lead"],
            ),
            evidence_refs=[acquisition_evidence.id],
        ),
        action="created",
    )
    app.state.learning_service.ensure_acquisition_task(acquisition_proposal)
    acquisition_decision = app.state.decision_request_repository.upsert_decision_request(
        DecisionRequestRecord(
            task_id=acquisition_proposal.id,
            decision_type="acquisition-approval",
            risk_level="confirm",
            summary="Delete this acquisition decision with the industry team.",
            requested_by="copaw-main-brain",
        ),
    )
    install_binding_plan = app.state.learning_service.engine.save_install_binding_plan(
        InstallBindingPlan(
            proposal_id=acquisition_proposal.id,
            industry_instance_id=instance_id,
            target_agent_id=solution_agent_id,
            target_role_id="solution-lead",
            status="applied",
            install_item=acquisition_proposal.install_item,
            evidence_refs=[acquisition_evidence.id],
        ),
        action="created",
    )
    onboarding_run = app.state.learning_service.engine.save_onboarding_run(
        OnboardingRun(
            plan_id=install_binding_plan.id,
            proposal_id=acquisition_proposal.id,
            industry_instance_id=instance_id,
            target_agent_id=solution_agent_id,
            target_role_id="solution-lead",
            status="passed",
            summary="Delete this onboarding run with the industry team.",
            checks=[
                {
                    "key": "materialization",
                    "status": "pass",
                    "message": "Install plan materialized.",
                },
            ],
            evidence_refs=[acquisition_evidence.id],
        ),
        action="created",
    )

    delete_response = client.delete(f"/industry/v1/instances/{instance_id}")
    assert delete_response.status_code == 200
    delete_payload = delete_response.json()
    assert delete_payload["deleted"] is True
    assert delete_payload["previous_status"] == "active"
    assert delete_payload["deleted_counts"]["learning_proposals"] == 1
    assert delete_payload["deleted_counts"]["learning_patches"] == 1
    assert delete_payload["deleted_counts"]["learning_growth"] == 1
    assert delete_payload["deleted_counts"]["acquisition_proposals"] == 1
    assert delete_payload["deleted_counts"]["install_binding_plans"] == 1
    assert delete_payload["deleted_counts"]["onboarding_runs"] == 1
    assert delete_payload["deleted_counts"]["evidence"] >= 3
    assert delete_payload["deleted_counts"]["decisions"] >= 2

    assert client.get("/industry/v1/instances").json() == []
    assert app.state.industry_instance_repository.get_instance(instance_id) is None
    assert all(app.state.goal_service.get_goal(goal_id) is None for goal_id in goal_ids)
    assert all(
        app.state.schedule_repository.get_schedule(schedule_id) is None
        for schedule_id in schedule_ids
    )
    assert app.state.evidence_ledger.get_record(base_evidence.id) is None
    assert app.state.evidence_ledger.get_record(patch_evidence.id) is None
    assert app.state.evidence_ledger.get_record(acquisition_evidence.id) is None
    assert not any(
        item.id == proposal.id for item in app.state.learning_service.list_proposals(limit=None)
    )
    assert not any(
        item.id == created_patch.id for item in app.state.learning_service.list_patches(limit=None)
    )
    assert not any(
        item.source_patch_id == created_patch.id
        for item in app.state.learning_service.list_growth(limit=None)
    )
    assert not any(
        item.id == acquisition_proposal.id
        for item in app.state.learning_service.list_acquisition_proposals(limit=None)
    )
    assert app.state.decision_request_repository.get_decision_request(acquisition_decision.id) is None
    assert not any(
        item.id == install_binding_plan.id
        for item in app.state.learning_service.list_install_binding_plans(limit=None)
    )
    assert not any(
        item.id == onboarding_run.id
        for item in app.state.learning_service.list_onboarding_runs(limit=None)
    )
    assert app.state.decision_request_repository.list_decision_requests(
        task_id=created_patch.id,
    ) == []
    with sqlite3.connect(app.state.learning_service.engine.database_path) as conn:
        audit_rows = conn.execute(
            """
            SELECT entity_type, entity_id
            FROM learning_audit_log
            WHERE entity_id IN (?, ?, ?, ?, ?, ?)
            """,
            (
                proposal.id,
                created_patch.id,
                growth.id,
                acquisition_proposal.id,
                install_binding_plan.id,
                onboarding_run.id,
            ),
        ).fetchall()
    assert audit_rows == []
    assert client.get(f"/runtime-center/industry/{instance_id}").status_code == 404


def test_industry_learning_kickoff_materializes_acquisition_objects_and_exposes_them(
    tmp_path,
    monkeypatch,
) -> None:
    async def _fake_example_run(*args, **kwargs):
        return InstallTemplateExampleRunRecord(
            template_id="browser-local",
            status="success",
            started_at="2026-03-22T00:00:00Z",
            finished_at="2026-03-22T00:00:01Z",
            summary="Browser runtime smoke completed",
            operations=["start", "stop"],
        )

    monkeypatch.setattr(
        "copaw.capabilities.install_templates.run_install_template_example",
        _fake_example_run,
    )
    app = _build_industry_app(
        tmp_path,
        draft_generator=BrowserIndustryDraftGenerator(),
    )
    client = TestClient(app)

    profile = IndustryProfile(
        industry="Customer Operations",
        company_name="Northwind Robotics",
        product="Browser onboarding workflows",
        target_customers=["Operators"],
        channels=["Email"],
        goals=["Launch the first governed browser workflow"],
        constraints=["Keep onboarding actions inside the governed browser runtime."],
    )
    draft = BrowserIndustryDraftGenerator().build_draft(profile, "northwind-robotics")

    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_activate": True,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]

    kickoff_result = asyncio.run(
        app.state.industry_service.kickoff_execution_from_chat(
            industry_instance_id=instance_id,
            message_text="Start the first learning cycle now.",
            owner_agent_id="copaw-agent-runner",
            session_id=f"industry:{instance_id}",
            channel="console",
        ),
    )

    assert kickoff_result is not None
    assert kickoff_result["kickoff_stage"] == "learning"
    acquisition_cycle = kickoff_result["acquisition_cycle"]
    assert acquisition_cycle is not None
    assert acquisition_cycle["success"] is True
    assert acquisition_cycle["proposals"]
    assert acquisition_cycle["plans"]
    assert acquisition_cycle["onboarding_runs"]
    assert any(
        item["status"] == "passed" for item in acquisition_cycle["onboarding_runs"]
    )

    detail_response = client.get(f"/industry/v1/instances/{instance_id}")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["acquisition_proposals"]
    assert detail_payload["install_binding_plans"]
    assert detail_payload["onboarding_runs"]
    assert any(
        item["key"] == "trial-run:browser-local" and item["status"] == "pass"
        for run in detail_payload["onboarding_runs"]
        for item in run["checks"]
    )
    assert detail_payload["stats"]["acquisition_proposal_count"] == len(
        detail_payload["acquisition_proposals"],
    )
    assert detail_payload["stats"]["install_binding_plan_count"] == len(
        detail_payload["install_binding_plans"],
    )
    assert detail_payload["stats"]["onboarding_run_count"] == len(
        detail_payload["onboarding_runs"],
    )
    assert detail_payload["routes"]["acquisition_proposals"]
    assert detail_payload["routes"]["install_binding_plans"]
    assert detail_payload["routes"]["onboarding_runs"]


def test_industry_rebootstrap_preserves_actor_identity_and_records_semantic_drift(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    owner_scope = "industry-v1-northwind-robotics"
    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Industrial Automation",
            company_name="Northwind Robotics",
            product="factory monitoring copilots",
            goals=["launch two pilot deployments"],
        ),
    )
    initial_draft = FakeIndustryDraftGenerator().build_draft(profile, owner_scope)

    first_response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": initial_draft.model_dump(mode="json"),
            "auto_activate": True,
        },
    )
    assert first_response.status_code == 200
    first_payload = first_response.json()
    instance_id = first_payload["team"]["team_id"]
    first_solution_role = next(
        agent
        for agent in first_payload["team"]["agents"]
        if agent["role_id"] == "solution-lead"
    )
    stable_agent_id = first_solution_role["agent_id"]
    stable_actor_key = first_solution_role["actor_key"]

    runtime_before = app.state.agent_runtime_repository.get_runtime(stable_agent_id)
    assert runtime_before is not None
    baseline_fingerprint = runtime_before.actor_fingerprint
    assert baseline_fingerprint == first_solution_role["actor_fingerprint"]

    drifted_draft = FakeIndustryDraftGenerator().build_draft(profile, owner_scope)
    drifted_solution_role = next(
        role for role in drifted_draft.team.agents if role.role_id == "solution-lead"
    )
    drifted_solution_role.role_name = "Workflow Architect"
    drifted_solution_role.name = "Northwind Workflow Architect"
    drifted_solution_role.role_summary = "Owns workflow design and rollout framing."
    drifted_solution_role.mission = (
        "Turn the brief into a rollout-ready operating workflow."
    )

    second_response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": drifted_draft.model_dump(mode="json"),
            "auto_activate": True,
        },
    )
    assert second_response.status_code == 200
    second_payload = second_response.json()
    second_solution_role = next(
        agent
        for agent in second_payload["team"]["agents"]
        if agent["role_id"] == "solution-lead"
    )

    assert second_payload["team"]["team_id"] == instance_id
    assert second_solution_role["agent_id"] == stable_agent_id
    assert second_solution_role["actor_key"] == stable_actor_key
    assert second_solution_role["actor_fingerprint"] != baseline_fingerprint

    stored_instance = app.state.industry_instance_repository.get_instance(instance_id)
    assert stored_instance is not None
    stored_solution_role = next(
        agent
        for agent in stored_instance.team_payload["agents"]
        if agent["role_id"] == "solution-lead"
    )
    assert stored_solution_role["agent_id"] == stable_agent_id
    assert stored_solution_role["actor_key"] == stable_actor_key

    runtime_after = app.state.agent_runtime_repository.get_runtime(stable_agent_id)
    assert runtime_after is not None
    assert runtime_after.actor_key == stable_actor_key
    assert runtime_after.actor_fingerprint == second_solution_role["actor_fingerprint"]
    drift = runtime_after.metadata.get("actor_semantic_drift")
    assert drift is not None
    assert drift["previous_fingerprint"] == baseline_fingerprint
    assert drift["current_fingerprint"] == runtime_after.actor_fingerprint
    assert drift["detected_at"]


def test_industry_chat_kickoff_executes_in_background_without_blocking_response(
    tmp_path,
) -> None:
    app = _build_industry_app(
        tmp_path,
        turn_executor=SlowTurnExecutor(delay_seconds=0.2),
    )
    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Industrial Automation",
            company_name="Northwind Robotics",
            product="factory monitoring copilots",
            business_model="B2B software and implementation services",
            channels=["industry events", "integrator partners"],
            goals=["launch two pilot deployments"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )

    with TestClient(app) as client:
        response = client.post(
            "/industry/v1/bootstrap",
            json={
                "profile": profile.model_dump(mode="json"),
                "draft": draft.model_dump(mode="json"),
                "auto_activate": False,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        instance_id = payload["team"]["team_id"]

        started_at = time.perf_counter()
        kickoff = asyncio.run(
            app.state.industry_service.kickoff_execution_from_chat(
                industry_instance_id=instance_id,
                message_text="Start the first execution cycle for today.",
                owner_agent_id="copaw-agent-runner",
                session_id=f"industry:{instance_id}",
                channel="console",
                execute_background=True,
            ),
        )
        elapsed = time.perf_counter() - started_at

        assert kickoff is not None
        assert kickoff["goal_dispatches"]
        assert all(
            item["scheduled_execution"]
            for dispatch in kickoff["goal_dispatches"]
            for item in dispatch["dispatch_results"]
        )

        all_task_ids = [
            item["task_id"]
            for dispatch in kickoff["goal_dispatches"]
            for item in dispatch["dispatch_results"]
        ]
        immediate_statuses = [
            app.state.task_repository.get_task(task_id).status
            for task_id in all_task_ids
        ]
        assert any(status != "completed" for status in immediate_statuses), (
            elapsed,
            immediate_statuses,
        )
        assert elapsed < 1.0


def test_industry_bootstrap_defaults_to_live_learning_contract(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    profile = normalize_industry_profile(
        IndustryPreviewRequest(
            industry="Industrial Automation",
            company_name="Northwind Robotics",
            product="factory monitoring copilots",
            business_model="B2B software and implementation services",
            channels=["industry events", "integrator partners"],
            goals=["launch two pilot deployments"],
        ),
    )
    draft = FakeIndustryDraftGenerator().build_draft(
        profile,
        "industry-v1-northwind-robotics",
    )

    with TestClient(app) as client:
        response = client.post(
            "/industry/v1/bootstrap",
            json={
                "profile": profile.model_dump(mode="json"),
                "draft": draft.model_dump(mode="json"),
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["goals"]
        dispatch_by_kind = {
            item["kind"]: bool(item.get("dispatch"))
            for item in payload["goals"]
        }
        assert dispatch_by_kind["researcher"] is True
        assert dispatch_by_kind["execution-core"] is True
        assert dispatch_by_kind["solution"] is True

        instance_id = payload["team"]["team_id"]
        runtime_payload = client.get(f"/runtime-center/industry/{instance_id}").json()
        assert runtime_payload["autonomy_status"] == "learning"
        assert runtime_payload["execution"]["status"] == "learning"
        assert runtime_payload["current_cycle"]["status"] == "active"
        assert all(goal["status"] == "active" for goal in runtime_payload["goals"])
        assert all(schedule["enabled"] is True for schedule in runtime_payload["schedules"])


def test_industry_runtime_detail_and_goal_detail_use_formal_instance_store(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": normalize_industry_profile(
                IndustryPreviewRequest(
                    industry="Industrial Automation",
                    company_name="Northwind Robotics",
                    product="factory monitoring copilots",
                    business_model="B2B software and implementation services",
                    channels=["industry events", "integrator partners"],
                    goals=["launch two pilot deployments"],
                ),
            ).model_dump(mode="json"),
            "draft": FakeIndustryDraftGenerator()
            .build_draft(
                normalize_industry_profile(
                    IndustryPreviewRequest(
                        industry="Industrial Automation",
                        company_name="Northwind Robotics",
                        product="factory monitoring copilots",
                        business_model="B2B software and implementation services",
                        channels=["industry events", "integrator partners"],
                        goals=["launch two pilot deployments"],
                    ),
                ),
                "industry-v1-northwind-robotics",
            )
            .model_dump(mode="json"),
            "auto_activate": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    instance_id = payload["team"]["team_id"]
    kickoff = asyncio.run(
        app.state.industry_service.kickoff_execution_from_chat(
            industry_instance_id=instance_id,
            message_text="Start the first execution cycle for today.",
            owner_agent_id="copaw-agent-runner",
            session_id=f"industry:{instance_id}",
            channel="console",
        ),
    )
    assert kickoff is not None
    assert kickoff["started_goal_ids"]

    summaries = client.get("/industry/v1/instances")
    assert summaries.status_code == 200
    summary = summaries.json()[0]
    assert summary["instance_id"] == instance_id
    assert "goal_count" not in summary["stats"]
    assert "active_goal_count" not in summary["stats"]
    assert summary["stats"]["schedule_count"] == len(payload["schedules"])

    goal_id = kickoff["started_goal_ids"][0]
    goal_detail = client.get(f"/goals/{goal_id}/detail")
    assert goal_detail.status_code == 200
    goal_payload = goal_detail.json()
    assert goal_payload["industry"]["instance_id"] == instance_id
    assert goal_payload["industry"]["label"] == payload["team"]["label"]
    assert len(goal_payload["tasks"]) >= 1

    task_id = goal_payload["tasks"][0]["task"]["id"]
    app.state.evidence_ledger.append(
        EvidenceRecord(
            task_id=task_id,
            actor_ref="copaw-agent-runner",
            environment_ref=f"session:console:industry:{instance_id}",
            capability_ref="system:dispatch_query",
            risk_level="guarded",
            action_summary="industry daily signal",
            result_summary="captured operator evidence for the industry instance",
        ),
    )
    proposal = app.state.learning_service.create_proposal(
        title="Tighten pilot rollout",
        description="Focus the next deployment wave on the highest-fit pilot sites.",
        source_agent_id="copaw-agent-runner",
        goal_id=goal_id,
        task_id=task_id,
        agent_id="copaw-agent-runner",
    )
    assert proposal.goal_id == goal_id

    detail = client.get(f"/industry/v1/instances/{instance_id}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["instance_id"] == instance_id
    assert detail_payload["routes"]["runtime_detail"] == (
        f"/api/runtime-center/industry/{instance_id}"
    )
    assert "goal_count" not in detail_payload["stats"]
    assert "active_goal_count" not in detail_payload["stats"]
    assert detail_payload["stats"]["schedule_count"] == len(payload["schedules"])
    assert detail_payload["reports"]["daily"]["evidence_count"] >= 1
    assert detail_payload["reports"]["daily"]["proposal_count"] >= 1
    assert any(goal["agent_class"] == "business" for goal in detail_payload["goals"])

    runtime_detail = client.get(f"/runtime-center/industry/{instance_id}")
    assert runtime_detail.status_code == 200
    runtime_payload = runtime_detail.json()
    assert runtime_payload["instance_id"] == instance_id
    assert runtime_payload["stats"]["schedule_count"] == len(payload["schedules"])
    assert runtime_payload["reports"]["daily"]["recent_evidence"][0]["task_id"] == task_id
    nodes_by_id = {
        node["node_id"]: node for node in runtime_payload["main_chain"]["nodes"]
    }
    assert "goal_count" not in nodes_by_id["carrier"]["metrics"]
    assert "active_goal_count" not in nodes_by_id["strategy"]["metrics"]
    assert "active_goal_count" not in nodes_by_id["instance-reconcile"]["metrics"]
    assert "goals." not in nodes_by_id["carrier"]["summary"]


def test_industry_bootstrap_auto_activate_enters_live_learning_contract(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = IndustryProfile(
        industry="Industrial Equipment",
        company_name="Northwind Robotics",
        product="Predictive maintenance deployments",
        target_customers=["Factory operators"],
        channels=["LinkedIn"],
        goals=["Launch the first operator-ready execution loop"],
        constraints=["Operator confirmation required before the first launch"],
    )
    draft = FakeIndustryDraftGenerator().build_draft(profile, "northwind-robotics")

    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_activate": True,
        },
    )

    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]

    runtime_detail = client.get(f"/runtime-center/industry/{instance_id}")
    assert runtime_detail.status_code == 200
    runtime_payload = runtime_detail.json()
    assert runtime_payload["autonomy_status"] == "learning"
    assert runtime_payload["execution"]["status"] == "learning"
    assert all(goal["status"] == "active" for goal in runtime_payload["goals"])
    assert all(schedule["enabled"] is True for schedule in runtime_payload["schedules"])
    assert runtime_payload["current_cycle"]["status"] == "active"
    node_ids = [node["node_id"] for node in runtime_payload["main_chain"]["nodes"]]
    assert "goal" not in node_ids
    assert "task" not in node_ids

    kickoff_result = asyncio.run(
        app.state.industry_service.kickoff_execution_from_chat(
            industry_instance_id=instance_id,
            message_text="Start the first execution cycle for today.",
            owner_agent_id="copaw-agent-runner",
            session_id=f"industry:{instance_id}",
            channel="console",
        ),
    )
    assert kickoff_result is not None
    assert kickoff_result["activated"] is False
    assert kickoff_result["kickoff_stage"] == "learning"
    assert kickoff_result["blocked_stage"] == "learning"
    assert kickoff_result["started_goal_ids"] == []


def test_industry_runtime_main_chain_exposes_live_assignment_chain_after_auto_activate(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = IndustryProfile(
        industry="Industrial Equipment",
        company_name="Northwind Robotics",
        product="Predictive maintenance deployments",
        target_customers=["Factory operators"],
        channels=["LinkedIn"],
        goals=["Launch the first operator-ready execution loop"],
        constraints=["Operator confirmation required before the first launch"],
    )
    draft = FakeIndustryDraftGenerator().build_draft(profile, "northwind-robotics")

    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_activate": True,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]

    waiting_payload = client.get(f"/runtime-center/industry/{instance_id}").json()
    assert waiting_payload["autonomy_status"] == "learning"
    assert waiting_payload["execution"]["status"] == "learning"
    target_goal = next(
        goal
        for goal in waiting_payload["goals"]
        if goal["owner_agent_id"] != "copaw-agent-runner"
    )
    target_goal_id = target_goal["goal_id"]
    target_owner_agent_id = target_goal["owner_agent_id"]
    target_role_id = target_goal["role_id"]
    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None
    goal_record = app.state.goal_service.get_goal(target_goal_id)
    assert goal_record is not None
    assert goal_record.industry_instance_id == instance_id
    assert goal_record.lane_id
    lane = app.state.operating_lane_service.get_lane(goal_record.lane_id)
    assert lane is not None
    assert lane.owner_agent_id == target_owner_agent_id
    original_goal_ids = list(record.goal_ids or [])
    app.state.industry_instance_repository.upsert_instance(
        record.model_copy(
            update={
                "goal_ids": [
                    goal_id for goal_id in original_goal_ids if goal_id != target_goal_id
                ],
            },
        ),
    )
    trimmed_record = app.state.industry_instance_repository.get_instance(instance_id)
    assert trimmed_record is not None
    assert target_goal_id in app.state.industry_service._resolve_instance_goal_ids(
        trimmed_record,
    )
    app.state.industry_instance_repository.upsert_instance(
        trimmed_record.model_copy(update={"goal_ids": original_goal_ids}),
    )
    target_override = app.state.goal_override_repository.get_override(target_goal_id)
    assert target_override is not None
    app.state.goal_override_repository.upsert_override(
        target_override.model_copy(
            update={
                "compiler_context": {
                    "bootstrap_kind": "industry-v1",
                    "report_back_mode": (
                        target_override.compiler_context.get("report_back_mode")
                        if isinstance(target_override.compiler_context, dict)
                        else None
                    )
                    or "summary",
                },
            },
        ),
    )
    refreshed_record = app.state.industry_instance_repository.get_instance(instance_id)
    assert refreshed_record is not None
    context_by_agent = app.state.industry_service._build_instance_goal_context_by_agent(
        record=refreshed_record,
    )
    assert target_owner_agent_id in context_by_agent
    stripped_payload = client.get(f"/runtime-center/industry/{instance_id}").json()
    stripped_goal = next(
        goal for goal in stripped_payload["goals"] if goal["goal_id"] == target_goal_id
    )
    assert stripped_goal["owner_agent_id"] == target_owner_agent_id
    assert stripped_goal["role_id"] == target_role_id
    active_goal_links = app.state.industry_service._list_active_goal_links_for_instance(
        refreshed_record,
    )
    assert active_goal_links.get(target_owner_agent_id) == (
        target_goal_id,
        goal_record.title,
    )

    runtime_detail = client.get(f"/runtime-center/industry/{instance_id}")
    assert runtime_detail.status_code == 200
    runtime_payload = runtime_detail.json()
    assert runtime_payload["execution"]["status"] == "learning"
    assert runtime_payload["team"]["status"] in {"learning", "coordinating", "active", "running"}

    nodes = {node["node_id"]: node for node in runtime_payload["main_chain"]["nodes"]}
    assert nodes["strategy"]["truth_source"] == "StrategyMemoryRecord"
    assert nodes["strategy"]["route"].endswith(f"industry_instance_id={instance_id}")
    assert nodes["instance-reconcile"]["backflow_port"] == (
        "IndustryService._sync_strategy_memory_for_instance()"
    )
    assert "goal" not in nodes
    assert "task" not in nodes
    assert nodes["assignment"]["current_ref"] is not None
    assert nodes["cycle"]["current_ref"] is not None


def test_industry_operating_cycle_closes_through_fixed_sop_report_and_strategy_sync(
    tmp_path,
) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = IndustryProfile(
        industry="Industrial Equipment",
        company_name="Northwind Robotics",
        product="Predictive maintenance deployments",
        target_customers=["Factory operators"],
        channels=["LinkedIn"],
        goals=["Launch the first operator-ready execution loop"],
        constraints=["Use the SOP-bound solution lane for repeatable execution."],
    )
    draft = FakeIndustryDraftGenerator().build_draft(profile, "northwind-robotics")

    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_activate": False,
            "auto_dispatch": False,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]
    owner_scope = app.state.industry_instance_repository.get_instance(instance_id).owner_scope

    runtime_payload = client.get(f"/runtime-center/industry/{instance_id}").json()
    solution_lane = next(
        lane
        for lane in runtime_payload["lanes"]
        if lane["owner_role_id"] == "solution-lead"
    )
    solution_agent_id = solution_lane["owner_agent_id"]

    binding = app.state.fixed_sop_service.create_binding(
        FixedSopBindingCreateRequest(
            template_id="fixed-sop-http-routine-bridge",
            binding_name="Solution Lane Fixed SOP",
            status="active",
            owner_scope=owner_scope,
            owner_agent_id=solution_agent_id,
            industry_instance_id=instance_id,
            metadata={"binding_source": "industry-test"},
        ),
    )

    backlog_item = app.state.industry_service._backlog_service.record_chat_writeback(
        industry_instance_id=instance_id,
        lane_id=solution_lane["lane_id"],
        title="Run the SOP-bound solution lane",
        summary="Use the governed SOP binding instead of a free-form query step.",
        priority=5,
        source_ref="test:sop-binding-backlog",
        metadata={
            "owner_agent_id": solution_agent_id,
            "industry_role_id": "solution-lead",
            "industry_role_name": solution_lane.get("title"),
            "role_name": solution_lane.get("title"),
            "role_summary": solution_lane.get("summary"),
            "mission": solution_lane.get("summary"),
            "goal_kind": "solution",
            "task_mode": "autonomy-cycle",
            "report_back_mode": "summary",
            "fixed_sop_binding_id": binding.binding.binding_id,
            "fixed_sop_binding_name": binding.binding.binding_name,
            "fixed_sop_source_type": "assignment",
            "fixed_sop_source_ref": "test:sop-binding-backlog",
            "fixed_sop_input_payload": {"window": "today"},
            "plan_steps": ["Trigger the governed SOP binding and return the result."],
        },
    )

    first_cycle = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:sop-binding-cycle",
            force=True,
            auto_dispatch_materialized_goals=True,
        ),
    )
    assert first_cycle["count"] == 1
    processed_instance = first_cycle["processed_instances"][0]
    assert processed_instance["started_cycle_id"] is not None
    assert processed_instance["created_goal_ids"] == []
    assert processed_instance["created_assignment_ids"]
    assert processed_instance["created_task_ids"]
    created_task = app.state.task_repository.get_task(
        processed_instance["created_task_ids"][0],
    )
    assert created_task is not None
    assert created_task.goal_id is None
    assert created_task.assignment_id == processed_instance["created_assignment_ids"][0]
    assert created_task.task_type == "system:run_fixed_sop"

    second_cycle = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:sop-binding-reconcile",
            force=True,
        ),
    )
    assert second_cycle["count"] == 1
    assert second_cycle["processed_instances"][0]["processed_report_ids"]

    refreshed = client.get(f"/runtime-center/industry/{instance_id}")
    assert refreshed.status_code == 200
    refreshed_payload = refreshed.json()

    assignment = next(
        assignment
        for assignment in refreshed_payload["assignments"]
        if assignment["assignment_id"] == processed_instance["created_assignment_ids"][0]
    )
    assert assignment["metadata"]["fixed_sop_binding_id"] == binding.binding.binding_id
    assert "sop_binding_id" not in assignment["metadata"]

    report = next(
        report
        for report in refreshed_payload["agent_reports"]
        if report["assignment_id"] == processed_instance["created_assignment_ids"][0]
    )
    assert report["result"] == "completed"
    assert report["metadata"]["fixed_sop_binding_id"] == binding.binding.binding_id
    assert "sop_binding_id" not in report["metadata"]
    assert report["evidence_ids"]

    nodes = {node["node_id"]: node for node in refreshed_payload["main_chain"]["nodes"]}
    assert nodes["routine"]["truth_source"] == "FixedSopBindingRecord + WorkflowRunRecord + EvidenceRecord"
    assert nodes["routine"]["current_ref"] == binding.binding.binding_id
    assert nodes["report"]["current_ref"] == report["report_id"]
    assert refreshed_payload["strategy_memory"]["strategy_id"]
    assert backlog_item.id not in {
        item["backlog_item_id"]
        for item in refreshed_payload["backlog"]
        if item["status"] in {"open", "selected"}
    }


def test_industry_operating_cycle_preflight_opens_morning_review_window(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = IndustryProfile(
        industry="Industrial Equipment",
        company_name="Northwind Robotics",
        product="Predictive maintenance deployments",
        target_customers=["Factory operators"],
        channels=["LinkedIn"],
        goals=["Launch the first operator-ready execution loop"],
    )
    draft = FakeIndustryDraftGenerator().build_draft(profile, "northwind-robotics")
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_activate": True,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]

    app.state.industry_service._current_prediction_review_window = lambda: "morning"
    should_run, reason = app.state.industry_service.should_run_operating_cycle()
    assert should_run is True
    assert reason in {"open-backlog", "review-window:morning"}
    record = app.state.industry_instance_repository.get_instance(instance_id)
    assert record is not None
    assert (
        app.state.industry_service._due_prediction_review_window(record=record)
        == "morning"
    )

    cycle_result = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:morning-review-window",
            force=False,
        ),
    )
    assert cycle_result["count"] == 1
    assert cycle_result["processed_instances"][0]["created_prediction_case_id"] is not None


def test_industry_operating_cycle_emits_cycle_prediction_opportunities(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    profile = IndustryProfile(
        industry="Industrial Equipment",
        company_name="Northwind Robotics",
        product="Predictive maintenance deployments",
        target_customers=["Factory operators"],
        channels=["LinkedIn"],
        goals=["Launch the first operator-ready execution loop"],
    )
    draft = FakeIndustryDraftGenerator().build_draft(profile, "northwind-robotics")
    response = client.post(
        "/industry/v1/bootstrap",
        json={
            "profile": profile.model_dump(mode="json"),
            "draft": draft.model_dump(mode="json"),
            "auto_activate": False,
            "auto_dispatch": False,
            "execute": False,
        },
    )
    assert response.status_code == 200
    instance_id = response.json()["team"]["team_id"]

    runtime_payload = client.get(f"/runtime-center/industry/{instance_id}").json()
    execution_lane = next(
        lane
        for lane in runtime_payload["lanes"]
        if lane["owner_role_id"] == "execution-core"
    )
    app.state.industry_service._backlog_service.record_chat_writeback(
        industry_instance_id=instance_id,
        lane_id=execution_lane["lane_id"],
        title="Review the next operating bottleneck",
        summary="Main brain should inspect the current operator bottleneck before dispatch.",
        priority=5,
        source_ref="test:cycle-prediction-input",
        metadata={
            "owner_agent_id": execution_lane["owner_agent_id"],
            "industry_role_id": "execution-core",
            "industry_role_name": execution_lane.get("title"),
            "goal_kind": "execution-core",
            "task_mode": "autonomy-cycle",
            "report_back_mode": "summary",
            "plan_steps": ["Inspect the current bottleneck and propose the next governed move."],
        },
    )

    cycle_result = asyncio.run(
        app.state.industry_service.run_operating_cycle(
            instance_id=instance_id,
            actor="test:cycle-prediction",
            force=True,
        ),
    )
    assert cycle_result["count"] == 1
    processed = cycle_result["processed_instances"][0]
    assert processed["created_prediction_case_id"] is not None
    assert processed["created_prediction_backlog_ids"]

    cycle_cases = app.state.prediction_service.list_cases(
        case_kind="cycle",
        industry_instance_id=instance_id,
    )
    assert len(cycle_cases) == 1

    refreshed_payload = client.get(f"/runtime-center/industry/{instance_id}").json()
    prediction_items = [
        item
        for item in refreshed_payload["backlog"]
        if item["backlog_item_id"] in processed["created_prediction_backlog_ids"]
    ]
    assert prediction_items
    assert all(item["source_kind"] == "prediction" for item in prediction_items)
