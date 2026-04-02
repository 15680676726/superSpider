# -*- coding: utf-8 -*-
from __future__ import annotations

import json

from copaw.state import SQLiteStateStore, StrategyMemoryRecord
from copaw.state.repositories import SqliteStrategyMemoryRepository
from copaw.state.strategy_memory_service import (
    StateStrategyMemoryService,
    resolve_strategy_payload,
)


def test_strategy_memory_service_persists_and_reads_active_strategy(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteStrategyMemoryRepository(store)
    service = StateStrategyMemoryService(repository=repository)

    strategy = service.upsert_strategy(
        StrategyMemoryRecord(
            strategy_id=service.canonical_strategy_id(
                scope_type="industry",
                scope_id="industry-1",
                owner_agent_id="copaw-agent-runner",
            ),
            scope_type="industry",
            scope_id="industry-1",
            owner_agent_id="copaw-agent-runner",
            owner_scope="industry-v1-demo",
            industry_instance_id="industry-1",
            title="白泽战略记忆",
            summary="聚焦行业团队的主线目标与分派原则。",
            mission="先统筹，再分派，再核证据。",
            north_star="让行业团队持续稳定产出。",
            priority_order=["先完成周报主线", "再推进执行闭环"],
            thinking_axes=["经营目标", "风险", "证据"],
            delegation_policy=["优先按角色边界分派"],
            direct_execution_policy=[
                "主脑不直接使用浏览器、桌面、文件编辑等叶子执行能力。",
                "没有合适执行位时，先补位、改派或请求确认，不让主脑兜底变成执行员。",
            ],
            execution_constraints=["高风险动作必须确认"],
            evidence_requirements=["所有外部动作留证据"],
            active_goal_ids=["goal-1"],
            active_goal_titles=["完成周报主线"],
            teammate_contracts=[
                {
                    "agent_id": "worker-1",
                    "role_id": "operator",
                    "role_name": "运营负责人",
                }
            ],
            source_ref="industry-instance:industry-1",
            metadata={"industry_label": "演示行业"},
        ),
    )

    active = service.get_active_strategy(
        scope_type="industry",
        scope_id="industry-1",
        owner_agent_id="copaw-agent-runner",
    )

    assert active is not None
    assert active.strategy_id == strategy.strategy_id
    assert active.north_star == "让行业团队持续稳定产出。"
    assert active.priority_order == ["先完成周报主线", "再推进执行闭环"]
    assert active.teammate_contracts[0]["agent_id"] == "worker-1"


def test_resolve_strategy_payload_uses_owner_fallback_chain(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteStrategyMemoryRepository(store)
    service = StateStrategyMemoryService(repository=repository)

    service.upsert_strategy(
        StrategyMemoryRecord(
            strategy_id="strategy:industry:industry-2:copaw-agent-runner",
            scope_type="industry",
            scope_id="industry-2",
            owner_agent_id="copaw-agent-runner",
            title="Industry fallback strategy",
            summary="Use execution-core fallback when the leaf agent has no dedicated strategy.",
            north_star="Stabilize the main operating loop",
            priority_order=["stability", "throughput"],
            status="active",
        ),
    )

    payload = resolve_strategy_payload(
        service=service,
        scope_type="industry",
        scope_id="industry-2",
        owner_agent_id="industry-leaf-agent",
        fallback_owner_agent_ids=["copaw-agent-runner", None],
    )

    assert payload is not None
    assert payload["strategy_id"] == "strategy:industry:industry-2:copaw-agent-runner"
    assert payload["north_star"] == "Stabilize the main operating loop"



def test_strategy_memory_service_compacts_large_payloads(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteStrategyMemoryRepository(store)
    service = StateStrategyMemoryService(repository=repository)

    strategy = service.upsert_strategy(
        StrategyMemoryRecord(
            strategy_id=service.canonical_strategy_id(
                scope_type="industry",
                scope_id="industry-compact",
                owner_agent_id="copaw-agent-runner",
            ),
            scope_type="industry",
            scope_id="industry-compact",
            owner_agent_id="copaw-agent-runner",
            title="Compact strategy",
            summary="Keep the execution memory lean and operator-usable.",
            north_star="Stabilize the loop without bloating the prompt.",
            priority_order=[f"PRIORITY-{index:02d}" for index in range(16)],
            thinking_axes=[f"AXIS-{index:02d}" for index in range(14)],
            delegation_policy=[f"DELEGATE-{index:02d}" for index in range(12)],
            direct_execution_policy=[f"DIRECT-{index:02d}" for index in range(12)],
            execution_constraints=[f"CONSTRAINT-{index:02d}" for index in range(16)],
            evidence_requirements=[f"EVIDENCE-{index:02d}" for index in range(16)],
            active_goal_titles=[f"GOAL-{index:02d}" for index in range(16)],
            teammate_contracts=[
                {
                    "agent_id": f"agent-{index}",
                    "role_id": f"role-{index}",
                    "role_name": f"Role {index}",
                    "mission": "x" * 320,
                    "capabilities": [f"cap-{slot}" for slot in range(20)],
                    "evidence_expectations": [f"proof-{slot}" for slot in range(10)],
                }
                for index in range(10)
            ],
            metadata={
                "operator_requirements": [f"REQ-{index:02d}" for index in range(20)],
                "recent_failures": [f"FAIL-{index:02d}" for index in range(10)],
                "effective_actions": [f"WIN-{index:02d}" for index in range(10)],
                "forbidden_repeats": [f"AVOID-{index:02d}" for index in range(10)],
                "chat_writeback_history": [
                    {
                        "fingerprint": f"fp-{index}",
                        "instruction": "x" * 320,
                        "classification": [f"tag-{slot}" for slot in range(8)],
                        "updated_at": f"2026-03-17T00:{index:02d}:00Z",
                    }
                    for index in range(15)
                ],
            },
        ),
    )

    active = service.get_active_strategy(
        scope_type="industry",
        scope_id="industry-compact",
        owner_agent_id="copaw-agent-runner",
    )
    payload = resolve_strategy_payload(
        service=service,
        scope_type="industry",
        scope_id="industry-compact",
        owner_agent_id="copaw-agent-runner",
    )

    assert active is not None
    assert payload is not None
    assert strategy.strategy_id == active.strategy_id
    assert len(active.priority_order) == 12
    assert len(active.thinking_axes) == 10
    assert len(active.delegation_policy) == 8
    assert len(active.direct_execution_policy) == 8
    assert len(active.execution_constraints) == 12
    assert len(active.evidence_requirements) == 12
    assert len(active.active_goal_titles) == 12
    assert len(active.teammate_contracts) == 8
    assert len(active.teammate_contracts[0]["capabilities"]) == 12
    assert len(active.teammate_contracts[0]["evidence_expectations"]) == 6
    assert len(active.metadata["operator_requirements"]) == 12
    assert len(active.metadata["recent_failures"]) == 6
    assert len(active.metadata["effective_actions"]) == 6
    assert len(active.metadata["forbidden_repeats"]) == 6
    assert len(active.metadata["chat_writeback_history"]) == 10
    assert active.metadata["chat_writeback_history"][0]["fingerprint"] == "fp-5"
    assert active.metadata["chat_writeback_history"][-1]["fingerprint"] == "fp-14"
    assert active.metadata["chat_writeback_history"][-1]["instruction"].endswith("...")
    assert len(active.metadata["chat_writeback_history"][-1]["classification"]) == 6
    assert len(payload["priority_order"]) == 12
    assert len(payload["metadata"]["chat_writeback_history"]) == 10


def test_strategy_memory_service_persists_typed_uncertainty_and_lane_budget_truth(tmp_path) -> None:
    store = SQLiteStateStore(tmp_path / "state.db")
    repository = SqliteStrategyMemoryRepository(store)
    service = StateStrategyMemoryService(repository=repository)

    strategy = service.upsert_strategy(
        StrategyMemoryRecord(
            strategy_id=service.canonical_strategy_id(
                scope_type="industry",
                scope_id="industry-budgeted",
                owner_agent_id="copaw-agent-runner",
            ),
            scope_type="industry",
            scope_id="industry-budgeted",
            owner_agent_id="copaw-agent-runner",
            title="Budgeted strategy",
            summary="Keep uncertainty and lane budget truth on the formal strategy record.",
            north_star="Fund the right lanes without losing review triggers.",
            strategic_uncertainties=[
                {
                    "uncertainty_id": "uncertainty-1",
                    "statement": "Retention signal is still noisy.",
                    "scope": "lane",
                    "impact_level": "high",
                    "current_confidence": 0.45,
                    "evidence_for_refs": ["evidence-for-1"],
                    "evidence_against_refs": ["evidence-against-1"],
                    "review_by_cycle": "cycle-2",
                    "escalate_when": ["confidence drop", "target miss"],
                }
            ],
            lane_budgets=[
                {
                    "lane_id": "lane-retention",
                    "budget_window": "next-3-cycles",
                    "target_share": 0.6,
                    "min_share": 0.4,
                    "max_share": 0.75,
                    "review_pressure": "protect-core-signal",
                    "defer_reason": "wait for cleaner churn baseline",
                    "force_include_reason": "current cycle is retention-critical",
                }
            ],
        ),
    )

    active = service.get_active_strategy(
        scope_type="industry",
        scope_id="industry-budgeted",
        owner_agent_id="copaw-agent-runner",
    )
    payload = resolve_strategy_payload(
        service=service,
        scope_type="industry",
        scope_id="industry-budgeted",
        owner_agent_id="copaw-agent-runner",
    )

    with store.connection() as conn:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(strategy_memories)").fetchall()
        }
        raw = conn.execute(
            """
            SELECT strategic_uncertainties_json, lane_budgets_json
            FROM strategy_memories
            WHERE strategy_id = ?
            """,
            (strategy.strategy_id,),
        ).fetchone()

    assert active is not None
    assert payload is not None
    assert "strategic_uncertainties_json" in columns
    assert "lane_budgets_json" in columns
    assert active.strategic_uncertainties[0].uncertainty_id == "uncertainty-1"
    assert active.strategic_uncertainties[0].escalate_when == [
        "confidence drop",
        "target miss",
    ]
    assert active.lane_budgets[0].lane_id == "lane-retention"
    assert payload["strategic_uncertainties"][0]["uncertainty_id"] == "uncertainty-1"
    assert payload["lane_budgets"][0]["lane_id"] == "lane-retention"
    assert raw is not None
    assert json.loads(raw["strategic_uncertainties_json"])[0]["uncertainty_id"] == "uncertainty-1"
    assert json.loads(raw["lane_budgets_json"])[0]["lane_id"] == "lane-retention"
