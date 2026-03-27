# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

from .models import Proposal, ProposalStatus
from .runtime_core import LearningRuntimeCore


class LearningProposalService:
    """Proposal-facing learning operations."""

    def __init__(self, core: LearningRuntimeCore) -> None:
        self._core = core

    def list_proposals(
        self,
        *,
        status: ProposalStatus | str | None = None,
        created_since: datetime | None = None,
        limit: int | None = None,
    ) -> list[Proposal]:
        return self._core.list_proposals(
            status=status,
            created_since=created_since,
            limit=limit,
        )

    def delete_proposal(self, proposal_id: str) -> bool:
        return self._core.delete_proposal(proposal_id)

    def create_proposal(
        self,
        *,
        title: str,
        description: str,
        source_agent_id: str = "copaw-agent-runner",
        goal_id: str | None = None,
        task_id: str | None = None,
        agent_id: str | None = None,
        target_layer: str = "",
        evidence_refs: list[str] | None = None,
    ) -> Proposal:
        return self._core.create_proposal(
            title=title,
            description=description,
            source_agent_id=source_agent_id,
            goal_id=goal_id,
            task_id=task_id,
            agent_id=agent_id,
            target_layer=target_layer,
            evidence_refs=evidence_refs,
        )

    def accept_proposal(self, proposal_id: str) -> Proposal:
        return self._core.accept_proposal(proposal_id)

    def reject_proposal(self, proposal_id: str) -> Proposal:
        return self._core.reject_proposal(proposal_id)


__all__ = ["LearningProposalService"]
