# -*- coding: utf-8 -*-
"""CoPaw Agent - Main agent implementation.

This module provides the main CoPawAgent class built on ReActAgent,
with integrated tools, skills, and memory management.
"""
import asyncio
import functools
import json
import logging
import os
import inspect
from collections.abc import Iterable
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, List, Literal, Optional, Type

from agentscope.agent import ReActAgent
from agentscope.mcp import HttpStatefulClient, StdIOStatefulClient
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg, TextBlock
from agentscope.tool import Toolkit, ToolResponse
from anyio import ClosedResourceError
from pydantic import BaseModel

from ..industry.models import IndustrySeatCapabilityLayers
from ..skill_service import (
    ensure_skills_initialized,
    get_working_skills_dir,
    list_available_skills,
)
from .command_handler import CommandHandler
from .hooks import MemoryCompactionHook
from .model_factory import create_model_and_formatter
from .prompt import build_system_prompt_from_working_dir
from .tools import (
    browser_use,
    desktop_screenshot,
    edit_file,
    execute_shell_command,
    get_current_time,
    read_file,
    send_file_to_user,
    write_file,
    create_memory_search_tool,
)
from ..capabilities.tool_execution_contracts import get_tool_execution_contract
from ..capabilities.execution_support import _normalize_optional_empty_executor_args
from .utils import process_file_and_media_blocks_in_message
from ..constant import (
    MEMORY_COMPACT_RATIO,
)
from ..agents.memory import MemoryManager
from ..memory.conversation_compaction_service import ConversationCompactionService

logger = logging.getLogger(__name__)

ToolPreflightHook = Callable[[str, tuple[Any, ...], dict[str, Any]], ToolResponse | None]
ToolExecutionDelegate = Callable[[str, dict[str, Any]], Any]

_TOOL_PREFLIGHT_HOOK: ContextVar[ToolPreflightHook | None] = (
    ContextVar("_tool_preflight_hook", default=None)
)
_TOOL_CHOICE_OVERRIDE_RESOLVER: ContextVar[
    Callable[[], Literal["auto", "none", "required"] | None] | None
] = ContextVar("_tool_choice_override_resolver", default=None)
_TOOL_EXECUTION_DELEGATE: ContextVar[ToolExecutionDelegate | None] = ContextVar(
    "_tool_execution_delegate",
    default=None,
)

# Valid namesake strategies for tool registration
NamesakeStrategy = Literal["override", "skip", "raise", "rename"]

_BUILTIN_TOOL_FUNCTIONS = (
    execute_shell_command,
    read_file,
    write_file,
    edit_file,
    browser_use,
    desktop_screenshot,
    send_file_to_user,
    get_current_time,
)


def _serialize_tool_result(value: Any) -> str:
    """Serialize non-ToolResponse results into text for toolkit compatibility."""
    if value is None:
        return "Tool executed successfully."
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            value = model_dump(mode="json")
        except TypeError:
            value = model_dump()
    try:
        return json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except TypeError:
        return str(value)


def _coerce_tool_response(value: Any) -> ToolResponse:
    """Normalize legacy tool outputs to the ToolResponse contract."""
    if isinstance(value, ToolResponse):
        return value
    return ToolResponse(
        content=[
            TextBlock(
                type="text",
                text=_serialize_tool_result(value),
            ),
        ],
    )


def _coerce_tool_execution_delegate_result(value: Any) -> ToolResponse:
    if isinstance(value, dict):
        output = value.get("output")
        if output is not None:
            return _coerce_tool_response(output)
        summary = value.get("summary")
        if isinstance(summary, str) and summary:
            return ToolResponse(
                content=[
                    TextBlock(
                        type="text",
                        text=summary,
                    ),
                ],
            )
    return _coerce_tool_response(value)


def _tool_execution_delegate_failure_response(
    capability_id: str,
    exc: Exception,
) -> ToolResponse:
    return ToolResponse(
        content=[
            TextBlock(
                type="text",
                text=f"Capability front door failed for {capability_id}: {exc}",
            ),
        ],
    )


def _tool_capability_id_for_function(
    tool_fn: Callable[..., Any],
) -> str | None:
    tool_name = getattr(tool_fn, "__name__", None)
    if not tool_name:
        return None
    capability_id = f"tool:{tool_name}"
    if get_tool_execution_contract(capability_id) is None:
        return None
    return capability_id


def _build_tool_payload_from_call(
    tool_fn: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> dict[str, Any] | None:
    try:
        signature = inspect.signature(tool_fn)
        bound = signature.bind_partial(*args, **kwargs)
    except TypeError:
        return None
    return _normalize_optional_empty_executor_args(signature, dict(bound.arguments))


def _run_tool_contract_validation(
    tool_fn: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> ToolResponse | None:
    capability_id = _tool_capability_id_for_function(tool_fn)
    if capability_id is None:
        return None
    tool_contract = get_tool_execution_contract(capability_id)
    if tool_contract is None:
        return None
    payload = _build_tool_payload_from_call(tool_fn, args, kwargs)
    if payload is None:
        return None
    validation_error = tool_contract.validate_payload(payload)
    if validation_error is None:
        return None
    return ToolResponse(
        content=[
            TextBlock(
                type="text",
                text=validation_error,
            ),
        ],
    )


@contextmanager
def bind_tool_preflight(
    preflight: ToolPreflightHook | None,
):
    """Bind a per-query tool preflight hook for wrapped toolkit functions."""
    previous = _TOOL_PREFLIGHT_HOOK.get()
    _TOOL_PREFLIGHT_HOOK.set(preflight)
    try:
        yield
    finally:
        _TOOL_PREFLIGHT_HOOK.set(previous)


@contextmanager
def bind_reasoning_tool_choice_resolver(
    resolver: Callable[[], Literal["auto", "none", "required"] | None] | None,
):
    """Bind a per-query tool-choice override resolver."""
    previous = _TOOL_CHOICE_OVERRIDE_RESOLVER.get()
    _TOOL_CHOICE_OVERRIDE_RESOLVER.set(resolver)
    try:
        yield
    finally:
        _TOOL_CHOICE_OVERRIDE_RESOLVER.set(previous)


@contextmanager
def bind_tool_execution_delegate(
    delegate: ToolExecutionDelegate | None,
):
    previous = _TOOL_EXECUTION_DELEGATE.get()
    _TOOL_EXECUTION_DELEGATE.set(delegate)
    try:
        yield
    finally:
        _TOOL_EXECUTION_DELEGATE.set(previous)


def _run_tool_preflight(
    tool_name: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> ToolResponse | None:
    preflight = _TOOL_PREFLIGHT_HOOK.get()
    if not callable(preflight):
        return None
    try:
        return preflight(tool_name, args, kwargs)
    except Exception:
        logger.exception("Tool preflight hook failed for '%s'", tool_name)
        return None


def _run_tool_frontdoor_checks(
    tool_fn: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    *,
    apply_preflight: bool,
) -> ToolResponse | None:
    validation_block = _run_tool_contract_validation(tool_fn, args, kwargs)
    if validation_block is not None:
        return validation_block
    if not apply_preflight:
        return None
    return _run_tool_preflight(tool_fn.__name__, args, kwargs)


def _resolve_tool_execution_delegate_call(
    tool_fn: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> tuple[ToolExecutionDelegate, str, dict[str, Any]] | None:
    delegate = _TOOL_EXECUTION_DELEGATE.get()
    if not callable(delegate):
        return None
    capability_id = _tool_capability_id_for_function(tool_fn)
    if capability_id is None:
        return None
    payload = _build_tool_payload_from_call(tool_fn, args, kwargs)
    if payload is None:
        return None
    return delegate, capability_id, payload


def _wrap_tool_function_for_toolkit(
    tool_fn: Callable[..., Any],
    *,
    apply_preflight: bool = True,
) -> Callable[..., Any]:
    """Wrap tool functions so legacy return types still satisfy AgentScope."""
    if inspect.isasyncgenfunction(tool_fn):
        @functools.wraps(tool_fn)
        async def _wrapped(*args: Any, **kwargs: Any):
            blocked = _run_tool_frontdoor_checks(
                tool_fn,
                args,
                kwargs,
                apply_preflight=apply_preflight,
            )
            if blocked is not None:
                yield blocked
                return
            delegated = _resolve_tool_execution_delegate_call(tool_fn, args, kwargs)
            if delegated is not None:
                delegate, capability_id, payload = delegated
                try:
                    yield _coerce_tool_execution_delegate_result(
                        await delegate(capability_id, payload),
                    )
                    return
                except Exception as exc:
                    logger.exception(
                        "Tool execution delegate failed for '%s'; blocking builtin fallback",
                        capability_id,
                    )
                    yield _tool_execution_delegate_failure_response(
                        capability_id,
                        exc,
                    )
                    return
            async for item in tool_fn(*args, **kwargs):
                yield _coerce_tool_response(item)

        return _wrapped

    if inspect.iscoroutinefunction(tool_fn):
        @functools.wraps(tool_fn)
        async def _wrapped(*args: Any, **kwargs: Any) -> ToolResponse:
            blocked = _run_tool_frontdoor_checks(
                tool_fn,
                args,
                kwargs,
                apply_preflight=apply_preflight,
            )
            if blocked is not None:
                return blocked
            delegated = _resolve_tool_execution_delegate_call(tool_fn, args, kwargs)
            if delegated is not None:
                delegate, capability_id, payload = delegated
                try:
                    return _coerce_tool_execution_delegate_result(
                        await delegate(capability_id, payload),
                    )
                except Exception as exc:
                    logger.exception(
                        "Tool execution delegate failed for '%s'; blocking builtin fallback",
                        capability_id,
                    )
                    return _tool_execution_delegate_failure_response(
                        capability_id,
                        exc,
                    )
            return _coerce_tool_response(await tool_fn(*args, **kwargs))

        return _wrapped

    if inspect.isgeneratorfunction(tool_fn):
        @functools.wraps(tool_fn)
        def _wrapped(*args: Any, **kwargs: Any):
            blocked = _run_tool_frontdoor_checks(
                tool_fn,
                args,
                kwargs,
                apply_preflight=apply_preflight,
            )
            if blocked is not None:
                yield blocked
                return
            for item in tool_fn(*args, **kwargs):
                yield _coerce_tool_response(item)

        return _wrapped

    @functools.wraps(tool_fn)
    def _wrapped(*args: Any, **kwargs: Any) -> ToolResponse:
        blocked = _run_tool_frontdoor_checks(
            tool_fn,
            args,
            kwargs,
            apply_preflight=apply_preflight,
        )
        if blocked is not None:
            return blocked
        return _coerce_tool_response(tool_fn(*args, **kwargs))

    return _wrapped


def normalize_reasoning_tool_choice(
    tool_choice: Literal["auto", "none", "required"] | None,
    has_tools: bool,
) -> Literal["auto", "none", "required"] | None:
    """Normalize tool_choice for reasoning to reduce provider variance."""
    resolver = _TOOL_CHOICE_OVERRIDE_RESOLVER.get()
    if callable(resolver):
        try:
            override = resolver()
        except Exception:
            logger.exception("Tool-choice override resolver failed")
        else:
            if override is not None:
                return override
    if tool_choice is None and has_tools:
        return "auto"
    return tool_choice


class CoPawAgent(ReActAgent):
    """CoPaw Agent with integrated tools, skills, and memory management.

    This agent extends ReActAgent with:
    - Built-in tools (shell, file operations, browser, etc.)
    - Dynamic skill loading from working directory
    - Memory management with auto-compaction
    - System command handling (/compact, /new, etc.)
    """

    def __init__(
        self,
        env_context: Optional[str] = None,
        prompt_appendix: str | None = None,
        enable_memory_manager: bool = True,
        mcp_clients: Optional[List[Any]] = None,
        conversation_compaction_service: ConversationCompactionService | None = None,
        memory_manager: MemoryManager | None = None,
        max_iters: int = 50,
        max_input_length: int = 128 * 1024,  # 128K = 131072 tokens
        namesake_strategy: NamesakeStrategy = "skip",
        allowed_tool_capability_ids: Iterable[str] | None = None,
        allowed_skill_names: Iterable[str] | None = None,
        capability_layers: IndustrySeatCapabilityLayers | None = None,
        extra_tool_functions: Iterable[Callable[..., Any]] | None = None,
    ):
        """Initialize CoPawAgent.

        Args:
            env_context: Optional environment context to prepend to
                system prompt
            enable_memory_manager: Whether to enable memory manager
            mcp_clients: Optional list of MCP clients for tool
                integration
            memory_manager: Optional memory manager instance
            max_iters: Maximum number of reasoning-acting iterations
                (default: 50)
            max_input_length: Maximum input length in tokens for model
                context window (default: 128K = 131072)
            namesake_strategy: Strategy to handle namesake tool functions.
                Options: "override", "skip", "raise", "rename"
                (default: "skip")
        """
        self._env_context = env_context
        self._prompt_appendix = prompt_appendix
        self._max_input_length = max_input_length
        self._mcp_clients = mcp_clients or []
        self._namesake_strategy = namesake_strategy
        self._allowed_tool_capability_ids = (
            set(allowed_tool_capability_ids)
            if allowed_tool_capability_ids is not None
            else None
        )
        self._allowed_skill_names = (
            set(allowed_skill_names)
            if allowed_skill_names is not None
            else None
        )
        self._capability_layers = capability_layers
        self._extra_tool_functions = list(extra_tool_functions or [])

        # Memory compaction threshold: configurable ratio of max_input_length
        self._memory_compact_threshold = int(
            max_input_length * MEMORY_COMPACT_RATIO,
        )

        # Initialize toolkit with built-in tools
        toolkit = self._create_toolkit(namesake_strategy=namesake_strategy)

        # Load and register skills
        self._register_skills(toolkit)

        # Build system prompt
        sys_prompt = self._build_sys_prompt()

        # Create model and formatter using factory method
        model, formatter = create_model_and_formatter()

        # Initialize parent ReActAgent
        super().__init__(
            name="Spider Mesh",
            model=model,
            sys_prompt=sys_prompt,
            toolkit=toolkit,
            memory=InMemoryMemory(),
            formatter=formatter,
            max_iters=max_iters,
        )

        # Setup memory manager
        self._setup_memory_manager(
            enable_memory_manager,
            conversation_compaction_service,
            memory_manager,
            namesake_strategy,
        )

        # Setup command handler
        self.command_handler = CommandHandler(
            agent_name=self.name,
            memory=self.memory,
            memory_manager=self.memory_manager,
            enable_memory_manager=self._enable_memory_manager,
        )

        # Register hooks
        self._register_hooks()

    def _create_toolkit(
        self,
        namesake_strategy: NamesakeStrategy = "skip",
    ) -> Toolkit:
        """Create and populate toolkit with built-in tools.

        Args:
            namesake_strategy: Strategy to handle namesake tool functions.
                Options: "override", "skip", "raise", "rename"
                (default: "skip")

        Returns:
            Configured toolkit instance
        """
        toolkit = Toolkit()

        # Register built-in tools
        for tool_fn in _BUILTIN_TOOL_FUNCTIONS:
            capability_id = f"tool:{tool_fn.__name__}"
            if (
                self._allowed_tool_capability_ids is not None
                and capability_id not in self._allowed_tool_capability_ids
            ):
                continue
            toolkit.register_tool_function(
                _wrap_tool_function_for_toolkit(tool_fn),
                namesake_strategy=namesake_strategy,
            )

        for tool_fn in self._extra_tool_functions:
            toolkit.register_tool_function(
                _wrap_tool_function_for_toolkit(
                    tool_fn,
                    apply_preflight=False,
                ),
                namesake_strategy=namesake_strategy,
            )

        return toolkit

    def _register_skills(self, toolkit: Toolkit) -> None:
        """Load and register skills from working directory.

        Args:
            toolkit: Toolkit to register skills to
        """
        # Check skills initialization
        ensure_skills_initialized()

        working_skills_dir = get_working_skills_dir()
        available_skills = list_available_skills()

        for skill_name in available_skills:
            if (
                self._allowed_skill_names is not None
                and skill_name not in self._allowed_skill_names
            ):
                continue
            skill_dir = working_skills_dir / skill_name
            if skill_dir.exists():
                try:
                    toolkit.register_agent_skill(str(skill_dir))
                    logger.debug("Registered skill: %s", skill_name)
                except Exception as e:
                    logger.error(
                        "Failed to register skill '%s': %s",
                        skill_name,
                        e,
                    )

    def _build_sys_prompt(self) -> str:
        """Build system prompt from working dir files and env context.

        Returns:
            Complete system prompt string
        """
        sys_prompt = build_system_prompt_from_working_dir()
        if self._env_context is not None:
            sys_prompt = self._env_context + "\n\n" + sys_prompt
        if self._prompt_appendix:
            sys_prompt = sys_prompt + "\n\n" + self._prompt_appendix
        return sys_prompt

    def _setup_memory_manager(
        self,
        enable_memory_manager: bool,
        conversation_compaction_service: ConversationCompactionService | None,
        memory_manager: MemoryManager | None,
        namesake_strategy: NamesakeStrategy,
    ) -> None:
        """Setup memory manager and register memory search tool if enabled.

        Args:
            enable_memory_manager: Whether to enable memory manager
            memory_manager: Optional memory manager instance
            namesake_strategy: Strategy to handle namesake tool functions
        """
        # Check env var: if ENABLE_MEMORY_MANAGER=false, disable memory manager
        env_enable_mm = os.getenv("ENABLE_MEMORY_MANAGER", "")
        if env_enable_mm.lower() == "false":
            enable_memory_manager = False

        self._enable_memory_manager: bool = enable_memory_manager
        resolved_compaction_service = (
            conversation_compaction_service or memory_manager
        )
        self.conversation_compaction_service = resolved_compaction_service
        self.memory_manager = resolved_compaction_service

        # Register memory_search tool if enabled and available
        if (
            self._enable_memory_manager
            and self.conversation_compaction_service is not None
        ):
            # update memory manager
            self.memory = self.conversation_compaction_service.get_in_memory_memory()

            # Register memory_search as a tool function
            self.toolkit.register_tool_function(
                _wrap_tool_function_for_toolkit(
                    create_memory_search_tool(self.conversation_compaction_service),
                ),
                namesake_strategy=namesake_strategy,
            )
            logger.debug("Registered memory_search tool")

    def _register_hooks(self) -> None:
        """Register pre-reasoning hooks."""
        # Memory compaction hook - auto-compact when context is full
        if (
            self._enable_memory_manager
            and self.conversation_compaction_service is not None
        ):
            memory_compact_hook = MemoryCompactionHook(
                memory_manager=self.conversation_compaction_service,
            )
            self.register_instance_hook(
                hook_type="pre_reasoning",
                hook_name="memory_compact_hook",
                hook=memory_compact_hook.__call__,
            )
            logger.debug("Registered memory compaction hook")

    def rebuild_sys_prompt(self) -> None:
        """Rebuild and replace the system prompt.

        Useful after load_session_state to ensure the prompt reflects the
        latest built-in core system prompt and runtime appendix.

        Updates both self._sys_prompt and the first system-role
        message stored in self.memory.content (if one exists).
        """
        self._sys_prompt = self._build_sys_prompt()

        for msg, _marks in self.memory.content:
            if msg.role == "system":
                msg.content = self.sys_prompt
            break

    async def register_mcp_clients(
        self,
        namesake_strategy: NamesakeStrategy = "skip",
    ) -> None:
        """Register MCP clients on this agent's toolkit after construction.

        Args:
            namesake_strategy: Strategy to handle namesake tool functions.
                Options: "override", "skip", "raise", "rename"
                (default: "skip")
        """
        for i, client in enumerate(self._mcp_clients):
            client_name = getattr(client, "name", repr(client))
            try:
                await self.toolkit.register_mcp_client(
                    client,
                    namesake_strategy=namesake_strategy,
                )
            except (ClosedResourceError, asyncio.CancelledError) as error:
                if self._should_propagate_cancelled_error(error):
                    raise
                logger.warning(
                    "MCP client '%s' session interrupted while listing tools; "
                    "trying recovery",
                    client_name,
                )
                recovered_client = await self._recover_mcp_client(client)
                if recovered_client is not None:
                    self._mcp_clients[i] = recovered_client
                    try:
                        await self.toolkit.register_mcp_client(
                            recovered_client,
                            namesake_strategy=namesake_strategy,
                        )
                        continue
                    except asyncio.CancelledError as recover_error:
                        if self._should_propagate_cancelled_error(
                            recover_error,
                        ):
                            raise
                        logger.warning(
                            "MCP client '%s' registration cancelled after "
                            "recovery, skipping",
                            client_name,
                        )
                    except Exception as e:  # pylint: disable=broad-except
                        logger.warning(
                            "MCP client '%s' still unavailable after "
                            "recovery, skipping: %s",
                            client_name,
                            e,
                        )
                else:
                    logger.warning(
                        "MCP client '%s' recovery failed, skipping",
                        client_name,
                    )
            except Exception as e:  # pylint: disable=broad-except
                logger.exception(
                    "Unexpected error registering MCP client '%s': %s",
                    client_name,
                    e,
                )
                raise

    async def _recover_mcp_client(self, client: Any) -> Any | None:
        """Recover MCP client from broken session and return healthy client."""
        if await self._reconnect_mcp_client(client):
            return client

        rebuilt_client = self._rebuild_mcp_client(client)
        if rebuilt_client is None:
            return None

        if await self._reconnect_mcp_client(rebuilt_client):
            return self._reuse_shared_client_reference(
                original_client=client,
                rebuilt_client=rebuilt_client,
            )

        return None

    @staticmethod
    def _reuse_shared_client_reference(
        original_client: Any,
        rebuilt_client: Any,
    ) -> Any:
        """Keep manager-shared client reference stable after rebuild."""
        original_dict = getattr(original_client, "__dict__", None)
        rebuilt_dict = getattr(rebuilt_client, "__dict__", None)
        if isinstance(original_dict, dict) and isinstance(rebuilt_dict, dict):
            original_dict.update(rebuilt_dict)
            return original_client
        return rebuilt_client

    @staticmethod
    def _should_propagate_cancelled_error(error: BaseException) -> bool:
        """Only swallow MCP-internal cancellations, not task cancellation."""
        if not isinstance(error, asyncio.CancelledError):
            return False

        task = asyncio.current_task()
        if task is None:
            return False

        cancelling = getattr(task, "cancelling", None)
        if callable(cancelling):
            return cancelling() > 0

        # Python < 3.11: Task.cancelling() is unavailable.
        # Fall back to propagating CancelledError to avoid swallowing
        # genuine task cancellations when we cannot inspect the state.
        return True

    @staticmethod
    async def _reconnect_mcp_client(
        client: Any,
        timeout: float = 60.0,
    ) -> bool:
        """Best-effort reconnect for stateful MCP clients."""
        close_fn = getattr(client, "close", None)
        if callable(close_fn):
            try:
                await close_fn()
            except asyncio.CancelledError:  # pylint: disable=try-except-raise
                raise
            except Exception:  # pylint: disable=broad-except
                pass

        connect_fn = getattr(client, "connect", None)
        if not callable(connect_fn):
            return False

        try:
            await asyncio.wait_for(connect_fn(), timeout=timeout)
            return True
        except asyncio.CancelledError:  # pylint: disable=try-except-raise
            raise
        except asyncio.TimeoutError:
            return False
        except Exception:  # pylint: disable=broad-except
            return False

    @staticmethod
    def _rebuild_mcp_client(client: Any) -> Any | None:
        """Rebuild a fresh MCP client instance from stored config metadata."""
        rebuild_info = getattr(client, "_copaw_rebuild_info", None)
        if not isinstance(rebuild_info, dict):
            return None

        transport = rebuild_info.get("transport")
        name = rebuild_info.get("name")

        try:
            if transport == "stdio":
                rebuilt_client = StdIOStatefulClient(
                    name=name,
                    command=rebuild_info.get("command"),
                    args=rebuild_info.get("args", []),
                    env=rebuild_info.get("env", {}),
                    cwd=rebuild_info.get("cwd"),
                )
                setattr(rebuilt_client, "_copaw_rebuild_info", rebuild_info)
                return rebuilt_client

            rebuilt_client = HttpStatefulClient(
                name=name,
                transport=transport,
                url=rebuild_info.get("url"),
                headers=rebuild_info.get("headers"),
            )
            setattr(rebuilt_client, "_copaw_rebuild_info", rebuild_info)
            return rebuilt_client
        except Exception:  # pylint: disable=broad-except
            return None

    async def _reasoning(
        self,
        tool_choice: Literal["auto", "none", "required"] | None = None,
    ) -> Msg:
        """Ensure a stable default tool-choice behavior across providers."""
        tool_choice = normalize_reasoning_tool_choice(
            tool_choice=tool_choice,
            has_tools=bool(self.toolkit.get_json_schemas()),
        )

        return await super()._reasoning(tool_choice=tool_choice)

    async def reply(
        self,
        msg: Msg | list[Msg] | None = None,
        structured_model: Type[BaseModel] | None = None,
    ) -> Msg:
        """Override reply to process file blocks and handle commands.

        Args:
            msg: Input message(s) from user
            structured_model: Optional pydantic model for structured output

        Returns:
            Response message
        """
        # Process file and media blocks in messages
        if msg is not None:
            await process_file_and_media_blocks_in_message(msg)

        # Check if message is a system command
        last_msg = msg[-1] if isinstance(msg, list) else msg
        query = (
            last_msg.get_text_content() if isinstance(last_msg, Msg) else None
        )

        if self.command_handler.is_command(query):
            logger.info(f"Received command: {query}")
            msg = await self.command_handler.handle_command(query)
            await self.print(msg)
            return msg

        # Normal message processing
        return await super().reply(msg=msg, structured_model=structured_model)

    async def interrupt(self, msg: Msg | list[Msg] | None = None) -> None:
        """Interrupt the current reply process and wait for cleanup."""
        if self._reply_task and not self._reply_task.done():
            task = self._reply_task
            task.cancel(msg)
            try:
                await task
            except asyncio.CancelledError:
                if not task.cancelled():
                    raise
            except Exception:
                logger.warning(
                    "Exception occurred during interrupt cleanup",
                    exc_info=True,
                )
