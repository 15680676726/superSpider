# -*- coding: utf-8 -*-
"""Typed tool execution contracts for the unified capability front-door."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable, Literal

from ..agents.tools import (
    browser_use,
    desktop_screenshot,
    edit_file,
    execute_shell_command,
    get_current_time,
    read_file,
    send_file_to_user,
    write_file,
)
from .execution_support import _tool_response_payload, _tool_response_summary

ToolExecutor = Callable[..., Any]
ConcurrencyClass = Literal["parallel-read", "serial-write"]
ActionMode = Literal["read", "write"]


def _non_empty_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


@dataclass(frozen=True, slots=True)
class ToolExecutionContract:
    capability_id: str
    executor: ToolExecutor
    action_mode: ActionMode | None = None
    concurrency_class: ConcurrencyClass = "serial-write"
    preflight_policy: str | None = None
    required_keys: tuple[str, ...] = ()
    required_text_fields: tuple[str, ...] = ()
    allow_empty_text_fields: frozenset[str] = frozenset()
    result_normalizer: Callable[[object], object | None] | None = None
    action_mode_resolver: Callable[[dict[str, object]], ActionMode | None] | None = None
    concurrency_class_resolver: (
        Callable[[dict[str, object], ActionMode | None], ConcurrencyClass | None] | None
    ) = None

    def validate_payload(self, payload: dict[str, object]) -> str | None:
        missing: list[str] = []
        for key in self.required_keys:
            if key not in payload or payload.get(key) is None:
                missing.append(key)
        for key in self.required_text_fields:
            if key in self.allow_empty_text_fields and key in payload:
                continue
            if _non_empty_text(payload.get(key)) is None:
                missing.append(key)
        if not missing:
            return None
        unique_missing = ", ".join(dict.fromkeys(missing))
        return f"Missing required tool field(s): {unique_missing}"

    def normalize_output(self, response: object) -> object | None:
        if callable(self.result_normalizer):
            return self.result_normalizer(response)
        return _tool_response_payload(response)

    def resolve_action_mode(self, payload: dict[str, object]) -> ActionMode | None:
        if callable(self.action_mode_resolver):
            resolved = self.action_mode_resolver(payload)
            if resolved in {"read", "write"}:
                return resolved
        if self.action_mode in {"read", "write"}:
            return self.action_mode
        return None

    def resolve_concurrency_class(
        self,
        payload: dict[str, object],
        *,
        action_mode: ActionMode | None,
    ) -> ConcurrencyClass:
        if callable(self.concurrency_class_resolver):
            resolved = self.concurrency_class_resolver(payload, action_mode)
            if resolved in {"parallel-read", "serial-write"}:
                return resolved
        if action_mode == "read":
            return "parallel-read"
        if action_mode == "write":
            return "serial-write"
        return self.concurrency_class


def _normalize_shell_response(response: object) -> dict[str, object] | None:
    payload = _tool_response_payload(response)
    if isinstance(payload, dict):
        return payload
    summary = _tool_response_summary(response)
    if not isinstance(summary, str) or not summary.strip():
        return None
    text = summary.strip()
    lowered = text.lower()
    if lowered.startswith("blocked by shell safety policy"):
        return {
            "status": "blocked",
            "returncode": -1,
            "stdout": "",
            "stderr": text,
            "phase": "blocked",
        }
    if lowered.startswith("command failed with exit code "):
        match = re.match(r"Command failed with exit code (-?\d+)\.", text)
        returncode = int(match.group(1)) if match else -1
        stdout = ""
        stderr = ""
        if "\n[stdout]\n" in text:
            stdout = text.split("\n[stdout]\n", 1)[1].split("\n[stderr]\n", 1)[0]
        if "\n[stderr]\n" in text:
            stderr = text.split("\n[stderr]\n", 1)[1]
        payload = {
            "status": "error",
            "returncode": returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
        if "timeout" in lowered:
            payload["status"] = "timeout"
            payload["timed_out"] = True
        return payload
    return {
        "status": "success",
        "returncode": 0,
        "stdout": "" if text == "Command executed successfully (no output)." else text,
        "stderr": "",
    }


_READ_ONLY_SHELL_COMMANDS = frozenset(
    {
        "cat",
        "dir",
        "echo",
        "get-childitem",
        "get-content",
        "get-date",
        "get-item",
        "get-location",
        "ls",
        "pwd",
        "rg",
        "select-string",
        "test-path",
        "type",
        "where",
        "whoami",
    }
)
_READ_ONLY_GIT_SUBCOMMANDS = frozenset(
    {
        "branch",
        "diff",
        "log",
        "rev-parse",
        "show",
        "status",
    }
)


def _shell_tokens(command: str | None) -> list[str]:
    text = _non_empty_text(command)
    if text is None:
        return []
    return re.findall(r'"[^"]*"|\'[^\']*\'|\S+', text)


def _resolve_shell_action_mode(payload: dict[str, object]) -> ActionMode:
    tokens = _shell_tokens(payload.get("command"))
    if not tokens:
        return "write"
    first = tokens[0].strip("\"'").lower()
    if first in _READ_ONLY_SHELL_COMMANDS:
        return "read"
    if first == "git":
        second = tokens[1].strip("\"'").lower() if len(tokens) > 1 else ""
        if second in _READ_ONLY_GIT_SUBCOMMANDS:
            return "read"
    return "write"


def _resolve_shell_concurrency_class(
    payload: dict[str, object],
    action_mode: ActionMode | None,
) -> ConcurrencyClass:
    if action_mode == "read":
        return "parallel-read"
    return "serial-write"


TOOL_EXECUTION_CONTRACTS: dict[str, ToolExecutionContract] = {
    "tool:browser_use": ToolExecutionContract(
        capability_id="tool:browser_use",
        executor=browser_use,
        action_mode="write",
        concurrency_class="serial-write",
        preflight_policy="inline",
    ),
    "tool:desktop_screenshot": ToolExecutionContract(
        capability_id="tool:desktop_screenshot",
        executor=desktop_screenshot,
        action_mode="read",
        concurrency_class="parallel-read",
        preflight_policy="inline",
    ),
    "tool:edit_file": ToolExecutionContract(
        capability_id="tool:edit_file",
        executor=edit_file,
        action_mode="write",
        concurrency_class="serial-write",
        preflight_policy="inline",
        required_keys=("old_text", "new_text"),
        required_text_fields=("file_path",),
        allow_empty_text_fields=frozenset({"new_text"}),
    ),
    "tool:execute_shell_command": ToolExecutionContract(
        capability_id="tool:execute_shell_command",
        executor=execute_shell_command,
        action_mode="write",
        concurrency_class="serial-write",
        preflight_policy="shell-safety",
        required_text_fields=("command",),
        result_normalizer=_normalize_shell_response,
        action_mode_resolver=_resolve_shell_action_mode,
        concurrency_class_resolver=_resolve_shell_concurrency_class,
    ),
    "tool:get_current_time": ToolExecutionContract(
        capability_id="tool:get_current_time",
        executor=get_current_time,
        action_mode="read",
        concurrency_class="parallel-read",
        preflight_policy="inline",
    ),
    "tool:read_file": ToolExecutionContract(
        capability_id="tool:read_file",
        executor=read_file,
        action_mode="read",
        concurrency_class="parallel-read",
        preflight_policy="inline",
        required_text_fields=("file_path",),
    ),
    "tool:send_file_to_user": ToolExecutionContract(
        capability_id="tool:send_file_to_user",
        executor=send_file_to_user,
        action_mode="write",
        concurrency_class="serial-write",
        preflight_policy="inline",
        required_text_fields=("file_path",),
    ),
    "tool:write_file": ToolExecutionContract(
        capability_id="tool:write_file",
        executor=write_file,
        action_mode="write",
        concurrency_class="serial-write",
        preflight_policy="inline",
        required_keys=("content",),
        required_text_fields=("file_path",),
        allow_empty_text_fields=frozenset({"content"}),
    ),
}


def get_tool_execution_contract(capability_id: str) -> ToolExecutionContract | None:
    return TOOL_EXECUTION_CONTRACTS.get(capability_id)
