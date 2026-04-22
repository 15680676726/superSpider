# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import subprocess
import zipfile
from pathlib import Path
from types import SimpleNamespace

from copaw.app import sidecar_release_service as sidecar_release_service_module
from copaw.app.sidecar_release_service import SidecarReleaseService
from copaw.state import SQLiteStateStore
from copaw.state import models_executor_runtime as executor_models
from copaw.state.executor_runtime_service import ExecutorRuntimeService


def _build_service(tmp_path: Path) -> ExecutorRuntimeService:
    return ExecutorRuntimeService(state_store=SQLiteStateStore(tmp_path / "state.db"))


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_zip_with_executable(
    path: Path,
    *,
    executable_name: str,
    executable_text: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(executable_name, executable_text)


def test_sidecar_version_compatibility_rejects_unsupported_install(tmp_path: Path) -> None:
    service = _build_service(tmp_path)
    install_type = executor_models.ExecutorSidecarInstallRecord
    policy_type = executor_models.ExecutorSidecarCompatibilityPolicyRecord

    executable_path = tmp_path / "runtime" / "codex" / "0.9.0" / "codex.exe"
    executable_path.parent.mkdir(parents=True, exist_ok=True)
    executable_path.write_text("codex", encoding="utf-8")

    service.upsert_sidecar_install(
        install_type(
            install_id="codex-stable-0.9.0",
            runtime_family="codex",
            channel="stable",
            version="0.9.0",
            install_root=str(executable_path.parent),
            executable_path=str(executable_path),
            install_status="ready",
            metadata={"protocol_features": []},
        )
    )
    service.upsert_sidecar_compatibility_policy(
        policy_type(
            policy_id="codex-stable-policy",
            runtime_family="codex",
            channel="stable",
            supported_version_range=">=0.10,<0.11",
            required_copaw_version_range=">=1.0",
            status="active",
            metadata={
                "fail_closed": True,
                "required_protocol_features": ["approval/request"],
            },
        )
    )
    release_service = SidecarReleaseService(
        executor_runtime_service=service,
        copaw_version="1.0.0",
    )

    compatibility = release_service.describe_version_governance(
        runtime_family="codex",
        channel="stable",
    )

    assert compatibility["compatibility"]["status"] == "incompatible"
    assert compatibility["compatibility"]["fail_closed"] is True
    assert "0.9.0" in " ".join(compatibility["compatibility"]["blockers"])


def test_sidecar_upgrade_rolls_back_when_health_check_fails(tmp_path: Path) -> None:
    service = _build_service(tmp_path)
    install_type = executor_models.ExecutorSidecarInstallRecord
    policy_type = executor_models.ExecutorSidecarCompatibilityPolicyRecord
    release_type = executor_models.ExecutorSidecarReleaseRecord

    current_executable = tmp_path / "runtime" / "codex" / "0.9.0" / "codex.exe"
    current_executable.parent.mkdir(parents=True, exist_ok=True)
    current_executable.write_text("codex-0.9.0", encoding="utf-8")
    artifact_path = tmp_path / "artifacts" / "codex-0.10.0.zip"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("codex-0.10.0", encoding="utf-8")

    service.upsert_sidecar_install(
        install_type(
            install_id="codex-stable-0.9.0",
            runtime_family="codex",
            channel="stable",
            version="0.9.0",
            install_root=str(current_executable.parent),
            executable_path=str(current_executable),
            install_status="ready",
            metadata={"protocol_features": ["approval/request"]},
        )
    )
    service.upsert_sidecar_compatibility_policy(
        policy_type(
            policy_id="codex-stable-policy",
            runtime_family="codex",
            channel="stable",
            supported_version_range=">=0.10,<0.11",
            required_copaw_version_range=">=1.0",
            status="active",
            metadata={
                "fail_closed": True,
                "required_protocol_features": ["approval/request"],
            },
        )
    )
    service.upsert_sidecar_release(
        release_type(
            release_id="codex-stable-0.10.0",
            runtime_family="codex",
            channel="stable",
            version="0.10.0",
            artifact_ref=str(artifact_path),
            artifact_checksum=f"sha256:{_checksum(artifact_path)}",
            status="published",
            metadata={"executable_name": "codex.exe"},
        )
    )
    release_service = SidecarReleaseService(
        executor_runtime_service=service,
        copaw_version="1.0.0",
    )

    result = release_service.upgrade_sidecar(
        runtime_family="codex",
        channel="stable",
        staging_root=tmp_path / "staging",
        verify_health=lambda _install: False,
    )
    active_install = service.get_active_sidecar_install(runtime_family="codex", channel="stable")

    assert result["status"] == "rolled_back"
    assert result["rolled_back"] is True
    assert result["target_release_id"] == "codex-stable-0.10.0"
    assert active_install is not None
    assert active_install.version == "0.9.0"


def test_sidecar_install_materializes_real_executable_from_published_release(
    tmp_path: Path,
) -> None:
    service = _build_service(tmp_path)
    policy_type = executor_models.ExecutorSidecarCompatibilityPolicyRecord
    release_type = executor_models.ExecutorSidecarReleaseRecord

    artifact_path = tmp_path / "artifacts" / "codex.exe"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("real-codex-binary", encoding="utf-8")

    service.upsert_sidecar_compatibility_policy(
        policy_type(
            policy_id="codex-stable-policy",
            runtime_family="codex",
            channel="stable",
            supported_version_range=">=0.10,<0.11",
            required_copaw_version_range=">=1.0",
            status="active",
            metadata={"fail_closed": True},
        )
    )
    service.upsert_sidecar_release(
        release_type(
            release_id="codex-stable-0.10.0",
            runtime_family="codex",
            channel="stable",
            version="0.10.0",
            artifact_ref=str(artifact_path),
            artifact_checksum=f"sha256:{_checksum(artifact_path)}",
            status="published",
            metadata={"executable_name": "codex.exe"},
        )
    )
    release_service = SidecarReleaseService(
        executor_runtime_service=service,
        copaw_version="1.0.0",
    )

    result = release_service.install_sidecar(
        runtime_family="codex",
        channel="stable",
        staging_root=tmp_path / "staging",
        verify_health=lambda _install: True,
    )
    active_install = service.get_active_sidecar_install(runtime_family="codex", channel="stable")

    assert result["status"] == "installed"
    assert active_install is not None
    assert active_install.version == "0.10.0"
    executable_path = Path(active_install.executable_path)
    assert executable_path.exists()
    assert executable_path.read_text(encoding="utf-8") == "real-codex-binary"
    assert "managed sidecar executable" not in executable_path.read_text(encoding="utf-8")


def test_sidecar_upgrade_extracts_archive_and_activates_real_executable(
    tmp_path: Path,
) -> None:
    service = _build_service(tmp_path)
    install_type = executor_models.ExecutorSidecarInstallRecord
    policy_type = executor_models.ExecutorSidecarCompatibilityPolicyRecord
    release_type = executor_models.ExecutorSidecarReleaseRecord

    current_executable = tmp_path / "runtime" / "codex" / "0.9.0" / "codex.exe"
    current_executable.parent.mkdir(parents=True, exist_ok=True)
    current_executable.write_text("codex-0.9.0", encoding="utf-8")
    artifact_path = tmp_path / "artifacts" / "codex-0.10.0.zip"
    _write_zip_with_executable(
        artifact_path,
        executable_name="codex.exe",
        executable_text="real-codex-0.10.0",
    )

    service.upsert_sidecar_install(
        install_type(
            install_id="codex-stable-0.9.0",
            runtime_family="codex",
            channel="stable",
            version="0.9.0",
            install_root=str(current_executable.parent),
            executable_path=str(current_executable),
            install_status="ready",
            metadata={"protocol_features": ["approval/request"]},
        )
    )
    service.upsert_sidecar_compatibility_policy(
        policy_type(
            policy_id="codex-stable-policy",
            runtime_family="codex",
            channel="stable",
            supported_version_range=">=0.10,<0.11",
            required_copaw_version_range=">=1.0",
            status="active",
            metadata={
                "fail_closed": True,
                "required_protocol_features": ["approval/request"],
            },
        )
    )
    service.upsert_sidecar_release(
        release_type(
            release_id="codex-stable-0.10.0",
            runtime_family="codex",
            channel="stable",
            version="0.10.0",
            artifact_ref=str(artifact_path),
            artifact_checksum=f"sha256:{_checksum(artifact_path)}",
            status="published",
            metadata={"executable_name": "codex.exe"},
        )
    )
    release_service = SidecarReleaseService(
        executor_runtime_service=service,
        copaw_version="1.0.0",
    )

    result = release_service.upgrade_sidecar(
        runtime_family="codex",
        channel="stable",
        staging_root=tmp_path / "staging",
        verify_health=lambda _install: True,
    )
    active_install = service.get_active_sidecar_install(runtime_family="codex", channel="stable")

    assert result["status"] == "upgraded"
    assert active_install is not None
    assert active_install.version == "0.10.0"
    executable_path = Path(active_install.executable_path)
    assert executable_path.exists()
    assert executable_path.read_text(encoding="utf-8") == "real-codex-0.10.0"


def test_sidecar_release_service_syncs_bundled_manifest_into_state(tmp_path: Path) -> None:
    service = _build_service(tmp_path)
    artifact_path = tmp_path / "bundle" / "codex-0.10.0.zip"
    _write_zip_with_executable(
        artifact_path,
        executable_name="codex.exe",
        executable_text="real-codex-0.10.0",
    )
    manifest_path = tmp_path / "bundle" / "manifest.json"
    manifest_path.write_text(
        """
{
  "runtime_family": "codex",
  "channel": "stable",
  "compatibility_policy": {
    "policy_id": "codex-stable-policy",
    "supported_version_range": ">=0.10,<0.11",
    "required_copaw_version_range": ">=1.0",
    "status": "active",
    "metadata": {
      "fail_closed": true,
      "required_protocol_features": ["approval/request"]
    }
  },
  "releases": [
    {
      "release_id": "codex-stable-0.10.0",
      "version": "0.10.0",
      "artifact_ref": "codex-0.10.0.zip",
      "artifact_checksum": "sha256:%s",
      "status": "published",
      "metadata": {
        "executable_name": "codex.exe",
        "protocol_features": ["approval/request"]
      }
    }
  ]
}
"""
        % _checksum(artifact_path),
        encoding="utf-8",
    )
    release_service = SidecarReleaseService(
        executor_runtime_service=service,
        copaw_version="1.0.0",
    )

    release_service.sync_bundled_release_manifest(manifest_path)

    policy = service.resolve_sidecar_compatibility_policy(runtime_family="codex", channel="stable")
    release = service.resolve_sidecar_release(
        runtime_family="codex",
        channel="stable",
        release_id="codex-stable-0.10.0",
        status="published",
    )

    assert policy is not None
    assert policy.supported_version_range == ">=0.10,<0.11"
    assert release is not None
    assert Path(release.artifact_ref) == artifact_path.resolve()


def test_sidecar_install_copies_npm_shim_support_tree(tmp_path: Path) -> None:
    service = _build_service(tmp_path)
    policy_type = executor_models.ExecutorSidecarCompatibilityPolicyRecord
    release_type = executor_models.ExecutorSidecarReleaseRecord

    source_root = tmp_path / "source"
    artifact_path = source_root / "codex.cmd"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        """
@ECHO off
SETLOCAL
SET dp0=%~dp0
"%dp0%\\node.exe" "%dp0%\\node_modules\\@openai\\codex\\bin\\codex.js" %*
""".strip(),
        encoding="utf-8",
    )
    support_file = source_root / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
    support_file.parent.mkdir(parents=True, exist_ok=True)
    support_file.write_text("console.log('codex')", encoding="utf-8")

    service.upsert_sidecar_compatibility_policy(
        policy_type(
            policy_id="codex-stable-policy",
            runtime_family="codex",
            channel="stable",
            supported_version_range=">=0.10,<0.11",
            required_copaw_version_range=">=1.0",
            status="active",
            metadata={"fail_closed": True},
        )
    )
    service.upsert_sidecar_release(
        release_type(
            release_id="codex-stable-0.10.0",
            runtime_family="codex",
            channel="stable",
            version="0.10.0",
            artifact_ref=str(artifact_path),
            artifact_checksum=f"sha256:{_checksum(artifact_path)}",
            status="published",
            metadata={"executable_name": "codex.cmd"},
        )
    )
    release_service = SidecarReleaseService(
        executor_runtime_service=service,
        copaw_version="1.0.0",
    )

    release_service.install_sidecar(
        runtime_family="codex",
        channel="stable",
        staging_root=tmp_path / "staging",
        verify_health=lambda _install: True,
    )
    active_install = service.get_active_sidecar_install(runtime_family="codex", channel="stable")

    assert active_install is not None
    installed_support_file = (
        Path(active_install.install_root)
        / "node_modules"
        / "@openai"
        / "codex"
        / "bin"
        / "codex.js"
    )
    assert installed_support_file.exists()
    assert installed_support_file.read_text(encoding="utf-8") == "console.log('codex')"


def test_sidecar_install_runs_default_health_probe(tmp_path: Path, monkeypatch) -> None:
    service = _build_service(tmp_path)
    policy_type = executor_models.ExecutorSidecarCompatibilityPolicyRecord
    release_type = executor_models.ExecutorSidecarReleaseRecord
    artifact_path = tmp_path / "artifacts" / "codex.exe"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("real-codex-binary", encoding="utf-8")

    service.upsert_sidecar_compatibility_policy(
        policy_type(
            policy_id="codex-stable-policy",
            runtime_family="codex",
            channel="stable",
            supported_version_range=">=0.10,<0.11",
            required_copaw_version_range=">=1.0",
            status="active",
            metadata={"fail_closed": True},
        )
    )
    service.upsert_sidecar_release(
        release_type(
            release_id="codex-stable-0.10.0",
            runtime_family="codex",
            channel="stable",
            version="0.10.0",
            artifact_ref=str(artifact_path),
            artifact_checksum=f"sha256:{_checksum(artifact_path)}",
            status="published",
            metadata={"executable_name": "codex.exe"},
        )
    )
    release_service = SidecarReleaseService(
        executor_runtime_service=service,
        copaw_version="1.0.0",
    )
    captured: dict[str, object] = {}

    def _fake_run(command, **kwargs):
        captured["command"] = list(command)
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout="codex-cli 0.10.0", stderr="")

    monkeypatch.setattr(
        sidecar_release_service_module,
        "subprocess",
        SimpleNamespace(run=_fake_run),
        raising=False,
    )

    release_service.install_sidecar(
        runtime_family="codex",
        channel="stable",
        staging_root=tmp_path / "staging",
    )
    active_install = service.get_active_sidecar_install(runtime_family="codex", channel="stable")

    assert active_install is not None
    assert captured["command"] == [active_install.executable_path, "--version"]
