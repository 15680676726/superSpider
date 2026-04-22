# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from typing import Any, Protocol

from ...kernel.executor_runtime_port import (
    ExecutorNormalizedEvent,
    ExecutorRuntimePort,
    ExecutorTurnStartResult,
)
from .codex_protocol import (
    build_thread_start_request,
    build_turn_start_request,
    build_turn_steer_request,
    build_turn_stop_request,
    extract_model_ref,
    extract_runtime_metadata,
    extract_thread_id,
    extract_turn_id,
    normalize_codex_event,
)


class _CodexTransport(Protocol):
    def request(
        self,
        method: str,
        params: dict[str, object] | None = None,
    ) -> dict[str, object]: ...

    def subscribe_events(self, thread_id: str) -> Iterable[dict[str, object]]: ...

    def set_server_request_handler(self, handler) -> None: ...

    def describe_sidecar(self) -> dict[str, object]: ...

    def restart(self) -> dict[str, object]: ...


class CodexAppServerAdapter(ExecutorRuntimePort):
    def __init__(self, *, transport: _CodexTransport) -> None:
        self._transport = transport

    def start_assignment_turn(
        self,
        *,
        assignment_id: str,
        project_root: str,
        prompt: str,
        thread_id: str | None = None,
        model_ref: str | None = None,
        sidecar_launch_payload: dict[str, object] | None = None,
    ) -> ExecutorTurnStartResult:
        configure_launch = getattr(self._transport, "configure_launch", None)
        if callable(configure_launch):
            configure_launch(sidecar_launch_payload=sidecar_launch_payload)
        resolved_thread_id = thread_id
        if resolved_thread_id is None:
            thread_method, thread_params = build_thread_start_request(
                assignment_id=assignment_id,
                project_root=project_root,
                model_ref=model_ref,
            )
            thread_response = self._transport.request(thread_method, thread_params)
            resolved_thread_id = extract_thread_id(thread_response)
            if resolved_thread_id is None:
                raise ValueError("Codex App Server did not return a thread id")
        else:
            thread_response = {}

        turn_method, turn_params = build_turn_start_request(
            thread_id=resolved_thread_id,
            prompt=prompt,
            assignment_id=assignment_id,
            project_root=project_root,
            model_ref=model_ref,
        )
        turn_response = self._transport.request(turn_method, turn_params)
        turn_id = extract_turn_id(turn_response)
        if turn_id is None:
            raise ValueError("Codex App Server did not return a turn id")
        return ExecutorTurnStartResult(
            thread_id=resolved_thread_id,
            turn_id=turn_id,
            model_ref=extract_model_ref(turn_response) or extract_model_ref(thread_response),
            runtime_metadata=extract_runtime_metadata(turn_response),
        )

    def steer_turn(
        self,
        *,
        thread_id: str,
        turn_id: str,
        prompt: str,
    ) -> dict[str, Any]:
        method, params = build_turn_steer_request(
            thread_id=thread_id,
            turn_id=turn_id,
            prompt=prompt,
        )
        return self._coerce_response(self._transport.request(method, params))

    def stop_turn(
        self,
        *,
        thread_id: str,
        turn_id: str | None = None,
    ) -> dict[str, Any]:
        method, params = build_turn_stop_request(
            thread_id=thread_id,
            turn_id=turn_id,
        )
        return self._coerce_response(self._transport.request(method, params))

    def subscribe_events(self, *, thread_id: str) -> Iterator[ExecutorNormalizedEvent]:
        for payload in self._transport.subscribe_events(thread_id):
            event = self.normalize_event(payload)
            if event is not None:
                yield event

    def set_server_request_handler(self, handler) -> None:
        setter = getattr(self._transport, "set_server_request_handler", None)
        if callable(setter):
            setter(handler)

    def describe_sidecar(self) -> dict[str, Any]:
        describe = getattr(self._transport, "describe_sidecar", None)
        if callable(describe):
            payload = describe()
            if isinstance(payload, Mapping):
                return dict(payload)
        return {}

    def restart_sidecar(self) -> dict[str, Any]:
        restart = getattr(self._transport, "restart", None)
        if callable(restart):
            payload = restart()
            if isinstance(payload, Mapping):
                return dict(payload)
        return {}

    def close(self) -> None:
        closer = getattr(self._transport, "close", None)
        if callable(closer):
            closer()

    def normalize_event(
        self,
        payload: dict[str, Any],
    ) -> ExecutorNormalizedEvent | None:
        if not isinstance(payload, Mapping):
            return None
        return normalize_codex_event(payload)

    @staticmethod
    def _coerce_response(payload: object) -> dict[str, Any]:
        if isinstance(payload, Mapping):
            return dict(payload)
        return {}
