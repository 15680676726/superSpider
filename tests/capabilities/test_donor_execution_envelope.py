from __future__ import annotations

import asyncio


def test_donor_execution_envelope_times_out_and_normalizes_timeout_error() -> None:
    from copaw.capabilities.donor_execution_envelope import run_donor_execution_envelope

    async def _slow_action():
        await asyncio.sleep(0.05)
        return {"ok": True}

    result = asyncio.run(
        run_donor_execution_envelope(
            label="adapter:mcp",
            awaitable_factory=_slow_action,
            action_timeout_sec=0.01,
        ),
    )

    assert result["success"] is False
    assert result["outcome"] == "timeout"
    assert result["error_type"] == "timeout_error"
    assert result["heartbeat_count"] == 0


def test_donor_execution_envelope_records_heartbeat_snapshots() -> None:
    from copaw.capabilities.donor_execution_envelope import run_donor_execution_envelope

    state = {"phase": "starting"}

    async def _slow_action():
        await asyncio.sleep(0.025)
        state["phase"] = "finishing"
        await asyncio.sleep(0.025)
        return {"ok": True}

    result = asyncio.run(
        run_donor_execution_envelope(
            label="runtime:start",
            awaitable_factory=_slow_action,
            action_timeout_sec=0.2,
            heartbeat_interval_sec=0.01,
            heartbeat_snapshot_factory=lambda: {"phase": state["phase"]},
        ),
    )

    assert result["success"] is True
    assert result["outcome"] == "succeeded"
    assert result["heartbeat_count"] >= 1
    assert result["heartbeat_snapshots"][0]["phase"] == "starting"
