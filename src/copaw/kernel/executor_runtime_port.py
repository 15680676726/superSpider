# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol


@dataclass(slots=True)
class ExecutorTurnStartResult:
    thread_id: str
    turn_id: str
    model_ref: str | None = None
    runtime_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExecutorNormalizedEvent:
    event_type: str
    source_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    raw_method: str | None = None


class ExecutorRuntimePort(Protocol):
    def start_assignment_turn(
        self,
        *,
        assignment_id: str,
        project_root: str,
        prompt: str,
        thread_id: str | None = None,
        model_ref: str | None = None,
        sidecar_launch_payload: dict[str, Any] | None = None,
    ) -> ExecutorTurnStartResult: ...

    def steer_turn(
        self,
        *,
        thread_id: str,
        turn_id: str,
        prompt: str,
    ) -> dict[str, Any]: ...

    def stop_turn(
        self,
        *,
        thread_id: str,
        turn_id: str | None = None,
    ) -> dict[str, Any]: ...

    def subscribe_events(self, *, thread_id: str) -> Iterable[ExecutorNormalizedEvent]: ...

    def normalize_event(
        self,
        payload: dict[str, Any],
    ) -> ExecutorNormalizedEvent | None: ...
