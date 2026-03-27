# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.kernel.governance import GovernanceService
from copaw.state import GovernanceControlRecord, SQLiteStateStore
from copaw.state.repositories import SqliteGovernanceControlRepository


def test_governance_service_no_longer_exposes_query_confirmation_policy_controls(
    tmp_path,
) -> None:
    repository = SqliteGovernanceControlRepository(
        SQLiteStateStore(tmp_path / "governance.sqlite3"),
    )
    service = GovernanceService(control_repository=repository)

    status = service.get_status()

    assert not hasattr(service, "set_query_confirmation_policy")
    assert "query_confirmation_policies" not in status.metadata
    control = repository.get_control("runtime")
    assert control is not None
    assert "query_confirmation_policies" not in control.metadata


def test_governance_service_preserves_runtime_metadata_without_query_confirmation_policy(
    tmp_path,
) -> None:
    repository = SqliteGovernanceControlRepository(
        SQLiteStateStore(tmp_path / "governance.sqlite3"),
    )
    service = GovernanceService(control_repository=repository)
    repository.upsert_control(
        GovernanceControlRecord(
            id="runtime",
            metadata={"retained": "ok"},
        )
    )

    status = service.get_status()

    assert status.metadata["retained"] == "ok"
    assert "query_confirmation_policies" not in status.metadata
    control = repository.get_control("runtime")
    assert control is not None
    assert control.metadata["retained"] == "ok"
    assert "query_confirmation_policies" not in control.metadata
