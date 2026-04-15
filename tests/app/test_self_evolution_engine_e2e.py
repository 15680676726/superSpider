# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from copaw.app.routers.learning import router as learning_router
from copaw.capabilities.install_templates import InstallTemplateExampleRunRecord
from copaw.evidence.models import EvidenceRecord
from copaw.state.repositories import SqliteCapabilityOverrideRepository
from tests.app.industry_api_parts.shared import (
    BrowserIndustryDraftGenerator,
    _build_industry_app,
    bootstrap_goal_by_owner,
)


class _SelectiveFailingTurnExecutor:
    def __init__(self) -> None:
        self.fail_session_ids: set[str] = set()
        self.requests: list[tuple[object, dict[str, object]]] = []

    async def stream_request(self, request, **kwargs):
        self.requests.append((request, dict(kwargs)))
        session_id = ""
        if isinstance(request, dict):
            session_id = str(request.get("session_id") or "")
        if session_id in self.fail_session_ids:
            yield {
                "object": "message",
                "status": "failed",
                "error": {"message": "query runtime failed"},
                "request": request,
            }
            return
        yield {
            "object": "message",
            "status": "completed",
            "request": request,
            "kwargs": kwargs,
        }


def _close_test_app(app) -> None:
    close_ledger = getattr(getattr(app.state, "evidence_ledger", None), "close", None)
    if callable(close_ledger):
        close_ledger()


def _inject_capability_patch_repository(app) -> SqliteCapabilityOverrideRepository:
    repository = SqliteCapabilityOverrideRepository(app.state.state_store)
    app.state.learning_service._patch_executor._capability_override_repo = repository
    app.state.capability_override_repository = repository
    return repository


def _compile_goal_specs(app, goal_id: str, *, owner_agent_id: str) -> list[dict[str, object]]:
    return [
        spec.model_dump(mode="json")
        for spec in app.state.goal_service.compile_goal(
            goal_id,
            context={"owner_agent_id": owner_agent_id},
        )
    ]


def test_self_evolution_engine_runs_full_loop_and_survives_restart(
    tmp_path,
    monkeypatch,
) -> None:
    async def _fake_example_run(*args, **kwargs):
        return InstallTemplateExampleRunRecord(
            template_id="browser-local",
            status="success",
            started_at="2026-04-15T00:00:00Z",
            finished_at="2026-04-15T00:00:01Z",
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
    app.include_router(learning_router)
    capability_override_repository = _inject_capability_patch_repository(app)

    try:
        client = TestClient(app)

        preview = client.post(
            "/industry/v1/preview",
            json={
                "industry": "Customer Operations",
                "company_name": "Northwind Robotics",
                "product": "browser onboarding workflows",
            },
        )
        assert preview.status_code == 200
        preview_payload = preview.json()

        bootstrap = client.post(
            "/industry/v1/bootstrap",
            json={
                "profile": preview_payload["profile"],
                "draft": preview_payload["draft"],
                "auto_activate": True,
                "auto_dispatch": True,
                "execute": False,
            },
        )
        assert bootstrap.status_code == 200
        bootstrap_payload = bootstrap.json()
        instance_id = bootstrap_payload["team"]["team_id"]
        execution_core_goal_id = bootstrap_goal_by_owner(
            bootstrap_payload,
            "copaw-agent-runner",
        )["goal_id"]

        runtime_detail_after_bootstrap = client.get(
            f"/runtime-center/industry/{instance_id}",
        )
        assert runtime_detail_after_bootstrap.status_code == 200
        runtime_payload = runtime_detail_after_bootstrap.json()
        assignment_entry = next(
            item
            for item in runtime_payload["assignments"]
            if item.get("task_id") and item.get("assignment_id")
        )
        task_id = str(assignment_entry["task_id"])
        assignment_id = str(assignment_entry["assignment_id"])
        owner_agent_id = str(assignment_entry["owner_agent_id"])

        task_record = app.state.task_repository.get_task(task_id)
        assert task_record is not None
        assert task_record.goal_id
        assignment_goal_id = str(task_record.goal_id)

        acquisition = client.post(
            "/learning/acquisition/run",
            json={"industry_instance_id": instance_id},
        )
        assert acquisition.status_code == 200
        acquisition_payload = acquisition.json()
        assert acquisition_payload["success"] is True
        assert acquisition_payload["proposals_processed"] >= 1
        assert acquisition_payload["plans_materialized"] >= 1
        assert acquisition_payload["onboarding_passed"] >= 1

        instance_detail = client.get(f"/industry/v1/instances/{instance_id}")
        assert instance_detail.status_code == 200
        instance_payload = instance_detail.json()
        assert instance_payload["acquisition_proposals"]
        assert instance_payload["install_binding_plans"]
        assert instance_payload["onboarding_runs"]

        failed_evidence_ids: list[str] = []
        for idx in range(3):
            failed_evidence = app.state.evidence_ledger.append(
                EvidenceRecord(
                    task_id=task_id,
                    actor_ref=owner_agent_id,
                    capability_ref="tool:unstable_browser_step",
                    risk_level="guarded",
                    action_summary=f"browser step failure {idx + 1}",
                    result_summary="error: governed browser step failed",
                    status="failed",
                ),
            )
            failed_evidence_ids.append(failed_evidence.id)

        strategy = client.post(
            "/learning/automation/strategy",
            json={
                "actor": "copaw-main-brain",
                "limit": 20,
                "auto_apply": True,
                "auto_rollback": False,
                "failure_threshold": 2,
                "confirm_threshold": 6,
                "max_proposals": 3,
            },
        )
        assert strategy.status_code == 200
        strategy_payload = strategy.json()
        assert strategy_payload["success"] is True
        assert strategy_payload["proposals_created"] == 1
        assert strategy_payload["patches_created"] == 1
        assert len(strategy_payload["auto_applied"]) == 1

        proposal_id = str(strategy_payload["proposals"][0]["id"])
        patch_id = str(strategy_payload["patches"][0]["id"])
        assert strategy_payload["patches"][0]["status"] == "applied"

        override = capability_override_repository.get_override(
            "tool:unstable_browser_step",
        )
        assert override is not None
        assert override.source_patch_id == patch_id

        runtime_patches = client.get(
            "/runtime-center/learning/patches",
            params={"task_id": task_id},
        )
        assert runtime_patches.status_code == 200
        patch_payloads = runtime_patches.json()
        assert any(item["id"] == patch_id for item in patch_payloads)

        runtime_growth = client.get(
            "/runtime-center/learning/growth",
            params={"task_id": task_id},
        )
        assert runtime_growth.status_code == 200
        growth_payloads = runtime_growth.json()
        linked_growth_ids = {
            str(item["id"])
            for item in growth_payloads
            if str(item.get("source_patch_id") or "") == patch_id
        }
        assert linked_growth_ids

        detail_after_strategy = client.get(f"/runtime-center/industry/{instance_id}")
        assert detail_after_strategy.status_code == 200
        closure = detail_after_strategy.json()["optimization_closure"]
        assert closure["counts"]["proposals"] >= 1
        assert closure["counts"]["patches"] >= 1
        assert closure["counts"]["growth"] >= 1
        linked_entry = next(
            item
            for item in closure["links"]
            if item["task_id"] == task_id and item["assignment_id"] == assignment_id
        )
        assert proposal_id in linked_entry["proposal_ids"]
        assert patch_id in linked_entry["patch_ids"]
        assert linked_growth_ids.issubset(set(linked_entry["growth_ids"]))

        compiled_specs = _compile_goal_specs(
            app,
            assignment_goal_id,
            owner_agent_id=owner_agent_id,
        )
        assert compiled_specs
        compiler_meta = compiled_specs[0]["payload"]["compiler"]
        assert patch_id in compiler_meta["feedback_patch_ids"]
        assert linked_growth_ids.issubset(set(compiler_meta["feedback_growth_ids"]))
        assert set(failed_evidence_ids).issubset(set(compiler_meta["feedback_evidence_refs"]))

    finally:
        _close_test_app(app)

    restarted_app = _build_industry_app(
        tmp_path,
        draft_generator=BrowserIndustryDraftGenerator(),
    )
    restarted_app.include_router(learning_router)
    _inject_capability_patch_repository(restarted_app)

    try:
        restarted_client = TestClient(restarted_app)

        restarted_patches = restarted_client.get(
            "/runtime-center/learning/patches",
            params={"task_id": task_id},
        )
        assert restarted_patches.status_code == 200
        assert any(item["id"] == patch_id for item in restarted_patches.json())

        restarted_growth = restarted_client.get(
            "/runtime-center/learning/growth",
            params={"task_id": task_id},
        )
        assert restarted_growth.status_code == 200
        restarted_growth_ids = {
            str(item["id"])
            for item in restarted_growth.json()
            if str(item.get("source_patch_id") or "") == patch_id
        }
        assert linked_growth_ids == restarted_growth_ids

        restarted_detail = restarted_client.get(
            f"/runtime-center/industry/{instance_id}",
        )
        assert restarted_detail.status_code == 200
        restarted_closure = restarted_detail.json()["optimization_closure"]
        restarted_link = next(
            item
            for item in restarted_closure["links"]
            if item["task_id"] == task_id and item["assignment_id"] == assignment_id
        )
        assert proposal_id in restarted_link["proposal_ids"]
        assert patch_id in restarted_link["patch_ids"]
        assert linked_growth_ids.issubset(set(restarted_link["growth_ids"]))

        restarted_compiled_specs = _compile_goal_specs(
            restarted_app,
            assignment_goal_id,
            owner_agent_id=owner_agent_id,
        )
        assert restarted_compiled_specs
        restarted_compiler_meta = restarted_compiled_specs[0]["payload"]["compiler"]
        assert patch_id in restarted_compiler_meta["feedback_patch_ids"]
        assert linked_growth_ids.issubset(
            set(restarted_compiler_meta["feedback_growth_ids"]),
        )
        assert set(failed_evidence_ids).issubset(
            set(restarted_compiler_meta["feedback_evidence_refs"]),
        )
    finally:
        _close_test_app(restarted_app)


def test_self_evolution_engine_generates_failure_evidence_via_formal_execution_chain(
    tmp_path,
    monkeypatch,
) -> None:
    async def _fake_example_run(*args, **kwargs):
        return InstallTemplateExampleRunRecord(
            template_id="browser-local",
            status="success",
            started_at="2026-04-15T00:00:00Z",
            finished_at="2026-04-15T00:00:01Z",
            summary="Browser runtime smoke completed",
            operations=["start", "stop"],
        )

    monkeypatch.setattr(
        "copaw.capabilities.install_templates.run_install_template_example",
        _fake_example_run,
    )

    turn_executor = _SelectiveFailingTurnExecutor()
    app = _build_industry_app(
        tmp_path,
        draft_generator=BrowserIndustryDraftGenerator(),
        turn_executor=turn_executor,
    )
    app.include_router(learning_router)
    capability_override_repository = _inject_capability_patch_repository(app)

    try:
        client = TestClient(app)

        preview = client.post(
            "/industry/v1/preview",
            json={
                "industry": "Customer Operations",
                "company_name": "Northwind Robotics",
                "product": "browser onboarding workflows",
            },
        )
        assert preview.status_code == 200
        preview_payload = preview.json()

        bootstrap = client.post(
            "/industry/v1/bootstrap",
            json={
                "profile": preview_payload["profile"],
                "draft": preview_payload["draft"],
                "auto_activate": True,
                "auto_dispatch": False,
                "execute": False,
            },
        )
        assert bootstrap.status_code == 200
        bootstrap_payload = bootstrap.json()
        instance_id = bootstrap_payload["team"]["team_id"]
        runtime_detail_after_bootstrap = client.get(
            f"/runtime-center/industry/{instance_id}",
        )
        assert runtime_detail_after_bootstrap.status_code == 200

        solution_goal = next(
            item
            for item in list(bootstrap_payload["draft"]["goals"] or [])
            if str(item.get("kind") or "") == "solution"
        )
        goal_id = str(solution_goal["goal_id"])
        owner_agent_id = str(solution_goal["owner_agent_id"])

        turn_executor.fail_session_ids.add(goal_id)

        acquisition = client.post(
            "/learning/acquisition/run",
            json={"industry_instance_id": instance_id},
        )
        assert acquisition.status_code == 200
        acquisition_payload = acquisition.json()
        assert acquisition_payload["success"] is True
        assert acquisition_payload["proposals_processed"] >= 1
        assert acquisition_payload["plans_materialized"] >= 1
        assert acquisition_payload["onboarding_passed"] >= 1

        failed_task_ids: list[str] = []
        failed_evidence_ids: list[str] = []
        for _ in range(3):
            dispatch_payload = asyncio.run(
                app.state.goal_service.dispatch_goal_execute_now(
                    goal_id,
                    context={"owner_agent_id": owner_agent_id},
                    owner_agent_id=owner_agent_id,
                    activate=True,
                )
            )
            assert dispatch_payload["dispatch_results"][0]["phase"] == "failed"
            assert dispatch_payload["dispatch_results"][0]["executed"] is True
            failed_task_id = str(dispatch_payload["dispatch_results"][0]["task_id"])
            failed_task_ids.append(failed_task_id)
            evidence_response = client.get(
                "/runtime-center/evidence",
                params={"task_id": failed_task_id},
            )
            assert evidence_response.status_code == 200
            evidence_payload = evidence_response.json()
            assert evidence_payload
            latest_evidence = evidence_payload[0]
            assert latest_evidence["task_id"] == failed_task_id
            assert latest_evidence["capability_ref"] == "system:dispatch_query"
            assert latest_evidence["status"] == "failed"
            failed_evidence_ids.append(str(latest_evidence["id"]))

        strategy = client.post(
            "/learning/automation/strategy",
            json={
                "actor": "copaw-main-brain",
                "limit": 20,
                "auto_apply": True,
                "auto_rollback": False,
                "failure_threshold": 2,
                "confirm_threshold": 6,
                "max_proposals": 3,
            },
        )
        assert strategy.status_code == 200
        strategy_payload = strategy.json()
        assert strategy_payload["success"] is True
        assert strategy_payload["proposals_created"] == 1
        assert strategy_payload["patches_created"] == 1
        assert len(strategy_payload["auto_applied"]) == 1

        proposal_id = str(strategy_payload["proposals"][0]["id"])
        patch_id = str(strategy_payload["patches"][0]["id"])
        source_task_id = str(strategy_payload["patches"][0]["task_id"])
        assert source_task_id == failed_task_ids[0]
        assert strategy_payload["patches"][0]["status"] == "applied"

        override = capability_override_repository.get_override("system:dispatch_query")
        assert override is not None
        assert override.source_patch_id == patch_id

        runtime_patches = client.get(
            "/runtime-center/learning/patches",
            params={"task_id": source_task_id},
        )
        assert runtime_patches.status_code == 200
        patch_payloads = runtime_patches.json()
        assert any(item["id"] == patch_id for item in patch_payloads)

        runtime_growth = client.get(
            "/runtime-center/learning/growth",
            params={"task_id": source_task_id},
        )
        assert runtime_growth.status_code == 200
        growth_payloads = runtime_growth.json()
        linked_growth_ids = {
            str(item["id"])
            for item in growth_payloads
            if str(item.get("source_patch_id") or "") == patch_id
        }
        assert linked_growth_ids

        runtime_detail = client.get(f"/runtime-center/industry/{instance_id}")
        assert runtime_detail.status_code == 200
        closure = runtime_detail.json()["optimization_closure"]
        assert closure["counts"]["proposals"] >= 1
        assert closure["counts"]["patches"] >= 1
        assert closure["counts"]["growth"] >= 1
        linked_entry = next(
            item
            for item in closure["links"]
            if item["task_id"] == source_task_id
        )
        assert proposal_id in linked_entry["proposal_ids"]
        assert patch_id in linked_entry["patch_ids"]
        assert linked_growth_ids.issubset(set(linked_entry["growth_ids"]))

        compiled_specs = _compile_goal_specs(
            app,
            goal_id,
            owner_agent_id=owner_agent_id,
        )
        assert compiled_specs
        compiler_meta = compiled_specs[0]["payload"]["compiler"]
        assert patch_id in compiler_meta["feedback_patch_ids"]
        assert linked_growth_ids.issubset(set(compiler_meta["feedback_growth_ids"]))
        assert set(failed_evidence_ids).issubset(set(compiler_meta["feedback_evidence_refs"]))
    finally:
        _close_test_app(app)

    restarted_app = _build_industry_app(
        tmp_path,
        draft_generator=BrowserIndustryDraftGenerator(),
    )
    restarted_app.include_router(learning_router)
    restarted_capability_override_repository = _inject_capability_patch_repository(
        restarted_app,
    )

    try:
        restarted_client = TestClient(restarted_app)

        restarted_override = restarted_capability_override_repository.get_override(
            "system:dispatch_query",
        )
        assert restarted_override is not None
        assert restarted_override.source_patch_id == patch_id

        restarted_patches = restarted_client.get(
            "/runtime-center/learning/patches",
            params={"task_id": source_task_id},
        )
        assert restarted_patches.status_code == 200
        assert any(item["id"] == patch_id for item in restarted_patches.json())

        restarted_growth = restarted_client.get(
            "/runtime-center/learning/growth",
            params={"task_id": source_task_id},
        )
        assert restarted_growth.status_code == 200
        restarted_growth_ids = {
            str(item["id"])
            for item in restarted_growth.json()
            if str(item.get("source_patch_id") or "") == patch_id
        }
        assert linked_growth_ids == restarted_growth_ids

        restarted_detail = restarted_client.get(
            f"/runtime-center/industry/{instance_id}",
        )
        assert restarted_detail.status_code == 200
        restarted_closure = restarted_detail.json()["optimization_closure"]
        restarted_link = next(
            item
            for item in restarted_closure["links"]
            if item["task_id"] == source_task_id
        )
        assert proposal_id in restarted_link["proposal_ids"]
        assert patch_id in restarted_link["patch_ids"]
        assert linked_growth_ids.issubset(set(restarted_link["growth_ids"]))

        restarted_compiled_specs = _compile_goal_specs(
            restarted_app,
            goal_id,
            owner_agent_id=owner_agent_id,
        )
        assert restarted_compiled_specs
        restarted_compiler_meta = restarted_compiled_specs[0]["payload"]["compiler"]
        assert patch_id in restarted_compiler_meta["feedback_patch_ids"]
        assert linked_growth_ids.issubset(
            set(restarted_compiler_meta["feedback_growth_ids"]),
        )
        assert set(failed_evidence_ids).issubset(
            set(restarted_compiler_meta["feedback_evidence_refs"]),
        )
    finally:
        _close_test_app(restarted_app)
