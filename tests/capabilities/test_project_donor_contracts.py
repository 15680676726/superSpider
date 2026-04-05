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
    assert contract.execute_command.endswith('Scripts\\openspace.exe" --help')
    assert contract.healthcheck_command.endswith('Scripts\\openspace.exe" --help')


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

    async def _fake_install_attempt(*, command_parts, timeout, report_path):
        _ = timeout
        install_commands.append(list(command_parts))
        package_ref = command_parts[-1]
        attempts.append(package_ref)
        if package_ref.startswith("git+https://"):
            return {
                "success": False,
                "summary": "git transport failed",
                "stdout": "",
                "stderr": "",
                "returncode": 1,
            }
        return {
            "success": True,
            "summary": "installed via codeload",
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
                        "url": "https://codeload.github.com/HKUDS/OpenSpace/tar.gz/refs/heads/main",
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
            metadata={"entry_source": "console-script", "script_path": "D:/fake/external/runtime-openspace/.venv/Scripts/openspace.exe"},
            ),
        )
    monkeypatch.setattr(
        capability_market_module,
        "_run_external_project_shell_command",
        lambda command, timeout: capability_market_module.asyncio.sleep(0, result=(True, "ok")),
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
        "git+https://github.com/HKUDS/OpenSpace.git@main",
        "https://codeload.github.com/HKUDS/OpenSpace/tar.gz/refs/heads/main",
    ]
    assert install_commands[0][0] == "D:/fake/external/runtime-openspace/.venv/Scripts/python.exe"
    assert "--user" not in install_commands[0]
    assert result["installed"] is True
    assert result["name"] == "openspace"
    assert result["capability_kind"] == "runtime-component"
    assert result["installed_capability_ids"] == ["runtime:openspace"]

    config = saved["config"]
    package = config.external_capability_packages["runtime:openspace"]
    assert package.package_ref == "https://codeload.github.com/HKUDS/OpenSpace/tar.gz/refs/heads/main"
    assert package.package_kind == "codeload-tar-gz"
    assert package.environment_root == "D:/fake/external/runtime-openspace"
    assert package.python_path == "D:/fake/external/runtime-openspace/.venv/Scripts/python.exe"
    assert package.scripts_dir == "D:/fake/external/runtime-openspace/.venv/Scripts"
    assert package.metadata["distribution_name"] == "openspace"
    assert package.metadata["entry_source"] == "console-script"
