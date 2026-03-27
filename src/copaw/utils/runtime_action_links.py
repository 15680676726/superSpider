# -*- coding: utf-8 -*-
from __future__ import annotations


def build_decision_actions(
    decision_id: str,
    *,
    status: str = "open",
) -> dict[str, str]:
    route = f"/api/runtime-center/decisions/{decision_id}"
    if status == "reviewing":
        return {
            "approve": f"{route}/approve",
            "reject": f"{route}/reject",
        }
    return {
        "review": f"{route}/review",
        "approve": f"{route}/approve",
        "reject": f"{route}/reject",
    }


def build_patch_actions(
    patch_id: str,
    *,
    status: str,
    risk_level: str,
) -> dict[str, str]:
    base = f"/api/runtime-center/learning/patches/{patch_id}"
    if status == "proposed":
        actions = {"reject": f"{base}/reject"}
        actions["approve" if risk_level == "confirm" else "apply"] = (
            f"{base}/approve" if risk_level == "confirm" else f"{base}/apply"
        )
        return actions
    if status == "approved":
        return {"apply": f"{base}/apply", "reject": f"{base}/reject"}
    if status == "applied":
        return {"rollback": f"{base}/rollback"}
    return {}

