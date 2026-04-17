# -*- coding: utf-8 -*-
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import threading

from copaw.memory import (
    DerivedMemoryIndexService,
    MemoryReflectionService,
    MemoryRetainService,
    MemorySleepInferenceService,
    MemorySleepService,
)
from copaw.state import (
    IndustryMemoryProfileRecord,
    MemoryStructureProposalRecord,
    SQLiteStateStore,
    StrategyMemoryRecord,
    WorkContextMemoryOverlayRecord,
)
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


def test_memory_sleep_service_long_chain_survives_restart_and_continues_same_work_context(
    tmp_path,
) -> None:
    class _LongChainInferenceService:
        @staticmethod
        def infer(**kwargs):
            scope_type = str(kwargs.get("scope_type") or "")
            scope_id = str(kwargs.get("scope_id") or "")
            knowledge_chunks = list(kwargs.get("knowledge_chunks") or [])
            joined_text = "\n".join(
                str(getattr(item, "content", "") or "")
                for item in knowledge_chunks
            ).lower()
            archive_mode = "evidence archive" in joined_text
            focus_line = (
                "Evidence archive before outbound confirmation."
                if archive_mode
                else "Finance review before outbound approval."
            )
            payload = {
                "digest": {
                    "headline": f"Digest for {scope_id}",
                    "summary": focus_line,
                    "current_constraints": [focus_line],
                    "current_focus": [focus_line],
                    "top_entities": ["finance-review"],
                    "top_relations": ["work-context->finance-review"],
                },
                "alias_maps": [],
                "merge_results": [],
                "soft_rules": [
                    {
                        "rule_text": focus_line,
                        "state": "candidate",
                    }
                ],
                "conflict_proposals": [],
            }
            if scope_type == "industry":
                payload["industry_profile"] = {
                    "headline": "Industry finance baseline",
                    "summary": focus_line,
                    "strategic_direction": focus_line,
                    "active_constraints": [focus_line],
                    "active_focuses": [focus_line],
                    "key_entities": ["finance-review"],
                    "key_relations": ["industry->finance-review"],
                }
                return payload
            payload["work_context_overlay"] = {
                "headline": f"Overlay for {scope_id}",
                "summary": focus_line,
                "focus_summary": focus_line,
                "active_constraints": [focus_line],
                "active_focuses": [focus_line],
                "active_entities": ["finance-review"],
                "active_relations": ["work-context->finance-review"],
            }
            if "legacy note still says outbound approval may happen before finance review" in joined_text:
                payload["conflict_proposals"] = [
                    {
                        "title": "Approval order conflict",
                        "summary": "Legacy guidance still conflicts with the stricter finance-review gate.",
                        "recommended_action": "Keep finance review as the hard gate until legacy guidance is cleared.",
                        "status": "pending",
                    }
                ]
            return payload

    inference_service = _LongChainInferenceService()
    _store, knowledge, strategy, _retain, sleep = _build_memory_sleep_services(
        tmp_path,
        inference_service=inference_service,
    )

    strategy.upsert_strategy(
        StrategyMemoryRecord(
            strategy_id="strategy:industry:industry-long-chain-1:main-brain",
            scope_type="industry",
            scope_id="industry-long-chain-1",
            owner_agent_id="main-brain",
            industry_instance_id="industry-long-chain-1",
            title="Evidence-first outbound lane",
            summary="Keep outbound approval blocked until finance review and evidence archive complete.",
            execution_constraints=[
                "Do not approve outbound before finance review.",
                "Evidence archive must be captured before outbound confirmation.",
            ],
            current_focuses=[
                "Hold the outbound lane on finance review.",
            ],
        ),
    )
    knowledge.remember_fact(
        title="Industry finance gate",
        content="All outbound approvals in this industry must wait for finance review.",
        scope_type="industry",
        scope_id="industry-long-chain-1",
        source_ref="knowledge:industry-long-chain-1:1",
        tags=["approval", "finance"],
    )
    industry_job = sleep.run_sleep(
        scope_type="industry",
        scope_id="industry-long-chain-1",
        trigger_kind="manual",
    )
    assert industry_job.status == "completed"

    knowledge.remember_fact(
        title="Current work context blocker",
        content="Outbound approval is currently blocked by the finance review step.",
        scope_type="work_context",
        scope_id="ctx-long-chain-1",
        source_ref="knowledge:ctx-long-chain-1:1",
        tags=["approval", "finance"],
    )
    knowledge.remember_fact(
        title="Legacy conflicting note",
        content="A legacy note still says outbound approval may happen before finance review.",
        scope_type="work_context",
        scope_id="ctx-long-chain-1",
        source_ref="knowledge:ctx-long-chain-1:2",
        tags=["approval", "conflict"],
    )
    sleep.mark_scope_dirty(
        scope_type="work_context",
        scope_id="ctx-long-chain-1",
        industry_instance_id="industry-long-chain-1",
        reason="bind-industry",
        source_ref="knowledge:ctx-long-chain-1:1",
    )

    first_job = sleep.run_sleep(
        scope_type="work_context",
        scope_id="ctx-long-chain-1",
        trigger_kind="manual",
    )
    assert first_job.status == "completed"
    first_overlay = sleep.get_active_work_context_overlay("ctx-long-chain-1")
    assert first_overlay is not None
    assert first_overlay.version >= 1
    assert first_overlay.industry_instance_id == "industry-long-chain-1"
    first_pending_conflicts = sleep.list_conflict_proposals(
        scope_type="work_context",
        scope_id="ctx-long-chain-1",
        status="pending",
        limit=None,
    )
    assert first_pending_conflicts

    _store_restarted, knowledge_restarted, _strategy_restarted, _retain_restarted, sleep_restarted = (
        _build_memory_sleep_services(tmp_path, inference_service=inference_service)
    )

    restarted_overlay = sleep_restarted.get_active_work_context_overlay("ctx-long-chain-1")
    assert restarted_overlay is not None
    assert restarted_overlay.overlay_id == first_overlay.overlay_id
    restarted_profile = sleep_restarted.get_active_industry_profile("industry-long-chain-1")
    assert restarted_profile is not None
    assert restarted_profile.industry_instance_id == "industry-long-chain-1"
    restarted_surface = sleep_restarted.resolve_scope_overlay(
        scope_type="work_context",
        scope_id="ctx-long-chain-1",
    )
    assert restarted_surface["work_context_overlay"] is not None
    assert restarted_surface["industry_profile"] is not None
    assert restarted_surface["conflicts"]

    knowledge_restarted.remember_fact(
        title="Next-day continuity update",
        content="Finance review is complete; keep the lane focused on evidence archive before outbound confirmation.",
        scope_type="work_context",
        scope_id="ctx-long-chain-1",
        source_ref="knowledge:ctx-long-chain-1:3",
        tags=["approval", "archive", "follow-up"],
    )
    scheduled_jobs = sleep_restarted.run_due_sleep_jobs(limit=None)
    assert scheduled_jobs
    assert scheduled_jobs[0].status == "completed"
    assert scheduled_jobs[0].trigger_kind == "scheduled"

    latest_overlay = sleep_restarted.get_active_work_context_overlay("ctx-long-chain-1")
    assert latest_overlay is not None
    assert latest_overlay.version >= 2
    assert latest_overlay.industry_instance_id == "industry-long-chain-1"
    assert "evidence archive" in " ".join(
        [
            latest_overlay.headline,
            latest_overlay.summary,
            latest_overlay.focus_summary,
            *latest_overlay.active_constraints,
            *latest_overlay.active_focuses,
        ]
    ).lower()
    latest_scope_state = sleep_restarted.get_scope_state(
        scope_type="work_context",
        scope_id="ctx-long-chain-1",
    )
    assert latest_scope_state is not None
    assert latest_scope_state.is_dirty is False
    assert latest_scope_state.last_sleep_job_id == scheduled_jobs[0].job_id
    latest_pending_conflicts = sleep_restarted.list_conflict_proposals(
        scope_type="work_context",
        scope_id="ctx-long-chain-1",
        status="pending",
        limit=None,
    )
    assert latest_pending_conflicts


def test_memory_sleep_service_parallel_scope_runs_keep_single_active_overlay_truth(tmp_path) -> None:
    class _BarrierInferenceService:
        def __init__(self) -> None:
            self._barrier = threading.Barrier(2)

        def infer(self, **kwargs):
            scope_id = str(kwargs.get("scope_id") or "scope")
            try:
                self._barrier.wait(timeout=5)
            except threading.BrokenBarrierError as exc:  # pragma: no cover - defensive guard
                raise AssertionError("parallel sleep inference barrier broke") from exc
            return {
                "digest": {
                    "headline": f"Concurrent digest {scope_id}",
                    "summary": "Both workers compiled the same work context.",
                    "current_constraints": ["Wait for finance review before outbound approval."],
                    "current_focus": ["Keep the outbound lane aligned."],
                    "top_entities": ["finance-review"],
                    "top_relations": ["work-context->finance-review"],
                },
                "alias_maps": [],
                "merge_results": [],
                "soft_rules": [],
                "conflict_proposals": [],
                "work_context_overlay": {
                    "headline": f"Concurrent overlay {scope_id}",
                    "summary": "Parallel runs should still converge to one active overlay.",
                    "focus_summary": "Keep the outbound lane aligned.",
                    "active_constraints": ["Wait for finance review before outbound approval."],
                    "active_focuses": ["Keep the outbound lane aligned."],
                    "active_entities": ["finance-review"],
                    "active_relations": ["work-context->finance-review"],
                },
            }

    _store_seed, knowledge_seed, strategy_seed, _retain_seed, sleep_seed = _build_memory_sleep_services(tmp_path)
    strategy_seed.upsert_strategy(
        StrategyMemoryRecord(
            strategy_id="strategy:industry:industry-concurrent-1:main-brain",
            scope_type="industry",
            scope_id="industry-concurrent-1",
            owner_agent_id="main-brain",
            industry_instance_id="industry-concurrent-1",
            title="Concurrent industry baseline",
            summary="Keep outbound approval blocked until finance review.",
            execution_constraints=["Wait for finance review before outbound approval."],
            current_focuses=["Hold the outbound lane on finance review."],
        ),
    )
    knowledge_seed.remember_fact(
        title="Concurrent industry rule",
        content="This industry keeps outbound approval behind finance review.",
        scope_type="industry",
        scope_id="industry-concurrent-1",
        source_ref="knowledge:industry-concurrent-1:1",
        tags=["approval", "finance"],
    )
    sleep_seed.run_sleep(
        scope_type="industry",
        scope_id="industry-concurrent-1",
        trigger_kind="manual",
    )
    knowledge_seed.remember_fact(
        title="Concurrent work context",
        content="The current work context still needs finance review before outbound approval.",
        scope_type="work_context",
        scope_id="ctx-concurrent-1",
        source_ref="knowledge:ctx-concurrent-1:1",
        tags=["approval", "finance"],
    )
    sleep_seed.mark_scope_dirty(
        scope_type="work_context",
        scope_id="ctx-concurrent-1",
        industry_instance_id="industry-concurrent-1",
        reason="bind-industry",
        source_ref="knowledge:ctx-concurrent-1:1",
    )

    inference_service = _BarrierInferenceService()
    _store_a, _knowledge_a, _strategy_a, _retain_a, sleep_a = _build_memory_sleep_services(
        tmp_path,
        inference_service=inference_service,
    )
    _store_b, _knowledge_b, _strategy_b, _retain_b, sleep_b = _build_memory_sleep_services(
        tmp_path,
        inference_service=inference_service,
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        jobs = list(
            executor.map(
                lambda service: service.run_sleep(
                    scope_type="work_context",
                    scope_id="ctx-concurrent-1",
                    trigger_kind="manual",
                ),
                (sleep_a, sleep_b),
            )
        )

    assert len(jobs) == 2
    assert all(job.status == "completed" for job in jobs)

    _store_verify, _knowledge_verify, _strategy_verify, _retain_verify, sleep_verify = (
        _build_memory_sleep_services(tmp_path)
    )
    active_overlays = sleep_verify.list_work_context_overlays(
        work_context_id="ctx-concurrent-1",
        status="active",
        limit=None,
    )
    assert len(active_overlays) == 1
    active_overlay = active_overlays[0]
    assert active_overlay.industry_instance_id == "industry-concurrent-1"
    active_digests = [
        item
        for item in sleep_verify.list_digests(
            scope_type="work_context",
            scope_id="ctx-concurrent-1",
            limit=None,
        )
        if item.status == "active"
    ]
    assert len(active_digests) == 1
    pending_structure_proposals = sleep_verify.list_structure_proposals(
        scope_type="work_context",
        scope_id="ctx-concurrent-1",
        status="pending",
        limit=None,
    )
    assert len(pending_structure_proposals) == 1
    assert pending_structure_proposals[0].candidate_overlay_id == active_overlay.overlay_id
    latest_scope_state = sleep_verify.get_scope_state(
        scope_type="work_context",
        scope_id="ctx-concurrent-1",
    )
    assert latest_scope_state is not None
    assert latest_scope_state.is_dirty is False
    assert len(sleep_verify.list_sleep_jobs(scope_type="work_context", scope_id="ctx-concurrent-1")) == 2


def test_memory_sleep_service_builds_continuity_anchors_from_graph_and_activation(tmp_path) -> None:
    _store, knowledge, strategy, _retain, sleep = _build_memory_sleep_services(tmp_path)

    strategy.upsert_strategy(
        StrategyMemoryRecord(
            strategy_id="strategy:industry:industry-anchor-1:main-brain",
            scope_type="industry",
            scope_id="industry-anchor-1",
            owner_agent_id="main-brain",
            industry_instance_id="industry-anchor-1",
            title="Review before confirmation",
            summary="Keep review-first continuity stable.",
            execution_constraints=["Finish finance review before customer confirmation."],
            current_focuses=["Protect the review-first order."],
        ),
    )
    knowledge.remember_fact(
        title="Finance review gate",
        content="Customer confirmation must wait until finance review proof is complete.",
        scope_type="work_context",
        scope_id="ctx-anchor-1",
        source_ref="fact:ctx-anchor-1:1",
        tags=["finance", "review"],
    )
    knowledge.remember_fact(
        title="Customer confirmation order",
        content="Do not send customer confirmation before finance review is done.",
        scope_type="work_context",
        scope_id="ctx-anchor-1",
        source_ref="fact:ctx-anchor-1:2",
        tags=["finance", "confirmation"],
    )
    sleep.mark_scope_dirty(
        scope_type="work_context",
        scope_id="ctx-anchor-1",
        industry_instance_id="industry-anchor-1",
        reason="bind-industry",
        source_ref="fact:ctx-anchor-1:1",
    )

    job = sleep.run_sleep(
        scope_type="work_context",
        scope_id="ctx-anchor-1",
        trigger_kind="manual",
    )

    assert job.status == "completed"
    overlay = sleep.get_active_work_context_overlay("ctx-anchor-1")
    assert overlay is not None
    continuity_anchors = list((overlay.metadata or {}).get("continuity_anchors") or [])
    assert continuity_anchors
    assert any(
        "finance review" in anchor.lower() or "customer confirmation" in anchor.lower()
        for anchor in continuity_anchors
    )


def test_memory_sleep_service_accepting_structure_proposal_materializes_new_active_overlay(tmp_path) -> None:
    _store, _knowledge, _strategy, _retain, sleep = _build_memory_sleep_services(tmp_path)

    first_overlay = sleep._repository.upsert_work_context_overlay(
        WorkContextMemoryOverlayRecord(
            overlay_id="overlay:ctx-proposal-1:v1",
            work_context_id="ctx-proposal-1",
            headline="Proposal overlay",
            summary="Original overlay ordering",
            focus_summary="second focus",
            active_constraints=["second focus constraint", "first focus constraint"],
            active_focuses=["second focus", "first focus"],
            active_entities=["entity-a"],
            active_relations=["relation-a"],
            version=1,
            status="active",
            metadata={"read_order": ["work_context_overlay", "graph", "evidence"]},
        )
    )
    proposal = sleep._repository.upsert_structure_proposal(
        MemoryStructureProposalRecord(
            proposal_id="structure:work_context:ctx-proposal-1:manual",
            scope_type="work_context",
            scope_id="ctx-proposal-1",
            work_context_id="ctx-proposal-1",
            proposal_kind="read-order-optimization",
            title="Promote first focus to the top",
            summary="Move first focus ahead of second focus in the main read surface.",
            recommended_action="Make first focus the primary read item.",
            candidate_overlay_id=first_overlay.overlay_id,
            risk_level="medium",
            status="pending",
        )
    )

    decided = sleep.decide_structure_proposal(
        proposal_id=proposal.proposal_id,
        decision="accepted",
        decided_by="tester",
    )

    assert decided.status == "accepted"
    active_overlay = sleep.get_active_work_context_overlay("ctx-proposal-1")
    assert active_overlay is not None
    assert active_overlay.overlay_id != first_overlay.overlay_id
    assert active_overlay.version == 2
    assert active_overlay.active_focuses[0] == "first focus"
    assert active_overlay.focus_summary == "first focus"
    assert active_overlay.metadata["last_applied_proposal_id"] == proposal.proposal_id


def test_memory_sleep_service_accepting_structure_proposal_materializes_new_active_industry_profile(
    tmp_path,
) -> None:
    _store, _knowledge, _strategy, _retain, sleep = _build_memory_sleep_services(tmp_path)

    first_profile = sleep._repository.upsert_industry_profile(
        IndustryMemoryProfileRecord(
            profile_id="industry-profile:industry-proposal-1:v1",
            industry_instance_id="industry-proposal-1",
            headline="Proposal profile",
            summary="Original industry ordering",
            strategic_direction="second direction",
            active_constraints=["second constraint", "first constraint"],
            active_focuses=["second direction", "first direction"],
            key_entities=["entity-a"],
            key_relations=["second relation", "first relation"],
            version=1,
            status="active",
            metadata={"read_order": ["industry_profile", "graph", "evidence"]},
        )
    )
    proposal = sleep._repository.upsert_structure_proposal(
        MemoryStructureProposalRecord(
            proposal_id="structure:industry:industry-proposal-1:manual",
            scope_type="industry",
            scope_id="industry-proposal-1",
            industry_instance_id="industry-proposal-1",
            proposal_kind="read-order-optimization",
            title="Promote first direction to the top",
            summary="Move first direction ahead of second direction in the main industry read surface.",
            recommended_action="Make first direction the primary industry focus.",
            candidate_profile_id=first_profile.profile_id,
            risk_level="medium",
            status="pending",
        )
    )

    decided = sleep.decide_structure_proposal(
        proposal_id=proposal.proposal_id,
        decision="accepted",
        decided_by="tester",
    )

    assert decided.status == "accepted"
    active_profile = sleep.get_active_industry_profile("industry-proposal-1")
    assert active_profile is not None
    assert active_profile.profile_id != first_profile.profile_id
    assert active_profile.version == 2
    assert active_profile.active_focuses[0] == "first direction"
    assert active_profile.strategic_direction == "first direction"
    assert active_profile.metadata["last_applied_proposal_id"] == proposal.proposal_id

    resolved_surface = sleep.resolve_scope_overlay(
        scope_type="industry",
        scope_id="industry-proposal-1",
    )
    resolved_profile = resolved_surface["industry_profile"]
    assert resolved_profile is not None
    assert resolved_profile.profile_id == active_profile.profile_id
