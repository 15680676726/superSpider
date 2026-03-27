# -*- coding: utf-8 -*-
from __future__ import annotations

from .browser_control_shared import *  # noqa: F401,F403
from .browser_control_actions_core import *  # noqa: F401,F403


def _basename_from_path(path: str) -> str:
    return str(path or "").replace("\\", "/").rsplit("/", 1)[-1]


async def _evaluate_on_page(page, expression: str):
    if _USE_SYNC_PLAYWRIGHT:
        return await _run_sync(page.evaluate, expression)
    return await page.evaluate(expression)


async def _locator_input_value(locator) -> str:
    if _USE_SYNC_PLAYWRIGHT:
        value = await _run_sync(locator.input_value)
    else:
        value = await locator.input_value()
    return str(value or "")


async def _locator_is_checked(locator) -> bool:
    if _USE_SYNC_PLAYWRIGHT:
        return bool(await _run_sync(locator.is_checked))
    return bool(await locator.is_checked())


async def _locator_evaluate(locator, expression: str):
    if _USE_SYNC_PLAYWRIGHT:
        return await _run_sync(locator.evaluate, expression)
    return await locator.evaluate(expression)


async def _selected_file_names(page) -> list[str]:
    result = await _evaluate_on_page(
        page,
        """
        () => Array.from(document.querySelectorAll('input[type="file"]'))
          .flatMap((input) =>
            Array.from(input.files || []).map((file) => String(file.name || ""))
          )
        """,
    )
    if isinstance(result, list):
        return [str(item) for item in result]
    if isinstance(result, (int, float)):
        return [f"__count__:{index}" for index in range(max(0, int(result)))]
    return []


def _json_error(error: str, *, verification: dict[str, Any] | None = None) -> ToolResponse:
    payload: dict[str, Any] = {"ok": False, "error": error}
    if verification:
        payload["verification"] = verification
    return _tool_response(json.dumps(payload, ensure_ascii=False, indent=2))


async def _verify_field_value(locator, field_type: str, expected_value: Any) -> tuple[bool, Any]:
    normalized_type = (field_type or "textbox").lower()
    if normalized_type == "checkbox":
        if isinstance(expected_value, str):
            expected_bool = expected_value.strip().lower() in ("true", "1", "yes")
        else:
            expected_bool = bool(expected_value)
        actual_bool = await _locator_is_checked(locator)
        return actual_bool is expected_bool, actual_bool
    if normalized_type == "radio":
        actual_bool = await _locator_is_checked(locator)
        return actual_bool, actual_bool
    if normalized_type == "combobox":
        actual_values = await _locator_evaluate(
            locator,
            """
            (element) =>
              Array.from(element.selectedOptions || []).map(
                (option) => String(option.value || option.label || option.textContent || "")
              )
            """,
        )
        normalized_values = (
            [str(item) for item in actual_values]
            if isinstance(actual_values, list)
            else [str(actual_values or "")]
        )
        expected_text = str(expected_value or "")
        return expected_text in normalized_values, normalized_values
    actual_text = await _locator_input_value(locator)
    expected_text = str(expected_value if expected_value is not None else "")
    return actual_text == expected_text, actual_text


async def _action_snapshot(
    page_id: str,
    filename: str,
    frame_selector: str = "",
    session_id: str = "default",
) -> ToolResponse:
    page = _get_page(page_id, session_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if _USE_SYNC_PLAYWRIGHT:
            # Hybrid mode: execute in thread pool
            loop = asyncio.get_event_loop()
            root = _get_root(page, page_id, frame_selector)
            locator = root.locator(":root")
            raw = await loop.run_in_executor(
                _get_executor(),
                lambda: locator.aria_snapshot(),  # pylint: disable=unnecessary-lambda
            )
        else:
            root = _get_root(page, page_id, frame_selector)
            locator = root.locator(":root")
            raw = await locator.aria_snapshot()

        raw_str = str(raw) if raw is not None else ""
        snapshot, refs = build_role_snapshot_from_aria(
            raw_str,
            interactive=False,
            compact=False,
        )
        _session_bucket("refs", session_id, create=True)[page_id] = refs
        _session_bucket("refs_frame", session_id, create=True)[page_id] = (
            frame_selector.strip() if frame_selector else ""
        )
        _touch_activity(session_id)
        out = {
            "ok": True,
            "snapshot": snapshot,
            "refs": list(refs.keys()),
            "url": page.url,
        }
        if frame_selector and frame_selector.strip():
            out["frame_selector"] = frame_selector.strip()
        if filename and filename.strip():
            with open(filename.strip(), "w", encoding="utf-8") as f:
                f.write(snapshot)
            out["filename"] = filename.strip()
        return _tool_response(json.dumps(out, ensure_ascii=False, indent=2))
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Snapshot failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_navigate_back(page_id: str, session_id: str = "default") -> ToolResponse:
    page = _get_page(page_id, session_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if _USE_SYNC_PLAYWRIGHT:
            await _run_sync(page.go_back)
        else:
            await page.go_back()
        _touch_activity(session_id)
        return _tool_response(
            json.dumps(
                {"ok": True, "message": "Navigated back", "url": page.url},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Navigate back failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_evaluate(
    page_id: str,
    code: str,
    ref: str = "",
    element: str = "",  # pylint: disable=unused-argument
    frame_selector: str = "",
    session_id: str = "default",
) -> ToolResponse:
    code = (code or "").strip()
    if not code:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "code required for evaluate"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    page = _get_page(page_id, session_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if ref and ref.strip():
            locator = _get_locator_by_ref(
                page,
                page_id,
                ref.strip(),
                frame_selector,
                session_id,
            )
            if locator is None:
                return _tool_response(
                    json.dumps(
                        {"ok": False, "error": f"Unknown ref: {ref}"},
                        ensure_ascii=False,
                        indent=2,
                    ),
                )
            if _USE_SYNC_PLAYWRIGHT:
                result = await _run_sync(locator.evaluate, code)
            else:
                result = await locator.evaluate(code)
        else:
            if code.strip().startswith("(") or code.strip().startswith(
                "function",
            ):
                if _USE_SYNC_PLAYWRIGHT:
                    result = await _run_sync(page.evaluate, code)
                else:
                    result = await page.evaluate(code)
            else:
                if _USE_SYNC_PLAYWRIGHT:
                    result = await _run_sync(
                        page.evaluate,
                        f"() => {{ return ({code}); }}",
                    )
                else:
                    result = await page.evaluate(
                        f"() => {{ return ({code}); }}",
                    )
        _touch_activity(session_id)
        try:
            out = json.dumps(
                {"ok": True, "result": result},
                ensure_ascii=False,
                indent=2,
            )
        except TypeError:
            out = json.dumps(
                {"ok": True, "result": str(result)},
                ensure_ascii=False,
                indent=2,
            )
        return _tool_response(out)
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Evaluate failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_resize(
    page_id: str,
    width: int,
    height: int,
    session_id: str = "default",
) -> ToolResponse:
    if width <= 0 or height <= 0:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "width and height must be positive"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    page = _get_page(page_id, session_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if _USE_SYNC_PLAYWRIGHT:
            await _run_sync(
                page.set_viewport_size,
                {"width": width, "height": height},
            )
        else:
            await page.set_viewport_size({"width": width, "height": height})
        _touch_activity(session_id)
        return _tool_response(
            json.dumps(
                {"ok": True, "message": f"Resized to {width}x{height}"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Resize failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_console_messages(
    page_id: str,
    level: str,
    filename: str,
    session_id: str = "default",
) -> ToolResponse:
    level = (level or "info").strip().lower()
    order = ("error", "warning", "info", "debug")
    idx = order.index(level) if level in order else 2
    page = _get_page(page_id, session_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    logs = _session_bucket("console_logs", session_id).get(page_id, [])
    filtered = (
        [m for m in logs if order.index(m["level"]) <= idx]
        if level in order
        else logs
    )
    lines = [f"[{m['level']}] {m['text']}" for m in filtered]
    text = "\n".join(lines)
    if filename and filename.strip():
        with open(filename.strip(), "w", encoding="utf-8") as f:
            f.write(text)
        return _tool_response(
            json.dumps(
                {
                    "ok": True,
                    "message": f"Console messages saved to {filename}",
                    "filename": filename.strip(),
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    return _tool_response(
        json.dumps(
            {"ok": True, "messages": filtered, "text": text},
            ensure_ascii=False,
            indent=2,
        ),
    )


async def _action_handle_dialog(
    page_id: str,
    accept: bool,
    prompt_text: str,
    session_id: str = "default",
) -> ToolResponse:
    page = _get_page(page_id, session_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    dialogs = _session_bucket("pending_dialogs", session_id).get(page_id, [])
    if not dialogs:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "No pending dialog"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        dialog = dialogs.pop(0)
        if accept:
            if prompt_text and hasattr(dialog, "accept"):
                if _USE_SYNC_PLAYWRIGHT:
                    await _run_sync(dialog.accept, prompt_text)
                else:
                    await dialog.accept(prompt_text)
            else:
                if _USE_SYNC_PLAYWRIGHT:
                    await _run_sync(dialog.accept)
                else:
                    await dialog.accept()
        else:
            if _USE_SYNC_PLAYWRIGHT:
                await _run_sync(dialog.dismiss)
            else:
                await dialog.dismiss()
        _touch_activity(session_id)
        return _tool_response(
            json.dumps(
                {"ok": True, "message": "Dialog handled"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Handle dialog failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_file_upload(
    page_id: str,
    paths_json: str,
    session_id: str = "default",
) -> ToolResponse:
    page = _get_page(page_id, session_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    paths = _parse_json_param(paths_json, [])
    if not isinstance(paths, list):
        paths = []
    try:
        before_files = await _selected_file_names(page)
        choosers = _session_bucket("pending_file_choosers", session_id).get(
            page_id,
            [],
        )
        if not choosers:
            return _tool_response(
                json.dumps(
                    {
                        "ok": False,
                        "error": "No chooser. Click upload then file_upload.",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        chooser = choosers.pop(0)
        if paths:
            if _USE_SYNC_PLAYWRIGHT:
                await _run_sync(chooser.set_files, paths)
            else:
                await chooser.set_files(paths)
            after_files = await _selected_file_names(page)
            expected_names = [
                name for name in (_basename_from_path(str(path)) for path in paths) if name
            ]
            verified = bool(after_files) and (
                all(name in after_files for name in expected_names)
                or after_files != before_files
            )
            verification = {
                "verified": verified,
                "before_files": before_files,
                "after_files": after_files,
                "expected_files": expected_names,
            }
            if not verified:
                return _json_error(
                    "File upload verification failed: page file inputs did not reflect the requested files.",
                    verification=verification,
                )
            _touch_activity(session_id)
            return _tool_response(
                json.dumps(
                    {
                        "ok": True,
                        "message": f"Uploaded {len(paths)} file(s)",
                        "verification": verification,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        if _USE_SYNC_PLAYWRIGHT:
            await _run_sync(chooser.set_files, [])
        else:
            await chooser.set_files([])
        after_files = await _selected_file_names(page)
        _touch_activity(session_id)
        return _tool_response(
            json.dumps(
                {
                    "ok": True,
                    "message": "File chooser cancelled",
                    "verification": {
                        "verified": True,
                        "before_files": before_files,
                        "after_files": after_files,
                        "expected_files": [],
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"File upload failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_fill_form(
    page_id: str,
    fields_json: str,
    session_id: str = "default",
) -> ToolResponse:
    page = _get_page(page_id, session_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    fields = _parse_json_param(fields_json, [])
    if not isinstance(fields, list) or not fields:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "fields required (JSON array)"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    refs = _get_refs(page_id, session_id)
    # Use last snapshot's frame so fill_form works after iframe snapshot
    frame = _session_bucket("refs_frame", session_id).get(page_id, "")
    try:
        verified_fields: list[str] = []
        missing_refs: list[str] = []
        verification_failures: list[dict[str, Any]] = []
        for index, f in enumerate(fields):
            ref = (f.get("ref") or "").strip()
            field_label = ref or f"field-{index + 1}"
            if not ref or ref not in refs:
                missing_refs.append(field_label)
                continue
            locator = _get_locator_by_ref(page, page_id, ref, frame, session_id)
            if locator is None:
                verification_failures.append(
                    {
                        "ref": field_label,
                        "reason": "locator-unavailable",
                    },
                )
                continue
            field_type = (f.get("type") or "textbox").lower()
            value = f.get("value")
            if field_type == "checkbox":
                if isinstance(value, str):
                    value = value.strip().lower() in ("true", "1", "yes")
                if _USE_SYNC_PLAYWRIGHT:
                    await _run_sync(locator.set_checked, bool(value))
                else:
                    await locator.set_checked(bool(value))
            elif field_type == "radio":
                if _USE_SYNC_PLAYWRIGHT:
                    await _run_sync(locator.set_checked, True)
                else:
                    await locator.set_checked(True)
            elif field_type == "combobox":
                if _USE_SYNC_PLAYWRIGHT:
                    await _run_sync(
                        locator.select_option,
                        label=value if isinstance(value, str) else None,
                        value=value,
                    )
                else:
                    await locator.select_option(
                        label=value if isinstance(value, str) else None,
                        value=value,
                    )
            elif field_type == "slider":
                if _USE_SYNC_PLAYWRIGHT:
                    await _run_sync(locator.fill, str(value))
                else:
                    await locator.fill(str(value))
            else:
                if _USE_SYNC_PLAYWRIGHT:
                    await _run_sync(
                        locator.fill,
                        str(value) if value is not None else "",
                    )
                else:
                    await locator.fill(str(value) if value is not None else "")
            verified, actual_value = await _verify_field_value(locator, field_type, value)
            if verified:
                verified_fields.append(field_label)
            else:
                verification_failures.append(
                    {
                        "ref": field_label,
                        "expected": value,
                        "actual": actual_value,
                        "type": field_type,
                    },
                )
        verification = {
            "verified": not missing_refs and not verification_failures and bool(verified_fields),
            "verified_fields": verified_fields,
            "missing_refs": missing_refs,
            "verification_failures": verification_failures,
        }
        if missing_refs or verification_failures or not verified_fields:
            details: list[str] = []
            if missing_refs:
                details.append(f"missing refs: {', '.join(missing_refs)}")
            if verification_failures:
                details.append(
                    "verification failures: "
                    + ", ".join(str(item.get("ref") or "unknown") for item in verification_failures)
                )
            return _json_error(
                "Fill form verification failed: " + "; ".join(details),
                verification=verification,
            )
        _touch_activity(session_id)
        return _tool_response(
            json.dumps(
                {
                    "ok": True,
                    "message": f"Filled {len(verified_fields)} field(s)",
                    "verification": verification,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Fill form failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


def _run_playwright_install() -> None:
    """Run playwright install in a blocking way (for use in thread)."""
    subprocess.run(
        [sys.executable, "-m", "playwright", "install"],
        check=True,
        capture_output=True,
        text=True,
        timeout=600,  # 10 minutes max
    )


async def _action_install() -> ToolResponse:
    """Install Playwright browsers. If a system Chrome/Chromium/Edge is found,
    use it and skip download. On macOS with no Chromium, use Safari (WebKit)
    so no download is needed. Only run playwright install when necessary.
    """
    exe = _chromium_executable_path()
    if exe:
        return _tool_response(
            json.dumps(
                {
                    "ok": True,
                    "message": f"Using system browser (no download): {exe}",
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    if _use_webkit_fallback():
        return _tool_response(
            json.dumps(
                {
                    "ok": True,
                    "message": "On macOS using Safari (WebKit); no browser download needed.",
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        await asyncio.to_thread(_run_playwright_install)
        return _tool_response(
            json.dumps(
                {"ok": True, "message": "Browser installed"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except subprocess.TimeoutExpired:
        return _tool_response(
            json.dumps(
                {
                    "ok": False,
                    "error": "Browser install timed out (10 min). Run manually in terminal: "
                    f"{sys.executable!s} -m playwright install",
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {
                    "ok": False,
                    "error": f"Install failed: {e!s}. Install manually: "
                    f"{sys.executable!s} -m pip install playwright && "
                    f"{sys.executable!s} -m playwright install",
                },
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_press_key(
    page_id: str,
    key: str,
    session_id: str = "default",
) -> ToolResponse:
    key = (key or "").strip()
    if not key:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "key required for press_key"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    page = _get_page(page_id, session_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if _USE_SYNC_PLAYWRIGHT:
            await _run_sync(page.keyboard.press, key)
        else:
            await page.keyboard.press(key)
        _touch_activity(session_id)
        return _tool_response(
            json.dumps(
                {"ok": True, "message": f"Pressed key {key}"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Press key failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_network_requests(
    page_id: str,
    include_static: bool,
    filename: str,
    session_id: str = "default",
) -> ToolResponse:
    page = _get_page(page_id, session_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    requests = _session_bucket("network_requests", session_id).get(page_id, [])
    if not include_static:
        static = ("image", "stylesheet", "font", "media")
        requests = [r for r in requests if r.get("resourceType") not in static]
    lines = [
        f"{r.get('method', '')} {r.get('url', '')} {r.get('status', '')}"
        for r in requests
    ]
    text = "\n".join(lines)
    if filename and filename.strip():
        with open(filename.strip(), "w", encoding="utf-8") as f:
            f.write(text)
        return _tool_response(
            json.dumps(
                {
                    "ok": True,
                    "message": f"Network requests saved to {filename}",
                    "filename": filename.strip(),
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    return _tool_response(
        json.dumps(
            {"ok": True, "requests": requests, "text": text},
            ensure_ascii=False,
            indent=2,
        ),
    )


async def _action_run_code(
    page_id: str,
    code: str,
    session_id: str = "default",
) -> ToolResponse:
    """Run JS in page (like eval). Use evaluate for element (ref)."""
    code = (code or "").strip()
    if not code:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "code required for run_code"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    page = _get_page(page_id, session_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if code.strip().startswith("(") or code.strip().startswith("function"):
            if _USE_SYNC_PLAYWRIGHT:
                result = await _run_sync(page.evaluate, code)
            else:
                result = await page.evaluate(code)
        else:
            if _USE_SYNC_PLAYWRIGHT:
                result = await _run_sync(
                    page.evaluate,
                    f"() => {{ return ({code}); }}",
                )
            else:
                result = await page.evaluate(f"() => {{ return ({code}); }}")
        _touch_activity(session_id)
        try:
            out = json.dumps(
                {"ok": True, "result": result},
                ensure_ascii=False,
                indent=2,
            )
        except TypeError:
            out = json.dumps(
                {"ok": True, "result": str(result)},
                ensure_ascii=False,
                indent=2,
            )
        return _tool_response(out)
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Run code failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_drag(
    page_id: str,
    start_ref: str,
    end_ref: str,
    start_selector: str = "",
    end_selector: str = "",
    start_element: str = "",  # pylint: disable=unused-argument
    end_element: str = "",  # pylint: disable=unused-argument
    frame_selector: str = "",
    session_id: str = "default",
) -> ToolResponse:
    start_ref = (start_ref or "").strip()
    end_ref = (end_ref or "").strip()
    start_selector = (start_selector or "").strip()
    end_selector = (end_selector or "").strip()
    use_refs = bool(start_ref and end_ref)
    use_selectors = bool(start_selector and end_selector)
    if not use_refs and not use_selectors:
        return _tool_response(
            json.dumps(
                {
                    "ok": False,
                    "error": (
                        "drag needs (start_ref,end_ref) or (start_sel,end_sel)"
                    ),
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    page = _get_page(page_id, session_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        root = _get_root(page, page_id, frame_selector)
        if use_refs:
            start_locator = _get_locator_by_ref(
                page,
                page_id,
                start_ref,
                frame_selector,
                session_id,
            )
            end_locator = _get_locator_by_ref(
                page,
                page_id,
                end_ref,
                frame_selector,
                session_id,
            )
            if start_locator is None or end_locator is None:
                return _tool_response(
                    json.dumps(
                        {"ok": False, "error": "Unknown ref for drag"},
                        ensure_ascii=False,
                        indent=2,
                    ),
                )
        else:
            start_locator = root.locator(start_selector).first
            end_locator = root.locator(end_selector).first
        if _USE_SYNC_PLAYWRIGHT:
            await _run_sync(start_locator.drag_to, end_locator)
        else:
            await start_locator.drag_to(end_locator)
        _touch_activity(session_id)
        return _tool_response(
            json.dumps(
                {"ok": True, "message": "Drag completed"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Drag failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_hover(
    page_id: str,
    ref: str = "",
    element: str = "",  # pylint: disable=unused-argument
    selector: str = "",
    frame_selector: str = "",
    session_id: str = "default",
) -> ToolResponse:
    ref = (ref or "").strip()
    selector = (selector or "").strip()
    if not ref and not selector:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "hover requires ref or selector"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    page = _get_page(page_id, session_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        if ref:
            locator = _get_locator_by_ref(
                page,
                page_id,
                ref,
                frame_selector,
                session_id,
            )
            if locator is None:
                return _tool_response(
                    json.dumps(
                        {"ok": False, "error": f"Unknown ref: {ref}"},
                        ensure_ascii=False,
                        indent=2,
                    ),
                )
        else:
            root = _get_root(page, page_id, frame_selector)
            locator = root.locator(selector).first
        if _USE_SYNC_PLAYWRIGHT:
            await _run_sync(locator.hover)
        else:
            await locator.hover()
        _touch_activity(session_id)
        return _tool_response(
            json.dumps(
                {"ok": True, "message": f"Hovered {ref or selector}"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Hover failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_select_option(
    page_id: str,
    ref: str = "",
    element: str = "",  # pylint: disable=unused-argument
    values_json: str = "",
    frame_selector: str = "",
    session_id: str = "default",
) -> ToolResponse:
    ref = (ref or "").strip()
    values = _parse_json_param(values_json, [])
    if not isinstance(values, list):
        values = [values] if values is not None else []
    if not ref:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": "ref required for select_option"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    if not values:
        return _tool_response(
            json.dumps(
                {
                    "ok": False,
                    "error": "values required (JSON array or comma-separated)",
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    page = _get_page(page_id, session_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    try:
        locator = _get_locator_by_ref(
            page,
            page_id,
            ref,
            frame_selector,
            session_id,
        )
        if locator is None:
            return _tool_response(
                json.dumps(
                    {"ok": False, "error": f"Unknown ref: {ref}"},
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        if _USE_SYNC_PLAYWRIGHT:
            await _run_sync(locator.select_option, value=values)
        else:
            await locator.select_option(value=values)
        _touch_activity(session_id)
        return _tool_response(
            json.dumps(
                {"ok": True, "message": f"Selected {values}"},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Select option failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


async def _action_tabs(  # pylint: disable=too-many-return-statements
    page_id: str,
    tab_action: str,
    index: int,
    session_id: str = "default",
) -> ToolResponse:
    def _distinct_page_ids(pages_map: dict[str, Any]) -> list[str]:
        ordered_ids: list[str] = []
        seen_handles: set[int] = set()
        for candidate_id, candidate_page in pages_map.items():
            marker = id(candidate_page) if candidate_page is not None else hash(candidate_id)
            if marker in seen_handles:
                continue
            seen_handles.add(marker)
            ordered_ids.append(candidate_id)
        return ordered_ids

    async def _synchronize_pages() -> dict[str, Any]:
        pages_map = _session_bucket("pages", session_id, create=True)
        session = _get_session_state(session_id)
        if not isinstance(session, dict):
            return pages_map
        context = session.get("context")
        if context is None:
            return pages_map
        try:
            if _USE_SYNC_PLAYWRIGHT:
                live_pages = await _run_sync(lambda: list(context.pages))
            else:
                live_pages = list(context.pages)
        except Exception:
            return pages_map
        for live_page in live_pages:
            if any(existing_page is live_page for existing_page in pages_map.values()):
                continue
            new_id = _next_page_id(session_id)
            _session_bucket("refs", session_id, create=True)[new_id] = {}
            _session_bucket("console_logs", session_id, create=True)[new_id] = []
            _session_bucket("network_requests", session_id, create=True)[new_id] = []
            _session_bucket("pending_dialogs", session_id, create=True)[new_id] = []
            _session_bucket("pending_file_choosers", session_id, create=True)[new_id] = []
            _attach_page_listeners(live_page, new_id, session_id)
            pages_map[new_id] = live_page
        return pages_map

    tab_action = (tab_action or "").strip().lower()
    if not tab_action:
        return _tool_response(
            json.dumps(
                {
                    "ok": False,
                    "error": "tab_action required (list, new, close, select)",
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    pages = await _synchronize_pages()
    page_ids = _distinct_page_ids(pages)
    if tab_action == "switch":
        tab_action = "select"
    if tab_action == "list":
        return _tool_response(
            json.dumps(
                {"ok": True, "tabs": page_ids, "count": len(page_ids)},
                ensure_ascii=False,
                indent=2,
            ),
        )
    if tab_action == "new":
        session = await _ensure_browser_session(session_id)
        if not isinstance(session, dict) or session.get("context") is None:
            err = _state.get("_last_browser_error") or "Browser not started"
            return _tool_response(
                json.dumps(
                    {"ok": False, "error": err},
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        try:
            if _USE_SYNC_PLAYWRIGHT:
                page = await _run_sync(session["context"].new_page)
            else:
                page = await session["context"].new_page()
            pages = await _synchronize_pages()
            new_id = next(
                (
                    candidate_id
                    for candidate_id, candidate_page in pages.items()
                    if candidate_page is page
                ),
                None,
            )
            if new_id is None:
                new_id = _next_page_id(session_id)
                _session_bucket("refs", session_id, create=True)[new_id] = {}
                _session_bucket("console_logs", session_id, create=True)[new_id] = []
                _session_bucket("network_requests", session_id, create=True)[new_id] = []
                _session_bucket("pending_dialogs", session_id, create=True)[new_id] = []
                _session_bucket("pending_file_choosers", session_id, create=True)[new_id] = []
                _attach_page_listeners(page, new_id, session_id)
                pages[new_id] = page
            _set_current_page_id(new_id, session_id)
            _state["current_session_id"] = session_id
            _touch_activity(session_id)
            return _tool_response(
                json.dumps(
                    {
                        "ok": True,
                        "page_id": new_id,
                        "tabs": _distinct_page_ids(_session_bucket("pages", session_id)),
                        "session_id": session_id,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        except Exception as e:
            return _tool_response(
                json.dumps(
                    {"ok": False, "error": f"New tab failed: {e!s}"},
                    ensure_ascii=False,
                    indent=2,
                ),
            )
    if tab_action == "close":
        target_id = page_ids[index] if 0 <= index < len(page_ids) else page_id
        return await _action_close(target_id, session_id)
    if tab_action == "select":
        target_id = page_ids[index] if 0 <= index < len(page_ids) else page_id
        if target_id not in pages:
            return _json_error(f"Tab '{target_id}' not found in session '{session_id}'")
        target_page = pages[target_id]
        resolved_page_id = page_id if page_id in pages else target_id
        pages[resolved_page_id] = target_page
        _set_current_page_id(resolved_page_id, session_id)
        _state["current_session_id"] = session_id
        _touch_activity(session_id)
        return _tool_response(
            json.dumps(
                {
                    "ok": True,
                    "message": (
                        f"Rebound page_id={resolved_page_id} to tab {target_id}"
                        if resolved_page_id != target_id
                        else f"Use page_id={target_id} for later actions"
                    ),
                    "page_id": resolved_page_id,
                    "selected_page_id": target_id,
                    "session_id": session_id,
                    "verification": {
                        "verified": True,
                        "current_page_id": resolved_page_id,
                        "selected_page_id": target_id,
                        "tabs": page_ids,
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    return _tool_response(
        json.dumps(
            {"ok": False, "error": f"Unknown tab_action: {tab_action}"},
            ensure_ascii=False,
            indent=2,
        ),
    )


async def _action_wait_for(
    page_id: str,
    wait_time: float = 0,
    text: str = "",
    text_gone: str = "",
    session_id: str = "default",
) -> ToolResponse:
    page = _get_page(page_id, session_id)
    if not page:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Page '{page_id}' not found"},
                ensure_ascii=False,
                indent=2,
            ),
        )

    wait_seconds = max(float(wait_time or 0), 0.0)
    timeout_ms = max(int(wait_seconds * 1000), 1) if wait_seconds else 30_000
    try:
        if text:
            script = "(text) => document.body && document.body.innerText.includes(text)"
            if _USE_SYNC_PLAYWRIGHT:
                await _run_sync(
                    page.wait_for_function,
                    script,
                    arg=text,
                    timeout=timeout_ms,
                )
            else:
                await page.wait_for_function(
                    script,
                    arg=text,
                    timeout=timeout_ms,
                )
            message = f"Text appeared: {text}"
        elif text_gone:
            script = "(text) => !document.body || !document.body.innerText.includes(text)"
            if _USE_SYNC_PLAYWRIGHT:
                await _run_sync(
                    page.wait_for_function,
                    script,
                    arg=text_gone,
                    timeout=timeout_ms,
                )
            else:
                await page.wait_for_function(
                    script,
                    arg=text_gone,
                    timeout=timeout_ms,
                )
            message = f"Text disappeared: {text_gone}"
        else:
            timeout_value = int(wait_seconds * 1000)
            if _USE_SYNC_PLAYWRIGHT:
                await _run_sync(page.wait_for_timeout, timeout_value)
            else:
                await page.wait_for_timeout(timeout_value)
            message = f"Waited {wait_seconds:g}s"
        _touch_activity(session_id)
        return _tool_response(
            json.dumps(
                {"ok": True, "message": message},
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as e:
        return _tool_response(
            json.dumps(
                {"ok": False, "error": f"Wait failed: {e!s}"},
                ensure_ascii=False,
                indent=2,
            ),
        )


__all__ = [name for name in globals() if not name.startswith("__")]
