# -*- coding: utf-8 -*-
from __future__ import annotations


def _extract_event_text(value: object | None) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = str(item.get("text") or "").strip()
            else:
                text = str(getattr(item, "text", "") or "").strip()
            if text:
                parts.append(text)
        if parts:
            return "\n".join(parts)
    return None


def _resolve_dispatch_summary(event: object | None, fallback: str) -> str:
    if isinstance(event, dict):
        return (
            _extract_event_text(event.get("content"))
            or _extract_event_text(event.get("message"))
            or fallback
        )
    if event is not None:
        return (
            _extract_event_text(getattr(event, "content", None))
            or _extract_event_text(getattr(event, "message", None))
            or fallback
        )
    return fallback


def _normalize_dispatch_status(value: object | None) -> str:
    status = str(value or "").strip().lower()
    if status == "canceled":
        return "cancelled"
    return status


def _default_dispatch_error(summary: str) -> str:
    lowered = summary.strip().lower()
    if "command" in lowered:
        return "command runtime failed"
    return "query runtime failed"


class SystemDispatchFacade:
    def __init__(
        self,
        *,
        channel_manager: object | None = None,
        turn_executor: object | None = None,
    ) -> None:
        self._channel_manager = channel_manager
        self._turn_executor = turn_executor

    def set_channel_manager(self, channel_manager: object | None) -> None:
        self._channel_manager = channel_manager

    def set_turn_executor(self, turn_executor: object | None) -> None:
        self._turn_executor = turn_executor

    async def handle_send_channel_text(
        self,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        if self._channel_manager is None:
            return {"success": False, "error": "Channel manager is not available"}
        channel = str(resolved_payload.get("channel") or "")
        user_id = str(resolved_payload.get("user_id") or "")
        session_id = str(resolved_payload.get("session_id") or "")
        text = str(resolved_payload.get("text") or "")
        meta = resolved_payload.get("meta") or {}
        if not channel or not user_id or not session_id or not text:
            return {
                "success": False,
                "error": "channel/user_id/session_id/text are required",
            }
        await self._channel_manager.send_text(
            channel=channel,
            user_id=user_id,
            session_id=session_id,
            text=text,
            meta=meta if isinstance(meta, dict) else {},
        )
        return {
            "success": True,
            "summary": f"Sent text to {channel}/{user_id}.",
            "channel": channel,
            "user_id": user_id,
            "session_id": session_id,
        }

    async def execute_turn_dispatch(
        self,
        resolved_payload: dict[str, object],
        *,
        summary: str,
    ) -> dict[str, object]:
        if self._turn_executor is None:
            return {
                "success": False,
                "error": "Kernel query executor is not available",
            }

        request_payload = (
            resolved_payload.get("dispatch_request")
            or resolved_payload.get("normalized_request")
            or resolved_payload.get("request")
            or resolved_payload.get("request_payload")
            or resolved_payload.get("agent_request")
            or {}
        )
        if hasattr(request_payload, "model_dump"):
            request_payload = request_payload.model_dump(mode="json")
        if not isinstance(request_payload, dict):
            return {"success": False, "error": "request payload must be a dict"}
        request_payload = dict(request_payload)

        channel = str(
            resolved_payload.get("channel") or request_payload.get("channel") or "",
        )
        user_id = str(
            resolved_payload.get("user_id") or request_payload.get("user_id") or "",
        )
        session_id = str(
            resolved_payload.get("session_id")
            or request_payload.get("session_id")
            or "",
        )
        if user_id:
            request_payload.setdefault("user_id", user_id)
        if session_id:
            request_payload.setdefault("session_id", session_id)
        if channel:
            request_payload.setdefault("channel", channel)

        dispatch_meta = resolved_payload.get("meta") or resolved_payload.get(
            "dispatch_meta",
        )
        if not isinstance(dispatch_meta, dict):
            dispatch_meta = {}

        mode = str(
            resolved_payload.get("mode")
            or resolved_payload.get("dispatch_mode")
            or "stream",
        )
        dispatch_events = resolved_payload.get("dispatch_events", True)
        dispatch_channel = str(
            resolved_payload.get("dispatch_channel") or channel or "",
        )
        dispatch_user_id = str(
            resolved_payload.get("dispatch_user_id") or user_id or "",
        )
        dispatch_session_id = str(
            resolved_payload.get("dispatch_session_id") or session_id or "",
        )
        task_id = str(
            resolved_payload.get("task_id")
            or resolved_payload.get("kernel_task_id")
            or "",
        )

        last_event = None
        last_message_event = None
        async for event in self._turn_executor.stream_request(
            request_payload,
            kernel_task_id=task_id or None,
            skip_kernel_admission=False,
        ):
            last_event = event
            if (
                isinstance(event, dict)
                and str(event.get("object") or "").strip().lower() == "message"
            ) or (
                event is not None
                and str(getattr(event, "object", "") or "").strip().lower() == "message"
            ):
                last_message_event = event
            if mode == "final":
                continue
            if (
                dispatch_events
                and self._channel_manager is not None
                and dispatch_channel
                and dispatch_user_id
                and dispatch_session_id
            ):
                await self._channel_manager.send_event(
                    channel=dispatch_channel,
                    user_id=dispatch_user_id,
                    session_id=dispatch_session_id,
                    event=event,
                    meta=dispatch_meta,
                )

        if mode == "final" and last_event is not None:
            if (
                dispatch_events
                and self._channel_manager is not None
                and dispatch_channel
                and dispatch_user_id
                and dispatch_session_id
            ):
                await self._channel_manager.send_event(
                    channel=dispatch_channel,
                    user_id=dispatch_user_id,
                    session_id=dispatch_session_id,
                    event=last_event,
                    meta=dispatch_meta,
                )

        event_status = ""
        if isinstance(last_event, dict):
            event_status = str(last_event.get("status") or "")
        elif last_event is not None:
            event_status = str(getattr(last_event, "status", "") or "")
        normalized_status = _normalize_dispatch_status(event_status)
        success = normalized_status not in {"failed", "error", "cancelled"}
        error = None
        if not success:
            if isinstance(last_event, dict):
                error_payload = last_event.get("error")
                if isinstance(error_payload, dict):
                    error = str(
                        error_payload.get("message")
                        or error_payload.get("detail")
                        or "",
                    ).strip() or None
                elif error_payload is not None:
                    error = str(error_payload).strip() or None
            elif last_event is not None:
                error_payload = getattr(last_event, "error", None)
                if error_payload is not None:
                    error = str(
                        getattr(error_payload, "message", None) or error_payload,
                    ).strip() or None
            if error is None:
                error = _default_dispatch_error(summary)

        effective_summary = _resolve_dispatch_summary(last_message_event, summary)
        return {
            "success": success,
            "summary": effective_summary if success else (error or effective_summary),
            "error": error,
            "dispatch_status": normalized_status or None,
            "task_id": task_id or None,
            "channel": channel or None,
            "user_id": user_id or None,
            "session_id": session_id or None,
            "dispatch_channel": dispatch_channel or None,
            "dispatch_user_id": dispatch_user_id or None,
            "dispatch_session_id": dispatch_session_id or None,
        }
