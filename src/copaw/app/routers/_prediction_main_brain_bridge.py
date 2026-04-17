# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from hashlib import sha1
from typing import Any
from urllib.parse import quote

from ...industry.identity import EXECUTION_CORE_AGENT_ID, EXECUTION_CORE_ROLE_ID


def _mapping(value: object | None) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json")
        if isinstance(payload, dict):
            return dict(payload)
    return {}


def _string(*values: object | None) -> str | None:
    for value in values:
        if not isinstance(value, str):
            continue
        normalized = value.strip()
        if normalized:
            return normalized
    return None


def _prediction_backlog_priority(priority: object | None) -> int:
    try:
        value = int(priority or 0)
    except (TypeError, ValueError):
        return 2
    return max(2, min(5, max(1, int(round(value / 25.0)))))


def _stable_prediction_source_ref(
    *,
    action_kind: str | None,
    target_agent_id: str | None,
    target_goal_id: str | None,
    title: str,
    action_payload: dict[str, object],
) -> str:
    normalized = {
        "action_kind": _string(action_kind),
        "target_agent_id": _string(target_agent_id),
        "target_goal_id": _string(target_goal_id),
        "title": title.strip().lower(),
        "action_payload": dict(action_payload),
    }
    serialized = json.dumps(normalized, ensure_ascii=False, sort_keys=True, default=str)
    return f"prediction:{sha1(serialized.encode('utf-8')).hexdigest()[:16]}"


def _resolve_prediction_lane_id(
    industry_service: object,
    *,
    industry_instance_id: str,
    recommendation: dict[str, object],
) -> str | None:
    lane_service = getattr(industry_service, "_operating_lane_service", None)
    if lane_service is None:
        return None
    metadata = _mapping(recommendation.get("metadata"))
    action_payload = _mapping(recommendation.get("action_payload"))
    target_agent_id = (
        _string(recommendation.get("target_agent_id"))
        or _string(metadata.get("target_agent_id"))
        or _string(action_payload.get("agent_id"))
    )
    lane = lane_service.resolve_lane(
        industry_instance_id=industry_instance_id,
        lane_key=_string(metadata.get("goal_kind")) or _string(metadata.get("family_id")),
        role_id=_string(metadata.get("industry_role_id")) or _string(action_payload.get("role_id")),
        owner_agent_id=target_agent_id,
    )
    return _string(getattr(lane, "id", None))


def _build_prediction_backlog_spec(
    industry_service: object,
    *,
    industry_instance_id: str,
    actor: str,
    case_id: str,
    case_payload: dict[str, object],
    recommendation: dict[str, object],
    source_route: str | None,
    meeting_window: str | None,
) -> dict[str, object]:
    metadata = _mapping(recommendation.get("metadata"))
    action_payload = _mapping(recommendation.get("action_payload"))
    target_agent_id = (
        _string(recommendation.get("target_agent_id"))
        or _string(metadata.get("target_agent_id"))
        or _string(action_payload.get("agent_id"))
    )
    title = _string(recommendation.get("title")) or "周期机会"
    return {
        "lane_id": _resolve_prediction_lane_id(
            industry_service,
            industry_instance_id=industry_instance_id,
            recommendation=recommendation,
        ),
        "title": title,
        "summary": (
            _string(recommendation.get("summary"))
            or "预测发现了一个需要主脑接管的治理机会。"
        ),
        "priority": _prediction_backlog_priority(recommendation.get("priority")),
        "source_ref": _stable_prediction_source_ref(
            action_kind=_string(recommendation.get("action_kind")),
            target_agent_id=target_agent_id,
            target_goal_id=_string(recommendation.get("target_goal_id")),
            title=title,
            action_payload=action_payload,
        ),
        "metadata": {
            "source": "prediction",
            "trigger_source": f"prediction-coordinate:{case_id}",
            "trigger_actor": actor,
            "trigger_reason": "Operator explicitly asked the main brain to take over this prediction recommendation.",
            "prediction_case_id": case_id,
            "prediction_recommendation_id": _string(recommendation.get("recommendation_id")),
            "prediction_case_kind": _string(case_payload.get("case_kind")),
            "prediction_status": _string(recommendation.get("status")),
            "prediction_confidence": recommendation.get("confidence"),
            "meeting_window": meeting_window,
            "action_kind": _string(recommendation.get("action_kind")),
            "risk_level": _string(recommendation.get("risk_level")),
            "executable": bool(recommendation.get("executable")),
            "owner_agent_id": target_agent_id,
            "target_goal_id": _string(recommendation.get("target_goal_id")),
            "industry_role_id": (
                _string(metadata.get("industry_role_id"))
                or _string(action_payload.get("role_id"))
            ),
            "industry_role_name": (
                _string(metadata.get("industry_role_name"))
                or _string(metadata.get("suggested_role_name"))
            ),
            "goal_kind": _string(metadata.get("goal_kind")) or _string(metadata.get("family_id")),
            "report_back_mode": "summary",
            "source_route": source_route,
            "plan_steps": [
                "Review the main-brain meeting recommendation and lock the concrete objective.",
                "Execute the next governed move and leave evidence.",
                "Report the result, blocker, or follow-up back to the main brain.",
            ],
        },
    }


def _append_control_thread_message(
    industry_service: object,
    *,
    industry_instance_id: str,
    case_id: str,
    case_title: str,
    recommendation: dict[str, object],
    backlog_item_id: str,
    backlog_status: str | None,
    started_cycle_id: str | None,
    coordination_reason: str | None,
    actor: str,
) -> None:
    session_backend = getattr(industry_service, "_session_backend", None)
    if session_backend is None:
        return
    loader = getattr(session_backend, "load_session_snapshot", None)
    saver = getattr(session_backend, "save_session_snapshot", None)
    if not callable(loader) or not callable(saver):
        return
    session_id = f"industry-chat:{industry_instance_id}:{EXECUTION_CORE_ROLE_ID}"
    payload = loader(
        session_id=session_id,
        user_id=EXECUTION_CORE_AGENT_ID,
        allow_not_exist=True,
    )
    if not isinstance(payload, dict):
        payload = {}
    payload = dict(payload)
    agent_state = payload.get("agent")
    if not isinstance(agent_state, dict):
        agent_state = {}
    memory_state = agent_state.get("memory")
    if isinstance(memory_state, list):
        messages = list(memory_state)
        agent_state["memory"] = messages
    elif isinstance(memory_state, dict):
        normalized_memory = dict(memory_state)
        content = normalized_memory.get("content")
        messages = list(content) if isinstance(content, list) else []
        normalized_memory["content"] = messages
        agent_state["memory"] = normalized_memory
    else:
        messages = []
        agent_state["memory"] = messages
    recommendation_id = _string(recommendation.get("recommendation_id")) or case_id
    message_id = f"prediction-coordinate:{recommendation_id}"
    if any(
        isinstance(item, dict) and _string(item.get("id")) == message_id
        for item in messages
    ):
        return
    title = _string(recommendation.get("title")) or recommendation_id
    summary = _string(recommendation.get("summary"))
    risk_level = _string(recommendation.get("risk_level")) or "auto"
    lines = [
        "运营者刚把一条预测建议交给主脑处理。",
        f"- 复盘案例：{case_title}",
        f"- 建议标题：{title}",
        f"- 风险级别：{risk_level}",
        f"- backlog：{backlog_item_id}（{backlog_status or 'open'}）",
        f"- 请求来源：{actor}",
    ]
    if summary:
        lines.append(f"- 建议摘要：{summary}")
    if started_cycle_id:
        lines.append(f"- 当前结果：已进入主脑 operating cycle {started_cycle_id}")
    elif coordination_reason:
        lines.append(f"- 当前结果：已登记，等待主脑继续协调（{coordination_reason}）")
    else:
        lines.append("- 当前结果：已登记，等待主脑继续协调。")
    lines.append("请主脑决定是否物化为目标、分派执行位，并继续监督回流。")
    messages.append(
        {
            "id": message_id,
            "role": "assistant",
            "object": "message",
            "type": "message",
            "status": "completed",
            "content": [{"type": "text", "text": "\n".join(lines)}],
            "metadata": {
                "synthetic": True,
                "message_kind": "prediction-coordinate",
                "industry_instance_id": industry_instance_id,
                "prediction_case_id": case_id,
                "prediction_recommendation_id": recommendation_id,
                "backlog_item_id": backlog_item_id,
                "started_cycle_id": started_cycle_id,
                "coordination_reason": coordination_reason,
                "requested_by": actor,
            },
        },
    )
    payload["agent"] = agent_state
    saver(
        session_id=session_id,
        user_id=EXECUTION_CORE_AGENT_ID,
        payload=payload,
        source_ref=f"prediction-coordinate:{recommendation_id}",
    )
    try:
        from ...app.console_push_store import append_now

        append_now(
            session_id,
            f"Main brain received prediction handoff: {title}",
        )
    except Exception:
        pass


async def coordinate_prediction_recommendation(
    industry_service: object,
    *,
    industry_instance_id: str,
    actor: str,
    case_id: str,
    case_payload: dict[str, object],
    recommendation: dict[str, object],
    source_route: str | None = None,
    meeting_window: str | None = None,
) -> dict[str, object]:
    repository = getattr(industry_service, "_industry_instance_repository", None)
    if repository is None:
        raise RuntimeError("Industry repository is not available")
    record = repository.get_instance(industry_instance_id)
    if record is None:
        raise KeyError(f"Industry instance '{industry_instance_id}' was not found")
    backlog_service = getattr(industry_service, "_backlog_service", None)
    if backlog_service is None:
        raise RuntimeError("Backlog service is not available")
    backlog_repository = getattr(industry_service, "_backlog_item_repository", None)
    spec = _build_prediction_backlog_spec(
        industry_service,
        industry_instance_id=industry_instance_id,
        actor=actor,
        case_id=case_id,
        case_payload=case_payload,
        recommendation=recommendation,
        source_route=source_route,
        meeting_window=meeting_window,
    )
    detail_getter = getattr(industry_service, "get_instance_detail", None)
    detail = detail_getter(industry_instance_id) if callable(detail_getter) else None
    detail_payload = _mapping(detail)
    backlog_entries = list(detail_payload.get("backlog") or [])
    existing_view = next(
        (
            _mapping(item)
            for item in backlog_entries
            if _string(_mapping(item).get("source_kind")) == "prediction"
            and _string(_mapping(item).get("source_ref")) == _string(spec.get("source_ref"))
        ),
        None,
    )
    reused_backlog = existing_view is not None
    if existing_view is None:
        backlog_item = backlog_service.record_generated_item(
            industry_instance_id=industry_instance_id,
            lane_id=_string(spec.get("lane_id")),
            title=_string(spec.get("title")) or "周期机会",
            summary=_string(spec.get("summary")) or "",
            priority=int(spec.get("priority") or 0),
            source_kind="prediction",
            source_ref=_string(spec.get("source_ref")) or f"prediction:{industry_instance_id}",
            metadata=_mapping(spec.get("metadata")),
        )
    else:
        backlog_item = (
            backlog_repository.get_item(existing_view["id"])
            if backlog_repository is not None and _string(existing_view.get("id"))
            else None
        ) or existing_view
        if hasattr(backlog_item, "model_copy") and backlog_repository is not None:
            was_terminal = _string(getattr(backlog_item, "status", None)) in {"completed", "cancelled"}
            merged_metadata = _mapping(getattr(backlog_item, "metadata", None))
            merged_metadata.update(_mapping(spec.get("metadata")))
            backlog_item = backlog_repository.upsert_item(
                backlog_item.model_copy(
                    update={
                        "lane_id": _string(spec.get("lane_id")) or getattr(backlog_item, "lane_id", None),
                        "title": _string(spec.get("title")) or getattr(backlog_item, "title", None),
                        "summary": _string(spec.get("summary")) or getattr(backlog_item, "summary", None),
                        "status": "open" if was_terminal else getattr(backlog_item, "status", None),
                        "priority": max(
                            int(getattr(backlog_item, "priority", 0) or 0),
                            int(spec.get("priority") or 0),
                        ),
                        "cycle_id": None if was_terminal else getattr(backlog_item, "cycle_id", None),
                        "goal_id": None if was_terminal else getattr(backlog_item, "goal_id", None),
                        "assignment_id": None if was_terminal else getattr(backlog_item, "assignment_id", None),
                        "metadata": merged_metadata,
                    },
                ),
            )
    backlog_item_payload = _mapping(backlog_item)
    run_operating_cycle = getattr(industry_service, "run_operating_cycle", None)
    cycle_result = (
        await run_operating_cycle(
            instance_id=industry_instance_id,
            actor=EXECUTION_CORE_AGENT_ID,
            backlog_item_ids=[_string(backlog_item_payload.get("id")) or ""],
            auto_dispatch_materialized_goals=True,
        )
        if callable(run_operating_cycle)
        else {"processed_instances": []}
    )
    processed_instances = list(_mapping(cycle_result).get("processed_instances") or [])
    instance_result = next(
        (
            _mapping(item)
            for item in processed_instances
            if _string(_mapping(item).get("instance_id")) == industry_instance_id
        ),
        {},
    )
    if backlog_repository is not None and _string(backlog_item_payload.get("id")):
        refreshed = backlog_repository.get_item(_string(backlog_item_payload.get("id")))
        if refreshed is not None:
            backlog_item_payload = _mapping(refreshed)
    session_id = f"industry-chat:{industry_instance_id}:{EXECUTION_CORE_ROLE_ID}"
    chat_route = f"/chat?threadId={quote(session_id, safe='')}"
    _append_control_thread_message(
        industry_service,
        industry_instance_id=industry_instance_id,
        case_id=case_id,
        case_title=_string(case_payload.get("title")) or case_id,
        recommendation=recommendation,
        backlog_item_id=_string(backlog_item_payload.get("id")) or "",
        backlog_status=_string(backlog_item_payload.get("status")),
        started_cycle_id=_string(instance_result.get("started_cycle_id")),
        coordination_reason=_string(instance_result.get("reason")),
        actor=actor,
    )
    title = _string(recommendation.get("title")) or _string(recommendation.get("recommendation_id")) or case_id
    summary = (
        f"预测建议“{title}”已登记给主脑处理。"
        if reused_backlog
        else f"预测建议“{title}”已交给主脑，并写入执行 backlog。"
    )
    return {
        "summary": summary,
        "industry_instance_id": industry_instance_id,
        "backlog_item_id": _string(backlog_item_payload.get("id")),
        "backlog_status": _string(backlog_item_payload.get("status")),
        "reused_backlog": reused_backlog,
        "started_cycle_id": _string(instance_result.get("started_cycle_id")),
        "coordination_reason": _string(instance_result.get("reason")),
        "chat_thread_id": session_id,
        "chat_route": chat_route,
    }


__all__ = ["coordinate_prediction_recommendation"]
