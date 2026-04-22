# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

from ..__version__ import __version__
from ..state.executor_runtime_service import ExecutorRuntimeService
from ..state.models_executor_runtime import (
    ExecutorSidecarInstallRecord,
    ExecutorSidecarReleaseRecord,
)


def _text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: object | None) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [item for item in (_text(item) for item in value) if item is not None]
    text = _text(value)
    return [text] if text is not None else []


def _parse_version(value: str | None) -> Version | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return Version(text)
    except InvalidVersion:
        return None


def _matches_range(version_text: str | None, specifier_text: str | None) -> bool:
    version = _parse_version(version_text)
    specifier = _text(specifier_text)
    if version is None or specifier is None:
        return False
    return version in SpecifierSet(specifier)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SidecarReleaseService:
    def __init__(
        self,
        *,
        executor_runtime_service: ExecutorRuntimeService,
        copaw_version: str | None = None,
    ) -> None:
        self._executor_runtime_service = executor_runtime_service
        self._copaw_version = _text(copaw_version) or __version__

    def describe_version_governance(
        self,
        *,
        runtime_family: str,
        channel: str | None = None,
    ) -> dict[str, Any]:
        current_install = self._executor_runtime_service.get_active_sidecar_install(
            runtime_family=runtime_family,
            channel=channel,
        )
        compatibility = self.evaluate_install_compatibility(
            runtime_family=runtime_family,
            channel=channel,
            install=current_install,
        )
        available_upgrade = self.find_available_upgrade(
            runtime_family=runtime_family,
            channel=channel,
        )
        return {
            "current_install": self._serialize_install(current_install),
            "compatibility": compatibility,
            "available_upgrade": self._serialize_release(available_upgrade),
        }

    def evaluate_install_compatibility(
        self,
        *,
        runtime_family: str,
        channel: str | None = None,
        install: ExecutorSidecarInstallRecord | None = None,
    ) -> dict[str, Any]:
        current_install = install or self._executor_runtime_service.get_active_sidecar_install(
            runtime_family=runtime_family,
            channel=channel,
        )
        policy = self._executor_runtime_service.resolve_sidecar_compatibility_policy(
            runtime_family=runtime_family,
            channel=channel,
        )
        if current_install is None:
            return {
                "status": "missing-install",
                "fail_closed": False,
                "blockers": [],
                "current_version": None,
                "supported_version_range": _text(getattr(policy, "supported_version_range", None)),
                "required_copaw_version_range": _text(
                    getattr(policy, "required_copaw_version_range", None),
                ),
            }
        if policy is None:
            return {
                "status": "missing-policy",
                "fail_closed": True,
                "blockers": ["No active sidecar compatibility policy is configured."],
                "current_version": current_install.version,
                "supported_version_range": None,
                "required_copaw_version_range": None,
            }
        blockers: list[str] = []
        if not _matches_range(current_install.version, policy.supported_version_range):
            blockers.append(
                "Installed sidecar version "
                f"{current_install.version} is outside supported range "
                f"{policy.supported_version_range}."
            )
        required_copaw_range = _text(policy.required_copaw_version_range)
        if required_copaw_range is not None and not _matches_range(
            self._copaw_version,
            required_copaw_range,
        ):
            blockers.append(
                f"CoPaw version {self._copaw_version} is outside required range "
                f"{required_copaw_range}."
            )
        required_features = _string_list(policy.metadata.get("required_protocol_features"))
        installed_features = _string_list(current_install.metadata.get("protocol_features"))
        missing_features = [item for item in required_features if item not in installed_features]
        if missing_features:
            blockers.append(
                "Installed sidecar is missing required protocol features: "
                + ", ".join(missing_features)
                + "."
            )
        return {
            "status": "compatible" if not blockers else "incompatible",
            "fail_closed": bool(policy.metadata.get("fail_closed", True)),
            "blockers": blockers,
            "current_version": current_install.version,
            "supported_version_range": policy.supported_version_range,
            "required_copaw_version_range": required_copaw_range,
            "required_protocol_features": required_features,
        }

    def find_available_upgrade(
        self,
        *,
        runtime_family: str,
        channel: str | None = None,
    ) -> ExecutorSidecarReleaseRecord | None:
        current_install = self._executor_runtime_service.get_active_sidecar_install(
            runtime_family=runtime_family,
            channel=channel,
        )
        current_version = _parse_version(getattr(current_install, "version", None))
        policy = self._executor_runtime_service.resolve_sidecar_compatibility_policy(
            runtime_family=runtime_family,
            channel=channel,
        )
        releases = self._executor_runtime_service.list_sidecar_releases(
            runtime_family=runtime_family,
            channel=channel,
            status="published",
        )
        compatible_releases: list[ExecutorSidecarReleaseRecord] = []
        for release in releases:
            release_version = _parse_version(release.version)
            if release_version is None:
                continue
            if current_version is not None and release_version <= current_version:
                continue
            if policy is not None and not _matches_range(
                release.version,
                policy.supported_version_range,
            ):
                continue
            compatible_releases.append(release)
        compatible_releases.sort(
            key=lambda item: _parse_version(item.version) or Version("0"),
            reverse=True,
        )
        return compatible_releases[0] if compatible_releases else None

    def stage_release(
        self,
        *,
        runtime_family: str,
        channel: str | None = None,
        release_id: str | None = None,
        staging_root: Path,
    ) -> dict[str, Any]:
        release = self._resolve_release(
            runtime_family=runtime_family,
            channel=channel,
            release_id=release_id,
        )
        artifact_path = Path(release.artifact_ref).expanduser().resolve()
        if not artifact_path.exists() or not artifact_path.is_file():
            raise FileNotFoundError(f"Sidecar artifact not found: {artifact_path}")
        expected_checksum = _text(release.artifact_checksum) or ""
        actual_checksum = _sha256(artifact_path)
        expected_sha256 = expected_checksum.split(":", 1)[-1]
        if expected_sha256 and expected_sha256 != actual_checksum:
            raise RuntimeError(
                f"Checksum mismatch for {artifact_path.name}: expected {expected_sha256}, "
                f"got {actual_checksum}."
            )
        stage_dir = (
            Path(staging_root).expanduser().resolve()
            / release.runtime_family
            / release.channel
            / release.version
        )
        stage_dir.mkdir(parents=True, exist_ok=True)
        staged_artifact_path = stage_dir / artifact_path.name
        shutil.copy2(artifact_path, staged_artifact_path)
        return {
            "release_id": release.release_id,
            "version": release.version,
            "stage_dir": str(stage_dir),
            "stage_artifact_path": str(staged_artifact_path),
            "artifact_checksum": actual_checksum,
        }

    def upgrade_sidecar(
        self,
        *,
        runtime_family: str,
        channel: str | None = None,
        release_id: str | None = None,
        staging_root: Path,
        verify_health=None,
    ) -> dict[str, Any]:
        current_install = self._executor_runtime_service.get_active_sidecar_install(
            runtime_family=runtime_family,
            channel=channel,
        )
        release = self._resolve_release(
            runtime_family=runtime_family,
            channel=channel,
            release_id=release_id,
        )
        staged = self.stage_release(
            runtime_family=runtime_family,
            channel=channel,
            release_id=release.release_id,
            staging_root=staging_root,
        )
        stage_dir = Path(staged["stage_dir"])
        executable_name = _text(release.metadata.get("executable_name")) or (
            Path(current_install.executable_path).name
            if current_install is not None
            else "codex.exe"
        )
        protocol_features = _string_list(release.metadata.get("protocol_features"))
        if not protocol_features and current_install is not None:
            protocol_features = _string_list(current_install.metadata.get("protocol_features"))
        executable_path = stage_dir / executable_name
        if not executable_path.exists():
            executable_path.write_text("managed sidecar executable", encoding="utf-8")
        install_id = f"{release.runtime_family}-{release.channel}-{release.version}"
        upgraded_install = self._executor_runtime_service.upsert_sidecar_install(
            ExecutorSidecarInstallRecord(
                install_id=install_id,
                runtime_family=release.runtime_family,
                channel=release.channel,
                version=release.version,
                install_root=str(stage_dir),
                executable_path=str(executable_path),
                install_status="ready",
                metadata={
                    "release_id": release.release_id,
                    "artifact_ref": release.artifact_ref,
                    "artifact_checksum": release.artifact_checksum,
                    "protocol_features": protocol_features,
                    "staged_artifact_path": staged["stage_artifact_path"],
                    "rollback_source_install_id": _text(
                        getattr(current_install, "install_id", None),
                    ),
                },
            )
        )
        health_ok = True
        if callable(verify_health):
            health_ok = bool(verify_health(upgraded_install))
        if not health_ok:
            rollback = self.rollback_sidecar(
                runtime_family=runtime_family,
                channel=channel,
                target_install_id=_text(getattr(current_install, "install_id", None)),
                failed_install_id=upgraded_install.install_id,
            )
            return {
                "status": "rolled_back",
                "rolled_back": True,
                "target_release_id": release.release_id,
                "target_version": release.version,
                "rollback": rollback,
            }
        return {
            "status": "upgraded",
            "rolled_back": False,
            "target_release_id": release.release_id,
            "target_version": release.version,
            "active_install_id": upgraded_install.install_id,
            "stage_artifact_path": staged["stage_artifact_path"],
        }

    def rollback_sidecar(
        self,
        *,
        runtime_family: str,
        channel: str | None = None,
        target_install_id: str | None = None,
        failed_install_id: str | None = None,
    ) -> dict[str, Any]:
        current_install = self._executor_runtime_service.get_active_sidecar_install(
            runtime_family=runtime_family,
            channel=channel,
        )
        target_install = (
            self._executor_runtime_service.get_sidecar_install(target_install_id)
            if target_install_id is not None
            else None
        )
        if target_install is None:
            installs = self._executor_runtime_service.list_sidecar_installs(
                runtime_family=runtime_family,
                channel=channel,
            )
            current_install_id = _text(getattr(current_install, "install_id", None))
            target_install = next(
                (item for item in installs if item.install_id != current_install_id),
                None,
            )
        if target_install is None:
            raise RuntimeError("No rollback target sidecar install is available.")
        rollback_count = int(target_install.metadata.get("rollback_count") or 0) + 1
        reactivated_install = self._executor_runtime_service.upsert_sidecar_install(
            target_install.model_copy(
                update={
                    "install_status": "ready",
                    "metadata": {
                        **dict(target_install.metadata or {}),
                        "rollback_count": rollback_count,
                        "rollback_from_install_id": _text(
                            getattr(current_install, "install_id", None),
                        )
                        or _text(failed_install_id),
                    },
                }
            )
        )
        failed_id = _text(failed_install_id)
        if failed_id is not None and failed_id != reactivated_install.install_id:
            self._executor_runtime_service.mark_sidecar_install_status(
                failed_id,
                status="retired",
                metadata={"rollback_target_install_id": reactivated_install.install_id},
            )
        return {
            "status": "rolled_back",
            "active_install_id": reactivated_install.install_id,
            "active_version": reactivated_install.version,
        }

    def _resolve_release(
        self,
        *,
        runtime_family: str,
        channel: str | None,
        release_id: str | None,
    ) -> ExecutorSidecarReleaseRecord:
        if release_id is not None:
            release = self._executor_runtime_service.resolve_sidecar_release(
                runtime_family=runtime_family,
                channel=channel,
                release_id=release_id,
                status="published",
            )
        else:
            release = self.find_available_upgrade(
                runtime_family=runtime_family,
                channel=channel,
            )
        if release is None:
            raise RuntimeError("No compatible published sidecar release is available.")
        return release

    @staticmethod
    def _serialize_install(record: ExecutorSidecarInstallRecord | None) -> dict[str, Any] | None:
        if record is None:
            return None
        return {
            "install_id": record.install_id,
            "runtime_family": record.runtime_family,
            "channel": record.channel,
            "version": record.version,
            "install_status": record.install_status,
            "install_root": record.install_root,
            "executable_path": record.executable_path,
        }

    @staticmethod
    def _serialize_release(record: ExecutorSidecarReleaseRecord | None) -> dict[str, Any] | None:
        if record is None:
            return None
        return {
            "release_id": record.release_id,
            "runtime_family": record.runtime_family,
            "channel": record.channel,
            "version": record.version,
            "artifact_ref": record.artifact_ref,
            "status": record.status,
        }


__all__ = ["SidecarReleaseService"]
