# -*- coding: utf-8 -*-
from __future__ import annotations

from ...config import load_config
from ..models import CapabilityMount


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
        metadata.update(
            {
                "config_key": key,
                "install_command": str(getattr(package, "install_command", "") or ""),
                "execute_command": execute_command,
                "healthcheck_command": healthcheck_command,
                "execution_mode": str(
                    getattr(package, "execution_mode", "shell") or "shell"
                ),
                "source_url": str(getattr(package, "source_url", "") or ""),
            },
        )
        mounts.append(
            CapabilityMount(
                id=capability_id,
                name=str(getattr(package, "name", "") or capability_id),
                summary=str(
                    getattr(package, "summary", "")
                    or "External open-source capability"
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
                environment_requirements=list(
                    getattr(package, "environment_requirements", None)
                    or ["workspace", "process"]
                ),
                environment_description=(
                    "Requires the local runtime environment to host an external donor package."
                ),
                evidence_contract=list(
                    getattr(package, "evidence_contract", None) or ["shell-command"]
                ),
                evidence_description=(
                    "Records installation and runtime calls for the external donor package."
                ),
                role_access_policy=[],
                executor_ref=execute_command or healthcheck_command or capability_id,
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
