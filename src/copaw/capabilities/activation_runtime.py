# -*- coding: utf-8 -*-
from __future__ import annotations

from .activation_models import ActivationRequest, ActivationResult, ActivationState
from .activation_strategies import ActivationStrategy


class ActivationRuntime:
    async def activate(
        self,
        request: ActivationRequest,
        strategy: ActivationStrategy,
    ) -> ActivationResult:
        context = await strategy.resolve_context(request)
        current = await strategy.read_state(context)
        if current.status == "ready" or not request.allow_heal or not current.auto_heal_supported:
            return self._build_result(
                request=request,
                state=current,
                auto_heal_attempted=False,
                operations=current.operations,
            )
        operations = list(current.operations)
        operations.extend(await strategy.remediate(context, current))
        refreshed = await strategy.read_state(context)
        return self._build_result(
            request=request,
            state=refreshed,
            auto_heal_attempted=True,
            operations=operations or refreshed.operations,
        )

    @staticmethod
    def _build_result(
        *,
        request: ActivationRequest,
        state: ActivationState,
        auto_heal_attempted: bool,
        operations: list[str],
    ) -> ActivationResult:
        payload = state.model_dump(mode="python")
        payload["operations"] = list(operations)
        return ActivationResult(
            subject_id=request.subject_id,
            activation_class=request.activation_class,
            auto_heal_attempted=auto_heal_attempted,
            **payload,
        )
