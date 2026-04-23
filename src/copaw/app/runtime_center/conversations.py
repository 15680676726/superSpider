# -*- coding: utf-8 -*-
"""Formal runtime conversation facade for chat thread resolution."""
from __future__ import annotations

from typing import Any

from agentscope_runtime.engine.schemas.agent_schemas import Message
from pydantic import BaseModel, Field

from ...industry.identity import (
    EXECUTION_CORE_AGENT_ID,
    EXECUTION_CORE_ROLE_ID,
    is_execution_core_agent_id,
    is_execution_core_role_id,
    normalize_industry_role_id,
)
from ...utils.runtime_routes import (
    human_assist_task_current_route,
    human_assist_task_list_route,
    human_assist_task_route,
)
from ..channels.schema import DEFAULT_CHANNEL
from ..runtime_threads import (
    RuntimeThreadHistory,
    RuntimeThreadSpec,
    SessionRuntimeThreadHistoryReader,
)


class RuntimeConversationPayload(BaseModel):
    """Resolved runtime conversation payload for the frontend chat widget."""

    id: str
    name: str
    session_id: str
    user_id: str
    channel: str = Field(default=DEFAULT_CHANNEL)
    meta: dict[str, object] = Field(default_factory=dict)
    messages: list[Message] = Field(default_factory=list)


class RuntimeConversationFacade:
    """Resolve formal thread ids into canonical chat/session payloads."""

    def __init__(
        self,
        *,
        history_reader: SessionRuntimeThreadHistoryReader,
        industry_service: object | None = None,
        agent_profile_service: object | None = None,
        agent_thread_binding_repository: object | None = None,
        executor_runtime_service: object | None = None,
        human_assist_task_service: object | None = None,
        work_context_repository: object | None = None,
    ) -> None:
        self._history_reader = history_reader
        self._industry_service = industry_service
        self._agent_profile_service = agent_profile_service
        self._agent_thread_binding_repository = agent_thread_binding_repository
        self._executor_runtime_service = executor_runtime_service
        self._human_assist_task_service = human_assist_task_service
        self._work_context_repository = work_context_repository

    async def get_conversation(
        self,
        conversation_id: str,
        *,
        optional_meta_keys: set[str] | None = None,
    ) -> RuntimeConversationPayload:
        thread_spec = await self._resolve_thread_spec(conversation_id)
        history = await self._history_reader.get_thread_history(thread_spec)
        if not history.messages:
            history = RuntimeThreadHistory(
                messages=self._build_empty_thread_bootstrap_messages(thread_spec),
            )
        return RuntimeConversationPayload(
            id=thread_spec.id,
            name=thread_spec.name,
            session_id=thread_spec.session_id,
            user_id=thread_spec.user_id,
            channel=thread_spec.channel,
            meta=self._build_conversation_meta(
                thread_spec,
                optional_meta_keys=optional_meta_keys,
            ),
            messages=history.messages,
        )

    def _build_conversation_meta(
        self,
        thread_spec: RuntimeThreadSpec,
        *,
        optional_meta_keys: set[str] | None = None,
    ) -> dict[str, object]:
        meta = _compact_mapping(thread_spec.meta)
        requested_optional_meta = {
            item.strip()
            for item in (optional_meta_keys or set())
            if isinstance(item, str) and item.strip()
        }
        if "main_brain_commit" in requested_optional_meta:
            main_brain_commit = self._get_persisted_main_brain_commit(thread_spec)
            if main_brain_commit is not None:
                meta["main_brain_commit"] = main_brain_commit
        if "human_assist_task" in requested_optional_meta:
            human_assist_task = self._get_current_human_assist_task(thread_spec.id)
            if human_assist_task is not None:
                meta["human_assist_task"] = human_assist_task
                meta["human_assist_tasks_route"] = human_assist_task.get(
                    "tasks_route",
                ) or human_assist_task_list_route(chat_thread_id=thread_spec.id)
        return meta

    def _get_persisted_main_brain_commit(
        self,
        thread_spec: RuntimeThreadSpec,
    ) -> dict[str, object] | None:
        backend = getattr(self._history_reader, "_session_backend", None)
        merged_loader = getattr(backend, "load_merged_session_snapshot", None)
        if callable(merged_loader):
            payload = merged_loader(
                session_id=thread_spec.session_id,
                primary_user_id=thread_spec.user_id,
                allow_not_exist=True,
            )
        else:
            loader = getattr(backend, "load_session_snapshot", None)
            if not callable(loader):
                return None
            payload = loader(
                session_id=thread_spec.session_id,
                user_id=thread_spec.user_id,
                allow_not_exist=True,
            )
        if not isinstance(payload, dict):
            return None
        main_brain = payload.get("main_brain")
        commit_payload = (
            _compact_mapping(main_brain.get("phase2_commit"))
            if isinstance(main_brain, dict)
            else {}
        )
        if not commit_payload:
            query_runtime_state = payload.get("query_runtime_state")
            if isinstance(query_runtime_state, dict):
                commit_payload = _compact_mapping(query_runtime_state.get("commit_outcome"))
                if commit_payload:
                    commit_payload.setdefault("state_channel", "query_runtime_state")
                else:
                    commit_payload = _compact_mapping(
                        query_runtime_state.get("accepted_persistence"),
                    )
                    if commit_payload:
                        commit_payload.setdefault("state_channel", "query_runtime_state")
        if not commit_payload:
            return None
        control_thread_id = _first_non_empty(
            commit_payload.get("control_thread_id"),
            commit_payload.get("session_id"),
        )
        if control_thread_id is not None and control_thread_id != thread_spec.id:
            return None
        return commit_payload

    def _get_current_human_assist_task(
        self,
        chat_thread_id: str,
    ) -> dict[str, object] | None:
        service = self._human_assist_task_service
        getter = getattr(service, "get_visible_current_task", None)
        if not callable(getter):
            getter = getattr(service, "get_current_task", None)
        if not callable(getter):
            return None
        task = getter(chat_thread_id=chat_thread_id)
        if task is None:
            return None
        model_dump = getattr(task, "model_dump", None)
        payload = model_dump(mode="json") if callable(model_dump) else {}
        if not isinstance(payload, dict):
            return None
        task_id = str(payload.get("id") or "").strip()
        if task_id:
            payload["route"] = human_assist_task_route(task_id)
        payload["tasks_route"] = human_assist_task_list_route(
            chat_thread_id=chat_thread_id,
        )
        payload["current_route"] = human_assist_task_current_route(
            chat_thread_id=chat_thread_id,
        )
        return payload

    def _build_empty_thread_bootstrap_messages(
        self,
        thread_spec: RuntimeThreadSpec,
    ) -> list[Message]:
        if not thread_spec.id.startswith("industry-chat:"):
            return []
        if not (
            is_execution_core_role_id(thread_spec.meta.get("industry_role_id"))
            or is_execution_core_agent_id(
                _first_non_empty(thread_spec.meta.get("agent_id"), thread_spec.user_id),
            )
        ):
            return []
        industry_instance_id = _first_non_empty(
            thread_spec.meta.get("industry_instance_id"),
        )
        if industry_instance_id is None or self._industry_service is None:
            return []
        detail = _call_optional(
            self._industry_service,
            "get_instance_detail",
            industry_instance_id,
        )
        if not _industry_thread_waiting_for_kickoff(detail):
            return []
        return [
            _build_synthetic_assistant_message(
                message_id=f"synthetic:{thread_spec.id}:kickoff",
                text=_build_industry_kickoff_prompt(detail, thread_spec=thread_spec),
                metadata={
                    "synthetic": True,
                    "message_kind": "industry-kickoff-prompt",
                    "industry_instance_id": industry_instance_id,
                },
            ),
        ]

    async def _resolve_thread_spec(self, conversation_id: str) -> RuntimeThreadSpec:
        if conversation_id.startswith("actor-chat:"):
            raise ValueError(
                "不支持的运行会话编号。"
                "请改用 /chat 或 industry-chat:* 主脑控制线程。",
            )
        if conversation_id.startswith("agent-chat:"):
            raise ValueError(self._build_removed_agent_chat_detail(conversation_id))
        bound = self._resolve_bound_conversation(conversation_id)
        if bound is not None:
            return bound
        if conversation_id.startswith("industry-chat:"):
            # Try to resolve from industry service even without a persisted binding
            return self._resolve_industry_conversation(conversation_id)
        raise ValueError(
            "不支持的运行会话编号。"
            "请先进入 /chat 或行业主脑控制线程。",
        )

    def _resolve_bound_conversation(self, conversation_id: str) -> RuntimeThreadSpec | None:
        repository = self._agent_thread_binding_repository
        binding = None
        if repository is not None and callable(getattr(repository, "get_binding", None)):
            binding = repository.get_binding(conversation_id)
            if binding is None and conversation_id.startswith("industry-chat:"):
                _, _, remainder = conversation_id.partition("industry-chat:")
                instance_id, separator, role_id = remainder.rpartition(":")
                if instance_id and separator and role_id:
                    normalized_role_id = normalize_industry_role_id(role_id)
                    if normalized_role_id and normalized_role_id != role_id:
                        normalized_id = f"industry-chat:{instance_id}:{normalized_role_id}"
                        binding = repository.get_binding(normalized_id)
        if binding is None:
            return self._resolve_executor_bound_conversation(conversation_id)
        canonical_thread_id = _first_non_empty(
            binding.session_id,
            binding.alias_of_thread_id,
            binding.thread_id,
        )
        agent_profile = self._get_agent_profile(binding.agent_id)
        industry_detail = None
        if binding.industry_instance_id and self._industry_service is not None:
            industry_detail = _call_optional(
                self._industry_service,
                "get_instance_detail",
                binding.industry_instance_id,
            )
        agent_name = _first_non_empty(
            _field_value(agent_profile, "name"),
            _field_value(binding.metadata, "agent_name"),
            binding.agent_id,
        )
        role_name = _first_non_empty(
            _field_value(agent_profile, "role_name"),
            _field_value(binding.metadata, "role_name"),
            binding.industry_role_id,
        )
        industry_label = _field_value(industry_detail, "label")
        control_thread_id = _industry_control_thread_id(
            industry_instance_id=binding.industry_instance_id,
            industry_role_id=binding.industry_role_id,
            agent_id=binding.agent_id,
        )
        session_kind = "agent-chat"
        if binding.industry_instance_id and binding.industry_role_id:
            session_kind = (
                "industry-control-thread"
                if canonical_thread_id == control_thread_id
                else "industry-agent-chat"
            )
        meta = _compact_mapping(
            {
                "session_kind": session_kind,
                "entry_source": (
                    "industry"
                    if binding.binding_kind == "industry-role-alias"
                    else "agent-workbench"
                ),
                "requested_thread_id": conversation_id,
                "agent_id": binding.agent_id,
                "agent_name": agent_name,
                "industry_instance_id": binding.industry_instance_id,
                "industry_label": industry_label,
                "industry_role_id": binding.industry_role_id,
                "industry_role_name": role_name,
                "owner_scope": binding.owner_scope,
                "buddy_profile_id": _resolve_buddy_profile_id(
                    industry_instance_id=binding.industry_instance_id,
                    owner_scope=binding.owner_scope,
                ),
                "current_focus_kind": _field_value(agent_profile, "current_focus_kind"),
                "current_focus_id": _field_value(agent_profile, "current_focus_id"),
                "current_focus": _field_value(agent_profile, "current_focus"),
                "thread_binding_kind": binding.binding_kind,
                "canonical_thread_id": canonical_thread_id,
                "control_thread_id": control_thread_id,
                **self._resolve_work_context_contract(
                    work_context_id=binding.work_context_id,
                    context_key=(
                        f"control-thread:{control_thread_id}"
                        if control_thread_id is not None
                        else None
                    ),
                ),
            },
        )
        name = (
            f"{industry_label} - {role_name}"
            if industry_label and role_name
            else (f"{agent_name} - {role_name}" if role_name else agent_name)
        )
        return RuntimeThreadSpec(
            id=_required_text(canonical_thread_id, field_name="thread_id"),
            name=name,
            session_id=_required_text(canonical_thread_id, field_name="session_id"),
            user_id=binding.agent_id,
            channel=binding.channel or DEFAULT_CHANNEL,
            meta=meta,
        )

    def _resolve_executor_bound_conversation(
        self,
        conversation_id: str,
    ) -> RuntimeThreadSpec | None:
        service = self._executor_runtime_service
        lister = getattr(service, "list_thread_bindings", None)
        if not callable(lister):
            return None
        candidate_thread_ids = [conversation_id]
        if conversation_id.startswith("industry-chat:"):
            _, _, remainder = conversation_id.partition("industry-chat:")
            instance_id, separator, role_id = remainder.rpartition(":")
            if instance_id and separator and role_id:
                normalized_role_id = normalize_industry_role_id(role_id)
                if normalized_role_id and normalized_role_id != role_id:
                    candidate_thread_ids.append(
                        f"industry-chat:{instance_id}:{normalized_role_id}",
                    )
        binding = None
        runtime = None
        for candidate_thread_id in candidate_thread_ids:
            for candidate in list(lister(thread_id=candidate_thread_id, limit=10) or []):
                resolved_runtime = self._get_executor_runtime(
                    getattr(candidate, "runtime_id", None),
                )
                if resolved_runtime is None:
                    continue
                binding = candidate
                runtime = resolved_runtime
                break
            if binding is not None and runtime is not None:
                break
        if binding is None or runtime is None:
            return None
        runtime_metadata = _compact_mapping(_field_value(runtime, "metadata"))
        binding_metadata = _compact_mapping(_field_value(binding, "metadata"))
        continuity = {
            **_compact_mapping(runtime_metadata.get("continuity")),
            **_compact_mapping(binding_metadata.get("continuity")),
        }
        industry_instance_id = None
        industry_role_id = None
        if conversation_id.startswith("industry-chat:"):
            _, _, remainder = conversation_id.partition("industry-chat:")
            instance_id, separator, role_id = remainder.rpartition(":")
            if instance_id and separator and role_id:
                industry_instance_id = instance_id
                industry_role_id = role_id
        industry_instance_id = _first_non_empty(
            binding_metadata.get("industry_instance_id"),
            industry_instance_id,
        )
        industry_role_id = _first_non_empty(
            binding_metadata.get("industry_role_id"),
            _field_value(binding, "role_id"),
            _field_value(runtime, "role_id"),
            industry_role_id,
        )
        canonical_thread_id = _first_non_empty(
            continuity.get("control_thread_id"),
            continuity.get("session_id"),
            _field_value(binding, "thread_id"),
            _field_value(runtime, "thread_id"),
            conversation_id,
        )
        owner_agent_id = _required_text(
            _first_non_empty(
                runtime_metadata.get("owner_agent_id"),
                binding_metadata.get("owner_agent_id"),
                _field_value(runtime, "role_id"),
                _field_value(binding, "role_id"),
            ),
            field_name="agent_id",
        )
        agent_profile = self._get_agent_profile(owner_agent_id)
        industry_detail = None
        if industry_instance_id and self._industry_service is not None:
            industry_detail = _call_optional(
                self._industry_service,
                "get_instance_detail",
                industry_instance_id,
            )
        industry_label = _field_value(industry_detail, "label")
        role_name = _first_non_empty(
            _field_value(agent_profile, "role_name"),
            binding_metadata.get("role_name"),
            industry_role_id,
            _field_value(runtime, "role_id"),
        )
        agent_name = _first_non_empty(
            _field_value(agent_profile, "name"),
            binding_metadata.get("agent_name"),
            runtime_metadata.get("owner_agent_id"),
            owner_agent_id,
        )
        control_thread_id = _first_non_empty(
            continuity.get("control_thread_id"),
            _industry_control_thread_id(
                industry_instance_id=industry_instance_id,
                industry_role_id=industry_role_id,
                agent_id=owner_agent_id,
            ),
        )
        session_kind = (
            "industry-control-thread"
            if industry_instance_id and canonical_thread_id == control_thread_id
            else "industry-agent-chat"
            if industry_instance_id
            else "executor-runtime-thread"
        )
        meta = _compact_mapping(
            {
                "session_kind": session_kind,
                "entry_source": "executor-runtime",
                "requested_thread_id": conversation_id,
                "agent_id": owner_agent_id,
                "agent_name": agent_name,
                "industry_instance_id": industry_instance_id,
                "industry_label": industry_label,
                "industry_role_id": industry_role_id,
                "industry_role_name": role_name,
                "thread_binding_kind": "executor-runtime",
                "canonical_thread_id": canonical_thread_id,
                "control_thread_id": control_thread_id,
                **self._resolve_work_context_contract(
                    work_context_id=_first_non_empty(continuity.get("work_context_id")),
                    context_key=(
                        f"control-thread:{control_thread_id}"
                        if control_thread_id is not None
                        else None
                    ),
                ),
            },
        )
        name = (
            f"{industry_label} - {role_name}"
            if industry_label and role_name
            else (f"{agent_name} - {role_name}" if role_name else agent_name)
        )
        return RuntimeThreadSpec(
            id=_required_text(canonical_thread_id, field_name="thread_id"),
            name=name,
            session_id=_required_text(canonical_thread_id, field_name="session_id"),
            user_id=owner_agent_id,
            channel=DEFAULT_CHANNEL,
            meta=meta,
        )

    def _build_industry_control_thread_spec(
        self,
        *,
        detail: object,
        entry_source: str,
        requested_role_id: str | None = None,
        requested_agent_id: str | None = None,
        requested_agent_name: str | None = None,
    ) -> RuntimeThreadSpec:
        execution_role = _find_industry_role(detail, role_id=EXECUTION_CORE_ROLE_ID)
        runtime_execution_role = (
            None
            if execution_role is not None
            else _find_runtime_agent(detail, role_id=EXECUTION_CORE_ROLE_ID)
        )
        resolved_agent_id = _first_non_empty(
            _field_value(execution_role, "agent_id") if execution_role is not None else None,
            _field_value(runtime_execution_role, "agent_id") if runtime_execution_role is not None else None,
            EXECUTION_CORE_AGENT_ID,
        )
        conversation_id = _industry_control_thread_id(
            industry_instance_id=_field_value(detail, "instance_id"),
            industry_role_id=EXECUTION_CORE_ROLE_ID,
            agent_id=resolved_agent_id,
        )
        if conversation_id is None:
            raise RuntimeError("Industry control thread is not available")
        agent_profile = self._get_agent_profile(resolved_agent_id)
        resolved_role_name = _first_non_empty(
            _field_value(execution_role, "role_name"),
            _field_value(execution_role, "name"),
            _field_value(runtime_execution_role, "role_name") if runtime_execution_role is not None else None,
            _field_value(runtime_execution_role, "name") if runtime_execution_role is not None else None,
            EXECUTION_CORE_ROLE_ID,
        )
        resolved_agent_name = _first_non_empty(
            _field_value(execution_role, "name") if execution_role is not None else None,
            _field_value(runtime_execution_role, "name") if runtime_execution_role is not None else None,
            requested_agent_name,
            resolved_role_name,
            resolved_agent_id,
        )
        meta = _compact_mapping(
            {
                "session_kind": "industry-control-thread",
                "entry_source": entry_source,
                "agent_id": resolved_agent_id,
                "agent_name": resolved_agent_name,
                "industry_instance_id": _field_value(detail, "instance_id"),
                "industry_label": _field_value(detail, "label"),
                "industry_role_id": EXECUTION_CORE_ROLE_ID,
                "industry_role_name": resolved_role_name,
                "owner_scope": _field_value(detail, "owner_scope"),
                "buddy_profile_id": _resolve_buddy_profile_id(
                    industry_instance_id=_field_value(detail, "instance_id"),
                    owner_scope=_field_value(detail, "owner_scope"),
                ),
                "current_focus_kind": _field_value(agent_profile, "current_focus_kind"),
                "current_focus_id": _field_value(agent_profile, "current_focus_id"),
                "current_focus": _field_value(agent_profile, "current_focus"),
                "control_thread_id": conversation_id,
                "requested_agent_id": (
                    requested_agent_id
                    if requested_agent_id is not None and requested_agent_id != resolved_agent_id
                    else None
                ),
                "requested_industry_role_id": (
                    requested_role_id
                    if requested_role_id is not None and not is_execution_core_role_id(requested_role_id)
                    else None
                ),
                **self._resolve_work_context_contract(
                    context_key=f"control-thread:{conversation_id}",
                ),
            },
        )
        return RuntimeThreadSpec(
            id=conversation_id,
            name=_industry_conversation_name(detail, execution_role or runtime_execution_role),
            session_id=conversation_id,
            user_id=_required_text(resolved_agent_id, field_name="agent_id"),
            channel=DEFAULT_CHANNEL,
            meta=meta,
        )

    def _resolve_industry_conversation(self, conversation_id: str) -> RuntimeThreadSpec:
        if self._industry_service is None:
            raise RuntimeError("Industry service is unavailable")

        _, _, remainder = conversation_id.partition("industry-chat:")
        instance_id, separator, role_id = remainder.rpartition(":")
        if not instance_id or not separator or not role_id:
            raise ValueError(f"Invalid industry conversation id: {conversation_id}")

        detail = _call_optional(self._industry_service, "get_instance_detail", instance_id)
        if detail is None:
            raise KeyError(f"Industry instance '{instance_id}' was not found")

        role = _find_industry_role(detail, role_id=role_id)
        runtime_agent = None
        if role is None:
            runtime_agent = _find_runtime_agent(detail, role_id=role_id)
            role = runtime_agent
        if role is None:
            team_agents = _team_agents(detail)
            runtime_agents = _runtime_agents(detail)
            available_role_ids = [
                _first_non_empty(_field_value(item, "role_id"), _field_value(item, "industry_role_id"))
                for item in team_agents
            ]
            available_runtime_ids = [
                _first_non_empty(_field_value(item, "role_id"), _field_value(item, "industry_role_id"))
                for item in runtime_agents
            ]
            raise KeyError(
                f"Industry instance '{instance_id}' does not contain role '{role_id}'. "
                f"Team roles={available_role_ids}; runtime roles={available_runtime_ids}."
            )

        requested_agent_id = _first_non_empty(
            _field_value(role, "agent_id"),
            _field_value(role, "id"),
            role_id,
        )
        requested_agent_name = _first_non_empty(
            _field_value(role, "name"),
            _field_value(role, "role_name"),
            requested_agent_id,
        )
        requested_role_id = _first_non_empty(
            _field_value(role, "role_id"),
            _field_value(role, "industry_role_id"),
            role_id,
        )
        return self._build_industry_control_thread_spec(
            detail=detail,
            entry_source="industry",
            requested_role_id=requested_role_id,
            requested_agent_id=requested_agent_id,
            requested_agent_name=requested_agent_name,
        )

    def _build_removed_agent_chat_detail(self, conversation_id: str) -> str:
        agent_id = conversation_id.removeprefix("agent-chat:")
        if not agent_id:
            return "不支持的运行会话编号。请改用 /chat 或 industry-chat:* 主脑控制线程。"
        profile = self._get_agent_profile(agent_id)
        industry_instance_id = _first_non_empty(
            _field_value(profile, "industry_instance_id"),
        )
        control_thread_id = _industry_control_thread_id(
            industry_instance_id=industry_instance_id,
            industry_role_id=_field_value(profile, "industry_role_id"),
            agent_id=_field_value(profile, "agent_id") or agent_id,
        )
        if control_thread_id is not None:
            return (
                "前台聊天已收口为主脑入口，不再开放 agent-chat:* 直接会话。"
                f"请改用 {control_thread_id} 主脑控制线程。"
            )
        return (
            "前台聊天已收口为主脑入口，不再开放 agent-chat:* 直接会话。"
            "请直接进入 /chat 与主脑沟通，执行位详情请在工作台查看。"
        )

    def _get_agent_profile(self, agent_id: str | None) -> object | None:
        if not agent_id or self._agent_profile_service is None:
            return None
        return _call_optional(self._agent_profile_service, "get_agent", agent_id)

    def _get_executor_runtime(self, runtime_id: object | None) -> object | None:
        normalized_runtime_id = _first_non_empty(runtime_id)
        if normalized_runtime_id is None:
            return None
        service = self._executor_runtime_service
        getter = getattr(service, "get_runtime", None)
        if not callable(getter):
            return None
        try:
            runtime = getter(normalized_runtime_id, formal_only=True)
        except TypeError:
            runtime = getter(normalized_runtime_id)
        if runtime is not None:
            return runtime
        try:
            return getter(normalized_runtime_id)
        except TypeError:
            return None

    def _resolve_work_context_contract(
        self,
        *,
        work_context_id: object | None = None,
        context_key: object | None = None,
    ) -> dict[str, object]:
        normalized_context_id = _first_non_empty(work_context_id)
        normalized_context_key = _first_non_empty(context_key)
        repository = self._work_context_repository
        record = None
        if normalized_context_id and repository is not None:
            getter = getattr(repository, "get_context", None)
            if callable(getter):
                record = getter(normalized_context_id)
        if (
            record is None
            and normalized_context_id is None
            and normalized_context_key
            and repository is not None
        ):
            getter = getattr(repository, "get_by_context_key", None)
            if callable(getter):
                record = getter(normalized_context_key)
        if record is not None:
            normalized_context_id = _first_non_empty(_field_value(record, "id"), normalized_context_id)
            normalized_context_key = _first_non_empty(
                _field_value(record, "context_key"),
                normalized_context_key,
            )
        return _compact_mapping(
            {
                "work_context_id": normalized_context_id,
                "context_key": normalized_context_key,
                "work_context": self._work_context_payload(
                    normalized_context_id,
                    record=record,
                ),
            },
        )

    def _work_context_payload(
        self,
        work_context_id: object | None,
        *,
        record: object | None = None,
    ) -> dict[str, object] | None:
        context_id = _first_non_empty(work_context_id)
        if context_id is None and record is None:
            return None
        if record is None:
            repository = self._work_context_repository
            getter = getattr(repository, "get_context", None)
            if not callable(getter):
                return {"id": context_id} if context_id is not None else None
            record = getter(context_id)
        if record is None:
            return {"id": context_id} if context_id is not None else None
        return _compact_mapping(
            {
                "id": _field_value(record, "id") or context_id,
                "title": _field_value(record, "title"),
                "context_type": _field_value(record, "context_type"),
                "status": _field_value(record, "status"),
                "context_key": _field_value(record, "context_key"),
            },
        )


def _call_optional(target: object, method_name: str, *args):
    method = getattr(target, method_name, None)
    if not callable(method):
        return None
    return method(*args)


def _field_value(value: object | None, name: str) -> object | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _first_non_empty(*values: object | None) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _required_text(value: object | None, *, field_name: str) -> str:
    text = _first_non_empty(value)
    if text is None:
        raise RuntimeError(f"运行会话缺少必填字段“{field_name}”")
    return text


def _industry_control_thread_id(
    *,
    industry_instance_id: object | None,
    industry_role_id: object | None,
    agent_id: object | None,
) -> str | None:
    del industry_role_id, agent_id
    resolved_instance_id = _first_non_empty(industry_instance_id)
    if resolved_instance_id is None:
        return None
    return f"industry-chat:{resolved_instance_id}:{EXECUTION_CORE_ROLE_ID}"


def _resolve_buddy_profile_id(
    *,
    industry_instance_id: object | None,
    owner_scope: object | None,
) -> str | None:
    resolved_instance_id = _first_non_empty(industry_instance_id)
    if resolved_instance_id and resolved_instance_id.startswith("buddy:"):
        parts = resolved_instance_id.split(":")
        if len(parts) >= 2:
            return _first_non_empty(parts[1], owner_scope)
    return _first_non_empty(owner_scope)


def _industry_thread_waiting_for_kickoff(detail: object | None) -> bool:
    team = _field_value(detail, "team")
    execution = _field_value(detail, "execution")
    current_cycle = _field_value(detail, "current_cycle")
    statuses = (
        _field_value(detail, "status"),
        _field_value(team, "status"),
        _field_value(team, "autonomy_status"),
        _field_value(detail, "autonomy_status"),
        _field_value(execution, "status"),
        _field_value(current_cycle, "status"),
    )
    return any(_normalize_token(status) == "waiting-confirm" for status in statuses)


def _build_industry_kickoff_prompt(
    detail: object | None,
    *,
    thread_spec: RuntimeThreadSpec,
) -> str:
    label = _first_non_empty(_field_value(detail, "label"), thread_spec.name) or "当前团队"
    current_cycle = _field_value(detail, "current_cycle")
    current_focus = _first_non_empty(
        _field_value(current_cycle, "title"),
        _field_value(current_cycle, "summary"),
    )
    lanes = _field_value(detail, "lanes")
    lane_count = len(lanes) if isinstance(lanes, list) else 0
    backlog_count = len(_field_value(detail, "backlog")) if isinstance(_field_value(detail, "backlog"), list) else 0
    cycle_count = len(_field_value(detail, "cycles")) if isinstance(_field_value(detail, "cycles"), list) else 0
    if cycle_count <= 0 and current_cycle is not None:
        cycle_count = 1
    assignment_count = len(_field_value(detail, "assignments")) if isinstance(_field_value(detail, "assignments"), list) else 0
    report_count = len(_field_value(detail, "agent_reports")) if isinstance(_field_value(detail, "agent_reports"), list) else 0
    summary_line = (
        f"当前待编排：lane {lane_count} / backlog {backlog_count} / cycle {cycle_count} / assignment {assignment_count} / report {report_count}。"
    )
    if current_focus:
        summary_line = f"{summary_line} 当前 cycle：{current_focus}。"
    lane_titles: list[str] = []
    if isinstance(lanes, list):
        for lane in lanes:
            if not isinstance(lane, dict):
                continue
            title = _first_non_empty(lane.get("title"), lane.get("lane_key"), lane.get("lane_id"))
            if title is None:
                continue
            lane_titles.append(title)
            if len(lane_titles) >= 3:
                break
    if lane_titles:
        summary_line = f"{summary_line} 当前 lane：{'、'.join(lane_titles)}。"
    return (
        f"“{label}” 已创建完成，当前停在主脑启动确认。\n"
        "系统不会直接把执行位推入干活，而是会先进入行业学习阶段：由研究位补齐行业、客户、竞争和平台信号，再自动转入后续协调与执行。\n"
        "如果当前仍停在这里，说明这条链路需要一次显式启动；你可以直接回复“开始学习”或“继续执行”。\n"
        "如果你想先调整优先级、lane、backlog 或节奏，也可以直接在这里补充要求。\n"
        f"{summary_line}{_build_kickoff_staffing_suffix(detail)}"
    )

def _build_kickoff_staffing_suffix(detail: object | None) -> str:
    staffing = _field_value(detail, "staffing")
    if not isinstance(staffing, dict):
        return ""
    lines: list[str] = []

    def _present_staffing_kind(value: object) -> str:
        normalized = _first_non_empty(value)
        if not normalized:
            return "待补位"
        mapping = {
            "routing-pending": "待补位",
            "career-seat-proposal": "长期岗位提案",
            "temporary-seat-proposal": "临时席位提案",
        }
        return mapping.get(normalized, normalized)

    def _present_staffing_status(value: object) -> str:
        normalized = _first_non_empty(value)
        if not normalized:
            return "就绪"
        mapping = {
            "waiting-review": "待审核",
            "ready": "就绪",
            "active": "运行中",
            "paused": "已暂停",
        }
        return mapping.get(normalized, normalized)

    active_gap = staffing.get("active_gap")
    if isinstance(active_gap, dict):
        gap_role = _first_non_empty(
            active_gap.get("target_role_name"),
            active_gap.get("target_role_id"),
        ) or "未指派席位"
        gap_kind = _present_staffing_kind(active_gap.get("kind"))
        gap_decision_id = _first_non_empty(active_gap.get("decision_request_id"))
        gap_line = f"当前待补位：{gap_role}（{gap_kind}）"
        if gap_decision_id:
            gap_line = f"{gap_line}，决策 {gap_decision_id}"
        lines.append(f"{gap_line}。")
    pending_proposals = staffing.get("pending_proposals")
    if isinstance(pending_proposals, list) and pending_proposals:
        valid_pending_proposals = [
            item for item in pending_proposals if isinstance(item, dict)
        ]
        preview_items: list[str] = []
        for item in valid_pending_proposals[:3]:
            proposal_role = _first_non_empty(
                item.get("target_role_name"),
                item.get("target_role_id"),
            ) or "待确认补位"
            proposal_kind = _present_staffing_kind(item.get("kind"))
            proposal_decision_id = _first_non_empty(item.get("decision_request_id"))
            details = [
                value
                for value in (
                    proposal_kind,
                    f"决策 {proposal_decision_id}" if proposal_decision_id else None,
                )
                if value
            ]
            if details:
                proposal_role = f"{proposal_role}（{'，'.join(details)}）"
            preview_items.append(proposal_role)
        if preview_items:
            preview = ", ".join(preview_items)
            if len(valid_pending_proposals) > 3:
                preview = f"{preview} 等 {len(valid_pending_proposals)} 项"
            lines.append(f"待确认补位：{preview}。")
    temporary_seats = staffing.get("temporary_seats")
    if isinstance(temporary_seats, list) and temporary_seats:
        preview = ", ".join(
            _first_non_empty(item.get("role_name"), item.get("role_id")) or "临时席位"
            for item in temporary_seats[:3]
            if isinstance(item, dict)
        )
        if preview:
            lines.append(f"当前临时席位：{preview}。")
    researcher = staffing.get("researcher")
    if isinstance(researcher, dict):
        researcher_name = _first_non_empty(
            researcher.get("role_name"),
            researcher.get("agent_id"),
        ) or "研究位"
        if researcher_name == "Researcher":
            researcher_name = "研究位"
        researcher_status = _present_staffing_status(researcher.get("status"))
        pending_signal_count = researcher.get("pending_signal_count")
        researcher_line = f"{researcher_name} 当前状态：{researcher_status}"
        if isinstance(pending_signal_count, int):
            researcher_line = f"{researcher_line}，待主脑处理研究汇报 {pending_signal_count}"
        lines.append(f"{researcher_line}。")
    return f"\n{'\n'.join(lines)}" if lines else ""

def _build_synthetic_assistant_message(
    *,
    message_id: str,
    text: str,
    metadata: dict[str, object] | None = None,
) -> Message:
    return Message.model_validate(
        {
            "id": message_id,
            "role": "assistant",
            "object": "message",
            "type": "message",
            "status": "completed",
            "content": [{"type": "text", "text": text}],
            "metadata": _compact_mapping(metadata or {}),
        },
    )


def _compact_mapping(values: object | None) -> dict[str, object]:
    if not isinstance(values, dict):
        return {}
    return {
        key: value
        for key, value in values.items()
        if value is not None and (not isinstance(value, str) or value.strip())
    }


def _team_agents(detail: object | None) -> list[object]:
    team = _field_value(detail, "team")
    agents = _field_value(team, "agents")
    if isinstance(agents, list):
        return list(agents)
    return []


def _runtime_agents(detail: object | None) -> list[object]:
    agents = _field_value(detail, "agents")
    if isinstance(agents, list):
        return list(agents)
    return []


def _normalize_token(value: object | None) -> str | None:
    text = _first_non_empty(value)
    if text is None:
        return None
    return text.lower()


def _role_matches(role: object | None, token: str) -> bool:
    normalized = _normalize_token(token)
    if not normalized:
        return False
    for field in ("role_id", "industry_role_id", "agent_id", "role_name", "name"):
        candidate = _normalize_token(_field_value(role, field))
        if candidate and candidate == normalized:
            return True
        if candidate and (
            is_execution_core_role_id(candidate)
            and is_execution_core_role_id(normalized)
        ):
            return True
    return False


def _find_industry_role(detail: object | None, *, role_id: str) -> object | None:
    normalized_role_id = normalize_industry_role_id(role_id)
    if not normalized_role_id:
        return None
    for role in _team_agents(detail):
        if _role_matches(role, normalized_role_id):
            return role
    return None


def _find_runtime_agent(detail: object | None, *, role_id: str) -> object | None:
    normalized_role_id = normalize_industry_role_id(role_id)
    if not normalized_role_id:
        return None
    for agent in _runtime_agents(detail):
        if _role_matches(agent, normalized_role_id):
            return agent
    return None


def _industry_conversation_name(detail: object, role: object) -> str:
    label = _first_non_empty(_field_value(detail, "label")) or "Industry Team"
    role_name = _first_non_empty(_field_value(role, "role_name")) or "Agent"
    return f"{label} - {role_name}"


__all__ = ["RuntimeConversationFacade", "RuntimeConversationPayload"]
