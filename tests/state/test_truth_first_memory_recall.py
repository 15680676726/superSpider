# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from copaw.evidence.models import EvidenceRecord
from copaw.memory import MemoryPrecedenceService, MemoryProfileService, MemoryRecallService
from copaw.state import AgentReportRecord, SQLiteStateStore, StrategyMemoryRecord
from copaw.state.knowledge_service import StateKnowledgeService
from copaw.state.repositories import (
    SqliteAgentReportRepository,
    SqliteKnowledgeChunkRepository,
    SqliteMemoryFactIndexRepository,
    SqliteStrategyMemoryRepository,
)
from copaw.state.strategy_memory_service import StateStrategyMemoryService
from copaw.state.models import MemoryFactIndexRecord


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _build_services(tmp_path):
    store = SQLiteStateStore(tmp_path / "state.db")
    knowledge_repo = SqliteKnowledgeChunkRepository(store)
    strategy_repo = SqliteStrategyMemoryRepository(store)
    agent_report_repo = SqliteAgentReportRepository(store)
    fact_repo = SqliteMemoryFactIndexRepository(store)

    from copaw.memory import DerivedMemoryIndexService

    derived = DerivedMemoryIndexService(
        fact_index_repository=fact_repo,
        knowledge_repository=knowledge_repo,
        strategy_repository=strategy_repo,
        agent_report_repository=agent_report_repo,
    )
    knowledge = StateKnowledgeService(
        repository=knowledge_repo,
        derived_index_service=derived,
        reflection_service=None,
    )
    strategy = StateStrategyMemoryService(
        repository=strategy_repo,
        derived_index_service=derived,
        reflection_service=None,
    )
    profile = MemoryProfileService(derived_index_service=derived)
    recall = MemoryRecallService(derived_index_service=derived)

    class _IndexedAgentReports:
        def __init__(self, repository, index_service) -> None:
            self._repository = repository
            self._index_service = index_service

        def upsert_report(self, record: AgentReportRecord) -> AgentReportRecord:
            stored = self._repository.upsert_report(record)
            self._index_service.upsert_agent_report(stored)
            return stored

    return {
        "store": store,
        "knowledge": knowledge,
        "strategy": strategy,
        "agent_reports": _IndexedAgentReports(agent_report_repo, derived),
        "derived": derived,
        "profile": profile,
        "recall": recall,
    }


def _fact(
    entry_id: str,
    *,
    title: str,
    summary: str = "",
    content_text: str = "",
    scope_type: str = "industry",
    scope_id: str = "industry-1",
    source_type: str = "knowledge_chunk",
    source_ref: str | None = None,
    evidence_refs: list[str] | None = None,
    metadata: dict | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> MemoryFactIndexRecord:
    created = created_at or _now()
    updated = updated_at or created
    return MemoryFactIndexRecord(
        id=entry_id,
        source_type=source_type,
        source_ref=source_ref or entry_id,
        scope_type=scope_type,
        scope_id=scope_id,
        title=title,
        summary=summary,
        content_excerpt=summary or content_text[:80],
        content_text=content_text or summary or title,
        evidence_refs=list(evidence_refs or []),
        metadata=dict(metadata or {}),
        created_at=created,
        updated_at=updated,
        source_updated_at=updated,
    )


def test_profile_service_derives_shared_profile_from_truth_sources(tmp_path) -> None:
    services = _build_services(tmp_path)
    strategy = services["strategy"]
    knowledge = services["knowledge"]
    derived = services["derived"]
    profile_service = services["profile"]

    strategy.upsert_strategy(
        StrategyMemoryRecord(
            strategy_id="strategy:industry:industry-1:main-brain",
            scope_type="industry",
            scope_id="industry-1",
            owner_agent_id="main-brain",
            industry_instance_id="industry-1",
            title="Outbound discipline",
            summary="Operate with evidence-backed outbound control.",
            mission="Protect signal quality before volume.",
            execution_constraints=["No outbound action without evidence review."],
            evidence_requirements=["Evidence review is mandatory before outreach."],
            current_focuses=["Move research findings into verified operator-ready actions."],
        ),
    )
    knowledge.remember_fact(
        title="Current workspace",
        content="The active work context is a shared outbound review board for operator follow-up.",
        scope_type="work_context",
        scope_id="wc-1",
        source_ref="work-context:wc-1",
        role_bindings=["execution-core"],
        tags=["context"],
    )
    derived.upsert_agent_report(
        AgentReportRecord(
            id="report-1",
            industry_instance_id="industry-1",
            work_context_id="wc-1",
            owner_agent_id="agent-researcher",
            owner_role_id="execution-core",
            headline="Research is ready for evidence review",
            summary="Follow-up should stay on the shared review board until the evidence pass completes.",
            evidence_ids=["evidence-1"],
            processed=True,
            result="completed",
        ),
    )
    derived.upsert_evidence(
        EvidenceRecord(
            id="evidence-1",
            task_id="task-1",
            actor_ref="execution-core",
            risk_level="guarded",
            action_summary="Reviewed outbound evidence package",
            result_summary="Evidence package confirms the current outreach draft.",
            metadata={"work_context_id": "wc-1"},
        ),
    )

    views = profile_service.build_views(scope_type="work_context", scope_id="wc-1")

    assert "Operate with evidence-backed outbound control." in " ".join(views.profile.static_profile)
    assert "Protect signal quality before volume." in " ".join(views.profile.static_profile)
    assert "evidence review" in views.profile.current_focus_summary.lower()
    assert any("shared outbound review board" in item.lower() for item in views.profile.current_operating_context)
    assert any("evidence package confirms" in item.lower() for item in views.profile.dynamic_profile)
    assert any("No outbound action without evidence review." in item for item in views.profile.active_constraints)


def test_precedence_service_prefers_durable_evidence_backed_fact_over_temporary_and_inference() -> None:
    service = MemoryPrecedenceService()
    base = _now()
    entries = [
        _fact(
            "durable-plain",
            title="Outbound policy",
            summary="Use the outbound playbook.",
            evidence_refs=[],
            metadata={"memory_type": "fact", "subject_key": "policy:outbound"},
            created_at=base - timedelta(minutes=3),
            updated_at=base - timedelta(minutes=3),
        ),
        _fact(
            "temporary",
            title="Outbound policy",
            summary="Pause for now.",
            metadata={"memory_type": "temporary", "subject_key": "policy:outbound"},
            created_at=base,
            updated_at=base,
        ),
        _fact(
            "inference",
            title="Outbound policy",
            summary="We probably should pause outreach.",
            source_type="agent_report",
            metadata={"memory_type": "inference", "subject_key": "policy:outbound"},
            created_at=base - timedelta(minutes=1),
            updated_at=base - timedelta(minutes=1),
        ),
        _fact(
            "durable-evidence",
            title="Outbound policy",
            summary="Only send outbound after evidence review.",
            evidence_refs=["evidence-1"],
            metadata={"memory_type": "fact", "subject_key": "policy:outbound"},
            created_at=base - timedelta(minutes=2),
            updated_at=base - timedelta(minutes=2),
        ),
    ]

    partition = service.partition_entries(entries)

    assert [entry.id for entry in partition.latest] == ["durable-evidence"]
    assert {entry.id for entry in partition.history} == {"durable-plain", "temporary", "inference"}


def test_precedence_service_splits_latest_history_and_filters_expired_records() -> None:
    service = MemoryPrecedenceService()
    base = _now()
    entries = [
        _fact(
            "history-1",
            title="Shared context",
            summary="Old board is still active.",
            metadata={"memory_type": "fact", "subject_key": "context:shared"},
            created_at=base - timedelta(days=2),
            updated_at=base - timedelta(days=2),
        ),
        _fact(
            "latest-1",
            title="Shared context",
            summary="New board is the active workspace.",
            metadata={"memory_type": "fact", "subject_key": "context:shared"},
            created_at=base - timedelta(hours=2),
            updated_at=base - timedelta(hours=2),
        ),
        _fact(
            "expired-temp",
            title="Shared context",
            summary="Temporary freeze on edits.",
            metadata={
                "memory_type": "temporary",
                "subject_key": "context:shared",
                "expires_at": (base - timedelta(minutes=5)).isoformat(),
            },
            created_at=base - timedelta(minutes=10),
            updated_at=base - timedelta(minutes=10),
        ),
    ]

    partition = service.partition_entries(entries, now=base)

    assert [entry.id for entry in partition.latest] == ["latest-1"]
    assert {entry.id for entry in partition.history} == {"history-1", "expired-temp"}


def test_truth_first_recall_contract_has_no_vector_or_sidecar_runtime_surface(tmp_path) -> None:
    services = _build_services(tmp_path)
    strategy = services["strategy"]
    knowledge = services["knowledge"]
    recall = services["recall"]

    strategy.upsert_strategy(
        StrategyMemoryRecord(
            strategy_id="strategy:industry:industry-1:main-brain",
            scope_type="industry",
            scope_id="industry-1",
            owner_agent_id="main-brain",
            industry_instance_id="industry-1",
            title="Truth-first recall",
            summary="Profile and latest facts come before lexical fallback.",
            mission="Keep recall explicit and auditable.",
            current_focuses=["Use shared truth-derived memory views."],
        ),
    )
    knowledge.remember_fact(
        title="Outbound follow-up",
        content="The active workstream requires evidence-backed outbound follow-up.",
        scope_type="industry",
        scope_id="industry-1",
        role_bindings=["execution-core"],
        tags=["policy"],
    )

    descriptors = recall.list_backends()
    response = recall.recall(
        query="evidence backed outbound",
        scope_type="industry",
        scope_id="industry-1",
        role="execution-core",
        limit=5,
    )

    assert [descriptor.backend_id for descriptor in descriptors] == ["truth-first"]
    assert response.backend_used == "truth-first"
    assert response.hits
    assert response.hits[0].source_type == "memory_profile"
    assert not hasattr(recall, "prepare_sidecar_backends")
    assert not (Path("src/copaw/memory/qmd_backend.py")).exists()
    assert not (Path("src/copaw/memory/qmd_bridge_server.mjs")).exists()
    recall_source = Path("src/copaw/memory/recall_service.py").read_text(encoding="utf-8")
    derived_source = Path("src/copaw/memory/derived_index_service.py").read_text(encoding="utf-8")
    memory_init_source = Path("src/copaw/memory/__init__.py").read_text(encoding="utf-8")
    assert "hashed_vector(" not in recall_source
    assert "hashed_vector(" not in derived_source
    assert "local-vector" not in recall_source
    assert "hybrid-local" not in recall_source
    assert "QmdBackendConfig" not in memory_init_source
    assert "QmdRecallBackend" not in memory_init_source


def test_legacy_rows_rebuild_into_profile_latest_and_history_views(tmp_path) -> None:
    services = _build_services(tmp_path)
    strategy = services["strategy"]
    knowledge = services["knowledge"]
    derived = services["derived"]
    profile_service = services["profile"]

    strategy.upsert_strategy(
        StrategyMemoryRecord(
            strategy_id="strategy:industry:industry-1:main-brain",
            scope_type="industry",
            scope_id="industry-1",
            owner_agent_id="main-brain",
            industry_instance_id="industry-1",
            title="Legacy rebuild",
            summary="Legacy rows should still rebuild into truth-first views.",
            mission="Treat the fact index as a rebuildable projection.",
        ),
    )
    knowledge.remember_fact(
        title="Shared history",
        content="Old workspace summary for the outbound board.",
        scope_type="industry",
        scope_id="industry-1",
        source_ref="legacy:old",
        role_bindings=["execution-core"],
    )
    knowledge.remember_fact(
        title="Shared history",
        content="Current workspace summary for the outbound board with verified evidence.",
        scope_type="industry",
        scope_id="industry-1",
        source_ref="legacy:new",
        role_bindings=["execution-core"],
    )
    rebuild = derived.rebuild_all(
        scope_type="industry",
        scope_id="industry-1",
        include_reporting=False,
        include_learning=False,
        evidence_limit=0,
    )
    views = profile_service.build_views(scope_type="industry", scope_id="industry-1")

    assert rebuild.fact_index_count >= 3
    assert views.profile.static_profile
    assert views.latest
    assert views.history
    assert any(entry.source_type == "strategy_memory" for entry in views.latest)
    assert any(entry.title == "Shared history" for entry in views.history)
