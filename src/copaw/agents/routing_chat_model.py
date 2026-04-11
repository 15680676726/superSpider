# -*- coding: utf-8 -*-
"""ChatModel router for local/cloud model selection."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Literal, Type

from agentscope.model import ChatModelBase
from agentscope.model._model_response import ChatResponse
from pydantic import BaseModel

from ..config.config import AgentsLLMRoutingConfig

logger = logging.getLogger(__name__)


Route = Literal["local", "cloud"]


@dataclass
class RoutingDecision:
    route: Route
    reasons: list[str] = field(default_factory=list)


class RoutingPolicy:
    """Select a route using the configured default mode."""

    def __init__(self, cfg: AgentsLLMRoutingConfig):
        self.cfg = cfg

    def decide(
        self,
        *,
        text: str = "",
        channel: str = "",
        tools_available: bool = True,
    ) -> RoutingDecision:
        del text, channel, tools_available

        if getattr(self.cfg, "mode", "local_first") == "cloud_first":
            return RoutingDecision(
                route="cloud",
                reasons=["mode:cloud_first"],
            )

        return RoutingDecision(
            route="local",
            reasons=["mode:local_first"],
        )


@dataclass(frozen=True)
class RoutingEndpoint:
    provider_id: str
    model_name: str
    model: ChatModelBase


class RoutingChatModel(ChatModelBase):
    """A ChatModelBase that routes between local and cloud slots."""

    def __init__(
        self,
        *,
        local_endpoint: RoutingEndpoint,
        cloud_endpoint: RoutingEndpoint,
        routing_cfg: AgentsLLMRoutingConfig,
    ) -> None:
        local_stream = bool(getattr(local_endpoint.model, "stream", True))
        cloud_stream = bool(getattr(cloud_endpoint.model, "stream", True))
        super().__init__(
            model_name="routing",
            stream=bool(local_stream or cloud_stream),
        )
        self.local_endpoint = local_endpoint
        self.cloud_endpoint = cloud_endpoint
        self.routing_cfg = routing_cfg
        self.policy = RoutingPolicy(routing_cfg)
        # Help upstream formatters pick the correct format family.
        self.preferred_chat_model_class = getattr(
            local_endpoint.model,
            "preferred_chat_model_class",
            local_endpoint.model.__class__,
        )

    async def _call_endpoint(
        self,
        *,
        endpoint: RoutingEndpoint,
        messages: list[dict],
        tools: list[dict] | None,
        tool_choice: Literal["auto", "none", "required"] | str | None,
        structured_model: Type[BaseModel] | None,
        kwargs: dict[str, Any],
    ) -> ChatResponse | AsyncGenerator[ChatResponse, None]:
        original_stream = getattr(endpoint.model, "stream", None)
        stream_overridden = isinstance(original_stream, bool)
        if stream_overridden:
            try:
                setattr(endpoint.model, "stream", bool(self.stream))
            except Exception:
                stream_overridden = False
        try:
            return await endpoint.model(
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                structured_model=structured_model,
                **kwargs,
            )
        finally:
            if stream_overridden:
                try:
                    setattr(endpoint.model, "stream", original_stream)
                except Exception:
                    logger.debug(
                        "Failed to restore endpoint stream flag: provider=%s model=%s",
                        endpoint.provider_id,
                        endpoint.model_name,
                    )

    async def _call_with_fallback(
        self,
        *,
        primary: RoutingEndpoint,
        secondary: RoutingEndpoint,
        messages: list[dict],
        tools: list[dict] | None,
        tool_choice: Literal["auto", "none", "required"] | str | None,
        structured_model: Type[BaseModel] | None,
        kwargs: dict[str, Any],
    ) -> ChatResponse | AsyncGenerator[ChatResponse, None]:
        try:
            result = await self._call_endpoint(
                endpoint=primary,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                structured_model=structured_model,
                kwargs=kwargs,
            )
        except Exception:
            logger.exception(
                "LLM routing primary endpoint failed: provider=%s model=%s; falling back to provider=%s model=%s",
                primary.provider_id,
                primary.model_name,
                secondary.provider_id,
                secondary.model_name,
            )
            return await self._call_endpoint(
                endpoint=secondary,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                structured_model=structured_model,
                kwargs=kwargs,
            )

        if not hasattr(result, "__aiter__"):
            return result

        async def _stream_with_fallback() -> AsyncGenerator[ChatResponse, None]:
            yielded = False
            try:
                async for item in result:  # type: ignore[misc]
                    yielded = True
                    yield item
                return
            except Exception:
                # Mid-stream failures cannot be safely resumed from the secondary.
                # But first-token failures can be retried on the other endpoint.
                if yielded:
                    raise
                logger.exception(
                    "LLM routing primary stream failed before yielding tokens; falling back to provider=%s model=%s",
                    secondary.provider_id,
                    secondary.model_name,
                )
                resumed = await self._call_endpoint(
                    endpoint=secondary,
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    structured_model=structured_model,
                    kwargs=kwargs,
                )
                if hasattr(resumed, "__aiter__"):
                    async for item in resumed:  # type: ignore[misc]
                        yield item
                    return
                yield resumed  # type: ignore[misc]

        return _stream_with_fallback()

    async def __call__(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        tool_choice: Literal["auto", "none", "required"] | str | None = None,
        structured_model: Type[BaseModel] | None = None,
        **kwargs: Any,
    ) -> ChatResponse | AsyncGenerator[ChatResponse, None]:
        text = " ".join(
            message["content"]
            for message in messages
            if message.get("role") == "user"
            and isinstance(message.get("content"), str)
        )
        decision = self.policy.decide(
            text=text,
            tools_available=tools is not None,
        )
        endpoint = (
            self.local_endpoint
            if decision.route == "local"
            else self.cloud_endpoint
        )
        fallback = (
            self.cloud_endpoint
            if endpoint is self.local_endpoint
            else self.local_endpoint
        )

        logger.debug(
            "LLM routing decision: route=%s provider=%s model=%s reasons=%s",
            decision.route,
            endpoint.provider_id,
            endpoint.model_name,
            ",".join(decision.reasons),
        )

        return await self._call_with_fallback(
            primary=endpoint,
            secondary=fallback,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            structured_model=structured_model,
            kwargs=dict(kwargs),
        )
