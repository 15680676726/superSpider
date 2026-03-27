# -*- coding: utf-8 -*-
# pylint: disable=too-many-return-statements
"""
Bridge between channels and the SRK kernel: factory to build
ProcessHandler from KernelDispatcher. Shared helpers for channels (e.g. file URL).
"""
from __future__ import annotations

import os
from typing import Any, Optional

from ..runtime_commands import infer_turn_capability_and_risk
from ...kernel import KernelDispatcher, KernelTask
from urllib.parse import urlparse
from urllib.request import url2pathname


def file_url_to_local_path(url: str) -> Optional[str]:
    """Convert file:// URL or plain local path to local path string.

    Supports:
    - file:// URL (all platforms): file:///path, file://D:/path,
      file://D:\\path (Windows two-slash).
    - Plain local path: D:\\path, /tmp/foo (no scheme). Pass-through after
      stripping whitespace; no existence check (caller may use Path().exists).

    Returns None only when url is clearly not a local file (e.g. http(s) URL)
    or file URL could not be resolved to a non-empty path.
    """
    if not url or not isinstance(url, str):
        return None
    s = url.strip()
    if not s:
        return None
    parsed = urlparse(s)
    if parsed.scheme == "file":
        path = url2pathname(parsed.path)
        if not path and parsed.netloc:
            path = url2pathname(parsed.netloc.replace("\\", "/"))
        elif (
            path
            and parsed.netloc
            and len(parsed.netloc) == 1
            and os.name == "nt"
        ):
            path = f"{parsed.netloc}:{path}"
        return path if path else None
    if parsed.scheme in ("http", "https"):
        return None
    if not parsed.scheme:
        return s
    if (
        os.name == "nt"
        and len(parsed.scheme) == 1
        and parsed.path.startswith("\\")
    ):
        return s
    return None


def make_process_from_kernel(dispatcher: KernelDispatcher):
    """
    Use SRK KernelDispatcher as the channel's process.

    Each channel does: native -> build_agent_request_from_native()
        -> process(request) -> kernel submit/execute.
    Dispatches through system:dispatch_query so all ingress is owned
    by the kernel, not runner.stream_query.
    """

    async def _process(request: Any):
        request_payload: dict[str, object] | None
        if hasattr(request, "model_dump"):
            request_payload = request.model_dump(mode="json")
        elif isinstance(request, dict):
            request_payload = dict(request)
        else:
            request_payload = None

        session_id = getattr(request, "session_id", None)
        user_id = getattr(request, "user_id", None)
        channel = getattr(request, "channel", None)
        if request_payload:
            session_id = session_id or request_payload.get("session_id")
            user_id = user_id or request_payload.get("user_id")
            channel = channel or request_payload.get("channel")

        if not session_id or not user_id or not channel:
            raise RuntimeError("Channel ingress missing session/user/channel identifiers.")

        query_text = None
        query_preview = None
        if request_payload:
            input_payload = request_payload.get("input") or []
            if input_payload:
                first = input_payload[0] or {}
                content = first.get("content") if isinstance(first, dict) else None
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            text = str(item.get("text") or "").strip()
                            if text:
                                query_text = text
                                query_preview = text[:60]
                                break

        meta = getattr(request, "channel_meta", None)
        if meta is None and request_payload:
            meta = request_payload.get("channel_meta")
        if not isinstance(meta, dict):
            meta = {}

        capability_ref, risk_level = infer_turn_capability_and_risk(query_text)
        task = KernelTask(
            title=query_preview or f"Channel query from {user_id}@{channel}",
            capability_ref=capability_ref,
            environment_ref=f"session:{channel}:{session_id}",
            owner_agent_id="copaw-channel-ingress",
            risk_level=risk_level,
            payload={
                "request": request_payload or {},
                "channel": str(channel),
                "user_id": str(user_id),
                "session_id": str(session_id),
                "mode": "stream",
                "meta": meta,
            },
        )
        task.payload["task_id"] = task.id
        admission = dispatcher.submit(task)
        if admission.phase != "executing":
            if admission.phase == "waiting-confirm":
                raise RuntimeError(
                    "Channel ingress task requires confirmation before execution.",
                )
            raise RuntimeError(
                admission.error
                or admission.summary
                or (
                    "Channel ingress task was not admitted for execution "
                    f"(phase={admission.phase})."
                ),
            )
        result = await dispatcher.execute_task(task.id)
        if not result.success:
            raise RuntimeError(
                result.error or result.summary or "Channel ingress execution failed.",
            )
        if False:
            yield None

    return _process
