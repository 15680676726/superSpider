"""Desktop control adapters."""

from .templates import (
    DesktopMCPTemplate,
    build_windows_desktop_mcp_client_config,
    get_desktop_mcp_template,
    list_desktop_mcp_templates,
)
from .windows_host import DesktopAutomationError, WindowSelector, WindowsDesktopHost

__all__ = [
    "DesktopAutomationError",
    "DesktopMCPTemplate",
    "WindowSelector",
    "WindowsDesktopHost",
    "build_windows_desktop_mcp_client_config",
    "get_desktop_mcp_template",
    "list_desktop_mcp_templates",
]
