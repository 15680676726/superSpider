# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib
from collections.abc import Collection
from uuid import uuid4

from ..capabilities.tool_execution_contracts import get_tool_execution_contract
from ..constant import MEMORY_COMPACT_KEEP_RECENT
from ..industry.models import (
    IndustrySeatCapabilityLayers,
    resolve_runtime_effective_capability_ids,
)
from ..memory.conversation_compaction_service import ConversationCompactionService
from ..memory.knowledge_writeback_service import KnowledgeWritebackService
from .main_brain_intake import (
    build_industry_chat_action_kwargs,
    read_attached_main_brain_intake_contract,
    resolve_execution_core_industry_instance_id,
)
from .query_execution_context_runtime import _QueryExecutionContextRuntimeMixin
from .main_brain_result_committer import (
    build_accepted_persistence,
    normalize_durable_commit_result,
    set_request_runtime_value,
    update_request_runtime_context,
)
from .query_execution_resident_runtime import _QueryExecutionResidentRuntimeMixin
from .query_execution_shared import *  # noqa: F401,F403
from .query_execution_usage_runtime import _QueryExecutionUsageRuntimeMixin
from .runtime_outcome import (
    build_execution_diagnostics,
    build_execution_knowledge_writeback,
    classify_runtime_outcome,
)


def CoPawAgent(*args, **kwargs):
    module = importlib.import_module("copaw.kernel.query_execution")
    return module.CoPawAgent(*args, **kwargs)


def load_config(*args, **kwargs):
    module = importlib.import_module("copaw.kernel.query_execution")
    return module.load_config(*args, **kwargs)


def stream_printing_messages(*args, **kwargs):
    module = importlib.import_module("copaw.kernel.query_execution")
    return module.stream_printing_messages(*args, **kwargs)


_EXECUTION_CORE_ALLOWED_LOCAL_TOOL_CAPABILITY_IDS = {
    "tool:edit_file",
    "tool:execute_shell_command",
    "tool:get_current_time",
    "tool:read_file",
    "tool:write_file",
}

_RUNTIME_ENTROPY_FAILURE_SOURCE = "sidecar-memory"
_RUNTIME_ENTROPY_DEGRADED_SUMMARY = (
    "The private compaction memory sidecar is unavailable; "
    "runtime continues on canonical state only."
)
_RUNTIME_ENTROPY_DEGRADED_NEXT_STEP = (
    "Restore the compaction sidecar if long-horizon scratch recall is required."
)
_RUNTIME_ENTROPY_AVAILABLE_SUMMARY = "The private compaction memory sidecar is attached."
_DONOR_TRIAL_CARRY_FORWARD_FAILURE_SOURCE = "donor-trial-carry-forward"
_DONOR_TRIAL_CARRY_FORWARD_INACTIVE_SUMMARY = (
    "No donor/trial metadata carry-forward is active."
)
_DONOR_TRIAL_CARRY_FORWARD_BOUNDED_SUMMARY = (
    "Donor/trial metadata carry-forward is bounded by the runtime contract."
)
_DONOR_TRIAL_CARRY_FORWARD_DEGRADED_SUMMARY = (
    "Donor/trial metadata overflow compacted into runtime evidence."
)
_DONOR_TRIAL_CARRY_FORWARD_DEGRADED_NEXT_STEP = (
    "Inspect runtime evidence/artifacts or narrow donor/trial scope before continuing."
)
_QUERY_TRIAL_ATTRIBUTION_SCALAR_FIELDS = (
    "candidate_id",
    "skill_candidate_id",
    "skill_trial_id",
    "skill_lifecycle_stage",
    "selected_scope",
    "selected_seat_ref",
    "donor_id",
    "package_id",
    "source_profile_id",
    "candidate_source_kind",
    "resolution_kind",
    "verified_stage",
    "provider_resolution_status",
    "compatibility_status",
    "protocol_surface_kind",
    "transport_kind",
    "compiled_adapter_id",
    "selected_adapter_action_id",
    "probe_outcome",
    "probe_error_type",
)
_QUERY_TRIAL_ATTRIBUTION_LIST_FIELDS = (
    "replacement_target_ids",
    "rollback_target_ids",
    "capability_ids",
    "compiled_action_ids",
    "adapter_blockers",
    "probe_evidence_refs",
)
_QUERY_TRIAL_ATTRIBUTION_FIELD_SET = frozenset(
    _QUERY_TRIAL_ATTRIBUTION_SCALAR_FIELDS + _QUERY_TRIAL_ATTRIBUTION_LIST_FIELDS,
)
_QUERY_TRIAL_ATTRIBUTION_MAX_LIST_ITEMS = 3
_DONOR_TRIAL_VISIBILITY_MAX_ITEMS = 6
_COMPACTION_VISIBILITY_KEYS = (
    "compaction_state",
    "donor_trial_carry_forward",
    "tool_result_budget",
    "tool_use_summary",
)


def _build_tool_result_budget_contract(
    *,
    enabled: bool,
    keep_recent_tool_results: int,
) -> dict[str, Any]:
    return {
        "enabled": bool(enabled),
        "keep_recent_messages": MEMORY_COMPACT_KEEP_RECENT,
        "keep_recent_tool_results": int(keep_recent_tool_results or 0),
        "state_channel": "query_runtime_state",
        "summary_surface": "runtime-center",
        "spill_surface": "runtime-center",
        "replay_surface": "runtime-conversation",
    }


def _bounded_string_list(
    value: Any,
    *,
    max_items: int,
    allowed_values: Collection[str] | None = None,
) -> list[str]:
    resolved: list[str] = []
    allowed = set(allowed_values or ())
    for item in _string_list(value):
        if allowed and item not in allowed:
            continue
        if item in resolved:
            continue
        resolved.append(item)
        if len(resolved) >= max_items:
            break
    return resolved


def _build_donor_trial_budget_contract() -> dict[str, Any]:
    return {
        "accepted_scalar_fields": list(_QUERY_TRIAL_ATTRIBUTION_SCALAR_FIELDS),
        "accepted_list_fields": list(_QUERY_TRIAL_ATTRIBUTION_LIST_FIELDS),
        "max_list_items": _QUERY_TRIAL_ATTRIBUTION_MAX_LIST_ITEMS,
        "acceptance": "bounded-runtime-metadata",
        "state_channel": "query_runtime_state",
        "summary_surface": "runtime-center",
        "spill_surface": "runtime-evidence",
    }


def build_donor_trial_carry_forward_projection(
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    raw_payload = _mapping_value(payload)
    retained_metadata_keys = _bounded_string_list(
        raw_payload.get("retained_metadata_keys"),
        max_items=_DONOR_TRIAL_VISIBILITY_MAX_ITEMS,
        allowed_values=_QUERY_TRIAL_ATTRIBUTION_FIELD_SET,
    )
    truncated_metadata_keys = _bounded_string_list(
        raw_payload.get("truncated_metadata_keys"),
        max_items=_DONOR_TRIAL_VISIBILITY_MAX_ITEMS,
        allowed_values=_QUERY_TRIAL_ATTRIBUTION_FIELD_SET,
    )
    artifact_refs = _bounded_string_list(
        raw_payload.get("artifact_refs"),
        max_items=_DONOR_TRIAL_VISIBILITY_MAX_ITEMS,
    )
    status = _first_non_empty(raw_payload.get("status"))
    if status is None:
        status = (
            "bounded"
            if retained_metadata_keys or truncated_metadata_keys or artifact_refs
            else "inactive"
        )
    summary = _first_non_empty(
        raw_payload.get("summary"),
        (
            _DONOR_TRIAL_CARRY_FORWARD_DEGRADED_SUMMARY
            if status == "degraded"
            else _DONOR_TRIAL_CARRY_FORWARD_BOUNDED_SUMMARY
            if status == "bounded"
            else _DONOR_TRIAL_CARRY_FORWARD_INACTIVE_SUMMARY
        ),
    )
    return {
        "status": status,
        "summary": summary,
        "retained_metadata_keys": retained_metadata_keys,
        "truncated_metadata_keys": truncated_metadata_keys,
        "artifact_refs": artifact_refs,
    }


def _build_donor_trial_carry_forward_degradation(
    projection: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    resolved = build_donor_trial_carry_forward_projection(projection)
    if resolved["status"] != "degraded":
        return None
    return {
        **build_execution_diagnostics(
            failure_source=_DONOR_TRIAL_CARRY_FORWARD_FAILURE_SOURCE,
            remediation_summary=_first_non_empty(
                resolved.get("summary"),
                _DONOR_TRIAL_CARRY_FORWARD_DEGRADED_SUMMARY,
            ),
        ),
        "blocked_next_step": _DONOR_TRIAL_CARRY_FORWARD_DEGRADED_NEXT_STEP,
        "retained_metadata_keys": list(resolved["retained_metadata_keys"]),
        "truncated_metadata_keys": list(resolved["truncated_metadata_keys"]),
        "artifact_refs": list(resolved["artifact_refs"]),
    }


def _runtime_entropy_degraded_components(
    degradation: Mapping[str, Any] | None,
) -> list[str]:
    resolved: list[str] = []
    for key, value in dict(degradation or {}).items():
        if _mapping_value(value):
            resolved.append(str(key))
    return resolved


def _runtime_entropy_failure_source(
    degradation: Mapping[str, Any] | None,
) -> str:
    for key in ("sidecar_memory", "donor_trial_carry_forward"):
        failure_source = _first_non_empty(
            _mapping_value(dict(degradation or {}).get(key)).get("failure_source"),
        )
        if failure_source is not None:
            return failure_source
    return ""

_QUERY_TOOL_CAPABILITY_IDS_BY_NAME = {
    "browser_use": "tool:browser_use",
    "desktop_screenshot": "tool:desktop_screenshot",
    "edit_file": "tool:edit_file",
    "execute_shell_command": "tool:execute_shell_command",
    "get_current_time": "tool:get_current_time",
    "read_file": "tool:read_file",
    "send_file_to_user": "tool:send_file_to_user",
    "write_file": "tool:write_file",
}


def _query_tool_contract_metadata(
    payload: dict[str, Any] | None,
    *,
    capability_trial_attribution: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    raw_payload = dict(payload or {})
    tool_name = _first_non_empty(raw_payload.get("tool_name"))
    capability_id = _QUERY_TOOL_CAPABILITY_IDS_BY_NAME.get(tool_name or "")
    if capability_id is None:
        return raw_payload
    tool_contract = get_tool_execution_contract(capability_id)
    if tool_contract is None:
        return raw_payload
    metadata = {
        **dict(_mapping_value(raw_payload.get("metadata"))),
        "tool_contract": capability_id,
    }
    action_mode = tool_contract.resolve_action_mode(raw_payload)
    if action_mode in {"read", "write"}:
        metadata["action_mode"] = action_mode
        metadata["read_only"] = action_mode == "read"
    metadata["concurrency_class"] = tool_contract.resolve_concurrency_class(
        raw_payload,
        action_mode=action_mode if action_mode in {"read", "write"} else None,
    )
    metadata["preflight_policy"] = tool_contract.preflight_policy
    if capability_trial_attribution:
        for key in _QUERY_TRIAL_ATTRIBUTION_SCALAR_FIELDS:
            resolved = _first_non_empty(capability_trial_attribution.get(key))
            if resolved is not None:
                metadata[key] = resolved
        for key in _QUERY_TRIAL_ATTRIBUTION_LIST_FIELDS:
            resolved_items = _string_list(capability_trial_attribution.get(key))
            if resolved_items:
                metadata[key] = resolved_items
    raw_payload["metadata"] = metadata
    return raw_payload


def _normalize_capability_trial_attribution(
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    raw_payload = _mapping_value(payload)
    if not raw_payload:
        return {}
    normalized: dict[str, Any] = {}
    candidate_id = _first_non_empty(
        raw_payload.get("candidate_id"),
        raw_payload.get("skill_candidate_id"),
    )
    if candidate_id is not None:
        normalized["candidate_id"] = candidate_id
    skill_candidate_id = _first_non_empty(
        raw_payload.get("skill_candidate_id"),
        raw_payload.get("candidate_id"),
    )
    if skill_candidate_id is not None:
        normalized["skill_candidate_id"] = skill_candidate_id
    skill_trial_id = _first_non_empty(
        raw_payload.get("skill_trial_id"),
        raw_payload.get("trial_id"),
    )
    if skill_trial_id is not None:
        normalized["skill_trial_id"] = skill_trial_id
    skill_lifecycle_stage = _first_non_empty(
        raw_payload.get("skill_lifecycle_stage"),
        raw_payload.get("lifecycle_stage"),
    )
    if skill_lifecycle_stage is not None:
        normalized["skill_lifecycle_stage"] = skill_lifecycle_stage
    selected_scope = _first_non_empty(
        raw_payload.get("selected_scope"),
        raw_payload.get("scope_type"),
        raw_payload.get("trial_scope"),
    )
    if selected_scope is not None:
        normalized["selected_scope"] = selected_scope
    selected_seat_ref = _first_non_empty(raw_payload.get("selected_seat_ref"))
    if selected_seat_ref is not None:
        normalized["selected_seat_ref"] = selected_seat_ref
    for key in (
        "donor_id",
        "package_id",
        "source_profile_id",
        "candidate_source_kind",
        "resolution_kind",
        "verified_stage",
        "provider_resolution_status",
        "compatibility_status",
        "protocol_surface_kind",
        "transport_kind",
        "compiled_adapter_id",
        "selected_adapter_action_id",
        "probe_outcome",
        "probe_error_type",
    ):
        resolved = _first_non_empty(raw_payload.get(key))
        if resolved is not None:
            normalized[key] = resolved
    for key in _QUERY_TRIAL_ATTRIBUTION_LIST_FIELDS:
        resolved_items = _bounded_string_list(
            raw_payload.get(key),
            max_items=_QUERY_TRIAL_ATTRIBUTION_MAX_LIST_ITEMS,
        )
        if resolved_items:
            normalized[key] = resolved_items
    return normalized


def _merge_query_tool_trial_attribution(
    payload: dict[str, Any] | None,
    attribution: Mapping[str, Any] | None,
) -> dict[str, Any]:
    resolved_payload = _query_tool_contract_metadata(payload)
    resolved_attribution = {
        key: value
        for key, value in _normalize_capability_trial_attribution(attribution).items()
        if value is not None and value != "" and value != []
    }
    if not resolved_attribution:
        return resolved_payload
    metadata = {
        **dict(_mapping_value(resolved_payload.get("metadata"))),
        **resolved_attribution,
    }
    resolved_payload["metadata"] = metadata
    return resolved_payload


def _query_environment_ref(execution_context: Mapping[str, Any] | None) -> str | None:
    runtime = _mapping_value((execution_context or {}).get("main_brain_runtime"))
    environment = _mapping_value(runtime.get("environment"))
    return _first_non_empty(
        environment.get("ref"),
        environment.get("session_id"),
    )


def _resolve_runtime_entropy_budget_payload(
    *,
    running_config: Any | None = None,
) -> dict[str, Any]:
    running = running_config if running_config is not None else load_config().agents.running
    compact_threshold = getattr(running, "memory_compact_threshold", None)
    if compact_threshold is None:
        compact_threshold = int(
            max(
                0,
                float(getattr(running, "max_input_length", 0) or 0)
                * float(getattr(running, "memory_compact_ratio", 0) or 0),
            ),
        )
    tool_result_compact_enabled = bool(
        getattr(running, "enable_tool_result_compact", False),
    )
    tool_result_compact_keep_n = int(
        getattr(running, "tool_result_compact_keep_n", 0) or 0,
    )
    return {
        "max_input_length": int(getattr(running, "max_input_length", 0) or 0),
        "memory_compact_ratio": float(getattr(running, "memory_compact_ratio", 0) or 0),
        "memory_compact_threshold": int(compact_threshold or 0),
        "memory_compact_reserve": int(getattr(running, "memory_compact_reserve", 0) or 0),
        "enable_tool_result_compact": tool_result_compact_enabled,
        "tool_result_compact_keep_n": tool_result_compact_keep_n,
        "keep_recent_messages": MEMORY_COMPACT_KEEP_RECENT,
        "tool_result_budget": _build_tool_result_budget_contract(
            enabled=tool_result_compact_enabled,
            keep_recent_tool_results=tool_result_compact_keep_n,
        ),
    }


def _normalize_runtime_entropy_degradation(
    *,
    sidecar_memory_available: bool,
    degradation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved = {
        key: value for key, value in dict(degradation or {}).items() if value is not None
    }
    sidecar_memory = _mapping_value(resolved.get("sidecar_memory"))
    if sidecar_memory or sidecar_memory_available:
        return resolved
    resolved["sidecar_memory"] = build_execution_diagnostics(
        failure_source=_RUNTIME_ENTROPY_FAILURE_SOURCE,
        remediation_summary=_RUNTIME_ENTROPY_DEGRADED_SUMMARY,
    )
    return resolved


def build_runtime_entropy_sidecar_memory_projection(
    *,
    sidecar_memory_available: bool,
    degradation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_degradation = _normalize_runtime_entropy_degradation(
        sidecar_memory_available=sidecar_memory_available,
        degradation=degradation,
    )
    sidecar_memory = _mapping_value(resolved_degradation.get("sidecar_memory"))
    if sidecar_memory:
        remediation_summary = _first_non_empty(
            sidecar_memory.get("remediation_summary"),
            _RUNTIME_ENTROPY_DEGRADED_SUMMARY,
        )
        blocked_next_step = _first_non_empty(
            sidecar_memory.get("blocked_next_step"),
            _RUNTIME_ENTROPY_DEGRADED_NEXT_STEP,
        )
        failure_source = _first_non_empty(
            sidecar_memory.get("failure_source"),
            _RUNTIME_ENTROPY_FAILURE_SOURCE,
        )
        return {
            "status": "degraded",
            "availability": "missing",
            "failure_source": failure_source,
            "summary": remediation_summary,
            "blocked_next_step": blocked_next_step,
            "remediation_summary": remediation_summary,
        }
    return {
        "status": "available",
        "availability": "attached",
        "failure_source": _RUNTIME_ENTROPY_FAILURE_SOURCE,
        "summary": _RUNTIME_ENTROPY_AVAILABLE_SUMMARY,
        "blocked_next_step": "",
        "remediation_summary": _RUNTIME_ENTROPY_AVAILABLE_SUMMARY,
    }


def build_runtime_entropy_contract_payload(
    *,
    sidecar_memory_available: bool,
    degradation: dict[str, Any] | None = None,
    budget: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_budget = dict(budget or _resolve_runtime_entropy_budget_payload())
    resolved_degradation = _normalize_runtime_entropy_degradation(
        sidecar_memory_available=sidecar_memory_available,
        degradation=degradation,
    )
    sidecar_memory = build_runtime_entropy_sidecar_memory_projection(
        sidecar_memory_available=sidecar_memory_available,
        degradation=resolved_degradation,
    )
    degraded_components = _runtime_entropy_degraded_components(resolved_degradation)
    status = "degraded" if degraded_components else "available"
    donor_trial_degradation = _mapping_value(
        resolved_degradation.get("donor_trial_carry_forward"),
    )
    return {
        "status": status,
        "sidecar_memory_status": sidecar_memory["status"],
        "degraded_components": degraded_components,
        "carry_forward_contract": (
            "canonical-state-only"
            if sidecar_memory["status"] == "degraded"
            else "private-compaction-sidecar"
        ),
        "failure_source": _runtime_entropy_failure_source(resolved_degradation),
        "donor_trial_budget": _build_donor_trial_budget_contract(),
        "donor_trial_carry_forward_status": (
            "degraded" if donor_trial_degradation else "inactive"
        ),
        "tool_result_budget": dict(
            resolved_budget.get("tool_result_budget") or {},
        ),
        **resolved_budget,
    }


def build_query_runtime_entropy_contract_payload(
    *,
    sidecar_memory_available: bool,
    degradation: dict[str, Any] | None = None,
    budget: dict[str, Any] | None = None,
    runtime_entropy: dict[str, Any] | None = None,
    compaction_visibility: dict[str, Any] | None = None,
    donor_trial_carry_forward: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_budget = dict(budget or _resolve_runtime_entropy_budget_payload())
    resolved_degradation = _normalize_runtime_entropy_degradation(
        sidecar_memory_available=sidecar_memory_available,
        degradation=degradation,
    )
    resolved_donor_trial_carry_forward = build_donor_trial_carry_forward_projection(
        donor_trial_carry_forward,
    )
    resolved_runtime_entropy = dict(
        runtime_entropy
        or build_runtime_entropy_contract_payload(
            sidecar_memory_available=sidecar_memory_available,
            degradation=resolved_degradation,
            budget=resolved_budget,
        ),
    )
    resolved_runtime_entropy.setdefault(
        "donor_trial_budget",
        _build_donor_trial_budget_contract(),
    )
    resolved_runtime_entropy["donor_trial_carry_forward_status"] = (
        resolved_donor_trial_carry_forward["status"]
    )
    resolved_runtime_entropy["donor_trial_carry_forward"] = (
        resolved_donor_trial_carry_forward
    )
    return {
        # Compatibility wrapper: keep the historical query_runtime_entropy surface
        # while projecting the canonical runtime_entropy contract verbatim.
        "status": resolved_runtime_entropy["status"],
        "runtime_entropy": resolved_runtime_entropy,
        "budget": resolved_budget,
        "sidecar_memory": build_runtime_entropy_sidecar_memory_projection(
            sidecar_memory_available=sidecar_memory_available,
            degradation=resolved_degradation,
        ),
        "degradation": resolved_degradation,
        "donor_trial_carry_forward": resolved_donor_trial_carry_forward,
        **_normalize_runtime_compaction_visibility(compaction_visibility),
    }


def _normalize_runtime_compaction_visibility(
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    source = dict(payload or {})
    normalized: dict[str, Any] = {}
    for key in _COMPACTION_VISIBILITY_KEYS:
        if key == "donor_trial_carry_forward":
            normalized[key] = build_donor_trial_carry_forward_projection(
                _mapping_value(source.get(key)),
            )
            continue
        value = _mapping_value(source.get(key))
        if value:
            normalized[key] = value
    return normalized


def _resolve_runtime_compaction_visibility_payload(
    conversation_compaction_service: Any | None,
) -> dict[str, Any]:
    if conversation_compaction_service is None:
        return {}
    visibility_source: dict[str, Any] = {}
    for getter_name in ("runtime_visibility_payload", "runtime_health_payload"):
        getter = getattr(conversation_compaction_service, getter_name, None)
        if not callable(getter):
            continue
        try:
            payload = getter()
        except Exception:
            logger.debug("Runtime compaction visibility getter failed", exc_info=True)
            continue
        payload_mapping = _mapping_value(payload)
        if payload_mapping:
            visibility_source.update(payload_mapping)
    builder = getattr(conversation_compaction_service, "build_visibility_payload", None)
    if callable(builder):
        try:
            payload = builder(visibility_source or None)
        except TypeError:
            payload = builder()
        except Exception:
            logger.debug("Runtime compaction visibility builder failed", exc_info=True)
        else:
            payload_mapping = _mapping_value(payload)
            if payload_mapping:
                return _normalize_runtime_compaction_visibility(payload_mapping)
    return _normalize_runtime_compaction_visibility(visibility_source)


class _QueryExecutionRuntimeMixin(
    _QueryExecutionContextRuntimeMixin,
    _QueryExecutionResidentRuntimeMixin,
    _QueryExecutionUsageRuntimeMixin,
):
    def __init__(
        self,
        *,
        session_backend: Any,
        conversation_compaction_service: ConversationCompactionService | None = None,
        mcp_manager: Any | None = None,
        tool_bridge: Any | None = None,
        environment_service: Any | None = None,
        capability_service: Any | None = None,
        kernel_dispatcher: Any | None = None,
        agent_profile_service: Any | None = None,
        delegation_service: Any | None = None,
        industry_service: Any | None = None,
        strategy_memory_service: Any | None = None,
        prediction_service: Any | None = None,
        knowledge_service: Any | None = None,
        memory_recall_service: Any | None = None,
        memory_activation_service: Any | None = None,
        buddy_projection_service: Any | None = None,
        actor_mailbox_service: Any | None = None,
        agent_runtime_repository: Any | None = None,
        governance_control_repository: Any | None = None,
        task_repository: Any | None = None,
        task_runtime_repository: Any | None = None,
        evidence_ledger: Any | None = None,
        provider_manager: Any | None = None,
        lease_heartbeat_interval_seconds: float = 15.0,
    ) -> None:
        self._session_backend = session_backend
        self._conversation_compaction_service = conversation_compaction_service
        self._mcp_manager = mcp_manager
        self._tool_bridge = tool_bridge
        self._environment_service = environment_service
        self._capability_service = capability_service
        self._kernel_dispatcher = kernel_dispatcher
        self._agent_profile_service = agent_profile_service
        self._delegation_service = delegation_service
        self._industry_service = industry_service
        self._strategy_memory_service = strategy_memory_service
        self._prediction_service = prediction_service
        self._knowledge_service = knowledge_service
        self._memory_recall_service = memory_recall_service
        self._memory_activation_service = memory_activation_service
        self._buddy_projection_service = buddy_projection_service
        self._actor_mailbox_service = actor_mailbox_service
        self._agent_runtime_repository = agent_runtime_repository
        self._governance_control_repository = governance_control_repository
        self._task_repository = task_repository
        self._task_runtime_repository = task_runtime_repository
        self._evidence_ledger = evidence_ledger
        self._provider_manager = provider_manager
        self._lease_heartbeat_interval_seconds = max(
            0.01,
            float(lease_heartbeat_interval_seconds),
        )
        self._resident_agents: dict[str, _ResidentQueryAgent] = {}
        self._resident_agent_cache_lock = asyncio.Lock()
        self._interactive_actor_locks: dict[str, asyncio.Lock] = {}

    def resolve_request_owner_agent_id(self, *, request: Any) -> str:
        owner_agent_id, _profile = self._resolve_query_agent_profile(request=request)
        return owner_agent_id

    def set_session_backend(self, session_backend: Any) -> None:
        self._session_backend = session_backend

    def set_conversation_compaction_service(
        self,
        conversation_compaction_service: ConversationCompactionService | None,
    ) -> None:
        self._conversation_compaction_service = conversation_compaction_service

    def set_mcp_manager(self, mcp_manager: Any | None) -> None:
        self._mcp_manager = mcp_manager

    def set_tool_bridge(self, tool_bridge: Any | None) -> None:
        self._tool_bridge = tool_bridge

    def set_environment_service(self, environment_service: Any | None) -> None:
        self._environment_service = environment_service

    def set_capability_service(self, capability_service: Any | None) -> None:
        self._capability_service = capability_service

    def set_kernel_dispatcher(self, kernel_dispatcher: Any | None) -> None:
        self._kernel_dispatcher = kernel_dispatcher

    def set_agent_profile_service(self, agent_profile_service: Any | None) -> None:
        self._agent_profile_service = agent_profile_service

    def set_delegation_service(self, delegation_service: Any | None) -> None:
        self._delegation_service = delegation_service

    def set_industry_service(self, industry_service: Any | None) -> None:
        self._industry_service = industry_service

    def set_strategy_memory_service(self, strategy_memory_service: Any | None) -> None:
        self._strategy_memory_service = strategy_memory_service

    def set_prediction_service(self, prediction_service: Any | None) -> None:
        self._prediction_service = prediction_service

    def set_knowledge_service(self, knowledge_service: Any | None) -> None:
        self._knowledge_service = knowledge_service

    def set_memory_recall_service(self, memory_recall_service: Any | None) -> None:
        self._memory_recall_service = memory_recall_service

    def set_buddy_projection_service(self, buddy_projection_service: Any | None) -> None:
        self._buddy_projection_service = buddy_projection_service

    def set_memory_activation_service(self, memory_activation_service: Any | None) -> None:
        self._memory_activation_service = memory_activation_service

    def set_actor_mailbox_service(self, actor_mailbox_service: Any | None) -> None:
        self._actor_mailbox_service = actor_mailbox_service

    def set_agent_runtime_repository(self, agent_runtime_repository: Any | None) -> None:
        self._agent_runtime_repository = agent_runtime_repository

    def set_governance_control_repository(
        self,
        governance_control_repository: Any | None,
    ) -> None:
        self._governance_control_repository = governance_control_repository

    def set_task_repository(self, task_repository: Any | None) -> None:
        self._task_repository = task_repository

    def set_task_runtime_repository(self, task_runtime_repository: Any | None) -> None:
        self._task_runtime_repository = task_runtime_repository

    def set_evidence_ledger(self, evidence_ledger: Any | None) -> None:
        self._evidence_ledger = evidence_ledger

    def get_query_runtime_entropy_contract(self) -> dict[str, Any]:
        return self._build_query_runtime_entropy_contract()

    def _resolve_query_runtime_entropy_budget(self) -> dict[str, Any]:
        return _resolve_runtime_entropy_budget_payload()

    def _build_query_runtime_sidecar_memory_contract(
        self,
        *,
        degradation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return build_runtime_entropy_sidecar_memory_projection(
            sidecar_memory_available=self._conversation_compaction_service is not None,
            degradation=degradation,
        )

    def _build_runtime_entropy_contract(
        self,
        *,
        degradation: dict[str, Any] | None = None,
        budget: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return build_runtime_entropy_contract_payload(
            sidecar_memory_available=self._conversation_compaction_service is not None,
            degradation=degradation,
            budget=budget,
        )

    def _build_query_runtime_entropy_contract(
        self,
        *,
        degradation: dict[str, Any] | None = None,
        runtime_entropy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        budget = self._resolve_query_runtime_entropy_budget()
        compaction_visibility = _resolve_runtime_compaction_visibility_payload(
            self._conversation_compaction_service,
        )
        donor_trial_carry_forward = build_donor_trial_carry_forward_projection(
            _mapping_value(compaction_visibility.get("donor_trial_carry_forward")),
        )
        resolved_degradation = _normalize_runtime_entropy_degradation(
            sidecar_memory_available=self._conversation_compaction_service is not None,
            degradation=degradation,
        )
        donor_trial_degradation = _build_donor_trial_carry_forward_degradation(
            donor_trial_carry_forward,
        )
        if donor_trial_degradation is not None:
            resolved_degradation["donor_trial_carry_forward"] = donor_trial_degradation
        rebuilt_runtime_entropy = build_runtime_entropy_contract_payload(
            sidecar_memory_available=self._conversation_compaction_service is not None,
            degradation=resolved_degradation,
            budget=budget,
        )
        rebuilt_runtime_entropy["donor_trial_carry_forward_status"] = (
            donor_trial_carry_forward["status"]
        )
        rebuilt_runtime_entropy["donor_trial_carry_forward"] = donor_trial_carry_forward
        if runtime_entropy is not None:
            runtime_entropy.clear()
            runtime_entropy.update(rebuilt_runtime_entropy)
            resolved_runtime_entropy = runtime_entropy
        else:
            resolved_runtime_entropy = rebuilt_runtime_entropy
        return build_query_runtime_entropy_contract_payload(
            sidecar_memory_available=self._conversation_compaction_service is not None,
            degradation=resolved_degradation,
            budget=budget,
            runtime_entropy=resolved_runtime_entropy,
            compaction_visibility=compaction_visibility,
            donor_trial_carry_forward=donor_trial_carry_forward,
        )

    def _build_governance_control_record(
        self,
        *,
        existing_control: GovernanceControlRecord | None,
        metadata: dict[str, Any],
        updated_at: datetime,
    ) -> GovernanceControlRecord:
        if existing_control is None:
            return GovernanceControlRecord(
                id="runtime",
                metadata=metadata,
                updated_at=updated_at,
            )
        return GovernanceControlRecord(
            id=_first_non_empty(getattr(existing_control, "id", None), "runtime") or "runtime",
            emergency_stop_active=bool(
                getattr(existing_control, "emergency_stop_active", False),
            ),
            emergency_reason=getattr(existing_control, "emergency_reason", None),
            emergency_actor=getattr(existing_control, "emergency_actor", None),
            paused_schedule_ids=list(
                getattr(existing_control, "paused_schedule_ids", []) or [],
            ),
            channel_shutdown_applied=bool(
                getattr(existing_control, "channel_shutdown_applied", False),
            ),
            metadata=metadata,
            created_at=getattr(existing_control, "created_at", updated_at),
            updated_at=updated_at,
        )

    async def execute_stream(
        self,
        *,
        msgs: list[Any],
        request: Any,
        kernel_task_id: str | None = None,
        transient_input_message_ids: set[str] | None = None,
    ) -> AsyncIterator[tuple[Msg, bool]]:
        session_id = request.session_id
        user_id = request.user_id
        channel = getattr(request, "channel", DEFAULT_CHANNEL)
        logger.info(
            "Execute kernel query:\n%s",
            json.dumps(
                {
                    "session_id": session_id,
                    "user_id": user_id,
                    "channel": channel,
                    "msgs_len": len(msgs) if msgs else 0,
                    "msgs_str": str(msgs)[:300] + "...",
                    "kernel_task_id": kernel_task_id,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
        owner_agent_id, agent_profile = self._resolve_query_agent_profile(
            request=request,
        )
        actor_lock = self._interactive_actor_locks.setdefault(
            owner_agent_id,
            asyncio.Lock(),
        )
        async with actor_lock:
            async for msg, last in self._execute_stream_locked(
                msgs=msgs,
                request=request,
                kernel_task_id=kernel_task_id,
                session_id=session_id,
                user_id=user_id,
                channel=channel,
                owner_agent_id=owner_agent_id,
                agent_profile=agent_profile,
                transient_input_message_ids=transient_input_message_ids,
            ):
                yield msg, last

    async def _execute_stream_locked(
        self,
        *,
        msgs: list[Any],
        request: Any,
        kernel_task_id: str | None,
        session_id: str,
        user_id: str,
        channel: str,
        owner_agent_id: str,
        agent_profile: Any | None,
        transient_input_message_ids: set[str] | None,
    ) -> AsyncIterator[tuple[Msg, bool]]:
        agent = None
        lease = None
        actor_lease = None
        session_state_loaded = False
        final_summary: str | None = None
        final_error: str | None = None
        stream_step_count = 0
        execution_context: dict[str, Any] = {}
        resident_key = self._resident_agent_cache_key(
            channel=channel,
            session_id=session_id,
            user_id=user_id,
            owner_agent_id=owner_agent_id,
        )

        try:
            env_context = build_env_context(
                session_id=session_id,
                user_id=user_id,
                channel=channel,
                working_dir=str(WORKING_DIR),
            )
            execution_context = self._resolve_execution_task_context(
                request=request,
                agent_id=owner_agent_id,
                kernel_task_id=kernel_task_id,
                conversation_thread_id=session_id,
            )
            self._mark_actor_query_started(
                agent_id=owner_agent_id,
                task_id=kernel_task_id,
                session_id=session_id,
                user_id=user_id,
                conversation_thread_id=session_id,
                channel=channel,
                execution_context=execution_context,
            )
            try:
                actor_lease = self._acquire_actor_runtime_lease(
                    agent_id=owner_agent_id,
                    task_id=kernel_task_id,
                    conversation_thread_id=session_id,
                )
            except RuntimeError as exc:
                lowered = str(exc).lower()
                if "already leased by" in lowered:
                    busy_msg = Msg(
                        name="Spider Mesh",
                        role="assistant",
                        content=[
                            TextBlock(
                                type="text",
                                text=(
                                    "**执行编排暂时不可用（执行位正忙）**\n\n"
                                    "- 当前执行核正在处理其它任务，为避免环境/会话冲突，本轮无法进入执行编排。\n"
                                    "- 建议：等待当前执行完成后再重试；或在 AgentWorkbench / 运行面板里停止正在执行的任务后再发起。"
                                ),
                            )
                        ],
                    )
                    final_summary = _message_preview(busy_msg)
                    final_error = "actor_runtime_busy"
                    yield busy_msg, True
                    return
                raise
            self._assert_bound_chat_context(
                request=request,
                owner_agent_id=owner_agent_id,
                agent_profile=agent_profile,
            )
            (
                tool_capability_ids,
                skill_names,
                mcp_client_keys,
                system_capability_ids,
                desktop_actuation_available,
                capability_layers,
            ) = self._resolve_query_capability_context(owner_agent_id)
            (
                tool_capability_ids,
                skill_names,
                mcp_client_keys,
                system_capability_ids,
                desktop_actuation_available,
            ) = self._prune_execution_core_control_capability_context(
                request=request,
                owner_agent_id=owner_agent_id,
                agent_profile=agent_profile,
                tool_capability_ids=tool_capability_ids,
                skill_names=skill_names,
                mcp_client_keys=mcp_client_keys,
                system_capability_ids=system_capability_ids,
                desktop_actuation_available=desktop_actuation_available,
            )
            delegation_guard = self._resolve_delegation_first_guard(
                request=request,
                owner_agent_id=owner_agent_id,
                agent_profile=agent_profile,
                system_capability_ids=system_capability_ids,
            )
            team_role_gap_action_result = await self._handle_team_role_gap_chat_action(
                msgs=msgs,
                request=request,
                owner_agent_id=owner_agent_id,
                agent_profile=agent_profile,
            )
            if team_role_gap_action_result is not None:
                final_summary = _message_preview(team_role_gap_action_result)
                yield team_role_gap_action_result, True
                return
            team_role_gap_notice = self._build_team_role_gap_notice_message(
                msgs=msgs,
                request=request,
                owner_agent_id=owner_agent_id,
                agent_profile=agent_profile,
            )
            if team_role_gap_notice is not None:
                final_summary = _message_preview(team_role_gap_notice)
                yield team_role_gap_notice, True
                return
            chat_writeback_summary, industry_kickoff_summary = await self._apply_requested_main_brain_intake(
                msgs=msgs,
                request=request,
                owner_agent_id=owner_agent_id,
                agent_profile=agent_profile,
            )
            team_role_gap_summary = self._resolve_active_team_role_gap_summary(
                request=request,
                owner_agent_id=owner_agent_id,
                agent_profile=agent_profile,
            )
            mounted_capabilities = _merged_capability_ids(
                tool_capability_ids=tool_capability_ids,
                skill_names=skill_names,
                mcp_client_keys=mcp_client_keys,
                system_capability_ids=system_capability_ids,
            )
            prompt_appendix = self._build_profile_prompt_appendix(
                request=request,
                msgs=msgs,
                owner_agent_id=owner_agent_id,
                kernel_task_id=kernel_task_id,
                agent_profile=agent_profile,
                mounted_capabilities=mounted_capabilities,
                capability_layers=capability_layers,
                desktop_actuation_available=desktop_actuation_available,
                execution_context=execution_context,
                delegation_guard=delegation_guard,
                industry_kickoff_summary=industry_kickoff_summary,
                chat_writeback_summary=chat_writeback_summary,
                team_role_gap_summary=team_role_gap_summary,
            )
            system_tool_functions = self._build_system_tool_functions(
                request=request,
                owner_agent_id=owner_agent_id,
                agent_profile=agent_profile,
                system_capability_ids=system_capability_ids,
                kernel_task_id=kernel_task_id,
                delegation_guard=delegation_guard,
            )

            mcp_clients = []
            if self._mcp_manager is not None:
                if mcp_client_keys is None:
                    mcp_clients = await self._mcp_manager.get_clients()
                else:
                    for client_key in mcp_client_keys:
                        client = await self._mcp_manager.get_client(client_key)
                        if client is not None:
                            mcp_clients.append(client)

            config = load_config()
            resident_signature = self._resident_agent_signature(
                owner_agent_id=owner_agent_id,
                actor_key=_field_value(agent_profile, "actor_key"),
                actor_fingerprint=_field_value(agent_profile, "actor_fingerprint"),
                prompt_appendix=prompt_appendix,
                tool_capability_ids=tool_capability_ids,
                skill_names=skill_names,
                mcp_client_keys=mcp_client_keys,
                system_capability_ids=system_capability_ids,
            )
            resident = await self._get_or_create_resident_agent(
                cache_key=resident_key,
                signature=resident_signature,
                session_id=session_id,
                user_id=user_id,
                channel=channel,
                owner_agent_id=owner_agent_id,
                create_agent=lambda: CoPawAgent(
                    env_context=env_context,
                    prompt_appendix=prompt_appendix,
                    mcp_clients=mcp_clients,
                    conversation_compaction_service=self._conversation_compaction_service,
                    max_iters=config.agents.running.max_iters,
                    max_input_length=config.agents.running.max_input_length,
                    allowed_tool_capability_ids=tool_capability_ids,
                    allowed_skill_names=skill_names,
                    capability_layers=capability_layers,
                    extra_tool_functions=system_tool_functions,
                ),
            )
            agent = resident.agent
            session_state_loaded = True

            if self._environment_service is not None:
                try:
                    lease = self._environment_service.acquire_session_lease(
                        channel=channel,
                        session_id=session_id,
                        user_id=user_id,
                        owner=owner_agent_id,
                        handle={
                            "channel": channel,
                            "session_id": session_id,
                            "user_id": user_id,
                            "task_id": kernel_task_id,
                        },
                        metadata={
                            "channel": channel,
                            "session_id": session_id,
                            "user_id": user_id,
                            "conversation_thread_id": session_id,
                            "kernel_task_id": kernel_task_id,
                            "owner_agent_id": owner_agent_id,
                        },
                    )
                except Exception:
                    logger.exception("Environment session lease failed")

            self._record_query_checkpoint(
                agent_id=owner_agent_id,
                task_id=kernel_task_id,
                session_id=session_id,
                user_id=user_id,
                conversation_thread_id=session_id,
                channel=channel,
                phase="query-loaded",
                checkpoint_kind="resume",
                status="ready",
                summary="已加载交互查询轮次的会话状态",
                execution_context=execution_context,
                snapshot_payload={
                    "session_state_loaded": True,
                },
            )
            agent.rebuild_sys_prompt()

            heartbeat = self._build_query_lease_heartbeat(
                session_lease=lease,
                actor_lease=actor_lease,
            )
            capability_trial_attribution = _normalize_capability_trial_attribution(
                _mapping_value((execution_context or {}).get("capability_trial_attribution")),
            )
            tool_execution_delegate = self._build_query_tool_execution_delegate(
                owner_agent_id=owner_agent_id,
                kernel_task_id=kernel_task_id,
                execution_context=execution_context,
            )
            capability_trial_attribution = _normalize_capability_trial_attribution(
                (execution_context or {}).get("capability_trial_attribution"),
            )
            if capability_trial_attribution:
                setattr(
                    request,
                    "_copaw_capability_trial_attribution",
                    dict(capability_trial_attribution),
                )
            tool_preflight = self._build_tool_preflight(
                delegation_guard=delegation_guard,
                msgs=msgs,
                request=request,
                owner_agent_id=owner_agent_id,
                agent_profile=agent_profile,
                kernel_task_id=kernel_task_id,
            )
            with bind_reasoning_tool_choice_resolver(
                lambda: (
                    "required"
                    if delegation_guard is not None and delegation_guard.locked
                    else None
                ),
            ):
                with bind_tool_execution_delegate(tool_execution_delegate):
                    with bind_tool_preflight(tool_preflight):
                        with bind_shell_evidence_sink(
                            self._make_shell_evidence_sink(
                                kernel_task_id,
                                capability_trial_attribution=capability_trial_attribution,
                            ),
                        ):
                            with bind_file_evidence_sink(
                                self._make_file_evidence_sink(
                                    kernel_task_id,
                                    capability_trial_attribution=capability_trial_attribution,
                                ),
                            ):
                                with bind_browser_evidence_sink(
                                    self._make_browser_evidence_sink(
                                        kernel_task_id,
                                        capability_trial_attribution=capability_trial_attribution,
                                    ),
                                ):
                                    if heartbeat is None:
                                        async for msg, last in stream_printing_messages(
                                            agents=[agent],
                                            coroutine_task=agent(msgs),
                                        ):
                                            stream_step_count += 1
                                            final_summary = _message_preview(msg) or final_summary
                                            self._record_query_checkpoint(
                                                agent_id=owner_agent_id,
                                                task_id=kernel_task_id,
                                                session_id=session_id,
                                                user_id=user_id,
                                                conversation_thread_id=session_id,
                                                channel=channel,
                                                phase="query-streaming",
                                                checkpoint_kind="worker-step",
                                                status="ready",
                                                summary=final_summary or f"Stream output step {stream_step_count}",
                                                execution_context=execution_context,
                                                stream_step_count=stream_step_count,
                                                snapshot_payload={
                                                    "last_message_preview": final_summary,
                                                    "last_message_is_terminal": last,
                                                },
                                            )
                                            yield msg, last
                                    else:
                                        async with heartbeat:
                                            async for msg, last in stream_printing_messages(
                                                agents=[agent],
                                                coroutine_task=agent(msgs),
                                            ):
                                                stream_step_count += 1
                                                await heartbeat.pulse()
                                                final_summary = _message_preview(msg) or final_summary
                                                self._record_query_checkpoint(
                                                    agent_id=owner_agent_id,
                                                    task_id=kernel_task_id,
                                                    session_id=session_id,
                                                    user_id=user_id,
                                                    conversation_thread_id=session_id,
                                                    channel=channel,
                                                    phase="query-streaming",
                                                    checkpoint_kind="worker-step",
                                                    status="ready",
                                                    summary=final_summary or f"Stream output step {stream_step_count}",
                                                    execution_context=execution_context,
                                                    stream_step_count=stream_step_count,
                                                    snapshot_payload={
                                                        "last_message_preview": final_summary,
                                                        "last_message_is_terminal": last,
                                                    },
                                                )
                                                yield msg, last
        except asyncio.CancelledError:
            final_error = "任务已取消。"
            if agent is not None:
                await agent.interrupt()
            self._resident_agents.pop(resident_key, None)
            raise
        except Exception as exc:
            final_error = str(exc)
            self._resident_agents.pop(resident_key, None)
            raise
        finally:
            if agent is not None and session_state_loaded:
                await self._prune_transient_messages(
                    agent=agent,
                    message_ids=transient_input_message_ids,
                )
                await self._session_backend.save_session_state(
                    session_id=session_id,
                    user_id=user_id,
                    agent=agent,
                )

            if lease is not None and self._environment_service is not None:
                self._environment_service.release_session_lease(
                    lease.id,
                    lease_token=lease.lease_token,
                    reason="query turn completed",
                )
            self._release_actor_runtime_lease(actor_lease)
            self._mark_actor_query_finished(
                agent_id=owner_agent_id,
                task_id=kernel_task_id,
                session_id=session_id,
                user_id=user_id,
                conversation_thread_id=session_id,
                channel=channel,
                summary=final_summary,
                error=final_error,
                execution_context=execution_context,
                stream_step_count=stream_step_count,
            )

    async def resume_query_tool_confirmation(
        self,
        *,
        decision_request_id: str,
    ) -> dict[str, Any]:
        match = self._load_query_tool_confirmation_context(
            decision_request_id=decision_request_id,
        )
        if match is None:
            return {
                "resumed": False,
                "reason": "decision_not_query_tool_confirmation",
            }

        request_context = match["request_context"]
        query_text = match["query_text"]
        owner_agent_id = match["owner_agent_id"]
        tool_name = _first_non_empty(match.get("tool_name"))
        workflow_label = _risky_tool_workflow_label(tool_name)
        surface_label = _risky_tool_surface_label(tool_name)
        request = _build_query_resume_request(
            request_context=request_context,
            owner_agent_id=owner_agent_id,
        )
        dispatcher = self._kernel_dispatcher
        kernel_task_id: str | None = None
        managed_by_kernel_dispatcher = False
        control_msg = Msg(
            name="runtime-center",
            role="user",
            content=(
                f"系统已批准，确认继续执行刚才被确认门拦住的{workflow_label}。"
                + (f" 原请求：{query_text}" if query_text else "")
                + " 请直接从当前会话继续执行，不要再次请求确认，也不要重新解释审批要求。"
            ),
            metadata={
                "decision_request_id": decision_request_id,
                "transient": True,
                "resume_kind": "query-tool-confirmation",
            },
        )
        final_summary: str | None = None
        stream_events = 0
        if dispatcher is not None:
            admitted = dispatcher.submit(
                KernelTask(
                    title=query_text or f"Resume approved query tool confirmation {decision_request_id}",
                    capability_ref="system:dispatch_query",
                    environment_ref=f"session:{request.channel}:{request.session_id}",
                    owner_agent_id=owner_agent_id,
                    risk_level="auto",
                    payload={
                        "request": request_context,
                        "request_context": dict(request_context),
                        "channel": request.channel,
                        "user_id": request.user_id,
                        "session_id": request.session_id,
                        "dispatch_events": False,
                        "resume_source_decision_id": decision_request_id,
                        "resume_kind": "query-tool-confirmation",
                        "query_preview": query_text,
                    },
                ),
            )
            kernel_task_id = _first_non_empty(getattr(admitted, "task_id", None))
            managed_by_kernel_dispatcher = getattr(admitted, "phase", None) == "executing"
            if kernel_task_id is None:
                return {
                    "resumed": False,
                    "reason": "resume_task_admission_missing_task_id",
                    "decision_request_id": decision_request_id,
                }
            if getattr(admitted, "phase", None) != "executing":
                return {
                    "resumed": False,
                    "reason": "resume_task_not_executing",
                    "decision_request_id": decision_request_id,
                    "task_id": kernel_task_id,
                    "phase": getattr(admitted, "phase", None),
                    "summary": getattr(admitted, "summary", None),
                }
        try:
            async for msg, _last in self.execute_stream(
                msgs=[control_msg],
                request=request,
                kernel_task_id=kernel_task_id,
                transient_input_message_ids={control_msg.id},
            ):
                stream_events += 1
                final_summary = _message_preview(msg) or final_summary
        except Exception:
            if managed_by_kernel_dispatcher and kernel_task_id is not None and dispatcher is not None:
                try:
                    dispatcher.fail_task(
                        kernel_task_id,
                        error=f"已批准的{surface_label}续跑失败。",
                    )
                except Exception:
                    logger.exception(
                        "Failed to record query-tool-confirmation resume failure for %s",
                        decision_request_id,
                    )
            raise
        if managed_by_kernel_dispatcher and kernel_task_id is not None and dispatcher is not None:
            try:
                dispatcher.complete_task(
                    kernel_task_id,
                    summary=final_summary or "Approved query tool confirmation resumed",
                    metadata={
                        "source": "query-tool-confirmation-resume",
                        "decision_request_id": decision_request_id,
                    },
                )
            except Exception:
                logger.exception(
                    "Failed to complete query-tool-confirmation resume task for %s",
                    decision_request_id,
                )
        return {
            "resumed": True,
            "decision_request_id": decision_request_id,
            "owner_agent_id": owner_agent_id,
            "session_id": request.session_id,
            "channel": getattr(request, "channel", DEFAULT_CHANNEL),
            "task_id": kernel_task_id,
            "stream_events": stream_events,
            "summary": final_summary or "query tool confirmation resumed",
        }

    async def resume_human_assist_task(
        self,
        *,
        task: Any,
    ) -> dict[str, Any]:
        task_payload = _mapping_value(task)
        task_id = _first_non_empty(task_payload.get("id"))
        chat_thread_id = _first_non_empty(task_payload.get("chat_thread_id"))
        if task_id is None or chat_thread_id is None:
            return {
                "resumed": False,
                "reason": "human_assist_task_missing_context",
            }

        submission_payload = _mapping_value(task_payload.get("submission_payload"))
        industry_instance_id = _first_non_empty(
            submission_payload.get("industry_instance_id"),
            task_payload.get("industry_instance_id"),
        )
        main_brain_runtime_payload = _mapping_value(
            submission_payload.get("main_brain_runtime"),
        )
        work_context_id = _first_non_empty(
            submission_payload.get("work_context_id"),
            main_brain_runtime_payload.get("work_context_id"),
        )
        environment_ref = _first_non_empty(
            submission_payload.get("environment_ref"),
            main_brain_runtime_payload.get("environment_ref"),
        )
        request_context: dict[str, Any] = {
            "session_id": _first_non_empty(
                submission_payload.get("session_id"),
                chat_thread_id,
            ),
            "control_thread_id": _first_non_empty(
                submission_payload.get("control_thread_id"),
                chat_thread_id,
            ),
            "user_id": _first_non_empty(
                submission_payload.get("user_id"),
                "runtime-center",
            ),
            "channel": _first_non_empty(
                submission_payload.get("channel"),
                DEFAULT_CHANNEL,
            ),
            "entry_source": _first_non_empty(
                submission_payload.get("entry_source"),
                "human-assist-resume",
            ),
            "owner_scope": _first_non_empty(submission_payload.get("owner_scope")),
            "industry_instance_id": industry_instance_id,
            "industry_role_id": _first_non_empty(
                submission_payload.get("industry_role_id"),
                EXECUTION_CORE_ROLE_ID if industry_instance_id else None,
            ),
            "industry_role_name": _first_non_empty(
                submission_payload.get("industry_role_name"),
            ),
            "industry_label": _first_non_empty(submission_payload.get("industry_label")),
            "session_kind": _first_non_empty(
                submission_payload.get("session_kind"),
                "industry-control-thread" if chat_thread_id.startswith("industry-chat:") else None,
            ),
            "work_context_id": work_context_id,
            "environment_ref": environment_ref,
            "main_brain_runtime": main_brain_runtime_payload,
        }
        provisional_owner_agent_id = (
            _first_non_empty(
                submission_payload.get("agent_id"),
                submission_payload.get("target_agent_id"),
            )
            or EXECUTION_CORE_AGENT_ID
        )
        request = _build_query_resume_request(
            request_context=request_context,
            owner_agent_id=provisional_owner_agent_id,
        )
        normalized_main_brain_runtime = _mapping_value(
            getattr(request, "_copaw_main_brain_runtime_context", None)
            or getattr(request, "main_brain_runtime", None),
        )
        if normalized_main_brain_runtime:
            request_context["main_brain_runtime"] = normalized_main_brain_runtime
        control_thread_id = _first_non_empty(request_context.get("control_thread_id"))
        if control_thread_id is not None:
            setattr(request, "control_thread_id", control_thread_id)
        resume_checkpoint_ref = _first_non_empty(task_payload.get("resume_checkpoint_ref"))
        if resume_checkpoint_ref is not None:
            setattr(request, "resume_checkpoint_id", resume_checkpoint_ref)
            setattr(request, "checkpoint_id", resume_checkpoint_ref)
        owner_agent_id = self.resolve_request_owner_agent_id(request=request)
        title = _first_non_empty(task_payload.get("title")) or task_id
        required_action = _first_non_empty(task_payload.get("required_action"))
        submission_text = _first_non_empty(task_payload.get("submission_text"))
        evidence_refs = _string_list(task_payload.get("submission_evidence_refs"))

        control_parts = [
            f"宿主协作任务已通过验收，请从当前会话继续原流程。任务：{title}。",
        ]
        if required_action:
            control_parts.append(f"已完成动作：{required_action}")
        if submission_text:
            control_parts.append(f"宿主提交：{submission_text}")
        if evidence_refs:
            control_parts.append(f"证据：{', '.join(evidence_refs[:6])}")
        if resume_checkpoint_ref:
            control_parts.append(f"恢复点：{resume_checkpoint_ref}")
        control_msg = Msg(
            name="runtime-center",
            role="user",
            content=" ".join(control_parts),
            metadata={
                "human_assist_task_id": task_id,
                "transient": True,
                "resume_kind": "human-assist",
                "resume_checkpoint_ref": resume_checkpoint_ref,
            },
        )
        dispatcher = self._kernel_dispatcher
        kernel_task_id: str | None = None
        managed_by_kernel_dispatcher = False
        final_summary: str | None = None
        stream_events = 0
        if dispatcher is not None:
            admitted = dispatcher.submit(
                KernelTask(
                    title=f"Resume human assist task {title}",
                    capability_ref="system:dispatch_query",
                    work_context_id=work_context_id,
                    environment_ref=(
                        environment_ref
                        or f"session:{request.channel}:{request.session_id}"
                    ),
                    owner_agent_id=owner_agent_id,
                    risk_level="auto",
                    payload={
                        "request_context": dict(request_context),
                        "environment_ref": environment_ref,
                        "work_context_id": work_context_id,
                        "channel": request.channel,
                        "user_id": request.user_id,
                        "session_id": request.session_id,
                        "dispatch_events": False,
                        "resume_kind": "human-assist",
                        "human_assist_task_id": task_id,
                        "resume_checkpoint_ref": resume_checkpoint_ref,
                    },
                ),
            )
            kernel_task_id = _first_non_empty(getattr(admitted, "task_id", None))
            managed_by_kernel_dispatcher = getattr(admitted, "phase", None) == "executing"
            if kernel_task_id is None:
                return {
                    "resumed": False,
                    "reason": "resume_task_admission_missing_task_id",
                    "human_assist_task_id": task_id,
                }
            if getattr(admitted, "phase", None) != "executing":
                return {
                    "resumed": False,
                    "reason": "resume_task_not_executing",
                    "human_assist_task_id": task_id,
                    "task_id": kernel_task_id,
                    "phase": getattr(admitted, "phase", None),
                    "summary": getattr(admitted, "summary", None),
                }
        try:
            async for msg, _last in self.execute_stream(
                msgs=[control_msg],
                request=request,
                kernel_task_id=kernel_task_id,
                transient_input_message_ids={control_msg.id},
            ):
                stream_events += 1
                final_summary = _message_preview(msg) or final_summary
        except Exception:
            if managed_by_kernel_dispatcher and kernel_task_id is not None and dispatcher is not None:
                try:
                    dispatcher.fail_task(
                        kernel_task_id,
                        error="Human assist resume failed.",
                    )
                except Exception:
                    logger.exception(
                        "Failed to record human assist resume failure for %s",
                        task_id,
                    )
            raise
        if managed_by_kernel_dispatcher and kernel_task_id is not None and dispatcher is not None:
            try:
                dispatcher.complete_task(
                    kernel_task_id,
                    summary=final_summary or "Human assist resume finished",
                    metadata={
                        "source": "human-assist-resume",
                        "human_assist_task_id": task_id,
                    },
                )
            except Exception:
                logger.exception(
                    "Failed to complete human assist resume task for %s",
                    task_id,
                )
        return {
            "resumed": True,
            "human_assist_task_id": task_id,
            "owner_agent_id": owner_agent_id,
            "session_id": request.session_id,
            "channel": getattr(request, "channel", DEFAULT_CHANNEL),
            "task_id": kernel_task_id,
            "stream_events": stream_events,
            "summary": final_summary or "human assist resumed",
        }

    async def _prune_transient_messages(
        self,
        *,
        agent: Any,
        message_ids: set[str] | None,
    ) -> None:
        if not message_ids:
            return
        memory = getattr(agent, "memory", None)
        if memory is None:
            return
        delete = getattr(memory, "delete", None)
        if callable(delete):
            result = delete(list(message_ids))
            if asyncio.iscoroutine(result):
                await result
            return
        content = getattr(memory, "content", None)
        if isinstance(content, list):
            memory.content = [
                (msg, marks)
                for msg, marks in content
                if getattr(msg, "id", None) not in message_ids
            ]

    def _make_shell_evidence_sink(
        self,
        kernel_task_id: str | None,
        *,
        capability_trial_attribution: Mapping[str, Any] | None = None,
    ):
        if self._tool_bridge is None or kernel_task_id is None:
            return None
        return lambda payload: self._tool_bridge.record_shell_event(
            kernel_task_id,
            _merge_query_tool_trial_attribution(payload, capability_trial_attribution),
        )

    def _make_file_evidence_sink(
        self,
        kernel_task_id: str | None,
        *,
        capability_trial_attribution: Mapping[str, Any] | None = None,
    ):
        if self._tool_bridge is None or kernel_task_id is None:
            return None
        return lambda payload: self._tool_bridge.record_file_event(
            kernel_task_id,
            _merge_query_tool_trial_attribution(payload, capability_trial_attribution),
        )

    def _make_browser_evidence_sink(
        self,
        kernel_task_id: str | None,
        *,
        capability_trial_attribution: Mapping[str, Any] | None = None,
    ):
        if self._tool_bridge is None or kernel_task_id is None:
            return None
        return lambda payload: self._tool_bridge.record_browser_event(
            kernel_task_id,
            _merge_query_tool_trial_attribution(payload, capability_trial_attribution),
        )

    def _build_query_tool_execution_delegate(
        self,
        *,
        owner_agent_id: str | None,
        kernel_task_id: str | None,
        execution_context: Mapping[str, Any] | None,
    ):
        dispatcher = self._kernel_dispatcher
        submit = getattr(dispatcher, "submit", None)
        execute_task = getattr(dispatcher, "execute_task", None)
        if not callable(submit) or not callable(execute_task):
            return None
        if owner_agent_id is None or kernel_task_id is None:
            return None
        work_context_id = _first_non_empty(
            (execution_context or {}).get("work_context_id"),
        )
        environment_ref = _query_environment_ref(execution_context)
        risk_level = _first_non_empty(
            _mapping_value((execution_context or {}).get("main_brain_runtime")).get("risk_level"),
            "auto",
        ) or "auto"
        capability_trial_attribution = _normalize_capability_trial_attribution(
            _mapping_value((execution_context or {}).get("capability_trial_attribution")),
        )

        async def _delegate(capability_id: str, payload: dict[str, Any]) -> dict[str, Any]:
            task_payload = dict(payload or {})
            if capability_trial_attribution:
                task_payload["metadata"] = {
                    **dict(_mapping_value(task_payload.get("metadata"))),
                    **capability_trial_attribution,
                }
            capability_key = capability_id.replace(":", "-")
            task = KernelTask(
                id=f"{kernel_task_id}:tool:{capability_key}:{uuid4().hex[:8]}",
                parent_task_id=kernel_task_id,
                title=f"Query tool execution: {capability_id}",
                capability_ref=capability_id,
                owner_agent_id=owner_agent_id,
                work_context_id=work_context_id,
                environment_ref=environment_ref,
                risk_level=risk_level,
                payload=task_payload,
            )
            admitted = submit(task)
            admitted_payload = (
                admitted.model_dump(mode="json")
                if hasattr(admitted, "model_dump")
                else dict(admitted)
                if isinstance(admitted, dict)
                else None
            )
            if getattr(admitted, "phase", None) != "executing":
                return admitted_payload or {
                    "success": False,
                    "phase": getattr(admitted, "phase", None),
                    "summary": getattr(admitted, "summary", None) or "Tool admission did not execute.",
                    "decision_request_id": getattr(admitted, "decision_request_id", None),
                }
            result = await execute_task(task.id)
            return (
                result.model_dump(mode="json")
                if hasattr(result, "model_dump")
                else result
                if isinstance(result, dict)
                else {"success": False, "summary": "Unexpected query tool execution result."}
            )

        return _delegate

    def _mark_actor_query_started(
        self,
        *,
        agent_id: str,
        task_id: str | None,
        session_id: str,
        user_id: str,
        conversation_thread_id: str | None,
        channel: str,
        execution_context: dict[str, Any] | None = None,
    ) -> None:
        runtime_repository = self._agent_runtime_repository
        runtime = runtime_repository.get_runtime(agent_id) if runtime_repository is not None else None
        now = _utc_now()
        checkpoint = self._record_query_checkpoint(
            agent_id=agent_id,
            task_id=task_id,
            session_id=session_id,
            user_id=user_id,
            conversation_thread_id=conversation_thread_id,
            channel=channel,
            phase="query-start",
            checkpoint_kind="worker-step",
            status="ready",
            summary="已开始交互查询轮次",
            execution_context=execution_context,
        )
        checkpoint_id = getattr(checkpoint, "id", None) if checkpoint is not None else None
        if runtime is None or runtime_repository is None:
            return
        degradation = _mapping_value((execution_context or {}).get("degradation"))
        main_brain_runtime = self._merge_main_brain_runtime_contexts(
            dict(runtime.metadata or {}).get("main_brain_runtime"),
            (execution_context or {}).get("main_brain_runtime"),
        )
        metadata = {
            **dict(runtime.metadata or {}),
            "last_query_channel": channel,
            "last_query_session_id": session_id,
            "last_query_user_id": user_id,
            "last_query_thread_id": conversation_thread_id,
            "last_resume_cursor": _first_non_empty(
                _mapping_value(
                    (execution_context or {}).get("resume_point"),
                ).get("cursor"),
            ),
            "last_task_segment_id": _first_non_empty(
                _mapping_value(
                    (execution_context or {}).get("task_segment"),
                ).get("segment_id"),
            ),
        }
        if degradation:
            metadata["runtime_degradation"] = degradation
        else:
            metadata.pop("runtime_degradation", None)
        if main_brain_runtime is not None:
            metadata["main_brain_runtime"] = main_brain_runtime
        runtime_repository.upsert_runtime(
            runtime.model_copy(
                update={
                    "runtime_status": "running",
                    "current_task_id": task_id or runtime.current_task_id,
                    "last_started_at": now,
                    "last_heartbeat_at": now,
                    "last_error_summary": None,
                    "last_checkpoint_id": checkpoint_id or runtime.last_checkpoint_id,
                    "metadata": metadata,
                },
            ),
        )

    def _mark_actor_query_finished(
        self,
        *,
        agent_id: str,
        task_id: str | None,
        session_id: str,
        user_id: str,
        conversation_thread_id: str | None,
        channel: str,
        summary: str | None,
        error: str | None,
        execution_context: dict[str, Any] | None = None,
        stream_step_count: int = 0,
    ) -> None:
        runtime_repository = self._agent_runtime_repository
        runtime = runtime_repository.get_runtime(agent_id) if runtime_repository is not None else None
        now = _utc_now()
        resolved_error = normalize_runtime_summary(error)
        final_summary = normalize_runtime_summary(summary) or resolved_error or "交互查询已完成"
        checkpoint_phase, checkpoint_status = query_checkpoint_outcome(resolved_error)
        checkpoint = self._record_query_checkpoint(
            agent_id=agent_id,
            task_id=task_id,
            session_id=session_id,
            user_id=user_id,
            conversation_thread_id=conversation_thread_id,
            channel=channel,
            phase=checkpoint_phase,
            checkpoint_kind="task-result",
            status=checkpoint_status,
            summary=final_summary,
            execution_context=execution_context,
            stream_step_count=stream_step_count,
            snapshot_payload={
                "error": resolved_error,
                "final_summary": final_summary,
            },
        )
        checkpoint_id = getattr(checkpoint, "id", None) if checkpoint is not None else None
        if runtime is None or runtime_repository is None:
            return
        blocking_error = resolved_error if should_block_runtime_error(resolved_error) else None
        degradation = _mapping_value((execution_context or {}).get("degradation"))
        main_brain_runtime_payload = _mapping_value(
            (execution_context or {}).get("main_brain_runtime"),
        )
        work_context_id = _first_non_empty((execution_context or {}).get("work_context_id"))
        environment_ref = _query_environment_ref(execution_context) or channel
        risk_level = _first_non_empty(
            main_brain_runtime_payload.get("risk_level"),
            "auto",
        )
        outcome = classify_runtime_outcome(
            resolved_error,
            success=resolved_error is None,
            phase="blocked" if blocking_error else None,
        )
        diagnostics = build_execution_diagnostics(
            phase=outcome,
            error=resolved_error,
            summary=final_summary,
        )
        knowledge_writeback_service = KnowledgeWritebackService(
            knowledge_service=self._knowledge_service,
        )
        knowledge_writeback = build_execution_knowledge_writeback(
            scope_type="work_context" if work_context_id else "task" if task_id else "agent",
            scope_id=(
                work_context_id
                or task_id
                or agent_id
            ),
            outcome_ref=_first_non_empty(checkpoint_id, task_id, session_id, agent_id) or agent_id,
            outcome=outcome,
            summary=final_summary,
            capability_ref="system:dispatch_query",
            environment_ref=environment_ref,
            risk_level=risk_level,
            failure_source=diagnostics.get("failure_source"),
            blocked_next_step=diagnostics.get("blocked_next_step"),
            evidence_refs=[checkpoint_id] if checkpoint_id else None,
            recovery_summary=(
                diagnostics.get("remediation_summary")
                if outcome in {"failed", "blocked", "cancelled", "timeout"}
                else None
            ),
            knowledge_writeback_service=knowledge_writeback_service,
            persist=True,
        )
        main_brain_runtime = self._merge_main_brain_runtime_contexts(
            dict(runtime.metadata or {}).get("main_brain_runtime"),
            (execution_context or {}).get("main_brain_runtime"),
        )
        metadata = {
            **dict(runtime.metadata or {}),
            "last_query_channel": channel,
            "last_query_session_id": session_id,
            "last_query_user_id": user_id,
            "last_query_thread_id": conversation_thread_id,
            "last_stream_step_count": stream_step_count,
            "last_query_outcome": (
                "failed"
                if blocking_error
                else "cancelled"
                if resolved_error
                else "degraded"
                if degradation
                else "completed"
            ),
            "knowledge_writeback": knowledge_writeback,
        }
        if degradation:
            metadata["runtime_degradation"] = degradation
        else:
            metadata.pop("runtime_degradation", None)
        if main_brain_runtime is not None:
            metadata["main_brain_runtime"] = main_brain_runtime
        runtime_repository.upsert_runtime(
            runtime.model_copy(
                update={
                    "runtime_status": (
                        "paused"
                        if runtime.desired_state == "paused"
                        else "blocked"
                        if blocking_error
                        else "idle"
                    ),
                    "current_task_id": None,
                    "last_heartbeat_at": now,
                    "last_stopped_at": now,
                    "last_result_summary": runtime.last_result_summary if resolved_error else final_summary,
                    "last_error_summary": resolved_error,
                    "last_checkpoint_id": checkpoint_id or runtime.last_checkpoint_id,
                    "metadata": metadata,
                },
            ),
        )

    def _record_query_checkpoint(
        self,
        *,
        agent_id: str,
        task_id: str | None,
        session_id: str,
        user_id: str,
        conversation_thread_id: str | None,
        channel: str,
        phase: str,
        checkpoint_kind: str,
        status: str,
        summary: str,
        execution_context: dict[str, Any] | None = None,
        stream_step_count: int = 0,
        snapshot_payload: dict[str, object] | None = None,
    ) -> Any | None:
        if self._actor_mailbox_service is None:
            return None
        create_checkpoint = getattr(self._actor_mailbox_service, "create_checkpoint", None)
        if not callable(create_checkpoint):
            return None
        runtime = (
            self._agent_runtime_repository.get_runtime(agent_id)
            if self._agent_runtime_repository is not None
            else None
        )
        mailbox_id = getattr(runtime, "current_mailbox_id", None) if runtime is not None else None
        task_segment = _mapping_value((execution_context or {}).get("task_segment"))
        resume_point = _mapping_value((execution_context or {}).get("resume_point"))
        main_brain_runtime = self._merge_main_brain_runtime_contexts(
            (execution_context or {}).get("main_brain_runtime"),
        )
        checkpoint_payload = {
            "session_id": session_id,
            "user_id": user_id,
            "channel": channel,
            "kernel_task_id": task_id,
            "stream_step_count": stream_step_count,
            "task_segment": task_segment,
            "resume_point": {
                **resume_point,
                "phase": phase,
                "cursor": _first_non_empty(
                    resume_point.get("cursor"),
                    task_segment.get("segment_id"),
                    conversation_thread_id,
                ),
            },
        }
        if main_brain_runtime is not None:
            checkpoint_payload["main_brain_runtime"] = main_brain_runtime
        degradation = _mapping_value((execution_context or {}).get("degradation"))
        if degradation:
            checkpoint_payload["degradation"] = degradation
        return create_checkpoint(
            agent_id=agent_id,
            mailbox_id=mailbox_id,
            task_id=task_id,
            work_context_id=_first_non_empty((execution_context or {}).get("work_context_id")),
            checkpoint_kind=checkpoint_kind,
            status=status,
            phase=phase,
            conversation_thread_id=conversation_thread_id,
            environment_ref=channel,
            summary=summary,
            snapshot_payload={
                "channel": channel,
                "conversation_thread_id": conversation_thread_id,
                **dict(snapshot_payload or {}),
            },
            resume_payload=checkpoint_payload,
        )

    def _resolve_query_agent_profile(
        self,
        *,
        request: Any,
    ) -> tuple[str, Any | None]:
        for agent_id in self._request_agent_candidates(request):
            if not agent_id:
                continue
            profile = self._get_agent_profile(agent_id)
            if profile is not None:
                return agent_id, profile
        fallback_profile = self._resolve_fallback_execution_core_profile(request=request)
        if fallback_profile is not None:
            return str(
                getattr(fallback_profile, "agent_id", EXECUTION_CORE_AGENT_ID),
            ), fallback_profile
        return EXECUTION_CORE_AGENT_ID, self._get_agent_profile(EXECUTION_CORE_AGENT_ID)

    def _request_agent_candidates(self, request: Any) -> list[str]:
        candidates: list[str] = []
        for value in (
            getattr(request, "agent_id", None),
            getattr(request, "target_agent_id", None),
            getattr(request, "user_id", None),
        ):
            normalized = _normalize_agent_candidate(value)
            if normalized and normalized not in candidates:
                candidates.append(normalized)

        industry_instance_id = _first_non_empty(
            getattr(request, "industry_instance_id", None),
        )
        industry_role_id = _first_non_empty(
            getattr(request, "industry_role_id", None),
        )
        if industry_instance_id:
            resolved_agent_id = self._resolve_industry_agent_id(
                industry_instance_id=industry_instance_id,
                industry_role_id=industry_role_id or EXECUTION_CORE_ROLE_ID,
            )
            if resolved_agent_id and resolved_agent_id not in candidates:
                candidates.append(resolved_agent_id)
        return candidates

    def _get_agent_profile(self, agent_id: str) -> Any | None:
        service = self._agent_profile_service
        if service is None:
            return None
        getter = getattr(service, "get_agent", None)
        if not callable(getter):
            return None
        return getter(agent_id)

    def _list_agent_profiles(self) -> list[Any]:
        service = self._agent_profile_service
        if service is None:
            return []
        lister = getattr(service, "list_agents", None)
        if not callable(lister):
            return []
        try:
            profiles = list(lister())
        except Exception:
            logger.exception("Failed to list agent profiles for query owner resolution")
            return []
        return profiles

    def _find_industry_agent_profile(
        self,
        *,
        industry_instance_id: str,
        industry_role_id: str,
    ) -> Any | None:
        normalized_role_id = normalize_industry_role_id(industry_role_id)
        if normalized_role_id is None:
            return None
        if is_execution_core_role_id(normalized_role_id):
            return self._get_agent_profile(EXECUTION_CORE_AGENT_ID)
        for profile in self._list_agent_profiles():
            if _first_non_empty(getattr(profile, "industry_instance_id", None)) != industry_instance_id:
                continue
            profile_role_id = normalize_industry_role_id(
                _first_non_empty(getattr(profile, "industry_role_id", None)),
            )
            if profile_role_id != normalized_role_id:
                continue
            return profile
        return None

    def _resolve_industry_agent_id(
        self,
        *,
        industry_instance_id: str,
        industry_role_id: str,
    ) -> str | None:
        profile = self._find_industry_agent_profile(
            industry_instance_id=industry_instance_id,
            industry_role_id=industry_role_id,
        )
        if profile is not None:
            return _normalize_agent_candidate(getattr(profile, "agent_id", None))
        instance = self._get_industry_instance(industry_instance_id)
        if instance is None:
            return None
        normalized_role_id = normalize_industry_role_id(industry_role_id)
        for collection_name in ("team", "agents"):
            items = _field_value(instance, collection_name)
            if collection_name == "team":
                items = _field_value(items, "agents")
            if not isinstance(items, list):
                continue
            for item in items:
                candidate_role_id = normalize_industry_role_id(
                    _field_value(item, "role_id", "industry_role_id"),
                )
                if candidate_role_id != normalized_role_id:
                    continue
                agent_id = _normalize_agent_candidate(
                    _field_value(item, "agent_id", "id"),
                )
                if agent_id:
                    return agent_id
        return None

    def _resolve_fallback_execution_core_profile(self, *, request: Any) -> Any | None:
        session_kind = _first_non_empty(getattr(request, "session_kind", None))
        channel = _first_non_empty(getattr(request, "channel", None))
        industry_instance_id = _first_non_empty(getattr(request, "industry_instance_id", None))
        if industry_instance_id:
            return self._get_agent_profile(EXECUTION_CORE_AGENT_ID)
        if session_kind not in {None, "industry-agent-chat"} and channel != DEFAULT_CHANNEL:
            return None
        return self._get_agent_profile(EXECUTION_CORE_AGENT_ID)

    def _resolve_query_capability_context(
        self,
        owner_agent_id: str,
    ) -> tuple[
        set[str] | None,
        set[str] | None,
        list[str] | None,
        set[str] | None,
        bool,
        IndustrySeatCapabilityLayers | None,
    ]:
        service = self._capability_service
        if service is None:
            return None, None, None, None, False, None
        lister = getattr(service, "list_accessible_capabilities", None)
        if not callable(lister):
            return None, None, None, None, False, None
        mounts = list(lister(agent_id=owner_agent_id, enabled_only=True) or [])
        runtime_capability_layers = self._resolve_runtime_capability_layers(
            owner_agent_id=owner_agent_id,
        )
        if runtime_capability_layers is not None:
            runtime = (
                self._agent_runtime_repository.get_runtime(owner_agent_id)
                if self._agent_runtime_repository is not None
                else None
            )
            runtime_metadata = _mapping_value(getattr(runtime, "metadata", None))
            effective_capability_ids = set(
                resolve_runtime_effective_capability_ids(runtime_metadata),
            )
            mounts = [
                mount
                for mount in mounts
                if str(getattr(mount, "id", "")) in effective_capability_ids
            ]
        tool_capability_ids = {
            str(mount.id)
            for mount in mounts
            if getattr(mount, "source_kind", None) == "tool"
        }
        skill_names = {
            _capability_name_from_id(str(mount.id), prefix="skill:")
            for mount in mounts
            if getattr(mount, "source_kind", None) == "skill"
        }
        mcp_client_keys = sorted(
            _capability_name_from_id(str(mount.id), prefix="mcp:")
            for mount in mounts
            if getattr(mount, "source_kind", None) == "mcp"
        )
        system_capability_ids = {
            str(mount.id)
            for mount in mounts
            if getattr(mount, "source_kind", None) == "system"
        }
        desktop_actuation_available = any(
            _mount_supports_desktop_actuation(mount)
            for mount in mounts
        )
        return (
            tool_capability_ids,
            skill_names,
            mcp_client_keys,
            system_capability_ids,
            desktop_actuation_available,
            runtime_capability_layers,
        )

    def _resolve_runtime_capability_layers(
        self,
        *,
        owner_agent_id: str,
    ) -> IndustrySeatCapabilityLayers | None:
        repository = self._agent_runtime_repository
        getter = getattr(repository, "get_runtime", None)
        if not callable(getter):
            return None
        runtime = getter(owner_agent_id)
        if runtime is None:
            return None
        metadata = _mapping_value(getattr(runtime, "metadata", None))
        capability_layers = metadata.get("capability_layers")
        if capability_layers is None:
            return None
        try:
            return IndustrySeatCapabilityLayers.from_metadata(capability_layers)
        except Exception:
            logger.exception(
                "Failed to resolve runtime capability layers for '%s'",
                owner_agent_id,
            )
            return None

    def _prune_execution_core_control_capability_context(
        self,
        *,
        request: Any,
        owner_agent_id: str,
        agent_profile: Any | None,
        tool_capability_ids: set[str] | None,
        skill_names: set[str] | None,
        mcp_client_keys: list[str] | None,
        system_capability_ids: set[str] | None,
        desktop_actuation_available: bool,
    ) -> tuple[
        set[str] | None,
        set[str] | None,
        list[str] | None,
        set[str] | None,
        bool,
    ]:
        industry_instance_id = _first_non_empty(
            getattr(request, "industry_instance_id", None),
            getattr(agent_profile, "industry_instance_id", None)
            if agent_profile is not None
            else None,
        )
        industry_role_id = _first_non_empty(
            getattr(request, "industry_role_id", None),
            getattr(agent_profile, "industry_role_id", None)
            if agent_profile is not None
            else None,
        )
        if not industry_instance_id:
            return (
                tool_capability_ids,
                skill_names,
                mcp_client_keys,
                system_capability_ids,
                desktop_actuation_available,
            )
        if not (
            is_execution_core_agent_id(owner_agent_id)
            or industry_role_id == EXECUTION_CORE_ROLE_ID
        ):
            return (
                tool_capability_ids,
                skill_names,
                mcp_client_keys,
                system_capability_ids,
                desktop_actuation_available,
            )
        allowed_system_capability_ids = {
            "system:apply_role",
            "system:discover_capabilities",
            "system:dispatch_query",
            "system:delegate_task",
        }
        filtered_system_capability_ids = {
            capability_id
            for capability_id in (system_capability_ids or set())
            if capability_id in allowed_system_capability_ids
        }
        filtered_tool_capability_ids = {
            capability_id
            for capability_id in (tool_capability_ids or set())
            if capability_id in _EXECUTION_CORE_ALLOWED_LOCAL_TOOL_CAPABILITY_IDS
        }
        return (
            filtered_tool_capability_ids,
            set(),
            [],
            filtered_system_capability_ids,
            False,
        )

    def _resolve_delegation_first_guard(
        self,
        *,
        request: Any,
        owner_agent_id: str,
        agent_profile: Any | None,
        system_capability_ids: set[str] | None,
    ) -> _DelegationFirstGuard | None:
        if not system_capability_ids:
            return None
        if not (
            "system:dispatch_query" in system_capability_ids
            or "system:delegate_task" in system_capability_ids
        ):
            return None
        industry_instance_id = _first_non_empty(
            getattr(request, "industry_instance_id", None),
            getattr(agent_profile, "industry_instance_id", None)
            if agent_profile is not None
            else None,
        )
        industry_role_id = _first_non_empty(
            getattr(request, "industry_role_id", None),
            getattr(agent_profile, "industry_role_id", None)
            if agent_profile is not None
            else None,
        )
        if not industry_instance_id:
            return None
        if not (
            is_execution_core_agent_id(owner_agent_id)
            or industry_role_id == EXECUTION_CORE_ROLE_ID
        ):
            return None
        teammates = tuple(
            self._list_delegation_first_teammates(
                industry_instance_id=industry_instance_id,
                owner_agent_id=owner_agent_id,
            ),
        )
        if not teammates:
            return None
        return _DelegationFirstGuard(
            owner_agent_id=owner_agent_id,
            teammates=teammates,
        )

    async def _resolve_requested_main_brain_intake_contract(
        self,
        *,
        msgs: list[Any],
        request: Any,
    ):
        _ = msgs
        intake_contract = read_attached_main_brain_intake_contract(request=request)
        if intake_contract is None:
            return None
        if intake_contract.writeback_requested and not intake_contract.has_active_writeback_plan:
            raise RuntimeError(
                "Structured chat writeback was explicitly requested but could not be materialized.",
            )
        return intake_contract

    def _resolve_requested_chat_writeback_plan(
        self,
        *,
        msgs: list[Any],
        request: Any,
    ) -> ChatWritebackPlan | None:
        _ = msgs
        intake_contract = read_attached_main_brain_intake_contract(request=request)
        if intake_contract is not None and intake_contract.writeback_requested and not intake_contract.has_active_writeback_plan:
            raise RuntimeError(
                "Structured chat writeback was explicitly requested but could not be materialized.",
            )
        if intake_contract is None or not intake_contract.has_active_writeback_plan:
            return None
        return intake_contract.writeback_plan

    async def _apply_requested_main_brain_intake(
        self,
        *,
        msgs: list[Any],
        request: Any,
        owner_agent_id: str,
        agent_profile: Any | None,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        industry_instance_id = resolve_execution_core_industry_instance_id(
            request=request,
            owner_agent_id=owner_agent_id,
            agent_profile=agent_profile,
        )
        if industry_instance_id is None:
            return None, None
        service = self._industry_service
        if service is None:
            return None, None
        intake_contract = await self._resolve_requested_main_brain_intake_contract(
            msgs=msgs,
            request=request,
        )
        if intake_contract is None:
            return None, None
        accepted_persistence = build_accepted_persistence(
            request=request,
            source="query_execution_runtime",
            boundary="execution_runtime_intake",
        )
        self._persist_query_runtime_state(
            request=request,
            accepted_persistence=accepted_persistence,
        )
        chat_writeback_summary = None
        if intake_contract.has_active_writeback_plan:
            applier = getattr(service, "apply_execution_chat_writeback", None)
            if callable(applier):
                try:
                    apply_kwargs = build_industry_chat_action_kwargs(
                        industry_instance_id=industry_instance_id,
                        message_text=intake_contract.message_text,
                        owner_agent_id=owner_agent_id,
                        request=request,
                    )
                    try:
                        result = applier(
                            **apply_kwargs,
                            writeback_plan=intake_contract.writeback_plan,
                        )
                    except TypeError as exc:
                        if "writeback_plan" not in str(exc):
                            raise
                        result = applier(**apply_kwargs)
                    if asyncio.iscoroutine(result):
                        result = await result
                    chat_writeback_summary = normalize_durable_commit_result(
                        result,
                        action_type="writeback_operating_truth",
                        commit_key="query_execution_runtime:writeback",
                        default_record_id=None,
                        empty_reason="writeback_handler_returned_no_result",
                    )
                    chat_writeback_summary["action_type"] = "writeback_operating_truth"
                except Exception as exc:
                    logger.exception(
                        "Failed to persist execution-core chat writeback for industry '%s'",
                        industry_instance_id,
                    )
                    chat_writeback_summary = {
                        "status": "commit_failed",
                        "action_type": "writeback_operating_truth",
                        "reason": "writeback_handler_exception",
                        "message": str(exc).strip()
                        or "Execution-core chat writeback raised before durable persistence.",
                        "commit_key": "query_execution_runtime:writeback",
                    }
        industry_kickoff_summary = None
        if intake_contract.should_kickoff:
            kickoff = getattr(service, "kickoff_execution_from_chat", None)
            if callable(kickoff):
                try:
                    result = kickoff(
                        **build_industry_chat_action_kwargs(
                            industry_instance_id=industry_instance_id,
                            message_text=intake_contract.message_text,
                            owner_agent_id=owner_agent_id,
                            request=request,
                        ),
                    )
                    if asyncio.iscoroutine(result):
                        result = await result
                    industry_kickoff_summary = normalize_durable_commit_result(
                        result,
                        action_type="orchestrate_execution",
                        commit_key="query_execution_runtime:kickoff",
                        default_record_id=None,
                        empty_reason="kickoff_handler_returned_no_result",
                    )
                    industry_kickoff_summary["action_type"] = "orchestrate_execution"
                except Exception as exc:
                    logger.exception(
                        "Failed to kick off industry execution for '%s' from chat",
                        industry_instance_id,
                    )
                    industry_kickoff_summary = {
                        "status": "commit_failed",
                        "action_type": "orchestrate_execution",
                        "reason": "kickoff_handler_exception",
                        "message": str(exc).strip()
                        or "Execution kickoff raised before durable persistence.",
                        "commit_key": "query_execution_runtime:kickoff",
                    }
        commit_outcome = self._combine_requested_main_brain_commit_outcome(
            chat_writeback_summary=chat_writeback_summary,
            industry_kickoff_summary=industry_kickoff_summary,
        )
        if commit_outcome is not None:
            self._persist_query_runtime_state(
                request=request,
                commit_outcome=commit_outcome,
            )
        return chat_writeback_summary, industry_kickoff_summary

    def _combine_requested_main_brain_commit_outcome(
        self,
        *,
        chat_writeback_summary: dict[str, Any] | None,
        industry_kickoff_summary: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        outcomes = [
            outcome
            for outcome in (chat_writeback_summary, industry_kickoff_summary)
            if isinstance(outcome, dict) and outcome
        ]
        if not outcomes:
            return None
        for status in ("commit_failed", "governance_denied", "confirm_required", "commit_deferred"):
            for outcome in outcomes:
                if str(outcome.get("status") or "").strip() == status:
                    combined = dict(outcome)
                    if len(outcomes) > 1:
                        combined["action_type"] = "writeback_and_kickoff"
                    return combined
        if len(outcomes) == 1:
            return dict(outcomes[0])
        record_id = _first_non_empty(
            outcomes[0].get("record_id"),
            outcomes[1].get("record_id"),
        )
        return {
            "status": "committed",
            "action_type": "writeback_and_kickoff",
            "summary": "Durably persisted requested main-brain intake writeback and kickoff.",
            "record_id": record_id,
            "commit_key": "query_execution_runtime:intake",
        }

    def _persist_query_runtime_state(
        self,
        *,
        request: Any,
        accepted_persistence: dict[str, Any] | None = None,
        commit_outcome: dict[str, Any] | None = None,
    ) -> None:
        runtime_context = update_request_runtime_context(
            request,
            accepted_persistence=accepted_persistence,
            commit_outcome=commit_outcome,
        )
        query_runtime_state = _mapping_value(runtime_context.get("query_runtime_state"))
        if accepted_persistence is not None:
            query_runtime_state["accepted_persistence"] = dict(accepted_persistence)
        if commit_outcome is not None:
            query_runtime_state["commit_outcome"] = dict(commit_outcome)
        if not query_runtime_state:
            return
        runtime_context["query_runtime_state"] = query_runtime_state
        set_request_runtime_value(
            request,
            "_copaw_main_brain_runtime_context",
            runtime_context,
        )
        set_request_runtime_value(
            request,
            "_copaw_query_runtime_state",
            query_runtime_state,
        )
        self._save_query_runtime_state_snapshot(
            request=request,
            query_runtime_state=query_runtime_state,
        )

    def _save_query_runtime_state_snapshot(
        self,
        *,
        request: Any,
        query_runtime_state: dict[str, Any],
    ) -> None:
        session_backend = self._session_backend
        if session_backend is None:
            return
        session_id = _first_non_empty(getattr(request, "session_id", None))
        user_id = _first_non_empty(getattr(request, "user_id", None))
        if session_id is None or user_id is None:
            return
        saver = getattr(session_backend, "save_session_snapshot", None)
        if not callable(saver):
            return
        snapshot: dict[str, Any] = {}
        loader = getattr(session_backend, "load_session_snapshot", None)
        if callable(loader):
            try:
                existing = loader(
                    session_id=session_id,
                    user_id=user_id,
                    allow_not_exist=True,
                )
            except TypeError:
                try:
                    existing = loader(
                        session_id=session_id,
                        user_id=user_id,
                    )
                except Exception:
                    existing = None
            if isinstance(existing, dict):
                snapshot = dict(existing)
        persisted_state = _mapping_value(snapshot.get("query_runtime_state"))
        persisted_state.update(query_runtime_state)
        snapshot["query_runtime_state"] = persisted_state
        try:
            saver(
                session_id=session_id,
                user_id=user_id,
                payload=snapshot,
                source_ref="state:/query-runtime",
            )
        except Exception:
            logger.exception(
                "Failed to persist query runtime state snapshot for session '%s'",
                session_id,
            )
