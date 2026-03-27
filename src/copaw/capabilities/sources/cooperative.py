# -*- coding: utf-8 -*-
from __future__ import annotations

from ..models import CapabilityMount


def list_cooperative_capabilities() -> list[CapabilityMount]:
    return [
        CapabilityMount(
            id="system:browser_companion_runtime",
            name="browser_companion_runtime",
            summary="Attach and maintain a cooperative browser companion channel for known browser work.",
            kind="system-op",
            source_kind="system",
            risk_level="guarded",
            risk_description=(
                "Attaches to a live browser continuity channel and can affect authenticated browser execution."
            ),
            environment_requirements=["browser", "environment", "session"],
            environment_description=(
                "Requires a live browser environment plus canonical session/environment mounts."
            ),
            evidence_contract=["browser-companion", "runtime-event", "environment-session"],
            evidence_description=(
                "Records browser companion registration state and runtime host-event continuity anchors."
            ),
            role_access_policy=["all"],
            executor_ref="EnvironmentService.register_browser_companion",
            replay_support=False,
            enabled=True,
            tags=["system", "browser", "cooperative-adapter", "phase2"],
        ),
        CapabilityMount(
            id="system:document_bridge_runtime",
            name="document_bridge_runtime",
            summary="Register an office/document object-model bridge for semantic writing chains.",
            kind="system-op",
            source_kind="system",
            risk_level="guarded",
            risk_description=(
                "Bridges live document surfaces and can influence file/document mutation paths."
            ),
            environment_requirements=["document", "workspace", "environment", "session"],
            environment_description=(
                "Requires canonical session/environment mounts and a mounted document or workspace surface."
            ),
            evidence_contract=["document-bridge", "runtime-event", "environment-session"],
            evidence_description=(
                "Records document-bridge identity, family support, and cooperative execution preference."
            ),
            role_access_policy=["all"],
            executor_ref="EnvironmentService.register_document_bridge",
            replay_support=False,
            enabled=True,
            tags=["system", "document", "cooperative-adapter", "phase2"],
        ),
        CapabilityMount(
            id="system:host_watchers_runtime",
            name="host_watchers_runtime",
            summary="Maintain filesystem, download, and notification watcher runtime state.",
            kind="system-op",
            source_kind="system",
            risk_level="auto",
            risk_description=(
                "Watcher registration is read-mostly host observation, but it affects runtime recovery signals."
            ),
            environment_requirements=["environment", "session", "runtime-events"],
            environment_description=(
                "Requires canonical session/environment mounts and the runtime event mechanism."
            ),
            evidence_contract=["host-watcher", "runtime-event", "environment-session"],
            evidence_description=(
                "Records watcher availability and emits runtime events for host observations such as completed downloads."
            ),
            role_access_policy=["all"],
            executor_ref="EnvironmentService.register_host_watchers",
            replay_support=False,
            enabled=True,
            tags=["system", "watchers", "cooperative-adapter", "phase2"],
        ),
        CapabilityMount(
            id="system:windows_app_adapter_runtime",
            name="windows_app_adapter_runtime",
            summary="Register high-value Windows application adapters and native-first execution hints.",
            kind="system-op",
            source_kind="system",
            risk_level="guarded",
            risk_description=(
                "Windows app adapters influence how runtime mutates live application surfaces."
            ),
            environment_requirements=["desktop", "environment", "session"],
            environment_description=(
                "Requires canonical session/environment mounts and a Windows desktop execution seat."
            ),
            evidence_contract=["windows-app-adapter", "runtime-event", "environment-session"],
            evidence_description=(
                "Records Windows app adapter identity, control channel, and preferred execution path."
            ),
            role_access_policy=["all"],
            executor_ref="EnvironmentService.register_windows_app_adapter",
            replay_support=False,
            enabled=True,
            tags=["system", "windows", "desktop", "cooperative-adapter", "phase2"],
        ),
    ]


__all__ = ["list_cooperative_capabilities"]
