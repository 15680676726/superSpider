from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_build_github_python_project_transport_chain_prefers_git_then_codeload_then_archive() -> None:
    from copaw.capabilities.project_donor_contracts import (
        build_github_python_project_transport_chain,
    )

    transports = build_github_python_project_transport_chain(
        source_url="https://github.com/HKUDS/OpenSpace",
        ref="main",
    )

    assert [item.kind for item in transports] == [
        "git",
        "codeload-tar-gz",
        "github-archive-zip",
    ]
    assert transports[0].package_ref == "git+https://github.com/HKUDS/OpenSpace.git@main"
    assert (
        transports[1].package_ref
        == "https://codeload.github.com/HKUDS/OpenSpace/tar.gz/refs/heads/main"
    )
    assert (
        transports[2].package_ref
        == "https://github.com/HKUDS/OpenSpace/archive/refs/heads/main.zip"
    )


def test_parse_pip_report_requested_distribution_returns_requested_project() -> None:
    from copaw.capabilities.project_donor_contracts import (
        parse_pip_install_report_requested_distribution,
    )

    payload = {
        "install": [
            {
                "requested": False,
                "metadata": {"name": "click", "version": "8.3.2"},
            },
            {
                "requested": True,
                "metadata": {"name": "openspace", "version": "0.1.0"},
                "download_info": {
                    "url": "https://codeload.github.com/HKUDS/OpenSpace/tar.gz/refs/heads/main",
                },
            },
        ],
    }

    resolved = parse_pip_install_report_requested_distribution(payload)

    assert resolved is not None
    assert resolved.distribution_name == "openspace"
    assert resolved.distribution_version == "0.1.0"
    assert (
        resolved.download_url
        == "https://codeload.github.com/HKUDS/OpenSpace/tar.gz/refs/heads/main"
    )


def test_resolve_installed_python_project_contract_prefers_console_script_path(
    monkeypatch,
    tmp_path,
) -> None:
    from copaw.capabilities.project_donor_contracts import (
        resolve_installed_python_project_contract,
    )

    monkeypatch.setattr(
        "copaw.capabilities.project_donor_contracts.inspect_installed_python_distribution",
        lambda **kwargs: {
            "distribution_name": "openspace",
            "package_version": "0.1.0",
            "entry_points": [
                {
                    "group": "console_scripts",
                    "name": "openspace",
                    "value": "openspace.__main__:run_main",
                },
            ],
        },
    )

    scripts_dir = tmp_path / "Scripts"
    scripts_dir.mkdir()
    (scripts_dir / "openspace.exe").write_text("", encoding="utf-8")

    contract = resolve_installed_python_project_contract(
        python_path="D:/fake/.venv/Scripts/python.exe",
        scripts_dir=str(scripts_dir),
        distribution_name="openspace",
        capability_kind="runtime-component",
    )

    assert contract.install_name == "openspace"
    assert contract.package_version == "0.1.0"
    assert contract.entry_module == "openspace"
    assert contract.console_script == "openspace"
    assert contract.execute_command.endswith('Scripts\\openspace.exe"')
    assert contract.healthcheck_command.endswith('Scripts\\openspace.exe" --help')


def test_resolve_installed_python_project_contract_exposes_runtime_contract_prediction(
    monkeypatch,
    tmp_path,
) -> None:
    from copaw.capabilities.project_donor_contracts import (
        resolve_installed_python_project_contract,
    )

    monkeypatch.setattr(
        "copaw.capabilities.project_donor_contracts.inspect_installed_python_distribution",
        lambda **kwargs: {
            "distribution_name": "openspace",
            "package_version": "0.1.0",
            "entry_points": [
                {
                    "group": "console_scripts",
                    "name": "openspace",
                    "value": "openspace.__main__:run_main",
                },
            ],
        },
    )

    scripts_dir = tmp_path / "Scripts"
    scripts_dir.mkdir()
    (scripts_dir / "openspace.exe").write_text("", encoding="utf-8")

    contract = resolve_installed_python_project_contract(
        python_path="D:/fake/.venv/Scripts/python.exe",
        scripts_dir=str(scripts_dir),
        distribution_name="openspace",
        capability_kind="runtime-component",
    )

    assert contract.runtime_kind == "service"
    assert contract.supported_actions == [
        "describe",
        "start",
        "healthcheck",
        "stop",
        "restart",
    ]
    assert contract.scope_policy == "session"
    assert contract.ready_probe_kind == "http"
    assert contract.stop_strategy == "terminate"
    assert contract.startup_entry_ref == 'script:openspace'
    assert contract.predicted_default_port == 7788
    assert contract.predicted_health_path == "/health"
    assert contract.environment_requirements == ["process", "network"]
    assert contract.evidence_contract == ["shell-command", "runtime-event"]


def test_resolve_installed_python_project_contract_prefers_service_entrypoint_for_runtime_components(
    monkeypatch,
    tmp_path,
) -> None:
    from copaw.capabilities.project_donor_contracts import (
        resolve_installed_python_project_contract,
    )

    monkeypatch.setattr(
        "copaw.capabilities.project_donor_contracts.inspect_installed_python_distribution",
        lambda **kwargs: {
            "distribution_name": "openspace",
            "package_version": "0.1.0",
            "entry_points": [
                {
                    "group": "console_scripts",
                    "name": "openspace",
                    "value": "openspace.__main__:run_main",
                },
                {
                    "group": "console_scripts",
                    "name": "openspace-dashboard",
                    "value": "openspace.dashboard_server:main",
                },
                {
                    "group": "console_scripts",
                    "name": "openspace-server",
                    "value": "openspace.local_server.main:main",
                },
                {
                    "group": "console_scripts",
                    "name": "openspace-mcp",
                    "value": "openspace.mcp_server:run_mcp_server",
                },
            ],
        },
    )

    scripts_dir = tmp_path / "Scripts"
    scripts_dir.mkdir()
    (scripts_dir / "openspace.exe").write_text("", encoding="utf-8")
    (scripts_dir / "openspace-dashboard.exe").write_text("", encoding="utf-8")
    (scripts_dir / "openspace-server.exe").write_text("", encoding="utf-8")
    (scripts_dir / "openspace-mcp.exe").write_text("", encoding="utf-8")

    contract = resolve_installed_python_project_contract(
        python_path="D:/fake/.venv/Scripts/python.exe",
        scripts_dir=str(scripts_dir),
        distribution_name="openspace",
        capability_kind="runtime-component",
    )

    assert contract.install_name == "openspace"
    assert contract.console_script == "openspace-dashboard"
    assert contract.entry_module == "openspace.dashboard_server"
    assert contract.execute_command.endswith('Scripts\\openspace-dashboard.exe"')
    assert contract.healthcheck_command.endswith(
        'Scripts\\openspace-dashboard.exe" --help'
    )
    assert contract.startup_entry_ref == "script:openspace-dashboard"
    assert contract.predicted_default_port == 7788
    assert contract.predicted_health_path == "/health"


def test_inspect_installed_python_distribution_reads_target_python_environment(
    monkeypatch,
) -> None:
    from copaw.capabilities.project_donor_contracts import (
        inspect_installed_python_distribution,
    )

    class _Completed:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = (
                '{"distribution_name":"openspace","package_version":"0.1.0",'
                '"entry_points":[{"group":"console_scripts","name":"openspace",'
                '"value":"openspace.__main__:run_main"}]}'
            )
            self.stderr = ""

    calls: list[list[str]] = []

    def _fake_run(command, **kwargs):
        calls.append(list(command))
        return _Completed()

    monkeypatch.setattr(
        "copaw.capabilities.project_donor_contracts.subprocess.run",
        _fake_run,
    )

    payload = inspect_installed_python_distribution(
        python_path="D:/fake/.venv/Scripts/python.exe",
        distribution_name="openspace",
    )

    assert payload["distribution_name"] == "openspace"
    assert payload["package_version"] == "0.1.0"
    assert calls[0][0] == "D:/fake/.venv/Scripts/python.exe"
    assert calls[0][-1] == "openspace"


@pytest.mark.asyncio
async def test_install_github_python_project_retries_transport_chain_before_saving(monkeypatch) -> None:
    from copaw.app.routers import capability_market as capability_market_module
    from copaw.config.config import Config

    saved: dict[str, object] = {}

    monkeypatch.setattr(
        capability_market_module,
        "load_config",
        lambda: Config(),
    )
    monkeypatch.setattr(
        capability_market_module,
        "save_config",
        lambda config: saved.setdefault("config", config),
    )
    monkeypatch.setattr(
        capability_market_module,
        "_resolve_github_default_ref",
        lambda source_url: "main",
    )
    monkeypatch.setattr(
        capability_market_module,
        "_prepare_external_project_environment",
        lambda **kwargs: {
            "environment_root": "D:/fake/external/runtime-openspace",
            "python_path": "D:/fake/external/runtime-openspace/.venv/Scripts/python.exe",
            "scripts_dir": "D:/fake/external/runtime-openspace/.venv/Scripts",
        },
    )
    attempts: list[str] = []
    install_commands: list[list[str]] = []
    verify_calls: list[tuple[str, int]] = []

    async def _fake_install_attempt(*, command_parts, timeout, report_path):
        _ = timeout
        install_commands.append(list(command_parts))
        package_ref = command_parts[-1]
        attempts.append(package_ref)
        if "codeload.github.com" in package_ref:
            return {
                "success": False,
                "summary": "codeload transport failed",
                "stdout": "",
                "stderr": "",
                "returncode": 1,
            }
        return {
            "success": True,
            "summary": "installed via archive",
            "stdout": "",
            "stderr": "",
            "returncode": 0,
            "report_path": report_path,
        }

    monkeypatch.setattr(
        capability_market_module,
        "_run_external_project_install_attempt",
        _fake_install_attempt,
    )
    monkeypatch.setattr(
        capability_market_module,
        "_load_pip_install_report",
        lambda report_path: {
            "install": [
                {
                    "requested": True,
                    "metadata": {"name": "openspace", "version": "0.1.0"},
                    "download_info": {
                        "url": "https://github.com/HKUDS/OpenSpace/archive/refs/heads/main.zip",
                    },
                },
            ],
        },
    )
    monkeypatch.setattr(
        capability_market_module,
        "resolve_installed_python_project_contract",
        lambda **kwargs: SimpleNamespace(
            install_name="openspace",
            distribution_name="openspace",
            package_version="0.1.0",
            entry_module="openspace",
            console_script="openspace",
            execute_command='"D:/fake/external/runtime-openspace/.venv/Scripts/openspace.exe" --help',
            healthcheck_command='"D:/fake/external/runtime-openspace/.venv/Scripts/openspace.exe" --help',
            runtime_kind="service",
            supported_actions=[
                "describe",
                "start",
                "healthcheck",
                "stop",
                "restart",
                ],
                scope_policy="session",
                ready_probe_kind="http",
                ready_probe_config={
                    "command": "",
                    "predicted_default_port": 7788,
                    "predicted_health_path": "/health",
                    "url": "http://127.0.0.1:7788/health",
                },
            stop_strategy="terminate",
            startup_entry_ref="script:openspace",
            environment_requirements=["workspace", "process"],
            evidence_contract=["shell-command", "runtime-event"],
            predicted_default_port=7788,
            predicted_health_path="/health",
            metadata={"entry_source": "console-script", "script_path": "D:/fake/external/runtime-openspace/.venv/Scripts/openspace.exe"},
            ),
        )
    monkeypatch.setattr(
        capability_market_module,
        "_run_external_project_shell_command",
        lambda command, timeout: verify_calls.append((command, timeout))
        or capability_market_module.asyncio.sleep(0, result=(True, "ok")),
    )

    result = await capability_market_module._install_external_project_capability(
        source_url="https://github.com/HKUDS/OpenSpace",
        version="",
        capability_kind="runtime-component",
        entry_module=None,
        execute_command=None,
        healthcheck_command=None,
        enable=True,
        overwrite=True,
    )

    assert attempts == [
        "https://codeload.github.com/HKUDS/OpenSpace/tar.gz/refs/heads/main",
        "https://github.com/HKUDS/OpenSpace/archive/refs/heads/main.zip",
    ]
    assert install_commands[0][0] == "D:/fake/external/runtime-openspace/.venv/Scripts/python.exe"
    assert "--user" not in install_commands[0]
    assert result["installed"] is True
    assert result["name"] == "openspace"
    assert result["capability_kind"] == "runtime-component"
    assert result["installed_capability_ids"] == ["runtime:openspace"]
    assert result["runtime_contract"]["runtime_kind"] == "service"
    assert result["runtime_contract"]["predicted_default_port"] == 7788
    assert "port" not in result["runtime_contract"]
    assert "health_url" not in result["runtime_contract"]
    assert verify_calls == []

    config = saved["config"]
    package = config.external_capability_packages["runtime:openspace"]
    assert package.package_ref == "https://github.com/HKUDS/OpenSpace/archive/refs/heads/main.zip"
    assert package.package_kind == "github-archive-zip"
    assert package.environment_root == "D:/fake/external/runtime-openspace"
    assert package.python_path == "D:/fake/external/runtime-openspace/.venv/Scripts/python.exe"
    assert package.scripts_dir == "D:/fake/external/runtime-openspace/.venv/Scripts"
    assert package.metadata["distribution_name"] == "openspace"
    assert package.metadata["entry_source"] == "console-script"
    assert package.runtime_kind == "service"
    assert package.supported_actions == [
        "describe",
        "start",
        "healthcheck",
        "stop",
        "restart",
    ]
    assert package.scope_policy == "session"
    assert package.ready_probe_kind == "http"
    assert package.ready_probe_config["predicted_default_port"] == 7788
    assert package.stop_strategy == "terminate"
    assert package.startup_entry_ref == "script:openspace"


@pytest.mark.asyncio
async def test_install_external_project_persists_adapter_contract_when_surface_is_eligible(
    monkeypatch,
) -> None:
    from copaw.app.routers import capability_market as capability_market_module
    from copaw.config.config import Config

    saved: dict[str, object] = {}

    monkeypatch.setattr(
        capability_market_module,
        "load_config",
        lambda: Config(),
    )
    monkeypatch.setattr(
        capability_market_module,
        "save_config",
        lambda config: saved.setdefault("config", config),
    )
    monkeypatch.setattr(
        capability_market_module,
        "_resolve_github_default_ref",
        lambda source_url: "main",
    )
    monkeypatch.setattr(
        capability_market_module,
        "_prepare_external_project_environment",
        lambda **kwargs: {
            "environment_root": "D:/fake/external/adapter-openspace",
            "python_path": "D:/fake/external/adapter-openspace/.venv/Scripts/python.exe",
            "scripts_dir": "D:/fake/external/adapter-openspace/.venv/Scripts",
        },
    )

    async def _fake_install_attempt(*, command_parts, timeout, report_path):
        _ = (command_parts, timeout)
        return {
            "success": True,
            "summary": "installed via archive",
            "stdout": "",
            "stderr": "",
            "returncode": 0,
            "report_path": report_path,
        }

    monkeypatch.setattr(
        capability_market_module,
        "_run_external_project_install_attempt",
        _fake_install_attempt,
    )
    monkeypatch.setattr(
        capability_market_module,
        "_load_pip_install_report",
        lambda report_path: {
            "install": [
                {
                    "requested": True,
                    "metadata": {"name": "openspace", "version": "0.1.0"},
                    "download_info": {
                        "url": "https://github.com/HKUDS/OpenSpace/archive/refs/heads/main.zip",
                    },
                },
            ],
        },
    )
    monkeypatch.setattr(
        capability_market_module,
        "resolve_installed_python_project_contract",
        lambda **kwargs: SimpleNamespace(
            install_name="openspace",
            distribution_name="openspace",
            package_version="0.1.0",
            entry_module="openspace.mcp_server",
            console_script="openspace-mcp",
            execute_command='"D:/fake/external/adapter-openspace/.venv/Scripts/openspace-mcp.exe"',
            healthcheck_command='"D:/fake/external/adapter-openspace/.venv/Scripts/openspace-mcp.exe" --help',
            runtime_kind="cli",
            supported_actions=["describe", "run"],
            scope_policy="seat",
            ready_probe_kind="none",
            ready_probe_config={},
            stop_strategy="terminate",
            startup_entry_ref="script:openspace-mcp",
            environment_requirements=["workspace", "process", "desktop-session"],
            evidence_contract=["shell-command", "runtime-event", "environment-session"],
            predicted_default_port=None,
            predicted_health_path=None,
            metadata={
                "mcp_server_ref": "mcp:openspace",
                "mcp_tools": [
                    {
                        "action_id": "execute_task",
                        "tool_name": "execute_task",
                        "input_schema": {"type": "object"},
                    },
                ],
            },
        ),
    )

    result = await capability_market_module._install_external_project_capability(
        source_url="https://github.com/HKUDS/OpenSpace",
        version="",
        capability_kind="adapter",
        entry_module=None,
        execute_command=None,
        healthcheck_command=None,
        enable=True,
        overwrite=True,
    )

    package = saved["config"].external_capability_packages["adapter:openspace"]
    assert result["installed"] is True
    assert result["installed_capability_ids"] == ["adapter:openspace"]
    assert package.intake_protocol_kind == "native_mcp"
    assert package.call_surface_ref == "mcp:openspace"
    assert package.adapter_contract["transport_kind"] == "mcp"
    assert package.adapter_contract["actions"][0]["action_id"] == "execute_task"
