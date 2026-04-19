# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass

from .chat_continuation_policy import decide_research_chat_continuation


@dataclass(frozen=True)
class ResearchChatContinuationPlan:
    action_kind: str
    stop_reason: str = ""
    next_round_mode: str = ""
    next_question: str = ""
    next_link_url: str = ""
    increment_link_depth: bool = False


class ResearchChatContinuationOwner:
    def __init__(
        self,
        *,
        build_followup_question,
        build_continuation_question,
    ) -> None:
        self._build_followup_question = build_followup_question
        self._build_continuation_question = build_continuation_question

    def plan(
        self,
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
    ) -> ResearchChatContinuationPlan:
        decision = decide_research_chat_continuation(
            page_kind=page_kind,
            blocker_hints=list(blocker_hints),
            round_index=round_index,
            entry_mode=entry_mode,
            has_structured_answer=has_structured_answer,
            findings_count=findings_count,
            new_findings_count=new_findings_count,
            has_adapter_gaps=has_adapter_gaps,
            selected_links_count=selected_links_count,
            deepened_link_count=deepened_link_count,
            consecutive_no_new_findings=consecutive_no_new_findings,
            next_link_url=next_link_url,
            has_pdf_link=has_pdf_link,
            raw_link_count=raw_link_count,
            current_link_depth=current_link_depth,
            max_link_depth=max_link_depth,
            max_consecutive_no_new_findings=max_consecutive_no_new_findings,
        )
        if decision.decision_kind == "stop":
            return ResearchChatContinuationPlan(
                action_kind="stop",
                stop_reason=decision.stop_reason,
            )
        if decision.decision_kind == "deepen-link":
            link_url = str(decision.next_link_url or "").strip()
            return ResearchChatContinuationPlan(
                action_kind="deepen-link",
                next_link_url=link_url,
                next_question=f"Deepen source: {link_url}",
                increment_link_depth=bool(link_url),
            )

        next_round_mode = str(decision.next_round_mode or "").strip()
        if next_round_mode == "coverage-followup":
            next_question = str(self._build_followup_question() or "").strip()
        else:
            next_question = str(self._build_continuation_question() or "").strip()
        return ResearchChatContinuationPlan(
            action_kind="next-round",
            next_round_mode=next_round_mode or "generic-continue",
            next_question=next_question,
        )


__all__ = [
    "ResearchChatContinuationOwner",
    "ResearchChatContinuationPlan",
]
