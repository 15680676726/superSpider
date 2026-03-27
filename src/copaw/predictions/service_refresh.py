# -*- coding: utf-8 -*-
from __future__ import annotations

from ..kernel.decision_policy import (
    decision_chat_route,
    decision_chat_thread_id,
    decision_requires_human_confirmation,
)
from ..kernel.persistence import decode_kernel_task_metadata
from .service_shared import *  # noqa: F401,F403


class _PredictionServiceRefreshMixin:
    def _case_confidence(
        self,
        signals: list[PredictionSignalRecord],
        recommendations: list[PredictionRecommendationRecord],
    ) -> float:
        if not signals and not recommendations:
            return 0.4
        top_signals = sorted((item.strength for item in signals), reverse=True)[:3]
        signal_component = (sum(top_signals) / len(top_signals)) if top_signals else 0.2
        recommendation_component = (
            sum(item.confidence for item in recommendations) / len(recommendations)
            if recommendations
            else 0.45
        )
        coverage_bonus = min(0.16, (len(signals) * 0.015) + (len(recommendations) * 0.03))
        value = 0.3 + (signal_component * 0.45) + (recommendation_component * 0.12) + coverage_bonus
        return max(0.25, min(0.95, round(value, 3)))

    def _case_signal_strength(self, case_id: str) -> float:
        signals = self._signal_repository.list_signals(case_id=case_id)
        if not signals:
            return 0.0
        top_signals = sorted((item.strength for item in signals), reverse=True)[:3]
        return round(sum(top_signals) / len(top_signals), 3)

    def _set_recommendation_status(
        self,
        record: PredictionRecommendationRecord,
        status: str,
        summary: str,
    ) -> PredictionRecommendationRecord:
        updated = record.model_copy(
            update={
                "status": status,
                "outcome_summary": summary,
                "updated_at": _utc_now(),
            },
        )
        self._recommendation_repository.upsert_recommendation(updated)
        return updated

    def _status_from_phase(self, phase: object | None, *, fallback: str) -> str:
        normalized = str(phase or "").strip().lower()
        mapping = {
            "pending": "queued",
            "risk-check": "queued",
            "executing": "queued",
            "waiting-confirm": "waiting-confirm",
            "completed": "executed",
            "failed": "failed",
            "cancelled": "rejected",
            "approved": "approved",
            "rejected": "rejected",
            "expired": "rejected",
        }
        return mapping.get(normalized, fallback)

    def _recommendation_execution_metadata(
        self,
        record: PredictionRecommendationRecord,
        *,
        execution: dict[str, Any],
    ) -> dict[str, Any]:
        metadata = dict(record.metadata or {})
        output = _safe_dict(execution.get("output"))
        if output:
            metadata["last_execution_output"] = output
            installed_capability_ids = _string_list(output.get("installed_capability_ids"))
            if installed_capability_ids:
                metadata["installed_capability_ids"] = installed_capability_ids
            resolved_candidate = _safe_dict(output.get("resolved_candidate"))
            if resolved_candidate:
                metadata["resolved_candidate"] = resolved_candidate
            assignment_result = output.get("assignment_result")
            if isinstance(assignment_result, dict):
                metadata["assignment_result"] = dict(assignment_result)
        return metadata

    def _refresh_recommendation(
        self,
        record: PredictionRecommendationRecord,
    ) -> tuple[PredictionRecommendationRecord, bool]:
        if record.status == "manual-only":
            return record, False
        update: dict[str, Any] = {}
        if record.decision_request_id and self._decision_request_repository is not None:
            decision = self._decision_request_repository.get_decision_request(record.decision_request_id)
            if decision is not None:
                mapped_status = self._status_from_phase(decision.status, fallback=record.status)
                if mapped_status != record.status:
                    update["status"] = mapped_status
                if decision.resolution and not record.outcome_summary:
                    update["outcome_summary"] = decision.resolution
        if record.execution_task_id and self._task_runtime_repository is not None:
            runtime = self._task_runtime_repository.get_runtime(record.execution_task_id)
            if runtime is not None:
                mapped_status = self._status_from_phase(
                    runtime.current_phase or runtime.runtime_status,
                    fallback=str(update.get("status") or record.status),
                )
                if mapped_status != str(update.get("status") or record.status):
                    update["status"] = mapped_status
                if runtime.last_result_summary and mapped_status == "executed":
                    update["outcome_summary"] = runtime.last_result_summary
                if runtime.last_error_summary and mapped_status == "failed":
                    update["outcome_summary"] = runtime.last_error_summary
                if runtime.last_evidence_id and not record.execution_evidence_id:
                    update["execution_evidence_id"] = runtime.last_evidence_id
        if not update:
            return record, False
        updated = record.model_copy(update={**update, "updated_at": _utc_now()})
        self._recommendation_repository.upsert_recommendation(updated)
        return updated, True

    def _decision_payload(self, decision_request_id: str | None) -> dict[str, Any] | None:
        if not decision_request_id or self._decision_request_repository is None:
            return None
        decision = self._decision_request_repository.get_decision_request(decision_request_id)
        if decision is None:
            return None
        payload = decision.model_dump(mode="json")
        payload["route"] = f"/api/runtime-center/decisions/{decision.id}"
        task_payload: dict[str, Any] = {}
        if decision.task_id and self._task_repository is not None:
            task = self._task_repository.get_task(decision.task_id)
            if task is not None:
                task_payload = _safe_dict(
                    decode_kernel_task_metadata(getattr(task, "acceptance_criteria", None)),
                )
        chat_payload = _prediction_decision_chat_payload(task_payload)
        chat_thread_id = decision_chat_thread_id(chat_payload)
        chat_route = decision_chat_route(chat_thread_id)
        requires_human_confirmation = decision_requires_human_confirmation(
            decision_type=decision.decision_type,
            payload=chat_payload,
        )
        payload["governance_route"] = payload["route"]
        payload["chat_thread_id"] = chat_thread_id
        payload["chat_route"] = chat_route
        payload["preferred_route"] = chat_route if requires_human_confirmation else payload["route"]
        payload["requires_human_confirmation"] = requires_human_confirmation
        return payload

    def _recommendation_view(
        self,
        record: PredictionRecommendationRecord,
    ) -> PredictionRecommendationView:
        refreshed, _ = self._refresh_recommendation(record)
        payload = refreshed.model_dump(mode="json")
        routes: dict[str, str] = {
            "case": _route_prediction(refreshed.case_id),
        }
        industry_instance_id = _string(
            payload.get("metadata", {}).get("industry_instance_id")
            if isinstance(payload.get("metadata"), dict)
            else None,
        ) or _string(
            payload.get("action_payload", {}).get("instance_id")
            if isinstance(payload.get("action_payload"), dict)
            else None,
        )
        if industry_instance_id:
            routes["industry"] = f"/api/runtime-center/industry/{industry_instance_id}"
        if refreshed.executable and refreshed.status not in {"executed", "rejected", "failed", "manual-only"}:
            routes["coordinate"] = (
                f"/api/predictions/{refreshed.case_id}/recommendations/"
                f"{refreshed.recommendation_id}/coordinate"
            )
        if refreshed.decision_request_id:
            routes["decision"] = f"/api/runtime-center/decisions/{refreshed.decision_request_id}"
        if refreshed.target_goal_id:
            routes["goal"] = f"/api/runtime-center/goals/{refreshed.target_goal_id}"
        if refreshed.target_agent_id:
            routes["agent"] = f"/api/runtime-center/agents/{refreshed.target_agent_id}"
        if refreshed.execution_evidence_id:
            routes["evidence"] = f"/api/runtime-center/evidence/{refreshed.execution_evidence_id}"
        install_templates = _safe_list(payload.get("metadata", {}).get("install_templates"))
        if install_templates:
            first = _safe_dict(install_templates[0])
            market = _safe_dict(first.get("routes")).get("market")
            if isinstance(market, str) and market.strip():
                routes["market"] = market.strip()
        return PredictionRecommendationView(
            recommendation=payload,
            decision=self._decision_payload(refreshed.decision_request_id),
            routes=routes,
        )

    def _is_capability_optimization_recommendation(
        self,
        record: PredictionRecommendationRecord,
    ) -> bool:
        metadata = _safe_dict(record.metadata)
        gap_kind = str(metadata.get("gap_kind") or "").strip()
        return gap_kind in {
            "missing_capability",
            "underperforming_capability",
            "capability_rollout",
            "capability_retirement",
        }

    def _capability_optimization_gap_kind(
        self,
        item: PredictionCapabilityOptimizationItem,
    ) -> str:
        metadata = _safe_dict(item.recommendation.recommendation.get("metadata"))
        return str(metadata.get("gap_kind") or "").strip()

    def _capability_optimization_stage(
        self,
        item: PredictionCapabilityOptimizationItem,
    ) -> str:
        metadata = _safe_dict(item.recommendation.recommendation.get("metadata"))
        return str(metadata.get("optimization_stage") or "").strip()

    def _capability_optimization_status_bucket(self, status: str) -> str:
        normalized = status.strip().lower()
        if normalized in {"executed", "approved", "failed", "rejected"}:
            return "history"
        return "actionable"

    def _capability_optimization_actionable_sort_key(
        self,
        item: PredictionCapabilityOptimizationItem,
    ) -> tuple[int, int, float, str]:
        recommendation = item.recommendation.recommendation
        status = str(recommendation.get("status") or "").strip().lower()
        status_rank = {
            "waiting-confirm": 0,
            "proposed": 1,
            "queued": 2,
            "reviewing": 3,
            "manual-only": 4,
        }.get(status, 5)
        priority = int(recommendation.get("priority") or 0)
        confidence = float(recommendation.get("confidence") or 0.0)
        updated_at = str(recommendation.get("updated_at") or "")
        return (status_rank, -priority, -confidence, updated_at)

    def _capability_optimization_history_sort_key(
        self,
        item: PredictionCapabilityOptimizationItem,
    ) -> tuple[str, int]:
        recommendation = item.recommendation.recommendation
        updated_at = str(recommendation.get("updated_at") or "")
        priority = int(recommendation.get("priority") or 0)
        return (updated_at, priority)

    def _capability_client_key(self, capability_id: str | None) -> str | None:
        if not capability_id:
            return None
        normalized = capability_id.strip()
        if normalized.startswith("mcp:"):
            suffix = normalized.split(":", 1)[1].strip()
            return suffix or None
        return None

    def _hottest_agent(self, facts: _FactPack) -> dict[str, Any] | None:
        breakdown = [
            _safe_dict(item)
            for item in _safe_list(facts.performance.get("agent_breakdown"))
        ]
        if breakdown:
            breakdown.sort(
                key=lambda item: (
                    -int(item.get("failed_task_count") or 0),
                    -int(item.get("active_task_count") or 0),
                    -int(item.get("decision_count") or 0),
                    -int(item.get("evidence_count") or 0),
                    str(item.get("agent_id") or ""),
                ),
            )
            return breakdown[0]
        for agent in facts.agents:
            payload = (
                agent.model_dump(mode="json")
                if hasattr(agent, "model_dump")
                else dict(agent) if isinstance(agent, dict) else {}
            )
            if not payload:
                continue
            return payload
        return None

    def _list_recent_reviews(self, *, limit: int = 50) -> list[PredictionReviewRecord]:
        return self._review_repository.list_reviews(limit=limit)

    def _list_recent_recommendations(
        self,
        *,
        limit: int = 50,
        activity_since: datetime | None = None,
    ) -> list[PredictionRecommendationRecord]:
        items = self._recommendation_repository.list_recommendations(
            limit=limit,
            activity_since=activity_since,
        )
        refreshed: list[PredictionRecommendationRecord] = []
        for item in items:
            refreshed.append(self._refresh_recommendation(item)[0])
        refreshed.sort(key=lambda item: (item.updated_at, item.recommendation_id), reverse=True)
        return refreshed[:limit]


def _prediction_decision_chat_payload(task_meta: dict[str, Any]) -> dict[str, Any]:
    payload = _safe_dict(task_meta.get("payload"))
    request = _safe_dict(payload.get("request"))
    request_context = _safe_dict(payload.get("request_context"))
    meta = _safe_dict(payload.get("meta"))
    return {
        "decision_type": payload.get("decision_type"),
        "control_thread_id": (
            meta.get("control_thread_id")
            or request_context.get("control_thread_id")
            or request.get("control_thread_id")
            or payload.get("control_thread_id")
        ),
        "thread_id": (
            meta.get("thread_id")
            or request_context.get("thread_id")
            or request.get("thread_id")
            or payload.get("thread_id")
        ),
        "session_id": (
            request_context.get("session_id")
            or request.get("session_id")
            or payload.get("session_id")
        ),
        "session_kind": (
            request_context.get("session_kind")
            or request.get("session_kind")
            or payload.get("session_kind")
        ),
    }
