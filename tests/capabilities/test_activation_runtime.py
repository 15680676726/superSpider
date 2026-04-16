# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio


def test_activation_status_set_is_fixed_contract() -> None:
    from copaw.capabilities.activation_models import ACTIVATION_STATUSES

    assert ACTIVATION_STATUSES == (
        "installed",
        "activating",
        "ready",
        "healing",
        "waiting_human",
        "blocked",
    )


def test_activation_reason_taxonomy_is_normalized_contract() -> None:
    from copaw.capabilities.activation_models import normalize_activation_reason

    assert normalize_activation_reason("dependency_missing") == "dependency_missing"
    assert normalize_activation_reason("adapter_offline") == "adapter_offline"
    assert normalize_activation_reason("session_unbound") == "session_unbound"
    assert normalize_activation_reason("host_unavailable") == "host_unavailable"
    assert normalize_activation_reason("token_expired") == "token_expired"
    assert normalize_activation_reason("scope_unbound") == "scope_unbound"
    assert normalize_activation_reason("runtime_unavailable") == "runtime_unavailable"
    assert (
        normalize_activation_reason("policy_retryable_block")
        == "policy_retryable_block"
    )
    assert normalize_activation_reason("human_auth_required") == "human_auth_required"
    assert normalize_activation_reason("captcha_required") == "captcha_required"
    assert normalize_activation_reason("two_factor_required") == "two_factor_required"
    assert (
        normalize_activation_reason("explicit_human_confirm_required")
        == "explicit_human_confirm_required"
    )
    assert normalize_activation_reason("host_open_required") == "host_open_required"
    assert normalize_activation_reason("policy_blocked") == "policy_blocked"
    assert normalize_activation_reason("unsupported_host") == "unsupported_host"
    assert (
        normalize_activation_reason("invalid_capability_contract")
        == "invalid_capability_contract"
    )
    assert normalize_activation_reason("broken_installation") == "broken_installation"


def test_activation_runtime_resolves_reads_heals_and_rereads_before_ready() -> None:
    from copaw.capabilities.activation_models import ActivationRequest, ActivationState
    from copaw.capabilities.activation_runtime import ActivationRuntime

    class SequencedStrategy:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self._read_count = 0

        async def resolve_context(self, request: ActivationRequest) -> dict[str, object]:
            self.calls.append(f"resolve:{request.subject_id}")
            return {"subject_id": request.subject_id}

        async def read_state(self, context: dict[str, object]) -> ActivationState:
            self._read_count += 1
            self.calls.append(f"read:{self._read_count}")
            if self._read_count == 1:
                return ActivationState(
                    status="blocked",
                    reason="session_unbound",
                    auto_heal_supported=True,
                    runtime={"read": 1, "subject_id": context["subject_id"]},
                )
            return ActivationState(
                status="ready",
                runtime={"read": 2, "subject_id": context["subject_id"]},
            )

        async def remediate(
            self,
            context: dict[str, object],
            state: ActivationState,
        ) -> list[str]:
            self.calls.append(f"heal:{state.reason}:{context['subject_id']}")
            return ["ensure-session"]

    runtime = ActivationRuntime()
    strategy = SequencedStrategy()
    result = asyncio.run(
        runtime.activate(
            ActivationRequest(
                subject_id="browser-companion",
                activation_class="host-attached",
            ),
            strategy,
        )
    )

    assert strategy.calls == [
        "resolve:browser-companion",
        "read:1",
        "heal:session_unbound:browser-companion",
        "read:2",
    ]
    assert result.status == "ready"
    assert result.operations == ["ensure-session"]
    assert result.auto_heal_attempted is True
    assert result.runtime["read"] == 2


def test_activation_runtime_does_not_assume_ready_without_fresh_reread() -> None:
    from copaw.capabilities.activation_models import ActivationRequest, ActivationState
    from copaw.capabilities.activation_runtime import ActivationRuntime

    class StillBlockedStrategy:
        async def resolve_context(self, request: ActivationRequest) -> dict[str, object]:
            return {"subject_id": request.subject_id}

        async def read_state(self, context: dict[str, object]) -> ActivationState:
            return ActivationState(
                status="blocked",
                reason="session_unbound",
                auto_heal_supported=True,
                runtime={"subject_id": context["subject_id"]},
            )

        async def remediate(
            self,
            context: dict[str, object],
            state: ActivationState,
        ) -> list[str]:
            _ = context
            _ = state
            return ["ensure-session"]

    runtime = ActivationRuntime()
    result = asyncio.run(
        runtime.activate(
            ActivationRequest(
                subject_id="browser-companion",
                activation_class="host-attached",
            ),
            StillBlockedStrategy(),
        )
    )

    assert result.status == "blocked"
    assert result.reason == "session_unbound"
    assert result.auto_heal_attempted is True
    assert result.operations == ["ensure-session"]


def test_auth_bound_activation_strategy_refreshes_expired_token_before_ready() -> None:
    from copaw.app.mcp.runtime_contract import build_mcp_runtime_record
    from copaw.capabilities.activation_models import ActivationRequest
    from copaw.capabilities.activation_runtime import ActivationRuntime
    from copaw.capabilities.activation_strategies import McpAuthActivationStrategy
    from copaw.config.config import MCPClientConfig

    config = MCPClientConfig(
        name="remote_drive",
        enabled=True,
        transport="streamable_http",
        url="https://mcp.example.com/drive",
        headers={"Authorization": "Bearer stale"},
    )

    class _FakeManager:
        def __init__(self) -> None:
            self._expired = True
            self.replace_calls: list[tuple[str, float]] = []

        async def get_runtime_record(self, key: str, *, scope_ref: str | None = None):
            _ = scope_ref
            if self._expired:
                return build_mcp_runtime_record(
                    key,
                    config,
                    status="failed",
                    init_mode="warn",
                    connect_timeout_seconds=30.0,
                    error="OAuth token expired",
                    connected=False,
                )
            return build_mcp_runtime_record(
                key,
                config,
                status="ready",
                init_mode="warn",
                connect_timeout_seconds=30.0,
                connected=True,
            )

        async def get_client_config(
            self,
            key: str,
            *,
            scope_ref: str | None = None,
        ):
            _ = (key, scope_ref)
            return config.model_copy(deep=True)

        async def replace_client(
            self,
            key: str,
            client_config: MCPClientConfig,
            timeout: float = 60.0,
        ) -> None:
            assert key == "remote_drive"
            assert client_config.transport == "streamable_http"
            self.replace_calls.append((key, timeout))
            self._expired = False

    manager = _FakeManager()
    result = asyncio.run(
        ActivationRuntime().activate(
            ActivationRequest(
                subject_id="mcp:remote_drive",
                activation_class="auth-bound",
            ),
            McpAuthActivationStrategy(
                client_key="remote_drive",
                mcp_manager=manager,
            ),
        )
    )

    assert result.status == "ready"
    assert result.auto_heal_attempted is True
    assert result.operations == ["refresh-auth-runtime"]
    assert manager.replace_calls == [("remote_drive", 60.0)]


def test_auth_bound_activation_strategy_stops_at_human_boundary() -> None:
    from copaw.app.mcp.runtime_contract import build_mcp_runtime_record
    from copaw.capabilities.activation_models import ActivationRequest
    from copaw.capabilities.activation_runtime import ActivationRuntime
    from copaw.capabilities.activation_strategies import McpAuthActivationStrategy
    from copaw.config.config import MCPClientConfig

    config = MCPClientConfig(
        name="remote_drive",
        enabled=True,
        transport="streamable_http",
        url="https://mcp.example.com/drive",
        headers={"Authorization": "Bearer pending"},
    )

    class _FakeManager:
        def __init__(self) -> None:
            self.replace_calls = 0

        async def get_runtime_record(self, key: str, *, scope_ref: str | None = None):
            _ = (key, scope_ref)
            return build_mcp_runtime_record(
                "remote_drive",
                config,
                status="failed",
                init_mode="warn",
                connect_timeout_seconds=30.0,
                error="Captcha required before OAuth re-consent",
                connected=False,
            )

        async def replace_client(
            self,
            key: str,
            client_config: MCPClientConfig,
            timeout: float = 60.0,
        ) -> None:
            _ = (key, client_config, timeout)
            self.replace_calls += 1

    manager = _FakeManager()
    result = asyncio.run(
        ActivationRuntime().activate(
            ActivationRequest(
                subject_id="mcp:remote_drive",
                activation_class="auth-bound",
            ),
            McpAuthActivationStrategy(
                client_key="remote_drive",
                mcp_manager=manager,
            ),
        )
    )

    assert result.status == "waiting_human"
    assert result.reason == "captcha_required"
    assert result.auto_heal_attempted is False
    assert manager.replace_calls == 0


def test_stateless_activation_strategy_reconnects_runtime_without_session_truth() -> None:
    from copaw.app.mcp.runtime_contract import build_mcp_runtime_record
    from copaw.capabilities.activation_models import ActivationRequest
    from copaw.capabilities.activation_runtime import ActivationRuntime
    from copaw.capabilities.activation_strategies import McpStatelessActivationStrategy
    from copaw.config.config import MCPClientConfig

    config = MCPClientConfig(
        name="filesystem",
        enabled=True,
        transport="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem"],
    )

    class _FakeManager:
        def __init__(self) -> None:
            self._ready = False
            self.replace_calls: list[tuple[str, float]] = []

        async def get_runtime_record(self, key: str, *, scope_ref: str | None = None):
            _ = scope_ref
            if not self._ready:
                return build_mcp_runtime_record(
                    key,
                    config,
                    status="failed",
                    init_mode="warn",
                    connect_timeout_seconds=15.0,
                    error="connection refused",
                    connected=False,
                )
            return build_mcp_runtime_record(
                key,
                config,
                status="ready",
                init_mode="warn",
                connect_timeout_seconds=15.0,
                connected=True,
            )

        async def get_client_config(
            self,
            key: str,
            *,
            scope_ref: str | None = None,
        ):
            _ = (key, scope_ref)
            return config.model_copy(deep=True)

        async def replace_client(
            self,
            key: str,
            client_config: MCPClientConfig,
            timeout: float = 60.0,
        ) -> None:
            assert key == "filesystem"
            assert client_config.command == "npx"
            self.replace_calls.append((key, timeout))
            self._ready = True

    manager = _FakeManager()
    result = asyncio.run(
        ActivationRuntime().activate(
            ActivationRequest(
                subject_id="mcp:filesystem",
                activation_class="stateless",
            ),
            McpStatelessActivationStrategy(
                client_key="filesystem",
                mcp_manager=manager,
            ),
        )
    )

    assert result.status == "ready"
    assert result.auto_heal_attempted is True
    assert result.operations == ["reconnect-runtime-client"]
    assert manager.replace_calls == [("filesystem", 60.0)]
