from __future__ import annotations

from copaw.kernel.runtime_outcome import classify_runtime_outcome


def test_classify_runtime_outcome_does_not_treat_successful_help_text_as_timeout() -> None:
    summary = (
        "usage: openspace [-h] [--timeout TIMEOUT]\n"
        "OpenSpace help output"
    )

    assert classify_runtime_outcome(summary, success=True) == "completed"
