# -*- coding: utf-8 -*-
"""Desktop adapter templates for canonical capability-market installation."""

from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class DesktopMCPTemplate:
    """Static template used to install a host adapter into MCP config."""

    template_id: str
    name: str
    description: str
    platform: str
    default_client_key: str
    client: dict[str, object]
    capability_tags: tuple[str, ...]
    notes: tuple[str, ...]


def build_windows_desktop_mcp_client_config(
    *,
    python_executable: str | None = None,
    enabled: bool = True,
) -> dict[str, object]:
    """Build the stdio MCP client payload for the Windows desktop adapter."""
    return {
        "name": "Windows Desktop",
        "description": (
            "Local Windows desktop control adapter for app launch, window "
            "focus, mouse clicks, typing, and key chords."
        ),
        "enabled": bool(enabled),
        "transport": "stdio",
        "url": "",
        "headers": {},
        "command": python_executable or sys.executable,
        "args": ["-m", "copaw.adapters.desktop.windows_mcp_server"],
        "env": {"PYTHONIOENCODING": "utf-8"},
        "cwd": "",
    }


def list_desktop_mcp_templates() -> list[DesktopMCPTemplate]:
    """List built-in desktop MCP templates."""
    return [
        DesktopMCPTemplate(
            template_id="desktop-windows",
            name="Windows Desktop Adapter",
            description=(
                "Mount a local Windows desktop-control adapter through MCP."
            ),
            platform="windows",
            default_client_key="desktop_windows",
            client=build_windows_desktop_mcp_client_config(),
            capability_tags=("desktop", "window", "keyboard", "mouse"),
            notes=(
                "Runs as a local stdio MCP server using the current Python runtime.",
                "Pairs well with the built-in desktop screenshot observation tool.",
                "Requires a real Windows desktop session; headless servers are not supported.",
            ),
        ),
    ]


def get_desktop_mcp_template(template_id: str) -> DesktopMCPTemplate | None:
    """Return a desktop MCP template by id."""
    for template in list_desktop_mcp_templates():
        if template.template_id == template_id:
            return template
    return None
