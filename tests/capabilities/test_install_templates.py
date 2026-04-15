# -*- coding: utf-8 -*-
from types import SimpleNamespace
from unittest.mock import patch

from copaw.capabilities.install_templates import (
    CapabilityInstallTemplateSpec,
    get_install_template,
    list_install_templates,
    may_have_install_template_for_capability,
    resolve_install_template_ids_for_capability,
)


def test_get_install_template_builds_only_requested_browser_template() -> None:
    browser_template = CapabilityInstallTemplateSpec(
        id="browser-local",
        name="Local Browser Runtime",
    )

    def _unexpected_builder(*args, **kwargs):
        del args, kwargs
        raise AssertionError("unrelated install templates should not be built")

    with (
        patch(
            "copaw.capabilities.install_templates._build_browser_install_template",
            return_value=browser_template,
        ) as browser_builder,
        patch(
            "copaw.capabilities.install_templates.list_desktop_mcp_templates",
            return_value=[],
        ),
        patch(
            "copaw.capabilities.install_templates._build_browser_companion_install_template",
            side_effect=_unexpected_builder,
        ),
        patch(
            "copaw.capabilities.install_templates._build_document_bridge_install_template",
            side_effect=_unexpected_builder,
        ),
        patch(
            "copaw.capabilities.install_templates._build_host_watchers_install_template",
            side_effect=_unexpected_builder,
        ),
        patch(
            "copaw.capabilities.install_templates._build_windows_app_adapters_install_template",
            side_effect=_unexpected_builder,
        ),
    ):
        template = get_install_template("browser-local", include_runtime=True)

    assert template == browser_template
    browser_builder.assert_called_once()


def test_list_install_templates_reuses_capability_mount_lookup_per_capability_id() -> None:
    class _CountingCapabilityService:
        def __init__(self) -> None:
            self.counts: dict[str, int] = {}

        def list_mcp_client_infos(self) -> list[dict[str, object]]:
            return []

        def get_capability(self, capability_id: str):
            self.counts[capability_id] = self.counts.get(capability_id, 0) + 1
            if self.counts[capability_id] > 1:
                raise AssertionError(
                    f"capability {capability_id} should be looked up once per template listing",
                )
            return SimpleNamespace(id=capability_id, enabled=True)

    capability_service = _CountingCapabilityService()

    with (
        patch(
            "copaw.capabilities.install_templates.list_desktop_mcp_templates",
            return_value=[],
        ),
        patch(
            "copaw.capabilities.install_templates.get_browser_support_snapshot",
            return_value={"playwright_ready": True},
        ),
    ):
        templates = list_install_templates(
            capability_service=capability_service,
            include_runtime=False,
        )

    assert {template.id for template in templates} == {
        "browser-local",
        "browser-companion",
        "document-office-bridge",
        "host-watchers",
        "windows-app-adapters",
    }
    assert capability_service.counts == {
        "tool:browser_use": 1,
        "system:browser_companion_runtime": 1,
        "system:document_bridge_runtime": 1,
        "system:host_watchers_runtime": 1,
        "system:windows_app_adapter_runtime": 1,
    }


def test_list_install_templates_prefers_capability_lookup_api_when_available() -> None:
    mounts = {
        capability_id: SimpleNamespace(id=capability_id, enabled=True)
        for capability_id in (
            "tool:browser_use",
            "system:browser_companion_runtime",
            "system:document_bridge_runtime",
            "system:host_watchers_runtime",
            "system:windows_app_adapter_runtime",
        )
    }

    class _LookupCapabilityService:
        def __init__(self) -> None:
            self.list_capability_lookup_calls = 0
            self.get_capability_calls = 0

        def list_capability_lookup(self):
            self.list_capability_lookup_calls += 1
            return dict(mounts)

        def list_mcp_client_infos(self) -> list[dict[str, object]]:
            return []

        def get_capability(self, capability_id: str):
            del capability_id
            self.get_capability_calls += 1
            raise AssertionError(
                "install template listing should prefer list_capability_lookup() when available",
            )

    capability_service = _LookupCapabilityService()

    with (
        patch(
            "copaw.capabilities.install_templates.list_desktop_mcp_templates",
            return_value=[],
        ),
        patch(
            "copaw.capabilities.install_templates.get_browser_support_snapshot",
            return_value={"playwright_ready": True},
        ),
    ):
        templates = list_install_templates(
            capability_service=capability_service,
            include_runtime=False,
        )

    assert {template.id for template in templates} == {
        "browser-local",
        "browser-companion",
        "document-office-bridge",
        "host-watchers",
        "windows-app-adapters",
    }
    assert capability_service.list_capability_lookup_calls == 1
    assert capability_service.get_capability_calls == 0


def test_list_install_templates_reuses_pending_decision_listing_once() -> None:
    mounts = {
        capability_id: SimpleNamespace(id=capability_id, enabled=True)
        for capability_id in (
            "tool:browser_use",
            "system:browser_companion_runtime",
            "system:document_bridge_runtime",
            "system:host_watchers_runtime",
            "system:windows_app_adapter_runtime",
        )
    }

    class _LookupCapabilityService:
        def list_capability_lookup(self):
            return dict(mounts)

        def list_mcp_client_infos(self) -> list[dict[str, object]]:
            return []

    class _CountingDecisionRequestRepository:
        def __init__(self) -> None:
            self.calls = 0

        def list_decision_requests(self):
            self.calls += 1
            if self.calls > 1:
                raise AssertionError(
                    "install template listing should reuse one pending decision snapshot per listing",
                )
            return [
                SimpleNamespace(status="open", summary="browser runtime approval"),
                SimpleNamespace(status="reviewing", summary="desktop host review"),
            ]

    decision_request_repository = _CountingDecisionRequestRepository()

    with (
        patch(
            "copaw.capabilities.install_templates.list_desktop_mcp_templates",
            return_value=[],
        ),
        patch(
            "copaw.capabilities.install_templates.get_browser_support_snapshot",
            return_value={"playwright_ready": True},
        ),
    ):
        templates = list_install_templates(
            capability_service=_LookupCapabilityService(),
            decision_request_repository=decision_request_repository,
            include_runtime=False,
        )

    assert {template.id for template in templates} == {
        "browser-local",
        "browser-companion",
        "document-office-bridge",
        "host-watchers",
        "windows-app-adapters",
    }
    assert decision_request_repository.calls == 1


def test_may_have_install_template_for_capability_only_flags_supported_families() -> None:
    assert may_have_install_template_for_capability("mcp:desktop_windows") is True
    assert may_have_install_template_for_capability("tool:browser_use") is True
    assert may_have_install_template_for_capability("system:dispatch_query") is False


def test_resolve_install_template_ids_for_capability_returns_known_candidates() -> None:
    assert resolve_install_template_ids_for_capability("mcp:desktop_windows") == [
        "desktop-windows"
    ]
    assert resolve_install_template_ids_for_capability("tool:browser_use") == [
        "browser-local",
        "browser-companion",
    ]
    assert resolve_install_template_ids_for_capability("system:dispatch_query") == []
