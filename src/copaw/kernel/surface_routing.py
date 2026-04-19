# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

SURFACE_ORDER: tuple[str, ...] = ("file", "browser", "desktop")

FILE_DIRECT_TEXT_HINTS: tuple[tuple[str, str], ...] = (
    ("文件", "文件"),
    ("文件夹", "文件夹"),
    ("目录", "目录"),
    ("文档", "文档"),
    ("资料", "资料"),
    ("图片", "图片"),
    ("封面", "封面"),
    ("text", "text"),
    ("txt", "txt"),
    ("text file", "text file"),
    ("folder", "folder"),
    ("file", "file"),
    ("document", "document"),
    ("material", "material"),
)
DESKTOP_DIRECT_TEXT_HINTS: tuple[tuple[str, str], ...] = (
    ("桌面", "桌面"),
    ("桌面应用", "桌面应用"),
    ("桌面软件", "桌面软件"),
    ("桌面客户端", "桌面客户端"),
    ("windows", "Windows"),
    ("win32", "Win32"),
    ("desktop", "desktop"),
)
BROWSER_DIRECT_TEXT_HINTS: tuple[tuple[str, str], ...] = (
    ("浏览器", "浏览器"),
    ("网页", "网页"),
    ("网站", "网站"),
    ("平台", "平台"),
    ("草稿箱", "草稿箱"),
    ("表单", "表单"),
    ("登录", "登录"),
    ("browser", "browser"),
    ("web", "web"),
    ("website", "website"),
    ("page", "page"),
    ("dashboard", "dashboard"),
)

_FILE_SURFACE_TOKENS: tuple[str, ...] = (
    " file ",
    " files ",
    " folder ",
    " folders ",
    " text ",
    " txt ",
    " document ",
    " documents ",
    " 文件",
    "文件",
    "文件夹",
    "目录",
    "文档",
    "资料",
    "图片",
    "封面",
    "上传",
    "txt",
)
_DESKTOP_SURFACE_TOKENS: tuple[str, ...] = (
    " desktop ",
    " windows ",
    " win32 ",
    "桌面",
    "电脑",
    "本机",
    "资源管理器",
    "桌面应用",
    "桌面软件",
    "桌面客户端",
)
_BROWSER_SURFACE_TOKENS: tuple[str, ...] = (
    " browser ",
    " chrome ",
    " edge ",
    " page ",
    " tab ",
    "网页",
    "网站",
    "浏览器",
    "平台",
    "草稿箱",
)

_FILE_ACTION_HINTS: tuple[tuple[str, str], ...] = (
    ("整理", "整理"),
    ("归档", "归档"),
    ("分类", "分类"),
    ("移动", "移动"),
    ("保存", "保存"),
    ("上传", "上传"),
    ("选择", "选择"),
    ("archive", "archive"),
    ("organize", "organize"),
    ("sort", "sort"),
    ("move", "move"),
    ("save", "save"),
    ("upload", "upload"),
    ("select", "select"),
)
_DESKTOP_ACTION_HINTS: tuple[tuple[str, str], ...] = (
    ("打开", "打开"),
    ("启动", "启动"),
    ("进入", "进入"),
    ("客户端", "客户端"),
    ("软件", "软件"),
    ("应用", "应用"),
    ("窗口", "窗口"),
    ("click", "click"),
    ("type", "type"),
    ("launch", "launch"),
    ("client", "client"),
    ("app", "app"),
    ("application", "application"),
    ("window", "window"),
)
_BROWSER_ACTION_HINTS: tuple[tuple[str, str], ...] = (
    ("登录", "登录"),
    ("后台", "后台"),
    ("平台", "平台"),
    ("草稿", "草稿"),
    ("页面", "页面"),
    ("网页", "网页"),
    ("站点", "站点"),
    ("链接", "链接"),
    ("login", "login"),
    ("sign in", "sign in"),
    ("dashboard", "dashboard"),
    ("backend", "backend"),
    ("admin", "admin"),
    ("browser", "browser"),
    ("website", "website"),
    ("page", "page"),
    ("link", "link"),
)

_FILE_ENVIRONMENT_HINTS = ("file", "document", "folder", "workspace", "file-view")
_DESKTOP_ENVIRONMENT_HINTS = ("desktop", "window", "client", "windows", "local")
_BROWSER_ENVIRONMENT_HINTS = ("browser", "web", "page", "dashboard", "backend")


def normalize_execution_surfaces(*values: object) -> list[str]:
    normalized: list[str] = []
    for value in values:
        items = value if isinstance(value, (list, tuple, set)) else [value]
        for item in items:
            text = _string(item)
            if text is None:
                continue
            lowered = text.lower()
            if lowered in {"file", "browser", "desktop"} and lowered not in normalized:
                normalized.append(lowered)
    return normalized


def infer_requested_execution_surfaces(
    *,
    texts: Sequence[str] | None = None,
    capability_ids: Sequence[str] | None = None,
    capability_mounts: Sequence[Any] | None = None,
    environment_texts: Sequence[str] | None = None,
    allow_hard_hints_without_text: bool = False,
) -> list[str]:
    normalized_texts = [text for text in _string_list(texts) if text]
    message_blob = _search_blob(normalized_texts)
    combined_text = f" {' '.join(normalized_texts).lower()} "
    capability_id_set = {
        capability_id.lower()
        for capability_id in _string_list(capability_ids)
    }
    mount_blob = _search_blob(_collect_mount_texts(capability_mounts))
    environment_blob = _search_blob(environment_texts)

    surfaces: list[str] = []
    for surface in SURFACE_ORDER:
        text_requested = _surface_requested_from_text(
            surface=surface,
            message_blob=message_blob,
            combined_text=combined_text,
        )
        capability_supported = _surface_supported_by_capabilities(
            surface=surface,
            capability_ids=capability_id_set,
            mount_blob=mount_blob,
        )
        environment_supported = _surface_supported_by_environment(
            surface=surface,
            environment_blob=environment_blob,
        )
        hard_hint_supported = capability_supported or environment_supported
        if (
            allow_hard_hints_without_text
            and hard_hint_supported
            and _surface_can_use_hard_hints_without_text(
                surface=surface,
                text_requested=text_requested,
            )
        ):
            surfaces.append(surface)
            continue
        if text_requested and capability_supported:
            surfaces.append(surface)
            continue
        if text_requested and environment_supported:
            surfaces.append(surface)
            continue
        if text_requested:
            surfaces.append(surface)

    if (
        "file" in surfaces
        and "desktop" not in surfaces
        and "browser" not in surfaces
        and bool(_match_keyword_labels(message_blob, _DESKTOP_ACTION_HINTS))
    ):
        surfaces.append("desktop")
    return normalize_execution_surfaces(surfaces)


def resolve_execution_surface_support(
    *,
    surface: str,
    capability_ids: Sequence[str] | None = None,
    capability_mounts: Sequence[Any] | None = None,
    environment_texts: Sequence[str] | None = None,
    preferred_families: Sequence[str] | None = None,
) -> str | None:
    normalized_surface = _string(surface)
    if normalized_surface is None:
        return None
    lowered_surface = normalized_surface.lower()
    capability_id_set = {
        capability_id.lower()
        for capability_id in _string_list(capability_ids)
    }
    mount_blob = _search_blob(_collect_mount_texts(capability_mounts))
    if _surface_supported_by_capabilities(
        surface=lowered_surface,
        capability_ids=capability_id_set,
        mount_blob=mount_blob,
    ):
        return f"{lowered_surface} capability match"

    preferred_family_set = {
        family.lower()
        for family in _string_list(preferred_families)
    }
    environment_blob = _search_blob(environment_texts)
    if lowered_surface in preferred_family_set or _surface_supported_by_environment(
        surface=lowered_surface,
        environment_blob=environment_blob,
    ):
        return f"{lowered_surface} environment match"
    return None


def _surface_requested_from_text(
    *,
    surface: str,
    message_blob: str,
    combined_text: str,
) -> bool:
    if surface == "file":
        return bool(
            _match_keyword_labels(message_blob, FILE_DIRECT_TEXT_HINTS)
            or _contains_token(combined_text, _FILE_SURFACE_TOKENS)
            or _match_keyword_labels(message_blob, _FILE_ACTION_HINTS)
        )
    if surface == "desktop":
        return bool(
            _match_keyword_labels(message_blob, DESKTOP_DIRECT_TEXT_HINTS)
            or _contains_token(combined_text, _DESKTOP_SURFACE_TOKENS)
            or _match_keyword_labels(message_blob, _DESKTOP_ACTION_HINTS)
        )
    if surface == "browser":
        return bool(
            _match_keyword_labels(message_blob, BROWSER_DIRECT_TEXT_HINTS)
            or _contains_token(combined_text, _BROWSER_SURFACE_TOKENS)
            or _match_keyword_labels(message_blob, _BROWSER_ACTION_HINTS)
        )
    return False


def _surface_supported_by_capabilities(
    *,
    surface: str,
    capability_ids: set[str],
    mount_blob: str,
) -> bool:
    if surface == "file":
        return any(
            capability_id in {"tool:read_file", "tool:write_file", "tool:edit_file", "tool:document_surface"}
            for capability_id in capability_ids
        ) or any(hint in mount_blob for hint in (" file ", " file-view ", " document ", " folder "))
    if surface == "desktop":
        return any(
            "desktop" in capability_id or capability_id.startswith("mcp:desktop")
            for capability_id in capability_ids
        ) or any(hint in mount_blob for hint in (" desktop ", " window ", " windows ", " client "))
    if surface == "browser":
        return any(
            "browser" in capability_id or "web" in capability_id
            for capability_id in capability_ids
        ) or any(hint in mount_blob for hint in (" browser ", " web ", " page ", " dashboard "))
    return False


def _surface_supported_by_environment(
    *,
    surface: str,
    environment_blob: str,
) -> bool:
    if surface == "file":
        return any(hint in environment_blob for hint in _FILE_ENVIRONMENT_HINTS)
    if surface == "desktop":
        return any(hint in environment_blob for hint in _DESKTOP_ENVIRONMENT_HINTS)
    if surface == "browser":
        return any(hint in environment_blob for hint in _BROWSER_ENVIRONMENT_HINTS)
    return False


def _surface_can_use_hard_hints_without_text(
    *,
    surface: str,
    text_requested: bool,
) -> bool:
    if text_requested:
        return True
    return surface in {"browser", "desktop"}


def _collect_mount_texts(capability_mounts: Sequence[Any] | None) -> list[str]:
    texts: list[str] = []
    for mount in list(capability_mounts or []):
        metadata = getattr(mount, "metadata", None)
        texts.extend(
            _string_list(
                [
                    getattr(mount, "id", None),
                    getattr(mount, "name", None),
                    getattr(mount, "summary", None),
                    getattr(mount, "environment_description", None),
                    list(getattr(mount, "environment_requirements", []) or []),
                    list(getattr(mount, "tags", []) or []),
                    list(metadata.values()) if isinstance(metadata, dict) else None,
                ]
            )
        )
    return texts


def _contains_token(combined_text: str, tokens: Iterable[str]) -> bool:
    return any(token in combined_text for token in tokens)


def _match_keyword_labels(
    message_blob: str,
    hints: tuple[tuple[str, str], ...],
) -> list[str]:
    return [
        label
        for hint, label in hints
        if hint.strip() and hint.lower() in message_blob
    ]


def _search_blob(values: Sequence[str] | None) -> str:
    lowered = [
        text.lower()
        for text in _string_list(values)
    ]
    if not lowered:
        return " "
    return f" {' '.join(lowered)} "


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = value if isinstance(value, str) else str(value)
    text = text.strip()
    return text or None


def _string_list(values: Sequence[Any] | None) -> list[str]:
    resolved: list[str] = []
    if values is None:
        return resolved
    for value in values:
        if isinstance(value, (list, tuple, set)):
            resolved.extend(_string_list(list(value)))
            continue
        text = _string(value)
        if text is not None:
            resolved.append(text)
    return resolved


__all__ = [
    "BROWSER_DIRECT_TEXT_HINTS",
    "DESKTOP_DIRECT_TEXT_HINTS",
    "FILE_DIRECT_TEXT_HINTS",
    "SURFACE_ORDER",
    "infer_requested_execution_surfaces",
    "normalize_execution_surfaces",
    "resolve_execution_surface_support",
]
