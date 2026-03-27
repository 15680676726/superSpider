# -*- coding: utf-8 -*-
from __future__ import annotations

import builtins

import copaw.config.utils as config_utils


def test_is_running_in_container_accepts_bool_constant(monkeypatch) -> None:
    monkeypatch.delenv("COPAW_RUNNING_IN_CONTAINER", raising=False)
    monkeypatch.setattr(config_utils, "RUNNING_IN_CONTAINER", False)
    monkeypatch.setattr(config_utils.os.path, "exists", lambda _path: False)

    def _raise_file_not_found(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(builtins, "open", _raise_file_not_found)

    assert config_utils.is_running_in_container() is False

    monkeypatch.setattr(config_utils, "RUNNING_IN_CONTAINER", True)
    assert config_utils.is_running_in_container() is True


def test_get_playwright_chromium_executable_path_uses_system_discovery_with_bool_flag(
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        config_utils.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH_ENV,
        raising=False,
    )
    monkeypatch.delenv("COPAW_RUNNING_IN_CONTAINER", raising=False)
    monkeypatch.setattr(config_utils, "RUNNING_IN_CONTAINER", False)
    monkeypatch.setattr(config_utils.os.path, "exists", lambda _path: False)
    monkeypatch.setattr(
        config_utils,
        "_discover_system_chromium_path",
        lambda: "C:/Program Files/Google/Chrome/Application/chrome.exe",
    )

    def _raise_file_not_found(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(builtins, "open", _raise_file_not_found)

    assert (
        config_utils.get_playwright_chromium_executable_path()
        == "C:/Program Files/Google/Chrome/Application/chrome.exe"
    )
