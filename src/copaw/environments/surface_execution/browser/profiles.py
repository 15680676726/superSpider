# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .contracts import BrowserObservation
from .observer import observe_browser_page

BrowserDomProbeBuilder = Callable[..., Mapping[str, Any] | None]


@dataclass(frozen=True)
class BrowserPageProfile:
    profile_id: str
    page_title: str = ""
    dom_probe_builder: BrowserDomProbeBuilder | None = None
    include_generic_live_probe: bool = False


def _capture_generic_live_probe(
    *,
    browser_runner,
    session_id: str,
    page_id: str,
) -> dict[str, object]:
    payload = browser_runner(
        action="evaluate",
        session_id=session_id,
        page_id=page_id,
        code=(
            "(() => ({"
            " bodyText: (document.body && document.body.innerText) ? document.body.innerText : '',"
            " href: location.href || '',"
            " title: document.title || ''"
            " }))()"
        ),
    )
    result = payload.get("result") if isinstance(payload, dict) else {}
    if not isinstance(result, Mapping):
        return {}
    return {
        "body_text": str(result.get("bodyText") or result.get("body_text") or ""),
        "page_url": str(result.get("href") or ""),
        "page_title": str(result.get("title") or ""),
    }


def _merge_dom_probes(
    *,
    base_probe: Mapping[str, Any] | None,
    overlay_probe: Mapping[str, Any] | None,
) -> dict[str, object]:
    merged: dict[str, object] = dict(base_probe or {})
    overlay = dict(overlay_probe or {})
    for key in ("inputs", "targets", "control_groups", "readable_sections", "blockers"):
        combined: list[object] = []
        for source in (base_probe or {}, overlay):
            value = source.get(key)
            if isinstance(value, list):
                combined.extend(value)
        if combined:
            merged[key] = combined
    for key, value in overlay.items():
        if key in {"inputs", "targets", "control_groups", "readable_sections", "blockers"}:
            continue
        merged[key] = value
    return merged


def capture_live_browser_page_context(
    *,
    browser_runner,
    session_id: str,
    page_id: str,
    profile: BrowserPageProfile | None = None,
    page_url: str = "",
    page_title: str = "",
) -> dict[str, object]:
    snapshot_payload = browser_runner(
        action="snapshot",
        session_id=session_id,
        page_id=page_id,
    )
    if not isinstance(snapshot_payload, dict):
        snapshot_payload = {}
    snapshot_text = str(snapshot_payload.get("snapshot") or "")
    resolved_page_url = str(snapshot_payload.get("url") or page_url or "")
    resolved_page_title = (
        page_title
        or (profile.page_title if profile is not None else "")
        or str(snapshot_payload.get("title") or "")
    )
    generic_probe: dict[str, object] = {}
    if profile is None or bool(profile.include_generic_live_probe):
        generic_probe = _capture_generic_live_probe(
            browser_runner=browser_runner,
            session_id=session_id,
            page_id=page_id,
        )
    if not resolved_page_url:
        resolved_page_url = str(generic_probe.get("page_url") or "")
    if not resolved_page_title:
        resolved_page_title = str(generic_probe.get("page_title") or "")
    dom_probe: Mapping[str, Any] | None = generic_probe
    if profile is not None and callable(profile.dom_probe_builder):
        profile_probe = profile.dom_probe_builder(
            browser_runner=browser_runner,
            session_id=session_id,
            page_id=page_id,
            snapshot_text=snapshot_text,
            page_url=resolved_page_url,
            page_title=resolved_page_title,
        )
        dom_probe = _merge_dom_probes(base_probe=generic_probe, overlay_probe=profile_probe)
    observation = observe_browser_page(
        snapshot_text=snapshot_text,
        page_url=resolved_page_url,
        page_title=resolved_page_title,
        dom_probe=dom_probe,
    )
    return {
        "snapshot_text": snapshot_text,
        "page_url": resolved_page_url,
        "page_title": resolved_page_title,
        "dom_probe": dict(dom_probe or {}),
        "observation": observation,
    }


def observe_live_browser_page(
    *,
    browser_runner,
    session_id: str,
    page_id: str,
    profile: BrowserPageProfile | None = None,
    page_url: str = "",
    page_title: str = "",
) -> BrowserObservation:
    context = capture_live_browser_page_context(
        browser_runner=browser_runner,
        session_id=session_id,
        page_id=page_id,
        profile=profile,
        page_url=page_url,
        page_title=page_title,
    )
    return context["observation"]  # type: ignore[return-value]


__all__ = [
    "BrowserPageProfile",
    "BrowserDomProbeBuilder",
    "capture_live_browser_page_context",
    "observe_live_browser_page",
]
