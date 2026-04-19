from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ResearchChatDecisionKind = Literal["stop", "deepen-link", "next-round"]


@dataclass(frozen=True)
class ResearchChatContinuationDecision:
    decision_kind: ResearchChatDecisionKind
    stop_reason: str = ""
    next_round_mode: str = ""
    next_link_url: str = ""


def decide_research_chat_continuation(
    *,
    page_kind: str,
    blocker_hints: list[str],
    round_index: int,
    entry_mode: str,
    has_structured_answer: bool,
    findings_count: int,
    new_findings_count: int,
    has_adapter_gaps: bool,
    selected_links_count: int,
    deepened_link_count: int,
    consecutive_no_new_findings: int,
    next_link_url: str,
    has_pdf_link: bool,
    raw_link_count: int,
    current_link_depth: int,
    max_link_depth: int,
    max_consecutive_no_new_findings: int,
) -> ResearchChatContinuationDecision:
    normalized_blockers = {str(item or "").strip() for item in blocker_hints if str(item or "").strip()}
    normalized_entry_mode = str(entry_mode or "").strip()
    if str(page_kind or "").strip() == "login-wall" or "login-required" in normalized_blockers:
        return ResearchChatContinuationDecision(
            decision_kind="stop",
            stop_reason="waiting-login",
        )

    should_deepen = bool(
        str(next_link_url or "").strip()
        and not has_structured_answer
        and (raw_link_count > 1 or has_pdf_link)
        and current_link_depth < max_link_depth
    )
    if should_deepen:
        return ResearchChatContinuationDecision(
            decision_kind="deepen-link",
            next_link_url=str(next_link_url or "").strip(),
        )

    if has_structured_answer and round_index == 1:
        return ResearchChatContinuationDecision(
            decision_kind="next-round",
            next_round_mode="coverage-followup",
        )

    if (
        has_structured_answer
        and normalized_entry_mode == "resume-followup"
        and not has_adapter_gaps
        and new_findings_count >= 1
    ):
        return ResearchChatContinuationDecision(
            decision_kind="stop",
            stop_reason="followup-complete",
        )

    if (
        has_structured_answer
        and normalized_entry_mode == "coverage-followup"
        and not has_adapter_gaps
        and new_findings_count >= 2
    ):
        return ResearchChatContinuationDecision(
            decision_kind="stop",
            stop_reason="followup-complete",
        )

    if (
        has_structured_answer
        and normalized_entry_mode == "generic-continue"
        and not has_adapter_gaps
        and new_findings_count >= 1
    ):
        return ResearchChatContinuationDecision(
            decision_kind="stop",
            stop_reason="followup-complete",
        )

    if selected_links_count == 0 and deepened_link_count == 0 and round_index == 1 and findings_count >= 2:
        return ResearchChatContinuationDecision(
            decision_kind="stop",
            stop_reason="enough-findings",
        )

    if consecutive_no_new_findings >= max_consecutive_no_new_findings:
        return ResearchChatContinuationDecision(
            decision_kind="stop",
            stop_reason="no-new-findings",
        )

    if deepened_link_count > 0:
        return ResearchChatContinuationDecision(
            decision_kind="stop",
            stop_reason="deepened-link-closed",
        )

    return ResearchChatContinuationDecision(
        decision_kind="next-round",
        next_round_mode="generic-continue",
    )


__all__ = [
    "ResearchChatContinuationDecision",
    "decide_research_chat_continuation",
]
