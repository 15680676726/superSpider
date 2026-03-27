# -*- coding: utf-8 -*-
"""Observation and replay access for environment surfaces."""
from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .service import EnvironmentService


class EnvironmentReplayService:
    """Focused collaborator for evidence-derived replay surfaces."""

    def __init__(self, service: EnvironmentService) -> None:
        self._service = service
        self._replay_executors: dict[str, object] = {}

    @property
    def executor_types(self) -> list[str]:
        return sorted(self._replay_executors.keys())

    def register_replay_executor(
        self,
        replay_type: str,
        executor: object | None,
    ) -> None:
        key = (replay_type or "").strip()
        if not key:
            return
        if executor is None:
            self._replay_executors.pop(key, None)
            return
        self._replay_executors[key] = executor

    def list_observations(
        self,
        *,
        environment_ref: str | None,
        limit: int = 20,
    ):
        if self._service._observation_cache is None:
            return []
        resolved_ref = self._resolve_environment_ref(environment_ref)
        return self._service._observation_cache.list_recent(
            environment_ref=resolved_ref,
            limit=limit,
        )

    def get_observation(self, observation_id: str):
        if self._service._observation_cache is None:
            return None
        return self._service._observation_cache.get_observation(observation_id)

    def list_replays(
        self,
        *,
        environment_ref: str | None,
        limit: int = 20,
    ):
        if self._service._action_replay is None:
            return []
        resolved_ref = self._resolve_environment_ref(environment_ref)
        return self._service._action_replay.list_replays(
            environment_ref=resolved_ref,
            limit=limit,
        )

    def get_replay(self, replay_id: str):
        if self._service._action_replay is None:
            return None
        return self._service._action_replay.get_replay(replay_id)

    async def execute_replay(
        self,
        replay_id: str,
        *,
        actor: str = "runtime-center",
    ) -> dict[str, object]:
        if self._service._action_replay is None:
            raise RuntimeError("Action replay store is not available")
        replay = self._service._action_replay.get_replay(replay_id)
        if replay is None:
            raise KeyError(f"Replay '{replay_id}' not found")
        metadata = dict(replay.metadata or {})
        capability_ref = metadata.get("capability_ref")
        payload = metadata.get("payload")
        if not isinstance(capability_ref, str) or not capability_ref.strip():
            raise ValueError(
                f"Replay '{replay_id}' is missing capability_ref metadata",
            )
        if not isinstance(payload, dict):
            raise ValueError(
                f"Replay '{replay_id}' is missing executable payload metadata",
            )
        direct_executor = self._replay_executors.get(replay.replay_type)
        if callable(direct_executor):
            direct_result = direct_executor(
                replay,
                {
                    "actor": actor,
                    "metadata": metadata,
                    "environment_ref": metadata.get("environment_ref"),
                    "capability_ref": capability_ref,
                },
            )
            if inspect.isawaitable(direct_result):
                direct_result = await direct_result
            result_payload = (
                dict(direct_result)
                if isinstance(direct_result, dict)
                else {"value": direct_result}
            )
            result_payload.setdefault("mode", "direct")
            self._publish_runtime_event(
                topic="replay",
                action="replayed",
                payload={
                    "replay_id": replay.replay_id,
                    "mode": result_payload.get("mode"),
                },
            )
            return {
                "replay": replay.model_dump(mode="json"),
                "result": result_payload,
                "mode": "direct",
            }
        if self._service._kernel_dispatcher is None:
            raise RuntimeError("Kernel dispatcher is not available for replay execution")
        from ..kernel import KernelTask

        submitted_task = KernelTask(
            title=f"Replay {replay.replay_type}: {replay.summary}",
            capability_ref=capability_ref,
            environment_ref=(
                str(metadata.get("environment_ref"))
                if metadata.get("environment_ref")
                else None
            ),
            owner_agent_id=actor,
            risk_level=str(metadata.get("risk_level") or "guarded"),
            payload=dict(payload),
        )
        admitted = self._service._kernel_dispatcher.submit(submitted_task)
        if admitted.phase != "executing":
            result = admitted.model_dump(mode="json")
        else:
            executed = await self._service._kernel_dispatcher.execute_task(
                submitted_task.id,
            )
            result = executed.model_dump(mode="json")
        replay_action = (
            "submitted"
            if result.get("phase") == "waiting-confirm"
            else ("blocked" if result.get("phase") != "completed" else "executed")
        )
        self._publish_runtime_event(
            topic="replay",
            action=replay_action,
            payload={
                "replay_id": replay.replay_id,
                "task_id": result.get("task_id"),
                "phase": result.get("phase"),
                "decision_request_id": result.get("decision_request_id"),
            },
        )
        return {
            "replay": replay.model_dump(mode="json"),
            "result": result,
            "mode": "kernel",
        }

    def _publish_runtime_event(
        self,
        *,
        topic: str,
        action: str,
        payload: dict[str, object],
    ) -> None:
        if self._service._runtime_event_bus is None:
            return
        self._service._runtime_event_bus.publish(
            topic=topic,
            action=action,
            payload=payload,
        )

    def _resolve_environment_ref(self, env_ref: str | None) -> str | None:
        if not env_ref:
            return None
        if env_ref.startswith("env:"):
            mount = self._service.get_environment(env_ref)
            return mount.ref if mount is not None else None
        return env_ref
