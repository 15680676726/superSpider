# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import timedelta

from copaw.app.runtime_bootstrap_query import build_surface_learning_bootstrap_projection
from copaw.app.runtime_bootstrap_repositories import build_runtime_repositories
from copaw.state import SQLiteStateStore
from copaw.state.models_surface_learning import (
    SurfaceCapabilityTwinRecord,
    SurfacePlaybookRecord,
)
from copaw.state.repositories import (
    SqliteSurfaceCapabilityTwinRepository,
    SqliteSurfacePlaybookRepository,
)


def test_surface_learning_repositories_round_trip_active_scope_and_history(
    tmp_path,
) -> None:
    store = SQLiteStateStore(tmp_path / "surface-learning-state.sqlite3")
    twin_repository = SqliteSurfaceCapabilityTwinRepository(store)
    playbook_repository = SqliteSurfacePlaybookRepository(store)

    first_twin = SurfaceCapabilityTwinRecord(
        twin_id="twin:industry:novel:upload_chapter:v1",
        scope_level="industry_scope",
        scope_id="industry:novel",
        capability_name="upload_chapter",
        capability_kind="browser-action",
        surface_kind="browser",
        summary="Upload a new novel chapter to the publishing page.",
        entry_conditions=["editor page ready"],
        execution_steps=["open chapter form", "fill title", "submit"],
        result_signals=["chapter published"],
        source_transition_refs=["evidence:transition:1"],
        version=1,
        status="active",
    )
    second_twin = first_twin.model_copy(
        update={
            "twin_id": "twin:industry:novel:upload_chapter:v2",
            "summary": "Upload and publish a chapter with validation checks.",
            "source_transition_refs": ["evidence:transition:2"],
            "version": 2,
            "updated_at": first_twin.updated_at + timedelta(minutes=5),
        }
    )
    playbook_v1 = SurfacePlaybookRecord(
        playbook_id="playbook:industry:novel:v1",
        twin_id=first_twin.twin_id,
        scope_level="industry_scope",
        scope_id="industry:novel",
        summary="Novel publishing quick playbook.",
        capability_names=["upload_chapter"],
        recommended_steps=["check latest draft", "upload chapter", "verify publish result"],
        execution_steps=["open chapter form", "submit publish"],
        success_signals=["chapter published"],
        version=1,
        status="active",
    )
    playbook_v2 = playbook_v1.model_copy(
        update={
            "playbook_id": "playbook:industry:novel:v2",
            "twin_id": second_twin.twin_id,
            "recommended_steps": [
                "check latest draft",
                "run validation",
                "upload chapter",
                "verify publish result",
            ],
            "version": 2,
            "updated_at": playbook_v1.updated_at + timedelta(minutes=5),
        }
    )

    twin_repository.upsert_twin(first_twin)
    twin_repository.upsert_twin(second_twin)
    playbook_repository.upsert_playbook(playbook_v1)
    playbook_repository.upsert_playbook(playbook_v2)

    active_twins = twin_repository.list_twins(
        scope_level="industry_scope",
        scope_id="industry:novel",
        status="active",
    )
    history_twins = twin_repository.list_twins(
        scope_level="industry_scope",
        scope_id="industry:novel",
    )
    active_playbook = playbook_repository.get_active_playbook(
        scope_level="industry_scope",
        scope_id="industry:novel",
    )
    history_playbooks = playbook_repository.list_playbooks(
        scope_level="industry_scope",
        scope_id="industry:novel",
    )

    assert [record.twin_id for record in active_twins] == [second_twin.twin_id]
    assert [record.twin_id for record in history_twins] == [
        second_twin.twin_id,
        first_twin.twin_id,
    ]
    assert history_twins[1].status == "superseded"
    assert active_playbook is not None
    assert active_playbook.playbook_id == playbook_v2.playbook_id
    assert [record.playbook_id for record in history_playbooks] == [
        playbook_v2.playbook_id,
        playbook_v1.playbook_id,
    ]
    assert history_playbooks[1].status == "superseded"


def test_build_runtime_repositories_includes_surface_learning_repositories(
    tmp_path,
) -> None:
    repositories = build_runtime_repositories(
        SQLiteStateStore(tmp_path / "surface-learning-bootstrap.sqlite3"),
    )

    assert repositories.surface_capability_twin_repository is not None
    assert repositories.surface_playbook_repository is not None


def test_surface_learning_bootstrap_projection_returns_scope_summary(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "surface-learning-query.sqlite3")
    repositories = build_runtime_repositories(store)
    twin = SurfaceCapabilityTwinRecord(
        twin_id="twin:role:writer:upload_chapter:v1",
        scope_level="role_scope",
        scope_id="writer",
        capability_name="upload_chapter",
        capability_kind="browser-action",
        surface_kind="browser",
        summary="Upload a chapter from the writer cockpit.",
        entry_conditions=["writer cockpit available"],
        execution_steps=["open chapter form", "submit publish"],
        result_signals=["chapter published"],
        version=3,
        status="active",
    )
    playbook = SurfacePlaybookRecord(
        playbook_id="playbook:role:writer:v3",
        twin_id=twin.twin_id,
        scope_level="role_scope",
        scope_id="writer",
        summary="Writer publishing shortcut playbook.",
        capability_names=["upload_chapter"],
        recommended_steps=["check draft", "publish chapter", "verify result"],
        execution_steps=["open chapter form", "submit publish"],
        success_signals=["chapter published"],
        version=3,
        status="active",
        updated_at=twin.updated_at + timedelta(minutes=3),
    )
    repositories.surface_capability_twin_repository.upsert_twin(twin)
    repositories.surface_playbook_repository.upsert_playbook(playbook)

    projection = build_surface_learning_bootstrap_projection(
        repositories=repositories,
        scope_level="role_scope",
        scope_id="writer",
    )

    assert projection is not None
    assert projection.scope_level == "role_scope"
    assert projection.scope_id == "writer"
    assert projection.version == 3
    assert projection.updated_at == playbook.updated_at
    assert [item.capability_name for item in projection.active_twins] == ["upload_chapter"]
    assert projection.active_playbook is not None
    assert projection.active_playbook.capability_names == ["upload_chapter"]
    assert not hasattr(projection.active_playbook, "raw_graph")
