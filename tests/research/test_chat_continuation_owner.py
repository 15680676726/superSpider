from __future__ import annotations

from copaw.research.chat_continuation_owner import ResearchChatContinuationOwner


def test_owner_builds_coverage_followup_round_from_first_structured_answer() -> None:
    owner = ResearchChatContinuationOwner(
        build_followup_question=lambda: "follow up question",
        build_continuation_question=lambda: "continue question",
    )

    outcome = owner.plan(
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

    assert outcome.action_kind == "next-round"
    assert outcome.next_round_mode == "coverage-followup"
    assert outcome.next_question == "follow up question"


def test_owner_builds_deepen_link_action_from_shared_policy() -> None:
    owner = ResearchChatContinuationOwner(
        build_followup_question=lambda: "follow up question",
        build_continuation_question=lambda: "continue question",
    )

    outcome = owner.plan(
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

    assert outcome.action_kind == "deepen-link"
    assert outcome.next_link_url == "https://example.com/source-1"
    assert outcome.next_question == "Deepen source: https://example.com/source-1"
    assert outcome.increment_link_depth is True


def test_owner_stops_when_shared_policy_says_followup_complete() -> None:
    owner = ResearchChatContinuationOwner(
        build_followup_question=lambda: "follow up question",
        build_continuation_question=lambda: "continue question",
    )

    outcome = owner.plan(
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

    assert outcome.action_kind == "stop"
    assert outcome.stop_reason == "followup-complete"


def test_owner_falls_back_to_generic_continue_question() -> None:
    owner = ResearchChatContinuationOwner(
        build_followup_question=lambda: "follow up question",
        build_continuation_question=lambda: "continue question",
    )

    outcome = owner.plan(
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

    assert outcome.action_kind == "next-round"
    assert outcome.next_round_mode == "generic-continue"
    assert outcome.next_question == "continue question"
