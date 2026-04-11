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
        create_agent,
    ) -> _ResidentQueryAgent:
        async with self._resident_agent_cache_lock:
            cached = self._resident_agents.get(cache_key)
            if cached is not None and cached.signature == signature:
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

            runtime_model_fingerprint = build_runtime_model_fingerprint()
        except Exception:
            runtime_model_fingerprint = ""
        payload = {
            "owner_agent_id": owner_agent_id,
            "actor_key": _first_non_empty(actor_key),
            "actor_fingerprint": _first_non_empty(actor_fingerprint),
            "prompt_appendix": prompt_appendix or "",
            "tool_capability_ids": sorted(tool_capability_ids or []),
            "skill_names": sorted(skill_names or []),
            "mcp_client_keys": sorted(mcp_client_keys) if isinstance(mcp_client_keys, list) else None,
            "system_capability_ids": sorted(system_capability_ids or []),
            "runtime_model_fingerprint": runtime_model_fingerprint,
        }
        return hashlib.sha1(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"),
        ).hexdigest()

    def _acquire_actor_runtime_lease(
        self,
        *,
        agent_id: str,
        task_id: str | None,
        conversation_thread_id: str | None,
    ) -> Any | None:
        if self._should_bypass_actor_runtime_lease(
            agent_id=agent_id,
            task_id=task_id,
        ):
            return None
        if self._environment_service is None:
            return None
        acquire = getattr(self._environment_service, "acquire_actor_lease", None)
        if not callable(acquire):
            return None
        try:
            return acquire(
                agent_id=agent_id,
                owner=_first_non_empty(conversation_thread_id, task_id, agent_id) or agent_id,
                ttl_seconds=180,
                metadata={
                    "task_id": task_id,
                    "thread_id": conversation_thread_id,
                    "lease_kind": "interactive-query",
                },
            )
        except RuntimeError as exc:
            message = str(exc).lower()
            if "not available" in message:
                return None
            logger.info(
                "Actor runtime lease acquisition blocked for '%s': %s",
                agent_id,
                exc,
            )
            raise
        except Exception:
            logger.exception("Actor runtime lease acquisition failed")
            return None

    def _should_bypass_actor_runtime_lease(
        self,
        *,
        agent_id: str,
        task_id: str | None,
    ) -> bool:
        if not task_id:
            return False
        runtime_repository = getattr(self, "_agent_runtime_repository", None)
        if runtime_repository is None:
            return False
        get_runtime = getattr(runtime_repository, "get_runtime", None)
        if not callable(get_runtime):
            return False
        try:
            runtime = get_runtime(agent_id)
        except Exception:
            logger.debug("Failed to resolve runtime before actor lease acquisition.", exc_info=True)
            return False
        if runtime is None:
            return False
        current_task_id = _first_non_empty(getattr(runtime, "current_task_id", None))
        current_mailbox_id = _first_non_empty(getattr(runtime, "current_mailbox_id", None))
        return current_task_id == task_id and current_mailbox_id is not None

    def _heartbeat_actor_runtime_lease(self, lease: Any | None) -> None:
        if lease is None or self._environment_service is None:
            return
        heartbeat = getattr(self._environment_service, "heartbeat_actor_lease", None)
        if not callable(heartbeat):
            return
        try:
            heartbeat(lease.id, lease_token=lease.lease_token, ttl_seconds=180)
        except Exception:
            logger.exception("Actor runtime lease heartbeat failed")

    def _release_actor_runtime_lease(self, lease: Any | None) -> None:
        if lease is None or self._environment_service is None:
            return
        release = getattr(self._environment_service, "release_actor_lease", None)
        if not callable(release):
            return
        try:
            release(lease.id, lease_token=lease.lease_token, reason="interactive query completed")
        except Exception:
            logger.exception("Actor runtime lease release failed")

    def _build_query_lease_heartbeat(
        self,
        *,
        session_lease: Any | None,
        actor_lease: Any | None,
    ) -> LeaseHeartbeat | None:
        if session_lease is None and actor_lease is None:
            return None
        lease_state = {
            "session_lease": session_lease,
            "actor_lease": actor_lease,
        }
        return LeaseHeartbeat(
            label="interactive-query",
            interval_seconds=self._lease_heartbeat_interval_seconds,
            heartbeat=lambda: lease_state.__setitem__(
                "session_lease",
                self._heartbeat_query_leases(
                    session_lease=lease_state.get("session_lease"),
                    actor_lease=lease_state.get("actor_lease"),
                ),
            ),
        )

    def _heartbeat_query_leases(
        self,
        *,
        session_lease: Any | None,
        actor_lease: Any | None,
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
        self._heartbeat_actor_runtime_lease(actor_lease)
        return session_lease
