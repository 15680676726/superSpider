# -*- coding: utf-8 -*-
from __future__ import annotations

import json

from fastapi import HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from typing import Literal

from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

from ...kernel.query_execution_shared import (
    _extract_leading_chat_action_hints,
    _normalize_requested_actions,
)
from ...predictions import PredictionCapabilityOptimizationOverview
from ..runtime_center import (
    RuntimeCenterQueryService,
    RuntimeOverviewResponse,
    apply_runtime_center_surface_headers,
)
from ..runtime_chat_media import enrich_agent_request_with_media
from .runtime_center_shared import (
    GovernanceDecisionBatchRequest,
    GovernanceEmergencyStopRequest,
    GovernancePatchBatchRequest,
    GovernanceResumeRequest,
    KnowledgeChunkUpsertRequest,
    KnowledgeImportRequest,
    KnowledgeMemoryUpsertRequest,
    MemoryRebuildRequest,
    MemoryReflectRequest,
    _call_runtime_query_method,
    _encode_sse_event,
    _get_derived_memory_index_service,
    _get_governance_service,
    _get_industry_service,
    _get_knowledge_service,
    _get_memory_recall_service,
    _get_memory_reflection_service,
    _get_prediction_service,
    _get_reporting_service,
    _get_runtime_event_bus,
    _get_state_query_service,
    _get_strategy_memory_service,
    _get_turn_executor,
    _serialize_knowledge_chunk,
    router,
)

__all__ = [
    "AgentRequest",
    "GovernanceDecisionBatchRequest",
    "GovernanceEmergencyStopRequest",
    "GovernancePatchBatchRequest",
    "GovernanceResumeRequest",
    "HTTPException",
    "KnowledgeChunkUpsertRequest",
    "KnowledgeImportRequest",
    "KnowledgeMemoryUpsertRequest",
    "Literal",
    "MemoryRebuildRequest",
    "MemoryReflectRequest",
    "PredictionCapabilityOptimizationOverview",
    "Request",
    "Response",
    "RuntimeCenterQueryService",
    "RuntimeOverviewResponse",
    "StreamingResponse",
    "_call_runtime_query_method",
    "_encode_sse_event",
    "_extract_leading_chat_action_hints",
    "_get_derived_memory_index_service",
    "_get_governance_service",
    "_get_industry_service",
    "_get_knowledge_service",
    "_get_memory_recall_service",
    "_get_memory_reflection_service",
    "_get_prediction_service",
    "_get_reporting_service",
    "_get_runtime_event_bus",
    "_get_state_query_service",
    "_get_strategy_memory_service",
    "_get_turn_executor",
    "_normalize_requested_actions",
    "_serialize_knowledge_chunk",
    "apply_runtime_center_surface_headers",
    "enrich_agent_request_with_media",
    "json",
    "router",
]
