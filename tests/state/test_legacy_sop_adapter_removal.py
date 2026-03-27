# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util

import copaw.state as state
from copaw.state import SQLiteStateStore
from copaw.state import repositories as state_repositories


def test_legacy_sop_adapters_package_is_removed() -> None:
    assert importlib.util.find_spec("copaw.sop_adapters") is None


def test_state_no_longer_exports_legacy_sop_adapter_symbols() -> None:
    assert not hasattr(state, "SopAdapterTemplateRecord")
    assert not hasattr(state, "SopAdapterBindingRecord")
    assert not hasattr(state_repositories, "BaseSopAdapterTemplateRepository")
    assert not hasattr(state_repositories, "BaseSopAdapterBindingRepository")
    assert not hasattr(state_repositories, "SqliteSopAdapterTemplateRepository")
    assert not hasattr(state_repositories, "SqliteSopAdapterBindingRepository")


def test_fresh_state_schema_omits_legacy_sop_adapter_tables(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    store.initialize()

    with store.connection() as conn:
        tables = {
            str(row["name"])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'",
            ).fetchall()
        }

    assert "sop_adapter_templates" not in tables
    assert "sop_adapter_bindings" not in tables
