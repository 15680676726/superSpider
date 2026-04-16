# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
import types
import warnings


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "run_unified_mcp_activation_live_acceptance.py"
)


def _load_live_acceptance_script():
    spec = importlib.util.spec_from_file_location(
        "run_unified_mcp_activation_live_acceptance",
        SCRIPT_PATH,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("failed to load live acceptance script module")
    module = importlib.util.module_from_spec(spec)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        spec.loader.exec_module(module)
    return module


def test_live_acceptance_runtime_noise_prep_sets_numexpr_defaults(monkeypatch) -> None:
    monkeypatch.delenv("NUMEXPR_MAX_THREADS", raising=False)
    monkeypatch.delenv("NUMEXPR_NUM_THREADS", raising=False)
    monkeypatch.delenv("PYTHONWARNINGS", raising=False)

    module = _load_live_acceptance_script()

    module._prepare_runtime_noise_filters()

    assert os.environ["NUMEXPR_MAX_THREADS"] == "16"
    assert os.environ["NUMEXPR_NUM_THREADS"] == "16"
    assert (
        os.environ["PYTHONWARNINGS"]
        == "ignore:websockets.legacy is deprecated:DeprecationWarning:websockets.legacy,"
        "ignore:websockets.server.WebSocketServerProtocol is deprecated:"
        "DeprecationWarning:uvicorn.protocols.websockets.websockets_impl"
    )


def test_live_acceptance_runtime_noise_prep_filters_known_websocket_deprecations() -> None:
    module = _load_live_acceptance_script()

    with warnings.catch_warnings(record=True) as caught:
        warnings.resetwarnings()
        module._prepare_runtime_noise_filters()
        warnings.warn_explicit(
            "websockets.legacy is deprecated; see upgrade guide",
            DeprecationWarning,
            filename=str(SCRIPT_PATH),
            lineno=1,
            module="websockets.legacy",
        )
        warnings.warn_explicit(
            "websockets.server.WebSocketServerProtocol is deprecated",
            DeprecationWarning,
            filename=str(SCRIPT_PATH),
            lineno=1,
            module="uvicorn.protocols.websockets.websockets_impl",
        )
        warnings.warn_explicit(
            "keep-this-warning",
            DeprecationWarning,
            filename=str(SCRIPT_PATH),
            lineno=1,
            module="copaw.tests.live_acceptance",
        )

    assert [str(item.message) for item in caught] == ["keep-this-warning"]


def test_prepare_third_party_runtime_log_filters_raise_noise_floor(monkeypatch) -> None:
    module = _load_live_acceptance_script()
    levels: list[tuple[str, int]] = []
    remove_calls: list[str] = []
    add_calls: list[tuple[object, str]] = []
    real_get_logger = module.logging.getLogger

    class FakeLogger:
        def setLevel(self, level: int) -> None:
            levels.append(("mcp.server.lowlevel.server", level))

    class FakeLoguruLogger:
        def remove(self) -> None:
            remove_calls.append("remove")

        def add(self, sink, *, level: str) -> None:
            add_calls.append((sink, level))

    fake_loguru = types.SimpleNamespace(logger=FakeLoguruLogger())

    def fake_get_logger(name=None):
        if name == "mcp.server.lowlevel.server":
            return FakeLogger()
        return real_get_logger(name)

    monkeypatch.setattr(module.logging, "getLogger", fake_get_logger)
    monkeypatch.setitem(sys.modules, "loguru", fake_loguru)

    module._prepare_third_party_runtime_log_filters()

    assert levels == [("mcp.server.lowlevel.server", module.logging.WARNING)]
    assert remove_calls == ["remove"]
    assert add_calls == [(module.sys.stderr, "WARNING")]


def test_live_server_builds_uvicorn_config_with_wsproto(monkeypatch) -> None:
    module = _load_live_acceptance_script()
    captured: dict[str, object] = {}

    class DummyServer:
        async def serve(self) -> None:
            return None

    def fake_config(app, **kwargs):
        captured["app"] = app
        captured.update(kwargs)
        return object()

    def fake_server(config) -> DummyServer:
        captured["config"] = config
        return DummyServer()

    monkeypatch.setattr(module.uvicorn, "Config", fake_config)
    monkeypatch.setattr(module.uvicorn, "Server", fake_server)

    server = module._LiveServer(object(), host="127.0.0.1", port=8765)
    server._run()

    assert captured["ws"] == "wsproto"


def test_live_acceptance_script_ensures_repo_src_on_sys_path(monkeypatch) -> None:
    module = _load_live_acceptance_script()
    repo_src = str(SCRIPT_PATH.parents[1] / "src")
    sentinel_path = "C:/tmp/not-copaw-src"

    monkeypatch.setattr(module.sys, "path", [sentinel_path], raising=False)

    module._ensure_repo_src_on_sys_path()

    assert module.sys.path[0] == repo_src
    assert sentinel_path in module.sys.path[1:]


def test_live_acceptance_script_ensures_repo_src_in_pythonpath_env(monkeypatch) -> None:
    module = _load_live_acceptance_script()
    repo_src = str(SCRIPT_PATH.parents[1] / "src")
    sentinel_path = "C:/tmp/other-pythonpath"

    monkeypatch.setenv("PYTHONPATH", sentinel_path)

    module._ensure_repo_src_in_environment()

    assert os.environ["PYTHONPATH"].split(os.pathsep)[0] == repo_src
    assert sentinel_path in os.environ["PYTHONPATH"].split(os.pathsep)[1:]
