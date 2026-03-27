# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.utils.runtime_action_links import build_decision_actions, build_patch_actions


def test_decision_actions_use_one_shared_contract() -> None:
    assert build_decision_actions("decision-1", status="open") == {
        "review": "/api/runtime-center/decisions/decision-1/review",
        "approve": "/api/runtime-center/decisions/decision-1/approve",
        "reject": "/api/runtime-center/decisions/decision-1/reject",
    }
    assert build_decision_actions("decision-1", status="reviewing") == {
        "approve": "/api/runtime-center/decisions/decision-1/approve",
        "reject": "/api/runtime-center/decisions/decision-1/reject",
    }


def test_patch_actions_use_one_shared_contract() -> None:
    assert build_patch_actions("patch-1", status="proposed", risk_level="confirm") == {
        "reject": "/api/runtime-center/learning/patches/patch-1/reject",
        "approve": "/api/runtime-center/learning/patches/patch-1/approve",
    }
    assert build_patch_actions("patch-1", status="proposed", risk_level="auto") == {
        "reject": "/api/runtime-center/learning/patches/patch-1/reject",
        "apply": "/api/runtime-center/learning/patches/patch-1/apply",
    }
