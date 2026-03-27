# -*- coding: utf-8 -*-
from __future__ import annotations

from ...config import load_config
from ..models import CapabilityMount


def list_mcp_capabilities() -> list[CapabilityMount]:
    config = load_config()
    mounts: list[CapabilityMount] = []
    for key, client in config.mcp.clients.items():
        if client.transport == "stdio":
            requirements = ["process", "workspace"]
            env_description = "需要本地进程和工作目录来启动 stdio MCP 服务"
        else:
            requirements = ["network"]
            env_description = f"需要网络连接以访问远程 MCP 端点 ({client.transport})"

        summary = client.description or f"MCP client via {client.transport}"

        tags: list[str] = ["mcp", client.transport]
        if client.enabled:
            tags.append("active")

        mounts.append(
            CapabilityMount(
                id=f"mcp:{key}",
                name=client.name,
                summary=summary,
                kind="remote-mcp",
                source_kind="mcp",
                risk_level="guarded",
                risk_description="远程 MCP 调用涉及外部服务通信，结果不可完全预测",
                environment_requirements=requirements,
                environment_description=env_description,
                role_access_policy=["mcp-enabled"] if client.enabled else ["mcp-disabled"],
                evidence_contract=["mcp-call", "remote-tool-trace"],
                evidence_description="记录 MCP 调用请求和远程工具执行轨迹",
                executor_ref=client.command or client.url or key,
                provider_ref=client.transport,
                replay_support=False,
                enabled=bool(client.enabled),
                tags=tags,
                metadata={
                    "key": key,
                    "transport": client.transport,
                    "cwd": client.cwd,
                },
            ),
        )
    mounts.sort(key=lambda item: item.id)
    return mounts
