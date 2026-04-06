# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any
from urllib.parse import urlparse

from .external_adapter_contracts import (
    donor_execution_contract_metadata,
    donor_execution_envelope_metadata,
    host_compatibility_requirements_metadata,
    normalize_provider_injection_mode,
)


def _normalize_name(value: object | None) -> str:
    return str(value or "").strip().replace("-", "_").lower()


@dataclass(frozen=True, slots=True)
class GitHubPythonProjectTransport:
    kind: str
    package_ref: str


@dataclass(frozen=True, slots=True)
class PipRequestedDistribution:
    distribution_name: str
    distribution_version: str
    download_url: str = ""


@dataclass(frozen=True, slots=True)
class InstalledPythonProjectContract:
    install_name: str
    distribution_name: str
    package_version: str
    entry_module: str
    console_script: str | None
    execute_command: str
    healthcheck_command: str
    runtime_kind: str
    supported_actions: list[str]
    scope_policy: str
    ready_probe_kind: str
    ready_probe_config: dict[str, Any]
    stop_strategy: str
    startup_entry_ref: str
    environment_requirements: list[str]
    evidence_contract: list[str]
    predicted_default_port: int | None
    predicted_health_path: str | None
    provider_injection_mode: str
    execution_envelope: dict[str, Any]
    host_compatibility_requirements: dict[str, Any]
    metadata: dict[str, Any]


_DISCOVERY_JSON_BEGIN = "__COPAW_DISCOVERY_JSON_BEGIN__"
_DISCOVERY_JSON_END = "__COPAW_DISCOVERY_JSON_END__"

_MCP_ACTION_DISCOVERY_SCRIPT = """
import asyncio
import json
import sys

from copaw.app.mcp.manager import MCPClientManager
from copaw.config.config import MCPClientConfig

BEGIN = "__COPAW_DISCOVERY_JSON_BEGIN__"
END = "__COPAW_DISCOVERY_JSON_END__"


def _tool_entries(payload):
    if isinstance(payload, list):
        return list(payload)
    if isinstance(payload, dict):
        return list(payload.get("tools") or [])
    return list(getattr(payload, "tools", []) or [])


def _schema(value):
    return value if isinstance(value, dict) else {}


async def main():
    command = sys.argv[1]
    args = json.loads(sys.argv[2])
    cwd = sys.argv[3]
    manager = MCPClientManager()
    actions = []
    try:
        client_config = MCPClientConfig(
            name="donor-mcp-discovery",
            command=command,
            args=list(args or []),
            cwd=cwd or "",
        )
        await manager.replace_client("donor-mcp-discovery", client_config, timeout=30.0)
        client = await manager.get_client("donor-mcp-discovery")
        if client is not None and callable(getattr(client, "list_tools", None)):
            response = await client.list_tools()
            for item in _tool_entries(response):
                if isinstance(item, dict):
                    name = str(item.get("name") or item.get("tool_name") or "").strip()
                    description = str(item.get("description") or "").strip()
                    input_schema = item.get("inputSchema") or item.get("input_schema") or item.get("parameters")
                    output_schema = item.get("outputSchema") or item.get("output_schema")
                else:
                    name = str(getattr(item, "name", "") or getattr(item, "tool_name", "") or "").strip()
                    description = str(getattr(item, "description", "") or "").strip()
                    input_schema = (
                        getattr(item, "inputSchema", None)
                        or getattr(item, "input_schema", None)
                        or getattr(item, "parameters", None)
                    )
                    output_schema = (
                        getattr(item, "outputSchema", None)
                        or getattr(item, "output_schema", None)
                    )
                if not name:
                    continue
                actions.append(
                    {
                        "action_id": name,
                        "tool_name": name,
                        "summary": description,
                        "input_schema": _schema(input_schema),
                        "output_schema": _schema(output_schema),
                    }
                )
    except Exception:
        actions = []
    finally:
        try:
            await manager.close_all()
        except Exception:
            pass
    print(BEGIN)
    print(json.dumps({"actions": actions}, ensure_ascii=False))
    print(END)


asyncio.run(main())
"""

_SDK_ACTION_DISCOVERY_SCRIPT = """
import importlib
import inspect
import json
import sys

BEGIN = "__COPAW_DISCOVERY_JSON_BEGIN__"
END = "__COPAW_DISCOVERY_JSON_END__"


def _optional_constructor(cls):
    try:
        signature = inspect.signature(cls)
    except Exception:
        return False
    for parameter in signature.parameters.values():
        if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            continue
        if parameter.default is inspect._empty:
            return False
    return True


def _schema_type(annotation):
    text = str(annotation or "").lower()
    if "int" in text:
        return "integer"
    if "float" in text:
        return "number"
    if "bool" in text:
        return "boolean"
    if "dict" in text:
        return "object"
    if "list" in text or "tuple" in text or "set" in text:
        return "array"
    return "string"


def _signature_schema(signature, *, drop_first=False):
    properties = {}
    required = []
    parameters = list(signature.parameters.values())
    if drop_first and parameters:
        parameters = parameters[1:]
    for parameter in parameters:
        if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            continue
        properties[parameter.name] = {"type": _schema_type(parameter.annotation)}
        if parameter.default is inspect._empty:
            required.append(parameter.name)
    payload = {"type": "object", "properties": properties}
    if required:
        payload["required"] = required
    return payload


def _summary(obj):
    doc = inspect.getdoc(obj) or ""
    return doc.splitlines()[0].strip() if doc else ""


def _action(action_id, callable_ref, obj, *, drop_first=False):
    return {
        "action_id": action_id,
        "callable_name": action_id,
        "callable_ref": callable_ref,
        "summary": _summary(obj),
        "input_schema": _signature_schema(inspect.signature(obj), drop_first=drop_first),
        "output_schema": {},
    }


module_ref = sys.argv[1]
module_name = module_ref[len("module:") :] if module_ref.startswith("module:") else module_ref
module = importlib.import_module(module_name)
actions = []

for name, value in inspect.getmembers(module, inspect.isfunction):
    if name.startswith("_") or getattr(value, "__module__", "") != module.__name__:
        continue
    actions.append(_action(name, f"module:{module_name}:{name}", value))

for class_name, cls in inspect.getmembers(module, inspect.isclass):
    if class_name.startswith("_") or getattr(cls, "__module__", "") != module.__name__:
        continue
    if not _optional_constructor(cls):
        continue
    for method_name, method in inspect.getmembers(cls, inspect.isfunction):
        if method_name.startswith("_"):
            continue
        action_id = f"{class_name}.{method_name}"
        callable_ref = f"module:{module_name}:{class_name}.{method_name}"
        actions.append(_action(action_id, callable_ref, method, drop_first=True))

print(BEGIN)
print(json.dumps({"actions": actions}, ensure_ascii=False))
print(END)
"""


def _github_owner_repo(source_url: str) -> tuple[str, str]:
    parsed = urlparse(str(source_url or "").strip())
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise ValueError("GitHub source_url must point to an owner/repository")
    return parts[0], parts[1]


def build_github_python_project_transport_chain(
    *,
    source_url: str,
    ref: str,
) -> tuple[GitHubPythonProjectTransport, ...]:
    owner, repo = _github_owner_repo(source_url)
    normalized_ref = str(ref or "").strip() or "main"
    return (
        GitHubPythonProjectTransport(
            kind="git",
            package_ref=f"git+https://github.com/{owner}/{repo}.git@{normalized_ref}",
        ),
        GitHubPythonProjectTransport(
            kind="codeload-tar-gz",
            package_ref=(
                f"https://codeload.github.com/{owner}/{repo}/tar.gz/refs/heads/{normalized_ref}"
            ),
        ),
        GitHubPythonProjectTransport(
            kind="github-archive-zip",
            package_ref=(
                f"https://github.com/{owner}/{repo}/archive/refs/heads/{normalized_ref}.zip"
            ),
        ),
    )


def parse_pip_install_report_requested_distribution(
    payload: dict[str, Any] | None,
) -> PipRequestedDistribution | None:
    for item in list((payload or {}).get("install") or []):
        if not isinstance(item, dict) or not item.get("requested"):
            continue
        metadata = item.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        distribution_name = str(metadata.get("name") or "").strip()
        if not distribution_name:
            continue
        distribution_version = str(metadata.get("version") or "").strip()
        download_info = item.get("download_info") or {}
        if not isinstance(download_info, dict):
            download_info = {}
        return PipRequestedDistribution(
            distribution_name=distribution_name,
            distribution_version=distribution_version,
            download_url=str(download_info.get("url") or "").strip(),
        )
    return None


def _entry_module_from_target(target: str) -> str:
    module_path = str(target or "").split(":", 1)[0].strip()
    if module_path.endswith(".__main__"):
        module_path = module_path[: -len(".__main__")]
    if module_path:
        return module_path
    return "external_capability"


def _resolve_console_script_path(script_name: str, *, scripts_dir: str) -> str | None:
    normalized = str(script_name or "").strip()
    if not normalized:
        return None
    base_dir = Path(str(scripts_dir or "").strip())
    if not str(base_dir):
        return None
    suffixes = [".exe", "-script.py", ".cmd", ".bat", ""]
    for suffix in suffixes:
        candidate = base_dir / f"{normalized}{suffix}"
        if candidate.exists():
            return str(candidate)
    return None


def _service_entrypoint_score(
    entry_point: dict[str, Any],
    *,
    normalized_distribution: str,
) -> int:
    name = _normalize_name(entry_point.get("name"))
    target_module = _normalize_name(
        _entry_module_from_target(str(entry_point.get("value") or "")),
    )
    if not name:
        return -10_000
    score = 0
    if normalized_distribution and name == normalized_distribution:
        score += 10
    if "dashboard" in name or "dashboard" in target_module:
        score += 500
    if "server" in name or "server" in target_module:
        score += 400
    if "api" in name or "api" in target_module:
        score += 250
    if "daemon" in name or "daemon" in target_module:
        score += 150
    if "web" in name or "web" in target_module:
        score += 100
    if "mcp" in name or "mcp" in target_module:
        score -= 600
    if any(token in name for token in ("upload", "download", "skill")):
        score -= 300
    return score


def _shell_command_for_capability(
    *,
    capability_kind: str,
    script_path: str | None,
    entry_module: str,
    python_path: str,
) -> tuple[str, str]:
    if script_path:
        script = f'"{script_path}"'
        if capability_kind == "runtime-component":
            return script, f"{script} --help"
        if capability_kind == "project-package":
            return script, f"{script} --version"
        return script, script
    python_exe = f'"{python_path}"'
    if capability_kind == "runtime-component":
        return (
            f"{python_exe} -m {entry_module}",
            f"{python_exe} -m {entry_module} --help",
        )
    if capability_kind == "project-package":
        return (
            f"{python_exe} -m {entry_module}",
            f"{python_exe} -m {entry_module} --version",
        )
    return (
        f'{python_exe} -c "import {entry_module}; print(getattr({entry_module}, \'__name__\', \'{entry_module}\'))"',
        f'{python_exe} -c "import {entry_module}; print(getattr({entry_module}, \'__name__\', \'{entry_module}\'))"',
    )


def _default_scope_policy(capability_kind: str) -> str:
    if capability_kind == "adapter":
        return "seat"
    return "session"


def _default_runtime_kind(capability_kind: str) -> str:
    return "service" if capability_kind == "runtime-component" else "cli"


def _default_supported_actions(runtime_kind: str) -> list[str]:
    if runtime_kind == "service":
        return ["describe", "start", "healthcheck", "stop", "restart"]
    return ["describe", "run"]


def _default_environment_requirements(capability_kind: str) -> list[str]:
    if capability_kind == "adapter":
        return ["workspace", "process", "desktop-session"]
    if capability_kind == "runtime-component":
        return ["process", "network"]
    return ["workspace", "process"]


def _default_evidence_contract(capability_kind: str) -> list[str]:
    if capability_kind == "adapter":
        return ["shell-command", "runtime-event", "environment-session"]
    if capability_kind == "runtime-component":
        return ["shell-command", "runtime-event"]
    return ["shell-command", "call-record"]


def _default_provider_injection_mode() -> str:
    return normalize_provider_injection_mode("environment") or "environment"


def _default_execution_envelope(
    *,
    runtime_kind: str,
    ready_probe_kind: str,
) -> dict[str, Any]:
    return donor_execution_envelope_metadata(
        {
            "startup_timeout_sec": 90 if runtime_kind == "service" else 30,
            "action_timeout_sec": 180 if runtime_kind == "service" else 120,
            "idle_timeout_sec": 45 if runtime_kind == "service" else 30,
            "heartbeat_interval_sec": 15 if runtime_kind == "service" else 10,
            "cancel_grace_sec": 10 if runtime_kind == "service" else 5,
            "kill_grace_sec": 3,
            "max_retries": 1 if runtime_kind == "service" else 0,
            "retry_backoff_policy": "exponential"
            if runtime_kind == "service"
            else "none",
            "output_size_limit": 65_536,
            "probe_kind": ready_probe_kind or "none",
            "probe_timeout_sec": 15 if ready_probe_kind == "http" else 10,
        },
    )


def _default_host_compatibility_requirements(
    *,
    environment_requirements: list[str],
    ready_probe_kind: str,
) -> dict[str, Any]:
    required_surfaces = sorted(
        {
            str(item).strip()
            for item in environment_requirements
            if str(item).strip()
        },
    )
    if ready_probe_kind == "http":
        required_surfaces = sorted({*required_surfaces, "network"})
    return host_compatibility_requirements_metadata(
        {
            "supported_os": ["windows", "linux", "darwin"],
            "supported_architectures": ["x86_64", "amd64", "arm64"],
            "required_runtimes": ["python"],
            "package_manager": "pip",
            "required_provider_contract_kind": "cooperative_provider_runtime",
            "required_surfaces": required_surfaces,
            "required_env_keys": [],
            "config_location_expectations": [],
            "workspace_policy": (
                "package-environment-root"
                if "workspace" in required_surfaces
                else "isolated-runtime-root"
            ),
            "startup_expectations": [
                "startup_entry_ref",
                f"readiness_probe:{ready_probe_kind or 'none'}",
            ],
        },
    )


def _callable_surface_hints(
    *,
    capability_kind: str,
    console_entry_points: list[dict[str, Any]],
    resolved_entry_module: str,
) -> dict[str, Any]:
    hints: dict[str, Any] = {}
    mcp_entry = next(
        (
            entry_point
            for entry_point in console_entry_points
            if "mcp" in _normalize_name(entry_point.get("name"))
            or "mcp" in _normalize_name(entry_point.get("value"))
        ),
        None,
    )
    if mcp_entry is not None:
        mcp_name = str(mcp_entry.get("name") or "").strip()
        if mcp_name:
            hints["mcp_server_ref"] = f"script:{mcp_name}"
    if capability_kind == "adapter" and resolved_entry_module:
        hints.setdefault("sdk_entry_ref", f"module:{resolved_entry_module}")
    return hints


def project_installed_python_project_package_metadata(
    contract: InstalledPythonProjectContract,
) -> dict[str, Any]:
    return {
        **dict(contract.metadata or {}),
        **donor_execution_contract_metadata(
            {
                "provider_injection_mode": contract.provider_injection_mode,
                "execution_envelope": contract.execution_envelope,
                "host_compatibility_requirements": (
                    contract.host_compatibility_requirements
                ),
            },
        ),
    }


def _repo_src_path() -> str:
    return str(Path(__file__).resolve().parents[2])


def _discovery_subprocess_env() -> dict[str, str]:
    env = dict(os.environ)
    src_path = _repo_src_path()
    existing = str(env.get("PYTHONPATH") or "").strip()
    env["PYTHONPATH"] = (
        src_path if not existing else os.pathsep.join((src_path, existing))
    )
    return env


def _extract_marked_json_payload(stdout: str) -> object | None:
    text = str(stdout or "")
    start = text.rfind(_DISCOVERY_JSON_BEGIN)
    end = text.rfind(_DISCOVERY_JSON_END)
    if start < 0 or end < 0 or end <= start:
        return None
    payload = text[start + len(_DISCOVERY_JSON_BEGIN) : end].strip()
    if not payload:
        return None
    return json.loads(payload)


def _run_json_probe(
    command: list[str],
    *,
    timeout: int,
    env: dict[str, str] | None = None,
) -> object | None:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        env=env,
    )
    payload = _extract_marked_json_payload(completed.stdout or "")
    if payload is not None:
        return payload
    if completed.returncode != 0:
        return None
    return None


def _action_list(payload: object | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    actions = payload.get("actions")
    if not isinstance(actions, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in actions:
        if isinstance(item, dict):
            normalized.append(dict(item))
    return normalized


def _resolve_stdio_probe_command(
    *,
    call_surface_ref: str,
    scripts_dir: str,
    python_path: str,
) -> tuple[str, list[str], str] | None:
    normalized = str(call_surface_ref or "").strip()
    if not normalized:
        return None
    cwd = str(Path(scripts_dir).parent) if str(scripts_dir or "").strip() else ""
    if normalized.startswith("script:"):
        script_name = normalized.split(":", 1)[1].strip()
        script_path = _resolve_console_script_path(script_name, scripts_dir=scripts_dir)
        if script_path is None:
            return None
        return script_path, [], cwd
    if normalized.startswith("module:"):
        module_name = normalized.split(":", 1)[1].strip()
        if not module_name or not str(python_path or "").strip():
            return None
        return python_path, ["-m", module_name], cwd
    return None


def _discover_mcp_tool_actions(
    *,
    call_surface_ref: str,
    python_path: str,
    scripts_dir: str,
    timeout: int = 45,
) -> list[dict[str, Any]]:
    probe = _resolve_stdio_probe_command(
        call_surface_ref=call_surface_ref,
        scripts_dir=scripts_dir,
        python_path=python_path,
    )
    if probe is None:
        return []
    command, args, cwd = probe
    payload = _run_json_probe(
        [
            sys.executable,
            "-c",
            _MCP_ACTION_DISCOVERY_SCRIPT,
            command,
            json.dumps(args, ensure_ascii=False),
            cwd,
        ],
        timeout=timeout,
        env=_discovery_subprocess_env(),
    )
    return _action_list(payload)


def _discover_sdk_actions(
    *,
    sdk_entry_ref: str,
    python_path: str,
    timeout: int = 45,
) -> list[dict[str, Any]]:
    if not str(sdk_entry_ref or "").strip() or not str(python_path or "").strip():
        return []
    payload = _run_json_probe(
        [
            python_path,
            "-c",
            _SDK_ACTION_DISCOVERY_SCRIPT,
            sdk_entry_ref,
        ],
        timeout=timeout,
    )
    return _action_list(payload)


def discover_installed_python_callable_actions(
    *,
    metadata: dict[str, Any] | None,
    python_path: str,
    scripts_dir: str,
) -> dict[str, Any]:
    payload = dict(metadata or {})
    mcp_server_ref = str(payload.get("mcp_server_ref") or "").strip()
    existing_mcp_tools = _action_list({"actions": payload.get("mcp_tools")})
    if mcp_server_ref and not existing_mcp_tools:
        discovered_mcp_tools = _discover_mcp_tool_actions(
            call_surface_ref=mcp_server_ref,
            python_path=python_path,
            scripts_dir=scripts_dir,
        )
        if discovered_mcp_tools:
            payload["mcp_tools"] = discovered_mcp_tools
    sdk_entry_ref = str(payload.get("sdk_entry_ref") or "").strip()
    existing_sdk_actions = _action_list({"actions": payload.get("sdk_actions")})
    if sdk_entry_ref and not existing_sdk_actions:
        discovered_sdk_actions = _discover_sdk_actions(
            sdk_entry_ref=sdk_entry_ref,
            python_path=python_path,
        )
        if discovered_sdk_actions:
            payload["sdk_actions"] = discovered_sdk_actions
    return payload


def _predict_service_probe(
    *,
    distribution_name: str,
    entry_module: str,
    console_script: str | None = None,
) -> tuple[int | None, str | None]:
    normalized = " ".join(
        filter(
            None,
            (
                _normalize_name(distribution_name),
                _normalize_name(entry_module),
                _normalize_name(console_script),
            ),
        ),
    )
    if "openspace_dashboard" in normalized:
        return 7788, "/health"
    if "openspace_server" in normalized or "local_server" in normalized:
        return 5000, "/health"
    if "openspace" in normalized:
        return 7788, "/health"
    if "flask" in normalized:
        return 5000, "/"
    if "fastapi" in normalized or "uvicorn" in normalized:
        return 8000, "/health"
    return None, None


def inspect_installed_python_distribution(
    *,
    python_path: str,
    distribution_name: str,
    timeout: int = 120,
) -> dict[str, Any]:
    script = (
        "import importlib.metadata as metadata, json, sys\n"
        "dist = metadata.distribution(sys.argv[1])\n"
        "payload = {\n"
        "  'distribution_name': str(dist.metadata.get('Name') or sys.argv[1]),\n"
        "  'package_version': str(getattr(dist, 'version', '') or ''),\n"
        "  'entry_points': [\n"
        "    {\n"
        "      'group': str(getattr(ep, 'group', '') or ''),\n"
        "      'name': str(getattr(ep, 'name', '') or ''),\n"
        "      'value': str(getattr(ep, 'value', '') or ''),\n"
        "    }\n"
        "    for ep in list(getattr(dist, 'entry_points', []) or [])\n"
        "  ],\n"
        "}\n"
        "print(json.dumps(payload, ensure_ascii=False))\n"
    )
    completed = subprocess.run(
        [python_path, "-c", script, distribution_name],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        error_output = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(
            error_output
            or f"Failed to inspect installed distribution '{distribution_name}'",
        )
    payload = json.loads((completed.stdout or "").strip() or "{}")
    return payload if isinstance(payload, dict) else {}


def resolve_installed_python_project_contract(
    *,
    python_path: str,
    scripts_dir: str,
    distribution_name: str,
    capability_kind: str,
    entry_module: str | None = None,
) -> InstalledPythonProjectContract:
    distribution = inspect_installed_python_distribution(
        python_path=python_path,
        distribution_name=distribution_name,
    )
    console_entry_points = [
        entry_point
        for entry_point in list(distribution.get("entry_points") or [])
        if str(entry_point.get("group") or "").strip() == "console_scripts"
    ]
    resolved_distribution_name = str(
        distribution.get("distribution_name") or distribution_name,
    ).strip() or distribution_name
    resolved_package_version = str(distribution.get("package_version") or "").strip()
    normalized_distribution = _normalize_name(resolved_distribution_name)
    preferred_entry_module = str(entry_module or "").strip()
    preferred_console_script = None
    chosen_entry_point = None
    if preferred_entry_module:
        normalized_entry = _normalize_name(preferred_entry_module)
        for entry_point in console_entry_points:
            if _normalize_name(entry_point.get("name", "")) == normalized_entry:
                chosen_entry_point = entry_point
                break
    if chosen_entry_point is None and capability_kind == "runtime-component":
        service_candidates = sorted(
            console_entry_points,
            key=lambda entry_point: _service_entrypoint_score(
                entry_point,
                normalized_distribution=normalized_distribution,
            ),
            reverse=True,
        )
        if service_candidates:
            best_candidate = service_candidates[0]
            if (
                _service_entrypoint_score(
                    best_candidate,
                    normalized_distribution=normalized_distribution,
                )
                > 0
            ):
                chosen_entry_point = best_candidate
    if chosen_entry_point is None:
        for entry_point in console_entry_points:
            if _normalize_name(entry_point.get("name", "")) == normalized_distribution:
                chosen_entry_point = entry_point
                break
    if chosen_entry_point is None and console_entry_points:
        chosen_entry_point = console_entry_points[0]
    if chosen_entry_point is not None:
        preferred_console_script = (
            str(chosen_entry_point.get("name", "") or "").strip() or None
        )
    resolved_entry_module = preferred_entry_module
    if not resolved_entry_module and chosen_entry_point is not None:
        resolved_entry_module = _entry_module_from_target(
            str(chosen_entry_point.get("value", "") or ""),
        )
    if not resolved_entry_module:
        resolved_entry_module = normalized_distribution or "external_capability"
    script_path = (
        _resolve_console_script_path(
            preferred_console_script,
            scripts_dir=scripts_dir,
        )
        if preferred_console_script is not None
        else None
    )
    execute_command, healthcheck_command = _shell_command_for_capability(
        capability_kind=capability_kind,
        script_path=script_path,
        entry_module=resolved_entry_module,
        python_path=python_path,
    )
    runtime_kind = _default_runtime_kind(capability_kind)
    supported_actions = _default_supported_actions(runtime_kind)
    predicted_default_port, predicted_health_path = _predict_service_probe(
        distribution_name=resolved_distribution_name,
        entry_module=resolved_entry_module,
        console_script=preferred_console_script,
    )
    ready_probe_kind = "none"
    if runtime_kind == "service":
        ready_probe_kind = (
            "http"
            if isinstance(predicted_default_port, int) and predicted_health_path
            else "command"
        )
    ready_probe_config = {
        "command": healthcheck_command if ready_probe_kind == "command" else "",
        "predicted_default_port": predicted_default_port,
        "predicted_health_path": predicted_health_path,
    }
    if ready_probe_kind == "http" and isinstance(predicted_default_port, int):
        ready_probe_config["url"] = (
            f"http://127.0.0.1:{predicted_default_port}{predicted_health_path}"
        )
    startup_entry_ref = (
        f"script:{preferred_console_script}"
        if preferred_console_script
        else f"module:{resolved_entry_module}"
    )
    provider_injection_mode = _default_provider_injection_mode()
    execution_envelope = _default_execution_envelope(
        runtime_kind=runtime_kind,
        ready_probe_kind=ready_probe_kind,
    )
    host_compatibility_requirements = _default_host_compatibility_requirements(
        environment_requirements=_default_environment_requirements(capability_kind),
        ready_probe_kind=ready_probe_kind,
    )
    install_name = (
        normalized_distribution
        or _normalize_name(resolved_entry_module)
        or preferred_console_script
        or "external_capability"
    )
    return InstalledPythonProjectContract(
        install_name=install_name,
        distribution_name=resolved_distribution_name,
        package_version=resolved_package_version,
        entry_module=resolved_entry_module,
        console_script=preferred_console_script,
        execute_command=execute_command,
        healthcheck_command=healthcheck_command,
        runtime_kind=runtime_kind,
        supported_actions=supported_actions,
        scope_policy=_default_scope_policy(capability_kind),
        ready_probe_kind=ready_probe_kind,
        ready_probe_config=ready_probe_config,
        stop_strategy="terminate",
        startup_entry_ref=startup_entry_ref,
        environment_requirements=_default_environment_requirements(capability_kind),
        evidence_contract=_default_evidence_contract(capability_kind),
        predicted_default_port=predicted_default_port,
        predicted_health_path=predicted_health_path,
        provider_injection_mode=provider_injection_mode,
        execution_envelope=execution_envelope,
        host_compatibility_requirements=host_compatibility_requirements,
        metadata={
            "entry_source": "console-script" if preferred_console_script else "module",
            "console_script": preferred_console_script,
            "script_path": script_path,
            **_callable_surface_hints(
                capability_kind=capability_kind,
                console_entry_points=console_entry_points,
                resolved_entry_module=resolved_entry_module,
            ),
            **donor_execution_contract_metadata(
                {
                    "provider_injection_mode": provider_injection_mode,
                    "execution_envelope": execution_envelope,
                    "host_compatibility_requirements": (
                        host_compatibility_requirements
                    ),
                },
            ),
        },
    )
