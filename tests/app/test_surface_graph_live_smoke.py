# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from uuid import uuid4

import pytest

from copaw.agents.tools.browser_control import run_browser_use_json
from copaw.agents.tools.desktop_actuation import (
    _observe_guided_desktop_surface,
    _run_guided_desktop_action,
)
from copaw.agents.tools.evidence_runtime import (
    bind_browser_evidence_sink,
    bind_desktop_evidence_sink,
    bind_file_evidence_sink,
)
from copaw.environments.surface_execution.browser.profiles import BrowserPageProfile
from copaw.environments.surface_execution.browser.service import (
    BrowserSurfaceExecutionService,
)
from copaw.environments.surface_execution.desktop.service import (
    DesktopSurfaceExecutionService,
)
from copaw.environments.surface_execution.document.service import (
    DocumentSurfaceExecutionService,
)


LIVE_SURFACE_GRAPH_SMOKE_SKIP_REASON = (
    "Set COPAW_RUN_SURFACE_GRAPH_LIVE_SMOKE=1 to run live surface graph smoke "
    "coverage (opt-in; not part of default regression coverage)."
)


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


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


def _wait_for_browser_status(
    *,
    session_id: str,
    page_id: str,
    expected_text: str,
    timeout_seconds: float = 10.0,
) -> str:
    deadline = time.monotonic() + timeout_seconds
    last_value = ""
    while time.monotonic() < deadline:
        payload = run_browser_use_json(
            action="evaluate",
            session_id=session_id,
            page_id=page_id,
            code=(
                "(() => {"
                "  const status = document.querySelector('#status');"
                "  return status ? String(status.textContent || '').trim() : '';"
                "})()"
            ),
        )
        if payload.get("ok") is False:
            raise AssertionError(_payload_error(payload))
        result = payload.get("result")
        last_value = str(result or "").strip()
        if last_value == expected_text:
            return last_value
        time.sleep(0.25)
    raise AssertionError(
        f"Timed out waiting for browser status {expected_text!r}; last={last_value!r}",
    )


def _browser_surface_probe_builder(
    *,
    browser_runner,
    session_id: str,
    page_id: str,
    snapshot_text: str,
    page_url: str,
    page_title: str,
) -> dict[str, object]:
    _ = snapshot_text, page_url, page_title
    payload = browser_runner(
        action="evaluate",
        session_id=session_id,
        page_id=page_id,
        code=textwrap.dedent(
            """
            (() => {
              const composer = document.querySelector('#composer');
              const send = document.querySelector('#send');
              const status = document.querySelector('#status');
              const targets = [];
              if (composer) {
                targets.push({
                  target_kind: 'input',
                  action_selector: '#composer',
                  readback_selector: '#composer',
                  element_kind: 'textarea',
                  scope_anchor: 'composer',
                  score: 12,
                  reason: 'primary composer textarea',
                  metadata: { target_slots: ['primary_input'] },
                });
              }
              if (send) {
                targets.push({
                  target_kind: 'button',
                  action_selector: '#send',
                  readback_selector: '#status',
                  element_kind: 'button',
                  scope_anchor: 'composer',
                  score: 11,
                  reason: 'submit surface smoke button',
                  metadata: { target_slots: ['submit_button'] },
                });
              }
              return {
                targets,
                readable_sections: status && String(status.textContent || '').trim()
                  ? [{
                      section_kind: 'result',
                      label: 'status',
                      summary: String(status.textContent || '').trim(),
                    }]
                  : [],
              };
            })()
            """,
        ),
    )
    result = payload.get("result") if isinstance(payload, dict) else {}
    return dict(result) if isinstance(result, dict) else {}


def _write_utf8(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content), encoding="utf-8")


def _document_observer(*, session_mount_id: str, document_path: str, document_family: str = "") -> dict[str, object]:
    _ = session_mount_id
    path = Path(document_path)
    stat = path.stat()
    return {
        "document_path": str(path),
        "document_family": document_family or "documents",
        "content_text": path.read_text(encoding="utf-8"),
        "revision_token": str(stat.st_mtime_ns),
    }


def _document_runner(
    *,
    action: str,
    session_mount_id: str,
    document_path: str,
    document_family: str = "",
    find_text: str = "",
    replace_text: str = "",
    content: str = "",
) -> dict[str, object]:
    _ = session_mount_id, document_family
    path = Path(document_path)
    if action == "edit_document_file":
        source = path.read_text(encoding="utf-8")
        path.write_text(source.replace(find_text, replace_text), encoding="utf-8")
        return {"ok": True}
    if action == "write_document_file":
        path.write_text(content, encoding="utf-8")
        return {"ok": True}
    return {"ok": False, "error": f"Unsupported document action: {action}"}


def _wait_for_desktop_observation(
    *,
    title: str,
    timeout_seconds: float = 12.0,
):
    deadline = time.monotonic() + timeout_seconds
    last_observation = None
    while time.monotonic() < deadline:
        observation = _observe_guided_desktop_surface(
            session_mount_id="surface-desktop-live",
            app_identity=title,
        )
        last_observation = observation
        if observation.slot_candidates.get("window_target"):
            return observation
        time.sleep(0.25)
    raise AssertionError(
        f"Timed out waiting for desktop window {title!r}; "
        f"last blockers={getattr(last_observation, 'blockers', [])!r}",
    )


def test_surface_graph_live_smoke_skip_reason_declares_opt_in_boundary() -> None:
    reason = LIVE_SURFACE_GRAPH_SMOKE_SKIP_REASON.lower()
    assert "opt-in" in reason
    assert "not part of default regression coverage" in reason


@pytest.mark.skipif(
    not _env_flag("COPAW_RUN_SURFACE_GRAPH_LIVE_SMOKE"),
    reason=LIVE_SURFACE_GRAPH_SMOKE_SKIP_REASON,
)
def test_live_surface_graph_browser_observe_probe_act_diff_smoke(tmp_path) -> None:
    html_path = tmp_path / "surface-browser-smoke.html"
    _write_utf8(
        html_path,
        """
        <!doctype html>
        <html>
        <body>
          <label for="composer">Prompt</label>
          <textarea id="composer"></textarea>
          <button id="send" type="button">Send</button>
          <div id="status">Idle</div>
          <script>
            const composer = document.getElementById('composer');
            const status = document.getElementById('status');
            document.getElementById('send').addEventListener('click', () => {
              status.textContent = `Published: ${composer.value.trim()}`;
              document.body.setAttribute('data-surface-state', 'published');
            });
          </script>
        </body>
        </html>
        """,
    )
    session_id = f"surface-browser-live-{uuid4().hex[:8]}"
    page_id = "surface-smoke"
    service = BrowserSurfaceExecutionService(browser_runner=run_browser_use_json)
    profile = BrowserPageProfile(
        profile_id="surface-browser-live-smoke",
        page_title="Surface Browser Smoke",
        dom_probe_builder=_browser_surface_probe_builder,
    )
    sink_payloads: list[dict[str, object]] = []

    try:
        start_payload = run_browser_use_json(
            action="start",
            session_id=session_id,
            headed=False,
        )
        if start_payload.get("ok") is False:
            pytest.skip(
                "Live browser surface smoke requires a working browser runtime: "
                f"{_payload_error(start_payload)}",
            )
        open_payload = run_browser_use_json(
            action="open",
            session_id=session_id,
            page_id=page_id,
            url=html_path.resolve().as_uri(),
        )
        if open_payload.get("ok") is False:
            pytest.skip(
                "Live browser surface smoke could not open the local surface page: "
                f"{_payload_error(open_payload)}",
            )
        run_browser_use_json(
            action="wait_for",
            session_id=session_id,
            page_id=page_id,
            wait_time=0.5,
        )

        initial_observation = service.observe_page(
            session_id=session_id,
            page_id=page_id,
            page_profile=profile,
        )
        assert initial_observation.surface_graph is not None
        forced_probe_observation = initial_observation.model_copy(
            update={
                "surface_graph": initial_observation.surface_graph.model_copy(
                    update={"confidence": 0.2},
                ),
            },
        )

        with bind_browser_evidence_sink(
            lambda payload: sink_payloads.append(dict(payload))
            or {"evidence_id": f"browser-evidence-{len(sink_payloads) + 1}"}
        ):
            type_result = service.execute_step(
                session_id=session_id,
                page_id=page_id,
                before_observation=forced_probe_observation,
                target_slot="primary_input",
                intent_kind="type",
                payload={"text": "surface smoke input"},
                success_assertion={"normalized_text": "surface smoke input"},
                page_profile=profile,
            )
            click_result = service.execute_step(
                session_id=session_id,
                page_id=page_id,
                before_observation=type_result.after_observation,
                target_slot="submit_button",
                intent_kind="click",
                payload={},
                success_assertion={"normalized_text": "Published: surface smoke input"},
                page_profile=profile,
            )

        assert type_result.status == "succeeded"
        assert click_result.status == "succeeded"
        assert click_result.transition is not None
        assert click_result.after_graph is not None
        assert _wait_for_browser_status(
            session_id=session_id,
            page_id=page_id,
            expected_text="Published: surface smoke input",
        ) == "Published: surface smoke input"
        evidence_kinds = [
            str(item.get("metadata", {}).get("evidence_kind") or "")
            for item in sink_payloads
        ]
        assert "surface-probe" in evidence_kinds
        assert "surface-transition" in evidence_kinds
    finally:
        _stop_browser_session(session_id)


@pytest.mark.skipif(
    not _env_flag("COPAW_RUN_SURFACE_GRAPH_LIVE_SMOKE"),
    reason=LIVE_SURFACE_GRAPH_SMOKE_SKIP_REASON,
)
def test_live_surface_graph_document_observe_act_reobserve_smoke(tmp_path) -> None:
    document_path = tmp_path / "surface-document-smoke.txt"
    document_path.write_text("draft line\nkeep boundary\n", encoding="utf-8")
    service = DocumentSurfaceExecutionService(
        document_observer=_document_observer,
        document_runner=_document_runner,
    )
    sink_payloads: list[dict[str, object]] = []

    with bind_file_evidence_sink(
        lambda payload: sink_payloads.append(dict(payload))
        or {"evidence_id": f"file-evidence-{len(sink_payloads) + 1}"}
    ):
        result = service.execute_step(
            session_mount_id="surface-document-live",
            document_path=str(document_path),
            document_family="documents",
            intent_kind="replace_text",
            payload={"find_text": "draft line", "replace_text": "final line"},
            success_assertion={"contains_text": "final line"},
        )

    assert result.status == "succeeded"
    assert result.verification_passed is True
    assert result.transition is not None
    assert result.before_graph is not None
    assert result.after_graph is not None
    assert document_path.read_text(encoding="utf-8").startswith("final line")
    assert [
        str(item.get("metadata", {}).get("evidence_kind") or "")
        for item in sink_payloads
    ].count("surface-transition") == 1


@pytest.mark.skipif(
    sys.platform != "win32" or not _env_flag("COPAW_RUN_SURFACE_GRAPH_LIVE_SMOKE"),
    reason=LIVE_SURFACE_GRAPH_SMOKE_SKIP_REASON,
)
def test_live_surface_graph_desktop_blocker_probe_focus_smoke(tmp_path) -> None:
    script_path = tmp_path / "surface_desktop_smoke.py"
    window_title = f"CoPaw Surface Desktop Smoke {uuid4().hex[:6]}"
    _write_utf8(
        script_path,
        f"""
        import tkinter as tk

        root = tk.Tk()
        root.title({window_title!r})
        root.geometry("320x180")
        label = tk.Label(root, text="surface desktop smoke")
        label.pack(padx=24, pady=24)
        root.after(600000, root.destroy)
        root.mainloop()
        """,
    )
    process = subprocess.Popen([sys.executable, str(script_path)])
    service = DesktopSurfaceExecutionService(
        desktop_observer=_observe_guided_desktop_surface,
        desktop_runner=_run_guided_desktop_action,
    )
    sink_payloads: list[dict[str, object]] = []

    try:
        observed = _wait_for_desktop_observation(title=window_title)
        expected_selector = str(
            observed.slot_candidates["window_target"][0].action_selector or "",
        ).strip()
        if not expected_selector:
            pytest.skip("Live desktop surface smoke could not resolve a target window selector.")
        blocked_observation = observed.model_copy(
            update={
                "slot_candidates": {},
                "blockers": ["window-target-unresolved"],
            },
        )

        with bind_desktop_evidence_sink(
            lambda payload: sink_payloads.append(dict(payload))
            or {"evidence_id": f"desktop-evidence-{len(sink_payloads) + 1}"}
        ):
            result = service.execute_step(
                session_mount_id="surface-desktop-live",
                app_identity=window_title,
                target_slot="window_target",
                intent_kind="focus_window",
                payload={},
                success_assertion={"focused_selector": expected_selector},
                before_observation=blocked_observation,
            )

        assert result.status == "succeeded"
        assert result.transition is not None
        assert result.after_observation is not None
        assert result.after_observation.readback.get("focused_window") == expected_selector
        assert [
            str(item.get("metadata", {}).get("evidence_kind") or "")
            for item in sink_payloads
        ].count("surface-transition") == 1
    finally:
        try:
            process.kill()
        except Exception:
            pass
        try:
            process.wait(timeout=5.0)
        except Exception:
            pass
