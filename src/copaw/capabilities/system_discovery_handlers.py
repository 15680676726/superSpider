# -*- coding: utf-8 -*-
from __future__ import annotations

import inspect


class SystemCapabilityDiscoveryFacade:
    def __init__(
        self,
        *,
        capability_discovery_service: object | None = None,
    ) -> None:
        self._capability_discovery_service = capability_discovery_service

    def set_capability_discovery_service(
        self,
        capability_discovery_service: object | None,
    ) -> None:
        self._capability_discovery_service = capability_discovery_service

    def set_state_store(self, state_store: object | None) -> None:
        service = self._capability_discovery_service
        if service is None:
            return
        setter = getattr(service, "set_state_store", None)
        if callable(setter):
            setter(state_store)

    async def handle_discover_capabilities(
        self,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        service = self._capability_discovery_service
        if service is None:
            return {
                "success": False,
                "error": "Capability discovery service is not available",
            }
        discover = getattr(service, "discover", None)
        if not callable(discover):
            return {
                "success": False,
                "error": "Capability discovery entrypoint is not available",
            }
        result = discover(resolved_payload)
        if inspect.isawaitable(result):
            result = await result
        if isinstance(result, dict):
            return result
        return {
            "success": False,
            "error": "Capability discovery returned an unexpected result",
        }
