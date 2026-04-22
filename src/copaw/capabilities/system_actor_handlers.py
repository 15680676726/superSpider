# -*- coding: utf-8 -*-
from __future__ import annotations

import inspect

from .execution_support import _model_dump_payload, _string_value


class SystemActorCapabilityFacade:
    def __init__(
        self,
        *,
        actor_mailbox_service: object | None = None,
        actor_supervisor: object | None = None,
    ) -> None:
        self._actor_mailbox_service = actor_mailbox_service
        self._actor_supervisor = actor_supervisor

    def set_actor_mailbox_service(self, actor_mailbox_service: object | None) -> None:
        self._actor_mailbox_service = actor_mailbox_service

    def set_actor_supervisor(self, actor_supervisor: object | None) -> None:
        self._actor_supervisor = actor_supervisor

    async def execute(
        self,
        capability_id: str,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        actor_mailbox_service = self._actor_mailbox_service
        if actor_mailbox_service is None:
            return {"success": False, "error": "Actor mailbox service is not available"}

        if capability_id == "system:enqueue_task":
            agent_id = str(
                resolved_payload.get("agent_id")
                or resolved_payload.get("target_agent_id")
                or resolved_payload.get("owner_agent_id")
                or "",
            ).strip()
            if not agent_id:
                return {"success": False, "error": "agent_id is required"}
            title = str(resolved_payload.get("title") or "").strip()
            if not title:
                return {"success": False, "error": "title is required"}
            payload_body = resolved_payload.get("payload")
            if payload_body is None:
                payload_body = resolved_payload.get("task_payload")
            if payload_body is None:
                payload_body = {}
            if not isinstance(payload_body, dict):
                return {"success": False, "error": "payload must be an object"}
            enqueue = getattr(actor_mailbox_service, "enqueue_item", None)
            if not callable(enqueue):
                return {
                    "success": False,
                    "error": "Actor mailbox service cannot enqueue items",
                }
            mailbox_item = enqueue(
                agent_id=agent_id,
                task_id=_string_value(resolved_payload.get("task_id")),
                source_agent_id=_string_value(
                    resolved_payload.get("source_agent_id")
                    or resolved_payload.get("owner_agent_id"),
                ),
                parent_mailbox_id=_string_value(resolved_payload.get("parent_mailbox_id")),
                envelope_type=_string_value(resolved_payload.get("envelope_type")) or "task",
                title=title,
                summary=str(resolved_payload.get("summary") or "").strip(),
                capability_ref=_string_value(resolved_payload.get("capability_ref")),
                conversation_thread_id=(
                    _string_value(resolved_payload.get("conversation_thread_id"))
                    or f"agent-chat:{agent_id}"
                ),
                payload=payload_body,
                priority=int(resolved_payload.get("priority") or 0),
                max_attempts=int(resolved_payload.get("max_attempts") or 3),
                metadata=(
                    dict(resolved_payload.get("metadata"))
                    if isinstance(resolved_payload.get("metadata"), dict)
                    else {}
                ),
            )
            execute_now = bool(
                resolved_payload.get("execute_now")
                or resolved_payload.get("run_now")
                or resolved_payload.get("execute"),
            )
            if execute_now:
                await self._maybe_run_actor_once(agent_id)
            return {
                "success": True,
                "summary": f"Enqueued mailbox work for '{agent_id}'.",
                "agent_id": agent_id,
                "mailbox": _model_dump_payload(mailbox_item),
            }

        if capability_id == "system:pause_actor":
            agent_id = str(
                resolved_payload.get("agent_id")
                or resolved_payload.get("target_agent_id")
                or "",
            ).strip()
            if not agent_id:
                return {"success": False, "error": "agent_id is required"}
            pause = getattr(actor_mailbox_service, "pause_actor", None)
            if not callable(pause):
                return {
                    "success": False,
                    "error": "Actor mailbox service cannot pause actors",
                }
            runtime = pause(agent_id, reason=_string_value(resolved_payload.get("reason")))
            return {
                "success": True,
                "summary": f"Paused actor '{agent_id}'.",
                "agent_id": agent_id,
                "runtime": _model_dump_payload(runtime),
            }

        if capability_id == "system:resume_actor":
            agent_id = str(
                resolved_payload.get("agent_id")
                or resolved_payload.get("target_agent_id")
                or "",
            ).strip()
            if not agent_id:
                return {"success": False, "error": "agent_id is required"}
            resume = getattr(actor_mailbox_service, "resume_actor", None)
            if not callable(resume):
                return {
                    "success": False,
                    "error": "Actor mailbox service cannot resume actors",
                }
            runtime = resume(agent_id)
            await self._maybe_run_actor_once(agent_id)
            return {
                "success": True,
                "summary": f"Resumed actor '{agent_id}'.",
                "agent_id": agent_id,
                "runtime": _model_dump_payload(runtime),
            }

        if capability_id == "system:cancel_actor_task":
            agent_id = str(
                resolved_payload.get("agent_id")
                or resolved_payload.get("target_agent_id")
                or "",
            ).strip()
            if not agent_id:
                return {"success": False, "error": "agent_id is required"}
            cancel_actor_task = getattr(actor_mailbox_service, "cancel_actor_task", None)
            if not callable(cancel_actor_task):
                return {
                    "success": False,
                    "error": "Actor mailbox service cannot cancel actor tasks",
                }
            result = cancel_actor_task(
                agent_id,
                task_id=_string_value(resolved_payload.get("task_id")),
            )
            return {
                "success": True,
                "summary": f"Cancelled actor work for '{agent_id}'.",
                **(
                    result
                    if isinstance(result, dict)
                    else {"result": _model_dump_payload(result)}
                ),
            }

        if capability_id == "system:retry_actor_mailbox":
            mailbox_id = str(
                resolved_payload.get("mailbox_id")
                or resolved_payload.get("item_id")
                or "",
            ).strip()
            if not mailbox_id:
                return {"success": False, "error": "mailbox_id is required"}
            get_item = getattr(actor_mailbox_service, "get_item", None)
            retry_item = getattr(actor_mailbox_service, "retry_item", None)
            if not callable(get_item) or not callable(retry_item):
                return {
                    "success": False,
                    "error": "Actor mailbox service cannot retry mailbox items",
                }
            existing_item = get_item(mailbox_id)
            if existing_item is None:
                return {
                    "success": False,
                    "error": f"Mailbox item '{mailbox_id}' not found",
                }
            agent_id = str(
                resolved_payload.get("agent_id")
                or resolved_payload.get("target_agent_id")
                or getattr(existing_item, "agent_id", "")
                or "",
            ).strip()
            if not agent_id:
                return {"success": False, "error": "agent_id is required"}
            if getattr(existing_item, "agent_id", None) != agent_id:
                return {
                    "success": False,
                    "error": f"Mailbox item '{mailbox_id}' does not belong to '{agent_id}'",
                }
            mailbox_item = retry_item(mailbox_id)
            execute_now = bool(
                resolved_payload.get("execute_now")
                or resolved_payload.get("run_now")
                or resolved_payload.get("execute"),
            )
            if execute_now:
                await self._maybe_run_actor_once(agent_id)
            return {
                "success": True,
                "summary": f"Re-queued mailbox item '{mailbox_id}' for '{agent_id}'.",
                "agent_id": agent_id,
                "mailbox": _model_dump_payload(mailbox_item),
            }

        if capability_id == "system:list_teammates":
            agent_id = str(
                resolved_payload.get("agent_id")
                or resolved_payload.get("owner_agent_id")
                or resolved_payload.get("target_agent_id")
                or "",
            ).strip()
            if not agent_id:
                return {"success": False, "error": "agent_id is required"}
            list_teammates = getattr(actor_mailbox_service, "list_teammates", None)
            if not callable(list_teammates):
                return {
                    "success": False,
                    "error": "Actor mailbox service cannot list teammates",
                }
            teammates = list_teammates(
                agent_id=agent_id,
                industry_instance_id=_string_value(
                    resolved_payload.get("industry_instance_id"),
                ),
            )
            return {
                "success": True,
                "summary": f"Listed {len(teammates)} teammate(s) for '{agent_id}'.",
                "agent_id": agent_id,
                "teammates": [_model_dump_payload(item) for item in teammates],
            }

        return {
            "success": False,
            "error": f"Unsupported actor capability '{capability_id}'",
        }

    async def _maybe_run_actor_once(self, agent_id: str) -> None:
        if self._actor_supervisor is None:
            return
        runner = getattr(self._actor_supervisor, "run_agent_once", None)
        if not callable(runner):
            return
        maybe_result = runner(agent_id)
        if inspect.isawaitable(maybe_result):
            await maybe_result
