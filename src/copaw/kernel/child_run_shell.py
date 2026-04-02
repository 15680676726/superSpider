# -*- coding: utf-8 -*-
"""Shared child-run writer coordination shell."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from .lease_heartbeat import LeaseHeartbeat


@dataclass(frozen=True, slots=True)
class ChildRunWriterContract:
    access_mode: str
    lease_class: str
    writer_lock_scope: str
    environment_ref: str | None = None


class ChildRunWriterLeaseConflict(RuntimeError):
    """Raised when a shared writer surface is already reserved elsewhere."""


def _mapping(value: object | None) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}


def _non_empty_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _resolve_contract(mapping: dict[str, object]) -> ChildRunWriterContract | None:
    access_mode = _non_empty_text(mapping.get("access_mode"))
    lease_class = _non_empty_text(mapping.get("lease_class")) or "exclusive-writer"
    writer_lock_scope = _non_empty_text(mapping.get("writer_lock_scope"))
    if access_mode != "writer" or writer_lock_scope is None:
        return None
    return ChildRunWriterContract(
        access_mode="writer",
        lease_class=lease_class,
        writer_lock_scope=writer_lock_scope,
        environment_ref=_non_empty_text(mapping.get("environment_ref")),
    )


def resolve_child_run_writer_contract(
    *,
    mailbox_item: object | None = None,
    payload: dict[str, object] | None = None,
    environment_ref: str | None = None,
) -> ChildRunWriterContract | None:
    candidates: list[dict[str, object]] = []
    if mailbox_item is not None:
        candidates.append(_mapping(getattr(mailbox_item, "metadata", None)))
        mailbox_payload = _mapping(getattr(mailbox_item, "payload", None))
        candidates.append(mailbox_payload)
        candidates.append(_mapping(mailbox_payload.get("meta")))
        nested_payload = _mapping(mailbox_payload.get("payload"))
        candidates.append(nested_payload)
        candidates.append(_mapping(nested_payload.get("meta")))
    task_payload = dict(payload or {})
    if task_payload:
        candidates.append(task_payload)
        candidates.append(_mapping(task_payload.get("meta")))
        nested_payload = _mapping(task_payload.get("payload"))
        candidates.append(nested_payload)
        candidates.append(_mapping(nested_payload.get("meta")))

    for candidate in candidates:
        contract = _resolve_contract(candidate)
        if contract is not None:
            if contract.environment_ref is not None or environment_ref is None:
                return contract
            return ChildRunWriterContract(
                access_mode=contract.access_mode,
                lease_class=contract.lease_class,
                writer_lock_scope=contract.writer_lock_scope,
                environment_ref=environment_ref,
            )
    return None


async def run_child_task_with_writer_lease(
    *,
    label: str,
    execute: Callable[[], Awaitable[Any]],
    environment_service: object | None,
    owner_agent_id: str | None,
    worker_id: str | None,
    contract: ChildRunWriterContract | None,
    ttl_seconds: int,
    heartbeat_interval_seconds: float,
) -> Any:
    if (
        contract is None
        or contract.access_mode != "writer"
        or environment_service is None
    ):
        return await execute()

    acquire = getattr(environment_service, "acquire_shared_writer_lease", None)
    heartbeat = getattr(environment_service, "heartbeat_shared_writer_lease", None)
    release = getattr(environment_service, "release_shared_writer_lease", None)
    if not callable(acquire) or not callable(heartbeat) or not callable(release):
        return await execute()

    owner = _non_empty_text(owner_agent_id) or _non_empty_text(worker_id) or "child-run"
    lease_metadata = {
        "access_mode": contract.access_mode,
        "lease_class": contract.lease_class,
        "writer_lock_scope": contract.writer_lock_scope,
        "environment_ref": contract.environment_ref,
        "owner_agent_id": _non_empty_text(owner_agent_id),
        "worker_id": _non_empty_text(worker_id),
    }
    try:
        lease = acquire(
            writer_lock_scope=contract.writer_lock_scope,
            owner=owner,
            ttl_seconds=ttl_seconds,
            metadata=lease_metadata,
        )
    except RuntimeError as exc:
        message = str(exc).lower()
        if "already leased by" in message:
            raise ChildRunWriterLeaseConflict(
                f"Writer scope '{contract.writer_lock_scope}' is already reserved.",
            ) from exc
        raise

    release_reason = "child run completed"
    try:
        async with LeaseHeartbeat(
            label=f"{label}:{contract.writer_lock_scope}",
            interval_seconds=heartbeat_interval_seconds,
            heartbeat=lambda: heartbeat(
                lease.id,
                lease_token=lease.lease_token or "",
                ttl_seconds=ttl_seconds,
                metadata=lease_metadata,
            ),
        ):
            return await execute()
    except asyncio.CancelledError:
        release_reason = "child run cancelled"
        raise
    except Exception:
        release_reason = "child run failed"
        raise
    finally:
        release(
            lease_id=lease.id,
            lease_token=lease.lease_token,
            reason=release_reason,
        )
