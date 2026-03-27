# -*- coding: utf-8 -*-
"""AgentScope/runtime message conversion helpers for the runtime layer."""
from __future__ import annotations

import json
from typing import List, Optional, Union
from urllib.parse import urlparse

from agentscope.message import Msg
from agentscope_runtime.engine.helpers.agent_api_builder import ResponseBuilder
from agentscope_runtime.engine.schemas.agent_schemas import (
    FunctionCall,
    FunctionCallOutput,
    Message,
    MessageType,
)


def build_env_context(
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    channel: Optional[str] = None,
    working_dir: Optional[str] = None,
    add_hint: bool = True,
) -> str:
    """Build prompt context for the current runtime request."""
    parts = []
    if session_id is not None:
        parts.append(f"- Current session_id: {session_id}")
    if user_id is not None:
        parts.append(f"- Current user_id: {user_id}")
    if channel is not None:
        parts.append(f"- Current channel: {channel}")
    if working_dir is not None:
        parts.append(f"- Working directory: {working_dir}")
    if add_hint:
        parts.append(
            "- Important hints:\n"
            "  1. Prefer mounted skills or capabilities when completing work. "
            "If a capability is unclear, inspect its docs before using it.\n"
            "  2. Before writing a file, read it first when you need to avoid "
            "overwriting existing content, then edit or append precisely.",
        )
    return "====================\n" + "\n".join(parts) + "\n===================="


def agentscope_msg_to_message(
    messages: Union[Msg, List[Msg]],
) -> List[Message]:
    """Convert AgentScope Msg objects into runtime Message objects."""
    if isinstance(messages, Msg):
        msgs = [messages]
    elif isinstance(messages, list):
        msgs = messages
    else:
        raise TypeError(f"Expected Msg or list[Msg], got {type(messages)}")

    results: List[Message] = []

    for msg in msgs:
        role = msg.role or "assistant"

        if isinstance(msg.content, str):
            response_builder = ResponseBuilder()
            message_builder = response_builder.create_message_builder(
                role=role,
                message_type=MessageType.MESSAGE,
            )
            message_builder.message.metadata = {
                "original_id": msg.id,
                "original_name": msg.name,
                "metadata": msg.metadata,
            }
            content_builder = message_builder.create_content_builder(content_type="text")
            content_builder.set_text(msg.content)
            content_builder.complete()
            message_builder.complete()
            results.append(message_builder.get_message_data())
            continue

        current_message_builder = None
        current_type = None

        for block in msg.content:
            if isinstance(block, dict):
                block_type = block.get("type", "text")
            else:
                continue

            if block_type == "text":
                if current_type != MessageType.MESSAGE:
                    if current_message_builder:
                        current_message_builder.complete()
                        results.append(current_message_builder.get_message_data())
                    response_builder = ResponseBuilder()
                    current_message_builder = response_builder.create_message_builder(
                        role=role,
                        message_type=MessageType.MESSAGE,
                    )
                    current_message_builder.message.metadata = {
                        "original_id": msg.id,
                        "original_name": msg.name,
                        "metadata": msg.metadata,
                    }
                    current_type = MessageType.MESSAGE
                content_builder = current_message_builder.create_content_builder(
                    content_type="text",
                )
                content_builder.set_text(block.get("text", ""))
                content_builder.complete()

            elif block_type == "thinking":
                if current_type != MessageType.REASONING:
                    if current_message_builder:
                        current_message_builder.complete()
                        results.append(current_message_builder.get_message_data())
                    response_builder = ResponseBuilder()
                    current_message_builder = response_builder.create_message_builder(
                        role=role,
                        message_type=MessageType.REASONING,
                    )
                    current_message_builder.message.metadata = {
                        "original_id": msg.id,
                        "original_name": msg.name,
                        "metadata": msg.metadata,
                    }
                    current_type = MessageType.REASONING
                content_builder = current_message_builder.create_content_builder(
                    content_type="text",
                )
                content_builder.set_text(block.get("thinking", ""))
                content_builder.complete()

            elif block_type == "tool_use":
                if current_message_builder:
                    current_message_builder.complete()
                    results.append(current_message_builder.get_message_data())
                response_builder = ResponseBuilder()
                current_message_builder = response_builder.create_message_builder(
                    role=role,
                    message_type=MessageType.PLUGIN_CALL,
                )
                current_message_builder.message.metadata = {
                    "original_id": msg.id,
                    "original_name": msg.name,
                    "metadata": msg.metadata,
                }
                current_type = MessageType.PLUGIN_CALL
                content_builder = current_message_builder.create_content_builder(
                    content_type="data",
                )
                if isinstance(block.get("input"), (dict, list)):
                    arguments = json.dumps(block.get("input"), ensure_ascii=False)
                else:
                    arguments = block.get("input")
                content_builder.set_data(
                    FunctionCall(
                        call_id=block.get("id"),
                        name=block.get("name"),
                        arguments=arguments,
                    ).model_dump(),
                )
                content_builder.complete()

            elif block_type == "tool_result":
                if current_message_builder:
                    current_message_builder.complete()
                    results.append(current_message_builder.get_message_data())
                response_builder = ResponseBuilder()
                current_message_builder = response_builder.create_message_builder(
                    role=role,
                    message_type=MessageType.PLUGIN_CALL_OUTPUT,
                )
                current_message_builder.message.metadata = {
                    "original_id": msg.id,
                    "original_name": msg.name,
                    "metadata": msg.metadata,
                }
                current_type = MessageType.PLUGIN_CALL_OUTPUT
                content_builder = current_message_builder.create_content_builder(
                    content_type="data",
                )
                if isinstance(block.get("output"), (dict, list)):
                    output = json.dumps(block.get("output"), ensure_ascii=False)
                else:
                    output = block.get("output")
                content_builder.set_data(
                    FunctionCallOutput(
                        call_id=block.get("id"),
                        name=block.get("name"),
                        output=output,
                    ).model_dump(exclude_none=True),
                )
                content_builder.complete()

            elif block_type == "image":
                if current_type != MessageType.MESSAGE:
                    if current_message_builder:
                        current_message_builder.complete()
                        results.append(current_message_builder.get_message_data())
                    response_builder = ResponseBuilder()
                    current_message_builder = response_builder.create_message_builder(
                        role=role,
                        message_type=MessageType.MESSAGE,
                    )
                    current_message_builder.message.metadata = {
                        "original_id": msg.id,
                        "original_name": msg.name,
                        "metadata": msg.metadata,
                    }
                    current_type = MessageType.MESSAGE
                content_builder = current_message_builder.create_content_builder(
                    content_type="image",
                )
                source = block.get("source")
                if isinstance(source, dict) and source.get("type") == "url":
                    content_builder.set_image_url(source.get("url"))
                elif isinstance(source, dict) and source.get("type") == "base64":
                    media_type = source.get("media_type", "image/jpeg")
                    base64_data = source.get("data", "")
                    content_builder.set_image_url(
                        f"data:{media_type};base64,{base64_data}",
                    )
                content_builder.complete()

            elif block_type == "audio":
                if current_type != MessageType.MESSAGE:
                    if current_message_builder:
                        current_message_builder.complete()
                        results.append(current_message_builder.get_message_data())
                    response_builder = ResponseBuilder()
                    current_message_builder = response_builder.create_message_builder(
                        role=role,
                        message_type=MessageType.MESSAGE,
                    )
                    current_message_builder.message.metadata = {
                        "original_id": msg.id,
                        "original_name": msg.name,
                        "metadata": msg.metadata,
                    }
                    current_type = MessageType.MESSAGE
                content_builder = current_message_builder.create_content_builder(
                    content_type="audio",
                )
                source = block.get("source")
                if isinstance(source, dict) and source.get("type") == "url":
                    url = source.get("url")
                    content_builder.content.data = url
                    try:
                        content_builder.content.format = urlparse(url).path.split(".")[-1]
                    except (AttributeError, IndexError, ValueError):
                        content_builder.content.format = None
                elif isinstance(source, dict) and source.get("type") == "base64":
                    media_type = source.get("media_type")
                    base64_data = source.get("data", "")
                    content_builder.content.data = (
                        f"data:{media_type};base64,{base64_data}"
                    )
                    content_builder.content.format = media_type
                content_builder.complete()

            else:
                if current_type != MessageType.MESSAGE:
                    if current_message_builder:
                        current_message_builder.complete()
                        results.append(current_message_builder.get_message_data())
                    response_builder = ResponseBuilder()
                    current_message_builder = response_builder.create_message_builder(
                        role=role,
                        message_type=MessageType.MESSAGE,
                    )
                    current_message_builder.message.metadata = {
                        "original_id": msg.id,
                        "original_name": msg.name,
                        "metadata": msg.metadata,
                    }
                    current_type = MessageType.MESSAGE
                content_builder = current_message_builder.create_content_builder(
                    content_type="text",
                )
                content_builder.set_text(str(block))
                content_builder.complete()

        if current_message_builder:
            current_message_builder.complete()
            results.append(current_message_builder.get_message_data())

    return results


__all__ = ["agentscope_msg_to_message", "build_env_context"]
