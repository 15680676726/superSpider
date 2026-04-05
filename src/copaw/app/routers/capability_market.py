# -*- coding: utf-8 -*-
"""Canonical capability market product surface."""
from __future__ import annotations

import asyncio
import json
import inspect
import re
import subprocess
import sys
from typing import Any, Literal
from urllib.parse import urlparse
from urllib.request import Request as URLRequest, urlopen

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ...agents.skills_hub import search_hub_skills
from ...adapters.desktop import (
    DesktopMCPTemplate,
    get_desktop_mcp_template,
)
from ...capabilities import CapabilityMount, CapabilityService, CapabilitySummary
from ...capabilities.mcp_registry import (
    McpRegistryCatalog,
    McpRegistryCatalogDetailResponse,
    McpRegistryCatalogSearchResponse,
)
from ...capabilities.browser_runtime import (
    BrowserProfileRecord,
    BrowserRuntimeService,
    BrowserSessionStartOptions,
)
from ...capabilities.install_templates import (
    CapabilityInstallTemplateSpec,
    InstallTemplateDoctorReport,
    InstallTemplateExampleRunRecord,
    build_install_template_doctor,
    get_install_template,
    list_install_templates,
    match_install_template_capability_ids,
    normalize_install_template_config,
    run_install_template_example,
)
from ...capabilities.lifecycle_assignment import (
    build_capability_lifecycle_assignment_payload,
)
from ...capabilities.remote_skill_catalog import (
    CuratedSkillCatalogEntry,
    CuratedSkillCatalogSearchResponse,
    CuratedSkillCatalogSource,
    get_curated_skill_catalog_entry,
    list_curated_skill_sources,
    search_curated_skill_catalog,
)
from ...capabilities.remote_skill_contract import (
    remote_skill_bundle_is_installable,
)
from ...config import load_config, save_config
from ...config.config import ExternalCapabilityPackageConfig
from ...discovery.models import DiscoveryHit, NormalizedDiscoveryHit
from ...discovery.provider_search import search_github_repository_donors
from ...state import SQLiteStateStore
from ...state.skill_candidate_service import CapabilityCandidateService
from ...state.skill_trial_service import SkillTrialService
from .capabilities import CapabilityMutationRequest
from .capability_contracts import (
    CreateSkillRequest,
    HubInstallRequest,
    MCPClientCreateRequest,
    MCPClientInfo,
    MCPClientUpdateRequest,
    SkillSpec,
)
from .governed_mutations import (
    dispatch_governed_mutation,
    get_capability_service as _shared_get_capability_service,
)

router = APIRouter(prefix="/capability-market", tags=["capability-market"])


class HubSkillSpec(BaseModel):
    slug: str
    name: str
    description: str = ""
    version: str = ""
    source_url: str = ""
    source_label: str | None = None


class CapabilityMarketCuratedInstallRequest(BaseModel):
    source_id: str
    candidate_id: str
    review_acknowledged: bool = False
    enable: bool = True
    overwrite: bool = False
    actor: str = Field(default="copaw-operator")
    target_agent_ids: list[str] = Field(default_factory=list)
    capability_ids: list[str] = Field(default_factory=list)
    capability_assignment_mode: Literal["replace", "merge"] = "merge"


class CapabilityMarketCuratedInstallResponse(BaseModel):
    installed: bool
    name: str
    enabled: bool
    source_url: str
    source_id: str
    candidate_id: str
    review_summary: str = ""
    review_notes: list[str] = Field(default_factory=list)
    assigned_capability_ids: list[str] = Field(default_factory=list)
    assignment_results: list["CapabilityMarketCapabilityAssignmentResult"] = Field(
        default_factory=list,
    )


class CapabilityMarketCreateSkillRequest(CreateSkillRequest):
    actor: str = Field(default="copaw-operator")
    overwrite: bool = Field(default=False)


class CapabilityMarketHubInstallRequest(HubInstallRequest):
    actor: str = Field(default="copaw-operator")
    target_agent_ids: list[str] = Field(default_factory=list)
    capability_ids: list[str] = Field(default_factory=list)
    capability_assignment_mode: Literal["replace", "merge"] = "merge"


class CapabilityMarketHubInstallResponse(BaseModel):
    installed: bool
    name: str
    enabled: bool
    source_url: str
    assigned_capability_ids: list[str] = Field(default_factory=list)
    assignment_results: list["CapabilityMarketCapabilityAssignmentResult"] = Field(
        default_factory=list,
    )


class CapabilityMarketProjectInstallRequest(BaseModel):
    candidate_id: str | None = None
    source_url: str | None = None
    version: str = ""
    capability_kind: Literal["project-package", "adapter", "runtime-component"] = (
        "project-package"
    )
    entry_module: str | None = None
    execute_command: str | None = None
    healthcheck_command: str | None = None
    enable: bool = True
    overwrite: bool = False
    actor: str = Field(default="copaw-operator")
    target_agent_id: str | None = None
    selected_seat_ref: str | None = None
    target_role_id: str | None = None
    capability_ids: list[str] = Field(default_factory=list)
    replacement_capability_ids: list[str] = Field(default_factory=list)
    replacement_target_ids: list[str] = Field(default_factory=list)
    capability_assignment_mode: Literal["replace", "merge"] = "merge"
    trial_scope: Literal["single-agent", "single-seat", "wider-rollout"] = "single-seat"


class CapabilityMarketProjectInstallResponse(BaseModel):
    installed: bool
    candidate_id: str | None = None
    name: str
    enabled: bool
    source_url: str
    capability_kind: str = "project-package"
    installed_capability_ids: list[str] = Field(default_factory=list)
    target_agent_id: str | None = None
    trial_attachment: dict[str, Any] | None = None


class CapabilityMarketProjectCandidate(BaseModel):
    display_name: str
    summary: str = ""
    source_kind: str = "github-repo"
    candidate_kind: str = "project"
    source_url: str
    version: str = ""
    source_lineage: str | None = None
    canonical_package_id: str | None = None
    capability_keys: list[str] = Field(default_factory=list)
    install_supported: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    routes: dict[str, str] = Field(default_factory=dict)


class CapabilityMarketMCPCreateRequest(BaseModel):
    client_key: str
    client: MCPClientCreateRequest
    actor: str = Field(default="copaw-operator")


class CapabilityMarketMCPUpdateRequest(MCPClientUpdateRequest):
    actor: str = Field(default="copaw-operator")


class CapabilityMarketMCPRegistryInstallRequest(BaseModel):
    option_key: str
    client_key: str | None = None
    enabled: bool = True
    actor: str = Field(default="copaw-operator")
    target_agent_ids: list[str] = Field(default_factory=list)
    capability_ids: list[str] = Field(default_factory=list)
    capability_assignment_mode: Literal["replace", "merge"] = "merge"
    input_values: dict[str, Any] = Field(default_factory=dict)


class CapabilityMarketMCPRegistryInstallResponse(MCPClientInfo):
    install_status: Literal[
        "installed",
        "already-installed",
        "enabled-existing",
        "updated-existing",
    ] = "installed"
    server_name: str
    registry_version: str = ""
    assigned_capability_ids: list[str] = Field(default_factory=list)
    assignment_results: list["CapabilityMarketCapabilityAssignmentResult"] = Field(
        default_factory=list,
    )
    summary: str = ""


class CapabilityMarketMCPRegistryUpgradeRequest(BaseModel):
    enabled: bool | None = None
    actor: str = Field(default="copaw-operator")
    input_values: dict[str, Any] = Field(default_factory=dict)


class CapabilityMarketMCPRegistryUpgradeResponse(MCPClientInfo):
    upgraded: bool = False
    server_name: str = ""
    previous_version: str = ""
    registry_version: str = ""
    summary: str = ""


class CapabilityMarketInstallTemplateSpec(CapabilityInstallTemplateSpec):
    pass


class CapabilityMarketWorkflowResumeRequest(BaseModel):
    template_id: str
    industry_instance_id: str | None = None
    preset_id: str | None = None
    parameters: dict[str, object] = Field(default_factory=dict)
    resume_action: Literal["preview"] = "preview"


class CapabilityMarketWorkflowResumeSpec(CapabilityMarketWorkflowResumeRequest):
    return_path: str


class CapabilityMarketCapabilityAssignmentResult(BaseModel):
    agent_id: str
    capability_ids: list[str] = Field(default_factory=list)
    mode: Literal["replace", "merge"] = "merge"
    success: bool = True
    summary: str = ""
    routes: dict[str, str] = Field(default_factory=dict)


CapabilityMarketCuratedInstallResponse.model_rebuild()
CapabilityMarketHubInstallResponse.model_rebuild()
CapabilityMarketMCPRegistryInstallResponse.model_rebuild()


class CapabilityMarketMCPTemplateInstallRequest(BaseModel):
    client_key: str | None = Field(default=None)
    enabled: bool | None = Field(default=None)
    actor: str = Field(default="copaw-operator")
    target_agent_ids: list[str] = Field(default_factory=list)
    capability_ids: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    capability_assignment_mode: Literal["replace", "merge"] = "merge"
    workflow_resume: CapabilityMarketWorkflowResumeRequest | None = None


class CapabilityMarketMCPTemplateInstallResponse(MCPClientInfo):
    install_status: Literal[
        "installed",
        "already-installed",
        "enabled-existing",
    ] = "installed"
    assigned_capability_ids: list[str] = Field(default_factory=list)
    assignment_results: list[CapabilityMarketCapabilityAssignmentResult] = Field(
        default_factory=list,
    )
    workflow_resume: CapabilityMarketWorkflowResumeSpec | None = None


class CapabilityMarketInstallTemplateInstallRequest(BaseModel):
    enabled: bool | None = Field(default=None)
    actor: str = Field(default="copaw-operator")
    target_agent_ids: list[str] = Field(default_factory=list)
    capability_ids: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)
    capability_assignment_mode: Literal["replace", "merge"] = "merge"
    workflow_resume: CapabilityMarketWorkflowResumeRequest | None = None


class CapabilityMarketInstallTemplateExampleRunRequest(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)


class BrowserProfileUpsertRequest(BaseModel):
    profile_id: str | None = Field(default=None)
    label: str | None = Field(default=None)
    headed: bool | None = Field(default=None)
    reuse_running_session: bool | None = Field(default=None)
    persist_login_state: bool | None = Field(default=None)
    entry_url: str | None = Field(default=None)
    is_default: bool | None = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BrowserSessionStartRequest(BaseModel):
    session_id: str = Field(default="default")
    profile_id: str | None = Field(default=None)
    headed: bool | None = Field(default=None)
    entry_url: str | None = Field(default=None)
    reuse_running_session: bool | None = Field(default=None)
    persist_login_state: bool | None = Field(default=None)


class CapabilityMarketInstallTemplateInstallResponse(BaseModel):
    template_id: str
    install_status: Literal[
        "installed",
        "already-installed",
        "enabled-existing",
    ] = "installed"
    source_kind: str
    target_ref: str | None = None
    enabled: bool | None = None
    ready: bool = False
    assigned_capability_ids: list[str] = Field(default_factory=list)
    assignment_results: list[CapabilityMarketCapabilityAssignmentResult] = Field(
        default_factory=list,
    )
    workflow_resume: CapabilityMarketWorkflowResumeSpec | None = None
    summary: str = ""
    routes: dict[str, str] = Field(default_factory=dict)


def _get_capability_service(request: Request) -> CapabilityService:
    return _shared_get_capability_service(request)


def _get_capability_candidate_service(
    request: Request,
) -> CapabilityCandidateService | None:
    service = getattr(request.app.state, "capability_candidate_service", None)
    if isinstance(service, CapabilityCandidateService):
        return service
    state_store = getattr(request.app.state, "state_store", None)
    if not isinstance(state_store, SQLiteStateStore):
        return None
    service = CapabilityCandidateService(
        state_store=state_store,
        donor_service=getattr(request.app.state, "capability_donor_service", None),
    )
    request.app.state.capability_candidate_service = service
    return service


def _get_skill_trial_service(request: Request) -> SkillTrialService | None:
    service = getattr(request.app.state, "skill_trial_service", None)
    if isinstance(service, SkillTrialService):
        return service
    state_store = getattr(request.app.state, "state_store", None)
    if not isinstance(state_store, SQLiteStateStore):
        return None
    service = SkillTrialService(state_store=state_store)
    request.app.state.skill_trial_service = service
    return service


def _get_agent_profile_service(request: Request):
    return getattr(request.app.state, "agent_profile_service", None)


def _get_decision_request_repository(request: Request):
    return getattr(request.app.state, "decision_request_repository", None)


def _get_mcp_registry_catalog(request: Request) -> McpRegistryCatalog:
    catalog = getattr(request.app.state, "mcp_registry_catalog", None)
    if catalog is not None and all(
        callable(getattr(catalog, attr, None))
        for attr in ("list_catalog", "get_catalog_detail", "materialize_install_plan")
    ):
        return catalog
    catalog = McpRegistryCatalog()
    request.app.state.mcp_registry_catalog = catalog
    return catalog


def _load_market_mcp_clients() -> dict[str, Any]:
    return dict(load_config().mcp.clients or {})


def _get_browser_runtime_service(
    request: Request,
    *,
    required: bool = False,
) -> BrowserRuntimeService | None:
    environment_service = _get_environment_service(request, required=False)
    service = getattr(request.app.state, "browser_runtime_service", None)
    if isinstance(service, BrowserRuntimeService):
        _bind_browser_companion_runtime(
            service,
            environment_service=environment_service,
        )
        return service
    state_store = getattr(request.app.state, "state_store", None)
    if isinstance(state_store, SQLiteStateStore):
        service = BrowserRuntimeService(
            state_store,
            browser_companion_runtime=_browser_companion_runtime_adapter(
                environment_service=environment_service,
            ),
        )
        request.app.state.browser_runtime_service = service
        return service
    if required:
        raise HTTPException(503, detail="Browser runtime service is not available")
    return None


def _get_environment_service(
    request: Request,
    *,
    required: bool = False,
) -> object | None:
    service = getattr(request.app.state, "environment_service", None)
    if service is not None:
        return service
    if required:
        raise HTTPException(503, detail="Environment service is not available")
    return None


class _EnvironmentServiceBrowserCompanionAdapter:
    def __init__(self, environment_service: object) -> None:
        self._environment_service = environment_service

    def register_companion(self, **kwargs) -> dict[str, Any]:
        return self._environment_service.register_browser_companion(**kwargs)

    def clear_companion(self, **kwargs) -> dict[str, Any]:
        return self._environment_service.clear_browser_companion(**kwargs)

    def snapshot(self, **kwargs) -> dict[str, Any]:
        return self._environment_service.browser_companion_snapshot(**kwargs)


def _browser_companion_runtime_adapter(
    *,
    environment_service: object | None,
) -> _EnvironmentServiceBrowserCompanionAdapter | None:
    if environment_service is None:
        return None
    register = getattr(environment_service, "register_browser_companion", None)
    clear = getattr(environment_service, "clear_browser_companion", None)
    snapshot = getattr(environment_service, "browser_companion_snapshot", None)
    if not callable(register) or not callable(clear) or not callable(snapshot):
        return None
    return _EnvironmentServiceBrowserCompanionAdapter(environment_service)


def _bind_browser_companion_runtime(
    service: BrowserRuntimeService,
    *,
    environment_service: object | None,
) -> BrowserRuntimeService:
    companion_runtime = _browser_companion_runtime_adapter(
        environment_service=environment_service,
    )
    setattr(service, "_browser_companion_runtime", companion_runtime)
    return service


def _call_install_template_surface(
    surface: object,
    *args,
    environment_service: object | None = None,
    **kwargs,
):
    if environment_service is not None:
        try:
            signature = inspect.signature(surface)
        except (TypeError, ValueError):
            signature = None
        if signature is not None and "environment_service" in signature.parameters:
            kwargs.setdefault("environment_service", environment_service)
    return surface(*args, **kwargs)


def _normalize_agent_ids(values: list[str]) -> list[str]:
    return [
        agent_id
        for agent_id in dict.fromkeys(str(item).strip() for item in values if str(item).strip())
    ]


def _normalize_capability_ids(values: list[str]) -> list[str]:
    return [
        capability_id
        for capability_id in dict.fromkeys(
            str(item).strip() for item in values if str(item).strip()
        )
    ]


def _market_error_status(detail: str) -> int:
    lower = detail.lower()
    if "not found" in lower:
        return 404
    if (
        "rate limit" in lower
        or "httperror" in lower
        or "urlerror" in lower
        or "timeout" in lower
        or "timed out" in lower
        or "upstream" in lower
    ):
        return 502
    return 400


def _unwrap_market_mutation_result(result: dict[str, Any]) -> dict[str, Any]:
    output = result.get("output")
    if not isinstance(output, dict):
        return dict(result)
    flattened = dict(result)
    flattened.update(output)
    return flattened


def _extract_installed_skill_name(summary: str | None) -> str:
    if not isinstance(summary, str):
        return ""
    prefix = "Installed skill '"
    suffix = "' from hub."
    if summary.startswith(prefix) and summary.endswith(suffix):
        return summary[len(prefix) : -len(suffix)]
    return ""


def _normalize_project_install_name(
    *,
    source_url: str,
    proposed_name: str | None,
) -> str:
    candidate = str(proposed_name or "").strip()
    if not candidate:
        path = urlparse(source_url).path.strip("/")
        candidate = path.split("/")[-1] if path else ""
    candidate = re.sub(r"[^a-zA-Z0-9_-]+", "_", candidate).strip("_")
    return candidate or "github_project_donor"


def _normalize_external_capability_kind(
    value: object | None,
) -> Literal["project-package", "adapter", "runtime-component"]:
    normalized = str(value or "").strip().lower()
    if normalized in {"project-package", "adapter", "runtime-component"}:
        return normalized  # type: ignore[return-value]
    return "project-package"


def _external_capability_prefix(
    capability_kind: Literal["project-package", "adapter", "runtime-component"],
) -> str:
    return {
        "project-package": "project",
        "adapter": "adapter",
        "runtime-component": "runtime",
    }[capability_kind]


def _external_source_kind(
    capability_kind: Literal["project-package", "adapter", "runtime-component"],
) -> Literal["project", "adapter", "runtime"]:
    return {
        "project-package": "project",
        "adapter": "adapter",
        "runtime-component": "runtime",
    }[capability_kind]


def _normalize_entry_module(value: object | None, *, fallback_name: str) -> str:
    candidate = str(value or "").strip()
    if not candidate:
        candidate = fallback_name
    candidate = candidate.replace("-", "_").strip("_")
    return candidate or "external_capability"


def _build_external_capability_id(
    capability_kind: Literal["project-package", "adapter", "runtime-component"],
    *,
    install_name: str,
) -> str:
    return f"{_external_capability_prefix(capability_kind)}:{install_name}"


def _normalize_github_project_source_url(source_url: str) -> str:
    normalized = str(source_url or "").strip().rstrip("/")
    parsed = urlparse(normalized)
    host = (parsed.netloc or "").strip().lower()
    if parsed.scheme not in {"http", "https"} or host not in {
        "github.com",
        "www.github.com",
    }:
        raise HTTPException(
            400,
            detail="Project donor currently supports GitHub repository URLs only",
        )
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise HTTPException(
            400,
            detail="Project donor source_url must point to a GitHub owner/repository",
        )
    return f"https://github.com/{parts[0]}/{parts[1]}"


def _github_owner_repo(source_url: str) -> tuple[str, str]:
    parsed = urlparse(source_url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise HTTPException(
            400,
            detail="Project donor source_url must point to a GitHub owner/repository",
        )
    return parts[0], parts[1]


def _resolve_github_default_ref(source_url: str) -> str:
    owner, repo = _github_owner_repo(source_url)
    request = URLRequest(
        f"https://api.github.com/repos/{owner}/{repo}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "copaw-donor-discovery/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=20.0) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    default_branch = str(payload.get("default_branch") or "").strip()
    return default_branch or "main"


def _build_github_archive_package_ref(source_url: str, *, version: str) -> str:
    owner, repo = _github_owner_repo(source_url)
    normalized_version = str(version or "").strip() or _resolve_github_default_ref(
        source_url,
    )
    return f"https://github.com/{owner}/{repo}/archive/refs/heads/{normalized_version}.zip"


def _default_external_execute_command(
    capability_kind: Literal["project-package", "adapter", "runtime-component"],
    *,
    entry_module: str,
) -> str:
    python_exe = sys.executable
    if capability_kind == "adapter":
        return (
            f'"{python_exe}" -c "import {entry_module}; '
            f"print(getattr({entry_module}, '__name__', '{entry_module}'))\""
        )
    if capability_kind == "runtime-component":
        return f'"{python_exe}" -m {entry_module} --help'
    return f'"{python_exe}" -m {entry_module} --version'


def _default_environment_requirements(
    capability_kind: Literal["project-package", "adapter", "runtime-component"],
) -> list[str]:
    if capability_kind == "adapter":
        return ["desktop", "process"]
    if capability_kind == "runtime-component":
        return ["process", "network"]
    return ["workspace", "process"]


def _default_evidence_contract(
    capability_kind: Literal["project-package", "adapter", "runtime-component"],
) -> list[str]:
    if capability_kind == "adapter":
        return ["shell-command", "runtime-event", "environment-session"]
    if capability_kind == "runtime-component":
        return ["shell-command", "runtime-event"]
    return ["shell-command", "call-record"]


async def _run_external_project_process(
    command_parts: list[str],
    *,
    timeout: int,
) -> tuple[bool, str]:
    def _run() -> tuple[bool, str]:
        try:
            completed = subprocess.run(
                command_parts,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        output = (completed.stdout or "").strip()
        error_output = (completed.stderr or "").strip()
        summary = (
            output
            or error_output
            or f"Process exited with code {completed.returncode}"
        )
        return completed.returncode == 0, summary

    return await asyncio.to_thread(_run)


async def _install_external_project_capability(
    *,
    source_url: str,
    version: str,
    capability_kind: Literal["project-package", "adapter", "runtime-component"],
    entry_module: str | None,
    execute_command: str | None,
    healthcheck_command: str | None,
    enable: bool,
    overwrite: bool,
) -> dict[str, object]:
    normalized_source_url = _normalize_github_project_source_url(source_url)
    install_name = _normalize_project_install_name(
        source_url=normalized_source_url,
        proposed_name=None,
    )
    normalized_entry_module = _normalize_entry_module(
        entry_module,
        fallback_name=install_name,
    )
    capability_id = _build_external_capability_id(
        capability_kind,
        install_name=install_name,
    )
    package_ref = _build_github_archive_package_ref(
        normalized_source_url,
        version=version,
    )
    config = load_config()
    packages = dict(getattr(config, "external_capability_packages", {}) or {})
    if capability_id in packages and not overwrite:
        raise HTTPException(
            409,
            detail=(
                f"External capability '{capability_id}' already exists. "
                "Use overwrite=true to replace it."
            ),
        )
    install_command_parts = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--user",
        "--disable-pip-version-check",
    ]
    if overwrite:
        install_command_parts.extend(["--upgrade", "--force-reinstall"])
    install_command_parts.append(package_ref)
    success, summary = await _run_external_project_process(
        install_command_parts,
        timeout=600,
    )
    if not success:
        raise HTTPException(
            400,
            detail=f"External project install failed: {summary}",
        )
    resolved_execute_command = str(execute_command or "").strip() or _default_external_execute_command(
        capability_kind,
        entry_module=normalized_entry_module,
    )
    resolved_healthcheck_command = (
        str(healthcheck_command or "").strip() or resolved_execute_command
    )
    if resolved_healthcheck_command:
        verify_success, verify_summary = await _run_external_project_process(
            (
                [sys.executable, "-m", normalized_entry_module, "--version"]
                if capability_kind == "project-package"
                else (
                    [sys.executable, "-m", normalized_entry_module, "--help"]
                    if capability_kind == "runtime-component"
                    else [
                        sys.executable,
                        "-c",
                        f"import {normalized_entry_module}; print('ok')",
                    ]
                )
            ),
            timeout=180,
        )
        if not verify_success:
            raise HTTPException(
                400,
                detail=f"External project verification failed: {verify_summary}",
            )
    packages[capability_id] = ExternalCapabilityPackageConfig(
        capability_id=capability_id,
        name=install_name,
        summary=f"External open-source donor from {normalized_source_url}",
        enabled=enable,
        kind=capability_kind,
        source_kind=_external_source_kind(capability_kind),
        source_url=normalized_source_url,
        package_ref=package_ref,
        package_kind="github-archive",
        package_version=version,
        execution_mode="shell",
        install_command=subprocess.list2cmdline(install_command_parts),
        execute_command=resolved_execute_command,
        healthcheck_command=resolved_healthcheck_command,
        environment_requirements=_default_environment_requirements(capability_kind),
        evidence_contract=_default_evidence_contract(capability_kind),
        provider_ref="github",
        metadata={
            "entry_module": normalized_entry_module,
            "provider": "github-repo",
            "open_source_project": True,
        },
    )
    config.external_capability_packages = packages
    save_config(config)
    return {
        "installed": True,
        "name": install_name,
        "enabled": enable,
        "source_url": normalized_source_url,
        "installed_capability_ids": [capability_id],
        "capability_kind": capability_kind,
        "execution_mode": "shell",
        "summary": summary,
    }


def _project_target_scope(
    *,
    trial_scope: str,
    selected_seat_ref: str | None,
    target_role_id: str | None,
) -> str:
    if str(selected_seat_ref or "").strip():
        return "seat"
    if str(trial_scope or "").strip().lower() == "wider-rollout":
        return "role" if str(target_role_id or "").strip() else "agent"
    if str(target_role_id or "").strip():
        return "role"
    return "agent"


def _resolve_project_candidate(
    request: Request,
    *,
    candidate_id: str | None,
    source_url: str | None,
    version: str | None,
):
    candidate_service = _get_capability_candidate_service(request)
    candidate = None
    if isinstance(candidate_id, str) and candidate_id.strip():
        if candidate_service is None:
            raise HTTPException(503, detail="Capability candidate service is not available")
        candidate = candidate_service.get_candidate(candidate_id.strip())
        if candidate is None:
            raise HTTPException(404, detail=f"Capability candidate '{candidate_id}' not found")
        if str(candidate.candidate_kind or "").strip().lower() not in {
            "project",
            "project-package",
            "adapter",
            "runtime-component",
        }:
            raise HTTPException(400, detail="Capability candidate is not a project donor")
    resolved_source_url = str(source_url or "").strip()
    if not resolved_source_url and candidate is not None:
        metadata = getattr(candidate, "metadata", None)
        metadata_payload = metadata if isinstance(metadata, dict) else {}
        raw_source_refs = metadata_payload.get("raw_source_refs")
        candidate_source_options: list[str] = [
            str(getattr(candidate, "candidate_source_ref", "") or "").strip(),
            str(metadata_payload.get("repository_url") or "").strip(),
            str(metadata_payload.get("source_url") or "").strip(),
        ]
        if isinstance(raw_source_refs, (list, tuple)):
            candidate_source_options.extend(
                str(item).strip() for item in raw_source_refs if str(item).strip()
            )
        for candidate_source in candidate_source_options:
            if not candidate_source:
                continue
            try:
                resolved_source_url = _normalize_github_project_source_url(
                    candidate_source,
                )
                break
            except HTTPException:
                continue
    resolved_version = str(version or "").strip() or str(
        getattr(candidate, "candidate_source_version", "") or ""
    ).strip()
    if not resolved_source_url:
        raise HTTPException(400, detail="Project donor source_url is required")
    return candidate, _normalize_github_project_source_url(resolved_source_url), resolved_version


def _materialize_project_candidate(
    request: Request,
    *,
    candidate: object | None,
    source_url: str,
    target_role_id: str | None,
    target_seat_ref: str | None,
    trial_scope: str,
    candidate_kind: str = "project",
):
    if candidate is not None:
        return candidate
    candidate_service = _get_capability_candidate_service(request)
    if candidate_service is None:
        return None
    discovery_hits = search_github_repository_donors(source_url, limit=1)
    hit = next(
        (
            item
            for item in discovery_hits
            if str(item.candidate_source_ref or "").strip() == source_url
        ),
        None,
    )
    if hit is None:
        lineage = source_url.rstrip("/").lower()
        hit = DiscoveryHit(
            source_id="github-repo",
            source_kind="github-repo",
            source_alias="github",
            candidate_kind=candidate_kind,
            display_name=source_url,
            summary="GitHub donor repository",
            candidate_source_ref=source_url,
            candidate_source_lineage=f"donor:github:{lineage}",
            canonical_package_id=f"pkg:github:{lineage}",
            metadata={
                "provider": "github-repo",
                "install_supported": True,
                "repository_url": source_url,
                "direct_query": True,
            },
        )
    normalized_hit = NormalizedDiscoveryHit(
        candidate_kind=str(hit.candidate_kind or candidate_kind),
        candidate_source_kind="external_remote",
        display_name=hit.display_name,
        summary=hit.summary,
        candidate_source_ref=hit.candidate_source_ref,
        candidate_source_version=hit.candidate_source_version,
        candidate_source_lineage=hit.candidate_source_lineage,
        canonical_package_id=hit.canonical_package_id,
        equivalence_class=(
            str(hit.canonical_package_id or "").strip()
            or str(hit.candidate_source_ref or "").strip()
            or source_url
        ),
        source_aliases=tuple(
            item
            for item in [str(hit.candidate_source_ref or "").strip()]
            if item
        ),
        source_ids=tuple(
            item
            for item in [str(hit.source_id or "").strip()]
            if item
        ),
        capability_keys=tuple(
            str(item).strip()
            for item in hit.capability_keys
            if str(item).strip()
        ),
        metadata=dict(hit.metadata),
    )
    imported = candidate_service.import_normalized_discovery_hits(
        normalized_hits=[normalized_hit],
        target_scope=_project_target_scope(
            trial_scope=trial_scope,
            selected_seat_ref=target_seat_ref,
            target_role_id=target_role_id,
        ),
        target_role_id=str(target_role_id or "").strip() or None,
        target_seat_ref=str(target_seat_ref or "").strip() or None,
    )
    return imported[0] if imported else None


def _build_project_remote_candidate_payload(
    *,
    candidate: object | None,
    source_url: str,
    version: str,
    capability_ids: list[str],
) -> dict[str, object]:
    install_name = _normalize_project_install_name(
        source_url=source_url,
        proposed_name=getattr(candidate, "proposed_skill_name", None),
    )
    resolved_capability_ids = _normalize_capability_ids(capability_ids)
    if not resolved_capability_ids:
        resolved_capability_ids = [f"skill:{install_name}"]
    return {
        "candidate_key": str(getattr(candidate, "candidate_id", "") or source_url),
        "source_kind": "github",
        "source_label": "GitHub",
        "title": str(getattr(candidate, "proposed_skill_name", "") or source_url),
        "description": str(getattr(candidate, "summary", "") or ""),
        "bundle_url": source_url,
        "source_url": source_url,
        "version": version,
        "install_name": install_name,
        "capability_ids": resolved_capability_ids,
        "capability_tags": ["project", "github", "remote"],
        "review_required": False,
    }


def _sync_project_trial_truth(
    request: Request,
    *,
    candidate_id: str | None,
    target_agent_id: str | None,
    result: dict[str, object],
) -> None:
    normalized_candidate_id = str(candidate_id or "").strip()
    if not normalized_candidate_id:
        return
    trial_attachment = result.get("trial_attachment")
    if not isinstance(trial_attachment, dict) or not trial_attachment.get("success"):
        return
    candidate_service = _get_capability_candidate_service(request)
    trial_service = _get_skill_trial_service(request)
    if candidate_service is None or trial_service is None:
        return
    candidate = candidate_service.get_candidate(normalized_candidate_id)
    if candidate is None:
        return
    selected_scope = str(
        trial_attachment.get("selected_scope") or getattr(candidate, "target_scope", "seat")
    ).strip() or "seat"
    scope_type = str(
        trial_attachment.get("scope_type") or selected_scope
    ).strip() or "seat"
    scope_ref = str(
        trial_attachment.get("scope_ref") or getattr(candidate, "target_seat_ref", "") or normalized_candidate_id
    ).strip()
    installed_capability_ids = [
        str(item).strip()
        for item in list(result.get("installed_capability_ids") or [])
        if str(item).strip()
    ]
    candidate_service.update_candidate_status(
        normalized_candidate_id,
        status="trial",
        lifecycle_stage="trial",
        metadata_updates={
            "resolution_kind": "adopt_external_donor",
            "selected_scope": selected_scope,
            "installed_capability_ids": installed_capability_ids,
            "target_agent_id": str(target_agent_id or "").strip() or None,
        },
    )
    trial_service.create_or_update_trial(
        candidate_id=normalized_candidate_id,
        donor_id=candidate.donor_id,
        package_id=candidate.package_id,
        source_profile_id=candidate.source_profile_id,
        canonical_package_id=candidate.canonical_package_id,
        candidate_source_lineage=candidate.candidate_source_lineage,
        source_aliases=list(candidate.source_aliases),
        equivalence_class=candidate.equivalence_class,
        capability_overlap_score=candidate.capability_overlap_score,
        replacement_relation=candidate.replacement_relation,
        scope_type=scope_type,
        scope_ref=scope_ref,
        verdict="pending",
        summary="Project donor attached to scoped trial and awaiting runtime evidence.",
        metadata={
            "target_agent_id": str(target_agent_id or "").strip() or None,
            "selected_scope": selected_scope,
            "installed_capability_ids": installed_capability_ids,
        },
    )


def _response_workflow_resume(
    workflow_resume: CapabilityMarketWorkflowResumeRequest | None,
) -> CapabilityMarketWorkflowResumeSpec | None:
    if workflow_resume is None:
        return None
    return CapabilityMarketWorkflowResumeSpec(
        **workflow_resume.model_dump(mode="json"),
        return_path=(
            "/runtime-center"
            f"?tab=automation&template={workflow_resume.template_id}"
        ),
    )


def _ensure_target_agents_exist(
    request: Request,
    *,
    target_agent_ids: list[str],
) -> None:
    if not target_agent_ids:
        return
    profile_service = _get_agent_profile_service(request)
    if profile_service is None:
        raise HTTPException(503, detail="Agent profile service is not available")
    get_agent = getattr(profile_service, "get_agent", None)
    missing_agents = [
        agent_id
        for agent_id in target_agent_ids
        if not callable(get_agent) or get_agent(agent_id) is None
    ]
    if missing_agents:
        raise HTTPException(
            404,
            detail="Target agents not found: " + ", ".join(sorted(missing_agents)),
        )


async def _assign_capabilities_to_agents(
    request: Request,
    *,
    template_id: str,
    actor: str,
    target_agent_ids: list[str],
    capability_ids: list[str],
    capability_assignment_mode: Literal["replace", "merge"],
) -> list[CapabilityMarketCapabilityAssignmentResult]:
    _ensure_target_agents_exist(request, target_agent_ids=target_agent_ids)
    agent_profile_service = _get_agent_profile_service(request)
    assignment_results: list[CapabilityMarketCapabilityAssignmentResult] = []
    for agent_id in target_agent_ids:
        lifecycle_payload = build_capability_lifecycle_assignment_payload(
            agent_profile_service=agent_profile_service,
            target_agent_id=agent_id,
            capability_ids=capability_ids,
            capability_assignment_mode=capability_assignment_mode,
            reason=(
                f"Capability market install template '{template_id}' "
                f"assigned capabilities to '{agent_id}'."
            ),
            actor=actor,
        )
        result = await _dispatch_market_mutation(
            request,
            capability_ref="system:apply_capability_lifecycle",
            title=f"Assign template {template_id} capabilities to {agent_id}",
            payload=lifecycle_payload,
            fallback_risk="guarded",
        )
        if not result.get("success"):
            detail = str(result.get("error") or "Capability assignment failed")
            raise HTTPException(_market_error_status(detail), detail=detail)
        assignment_results.append(
            CapabilityMarketCapabilityAssignmentResult(
                agent_id=agent_id,
                capability_ids=list(capability_ids),
                mode=capability_assignment_mode,
                success=True,
                summary=str(result.get("summary") or "").strip(),
                routes={
                    "agent": f"/api/runtime-center/agents/{agent_id}",
                    "capabilities": f"/api/runtime-center/agents/{agent_id}/capabilities",
                    "governed_capabilities": (
                        f"/api/runtime-center/agents/{agent_id}/capabilities/governed"
                    ),
                },
            ),
        )
    return assignment_results


def _resolve_remote_skill_capability_ids(
    request: Request,
    *,
    capability_ids: list[str],
    installed_name: str,
    target_agent_ids: list[str],
) -> list[str]:
    normalized = _normalize_capability_ids(capability_ids)
    if not normalized and installed_name:
        normalized = [f"skill:{installed_name}"]
    if target_agent_ids and not normalized:
        raise HTTPException(
            400,
            detail=(
                "Installed remote skill did not expose any capability ids for "
                "post-install assignment."
            ),
        )
    if not normalized:
        return []
    service = _get_capability_service(request)
    missing_capability_ids = [
        capability_id
        for capability_id in normalized
        if service.get_capability(capability_id) is None
    ]
    if missing_capability_ids:
        raise HTTPException(
            400,
            detail=(
                "Capability ids are not available after remote skill install: "
                + ", ".join(sorted(missing_capability_ids))
            ),
        )
    return normalized


async def _dispatch_market_mutation(
    request: Request,
    *,
    capability_ref: str,
    title: str,
    payload: dict[str, object],
    fallback_risk: str,
) -> dict[str, object]:
    return await dispatch_governed_mutation(
        request,
        capability_ref=capability_ref,
        title=title,
        payload=payload,
        environment_ref="config:capabilities",
        fallback_risk=fallback_risk,
    )


def _mcp_info_or_500(
    service: CapabilityService,
    *,
    client_key: str,
) -> MCPClientInfo:
    client_info = service.get_mcp_client_info(client_key)
    if client_info is None:
        raise HTTPException(
            500,
            detail=(
                f"MCP client '{client_key}' changed successfully but is not "
                "visible in the capability market surface"
            ),
        )
    return MCPClientInfo(**client_info)


async def _materialize_registry_mcp_install(
    request: Request,
    *,
    server_name: str,
    payload: CapabilityMarketMCPRegistryInstallRequest,
) -> CapabilityMarketMCPRegistryInstallResponse:
    catalog = _get_mcp_registry_catalog(request)
    installed_clients = _load_market_mcp_clients()
    existing_client = installed_clients.get(payload.client_key or "")
    try:
        plan = catalog.materialize_install_plan(
            server_name,
            option_key=payload.option_key,
            input_values=payload.input_values,
            client_key=payload.client_key,
            enabled=payload.enabled,
            existing_client=existing_client,
        )
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc

    service = _get_capability_service(request)
    target_agent_ids = _normalize_agent_ids(payload.target_agent_ids)
    assigned_capability_ids = _normalize_capability_ids(payload.capability_ids)
    if not assigned_capability_ids:
        assigned_capability_ids = [f"mcp:{plan.client_key}"]

    existing_visible = service.get_mcp_client_info(plan.client_key)
    install_status: Literal[
        "installed",
        "already-installed",
        "enabled-existing",
        "updated-existing",
    ] = "installed"
    capability_ref = "system:create_mcp_client"
    title = f"Install registry MCP {server_name} as {plan.client_key}"
    mutation_payload: dict[str, object] = {
        "client_key": plan.client_key,
        "client": plan.client.model_dump(mode="json"),
        "actor": payload.actor,
    }
    if existing_visible is not None:
        capability_ref = "system:update_mcp_client"
        title = f"Update registry MCP {server_name} as {plan.client_key}"
        install_status = "updated-existing"
        if not bool(existing_visible.get("enabled")) and payload.enabled:
            install_status = "enabled-existing"
        existing_registry = existing_visible.get("registry")
        if (
            isinstance(existing_registry, dict)
            and existing_registry.get("version")
            == plan.registry.version
            and bool(existing_visible.get("enabled")) == payload.enabled
        ):
            install_status = "already-installed"

    result = await _dispatch_market_mutation(
        request,
        capability_ref=capability_ref,
        title=title,
        payload=mutation_payload,
        fallback_risk="guarded",
    )
    if not result.get("success"):
        detail = str(result.get("error") or "Registry MCP install failed")
        raise HTTPException(_market_error_status(detail), detail=detail)

    invalid_capability_ids = [
        capability_id
        for capability_id in assigned_capability_ids
        if service.get_capability(capability_id) is None
    ]
    if invalid_capability_ids:
        raise HTTPException(
            400,
            detail=(
                "Capability ids are not available after MCP install: "
                + ", ".join(sorted(invalid_capability_ids))
            ),
        )

    assignment_results = await _assign_capabilities_to_agents(
        request,
        template_id=f"mcp-registry:{server_name}",
        actor=payload.actor,
        target_agent_ids=target_agent_ids,
        capability_ids=assigned_capability_ids,
        capability_assignment_mode=payload.capability_assignment_mode,
    )
    client_info = _mcp_info_or_500(service, client_key=plan.client_key)
    return CapabilityMarketMCPRegistryInstallResponse(
        **client_info.model_dump(mode="json"),
        install_status=install_status,
        server_name=server_name,
        registry_version=plan.registry.version,
        assigned_capability_ids=assigned_capability_ids,
        assignment_results=assignment_results,
        summary=plan.summary,
    )


async def _upgrade_registry_mcp_client(
    request: Request,
    *,
    client_key: str,
    payload: CapabilityMarketMCPRegistryUpgradeRequest,
) -> CapabilityMarketMCPRegistryUpgradeResponse:
    installed_clients = _load_market_mcp_clients()
    existing_client = installed_clients.get(client_key)
    if existing_client is None:
        raise HTTPException(404, detail=f"MCP client '{client_key}' not found")
    if existing_client.registry is None or not existing_client.registry.server_name:
        raise HTTPException(
            400,
            detail="This MCP client was not installed from the official MCP registry",
        )
    catalog = _get_mcp_registry_catalog(request)
    input_values = (
        payload.input_values
        if payload.input_values
        else dict(existing_client.registry.input_values or {})
    )
    try:
        plan = catalog.materialize_install_plan(
            existing_client.registry.server_name,
            option_key=existing_client.registry.option_key,
            input_values=input_values,
            client_key=client_key,
            enabled=existing_client.enabled if payload.enabled is None else payload.enabled,
            existing_client=existing_client,
        )
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc

    result = await _dispatch_market_mutation(
        request,
        capability_ref="system:update_mcp_client",
        title=f"Upgrade registry MCP {client_key}",
        payload={
            "client_key": client_key,
            "client": plan.client.model_dump(mode="json"),
            "actor": payload.actor,
        },
        fallback_risk="guarded",
    )
    if not result.get("success"):
        detail = str(result.get("error") or "Registry MCP upgrade failed")
        raise HTTPException(_market_error_status(detail), detail=detail)

    service = _get_capability_service(request)
    client_info = _mcp_info_or_500(service, client_key=client_key)
    previous_version = (
        existing_client.registry.version
        if existing_client.registry is not None
        else ""
    )
    return CapabilityMarketMCPRegistryUpgradeResponse(
        **client_info.model_dump(mode="json"),
        upgraded=bool(previous_version and previous_version != plan.registry.version),
        server_name=plan.registry.server_name,
        previous_version=previous_version,
        registry_version=plan.registry.version,
        summary=plan.summary,
    )


def _template_to_install_template_response(
    template: DesktopMCPTemplate,
    *,
    installed_clients: dict[str, bool],
) -> CapabilityMarketInstallTemplateSpec:
    enabled = installed_clients.get(template.default_client_key)
    installed = enabled is not None
    return CapabilityMarketInstallTemplateSpec(
        id=template.template_id,
        name=template.name,
        description=template.description,
        platform=template.platform,
        default_client_key=template.default_client_key,
        capability_tags=list(template.capability_tags),
        notes=list(template.notes),
        risk_level="guarded",
        capability_budget_cost=1,
        default_assignment_policy="selected-agents-only",
        installed=installed,
        enabled=enabled,
        ready=bool(enabled),
        routes={
            "detail": f"/api/capability-market/install-templates/{template.template_id}",
            "install": f"/api/capability-market/install-templates/{template.template_id}/install",
        },
    )


@router.get("/overview", response_model=dict[str, object])
async def get_capability_market_overview(request: Request) -> dict[str, object]:
    service = _get_capability_service(request)
    capabilities, summary = service.list_public_capability_inventory()
    state_query_service = getattr(request.app.state, "state_query_service", None)
    query_candidates = getattr(state_query_service, "list_capability_candidates", None)
    candidate_service = getattr(request.app.state, "capability_candidate_service", None)
    list_candidates = getattr(candidate_service, "list_candidates", None)
    summarize_candidates = getattr(candidate_service, "summarize_candidates", None)
    capability_candidates = []
    if callable(query_candidates):
        payload = query_candidates(limit=12)
        if isinstance(payload, list):
            capability_candidates = [dict(item) for item in payload if isinstance(item, dict)]
    if not capability_candidates and callable(list_candidates):
        capability_candidates = [item.model_dump(mode="json") for item in list_candidates(limit=12)]
    candidate_summary = (
        dict(summarize_candidates())
        if callable(summarize_candidates)
        else {"total": 0, "by_kind": {}, "by_source_kind": {}, "by_status": {}}
    )
    return {
        "summary": summary.model_dump(mode="json"),
        "installed": [mount.model_dump(mode="json") for mount in capabilities],
        "skills": service.list_skill_specs(),
        "available_skills": service.list_available_skill_specs(),
        "mcp_clients": service.list_mcp_client_infos(),
        "candidate_summary": candidate_summary,
        "capability_candidates": capability_candidates,
        "routes": {
            "capabilities": "/api/capability-market/capabilities",
            "capability_summary": "/api/capability-market/capabilities/summary",
            "skills": "/api/capability-market/skills",
            "mcp": "/api/capability-market/mcp",
            "mcp_catalog": "/api/capability-market/mcp/catalog",
            "install_templates": "/api/capability-market/install-templates",
            "curated_sources": "/api/capability-market/curated-sources",
            "curated_catalog": "/api/capability-market/curated-catalog",
            "curated_install": "/api/capability-market/curated-catalog/install",
            "hub_search": "/api/capability-market/hub/search",
            "hub_install": "/api/capability-market/hub/install",
            "project_search": "/api/capability-market/projects/search",
            "project_install": "/api/capability-market/projects/install",
            "candidate_list": "/api/runtime-center/capabilities/candidates",
        },
    }


@router.get("/capabilities", response_model=list[CapabilityMount])
async def list_market_capabilities(
    request: Request,
    kind: str | None = Query(default=None),
    enabled_only: bool = Query(default=False),
) -> list[CapabilityMount]:
    service = _get_capability_service(request)
    return service.list_public_capabilities(kind=kind, enabled_only=enabled_only)


@router.get("/capabilities/summary", response_model=CapabilitySummary)
async def get_market_capability_summary(request: Request) -> CapabilitySummary:
    service = _get_capability_service(request)
    return service.summarize_public()


@router.get("/skills", response_model=list[SkillSpec])
async def list_market_skills(request: Request) -> list[SkillSpec]:
    service = _get_capability_service(request)
    return [SkillSpec(**item) for item in service.list_skill_specs()]


@router.get("/mcp", response_model=list[MCPClientInfo])
async def list_market_mcp_clients(request: Request) -> list[MCPClientInfo]:
    service = _get_capability_service(request)
    return [MCPClientInfo(**item) for item in service.list_mcp_client_infos()]


@router.get("/mcp/catalog", response_model=McpRegistryCatalogSearchResponse)
async def search_market_mcp_catalog(
    request: Request,
    q: str = Query(default=""),
    category: str = Query(default="all"),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=12, ge=1, le=24),
) -> McpRegistryCatalogSearchResponse:
    catalog = _get_mcp_registry_catalog(request)
    return catalog.list_catalog(
        query=q,
        category=category,
        cursor=cursor,
        limit=limit,
        installed_clients=_load_market_mcp_clients(),
    )


@router.get("/mcp/catalog/{server_name:path}", response_model=McpRegistryCatalogDetailResponse)
async def get_market_mcp_catalog_detail(
    request: Request,
    server_name: str,
) -> McpRegistryCatalogDetailResponse:
    catalog = _get_mcp_registry_catalog(request)
    try:
        return catalog.get_catalog_detail(
            server_name,
            installed_clients=_load_market_mcp_clients(),
        )
    except ValueError as exc:
        raise HTTPException(404, detail=str(exc)) from exc


@router.post(
    "/mcp/catalog/{server_name:path}/install",
    response_model=CapabilityMarketMCPRegistryInstallResponse,
    status_code=201,
)
async def install_market_mcp_catalog_entry(
    request: Request,
    server_name: str,
    payload: CapabilityMarketMCPRegistryInstallRequest,
) -> CapabilityMarketMCPRegistryInstallResponse:
    return await _materialize_registry_mcp_install(
        request,
        server_name=server_name,
        payload=payload,
    )


@router.post(
    "/mcp/{client_key}/upgrade",
    response_model=CapabilityMarketMCPRegistryUpgradeResponse,
)
async def upgrade_market_mcp_client(
    request: Request,
    client_key: str,
    payload: CapabilityMarketMCPRegistryUpgradeRequest | None = None,
) -> CapabilityMarketMCPRegistryUpgradeResponse:
    return await _upgrade_registry_mcp_client(
        request,
        client_key=client_key,
        payload=payload or CapabilityMarketMCPRegistryUpgradeRequest(),
    )


@router.get(
    "/install-templates",
    response_model=list[CapabilityMarketInstallTemplateSpec],
)
async def list_market_install_templates(
    request: Request,
) -> list[CapabilityMarketInstallTemplateSpec]:
    service = _get_capability_service(request)
    decision_repository = _get_decision_request_repository(request)
    environment_service = _get_environment_service(request, required=False)
    browser_runtime_service = _get_browser_runtime_service(request)
    return [
        CapabilityMarketInstallTemplateSpec(**item.model_dump(mode="json"))
        for item in _call_install_template_surface(
            list_install_templates,
            capability_service=service,
            decision_request_repository=decision_repository,
            browser_runtime_service=browser_runtime_service,
            environment_service=environment_service,
            include_runtime=False,
        )
    ]


@router.get(
    "/install-templates/{template_id}",
    response_model=CapabilityMarketInstallTemplateSpec,
)
async def get_market_install_template(
    request: Request,
    template_id: str,
) -> CapabilityMarketInstallTemplateSpec:
    service = _get_capability_service(request)
    decision_repository = _get_decision_request_repository(request)
    environment_service = _get_environment_service(request, required=False)
    browser_runtime_service = _get_browser_runtime_service(request)
    template = _call_install_template_surface(
        get_install_template,
        template_id,
        capability_service=service,
        decision_request_repository=decision_repository,
        browser_runtime_service=browser_runtime_service,
        environment_service=environment_service,
        include_runtime=True,
    )
    if template is None:
        raise HTTPException(404, detail=f"Install template '{template_id}' not found")
    return CapabilityMarketInstallTemplateSpec(**template.model_dump(mode="json"))


@router.get(
    "/install-templates/{template_id}/doctor",
    response_model=InstallTemplateDoctorReport,
)
async def get_market_install_template_doctor(
    request: Request,
    template_id: str,
) -> InstallTemplateDoctorReport:
    service = _get_capability_service(request)
    environment_service = _get_environment_service(request, required=False)
    browser_runtime_service = _get_browser_runtime_service(request)
    report = _call_install_template_surface(
        build_install_template_doctor,
        template_id,
        capability_service=service,
        browser_runtime_service=browser_runtime_service,
        environment_service=environment_service,
    )
    if report is None:
        raise HTTPException(404, detail=f"Install template '{template_id}' not found")
    return report


@router.post(
    "/install-templates/{template_id}/example-run",
    response_model=InstallTemplateExampleRunRecord,
)
async def run_market_install_template_example(
    request: Request,
    template_id: str,
    payload: CapabilityMarketInstallTemplateExampleRunRequest | None = None,
) -> InstallTemplateExampleRunRecord:
    service = _get_capability_service(request)
    environment_service = _get_environment_service(request, required=False)
    browser_runtime_service = _get_browser_runtime_service(request)
    request_payload = payload or CapabilityMarketInstallTemplateExampleRunRequest()
    template = _call_install_template_surface(
        get_install_template,
        template_id,
        capability_service=service,
        decision_request_repository=_get_decision_request_repository(request),
        browser_runtime_service=browser_runtime_service,
        environment_service=environment_service,
        include_runtime=False,
    )
    if template is None:
        raise HTTPException(404, detail=f"Install template '{template_id}' not found")
    try:
        normalized_config = normalize_install_template_config(
            template.config_schema,
            request_payload.config,
        )
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    result = await _call_install_template_surface(
        run_install_template_example,
        template_id,
        capability_service=service,
        browser_runtime_service=browser_runtime_service,
        environment_service=environment_service,
        config=normalized_config,
    )
    if result is None:
        raise HTTPException(404, detail=f"Install template '{template_id}' not found")
    return result


@router.post(
    "/install-templates/{template_id}/install",
    response_model=CapabilityMarketInstallTemplateInstallResponse,
    status_code=201,
)
async def install_market_install_template(
    request: Request,
    template_id: str,
    payload: CapabilityMarketInstallTemplateInstallRequest | None = None,
) -> CapabilityMarketInstallTemplateInstallResponse:
    request_payload = payload or CapabilityMarketInstallTemplateInstallRequest()
    service = _get_capability_service(request)
    decision_repository = _get_decision_request_repository(request)
    environment_service = _get_environment_service(request, required=False)
    browser_runtime_service = _get_browser_runtime_service(
        request,
        required=template_id == "browser-local",
    )
    template = _call_install_template_surface(
        get_install_template,
        template_id,
        capability_service=service,
        decision_request_repository=decision_repository,
        browser_runtime_service=browser_runtime_service,
        environment_service=environment_service,
        include_runtime=True,
    )
    if template is None:
        raise HTTPException(404, detail=f"Install template '{template_id}' not found")
    try:
        normalized_config = normalize_install_template_config(
            template.config_schema,
            request_payload.config,
        )
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc

    assigned_capability_ids = _normalize_capability_ids(request_payload.capability_ids)
    if not assigned_capability_ids:
        if template.default_capability_id:
            assigned_capability_ids = [template.default_capability_id]
        elif template.default_client_key:
            assigned_capability_ids = [f"mcp:{template.default_client_key}"]

    if template.install_kind == "mcp-template":
        mcp_response = await _install_market_mcp_template_impl(
            request,
            template_id=template_id,
            payload=CapabilityMarketMCPTemplateInstallRequest(
                client_key=template.default_client_key,
                enabled=request_payload.enabled,
                actor=request_payload.actor,
                target_agent_ids=request_payload.target_agent_ids,
                capability_ids=assigned_capability_ids,
                config=normalized_config,
                capability_assignment_mode=request_payload.capability_assignment_mode,
                workflow_resume=request_payload.workflow_resume,
            ),
        )
        refreshed_template = _call_install_template_surface(
            get_install_template,
            template_id,
            capability_service=service,
            decision_request_repository=decision_repository,
            browser_runtime_service=browser_runtime_service,
            environment_service=environment_service,
            include_runtime=True,
        )
        return CapabilityMarketInstallTemplateInstallResponse(
            template_id=template_id,
            install_status=mcp_response.install_status,
            source_kind=template.source_kind,
            target_ref=mcp_response.key,
            enabled=mcp_response.enabled,
            ready=bool(refreshed_template.ready) if refreshed_template is not None else bool(mcp_response.enabled),
            assigned_capability_ids=list(mcp_response.assigned_capability_ids),
            assignment_results=list(mcp_response.assignment_results),
            workflow_resume=mcp_response.workflow_resume,
            summary=str(mcp_response.description or template.description or "").strip(),
            routes=template.routes,
        )

    if template.default_capability_id is None:
        raise HTTPException(
            400,
            detail=f"Install template '{template_id}' does not expose a default capability",
        )

    mount = service.get_capability(template.default_capability_id)
    if mount is None:
        raise HTTPException(
            404,
            detail=f"Capability '{template.default_capability_id}' not found",
        )
    install_status: Literal[
        "installed",
        "already-installed",
        "enabled-existing",
    ] = "already-installed"
    enabled = bool(mount.enabled)
    if request_payload.enabled is True and not enabled:
        result = await _dispatch_market_mutation(
            request,
            capability_ref="system:set_capability_enabled",
            title=f"Enable capability {template.default_capability_id}",
            payload={
                "capability_id": template.default_capability_id,
                "enabled": True,
                "actor": request_payload.actor,
            },
            fallback_risk="guarded",
        )
        if not result.get("success"):
            detail = str(result.get("error") or "Enable install template failed")
            raise HTTPException(_market_error_status(detail), detail=detail)
        install_status = "enabled-existing"
        enabled = True

    target_ref = template.default_capability_id
    summary = template.description
    if template_id == "browser-local" and browser_runtime_service is not None:
        default_profile = browser_runtime_service.ensure_default_profile(
            profile_id=str(
                normalized_config.get("profile_id") or "browser-local-default"
            ),
            label=str(
                normalized_config.get("profile_label") or "Default browser runtime"
            ),
            headed=bool(normalized_config.get("headed", True)),
            reuse_running_session=bool(
                normalized_config.get("reuse_running_session", True)
            ),
            persist_login_state=bool(
                normalized_config.get("persist_login_state", True)
            ),
            entry_url=str(normalized_config.get("entry_url") or ""),
            metadata={"source_template_id": template_id},
        )
        target_ref = default_profile.profile_id
        summary = f"{template.description} Default profile: {default_profile.label}"

    invalid_capability_ids = [
        capability_id
        for capability_id in assigned_capability_ids
        if service.get_capability(capability_id) is None
    ]
    if invalid_capability_ids:
        raise HTTPException(
            400,
            detail=(
                "Capability ids are not available for install template: "
                + ", ".join(sorted(invalid_capability_ids))
            ),
        )
    assignment_results = await _assign_capabilities_to_agents(
        request,
        template_id=template_id,
        actor=request_payload.actor,
        target_agent_ids=_normalize_agent_ids(request_payload.target_agent_ids),
        capability_ids=assigned_capability_ids,
        capability_assignment_mode=request_payload.capability_assignment_mode,
    )
    refreshed_template = _call_install_template_surface(
        get_install_template,
        template_id,
        capability_service=service,
        decision_request_repository=decision_repository,
        browser_runtime_service=browser_runtime_service,
        environment_service=environment_service,
        include_runtime=True,
    )
    ready = bool(refreshed_template.ready) if refreshed_template is not None else bool(enabled)
    return CapabilityMarketInstallTemplateInstallResponse(
        template_id=template_id,
        install_status=install_status,
        source_kind=template.source_kind,
        target_ref=target_ref,
        enabled=enabled,
        ready=ready,
        assigned_capability_ids=assigned_capability_ids,
        assignment_results=assignment_results,
        workflow_resume=_response_workflow_resume(request_payload.workflow_resume),
        summary=summary,
        routes=template.routes,
    )


@router.get(
    "/install-templates/browser-local/profiles",
    response_model=list[BrowserProfileRecord],
)
async def list_browser_runtime_profiles(
    request: Request,
) -> list[BrowserProfileRecord]:
    service = _get_browser_runtime_service(request, required=True)
    return service.list_profiles()


@router.post(
    "/install-templates/browser-local/profiles",
    response_model=BrowserProfileRecord,
    status_code=201,
)
async def upsert_browser_runtime_profile(
    request: Request,
    payload: BrowserProfileUpsertRequest,
) -> BrowserProfileRecord:
    service = _get_browser_runtime_service(request, required=True)
    existing = service.get_profile(payload.profile_id) if payload.profile_id else None
    profile_id = (
        str(payload.profile_id or "").strip()
        or (existing.profile_id if existing is not None else "browser-local-default")
    )
    label = (
        str(payload.label or "").strip()
        or (existing.label if existing is not None else "Default browser runtime")
    )
    record = BrowserProfileRecord(
        profile_id=profile_id,
        label=label,
        headed=(
            payload.headed if payload.headed is not None else bool(existing.headed)
            if existing is not None
            else True
        ),
        reuse_running_session=(
            payload.reuse_running_session
            if payload.reuse_running_session is not None
            else bool(existing.reuse_running_session)
            if existing is not None
            else True
        ),
        persist_login_state=(
            payload.persist_login_state
            if payload.persist_login_state is not None
            else bool(existing.persist_login_state)
            if existing is not None
            else True
        ),
        entry_url=(
            str(payload.entry_url or "").strip()
            or (existing.entry_url if existing is not None else "")
        ),
        is_default=(
            payload.is_default
            if payload.is_default is not None
            else bool(existing.is_default)
            if existing is not None
            else False
        ),
        metadata=(
            dict(existing.metadata or {}) | dict(payload.metadata or {})
            if existing is not None
            else dict(payload.metadata or {})
        ),
        created_at=(
            existing.created_at
            if existing is not None
            else BrowserProfileRecord(profile_id=profile_id, label=label).created_at
        ),
    )
    return service.upsert_profile(record)


@router.get(
    "/install-templates/browser-local/sessions",
    response_model=dict[str, Any],
)
async def list_browser_runtime_sessions(
    request: Request,
) -> dict[str, Any]:
    service = _get_browser_runtime_service(request, required=True)
    return service.runtime_snapshot()


@router.post(
    "/install-templates/browser-local/sessions/start",
    response_model=dict[str, Any],
)
async def start_browser_runtime_session(
    request: Request,
    payload: BrowserSessionStartRequest | None = None,
) -> dict[str, Any]:
    service = _get_browser_runtime_service(request, required=True)
    request_payload = payload or BrowserSessionStartRequest()
    return await service.start_session(
        BrowserSessionStartOptions(
            session_id=request_payload.session_id,
            profile_id=request_payload.profile_id,
            headed=request_payload.headed,
            entry_url=request_payload.entry_url,
            reuse_running_session=request_payload.reuse_running_session,
            persist_login_state=request_payload.persist_login_state,
        )
    )


@router.post(
    "/install-templates/browser-local/sessions/{session_id}/attach",
    response_model=dict[str, Any],
)
async def attach_browser_runtime_session(
    request: Request,
    session_id: str,
) -> dict[str, Any]:
    service = _get_browser_runtime_service(request, required=True)
    return service.attach_session(session_id)


@router.post(
    "/install-templates/browser-local/sessions/{session_id}/stop",
    response_model=dict[str, Any],
)
async def stop_browser_runtime_session(
    request: Request,
    session_id: str,
) -> dict[str, Any]:
    service = _get_browser_runtime_service(request, required=True)
    return await service.stop_session(session_id)


@router.post("/skills", response_model=dict[str, object], status_code=201)
async def create_market_skill(
    request: Request,
    payload: CapabilityMarketCreateSkillRequest,
) -> dict[str, object]:
    result = await _dispatch_market_mutation(
        request,
        capability_ref="system:create_skill",
        title=f"Create skill {payload.name}",
        payload={
            "name": payload.name,
            "content": payload.content,
            "references": payload.references,
            "scripts": payload.scripts,
            "overwrite": payload.overwrite,
            "actor": payload.actor,
        },
        fallback_risk="guarded",
    )
    if not result.get("success"):
        detail = str(
            result.get("error")
            or result.get("summary")
            or f"Failed to create skill '{payload.name}'."
        )
        raise HTTPException(_market_error_status(detail), detail=detail)
    return {
        **result,
        "created": True,
        "name": result.get("name") or payload.name,
    }


@router.post("/hub/install", response_model=CapabilityMarketHubInstallResponse)
async def install_market_hub_skill(
    request: Request,
    payload: CapabilityMarketHubInstallRequest,
) -> CapabilityMarketHubInstallResponse:
    result = await _dispatch_market_mutation(
        request,
        capability_ref="system:install_hub_skill",
        title=f"Install hub skill from {payload.bundle_url}",
        payload={
            "bundle_url": payload.bundle_url,
            "version": payload.version,
            "enable": payload.enable,
            "overwrite": payload.overwrite,
            "actor": payload.actor,
        },
        fallback_risk="guarded",
    )
    result = _unwrap_market_mutation_result(result)
    if not result.get("success"):
        detail = str(
            result.get("error")
            or result.get("summary")
            or "Skill hub install failed"
        )
        raise HTTPException(_market_error_status(detail), detail=detail)
    installed_name = str(result.get("name") or "") or _extract_installed_skill_name(
        result.get("summary"),
    )
    target_agent_ids = _normalize_agent_ids(payload.target_agent_ids)
    assigned_capability_ids = _resolve_remote_skill_capability_ids(
        request,
        capability_ids=payload.capability_ids,
        installed_name=installed_name,
        target_agent_ids=target_agent_ids,
    )
    assignment_results = await _assign_capabilities_to_agents(
        request,
        template_id=installed_name or payload.bundle_url,
        actor=payload.actor,
        target_agent_ids=target_agent_ids,
        capability_ids=assigned_capability_ids,
        capability_assignment_mode=payload.capability_assignment_mode,
    )
    return CapabilityMarketHubInstallResponse(
        installed=True,
        name=installed_name,
        enabled=bool(result.get("enabled", payload.enable)),
        source_url=str(result.get("source_url") or payload.bundle_url),
        assigned_capability_ids=assigned_capability_ids,
        assignment_results=assignment_results,
    )


@router.post(
    "/curated-catalog/install",
    response_model=CapabilityMarketCuratedInstallResponse,
)
async def install_market_curated_skill(
    request: Request,
    payload: CapabilityMarketCuratedInstallRequest,
) -> CapabilityMarketCuratedInstallResponse:
    candidate = await asyncio.to_thread(
        get_curated_skill_catalog_entry,
        payload.source_id,
        payload.candidate_id,
    )
    if candidate is None:
        raise HTTPException(
            404,
            detail=(
                "Curated skill candidate not found: "
                f"{payload.source_id}/{payload.candidate_id}"
            ),
        )
    if candidate.review_required and not payload.review_acknowledged:
        raise HTTPException(
            400,
            detail=(
                "该推荐技能在安装前需要操作方确认已阅读审查说明。"
            ),
        )
    result = await _dispatch_market_mutation(
        request,
        capability_ref="system:install_hub_skill",
        title=f"Install curated skill {candidate.title}",
        payload={
            "bundle_url": candidate.bundle_url,
            "version": candidate.version,
            "enable": payload.enable,
            "overwrite": payload.overwrite,
            "actor": payload.actor,
        },
        fallback_risk="guarded",
    )
    result = _unwrap_market_mutation_result(result)
    if not result.get("success"):
        detail = str(
            result.get("error")
            or result.get("summary")
            or "推荐技能安装失败"
        )
        raise HTTPException(_market_error_status(detail), detail=detail)
    installed_name = str(result.get("name") or "") or _extract_installed_skill_name(
        result.get("summary"),
    )
    target_agent_ids = _normalize_agent_ids(payload.target_agent_ids)
    assigned_capability_ids = _resolve_remote_skill_capability_ids(
        request,
        capability_ids=payload.capability_ids,
        installed_name=installed_name or candidate.install_name,
        target_agent_ids=target_agent_ids,
    )
    assignment_results = await _assign_capabilities_to_agents(
        request,
        template_id=candidate.candidate_id,
        actor=payload.actor,
        target_agent_ids=target_agent_ids,
        capability_ids=assigned_capability_ids,
        capability_assignment_mode=payload.capability_assignment_mode,
    )
    return CapabilityMarketCuratedInstallResponse(
        installed=True,
        name=installed_name,
        enabled=bool(result.get("enabled", payload.enable)),
        source_url=str(result.get("source_url") or candidate.bundle_url),
        source_id=payload.source_id,
        candidate_id=payload.candidate_id,
        review_summary=candidate.review_summary,
        review_notes=list(candidate.review_notes or []),
        assigned_capability_ids=assigned_capability_ids,
        assignment_results=assignment_results,
    )


@router.post(
    "/projects/install",
    response_model=CapabilityMarketProjectInstallResponse,
)
async def install_market_project_donor(
    request: Request,
    payload: CapabilityMarketProjectInstallRequest,
) -> CapabilityMarketProjectInstallResponse:
    capability_kind = _normalize_external_capability_kind(payload.capability_kind)
    candidate, source_url, version = _resolve_project_candidate(
        request,
        candidate_id=payload.candidate_id,
        source_url=payload.source_url,
        version=payload.version,
    )
    target_agent_id = str(payload.target_agent_id or "").strip() or None
    if target_agent_id is not None:
        _ensure_target_agents_exist(request, target_agent_ids=[target_agent_id])
    candidate = _materialize_project_candidate(
        request,
        candidate=candidate,
        source_url=source_url,
        target_role_id=str(payload.target_role_id or "").strip() or None,
        target_seat_ref=str(payload.selected_seat_ref or "").strip() or None,
        trial_scope=payload.trial_scope,
        candidate_kind=capability_kind,
    )
    resolved_candidate_id = str(
        getattr(candidate, "candidate_id", "") or payload.candidate_id or "",
    ).strip() or None
    install_result = _install_external_project_capability(
        source_url=source_url,
        version=version,
        capability_kind=capability_kind,
        entry_module=payload.entry_module,
        execute_command=payload.execute_command,
        healthcheck_command=payload.healthcheck_command,
        enable=payload.enable,
        overwrite=payload.overwrite,
    )
    if inspect.isawaitable(install_result):
        install_result = await install_result
    result = dict(install_result)
    installed_capability_ids = _normalize_capability_ids(
        list(result.get("installed_capability_ids") or []),
    )
    trial_attachment: dict[str, Any] | None = None
    if target_agent_id is not None:
        lifecycle_result = await _dispatch_market_mutation(
            request,
            capability_ref="system:apply_capability_lifecycle",
            title=(
                f"Attach project donor {source_url}"
                + (f" for {target_agent_id}" if target_agent_id else "")
            ),
            payload={
                "decision_kind": "continue_trial",
                "candidate_id": resolved_candidate_id,
                "target_agent_id": target_agent_id,
                "selected_seat_ref": str(payload.selected_seat_ref or "").strip() or None,
                "selected_scope": _project_target_scope(
                    trial_scope=payload.trial_scope,
                    selected_seat_ref=str(payload.selected_seat_ref or "").strip() or None,
                    target_role_id=str(payload.target_role_id or "").strip() or None,
                ),
                "scope_ref": (
                    str(payload.selected_seat_ref or "").strip()
                    or target_agent_id
                ),
                "target_role_id": str(payload.target_role_id or "").strip() or None,
                "capability_ids": installed_capability_ids,
                "replacement_capability_ids": _normalize_capability_ids(
                    payload.replacement_capability_ids,
                ),
                "replacement_target_ids": _normalize_capability_ids(
                    payload.replacement_target_ids,
                ),
                "capability_assignment_mode": payload.capability_assignment_mode,
                "actor": payload.actor,
            },
            fallback_risk="guarded",
        )
        lifecycle_result = _unwrap_market_mutation_result(lifecycle_result)
        if not lifecycle_result.get("success"):
            detail = str(
                lifecycle_result.get("error")
                or lifecycle_result.get("summary")
                or "Project donor trial attach failed"
            )
            raise HTTPException(_market_error_status(detail), detail=detail)
        if isinstance(lifecycle_result.get("trial_attachment"), dict):
            trial_attachment = dict(lifecycle_result.get("trial_attachment"))
        else:
            trial_attachment = {
                "success": True,
                "selected_scope": _project_target_scope(
                    trial_scope=payload.trial_scope,
                    selected_seat_ref=str(payload.selected_seat_ref or "").strip() or None,
                    target_role_id=str(payload.target_role_id or "").strip() or None,
                ),
                "scope_type": _project_target_scope(
                    trial_scope=payload.trial_scope,
                    selected_seat_ref=str(payload.selected_seat_ref or "").strip() or None,
                    target_role_id=str(payload.target_role_id or "").strip() or None,
                ),
                "scope_ref": str(payload.selected_seat_ref or "").strip() or target_agent_id,
            }
    result["trial_attachment"] = trial_attachment
    _sync_project_trial_truth(
        request,
        candidate_id=resolved_candidate_id,
        target_agent_id=target_agent_id,
        result=result,
    )
    return CapabilityMarketProjectInstallResponse(
        installed=bool(result.get("installed", True)),
        candidate_id=resolved_candidate_id,
        name=str(result.get("name") or ""),
        enabled=bool(result.get("enabled", payload.enable)),
        source_url=str(result.get("source_url") or source_url),
        capability_kind=str(result.get("capability_kind") or capability_kind),
        installed_capability_ids=[
            str(item).strip()
            for item in list(result.get("installed_capability_ids") or [])
            if str(item).strip()
        ],
        target_agent_id=target_agent_id,
        trial_attachment=(
            dict(result.get("trial_attachment"))
            if isinstance(result.get("trial_attachment"), dict)
            else None
        ),
    )


@router.post("/mcp", response_model=MCPClientInfo, status_code=201)
async def create_market_mcp_client(
    request: Request,
    payload: CapabilityMarketMCPCreateRequest,
) -> MCPClientInfo:
    result = await _dispatch_market_mutation(
        request,
        capability_ref="system:create_mcp_client",
        title=f"Create MCP client {payload.client_key}",
        payload={
            "client_key": payload.client_key,
            "client": payload.client.model_dump(mode="json"),
            "actor": payload.actor,
        },
        fallback_risk="guarded",
    )
    if not result.get("success"):
        detail = str(result.get("error") or "Create MCP client failed")
        raise HTTPException(_market_error_status(detail), detail=detail)
    service = _get_capability_service(request)
    return _mcp_info_or_500(service, client_key=payload.client_key)


async def _install_market_mcp_template_impl(
    request: Request,
    *,
    template_id: str,
    payload: CapabilityMarketMCPTemplateInstallRequest,
) -> CapabilityMarketMCPTemplateInstallResponse:
    template = get_desktop_mcp_template(template_id)
    if template is None:
        raise HTTPException(404, detail=f"MCP template '{template_id}' not found")

    service = _get_capability_service(request)
    client_key = payload.client_key or template.default_client_key
    client_payload = dict(template.client)
    if payload.config:
        if "command" in payload.config:
            client_payload["command"] = str(payload.config.get("command") or "").strip()
        if "args" in payload.config:
            client_payload["args"] = [
                str(item).strip()
                for item in list(payload.config.get("args") or [])
                if str(item).strip()
            ]
    if payload.enabled is not None:
        client_payload["enabled"] = payload.enabled
    elif "enabled" in payload.config:
        client_payload["enabled"] = bool(payload.config.get("enabled"))
    target_agent_ids = _normalize_agent_ids(payload.target_agent_ids)
    assigned_capability_ids = _normalize_capability_ids(payload.capability_ids)
    if not assigned_capability_ids:
        assigned_capability_ids = [f"mcp:{client_key}"]

    existing_client = service.get_mcp_client_info(client_key)
    install_status: Literal[
        "installed",
        "already-installed",
        "enabled-existing",
    ] = "installed"
    if existing_client is None:
        result = await _dispatch_market_mutation(
            request,
            capability_ref="system:create_mcp_client",
            title=f"Install MCP template {template_id} as {client_key}",
            payload={
                "client_key": client_key,
                "client": client_payload,
                "actor": payload.actor,
            },
            fallback_risk="guarded",
        )
        if not result.get("success"):
            detail = str(result.get("error") or "Install MCP template failed")
            raise HTTPException(_market_error_status(detail), detail=detail)
    else:
        install_status = "already-installed"
        should_enable = payload.enabled is True and not bool(existing_client.get("enabled"))
        if should_enable:
            result = await _dispatch_market_mutation(
                request,
                capability_ref="system:update_mcp_client",
                title=f"Enable installed MCP template {template_id} as {client_key}",
                payload={
                    "client_key": client_key,
                    "client": {"enabled": True},
                    "actor": payload.actor,
                },
                fallback_risk="guarded",
            )
            if not result.get("success"):
                detail = str(result.get("error") or "Enable MCP template failed")
                raise HTTPException(_market_error_status(detail), detail=detail)
            install_status = "enabled-existing"

    invalid_capability_ids = [
        capability_id
        for capability_id in assigned_capability_ids
        if service.get_capability(capability_id) is None
    ]
    if invalid_capability_ids:
        raise HTTPException(
            400,
            detail=(
                "Capability ids are not available after install: "
                + ", ".join(sorted(invalid_capability_ids))
            ),
        )

    assignment_results = await _assign_capabilities_to_agents(
        request,
        template_id=template_id,
        actor=payload.actor,
        target_agent_ids=target_agent_ids,
        capability_ids=assigned_capability_ids,
        capability_assignment_mode=payload.capability_assignment_mode,
    )
    response_resume = _response_workflow_resume(payload.workflow_resume)
    client_info = _mcp_info_or_500(service, client_key=client_key)
    return CapabilityMarketMCPTemplateInstallResponse(
        **client_info.model_dump(mode="json"),
        install_status=install_status,
        assigned_capability_ids=assigned_capability_ids,
        assignment_results=assignment_results,
        workflow_resume=response_resume,
    )


@router.put("/mcp/{client_key}", response_model=MCPClientInfo)
async def update_market_mcp_client(
    request: Request,
    client_key: str,
    updates: CapabilityMarketMCPUpdateRequest,
) -> MCPClientInfo:
    result = await _dispatch_market_mutation(
        request,
        capability_ref="system:update_mcp_client",
        title=f"Update MCP client {client_key}",
        payload={
            "client_key": client_key,
            "client": updates.model_dump(
                mode="json",
                exclude={"actor"},
                exclude_unset=True,
            ),
            "actor": updates.actor,
        },
        fallback_risk="guarded",
    )
    if not result.get("success"):
        detail = str(result.get("error") or "Update MCP client failed")
        raise HTTPException(_market_error_status(detail), detail=detail)
    service = _get_capability_service(request)
    return _mcp_info_or_500(service, client_key=client_key)


@router.patch("/capabilities/{capability_id:path}/toggle", response_model=dict[str, object])
async def toggle_market_capability(
    request: Request,
    capability_id: str,
    payload: CapabilityMutationRequest | None = None,
) -> dict[str, object]:
    service = _get_capability_service(request)
    mount = service.get_public_capability(capability_id)
    if mount is None:
        raise HTTPException(404, detail=f"Capability '{capability_id}' not found")

    desired_enabled = not mount.enabled
    result = await _dispatch_market_mutation(
        request,
        capability_ref="system:set_capability_enabled",
        title=f"Set capability {capability_id} enabled={desired_enabled}",
        payload={
            "capability_id": capability_id,
            "enabled": desired_enabled,
            "actor": payload.actor if payload is not None else "copaw-operator",
        },
        fallback_risk="guarded",
    )
    if result.get("success"):
        result.update(
            {
                "toggled": True,
                "id": capability_id,
                "enabled": desired_enabled,
            },
        )
    return result


@router.delete("/capabilities/{capability_id:path}", response_model=dict[str, object])
async def delete_market_capability(
    request: Request,
    capability_id: str,
    payload: CapabilityMutationRequest | None = None,
) -> dict[str, object]:
    service = _get_capability_service(request)
    mount = service.get_public_capability(capability_id)
    if mount is None:
        raise HTTPException(404, detail=f"Capability '{capability_id}' not found")

    result = await _dispatch_market_mutation(
        request,
        capability_ref="system:delete_capability",
        title=f"Delete capability {capability_id}",
        payload={
            "capability_id": capability_id,
            "actor": payload.actor if payload is not None else "copaw-operator",
        },
        fallback_risk="confirm",
    )
    if result.get("success"):
        result.update(
            {
                "deleted": True,
                "id": capability_id,
            },
        )
    return result


@router.get("/hub/search", response_model=list[HubSkillSpec])
async def search_market_hub(
    q: str = Query(default=""),
    limit: int = Query(default=20, ge=1, le=200),
) -> list[HubSkillSpec]:
    results = await asyncio.to_thread(search_hub_skills, q, limit=limit)
    return [
        HubSkillSpec(
            slug=item.slug,
            name=item.name,
            description=item.description,
            version=item.version,
            source_url=item.source_url,
            source_label=getattr(item, "source_label", None),
        )
        for item in results
    ]


@router.get("/curated-sources", response_model=list[CuratedSkillCatalogSource])
async def list_market_curated_sources() -> list[CuratedSkillCatalogSource]:
    return list_curated_skill_sources()


@router.get("/curated-catalog", response_model=CuratedSkillCatalogSearchResponse)
async def search_market_curated_catalog(
    q: str = Query(default=""),
    limit: int = Query(default=20, ge=1, le=500),
) -> CuratedSkillCatalogSearchResponse:
    return await asyncio.to_thread(search_curated_skill_catalog, q, limit=limit)


@router.get(
    "/projects/search",
    response_model=list[CapabilityMarketProjectCandidate],
)
async def search_market_project_donors(
    q: str = Query(default=""),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[CapabilityMarketProjectCandidate]:
    hits = await asyncio.to_thread(
        search_github_repository_donors,
        q,
        limit=limit,
    )
    return [
        CapabilityMarketProjectCandidate(
            display_name=str(hit.display_name or hit.candidate_source_ref or "GitHub donor"),
            summary=hit.summary,
            source_kind=hit.source_kind,
            candidate_kind=hit.candidate_kind,
            source_url=str(hit.candidate_source_ref or ""),
            version=str(hit.candidate_source_version or ""),
            source_lineage=hit.candidate_source_lineage,
            canonical_package_id=hit.canonical_package_id,
            capability_keys=[str(item).strip() for item in hit.capability_keys if str(item).strip()],
            install_supported=bool(hit.metadata.get("install_supported")),
            metadata=dict(hit.metadata),
            routes={
                "install": "/api/capability-market/projects/install",
                "source": str(hit.candidate_source_ref or ""),
            },
        )
        for hit in hits
        if str(hit.candidate_source_ref or "").strip()
    ]
