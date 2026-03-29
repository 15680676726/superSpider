# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

from copaw.app.runtime_chat_media import enrich_agent_request_with_media
from copaw.evidence import EvidenceLedger
from copaw.memory import (
    DerivedMemoryIndexService,
    MemoryRecallService,
    MemoryReflectionService,
    MemoryRetainService,
)
from copaw.media import MediaAnalysisRequest, MediaService, MediaSourceSpec
from copaw.state import (
    IndustryInstanceRecord,
    OperatingLaneRecord,
    SQLiteStateStore,
)
from copaw.state.knowledge_service import StateKnowledgeService
from copaw.state.main_brain_service import BacklogService, OperatingLaneService
from copaw.state.repositories import (
    SqliteBacklogItemRepository,
    SqliteIndustryInstanceRepository,
    SqliteKnowledgeChunkRepository,
    SqliteMediaAnalysisRepository,
    SqliteMemoryEntityViewRepository,
    SqliteMemoryFactIndexRepository,
    SqliteMemoryOpinionViewRepository,
    SqliteMemoryReflectionRunRepository,
    SqliteOperatingLaneRepository,
    SqliteStrategyMemoryRepository,
)
from copaw.state.strategy_memory_service import StateStrategyMemoryService


def _build_media_runtime(tmp_path: Path) -> SimpleNamespace:
    store = SQLiteStateStore(tmp_path / "state.db")
    industry_repository = SqliteIndustryInstanceRepository(store)
    media_repository = SqliteMediaAnalysisRepository(store)
    lane_repository = SqliteOperatingLaneRepository(store)
    backlog_repository = SqliteBacklogItemRepository(store)
    knowledge_repository = SqliteKnowledgeChunkRepository(store)
    fact_repository = SqliteMemoryFactIndexRepository(store)
    entity_repository = SqliteMemoryEntityViewRepository(store)
    opinion_repository = SqliteMemoryOpinionViewRepository(store)
    reflection_repository = SqliteMemoryReflectionRunRepository(store)
    strategy_repository = SqliteStrategyMemoryRepository(store)
    derived_index_service = DerivedMemoryIndexService(
        fact_index_repository=fact_repository,
        entity_view_repository=entity_repository,
        opinion_view_repository=opinion_repository,
        reflection_run_repository=reflection_repository,
        knowledge_repository=knowledge_repository,
        strategy_repository=strategy_repository,
    )
    reflection_service = MemoryReflectionService(
        derived_index_service=derived_index_service,
        entity_view_repository=entity_repository,
        opinion_view_repository=opinion_repository,
        reflection_run_repository=reflection_repository,
    )
    knowledge_service = StateKnowledgeService(
        repository=knowledge_repository,
        derived_index_service=derived_index_service,
        reflection_service=reflection_service,
    )
    strategy_memory_service = StateStrategyMemoryService(
        repository=strategy_repository,
    )
    memory_retain_service = MemoryRetainService(
        knowledge_service=knowledge_service,
        derived_index_service=derived_index_service,
        reflection_service=reflection_service,
    )
    memory_recall_service = MemoryRecallService(
        derived_index_service=derived_index_service,
    )
    backlog_service = BacklogService(repository=backlog_repository)
    lane_service = OperatingLaneService(repository=lane_repository)
    media_service = MediaService(
        repository=media_repository,
        evidence_ledger=EvidenceLedger(),
        knowledge_service=knowledge_service,
        strategy_memory_service=strategy_memory_service,
        backlog_service=backlog_service,
        operating_lane_service=lane_service,
        industry_instance_repository=industry_repository,
        memory_retain_service=memory_retain_service,
    )

    industry_repository.upsert_instance(
        IndustryInstanceRecord(
            instance_id="industry-v1-media",
            label="Media Ops Cell",
            summary="Industry control thread with media writeback.",
            owner_scope="industry-v1-media",
            status="active",
            execution_core_identity_payload={"agent_id": "copaw-agent-runner"},
            goal_ids=[],
            agent_ids=["copaw-agent-runner"],
            schedule_ids=[],
        ),
    )
    lane_repository.upsert_lane(
        OperatingLaneRecord(
            id="lane:media-ops",
            industry_instance_id="industry-v1-media",
            lane_key="media-ops",
            title="Media Ops",
            summary="Primary media operating lane.",
            owner_agent_id="copaw-agent-runner",
            owner_role_id="execution-core",
            priority=5,
            source_ref="test:media-ops",
        ),
    )

    return SimpleNamespace(
        media_service=media_service,
        media_repository=media_repository,
        backlog_repository=backlog_repository,
        knowledge_service=knowledge_service,
        memory_recall_service=memory_recall_service,
        strategy_memory_service=strategy_memory_service,
    )


def _build_industry_request(
    *,
    media_inputs: list[dict[str, object]] | None = None,
    media_analysis_ids: list[str] | None = None,
    work_context_id: str = "ctx-media-ops",
) -> AgentRequest:
    return AgentRequest.model_validate(
        {
            "id": "req-media-runtime",
            "session_id": "industry-chat:industry-v1-media:execution-core",
            "user_id": "ops-user",
            "channel": "console",
            "industry_instance_id": "industry-v1-media",
            "thread_id": "industry-chat:industry-v1-media:execution-core",
            "control_thread_id": "industry-chat:industry-v1-media:execution-core",
            "session_kind": "industry-control-thread",
            "work_context_id": work_context_id,
            "requested_actions": ["writeback_backlog"],
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [
                        {
                            "type": "text",
                            "text": "结合附件继续推进主脑长期计划，并把关键结论写回正式状态。",
                        }
                    ],
                }
            ],
            "media_inputs": list(media_inputs or []),
            "media_analysis_ids": list(media_analysis_ids or []),
        }
    )


def test_enrich_agent_request_with_media_writes_back_industry_chat_attachments(
    tmp_path: Path,
) -> None:
    runtime = _build_media_runtime(tmp_path)
    attachment_path = tmp_path / "brief.md"
    attachment_path.write_text(
        "# 电商执行资料\n先核对商品价格，再确认库存和物流模板，最后回写风险点。",
        encoding="utf-8",
    )
    request_payload = _build_industry_request(
        media_inputs=[
            {
                "source_kind": "upload",
                "filename": attachment_path.name,
                "storage_uri": str(attachment_path),
                "entry_point": "chat",
                "purpose": "chat-answer",
            }
        ],
    )

    updated_request, analysis_ids, consumed_inputs = asyncio.run(
        enrich_agent_request_with_media(
            request_payload,
            app_state=runtime,
        )
    )

    assert consumed_inputs is True
    assert len(analysis_ids) == 1

    request_data = updated_request.model_dump(mode="python")
    assert request_data["media_inputs"] == []
    assert request_data["media_analysis_ids"] == analysis_ids

    analysis = runtime.media_repository.get_analysis(analysis_ids[0])
    assert analysis is not None
    assert analysis.industry_instance_id == "industry-v1-media"
    assert analysis.work_context_id == "ctx-media-ops"
    assert analysis.backlog_writeback_status == "written"
    assert analysis.strategy_writeback_status == "written"

    backlog_items = runtime.backlog_repository.list_items(
        industry_instance_id="industry-v1-media",
        limit=None,
    )
    assert len(backlog_items) == 1
    assert backlog_items[0].source_kind == "media-analysis"
    assert backlog_items[0].metadata["analysis_id"] == analysis.analysis_id

    strategy = runtime.strategy_memory_service.get_active_strategy(
        scope_type="industry",
        scope_id="industry-v1-media",
        owner_agent_id=None,
    )
    assert strategy is not None
    assert analysis.analysis_id in (strategy.metadata or {}).get("media_analysis_ids", [])

    retained_chunks = runtime.knowledge_service.list_chunks(
        document_id="memory:work_context:ctx-media-ops",
        limit=None,
    )
    assert retained_chunks
    assert retained_chunks[0].source_ref == f"media-analysis:{analysis.analysis_id}"

    recall = runtime.memory_recall_service.recall(
        query="关键结论",
        role="execution-core",
        work_context_id="ctx-media-ops",
        include_related_scopes=False,
    )
    assert recall.hits
    assert recall.hits[0].scope_type == "work_context"
    assert recall.hits[0].scope_id == "ctx-media-ops"
    assert recall.hits[0].source_ref == f"media-analysis:{analysis.analysis_id}"


def test_enrich_agent_request_with_media_adopts_existing_analysis_into_industry_state(
    tmp_path: Path,
) -> None:
    runtime = _build_media_runtime(tmp_path)
    attachment_path = tmp_path / "existing-brief.md"
    attachment_path.write_text(
        "# 运营简报\n更新活动节奏，补齐客服回访，并跟进库存预警。",
        encoding="utf-8",
    )
    initial = asyncio.run(
        runtime.media_service.analyze(
            MediaAnalysisRequest(
                sources=[
                    MediaSourceSpec(
                        source_kind="upload",
                        filename=attachment_path.name,
                        storage_uri=str(attachment_path),
                        entry_point="chat",
                        purpose="chat-answer",
                    )
                ],
                thread_id="chat:generic-thread",
                entry_point="chat",
                purpose="chat-answer",
                writeback=False,
            )
        )
    )
    assert len(initial.analyses) == 1
    analysis_id = initial.analyses[0].analysis_id

    updated_request, analysis_ids, consumed_inputs = asyncio.run(
        enrich_agent_request_with_media(
            _build_industry_request(media_analysis_ids=[analysis_id]),
            app_state=runtime,
        )
    )

    assert consumed_inputs is False
    assert analysis_ids == [analysis_id]

    analysis = runtime.media_repository.get_analysis(analysis_id)
    assert analysis is not None
    assert analysis.industry_instance_id == "industry-v1-media"
    assert analysis.work_context_id == "ctx-media-ops"
    assert analysis.backlog_writeback_status == "written"
    assert analysis.strategy_writeback_status == "written"

    backlog_items = runtime.backlog_repository.list_items(
        industry_instance_id="industry-v1-media",
        limit=None,
    )
    assert len(backlog_items) == 1
    assert backlog_items[0].metadata["analysis_id"] == analysis_id

    request_data = updated_request.model_dump(mode="python")
    assert request_data["media_analysis_ids"] == [analysis_id]

    retained_chunks = runtime.knowledge_service.list_chunks(
        document_id="memory:work_context:ctx-media-ops",
        limit=None,
    )
    assert retained_chunks
    assert retained_chunks[0].source_ref == f"media-analysis:{analysis_id}"

    recall = runtime.memory_recall_service.recall(
        query="库存预警",
        role="execution-core",
        work_context_id="ctx-media-ops",
        include_related_scopes=False,
    )
    assert recall.hits
    assert recall.hits[0].scope_type == "work_context"
    assert recall.hits[0].scope_id == "ctx-media-ops"
    assert recall.hits[0].source_ref == f"media-analysis:{analysis_id}"
