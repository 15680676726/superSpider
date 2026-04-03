# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Callable

from ...agents.tools import (
    browser_use,
    desktop_screenshot,
    edit_file,
    execute_shell_command,
    get_current_time,
    read_file,
    send_file_to_user,
    write_file,
)
from ..models import CapabilityMount


def list_tool_capabilities() -> list[CapabilityMount]:
    tools: list[tuple[Callable[..., object], dict[str, object]]] = [
        (
            execute_shell_command,
            {
                "risk_level": "guarded",
                "risk_description": "执行任意 shell 命令，可能修改文件系统或触发外部进程",
                "environment_requirements": ["workspace"],
                "environment_description": "需要工作目录环境来执行命令",
                "evidence_contract": ["shell-command", "stdout", "stderr"],
                "evidence_description": "记录命令内容、标准输出和标准错误",
                "replay_support": True,
                "tags": ["shell", "execution", "workspace"],
                "metadata": {
                    "execution_policy": {
                        "evidence_owner": "tool-bridge",
                    },
                },
            },
        ),
        (
            read_file,
            {
                "risk_level": "auto",
                "risk_description": "只读操作，不修改文件系统",
                "environment_requirements": ["workspace", "file-view"],
                "environment_description": "需要工作目录和文件视图环境",
                "evidence_contract": ["file-read"],
                "evidence_description": "记录读取的文件路径",
                "replay_support": True,
                "tags": ["file", "read-only"],
                "metadata": {
                    "execution_policy": {
                        "action_mode": "read",
                        "evidence_owner": "execution-facade",
                    },
                },
            },
        ),
        (
            write_file,
            {
                "risk_level": "guarded",
                "risk_description": "写入文件，可能覆盖已有内容",
                "environment_requirements": ["workspace", "file-view"],
                "environment_description": "需要工作目录和文件视图环境",
                "evidence_contract": ["file-write"],
                "evidence_description": "记录写入的文件路径和内容摘要",
                "replay_support": True,
                "tags": ["file", "write"],
                "metadata": {
                    "execution_policy": {
                        "evidence_owner": "tool-bridge",
                        "writer_scope_source": "file_path",
                    },
                },
            },
        ),
        (
            edit_file,
            {
                "risk_level": "guarded",
                "risk_description": "编辑已有文件，可能修改关键内容",
                "environment_requirements": ["workspace", "file-view"],
                "environment_description": "需要工作目录和文件视图环境",
                "evidence_contract": ["file-edit"],
                "evidence_description": "记录编辑的文件路径和变更差异",
                "replay_support": True,
                "tags": ["file", "edit"],
                "metadata": {
                    "execution_policy": {
                        "action_mode": "write",
                        "evidence_owner": "tool-bridge",
                        "writer_scope_source": "file_path",
                    },
                },
            },
        ),
        (
            browser_use,
            {
                "risk_level": "guarded",
                "risk_description": "操控浏览器，可能访问外部网站或提交表单",
                "environment_requirements": ["browser", "network"],
                "environment_description": "需要浏览器实例和网络连接",
                "evidence_contract": ["browser-action", "browser-artifact"],
                "evidence_description": "记录浏览器操作和截图等产物",
                "replay_support": True,
                "tags": ["browser", "network", "external"],
                "metadata": {
                    "execution_policy": {
                        "action_mode": "write",
                        "evidence_owner": "tool-bridge",
                    },
                },
            },
        ),
        (
            desktop_screenshot,
            {
                "risk_level": "guarded",
                "risk_description": "截取桌面屏幕，涉及隐私敏感内容",
                "environment_requirements": ["desktop"],
                "environment_description": "需要桌面环境访问权限",
                "evidence_contract": ["screenshot-artifact"],
                "evidence_description": "记录截图产物",
                "replay_support": True,
                "tags": ["desktop", "screenshot"],
                "metadata": {
                    "execution_policy": {
                        "action_mode": "read",
                        "evidence_owner": "execution-facade",
                    },
                },
            },
        ),
        (
            send_file_to_user,
            {
                "risk_level": "guarded",
                "risk_description": "向渠道发送文件，涉及外部通信",
                "environment_requirements": ["channel-session", "workspace"],
                "environment_description": "需要活跃的渠道会话和工作目录",
                "evidence_contract": ["file-transfer"],
                "evidence_description": "记录文件传输路径和目标渠道",
                "replay_support": False,
                "tags": ["file", "channel", "transfer"],
                "metadata": {
                    "execution_policy": {
                        "action_mode": "write",
                        "evidence_owner": "execution-facade",
                        "writer_scope_source": "file_path",
                    },
                },
            },
        ),
        (
            get_current_time,
            {
                "risk_level": "auto",
                "risk_description": "纯只读操作，无副作用",
                "environment_requirements": [],
                "environment_description": "无特殊环境要求",
                "evidence_contract": ["call-record"],
                "evidence_description": "记录调用事实",
                "replay_support": False,
                "tags": ["utility", "read-only"],
                "metadata": {
                    "execution_policy": {
                        "action_mode": "read",
                        "evidence_owner": "execution-facade",
                    },
                },
            },
        ),
    ]
    mounts: list[CapabilityMount] = []
    for func, meta in tools:
        summary = _callable_summary(func)
        mounts.append(
            CapabilityMount(
                id=f"tool:{func.__name__}",
                name=func.__name__,
                summary=summary,
                kind="local-tool",
                source_kind="tool",
                risk_level=str(meta["risk_level"]),
                risk_description=str(meta.get("risk_description", "")),
                environment_requirements=list(meta["environment_requirements"]),
                environment_description=str(meta.get("environment_description", "")),
                role_access_policy=["all"],
                evidence_contract=list(meta["evidence_contract"]),
                evidence_description=str(meta.get("evidence_description", "")),
                executor_ref=func.__module__,
                replay_support=bool(meta["replay_support"]),
                tags=list(meta.get("tags", [])),
                metadata=dict(meta.get("metadata", {})),
            ),
        )
    mounts.sort(key=lambda item: item.id)
    return mounts


def _callable_summary(func: Callable[..., object]) -> str:
    doc = (func.__doc__ or "").strip().splitlines()
    if doc:
        return doc[0].strip()
    return f"Built-in tool {func.__name__}."
