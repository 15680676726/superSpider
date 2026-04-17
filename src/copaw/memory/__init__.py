# -*- coding: utf-8 -*-
from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS: dict[str, tuple[str, str]] = {
    "ActivationInput": (".activation_models", "ActivationInput"),
    "ActivationResult": (".activation_models", "ActivationResult"),
    "KnowledgeNeuron": (".activation_models", "KnowledgeNeuron"),
    "KnowledgeGraphService": (".knowledge_graph_service", "KnowledgeGraphService"),
    "MemoryActivationService": (".activation_service", "MemoryActivationService"),
    "DerivedMemoryIndexService": (".derived_index_service", "DerivedMemoryIndexService"),
    "build_scope_candidates": (".derived_index_service", "build_scope_candidates"),
    "normalize_memory_scope_type": (".derived_index_service", "normalize_memory_scope_type"),
    "normalize_scope_id": (".derived_index_service", "normalize_scope_id"),
    "parse_memory_document_id": (".derived_index_service", "parse_memory_document_id"),
    "selector_matches_scope": (".derived_index_service", "selector_matches_scope"),
    "source_route_for_entry": (".derived_index_service", "source_route_for_entry"),
    "MemoryBackendDescriptor": (".models", "MemoryBackendDescriptor"),
    "MemoryRecallHit": (".models", "MemoryRecallHit"),
    "MemoryRecallResponse": (".models", "MemoryRecallResponse"),
    "MemoryRebuildSummary": (".models", "MemoryRebuildSummary"),
    "MemoryReflectionSummary": (".models", "MemoryReflectionSummary"),
    "MemoryScopeSelector": (".models", "MemoryScopeSelector"),
    "ContinuityDetailService": (".continuity_detail_service", "ContinuityDetailService"),
    "MemoryEntryPartition": (".precedence", "MemoryEntryPartition"),
    "MemoryPrecedenceService": (".precedence", "MemoryPrecedenceService"),
    "MemoryProfile": (".profile_service", "MemoryProfile"),
    "MemoryProfileService": (".profile_service", "MemoryProfileService"),
    "SharedMemoryViews": (".profile_service", "SharedMemoryViews"),
    "MemoryRecallService": (".recall_service", "MemoryRecallService"),
    "MemoryReflectionService": (".reflection_service", "MemoryReflectionService"),
    "MemoryRetainService": (".retain_service", "MemoryRetainService"),
    "build_memory_sleep_model_runner": (".sleep_inference_service", "build_memory_sleep_model_runner"),
    "MemorySleepInferenceService": (".sleep_inference_service", "MemorySleepInferenceService"),
    "MemorySleepService": (".sleep_service", "MemorySleepService"),
    "MemorySurfaceService": (".surface_service", "MemorySurfaceService"),
    "StructureEnhancementService": (".structure_enhancement_service", "StructureEnhancementService"),
    "StructureProposalExecutor": (".structure_proposal_executor", "StructureProposalExecutor"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
