# -*- coding: utf-8 -*-
from types import SimpleNamespace
from unittest.mock import patch

from copaw.capabilities.install_templates import (
    CapabilityInstallTemplateSpec,
    get_install_template,
    list_install_templates,
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
