# -*- coding: utf-8 -*-
from __future__ import annotations

from .shared import *  # noqa: F401,F403
from copaw.sop_kernel import FixedSopBindingCreateRequest


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


def test_industry_chat_kickoff_background_reuses_team_projection_instead_of_rematerializing_it_per_goal(
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
        instance_id = response.json()["team"]["team_id"]
        materialize_calls = 0
        original = app.state.industry_service._materialize_team_blueprint

        def counted_materialize(record):
            nonlocal materialize_calls
            materialize_calls += 1
            return original(record)

        app.state.industry_service._materialize_team_blueprint = counted_materialize
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

        assert kickoff is not None
        assert kickoff["goal_dispatches"]
        assert materialize_calls <= 3


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
