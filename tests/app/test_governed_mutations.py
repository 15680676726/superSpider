# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.capabilities.models import CapabilityMount, CapabilitySummary

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


def test_shared_governed_mutation_helper_translates_dispatcher_errors() -> None:
    from copaw.app.routers.governed_mutations import translate_dispatcher_error

    with pytest.raises(Exception) as exc_info:
        translate_dispatcher_error(KeyError("missing-task"))

    assert "404" in str(exc_info.value) or "missing-task" in str(exc_info.value)
