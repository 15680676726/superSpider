# -*- coding: utf-8 -*-
from __future__ import annotations

import inspect
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse

from ..config import get_available_channels
from ..config.config import (
    ConsoleConfig,
    DingTalkConfig,
    DiscordConfig,
    FeishuConfig,
    IMessageChannelConfig,
    MQTTConfig,
    QQConfig,
    TelegramConfig,
    VoiceChannelConfig,
)
from ..constant import WORKING_DIR
from ..kernel.runtime_outcome import (
    is_blocked_runtime_error,
    is_cancellation_runtime_error,
    is_timeout_runtime_error,
)


def _build_channel_config(channel_name: str, payload: object) -> object:
    available = get_available_channels()
    if channel_name not in available:
        raise KeyError(f"Channel '{channel_name}' not found")
    if not isinstance(payload, dict):
        raise ValueError("channel_config must be an object")

    config_builders = {
        "telegram": TelegramConfig,
        "dingtalk": DingTalkConfig,
        "discord": DiscordConfig,
        "feishu": FeishuConfig,
        "qq": QQConfig,
        "imessage": IMessageChannelConfig,
        "console": ConsoleConfig,
        "voice": VoiceChannelConfig,
        "mqtt": MQTTConfig,
    }
    model_cls = config_builders.get(channel_name)
    if model_cls is None:
        return dict(payload)
    return model_cls(**payload)


def _model_dump_payload(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return dict(value)
    return value


def _capability_name_from_id(capability_id: str, *, prefix: str) -> str:
    if capability_id.startswith(prefix):
        return capability_id[len(prefix) :]
    return capability_id


def _string_value(value: object | None) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _filter_executor_kwargs(executor, payload: dict[str, object]) -> dict[str, Any]:
    signature = inspect.signature(executor)
    filtered: dict[str, Any] = {}
    wants_payload = "payload" in signature.parameters
    accepts_var_kwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )
    for name, parameter in signature.parameters.items():
        if parameter.kind not in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            continue
        if name == "payload":
            continue
        if name not in payload:
            continue
        filtered[name] = payload[name]
    if accepts_var_kwargs:
        for name, value in payload.items():
            if name == "payload" or name in filtered:
                continue
            filtered[name] = value
    if wants_payload and "payload" not in filtered:
        filtered["payload"] = payload
    return filtered


def _tool_response_summary(response: object) -> str:
    payload = _tool_response_payload(response)
    if payload is not None:
        summary = payload.get("summary")
        if isinstance(summary, str) and summary:
            return summary
        error = payload.get("error")
        if isinstance(error, str) and error:
            return f"error: {error}"
        if payload.get("success") is False:
            return "error: execution failed"
    content = getattr(response, "content", None)
    if isinstance(content, list):
        lines: list[str] = []
        for item in content:
            text = getattr(item, "text", None)
            if text is None and isinstance(item, dict):
                text = item.get("text")
            if isinstance(text, str) and text:
                lines.append(text)
        if lines:
            return "\n".join(lines)
    text = getattr(response, "text", None)
    if isinstance(text, str) and text:
        return text
    return str(response)


def _tool_response_success(response: object) -> bool:
    payload = _tool_response_payload(response)
    if payload is not None and isinstance(payload.get("success"), bool):
        return bool(payload["success"])
    summary = _tool_response_summary(response)
    normalized = (summary or "").strip().lower()
    return not (
        normalized.startswith("error:")
        or normalized.startswith("error executing tool")
        or normalized.startswith("failed to execute tool")
        or normalized.startswith("traceback")
        or normalized.startswith("command failed with exit code")
        or is_cancellation_runtime_error(summary)
        or is_timeout_runtime_error(summary)
        or is_blocked_runtime_error(summary)
    )


def _tool_response_payload(response: object) -> dict[str, Any] | None:
    if isinstance(response, dict):
        return response
    content = getattr(response, "content", None)
    if not isinstance(content, list):
        return None
    chunks: list[str] = []
    for item in content:
        text = getattr(item, "text", None)
        if text is None and isinstance(item, dict):
            text = item.get("text")
        if isinstance(text, str) and text.strip():
            chunks.append(text)
    if not chunks:
        return None
    joined = "\n".join(chunks).strip()
    if not joined:
        return None
    try:
        payload = json.loads(joined)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _json_tool_response(payload: dict[str, Any]) -> ToolResponse:
    return ToolResponse(
        content=[
            TextBlock(
                type="text",
                text=json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            ),
        ],
        metadata={"format": "json"},
    )


def _json_safe(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def _resolve_skill_script_path(skill, script_path: str) -> Path | None:
    normalized = (script_path or "").replace("\\", "/").strip()
    if not normalized:
        return None
    if normalized.startswith("/"):
        return None
    normalized = normalized.lstrip("./")
    if not normalized.startswith("scripts/"):
        normalized = f"scripts/{normalized}"
    candidate = Path(skill.path) / normalized
    try:
        candidate = candidate.resolve()
    except RuntimeError:
        return None
    scripts_root = (Path(skill.path) / "scripts").resolve()
    try:
        candidate.relative_to(scripts_root)
    except ValueError:
        return None
    if not candidate.exists() or not candidate.is_file():
        return None
    return candidate


def _normalize_script_args(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    return [str(value)]


def _resolve_script_cwd(skill, script_path: Path, cwd: str | None) -> Path | None:
    if not cwd:
        return script_path.parent
    raw = Path(cwd)
    if not raw.is_absolute():
        raw = WORKING_DIR / raw
    try:
        return raw.resolve()
    except RuntimeError:
        return None


def _build_script_command(
    script_path: Path,
    *,
    args: list[str],
    interpreter: str | None,
) -> str | None:
    ext = script_path.suffix.lower()
    command_parts: list[str] = []
    if interpreter:
        command_parts.append(interpreter)
        command_parts.append(str(script_path))
    elif ext == ".py":
        command_parts.extend([sys.executable, str(script_path)])
    elif ext in {".sh", ".bash"}:
        command_parts.extend(["bash", str(script_path)])
    else:
        command_parts.append(str(script_path))
    command_parts.extend(args)
    if os.name == "nt":
        return subprocess.list2cmdline(command_parts)
    return " ".join(shlex.quote(part) for part in command_parts)
