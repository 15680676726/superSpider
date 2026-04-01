# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.kernel.runtime_outcome import build_execution_diagnostics
from copaw.kernel.turn_executor import _admission_blocked_message


def test_build_execution_diagnostics_infers_waiting_confirm_contract() -> None:
    diagnostics = build_execution_diagnostics(
        phase="waiting-confirm",
        summary="Waiting for operator approval before continuing.",
    )

    assert diagnostics["failure_source"] == "waiting-confirm"
    assert diagnostics["blocked_next_step"] == (
        "Review the pending decision request before retrying the turn."
    )
    assert diagnostics["remediation_summary"] == (
        "Waiting for operator approval before continuing."
    )


def test_build_execution_diagnostics_uses_runtime_error_defaults() -> None:
    diagnostics = build_execution_diagnostics(
        phase="blocked",
        error="Runtime seat is still blocked by a host handoff.",
    )

    assert diagnostics["failure_source"] == "blocked"
    assert diagnostics["blocked_next_step"] == (
        "Resolve the current runtime blocker before retrying the turn."
    )
    assert diagnostics["remediation_summary"] == (
        "Runtime seat is still blocked by a host handoff."
    )


def test_admission_blocked_message_includes_blocked_next_step() -> None:
    msg = _admission_blocked_message(
        phase="blocked",
        summary="Runtime seat is still blocked by a host handoff.",
    )

    text = msg.get_text_content()
    if not text and isinstance(msg.content, list) and msg.content:
        first_block = msg.content[0]
        if isinstance(first_block, dict):
            text = str(first_block.get("text") or "")
    assert "Runtime seat is still blocked by a host handoff." in text
    assert (
        "Next step: Resolve the current runtime blocker before retrying the turn."
        in text
    )
