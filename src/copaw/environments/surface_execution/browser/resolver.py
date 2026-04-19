# -*- coding: utf-8 -*-
from __future__ import annotations

from .contracts import BrowserObservation, BrowserTargetCandidate


def _input_rank(candidate: BrowserTargetCandidate) -> tuple[int, int, int, int]:
    readback_bonus = 1 if candidate.readback_selector else 0
    composer_bonus = 1 if candidate.scope_anchor == "composer" else 0
    textarea_bonus = 1 if candidate.element_kind == "textarea" else 0
    return (readback_bonus, composer_bonus, textarea_bonus, candidate.score)


def _toggle_rank(candidate: BrowserTargetCandidate) -> tuple[int, int, int]:
    page_wide_penalty = 0 if bool(candidate.metadata.get("is_page_wide")) else 1
    composer_bonus = 1 if candidate.scope_anchor == "composer" else 0
    return (page_wide_penalty, composer_bonus, candidate.score)


def resolve_browser_target(
    observation: BrowserObservation,
    *,
    target_slot: str,
) -> BrowserTargetCandidate | None:
    generic_candidates = observation.slot_candidates.get(target_slot, [])
    if generic_candidates:
        if target_slot == "primary_input":
            return max(generic_candidates, key=_input_rank)
        if target_slot == "reasoning_toggle":
            return max(generic_candidates, key=_toggle_rank)
        return max(generic_candidates, key=lambda candidate: (candidate.score, candidate.scope_anchor == "composer"))
    if target_slot == "primary_input":
        if not observation.primary_input_candidates:
            return None
        return max(observation.primary_input_candidates, key=_input_rank)
    if target_slot == "reasoning_toggle":
        toggle_candidates: list[BrowserTargetCandidate] = []
        for group in observation.control_groups:
            if str(group.get("group_kind") or "") != "reasoning_toggle_group":
                continue
            for candidate in group.get("candidates", []):
                if isinstance(candidate, BrowserTargetCandidate):
                    toggle_candidates.append(candidate)
        if not toggle_candidates:
            return None
        return max(toggle_candidates, key=_toggle_rank)
    return None


__all__ = ["resolve_browser_target"]
