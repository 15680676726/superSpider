# -*- coding: utf-8 -*-
from __future__ import annotations


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
        async for event in self._turn_executor.stream_request(
            request_payload,
            kernel_task_id=task_id or None,
            skip_kernel_admission=True,
        ):
            if mode == "final":
                last_event = event
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

        return {
            "success": True,
            "summary": summary,
            "task_id": task_id or None,
            "channel": channel or None,
            "user_id": user_id or None,
            "session_id": session_id or None,
            "dispatch_channel": dispatch_channel or None,
            "dispatch_user_id": dispatch_user_id or None,
            "dispatch_session_id": dispatch_session_id or None,
        }
