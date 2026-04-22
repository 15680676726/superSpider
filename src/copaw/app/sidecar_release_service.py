# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

from ..__version__ import __version__
from ..state.executor_runtime_service import ExecutorRuntimeService
from ..state.models_executor_runtime import (
    ExecutorSidecarInstallRecord,
    ExecutorSidecarCompatibilityPolicyRecord,
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


def _copy_file(source: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


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

    def sync_bundled_release_manifest(self, manifest_path: Path) -> dict[str, Any]:
        path = Path(manifest_path).expanduser().resolve()
        payload = json.loads(path.read_text(encoding="utf-8"))
        runtime_family = _text(payload.get("runtime_family")) or "codex"
        channel = _text(payload.get("channel")) or "stable"
        policy_payload = dict(payload.get("compatibility_policy") or {})
        releases_payload = list(payload.get("releases") or [])
        if policy_payload:
            self._executor_runtime_service.upsert_sidecar_compatibility_policy(
                ExecutorSidecarCompatibilityPolicyRecord(
                    policy_id=_text(policy_payload.get("policy_id"))
                    or f"{runtime_family}-{channel}-policy",
                    runtime_family=runtime_family,
                    channel=channel,
                    supported_version_range=_text(policy_payload.get("supported_version_range"))
                    or ">=0",
                    required_copaw_version_range=_text(
                        policy_payload.get("required_copaw_version_range"),
                    )
                    or "",
                    status=_text(policy_payload.get("status")) or "active",
                    metadata=dict(policy_payload.get("metadata") or {}),
                )
            )
        synced_releases: list[str] = []
        for item in releases_payload:
            artifact_ref = Path(str(item.get("artifact_ref") or "")).expanduser()
            if not artifact_ref.is_absolute():
                artifact_ref = (path.parent / artifact_ref).resolve()
            release = self._executor_runtime_service.upsert_sidecar_release(
                ExecutorSidecarReleaseRecord(
                    release_id=_text(item.get("release_id"))
                    or f"{runtime_family}-{channel}-{_text(item.get('version')) or 'unknown'}",
                    runtime_family=runtime_family,
                    channel=channel,
                    version=_text(item.get("version")) or "0",
                    artifact_ref=str(artifact_ref),
                    artifact_checksum=_text(item.get("artifact_checksum")) or "",
                    status=_text(item.get("status")) or "published",
                    metadata=dict(item.get("metadata") or {}),
                )
            )
            synced_releases.append(release.release_id)
        return {
            "runtime_family": runtime_family,
            "channel": channel,
            "release_ids": synced_releases,
            "manifest_path": str(path),
        }

    def install_sidecar(
        self,
        *,
        runtime_family: str,
        channel: str | None = None,
        release_id: str | None = None,
        staging_root: Path,
        verify_health=None,
    ) -> dict[str, Any]:
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
        installed_install = self._activate_release_install(
            release=release,
            staged=staged,
            previous_install=None,
        )
        if not self._verify_install_health(
            installed_install,
            verify_health=verify_health,
        ):
            self._executor_runtime_service.mark_sidecar_install_status(
                installed_install.install_id,
                status="retired",
                metadata={"install_error": "health-verification-failed"},
            )
            raise RuntimeError(
                f"Sidecar health verification failed for release '{release.release_id}'.",
            )
        return {
            "status": "installed",
            "rolled_back": False,
            "target_release_id": release.release_id,
            "target_version": release.version,
            "active_install_id": installed_install.install_id,
            "stage_artifact_path": staged["stage_artifact_path"],
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
        upgraded_install = self._activate_release_install(
            release=release,
            staged=staged,
            previous_install=current_install,
        )
        health_ok = self._verify_install_health(
            upgraded_install,
            verify_health=verify_health,
        )
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

    def _activate_release_install(
        self,
        *,
        release: ExecutorSidecarReleaseRecord,
        staged: dict[str, Any],
        previous_install: ExecutorSidecarInstallRecord | None,
    ) -> ExecutorSidecarInstallRecord:
        stage_dir = Path(str(staged["stage_dir"]))
        staged_artifact_path = Path(str(staged["stage_artifact_path"]))
        executable_name = _text(release.metadata.get("executable_name")) or (
            Path(previous_install.executable_path).name
            if previous_install is not None
            else staged_artifact_path.name
        )
        protocol_features = _string_list(release.metadata.get("protocol_features"))
        if not protocol_features and previous_install is not None:
            protocol_features = _string_list(previous_install.metadata.get("protocol_features"))
        executable_path = self._materialize_executable(
            source_artifact_path=Path(release.artifact_ref).expanduser().resolve(),
            staged_artifact_path=staged_artifact_path,
            stage_dir=stage_dir,
            executable_name=executable_name,
        )
        install_id = f"{release.runtime_family}-{release.channel}-{release.version}"
        installed = self._executor_runtime_service.upsert_sidecar_install(
            ExecutorSidecarInstallRecord(
                install_id=install_id,
                runtime_family=release.runtime_family,
                channel=release.channel,
                version=release.version,
                install_root=str(executable_path.parent),
                executable_path=str(executable_path),
                install_status="ready",
                metadata={
                    "release_id": release.release_id,
                    "artifact_ref": release.artifact_ref,
                    "artifact_checksum": release.artifact_checksum,
                    "protocol_features": protocol_features,
                    "staged_artifact_path": str(staged_artifact_path),
                    "rollback_source_install_id": _text(
                        getattr(previous_install, "install_id", None),
                    ),
                },
            )
        )
        return installed

    def _materialize_executable(
        self,
        *,
        source_artifact_path: Path,
        staged_artifact_path: Path,
        stage_dir: Path,
        executable_name: str | None,
    ) -> Path:
        resolved_name = _text(executable_name)
        if zipfile.is_zipfile(staged_artifact_path):
            extract_root = stage_dir / "payload"
            if extract_root.exists():
                shutil.rmtree(extract_root)
            extract_root.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(staged_artifact_path) as archive:
                archive.extractall(extract_root)
            executable = self._find_executable(
                root=extract_root,
                executable_name=resolved_name,
            )
            if executable is None:
                raise RuntimeError(
                    f"Managed sidecar archive '{staged_artifact_path.name}' does not contain "
                    f"expected executable '{resolved_name or '<unspecified>'}'.",
                )
            return executable
        executable_path = (
            staged_artifact_path
            if resolved_name is None or staged_artifact_path.name == resolved_name
            else _copy_file(staged_artifact_path, stage_dir / resolved_name)
        )
        self._copy_direct_artifact_support_tree(
            source_artifact_path=source_artifact_path,
            stage_dir=stage_dir,
        )
        return executable_path

    def _copy_direct_artifact_support_tree(
        self,
        *,
        source_artifact_path: Path,
        stage_dir: Path,
    ) -> None:
        if source_artifact_path.suffix.lower() != ".cmd":
            return
        try:
            shim_text = source_artifact_path.read_text(encoding="utf-8")
        except OSError:
            return
        package_roots: set[Path] = set()
        for relative_ref in re.findall(r"%dp0%\\([^\"\r\n]+)", shim_text, flags=re.IGNORECASE):
            relative_path = Path(relative_ref.replace("\\", "/"))
            if not relative_path.parts or relative_path.parts[0] != "node_modules":
                continue
            package_root = self._package_root_from_relative_path(relative_path)
            if package_root is not None:
                package_roots.add(package_root)
        for package_root in sorted(package_roots):
            source_package_root = source_artifact_path.parent / package_root
            if not source_package_root.exists() or not source_package_root.is_dir():
                continue
            target_package_root = stage_dir / package_root
            if target_package_root.exists():
                shutil.rmtree(target_package_root)
            target_package_root.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source_package_root, target_package_root)

    def _package_root_from_relative_path(self, relative_path: Path) -> Path | None:
        parts = list(relative_path.parts)
        if len(parts) < 2 or parts[0] != "node_modules":
            return None
        if parts[1].startswith("@"):
            if len(parts) < 3:
                return None
            return Path(parts[0]) / parts[1] / parts[2]
        return Path(parts[0]) / parts[1]

    def _verify_install_health(
        self,
        install: ExecutorSidecarInstallRecord,
        *,
        verify_health=None,
    ) -> bool:
        if callable(verify_health):
            return bool(verify_health(install))
        return self._default_verify_install_health(install)

    def _default_verify_install_health(
        self,
        install: ExecutorSidecarInstallRecord,
    ) -> bool:
        executable_path = Path(install.executable_path).expanduser().resolve()
        if not executable_path.exists() or not executable_path.is_file():
            return False
        completed = subprocess.run(
            [str(executable_path), "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
            check=False,
        )
        return int(completed.returncode) == 0

    def _find_executable(
        self,
        *,
        root: Path,
        executable_name: str | None,
    ) -> Path | None:
        if executable_name is not None:
            exact = next(
                (item for item in root.rglob(executable_name) if item.is_file()),
                None,
            )
            if exact is not None:
                return exact
        files = [item for item in root.rglob("*") if item.is_file()]
        if len(files) == 1:
            return files[0]
        return None

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
