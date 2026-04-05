# -*- coding: utf-8 -*-
from __future__ import annotations

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
    return [
        view.model_dump(mode="json")
        for view in _list_memory_relation_views(
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
    return result.model_dump(mode="json")


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
    return [
        view.model_dump(mode="json")
        for view in service.list_entity_views(
            scope_type=scope_type,
            scope_id=scope_id,
            owner_agent_id=owner_agent_id,
            industry_instance_id=industry_instance_id,
            entity_key=entity_key,
            limit=limit,
        )
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
