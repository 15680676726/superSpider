# -*- coding: utf-8 -*-
"""Canonical chat-thread payload extraction for Runtime Center read surfaces."""
from __future__ import annotations

from typing import Any

from .projection_utils import first_non_empty


def extract_chat_thread_payload(
    metadata: dict[str, Any] | None,
) -> dict[str, str | None]:
    raw_payload = metadata.get("payload") if isinstance(metadata, dict) else None
    canonical_chat_thread = (
        raw_payload.get("chat_thread") if isinstance(raw_payload, dict) else None
    )
    if isinstance(canonical_chat_thread, dict):
        return {
            "control_thread_id": first_non_empty(
                canonical_chat_thread.get("control_thread_id"),
            ),
            "thread_id": first_non_empty(canonical_chat_thread.get("thread_id")),
            "session_id": first_non_empty(canonical_chat_thread.get("session_id")),
            "task_title": first_non_empty(canonical_chat_thread.get("task_title")),
            "industry_instance_id": first_non_empty(
                canonical_chat_thread.get("industry_instance_id"),
            ),
            "industry_label": first_non_empty(
                canonical_chat_thread.get("industry_label"),
            ),
            "owner_scope": first_non_empty(canonical_chat_thread.get("owner_scope")),
            "thread_mode": first_non_empty(canonical_chat_thread.get("thread_mode")),
            "decision_type": first_non_empty(
                canonical_chat_thread.get("decision_type"),
            ),
            "session_kind": first_non_empty(canonical_chat_thread.get("session_kind")),
        }
    request = raw_payload.get("request_context") if isinstance(raw_payload, dict) else None
    compiler = raw_payload.get("compiler") if isinstance(raw_payload, dict) else None
    meta = raw_payload.get("meta") if isinstance(raw_payload, dict) else None
    return {
        "control_thread_id": first_non_empty(
            request.get("control_thread_id") if isinstance(request, dict) else None,
            compiler.get("control_thread_id") if isinstance(compiler, dict) else None,
            meta.get("control_thread_id") if isinstance(meta, dict) else None,
        ),
        "thread_id": first_non_empty(
            request.get("thread_id") if isinstance(request, dict) else None,
            request.get("session_id") if isinstance(request, dict) else None,
        ),
        "session_id": first_non_empty(
            request.get("session_id") if isinstance(request, dict) else None,
        ),
        "task_title": first_non_empty(
            raw_payload.get("task_title") if isinstance(raw_payload, dict) else None,
            raw_payload.get("title") if isinstance(raw_payload, dict) else None,
        ),
        "industry_instance_id": first_non_empty(
            request.get("industry_instance_id") if isinstance(request, dict) else None,
        ),
        "industry_label": first_non_empty(
            request.get("industry_label") if isinstance(request, dict) else None,
        ),
        "owner_scope": first_non_empty(
            request.get("owner_scope") if isinstance(request, dict) else None,
        ),
        "thread_mode": first_non_empty(
            request.get("thread_mode") if isinstance(request, dict) else None,
            request.get("task_mode") if isinstance(request, dict) else None,
        ),
        "decision_type": first_non_empty(
            raw_payload.get("decision_type") if isinstance(raw_payload, dict) else None,
        ),
        "session_kind": first_non_empty(
            request.get("session_kind") if isinstance(request, dict) else None,
        ),
    }


__all__ = ["extract_chat_thread_payload"]
