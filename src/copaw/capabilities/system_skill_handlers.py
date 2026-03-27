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
        apply_role_handler=None,
    ) -> None:
        self._skill_service = skill_service
        self._get_capability = get_capability_fn
        self._resolve_agent_profile = resolve_agent_profile_fn
        self._agent_profile_service = agent_profile_service
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
        assignment_result: dict[str, object] | None = None
        if target_agent_id and self._apply_role_handler is not None:
            apply_payload = self._build_trial_apply_payload(
                target_agent_id=target_agent_id,
                installed_capability_ids=installed_capability_ids,
                replacement_capability_ids=replacement_capability_ids,
                capability_assignment_mode=capability_assignment_mode,
                reason=str(resolved_payload.get("reason") or "").strip(),
            )
            result = self._apply_role_handler(apply_payload)
            if inspect.isawaitable(result):
                result = await result
            assignment_result = (
                dict(result) if isinstance(result, dict) else {"success": False, "error": "apply_role returned an unexpected result"}
            )
            if not assignment_result.get("success"):
                return {
                    "success": False,
                    "error": str(assignment_result.get("error") or "remote skill trial assignment failed"),
                    "installed": True,
                    "name": getattr(installed, "name", ""),
                    "enabled": bool(getattr(installed, "enabled", True)),
                    "source_url": getattr(installed, "source_url", candidate.bundle_url),
                    "installed_capability_ids": installed_capability_ids,
                    "assignment_result": assignment_result,
                    "preflight": preflight.model_dump(mode="json"),
                }
        summary = (
            f"Installed remote skill '{getattr(installed, 'name', '')}'"
            + (
                f" and assigned it to '{target_agent_id}'."
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
            "assignment_result": assignment_result,
            "preflight": preflight.model_dump(mode="json"),
            "resolved_candidate": candidate.model_dump(mode="json"),
        }

    def set_agent_profile_service(self, agent_profile_service: object | None) -> None:
        self._agent_profile_service = agent_profile_service

    def set_apply_role_handler(self, apply_role_handler) -> None:
        self._apply_role_handler = apply_role_handler

    def _build_trial_apply_payload(
        self,
        *,
        target_agent_id: str,
        installed_capability_ids: list[str],
        replacement_capability_ids: list[str],
        capability_assignment_mode: str,
        reason: str,
    ) -> dict[str, object]:
        if capability_assignment_mode == "replace" and replacement_capability_ids:
            effective_capabilities = self._effective_capabilities_for_agent(target_agent_id)
            final_capabilities = [
                capability_id
                for capability_id in effective_capabilities
                if capability_id not in replacement_capability_ids
            ]
            for capability_id in installed_capability_ids:
                if capability_id not in final_capabilities:
                    final_capabilities.append(capability_id)
            return {
                "agent_id": target_agent_id,
                "capabilities": final_capabilities,
                "capability_assignment_mode": "replace",
                "reason": reason or f"Trial remote skill replacement for '{target_agent_id}'.",
            }
        return {
            "agent_id": target_agent_id,
            "capabilities": list(installed_capability_ids),
            "capability_assignment_mode": "merge",
            "reason": reason or f"Trial remote skill assignment for '{target_agent_id}'.",
        }

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
