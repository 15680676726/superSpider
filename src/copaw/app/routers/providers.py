# -*- coding: utf-8 -*-
"""API routes for LLM providers and models."""

from __future__ import annotations

from typing import List, Literal, Optional
from copy import deepcopy

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Request
from pydantic import BaseModel, Field

from ...providers.provider import ProviderInfo, ModelInfo
from ...providers.provider_admin_service import ProviderAdminService
from ...providers.provider_manager import (
    ActiveModelsInfo,
    ProviderFallbackConfig,
)
from ...providers.runtime_provider_facade import (
    ProviderRuntimeSurface,
)

router = APIRouter(prefix="/models", tags=["models"])
admin_router = APIRouter(prefix="/providers/admin", tags=["provider-admin"])

ChatModelName = Literal["OpenAIChatModel", "AnthropicChatModel"]


def get_runtime_provider(request: Request) -> ProviderRuntimeSurface:
    """Get the canonical runtime provider surface from app state."""
    runtime_provider = getattr(request.app.state, "runtime_provider", None)
    if runtime_provider is not None:
        return runtime_provider
    raise HTTPException(
        status_code=500,
        detail="runtime_provider is not attached to app.state",
    )


def get_provider_admin_service(request: Request) -> object:
    """Get the canonical provider admin service from app state."""
    service = getattr(request.app.state, "provider_admin_service", None)
    if service is not None:
        return service
    raise HTTPException(
        status_code=500,
        detail="provider admin surface is not attached to app.state",
    )


def _clone_provider_for_test(provider: object) -> object:
    model_copy = getattr(provider, "model_copy", None)
    if callable(model_copy):
        return model_copy(deep=True)
    return deepcopy(provider)


class ProviderConfigRequest(BaseModel):
    api_key: Optional[str] = Field(default=None)
    base_url: Optional[str] = Field(default=None)
    chat_model: Optional[ChatModelName] = Field(
        default=None,
        description="Chat model class name for protocol selection",
    )


class ModelSlotRequest(BaseModel):
    provider_id: str = Field(..., description="Provider to use")
    model: str = Field(..., description="Model identifier")


class CreateCustomProviderRequest(BaseModel):
    id: str = Field(...)
    name: str = Field(...)
    default_base_url: str = Field(default="")
    api_key_prefix: str = Field(default="")
    chat_model: ChatModelName = Field(default="OpenAIChatModel")
    models: List[ModelInfo] = Field(default_factory=list)


class AddModelRequest(BaseModel):
    id: str = Field(...)
    name: str = Field(...)


@router.get(
    "",
    response_model=List[ProviderInfo],
    summary="List all providers",
)
async def list_all_providers(
    runtime_provider: ProviderRuntimeSurface = Depends(get_runtime_provider),
) -> List[ProviderInfo]:
    return await runtime_provider.list_provider_info()


@admin_router.put(
    "/{provider_id}/config",
    response_model=ProviderInfo,
    summary="Configure a provider",
)
async def configure_provider(
    admin_service: object = Depends(get_provider_admin_service),
    provider_id: str = Path(...),
    body: ProviderConfigRequest = Body(...),
) -> ProviderInfo:
    try:
        return await admin_service.configure_provider(
            provider_id,
            api_key=body.api_key,
            base_url=body.base_url,
            chat_model=body.chat_model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@admin_router.post(
    "/custom-providers",
    response_model=ProviderInfo,
    summary="Create a custom provider",
    status_code=201,
)
async def create_custom_provider_endpoint(
    admin_service: object = Depends(get_provider_admin_service),
    body: CreateCustomProviderRequest = Body(...),
) -> ProviderInfo:
    try:
        provider_info = await admin_service.create_custom_provider(
            ProviderInfo(
                id=body.id,
                name=body.name,
                base_url=body.default_base_url,
                api_key_prefix=body.api_key_prefix,
                chat_model=body.chat_model,
                extra_models=body.models,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return provider_info


class TestConnectionResponse(BaseModel):
    success: bool = Field(..., description="Whether the test passed")
    message: str = Field(..., description="Human-readable result message")


class TestProviderRequest(BaseModel):
    api_key: Optional[str] = Field(
        default=None,
        description="Optional API key to test",
    )
    base_url: Optional[str] = Field(
        default=None,
        description="Optional Base URL to test",
    )
    chat_model: Optional[ChatModelName] = Field(
        default=None,
        description="Optional chat model class to test protocol behavior",
    )


class TestModelRequest(BaseModel):
    model_id: str = Field(..., description="Model ID to test")


class DiscoverModelsRequest(BaseModel):
    api_key: Optional[str] = Field(
        default=None,
        description="Optional API key to use for discovery",
    )
    base_url: Optional[str] = Field(
        default=None,
        description="Optional Base URL to use for discovery",
    )
    chat_model: Optional[ChatModelName] = Field(
        default=None,
        description="Optional chat model class to use for discovery",
    )


class DiscoverModelsResponse(BaseModel):
    success: bool = Field(..., description="Whether discovery succeeded")
    models: List[ModelInfo] = Field(
        default_factory=list,
        description="Discovered models",
    )
    message: str = Field(
        default="",
        description="Human-readable result message",
    )
    added_count: int = Field(
        default=0,
        description="How many new models were added into provider config",
    )


@router.post(
    "/{provider_id}/test",
    response_model=TestConnectionResponse,
    summary="Test provider connection",
)
async def test_provider(
    runtime_provider: ProviderRuntimeSurface = Depends(get_runtime_provider),
    provider_id: str = Path(...),
    body: Optional[TestProviderRequest] = Body(default=None),
) -> TestConnectionResponse:
    """Test if a provider's URL and API key are valid."""
    try:
        provider = runtime_provider.get_provider(provider_id)
        if provider is None:
            raise ValueError(f"Provider '{provider_id}' not found")
        # Ensure we don't accidentally modify provider config during test
        tmp_provider = _clone_provider_for_test(provider)
        if body and body.api_key:
            tmp_provider.api_key = body.api_key
        if body and body.base_url:
            tmp_provider.base_url = body.base_url
        ok = await tmp_provider.check_connection()
        return TestConnectionResponse(
            success=ok,
            message="Connection successful" if ok else "Connection failed",
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@admin_router.post(
    "/{provider_id}/discover",
    response_model=DiscoverModelsResponse,
    summary="Discover available models from provider",
)
async def discover_models(
    admin_service: object = Depends(get_provider_admin_service),
    provider_id: str = Path(...),
    body: Optional[DiscoverModelsRequest] = Body(default=None),
) -> DiscoverModelsResponse:
    try:
        try:
            result = await admin_service.discover_provider_models(
                provider_id,
                api_key=body.api_key if body else None,
                base_url=body.base_url if body else None,
                chat_model=body.chat_model if body else None,
            )
            success = True
        except Exception:
            result = []
            success = False
        return DiscoverModelsResponse(success=success, models=result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/{provider_id}/models/test",
    response_model=TestConnectionResponse,
    summary="Test a specific model",
)
async def test_model(
    runtime_provider: ProviderRuntimeSurface = Depends(get_runtime_provider),
    provider_id: str = Path(...),
    body: TestModelRequest = Body(...),
) -> TestConnectionResponse:
    """Test if a specific model works with the configured provider."""
    try:
        provider = runtime_provider.get_provider(provider_id)
        if provider is None:
            raise ValueError(f"Provider '{provider_id}' not found")
        ok = await provider.check_model_connection(model_id=body.model_id)
        return TestConnectionResponse(
            success=ok,
            message="Connection successful" if ok else "Connection failed",
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@admin_router.delete(
    "/custom-providers/{provider_id}",
    response_model=List[ProviderInfo],
    summary="Delete a custom provider",
)
async def delete_custom_provider_endpoint(
    request: Request,
    admin_service: object = Depends(get_provider_admin_service),
    provider_id: str = Path(...),
) -> List[ProviderInfo]:
    try:
        _ = request
        ok = admin_service.remove_custom_provider(provider_id)
        if not ok:
            raise ValueError(f"Custom Provider '{provider_id}' not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await get_runtime_provider(request).list_provider_info()


@admin_router.post(
    "/{provider_id}/models",
    response_model=ProviderInfo,
    summary="Add a model to a provider",
    status_code=201,
)
async def add_model_endpoint(
    admin_service: object = Depends(get_provider_admin_service),
    provider_id: str = Path(...),
    body: AddModelRequest = Body(...),
) -> ProviderInfo:
    try:
        provider = await admin_service.add_provider_model(
            provider_id,
            model_id=body.id,
            name=body.name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return provider


@admin_router.delete(
    "/{provider_id}/models/{model_id:path}",
    response_model=ProviderInfo,
    summary="Remove a model from a provider",
)
async def remove_model_endpoint(
    admin_service: object = Depends(get_provider_admin_service),
    provider_id: str = Path(...),
    model_id: str = Path(...),
) -> ProviderInfo:
    try:
        provider = await admin_service.remove_provider_model(
            provider_id,
            model_id=model_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return provider


@router.get(
    "/active",
    response_model=ActiveModelsInfo,
    summary="Get active LLM",
)
async def get_active_models(
    runtime_provider: ProviderRuntimeSurface = Depends(get_runtime_provider),
) -> ActiveModelsInfo:
    active_model = runtime_provider.get_active_model()
    resolved_slot, fallback_applied, resolution_reason, unavailable_candidates = (
        runtime_provider.resolve_model_slot()
    )
    fallback_config = runtime_provider.get_fallback_config()
    return ActiveModelsInfo(
        active_llm=active_model,
        resolved_llm=resolved_slot,
        fallback_enabled=fallback_config.enabled,
        fallback_chain=list(fallback_config.candidates),
        fallback_applied=fallback_applied,
        resolution_reason=resolution_reason,
        unavailable_candidates=unavailable_candidates,
    )


@admin_router.put(
    "/active",
    response_model=ActiveModelsInfo,
    summary="Set active LLM",
)
async def set_active_model(
    admin_service: object = Depends(get_provider_admin_service),
    body: ModelSlotRequest = Body(...),
) -> ActiveModelsInfo:
    try:
        return await admin_service.set_active_model(
            provider_id=body.provider_id,
            model_id=body.model,
        )
    except ValueError as exc:
        message = str(exc)
        lower_msg = message.lower()
        if "provider" in lower_msg and "not found" in lower_msg:
            # Missing provider
            raise HTTPException(status_code=404, detail=message) from exc
        # Invalid model, unreachable provider, or other configuration error
        raise HTTPException(status_code=400, detail=message) from exc


@router.get(
    "/fallback",
    response_model=ProviderFallbackConfig,
    summary="Get provider fallback policy",
)
async def get_provider_fallback(
    runtime_provider: ProviderRuntimeSurface = Depends(get_runtime_provider),
) -> ProviderFallbackConfig:
    return runtime_provider.get_fallback_config()


@admin_router.put(
    "/fallback",
    response_model=ProviderFallbackConfig,
    summary="Set provider fallback policy",
)
async def set_provider_fallback(
    admin_service: object = Depends(get_provider_admin_service),
    body: ProviderFallbackConfig = Body(...),
) -> ProviderFallbackConfig:
    try:
        return admin_service.set_fallback_config(
            enabled=body.enabled,
            candidates=list(body.candidates),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
