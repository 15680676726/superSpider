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
    metadata: dict[str, Any]


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
            return f"{script} --version", f"{script} --version"
        return script, script
    python_exe = f'"{python_path}"'
    if capability_kind == "runtime-component":
        return (
            f"{python_exe} -m {entry_module}",
            f"{python_exe} -m {entry_module} --help",
        )
    if capability_kind == "project-package":
        return (
            f"{python_exe} -m {entry_module} --version",
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
        metadata={
            "entry_source": "console-script" if preferred_console_script else "module",
            "console_script": preferred_console_script,
            "script_path": script_path,
        },
    )
