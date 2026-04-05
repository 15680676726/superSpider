from __future__ import annotations

import importlib


def test_runtime_service_graph_module_imports_cleanly() -> None:
    module = importlib.import_module("copaw.app.runtime_service_graph")

    assert module is not None
