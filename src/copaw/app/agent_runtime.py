# -*- coding: utf-8 -*-
"""Local direct-ingress runtime app for `/api/agent`.

This replaces the external AgentApp shell so direct agent requests enter the
same kernel-owned turn execution path as other ingress surfaces.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from agentscope_runtime.engine.schemas.agent_schemas import AgentRequest

from ..__version__ import __version__
from .runtime_chat_media import enrich_agent_request_with_media

logger = logging.getLogger(__name__)

_AGENT_RUNTIME_MODE = "daemon_thread"


def create_agent_runtime_app() -> FastAPI:
    """Create a local FastAPI sub-app for direct `/api/agent` ingress."""

    app = FastAPI(
        title="Spider Mesh Agent Runtime",
        description="Kernel-native direct ingress for /api/agent/process",
        version=__version__,
    )
    app.state._local_tasks = {}

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health_check(request: Request) -> dict[str, Any]:
        parent_app = _resolve_parent_app(request)
        turn_executor = getattr(parent_app.state, "turn_executor", None)
        return {
            "status": "healthy",
            "mode": _AGENT_RUNTIME_MODE,
            "runner": "ready" if turn_executor is not None else "not_ready",
        }

    @app.get("/")
    async def root() -> dict[str, Any]:
        return {
            "service": "Spider Mesh Agent Runtime",
            "mode": _AGENT_RUNTIME_MODE,
            "endpoints": {
                "process": "/process",
                "stream": "/process/stream",
                "health": "/health",
            },
        }

    @app.post("/shutdown")
    async def shutdown_process_simple() -> dict[str, str]:
        asyncio.create_task(_delayed_sigterm(delay_seconds=0.5))
        return {"status": "shutting down"}

    @app.post("/admin/shutdown")
    async def shutdown_process() -> dict[str, str]:
        asyncio.create_task(_delayed_sigterm(delay_seconds=1.0))
        return {"message": "Shutdown initiated"}

    @app.get("/admin/status")
    async def get_process_status() -> dict[str, Any]:
        try:
            import psutil

            proc = psutil.Process(os.getpid())
            return {
                "pid": os.getpid(),
                "status": proc.status(),
                "memory_usage": proc.memory_info().rss,
                "cpu_percent": proc.cpu_percent(),
                "uptime": proc.create_time(),
            }
        except Exception:
            logger.exception("Failed to collect process status for /api/agent")
            return {
                "pid": os.getpid(),
                "status": "unknown",
                "memory_usage": None,
                "cpu_percent": None,
                "uptime": None,
            }

    @app.post(
        "/process",
        openapi_extra={
            "requestBody": {
                "content": {
                    "application/json": {
                        "schema": {
                            "$ref": "#/components/schemas/AgentRequest",
                        },
                    },
                },
                "required": True,
                "description": (
                    "Agent API Request Format. Direct ingress is executed by "
                    "Spider Mesh's kernel-owned turn executor."
                ),
            },
        },
        tags=["agent-api"],
    )
    async def process_agent_request(
        request_payload: AgentRequest,
        request: Request,
    ) -> StreamingResponse:
        turn_executor = _get_turn_executor(request)
        parent_app = _resolve_parent_app(request)
        request_payload, _, _ = await enrich_agent_request_with_media(
            request_payload,
            app_state=parent_app.state,
        )
        return StreamingResponse(
            _stream_process_events(
                request=request,
                request_payload=request_payload,
                turn_executor=turn_executor,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    return app


def _resolve_parent_app(request: Request) -> FastAPI:
    parent_app = getattr(request.app.state, "parent_app", None)
    if parent_app is not None:
        return parent_app
    return request.app


def _get_turn_executor(request: Request) -> Any:
    parent_app = _resolve_parent_app(request)
    turn_executor = getattr(parent_app.state, "turn_executor", None)
    if turn_executor is None:
        raise HTTPException(
            status_code=503,
            detail="Kernel turn executor is not initialized",
        )
    return turn_executor


def _local_tasks(app: FastAPI) -> dict[str, asyncio.Task]:
    tasks = getattr(app.state, "_local_tasks", None)
    if not isinstance(tasks, dict):
        tasks = {}
        app.state._local_tasks = tasks
    return tasks


async def _stream_process_events(
    *,
    request: Request,
    request_payload: AgentRequest,
    turn_executor: Any,
) -> AsyncIterator[str]:
    current_task = asyncio.current_task()
    task_key = f"{request_payload.id or 'agent-process'}:{uuid.uuid4().hex}"
    local_tasks = _local_tasks(request.app)
    if current_task is not None:
        local_tasks[task_key] = current_task

    try:
        async for event in turn_executor.stream_request(request_payload):
            yield _encode_sse_event(event)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception("Direct /api/agent/process stream failed")
        yield _encode_sse_event({"error": str(exc)})
    finally:
        if current_task is not None and local_tasks.get(task_key) is current_task:
            local_tasks.pop(task_key, None)


def _encode_sse_event(event: Any) -> str:
    if hasattr(event, "model_dump_json"):
        payload = event.model_dump_json()
    elif hasattr(event, "json"):
        payload = event.json()
    else:
        payload = json.dumps(event, ensure_ascii=False)
    return f"data: {payload}\n\n"


async def _delayed_sigterm(*, delay_seconds: float) -> None:
    await asyncio.sleep(delay_seconds)
    os.kill(os.getpid(), signal.SIGTERM)


__all__ = ["create_agent_runtime_app"]
