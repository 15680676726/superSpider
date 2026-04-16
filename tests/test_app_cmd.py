# -*- coding: utf-8 -*-
from __future__ import annotations

from click.testing import CliRunner

import copaw.cli.app_cmd as app_cmd_module


def test_app_cmd_runs_uvicorn_with_wsproto(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(app_cmd_module, "write_last_api", lambda host, port: None)
    monkeypatch.setattr(app_cmd_module, "setup_logger", lambda level: None)

    def fake_uvicorn_run(*args, **kwargs) -> None:
        captured["args"] = args
        captured["kwargs"] = kwargs

    monkeypatch.setattr(app_cmd_module.uvicorn, "run", fake_uvicorn_run)

    result = CliRunner().invoke(app_cmd_module.app_cmd, ["--host", "127.0.0.1"])

    assert result.exit_code == 0
    assert captured["kwargs"]["ws"] == "wsproto"
