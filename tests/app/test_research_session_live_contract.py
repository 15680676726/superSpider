# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest

from copaw.agents.tools.browser_control import list_browser_downloads, run_browser_use_json
from copaw.research import BaiduPageResearchService
from copaw.state import SQLiteStateStore
from copaw.state.repositories import SqliteResearchSessionRepository


LIVE_BAIDU_RESEARCH_SMOKE_SKIP_REASON = (
    "Set COPAW_RUN_BAIDU_RESEARCH_LIVE_SMOKE=1 to run live Baidu research session "
    "smoke coverage (opt-in; not part of default regression coverage)."
)
_DEFAULT_GOAL = "梳理电商平台入门知识结构"
_SECURITY_CHALLENGE_MARKERS = ("验证码", "安全验证", "访问验证", "异常流量")


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _live_goal() -> str:
    return os.getenv("COPAW_BAIDU_RESEARCH_LIVE_GOAL", "").strip() or _DEFAULT_GOAL


def _payload_error(payload: object) -> str:
    if isinstance(payload, dict):
        for key in ("error", "message", "result"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return repr(payload)
    return repr(payload)


def _stop_browser_session(session_id: str | None) -> None:
    normalized = str(session_id or "").strip()
    if not normalized:
        return
    try:
        run_browser_use_json(action="stop", session_id=normalized)
    except Exception:
        pass


def _ensure_live_baidu_browser_ready_or_skip() -> None:
    probe_session_id = f"baidu-live-probe-{uuid4().hex[:8]}"
    try:
        start_payload = run_browser_use_json(
            action="start",
            session_id=probe_session_id,
            headed=False,
        )
        if start_payload.get("ok") is False:
            pytest.skip(
                "Live Baidu research smoke requires a working browser runtime: "
                f"{_payload_error(start_payload)}",
            )

        open_payload = run_browser_use_json(
            action="open",
            session_id=probe_session_id,
            page_id="probe",
            url=BaiduPageResearchService.BAIDU_CHAT_URL,
        )
        if open_payload.get("ok") is False:
            pytest.skip(
                "Live Baidu research smoke could not open Baidu chat: "
                f"{_payload_error(open_payload)}",
            )

        evaluate_payload = run_browser_use_json(
            action="evaluate",
            session_id=probe_session_id,
            page_id="probe",
            code=(
                "({"
                " title: document.title || '',"
                " href: location.href || '',"
                " bodyText: (document.body && document.body.innerText ? "
                "document.body.innerText : '').slice(0, 240)"
                "})"
            ),
        )
        if evaluate_payload.get("ok") is False:
            pytest.skip(
                "Live Baidu research smoke could not read Baidu chat page state: "
                f"{_payload_error(evaluate_payload)}",
            )
        result = evaluate_payload.get("result")
        body_text = ""
        if isinstance(result, dict):
            body_text = str(result.get("bodyText") or "")
        if any(marker in body_text for marker in _SECURITY_CHALLENGE_MARKERS):
            pytest.skip(
                "Live Baidu research smoke is blocked by a Baidu security challenge: "
                f"{body_text[:120]}",
            )
    except Exception as exc:
        pytest.skip(f"Live Baidu research smoke prerequisites are unavailable: {exc}")
    finally:
        _stop_browser_session(probe_session_id)


def _build_service(tmp_path: Path) -> tuple[BaiduPageResearchService, SqliteResearchSessionRepository]:
    repository = SqliteResearchSessionRepository(SQLiteStateStore(tmp_path / "state.sqlite3"))
    return (
        BaiduPageResearchService(
            research_session_repository=repository,
            browser_action_runner=run_browser_use_json,
            browser_download_resolver=list_browser_downloads,
        ),
        repository,
    )


def test_baidu_research_live_smoke_skip_reason_declares_opt_in_boundary() -> None:
    marks = list(getattr(test_baidu_research_session_live_contract, "pytestmark", []))
    skipif_mark = next(mark for mark in marks if mark.name == "skipif")
    reason = str(skipif_mark.kwargs.get("reason", "")).lower()
    assert "opt-in" in reason
    assert "not part of default regression coverage" in reason


@pytest.mark.skipif(
    not _env_flag("COPAW_RUN_BAIDU_RESEARCH_LIVE_SMOKE"),
    reason=LIVE_BAIDU_RESEARCH_SMOKE_SKIP_REASON,
)
def test_baidu_research_session_live_contract(tmp_path: Path) -> None:
    _ensure_live_baidu_browser_ready_or_skip()
    service, repository = _build_service(tmp_path)
    goal = _live_goal()

    start_result = service.start_session(
        goal=goal,
        trigger_source="live-smoke",
        owner_agent_id="industry-researcher-live-smoke",
    )
    assert start_result.session.status == "queued"
    assert start_result.rounds[0].question == goal

    browser_session_id = ""
    try:
        result = service.run_session(start_result.session.id)
        browser_session_id = str(result.session.browser_session_id or start_result.session.id)
    finally:
        _stop_browser_session(browser_session_id or start_result.session.id)

    stored_session = repository.get_research_session(start_result.session.id)
    stored_rounds = repository.list_research_rounds(session_id=start_result.session.id)

    assert stored_session is not None
    assert stored_session.browser_session_id
    assert stored_session.owner_agent_id == "industry-researcher-live-smoke"
    assert stored_session.trigger_source == "live-smoke"
    assert stored_rounds
    assert stored_rounds[0].question == goal

    latest_round = stored_rounds[-1]
    if result.session.status == "waiting-login":
        assert result.stop_reason == "waiting-login"
        assert latest_round.decision == "login_required"
        assert "login" in str(latest_round.response_summary or "").lower()
        assert stored_session.completed_at is None
        return

    assert result.session.status == "completed"
    assert stored_session.completed_at is not None
    assert result.stop_reason in {
        "followup-complete",
        "initial-brief-complete",
        "enough-findings",
        "no-new-findings",
        "deepened-link-closed",
        "completed",
        "max-rounds",
    }
    assert len(stored_rounds) >= 2, "Completed live Baidu research session did not run a real follow-up round."
    assert any(str(round_record.response_summary or "").strip() for round_record in stored_rounds), (
        "Completed live Baidu research session returned no round summary."
    )
    assert (
        stored_session.stable_findings
        or any(round_record.raw_links for round_record in stored_rounds)
        or any(round_record.downloaded_artifacts for round_record in stored_rounds)
    ), (
        "Completed live Baidu research session produced no findings, links, or downloads."
    )
