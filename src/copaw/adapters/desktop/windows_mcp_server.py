# -*- coding: utf-8 -*-
"""stdio MCP server exposing Windows desktop control actions."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .windows_host import DesktopAutomationError, WindowSelector, WindowsDesktopHost

server = FastMCP(
    name="copaw-desktop-windows",
    instructions=(
        "Control a local Windows desktop session through structured app/window/"
        "mouse/keyboard tools."
    ),
)
_HOST = WindowsDesktopHost()


def _selector(
    *,
    handle: int | None = None,
    title: str | None = None,
    title_contains: str | None = None,
    title_regex: str | None = None,
    process_id: int | None = None,
) -> WindowSelector:
    return WindowSelector(
        handle=handle,
        title=title,
        title_contains=title_contains,
        title_regex=title_regex,
        process_id=process_id,
    )


def _run_tool(tool_name: str, action, **kwargs) -> dict[str, Any]:
    try:
        result = action(**kwargs)
    except DesktopAutomationError as exc:
        payload = {
            "success": False,
            "tool": tool_name,
            "error": str(exc),
        }
        error_code = getattr(exc, "code", None)
        error_details = getattr(exc, "details", None)
        if error_code:
            payload["error_code"] = error_code
        if error_details:
            payload["error_details"] = error_details
        return payload
    return {
        "tool": tool_name,
        **result,
    }


@server.tool(
    name="list_windows",
    description="List top-level desktop windows and their bounds.",
    structured_output=True,
)
def list_windows(
    title: str | None = None,
    title_contains: str | None = None,
    title_regex: str | None = None,
    process_id: int | None = None,
    include_hidden: bool = False,
    limit: int = 50,
) -> dict[str, Any]:
    return _run_tool(
        "list_windows",
        _HOST.list_windows,
        selector=_selector(
            title=title,
            title_contains=title_contains,
            title_regex=title_regex,
            process_id=process_id,
        ),
        include_hidden=include_hidden,
        limit=limit,
    )


@server.tool(
    name="get_foreground_window",
    description="Return the current foreground window.",
    structured_output=True,
)
def get_foreground_window() -> dict[str, Any]:
    return _run_tool("get_foreground_window", _HOST.get_foreground_window)


@server.tool(
    name="launch_application",
    description="Launch a local Windows application.",
    structured_output=True,
)
def launch_application(
    executable: str,
    args: list[str] | None = None,
    cwd: str | None = None,
) -> dict[str, Any]:
    return _run_tool(
        "launch_application",
        _HOST.launch_application,
        executable=executable,
        args=args or [],
        cwd=cwd,
    )


@server.tool(
    name="wait_for_window",
    description="Wait until a matching top-level window appears.",
    structured_output=True,
)
def wait_for_window(
    handle: int | None = None,
    title: str | None = None,
    title_contains: str | None = None,
    title_regex: str | None = None,
    process_id: int | None = None,
    timeout_seconds: float = 10.0,
    poll_interval_seconds: float = 0.25,
    include_hidden: bool = False,
) -> dict[str, Any]:
    return _run_tool(
        "wait_for_window",
        _HOST.wait_for_window,
        selector=_selector(
            handle=handle,
            title=title,
            title_contains=title_contains,
            title_regex=title_regex,
            process_id=process_id,
        ),
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        include_hidden=include_hidden,
    )


@server.tool(
    name="focus_window",
    description="Bring a matching window to the foreground.",
    structured_output=True,
)
def focus_window(
    handle: int | None = None,
    title: str | None = None,
    title_contains: str | None = None,
    title_regex: str | None = None,
    process_id: int | None = None,
) -> dict[str, Any]:
    return _run_tool(
        "focus_window",
        _HOST.focus_window,
        selector=_selector(
            handle=handle,
            title=title,
            title_contains=title_contains,
            title_regex=title_regex,
            process_id=process_id,
        ),
    )


@server.tool(
    name="verify_window_focus",
    description="Verify that a matching window still owns the foreground.",
    structured_output=True,
)
def verify_window_focus(
    handle: int | None = None,
    title: str | None = None,
    title_contains: str | None = None,
    title_regex: str | None = None,
    process_id: int | None = None,
) -> dict[str, Any]:
    return _run_tool(
        "verify_window_focus",
        _HOST.verify_window_focus,
        selector=_selector(
            handle=handle,
            title=title,
            title_contains=title_contains,
            title_regex=title_regex,
            process_id=process_id,
        ),
    )


@server.tool(
    name="click",
    description="Click a screen coordinate or a coordinate inside a resolved window.",
    structured_output=True,
)
def click(
    x: int | None = None,
    y: int | None = None,
    handle: int | None = None,
    title: str | None = None,
    title_contains: str | None = None,
    title_regex: str | None = None,
    process_id: int | None = None,
    relative_to_window: bool = False,
    click_count: int = 1,
    button: str = "left",
    focus_target: bool = True,
) -> dict[str, Any]:
    return _run_tool(
        "click",
        _HOST.click,
        x=x,
        y=y,
        selector=_selector(
            handle=handle,
            title=title,
            title_contains=title_contains,
            title_regex=title_regex,
            process_id=process_id,
        ),
        relative_to_window=relative_to_window,
        click_count=click_count,
        button=button,
        focus_target=focus_target,
    )


@server.tool(
    name="write_document_file",
    description="Create or overwrite a text document, then reopen and reread it.",
    structured_output=True,
)
def write_document_file(
    path: str,
    content: str,
    encoding: str = "utf-8",
    create_parent_dirs: bool = True,
) -> dict[str, Any]:
    return _run_tool(
        "write_document_file",
        _HOST.write_document_file,
        path=path,
        content=content,
        encoding=encoding,
        create_parent_dirs=create_parent_dirs,
    )


@server.tool(
    name="edit_document_file",
    description="Edit a text document and verify exact content by rereading it.",
    structured_output=True,
)
def edit_document_file(
    path: str,
    find_text: str,
    replace_text: str,
    encoding: str = "utf-8",
) -> dict[str, Any]:
    return _run_tool(
        "edit_document_file",
        _HOST.edit_document_file,
        path=path,
        find_text=find_text,
        replace_text=replace_text,
        encoding=encoding,
    )


@server.tool(
    name="type_text",
    description="Send unicode text to the foreground or selected window.",
    structured_output=True,
)
def type_text(
    text: str,
    handle: int | None = None,
    title: str | None = None,
    title_contains: str | None = None,
    title_regex: str | None = None,
    process_id: int | None = None,
    focus_target: bool = True,
) -> dict[str, Any]:
    return _run_tool(
        "type_text",
        _HOST.type_text,
        text=text,
        selector=_selector(
            handle=handle,
            title=title,
            title_contains=title_contains,
            title_regex=title_regex,
            process_id=process_id,
        ),
        focus_target=focus_target,
    )


@server.tool(
    name="press_keys",
    description="Send a key chord like Ctrl+L or Enter.",
    structured_output=True,
)
def press_keys(
    keys: str | list[str],
    handle: int | None = None,
    title: str | None = None,
    title_contains: str | None = None,
    title_regex: str | None = None,
    process_id: int | None = None,
    focus_target: bool = True,
) -> dict[str, Any]:
    return _run_tool(
        "press_keys",
        _HOST.press_keys,
        keys=keys,
        selector=_selector(
            handle=handle,
            title=title,
            title_contains=title_contains,
            title_regex=title_regex,
            process_id=process_id,
        ),
        focus_target=focus_target,
    )


@server.tool(
    name="close_window",
    description="Request a graceful close for a matching top-level window.",
    structured_output=True,
)
def close_window(
    handle: int | None = None,
    title: str | None = None,
    title_contains: str | None = None,
    title_regex: str | None = None,
    process_id: int | None = None,
) -> dict[str, Any]:
    return _run_tool(
        "close_window",
        _HOST.close_window,
        selector=_selector(
            handle=handle,
            title=title,
            title_contains=title_contains,
            title_regex=title_regex,
            process_id=process_id,
        ),
    )


if __name__ == "__main__":
    server.run("stdio")
