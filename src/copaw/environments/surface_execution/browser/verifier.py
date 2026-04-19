# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from .contracts import BrowserTargetCandidate


def read_browser_target_readback(
    *,
    browser_runner,
    session_id: str,
    page_id: str,
    candidate: BrowserTargetCandidate,
) -> dict[str, str]:
    selector = candidate.readback_selector or candidate.action_selector
    if not selector:
        payload = {
            "observed_text": "",
            "normalized_text": "",
        }
        if candidate.target_kind == "toggle":
            payload["toggle_enabled"] = "true" if bool(candidate.metadata.get("enabled")) else "false"
        return payload
    if candidate.target_kind == "toggle":
        payload = browser_runner(
            action="evaluate",
            session_id=session_id,
            page_id=page_id,
            code=(
                "(() => {"
                f" const target = document.querySelector({selector!r});"
                " if (!target) return { text: '', normalized_text: '', toggle_enabled: 'false' };"
                " const text = String(target.innerText || target.textContent || '').replace(/\\s+/g, ' ').trim();"
                " const pressed = String(target.getAttribute('aria-pressed') || '').toLowerCase();"
                " const checked = String(target.getAttribute('aria-checked') || '').toLowerCase();"
                " const dataChecked = String(target.getAttribute('data-checked') || '').toLowerCase();"
                " const className = String(target.className || '').toLowerCase();"
                " const enabled = pressed === 'true'"
                "   || checked === 'true'"
                "   || dataChecked === 'true'"
                "   || className.includes('active')"
                "   || className.includes('selected')"
                "   || className.includes('checked');"
                " return {"
                "   text,"
                "   normalized_text: text,"
                "   toggle_enabled: enabled ? 'true' : 'false'"
                " };"
                "})()"
            ),
        )
        result: Any = payload.get("result") if isinstance(payload, dict) else {}
        if not isinstance(result, dict):
            result = {}
        observed_text = str(result.get("text") or result.get("label") or "")
        normalized_text = str(result.get("normalized_text") or observed_text)
        toggle_enabled = str(
            result.get("toggle_enabled")
            or ("true" if bool(result.get("enabled")) else "false")
        ).strip().lower()
        return {
            "observed_text": observed_text,
            "normalized_text": normalized_text,
            "toggle_enabled": "true" if toggle_enabled == "true" else "false",
        }
    if candidate.element_kind in {"textarea", "input"}:
        value_expr = "(target.value || '')"
    else:
        value_expr = "(target.innerText || target.textContent || '')"
    payload = browser_runner(
        action="evaluate",
        session_id=session_id,
        page_id=page_id,
        code=(
            "(() => {"
            f" const target = document.querySelector({selector!r});"
            " if (!target) return { text: '', normalized_text: '' };"
            f" const raw = {value_expr};"
            " const text = String(raw || '').replace(/\\s+/g, ' ').trim();"
            " return { text, normalized_text: text };"
            "})()"
        ),
    )
    result: Any = payload.get("result") if isinstance(payload, dict) else {}
    if not isinstance(result, dict):
        result = {}
    observed_text = str(result.get("text") or "")
    normalized_text = str(result.get("normalized_text") or observed_text)
    return {
        "observed_text": observed_text,
        "normalized_text": normalized_text,
    }


__all__ = ["read_browser_target_readback"]
