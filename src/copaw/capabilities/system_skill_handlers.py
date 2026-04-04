# -*- coding: utf-8 -*-
from __future__ import annotations

import inspect

from .remote_skill_contract import (
    build_remote_skill_preflight,
    resolve_candidate_capability_ids,
    resolve_remote_skill_candidate,
)
from .skill_service import CapabilitySkillService


class SystemSkillCapabilityFacade:
    def __init__(
        self,
        *,
        skill_service: CapabilitySkillService,
        get_capability_fn=None,
        resolve_agent_profile_fn=None,
        agent_profile_service: object | None = None,
        industry_service: object | None = None,
        trial_scope_handler=None,
        apply_role_handler=None,
    ) -> None:
        self._skill_service = skill_service
        self._get_capability = get_capability_fn
        self._resolve_agent_profile = resolve_agent_profile_fn
        self._agent_profile_service = agent_profile_service
        self._industry_service = industry_service
        self._trial_scope_handler = trial_scope_handler
        self._apply_role_handler = apply_role_handler

    def handle_create_skill(
        self,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        name = str(resolved_payload.get("name") or "").strip()
        if not name:
            return {"success": False, "error": "name is required"}
        content = resolved_payload.get("content")
        if not isinstance(content, str) or not content.strip():
            return {"success": False, "error": "content is required"}
        references = resolved_payload.get("references")
        if references is not None and not isinstance(references, dict):
            return {"success": False, "error": "references must be an object"}
        scripts = resolved_payload.get("scripts")
        if scripts is not None and not isinstance(scripts, dict):
            return {"success": False, "error": "scripts must be an object"}
        overwrite = bool(resolved_payload.get("overwrite", False))
        created = self._skill_service.create_skill(
            name=name,
            content=content,
            overwrite=overwrite,
            references=references,
            scripts=scripts,
        )
        if not created:
            return {
                "success": False,
                "error": f"Failed to create skill '{name}'.",
            }
        return {
            "success": True,
            "summary": f"Created skill '{name}'.",
            "created": True,
            "name": name,
        }

    def handle_install_hub_skill(
        self,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        bundle_url = str(resolved_payload.get("bundle_url") or "").strip()
        if not bundle_url:
            return {"success": False, "error": "bundle_url is required"}
        version = str(resolved_payload.get("version") or "")
        enable = bool(resolved_payload.get("enable", True))
        overwrite = bool(resolved_payload.get("overwrite", False))
        try:
            installed = self._skill_service.install_skill_from_hub(
                bundle_url=bundle_url,
                version=version,
                enable=enable,
                overwrite=overwrite,
            )
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        except RuntimeError as exc:
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            return {
                "success": False,
                "error": f"Skill hub import failed: {exc}",
            }
        return {
            "success": True,
            "summary": f"Installed skill '{installed.name}' from hub.",
            "installed": True,
            "name": installed.name,
            "enabled": installed.enabled,
            "source_url": installed.source_url,
        }

    async def handle_trial_remote_skill_assignment(
        self,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        candidate_payload = resolved_payload.get("candidate")
        if not isinstance(candidate_payload, dict):
            return {"success": False, "error": "candidate payload is required"}
        target_agent_id = str(resolved_payload.get("target_agent_id") or "").strip() or None
        candidate = resolve_remote_skill_candidate(
            candidate_payload,
            get_capability_fn=self._get_capability,
        )
        if candidate is None:
            return {
                "success": False,
                "error": "remote skill candidate could not be resolved or is not allowlisted",
            }
        capability_assignment_mode = str(
            resolved_payload.get("capability_assignment_mode") or "merge",
        ).strip().lower()
        if capability_assignment_mode not in {"merge", "replace"}:
            return {
                "success": False,
                "error": "capability_assignment_mode must be 'merge' or 'replace'",
            }
        replacement_capability_ids = [
            str(item).strip()
            for item in list(resolved_payload.get("replacement_capability_ids") or [])
            if str(item).strip()
        ]
        requested_capability_ids = [
            str(item).strip()
            for item in list(resolved_payload.get("capability_ids") or [])
            if str(item).strip()
        ]
        preflight = build_remote_skill_preflight(
            candidate=candidate,
            target_agent_id=target_agent_id,
            capability_assignment_mode=capability_assignment_mode,  # type: ignore[arg-type]
            replacement_capability_ids=replacement_capability_ids,
            requested_capability_ids=requested_capability_ids,
            get_capability_fn=self._get_capability,
            agent_profile_service=self._agent_profile_service,
        )
        review_acknowledged = bool(
            resolved_payload.get("review_acknowledged", not candidate.review_required),
        )
        if candidate.review_required and not review_acknowledged:
            return {
                "success": False,
                "error": "candidate review must be acknowledged before trial install",
                "preflight": preflight.model_dump(mode="json"),
            }
        if not preflight.ready:
            return {
                "success": False,
                "error": preflight.summary or "remote skill preflight failed",
                "preflight": preflight.model_dump(mode="json"),
            }
        try:
            installed = self._skill_service.install_skill_from_hub(
                bundle_url=candidate.bundle_url,
                version=str(resolved_payload.get("version") or candidate.version or ""),
                enable=bool(resolved_payload.get("enable", True)),
                overwrite=bool(resolved_payload.get("overwrite", False)),
            )
        except ValueError as exc:
            return {
                "success": False,
                "error": str(exc),
                "preflight": preflight.model_dump(mode="json"),
            }
        except RuntimeError as exc:
            return {
                "success": False,
                "error": str(exc),
                "preflight": preflight.model_dump(mode="json"),
            }
        except Exception as exc:
            return {
                "success": False,
                "error": f"Trial remote skill install failed: {exc}",
                "preflight": preflight.model_dump(mode="json"),
            }
        installed_name = str(getattr(installed, "name", "") or "").strip()
        installed_capability_ids = resolve_candidate_capability_ids(
            candidate,
            installed_name=installed_name,
        )
        if not installed_capability_ids:
            installed_capability_ids = resolve_candidate_capability_ids(
                candidate,
                requested_capability_ids=requested_capability_ids,
            )
        trial_attachment: dict[str, object] | None = None
        if target_agent_id:
            attachment_payload = self._build_trial_scope_payload(
                resolved_payload=resolved_payload,
                target_agent_id=target_agent_id,
                installed_capability_ids=installed_capability_ids,
                replacement_capability_ids=replacement_capability_ids,
                capability_assignment_mode=capability_assignment_mode,
                preflight=preflight.model_dump(mode="json"),
            )
            result = self._attach_trial_scope(attachment_payload)
            if inspect.isawaitable(result):
                result = await result
            trial_attachment = (
                dict(result)
                if isinstance(result, dict)
                else {
                    "success": False,
                    "error": "trial scope attach returned an unexpected result",
                }
            )
            if not trial_attachment.get("success"):
                return {
                    "success": False,
                    "error": str(
                        trial_attachment.get("error")
                        or "remote skill scoped attach failed"
                    ),
                    "installed": True,
                    "name": getattr(installed, "name", ""),
                    "enabled": bool(getattr(installed, "enabled", True)),
                    "source_url": getattr(installed, "source_url", candidate.bundle_url),
                    "installed_capability_ids": installed_capability_ids,
                    "trial_attachment": trial_attachment,
                    "preflight": preflight.model_dump(mode="json"),
                }
        summary = (
            f"Installed remote skill '{getattr(installed, 'name', '')}'"
            + (
                f" and attached it to '{target_agent_id}'."
                if target_agent_id
                else "."
            )
        )
        return {
            "success": True,
            "summary": summary,
            "installed": True,
            "name": getattr(installed, "name", ""),
            "enabled": bool(getattr(installed, "enabled", True)),
            "source_url": getattr(installed, "source_url", candidate.bundle_url),
            "installed_capability_ids": installed_capability_ids,
            "target_agent_id": target_agent_id,
            "replacement_capability_ids": replacement_capability_ids,
            "trial_attachment": trial_attachment,
            "preflight": preflight.model_dump(mode="json"),
            "resolved_candidate": candidate.model_dump(mode="json"),
        }

    async def handle_apply_capability_lifecycle(
        self,
        resolved_payload: dict[str, object],
    ) -> dict[str, object]:
        decision_kind = str(
            resolved_payload.get("decision_kind") or "continue_trial",
        ).strip().lower()
        if decision_kind not in {
            "continue_trial",
            "promote_to_role",
            "keep_seat_local",
            "replace_existing",
            "rollback",
            "retire",
        }:
            return {"success": False, "error": "unsupported decision_kind"}
        candidate_id = str(resolved_payload.get("candidate_id") or "").strip()
        target_agent_id = str(resolved_payload.get("target_agent_id") or "").strip()
        if not target_agent_id:
            return {"success": False, "error": "target_agent_id is required"}
        current_capabilities = self._effective_capabilities_for_agent(target_agent_id)
        target_capability_ids = [
            str(item).strip()
            for item in list(
                resolved_payload.get("target_capability_ids")
                or resolved_payload.get("capability_ids")
                or []
            )
            if str(item).strip()
        ]
        replacement_target_ids = [
            str(item).strip()
            for item in list(resolved_payload.get("replacement_target_ids") or [])
            if str(item).strip()
        ]
        rollback_target_ids = [
            str(item).strip()
            for item in list(resolved_payload.get("rollback_target_ids") or [])
            if str(item).strip()
        ]
        if decision_kind in {"continue_trial", "keep_seat_local"}:
            attachment_payload = {
                **dict(resolved_payload),
                "candidate_id": candidate_id or None,
                "target_agent_id": target_agent_id,
                "capability_ids": target_capability_ids,
                "replacement_capability_ids": replacement_target_ids,
                "selected_scope": (
                    str(resolved_payload.get("selected_scope") or "").strip().lower()
                    or self._resolve_trial_scope_kind(
                        selected_seat_ref=resolved_payload.get("selected_seat_ref"),
                        selected_scope=resolved_payload.get("selected_scope"),
                    )
                ),
                "scope_ref": self._resolve_trial_scope_ref(
                    target_agent_id=target_agent_id,
                    resolved_payload=resolved_payload,
                ),
            }
            result = self._attach_trial_scope(attachment_payload)
            if inspect.isawaitable(result):
                result = await result
            attachment_result = dict(result) if isinstance(result, dict) else {}
            return {
                "success": bool(attachment_result.get("success")),
                "summary": str(
                    attachment_result.get("summary")
                    or f"Applied capability lifecycle '{decision_kind}'."
                ),
                "decision_kind": decision_kind,
                "candidate_id": candidate_id,
                "target_agent_id": target_agent_id,
                "lifecycle_result": attachment_result,
            }
        if self._apply_role_handler is None:
            return {"success": False, "error": "apply_role handler is not available"}
        final_capabilities = self._build_lifecycle_capabilities(
            decision_kind=decision_kind,
            current_capabilities=current_capabilities,
            target_capability_ids=target_capability_ids,
            replacement_target_ids=replacement_target_ids,
            rollback_target_ids=rollback_target_ids,
        )
        apply_payload = {
            "agent_id": target_agent_id,
            "capabilities": final_capabilities,
            "capability_assignment_mode": "replace",
            "reason": str(resolved_payload.get("reason") or "").strip()
            or f"system:apply_capability_lifecycle:{decision_kind}",
        }
        result = self._apply_role_handler(apply_payload)
        if inspect.isawaitable(result):
            result = await result
        lifecycle_result = (
            dict(result)
            if isinstance(result, dict)
            else {"success": False, "error": "apply_role returned an unexpected result"}
        )
        return {
            "success": bool(lifecycle_result.get("success")),
            "summary": str(
                lifecycle_result.get("summary")
                or lifecycle_result.get("error")
                or f"Applied capability lifecycle '{decision_kind}'."
            ),
            "decision_kind": decision_kind,
            "candidate_id": candidate_id,
            "target_agent_id": target_agent_id,
            "selected_scope": self._resolve_trial_scope_kind(
                selected_seat_ref=resolved_payload.get("selected_seat_ref"),
                selected_scope=resolved_payload.get("selected_scope"),
            ),
            "selected_seat_ref": str(
                resolved_payload.get("selected_seat_ref") or ""
            ).strip()
            or None,
            "replacement_target_ids": replacement_target_ids,
            "rollback_target_ids": rollback_target_ids,
            "lifecycle_result": lifecycle_result,
        }

    def set_agent_profile_service(self, agent_profile_service: object | None) -> None:
        self._agent_profile_service = agent_profile_service

    def set_industry_service(self, industry_service: object | None) -> None:
        self._industry_service = industry_service

    def set_trial_scope_handler(self, trial_scope_handler) -> None:
        self._trial_scope_handler = trial_scope_handler

    def set_apply_role_handler(self, apply_role_handler) -> None:
        self._apply_role_handler = apply_role_handler

    def _attach_trial_scope(
        self,
        payload: dict[str, object],
    ):
        handler = self._trial_scope_handler
        if not callable(handler):
            handler = getattr(self._industry_service, "attach_candidate_to_scope", None)
        if callable(handler):
            try:
                return handler(**payload)
            except TypeError:
                return handler(payload)
        return {
            "success": False,
            "error": "industry trial scope attach is not available",
        }

    def _build_trial_scope_payload(
        self,
        *,
        resolved_payload: dict[str, object],
        target_agent_id: str,
        installed_capability_ids: list[str],
        replacement_capability_ids: list[str],
        capability_assignment_mode: str,
        preflight: dict[str, object],
    ) -> dict[str, object]:
        return {
            "candidate_id": str(resolved_payload.get("candidate_id") or "").strip() or None,
            "target_agent_id": target_agent_id,
            "capability_ids": list(installed_capability_ids),
            "replacement_capability_ids": list(replacement_capability_ids),
            "capability_assignment_mode": capability_assignment_mode,
            "selected_scope": self._resolve_trial_scope_kind(
                selected_seat_ref=resolved_payload.get("selected_seat_ref"),
                selected_scope=resolved_payload.get("selected_scope"),
            ),
            "scope_ref": self._resolve_trial_scope_ref(
                target_agent_id=target_agent_id,
                resolved_payload=resolved_payload,
            ),
            "selected_seat_ref": str(
                resolved_payload.get("selected_seat_ref") or ""
            ).strip()
            or None,
            "target_role_id": str(resolved_payload.get("target_role_id") or "").strip()
            or str(
                ((preflight.get("trial_plan") or {}) if isinstance(preflight, dict) else {}).get(
                    "target_role_id",
                )
                or ""
            ).strip()
            or None,
            "trial_scope": str(resolved_payload.get("trial_scope") or "").strip()
            or str(
                ((preflight.get("trial_plan") or {}) if isinstance(preflight, dict) else {}).get(
                    "rollout_scope",
                )
                or ""
            ).strip()
            or None,
            "lifecycle_stage": str(resolved_payload.get("lifecycle_stage") or "").strip()
            or "trial",
            "next_lifecycle_stage": str(
                resolved_payload.get("next_lifecycle_stage") or ""
            ).strip()
            or None,
            "replacement_target_ids": list(
                resolved_payload.get("replacement_target_ids") or replacement_capability_ids
            ),
            "rollback_target_ids": list(
                resolved_payload.get("rollback_target_ids") or replacement_capability_ids
            ),
            "reason": str(resolved_payload.get("reason") or "").strip()
            or f"Trial remote skill attachment for '{target_agent_id}'.",
            "preflight": preflight,
        }

    @staticmethod
    def _resolve_trial_scope_kind(
        *,
        selected_seat_ref: object | None,
        selected_scope: object | None,
    ) -> str:
        normalized_scope = str(selected_scope or "").strip().lower()
        if normalized_scope in {"seat", "session", "agent"}:
            return normalized_scope
        return "seat" if str(selected_seat_ref or "").strip() else "agent"

    def _resolve_trial_scope_ref(
        self,
        *,
        target_agent_id: str,
        resolved_payload: dict[str, object],
    ) -> str:
        explicit_scope_ref = str(resolved_payload.get("scope_ref") or "").strip()
        if explicit_scope_ref:
            return explicit_scope_ref
        selected_seat_ref = str(resolved_payload.get("selected_seat_ref") or "").strip()
        if selected_seat_ref:
            return selected_seat_ref
        return target_agent_id

    @staticmethod
    def _build_lifecycle_capabilities(
        *,
        decision_kind: str,
        current_capabilities: list[str],
        target_capability_ids: list[str],
        replacement_target_ids: list[str],
        rollback_target_ids: list[str],
    ) -> list[str]:
        final_capabilities = list(current_capabilities)
        if decision_kind in {"promote_to_role", "replace_existing"}:
            final_capabilities = [
                capability_id
                for capability_id in final_capabilities
                if capability_id not in replacement_target_ids
            ]
            for capability_id in target_capability_ids:
                if capability_id not in final_capabilities:
                    final_capabilities.append(capability_id)
            return final_capabilities
        if decision_kind == "rollback":
            final_capabilities = [
                capability_id
                for capability_id in final_capabilities
                if capability_id not in target_capability_ids
            ]
            for capability_id in rollback_target_ids:
                if capability_id not in final_capabilities:
                    final_capabilities.append(capability_id)
            return final_capabilities
        if decision_kind == "retire":
            return [
                capability_id
                for capability_id in final_capabilities
                if capability_id not in replacement_target_ids
            ]
        return final_capabilities

    def _effective_capabilities_for_agent(self, agent_id: str) -> list[str]:
        getter = getattr(self._agent_profile_service, "get_capability_surface", None)
        if callable(getter):
            surface = getter(agent_id)
            if isinstance(surface, dict):
                resolved = [
                    str(item).strip()
                    for item in list(surface.get("effective_capabilities") or [])
                    if str(item).strip()
                ]
                if resolved:
                    return resolved
        if callable(self._resolve_agent_profile):
            profile = self._resolve_agent_profile(agent_id)
            capabilities = getattr(profile, "capabilities", None) if profile is not None else None
            if isinstance(capabilities, list):
                return [str(item).strip() for item in capabilities if str(item).strip()]
        return []
