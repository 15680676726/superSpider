from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from types import SimpleNamespace

from copaw.app import runtime_service_graph as runtime_service_graph_module
from copaw.app import sidecar_release_service as sidecar_release_service_module
from copaw.app.runtime_bootstrap_execution import build_runtime_execution_stack
from copaw.state import SQLiteStateStore
from copaw.state.executor_runtime_service import ExecutorRuntimeService
from copaw.state.models_executor_runtime import (
    ExecutorSidecarCompatibilityPolicyRecord,
    ExecutorSidecarInstallRecord,
)


def _repositories() -> SimpleNamespace:
    return SimpleNamespace(
        capability_override_repository=object(),
        agent_profile_override_repository=object(),
        goal_override_repository=object(),
        workflow_template_repository=object(),
        workflow_run_repository=object(),
        governance_control_repository=object(),
        decision_request_repository=object(),
        task_repository=object(),
        task_runtime_repository=object(),
        runtime_frame_repository=object(),
        agent_mailbox_repository=object(),
        agent_runtime_repository=object(),
        agent_thread_binding_repository=object(),
    )


def test_build_runtime_execution_stack_passes_runtime_provider_to_capability_service(
    tmp_path,
) -> None:
    captured: dict[str, object] = {}

    class _LearningService:
        def __init__(self, **kwargs) -> None:
            captured["learning_service_kwargs"] = kwargs

    class _GovernanceService:
        def __init__(self, **kwargs) -> None:
            captured["governance_service_kwargs"] = kwargs

        def set_kernel_dispatcher(self, kernel_dispatcher) -> None:
            captured["governance_kernel_dispatcher"] = kernel_dispatcher

    class _KernelTaskStore:
        def __init__(self, **kwargs) -> None:
            captured["kernel_task_store_kwargs"] = kwargs

    class _KernelToolBridge:
        def __init__(self, **kwargs) -> None:
            captured["kernel_tool_bridge_kwargs"] = kwargs

    class _CapabilityService:
        def __init__(self, **kwargs) -> None:
            captured["capability_service_kwargs"] = kwargs

    class _KernelDispatcher:
        def __init__(self, **kwargs) -> None:
            captured["kernel_dispatcher_kwargs"] = kwargs

    build_runtime_execution_stack(
        mcp_manager=object(),
        environment_service=object(),
        evidence_ledger=object(),
        repositories=_repositories(),
        runtime_event_bus=object(),
        state_query_service=object(),
        conversation_compaction_service=None,
        experience_memory_service=None,
        state_store=SQLiteStateStore(tmp_path / "state.sqlite3"),
        work_context_service=object(),
        runtime_provider="provider-runtime-facade",
        learning_service_cls=_LearningService,
        governance_service_cls=_GovernanceService,
        kernel_task_store_cls=_KernelTaskStore,
        kernel_tool_bridge_cls=_KernelToolBridge,
        capability_service_cls=_CapabilityService,
        kernel_dispatcher_cls=_KernelDispatcher,
    )

    assert (
        captured["capability_service_kwargs"]["runtime_provider"]
        == "provider-runtime-facade"
    )


def test_build_kernel_runtime_forwards_runtime_provider_to_execution_stack(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        runtime_service_graph_module,
        "build_runtime_execution_stack_components",
        lambda **kwargs: captured.setdefault("kwargs", kwargs) or (
            "learning",
            "governance",
            "task-store",
            "tool-bridge",
            "capability-service",
            "dispatcher",
        ),
    )

    runtime_service_graph_module._build_kernel_runtime(
        mcp_manager=object(),
        environment_service=object(),
        evidence_ledger=object(),
        repositories=object(),
        runtime_event_bus=object(),
        state_query_service=object(),
        conversation_compaction_service=None,
        experience_memory_service=None,
        state_store=SQLiteStateStore(":memory:"),
        work_context_service=object(),
        runtime_provider="provider-runtime-facade",
        external_runtime_service=None,
    )

    assert captured["kwargs"]["runtime_provider"] == "provider-runtime-facade"


def test_build_default_executor_runtime_port_prefers_managed_sidecar_stdio(
    monkeypatch,
    tmp_path,
) -> None:
    captured: dict[str, object] = {}
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    executor_runtime_service = ExecutorRuntimeService(state_store=state_store)
    executor_runtime_service.upsert_sidecar_install(
        ExecutorSidecarInstallRecord(
            install_id="codex-stable-0.10.0",
            runtime_family="codex",
            channel="stable",
            version="0.10.0",
            install_root=str(tmp_path / "runtime" / "codex" / "0.10.0"),
            executable_path=str(tmp_path / "runtime" / "codex" / "0.10.0" / "codex.exe"),
            install_status="ready",
        )
    )
    executor_runtime_service.upsert_sidecar_compatibility_policy(
        ExecutorSidecarCompatibilityPolicyRecord(
            policy_id="codex-stable-policy",
            runtime_family="codex",
            channel="stable",
            supported_version_range=">=0.10,<0.11",
            required_copaw_version_range=">=0",
            status="active",
            metadata={"fail_closed": True},
        )
    )

    monkeypatch.delenv("COPAW_CODEX_APP_SERVER_WS_URL", raising=False)
    monkeypatch.setenv("COPAW_CODEX_APP_SERVER_BIN", str(tmp_path / "should-not-be-used.exe"))
    monkeypatch.setattr(
        runtime_service_graph_module,
        "_resolve_state_store",
        lambda: state_store,
    )
    def _fake_stdio_transport(**kwargs):
        captured["stdio_kwargs"] = kwargs
        return "stdio-transport"

    def _fake_ws_transport(**kwargs):
        captured["ws_kwargs"] = kwargs
        return "ws-transport"

    monkeypatch.setattr(
        runtime_service_graph_module,
        "CodexStdioTransport",
        _fake_stdio_transport,
        raising=False,
    )
    monkeypatch.setattr(
        runtime_service_graph_module,
        "CodexAppServerTransport",
        _fake_ws_transport,
    )
    monkeypatch.setattr(
        runtime_service_graph_module,
        "CodexAppServerAdapter",
        lambda transport: SimpleNamespace(transport=transport),
    )

    adapter = runtime_service_graph_module._build_default_executor_runtime_port()

    assert adapter.transport == "stdio-transport"
    assert "ws_kwargs" not in captured
    assert captured["stdio_kwargs"]["codex_command"] == (
        str(tmp_path / "runtime" / "codex" / "0.10.0" / "codex.exe"),
        "app-server",
    )


def test_build_default_executor_runtime_port_keeps_explicit_websocket_override(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setenv("COPAW_CODEX_APP_SERVER_WS_URL", "ws://127.0.0.1:9000")
    def _fake_ws_transport(**kwargs):
        captured["ws_kwargs"] = kwargs
        return "ws-transport"

    monkeypatch.setattr(
        runtime_service_graph_module,
        "CodexAppServerTransport",
        _fake_ws_transport,
    )
    monkeypatch.setattr(
        runtime_service_graph_module,
        "CodexAppServerAdapter",
        lambda transport: SimpleNamespace(transport=transport),
    )

    adapter = runtime_service_graph_module._build_default_executor_runtime_port()

    assert adapter.transport == "ws-transport"
    assert captured["ws_kwargs"]["websocket_url"] == "ws://127.0.0.1:9000"


def _write_zip_with_executable(
    path,
    *,
    executable_name: str,
    executable_text: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(executable_name, executable_text)


def _sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_build_default_executor_runtime_port_syncs_bundled_manifest_and_installs_sidecar(
    monkeypatch,
    tmp_path,
) -> None:
    captured: dict[str, object] = {}
    state_store = SQLiteStateStore(tmp_path / "state.sqlite3")
    bundle_root = tmp_path / "runtime" / "codex"
    artifact_path = bundle_root / "codex-0.10.0.zip"
    _write_zip_with_executable(
        artifact_path,
        executable_name="codex.exe",
        executable_text="real-codex-0.10.0",
    )
    manifest_path = bundle_root / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "runtime_family": "codex",
                "channel": "stable",
                "compatibility_policy": {
                    "policy_id": "codex-stable-policy",
                    "supported_version_range": ">=0.10,<0.11",
                    "required_copaw_version_range": ">=0",
                    "status": "active",
                    "metadata": {"fail_closed": True},
                },
                "releases": [
                    {
                        "release_id": "codex-stable-0.10.0",
                        "version": "0.10.0",
                        "artifact_ref": "codex-0.10.0.zip",
                        "artifact_checksum": f"sha256:{_sha256(artifact_path)}",
                        "status": "published",
                        "metadata": {"executable_name": "codex.exe"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.delenv("COPAW_CODEX_APP_SERVER_WS_URL", raising=False)
    monkeypatch.delenv("COPAW_CODEX_APP_SERVER_BIN", raising=False)
    monkeypatch.setattr(
        runtime_service_graph_module,
        "_resolve_state_store",
        lambda: state_store,
    )
    monkeypatch.setattr(
        runtime_service_graph_module,
        "WORKING_DIR",
        tmp_path,
    )
    monkeypatch.setattr(
        sidecar_release_service_module,
        "subprocess",
        SimpleNamespace(
            run=lambda command, **kwargs: subprocess.CompletedProcess(
                command,
                0,
                stdout="codex-cli 0.10.0",
                stderr="",
            )
        ),
        raising=False,
    )

    def _fake_stdio_transport(**kwargs):
        captured["stdio_kwargs"] = kwargs
        return "stdio-transport"

    monkeypatch.setattr(
        runtime_service_graph_module,
        "CodexStdioTransport",
        _fake_stdio_transport,
        raising=False,
    )
    monkeypatch.setattr(
        runtime_service_graph_module,
        "CodexAppServerAdapter",
        lambda transport: SimpleNamespace(transport=transport),
    )

    adapter = runtime_service_graph_module._build_default_executor_runtime_port()

    assert adapter.transport == "stdio-transport"
    active_install = ExecutorRuntimeService(state_store=state_store).get_active_sidecar_install(
        runtime_family="codex",
    )
    assert active_install is not None
    assert active_install.version == "0.10.0"
    assert captured["stdio_kwargs"]["codex_command"] == (
        active_install.executable_path,
        "app-server",
    )
