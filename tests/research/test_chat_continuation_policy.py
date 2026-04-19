from __future__ import annotations

from copaw.research.chat_continuation_policy import decide_research_chat_continuation


def test_policy_stops_immediately_on_login_wall_blocker() -> None:
    decision = decide_research_chat_continuation(
        page_kind="login-wall",
        blocker_hints=["login-required"],
        round_index=1,
        entry_mode="",
        has_structured_answer=False,
        findings_count=0,
        new_findings_count=0,
        has_adapter_gaps=False,
        selected_links_count=0,
        deepened_link_count=0,
        consecutive_no_new_findings=0,
        next_link_url="",
        has_pdf_link=False,
        raw_link_count=0,
        current_link_depth=0,
        max_link_depth=3,
        max_consecutive_no_new_findings=2,
    )

    assert decision.decision_kind == "stop"
    assert decision.stop_reason == "waiting-login"


def test_policy_prefers_deepen_link_when_page_has_links_but_no_answer() -> None:
    decision = decide_research_chat_continuation(
        page_kind="content-page",
        blocker_hints=[],
        round_index=1,
        entry_mode="",
        has_structured_answer=False,
        findings_count=0,
        new_findings_count=0,
        has_adapter_gaps=True,
        selected_links_count=1,
        deepened_link_count=0,
        consecutive_no_new_findings=0,
        next_link_url="https://example.com/source-1",
        has_pdf_link=True,
        raw_link_count=2,
        current_link_depth=0,
        max_link_depth=3,
        max_consecutive_no_new_findings=2,
    )

    assert decision.decision_kind == "deepen-link"
    assert decision.next_link_url == "https://example.com/source-1"


def test_policy_requests_coverage_followup_after_first_structured_answer() -> None:
    decision = decide_research_chat_continuation(
        page_kind="content-page",
        blocker_hints=[],
        round_index=1,
        entry_mode="",
        has_structured_answer=True,
        findings_count=1,
        new_findings_count=1,
        has_adapter_gaps=True,
        selected_links_count=1,
        deepened_link_count=0,
        consecutive_no_new_findings=0,
        next_link_url="",
        has_pdf_link=False,
        raw_link_count=1,
        current_link_depth=0,
        max_link_depth=3,
        max_consecutive_no_new_findings=2,
    )

    assert decision.decision_kind == "next-round"
    assert decision.next_round_mode == "coverage-followup"


def test_policy_stops_followup_complete_when_generic_continue_is_satisfied() -> None:
    decision = decide_research_chat_continuation(
        page_kind="content-page",
        blocker_hints=[],
        round_index=3,
        entry_mode="generic-continue",
        has_structured_answer=True,
        findings_count=3,
        new_findings_count=1,
        has_adapter_gaps=False,
        selected_links_count=0,
        deepened_link_count=0,
        consecutive_no_new_findings=0,
        next_link_url="",
        has_pdf_link=False,
        raw_link_count=0,
        current_link_depth=0,
        max_link_depth=3,
        max_consecutive_no_new_findings=2,
    )

    assert decision.decision_kind == "stop"
    assert decision.stop_reason == "followup-complete"


def test_policy_falls_back_to_generic_continue_when_more_clarification_is_needed() -> None:
    decision = decide_research_chat_continuation(
        page_kind="content-page",
        blocker_hints=[],
        round_index=2,
        entry_mode="coverage-followup",
        has_structured_answer=True,
        findings_count=1,
        new_findings_count=0,
        has_adapter_gaps=True,
        selected_links_count=0,
        deepened_link_count=0,
        consecutive_no_new_findings=1,
        next_link_url="",
        has_pdf_link=False,
        raw_link_count=0,
        current_link_depth=0,
        max_link_depth=3,
        max_consecutive_no_new_findings=2,
    )

    assert decision.decision_kind == "next-round"
    assert decision.next_round_mode == "generic-continue"
