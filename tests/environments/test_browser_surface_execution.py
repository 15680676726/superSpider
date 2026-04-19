# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.agents.tools.evidence_runtime import bind_browser_evidence_sink
from copaw.environments.surface_execution.browser import BrowserExecutionStep, BrowserTargetCandidate
from copaw.environments.surface_execution.browser.observer import observe_browser_page
from copaw.environments.surface_execution.browser.profiles import (
    BrowserPageProfile,
    observe_live_browser_page,
)
from copaw.environments.surface_execution.browser.resolver import resolve_browser_target
from copaw.environments.surface_execution.browser.service import BrowserSurfaceExecutionService
from copaw.environments.surface_execution.browser.verifier import read_browser_target_readback
from copaw.environments.surface_execution.owner import (
    GuidedBrowserSurfaceIntent,
    ProfessionSurfaceOperationOwner,
    ProfessionSurfaceOperationPlan,
    build_guided_browser_surface_owner,
)


def test_browser_target_candidate_keeps_action_and_readback_separate() -> None:
    candidate = BrowserTargetCandidate(
        target_kind="input",
        action_ref="e1",
        action_selector="",
        readback_selector="#chat-textarea",
        element_kind="textarea",
        scope_anchor="composer",
        score=10,
        reason="primary composer textarea",
    )

    assert candidate.action_ref == "e1"
    assert candidate.readback_selector == "#chat-textarea"


def test_resolver_prefers_primary_textarea_for_input_action() -> None:
    observation = observe_browser_page(
        snapshot_text='- textbox "Ask anything" [ref=e1]',
        page_url="https://chat.baidu.com/search",
        page_title="Baidu Chat",
        dom_probe={
            "inputs": [
                {
                    "target_kind": "input",
                    "action_ref": "e1",
                    "readback_selector": "#chat-textarea",
                    "element_kind": "textarea",
                    "scope_anchor": "composer",
                    "score": 10,
                    "reason": "primary textarea",
                },
                {
                    "target_kind": "input",
                    "action_ref": "e2",
                    "readback_selector": "input.search",
                    "element_kind": "input",
                    "scope_anchor": "header",
                    "score": 3,
                    "reason": "header search",
                },
            ]
        },
    )

    candidate = resolve_browser_target(observation, target_slot="primary_input")

    assert candidate is not None
    assert candidate.action_ref == "e1"
    assert candidate.readback_selector == "#chat-textarea"
    assert candidate.element_kind == "textarea"


def test_observer_derives_primary_input_candidate_from_snapshot_without_dom_probe() -> None:
    observation = observe_browser_page(
        snapshot_text='\n'.join(
            [
                '- heading "Baidu Chat"',
                '- textbox "Ask anything" [ref=e1]',
                '- button "Send" [ref=e2]',
            ]
        ),
        page_url="https://chat.baidu.com/search",
        page_title="Baidu Chat",
    )

    candidate = resolve_browser_target(observation, target_slot="primary_input")

    assert candidate is not None
    assert candidate.action_ref == "e1"
    assert candidate.target_kind == "input"
    assert candidate.scope_anchor == "snapshot"


def test_resolver_supports_profile_declared_submit_button_slot() -> None:
    observation = observe_browser_page(
        snapshot_text='- textbox "Ask anything" [ref=e1]\n- button "Send" [ref=e2]',
        page_url="https://chat.baidu.com/search",
        page_title="Baidu Chat",
        dom_probe={
            "targets": [
                {
                    "target_kind": "button",
                    "action_ref": "e2",
                    "readback_selector": "button.send",
                    "element_kind": "button",
                    "scope_anchor": "composer",
                    "score": 9,
                    "reason": "submit button",
                    "metadata": {"target_slots": ["submit_button"]},
                }
            ]
        },
    )

    candidate = resolve_browser_target(observation, target_slot="submit_button")

    assert candidate is not None
    assert candidate.action_ref == "e2"
    assert candidate.readback_selector == "button.send"


class _ProfileObservationRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def __call__(self, **payload):
        self.calls.append(dict(payload))
        action = str(payload.get("action") or "")
        if action == "snapshot":
            return {
                "ok": True,
                "snapshot": '- textbox "Ask anything" [ref=e1]\n- button "Send" [ref=e2]',
                "url": "https://chat.baidu.com/search",
            }
        if action == "evaluate":
            return {
                "ok": True,
                "result": {
                    "available": True,
                    "enabled": False,
                    "selector": "button[data-role='deep-think']",
                    "label": "Deep Think",
                },
            }
        raise AssertionError(f"Unexpected browser action: {action}")


def test_observe_live_browser_page_uses_thin_profile_probe() -> None:
    runner = _ProfileObservationRunner()

    def _probe_builder(
        *,
        browser_runner,
        session_id: str,
        page_id: str,
        snapshot_text: str,
        page_url: str,
        page_title: str,
    ):
        _ = snapshot_text, page_url, page_title
        probe_payload = browser_runner(
            action="evaluate",
            session_id=session_id,
            page_id=page_id,
            code="profile-probe:reasoning-toggle",
        )
        toggle = dict(probe_payload.get("result") or {})
        return {
            "targets": [
                {
                    "target_kind": "button",
                    "action_ref": "e2",
                    "readback_selector": "button.send",
                    "element_kind": "button",
                    "scope_anchor": "composer",
                    "score": 9,
                    "reason": "submit button",
                    "metadata": {"target_slots": ["submit_button"]},
                }
            ],
            "control_groups": [
                {
                    "group_kind": "reasoning_toggle_group",
                    "scope_anchor": "composer",
                    "candidates": [
                        {
                            "target_kind": "toggle",
                            "action_selector": str(toggle.get("selector") or ""),
                            "readback_selector": str(toggle.get("selector") or ""),
                            "element_kind": "button",
                            "scope_anchor": "composer",
                            "score": 8,
                            "reason": "deep think toggle",
                            "metadata": {
                                "enabled": bool(toggle.get("enabled")),
                                "label": str(toggle.get("label") or ""),
                                "target_slots": ["reasoning_toggle"],
                            },
                        }
                    ],
                }
            ],
        }

    profile = BrowserPageProfile(
        profile_id="baidu-chat",
        page_title="Baidu Chat",
        dom_probe_builder=_probe_builder,
    )

    observation = observe_live_browser_page(
        browser_runner=runner,
        session_id="research-browser",
        page_id="chat-page",
        profile=profile,
    )

    submit_candidate = resolve_browser_target(observation, target_slot="submit_button")
    toggle_candidate = resolve_browser_target(observation, target_slot="reasoning_toggle")

    assert observation.page_title == "Baidu Chat"
    assert submit_candidate is not None
    assert submit_candidate.action_ref == "e2"
    assert toggle_candidate is not None
    assert toggle_candidate.action_selector == "button[data-role='deep-think']"
    assert runner.calls[0]["action"] == "snapshot"
    assert any(call["action"] == "evaluate" for call in runner.calls)


def test_capture_live_browser_page_context_keeps_dom_probe_and_observation() -> None:
    from copaw.environments.surface_execution.browser.profiles import (
        capture_live_browser_page_context,
    )

    runner = _ProfileObservationRunner()

    def _probe_builder(
        *,
        browser_runner,
        session_id: str,
        page_id: str,
        snapshot_text: str,
        page_url: str,
        page_title: str,
    ):
        _ = browser_runner, session_id, page_id, snapshot_text, page_url, page_title
        return {
            "targets": [
                {
                    "target_kind": "button",
                    "action_ref": "e2",
                    "readback_selector": "button.send",
                    "element_kind": "button",
                    "scope_anchor": "composer",
                    "score": 9,
                    "reason": "submit button",
                    "metadata": {"target_slots": ["submit_button"]},
                }
            ]
        }

    profile = BrowserPageProfile(
        profile_id="baidu-chat",
        page_title="Baidu Chat",
        dom_probe_builder=_probe_builder,
    )

    context = capture_live_browser_page_context(
        browser_runner=runner,
        session_id="research-browser",
        page_id="chat-page",
        profile=profile,
    )

    candidate = resolve_browser_target(context["observation"], target_slot="submit_button")

    assert context["page_title"] == "Baidu Chat"
    assert context["page_url"] == "https://chat.baidu.com/search"
    assert context["dom_probe"]["targets"][0]["action_ref"] == "e2"
    assert candidate is not None
    assert candidate.action_ref == "e2"


class _GenericReadablePageRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def __call__(self, **payload):
        self.calls.append(dict(payload))
        action = str(payload.get("action") or "")
        if action == "snapshot":
            return {
                "ok": True,
                "snapshot": '\n'.join(
                    [
                        '- heading "番茄作家助手"',
                        '- textbox "请输入小说标题" [ref=e1]',
                        '- button "上传正文" [ref=e2]',
                    ]
                ),
                "url": "https://writer.fanqie.cn/upload",
                "title": "番茄作家助手",
            }
        if action == "evaluate":
            return {
                "ok": True,
                "result": {
                    "bodyText": (
                        "番茄作家助手\n"
                        "上传新小说\n"
                        "当前草稿：天命长歌\n"
                        "请先确认作品标题、简介和前三章内容，再点击上传正文。"
                    ),
                    "href": "https://writer.fanqie.cn/upload",
                    "title": "番茄作家助手",
                },
            }
        raise AssertionError(f"Unexpected browser action: {action}")


def test_capture_live_browser_page_context_derives_generic_readable_sections_without_provider_profile() -> None:
    from copaw.environments.surface_execution.browser.profiles import (
        capture_live_browser_page_context,
    )

    runner = _GenericReadablePageRunner()

    context = capture_live_browser_page_context(
        browser_runner=runner,
        session_id="writer-browser",
        page_id="upload-page",
    )

    observation = context["observation"]

    assert observation.page_title == "番茄作家助手"
    assert observation.page_url == "https://writer.fanqie.cn/upload"
    assert observation.readable_sections
    assert any("当前草稿：天命长歌" in str(section.get("text") or "") for section in observation.readable_sections)
    assert runner.calls[0]["action"] == "snapshot"
    assert any(call["action"] == "evaluate" for call in runner.calls)


class _GenericBlockedPageRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def __call__(self, **payload):
        self.calls.append(dict(payload))
        action = str(payload.get("action") or "")
        if action == "snapshot":
            return {
                "ok": True,
                "snapshot": '- heading "请登录后继续"\n- button "登录" [ref=e1]',
                "url": "https://example.com/dashboard",
                "title": "控制台",
            }
        if action == "evaluate":
            return {
                "ok": True,
                "result": {
                    "bodyText": "请登录后继续\n当前页面需要登录才能访问完整内容。",
                    "href": "https://example.com/dashboard",
                    "title": "控制台",
                },
            }
        raise AssertionError(f"Unexpected browser action: {action}")


def test_capture_live_browser_page_context_marks_generic_login_blocker_before_action() -> None:
    from copaw.environments.surface_execution.browser.profiles import (
        capture_live_browser_page_context,
    )

    runner = _GenericBlockedPageRunner()

    context = capture_live_browser_page_context(
        browser_runner=runner,
        session_id="blocked-browser",
        page_id="dashboard-page",
    )

    observation = context["observation"]

    assert observation.login_state == "login-required"
    assert "login-required" in observation.blockers
    assert any("请登录后继续" in str(section.get("text") or "") for section in observation.readable_sections)


def test_observer_derives_generic_upload_page_summary() -> None:
    observation = observe_browser_page(
        snapshot_text='- textbox "Novel title" [ref=e1]\n- button "Upload manuscript" [ref=e2]',
        page_url="https://writer.example.com/upload",
        page_title="Writer Console",
        dom_probe={
            "body_text": (
                "Upload new novel\n"
                "Current draft: Sky Song\n"
                "Review title, summary, and first three chapters before uploading."
            ),
            "targets": [
                {
                    "target_kind": "button",
                    "action_ref": "e2",
                    "readback_selector": "button.upload",
                    "element_kind": "button",
                    "scope_anchor": "main",
                    "score": 9,
                    "reason": "upload manuscript",
                    "metadata": {"label": "Upload manuscript"},
                }
            ],
        },
    )

    assert observation.page_summary.page_kind == "upload-flow"
    assert "Current draft: Sky Song" in observation.page_summary.primary_text
    assert "review-before-upload" in observation.page_summary.action_hints
    assert "upload" in observation.page_summary.action_hints


def test_observer_derives_login_wall_page_summary() -> None:
    observation = observe_browser_page(
        snapshot_text='- heading "Sign in to continue"\n- button "Sign in" [ref=e1]',
        page_url="https://example.com/dashboard",
        page_title="Dashboard",
        dom_probe={
            "body_text": "Login required\nSign in to continue using this page.",
        },
    )

    assert observation.page_summary.page_kind == "login-wall"
    assert observation.page_summary.headline == "Login required"
    assert "resolve-login" in observation.page_summary.action_hints
    assert "login-required" in observation.page_summary.blocker_hints


class _VerifierRunner:
    def __init__(self, result: dict[str, str]) -> None:
        self.result = dict(result)
        self.calls: list[dict[str, object]] = []

    def __call__(self, **payload):
        self.calls.append(dict(payload))
        return {"ok": True, "result": dict(self.result)}


def test_verifier_reads_textarea_value_from_readback_selector() -> None:
    runner = _VerifierRunner(
        {
            "text": "Clarify the key Zi Wei Dou Shu terms.",
            "normalized_text": "Clarify the key Zi Wei Dou Shu terms.",
        }
    )
    candidate = BrowserTargetCandidate(
        target_kind="input",
        action_ref="e1",
        action_selector="",
        readback_selector="#chat-textarea",
        element_kind="textarea",
        scope_anchor="composer",
        score=10,
        reason="primary composer textarea",
    )

    payload = read_browser_target_readback(
        browser_runner=runner,
        session_id="research-browser",
        page_id="chat-page",
        candidate=candidate,
    )

    assert payload == {
        "observed_text": "Clarify the key Zi Wei Dou Shu terms.",
        "normalized_text": "Clarify the key Zi Wei Dou Shu terms.",
    }
    assert "#chat-textarea" in str(runner.calls[0]["code"])
    assert ".value" in str(runner.calls[0]["code"])


def test_resolver_rejects_page_wide_container_as_toggle() -> None:
    observation = observe_browser_page(
        snapshot_text='- textbox "Ask anything" [ref=e1]',
        page_url="https://chat.baidu.com/search",
        page_title="Baidu Chat",
        dom_probe={
            "control_groups": [
                {
                    "group_kind": "reasoning_toggle_group",
                    "scope_anchor": "page",
                    "candidates": [
                        {
                            "target_kind": "toggle",
                            "action_selector": "[data-copaw-deep-think='1']",
                            "readback_selector": "[data-copaw-deep-think='1']",
                            "element_kind": "generic",
                            "scope_anchor": "page",
                            "score": 100,
                            "reason": "page wide container",
                            "metadata": {"is_page_wide": True},
                        },
                        {
                            "target_kind": "toggle",
                            "action_selector": "button[data-role='deep-think']",
                            "readback_selector": "button[data-role='deep-think']",
                            "element_kind": "button",
                            "scope_anchor": "composer",
                            "score": 8,
                            "reason": "composer toggle",
                        },
                    ],
                }
            ]
        },
    )

    candidate = resolve_browser_target(observation, target_slot="reasoning_toggle")

    assert candidate is not None
    assert candidate.action_selector == "button[data-role='deep-think']"
    assert candidate.scope_anchor == "composer"


class _ServiceRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.last_typed_text = ""
        self.toggle_enabled_by_selector = {
            "button[data-role='deep-think']": False,
            "[data-copaw-deep-think='1']": False,
        }

    def __call__(self, **payload):
        self.calls.append(dict(payload))
        action = str(payload.get("action") or "")
        if action == "type":
            self.last_typed_text = str(payload.get("text") or "")
            return {"ok": True}
        if action == "click":
            selector = str(payload.get("selector") or "")
            if selector in self.toggle_enabled_by_selector:
                self.toggle_enabled_by_selector[selector] = True
            return {"ok": True}
        if action == "press_key":
            return {"ok": True}
        if action == "evaluate":
            code = str(payload.get("code") or "")
            if "#chat-textarea" in code:
                return {
                    "ok": True,
                    "result": {
                        "text": self.last_typed_text,
                        "normalized_text": self.last_typed_text,
                    },
                }
            if "button[data-role='deep-think']" in code or "[data-copaw-deep-think='1']" in code:
                selector = (
                    "button[data-role='deep-think']"
                    if "button[data-role='deep-think']" in code
                    else "[data-copaw-deep-think='1']"
                )
                return {
                    "ok": True,
                    "result": {
                        "text": "Deep Think",
                        "normalized_text": "Deep Think",
                        "toggle_enabled": (
                            "true" if self.toggle_enabled_by_selector.get(selector) else "false"
                        ),
                    },
                }
        return {"ok": False, "result": {}}


class _LiveServiceRunner(_ServiceRunner):
    def __init__(self) -> None:
        super().__init__()
        self.snapshots = [
            {
                "ok": True,
                "snapshot": '- textbox "Ask anything" [ref=e1]',
                "url": "https://chat.baidu.com/search",
            },
            {
                "ok": True,
                "snapshot": '- textbox "Ask anything" [ref=e1]\n- region "Latest answer stream"',
                "url": "https://chat.baidu.com/search",
            },
        ]

    def __call__(self, **payload):
        action = str(payload.get("action") or "")
        if action == "snapshot":
            self.calls.append(dict(payload))
            return self.snapshots.pop(0)
        return super().__call__(**payload)


def test_browser_surface_service_executes_type_with_split_readback() -> None:
    runner = _ServiceRunner()
    service = BrowserSurfaceExecutionService(browser_runner=runner)

    result = service.execute_step(
        session_id="research-browser",
        page_id="chat-page",
        snapshot_text='- textbox "Ask anything" [ref=e1]',
        page_url="https://chat.baidu.com/search",
        page_title="Baidu Chat",
        dom_probe={
            "inputs": [
                {
                    "target_kind": "input",
                    "action_ref": "e1",
                    "readback_selector": "#chat-textarea",
                    "element_kind": "textarea",
                    "scope_anchor": "composer",
                    "score": 10,
                    "reason": "primary textarea",
                }
            ]
        },
        target_slot="primary_input",
        intent_kind="type",
        payload={"text": "Clarify the key Zi Wei Dou Shu terms."},
        success_assertion={"normalized_text": "Clarify the key Zi Wei Dou Shu terms."},
    )

    assert result.status == "succeeded"
    assert result.verification_passed is True
    assert result.resolved_target is not None
    assert result.resolved_target.action_ref == "e1"


def test_browser_surface_service_executes_scoped_toggle_click() -> None:
    runner = _ServiceRunner()
    service = BrowserSurfaceExecutionService(browser_runner=runner)

    result = service.execute_step(
        session_id="research-browser",
        page_id="chat-page",
        snapshot_text='- textbox "Ask anything" [ref=e1]',
        page_url="https://chat.baidu.com/search",
        page_title="Baidu Chat",
        dom_probe={
            "control_groups": [
                {
                    "group_kind": "reasoning_toggle_group",
                    "scope_anchor": "page",
                    "candidates": [
                        {
                            "target_kind": "toggle",
                            "action_selector": "[data-copaw-deep-think='1']",
                            "readback_selector": "[data-copaw-deep-think='1']",
                            "element_kind": "generic",
                            "scope_anchor": "page",
                            "score": 100,
                            "reason": "page wide container",
                            "metadata": {"is_page_wide": True},
                        },
                        {
                            "target_kind": "toggle",
                            "action_selector": "button[data-role='deep-think']",
                            "readback_selector": "button[data-role='deep-think']",
                            "element_kind": "button",
                            "scope_anchor": "composer",
                            "score": 8,
                            "reason": "composer toggle",
                        },
                    ],
                }
            ]
        },
        target_slot="reasoning_toggle",
        intent_kind="click",
        payload={},
        success_assertion={"normalized_text": "Deep Think"},
    )

    assert result.status == "succeeded"
    assert result.verification_passed is True
    assert result.resolved_target is not None
    assert result.resolved_target.action_selector == "button[data-role='deep-think']"


def test_browser_surface_service_verifies_toggle_click_by_enabled_state() -> None:
    runner = _ServiceRunner()
    service = BrowserSurfaceExecutionService(browser_runner=runner)

    result = service.execute_step(
        session_id="research-browser",
        page_id="chat-page",
        snapshot_text='- textbox "Ask anything" [ref=e1]',
        page_url="https://chat.baidu.com/search",
        page_title="Baidu Chat",
        dom_probe={
            "control_groups": [
                {
                    "group_kind": "reasoning_toggle_group",
                    "scope_anchor": "composer",
                    "candidates": [
                        {
                            "target_kind": "toggle",
                            "action_selector": "button[data-role='deep-think']",
                            "readback_selector": "button[data-role='deep-think']",
                            "element_kind": "button",
                            "scope_anchor": "composer",
                            "score": 8,
                            "reason": "composer toggle",
                        },
                    ],
                }
            ]
        },
        target_slot="reasoning_toggle",
        intent_kind="click",
        payload={},
        success_assertion={"toggle_enabled": "true"},
    )

    assert result.status == "succeeded"
    assert result.verification_passed is True
    assert result.readback["toggle_enabled"] == "true"


def test_browser_surface_service_executes_press_key_without_target_resolution() -> None:
    runner = _ServiceRunner()
    service = BrowserSurfaceExecutionService(browser_runner=runner)

    result = service.execute_step(
        session_id="research-browser",
        page_id="chat-page",
        snapshot_text='- textbox "Ask anything" [ref=e1]',
        page_url="https://chat.baidu.com/search",
        page_title="Baidu Chat",
        target_slot="page",
        intent_kind="press",
        payload={"key": "Enter"},
        success_assertion={},
    )

    assert result.status == "succeeded"
    assert result.verification_passed is True
    assert result.resolved_target is None
    press_key_calls = [call for call in runner.calls if call["action"] == "press_key"]
    assert press_key_calls == [
        {
            "action": "press_key",
            "session_id": "research-browser",
            "page_id": "chat-page",
            "key": "Enter",
        }
    ]


def test_browser_surface_service_refreshes_after_observation_with_page_profile() -> None:
    runner = _LiveServiceRunner()
    service = BrowserSurfaceExecutionService(browser_runner=runner)

    def _probe_builder(
        *,
        browser_runner,
        session_id: str,
        page_id: str,
        snapshot_text: str,
        page_url: str,
        page_title: str,
    ):
        _ = browser_runner, session_id, page_id, snapshot_text, page_url, page_title
        return {
            "inputs": [
                {
                    "target_kind": "input",
                    "action_ref": "e1",
                    "readback_selector": "#chat-textarea",
                    "element_kind": "textarea",
                    "scope_anchor": "composer",
                    "score": 10,
                    "reason": "primary textarea",
                }
            ]
        }

    profile = BrowserPageProfile(
        profile_id="baidu-chat",
        page_title="Baidu Chat",
        dom_probe_builder=_probe_builder,
    )

    result = service.execute_step(
        session_id="research-browser",
        page_id="chat-page",
        target_slot="primary_input",
        intent_kind="type",
        payload={"text": "Clarify the key Zi Wei Dou Shu terms."},
        success_assertion={"normalized_text": "Clarify the key Zi Wei Dou Shu terms."},
        page_profile=profile,
    )

    assert result.status == "succeeded"
    assert result.before_observation is not None
    assert result.after_observation is not None
    assert result.before_observation.snapshot_text == '- textbox "Ask anything" [ref=e1]'
    assert result.after_observation.snapshot_text == (
        '- textbox "Ask anything" [ref=e1]\n- region "Latest answer stream"'
    )
    snapshot_calls = [call for call in runner.calls if call["action"] == "snapshot"]
    assert len(snapshot_calls) == 2


def test_browser_surface_service_resolves_live_target_from_page_profile() -> None:
    runner = _ProfileObservationRunner()
    service = BrowserSurfaceExecutionService(browser_runner=runner)

    def _probe_builder(
        *,
        browser_runner,
        session_id: str,
        page_id: str,
        snapshot_text: str,
        page_url: str,
        page_title: str,
    ):
        _ = browser_runner, session_id, page_id, snapshot_text, page_url, page_title
        return {
            "targets": [
                {
                    "target_kind": "button",
                    "action_ref": "e2",
                    "readback_selector": "button.send",
                    "element_kind": "button",
                    "scope_anchor": "composer",
                    "score": 9,
                    "reason": "submit button",
                    "metadata": {"target_slots": ["submit_button"]},
                }
            ]
        }

    profile = BrowserPageProfile(
        profile_id="baidu-chat",
        page_title="Baidu Chat",
        dom_probe_builder=_probe_builder,
    )

    candidate = service.resolve_target(
        session_id="research-browser",
        page_id="chat-page",
        target_slot="submit_button",
        page_profile=profile,
    )

    assert candidate is not None
    assert candidate.action_ref == "e2"


def test_browser_surface_service_captures_page_context_via_shared_entry() -> None:
    runner = _ProfileObservationRunner()
    service = BrowserSurfaceExecutionService(browser_runner=runner)

    def _probe_builder(
        *,
        browser_runner,
        session_id: str,
        page_id: str,
        snapshot_text: str,
        page_url: str,
        page_title: str,
    ):
        _ = browser_runner, session_id, page_id, snapshot_text, page_url, page_title
        return {
            "targets": [
                {
                    "target_kind": "button",
                    "action_ref": "e2",
                    "readback_selector": "button.send",
                    "element_kind": "button",
                    "scope_anchor": "composer",
                    "score": 9,
                    "reason": "submit button",
                    "metadata": {"target_slots": ["submit_button"]},
                }
            ]
        }

    profile = BrowserPageProfile(
        profile_id="baidu-chat",
        page_title="Baidu Chat",
        dom_probe_builder=_probe_builder,
    )

    context = service.capture_page_context(
        session_id="research-browser",
        page_id="chat-page",
        page_profile=profile,
    )

    candidate = resolve_browser_target(context["observation"], target_slot="submit_button")

    assert context["page_title"] == "Baidu Chat"
    assert context["page_url"] == "https://chat.baidu.com/search"
    assert context["dom_probe"]["targets"][0]["action_ref"] == "e2"
    assert candidate is not None
    assert candidate.action_ref == "e2"


def test_browser_surface_service_reads_target_readback_via_shared_entry() -> None:
    runner = _ServiceRunner()
    service = BrowserSurfaceExecutionService(browser_runner=runner)
    runner.last_typed_text = "Clarify the key Zi Wei Dou Shu terms."
    candidate = BrowserTargetCandidate(
        target_kind="input",
        action_ref="e1",
        action_selector="",
        readback_selector="#chat-textarea",
        element_kind="textarea",
        scope_anchor="composer",
        score=10,
        reason="primary composer textarea",
    )

    payload = service.read_target_readback(
        session_id="research-browser",
        page_id="chat-page",
        target=candidate,
    )

    assert payload == {
        "observed_text": "Clarify the key Zi Wei Dou Shu terms.",
        "normalized_text": "Clarify the key Zi Wei Dou Shu terms.",
    }


def test_browser_surface_service_populates_evidence_ids_from_bound_browser_sink() -> None:
    runner = _ServiceRunner()
    service = BrowserSurfaceExecutionService(browser_runner=runner)
    sink_payloads: list[dict[str, object]] = []

    def _sink(payload: dict[str, object]) -> dict[str, object]:
        sink_payloads.append(dict(payload))
        return {"evidence_id": "evidence-browser-step-1"}

    with bind_browser_evidence_sink(_sink):
        result = service.execute_step(
            session_id="research-browser",
            page_id="chat-page",
            snapshot_text='- textbox "Ask anything" [ref=e1]',
            page_url="https://chat.baidu.com/search",
            page_title="Baidu Chat",
            dom_probe={
                "inputs": [
                    {
                        "target_kind": "input",
                        "action_ref": "e1",
                        "readback_selector": "#chat-textarea",
                        "element_kind": "textarea",
                        "scope_anchor": "composer",
                        "score": 10,
                        "reason": "primary textarea",
                    }
                ]
            },
            target_slot="primary_input",
            intent_kind="type",
            payload={"text": "Clarify the key Zi Wei Dou Shu terms."},
            success_assertion={"normalized_text": "Clarify the key Zi Wei Dou Shu terms."},
        )

    assert result.evidence_ids == ["evidence-browser-step-1"]
    assert len(sink_payloads) == 1
    assert sink_payloads[0]["action"] == "type"
    assert sink_payloads[0]["status"] == "success"
    assert sink_payloads[0]["page_id"] == "chat-page"
    assert sink_payloads[0]["metadata"]["verification"]["verified"] is True


def test_browser_surface_service_emits_failure_evidence_when_target_unresolved() -> None:
    runner = _ServiceRunner()
    service = BrowserSurfaceExecutionService(browser_runner=runner)
    sink_payloads: list[dict[str, object]] = []

    def _sink(payload: dict[str, object]) -> dict[str, object]:
        sink_payloads.append(dict(payload))
        return {"evidence_id": "evidence-browser-failure-1"}

    with bind_browser_evidence_sink(_sink):
        result = service.execute_step(
            session_id="research-browser",
            page_id="chat-page",
            snapshot_text='- button "Send" [ref=e2]',
            page_url="https://chat.baidu.com/search",
            page_title="Baidu Chat",
            target_slot="primary_input",
            intent_kind="type",
            payload={"text": "Clarify the key Zi Wei Dou Shu terms."},
            success_assertion={"normalized_text": "Clarify the key Zi Wei Dou Shu terms."},
        )

    assert result.status == "failed"
    assert result.blocker_kind == "target-unresolved"
    assert result.evidence_ids == ["evidence-browser-failure-1"]
    assert len(sink_payloads) == 1
    assert sink_payloads[0]["status"] == "error"
    assert sink_payloads[0]["metadata"]["verification"]["verified"] is False
    assert sink_payloads[0]["metadata"]["blocker_kind"] == "target-unresolved"


def test_browser_surface_service_runs_shared_step_loop_until_planner_stops() -> None:
    runner = _LiveServiceRunner()
    runner.snapshots = [
        {
            "ok": True,
            "snapshot": '- textbox "Ask anything" [ref=e1]',
            "url": "https://chat.baidu.com/search",
        },
        {
            "ok": True,
            "snapshot": '- textbox "Ask anything" [ref=e1]\n- region "Step 1 response"',
            "url": "https://chat.baidu.com/search",
        },
        {
            "ok": True,
            "snapshot": '- textbox "Ask anything" [ref=e1]\n- region "Step 2 response"',
            "url": "https://chat.baidu.com/search",
        },
        {
            "ok": True,
            "snapshot": '- textbox "Ask anything" [ref=e1]\n- region "Step 2 response"',
            "url": "https://chat.baidu.com/search",
        },
        {
            "ok": True,
            "snapshot": '- textbox "Ask anything" [ref=e1]\n- region "Step 2 response"',
            "url": "https://chat.baidu.com/search",
        },
    ]
    service = BrowserSurfaceExecutionService(browser_runner=runner)
    planner_calls: list[str] = []

    def _probe_builder(
        *,
        browser_runner,
        session_id: str,
        page_id: str,
        snapshot_text: str,
        page_url: str,
        page_title: str,
    ):
        _ = browser_runner, session_id, page_id, snapshot_text, page_url, page_title
        return {
            "inputs": [
                {
                    "target_kind": "input",
                    "action_ref": "e1",
                    "readback_selector": "#chat-textarea",
                    "element_kind": "textarea",
                    "scope_anchor": "composer",
                    "score": 10,
                    "reason": "primary textarea",
                }
            ]
        }

    profile = BrowserPageProfile(
        profile_id="baidu-chat",
        page_title="Baidu Chat",
        dom_probe_builder=_probe_builder,
    )

    def _planner(observation, history):
        planner_calls.append(observation.snapshot_text)
        if len(history) >= 2:
            return None
        return BrowserExecutionStep(
            intent_kind="type",
            target_slot="primary_input",
            payload={"text": f"step-{len(history) + 1}"},
            success_assertion={"normalized_text": f"step-{len(history) + 1}"},
        )

    loop_result = service.run_step_loop(
        session_id="research-browser",
        page_id="chat-page",
        planner=_planner,
        page_profile=profile,
        max_steps=3,
    )

    assert loop_result.stop_reason == "planner-stop"
    assert len(loop_result.steps) == 2
    assert loop_result.steps[0].readback["normalized_text"] == "step-1"
    assert loop_result.steps[1].readback["normalized_text"] == "step-2"
    assert loop_result.final_observation is not None
    assert len(planner_calls) == 3
    snapshot_calls = [call for call in runner.calls if call["action"] == "snapshot"]
    assert len(snapshot_calls) == 3


def test_browser_surface_service_step_loop_stops_on_failed_step() -> None:
    runner = _ProfileObservationRunner()
    service = BrowserSurfaceExecutionService(browser_runner=runner)

    def _planner(_observation, _history):
        return BrowserExecutionStep(
            intent_kind="type",
            target_slot="primary_input",
            payload={"text": "step-1"},
            success_assertion={"normalized_text": "step-1"},
        )

    loop_result = service.run_step_loop(
        session_id="research-browser",
        page_id="chat-page",
        planner=_planner,
        max_steps=2,
    )

    assert loop_result.stop_reason == "step-failed"
    assert len(loop_result.steps) == 1
    assert loop_result.steps[0].status == "failed"
    assert loop_result.steps[0].blocker_kind == "target-unresolved"


def test_browser_surface_service_run_step_loop_reuses_initial_observation() -> None:
    runner = _LiveServiceRunner()
    runner.snapshots = [
        {
            "ok": True,
            "snapshot": '- textbox "Ask anything" [ref=e1]',
            "url": "https://chat.baidu.com/search",
        },
        {
            "ok": True,
            "snapshot": '- textbox "Ask anything" [ref=e1]\n- region "Step 1 response"',
            "url": "https://chat.baidu.com/search",
        },
        {
            "ok": True,
            "snapshot": '- textbox "Ask anything" [ref=e1]\n- region "Step 2 response"',
            "url": "https://chat.baidu.com/search",
        },
    ]
    service = BrowserSurfaceExecutionService(browser_runner=runner)
    profile = BrowserPageProfile(
        profile_id="baidu-chat",
        page_title="Baidu Chat",
        dom_probe_builder=lambda **_kwargs: {
            "inputs": [
                {
                    "target_kind": "input",
                    "action_ref": "e1",
                    "readback_selector": "#chat-textarea",
                    "element_kind": "textarea",
                    "scope_anchor": "composer",
                    "score": 10,
                    "reason": "primary textarea",
                }
            ]
        },
    )
    initial_context = service.capture_page_context(
        session_id="research-browser",
        page_id="chat-page",
        page_profile=profile,
    )
    initial_observation = initial_context["observation"]
    runner.calls.clear()

    def _planner(_observation, history):
        if history:
            return None
        return BrowserExecutionStep(
            intent_kind="type",
            target_slot="primary_input",
            payload={"text": "step-1"},
            success_assertion={"normalized_text": "step-1"},
        )

    loop_result = service.run_step_loop(
        session_id="research-browser",
        page_id="chat-page",
        planner=_planner,
        initial_observation=initial_observation,
        page_profile=profile,
        max_steps=2,
    )

    assert loop_result.stop_reason == "planner-stop"
    snapshot_calls = [call for call in runner.calls if call["action"] == "snapshot"]
    assert len(snapshot_calls) == 1


def test_browser_surface_service_run_step_loop_accepts_shared_profession_owner_checkpoint() -> None:
    runner = _LiveServiceRunner()
    runner.snapshots = [
        {
            "ok": True,
            "snapshot": '- textbox "Ask anything" [ref=e1]',
            "url": "https://chat.baidu.com/search",
        },
        {
            "ok": True,
            "snapshot": '- textbox "Ask anything" [ref=e1]\n- region "Typed"',
            "url": "https://chat.baidu.com/search",
        },
    ]
    service = BrowserSurfaceExecutionService(browser_runner=runner)
    profile = BrowserPageProfile(
        profile_id="baidu-chat",
        page_title="Baidu Chat",
        dom_probe_builder=lambda **_kwargs: {
            "inputs": [
                {
                    "target_kind": "input",
                    "action_ref": "e1",
                    "readback_selector": "#chat-textarea",
                    "element_kind": "textarea",
                    "scope_anchor": "composer",
                    "score": 10,
                    "reason": "primary textarea",
                }
            ]
        },
    )
    checkpoints: list[tuple[str, str, str, int]] = []

    def _planner(*, observation, history, checkpoint):
        checkpoints.append(
            (
                checkpoint.formal_session_id,
                checkpoint.surface_kind,
                checkpoint.surface_thread_id,
                checkpoint.step_index,
            )
        )
        if history:
            return None
        return ProfessionSurfaceOperationPlan(
            intent_kind="type",
            target_slot="primary_input",
            payload={"text": "resume same browser thread"},
            success_assertion={"normalized_text": "resume same browser thread"},
        )

    owner = ProfessionSurfaceOperationOwner(
        formal_session_id="research-session-1",
        surface_thread_id="chat-page",
        planner=_planner,
    )

    loop_result = service.run_step_loop(
        session_id="research-browser",
        page_id="chat-page",
        owner=owner,
        page_profile=profile,
        max_steps=2,
    )

    assert checkpoints == [
        ("research-session-1", "browser", "chat-page", 0),
        ("research-session-1", "browser", "chat-page", 1),
    ]
    assert loop_result.stop_reason == "planner-stop"
    assert loop_result.operation_checkpoint is not None
    assert loop_result.operation_checkpoint.formal_session_id == "research-session-1"
    assert loop_result.operation_checkpoint.surface_kind == "browser"
    assert loop_result.operation_checkpoint.surface_thread_id == "chat-page"
    assert loop_result.operation_checkpoint.last_status == "succeeded"


def test_browser_guided_owner_types_then_submits_generic_form_flow() -> None:
    runner = _ServiceRunner()
    service = BrowserSurfaceExecutionService(browser_runner=runner)
    snapshot_text = '- textbox "Title" [ref=e1]\n- button "Submit" [ref=e2]'
    dom_probe = {
        "inputs": [
            {
                "target_kind": "input",
                "action_ref": "e1",
                "readback_selector": "#chat-textarea",
                "element_kind": "textarea",
                "scope_anchor": "form",
                "score": 10,
                "reason": "primary form field",
            }
        ],
        "targets": [
            {
                "target_kind": "button",
                "action_ref": "e2",
                "readback_selector": "button.submit",
                "element_kind": "button",
                "scope_anchor": "form",
                "score": 9,
                "reason": "submit button",
                "metadata": {"target_slots": ["submit_button"]},
            }
        ],
    }
    initial_observation = observe_browser_page(
        snapshot_text=snapshot_text,
        page_url="https://example.com/form",
        page_title="Generic Form",
        dom_probe=dom_probe,
    )
    owner = build_guided_browser_surface_owner(
        formal_session_id="profession-session-1",
        surface_thread_id="form-page",
        intent=GuidedBrowserSurfaceIntent(
            desired_text="launch listing draft",
            request_submit=True,
        ),
    )

    loop_result = service.run_step_loop(
        session_id="browser-session-1",
        page_id="form-page",
        owner=owner,
        initial_observation=initial_observation,
        snapshot_text=snapshot_text,
        page_url="https://example.com/form",
        page_title="Generic Form",
        dom_probe=dom_probe,
        max_steps=3,
    )

    assert [step.intent_kind for step in loop_result.steps] == ["type", "click"]
    click_call = next(call for call in runner.calls if call["action"] == "click")
    assert click_call["ref"] == "e2"


def test_browser_guided_owner_stops_on_login_wall() -> None:
    runner = _ServiceRunner()
    service = BrowserSurfaceExecutionService(browser_runner=runner)
    initial_observation = observe_browser_page(
        snapshot_text='- heading "请登录后继续"\n- button "登录" [ref=e1]',
        page_url="https://example.com/login",
        page_title="Login required",
        dom_probe={
            "page": {
                "bodyText": "请登录后继续\n当前页面需要登录才能继续。",
                "href": "https://example.com/login",
                "title": "Login required",
            }
        },
    )
    owner = build_guided_browser_surface_owner(
        formal_session_id="profession-session-1",
        surface_thread_id="login-page",
        intent=GuidedBrowserSurfaceIntent(
            desired_text="should never type",
            request_submit=True,
        ),
    )

    loop_result = service.run_step_loop(
        session_id="browser-session-1",
        page_id="login-page",
        owner=owner,
        initial_observation=initial_observation,
        max_steps=2,
    )

    assert loop_result.steps == []
    assert loop_result.stop_reason == "planner-stop"
