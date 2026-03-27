# -*- coding: utf-8 -*-
"""Artifact access helpers for environment surfaces."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .service import EnvironmentService


class EnvironmentArtifactService:
    """Focused collaborator for artifact reads."""

    def __init__(self, service: EnvironmentService) -> None:
        self._service = service

    def list_artifacts(
        self,
        *,
        environment_ref: str | None,
        limit: int = 20,
    ):
        if self._service._artifact_store is None:
            return []
        resolved_ref = self._resolve_environment_ref(environment_ref)
        return self._service._artifact_store.list_artifacts(
            environment_ref=resolved_ref,
            limit=limit,
        )

    def get_artifact(self, artifact_id: str):
        if self._service._artifact_store is None:
            return None
        return self._service._artifact_store.get_artifact(artifact_id)

    def _resolve_environment_ref(self, env_ref: str | None) -> str | None:
        if not env_ref:
            return None
        if env_ref.startswith("env:"):
            mount = self._service.get_environment(env_ref)
            return mount.ref if mount is not None else None
        return env_ref
