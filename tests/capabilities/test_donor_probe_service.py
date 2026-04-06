# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

from copaw.capabilities.models import CapabilityMount
from copaw.kernel.models import KernelTask


class _FakeCapabilityService:
    def __init__(
        self,
        *,
        mounts: dict[str, CapabilityMount],
        responses: dict[tuple[str, str], dict[str, object]],
    ) -> None:
        self._mounts = dict(mounts)
        self._responses = dict(responses)
        self.calls: list[KernelTask] = []

    def get_capability(self, capability_id: str) -> CapabilityMount | None:
        return self._mounts.get(capability_id)

    async def execute_task(self, task: KernelTask) -> dict[str, object]:
        self.calls.append(task)
        action = str(task.payload.get("action") or "").strip().lower()
        return dict(self._responses[(str(task.capability_ref or ""), action)])


def test_donor_probe_service_promotes_runtime_component_to_runtime_operable() -> None:
    from copaw.capabilities.donor_probe_service import DonorProbeService

    service = DonorProbeService(
        capability_service=_FakeCapabilityService(
            mounts={
                "runtime:openspace": CapabilityMount(
                    id="runtime:openspace",
                    name="openspace",
                    summary="Runtime donor",
                    kind="runtime-component",
                    source_kind="runtime",
                    risk_level="guarded",
                    metadata={
                        "verified_stage": "installed",
                        "provider_resolution_status": "not_required",
                        "compatibility_status": "compatible_native",
                        "runtime_contract": {
                            "runtime_kind": "service",
                            "supported_actions": ["start", "healthcheck", "stop"],
                        },
                    },
                ),
            },
            responses={
                (
                    "runtime:openspace",
                    "start",
                ): {
                    "success": True,
                    "summary": "Started runtime 'runtime:openspace'.",
                    "evidence_id": "ev-start",
                    "output": {
                        "runtime_id": "runtime:openspace",
                        "status": "ready",
                        "outcome": "succeeded",
                    },
                },
                (
                    "runtime:openspace",
                    "stop",
                ): {
                    "success": True,
                    "summary": "Stopped runtime 'runtime:openspace'.",
                    "evidence_id": "ev-stop",
                    "output": {
                        "runtime_id": "runtime:openspace",
                        "status": "stopped",
                        "outcome": "succeeded",
                    },
                },
            },
        ),
    )

    result = asyncio.run(
        service.probe_capability(
            capability_id="runtime:openspace",
            owner_agent_id="copaw-agent-runner",
            session_mount_id="session:seat-1",
            environment_ref="desktop:seat-1",
            work_context_id="work:openspace",
        ),
    )

    assert result["attempted"] is True
    assert result["success"] is True
    assert result["verified_stage"] == "runtime_operable"
    assert result["probe_outcome"] == "runtime_operable"
    assert result["provider_resolution_status"] == "not_required"
    assert result["compatibility_status"] == "compatible_native"
    assert result["probe_evidence_refs"] == ["ev-start", "ev-stop"]
    assert result["probe_runtime_id"] == "runtime:openspace"


def test_donor_probe_service_promotes_multi_action_adapter_to_adapter_probe_passed() -> None:
    from copaw.capabilities.donor_probe_service import DonorProbeService

    service = DonorProbeService(
        capability_service=_FakeCapabilityService(
            mounts={
                "adapter:demo": CapabilityMount(
                    id="adapter:demo",
                    name="demo",
                    summary="Adapter donor",
                    kind="adapter",
                    source_kind="adapter",
                    risk_level="guarded",
                    metadata={
                        "verified_stage": "installed",
                        "provider_resolution_status": "pending",
                        "compatibility_status": "compatible_via_bridge",
                        "adapter_contract": {
                            "compiled_adapter_id": "adapter:demo",
                            "transport_kind": "mcp",
                            "actions": [
                                {
                                    "action_id": "status",
                                    "transport_action_ref": "status",
                                    "input_schema": {"type": "object"},
                                    "output_schema": {},
                                },
                                {
                                    "action_id": "execute_task",
                                    "transport_action_ref": "execute_task",
                                    "input_schema": {"type": "object"},
                                    "output_schema": {},
                                },
                            ],
                        },
                    },
                ),
            },
            responses={
                (
                    "adapter:demo",
                    "status",
                ): {
                    "success": True,
                    "summary": "Adapter status responded.",
                    "evidence_id": "ev-status",
                    "output": {
                        "success": True,
                        "outcome": "succeeded",
                        "provider_injection": {
                            "provider_resolution_status": "resolved",
                        },
                    },
                },
            },
        ),
    )

    result = asyncio.run(
        service.probe_capability(
            capability_id="adapter:demo",
            owner_agent_id="copaw-agent-runner",
            session_mount_id="session:seat-1",
            environment_ref="desktop:seat-1",
            work_context_id="work:adapter",
        ),
    )

    assert result["attempted"] is True
    assert result["success"] is True
    assert result["verified_stage"] == "adapter_probe_passed"
    assert result["probe_outcome"] == "succeeded"
    assert result["provider_resolution_status"] == "resolved"
    assert result["compatibility_status"] == "compatible_via_bridge"
    assert result["selected_adapter_action_id"] == "status"
    assert result["probe_evidence_refs"] == ["ev-status"]


def test_donor_probe_service_marks_single_primary_adapter_action_as_verified() -> None:
    from copaw.capabilities.donor_probe_service import DonorProbeService

    service = DonorProbeService(
        capability_service=_FakeCapabilityService(
            mounts={
                "adapter:openspace": CapabilityMount(
                    id="adapter:openspace",
                    name="openspace",
                    summary="Adapter donor",
                    kind="adapter",
                    source_kind="adapter",
                    risk_level="guarded",
                    metadata={
                        "verified_stage": "installed",
                        "provider_resolution_status": "pending",
                        "compatibility_status": "compatible_native",
                        "adapter_contract": {
                            "compiled_adapter_id": "adapter:openspace",
                            "transport_kind": "mcp",
                            "actions": [
                                {
                                    "action_id": "execute_task",
                                    "transport_action_ref": "execute_task",
                                    "input_schema": {"type": "object"},
                                    "output_schema": {},
                                },
                            ],
                        },
                    },
                ),
            },
            responses={
                (
                    "adapter:openspace",
                    "execute_task",
                ): {
                    "success": True,
                    "summary": "Executed primary action.",
                    "evidence_id": "ev-execute",
                    "output": {
                        "success": True,
                        "outcome": "succeeded",
                        "provider_injection": {
                            "provider_resolution_status": "resolved",
                        },
                    },
                },
            },
        ),
    )

    result = asyncio.run(
        service.probe_capability(
            capability_id="adapter:openspace",
            owner_agent_id="copaw-agent-runner",
            session_mount_id="session:seat-1",
            environment_ref="desktop:seat-1",
            work_context_id="work:openspace",
        ),
    )

    assert result["attempted"] is True
    assert result["success"] is True
    assert result["verified_stage"] == "primary_action_verified"
    assert result["probe_outcome"] == "succeeded"
    assert result["selected_adapter_action_id"] == "execute_task"
    assert result["probe_evidence_refs"] == ["ev-execute"]


def test_donor_probe_service_does_not_promote_non_probeable_install_beyond_installed() -> None:
    from copaw.capabilities.donor_probe_service import DonorProbeService

    service = DonorProbeService(
        capability_service=_FakeCapabilityService(
            mounts={
                "project:black": CapabilityMount(
                    id="project:black",
                    name="black",
                    summary="CLI donor",
                    kind="project-package",
                    source_kind="project",
                    risk_level="auto",
                    metadata={
                        "verified_stage": "installed",
                        "provider_resolution_status": "not_required",
                        "compatibility_status": "compatible_native",
                    },
                ),
            },
            responses={},
        ),
    )

    result = asyncio.run(
        service.probe_capability(
            capability_id="project:black",
            owner_agent_id="copaw-agent-runner",
        ),
    )

    assert result["attempted"] is False
    assert result["success"] is False
    assert result["verified_stage"] == "installed"
    assert result["probe_outcome"] == "not_attempted"
