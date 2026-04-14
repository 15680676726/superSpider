from __future__ import annotations

from fastapi.testclient import TestClient

from .shared import _build_industry_app


def test_bootstrap_materializes_goal_records_as_explicit_compatibility_artifacts(tmp_path) -> None:
    app = _build_industry_app(tmp_path)
    client = TestClient(app)

    preview = client.post(
        "/industry/v1/preview",
        json={
            "industry": "Industrial Equipment",
            "company_name": "Northwind Robotics",
            "product": "factory monitoring copilots",
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
    instance_id = bootstrap.json()["team"]["team_id"]

    goals = app.state.goal_service.list_goals(industry_instance_id=instance_id, limit=None)
    assert goals
    assert all(goal.goal_class == "compatibility-bootstrap-goal" for goal in goals)

    overrides = app.state.goal_override_repository.list_overrides()
    bootstrap_overrides = [
        override
        for override in overrides
        if str((override.compiler_context or {}).get("industry_instance_id") or "") == instance_id
    ]
    assert bootstrap_overrides
    assert all(
        bool((override.compiler_context or {}).get("compatibility_materialization"))
        for override in bootstrap_overrides
    )
