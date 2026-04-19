# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

from .contracts import BrowserObservation, BrowserPageSummary, BrowserTargetCandidate
from ..graph_compiler import compile_browser_observation_to_graph


_REF_PATTERN = re.compile(r"\[ref=(?P<ref>[^\]]+)\]")
_GENERIC_LOGIN_BLOCKER_MARKERS = (
    "请登录后继续",
    "登录后继续",
    "登录后查看",
    "当前页面需要登录",
    "需要登录",
    "sign in to continue",
    "log in to continue",
    "login required",
)


def _target_slots_from_mapping(payload: Mapping[str, Any]) -> list[str]:
    slots: list[str] = []
    raw_slots = payload.get("target_slots")
    if isinstance(raw_slots, (list, tuple, set)):
        slots.extend(str(item or "").strip() for item in raw_slots if str(item or "").strip())
    metadata = payload.get("metadata")
    if isinstance(metadata, Mapping):
        raw_metadata_slots = metadata.get("target_slots")
        if isinstance(raw_metadata_slots, (list, tuple, set)):
            slots.extend(
                str(item or "").strip()
                for item in raw_metadata_slots
                if str(item or "").strip()
            )
    return list(dict.fromkeys(slots))


def _candidate_from_mapping(payload: Mapping[str, Any]) -> BrowserTargetCandidate:
    metadata = dict(payload.get("metadata") or {})
    target_slots = _target_slots_from_mapping(payload)
    if target_slots:
        metadata["target_slots"] = target_slots
    return BrowserTargetCandidate(
        target_kind=str(payload.get("target_kind") or "input"),
        action_ref=str(payload.get("action_ref") or ""),
        action_selector=str(payload.get("action_selector") or ""),
        readback_selector=str(payload.get("readback_selector") or ""),
        element_kind=str(payload.get("element_kind") or "generic"),
        scope_anchor=str(payload.get("scope_anchor") or ""),
        score=int(payload.get("score") or 0),
        reason=str(payload.get("reason") or ""),
        metadata=metadata,
    )


def _candidate_identity(candidate: BrowserTargetCandidate) -> tuple[str, str, str]:
    return (
        str(candidate.action_ref or ""),
        str(candidate.action_selector or ""),
        str(candidate.readback_selector or ""),
    )


def _dedupe_candidates(candidates: list[BrowserTargetCandidate]) -> list[BrowserTargetCandidate]:
    deduped: list[BrowserTargetCandidate] = []
    seen: set[tuple[str, str, str]] = set()
    for candidate in candidates:
        identity = _candidate_identity(candidate)
        if identity in seen:
            continue
        seen.add(identity)
        deduped.append(candidate)
    return deduped


def _build_slot_candidates(
    candidates: list[BrowserTargetCandidate],
) -> dict[str, list[BrowserTargetCandidate]]:
    slot_candidates: dict[str, list[BrowserTargetCandidate]] = {}
    for candidate in candidates:
        raw_slots = candidate.metadata.get("target_slots")
        if not isinstance(raw_slots, list):
            continue
        for slot in raw_slots:
            normalized = str(slot or "").strip()
            if not normalized:
                continue
            slot_candidates.setdefault(normalized, []).append(candidate)
    return slot_candidates


def _snapshot_primary_input_candidates(snapshot_text: str) -> list[BrowserTargetCandidate]:
    candidates: list[BrowserTargetCandidate] = []
    for raw_line in snapshot_text.splitlines():
        line = str(raw_line or "").strip()
        if "[ref=" not in line:
            continue
        match = _REF_PATTERN.search(line)
        if match is None:
            continue
        lowered = line.casefold()
        score = 0
        if "textbox" in lowered:
            score += 10
        if "searchbox" in lowered or "combobox" in lowered:
            score += 8
        if any(token in lowered for token in ("chat", "message", "ask", "input", "search")):
            score += 4
        if any(token in line for token in ("输入", "对话", "消息", "提问")):
            score += 4
        if "button" in lowered:
            score -= 10
        if score <= 0:
            continue
        element_kind = "textarea" if "textbox" in lowered else "input"
        candidates.append(
            BrowserTargetCandidate(
                target_kind="input",
                action_ref=match.group("ref"),
                action_selector="",
                readback_selector="",
                element_kind=element_kind,
                scope_anchor="snapshot",
                score=score,
                reason="snapshot-derived primary input",
                metadata={"target_slots": ["primary_input"], "derived_from": "snapshot"},
            )
        )
    return _dedupe_candidates(candidates)


def _normalize_page_text(raw_text: object) -> str:
    if raw_text is None:
        return ""
    lines: list[str] = []
    for raw_line in str(raw_text).replace("\r\n", "\n").splitlines():
        line = str(raw_line or "").strip()
        if not line:
            continue
        lines.append(line)
    return "\n".join(lines)


def _derive_readable_sections(
    *,
    snapshot_text: str,
    payload: Mapping[str, Any],
) -> list[dict[str, object]]:
    sections: list[dict[str, object]] = []
    for raw_section in payload.get("readable_sections", []):
        if isinstance(raw_section, Mapping):
            sections.append(dict(raw_section))
    body_text = _normalize_page_text(
        payload.get("body_text")
        or payload.get("bodyText")
        or payload.get("page_text")
    )
    if body_text:
        sections.append(
            {
                "section_kind": "visible-page-text",
                "label": "页面正文",
                "text": body_text,
                "source": "live-body-text",
            }
        )
    elif snapshot_text.strip():
        sections.append(
            {
                "section_kind": "snapshot-text",
                "label": "页面快照",
                "text": _normalize_page_text(snapshot_text),
                "source": "snapshot",
            }
        )
    return sections


def _infer_login_state(
    *,
    snapshot_text: str,
    payload: Mapping[str, Any],
) -> str:
    explicit = str(payload.get("login_state") or "").strip()
    if explicit:
        return explicit
    text = "\n".join(
        part
        for part in (
            _normalize_page_text(
                payload.get("body_text")
                or payload.get("bodyText")
                or payload.get("page_text")
            ),
            _normalize_page_text(snapshot_text),
        )
        if part
    ).casefold()
    if any(marker.casefold() in text for marker in _GENERIC_LOGIN_BLOCKER_MARKERS):
        return "login-required"
    return ""


def _derive_blockers(
    *,
    login_state: str,
    payload: Mapping[str, Any],
) -> list[str]:
    blockers = [str(item) for item in payload.get("blockers", []) if str(item).strip()]
    if login_state == "login-required" and "login-required" not in blockers:
        blockers.append("login-required")
    return blockers


def _first_nonempty_line(text: str) -> str:
    for raw_line in str(text or "").splitlines():
        line = str(raw_line or "").strip()
        if line:
            return line
    return ""


def _derive_page_summary(
    *,
    page_title: str,
    snapshot_text: str,
    readable_sections: list[dict[str, object]],
    interactive_targets: list[BrowserTargetCandidate],
    input_candidates: list[BrowserTargetCandidate],
    login_state: str,
    blockers: list[str],
) -> BrowserPageSummary:
    section_texts = [
        _normalize_page_text(section.get("text"))
        for section in readable_sections
        if isinstance(section, Mapping) and _normalize_page_text(section.get("text"))
    ]
    primary_text = next((text for text in section_texts if text), _normalize_page_text(snapshot_text))
    headline = _first_nonempty_line(primary_text) or str(page_title or "").strip()
    blocker_hints = [str(item or "").strip() for item in blockers if str(item or "").strip()]
    labels_text = "\n".join(
        str(candidate.metadata.get("label") or candidate.reason or "").strip()
        for candidate in interactive_targets
        if str(candidate.metadata.get("label") or candidate.reason or "").strip()
    )
    combined_text = "\n".join(part for part in [primary_text, _normalize_page_text(snapshot_text), labels_text] if part)
    lowered = combined_text.casefold()
    action_hints: list[str] = []
    page_kind = "content-page" if primary_text else "unknown"
    if login_state == "login-required" or "login-required" in blocker_hints:
        page_kind = "login-wall"
        action_hints.append("resolve-login")
    else:
        upload_markers = ("upload", "manuscript", "submit file", "file upload", "上传")
        has_upload_cue = any(marker in lowered for marker in upload_markers)
        if has_upload_cue:
            page_kind = "upload-flow"
            if input_candidates:
                action_hints.append("review-before-upload")
            action_hints.append("upload")
        elif input_candidates:
            page_kind = "form-flow"
            action_hints.append("fill-form")
            submit_markers = ("submit", "send", "continue", "next")
            if any(marker in lowered for marker in submit_markers):
                action_hints.append("submit")
    action_hints = list(dict.fromkeys(action_hints))
    return BrowserPageSummary(
        page_kind=page_kind,
        headline=headline,
        primary_text=primary_text,
        action_hints=action_hints,
        blocker_hints=blocker_hints,
    )


def observe_browser_page(
    *,
    snapshot_text: str,
    page_url: str = "",
    page_title: str = "",
    dom_probe: Mapping[str, Any] | None = None,
) -> BrowserObservation:
    payload = dict(dom_probe or {})
    explicit_input_candidates = [
        _candidate_from_mapping(item)
        for item in payload.get("inputs", [])
        if isinstance(item, Mapping)
    ]
    for candidate in explicit_input_candidates:
        slots = list(candidate.metadata.get("target_slots") or [])
        if "primary_input" not in slots:
            slots.append("primary_input")
        candidate.metadata["target_slots"] = slots
    snapshot_input_candidates = _snapshot_primary_input_candidates(snapshot_text)
    input_candidates = _dedupe_candidates([*explicit_input_candidates, *snapshot_input_candidates])
    extra_targets = [
        _candidate_from_mapping(item)
        for item in payload.get("targets", [])
        if isinstance(item, Mapping)
    ]
    control_groups: list[dict[str, object]] = []
    for raw_group in payload.get("control_groups", []):
        if not isinstance(raw_group, Mapping):
            continue
        group = dict(raw_group)
        group["candidates"] = [
            _candidate_from_mapping(item)
            for item in raw_group.get("candidates", [])
            if isinstance(item, Mapping)
        ]
        control_groups.append(group)
    interactive_targets = [*input_candidates, *extra_targets]
    for group in control_groups:
        interactive_targets.extend(group.get("candidates", []))
    interactive_targets = _dedupe_candidates(interactive_targets)
    readable_sections = _derive_readable_sections(snapshot_text=snapshot_text, payload=payload)
    login_state = _infer_login_state(snapshot_text=snapshot_text, payload=payload)
    blockers = _derive_blockers(login_state=login_state, payload=payload)
    observation = BrowserObservation(
        page_url=page_url,
        page_title=page_title,
        snapshot_text=snapshot_text,
        interactive_targets=interactive_targets,
        primary_input_candidates=input_candidates,
        slot_candidates=_build_slot_candidates(interactive_targets),
        control_groups=control_groups,
        readable_sections=readable_sections,
        login_state=login_state,
        blockers=blockers,
        page_summary=_derive_page_summary(
            page_title=page_title,
            snapshot_text=snapshot_text,
            readable_sections=readable_sections,
            interactive_targets=interactive_targets,
            input_candidates=input_candidates,
            login_state=login_state,
            blockers=blockers,
        ),
    )
    observation.surface_graph = compile_browser_observation_to_graph(observation)
    return observation


__all__ = ["observe_browser_page"]
