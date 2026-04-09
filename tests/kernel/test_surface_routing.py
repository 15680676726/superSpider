# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.capabilities.models import CapabilityMount
from copaw.kernel.surface_routing import (
    infer_requested_execution_surfaces,
    resolve_execution_surface_support,
)


def test_infer_requested_execution_surfaces_uses_hard_hints_when_enabled() -> None:
    mounts = [
        CapabilityMount(
            id="mcp:desktop_windows",
            name="desktop_windows",
            summary="Governed desktop control surface.",
            kind="remote-mcp",
            source_kind="mcp",
            risk_level="guarded",
            environment_requirements=["desktop", "interactive-session"],
            tags=["desktop"],
        ),
        CapabilityMount(
            id="tool:write_file",
            name="write_file",
            summary="Write local files.",
            kind="local-tool",
            source_kind="tool",
            risk_level="guarded",
            environment_requirements=["workspace", "file-view"],
            tags=["file", "write"],
        ),
    ]

    assert infer_requested_execution_surfaces(
        texts=["处理文末天机里的这一批任务"],
        capability_mounts=mounts,
        capability_ids=["mcp:desktop_windows", "tool:write_file"],
        environment_texts=["desktop", "workspace", "file-view"],
    ) == []

    assert infer_requested_execution_surfaces(
        texts=["处理文末天机里的这一批任务"],
        capability_mounts=mounts,
        capability_ids=["mcp:desktop_windows", "tool:write_file"],
        environment_texts=["desktop", "workspace", "file-view"],
        allow_hard_hints_without_text=True,
    ) == ["desktop"]


def test_resolve_execution_surface_support_prefers_capability_mounts() -> None:
    mounts = [
        CapabilityMount(
            id="tool:browser_use",
            name="browser_use",
            summary="Use a governed browser runtime.",
            kind="local-tool",
            source_kind="tool",
            risk_level="guarded",
            environment_requirements=["browser", "network"],
            tags=["browser", "network"],
        ),
    ]

    assert (
        resolve_execution_surface_support(
            surface="browser",
            capability_mounts=mounts,
            capability_ids=["tool:browser_use"],
            environment_texts=["network", "dashboard"],
            preferred_families=[],
        )
        == "browser capability match"
    )
    assert (
        resolve_execution_surface_support(
            surface="desktop",
            capability_mounts=[],
            capability_ids=[],
            environment_texts=["desktop", "window focus", "local client"],
            preferred_families=[],
        )
        == "desktop environment match"
    )


def test_infer_requested_execution_surfaces_recognizes_platform_draft_and_upload_browser_flow() -> None:
    assert infer_requested_execution_surfaces(
        texts=[
            "请在浏览器里打开番茄创作平台草稿箱，继续写今天的小说章节，并从 Windows 桌面目录选择封面图片上传",
        ],
        capability_ids=["tool:browser_use", "mcp:desktop_windows", "tool:write_file"],
        capability_mounts=[],
        environment_texts=["browser", "desktop", "workspace"],
    ) == ["file", "browser", "desktop"]
