# -*- coding: utf-8 -*-
from __future__ import annotations

from hashlib import sha1

from ..evidence import EvidenceRecord
from ..industry.models import IndustryBootstrapInstallItem
from ..kernel import KernelResult, KernelTask
from ..state import DecisionRequestRecord
from .models import (
    CapabilityAcquisitionProposal,
    GrowthEvent,
    InstallBindingPlan,
    OnboardingRun,
)
from .runtime_support import (
    LearningRuntimeDelegate,
    _MAIN_BRAIN_ACTOR,
    _list_like,
    _maybe_await,
    _mcp_trial_tool_entries,
    _mcp_trial_tool_name,
    _mcp_trial_tool_required_args,
    _merge_string_lists,
    _normalize_optional_str,
    _pick_safe_mcp_trial_tool_name,
    _stable_learning_id,
    _utc_now,
)


class LearningAcquisitionRuntimeService(LearningRuntimeDelegate):
    """Capability acquisition and onboarding runtime orchestration."""

    def list_acquisition_proposals(
        self,
        *,
        industry_instance_id: str | None = None,
        status: str | None = None,
        target_agent_id: str | None = None,
        target_role_id: str | None = None,
        acquisition_kind: str | None = None,
        limit: int | None = None,
    ) -> list[CapabilityAcquisitionProposal]:
        return self._engine.list_acquisition_proposals(
            industry_instance_id=industry_instance_id,
            status=status,
            target_agent_id=target_agent_id,
            target_role_id=target_role_id,
            acquisition_kind=acquisition_kind,
            limit=limit,
        )

    def get_acquisition_proposal(
        self,
        proposal_id: str,
    ) -> CapabilityAcquisitionProposal:
        return self._engine.get_acquisition_proposal(proposal_id)

    def delete_acquisition_proposal(self, proposal_id: str) -> bool:
        deleted = self._engine.delete_acquisition_proposal(proposal_id)
        if deleted:
            self._publish_runtime_event(
                topic="learning-acquisition",
                action="proposal-deleted",
                payload={"proposal_id": proposal_id},
            )
        return deleted

    async def approve_acquisition_proposal(
        self,
        proposal_id: str,
        *,
        approved_by: str = "system",
    ) -> dict[str, object]:
        proposal = self._engine.get_acquisition_proposal(proposal_id)
        if proposal.status in {"applied", "blocked"}:
            plan, run = self._get_existing_acquisition_artifacts(proposal.id)
            return {
                "proposal": proposal,
                "plan": plan,
                "onboarding_run": run,
                "decision_request": self._get_acquisition_decision(proposal.id),
            }
        if proposal.status == "rejected":
            proposal = self._reopen_acquisition_proposal(proposal)
        proposal, plan, run = await self._approve_and_materialize_acquisition_proposal(
            proposal,
            actor=approved_by,
        )
        return {
            "proposal": proposal,
            "plan": plan,
            "onboarding_run": run,
            "decision_request": self._get_acquisition_decision(proposal.id),
        }

    def reject_acquisition_proposal(
        self,
        proposal_id: str,
        *,
        rejected_by: str = "system",
    ) -> dict[str, object]:
        proposal = self._engine.get_acquisition_proposal(proposal_id)
        if proposal.status == "rejected":
            return {
                "proposal": proposal,
                "decision_request": self._get_acquisition_decision(proposal.id),
            }
        if proposal.status in {"materialized", "applied", "blocked"}:
            raise ValueError(
                f"Acquisition proposal {proposal_id} already entered execution and "
                "cannot be rejected directly.",
            )

        now = _utc_now()
        proposal = self._save_acquisition_proposal(
            proposal.model_copy(
                update={
                    "status": "rejected",
                    "rejected_by": rejected_by,
                    "rejected_at": now,
                    "updated_at": now,
                },
            ),
            action="rejected",
        )
        self._ensure_acquisition_task(proposal)
        self._resolve_acquisition_decision(
            proposal.id,
            status="rejected",
            resolution=f"Rejected by {rejected_by}.",
        )
        decision = self._record_acquisition_decision_if_missing(
            proposal,
            status="rejected",
            resolution=f"Rejected by {rejected_by}.",
            requested_by=rejected_by,
        )
        if decision is not None and proposal.decision_request_id != decision.id:
            proposal = self._save_acquisition_proposal(
                proposal.model_copy(
                    update={
                        "decision_request_id": decision.id,
                        "updated_at": _utc_now(),
                    },
                ),
                action="rejected",
            )
        evidence_id = self._append_acquisition_evidence(
            entity_id=proposal.id,
            actor=rejected_by,
            capability_ref="learning:acquisition-governance",
            risk_level=proposal.risk_level,
            action="reject-acquisition-proposal",
            result=f"Rejected acquisition proposal {proposal.title}.",
            status="recorded",
            metadata={
                "proposal_id": proposal.id,
                "decision_request_id": decision.id if decision is not None else None,
            },
        )
        if evidence_id is not None:
            proposal = self._save_acquisition_proposal(
                proposal.model_copy(
                    update={
                        "evidence_refs": _merge_string_lists(
                            proposal.evidence_refs,
                            [evidence_id],
                        ),
                        "updated_at": _utc_now(),
                    },
                ),
                action="rejected",
            )
        self._publish_runtime_event(
            topic="learning-acquisition",
            action="proposal-rejected",
            payload={
                "proposal_id": proposal.id,
                "industry_instance_id": proposal.industry_instance_id,
                "status": proposal.status,
            },
        )
        return {
            "proposal": proposal,
            "decision_request": self._get_acquisition_decision(proposal.id),
        }

    async def finalize_resolved_decision(
        self,
        decision_id: str,
        *,
        status: str,
        actor: str = "system",
        resolution: str | None = None,
    ) -> dict[str, object]:
        if self._decision_repo is None:
            raise KeyError(f"DecisionRequest '{decision_id}' not found")
        decision = self._decision_repo.get_decision_request(decision_id)
        if decision is None:
            raise KeyError(f"DecisionRequest '{decision_id}' not found")
        if _normalize_optional_str(getattr(decision, "decision_type", None)) != "acquisition-approval":
            raise ValueError(
                f"DecisionRequest '{decision_id}' is not an acquisition approval decision",
            )
        proposal_id = _normalize_optional_str(getattr(decision, "task_id", None))
        if proposal_id is None:
            raise ValueError(
                f"DecisionRequest '{decision_id}' does not reference an acquisition proposal",
            )
        if status == "approved":
            result = await self.approve_acquisition_proposal(
                proposal_id,
                approved_by=actor,
            )
            proposal = result.get("proposal")
            plan = result.get("plan")
            run = result.get("onboarding_run")
            if isinstance(proposal, CapabilityAcquisitionProposal):
                kernel_result = self._close_kernel_task_after_acquisition_approval(
                    proposal=proposal,
                    plan=plan if isinstance(plan, InstallBindingPlan) else None,
                    run=run if isinstance(run, OnboardingRun) else None,
                )
                if kernel_result is not None:
                    result["kernel_result"] = kernel_result
            return result
        if status == "rejected":
            return self.reject_acquisition_proposal(
                proposal_id,
                rejected_by=actor,
            )
        raise ValueError(f"Unsupported acquisition decision status '{status}'")

    def list_install_binding_plans(
        self,
        *,
        proposal_id: str | None = None,
        industry_instance_id: str | None = None,
        status: str | None = None,
        target_agent_id: str | None = None,
        target_role_id: str | None = None,
        limit: int | None = None,
    ) -> list[InstallBindingPlan]:
        return self._engine.list_install_binding_plans(
            proposal_id=proposal_id,
            industry_instance_id=industry_instance_id,
            status=status,
            target_agent_id=target_agent_id,
            target_role_id=target_role_id,
            limit=limit,
        )

    def get_install_binding_plan(self, plan_id: str) -> InstallBindingPlan:
        return self._engine.get_install_binding_plan(plan_id)

    def delete_install_binding_plan(self, plan_id: str) -> bool:
        deleted = self._engine.delete_install_binding_plan(plan_id)
        if deleted:
            self._publish_runtime_event(
                topic="learning-acquisition",
                action="plan-deleted",
                payload={"plan_id": plan_id},
            )
        return deleted

    def list_onboarding_runs(
        self,
        *,
        plan_id: str | None = None,
        proposal_id: str | None = None,
        industry_instance_id: str | None = None,
        status: str | None = None,
        target_agent_id: str | None = None,
        target_role_id: str | None = None,
        limit: int | None = None,
    ) -> list[OnboardingRun]:
        return self._engine.list_onboarding_runs(
            plan_id=plan_id,
            proposal_id=proposal_id,
            industry_instance_id=industry_instance_id,
            status=status,
            target_agent_id=target_agent_id,
            target_role_id=target_role_id,
            limit=limit,
        )

    def get_onboarding_run(self, run_id: str) -> OnboardingRun:
        return self._engine.get_onboarding_run(run_id)

    def delete_onboarding_run(self, run_id: str) -> bool:
        deleted = self._engine.delete_onboarding_run(run_id)
        if deleted:
            self._publish_runtime_event(
                topic="learning-acquisition",
                action="onboarding-deleted",
                payload={"run_id": run_id},
            )
        return deleted

    async def run_industry_acquisition_cycle(
        self,
        *,
        industry_instance_id: str,
        actor: str = _MAIN_BRAIN_ACTOR,
        rerun_existing: bool = False,
        providers: list[str] | None = None,
        max_install_recommendations_per_role: int = 4,
        max_sop_templates_per_role: int = 2,
    ) -> dict[str, object]:
        context = await self._get_industry_acquisition_context(
            industry_instance_id=industry_instance_id,
        )
        if context is None:
            return {
                "success": False,
                "industry_instance_id": industry_instance_id,
                "summary": "行业实例不存在，无法执行自动装配学习。",
                "proposals": [],
                "plans": [],
                "onboarding_runs": [],
                "warnings": ["industry-instance-unavailable"],
            }

        discovery_service = self._get_capability_discovery_service()
        if discovery_service is None:
            return {
                "success": False,
                "industry_instance_id": industry_instance_id,
                "summary": "能力发现服务不可用，无法执行自动装配学习。",
                "proposals": [],
                "plans": [],
                "onboarding_runs": [],
                "warnings": ["capability-discovery-unavailable"],
            }

        team = context.get("team")
        profile = context.get("profile")
        if team is None or profile is None:
            return {
                "success": False,
                "industry_instance_id": industry_instance_id,
                "summary": "行业上下文不完整，无法执行自动装配学习。",
                "proposals": [],
                "plans": [],
                "onboarding_runs": [],
                "warnings": ["industry-context-incomplete"],
            }

        goal_context_by_agent = dict(context.get("goal_context_by_agent") or {})
        proposals: list[CapabilityAcquisitionProposal] = []
        plans: list[InstallBindingPlan] = []
        onboarding_runs: list[OnboardingRun] = []
        decision_requests: list[DecisionRequestRecord] = []
        warnings: list[str] = []
        created_proposals = 0
        skipped_applied = 0
        pending_approvals = 0
        skipped_rejected = 0
        normalized_providers: list[str] = []
        for item in list(providers or []):
            provider = _normalize_optional_str(item)
            if provider is None:
                continue
            normalized_providers.append(provider.lower())

        for role in list(getattr(team, "agents", []) or []):
            agent_id = _normalize_optional_str(getattr(role, "agent_id", None))
            role_id = _normalize_optional_str(getattr(role, "role_id", None))
            if agent_id is None or role_id is None:
                continue
            discovery_result = await self._discover_role_acquisition_candidates(
                discovery_service=discovery_service,
                profile=profile,
                role=role,
                goal_context=goal_context_by_agent.get(agent_id, []),
                providers=normalized_providers or None,
            )
            warnings = _merge_string_lists(
                warnings,
                discovery_result.get("warnings"),
            )

            processed_install = 0
            for recommendation in list(discovery_result.get("recommendations") or []):
                if processed_install >= max_install_recommendations_per_role:
                    break
                if bool(recommendation.get("installed")):
                    continue
                for target_agent_id in self._resolve_install_target_agent_ids(
                    role=role,
                    recommendation=recommendation,
                ):
                    proposal, created = self._upsert_install_acquisition_proposal(
                        industry_instance_id=industry_instance_id,
                        owner_scope=_normalize_optional_str(context.get("owner_scope")),
                        target_role_id=role_id,
                        target_agent_id=target_agent_id,
                        recommendation=recommendation,
                    )
                    if proposal.status == "applied" and not rerun_existing:
                        skipped_applied += 1
                        continue
                    if proposal.status == "rejected" and not rerun_existing:
                        skipped_rejected += 1
                        continue
                    if proposal.status != "open":
                        proposal = self._reopen_acquisition_proposal(proposal)
                    if created:
                        created_proposals += 1
                    acquisition_result = await self._govern_acquisition_proposal(
                        proposal,
                        actor=actor,
                    )
                    governed_proposal = acquisition_result["proposal"]
                    decision = acquisition_result.get("decision_request")
                    plan = acquisition_result.get("plan")
                    run = acquisition_result.get("onboarding_run")
                    proposals.append(governed_proposal)
                    if isinstance(decision, DecisionRequestRecord):
                        decision_requests.append(decision)
                    if isinstance(plan, InstallBindingPlan):
                        plans.append(plan)
                    if isinstance(run, OnboardingRun):
                        onboarding_runs.append(run)
                    elif governed_proposal.status == "open":
                        pending_approvals += 1
                    processed_install += 1
                    if processed_install >= max_install_recommendations_per_role:
                        break

            processed_sop = 0
            for candidate in list(discovery_result.get("sop_templates") or []):
                if processed_sop >= max_sop_templates_per_role:
                    break
                if not self._is_actionable_sop_candidate(candidate):
                    continue
                proposal, created = self._upsert_binding_acquisition_proposal(
                    industry_instance_id=industry_instance_id,
                    owner_scope=_normalize_optional_str(context.get("owner_scope")),
                    role=role,
                    candidate=candidate,
                )
                if proposal is None:
                    continue
                if proposal.status == "applied" and not rerun_existing:
                    skipped_applied += 1
                    continue
                if proposal.status == "rejected" and not rerun_existing:
                    skipped_rejected += 1
                    continue
                if proposal.status != "open":
                    proposal = self._reopen_acquisition_proposal(proposal)
                if created:
                    created_proposals += 1
                acquisition_result = await self._govern_acquisition_proposal(
                    proposal,
                    actor=actor,
                )
                governed_proposal = acquisition_result["proposal"]
                decision = acquisition_result.get("decision_request")
                plan = acquisition_result.get("plan")
                run = acquisition_result.get("onboarding_run")
                proposals.append(governed_proposal)
                if isinstance(decision, DecisionRequestRecord):
                    decision_requests.append(decision)
                if isinstance(plan, InstallBindingPlan):
                    plans.append(plan)
                if isinstance(run, OnboardingRun):
                    onboarding_runs.append(run)
                elif governed_proposal.status == "open":
                    pending_approvals += 1
                processed_sop += 1

        passed_count = sum(1 for run in onboarding_runs if run.status == "passed")
        failed_count = sum(1 for run in onboarding_runs if run.status == "failed")
        result = {
            "success": True,
            "industry_instance_id": industry_instance_id,
            "summary": (
                f"已为行业实例 {industry_instance_id} 产出 {len(proposals)} 条自动装配结果，"
                f"其中待审批 {pending_approvals} 条，onboarding 通过 {passed_count} 条，失败 {failed_count} 条。"
            ),
            "proposals_created": created_proposals,
            "proposals_processed": len(proposals),
            "plans_materialized": len(plans),
            "onboarding_passed": passed_count,
            "onboarding_failed": failed_count,
            "skipped_applied": skipped_applied,
            "skipped_rejected": skipped_rejected,
            "pending_approvals": pending_approvals,
            "proposals": [proposal.model_dump(mode="json") for proposal in proposals],
            "plans": [plan.model_dump(mode="json") for plan in plans],
            "onboarding_runs": [run.model_dump(mode="json") for run in onboarding_runs],
            "decision_requests": [
                decision.model_dump(mode="json") for decision in decision_requests
            ],
            "warnings": warnings,
        }
        self._publish_runtime_event(
            topic="learning-acquisition",
            action="cycle",
            payload={
                "industry_instance_id": industry_instance_id,
                "proposals_processed": len(proposals),
                "pending_approvals": pending_approvals,
                "onboarding_passed": passed_count,
                "onboarding_failed": failed_count,
            },
        )
        return result

    async def _get_industry_acquisition_context(
        self,
        *,
        industry_instance_id: str,
    ) -> dict[str, object] | None:
        if self._industry_service is None:
            return None
        builder = getattr(
            self._industry_service,
            "build_acquisition_context_for_instance",
            None,
        )
        if callable(builder):
            payload = await _maybe_await(builder(industry_instance_id))
            if isinstance(payload, dict):
                return payload
        getter = getattr(self._industry_service, "get_instance_detail", None)
        if not callable(getter):
            return None
        detail = getter(industry_instance_id)
        if detail is None:
            return None
        return {
            "detail": detail,
            "profile": getattr(detail, "profile", None),
            "team": getattr(detail, "team", None),
            "owner_scope": getattr(detail, "owner_scope", None),
            "goal_context_by_agent": {},
        }

    def _get_capability_discovery_service(self) -> object | None:
        getter = (
            getattr(self._capability_service, "get_discovery_service", None)
            if self._capability_service is not None
            else None
        )
        return getter() if callable(getter) else None

    async def _discover_role_acquisition_candidates(
        self,
        *,
        discovery_service: object,
        profile: object,
        role: object,
        goal_context: list[str],
        providers: list[str] | None = None,
    ) -> dict[str, list[dict[str, object]] | list[str]]:
        discover = getattr(discovery_service, "discover", None)
        if not callable(discover):
            return {"recommendations": [], "sop_templates": [], "warnings": []}
        payload = {
            "industry_profile": (
                profile.model_dump(mode="json")
                if hasattr(profile, "model_dump")
                else profile
            ),
            "role": (
                role.model_dump(mode="json")
                if hasattr(role, "model_dump")
                else role
            ),
            "goal_context": list(goal_context or []),
        }
        if providers:
            payload["providers"] = list(providers)
        raw = await _maybe_await(
            discover(payload),
        )
        if not isinstance(raw, dict):
            return {"recommendations": [], "sop_templates": [], "warnings": []}
        return {
            "recommendations": [
                item
                for item in list(raw.get("recommendations") or [])
                if isinstance(item, dict)
            ],
            "sop_templates": [
                item
                for item in list(raw.get("sop_templates") or [])
                if isinstance(item, dict)
            ],
            "warnings": [
                str(item).strip()
                for item in list(raw.get("warnings") or [])
                if str(item).strip()
            ],
        }

    def _resolve_install_target_agent_ids(
        self,
        *,
        role: object,
        recommendation: dict[str, object],
    ) -> list[str]:
        explicit = [
            text
            for text in (
                _normalize_optional_str(item)
                for item in list(recommendation.get("target_agent_ids") or [])
            )
            if text is not None
        ]
        if explicit:
            return explicit
        fallback_agent_id = _normalize_optional_str(getattr(role, "agent_id", None))
        return [fallback_agent_id] if fallback_agent_id is not None else []

    def _upsert_install_acquisition_proposal(
        self,
        *,
        industry_instance_id: str,
        owner_scope: str | None,
        target_role_id: str | None,
        target_agent_id: str,
        recommendation: dict[str, object],
    ) -> tuple[CapabilityAcquisitionProposal, bool]:
        proposal_key = (
            f"{industry_instance_id}:install:{target_role_id or 'unknown'}:"
            f"{target_agent_id}:{recommendation.get('template_id') or 'unknown'}:"
            f"{recommendation.get('install_option_key') or 'default'}:"
            f"{recommendation.get('default_client_key') or recommendation.get('template_id') or 'default'}"
        )
        proposal_id = _stable_learning_id("acq-proposal", proposal_key)
        current = next(
            (
                item
                for item in self._engine.list_acquisition_proposals(limit=None)
                if item.id == proposal_id
            ),
            None,
        )
        now = _utc_now()
        install_item = IndustryBootstrapInstallItem(
            recommendation_id=_normalize_optional_str(recommendation.get("recommendation_id")),
            install_kind=str(recommendation.get("install_kind") or "mcp-template"),
            template_id=str(recommendation.get("template_id") or "").strip(),
            install_option_key=_normalize_optional_str(
                recommendation.get("install_option_key"),
            )
            or "",
            client_key=_normalize_optional_str(
                recommendation.get("default_client_key"),
            ),
            bundle_url=_normalize_optional_str(recommendation.get("source_url")),
            version=_normalize_optional_str(recommendation.get("version")),
            source_kind=str(recommendation.get("source_kind") or "install-template"),
            source_label=_normalize_optional_str(recommendation.get("source_label")),
            review_acknowledged=not bool(recommendation.get("review_required")),
            enabled=bool(recommendation.get("default_enabled", True)),
            required=bool(recommendation.get("required")),
            capability_assignment_mode="merge",
            capability_ids=[
                str(item).strip()
                for item in list(recommendation.get("capability_ids") or [])
                if str(item).strip()
            ],
            target_agent_ids=[target_agent_id],
            target_role_ids=[target_role_id] if target_role_id else [],
        )
        proposal = CapabilityAcquisitionProposal(
            id=proposal_id,
            proposal_key=proposal_key,
            industry_instance_id=industry_instance_id,
            owner_scope=owner_scope,
            target_agent_id=target_agent_id,
            target_role_id=target_role_id,
            acquisition_kind="install-capability",
            title=(
                f"为 {target_agent_id} 安装 {recommendation.get('title') or install_item.template_id}"
            ),
            summary=str(
                recommendation.get("description")
                or recommendation.get("title")
                or install_item.template_id
                or ""
            ),
            risk_level=(
                "confirm"
                if bool(recommendation.get("review_required"))
                else str(recommendation.get("risk_level") or "guarded")
            ),
            status=current.status if current is not None else "open",
            install_item=install_item,
            binding_request=None,
            decision_request_id=current.decision_request_id if current is not None else None,
            approved_by=current.approved_by if current is not None else None,
            approved_at=current.approved_at if current is not None else None,
            rejected_by=current.rejected_by if current is not None else None,
            rejected_at=current.rejected_at if current is not None else None,
            discovery_signals=[
                str(item).strip()
                for item in list(recommendation.get("match_signals") or [])
                if str(item).strip()
            ],
            evidence_refs=list(current.evidence_refs) if current is not None else [],
            created_at=current.created_at if current is not None else now,
            updated_at=now,
        )
        action = "updated" if current is not None else "created"
        return self._save_acquisition_proposal(proposal, action=action), current is None

    def _upsert_binding_acquisition_proposal(
        self,
        *,
        industry_instance_id: str,
        owner_scope: str | None,
        role: object,
        candidate: dict[str, object],
    ) -> tuple[CapabilityAcquisitionProposal | None, bool]:
        if self._fixed_sop_service is None:
            return None, False
        target_agent_id = _normalize_optional_str(getattr(role, "agent_id", None))
        target_role_id = _normalize_optional_str(getattr(role, "role_id", None))
        template_id = _normalize_optional_str(candidate.get("template_id"))
        if target_agent_id is None or target_role_id is None or template_id is None:
            return None, False
        get_template = getattr(self._fixed_sop_service, "get_template", None)
        template = get_template(template_id) if callable(get_template) else None
        if template is None:
            return None, False
        callback_mode = _normalize_optional_str(
            getattr(template, "callback_contract", {}).get("mode")
            if isinstance(getattr(template, "callback_contract", None), dict)
            else None,
        )
        if callback_mode not in {"none", "routine-callback", "workflow-callback"}:
            callback_mode = "routine-callback"
        from ..sop_kernel import FixedSopBindingCreateRequest

        binding_request = FixedSopBindingCreateRequest(
            template_id=template_id,
            binding_name=(
                f"{_normalize_optional_str(getattr(role, 'role_name', None)) or target_role_id}"
                f" / {candidate.get('name') or template_id}"
            ),
            status="draft",
            owner_scope=owner_scope,
            owner_agent_id=target_agent_id,
            industry_instance_id=industry_instance_id,
            callback_mode=callback_mode,  # type: ignore[arg-type]
            risk_baseline=_normalize_optional_str(getattr(template, "risk_baseline", None))
            or "guarded",
            metadata={
                "source": "learning-acquisition",
                "match_signals": [
                    str(item).strip()
                    for item in list(candidate.get("match_signals") or [])
                    if str(item).strip()
                ],
            },
        )
        proposal_key = (
            f"{industry_instance_id}:binding:{target_role_id}:{target_agent_id}:{template_id}"
        )
        proposal_id = _stable_learning_id("acq-proposal", proposal_key)
        current = next(
            (
                item
                for item in self._engine.list_acquisition_proposals(limit=None)
                if item.id == proposal_id
            ),
            None,
        )
        now = _utc_now()
        proposal = CapabilityAcquisitionProposal(
            id=proposal_id,
            proposal_key=proposal_key,
            industry_instance_id=industry_instance_id,
            owner_scope=owner_scope,
            target_agent_id=target_agent_id,
            target_role_id=target_role_id,
            acquisition_kind="create-sop-binding",
            title=f"为 {target_agent_id} 生成 {candidate.get('name') or template_id} 绑定",
            summary=str(candidate.get("summary") or candidate.get("name") or template_id),
            risk_level=_normalize_optional_str(getattr(template, "risk_baseline", None))
            or "guarded",
            status=current.status if current is not None else "open",
            install_item=None,
            binding_request=binding_request.model_dump(mode="json"),
            decision_request_id=current.decision_request_id if current is not None else None,
            approved_by=current.approved_by if current is not None else None,
            approved_at=current.approved_at if current is not None else None,
            rejected_by=current.rejected_by if current is not None else None,
            rejected_at=current.rejected_at if current is not None else None,
            discovery_signals=[
                str(item).strip()
                for item in list(candidate.get("match_signals") or [])
                if str(item).strip()
            ],
            evidence_refs=list(current.evidence_refs) if current is not None else [],
            created_at=current.created_at if current is not None else now,
            updated_at=now,
        )
        action = "updated" if current is not None else "created"
        return self._save_acquisition_proposal(proposal, action=action), current is None

    def _save_acquisition_proposal(
        self,
        proposal: CapabilityAcquisitionProposal,
        *,
        action: str,
    ) -> CapabilityAcquisitionProposal:
        saved = self._engine.save_acquisition_proposal(proposal, action=action)
        self._publish_runtime_event(
            topic="learning-acquisition",
            action=f"proposal-{action}",
            payload={
                "proposal_id": saved.id,
                "industry_instance_id": saved.industry_instance_id,
                "status": saved.status,
                "acquisition_kind": saved.acquisition_kind,
            },
        )
        return saved

    def _save_install_binding_plan(
        self,
        plan: InstallBindingPlan,
        *,
        action: str,
    ) -> InstallBindingPlan:
        saved = self._engine.save_install_binding_plan(plan, action=action)
        self._publish_runtime_event(
            topic="learning-acquisition",
            action=f"plan-{action}",
            payload={
                "plan_id": saved.id,
                "proposal_id": saved.proposal_id,
                "industry_instance_id": saved.industry_instance_id,
                "status": saved.status,
            },
        )
        return saved

    def _save_onboarding_run(
        self,
        run: OnboardingRun,
        *,
        action: str,
    ) -> OnboardingRun:
        saved = self._engine.save_onboarding_run(run, action=action)
        self._publish_runtime_event(
            topic="learning-acquisition",
            action=f"onboarding-{action}",
            payload={
                "run_id": saved.id,
                "plan_id": saved.plan_id,
                "proposal_id": saved.proposal_id,
                "industry_instance_id": saved.industry_instance_id,
                "status": saved.status,
            },
        )
        return saved

    async def _govern_acquisition_proposal(
        self,
        proposal: CapabilityAcquisitionProposal,
        *,
        actor: str,
    ) -> dict[str, object]:
        self._ensure_acquisition_task(proposal)
        if self._proposal_requires_manual_approval(proposal):
            decision = self._ensure_acquisition_decision(
                proposal,
                requested_by=actor,
            )
            if decision is None:
                raise RuntimeError("Acquisition decision repository is not available.")
            if proposal.decision_request_id != decision.id:
                proposal = self._save_acquisition_proposal(
                    proposal.model_copy(
                        update={
                            "decision_request_id": decision.id,
                            "updated_at": _utc_now(),
                        },
                    ),
                    action="pending-approval",
                )
            return {
                "proposal": proposal,
                "decision_request": decision,
                "plan": None,
                "onboarding_run": None,
            }
        proposal, plan, run = await self._approve_and_materialize_acquisition_proposal(
            proposal,
            actor=actor,
        )
        return {
            "proposal": proposal,
            "decision_request": self._get_acquisition_decision(proposal.id),
            "plan": plan,
            "onboarding_run": run,
        }

    async def _approve_and_materialize_acquisition_proposal(
        self,
        proposal: CapabilityAcquisitionProposal,
        *,
        actor: str,
    ) -> tuple[CapabilityAcquisitionProposal, InstallBindingPlan, OnboardingRun]:
        approved_install_item = proposal.install_item
        if approved_install_item is not None and not approved_install_item.review_acknowledged:
            approved_install_item = approved_install_item.model_copy(
                update={"review_acknowledged": True},
            )
        proposal = self._save_acquisition_proposal(
            proposal.model_copy(
                update={
                    "install_item": approved_install_item,
                    "approved_by": actor,
                    "approved_at": proposal.approved_at or _utc_now(),
                    "rejected_by": None,
                    "rejected_at": None,
                    "updated_at": _utc_now(),
                },
            ),
            action="approved",
        )
        self._ensure_acquisition_task(proposal)
        self._resolve_acquisition_decision(
            proposal.id,
            status="approved",
            resolution=f"已由 {actor} 批准。",
        )
        decision = self._record_acquisition_decision_if_missing(
            proposal,
            status="approved",
            resolution=f"已由 {actor} 批准。",
            requested_by=actor,
        )
        if decision is not None and proposal.decision_request_id != decision.id:
            proposal = self._save_acquisition_proposal(
                proposal.model_copy(
                    update={
                        "decision_request_id": decision.id,
                        "updated_at": _utc_now(),
                    },
                ),
                action="approved",
            )
        evidence_id = self._append_acquisition_evidence(
            entity_id=proposal.id,
            actor=actor,
            capability_ref="learning:acquisition-governance",
            risk_level=proposal.risk_level,
            action="approve-acquisition-proposal",
            result=f"已批准提案“{proposal.title}”，继续执行装配链路。",
            status="recorded",
            metadata={
                "proposal_id": proposal.id,
                "decision_request_id": decision.id if decision is not None else None,
            },
        )
        if evidence_id is not None:
            proposal = self._save_acquisition_proposal(
                proposal.model_copy(
                    update={
                        "evidence_refs": _merge_string_lists(
                            proposal.evidence_refs,
                            [evidence_id],
                        ),
                        "updated_at": _utc_now(),
                    },
                ),
                action="approved",
            )
        return await self._materialize_and_onboard_acquisition_proposal(
            proposal,
            actor=actor,
        )

    def _reopen_acquisition_proposal(
        self,
        proposal: CapabilityAcquisitionProposal,
    ) -> CapabilityAcquisitionProposal:
        cleared_decision_id = proposal.decision_request_id
        if proposal.status != "rejected" and proposal.approved_at is not None:
            cleared_decision_id = proposal.decision_request_id
        else:
            cleared_decision_id = None
        reopened = proposal.model_copy(
            update={
                "status": "open",
                "decision_request_id": cleared_decision_id,
                "approved_by": proposal.approved_by if proposal.status != "rejected" else None,
                "approved_at": proposal.approved_at if proposal.status != "rejected" else None,
                "rejected_by": None,
                "rejected_at": None,
                "updated_at": _utc_now(),
            },
        )
        reopened = self._save_acquisition_proposal(reopened, action="reopened")
        self._ensure_acquisition_task(reopened)
        return reopened

    def _proposal_requires_manual_approval(
        self,
        proposal: CapabilityAcquisitionProposal,
    ) -> bool:
        if proposal.approved_at is not None:
            return False
        if str(proposal.risk_level or "guarded") == "confirm":
            return True
        install_item = proposal.install_item
        if install_item is not None and not bool(install_item.review_acknowledged):
            return True
        return False

    def _get_existing_acquisition_artifacts(
        self,
        proposal_id: str,
    ) -> tuple[InstallBindingPlan | None, OnboardingRun | None]:
        plan = self._get_existing_install_binding_plan_for_proposal(proposal_id)
        run = (
            self._get_existing_onboarding_run_for_plan(plan.id)
            if plan is not None
            else self._get_existing_onboarding_run_for_proposal(proposal_id)
        )
        return plan, run

    def _get_existing_install_binding_plan_for_proposal(
        self,
        proposal_id: str,
    ) -> InstallBindingPlan | None:
        try:
            return self._engine.get_install_binding_plan(
                _stable_learning_id("acq-plan", proposal_id),
            )
        except KeyError:
            return None

    def _get_existing_onboarding_run_for_plan(
        self,
        plan_id: str,
    ) -> OnboardingRun | None:
        try:
            return self._engine.get_onboarding_run(
                _stable_learning_id("onboarding", plan_id),
            )
        except KeyError:
            return None

    def _get_existing_onboarding_run_for_proposal(
        self,
        proposal_id: str,
    ) -> OnboardingRun | None:
        plan = self._get_existing_install_binding_plan_for_proposal(proposal_id)
        if plan is None:
            return None
        return self._get_existing_onboarding_run_for_plan(plan.id)

    def _get_acquisition_decision(
        self,
        proposal_id: str,
    ) -> DecisionRequestRecord | None:
        if self._decision_repo is None:
            return None
        decisions = self._decision_repo.list_decision_requests(task_id=proposal_id, limit=None)
        if not decisions:
            return None
        decisions.sort(
            key=lambda item: (
                1 if item.status in {"open", "reviewing"} else 0,
                (item.resolved_at or item.created_at).isoformat(),
                item.created_at.isoformat(),
            ),
            reverse=True,
        )
        return decisions[0]

    def _ensure_acquisition_decision(
        self,
        proposal: CapabilityAcquisitionProposal,
        *,
        requested_by: str,
    ) -> DecisionRequestRecord | None:
        if self._decision_repo is None:
            return None
        self._ensure_acquisition_task(proposal)
        open_requests = [
            item
            for item in self._decision_repo.list_decision_requests(
                task_id=proposal.id,
                limit=None,
            )
            if item.status in {"open", "reviewing"}
        ]
        if open_requests:
            return open_requests[0]
        task, decision = self._ensure_kernel_backed_acquisition_task(
            proposal,
            requested_by=requested_by,
        )
        if decision is not None:
            return decision
        task_store = self._kernel_task_store()
        if task_store is None:
            raise RuntimeError(
                "Learning acquisition requires a kernel task store for decision requests.",
            )
        return task_store.ensure_decision_request(
            task,
            requested_by=requested_by,
        )

    def _resolve_acquisition_decision(
        self,
        proposal_id: str,
        *,
        status: str,
        resolution: str,
    ) -> None:
        if self._decision_repo is None:
            return
        open_requests = [
            item
            for item in self._decision_repo.list_decision_requests(
                task_id=proposal_id,
                limit=None,
            )
            if item.status in {"open", "reviewing"}
        ]
        for decision in open_requests:
            updated = decision.model_copy(
                update={
                    "status": status,
                    "resolution": resolution,
                    "resolved_at": _utc_now(),
                },
            )
            self._decision_repo.upsert_decision_request(updated)

    def _record_acquisition_decision_if_missing(
        self,
        proposal: CapabilityAcquisitionProposal,
        *,
        status: str,
        resolution: str,
        requested_by: str,
    ) -> DecisionRequestRecord | None:
        if self._decision_repo is None:
            return None
        self._ensure_acquisition_task(proposal)
        existing = self._decision_repo.list_decision_requests(task_id=proposal.id, limit=None)
        for decision in existing:
            if decision.status == status:
                return decision
        task, _decision = self._ensure_kernel_backed_acquisition_task(
            proposal,
            requested_by=requested_by,
        )
        task_store = self._kernel_task_store()
        if task_store is None:
            raise RuntimeError(
                "Learning acquisition requires a kernel task store for decision resolution.",
            )
        pending = next(
            (
                decision
                for decision in existing
                if decision.status in {"open", "reviewing"}
            ),
            None,
        )
        if pending is None:
            pending = task_store.ensure_decision_request(
                task,
                requested_by=requested_by,
            )
        if pending is None:
            return None
        return task_store.resolve_decision_request(
            pending.id,
            status=status,
            resolution=resolution,
        )

    def _task_status_for_acquisition(
        self,
        proposal: CapabilityAcquisitionProposal,
    ) -> str:
        if proposal.status == "applied":
            return "completed"
        if proposal.status == "blocked":
            return "blocked"
        if proposal.status in {"rejected", "skipped"}:
            return "cancelled"
        if self._proposal_requires_manual_approval(proposal):
            return "needs-confirm"
        if proposal.status == "materialized":
            return "running"
        return "queued"

    def _kernel_task_store(self) -> object | None:
        dispatcher = getattr(self, "_kernel_dispatcher", None)
        if dispatcher is None:
            return None
        return getattr(dispatcher, "task_store", None)

    def _build_acquisition_kernel_task(
        self,
        proposal: CapabilityAcquisitionProposal,
        *,
        existing: KernelTask | None = None,
    ) -> KernelTask:
        payload = dict(existing.payload) if existing is not None else {}
        payload.update(
            {
                "proposal_id": proposal.id,
                "industry_instance_id": proposal.industry_instance_id,
                "acquisition_kind": proposal.acquisition_kind,
                "decision_type": "acquisition-approval",
                "decision_summary": (
                    f"Approve acquisition proposal '{proposal.title}' before materializing it."
                ),
            },
        )
        task_segment = (
            dict(existing.task_segment)
            if existing is not None
            else {
                "kind": "learning-acquisition",
                "proposal_id": proposal.id,
                "acquisition_kind": proposal.acquisition_kind,
            }
        )
        return KernelTask(
            id=proposal.id,
            trace_id=existing.trace_id if existing is not None else f"trace:{proposal.id}",
            goal_id=existing.goal_id if existing is not None else None,
            parent_task_id=existing.parent_task_id if existing is not None else None,
            work_context_id=existing.work_context_id if existing is not None else None,
            title=proposal.title,
            capability_ref=existing.capability_ref if existing is not None else None,
            environment_ref=existing.environment_ref if existing is not None else None,
            owner_agent_id=proposal.target_agent_id or _MAIN_BRAIN_ACTOR,
            actor_owner_id=existing.actor_owner_id if existing is not None else None,
            phase=existing.phase if existing is not None else "pending",
            risk_level=proposal.risk_level,  # type: ignore[arg-type]
            task_segment=task_segment,
            resume_point=dict(existing.resume_point) if existing is not None else {},
            payload=payload,
            created_at=existing.created_at if existing is not None else proposal.created_at,
            updated_at=_utc_now(),
        )

    def _ensure_kernel_backed_acquisition_task(
        self,
        proposal: CapabilityAcquisitionProposal,
        *,
        requested_by: str | None = None,
    ) -> tuple[KernelTask, DecisionRequestRecord | None]:
        dispatcher = getattr(self, "_kernel_dispatcher", None)
        task_store = self._kernel_task_store()
        if dispatcher is None or task_store is None:
            raise RuntimeError(
                "Learning acquisition requires a kernel dispatcher-backed task store.",
            )
        existing = task_store.get(proposal.id)
        if existing is None:
            admitted = dispatcher.submit(self._build_acquisition_kernel_task(proposal))
            existing = task_store.get(proposal.id)
            if existing is None:
                raise RuntimeError(
                    f"Kernel admission did not persist acquisition task '{proposal.id}'.",
                )
            decision = (
                task_store.get_decision_request(admitted.decision_request_id)
                if admitted.decision_request_id is not None
                else self._get_acquisition_decision(proposal.id)
            )
            return existing, decision
        task_store.upsert(
            self._build_acquisition_kernel_task(
                proposal,
                existing=existing,
            ),
        )
        refreshed = task_store.get(proposal.id)
        decision = self._get_acquisition_decision(proposal.id)
        if (
            decision is None
            and refreshed is not None
            and refreshed.phase == "waiting-confirm"
            and self._proposal_requires_manual_approval(proposal)
        ):
            decision = task_store.ensure_decision_request(
                refreshed,
                requested_by=requested_by,
            )
        return refreshed, decision

    def _close_kernel_task_after_acquisition_approval(
        self,
        *,
        proposal: CapabilityAcquisitionProposal,
        plan: InstallBindingPlan | None,
        run: OnboardingRun | None,
    ) -> KernelResult | None:
        dispatcher = getattr(self, "_kernel_dispatcher", None)
        task_store = self._kernel_task_store()
        if dispatcher is None or task_store is None:
            return None
        task = task_store.get(proposal.id)
        if task is None:
            return None
        if task.phase in {"completed", "failed", "cancelled"}:
            return KernelResult(
                task_id=task.id,
                trace_id=task.trace_id,
                success=task.phase == "completed",
                phase=task.phase,
                summary=(
                    (run.summary if run is not None else None)
                    or (plan.blocked_reason if plan is not None else None)
                    or proposal.title
                ),
                decision_request_id=proposal.decision_request_id,
            )
        if proposal.status == "applied":
            return dispatcher.complete_task(
                proposal.id,
                summary=(
                    (run.summary if run is not None else None)
                    or f"Acquisition proposal '{proposal.title}' completed."
                ),
            )
        if proposal.status == "blocked":
            return dispatcher.fail_task(
                proposal.id,
                error=(
                    (run.summary if run is not None else None)
                    or (plan.blocked_reason if plan is not None else None)
                    or f"Acquisition proposal '{proposal.title}' failed."
                ),
            )
        return None

    def _ensure_acquisition_task(
        self,
        proposal: CapabilityAcquisitionProposal,
    ) -> None:
        self._ensure_kernel_backed_acquisition_task(proposal)

    async def _materialize_and_onboard_acquisition_proposal(
        self,
        proposal: CapabilityAcquisitionProposal,
        *,
        actor: str,
    ) -> tuple[CapabilityAcquisitionProposal, InstallBindingPlan, OnboardingRun]:
        now = _utc_now()
        plan_id = _stable_learning_id("acq-plan", proposal.id)
        try:
            current_plan = self._engine.get_install_binding_plan(plan_id)
        except KeyError:
            current_plan = None
        plan = InstallBindingPlan(
            id=plan_id,
            proposal_id=proposal.id,
            industry_instance_id=proposal.industry_instance_id,
            target_agent_id=proposal.target_agent_id,
            target_role_id=proposal.target_role_id,
            risk_level=proposal.risk_level,
            status="pending",
            install_item=proposal.install_item,
            binding_request=proposal.binding_request,
            install_result=current_plan.install_result if current_plan is not None else None,
            binding_id=current_plan.binding_id if current_plan is not None else None,
            doctor_status=current_plan.doctor_status if current_plan is not None else None,
            blocked_reason=None,
            metadata=dict(current_plan.metadata or {}) if current_plan is not None else {},
            evidence_refs=list(current_plan.evidence_refs or []) if current_plan is not None else [],
            created_at=current_plan.created_at if current_plan is not None else now,
            applied_at=None,
            updated_at=now,
        )
        plan = self._save_install_binding_plan(
            plan,
            action="updated" if current_plan is not None else "created",
        )
        proposal = self._save_acquisition_proposal(
            proposal.model_copy(
                update={"status": "materialized", "updated_at": _utc_now()},
            ),
            action="materialized",
        )
        if proposal.install_item is not None:
            plan = await self._apply_install_binding_plan(plan, actor=actor)
        else:
            plan = await self._apply_sop_binding_plan(plan, actor=actor)

        onboarding = await self._run_onboarding(plan=plan, proposal=proposal, actor=actor)
        final_status = "applied" if onboarding.status == "passed" else "blocked"
        proposal = self._save_acquisition_proposal(
            proposal.model_copy(
                update={
                    "status": final_status,
                    "evidence_refs": _merge_string_lists(
                        proposal.evidence_refs,
                        plan.evidence_refs,
                        onboarding.evidence_refs,
                    ),
                    "updated_at": _utc_now(),
                },
            ),
            action="applied" if final_status == "applied" else "blocked",
        )
        self._record_onboarding_outcome(
            proposal=proposal,
            plan=plan,
            run=onboarding,
            actor=actor,
        )
        return proposal, plan, onboarding

    async def _apply_install_binding_plan(
        self,
        plan: InstallBindingPlan,
        *,
        actor: str,
    ) -> InstallBindingPlan:
        executor = (
            getattr(self._industry_service, "execute_install_plan_for_instance", None)
            if self._industry_service is not None
            else None
        )
        if not callable(executor) or plan.install_item is None:
            blocked_reason = "行业安装执行器不可用。"
            evidence_id = self._append_acquisition_evidence(
                entity_id=plan.id,
                actor=actor,
                capability_ref="learning:install-plan",
                risk_level=plan.risk_level,
                action="materialize-install-plan",
                result=blocked_reason,
                status="failed",
                metadata={"proposal_id": plan.proposal_id},
            )
            return self._save_install_binding_plan(
                plan.model_copy(
                    update={
                        "status": "failed",
                        "blocked_reason": blocked_reason,
                        "evidence_refs": _merge_string_lists(plan.evidence_refs, [evidence_id]),
                        "updated_at": _utc_now(),
                    },
                ),
                action="failed",
            )
        try:
            results = await _maybe_await(
                executor(
                    plan.industry_instance_id,
                    [plan.install_item],
                ),
            )
        except Exception as exc:
            blocked_reason = str(exc).strip() or "安装执行失败。"
            evidence_id = self._append_acquisition_evidence(
                entity_id=plan.id,
                actor=actor,
                capability_ref="learning:install-plan",
                risk_level=plan.risk_level,
                action="materialize-install-plan",
                result=blocked_reason,
                status="failed",
                metadata={"proposal_id": plan.proposal_id},
            )
            return self._save_install_binding_plan(
                plan.model_copy(
                    update={
                        "status": "failed",
                        "blocked_reason": blocked_reason,
                        "evidence_refs": _merge_string_lists(plan.evidence_refs, [evidence_id]),
                        "updated_at": _utc_now(),
                    },
                ),
                action="failed",
            )

        install_result = None
        if isinstance(results, list) and results:
            first = results[0]
            install_result = first if hasattr(first, "model_dump") else None
            if install_result is None and isinstance(first, dict):
                from ..industry.models import IndustryBootstrapInstallResult

                install_result = IndustryBootstrapInstallResult.model_validate(first)
        status = "applied"
        blocked_reason = None
        detail = ""
        if install_result is None:
            status = "failed"
            blocked_reason = "安装执行未返回结果。"
            detail = blocked_reason
        else:
            detail = str(getattr(install_result, "detail", "") or "")
            if str(getattr(install_result, "status", "") or "") == "failed":
                status = "blocked"
                blocked_reason = detail or "安装执行失败。"
        evidence_id = self._append_acquisition_evidence(
            entity_id=plan.id,
            actor=actor,
            capability_ref="learning:install-plan",
            risk_level=plan.risk_level,
            action="materialize-install-plan",
            result=detail or "已生成安装落地结果。",
            status="recorded" if status == "applied" else "failed",
            metadata={
                "proposal_id": plan.proposal_id,
                "install_result": (
                    install_result.model_dump(mode="json")
                    if install_result is not None
                    else None
                ),
            },
        )
        return self._save_install_binding_plan(
            plan.model_copy(
                update={
                    "status": status,
                    "install_result": install_result,
                    "blocked_reason": blocked_reason,
                    "evidence_refs": _merge_string_lists(plan.evidence_refs, [evidence_id]),
                    "applied_at": _utc_now(),
                    "updated_at": _utc_now(),
                },
            ),
            action="applied" if status == "applied" else status,
        )

    async def _apply_sop_binding_plan(
        self,
        plan: InstallBindingPlan,
        *,
        actor: str,
    ) -> InstallBindingPlan:
        binding_request = self._coerce_binding_request(plan.binding_request)
        if self._fixed_sop_service is None or binding_request is None:
            blocked_reason = "SOP 绑定服务不可用。"
            evidence_id = self._append_acquisition_evidence(
                entity_id=plan.id,
                actor=actor,
                capability_ref="learning:sop-binding-plan",
                risk_level=plan.risk_level,
                action="materialize-sop-binding",
                result=blocked_reason,
                status="failed",
                metadata={"proposal_id": plan.proposal_id},
            )
            return self._save_install_binding_plan(
                plan.model_copy(
                    update={
                        "status": "failed",
                        "blocked_reason": blocked_reason,
                        "evidence_refs": _merge_string_lists(plan.evidence_refs, [evidence_id]),
                        "updated_at": _utc_now(),
                    },
                ),
                action="failed",
            )
        binding_detail = self._find_existing_binding_detail(binding_request)
        created = False
        try:
            if binding_detail is None:
                creator = getattr(self._fixed_sop_service, "create_binding", None)
                if not callable(creator):
                    raise RuntimeError("SOP 绑定创建器不可用。")
                binding_detail = creator(binding_request)
                created = True
            doctor_runner = getattr(self._fixed_sop_service, "run_doctor", None)
            doctor_report = (
                doctor_runner(binding_detail.binding.binding_id)
                if callable(doctor_runner)
                else None
            )
        except Exception as exc:
            blocked_reason = str(exc).strip() or "SOP 绑定落地失败。"
            evidence_id = self._append_acquisition_evidence(
                entity_id=plan.id,
                actor=actor,
                capability_ref="learning:sop-binding-plan",
                risk_level=plan.risk_level,
                action="materialize-sop-binding",
                result=blocked_reason,
                status="failed",
                metadata={"proposal_id": plan.proposal_id},
            )
            return self._save_install_binding_plan(
                plan.model_copy(
                    update={
                        "status": "failed",
                        "blocked_reason": blocked_reason,
                        "evidence_refs": _merge_string_lists(plan.evidence_refs, [evidence_id]),
                        "updated_at": _utc_now(),
                    },
                ),
                action="failed",
            )

        doctor_status = (
            _normalize_optional_str(getattr(doctor_report, "status", None))
            if doctor_report is not None
            else None
        )
        blocked_reason = (
            _normalize_optional_str(getattr(doctor_report, "summary", None))
            if doctor_status == "blocked"
            else None
        )
        status = "applied" if doctor_status in {"ready", "degraded"} else "blocked"
        evidence_id = self._append_acquisition_evidence(
            entity_id=plan.id,
            actor=actor,
            capability_ref="learning:sop-binding-plan",
            risk_level=plan.risk_level,
            action="materialize-sop-binding",
            result=(
                f"{'已创建' if created else '复用'}绑定 {binding_detail.binding.binding_id}，"
                f"doctor={doctor_status or 'unknown'}。"
            ),
            status="recorded" if status == "applied" else "failed",
            metadata={
                "proposal_id": plan.proposal_id,
                "binding_id": binding_detail.binding.binding_id,
                "doctor_status": doctor_status,
            },
        )
        return self._save_install_binding_plan(
            plan.model_copy(
                update={
                    "status": status,
                    "binding_id": binding_detail.binding.binding_id,
                    "doctor_status": doctor_status,
                    "blocked_reason": blocked_reason,
                    "evidence_refs": _merge_string_lists(plan.evidence_refs, [evidence_id]),
                    "applied_at": _utc_now(),
                    "updated_at": _utc_now(),
                },
            ),
            action="applied" if status == "applied" else "blocked",
        )

    def _find_existing_binding_detail(
        self,
        request: object,
    ) -> object | None:
        if self._fixed_sop_service is None:
            return None
        binding_request = self._coerce_binding_request(request)
        if binding_request is None:
            return None
        lister = getattr(self._fixed_sop_service, "list_binding_details", None)
        if not callable(lister):
            return None
        bindings = lister(
            template_id=binding_request.template_id,
            industry_instance_id=binding_request.industry_instance_id,
            owner_agent_id=binding_request.owner_agent_id,
            limit=10,
        )
        return bindings[0] if isinstance(bindings, list) and bindings else None

    async def _run_onboarding(
        self,
        *,
        plan: InstallBindingPlan,
        proposal: CapabilityAcquisitionProposal,
        actor: str,
    ) -> OnboardingRun:
        run_id = _stable_learning_id("onboarding", plan.id)
        try:
            current_run = self._engine.get_onboarding_run(run_id)
        except KeyError:
            current_run = None
        run = OnboardingRun(
            id=run_id,
            plan_id=plan.id,
            proposal_id=proposal.id,
            industry_instance_id=proposal.industry_instance_id,
            target_agent_id=proposal.target_agent_id,
            target_role_id=proposal.target_role_id,
            status="running",
            summary="",
            checks=[],
            evidence_refs=list(current_run.evidence_refs or []) if current_run is not None else [],
            created_at=current_run.created_at if current_run is not None else _utc_now(),
            completed_at=None,
            updated_at=_utc_now(),
        )
        run = self._save_onboarding_run(
            run,
            action="updated" if current_run is not None else "created",
        )
        if plan.install_item is not None:
            return await self._run_install_onboarding(
                plan=plan,
                proposal=proposal,
                run=run,
                actor=actor,
            )
        return await self._run_binding_onboarding(
            plan=plan,
            proposal=proposal,
            run=run,
            actor=actor,
        )

    async def _run_install_onboarding(
        self,
        *,
        plan: InstallBindingPlan,
        proposal: CapabilityAcquisitionProposal,
        run: OnboardingRun,
        actor: str,
    ) -> OnboardingRun:
        checks: list[dict[str, object]] = []
        if plan.status != "applied":
            checks.append(
                {
                    "key": "materialization",
                    "label": "Materialization",
                    "status": "fail",
                    "message": plan.blocked_reason or "安装计划未成功落地。",
                    "detail": plan.blocked_reason or "",
                },
            )
        install_result = plan.install_result
        capability_ids = (
            list(getattr(install_result, "capability_ids", []) or [])
            if install_result is not None
            else list(proposal.install_item.capability_ids or [])
            if proposal.install_item is not None
            else []
        )
        mount_getter = (
            getattr(self._capability_service, "get_capability", None)
            if self._capability_service is not None
            else None
        )
        capability_surface = (
            getattr(self._agent_profile_service, "get_capability_surface", None)(
                proposal.target_agent_id,
            )
            if self._agent_profile_service is not None
            and proposal.target_agent_id is not None
            and callable(getattr(self._agent_profile_service, "get_capability_surface", None))
            else None
        )
        effective_capabilities = {
            str(item).strip()
            for item in list((capability_surface or {}).get("effective_capabilities") or [])
            if str(item).strip()
        }
        for capability_id in capability_ids:
            mount = mount_getter(capability_id) if callable(mount_getter) else None
            available = mount is not None
            enabled = bool(getattr(mount, "enabled", False)) if mount is not None else False
            effective = not effective_capabilities or capability_id in effective_capabilities
            checks.append(
                {
                    "key": f"capability:{capability_id}",
                    "label": capability_id,
                    "status": "pass" if available and enabled and effective else "fail",
                    "message": (
                        "能力已可用并已分配给目标 agent。"
                        if available and enabled and effective
                        else "能力尚未处于可执行状态或未进入目标 agent 能力面。"
                    ),
                    "detail": capability_id,
                },
            )
        static_passed = all(check.get("status") != "fail" for check in checks)
        if static_passed:
            checks.extend(
                await self._build_install_trial_checks(
                    plan=plan,
                    proposal=proposal,
                    capability_ids=capability_ids,
                ),
            )
        else:
            checks.append(
                {
                    "key": "trial-run",
                    "label": "Trial Run",
                    "status": "info",
                    "message": "安装尚未处于可执行状态，已跳过试运行。",
                    "detail": "",
                },
            )
        passed = all(check.get("status") != "fail" for check in checks)
        summary = (
            f"已完成 {proposal.title} 的 onboarding 验证与试运行。"
            if passed
            else f"{proposal.title} 的 onboarding 仍有阻断项或试运行失败。"
        )
        evidence_id = self._append_acquisition_evidence(
            entity_id=run.id,
            actor=actor,
            capability_ref="learning:onboarding",
            risk_level=proposal.risk_level,
            action="run-install-onboarding",
            result=summary,
            status="recorded" if passed else "failed",
            metadata={"proposal_id": proposal.id, "plan_id": plan.id, "checks": checks},
        )
        return self._save_onboarding_run(
            run.model_copy(
                update={
                    "status": "passed" if passed else "failed",
                    "summary": summary,
                    "checks": checks,
                    "evidence_refs": _merge_string_lists(run.evidence_refs, [evidence_id]),
                    "completed_at": _utc_now(),
                    "updated_at": _utc_now(),
                },
            ),
            action="completed",
        )

    async def _build_install_trial_checks(
        self,
        *,
        plan: InstallBindingPlan,
        proposal: CapabilityAcquisitionProposal,
        capability_ids: list[str],
    ) -> list[dict[str, object]]:
        install_item = proposal.install_item
        template_id = (
            _normalize_optional_str(getattr(install_item, "template_id", None))
            if install_item is not None
            else None
        )
        if template_id is not None:
            template_check = await self._run_install_template_trial_check(
                template_id=template_id,
                plan=plan,
                proposal=proposal,
            )
            if template_check is not None:
                return [template_check]
        if not capability_ids:
            return [
                {
                    "key": "trial-run",
                    "label": "Trial Run",
                    "status": "fail",
                    "message": "当前安装项没有定义可执行的试运行步骤，不能视为 onboarding 已完成。",
                    "detail": template_id or "missing-trial-run",
                },
            ]
        checks: list[dict[str, object]] = []
        for capability_id in capability_ids:
            checks.append(
                await self._run_capability_trial_check(
                    capability_id=capability_id,
                    plan=plan,
                    proposal=proposal,
                ),
            )
        return checks

    async def _run_install_template_trial_check(
        self,
        *,
        template_id: str,
        plan: InstallBindingPlan,
        proposal: CapabilityAcquisitionProposal,
    ) -> dict[str, object] | None:
        from ..capabilities.install_templates import run_install_template_example

        example_run = await run_install_template_example(
            template_id,
            capability_service=self._capability_service,
            browser_runtime_service=self._get_onboarding_browser_runtime_service(),
            config=self._build_install_trial_config(plan=plan, proposal=proposal),
        )
        if example_run is None:
            return None
        payload = example_run.model_dump(mode="json")
        error_payload = payload.get("error")
        detail = (
            str(error_payload.get("summary") or error_payload.get("code") or "").strip()
            if isinstance(error_payload, dict)
            else ""
        )
        if not detail:
            detail = (
                ",".join(
                    str(item).strip()
                    for item in list(payload.get("operations") or [])
                    if str(item).strip()
                )
                or template_id
            )
        return {
            "key": f"trial-run:{template_id}",
            "label": "Trial Run",
            "status": "pass" if payload.get("status") == "success" else "fail",
            "message": str(payload.get("summary") or f"{template_id} 试运行已执行。"),
            "detail": detail,
            "metadata": payload,
        }

    async def _run_capability_trial_check(
        self,
        *,
        capability_id: str,
        plan: InstallBindingPlan,
        proposal: CapabilityAcquisitionProposal,
    ) -> dict[str, object]:
        template_map = {
            "tool:browser_use": "browser-local",
            "mcp:desktop_windows": "desktop-windows",
        }
        template_id = template_map.get(capability_id)
        if template_id is not None:
            template_check = await self._run_install_template_trial_check(
                template_id=template_id,
                plan=plan,
                proposal=proposal,
            )
            if template_check is not None:
                return template_check
        if capability_id.startswith("mcp:"):
            return await self._run_mcp_trial_check(capability_id=capability_id)
        if not capability_id.startswith("skill:"):
            return {
                "key": f"trial-run:{capability_id}",
                "label": capability_id,
                "status": "fail",
                "message": "该能力还没有定义安全试运行动作，onboarding 不能判定为通过。",
                "detail": "unsupported-trial-run",
            }
        resolver = (
            getattr(self._capability_service, "resolve_executor", None)
            if self._capability_service is not None
            else None
        )
        executor = resolver(capability_id) if callable(resolver) else None
        if executor is None:
            return {
                "key": f"trial-run:{capability_id}",
                "label": capability_id,
                "status": "fail",
                "message": "能力执行器不可用，无法完成真实试运行。",
                "detail": "executor-unavailable",
            }
        from ..capabilities.execution_support import (
            _tool_response_payload,
            _tool_response_success,
            _tool_response_summary,
        )

        try:
            describe_response = await _maybe_await(executor(action="describe"))
        except Exception as exc:
            return {
                "key": f"trial-run:{capability_id}",
                "label": capability_id,
                "status": "fail",
                "message": f"试运行说明读取失败：{exc}",
                "detail": exc.__class__.__name__,
            }

        describe_payload = _tool_response_payload(describe_response)
        if not _tool_response_success(describe_response):
            return {
                "key": f"trial-run:{capability_id}",
                "label": capability_id,
                "status": "fail",
                "message": _tool_response_summary(describe_response),
                "detail": "describe-failed",
                "metadata": describe_payload if isinstance(describe_payload, dict) else {},
            }

        skill_payload = (
            describe_payload.get("skill")
            if isinstance(describe_payload, dict)
            and isinstance(describe_payload.get("skill"), dict)
            else {}
        )
        trial_script_path = self._select_skill_trial_script(
            skill_payload.get("scripts")
            if isinstance(skill_payload, dict)
            else None,
        )
        if trial_script_path is None:
            return {
                "key": f"trial-run:{capability_id}",
                "label": capability_id,
                "status": "fail",
                "message": "当前 skill 没有声明安全试运行脚本，不能只靠说明信息判定通过。",
                "detail": "missing-skill-trial-script",
                "metadata": describe_payload if isinstance(describe_payload, dict) else {},
            }

        try:
            response = await _maybe_await(
                executor(
                    action="run_script",
                    script_path=trial_script_path,
                    timeout=120,
                ),
            )
        except Exception as exc:
            return {
                "key": f"trial-run:{capability_id}",
                "label": capability_id,
                "status": "fail",
                "message": f"试运行执行失败：{exc}",
                "detail": exc.__class__.__name__,
            }

        payload = _tool_response_payload(response)
        metadata = payload if isinstance(payload, dict) else {}
        metadata = {
            **metadata,
            "trial_script_path": trial_script_path,
            "trial_mode": "run_script",
        }
        return {
            "key": f"trial-run:{capability_id}",
            "label": capability_id,
            "status": "pass" if _tool_response_success(response) else "fail",
            "message": _tool_response_summary(response),
            "detail": trial_script_path,
            "metadata": metadata,
        }

    def _select_skill_trial_script(self, scripts_payload: object) -> str | None:
        if not isinstance(scripts_payload, dict):
            return None
        preferred_stems = (
            "trial",
            "smoke",
            "verify",
            "check",
            "doctor",
            "selftest",
        )
        supported_suffixes = {"", "py", "ps1", "sh", "js", "ts", "mjs", "cjs", "cmd", "bat"}
        candidates: list[tuple[int, str]] = []
        for raw_path in scripts_payload.keys():
            candidate = _normalize_optional_str(raw_path)
            if candidate is None:
                continue
            normalized = candidate.replace("\\", "/")
            basename = normalized.rsplit("/", 1)[-1].lower()
            stem, dot, suffix = basename.partition(".")
            if stem not in preferred_stems:
                continue
            if suffix.lower() not in supported_suffixes:
                continue
            candidates.append((preferred_stems.index(stem), candidate))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1]))
        return candidates[0][1]

    async def _resolve_mcp_trial_client(
        self,
        *,
        client_key: str,
    ) -> tuple[object | None, object | None, str]:
        capability_service = self._capability_service
        manager = (
            getattr(capability_service, "_mcp_manager", None)
            if capability_service is not None
            else None
        )
        if manager is not None and callable(getattr(manager, "get_client", None)):
            try:
                client = await manager.get_client(client_key)
            except Exception as exc:
                return None, None, f"mcp-manager-error:{exc.__class__.__name__}"
            if client is not None:
                return client, None, ""

        try:
            from .runtime_core import load_config

            config = load_config()
            client_config = getattr(getattr(config, "mcp", None), "clients", {}).get(
                client_key,
            )
        except Exception as exc:
            return None, None, f"load-config-failed:{exc.__class__.__name__}"
        if client_config is None:
            return None, None, "mcp-client-config-missing"

        from ..app.mcp.manager import MCPClientManager

        temp_manager = MCPClientManager()
        try:
            await temp_manager.replace_client(client_key, client_config, timeout=20.0)
            client = await temp_manager.get_client(client_key)
        except Exception as exc:
            try:
                await temp_manager.close_all()
            except Exception:
                pass
            return None, None, f"mcp-connect-failed:{exc.__class__.__name__}"
        if client is None:
            try:
                await temp_manager.close_all()
            except Exception:
                pass
            return None, None, "mcp-client-unavailable"
        return client, temp_manager, ""

    async def _run_mcp_trial_check(
        self,
        *,
        capability_id: str,
    ) -> dict[str, object]:
        from ..capabilities.execution_support import (
            _tool_response_payload,
            _tool_response_success,
            _tool_response_summary,
        )

        client_key = capability_id.split(":", 1)[1] if ":" in capability_id else ""
        if not client_key:
            return {
                "key": f"trial-run:{capability_id}",
                "label": capability_id,
                "status": "fail",
                "message": "MCP 客户端标识缺失，无法执行真实试运行。",
                "detail": "missing-client-key",
            }

        client, temp_manager, resolve_error = await self._resolve_mcp_trial_client(
            client_key=client_key,
        )
        if client is None:
            return {
                "key": f"trial-run:{capability_id}",
                "label": capability_id,
                "status": "fail",
                "message": "MCP 客户端当前不可连接，无法执行真实试运行。",
                "detail": resolve_error or "mcp-client-unavailable",
            }

        try:
            if not callable(getattr(client, "list_tools", None)):
                return {
                    "key": f"trial-run:{capability_id}",
                    "label": capability_id,
                    "status": "fail",
                    "message": "当前 MCP 客户端不支持工具清单拉取，无法完成真实试运行。",
                    "detail": "list-tools-unavailable",
                }

            tools_response = await client.list_tools()
            tool_entries = _mcp_trial_tool_entries(tools_response)
            tool_names = [
                name for name in (_mcp_trial_tool_name(item) for item in tool_entries) if name
            ]
            if not tool_names:
                return {
                    "key": f"trial-run:{capability_id}",
                    "label": capability_id,
                    "status": "fail",
                    "message": "MCP 客户端已连通，但没有返回可用工具，不能视为试运行通过。",
                    "detail": "no-tools-returned",
                }

            safe_tool_name = _pick_safe_mcp_trial_tool_name(tool_entries)
            metadata: dict[str, object] = {
                "tool_count": len(tool_names),
                "tool_names": tool_names[:8],
            }
            if not safe_tool_name:
                return {
                    "key": f"trial-run:{capability_id}",
                    "label": capability_id,
                    "status": "pass",
                    "message": f"已连通 MCP 客户端并拉取到 {len(tool_names)} 个工具清单。",
                    "detail": "list-tools",
                    "metadata": metadata,
                }

            callable_fn = await client.get_callable_function(
                safe_tool_name,
                wrap_tool_result=True,
                execution_timeout=15.0,
            )
            response = await callable_fn()
            metadata["trial_tool_name"] = safe_tool_name
            payload = _tool_response_payload(response)
            if isinstance(payload, dict):
                metadata["trial_output"] = payload
            return {
                "key": f"trial-run:{capability_id}",
                "label": capability_id,
                "status": "pass" if _tool_response_success(response) else "fail",
                "message": _tool_response_summary(response)
                or f"Executed MCP trial tool '{safe_tool_name}'.",
                "detail": safe_tool_name,
                "metadata": metadata,
            }
        except Exception as exc:
            return {
                "key": f"trial-run:{capability_id}",
                "label": capability_id,
                "status": "fail",
                "message": f"MCP 试运行失败：{exc}",
                "detail": exc.__class__.__name__,
            }
        finally:
            if temp_manager is not None and callable(getattr(temp_manager, "close_all", None)):
                try:
                    await temp_manager.close_all()
                except Exception:
                    pass

    def _build_install_trial_config(
        self,
        *,
        plan: InstallBindingPlan,
        proposal: CapabilityAcquisitionProposal,
    ) -> dict[str, object]:
        install_item = proposal.install_item
        template_id = (
            _normalize_optional_str(getattr(install_item, "template_id", None))
            if install_item is not None
            else None
        )
        if template_id != "browser-local":
            return {}
        profile_id = (
            _normalize_optional_str(getattr(plan.install_result, "client_key", None))
            or _normalize_optional_str(getattr(install_item, "client_key", None))
            or "browser-local-default"
        )
        return {
            "profile_id": profile_id,
            "session_id": (
                f"learning-onboarding-{sha1(plan.id.encode('utf-8')).hexdigest()[:12]}"
            ),
            "headed": False,
            "reuse_running_session": True,
            "persist_login_state": True,
        }

    def _get_onboarding_browser_runtime_service(self) -> object | None:
        if self._industry_service is None:
            return None
        getter = getattr(self._industry_service, "_get_browser_runtime_service", None)
        if callable(getter):
            try:
                return getter()
            except Exception:
                return None
        getter = getattr(self._industry_service, "get_browser_runtime_service", None)
        if callable(getter):
            try:
                return getter()
            except Exception:
                return None
        return None

    async def _run_binding_onboarding(
        self,
        *,
        plan: InstallBindingPlan,
        proposal: CapabilityAcquisitionProposal,
        run: OnboardingRun,
        actor: str,
    ) -> OnboardingRun:
        checks: list[dict[str, object]] = []
        evidence_refs = list(run.evidence_refs or [])
        if plan.binding_id is None or self._fixed_sop_service is None:
            checks.append(
                {
                    "key": "binding",
                    "label": "Binding",
                    "status": "fail",
                    "message": plan.blocked_reason or "未生成可用 binding。",
                    "detail": plan.blocked_reason or "",
                },
            )
            passed = False
        else:
            doctor_runner = getattr(self._fixed_sop_service, "run_doctor", None)
            doctor_report = doctor_runner(plan.binding_id) if callable(doctor_runner) else None
            doctor_status = _normalize_optional_str(getattr(doctor_report, "status", None)) or "unknown"
            checks.append(
                {
                    "key": "doctor",
                    "label": "Doctor",
                    "status": "pass" if doctor_status in {"ready", "degraded"} else "fail",
                    "message": getattr(doctor_report, "summary", None) or f"doctor={doctor_status}",
                    "detail": doctor_status,
                },
            )
            dry_run_status = "error"
            dry_run_summary = "SOP dry-run 不可用。"
            trigger = getattr(self._fixed_sop_service, "run_binding", None)
            if callable(trigger):
                try:
                    from ..sop_kernel import FixedSopRunRequest

                    trigger_response = await _maybe_await(
                        trigger(
                            plan.binding_id,
                            FixedSopRunRequest(
                                input_payload={"source": "learning-onboarding"},
                                owner_agent_id=proposal.target_agent_id,
                                owner_scope=proposal.owner_scope,
                                dry_run=True,
                                metadata={
                                    "proposal_id": proposal.id,
                                    "plan_id": plan.id,
                                    "source": "learning-onboarding",
                                },
                            ),
                        ),
                    )
                    dry_run_status = _normalize_optional_str(
                        getattr(trigger_response, "status", None),
                    ) or "success"
                    dry_run_summary = _normalize_optional_str(
                        getattr(trigger_response, "summary", None),
                    ) or "已完成 SOP dry-run。"
                    evidence_refs = _merge_string_lists(
                        evidence_refs,
                        [_normalize_optional_str(getattr(trigger_response, "evidence_id", None))],
                    )
                except Exception as exc:
                    dry_run_summary = str(exc).strip() or "SOP dry-run 失败。"
            checks.append(
                {
                    "key": "dry-run",
                    "label": "Dry Run",
                    "status": "pass" if dry_run_status == "success" else "fail",
                    "message": dry_run_summary,
                    "detail": dry_run_status,
                },
            )
            passed = doctor_status in {"ready", "degraded"} and dry_run_status == "success"
        summary = (
            f"已完成 {proposal.title} 的 SOP onboarding 验证。"
            if passed
            else f"{proposal.title} 的 SOP onboarding 未通过。"
        )
        evidence_id = self._append_acquisition_evidence(
            entity_id=run.id,
            actor=actor,
            capability_ref="learning:onboarding",
            risk_level=proposal.risk_level,
            action="run-binding-onboarding",
            result=summary,
            status="recorded" if passed else "failed",
            metadata={
                "proposal_id": proposal.id,
                "plan_id": plan.id,
                "binding_id": plan.binding_id,
                "checks": checks,
            },
        )
        return self._save_onboarding_run(
            run.model_copy(
                update={
                    "status": "passed" if passed else "failed",
                    "summary": summary,
                    "checks": checks,
                    "evidence_refs": _merge_string_lists(evidence_refs, [evidence_id]),
                    "completed_at": _utc_now(),
                    "updated_at": _utc_now(),
                },
            ),
            action="completed",
        )

    def _record_onboarding_outcome(
        self,
        *,
        proposal: CapabilityAcquisitionProposal,
        plan: InstallBindingPlan,
        run: OnboardingRun,
        actor: str,
    ) -> None:
        target_agent_id = proposal.target_agent_id or actor
        if target_agent_id:
            self._engine.record_growth(
                GrowthEvent(
                    agent_id=target_agent_id,
                    task_id=run.id,
                    change_type=(
                        "capability_onboarded"
                        if proposal.acquisition_kind == "install-capability" and run.status == "passed"
                        else "capability_onboarding_failed"
                        if proposal.acquisition_kind == "install-capability"
                        else "sop_binding_onboarded"
                        if run.status == "passed"
                        else "sop_binding_onboarding_failed"
                    ),
                    description=run.summary,
                    source_evidence_id=run.evidence_refs[0] if run.evidence_refs else None,
                    risk_level=proposal.risk_level,
                    result=run.status,
                ),
            )
        remember = (
            getattr(self._experience_memory_service, "remember_outcome", None)
            if self._experience_memory_service is not None
            else None
        )
        if callable(remember) and proposal.target_agent_id is not None:
            remember(
                agent_id=proposal.target_agent_id,
                title=proposal.title,
                status="completed" if run.status == "passed" else "failed",
                summary=run.summary,
                capability_ref=f"learning:{proposal.acquisition_kind}",
                task_id=run.id,
                source_agent_id=actor,
                industry_instance_id=proposal.industry_instance_id,
                industry_role_id=proposal.target_role_id,
                owner_scope=proposal.owner_scope,
                metadata={
                    "proposal_id": proposal.id,
                    "plan_id": plan.id,
                    "onboarding_run_id": run.id,
                    "acquisition_kind": proposal.acquisition_kind,
                    "binding_id": plan.binding_id,
                },
            )

    def _append_acquisition_evidence(
        self,
        *,
        entity_id: str,
        actor: str,
        capability_ref: str,
        risk_level: str,
        action: str,
        result: str,
        status: str,
        metadata: dict[str, object] | None = None,
    ) -> str | None:
        if self._evidence_ledger is None:
            return None
        record = self._evidence_ledger.append(
            EvidenceRecord(
                task_id=entity_id,
                actor_ref=actor,
                capability_ref=capability_ref,
                risk_level=risk_level,
                action_summary=action,
                result_summary=result,
                status=status,
                metadata=dict(metadata or {}),
            ),
        )
        return record.id

    @staticmethod
    def _coerce_binding_request(request: object) -> object | None:
        if request is None:
            return None
        if hasattr(request, "template_id") and hasattr(request, "owner_agent_id"):
            return request
        if isinstance(request, dict):
            from ..sop_kernel import FixedSopBindingCreateRequest

            return FixedSopBindingCreateRequest.model_validate(request)
        return None

    @staticmethod
    def _is_actionable_sop_candidate(candidate: dict[str, object]) -> bool:
        signals = [
            str(item).strip()
            for item in list(candidate.get("match_signals") or [])
            if str(item).strip()
        ]
        return any(not signal.startswith("query:") for signal in signals)


__all__ = ["LearningAcquisitionRuntimeService"]
