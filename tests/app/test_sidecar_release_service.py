# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
from pathlib import Path

from copaw.app.sidecar_release_service import SidecarReleaseService
from copaw.state import SQLiteStateStore
from copaw.state import models_executor_runtime as executor_models
from copaw.state.executor_runtime_service import ExecutorRuntimeService


def _build_service(tmp_path: Path) -> ExecutorRuntimeService:
    return ExecutorRuntimeService(state_store=SQLiteStateStore(tmp_path / "state.db"))


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
