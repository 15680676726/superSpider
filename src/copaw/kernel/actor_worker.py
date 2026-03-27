# -*- coding: utf-8 -*-
"""Resident actor worker for mailbox-driven execution."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..industry.identity import is_execution_core_agent_id
from .actor_mailbox import ActorMailboxService
from .lease_heartbeat import LeaseHeartbeat
from .models import KernelTask


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ActorWorker:
    """Single worker implementation reused across all dynamic actors."""

    def __init__(
        self,
        *,
        worker_id: str,
        mailbox_service: ActorMailboxService,
        kernel_dispatcher: object | None = None,
        environment_service: object | None = None,
        agent_runtime_repository: object | None = None,
        experience_memory_service: object | None = None,
        lease_ttl_seconds: int = 180,
        lease_heartbeat_interval_seconds: float | None = None,
    ) -> None:
        self._worker_id = worker_id
        self._mailbox_service = mailbox_service
        self._kernel_dispatcher = kernel_dispatcher
        self._environment_service = environment_service
        self._agent_runtime_repository = agent_runtime_repository
        self._experience_memory_service = experience_memory_service
        self._lease_ttl_seconds = max(30, lease_ttl_seconds)
        self._lease_heartbeat_interval_seconds = max(
            0.01,
            float(lease_heartbeat_interval_seconds or max(5.0, self._lease_ttl_seconds / 3)),
        )

    async def run_once(self, agent_id: str) -> bool:
        lease = self._acquire_actor_lease(agent_id)
        if lease is False:
            return False
        item = self._mailbox_service.claim_next(agent_id, worker_id=self._worker_id)
        if item is None:
            self._release_actor_lease(lease)
            return False
        checkpoint = self._mailbox_service.create_checkpoint(
            agent_id=agent_id,
            mailbox_id=item.id,
            task_id=item.task_id,
            work_context_id=item.work_context_id,
            checkpoint_kind="worker-step",
            status="ready",
            phase="claimed",
            conversation_thread_id=item.conversation_thread_id,
            summary=f"Claimed mailbox item {item.id}",
            snapshot_payload={"mailbox": item.model_dump(mode="json")},
        )
        try:
            started = item
            task_id = item.task_id
            if task_id is not None:
                started = self._mailbox_service.start_item(
                    item.id,
                    worker_id=self._worker_id,
                    task_id=task_id,
                )
                result = await self._execute_task_with_heartbeat(task_id, lease)
            else:
                capability_ref = str(
                    item.capability_ref
                    or item.payload.get("capability_ref")
                    or item.payload.get("capability_id")
                    or "",
                ).strip()
                if not capability_ref:
                    raise RuntimeError("Mailbox item is missing capability_ref")
                environment_ref = item.payload.get("environment_ref")
                risk_level = str(item.payload.get("risk_level") or "guarded")
                task_payload = item.payload.get("payload")
                if not isinstance(task_payload, dict):
                    task_payload = dict(item.payload)
                submitted_task = KernelTask(
                    title=item.title,
                    capability_ref=capability_ref,
                    environment_ref=str(environment_ref) if isinstance(environment_ref, str) and environment_ref.strip() else None,
                    owner_agent_id=agent_id,
                    work_context_id=item.work_context_id,
                    risk_level=(risk_level if risk_level in {"auto", "guarded", "confirm"} else "guarded"),
                    payload=dict(task_payload),
                )
                admitted = self._submit_task(submitted_task)
                task_id = submitted_task.id
                started = self._mailbox_service.start_item(
                    item.id,
                    worker_id=self._worker_id,
                    task_id=task_id,
                )
                if admitted is not None and getattr(admitted, "phase", None) != "executing":
                    phase = str(getattr(admitted, "phase", "blocked"))
                    summary = str(getattr(admitted, "summary", phase))
                    checkpoint = self._mailbox_service.create_checkpoint(
                        agent_id=agent_id,
                        mailbox_id=started.id,
                        task_id=task_id,
                        work_context_id=started.work_context_id,
                        checkpoint_kind="task-result",
                        status=(
                            "ready"
                            if phase == "waiting-confirm"
                            else "abandoned"
                            if phase == "cancelled"
                            else "failed"
                        ),
                        phase=phase,
                        conversation_thread_id=started.conversation_thread_id,
                        summary=summary,
                        resume_payload={"task_id": task_id, "phase": phase},
                    )
                    if phase == "waiting-confirm":
                        self._mailbox_service.block_item(
                            started.id,
                            reason=summary,
                            task_id=task_id,
                            checkpoint_id=checkpoint.id if checkpoint is not None else None,
                        )
                    elif phase == "cancelled":
                        self._mailbox_service.cancel_item(
                            started.id,
                            reason=summary,
                            task_id=task_id,
                            checkpoint_id=checkpoint.id if checkpoint is not None else None,
                        )
                        self._maybe_write_experience(
                            agent_id=agent_id,
                            item=started,
                            status="cancelled",
                            summary=summary,
                            task_id=task_id,
                            checkpoint_id=checkpoint.id if checkpoint is not None else None,
                        )
                    else:
                        self._mailbox_service.fail_item(
                            started.id,
                            error_summary=summary,
                            retryable=False,
                            task_id=task_id,
                            checkpoint_id=checkpoint.id if checkpoint is not None else None,
                        )
                        self._maybe_write_experience(
                            agent_id=agent_id,
                            item=started,
                            status="failed",
                            summary=summary,
                            error_summary=summary,
                            task_id=task_id,
                            checkpoint_id=checkpoint.id if checkpoint is not None else None,
                        )
                    return True
                result = await self._execute_task_with_heartbeat(task_id, lease)

            result_phase = str(getattr(result, "phase", "completed"))
            result_summary = str(getattr(result, "summary", "Actor mailbox item completed"))
            checkpoint = self._mailbox_service.create_checkpoint(
                agent_id=agent_id,
                mailbox_id=item.id,
                task_id=task_id,
                work_context_id=item.work_context_id,
                checkpoint_kind="task-result",
                status=(
                    "applied"
                    if result_phase == "completed"
                    else "ready"
                    if result_phase == "waiting-confirm"
                    else "abandoned"
                    if result_phase == "cancelled"
                    else "failed"
                ),
                phase=result_phase,
                conversation_thread_id=item.conversation_thread_id,
                summary=result_summary,
                resume_payload={"task_id": task_id, "phase": result_phase},
                snapshot_payload={"result": _model_dump(result)},
            )
            if result_phase == "completed":
                self._mailbox_service.complete_item(
                    item.id,
                    result_summary=result_summary,
                    checkpoint_id=checkpoint.id if checkpoint is not None else None,
                    task_id=task_id,
                )
                self._maybe_write_experience(
                    agent_id=agent_id,
                    item=started,
                    status="completed",
                    summary=result_summary,
                    task_id=task_id,
                    checkpoint_id=checkpoint.id if checkpoint is not None else None,
                )
            elif result_phase == "waiting-confirm":
                self._mailbox_service.block_item(
                    item.id,
                    reason=result_summary,
                    task_id=task_id,
                    checkpoint_id=checkpoint.id if checkpoint is not None else None,
                )
            elif result_phase == "cancelled":
                self._mailbox_service.cancel_item(
                    item.id,
                    reason=result_summary,
                    task_id=task_id,
                    checkpoint_id=checkpoint.id if checkpoint is not None else None,
                )
                self._maybe_write_experience(
                    agent_id=agent_id,
                    item=started,
                    status="cancelled",
                    summary=result_summary,
                    task_id=task_id,
                    checkpoint_id=checkpoint.id if checkpoint is not None else None,
                )
            else:
                self._mailbox_service.fail_item(
                    item.id,
                    error_summary=result_summary,
                    retryable=False,
                    task_id=task_id,
                    checkpoint_id=checkpoint.id if checkpoint is not None else None,
                )
                self._maybe_write_experience(
                    agent_id=agent_id,
                    item=started,
                    status="failed",
                    summary=result_summary,
                    error_summary=result_summary,
                    task_id=task_id,
                    checkpoint_id=checkpoint.id if checkpoint is not None else None,
                )
            return True
        except Exception as exc:
            failed_checkpoint = self._mailbox_service.create_checkpoint(
                agent_id=agent_id,
                mailbox_id=item.id,
                task_id=item.task_id,
                work_context_id=item.work_context_id,
                checkpoint_kind="task-result",
                status="failed",
                phase="worker-error",
                conversation_thread_id=item.conversation_thread_id,
                summary=str(exc),
                snapshot_payload={"error": str(exc)},
            )
            self._mailbox_service.fail_item(
                item.id,
                error_summary=str(exc),
                retryable=True,
                checkpoint_id=failed_checkpoint.id if failed_checkpoint is not None else None,
                task_id=item.task_id,
            )
            self._maybe_write_experience(
                agent_id=agent_id,
                item=item,
                status="failed",
                summary=str(exc),
                error_summary=str(exc),
                task_id=item.task_id,
                checkpoint_id=failed_checkpoint.id if failed_checkpoint is not None else None,
            )
            return True
        finally:
            self._release_actor_lease(lease)

    def _submit_task(self, task: KernelTask) -> Any | None:
        if self._kernel_dispatcher is None:
            raise RuntimeError("Kernel dispatcher is not available")
        submit = getattr(self._kernel_dispatcher, "submit", None)
        if not callable(submit):
            raise RuntimeError("Kernel dispatcher cannot submit tasks")
        return submit(task)

    async def _execute_task(self, task_id: str) -> Any:
        if self._kernel_dispatcher is None:
            raise RuntimeError("Kernel dispatcher is not available")
        execute = getattr(self._kernel_dispatcher, "execute_task", None)
        if not callable(execute):
            raise RuntimeError("Kernel dispatcher cannot execute tasks")
        result = execute(task_id)
        if hasattr(result, "__await__"):
            return await result
        return result

    async def _execute_task_with_heartbeat(self, task_id: str, lease) -> Any:
        heartbeat = self._build_actor_lease_heartbeat(lease)
        if heartbeat is None:
            return await self._execute_task(task_id)
        async with heartbeat:
            return await self._execute_task(task_id)

    def _acquire_actor_lease(self, agent_id: str):
        service = self._environment_service
        if service is None:
            return None
        acquire = getattr(service, "acquire_actor_lease", None)
        if not callable(acquire):
            return None
        try:
            return acquire(
                agent_id=agent_id,
                owner=self._worker_id,
                ttl_seconds=self._lease_ttl_seconds,
                metadata={"worker_id": self._worker_id},
            )
        except RuntimeError as exc:
            message = str(exc).lower()
            if "not available" in message or "already leased by" in message:
                return False
            raise

    def _release_actor_lease(self, lease) -> None:
        if lease is None or self._environment_service is None:
            return
        release = getattr(self._environment_service, "release_actor_lease", None)
        if not callable(release):
            return
        release(
            lease.id,
            lease_token=lease.lease_token,
            reason="actor worker step completed",
        )

    def _build_actor_lease_heartbeat(self, lease) -> LeaseHeartbeat | None:
        if lease is None or self._environment_service is None:
            return None
        heartbeat = getattr(self._environment_service, "heartbeat_actor_lease", None)
        if not callable(heartbeat):
            return None
        return LeaseHeartbeat(
            label=f"actor-worker:{self._worker_id}",
            interval_seconds=self._lease_heartbeat_interval_seconds,
            heartbeat=lambda: heartbeat(
                lease.id,
                lease_token=lease.lease_token,
                ttl_seconds=self._lease_ttl_seconds,
                metadata={"worker_id": self._worker_id},
            ),
        )

    def _maybe_write_experience(
        self,
        *,
        agent_id: str,
        item: object,
        status: str,
        summary: str,
        error_summary: str | None = None,
        task_id: str | None = None,
        checkpoint_id: str | None = None,
    ) -> None:
        remember = getattr(self._experience_memory_service, "remember_outcome", None)
        if not callable(remember) or is_execution_core_agent_id(agent_id):
            return
        runtime = self._get_runtime(agent_id)
        payload = getattr(item, "payload", None)
        payload_mapping = dict(payload) if isinstance(payload, dict) else {}
        task_payload = payload_mapping.get("payload")
        if not isinstance(task_payload, dict):
            task_payload = payload_mapping
        item_metadata = getattr(item, "metadata", None)
        metadata = dict(item_metadata) if isinstance(item_metadata, dict) else {}
        metadata.update(
            {
                "checkpoint_id": checkpoint_id,
                "attempt_count": getattr(item, "attempt_count", None),
                "conversation_thread_id": getattr(item, "conversation_thread_id", None),
                "worker_id": self._worker_id,
            },
        )
        remember(
            agent_id=agent_id,
            title=str(getattr(item, "title", "") or "").strip() or "Unnamed task",
            status=status,
            summary=summary,
            error_summary=error_summary,
            capability_ref=(
                str(getattr(item, "capability_ref", "") or "").strip()
                or str(task_payload.get("capability_ref") or "").strip()
                or None
            ),
            mailbox_id=str(getattr(item, "id", "") or "").strip() or None,
            task_id=task_id,
            source_agent_id=str(getattr(item, "source_agent_id", "") or "").strip() or None,
            industry_instance_id=(
                str(getattr(runtime, "industry_instance_id", "") or "").strip()
                or str(task_payload.get("industry_instance_id") or metadata.get("industry_instance_id") or "").strip()
                or None
            ),
            industry_role_id=(
                str(getattr(runtime, "industry_role_id", "") or "").strip()
                or str(task_payload.get("industry_role_id") or metadata.get("industry_role_id") or "").strip()
                or None
            ),
            role_name=str(getattr(runtime, "role_name", "") or "").strip() or None,
            owner_scope=str(task_payload.get("owner_scope") or metadata.get("owner_scope") or "").strip() or None,
            metadata=metadata,
        )

    def _get_runtime(self, agent_id: str) -> object | None:
        repository = self._agent_runtime_repository
        if repository is None:
            return None
        getter = getattr(repository, "get_runtime", None)
        if not callable(getter):
            return None
        return getter(agent_id)


def _model_dump(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value
