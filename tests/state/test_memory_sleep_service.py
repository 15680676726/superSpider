# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.memory import (
    DerivedMemoryIndexService,
    MemoryReflectionService,
    MemoryRetainService,
    MemorySleepInferenceService,
    MemorySleepService,
)
from copaw.state import SQLiteStateStore, StrategyMemoryRecord
from copaw.state.knowledge_service import StateKnowledgeService
from copaw.state.repositories import (
    SqliteAgentReportRepository,
    SqliteKnowledgeChunkRepository,
    SqliteMemoryEntityViewRepository,
    SqliteMemoryFactIndexRepository,
    SqliteMemoryOpinionViewRepository,
    SqliteMemoryRelationViewRepository,
    SqliteMemoryReflectionRunRepository,
    SqliteMemorySleepRepository,
    SqliteStrategyMemoryRepository,
)
from copaw.state.strategy_memory_service import StateStrategyMemoryService


def _build_memory_sleep_services(tmp_path, *, inference_service=None):
    store = SQLiteStateStore(tmp_path / "state.db")
    knowledge_repo = SqliteKnowledgeChunkRepository(store)
    strategy_repo = SqliteStrategyMemoryRepository(store)
    agent_report_repo = SqliteAgentReportRepository(store)
    fact_repo = SqliteMemoryFactIndexRepository(store)
    entity_repo = SqliteMemoryEntityViewRepository(store)
    opinion_repo = SqliteMemoryOpinionViewRepository(store)
    relation_repo = SqliteMemoryRelationViewRepository(store)
    reflection_repo = SqliteMemoryReflectionRunRepository(store)
    sleep_repo = SqliteMemorySleepRepository(store)
    derived = DerivedMemoryIndexService(
        fact_index_repository=fact_repo,
        entity_view_repository=entity_repo,
        opinion_view_repository=opinion_repo,
        relation_view_repository=relation_repo,
        reflection_run_repository=reflection_repo,
        knowledge_repository=knowledge_repo,
        strategy_repository=strategy_repo,
        agent_report_repository=agent_report_repo,
        sidecar_backends=[],
    )
    reflection = MemoryReflectionService(
        derived_index_service=derived,
        entity_view_repository=entity_repo,
        opinion_view_repository=opinion_repo,
        reflection_run_repository=reflection_repo,
    )
    knowledge = StateKnowledgeService(
        repository=knowledge_repo,
        derived_index_service=derived,
        reflection_service=reflection,
    )
    strategy = StateStrategyMemoryService(
        repository=strategy_repo,
        derived_index_service=derived,
        reflection_service=reflection,
    )
    retain = MemoryRetainService(
        knowledge_service=knowledge,
        derived_index_service=derived,
        reflection_service=reflection,
    )
    sleep = MemorySleepService(
        repository=sleep_repo,
        knowledge_service=knowledge,
        strategy_memory_service=strategy,
        derived_index_service=derived,
        reflection_service=reflection,
        inference_service=inference_service or MemorySleepInferenceService(),
    )
    knowledge.set_memory_sleep_service(sleep)
    strategy.set_memory_sleep_service(sleep)
    retain.set_memory_sleep_service(sleep)
    return store, knowledge, strategy, retain, sleep


def test_memory_sleep_service_marks_dirty_scopes_from_formal_writes(tmp_path) -> None:
    _store, knowledge, strategy, _retain, sleep = _build_memory_sleep_services(tmp_path)

    knowledge.remember_fact(
        title="Finance review gate",
        content="Outbound approval must wait for finance review.",
        scope_type="work_context",
        scope_id="ctx-sleep-1",
        source_ref="fact:ctx-sleep-1:1",
        tags=["approval"],
    )
    strategy.upsert_strategy(
        StrategyMemoryRecord(
            strategy_id="strategy:industry:industry-sleep-1:main-brain",
            scope_type="industry",
            scope_id="industry-sleep-1",
            owner_agent_id="main-brain",
            industry_instance_id="industry-sleep-1",
            title="Evidence-first outbound",
            summary="Keep outbound blocked until finance review completes.",
            execution_constraints=["Wait for finance review before outbound approval."],
            current_focuses=["Clear the finance review gate."],
        ),
    )

    dirty_scopes = sleep.list_scope_states(dirty_only=True)
    dirty_pairs = {(item.scope_type, item.scope_id) for item in dirty_scopes}
    assert ("work_context", "ctx-sleep-1") in dirty_pairs
    assert ("industry", "industry-sleep-1") in dirty_pairs


def test_memory_sleep_service_run_sleep_builds_artifacts_and_supersedes_prior_digest(tmp_path) -> None:
    _store, knowledge, _strategy, _retain, sleep = _build_memory_sleep_services(tmp_path)

    knowledge.remember_fact(
        title="Finance evidence review",
        content="Outbound approval must wait for finance review.",
        scope_type="work_context",
        scope_id="ctx-sleep-2",
        source_ref="fact:ctx-sleep-2:1",
        tags=["approval"],
    )
    knowledge.remember_fact(
        title="Finance review checklist",
        content="The team also calls finance evidence review simply finance review.",
        scope_type="work_context",
        scope_id="ctx-sleep-2",
        source_ref="fact:ctx-sleep-2:2",
        tags=["approval"],
    )
    knowledge.remember_fact(
        title="Approval shortcut conflict",
        content="A legacy note says outbound approval can happen before finance review.",
        scope_type="work_context",
        scope_id="ctx-sleep-2",
        source_ref="fact:ctx-sleep-2:3",
        tags=["conflict"],
    )

    first_job = sleep.run_sleep(
        scope_type="work_context",
        scope_id="ctx-sleep-2",
        trigger_kind="manual",
    )

    assert first_job.status == "completed"
    digest = sleep.get_active_digest("work_context", "ctx-sleep-2")
    assert digest is not None
    assert digest.version == 1
    assert sleep.list_alias_maps(scope_type="work_context", scope_id="ctx-sleep-2")
    assert sleep.list_merge_results(scope_type="work_context", scope_id="ctx-sleep-2")
    assert sleep.list_soft_rules(scope_type="work_context", scope_id="ctx-sleep-2")
    assert sleep.list_conflict_proposals(scope_type="work_context", scope_id="ctx-sleep-2")

    scope_state = sleep.get_scope_state(scope_type="work_context", scope_id="ctx-sleep-2")
    assert scope_state is not None
    assert scope_state.is_dirty is False
    assert scope_state.last_sleep_job_id == first_job.job_id

    knowledge.remember_fact(
        title="Current blocker",
        content="Customer message is still blocked until finance review is complete.",
        scope_type="work_context",
        scope_id="ctx-sleep-2",
        source_ref="fact:ctx-sleep-2:4",
        tags=["approval"],
    )
    second_job = sleep.run_sleep(
        scope_type="work_context",
        scope_id="ctx-sleep-2",
        trigger_kind="manual",
    )

    assert second_job.status == "completed"
    digests = sleep.list_digests(scope_type="work_context", scope_id="ctx-sleep-2")
    assert digests[0].status == "active"
    assert digests[0].version == 2
    assert digests[1].status == "superseded"
    assert len(sleep.list_sleep_jobs(scope_type="work_context", scope_id="ctx-sleep-2")) == 2

    overlay = sleep.resolve_scope_overlay(scope_type="work_context", scope_id="ctx-sleep-2")
    assert overlay["digest"] is not None
    assert overlay["digest"].version == 2


def test_memory_sleep_service_normalizes_model_enum_payload_before_persisting(tmp_path) -> None:
    class _InferenceService:
        @staticmethod
        def infer(**kwargs):
            _ = kwargs
            return {
                "digest": {
                    "headline": "Finance review digest",
                    "summary": "Sleep layer compiled the latest finance review rule.",
                    "current_constraints": ["Wait for finance review before outbound approval."],
                },
                "alias_maps": [],
                "merge_results": [],
                "soft_rules": [
                    {
                        "rule_text": "Wait for finance review before outbound approval.",
                        "state": "proposed",
                    }
                ],
                "conflict_proposals": [
                    {
                        "title": "Approval order conflict",
                        "summary": "Legacy notes disagree with the stricter finance-review gate.",
                        "status": "unresolved",
                    }
                ],
            }

    _store, knowledge, _strategy, _retain, sleep = _build_memory_sleep_services(
        tmp_path,
        inference_service=_InferenceService(),
    )

    knowledge.remember_fact(
        title="Finance review gate",
        content="Outbound approval must wait for finance review.",
        scope_type="work_context",
        scope_id="ctx-sleep-3",
        source_ref="fact:ctx-sleep-3:1",
        tags=["approval"],
    )

    job = sleep.run_sleep(
        scope_type="work_context",
        scope_id="ctx-sleep-3",
        trigger_kind="manual",
    )

    assert job.status == "completed"
    rules = sleep.list_soft_rules(scope_type="work_context", scope_id="ctx-sleep-3")
    proposals = sleep.list_conflict_proposals(scope_type="work_context", scope_id="ctx-sleep-3")
    assert rules[0].state == "candidate"
    assert proposals[0].status == "pending"


def test_memory_sleep_service_marks_job_failed_and_keeps_scope_dirty_on_inference_error(tmp_path) -> None:
    class _InferenceService:
        @staticmethod
        def infer(**kwargs):
            _ = kwargs
            raise RuntimeError("sleep inference exploded")

    _store, knowledge, _strategy, _retain, sleep = _build_memory_sleep_services(
        tmp_path,
        inference_service=_InferenceService(),
    )

    knowledge.remember_fact(
        title="Finance review gate",
        content="Outbound approval must wait for finance review.",
        scope_type="work_context",
        scope_id="ctx-sleep-4",
        source_ref="fact:ctx-sleep-4:1",
        tags=["approval"],
    )

    job = sleep.run_sleep(
        scope_type="work_context",
        scope_id="ctx-sleep-4",
        trigger_kind="manual",
    )

    assert job.status == "failed"
    assert job.completed_at is not None
    assert "sleep inference exploded" in str(job.metadata.get("error") or "")

    scope_state = sleep.get_scope_state(scope_type="work_context", scope_id="ctx-sleep-4")
    assert scope_state is not None
    assert scope_state.is_dirty is True
    assert scope_state.last_sleep_job_id == job.job_id
    assert scope_state.last_sleep_at is None
    assert sleep.get_active_digest("work_context", "ctx-sleep-4") is None


def test_memory_sleep_service_builds_industry_profile_work_overlay_and_structure_proposal(tmp_path) -> None:
    _store, knowledge, strategy, _retain, sleep = _build_memory_sleep_services(tmp_path)

    strategy.upsert_strategy(
        StrategyMemoryRecord(
            strategy_id="strategy:industry:industry-memory-1:main-brain",
            scope_type="industry",
            scope_id="industry-memory-1",
            owner_agent_id="main-brain",
            industry_instance_id="industry-memory-1",
            title="证据先行行业基线",
            summary="行业当前要求任何外呼动作都必须先通过财务复核。",
            execution_constraints=["外呼动作前必须先完成财务复核。"],
            current_focuses=["先收口共享行业规则，再放行外呼执行。"],
        ),
    )
    knowledge.remember_fact(
        title="共享行业规则",
        content="财务复核是当前行业共享规则，所有外呼审批都要先等它完成。",
        scope_type="industry",
        scope_id="industry-memory-1",
        source_ref="knowledge:industry-memory-1:1",
        tags=["approval", "finance"],
    )
    sleep.run_sleep(
        scope_type="industry",
        scope_id="industry-memory-1",
        trigger_kind="manual",
    )

    knowledge.remember_fact(
        title="当前工作焦点",
        content="当前工作上下文正在处理财务复核和外呼审批的先后顺序。",
        scope_type="work_context",
        scope_id="ctx-memory-overlay-1",
        source_ref="knowledge:ctx-memory-overlay-1:1",
        tags=["approval", "finance"],
    )
    scope_state = sleep.mark_scope_dirty(
        scope_type="work_context",
        scope_id="ctx-memory-overlay-1",
        industry_instance_id="industry-memory-1",
        reason="manual-bind-industry",
        source_ref="knowledge:ctx-memory-overlay-1:1",
    )
    assert scope_state.industry_instance_id == "industry-memory-1"

    job = sleep.run_sleep(
        scope_type="work_context",
        scope_id="ctx-memory-overlay-1",
        trigger_kind="manual",
    )

    assert job.status == "completed"
    industry_profile = sleep.get_active_industry_profile("industry-memory-1")
    assert industry_profile is not None
    assert industry_profile.strategic_direction
    assert "财务复核" in " ".join(industry_profile.active_constraints + industry_profile.active_focuses)

    overlay = sleep.get_active_work_context_overlay("ctx-memory-overlay-1")
    assert overlay is not None
    assert overlay.base_profile_id == industry_profile.profile_id
    assert overlay.industry_instance_id == "industry-memory-1"
    assert overlay.focus_summary
    assert "财务复核" in " ".join(
        [overlay.focus_summary, *overlay.active_constraints, *overlay.active_focuses],
    )

    proposals = sleep.list_structure_proposals(
        scope_type="work_context",
        scope_id="ctx-memory-overlay-1",
        status="pending",
    )
    assert proposals
    assert proposals[0].candidate_overlay_id == overlay.overlay_id
    assert proposals[0].candidate_profile_id == industry_profile.profile_id
