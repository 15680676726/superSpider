# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from ..kernel.runtime_coordination import build_durable_runtime_coordination


def build_runtime_launch_contract(
    *,
    entry_source: str,
    coordinator_id: str | None,
    durable_field_prefix: str = "",
) -> dict[str, Any]:
    normalized_entry_source = str(entry_source or "").strip() or "runtime-launch"
    coordination = build_durable_runtime_coordination(
        entrypoint=normalized_entry_source,
        coordinator_id=coordinator_id,
    )
    if durable_field_prefix:
        prefix = durable_field_prefix
        return {
            "entry_source": normalized_entry_source,
            f"{prefix}coordinator_contract": coordination["coordinator_contract"],
            f"{prefix}coordinator_entrypoint": coordination["coordinator_entrypoint"],
            f"{prefix}coordinator_id": coordination["coordinator_id"],
        }
    return {
        "entry_source": normalized_entry_source,
        **coordination,
    }


__all__ = ["build_runtime_launch_contract"]
