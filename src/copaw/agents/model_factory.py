# -*- coding: utf-8 -*-
"""Factory for creating chat models and formatters.

This module provides a unified factory for creating chat model instances
and their corresponding formatters based on configuration.

Example:
    >>> from copaw.agents.model_factory import create_model_and_formatter
    >>> model, formatter = create_model_and_formatter()
"""


import hashlib
import json
import logging
from typing import Sequence, Tuple, Type, Any
from functools import wraps

from agentscope.formatter import FormatterBase, OpenAIChatFormatter
from agentscope.model import ChatModelBase, OpenAIChatModel
from agentscope.message import Msg
import agentscope

try:
    from agentscope.formatter import AnthropicChatFormatter
    from agentscope.model import AnthropicChatModel
except ImportError:  # pragma: no cover - compatibility fallback
    AnthropicChatFormatter = None
    AnthropicChatModel = None

from copaw.config import load_config
from .utils.tool_message_utils import _sanitize_tool_messages
from ..providers import ProviderManager


def _file_url_to_path(url: str) -> str:
    """
    Strip file:// to path. On Windows file:///C:/path -> C:/path not /C:/path.
    """
    s = url.removeprefix("file://")
    # Windows: file:///C:/path yields "/C:/path"; remove leading slash.
    if len(s) >= 3 and s.startswith("/") and s[1].isalpha() and s[2] == ":":
        s = s[1:]
    return s


def _monkey_patch(func):
    """A monkey patch wrapper for agentscope <= 1.0.16dev"""

    @wraps(func)
    async def wrapper(
        self,
        msgs: list[Msg],
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        for msg in msgs:
            if isinstance(msg.content, str):
                continue
            if isinstance(msg.content, list):
                for block in msg.content:
                    if (
                        block["type"] in ["audio", "image", "video"]
                        and block.get("source", {}).get("type") == "url"
                    ):
                        url = block["source"]["url"]
                        if url.startswith("file://"):
                            block["source"]["url"] = _file_url_to_path(url)
        return await func(self, msgs, **kwargs)

    return wrapper


if agentscope.__version__ in ["1.0.16dev", "1.0.16"]:
    OpenAIChatFormatter.format = _monkey_patch(OpenAIChatFormatter.format)


logger = logging.getLogger(__name__)


# Mapping from chat model class to formatter class
_CHAT_MODEL_FORMATTER_MAP: dict[Type[ChatModelBase], Type[FormatterBase]] = {
    OpenAIChatModel: OpenAIChatFormatter,
}
if AnthropicChatModel is not None and AnthropicChatFormatter is not None:
    _CHAT_MODEL_FORMATTER_MAP[AnthropicChatModel] = AnthropicChatFormatter


def _get_formatter_for_chat_model(
    chat_model_class: Type[ChatModelBase],
) -> Type[FormatterBase]:
    """Get the appropriate formatter class for a chat model.

    Args:
        chat_model_class: The chat model class

    Returns:
        Corresponding formatter class, defaults to OpenAIChatFormatter
    """
    return _CHAT_MODEL_FORMATTER_MAP.get(
        chat_model_class,
        OpenAIChatFormatter,
    )


def _create_file_block_support_formatter(
    base_formatter_class: Type[FormatterBase],
) -> Type[FormatterBase]:
    """Create a formatter class with file block support.

    This factory function extends any Formatter class to support file blocks
    in tool results, which are not natively supported by AgentScope.

    Args:
        base_formatter_class: Base formatter class to extend

    Returns:
        Enhanced formatter class with file block support
    """

    class FileBlockSupportFormatter(base_formatter_class):
        """Formatter with file block support for tool results."""

        # pylint: disable=too-many-branches
        async def _format(self, msgs):
            """Override to sanitize tool messages, handle thinking blocks,
            and relay ``extra_content`` (Gemini thought_signature).

            This prevents OpenAI API errors from improperly paired
            tool messages, preserves reasoning_content from "thinking"
            blocks that the base formatter skips, and ensures
            ``extra_content`` on tool_use blocks (e.g. Gemini
            thought_signature) is carried through to the API request.
            """
            msgs = _sanitize_tool_messages(msgs)

            reasoning_contents = {}
            extra_contents: dict[str, Any] = {}
            for msg in msgs:
                if msg.role != "assistant":
                    continue
                for block in msg.get_content_blocks():
                    if block.get("type") == "thinking":
                        thinking = block.get("thinking", "")
                        if thinking:
                            reasoning_contents[id(msg)] = thinking
                        break
                for block in msg.get_content_blocks():
                    if (
                        block.get("type") == "tool_use"
                        and "extra_content" in block
                    ):
                        extra_contents[block["id"]] = block["extra_content"]

            messages = await super()._format(msgs)

            if extra_contents:
                for message in messages:
                    for tc in message.get("tool_calls", []):
                        ec = extra_contents.get(tc.get("id"))
                        if ec:
                            tc["extra_content"] = ec

            if reasoning_contents:
                in_assistant = [m for m in msgs if m.role == "assistant"]
                out_assistant = [
                    m for m in messages if m.get("role") == "assistant"
                ]
                if len(in_assistant) != len(out_assistant):
                    logger.warning(
                        "Assistant message count mismatch after formatting "
                        "(%d before, %d after). "
                        "Skipping reasoning_content injection.",
                        len(in_assistant),
                        len(out_assistant),
                    )
                else:
                    for in_msg, out_msg in zip(
                        in_assistant,
                        out_assistant,
                    ):
                        reasoning = reasoning_contents.get(id(in_msg))
                        if reasoning:
                            out_msg["reasoning_content"] = reasoning

            return _strip_top_level_message_name(messages)

        @staticmethod
        def convert_tool_result_to_string(
            output: str | list[dict],
        ) -> tuple[str, Sequence[Tuple[str, dict]]]:
            """Extend parent class to support file blocks.

            Uses try-first strategy for compatibility with parent class.

            Args:
                output: Tool result output (string or list of blocks)

            Returns:
                Tuple of (text_representation, multimodal_data)
            """
            if isinstance(output, str):
                return output, []

            # Try parent class method first
            try:
                return base_formatter_class.convert_tool_result_to_string(
                    output,
                )
            except ValueError as e:
                if "Unsupported block type: file" not in str(e):
                    raise

                # Handle output containing file blocks
                textual_output = []
                multimodal_data = []

                for block in output:
                    if not isinstance(block, dict) or "type" not in block:
                        raise ValueError(
                            f"Invalid block: {block}, "
                            "expected a dict with 'type' key",
                        ) from e

                    if block["type"] == "file":
                        file_path = block.get("path", "") or block.get(
                            "url",
                            "",
                        )
                        file_name = block.get("name", file_path)

                        textual_output.append(
                            f"The returned file '{file_name}' "
                            f"can be found at: {file_path}",
                        )
                        multimodal_data.append((file_path, block))
                    else:
                        # Delegate other block types to parent class
                        (
                            text,
                            data,
                        ) = base_formatter_class.convert_tool_result_to_string(
                            [block],
                        )
                        textual_output.append(text)
                        multimodal_data.extend(data)

                if len(textual_output) == 0:
                    return "", multimodal_data
                elif len(textual_output) == 1:
                    return textual_output[0], multimodal_data
                else:
                    return (
                        "\n".join("- " + _ for _ in textual_output),
                        multimodal_data,
                    )

    FileBlockSupportFormatter.__name__ = (
        f"FileBlockSupport{base_formatter_class.__name__}"
    )
    return FileBlockSupportFormatter


def _strip_top_level_message_name(
    messages: list[dict],
) -> list[dict]:
    """Strip top-level `name` from OpenAI chat messages.

    Some strict OpenAI-compatible backends reject `messages[*].name`
    (especially for assistant/tool roles) and may return 500/400 on
    follow-up turns. Keep function/tool names unchanged.
    """
    for message in messages:
        message.pop("name", None)
    return messages


def _slot_payload(slot: object | None) -> dict[str, str]:
    if slot is None:
        return {}
    provider_id = str(getattr(slot, "provider_id", "") or "").strip()
    model_name = str(getattr(slot, "model", "") or "").strip()
    if not provider_id and not model_name:
        return {}
    return {
        "provider_id": provider_id,
        "model": model_name,
    }


def _provider_payload(manager: ProviderManager, provider_id: str) -> dict[str, object]:
    provider = manager.get_provider(provider_id)
    if provider is None:
        return {"provider_missing": True}
    api_key = str(getattr(provider, "api_key", "") or "")
    return {
        "provider_missing": False,
        "base_url": str(getattr(provider, "base_url", "") or ""),
        "chat_model": str(getattr(provider, "chat_model", "") or ""),
        "is_local": bool(getattr(provider, "is_local", False)),
        "require_api_key": bool(getattr(provider, "require_api_key", True)),
        "api_key_sha1": (
            hashlib.sha1(api_key.encode("utf-8")).hexdigest()
            if api_key
            else ""
        ),
    }


def _slot_fingerprint_payload(
    manager: ProviderManager,
    slot: object | None,
) -> dict[str, object]:
    payload = _slot_payload(slot)
    provider_id = payload.get("provider_id", "")
    if provider_id:
        payload["provider"] = _provider_payload(manager, provider_id)
    return payload


def _runtime_fallback_payload(manager: ProviderManager) -> dict[str, object]:
    return {
        "kind": "runtime-fallback",
        "active": _slot_fingerprint_payload(manager, manager.get_active_model()),
        "fallback_enabled": bool(getattr(manager.get_fallback_config(), "enabled", False)),
        "fallback_chain": [
            _slot_fingerprint_payload(manager, slot)
            for slot in manager.get_fallback_slots()
        ],
    }


def describe_runtime_model_surface() -> dict[str, object]:
    """Describe the current runtime model surface for caching/observability."""
    config = load_config()
    routing_cfg = getattr(getattr(config, "agents", None), "llm_routing", None)
    manager = ProviderManager()
    if not bool(getattr(routing_cfg, "enabled", False)):
        return _runtime_fallback_payload(manager)

    local_cfg = getattr(routing_cfg, "local", None)
    cloud_cfg = getattr(routing_cfg, "cloud", None)
    cloud_slot = (
        cloud_cfg
        if str(getattr(cloud_cfg, "provider_id", "") or "").strip()
        and str(getattr(cloud_cfg, "model", "") or "").strip()
        else manager.get_active_model()
    )
    return {
        "kind": "routing",
        "mode": str(getattr(routing_cfg, "mode", "local_first") or "local_first"),
        "default_route": (
            "cloud"
            if getattr(routing_cfg, "mode", "local_first") == "cloud_first"
            else "local"
        ),
        "local": _slot_fingerprint_payload(manager, local_cfg),
        "cloud": _slot_fingerprint_payload(manager, cloud_slot),
        "cloud_source": (
            "routing.cloud"
            if str(getattr(cloud_cfg, "provider_id", "") or "").strip()
            and str(getattr(cloud_cfg, "model", "") or "").strip()
            else "providers.active"
        ),
        "active_runtime_fallback": _runtime_fallback_payload(manager),
    }


def build_runtime_model_fingerprint() -> str:
    payload = describe_runtime_model_surface()
    return hashlib.sha1(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"),
    ).hexdigest()


def create_runtime_chat_model() -> ChatModelBase:
    """Create the runtime chat model surface.

    This delegates to ProviderManager.get_active_chat_model(), which is
    routing-aware when `agents.llm_routing.enabled` is enabled.
    """
    return ProviderManager.get_active_chat_model()


def create_model_and_formatter() -> Tuple[ChatModelBase, FormatterBase]:
    """Factory method to create model and formatter instances.

    This method handles both local and remote models, selecting the
    appropriate chat model class and formatter based on configuration.

    Args:
        llm_cfg: Resolved model configuration. If None, will call
            get_active_llm_config() to fetch the active configuration.

    Returns:
        Tuple of (model_instance, formatter_instance)

    Example:
        >>> model, formatter = create_model_and_formatter()
    """
    model = create_runtime_chat_model()

    # Create the formatter based on chat_model_class
    formatter_model_class = getattr(
        model,
        "preferred_chat_model_class",
        model.__class__,
    )
    formatter = _create_formatter_instance(formatter_model_class)

    return model, formatter


def _create_formatter_instance(
    chat_model_class: Type[ChatModelBase],
) -> FormatterBase:
    """Create a formatter instance for the given chat model class.

    The formatter is enhanced with file block support for handling
    file outputs in tool results.

    Args:
        chat_model_class: The chat model class

    Returns:
        Formatter instance with file block support
    """
    base_formatter_class = _get_formatter_for_chat_model(chat_model_class)
    formatter_class = _create_file_block_support_formatter(
        base_formatter_class,
    )
    return formatter_class()


__all__ = [
    "create_model_and_formatter",
    "create_runtime_chat_model",
]
