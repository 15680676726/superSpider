# -*- coding: utf-8 -*-
"""Memory compaction hook for managing context window.

This hook monitors token usage and automatically compacts older messages
when the context window approaches its limit, preserving recent messages
and the system prompt.
"""
import logging
from typing import TYPE_CHECKING, Any

from agentscope.agent._react_agent import _MemoryMark, ReActAgent

from copaw.config import load_config
from copaw.constant import MEMORY_COMPACT_KEEP_RECENT
from ...memory.conversation_compaction_service import ConversationCompactionService
from ..utils import (
    check_valid_messages,
    safe_count_message_tokens,
    safe_count_str_tokens,
)

if TYPE_CHECKING:
    from reme.memory.file_based import ReMeInMemoryMemory

logger = logging.getLogger(__name__)


class MemoryCompactionHook:
    """Hook for automatic memory compaction when context is full.

    This hook monitors the token count of messages and triggers compaction
    when it exceeds the threshold. It preserves the system prompt and recent
    messages while summarizing older conversation history.
    """

    def __init__(
        self,
        conversation_compaction_service: ConversationCompactionService,
    ):
        """Initialize memory compaction hook.

        Args:
            conversation_compaction_service: Private conversation compaction service
        """
        self.conversation_compaction_service = conversation_compaction_service

    async def __call__(
        self,
        agent: ReActAgent,
        kwargs: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Pre-reasoning hook to check and compact memory if needed.

        This hook extracts system prompt messages and recent messages,
        builds an estimated full context prompt, and triggers compaction
        when the total estimated token count exceeds the threshold.

        Memory structure:
            [System Prompt (preserved)] + [Compactable (counted)] +
            [Recent (preserved)]

        Args:
            agent: The agent instance
            kwargs: Input arguments to the _reasoning method

        Returns:
            None (hook doesn't modify kwargs)
        """
        try:
            memory: "ReMeInMemoryMemory" = agent.memory
            token_counter = getattr(self.conversation_compaction_service, "token_counter", None)

            system_prompt = getattr(agent, "sys_prompt", "") or ""
            compressed_summary = memory.get_compressed_summary()
            str_token_count = safe_count_str_tokens(
                system_prompt + compressed_summary,
            )

            config = load_config()
            memory_compact_threshold = (
                config.agents.running.memory_compact_threshold
            )
            left_compact_threshold = memory_compact_threshold - str_token_count

            if left_compact_threshold <= 0:
                logger.warning(
                    "The memory_compact_threshold is set too low; "
                    "the combined token length of system_prompt and "
                    "compressed_summary exceeds the configured threshold. "
                    "Alternatively, you could use /clear to reset the context "
                    "and compressed_summary, ensuring the total remains "
                    "below the threshold.",
                )
                return None

            messages = await memory.get_memory(prepend_summary=False)
            formatter = getattr(agent, "formatter", None)
            formatted_messages = (
                await formatter.format(messages)
                if formatter is not None
                else []
            )
            message_token_count = await safe_count_message_tokens(
                formatted_messages,
            )
            if message_token_count + str_token_count <= memory_compact_threshold:
                return None

            running_config = config.agents.running
            enable_tool_result_compact = bool(
                getattr(running_config, "enable_tool_result_compact", False),
            )
            tool_result_compact_keep_n = int(
                getattr(running_config, "tool_result_compact_keep_n", 0),
            )
            if (
                enable_tool_result_compact
                and tool_result_compact_keep_n > 0
                and hasattr(self.conversation_compaction_service, "compact_tool_result")
            ):
                compact_msgs = messages[:-tool_result_compact_keep_n]
                await self.conversation_compaction_service.compact_tool_result(compact_msgs)

            memory_compact_reserve = int(
                getattr(running_config, "memory_compact_reserve", 0),
            )
            if hasattr(self.conversation_compaction_service, "check_context"):
                (
                    messages_to_compact,
                    _,
                    is_valid,
                ) = await self.conversation_compaction_service.check_context(
                    messages=messages,
                    memory_compact_threshold=left_compact_threshold,
                    memory_compact_reserve=memory_compact_reserve,
                    token_counter=token_counter,
                )
            else:
                messages_to_compact = _fallback_messages_to_compact(messages)
                is_valid = True

            if not messages_to_compact:
                return None

            if not is_valid:
                logger.error(
                    "Please include the output of the /history command when "
                    "reporting the bug to the community. Invalid "
                    "messages=%s",
                    messages,
                )
                keep_length: int = MEMORY_COMPACT_KEEP_RECENT
                messages_length = len(messages)
                while keep_length > 0 and not check_valid_messages(
                    messages[max(messages_length - keep_length, 0) :],
                ):
                    keep_length -= 1

                if keep_length > 0:
                    messages_to_compact = messages[
                        : max(messages_length - keep_length, 0)
                    ]
                else:
                    messages_to_compact = messages

            if not messages_to_compact:
                return None

            compact_content = await self.conversation_compaction_service.compact_memory(
                messages=messages_to_compact,
                previous_summary=memory.get_compressed_summary(),
            )

            await agent.memory.update_compressed_summary(compact_content)
            updated_count = await memory.update_messages_mark(
                new_mark=_MemoryMark.COMPRESSED,
                msg_ids=[msg.id for msg in messages_to_compact],
            )
            logger.info(f"Marked {updated_count} messages as compacted")

        except Exception as e:
            logger.error(
                "Failed to compact memory in pre_reasoning hook: %s",
                e,
                exc_info=True,
            )

        return None


def _fallback_messages_to_compact(messages: list[Any]) -> list[Any]:
    preserve_system = 1 if _has_system_message(messages) else 0
    compact_end = max(len(messages) - MEMORY_COMPACT_KEEP_RECENT, preserve_system)
    return messages[preserve_system:compact_end]


def _has_system_message(messages: list[Any]) -> bool:
    if not messages:
        return False
    role = getattr(messages[0], "role", None)
    return role == "system"
