# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.app.routers.capabilities import router as capabilities_router
from copaw.capabilities import CapabilityMount, CapabilityService


def build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(capabilities_router)
    app.state.capability_service = CapabilityService()
    return app


_SHELL_MOUNT = CapabilityMount(
    id="tool:execute_shell_command",
    name="execute_shell_command",
    summary="Run shell commands.",
    kind="local-tool",
    source_kind="tool",
    risk_level="guarded",
    risk_description="执行任意 shell 命令，可能修改文件系统",
    environment_requirements=["workspace"],
    environment_description="需要工作目录环境来执行命令",
    evidence_contract=["shell-command", "stdout", "stderr"],
    evidence_description="记录命令内容、标准输出和标准错误",
    tags=["shell", "execution"],
)

_SKILL_MOUNT = CapabilityMount(
    id="skill:research",
    name="research",
    summary="Research workflow",
    kind="skill-bundle",
    source_kind="skill",
    risk_level="guarded",
    risk_description="技能包可能执行脚本或访问外部资源",
    environment_requirements=["workspace"],
    environment_description="需要工作目录来访问引用文件",
    evidence_contract=["capability-call", "workspace-trace"],
    evidence_description="记录技能调用和工作目录变更轨迹",
    enabled=False,
    tags=["skill"],
)

_MCP_MOUNT = CapabilityMount(
    id="mcp:browser",
    name="browser",
    summary="Remote browser MCP",
    kind="remote-mcp",
    source_kind="mcp",
    risk_level="guarded",
    risk_description="远程 MCP 调用涉及外部服务通信",
    environment_requirements=["network"],
    environment_description="需要网络连接以访问远程 MCP 端点",
    evidence_contract=["mcp-call", "remote-tool-trace"],
    evidence_description="记录 MCP 调用请求和远程工具执行轨迹",
    tags=["mcp", "sse"],
)


def _patch_loaders(monkeypatch):
    from copaw.capabilities import registry as registry_module

    monkeypatch.setattr(
        registry_module,
        "list_tool_capabilities",
        lambda: [_SHELL_MOUNT],
    )
    monkeypatch.setattr(
        registry_module,
        "list_skill_capabilities",
        lambda: [_SKILL_MOUNT],
    )
    monkeypatch.setattr(
        registry_module,
        "list_mcp_capabilities",
        lambda: [_MCP_MOUNT],
    )
    monkeypatch.setattr(
        registry_module,
        "list_system_capabilities",
        lambda: [],
    )


def test_capabilities_api_lists_unified_mounts(monkeypatch) -> None:
    _patch_loaders(monkeypatch)
    client = TestClient(build_app())
    response = client.get("/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload] == [
        "tool:execute_shell_command",
        "mcp:browser",
        "skill:research",
    ]


def test_capabilities_api_filters_enabled_and_summarizes(monkeypatch) -> None:
    _patch_loaders(monkeypatch)
    client = TestClient(build_app())

    filtered = client.get("/capabilities", params={"enabled_only": True})
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()] == [
        "tool:execute_shell_command",
        "mcp:browser",
    ]

    summary = client.get("/capabilities/summary")
    assert summary.status_code == 200
    data = summary.json()
    assert data["total"] == 3
    assert data["enabled"] == 2
    assert data["by_kind"] == {
        "local-tool": 1,
        "remote-mcp": 1,
        "skill-bundle": 1,
    }
    assert data["by_source"] == {
        "mcp": 1,
        "skill": 1,
        "tool": 1,
    }


def test_capabilities_api_get_single_mount(monkeypatch) -> None:
    """GET /capabilities/{id} 返回单个能力详情。"""
    _patch_loaders(monkeypatch)
    client = TestClient(build_app())

    response = client.get("/capabilities/tool:execute_shell_command")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "tool:execute_shell_command"
    assert data["source_kind"] == "tool"
    assert data["risk_description"] == "执行任意 shell 命令，可能修改文件系统"
    assert data["environment_description"] == "需要工作目录环境来执行命令"
    assert data["evidence_description"] == "记录命令内容、标准输出和标准错误"
    assert "shell" in data["tags"]
    assert "execution" in data["tags"]


def test_capabilities_api_get_single_mount_404(monkeypatch) -> None:
    """GET /capabilities/{id} 不存在时返回 404。"""
    _patch_loaders(monkeypatch)
    client = TestClient(build_app())

    response = client.get("/capabilities/tool:nonexistent")
    assert response.status_code == 404


def test_capabilities_new_fields_are_present(monkeypatch) -> None:
    """确认新增字段在列表返回中存在。"""
    _patch_loaders(monkeypatch)
    client = TestClient(build_app())

    response = client.get("/capabilities")
    assert response.status_code == 200
    for item in response.json():
        assert "source_kind" in item
        assert "risk_description" in item
        assert "environment_description" in item
        assert "evidence_description" in item
        assert "tags" in item
        assert item["source_kind"] in ("tool", "skill", "mcp", "system")
