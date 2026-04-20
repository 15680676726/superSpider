# -*- coding: utf-8 -*-
from __future__ import annotations

from .runtime_center_shared_core import *  # noqa: F401,F403
from .runtime_center_dependencies import _get_research_session_repository
from .runtime_center_payloads import (
    serialize_runtime_research_brief,
    serialize_runtime_research_conflicts,
    serialize_runtime_research_findings,
    serialize_runtime_research_gaps,
    serialize_runtime_research_retrieval,
    serialize_runtime_research_sources,
    serialize_runtime_research_writeback_truth,
)


def _serialize_research_round(round_record: object | None) -> dict[str, object] | None:
    if round_record is None:
        return None
    model_dump = getattr(round_record, "model_dump", None)
    payload = model_dump(mode="json") if callable(model_dump) else {}
    if not isinstance(payload, dict):
        return None
    return {
        "id": payload.get("id"),
        "round_index": payload.get("round_index"),
        "status": payload.get("decision"),
        "response_summary": payload.get("response_summary"),
        "updated_at": payload.get("updated_at"),
    }


def _serialize_research_session(session: object) -> dict[str, object]:
    model_dump = getattr(session, "model_dump", None)
    payload = model_dump(mode="json") if callable(model_dump) else {}
    if not isinstance(payload, dict):
        payload = {}
    status = str(payload.get("status") or "").strip()
    return {
        "id": payload.get("id"),
        "status": status,
        "goal": payload.get("goal"),
        "round_count": payload.get("round_count"),
        "waiting_login": status == "waiting-login",
        "latest_status": payload.get("failure_summary") or status,
        "updated_at": payload.get("updated_at"),
    }


@router.get("/research", response_model=dict[str, object])
async def get_runtime_research(
    request: Request,
    response: Response,
) -> dict[str, object]:
    apply_runtime_center_surface_headers(response, surface="runtime-center")
    repository = _get_research_session_repository(request)
    sessions = repository.list_research_sessions(limit=1)
    if not sessions:
        return {
            "id": None,
            "status": None,
            "goal": None,
            "round_count": 0,
            "waiting_login": False,
            "latest_status": None,
            "updated_at": None,
            "session": None,
            "latest_round": None,
            "brief": None,
            "findings": [],
            "sources": [],
            "gaps": [],
            "conflicts": [],
            "writeback_truth": None,
        }
    session = sessions[0]
    serialized_session = _serialize_research_session(session)
    rounds = repository.list_research_rounds(session_id=session.id, limit=50)
    latest_round = rounds[-1] if rounds else None
    serialized_round = _serialize_research_round(latest_round)
    session_payload = getattr(session, "model_dump", lambda **_: {})(mode="json")
    if not isinstance(session_payload, dict):
        session_payload = {}
    round_payload: dict[str, object] = {}
    if latest_round is not None:
        round_payload = getattr(latest_round, "model_dump", lambda **_: {})(mode="json")
        if not isinstance(round_payload, dict):
            round_payload = {}
    brief_payload = serialize_runtime_research_brief(
        session_payload=session_payload,
        round_payload=round_payload,
    )
    findings_payload = serialize_runtime_research_findings(
        session_payload=session_payload,
        round_payload=round_payload,
    )
    sources_payload = serialize_runtime_research_sources(
        session_payload=session_payload,
        round_payload=round_payload,
    )
    gaps_payload = serialize_runtime_research_gaps(
        session_payload=session_payload,
        round_payload=round_payload,
    )
    conflicts_payload = serialize_runtime_research_conflicts(
        session_payload=session_payload,
        round_payload=round_payload,
        findings_payload=findings_payload,
    )
    writeback_truth_payload = serialize_runtime_research_writeback_truth(
        session_payload=session_payload,
        round_payload=round_payload,
        brief_payload=brief_payload,
    )
    retrieval_payload = serialize_runtime_research_retrieval(
        session_payload=session_payload,
        round_payload=round_payload,
    )
    latest_status = (
        (serialized_round or {}).get("response_summary")
        or (serialized_round or {}).get("status")
        or serialized_session.get("latest_status")
    )
    if serialized_round is not None:
        serialized_round = {
            **serialized_round,
            "findings": findings_payload,
            "sources": sources_payload,
            "gaps": gaps_payload,
            "conflicts": conflicts_payload,
            "retrieval": retrieval_payload,
        }
    return {
        **serialized_session,
        "latest_status": latest_status,
        "brief": brief_payload,
        "findings": findings_payload,
        "sources": sources_payload,
        "gaps": gaps_payload,
        "conflicts": conflicts_payload,
        "writeback_truth": writeback_truth_payload,
        "retrieval": retrieval_payload,
        "session": {
            **serialized_session,
            "latest_status": latest_status,
            "brief": brief_payload,
            "findings": findings_payload,
            "sources": sources_payload,
            "gaps": gaps_payload,
            "conflicts": conflicts_payload,
            "writeback_truth": writeback_truth_payload,
            "retrieval": retrieval_payload,
        },
        "latest_round": serialized_round,
    }


__all__ = ["get_runtime_research"]
