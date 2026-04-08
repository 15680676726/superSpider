# -*- coding: utf-8 -*-
from unittest.mock import patch

from copaw.capabilities.install_templates import (
    CapabilityInstallTemplateSpec,
    get_install_template,
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
