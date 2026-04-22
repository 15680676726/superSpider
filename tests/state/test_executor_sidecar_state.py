# -*- coding: utf-8 -*-
from __future__ import annotations

from copaw.state import SQLiteStateStore
from copaw.state import models_executor_runtime as executor_models
from copaw.state.executor_runtime_service import ExecutorRuntimeService


def _build_service(tmp_path) -> ExecutorRuntimeService:
    return ExecutorRuntimeService(state_store=SQLiteStateStore(tmp_path / "state.db"))


def _sidecar_install_record_type():
    record_type = getattr(executor_models, "ExecutorSidecarInstallRecord", None)
    assert record_type is not None
    return record_type


def _sidecar_compatibility_policy_record_type():
    record_type = getattr(
        executor_models,
        "ExecutorSidecarCompatibilityPolicyRecord",
        None,
    )
    assert record_type is not None
    return record_type


def _sidecar_release_record_type():
    record_type = getattr(executor_models, "ExecutorSidecarReleaseRecord", None)
    assert record_type is not None
    return record_type


def test_sidecar_install_truth_persists_single_active_install_and_history(
    tmp_path,
) -> None:
    service = _build_service(tmp_path)
    install_record_type = _sidecar_install_record_type()

    first = service.upsert_sidecar_install(
        install_record_type(
            install_id="codex-stable-0.9.0",
            runtime_family="codex",
            channel="stable",
            version="0.9.0",
            install_root="D:/word/copaw/runtime/codex/0.9.0",
            executable_path="D:/word/copaw/runtime/codex/0.9.0/codex.exe",
            install_status="ready",
            metadata={"managed_by": "copaw"},
        )
    )
    second = service.upsert_sidecar_install(
        install_record_type(
            install_id="codex-stable-0.10.0",
            runtime_family="codex",
            channel="stable",
            version="0.10.0",
            install_root="D:/word/copaw/runtime/codex/0.10.0",
            executable_path="D:/word/copaw/runtime/codex/0.10.0/codex.exe",
            install_status="ready",
            metadata={"managed_by": "copaw"},
        )
    )

    active = service.get_active_sidecar_install(runtime_family="codex")
    history = service.list_sidecar_installs(runtime_family="codex")

    assert first.install_id == "codex-stable-0.9.0"
    assert second.install_id == "codex-stable-0.10.0"
    assert active is not None
    assert active.install_id == second.install_id
    assert [record.install_id for record in history] == [
        second.install_id,
        first.install_id,
    ]
    assert history[1].install_status == "superseded"


def test_sidecar_compatibility_policy_and_release_truth_round_trip(tmp_path) -> None:
    service = _build_service(tmp_path)
    compatibility_policy_type = _sidecar_compatibility_policy_record_type()
    release_record_type = _sidecar_release_record_type()

    policy = service.upsert_sidecar_compatibility_policy(
        compatibility_policy_type(
            policy_id="codex-stable",
            runtime_family="codex",
            channel="stable",
            supported_version_range=">=0.10,<0.11",
            required_copaw_version_range=">=1.0",
            status="active",
            metadata={"fail_closed": True},
        )
    )
    release = service.upsert_sidecar_release(
        release_record_type(
            release_id="codex-stable-0.10.0",
            runtime_family="codex",
            channel="stable",
            version="0.10.0",
            artifact_ref="https://example.invalid/codex-stable-0.10.0.zip",
            artifact_checksum="sha256:test-checksum",
            status="published",
            metadata={"current": True},
        )
    )

    resolved_policy = service.resolve_sidecar_compatibility_policy(
        runtime_family="codex",
        channel="stable",
    )
    releases = service.list_sidecar_releases(
        runtime_family="codex",
        channel="stable",
    )

    assert policy.policy_id == "codex-stable"
    assert release.release_id == "codex-stable-0.10.0"
    assert resolved_policy is not None
    assert resolved_policy.policy_id == policy.policy_id
    assert [record.release_id for record in releases] == [release.release_id]
