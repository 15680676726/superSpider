# -*- coding: utf-8 -*-
from __future__ import annotations

from ...config import load_config
from ..models import CapabilityMount


def _default_environment_requirements(package: object) -> list[str]:
    kind = str(getattr(package, "kind", "") or "").strip()
    if kind == "adapter":
        return ["workspace", "process", "desktop-session"]
    if kind == "runtime-component":
        return ["process", "network"]
    return ["workspace", "process"]


def _default_evidence_contract(package: object) -> list[str]:
    kind = str(getattr(package, "kind", "") or "").strip()
    if kind == "adapter":
        return ["shell-command", "runtime-event", "environment-session"]
    if kind == "runtime-component":
        return ["shell-command", "runtime-event"]
    return ["shell-command", "call-record"]


def _runtime_contract_projection(package: object) -> dict[str, object]:
    ready_probe_config = dict(getattr(package, "ready_probe_config", {}) or {})
    predicted_default_port = ready_probe_config.get("predicted_default_port")
    predicted_health_path = ready_probe_config.get("predicted_health_path")
    return {
        "runtime_kind": str(getattr(package, "runtime_kind", "") or "").strip() or None,
        "supported_actions": [
            str(item).strip()
            for item in list(getattr(package, "supported_actions", []) or [])
            if str(item).strip()
        ],
        "scope_policy": str(getattr(package, "scope_policy", "") or "").strip() or "session",
        "ready_probe_kind": str(getattr(package, "ready_probe_kind", "") or "").strip() or "none",
        "ready_probe_config": ready_probe_config,
        "stop_strategy": str(getattr(package, "stop_strategy", "") or "").strip() or "terminate",
        "startup_entry_ref": str(getattr(package, "startup_entry_ref", "") or "").strip() or None,
        "predicted_default_port": (
            int(predicted_default_port)
            if isinstance(predicted_default_port, int)
            else None
        ),
        "predicted_health_path": (
            str(predicted_health_path).strip()
            if str(predicted_health_path or "").strip()
            else None
        ),
    }


def _adapter_contract_projection(package: object) -> dict[str, object]:
    contract = dict(getattr(package, "adapter_contract", {}) or {})
    if not contract:
        return {}
    actions = contract.get("actions")
    if not isinstance(actions, list):
        contract["actions"] = []
    return contract


def list_external_package_capabilities() -> list[CapabilityMount]:
    config = load_config()
    mounts: list[CapabilityMount] = []
    packages = dict(getattr(config, "external_capability_packages", {}) or {})
    for key, package in packages.items():
        capability_id = str(getattr(package, "capability_id", "") or key).strip()
        if not capability_id:
            continue
        execute_command = str(getattr(package, "execute_command", "") or "").strip()
        healthcheck_command = str(
            getattr(package, "healthcheck_command", "") or ""
        ).strip()
        metadata = dict(getattr(package, "metadata", {}) or {})
        runtime_contract = _runtime_contract_projection(package)
        adapter_contract = _adapter_contract_projection(package)
        environment_requirements = list(
            getattr(package, "environment_requirements", None) or []
        )
        if not environment_requirements:
            environment_requirements = _default_environment_requirements(package)
        evidence_contract = list(getattr(package, "evidence_contract", None) or [])
        if not evidence_contract or (
            evidence_contract == ["shell-command"]
            and str(getattr(package, "kind", "") or "").strip()
            in {"adapter", "runtime-component"}
        ):
            evidence_contract = _default_evidence_contract(package)
        metadata.update(
            {
                "config_key": key,
                "install_command": str(getattr(package, "install_command", "") or ""),
                "execute_command": execute_command,
                "healthcheck_command": healthcheck_command,
                "environment_root": str(
                    getattr(package, "environment_root", "") or ""
                ),
                "python_path": str(getattr(package, "python_path", "") or ""),
                "scripts_dir": str(getattr(package, "scripts_dir", "") or ""),
                "execution_mode": str(
                    getattr(package, "execution_mode", "shell") or "shell"
                ),
                "source_url": str(getattr(package, "source_url", "") or ""),
                "intake_protocol_kind": str(
                    getattr(package, "intake_protocol_kind", "") or "unknown"
                ),
                "call_surface_ref": (
                    str(getattr(package, "call_surface_ref", "") or "").strip() or None
                ),
                "adapter_contract": adapter_contract,
                "runtime_contract": runtime_contract,
            },
        )
        executor_ref = execute_command or healthcheck_command or capability_id
        if (
            str(getattr(package, "kind", "") or "").strip() == "adapter"
            and adapter_contract
        ):
            executor_ref = "external-adapter"
        mounts.append(
            CapabilityMount(
                id=capability_id,
                name=str(getattr(package, "name", "") or capability_id),
                summary=(
                    "Governed external adapter compiled into formal CoPaw business actions."
                    if str(getattr(package, "kind", "") or "").strip() == "adapter"
                    and adapter_contract
                    else str(
                        getattr(package, "summary", "")
                        or "External open-source capability"
                    )
                ),
                kind=str(
                    getattr(package, "kind", "project-package")
                    or "project-package"
                ),
                source_kind=str(
                    getattr(package, "source_kind", "project") or "project"
                ),
                risk_level="guarded",
                risk_description=(
                    "External open-source donor package executes through a governed shell contract."
                ),
                environment_requirements=environment_requirements,
                environment_description=(
                    "Requires the local runtime environment to host an external donor package."
                ),
                evidence_contract=evidence_contract,
                evidence_description=(
                    "Records installation and runtime calls for the external donor package."
                ),
                role_access_policy=[],
                executor_ref=executor_ref,
                provider_ref=str(getattr(package, "provider_ref", "github") or "github"),
                timeout_policy="external-package",
                package_ref=str(getattr(package, "package_ref", "") or None) or None,
                package_kind=str(getattr(package, "package_kind", "") or None) or None,
                package_version=(
                    str(getattr(package, "package_version", "") or None) or None
                ),
                replay_support=False,
                enabled=bool(getattr(package, "enabled", True)),
                tags=[
                    "external-donor",
                    str(
                        getattr(package, "kind", "project-package")
                        or "project-package"
                    ),
                ],
                metadata=metadata,
            ),
        )
    mounts.sort(key=lambda item: item.id)
    return mounts
