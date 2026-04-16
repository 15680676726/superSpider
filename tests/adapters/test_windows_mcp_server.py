# -*- coding: utf-8 -*-
from __future__ import annotations

import copaw.adapters.desktop.windows_mcp_server as windows_mcp_server_module


def test_windows_mcp_server_defaults_to_warning_log_level() -> None:
    assert windows_mcp_server_module.server.settings.log_level == "WARNING"
