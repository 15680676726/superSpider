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
            return f"{script} --help", f"{script} --help"
        if capability_kind == "project-package":
            return f"{script} --version", f"{script} --version"
        return script, script
    python_exe = f'"{python_path}"'
    if capability_kind == "runtime-component":
        return (
            f"{python_exe} -m {entry_module} --help",
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
    install_name = (
        preferred_console_script
        or normalized_distribution
        or _normalize_name(resolved_entry_module)
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
        metadata={
            "entry_source": "console-script" if preferred_console_script else "module",
            "console_script": preferred_console_script,
            "script_path": script_path,
        },
    )
