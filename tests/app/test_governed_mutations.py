# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.capabilities.models import CapabilityMount, CapabilitySummary
from copaw.capabilities.system_skill_handlers import SystemSkillCapabilityFacade

from copaw.app.routers.capabilities import router as capabilities_router


class _FakeDispatcher:
    def __init__(self) -> None:
        self.submitted: list[object] = []
        self.executed: list[str] = []

    def submit(self, task):
        self.submitted.append(task)
        return SimpleNamespace(phase="executing", model_dump=lambda mode="json": {"phase": "executing"})

    async def execute_task(self, task_id: str):
        self.executed.append(task_id)
        return SimpleNamespace(
            success=True,
            model_dump=lambda mode="json": {"success": True, "phase": "completed"},
        )


class _FakeCapabilityService:
    def __init__(self) -> None:
        self._public_mounts: dict[str, CapabilityMount] = {
            "skill:research": CapabilityMount(
                id="skill:research",
                name="Research Capability",
                summary="Test capability for research workflows.",
                kind="skill-bundle",
                risk_level="guarded",
            ),
            "system:set_capability_enabled": CapabilityMount(
                id="system:set_capability_enabled",
                name="Set Capability Enabled",
                summary="Governed mutation for toggling capability enablement.",
                kind="system-op",
                risk_level="guarded",
            ),
            "system:apply_capability_lifecycle": CapabilityMount(
                id="system:apply_capability_lifecycle",
                name="Apply Capability Lifecycle",
                summary="Governed lifecycle mutation.",
                kind="system-op",
                risk_level="guarded",
            ),
        }

    def get_capability(self, capability_id: str):
        return self._public_mounts.get(capability_id)

    def get_public_capability(self, capability_id: str):
        return self._public_mounts.get(capability_id)

    def list_capabilities(self, *, kind=None, enabled_only=False):
        return self.list_public_capabilities(kind=kind, enabled_only=enabled_only)

    def list_public_capabilities(self, *, kind=None, enabled_only=False):
        mounts = list(self._public_mounts.values())
        if kind is not None:
            mounts = [mount for mount in mounts if mount.kind == kind]
        if enabled_only:
            mounts = [mount for mount in mounts if mount.enabled]
        return mounts

    def summarize(self):
        return self.summarize_public()

    def summarize_public(self):
        mounts = list(self._public_mounts.values())
        return CapabilitySummary(
            total=len(mounts),
            enabled=sum(1 for mount in mounts if mount.enabled),
            by_kind=self._count_by_attr(mounts, "kind"),
            by_source=self._count_by_attr(mounts, "source_kind"),
        )

    def _count_by_attr(self, mounts: list[CapabilityMount], attr: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for mount in mounts:
            key = getattr(mount, attr)
            counts[key] = counts.get(key, 0) + 1
        return counts


def build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(capabilities_router)
    app.state.capability_service = _FakeCapabilityService()
    app.state.kernel_dispatcher = _FakeDispatcher()
    return app


def test_capability_toggle_reuses_shared_governed_mutation_dispatch() -> None:
    from copaw.app.routers.governed_mutations import dispatch_governed_mutation

    client = TestClient(build_app())
    response = client.patch("/capabilities/skill:research/toggle")

    assert callable(dispatch_governed_mutation)
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_requestless_governed_mutation_helper_dispatches_through_kernel() -> None:
    from copaw.kernel.governed_mutation_dispatch import (
        dispatch_governed_mutation_runtime,
    )

    dispatcher = _FakeDispatcher()
    capability_service = _FakeCapabilityService()

    result = asyncio.run(
        dispatch_governed_mutation_runtime(
            capability_service=capability_service,
            kernel_dispatcher=dispatcher,
            capability_ref="system:set_capability_enabled",
            title="Enable skill:research",
            environment_ref="config:capabilities",
            payload={
                "capability_id": "skill:research",
                "enabled": True,
                "actor": "copaw-operator",
            },
            fallback_risk="guarded",
        ),
    )

    assert result["success"] is True
    assert len(dispatcher.submitted) == 1
    assert dispatcher.submitted[0].capability_ref == "system:set_capability_enabled"
    assert dispatcher.submitted[0].risk_level == "guarded"
    assert dispatcher.executed == [dispatcher.submitted[0].id]


def test_shared_governed_mutation_helper_translates_dispatcher_errors() -> None:
    from copaw.app.routers.governed_mutations import translate_dispatcher_error

    with pytest.raises(Exception) as exc_info:
        translate_dispatcher_error(KeyError("missing-task"))

    assert "404" in str(exc_info.value) or "missing-task" in str(exc_info.value)


class _FakeIndustryService:
    def __init__(self) -> None:
        self.attach_calls: list[dict[str, object]] = []

    def attach_candidate_to_scope(self, **payload):
        self.attach_calls.append(dict(payload))
        return {
            "success": True,
            "summary": "Attached to seat scope.",
            "selected_scope": payload.get("selected_scope") or "seat",
            "scope_ref": payload.get("scope_ref"),
        }


def _surface_payload(
    *,
    effective: list[str],
    role: list[str],
    seat: list[str],
    session: list[str],
) -> dict[str, object]:
    return {
        "effective_capabilities": list(effective),
        "runtime": {
            "metadata": {
                "selected_seat_ref": "seat-browser-primary",
                "capability_layers": {
                    "role_prototype_capability_ids": list(role),
                    "seat_instance_capability_ids": list(seat),
                    "cycle_delta_capability_ids": [],
                    "session_overlay_capability_ids": list(session),
                    "effective_capability_ids": list(effective),
                },
            },
        },
    }


def test_lifecycle_replace_existing_blocks_protected_replace_without_lift() -> None:
    facade = SystemSkillCapabilityFacade(
        skill_service=SimpleNamespace(),
        agent_profile_service=SimpleNamespace(
            get_capability_surface=lambda _agent_id: _surface_payload(
                effective=["tool:browser_use", "skill:legacy-seat-pack", "mcp:browser-temp"],
                role=["tool:browser_use"],
                seat=["skill:legacy-seat-pack"],
                session=["mcp:browser-temp"],
            ),
        ),
        industry_service=_FakeIndustryService(),
        apply_role_handler=lambda _payload: {
            "success": True,
            "summary": "apply_role should not run for protected replacements",
        },
    )

    result = asyncio.run(
        facade.handle_apply_capability_lifecycle(
            {
                "decision_kind": "replace_existing",
                "target_agent_id": "agent-1",
                "target_capability_ids": ["mcp:desktop_windows"],
                "replacement_target_ids": ["skill:legacy-seat-pack"],
                "selected_scope": "seat",
                "selected_seat_ref": "seat-browser-primary",
                "protection_flags": ["protected_from_auto_replace"],
                "replacement_relation": "replace_requested",
            },
        ),
    )

    assert result["success"] is False
    assert result["decision_kind"] == "replace_existing"
    assert result["blocked_reason"] == "protected_from_auto_replace"
    assert result["governed_path_required"] is True
    assert "protection" in result["summary"].lower()


def test_lifecycle_rollback_restores_prior_seat_truth_without_dropping_session_overlay() -> None:
    applied_payloads: list[dict[str, object]] = []
    industry_service = _FakeIndustryService()

    facade = SystemSkillCapabilityFacade(
        skill_service=SimpleNamespace(),
        agent_profile_service=SimpleNamespace(
            get_capability_surface=lambda _agent_id: _surface_payload(
                effective=["tool:browser_use", "mcp:desktop_windows", "mcp:browser-temp"],
                role=["tool:browser_use"],
                seat=["mcp:desktop_windows"],
                session=["mcp:browser-temp"],
            ),
        ),
        industry_service=industry_service,
        apply_role_handler=lambda payload: (
            applied_payloads.append(dict(payload))
            or {"success": True, "summary": "Updated seat truth."}
        ),
    )

    result = asyncio.run(
        facade.handle_apply_capability_lifecycle(
            {
                "decision_kind": "rollback",
                "target_agent_id": "agent-1",
                "target_capability_ids": ["mcp:desktop_windows"],
                "rollback_target_ids": ["skill:legacy-seat-pack"],
                "replacement_target_ids": ["mcp:desktop_windows"],
                "selected_scope": "seat",
                "selected_seat_ref": "seat-browser-primary",
                "governed_mutation": True,
            },
        ),
    )

    assert result["success"] is True
    assert applied_payloads == []
    assert industry_service.attach_calls
    apply_payload = industry_service.attach_calls[0]
    assert apply_payload["capability_ids"] == ["skill:legacy-seat-pack"]
    assert apply_payload["capability_assignment_mode"] == "replace"
    assert apply_payload["selected_scope"] == "seat"
    assert apply_payload["selected_seat_ref"] == "seat-browser-primary"
    assert result["restored_capability_ids"] == ["skill:legacy-seat-pack"]
    assert result["preserved_overlay_capability_ids"] == ["mcp:browser-temp"]
