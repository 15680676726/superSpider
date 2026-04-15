# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import Counter

from .runtime_center_shared_core import *  # noqa: F401,F403
from .runtime_center_dependencies import _get_memory_activation_service, _list_memory_relation_views
from ..runtime_center.models import RuntimeActivationSummary
from ..runtime_center.projection_utils import string_list_from_values


def _first_non_empty(*values: object) -> str | None:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def _memory_entry_timestamp(entry: object) -> object | None:
    for field_name in ("source_updated_at", "updated_at", "created_at"):
        value = getattr(entry, field_name, None)
        if value is not None:
            return value
    return None


def _memory_timestamp_json(value: object | None) -> str | None:
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        try:
            return str(isoformat())
        except Exception:
            return None
    return str(value) if value is not None else None


def _sort_memory_entries(entries: list[object]) -> list[object]:
    return sorted(
        list(entries),
        key=lambda item: (
            _memory_entry_timestamp(item) is not None,
            _memory_entry_timestamp(item) or "",
        ),
        reverse=True,
    )


def _relation_metadata(entry: object) -> dict[str, object]:
    metadata = getattr(entry, "metadata", None)
    return dict(metadata or {}) if isinstance(metadata, dict) else {}


def _relation_display_key(entry: object) -> tuple[str, str]:
    relation_kind = str(getattr(entry, "relation_kind", "") or "").strip().lower() or "unknown"
    summary = str(getattr(entry, "summary", "") or "").strip().casefold()
    return relation_kind, summary


def _relation_display_priority(entry: object) -> tuple[int, int, float, bool, object, str]:
    metadata = _relation_metadata(entry)
    source_kind = str(metadata.get("source_kind") or "").strip().lower()
    target_kind = str(metadata.get("target_kind") or "").strip().lower()
    relation_kind = str(getattr(entry, "relation_kind", "") or "").strip().lower()
    confidence = float(getattr(entry, "confidence", 0.0) or 0.0)
    relation_id = str(getattr(entry, "relation_id", "") or "").strip()
    return (
        0 if source_kind == "fact" else 1,
        0 if target_kind == "opinion" else 1,
        -confidence,
        relation_kind == "mentions",
        _memory_entry_timestamp(entry) or "",
        relation_id,
    )


_ENTITY_TITLE_SUFFIXES = (
    "说明",
    "规则",
    "报告",
    "记录",
    "内容",
    "信息",
    "总结",
    "清单",
    "summary",
    "report",
    "record",
    "rule",
    "rules",
    "note",
    "notes",
)


def _entity_display_penalty(entry: object) -> int:
    entity_key = str(
        getattr(entry, "entity_key", None)
        or getattr(entry, "display_name", None)
        or ""
    ).strip()
    if not entity_key:
        return 1
    lowered = entity_key.casefold()
    if any(lowered.endswith(suffix) for suffix in _ENTITY_TITLE_SUFFIXES):
        return 1
    return 0


def _build_entity_relation_score_map(relation_views: list[object]) -> dict[str, int]:
    scores: Counter[str] = Counter()
    for relation in list(relation_views or []):
        relation_kind = str(getattr(relation, "relation_kind", "") or "").strip().lower()
        if relation_kind == "mentions":
            continue
        metadata = _relation_metadata(relation)
        entity_key = str(metadata.get("entity_key") or "").strip()
        if entity_key:
            scores[entity_key] += 1
        subject_key = str(metadata.get("subject_key") or "").strip()
        if subject_key:
            scores[subject_key] += 1
    return dict(scores)


def _sort_entity_views_for_display(
    entity_views: list[object],
    *,
    relation_score_map: dict[str, int],
) -> list[object]:
    def _priority(entry: object) -> tuple[int, int, int, int, float, object, str]:
        entity_key = str(getattr(entry, "entity_key", "") or "").strip()
        metadata = _relation_metadata(entry)
        entry_count = int(metadata.get("entry_count") or 0)
        related_entities = list(getattr(entry, "related_entities", []) or [])
        confidence = float(getattr(entry, "confidence", 0.0) or 0.0)
        return (
            -int(relation_score_map.get(entity_key, 0)),
            _entity_display_penalty(entry),
            -entry_count,
            -len(related_entities),
            -confidence,
            _memory_entry_timestamp(entry) or "",
            entity_key,
        )

    return sorted(list(entity_views or []), key=_priority)


def _dedupe_relation_views_for_display(
    relation_views: list[object],
    *,
    limit: int,
) -> list[object]:
    if limit <= 0:
        return []
    selected: list[object] = []
    seen: set[tuple[str, str]] = set()
    for entry in sorted(list(relation_views or []), key=_relation_display_priority):
        summary = str(getattr(entry, "summary", "") or "").strip()
        dedupe_key = _relation_display_key(entry) if summary else ("", str(getattr(entry, "relation_id", "") or ""))
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        selected.append(entry)
        if len(selected) >= limit:
            break
    return selected


def _resolve_memory_scope(
    *,
    scope_type: str | None = None,
    scope_id: str | None = None,
    task_id: str | None = None,
    work_context_id: str | None = None,
    agent_id: str | None = None,
    industry_instance_id: str | None = None,
    global_scope_id: str | None = None,
) -> tuple[str | None, str | None]:
    normalized_scope_type = str(scope_type or "").strip() or None
    normalized_scope_id = str(scope_id or "").strip() or None
    if normalized_scope_type and normalized_scope_id:
        return normalized_scope_type, normalized_scope_id
    for candidate_scope_type, candidate_scope_id in (
        ("work_context", work_context_id),
        ("task", task_id),
        ("agent", agent_id),
        ("industry", industry_instance_id),
        ("global", global_scope_id),
    ):
        normalized_candidate_scope_id = str(candidate_scope_id or "").strip()
        if normalized_candidate_scope_id:
            return candidate_scope_type, normalized_candidate_scope_id
    return None, None


def _activate_memory_for_surface(
    *,
    request: Request,
    query: str,
    role: str | None = None,
    scope_type: str | None = None,
    scope_id: str | None = None,
    task_id: str | None = None,
    work_context_id: str | None = None,
    agent_id: str | None = None,
    industry_instance_id: str | None = None,
    global_scope_id: str | None = None,
    limit: int = 12,
):
    service = _get_memory_activation_service(request)
    resolved_scope_type, resolved_scope_id = _resolve_memory_scope(
        scope_type=scope_type,
        scope_id=scope_id,
        task_id=task_id,
        work_context_id=work_context_id,
        agent_id=agent_id,
        industry_instance_id=industry_instance_id,
        global_scope_id=global_scope_id,
    )
    resolved_task_id = task_id
    resolved_work_context_id = work_context_id
    resolved_agent_id = agent_id
    resolved_industry_instance_id = industry_instance_id
    resolved_global_scope_id = global_scope_id
    if resolved_scope_type == "task":
        resolved_task_id = resolved_scope_id
    elif resolved_scope_type == "work_context":
        resolved_work_context_id = resolved_scope_id
    elif resolved_scope_type == "agent":
        resolved_agent_id = resolved_scope_id
    elif resolved_scope_type == "industry":
        resolved_industry_instance_id = resolved_scope_id
    elif resolved_scope_type == "global":
        resolved_global_scope_id = resolved_scope_id
    return service.activate_for_query(
        query=query,
        role=role,
        scope_type=resolved_scope_type,
        scope_id=resolved_scope_id,
        task_id=resolved_task_id,
        work_context_id=resolved_work_context_id,
        agent_id=resolved_agent_id,
        industry_instance_id=resolved_industry_instance_id,
        global_scope_id=resolved_global_scope_id,
        limit=limit,
    )


def _maybe_build_activation_payload(
    *,
    request: Request,
    include_activation: bool,
    query: str | None,
    role: str | None = None,
    scope_type: str | None = None,
    scope_id: str | None = None,
    task_id: str | None = None,
    work_context_id: str | None = None,
    agent_id: str | None = None,
    industry_instance_id: str | None = None,
    global_scope_id: str | None = None,
    limit: int = 12,
) -> dict[str, object] | None:
    normalized_query = str(query or "").strip()
    if not include_activation or not normalized_query:
        return None
    result = _activate_memory_for_surface(
        request=request,
        query=normalized_query,
        role=role,
        scope_type=scope_type,
        scope_id=scope_id,
        task_id=task_id,
        work_context_id=work_context_id,
        agent_id=agent_id,
        industry_instance_id=industry_instance_id,
        global_scope_id=global_scope_id,
        limit=limit,
    )
    return _serialize_activation_summary(result)


def _serialize_activation_summary(result: object) -> dict[str, object] | None:
    model_dump = getattr(result, "model_dump", None)
    if not callable(model_dump):
        return None
    payload = model_dump(mode="json")
    if not isinstance(payload, dict):
        return None
    summary = RuntimeActivationSummary(
        scope_type=_first_non_empty(payload.get("scope_type")) or "global",
        scope_id=_first_non_empty(payload.get("scope_id")) or "runtime",
        activated_count=len(payload.get("activated_neurons") or []),
        contradiction_count=len(payload.get("contradictions") or []),
        top_entities=string_list_from_values(payload.get("top_entities")),
        top_opinions=string_list_from_values(payload.get("top_opinions")),
        top_relations=string_list_from_values(payload.get("top_relations")),
        top_relation_kinds=string_list_from_values(payload.get("top_relation_kinds")),
        top_constraints=string_list_from_values(payload.get("top_constraints")),
        top_next_actions=string_list_from_values(payload.get("top_next_actions")),
        support_refs=string_list_from_values(payload.get("support_refs")),
        top_evidence_refs=string_list_from_values(
            payload.get("top_evidence_refs"),
            payload.get("evidence_refs"),
            payload.get("support_refs"),
        ),
        evidence_refs=string_list_from_values(payload.get("evidence_refs")),
        strategy_refs=string_list_from_values(payload.get("strategy_refs")),
    )
    return summary.model_dump(mode="json")


def _serialize_memory_entry(entry: object) -> dict[str, object]:
    model_dump = getattr(entry, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="json")
        if isinstance(payload, dict):
            return dict(payload)
    return {}


def _select_surface_relation_views(
    *,
    relation_views: list[object],
    activation_result: object | None,
    relation_limit: int,
) -> list[object]:
    limit = max(0, int(relation_limit))
    if limit <= 0:
        return []
    ordered_relations = list(relation_views or [])

    def _relation_metadata(item: object) -> dict[str, object]:
        metadata = getattr(item, "metadata", None)
        return dict(metadata or {}) if isinstance(metadata, dict) else {}

    def _is_fact_opinion_relation(item: object) -> bool:
        metadata = _relation_metadata(item)
        return (
            str(getattr(item, "relation_kind", "") or "").strip().lower() != "mentions"
            and str(metadata.get("source_kind") or "").strip().lower() == "fact"
            and str(metadata.get("target_kind") or "").strip().lower() == "opinion"
        )

    def _is_fact_non_mention_relation(item: object) -> bool:
        metadata = _relation_metadata(item)
        return (
            str(getattr(item, "relation_kind", "") or "").strip().lower() != "mentions"
            and str(metadata.get("source_kind") or "").strip().lower() == "fact"
        )

    if activation_result is None:
        primary_relations = [item for item in ordered_relations if _is_fact_opinion_relation(item)]
        if primary_relations:
            return primary_relations[: min(limit, 6)]
        return ordered_relations[:limit]

    prioritized_ids = [
        str(getattr(item, "relation_id", "") or "").strip()
        for item in list(getattr(activation_result, "top_relation_evidence", []) or [])
        if str(getattr(item, "relation_id", "") or "").strip()
    ]
    if not prioritized_ids:
        return ordered_relations[:limit]

    relation_by_id = {
        str(getattr(item, "relation_id", "") or "").strip(): item
        for item in ordered_relations
        if str(getattr(item, "relation_id", "") or "").strip()
    }
    prioritized_relations = [
        relation_by_id[relation_id]
        for relation_id in prioritized_ids
        if relation_id in relation_by_id
    ]
    prioritized_fact_opinions = [
        item for item in prioritized_relations if _is_fact_opinion_relation(item)
    ]
    all_fact_opinions = [
        item for item in ordered_relations if _is_fact_opinion_relation(item)
    ]
    fact_prioritized = [
        item
        for item in prioritized_relations
        if _is_fact_non_mention_relation(item)
    ]
    non_mention_prioritized = [
        item
        for item in prioritized_relations
        if str(getattr(item, "relation_kind", "") or "").strip().lower() != "mentions"
    ]
    if prioritized_fact_opinions:
        return prioritized_fact_opinions[: min(limit, 6)]
    if all_fact_opinions:
        return all_fact_opinions[: min(limit, 6)]
    selected = list(fact_prioritized or non_mention_prioritized or prioritized_relations)
    if selected:
        return selected[: min(limit, 6)]
    return ordered_relations[:limit]


def _build_memory_operator_surface_payload(
    *,
    request: Request,
    query: str | None = None,
    role: str | None = None,
    scope_type: str | None = None,
    scope_id: str | None = None,
    task_id: str | None = None,
    work_context_id: str | None = None,
    agent_id: str | None = None,
    industry_instance_id: str | None = None,
    global_scope_id: str | None = None,
    owner_agent_id: str | None = None,
    relation_kind: str | None = None,
    source_node_id: str | None = None,
    target_node_id: str | None = None,
    limit: int = 12,
    relation_limit: int = 12,
) -> dict[str, object]:
    resolved_scope_type, resolved_scope_id = _resolve_memory_scope(
        scope_type=scope_type,
        scope_id=scope_id,
        task_id=task_id,
        work_context_id=work_context_id,
        agent_id=agent_id,
        industry_instance_id=industry_instance_id,
        global_scope_id=global_scope_id,
    )
    normalized_query = str(query or "").strip()
    activation_result = None
    activation_payload = None
    if normalized_query:
        activation_result = _activate_memory_for_surface(
            request=request,
            query=normalized_query,
            role=role,
            scope_type=resolved_scope_type,
            scope_id=resolved_scope_id,
            task_id=task_id,
            work_context_id=work_context_id,
            agent_id=agent_id,
            industry_instance_id=industry_instance_id,
            global_scope_id=global_scope_id,
            limit=limit,
        )
        activation_payload = _serialize_activation_summary(activation_result)
    raw_relation_limit = max(0, int(relation_limit))
    if normalized_query:
        raw_relation_limit = max(raw_relation_limit * 4, 48)
    relation_views = _list_memory_relation_views(
        request,
        scope_type=resolved_scope_type,
        scope_id=resolved_scope_id,
        owner_agent_id=owner_agent_id,
        industry_instance_id=industry_instance_id,
        relation_kind=relation_kind,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        limit=raw_relation_limit,
    )
    surface_relation_views = _select_surface_relation_views(
        relation_views=list(relation_views or []),
        activation_result=activation_result,
        relation_limit=relation_limit,
    )
    surface_relation_views = _dedupe_relation_views_for_display(
        list(surface_relation_views or []),
        limit=max(0, int(relation_limit)),
    )
    relation_payloads = [_serialize_memory_entry(view) for view in surface_relation_views]
    relation_kind_counts = Counter(
        str(getattr(view, "relation_kind", "") or "").strip() or "unknown"
        for view in surface_relation_views
    )
    sleep_service = getattr(request.app.state, "memory_sleep_service", None)
    resolve_scope_overlay = getattr(sleep_service, "resolve_scope_overlay", None)
    sleep_payload = (
        resolve_scope_overlay(scope_type=resolved_scope_type, scope_id=resolved_scope_id)
        if callable(resolve_scope_overlay) and resolved_scope_type and resolved_scope_id
        else {}
    )
    return {
        "scope_type": resolved_scope_type or "global",
        "scope_id": resolved_scope_id or "runtime",
        "query": normalized_query or None,
        "activation": activation_payload,
        "sleep": dict(sleep_payload or {}) if isinstance(sleep_payload, dict) else {},
        "relation_count": len(relation_payloads),
        "relation_kind_counts": dict(relation_kind_counts),
        "relations": relation_payloads,
    }


def _list_truth_first_scope_entries(
    *,
    request: Request,
    scope_type: str | None,
    scope_id: str | None,
    owner_agent_id: str | None = None,
    industry_instance_id: str | None = None,
    limit: int | None = None,
) -> list[object]:
    service = _get_derived_memory_index_service(request)
    entries = service.list_fact_entries(
        scope_type=scope_type,
        scope_id=scope_id,
        owner_agent_id=owner_agent_id,
        industry_instance_id=industry_instance_id,
        limit=limit,
    )
    return _sort_memory_entries(list(entries or []))


def _build_memory_profile_payload(
    *,
    scope_type: str,
    scope_id: str,
    entries: list[object],
) -> dict[str, object]:
    latest_entries = entries[:4]
    latest_summaries = [
        _first_non_empty(
            getattr(entry, "summary", None),
            getattr(entry, "content_excerpt", None),
            getattr(entry, "title", None),
        )
        for entry in latest_entries
    ]
    normalized_summaries = [item for item in latest_summaries if item]
    preference_lines = [
        item
        for item in normalized_summaries
        if "prefer" in item.lower() or "preference" in item.lower()
    ]
    constraint_lines = [
        item
        for item in normalized_summaries
        if "must" in item.lower() or "only" in item.lower() or "required" in item.lower()
    ]
    updated_at = _memory_timestamp_json(_memory_entry_timestamp(latest_entries[0])) if latest_entries else None
    return {
        "scope_type": scope_type,
        "scope_id": scope_id,
        "static_profile": {
            "headline": _first_non_empty(
                getattr(latest_entries[0], "title", None) if latest_entries else None,
                scope_id,
            ),
            "summary": normalized_summaries[0] if normalized_summaries else "",
        },
        "dynamic_profile": normalized_summaries[:4],
        "active_preferences": preference_lines[:3],
        "active_constraints": constraint_lines[:3],
        "current_focus_summary": _first_non_empty(
            getattr(latest_entries[0], "title", None) if latest_entries else None,
            normalized_summaries[0] if normalized_summaries else None,
        ),
        "current_operating_context": normalized_summaries[0] if normalized_summaries else "",
        "updated_at": updated_at,
    }


def _build_memory_episode_payloads(
    *,
    scope_type: str,
    scope_id: str,
    entries: list[object],
    limit: int,
) -> list[dict[str, object]]:
    grouped: dict[str, list[object]] = {}
    for entry in entries:
        source_ref = str(getattr(entry, "source_ref", "") or "").strip() or str(
            getattr(entry, "id", "") or "memory-episode",
        )
        grouped.setdefault(source_ref, []).append(entry)
    payloads: list[dict[str, object]] = []
    for source_ref, grouped_entries in grouped.items():
        ordered = _sort_memory_entries(grouped_entries)
        first = ordered[0]
        last = ordered[-1]
        payloads.append(
            {
                "episode_id": f"episode:{scope_type}:{scope_id}:{source_ref}",
                "scope_type": scope_type,
                "scope_id": scope_id,
                "headline": _first_non_empty(
                    getattr(first, "title", None),
                    getattr(first, "summary", None),
                    source_ref,
                ),
                "summary": " / ".join(
                    filter(
                        None,
                        [
                            _first_non_empty(getattr(item, "summary", None), getattr(item, "title", None))
                            for item in ordered[:2]
                        ],
                    ),
                ),
                "entry_refs": [
                    str(getattr(item, "id", "") or "").strip()
                    for item in ordered
                    if str(getattr(item, "id", "") or "").strip()
                ],
                "work_context_id": scope_id if scope_type == "work_context" else None,
                "control_thread_id": _serialize_memory_entry(first).get("metadata", {}).get("control_thread_id"),
                "started_at": _memory_timestamp_json(_memory_entry_timestamp(last)),
                "ended_at": _memory_timestamp_json(_memory_entry_timestamp(first)),
            },
        )
        if len(payloads) >= max(1, int(limit)):
            break
    return payloads


@router.get("/memory/profiles", response_model=list[dict[str, object]])
async def list_memory_profiles(
    request: Request,
    response: Response,
    scope_type: Literal["global", "industry", "agent", "task", "work_context"] | None = None,
    scope_id: str | None = None,
    task_id: str | None = None,
    work_context_id: str | None = None,
    agent_id: str | None = None,
    global_scope_id: str | None = None,
    include_activation: bool = False,
    query: str | None = None,
    role: str | None = None,
    owner_agent_id: str | None = None,
    industry_instance_id: str | None = None,
    limit: int = 20,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    if scope_type and scope_id:
        entries = _list_truth_first_scope_entries(
            request=request,
            scope_type=scope_type,
            scope_id=scope_id,
            owner_agent_id=owner_agent_id,
            industry_instance_id=industry_instance_id,
            limit=max(limit * 4, 12),
        )
        payload = _build_memory_profile_payload(scope_type=scope_type, scope_id=scope_id, entries=entries)
        activation = _maybe_build_activation_payload(
            request=request,
            include_activation=include_activation,
            query=query,
            role=role,
            scope_type=scope_type,
            scope_id=scope_id,
            task_id=task_id,
            work_context_id=work_context_id,
            agent_id=agent_id,
            industry_instance_id=industry_instance_id,
            global_scope_id=global_scope_id,
        )
        if activation is not None:
            payload["activation"] = activation
        return [payload]

    service = _get_derived_memory_index_service(request)
    entries = _sort_memory_entries(
        list(
            service.list_fact_entries(
                owner_agent_id=owner_agent_id,
                industry_instance_id=industry_instance_id,
                limit=max(limit * 8, 40),
            )
            or []
        ),
    )
    scopes: list[tuple[str, str]] = []
    for entry in entries:
        key = (
            str(getattr(entry, "scope_type", "") or "").strip() or "global",
            str(getattr(entry, "scope_id", "") or "").strip() or "runtime",
        )
        if key not in scopes:
            scopes.append(key)
        if len(scopes) >= max(1, int(limit)):
            break
    return [
        _build_memory_profile_payload(
            scope_type=resolved_scope_type,
            scope_id=resolved_scope_id,
            entries=[
                entry
                for entry in entries
                if getattr(entry, "scope_type", None) == resolved_scope_type
                and getattr(entry, "scope_id", None) == resolved_scope_id
            ],
        )
        for resolved_scope_type, resolved_scope_id in scopes
    ]


@router.get("/memory/profiles/{scope_type}/{scope_id}", response_model=dict[str, object])
async def get_memory_profile(
    scope_type: Literal["global", "industry", "agent", "task", "work_context"],
    scope_id: str,
    request: Request,
    response: Response,
    task_id: str | None = None,
    work_context_id: str | None = None,
    agent_id: str | None = None,
    global_scope_id: str | None = None,
    include_activation: bool = False,
    query: str | None = None,
    role: str | None = None,
    owner_agent_id: str | None = None,
    industry_instance_id: str | None = None,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    entries = _list_truth_first_scope_entries(
        request=request,
        scope_type=scope_type,
        scope_id=scope_id,
        owner_agent_id=owner_agent_id,
        industry_instance_id=industry_instance_id,
        limit=20,
    )
    payload = _build_memory_profile_payload(scope_type=scope_type, scope_id=scope_id, entries=entries)
    activation = _maybe_build_activation_payload(
        request=request,
        include_activation=include_activation,
        query=query,
        role=role,
        scope_type=scope_type,
        scope_id=scope_id,
        task_id=task_id,
        work_context_id=work_context_id,
        agent_id=agent_id,
        industry_instance_id=industry_instance_id,
        global_scope_id=global_scope_id,
    )
    if activation is not None:
        payload["activation"] = activation
    return payload


@router.get("/memory/episodes", response_model=list[dict[str, object]])
async def list_memory_episodes(
    request: Request,
    response: Response,
    scope_type: Literal["global", "industry", "agent", "task", "work_context"] | None = None,
    scope_id: str | None = None,
    task_id: str | None = None,
    work_context_id: str | None = None,
    agent_id: str | None = None,
    industry_instance_id: str | None = None,
    global_scope_id: str | None = None,
    include_activation: bool = False,
    query: str | None = None,
    role: str | None = None,
    owner_agent_id: str | None = None,
    limit: int = 20,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    resolved_scope_type, resolved_scope_id = _resolve_memory_scope(
        scope_type=scope_type,
        scope_id=scope_id,
        task_id=task_id,
        work_context_id=work_context_id,
        agent_id=agent_id,
        industry_instance_id=industry_instance_id,
        global_scope_id=global_scope_id,
    )
    entries = _list_truth_first_scope_entries(
        request=request,
        scope_type=resolved_scope_type,
        scope_id=resolved_scope_id,
        owner_agent_id=owner_agent_id,
        industry_instance_id=industry_instance_id,
        limit=max(limit * 4, 20),
    )
    if resolved_scope_type is None or resolved_scope_id is None:
        return []
    payloads = _build_memory_episode_payloads(
        scope_type=resolved_scope_type,
        scope_id=resolved_scope_id,
        entries=entries,
        limit=limit,
    )
    activation = _maybe_build_activation_payload(
        request=request,
        include_activation=include_activation,
        query=query,
        role=role,
        scope_type=resolved_scope_type,
        scope_id=resolved_scope_id,
        task_id=task_id,
        work_context_id=work_context_id,
        agent_id=agent_id,
        industry_instance_id=industry_instance_id,
        global_scope_id=global_scope_id,
    )
    if activation is not None:
        for payload in payloads:
            payload["activation"] = activation
    return payloads


@router.get("/memory/history", response_model=list[dict[str, object]])
async def list_memory_history(
    request: Request,
    response: Response,
    scope_type: Literal["global", "industry", "agent", "task", "work_context"] | None = None,
    scope_id: str | None = None,
    task_id: str | None = None,
    work_context_id: str | None = None,
    agent_id: str | None = None,
    industry_instance_id: str | None = None,
    global_scope_id: str | None = None,
    owner_agent_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    resolved_scope_type, resolved_scope_id = _resolve_memory_scope(
        scope_type=scope_type,
        scope_id=scope_id,
        task_id=task_id,
        work_context_id=work_context_id,
        agent_id=agent_id,
        industry_instance_id=industry_instance_id,
        global_scope_id=global_scope_id,
    )
    entries = _list_truth_first_scope_entries(
        request=request,
        scope_type=resolved_scope_type,
        scope_id=resolved_scope_id,
        owner_agent_id=owner_agent_id,
        industry_instance_id=industry_instance_id,
        limit=limit,
    )
    return [_serialize_memory_entry(entry) for entry in entries[: max(1, int(limit))]]


@router.get("/memory/relations", response_model=list[dict[str, object]])
async def list_memory_relations(
    request: Request,
    response: Response,
    scope_type: Literal["global", "industry", "agent", "task", "work_context"] | None = None,
    scope_id: str | None = None,
    task_id: str | None = None,
    work_context_id: str | None = None,
    agent_id: str | None = None,
    global_scope_id: str | None = None,
    owner_agent_id: str | None = None,
    industry_instance_id: str | None = None,
    relation_kind: str | None = None,
    source_node_id: str | None = None,
    target_node_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    resolved_scope_type, resolved_scope_id = _resolve_memory_scope(
        scope_type=scope_type,
        scope_id=scope_id,
        task_id=task_id,
        work_context_id=work_context_id,
        agent_id=agent_id,
        global_scope_id=global_scope_id,
    )
    relation_views = _list_memory_relation_views(
        request,
        scope_type=resolved_scope_type,
        scope_id=resolved_scope_id,
        owner_agent_id=owner_agent_id,
        industry_instance_id=industry_instance_id,
        relation_kind=relation_kind,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        limit=max(0, int(limit)),
    )
    deduped_views = _dedupe_relation_views_for_display(
        list(relation_views or []),
        limit=max(0, int(limit)),
    )
    return [
        view.model_dump(mode="json")
        for view in deduped_views
    ]


@router.get("/memory/recall", response_model=dict[str, object])
async def recall_memory(
    request: Request,
    response: Response,
    query: str,
    role: str | None = None,
    scope_type: Literal["global", "industry", "agent", "task", "work_context"] | None = None,
    scope_id: str | None = None,
    task_id: str | None = None,
    work_context_id: str | None = None,
    agent_id: str | None = None,
    industry_instance_id: str | None = None,
    global_scope_id: str | None = None,
    include_related_scopes: bool = True,
    limit: int = 8,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_memory_recall_service(request)
    result = service.recall(
        query=query,
        role=role,
        scope_type=scope_type,
        scope_id=scope_id,
        task_id=task_id,
        work_context_id=work_context_id,
        agent_id=agent_id,
        industry_instance_id=industry_instance_id,
        global_scope_id=global_scope_id,
        include_related_scopes=include_related_scopes,
        limit=limit,
    )
    return result.model_dump(mode="json")


@router.get("/memory/activation", response_model=dict[str, object])
async def activate_memory(
    request: Request,
    response: Response,
    query: str,
    role: str | None = None,
    scope_type: Literal["global", "industry", "agent", "task", "work_context"] | None = None,
    scope_id: str | None = None,
    task_id: str | None = None,
    work_context_id: str | None = None,
    agent_id: str | None = None,
    industry_instance_id: str | None = None,
    global_scope_id: str | None = None,
    limit: int = 12,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    result = _activate_memory_for_surface(
        request=request,
        query=query,
        role=role,
        scope_type=scope_type,
        scope_id=scope_id,
        task_id=task_id,
        work_context_id=work_context_id,
        agent_id=agent_id,
        industry_instance_id=industry_instance_id,
        global_scope_id=global_scope_id,
        limit=limit,
    )
    return _serialize_activation_summary(result) or {}


@router.get("/memory/surface", response_model=dict[str, object])
async def get_memory_operator_surface(
    request: Request,
    response: Response,
    query: str | None = None,
    role: str | None = None,
    scope_type: Literal["global", "industry", "agent", "task", "work_context"] | None = None,
    scope_id: str | None = None,
    task_id: str | None = None,
    work_context_id: str | None = None,
    agent_id: str | None = None,
    industry_instance_id: str | None = None,
    global_scope_id: str | None = None,
    owner_agent_id: str | None = None,
    relation_kind: str | None = None,
    source_node_id: str | None = None,
    target_node_id: str | None = None,
    limit: int = 12,
    relation_limit: int = 12,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    return _build_memory_operator_surface_payload(
        request=request,
        query=query,
        role=role,
        scope_type=scope_type,
        scope_id=scope_id,
        task_id=task_id,
        work_context_id=work_context_id,
        agent_id=agent_id,
        industry_instance_id=industry_instance_id,
        global_scope_id=global_scope_id,
        owner_agent_id=owner_agent_id,
        relation_kind=relation_kind,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        limit=limit,
        relation_limit=relation_limit,
    )


@router.get("/memory/sleep/scopes", response_model=list[dict[str, object]])
async def list_memory_sleep_scopes(
    request: Request,
    response: Response,
    scope_type: Literal["global", "industry", "agent", "task", "work_context"] | None = None,
    scope_id: str | None = None,
    dirty_only: bool = False,
    limit: int = 100,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_memory_sleep_service(request)
    return [
        item.model_dump(mode="json")
        for item in service.list_scope_states(
            scope_type=scope_type,
            scope_id=scope_id,
            dirty_only=dirty_only,
            limit=limit,
        )
    ]


@router.get("/memory/sleep/jobs", response_model=list[dict[str, object]])
async def list_memory_sleep_jobs(
    request: Request,
    response: Response,
    scope_type: Literal["global", "industry", "agent", "task", "work_context"] | None = None,
    scope_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_memory_sleep_service(request)
    return [
        item.model_dump(mode="json")
        for item in service.list_sleep_jobs(
            scope_type=scope_type,
            scope_id=scope_id,
            status=status,
            limit=limit,
        )
    ]


@router.get("/memory/sleep/digests", response_model=list[dict[str, object]])
async def list_memory_sleep_digests(
    request: Request,
    response: Response,
    scope_type: Literal["global", "industry", "agent", "task", "work_context"] | None = None,
    scope_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_memory_sleep_service(request)
    return [
        item.model_dump(mode="json")
        for item in service.list_digests(
            scope_type=scope_type,
            scope_id=scope_id,
            status=status,
            limit=limit,
        )
    ]


@router.get("/memory/sleep/rules", response_model=list[dict[str, object]])
async def list_memory_sleep_rules(
    request: Request,
    response: Response,
    scope_type: Literal["global", "industry", "agent", "task", "work_context"] | None = None,
    scope_id: str | None = None,
    state: str | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_memory_sleep_service(request)
    return [
        item.model_dump(mode="json")
        for item in service.list_soft_rules(
            scope_type=scope_type,
            scope_id=scope_id,
            state=state,
            limit=limit,
        )
    ]


@router.get("/memory/sleep/conflicts", response_model=list[dict[str, object]])
async def list_memory_sleep_conflicts(
    request: Request,
    response: Response,
    scope_type: Literal["global", "industry", "agent", "task", "work_context"] | None = None,
    scope_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_memory_sleep_service(request)
    return [
        item.model_dump(mode="json")
        for item in service.list_conflict_proposals(
            scope_type=scope_type,
            scope_id=scope_id,
            status=status,
            limit=limit,
        )
    ]


@router.post("/memory/sleep/run", response_model=dict[str, object])
async def run_memory_sleep_scope(
    payload: MemorySleepRunRequest,
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_memory_sleep_service(request)
    result = service.run_sleep(
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        trigger_kind=payload.trigger_kind,
    )
    return result.model_dump(mode="json")


@router.get("/memory/index", response_model=list[dict[str, object]])
async def list_memory_index_entries(
    request: Request,
    response: Response,
    source_type: str | None = None,
    source_ref: str | None = None,
    scope_type: Literal["global", "industry", "agent", "task", "work_context"] | None = None,
    scope_id: str | None = None,
    owner_agent_id: str | None = None,
    industry_instance_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_derived_memory_index_service(request)
    return [
        entry.model_dump(mode="json")
        for entry in service.list_fact_entries(
            source_type=source_type,
            source_ref=source_ref,
            scope_type=scope_type,
            scope_id=scope_id,
            owner_agent_id=owner_agent_id,
            industry_instance_id=industry_instance_id,
            limit=limit,
        )
    ]


@router.post("/memory/rebuild", response_model=dict[str, object])
async def rebuild_memory_index(
    payload: MemoryRebuildRequest,
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_derived_memory_index_service(request)
    result = service.rebuild_all(
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        include_reporting=payload.include_reporting,
        include_learning=payload.include_learning,
        evidence_limit=payload.evidence_limit,
    )
    payload_data = result.model_dump(mode="json")
    rebuild_relation_views = getattr(service, "rebuild_relation_views", None)
    relation_views: list[object] = []
    if callable(rebuild_relation_views):
        relation_owner_agent_id = payload.scope_id if payload.scope_type == "agent" else None
        relation_industry_instance_id = payload.scope_id if payload.scope_type == "industry" else None
        relation_views = list(
            rebuild_relation_views(
                scope_type=payload.scope_type,
                scope_id=payload.scope_id,
                owner_agent_id=relation_owner_agent_id,
                industry_instance_id=relation_industry_instance_id,
            )
            or []
        )
    payload_data["relation_view_count"] = len(relation_views)
    metadata = dict(payload_data.get("metadata") or {})
    metadata["relation_rebuilt"] = callable(rebuild_relation_views)
    payload_data["metadata"] = metadata
    return payload_data


@router.get("/memory/entities", response_model=list[dict[str, object]])
async def list_memory_entities(
    request: Request,
    response: Response,
    scope_type: Literal["global", "industry", "agent", "task", "work_context"] | None = None,
    scope_id: str | None = None,
    owner_agent_id: str | None = None,
    industry_instance_id: str | None = None,
    entity_key: str | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_derived_memory_index_service(request)
    entity_views = list(
        service.list_entity_views(
            scope_type=scope_type,
            scope_id=scope_id,
            owner_agent_id=owner_agent_id,
            industry_instance_id=industry_instance_id,
            entity_key=entity_key,
            limit=max(0, int(limit)),
        )
        or []
    )
    relation_views = _list_memory_relation_views(
        request,
        scope_type=scope_type,
        scope_id=scope_id,
        owner_agent_id=owner_agent_id,
        industry_instance_id=industry_instance_id,
        limit=max(max(0, int(limit)) * 8, 40),
    )
    sorted_views = _sort_entity_views_for_display(
        entity_views,
        relation_score_map=_build_entity_relation_score_map(list(relation_views or [])),
    )
    return [
        view.model_dump(mode="json")
        for view in sorted_views[: max(0, int(limit))]
    ]


@router.get("/memory/opinions", response_model=list[dict[str, object]])
async def list_memory_opinions(
    request: Request,
    response: Response,
    scope_type: Literal["global", "industry", "agent", "task", "work_context"] | None = None,
    scope_id: str | None = None,
    owner_agent_id: str | None = None,
    industry_instance_id: str | None = None,
    subject_key: str | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_derived_memory_index_service(request)
    return [
        view.model_dump(mode="json")
        for view in service.list_opinion_views(
            scope_type=scope_type,
            scope_id=scope_id,
            owner_agent_id=owner_agent_id,
            industry_instance_id=industry_instance_id,
            subject_key=subject_key,
            limit=limit,
        )
    ]


@router.get("/memory/reflections", response_model=list[dict[str, object]])
async def list_memory_reflections(
    request: Request,
    response: Response,
    scope_type: Literal["global", "industry", "agent", "task", "work_context"] | None = None,
    scope_id: str | None = None,
    owner_agent_id: str | None = None,
    industry_instance_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, object]]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_memory_reflection_service(request)
    return [
        run.model_dump(mode="json")
        for run in service.list_runs(
            scope_type=scope_type,
            scope_id=scope_id,
            owner_agent_id=owner_agent_id,
            industry_instance_id=industry_instance_id,
            status=status,
            limit=limit,
        )
    ]


@router.post("/memory/reflect", response_model=dict[str, object])
async def reflect_memory_scope(
    payload: MemoryReflectRequest,
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    service = _get_memory_reflection_service(request)
    result = service.reflect(
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        owner_agent_id=payload.owner_agent_id,
        industry_instance_id=payload.industry_instance_id,
        trigger_kind=payload.trigger_kind,
        create_learning_proposals=payload.create_learning_proposals,
    )
    return result.model_dump(mode="json")
