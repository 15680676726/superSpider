# -*- coding: utf-8 -*-
from __future__ import annotations

from ..evidence import EvidenceRecord
from ..providers import ProviderManager
from .query_execution_shared import *  # noqa: F401,F403


class _QueryExecutionUsageRuntimeMixin:
    def record_turn_usage(
        self,
        *,
        request: Any,
        kernel_task_id: str | None,
        usage: Any,
    ) -> None:
        usage_payload = _normalize_usage_payload(usage)
        if not usage_payload:
            return
        now = _utc_now()
        owner_agent_id = self.resolve_request_owner_agent_id(request=request)
        cost_estimate = _extract_usage_cost_estimate(usage_payload)
        model_context = self._resolve_query_model_usage_context(
            request=request,
            owner_agent_id=owner_agent_id,
        )
        self._record_agent_runtime_usage(
            owner_agent_id=owner_agent_id,
            usage_payload=usage_payload,
            cost_estimate=cost_estimate,
            model_context=model_context,
            recorded_at=now,
        )
        self._record_query_usage_evidence(
            request=request,
            kernel_task_id=kernel_task_id,
            owner_agent_id=owner_agent_id,
            usage_payload=usage_payload,
            cost_estimate=cost_estimate,
            model_context=model_context,
            recorded_at=now,
        )

    def _record_agent_runtime_usage(
        self,
        *,
        owner_agent_id: str | None,
        usage_payload: dict[str, Any],
        cost_estimate: float | None,
        model_context: dict[str, Any],
        recorded_at: datetime,
    ) -> None:
        if self._agent_runtime_repository is None or not owner_agent_id:
            return
        runtime = self._agent_runtime_repository.get_runtime(owner_agent_id)
        if runtime is None:
            return
        metadata = dict(runtime.metadata or {})
        metadata["last_query_usage"] = usage_payload
        metadata["last_query_usage_at"] = recorded_at.isoformat()
        if model_context:
            metadata["last_query_model_context"] = model_context
        if cost_estimate is not None:
            metadata["last_query_cost_estimate"] = cost_estimate
            metadata["query_cost_total_estimate"] = round(
                _usage_float(metadata.get("query_cost_total_estimate"), 0.0)
                + cost_estimate,
                12,
            )
        metadata["query_usage_totals"] = _merge_usage_totals(
            metadata.get("query_usage_totals"),
            usage_payload,
        )
        self._agent_runtime_repository.upsert_runtime(
            runtime.model_copy(
                update={
                    "metadata": metadata,
                    "updated_at": recorded_at,
                },
            ),
        )

    def _record_query_usage_evidence(
        self,
        *,
        request: Any,
        kernel_task_id: str | None,
        owner_agent_id: str | None,
        usage_payload: dict[str, Any],
        cost_estimate: float | None,
        model_context: dict[str, Any],
        recorded_at: datetime,
    ) -> None:
        if self._evidence_ledger is None or not kernel_task_id:
            return
        task_runtime = None
        if self._task_runtime_repository is not None:
            task_runtime = self._task_runtime_repository.get_runtime(kernel_task_id)
        risk_level = _first_non_empty(
            getattr(task_runtime, "risk_level", None),
            "auto",
        ) or "auto"
        owner_agent_id = (
            _first_non_empty(
                getattr(task_runtime, "last_owner_agent_id", None),
                owner_agent_id,
            )
            or owner_agent_id
        )
        record = self._evidence_ledger.append(
            EvidenceRecord(
                task_id=kernel_task_id,
                actor_ref=(
                    f"agent:{owner_agent_id}"
                    if owner_agent_id
                    else "agent:interactive-query"
                ),
                environment_ref=(
                    f"session:{_first_non_empty(getattr(request, 'channel', None), DEFAULT_CHANNEL)}:"
                    f"{_first_non_empty(getattr(request, 'session_id', None), 'unknown')}"
                ),
                capability_ref="system:dispatch_query",
                risk_level=risk_level,
                action_summary="Record interactive query token usage",
                result_summary=_summarize_usage_payload(
                    usage_payload,
                    cost_estimate=cost_estimate,
                ),
                created_at=recorded_at,
                metadata={
                    "usage_kind": "interactive-query",
                    "usage": usage_payload,
                    "cost_estimate": cost_estimate,
                    "owner_agent_id": owner_agent_id,
                    "channel": _first_non_empty(getattr(request, "channel", None), DEFAULT_CHANNEL),
                    "session_id": _first_non_empty(getattr(request, "session_id", None)),
                    "user_id": _first_non_empty(getattr(request, "user_id", None)),
                    "session_kind": _first_non_empty(getattr(request, "session_kind", None)),
                    "industry_instance_id": _first_non_empty(
                        getattr(request, "industry_instance_id", None),
                    ),
                    "industry_role_id": _first_non_empty(
                        getattr(request, "industry_role_id", None),
                    ),
                    "model_context": model_context,
                },
            ),
        )
        if task_runtime is None or self._task_runtime_repository is None:
            return
        self._task_runtime_repository.upsert_runtime(
            task_runtime.model_copy(
                update={
                    "last_evidence_id": record.id,
                    "updated_at": recorded_at,
                },
            ),
        )

    def _resolve_query_model_usage_context(
        self,
        *,
        request: Any,
        owner_agent_id: str | None,
    ) -> dict[str, Any]:
        del request, owner_agent_id
        try:
            manager = self._provider_manager or ProviderManager()
            slot, using_fallback, reason, unavailable = manager.resolve_model_slot()
        except Exception:
            return {}
        return {
            "provider_id": slot.provider_id,
            "model": slot.model,
            "slot_source": "fallback" if using_fallback else "active",
            "selection_reason": reason,
            "unavailable_slots": list(unavailable),
        }


def _usage_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, dict):
        return {
            str(key): _usage_jsonable(item)
            for key, item in value.items()
            if item is not None
        }
    if isinstance(value, (list, tuple, set)):
        return [_usage_jsonable(item) for item in value]
    mapped = _mapping_value(value)
    if mapped:
        return _usage_jsonable(mapped)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _usage_int(*values: Any) -> int | None:
    for value in values:
        if value is None or isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        text = str(value).strip()
        if not text:
            continue
        try:
            return int(float(text))
        except ValueError:
            continue
    return None


def _usage_float(*values: Any) -> float | None:
    for value in values:
        if value is None or isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip()
        if not text:
            continue
        try:
            return float(text)
        except ValueError:
            continue
    return None


def _normalize_usage_payload(value: Any) -> dict[str, Any]:
    payload = _mapping_value(value)
    if not payload:
        return {}
    normalized = _usage_jsonable(payload)
    if not isinstance(normalized, dict):
        return {}
    prompt_tokens = _usage_int(
        normalized.get("prompt_tokens"),
        normalized.get("input_tokens"),
    )
    completion_tokens = _usage_int(
        normalized.get("completion_tokens"),
        normalized.get("output_tokens"),
    )
    total_tokens = _usage_int(normalized.get("total_tokens"))
    cached_tokens = _usage_int(
        normalized.get("cached_tokens"),
        normalized.get("cached_input_tokens"),
    )
    reasoning_tokens = _usage_int(normalized.get("reasoning_tokens"))
    if prompt_tokens is not None:
        normalized.setdefault("prompt_tokens", prompt_tokens)
    if completion_tokens is not None:
        normalized.setdefault("completion_tokens", completion_tokens)
    if total_tokens is None and (
        prompt_tokens is not None or completion_tokens is not None
    ):
        total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)
    if total_tokens is not None:
        normalized["total_tokens"] = total_tokens
    if cached_tokens is not None:
        normalized["cached_tokens"] = cached_tokens
    if reasoning_tokens is not None:
        normalized["reasoning_tokens"] = reasoning_tokens
    cost_estimate = _extract_usage_cost_estimate(normalized)
    if cost_estimate is not None:
        normalized["cost_estimate"] = cost_estimate
    return normalized


def _extract_usage_cost_estimate(usage_payload: dict[str, Any]) -> float | None:
    return _usage_float(
        usage_payload.get("cost_estimate"),
        usage_payload.get("estimated_cost"),
        usage_payload.get("cost"),
        usage_payload.get("total_cost"),
    )


def _merge_usage_totals(
    existing: Any,
    usage_payload: dict[str, Any],
) -> dict[str, Any]:
    totals = _mapping_value(existing)
    for key in (
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cached_tokens",
        "reasoning_tokens",
    ):
        amount = _usage_int(usage_payload.get(key))
        if amount is None:
            continue
        totals[key] = _usage_int(totals.get(key), 0) + amount
    return totals


def _summarize_usage_payload(
    usage_payload: dict[str, Any],
    *,
    cost_estimate: float | None,
) -> str:
    parts: list[str] = []
    prompt_tokens = _usage_int(usage_payload.get("prompt_tokens"))
    completion_tokens = _usage_int(usage_payload.get("completion_tokens"))
    total_tokens = _usage_int(usage_payload.get("total_tokens"))
    cached_tokens = _usage_int(usage_payload.get("cached_tokens"))
    reasoning_tokens = _usage_int(usage_payload.get("reasoning_tokens"))
    if prompt_tokens is not None:
        parts.append(f"prompt={prompt_tokens}")
    if completion_tokens is not None:
        parts.append(f"completion={completion_tokens}")
    if total_tokens is not None:
        parts.append(f"total={total_tokens}")
    if cached_tokens is not None:
        parts.append(f"cached={cached_tokens}")
    if reasoning_tokens is not None:
        parts.append(f"reasoning={reasoning_tokens}")
    if cost_estimate is not None:
        parts.append(f"cost={cost_estimate:g}")
    if not parts:
        return "Recorded interactive query usage."
    return f"Recorded interactive query usage ({', '.join(parts)})."
