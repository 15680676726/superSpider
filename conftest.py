# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import os

from _pytest.python import Package

os.environ.setdefault("PYDANTIC_DISABLE_PLUGINS", "logfire-plugin")

if os.name == "nt" and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    # pytest/TestClient on Windows can otherwise leave Proactor overlapped handles
    # pending during interpreter teardown, which shows up as flaky unraisable warnings.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

if not hasattr(Package, "obj"):
    Package.obj = property(lambda self: None)

if os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD") == "1":
    pytest_plugins = ("pytest_asyncio.plugin",)


def pytest_addoption(parser, pluginmanager) -> None:
    """Keep asyncio_mode config valid even when pytest-asyncio is disabled."""
    if pluginmanager.hasplugin("asyncio"):
        return
    parser.addini(
        "asyncio_mode",
        help="compat shim when pytest-asyncio is disabled",
        default="auto",
    )
