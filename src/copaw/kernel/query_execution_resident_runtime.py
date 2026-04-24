# -*- coding: utf-8 -*-
from __future__ import annotations

from .query_execution_shared import *  # noqa: F401,F403


class _QueryExecutionResidentRuntimeMixin:
    @staticmethod
    def _missing_session_lease_error(exc: Exception) -> bool:
        if not isinstance(exc, KeyError):
            return False
        message = str(exc).lower()
        return "session" in message and "not found" in message

    async def _get_or_create_resident_agent(
        self,
        *,
        cache_key: str,
        signature: str,
        session_id: str,
        user_id: str,
        channel: str,
        owner_agent_id: str,
        prompt_appendix: str | None,
        extra_tool_functions: list[object] | None,
        create_agent,
    ) -> _ResidentQueryAgent:
        async with self._resident_agent_cache_lock:
            cached = self._resident_agents.get(cache_key)
            if cached is not None and cached.signature == signature:
                refresh_runtime_bindings = getattr(cached.agent, "refresh_runtime_bindings", None)
                if callable(refresh_runtime_bindings):
                    await refresh_runtime_bindings(
                        prompt_appendix=prompt_appendix,
                        extra_tool_functions=extra_tool_functions,
                    )
                else:
                    set_prompt_appendix = getattr(cached.agent, "set_prompt_appendix", None)
                    if callable(set_prompt_appendix):
                        set_prompt_appendix(prompt_appendix)
                    cached.agent.rebuild_sys_prompt()
                return cached
            agent = create_agent()
            await agent.register_mcp_clients()
            agent.set_console_output_enabled(enabled=False)
            try:
                await self._session_backend.load_session_state(
                    session_id=session_id,
                    user_id=user_id,
                    agent=agent,
                )
            except KeyError as exc:
                logger.warning(
                    "load_session_state skipped (state schema mismatch): %s; "
                    "will save fresh state on completion to recover file",
                    exc,
                )
            resident = _ResidentQueryAgent(
                cache_key=cache_key,
                signature=signature,
                session_id=session_id,
                user_id=user_id,
                channel=channel,
                owner_agent_id=owner_agent_id,
                agent=agent,
            )
            self._resident_agents[cache_key] = resident
            return resident

    def _resident_agent_cache_key(
        self,
        *,
        channel: str,
        session_id: str,
        user_id: str,
        owner_agent_id: str,
    ) -> str:
        return f"{channel}:{session_id}:{user_id}:{owner_agent_id}"

    def _resident_agent_signature(
        self,
        *,
        owner_agent_id: str,
        actor_key: object | None,
        actor_fingerprint: object | None,
        prompt_appendix: str | None,
        tool_capability_ids: set[str] | None,
        skill_names: set[str] | None,
        mcp_client_keys: list[str] | None,
        system_capability_ids: set[str] | None,
    ) -> str:
        try:
            from copaw.agents.model_factory import build_runtime_model_fingerprint

            runtime_model_fingerprint = build_runtime_model_fingerprint(
                runtime_provider=self._provider_manager,
            )
        except Exception:
            runtime_model_fingerprint = ""
        payload = {
            "owner_agent_id": owner_agent_id,
            "actor_key": _first_non_empty(actor_key),
            "actor_fingerprint": _first_non_empty(actor_fingerprint),
            "tool_capability_ids": sorted(tool_capability_ids or []),
            "skill_names": sorted(skill_names or []),
            "mcp_client_keys": sorted(mcp_client_keys) if isinstance(mcp_client_keys, list) else None,
            "system_capability_ids": sorted(system_capability_ids or []),
            "runtime_model_fingerprint": runtime_model_fingerprint,
        }
        return hashlib.sha1(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"),
        ).hexdigest()

    def _build_query_lease_heartbeat(
        self,
        *,
        session_lease: Any | None,
    ) -> LeaseHeartbeat | None:
        if session_lease is None:
            return None
        lease_state = {"session_lease": session_lease}
        return LeaseHeartbeat(
            label="interactive-query",
            interval_seconds=self._lease_heartbeat_interval_seconds,
            heartbeat=lambda: lease_state.__setitem__(
                "session_lease",
                self._heartbeat_query_leases(
                    session_lease=lease_state.get("session_lease"),
                ),
            ),
        )

    def _heartbeat_query_leases(
        self,
        *,
        session_lease: Any | None,
    ) -> Any | None:
        if session_lease is not None and self._environment_service is not None:
            try:
                self._environment_service.heartbeat_session_lease(
                    session_lease.id,
                    lease_token=session_lease.lease_token or "",
                )
            except Exception as exc:
                if self._missing_session_lease_error(exc):
                    session_lease = None
                else:
                    raise
        return session_lease
