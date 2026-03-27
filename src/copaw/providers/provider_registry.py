# -*- coding: utf-8 -*-
"""Provider registry and built-in provider definitions."""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List

from .anthropic_provider import AnthropicProvider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider
from .provider import DefaultProvider, ModelInfo, Provider, ProviderInfo

if TYPE_CHECKING:
    from .provider_manager import ProviderManager


MODELSCOPE_MODELS: List[ModelInfo] = [
    ModelInfo(
        id="Qwen/Qwen3-235B-A22B-Instruct-2507",
        name="Qwen3-235B-A22B-Instruct-2507",
    ),
    ModelInfo(id="deepseek-ai/DeepSeek-V3.2", name="DeepSeek-V3.2"),
]

DASHSCOPE_MODELS: List[ModelInfo] = [
    ModelInfo(id="qwen3-max", name="Qwen3 Max"),
    ModelInfo(
        id="qwen3-235b-a22b-thinking-2507",
        name="Qwen3 235B A22B Thinking",
    ),
    ModelInfo(id="deepseek-v3.2", name="DeepSeek-V3.2"),
]

ALIYUN_CODINGPLAN_MODELS: List[ModelInfo] = [
    ModelInfo(id="qwen3.5-plus", name="Qwen3.5 Plus"),
    ModelInfo(id="glm-5", name="GLM-5"),
    ModelInfo(id="glm-4.7", name="GLM-4.7"),
    ModelInfo(id="MiniMax-M2.5", name="MiniMax M2.5"),
    ModelInfo(id="kimi-k2.5", name="Kimi K2.5"),
    ModelInfo(id="qwen3-max-2026-01-23", name="Qwen3 Max 2026-01-23"),
    ModelInfo(id="qwen3-coder-next", name="Qwen3 Coder Next"),
    ModelInfo(id="qwen3-coder-plus", name="Qwen3 Coder Plus"),
]

OPENAI_MODELS: List[ModelInfo] = [
    ModelInfo(id="gpt-5.2", name="GPT-5.2"),
    ModelInfo(id="gpt-5", name="GPT-5"),
    ModelInfo(id="gpt-5-mini", name="GPT-5 Mini"),
    ModelInfo(id="gpt-5-nano", name="GPT-5 Nano"),
    ModelInfo(id="gpt-4.1", name="GPT-4.1"),
    ModelInfo(id="gpt-4.1-mini", name="GPT-4.1 Mini"),
    ModelInfo(id="gpt-4.1-nano", name="GPT-4.1 Nano"),
    ModelInfo(id="o3", name="o3"),
    ModelInfo(id="o4-mini", name="o4-mini"),
    ModelInfo(id="gpt-4o", name="GPT-4o"),
    ModelInfo(id="gpt-4o-mini", name="GPT-4o Mini"),
]

AZURE_OPENAI_MODELS: List[ModelInfo] = [
    ModelInfo(id="gpt-5-chat", name="GPT-5 Chat"),
    ModelInfo(id="gpt-5-mini", name="GPT-5 Mini"),
    ModelInfo(id="gpt-5-nano", name="GPT-5 Nano"),
    ModelInfo(id="gpt-4.1", name="GPT-4.1"),
    ModelInfo(id="gpt-4.1-mini", name="GPT-4.1 Mini"),
    ModelInfo(id="gpt-4.1-nano", name="GPT-4.1 Nano"),
    ModelInfo(id="gpt-4o", name="GPT-4o"),
    ModelInfo(id="gpt-4o-mini", name="GPT-4o Mini"),
]

ANTHROPIC_MODELS: List[ModelInfo] = []

PROVIDER_MODELSCOPE = OpenAIProvider(
    id="modelscope",
    name="ModelScope",
    base_url="https://api-inference.modelscope.cn/v1",
    api_key_prefix="ms",
    models=MODELSCOPE_MODELS,
    freeze_url=True,
)

PROVIDER_DASHSCOPE = OpenAIProvider(
    id="dashscope",
    name="DashScope",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key_prefix="sk",
    models=DASHSCOPE_MODELS,
    freeze_url=True,
)

PROVIDER_ALIYUN_CODINGPLAN = OpenAIProvider(
    id="aliyun-codingplan",
    name="Aliyun Coding Plan",
    base_url="https://coding.dashscope.aliyuncs.com/v1",
    api_key_prefix="sk-sp",
    models=ALIYUN_CODINGPLAN_MODELS,
    freeze_url=True,
)

PROVIDER_LLAMACPP = DefaultProvider(
    id="llamacpp",
    name="llama.cpp (Local)",
    is_local=True,
    require_api_key=False,
)

PROVIDER_MLX = DefaultProvider(
    id="mlx",
    name="MLX (Local, Apple Silicon)",
    is_local=True,
    require_api_key=False,
)

PROVIDER_OPENAI = OpenAIProvider(
    id="openai",
    name="OpenAI",
    base_url="https://api.openai.com/v1",
    api_key_prefix="sk-",
    models=OPENAI_MODELS,
    freeze_url=True,
)

PROVIDER_AZURE_OPENAI = OpenAIProvider(
    id="azure-openai",
    name="Azure OpenAI",
    api_key_prefix="",
    models=AZURE_OPENAI_MODELS,
)

PROVIDER_ANTHROPIC = AnthropicProvider(
    id="anthropic",
    name="Anthropic",
    base_url="https://api.anthropic.com",
    api_key_prefix="sk-ant-",
    models=ANTHROPIC_MODELS,
    chat_model="AnthropicChatModel",
    freeze_url=True,
)

PROVIDER_OLLAMA = OllamaProvider(
    id="ollama",
    name="Ollama",
    require_api_key=False,
)


class ProviderRegistryService:
    """Manage builtin/custom provider registries."""

    def __init__(self, manager: ProviderManager) -> None:
        self._manager = manager

    def builtin_provider_definitions(self) -> List[Provider]:
        return [
            PROVIDER_MODELSCOPE,
            PROVIDER_DASHSCOPE,
            PROVIDER_ALIYUN_CODINGPLAN,
            PROVIDER_OPENAI,
            PROVIDER_AZURE_OPENAI,
            PROVIDER_ANTHROPIC,
            PROVIDER_OLLAMA,
            PROVIDER_LLAMACPP,
            PROVIDER_MLX,
        ]

    def init_builtins(self) -> None:
        for provider in self.builtin_provider_definitions():
            self.add_builtin(provider)

    def add_builtin(self, provider: Provider) -> None:
        self._manager.builtin_providers[provider.id] = provider.model_copy(deep=True)

    def is_builtin_provider(self, provider_id: str) -> bool:
        return provider_id in self._manager.builtin_providers

    async def list_provider_info(self) -> List[ProviderInfo]:
        provider_infos = []
        for provider in self._manager.builtin_providers.values():
            provider_infos.append(await provider.get_info())
        for provider in self._manager.custom_providers.values():
            provider_infos.append(await provider.get_info())
        return provider_infos

    def get_provider(self, provider_id: str) -> Provider | None:
        if provider_id in self._manager.builtin_providers:
            return self._manager.builtin_providers[provider_id]
        if provider_id in self._manager.custom_providers:
            return self._manager.custom_providers[provider_id]
        return None

    async def get_provider_info(self, provider_id: str) -> ProviderInfo | None:
        provider = self.get_provider(provider_id)
        return await provider.get_info() if provider else None

    def provider_from_data(self, data: Dict) -> Provider:
        provider_id = str(data.get("id", ""))
        chat_model = str(data.get("chat_model", ""))

        if provider_id == "anthropic" or chat_model == "AnthropicChatModel":
            return AnthropicProvider.model_validate(data)
        if provider_id == "ollama" or chat_model == "OllamaChatModel":
            return OllamaProvider.model_validate(data)
        if data.get("is_local", False):
            return DefaultProvider.model_validate(data)
        return OpenAIProvider.model_validate(data)

    def update_local_models(self) -> None:
        try:
            from ..local_models.manager import list_local_models
            from ..local_models.schema import BackendType

            llamacpp_models: list[ModelInfo] = []
            mlx_models: list[ModelInfo] = []

            for model in list_local_models():
                info = ModelInfo(id=model.id, name=model.display_name)
                if model.backend == BackendType.LLAMACPP:
                    llamacpp_models.append(info)
                elif model.backend == BackendType.MLX:
                    mlx_models.append(info)
            local_llamacpp = self.get_provider("llamacpp")
            local_mlx = self.get_provider("mlx")
            if local_llamacpp is not None:
                local_llamacpp.models = llamacpp_models
            if local_mlx is not None:
                local_mlx.models = mlx_models
        except ImportError:
            pass
