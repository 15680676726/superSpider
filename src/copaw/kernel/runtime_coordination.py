# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any


DURABLE_RUNTIME_COORDINATOR_CONTRACT = "durable-runtime-coordinator/v1"


def build_durable_runtime_coordination(
    *,
    entrypoint: str,
    coordinator_id: str | None,
    parent_id: str | None = None,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "coordinator_contract": DURABLE_RUNTIME_COORDINATOR_CONTRACT,
        "coordinator_entrypoint": entrypoint,
        "coordinator_id": str(coordinator_id or entrypoint).strip() or entrypoint,
    }
    if parent_id is not None:
        normalized_parent = str(parent_id).strip()
        if normalized_parent:
            payload["coordinator_parent_id"] = normalized_parent
    if isinstance(extras, dict):
        payload.update(extras)
    return payload
