# -*- coding: utf-8 -*-
from __future__ import annotations

from ..evidence import EvidenceLedger
from ..environments import (
    ActionReplayStore,
    ArtifactStore,
    EnvironmentRegistry,
    EnvironmentRepository,
    EnvironmentService,
    ObservationCache,
)
from ..constant import WORKING_DIR
from ..state import SQLiteStateStore
from .runtime_bootstrap_models import RuntimeRepositories
from .runtime_events import RuntimeEventBus


def build_runtime_observability(
    *,
    state_store: SQLiteStateStore,
    repositories: RuntimeRepositories,
) -> tuple[EvidenceLedger, EnvironmentRegistry, EnvironmentService, RuntimeEventBus]:
    evidence_ledger = EvidenceLedger(
        database_path=WORKING_DIR / "evidence" / "phase1.sqlite3",
    )
    environment_registry = EnvironmentRegistry(
        ledger=evidence_ledger,
        repository=EnvironmentRepository(state_store),
        session_repository=repositories.session_mount_repository,
    )
    runtime_event_bus = RuntimeEventBus()
    environment_service = EnvironmentService(registry=environment_registry)
    environment_service.set_session_repository(repositories.session_mount_repository)
    environment_service.set_observation_cache(
        ObservationCache(ledger=evidence_ledger),
    )
    environment_service.set_action_replay(
        ActionReplayStore(ledger=evidence_ledger),
    )
    environment_service.set_artifact_store(
        ArtifactStore(ledger=evidence_ledger),
    )
    environment_service.set_runtime_event_bus(runtime_event_bus)
    environment_service.set_agent_lease_repository(
        repositories.agent_lease_repository,
    )
    return (
        evidence_ledger,
        environment_registry,
        environment_service,
        runtime_event_bus,
    )
