# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.state import (
    MemoryAliasMapRecord,
    MemoryConflictProposalRecord,
    MemoryMergeResultRecord,
    MemoryScopeDigestRecord,
    MemorySleepJobRecord,
    MemorySleepScopeStateRecord,
    MemorySoftRuleRecord,
    SQLiteStateStore,
)
from copaw.state.repositories import SqliteMemorySleepRepository


def test_memory_sleep_repository_persists_scope_state_and_jobs(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteMemorySleepRepository(store)

    scope_state = repository.upsert_scope_state(
        MemorySleepScopeStateRecord(
            scope_type="work_context",
            scope_id="ctx-sleep-1",
            is_dirty=True,
            dirty_reasons=["knowledge-upsert"],
            dirty_source_refs=["knowledge:ctx-sleep-1:1"],
            dirty_count=1,
        )
    )
    queued_job = repository.upsert_sleep_job(
        MemorySleepJobRecord(
            job_id="sleep-job-1",
            scope_type="work_context",
            scope_id="ctx-sleep-1",
            trigger_kind="manual",
            status="queued",
            input_refs=["knowledge:ctx-sleep-1:1"],
        )
    )
    completed_job = repository.upsert_sleep_job(
        queued_job.model_copy(
            update={
                "status": "completed",
                "output_refs": ["digest:ctx-sleep-1:v1"],
            }
        )
    )

    loaded_scope_state = repository.get_scope_state(
        scope_type="work_context",
        scope_id="ctx-sleep-1",
    )
    assert loaded_scope_state is not None
    assert loaded_scope_state.is_dirty is True
    assert loaded_scope_state.dirty_reasons == ["knowledge-upsert"]
    assert loaded_scope_state.dirty_source_refs == ["knowledge:ctx-sleep-1:1"]

    dirty_scopes = repository.list_scope_states(dirty_only=True)
    assert [item.scope_id for item in dirty_scopes] == ["ctx-sleep-1"]

    loaded_job = repository.get_sleep_job("sleep-job-1")
    assert loaded_job is not None
    assert loaded_job.status == "completed"
    assert loaded_job.output_refs == ["digest:ctx-sleep-1:v1"]

    jobs = repository.list_sleep_jobs(
        scope_type="work_context",
        scope_id="ctx-sleep-1",
    )
    assert [item.job_id for item in jobs] == ["sleep-job-1"]


def test_memory_sleep_repository_persists_sleep_artifacts_by_scope(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteMemorySleepRepository(store)

    superseded_digest = repository.upsert_digest(
        MemoryScopeDigestRecord(
            digest_id="digest:industry-1:v1",
            scope_type="industry",
            scope_id="industry-1",
            headline="旧摘要",
            summary="旧阶段摘要",
            current_constraints=["先看旧规则"],
            current_focus=["旧焦点"],
            top_entities=["外呼"],
            top_relations=["外呼需要证据复核"],
            evidence_refs=["evidence:1"],
            source_job_id="sleep-job-1",
            version=1,
            status="superseded",
        )
    )
    active_digest = repository.upsert_digest(
        MemoryScopeDigestRecord(
            digest_id="digest:industry-1:v2",
            scope_type="industry",
            scope_id="industry-1",
            headline="当前摘要",
            summary="当前阶段重点是先完成证据复核。",
            current_constraints=["必须先完成证据复核"],
            current_focus=["收口外呼审批"],
            top_entities=["外呼审批", "财务证据复核"],
            top_relations=["外呼审批需要财务证据复核"],
            evidence_refs=["evidence:2"],
            source_job_id="sleep-job-2",
            version=2,
            status="active",
        )
    )
    repository.upsert_alias_map(
        MemoryAliasMapRecord(
            alias_id="alias:industry-1:finance-review",
            scope_type="industry",
            scope_id="industry-1",
            canonical_term="财务证据复核",
            aliases=["财务复核", "finance review"],
            confidence=0.9,
            evidence_refs=["evidence:2"],
            source_job_id="sleep-job-2",
            status="active",
        )
    )
    repository.upsert_merge_result(
        MemoryMergeResultRecord(
            merge_id="merge:industry-1:approval-gate",
            scope_type="industry",
            scope_id="industry-1",
            merged_title="外呼审批门",
            merged_summary="把外呼审批和证据复核收成同一个主题。",
            merged_source_refs=["knowledge:1", "knowledge:2"],
            evidence_refs=["evidence:2"],
            source_job_id="sleep-job-2",
            status="active",
        )
    )
    repository.upsert_soft_rule(
        MemorySoftRuleRecord(
            rule_id="rule:industry-1:approval-after-review",
            scope_type="industry",
            scope_id="industry-1",
            rule_text="外呼审批必须先完成财务证据复核。",
            rule_kind="requirement",
            evidence_refs=["evidence:2"],
            hit_count=3,
            day_span=2,
            conflict_count=0,
            risk_level="low",
            state="active",
            source_job_id="sleep-job-2",
        )
    )
    repository.upsert_conflict_proposal(
        MemoryConflictProposalRecord(
            proposal_id="proposal:industry-1:conflict-1",
            scope_type="industry",
            scope_id="industry-1",
            proposal_kind="conflict",
            title="审批顺序冲突",
            summary="一组记录要求先发消息，另一组要求先做复核。",
            conflicting_refs=["knowledge:old"],
            supporting_refs=["knowledge:new"],
            recommended_action="保留旧事实，等待更多证据。",
            risk_level="high",
            status="pending",
            source_job_id="sleep-job-2",
        )
    )

    assert superseded_digest.status == "superseded"
    assert repository.get_active_digest("industry", "industry-1") == active_digest

    digests = repository.list_digests(scope_type="industry", scope_id="industry-1")
    assert [item.digest_id for item in digests] == ["digest:industry-1:v2", "digest:industry-1:v1"]

    alias_maps = repository.list_alias_maps(scope_type="industry", scope_id="industry-1")
    assert alias_maps[0].canonical_term == "财务证据复核"
    assert "finance review" in alias_maps[0].aliases

    merge_results = repository.list_merge_results(scope_type="industry", scope_id="industry-1")
    assert merge_results[0].merged_title == "外呼审批门"

    soft_rules = repository.list_soft_rules(scope_type="industry", scope_id="industry-1", state="active")
    assert soft_rules[0].rule_text == "外呼审批必须先完成财务证据复核。"
    assert soft_rules[0].hit_count == 3

    proposals = repository.list_conflict_proposals(
        scope_type="industry",
        scope_id="industry-1",
        status="pending",
    )
    assert proposals[0].title == "审批顺序冲突"
