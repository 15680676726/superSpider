# -*- coding: utf-8 -*-
"""Environment detail and recovery health views."""
from __future__ import annotations

from datetime import datetime
import re
from typing import TYPE_CHECKING

from .models import SessionMount

if TYPE_CHECKING:
    from .service import EnvironmentService


class EnvironmentHealthService:
    """Focused collaborator for environment/session detail surfaces."""

    _HOST_EVENT_TOPICS = {
        "session",
        "resource-slot",
        "replay",
        "system",
        "window",
        "desktop",
        "download",
        "process",
        "network",
        "power",
        "host",
    }
    _HOST_EVENT_SUPPORTED_FAMILIES = (
        "active-window",
        "modal-uac-login",
        "download-completed",
        "process-exit-restart",
        "lock-unlock",
        "network-power",
    )
    _HOST_EVENT_RESPONSE_BY_FAMILY = {
        "active-window": "re-observe",
        "modal-uac-login": "handoff",
        "human-handoff-return": "handoff",
        "download-completed": "re-observe",
        "process-exit-restart": "recover",
        "lock-unlock": "recover",
        "network-power": "retry",
        "runtime-generic": "re-observe",
    }
    _HOST_EVENT_SEVERITY_BY_FAMILY = {
        "active-window": "medium",
        "modal-uac-login": "high",
        "human-handoff-return": "high",
        "download-completed": "low",
        "process-exit-restart": "high",
        "lock-unlock": "high",
        "network-power": "medium",
        "runtime-generic": "medium",
    }
    _HOST_EVENT_NOTE = (
        "Host events are runtime-mechanism signals for observe/recover loops, "
        "not truth-store records."
    )
    _CANONICAL_BROWSER_MODE_BY_LEGACY = {
        "tab-attached": "attach-existing-session",
        "tab_attached": "attach-existing-session",
    }
    _HOST_LABEL_CONTROL_RE = re.compile(r"[\r\n\t]+")
    _HOST_LABEL_WHITESPACE_RE = re.compile(r"\s+")

    def __init__(self, service: EnvironmentService) -> None:
        self._service = service

    def get_environment_detail(
        self,
        env_id: str,
        *,
        limit: int = 20,
    ) -> dict[str, object] | None:
        mount = self._service.get_environment(env_id)
        if mount is None:
            return None
        sessions = self._service.list_sessions(environment_id=env_id, limit=limit)
        observations = self._service.list_observations(
            environment_ref=mount.ref,
            limit=limit,
        )
        replays = self._service.list_replays(environment_ref=mount.ref, limit=limit)
        artifacts = self._service.list_artifacts(
            environment_ref=mount.ref,
            limit=limit,
        )
        live_handle = self._service._registry.get_live_handle_info(env_id)
        primary_session = self._select_primary_session(sessions)
        primary_recovery = self.build_recovery_payload(
            session=primary_session,
            environment_ref=mount.ref,
            live_handle=live_handle,
            replay_count=len(replays),
        )
        host_event_summary, host_events = self.build_host_events_projection(
            environment_id=mount.id,
            environment_ref=mount.ref,
            session_mount_id=primary_session.id if primary_session is not None else None,
            limit=limit,
        )
        host_contract = self.build_host_contract_projection(
            mount=mount,
            session=primary_session,
            live_handle=live_handle,
            recovery=primary_recovery,
            host_event_summary=host_event_summary,
        )
        self._backfill_host_event_summary_contract(
            host_event_summary=host_event_summary,
            host_contract=host_contract,
        )
        multi_seat_context = self._build_multi_seat_context(
            mount=mount,
            session=primary_session,
            host_contract=host_contract,
        )
        host_companion_session = self.build_host_companion_projection(
            mount=mount,
            session=primary_session,
            live_handle=live_handle,
            recovery=primary_recovery,
            host_contract=host_contract,
        )
        browser_site_contract = self.build_browser_site_contract_projection(
            mount=mount,
            session=primary_session,
            live_handle=live_handle,
            recovery=primary_recovery,
            host_contract=host_contract,
            host_companion_session=host_companion_session,
            host_event_summary=host_event_summary,
        )
        desktop_app_contract = self.build_desktop_app_contract_projection(
            mount=mount,
            session=primary_session,
            live_handle=live_handle,
            recovery=primary_recovery,
            host_contract=host_contract,
            host_companion_session=host_companion_session,
            host_event_summary=host_event_summary,
        )
        cooperative_adapter_availability = (
            self.build_cooperative_adapter_availability_projection(
                mount=mount,
                session=primary_session,
                live_handle=live_handle,
                host_contract=host_contract,
                browser_site_contract=browser_site_contract,
                desktop_app_contract=desktop_app_contract,
            )
        )
        seat_runtime = self.build_seat_runtime_projection(
            mount=mount,
            session=primary_session,
            host_contract=host_contract,
            host_companion_session=host_companion_session,
            live_handle=live_handle,
            session_count=len(sessions),
            multi_seat_context=multi_seat_context,
        )
        workspace_graph = self.build_workspace_graph_projection(
            mount=mount,
            session=primary_session,
            host_contract=host_contract,
            browser_site_contract=browser_site_contract,
            desktop_app_contract=desktop_app_contract,
            host_event_summary=host_event_summary,
            observations=observations,
            replays=replays,
            artifacts=artifacts,
            live_handle=live_handle,
        )
        host_twin = self.build_host_twin_projection(
            mount=mount,
            session=primary_session,
            host_contract=host_contract,
            recovery=primary_recovery,
            seat_runtime=seat_runtime,
            host_companion_session=host_companion_session,
            browser_site_contract=browser_site_contract,
            desktop_app_contract=desktop_app_contract,
            workspace_graph=workspace_graph,
            host_event_summary=host_event_summary,
        )
        payload = mount.model_dump(mode="json")
        payload.update(
            {
                "live_handle": live_handle,
                "recovery": self.build_recovery_payload(
                    session=None,
                    environment_ref=mount.ref,
                    live_handle=live_handle,
                    replay_count=len(replays),
                ),
                "host_contract": host_contract,
                "seat_runtime": seat_runtime,
                "host_companion_session": host_companion_session,
                "browser_site_contract": browser_site_contract,
                "desktop_app_contract": desktop_app_contract,
                "cooperative_adapter_availability": cooperative_adapter_availability,
                "workspace_graph": workspace_graph,
                "host_twin": host_twin,
                "host_twin_summary": host_twin.get("host_twin_summary"),
                "host_event_summary": host_event_summary,
                "host_events": host_events,
                "sessions": [session.model_dump(mode="json") for session in sessions],
                "observations": [
                    record.model_dump(mode="json") for record in observations
                ],
                "replays": [record.model_dump(mode="json") for record in replays],
                "artifacts": [record.model_dump(mode="json") for record in artifacts],
                "stats": {
                    "session_count": len(sessions),
                    "observation_count": len(observations),
                    "replay_count": len(replays),
                    "artifact_count": len(artifacts),
                },
            },
        )
        return payload

    def get_session_detail(
        self,
        session_mount_id: str,
        *,
        limit: int = 20,
    ) -> dict[str, object] | None:
        session = self._service.get_session(session_mount_id)
        if session is None:
            return None
        environment = self._service.get_environment(session.environment_id)
        environment_ref = environment.ref if environment is not None else None
        observations = self._service.list_observations(
            environment_ref=environment_ref,
            limit=limit,
        )
        replays = self._service.list_replays(
            environment_ref=environment_ref,
            limit=limit,
        )
        artifacts = self._service.list_artifacts(
            environment_ref=environment_ref,
            limit=limit,
        )
        live_handle = self._service._registry.get_live_handle_info(session.environment_id)
        recovery = self.build_recovery_payload(
            session=session,
            environment_ref=environment_ref,
            live_handle=live_handle,
            replay_count=len(replays),
        )
        host_event_summary, host_events = self.build_host_events_projection(
            environment_id=session.environment_id,
            environment_ref=environment_ref,
            session_mount_id=session.id,
            limit=limit,
        )
        host_contract = self.build_host_contract_projection(
            mount=environment,
            session=session,
            live_handle=live_handle,
            recovery=recovery,
            host_event_summary=host_event_summary,
        )
        self._backfill_host_event_summary_contract(
            host_event_summary=host_event_summary,
            host_contract=host_contract,
        )
        multi_seat_context = self._build_multi_seat_context(
            mount=environment,
            session=session,
            host_contract=host_contract,
        )
        host_companion_session = self.build_host_companion_projection(
            mount=environment,
            session=session,
            live_handle=live_handle,
            recovery=recovery,
            host_contract=host_contract,
        )
        browser_site_contract = self.build_browser_site_contract_projection(
            mount=environment,
            session=session,
            live_handle=live_handle,
            recovery=recovery,
            host_contract=host_contract,
            host_companion_session=host_companion_session,
            host_event_summary=host_event_summary,
        )
        desktop_app_contract = self.build_desktop_app_contract_projection(
            mount=environment,
            session=session,
            live_handle=live_handle,
            recovery=recovery,
            host_contract=host_contract,
            host_companion_session=host_companion_session,
            host_event_summary=host_event_summary,
        )
        cooperative_adapter_availability = (
            self.build_cooperative_adapter_availability_projection(
                mount=environment,
                session=session,
                live_handle=live_handle,
                host_contract=host_contract,
                browser_site_contract=browser_site_contract,
                desktop_app_contract=desktop_app_contract,
            )
        )
        seat_runtime = self.build_seat_runtime_projection(
            mount=environment,
            session=session,
            host_contract=host_contract,
            host_companion_session=host_companion_session,
            live_handle=live_handle,
            session_count=1 if environment is not None else 0,
            multi_seat_context=multi_seat_context,
        )
        workspace_graph = self.build_workspace_graph_projection(
            mount=environment,
            session=session,
            host_contract=host_contract,
            browser_site_contract=browser_site_contract,
            desktop_app_contract=desktop_app_contract,
            host_event_summary=host_event_summary,
            observations=observations,
            replays=replays,
            artifacts=artifacts,
            live_handle=live_handle,
        )
        host_twin = self.build_host_twin_projection(
            mount=environment,
            session=session,
            host_contract=host_contract,
            recovery=recovery,
            seat_runtime=seat_runtime,
            host_companion_session=host_companion_session,
            browser_site_contract=browser_site_contract,
            desktop_app_contract=desktop_app_contract,
            workspace_graph=workspace_graph,
            host_event_summary=host_event_summary,
        )
        payload = session.model_dump(mode="json")
        payload.update(
            {
                "live_handle": live_handle,
                "recovery": recovery,
                "host_contract": host_contract,
                "seat_runtime": seat_runtime,
                "host_companion_session": host_companion_session,
                "browser_site_contract": browser_site_contract,
                "desktop_app_contract": desktop_app_contract,
                "cooperative_adapter_availability": cooperative_adapter_availability,
                "workspace_graph": workspace_graph,
                "host_twin": host_twin,
                "host_twin_summary": host_twin.get("host_twin_summary"),
                "host_event_summary": host_event_summary,
                "host_events": host_events,
                "environment": (
                    environment.model_dump(mode="json")
                    if environment is not None
                    else None
                ),
                "observations": [
                    record.model_dump(mode="json") for record in observations
                ],
                "replays": [record.model_dump(mode="json") for record in replays],
                "artifacts": [record.model_dump(mode="json") for record in artifacts],
                "stats": {
                    "observation_count": len(observations),
                    "replay_count": len(replays),
                    "artifact_count": len(artifacts),
                },
            },
        )
        return payload

    def build_host_contract_projection(
        self,
        *,
        mount,
        session: SessionMount | None,
        live_handle: dict[str, object] | None,
        recovery: dict[str, object],
        host_event_summary: dict[str, object],
    ) -> dict[str, object]:
        (
            mount_metadata,
            session_metadata,
            runtime_metadata,
            runtime_descriptor,
            live_descriptor,
        ) = self._surface_runtime_context(
            mount=mount,
            session=session,
            live_handle=live_handle,
        )
        blocker_event = self._blocking_host_event(host_event_summary)
        explicit_handoff_state = self._first_string(
            session_metadata.get("handoff_state"),
            mount_metadata.get("handoff_state"),
            runtime_descriptor.get("handoff_state"),
            live_descriptor.get("handoff_state"),
        )
        explicit_handoff_reason = self._first_string(
            session_metadata.get("handoff_reason"),
            mount_metadata.get("handoff_reason"),
            runtime_descriptor.get("handoff_reason"),
            live_descriptor.get("handoff_reason"),
        )
        explicit_current_gap = self._first_string(
            session_metadata.get("current_gap_or_blocker"),
            mount_metadata.get("current_gap_or_blocker"),
            runtime_descriptor.get("current_gap_or_blocker"),
            live_descriptor.get("current_gap_or_blocker"),
        )
        recovered_runtime_ready = self._host_twin_recovered_runtime_ready(
            host_contract={
                "handoff_state": explicit_handoff_state,
                "handoff_owner_ref": self._first_string(
                    session_metadata.get("handoff_owner_ref"),
                    mount_metadata.get("handoff_owner_ref"),
                    runtime_descriptor.get("handoff_owner_ref"),
                    live_descriptor.get("handoff_owner_ref"),
                ),
                "handoff_reason": explicit_handoff_reason,
                "current_gap_or_blocker": explicit_current_gap,
            },
            recovery=recovery,
            host_event_summary=host_event_summary,
        )
        current_gap = self._first_string(
            explicit_current_gap,
            (
                self._host_event_gap_or_blocker(blocker_event)
                if not recovered_runtime_ready
                else None
            ),
        )
        if current_gap is None:
            recovery_note = self._first_string(recovery.get("note"))
            recovery_status = self._first_string(recovery.get("status"))
            if recovery_note and recovery_status not in {"attached", "restorable"}:
                current_gap = recovery_note
        return {
            "projection_kind": "host_contract_projection",
            "is_projection": True,
            "surface_kind": getattr(mount, "kind", None) if mount is not None else None,
            "environment_id": getattr(mount, "id", None) if mount is not None else None,
            "session_mount_id": session.id if session is not None else None,
            "host_mode": self._first_string(
                session_metadata.get("host_mode"),
                mount_metadata.get("host_mode"),
                runtime_descriptor.get("host_mode"),
                live_descriptor.get("host_mode"),
            ),
            "lease_class": self._first_string(
                session_metadata.get("lease_class"),
                mount_metadata.get("lease_class"),
                runtime_descriptor.get("lease_class"),
                live_descriptor.get("lease_class"),
            ),
            "access_mode": self._first_string(
                session_metadata.get("access_mode"),
                mount_metadata.get("access_mode"),
                runtime_descriptor.get("access_mode"),
                live_descriptor.get("access_mode"),
            ),
            "session_scope": self._first_string(
                session_metadata.get("session_scope"),
                mount_metadata.get("session_scope"),
                runtime_descriptor.get("session_scope"),
                live_descriptor.get("session_scope"),
            ),
            "work_context_id": self._first_string(
                session_metadata.get("work_context_id"),
                mount_metadata.get("work_context_id"),
                runtime_descriptor.get("work_context_id"),
                live_descriptor.get("work_context_id"),
            ),
            "account_scope_ref": self._first_string(
                session_metadata.get("account_scope_ref"),
                mount_metadata.get("account_scope_ref"),
                runtime_descriptor.get("account_scope_ref"),
                live_descriptor.get("account_scope_ref"),
            ),
            "handoff_state": self._first_string(
                explicit_handoff_state,
                (
                    self._host_event_handoff_state(blocker_event)
                    if not recovered_runtime_ready
                    else None
                ),
            ),
            "handoff_reason": self._first_string(
                explicit_handoff_reason,
                (
                    self._host_event_gap_or_blocker(blocker_event)
                    if explicit_handoff_state is None and not recovered_runtime_ready
                    else None
                ),
            ),
            "handoff_owner_ref": self._first_string(
                session_metadata.get("handoff_owner_ref"),
                mount_metadata.get("handoff_owner_ref"),
                runtime_descriptor.get("handoff_owner_ref"),
                live_descriptor.get("handoff_owner_ref"),
            ),
            "resume_kind": self._first_string(
                session_metadata.get("resume_kind"),
                mount_metadata.get("resume_kind"),
                runtime_descriptor.get("resume_kind"),
                live_descriptor.get("resume_kind"),
                self._recovery_resume_kind(recovery),
            ),
            "verification_channel": self._first_string(
                session_metadata.get("verification_channel"),
                mount_metadata.get("verification_channel"),
                runtime_descriptor.get("verification_channel"),
                live_descriptor.get("verification_channel"),
            ),
            "capability_summary": self._merge_string_lists(
                session_metadata.get("capability_summary"),
                mount_metadata.get("capability_summary"),
                runtime_descriptor.get("capability_summary"),
                live_descriptor.get("capability_summary"),
            ),
            "current_gap_or_blocker": current_gap,
            "lease_status": (
                session.lease_status
                if session is not None
                else (getattr(mount, "lease_status", None) if mount is not None else None)
            ),
            "lease_owner": (
                session.lease_owner
                if session is not None
                else (getattr(mount, "lease_owner", None) if mount is not None else None)
            ),
            "host_id": self._first_string(
                self._mapping(live_handle).get("host_id"),
                recovery.get("host_id"),
                runtime_metadata.get("host_id"),
            ),
            "process_id": self._normalize_process_id(
                self._mapping(live_handle).get("process_id")
                or recovery.get("process_id")
                or runtime_metadata.get("process_id"),
            ),
            "projection_note": (
                "Derived from EnvironmentMount/SessionMount metadata, lease runtime, "
                "live-handle info, and recovery projection."
            ),
        }

    def build_browser_site_contract_projection(
        self,
        *,
        mount,
        session: SessionMount | None,
        live_handle: dict[str, object] | None,
        recovery: dict[str, object],
        host_contract: dict[str, object],
        host_companion_session: dict[str, object],
        host_event_summary: dict[str, object],
    ) -> dict[str, object]:
        (
            mount_metadata,
            session_metadata,
            _runtime_metadata,
            runtime_descriptor,
            live_descriptor,
        ) = self._surface_runtime_context(
            mount=mount,
            session=session,
            live_handle=live_handle,
        )
        browser_context_refs = self._merge_string_lists(
            session_metadata.get("browser_context_refs"),
            mount_metadata.get("browser_context_refs"),
            runtime_descriptor.get("browser_context_refs"),
            [runtime_descriptor.get("browser"), runtime_descriptor.get("page_id")],
            [live_descriptor.get("browser"), live_descriptor.get("page_id")],
        )
        active_tab_ref = self._first_string(
            session_metadata.get("active_tab_ref"),
            mount_metadata.get("active_tab_ref"),
            runtime_descriptor.get("active_tab_ref"),
            runtime_descriptor.get("page_id"),
            live_descriptor.get("active_tab_ref"),
            live_descriptor.get("page_id"),
        )
        if active_tab_ref is None and browser_context_refs:
            active_tab_ref = browser_context_refs[-1]
        tab_scope = self._first_string(
            session_metadata.get("tab_scope"),
            mount_metadata.get("tab_scope"),
            runtime_descriptor.get("tab_scope"),
            live_descriptor.get("tab_scope"),
        )
        navigation = self._first_bool(
            session_metadata.get("navigation"),
            mount_metadata.get("navigation"),
            runtime_descriptor.get("navigation"),
            live_descriptor.get("navigation"),
        )
        if navigation is None and (active_tab_ref is not None or browser_context_refs):
            navigation = True
        dom_interaction = self._first_bool(
            session_metadata.get("dom_interaction"),
            mount_metadata.get("dom_interaction"),
            runtime_descriptor.get("dom_interaction"),
            live_descriptor.get("dom_interaction"),
        )
        if dom_interaction is None and active_tab_ref is not None:
            dom_interaction = True
        multi_tab = self._first_bool(
            session_metadata.get("multi_tab"),
            mount_metadata.get("multi_tab"),
            runtime_descriptor.get("multi_tab"),
            live_descriptor.get("multi_tab"),
        )
        if multi_tab is None:
            multi_tab = len(browser_context_refs) > 1 or (
                isinstance(tab_scope, str)
                and tab_scope.strip().lower() in {"multi-tab", "session-tabs", "window-tabs"}
            )
        login_state = self._first_string(
            session_metadata.get("login_state"),
            mount_metadata.get("login_state"),
            runtime_descriptor.get("login_state"),
            live_descriptor.get("login_state"),
        )
        download_policy = self._first_string(
            session_metadata.get("download_policy"),
            mount_metadata.get("download_policy"),
            runtime_descriptor.get("download_policy"),
            live_descriptor.get("download_policy"),
        )
        continuity_status = self._first_string(
            host_companion_session.get("continuity_status"),
        )
        download_bucket_refs = self._merge_string_lists(
            session_metadata.get("download_bucket_refs"),
            mount_metadata.get("download_bucket_refs"),
            runtime_descriptor.get("download_bucket_refs"),
            live_descriptor.get("download_bucket_refs"),
            [download_policy],
        )
        authenticated_continuation = self._first_bool(
            session_metadata.get("authenticated_continuation"),
            mount_metadata.get("authenticated_continuation"),
            runtime_descriptor.get("authenticated_continuation"),
            live_descriptor.get("authenticated_continuation"),
        )
        if authenticated_continuation is None:
            authenticated_continuation = bool(
                login_state is not None
                and login_state.strip().lower()
                in {"authenticated", "attached", "restored", "session-restored"}
            )
        cross_tab_continuation = self._first_bool(
            session_metadata.get("cross_tab_continuation"),
            mount_metadata.get("cross_tab_continuation"),
            runtime_descriptor.get("cross_tab_continuation"),
            live_descriptor.get("cross_tab_continuation"),
        )
        if cross_tab_continuation is None:
            cross_tab_continuation = bool(multi_tab)
        latest_download_event = self._host_event_latest(
            host_event_summary,
            "download-completed",
        )
        download_verification = self._first_bool(
            session_metadata.get("download_verification"),
            mount_metadata.get("download_verification"),
            runtime_descriptor.get("download_verification"),
            live_descriptor.get("download_verification"),
        )
        if download_verification is None:
            download_verification = bool(
                latest_download_event is not None or download_bucket_refs
            )
        last_verified_url = self._first_string(
            session_metadata.get("last_verified_url"),
            mount_metadata.get("last_verified_url"),
            runtime_descriptor.get("last_verified_url"),
            live_descriptor.get("last_verified_url"),
        )
        last_verified_dom_anchor = self._first_string(
            session_metadata.get("last_verified_dom_anchor"),
            mount_metadata.get("last_verified_dom_anchor"),
            runtime_descriptor.get("last_verified_dom_anchor"),
            live_descriptor.get("last_verified_dom_anchor"),
        )
        save_reopen_verification = self._first_bool(
            session_metadata.get("save_reopen_verification"),
            mount_metadata.get("save_reopen_verification"),
            runtime_descriptor.get("save_reopen_verification"),
            live_descriptor.get("save_reopen_verification"),
        )
        if save_reopen_verification is None:
            save_reopen_verification = bool(
                continuity_status in {"attached", "restorable", "same-host-other-process"}
                and self._first_string(
                    active_tab_ref,
                    last_verified_url,
                    last_verified_dom_anchor,
                )
                is not None
            )
        site_contract_ref = self._first_string(
            session_metadata.get("site_contract_ref"),
            mount_metadata.get("site_contract_ref"),
            runtime_descriptor.get("site_contract_ref"),
            live_descriptor.get("site_contract_ref"),
        )
        active_site = self._derive_site_identity(
            self._first_string(
                session_metadata.get("active_site"),
                mount_metadata.get("active_site"),
            ),
            site_contract_ref,
            active_tab_ref,
        )
        navigation_guard = self._first_mapping(
            session_metadata.get("navigation_guard"),
            mount_metadata.get("navigation_guard"),
            runtime_descriptor.get("navigation_guard"),
            live_descriptor.get("navigation_guard"),
        )
        action_timeout_seconds = self._positive_timeout(
            session_metadata.get("action_timeout_seconds"),
            mount_metadata.get("action_timeout_seconds"),
            runtime_descriptor.get("action_timeout_seconds"),
            live_descriptor.get("action_timeout_seconds"),
        )
        return {
            "projection_kind": "browser_site_contract_projection",
            "is_projection": True,
            "environment_id": getattr(mount, "id", None) if mount is not None else None,
            "session_mount_id": session.id if session is not None else None,
            "browser_mode": self._canonical_browser_mode(
                self._first_string(
                    session_metadata.get("browser_mode"),
                    mount_metadata.get("browser_mode"),
                    runtime_descriptor.get("browser_mode"),
                    live_descriptor.get("browser_mode"),
                    host_contract.get("host_mode"),
                ),
            ),
            "tab_scope": tab_scope,
            "login_state": login_state,
            "profile_ref": self._first_string(
                session_metadata.get("profile_ref"),
                mount_metadata.get("profile_ref"),
                runtime_descriptor.get("profile_ref"),
                live_descriptor.get("profile_ref"),
            ),
            "attach_transport_ref": (
                self._first_string(
                    session_metadata.get("browser_attach_transport_ref"),
                    mount_metadata.get("browser_attach_transport_ref"),
                    runtime_descriptor.get("browser_attach_transport_ref"),
                    live_descriptor.get("browser_attach_transport_ref"),
                )
                if any(
                    "browser_attach_transport_ref" in payload
                    for payload in (
                        session_metadata,
                        mount_metadata,
                        runtime_descriptor,
                        live_descriptor,
                    )
                )
                else self._first_string(
                    session_metadata.get("attach_transport_ref"),
                    session_metadata.get("browser_attach_transport_ref"),
                    mount_metadata.get("attach_transport_ref"),
                    mount_metadata.get("browser_attach_transport_ref"),
                    runtime_descriptor.get("attach_transport_ref"),
                    runtime_descriptor.get("browser_attach_transport_ref"),
                    live_descriptor.get("attach_transport_ref"),
                    live_descriptor.get("browser_attach_transport_ref"),
                )
            ),
            "attach_session_ref": self._first_string(
                session_metadata.get("browser_attach_session_ref"),
                mount_metadata.get("browser_attach_session_ref"),
                runtime_descriptor.get("browser_attach_session_ref"),
                live_descriptor.get("browser_attach_session_ref"),
            ),
            "attach_scope_ref": self._first_string(
                session_metadata.get("browser_attach_scope_ref"),
                mount_metadata.get("browser_attach_scope_ref"),
                runtime_descriptor.get("browser_attach_scope_ref"),
                live_descriptor.get("browser_attach_scope_ref"),
            ),
            "attach_reconnect_token": self._first_string(
                session_metadata.get("browser_attach_reconnect_token"),
                mount_metadata.get("browser_attach_reconnect_token"),
                runtime_descriptor.get("browser_attach_reconnect_token"),
                live_descriptor.get("browser_attach_reconnect_token"),
            ),
            "provider_kind": self._first_string(
                session_metadata.get("provider_kind"),
                mount_metadata.get("provider_kind"),
                runtime_descriptor.get("provider_kind"),
                live_descriptor.get("provider_kind"),
            ),
            "provider_session_ref": self._first_string(
                session_metadata.get("provider_session_ref"),
                mount_metadata.get("provider_session_ref"),
                runtime_descriptor.get("provider_session_ref"),
                live_descriptor.get("provider_session_ref"),
            ),
            "navigation_guard": navigation_guard,
            "action_timeout_seconds": action_timeout_seconds,
            "download_policy": download_policy,
            "storage_scope": self._first_string(
                session_metadata.get("storage_scope"),
                mount_metadata.get("storage_scope"),
                runtime_descriptor.get("storage_scope"),
                live_descriptor.get("storage_scope"),
            ),
            "site_contract_ref": site_contract_ref,
            "site_contract_status": self._first_string(
                session_metadata.get("site_contract_status"),
                mount_metadata.get("site_contract_status"),
                runtime_descriptor.get("site_contract_status"),
                live_descriptor.get("site_contract_status"),
            ),
            "site_risk_contract_ref": self._first_string(
                session_metadata.get("site_risk_contract_ref"),
                mount_metadata.get("site_risk_contract_ref"),
                runtime_descriptor.get("site_risk_contract_ref"),
                live_descriptor.get("site_risk_contract_ref"),
            ),
            "account_scope_ref": self._first_string(
                session_metadata.get("account_scope_ref"),
                mount_metadata.get("account_scope_ref"),
                runtime_descriptor.get("account_scope_ref"),
                live_descriptor.get("account_scope_ref"),
                host_contract.get("account_scope_ref"),
            ),
            "handoff_state": self._first_string(
                session_metadata.get("handoff_state"),
                mount_metadata.get("handoff_state"),
                runtime_descriptor.get("handoff_state"),
                live_descriptor.get("handoff_state"),
                host_contract.get("handoff_state"),
            ),
            "handoff_reason": self._first_string(
                session_metadata.get("handoff_reason"),
                mount_metadata.get("handoff_reason"),
                runtime_descriptor.get("handoff_reason"),
                live_descriptor.get("handoff_reason"),
                host_contract.get("handoff_reason"),
            ),
            "handoff_owner_ref": self._first_string(
                session_metadata.get("handoff_owner_ref"),
                mount_metadata.get("handoff_owner_ref"),
                runtime_descriptor.get("handoff_owner_ref"),
                live_descriptor.get("handoff_owner_ref"),
                host_contract.get("handoff_owner_ref"),
            ),
            "resume_kind": self._first_string(
                session_metadata.get("resume_kind"),
                mount_metadata.get("resume_kind"),
                runtime_descriptor.get("resume_kind"),
                live_descriptor.get("resume_kind"),
                host_contract.get("resume_kind"),
            ),
            "manual_resume_required": self._first_bool(
                session_metadata.get("manual_resume_required"),
                mount_metadata.get("manual_resume_required"),
                runtime_descriptor.get("manual_resume_required"),
                live_descriptor.get("manual_resume_required"),
                recovery.get("startup_recovery_required"),
            ),
            "active_tab_ref": active_tab_ref,
            "active_site": active_site,
            "last_verified_url": last_verified_url,
            "last_verified_dom_anchor": last_verified_dom_anchor,
            "navigation": navigation,
            "dom_interaction": dom_interaction,
            "multi_tab": multi_tab,
            "authenticated_continuation": authenticated_continuation,
            "cross_tab_continuation": cross_tab_continuation,
            "uploads": self._first_bool(
                session_metadata.get("uploads"),
                mount_metadata.get("uploads"),
                runtime_descriptor.get("uploads"),
                live_descriptor.get("uploads"),
            ),
            "downloads": self._first_bool(
                session_metadata.get("downloads"),
                mount_metadata.get("downloads"),
                runtime_descriptor.get("downloads"),
                live_descriptor.get("downloads"),
            ),
            "download_bucket_refs": download_bucket_refs,
            "download_verification": download_verification,
            "save_reopen_verification": save_reopen_verification,
            "pdf_export": self._first_bool(
                session_metadata.get("pdf_export"),
                mount_metadata.get("pdf_export"),
                runtime_descriptor.get("pdf_export"),
                live_descriptor.get("pdf_export"),
            ),
            "storage_access": self._first_bool(
                session_metadata.get("storage_access"),
                mount_metadata.get("storage_access"),
                runtime_descriptor.get("storage_access"),
                live_descriptor.get("storage_access"),
            ),
            "locale_timezone_override": self._first_bool(
                session_metadata.get("locale_timezone_override"),
                mount_metadata.get("locale_timezone_override"),
                runtime_descriptor.get("locale_timezone_override"),
                live_descriptor.get("locale_timezone_override"),
            ),
            "continuity_status": continuity_status,
            "continuity_source": self._first_string(
                host_companion_session.get("continuity_source"),
            ),
            "current_gap_or_blocker": self._first_string(
                session_metadata.get("current_gap_or_blocker"),
                mount_metadata.get("current_gap_or_blocker"),
                runtime_descriptor.get("current_gap_or_blocker"),
                live_descriptor.get("current_gap_or_blocker"),
                host_contract.get("current_gap_or_blocker"),
            ),
            "projection_note": (
                "Browser site contract is a surface-specific projection layered over "
                "the shared host contract, not a second browser truth store."
            ),
        }

    def _canonical_browser_mode(self, mode: object) -> str | None:
        normalized = self._first_string(mode)
        if normalized is None:
            return None
        lowered = normalized.strip().lower()
        if lowered in {
            "managed-isolated",
            "attach-existing-session",
            "remote-provider",
        }:
            return lowered
        return self._CANONICAL_BROWSER_MODE_BY_LEGACY.get(lowered, normalized)

    def build_desktop_app_contract_projection(
        self,
        *,
        mount,
        session: SessionMount | None,
        live_handle: dict[str, object] | None,
        recovery: dict[str, object],
        host_contract: dict[str, object],
        host_companion_session: dict[str, object],
        host_event_summary: dict[str, object],
    ) -> dict[str, object]:
        (
            mount_metadata,
            session_metadata,
            _runtime_metadata,
            runtime_descriptor,
            live_descriptor,
        ) = self._surface_runtime_context(
            mount=mount,
            session=session,
            live_handle=live_handle,
        )
        app_window_refs = self._merge_string_lists(
            session_metadata.get("app_window_refs"),
            mount_metadata.get("app_window_refs"),
            [runtime_descriptor.get("active_window_ref"), runtime_descriptor.get("window_scope")],
            [live_descriptor.get("active_window_ref"), live_descriptor.get("window_scope")],
        )
        active_window_ref = self._first_string(
            session_metadata.get("active_window_ref"),
            mount_metadata.get("active_window_ref"),
            runtime_descriptor.get("active_window_ref"),
            live_descriptor.get("active_window_ref"),
        )
        if active_window_ref is None:
            for candidate in app_window_refs:
                if "window" in candidate.lower():
                    active_window_ref = candidate
                    break
        active_process_ref = self._first_string(
            session_metadata.get("active_process_ref"),
            mount_metadata.get("active_process_ref"),
            runtime_descriptor.get("active_process_ref"),
            live_descriptor.get("active_process_ref"),
        )
        if active_process_ref is None and host_contract.get("process_id") is not None:
            active_process_ref = f"process:{host_contract.get('process_id')}"
        continuity_status = self._first_string(
            host_companion_session.get("continuity_status"),
        )
        blocker_event = self._blocking_host_event(host_event_summary)
        app_identity = self._first_string(
            session_metadata.get("app_identity"),
            mount_metadata.get("app_identity"),
            runtime_descriptor.get("app_identity"),
            live_descriptor.get("app_identity"),
            session_metadata.get("app_id"),
            mount_metadata.get("app_id"),
            runtime_descriptor.get("app_id"),
            live_descriptor.get("app_id"),
            session_metadata.get("app_name"),
            mount_metadata.get("app_name"),
            runtime_descriptor.get("app_name"),
            live_descriptor.get("app_name"),
        )
        window_anchor_summary = self._first_string(
            session_metadata.get("window_anchor_summary"),
            mount_metadata.get("window_anchor_summary"),
            runtime_descriptor.get("window_anchor_summary"),
            live_descriptor.get("window_anchor_summary"),
        )
        execution_guardrails = {
            **self._mapping(mount_metadata.get("execution_guardrails")),
            **self._mapping(runtime_descriptor.get("execution_guardrails")),
            **self._mapping(live_descriptor.get("execution_guardrails")),
            **self._mapping(session_metadata.get("execution_guardrails")),
        }
        operator_abort_state = self._build_operator_abort_state_projection(
            session_metadata.get("operator_abort_state"),
            mount_metadata.get("operator_abort_state"),
            runtime_descriptor.get("operator_abort_state"),
            live_descriptor.get("operator_abort_state"),
        )
        execution_guardrails = self._merge_operator_abort_guardrails_projection(
            execution_guardrails,
            operator_abort_state,
        )
        current_gap_or_blocker = self._first_string(
            session_metadata.get("current_gap_or_blocker"),
            mount_metadata.get("current_gap_or_blocker"),
            runtime_descriptor.get("current_gap_or_blocker"),
            live_descriptor.get("current_gap_or_blocker"),
            host_contract.get("current_gap_or_blocker"),
            self._host_event_gap_or_blocker(blocker_event),
        )
        save_reopen_verification = self._first_bool(
            session_metadata.get("save_reopen_verification"),
            mount_metadata.get("save_reopen_verification"),
            runtime_descriptor.get("save_reopen_verification"),
            live_descriptor.get("save_reopen_verification"),
        )
        if save_reopen_verification is None:
            save_reopen_verification = bool(
                continuity_status in {"attached", "restorable", "same-host-other-process"}
                and window_anchor_summary is not None
            )
        return {
            "projection_kind": "desktop_app_contract_projection",
            "is_projection": True,
            "environment_id": getattr(mount, "id", None) if mount is not None else None,
            "session_mount_id": session.id if session is not None else None,
            "app_identity": self._sanitize_prompt_facing_host_label(app_identity),
            "window_scope": self._first_string(
                session_metadata.get("window_scope"),
                mount_metadata.get("window_scope"),
                runtime_descriptor.get("window_scope"),
                live_descriptor.get("window_scope"),
            ),
            "active_window_ref": active_window_ref,
            "active_process_ref": active_process_ref,
            "control_channel": self._first_string(
                session_metadata.get("control_channel"),
                mount_metadata.get("control_channel"),
                runtime_descriptor.get("control_channel"),
                live_descriptor.get("control_channel"),
            ),
            "app_contract_ref": self._first_string(
                session_metadata.get("app_contract_ref"),
                mount_metadata.get("app_contract_ref"),
                runtime_descriptor.get("app_contract_ref"),
                live_descriptor.get("app_contract_ref"),
            ),
            "app_contract_status": self._first_string(
                session_metadata.get("app_contract_status"),
                mount_metadata.get("app_contract_status"),
                runtime_descriptor.get("app_contract_status"),
                live_descriptor.get("app_contract_status"),
            ),
            "writer_lock_scope": self._first_string(
                session_metadata.get("writer_lock_scope"),
                mount_metadata.get("writer_lock_scope"),
                runtime_descriptor.get("writer_lock_scope"),
                live_descriptor.get("writer_lock_scope"),
            ),
            "window_anchor_summary": self._sanitize_window_anchor_summary(
                window_anchor_summary,
            ),
            "execution_guardrails": execution_guardrails,
            "operator_abort_state": operator_abort_state,
            "account_scope_ref": self._first_string(
                session_metadata.get("account_scope_ref"),
                mount_metadata.get("account_scope_ref"),
                runtime_descriptor.get("account_scope_ref"),
                live_descriptor.get("account_scope_ref"),
                host_contract.get("account_scope_ref"),
            ),
            "handoff_state": self._first_string(
                session_metadata.get("handoff_state"),
                mount_metadata.get("handoff_state"),
                runtime_descriptor.get("handoff_state"),
                live_descriptor.get("handoff_state"),
                host_contract.get("handoff_state"),
            ),
            "handoff_reason": self._first_string(
                session_metadata.get("handoff_reason"),
                mount_metadata.get("handoff_reason"),
                runtime_descriptor.get("handoff_reason"),
                live_descriptor.get("handoff_reason"),
                host_contract.get("handoff_reason"),
            ),
            "handoff_owner_ref": self._first_string(
                session_metadata.get("handoff_owner_ref"),
                mount_metadata.get("handoff_owner_ref"),
                runtime_descriptor.get("handoff_owner_ref"),
                live_descriptor.get("handoff_owner_ref"),
                host_contract.get("handoff_owner_ref"),
            ),
            "resume_kind": self._first_string(
                session_metadata.get("resume_kind"),
                mount_metadata.get("resume_kind"),
                runtime_descriptor.get("resume_kind"),
                live_descriptor.get("resume_kind"),
                host_contract.get("resume_kind"),
            ),
            "manual_resume_required": self._first_bool(
                session_metadata.get("manual_resume_required"),
                mount_metadata.get("manual_resume_required"),
                runtime_descriptor.get("manual_resume_required"),
                live_descriptor.get("manual_resume_required"),
                recovery.get("startup_recovery_required"),
            ),
            "recovery_status": self._first_string(
                recovery.get("status"),
            ),
            "recovery_mode": self._first_string(
                recovery.get("mode"),
                recovery.get("resume_kind"),
            ),
            "save_reopen_verification": save_reopen_verification,
            "blocker_event_family": self._first_string(
                blocker_event.get("event_family") if blocker_event is not None else None,
            ),
            "continuity_status": continuity_status,
            "continuity_source": self._first_string(
                host_companion_session.get("continuity_source"),
            ),
            "current_gap_or_blocker": current_gap_or_blocker,
            "projection_note": (
                "Desktop app contract is a Windows-first app/window projection layered "
                "over the shared host contract."
            ),
        }

    def build_cooperative_adapter_availability_projection(
        self,
        *,
        mount,
        session: SessionMount | None,
        live_handle: dict[str, object] | None,
        host_contract: dict[str, object],
        browser_site_contract: dict[str, object],
        desktop_app_contract: dict[str, object],
    ) -> dict[str, object]:
        (
            mount_metadata,
            session_metadata,
            _runtime_metadata,
            runtime_descriptor,
            live_descriptor,
        ) = self._surface_runtime_context(
            mount=mount,
            session=session,
            live_handle=live_handle,
        )

        browser_transport_ref = self._first_string(
            session_metadata.get("browser_companion_transport_ref"),
            mount_metadata.get("browser_companion_transport_ref"),
            runtime_descriptor.get("browser_companion_transport_ref"),
            live_descriptor.get("browser_companion_transport_ref"),
            browser_site_contract.get("attach_transport_ref"),
        )
        browser_companion_status = self._first_string(
            session_metadata.get("browser_companion_status"),
            mount_metadata.get("browser_companion_status"),
            runtime_descriptor.get("browser_companion_status"),
            live_descriptor.get("browser_companion_status"),
        )
        browser_companion_available = self._first_bool(
            session_metadata.get("browser_companion_available"),
            mount_metadata.get("browser_companion_available"),
            runtime_descriptor.get("browser_companion_available"),
            live_descriptor.get("browser_companion_available"),
        )
        if browser_companion_available is None:
            browser_companion_available = bool(browser_transport_ref) or (
                browser_companion_status is not None
                and browser_companion_status.strip().lower()
                in {"ready", "attached", "available", "healthy"}
            )
        operator_abort_state = self._build_operator_abort_state_projection(
            session_metadata.get("operator_abort_state"),
            mount_metadata.get("operator_abort_state"),
            runtime_descriptor.get("operator_abort_state"),
            live_descriptor.get("operator_abort_state"),
        )
        browser_execution_guardrails = {
            **self._mapping(mount_metadata.get("browser_execution_guardrails")),
            **self._mapping(runtime_descriptor.get("browser_execution_guardrails")),
            **self._mapping(live_descriptor.get("browser_execution_guardrails")),
            **self._mapping(session_metadata.get("browser_execution_guardrails")),
        }
        browser_execution_guardrails = self._merge_operator_abort_guardrails_projection(
            browser_execution_guardrails,
            operator_abort_state,
        )

        document_bridge_ref = self._first_string(
            session_metadata.get("document_bridge_ref"),
            mount_metadata.get("document_bridge_ref"),
            runtime_descriptor.get("document_bridge_ref"),
            live_descriptor.get("document_bridge_ref"),
        )
        document_bridge_status = self._first_string(
            session_metadata.get("document_bridge_status"),
            mount_metadata.get("document_bridge_status"),
            runtime_descriptor.get("document_bridge_status"),
            live_descriptor.get("document_bridge_status"),
        )
        document_bridge_available = self._first_bool(
            session_metadata.get("document_bridge_available"),
            mount_metadata.get("document_bridge_available"),
            runtime_descriptor.get("document_bridge_available"),
            live_descriptor.get("document_bridge_available"),
        )
        if document_bridge_available is None:
            document_bridge_available = bool(document_bridge_ref) or (
                document_bridge_status is not None
                and document_bridge_status.strip().lower()
                in {"ready", "available", "healthy"}
            )
        document_execution_guardrails = {
            **self._mapping(mount_metadata.get("document_execution_guardrails")),
            **self._mapping(runtime_descriptor.get("document_execution_guardrails")),
            **self._mapping(live_descriptor.get("document_execution_guardrails")),
            **self._mapping(session_metadata.get("document_execution_guardrails")),
        }
        document_execution_guardrails = self._merge_operator_abort_guardrails_projection(
            document_execution_guardrails,
            operator_abort_state,
        )

        filesystem_watcher_status = self._first_string(
            session_metadata.get("filesystem_watcher_status"),
            mount_metadata.get("filesystem_watcher_status"),
            runtime_descriptor.get("filesystem_watcher_status"),
            live_descriptor.get("filesystem_watcher_status"),
        )
        filesystem_watcher_available = self._first_bool(
            session_metadata.get("filesystem_watcher_available"),
            mount_metadata.get("filesystem_watcher_available"),
            runtime_descriptor.get("filesystem_watcher_available"),
            live_descriptor.get("filesystem_watcher_available"),
        )
        if filesystem_watcher_available is None and filesystem_watcher_status is not None:
            filesystem_watcher_available = filesystem_watcher_status.strip().lower() in {
                "ready",
                "available",
                "healthy",
            }

        download_watcher_status = self._first_string(
            session_metadata.get("download_watcher_status"),
            mount_metadata.get("download_watcher_status"),
            runtime_descriptor.get("download_watcher_status"),
            live_descriptor.get("download_watcher_status"),
        )
        download_watcher_available = self._first_bool(
            session_metadata.get("download_watcher_available"),
            mount_metadata.get("download_watcher_available"),
            runtime_descriptor.get("download_watcher_available"),
            live_descriptor.get("download_watcher_available"),
        )
        if download_watcher_available is None and download_watcher_status is not None:
            download_watcher_available = download_watcher_status.strip().lower() in {
                "ready",
                "available",
                "healthy",
            }

        notification_watcher_status = self._first_string(
            session_metadata.get("notification_watcher_status"),
            mount_metadata.get("notification_watcher_status"),
            runtime_descriptor.get("notification_watcher_status"),
            live_descriptor.get("notification_watcher_status"),
        )
        notification_watcher_available = self._first_bool(
            session_metadata.get("notification_watcher_available"),
            mount_metadata.get("notification_watcher_available"),
            runtime_descriptor.get("notification_watcher_available"),
            live_descriptor.get("notification_watcher_available"),
        )
        if notification_watcher_available is None and notification_watcher_status is not None:
            notification_watcher_available = notification_watcher_status.strip().lower() in {
                "ready",
                "available",
                "healthy",
            }

        app_adapter_refs = self._merge_string_lists(
            session_metadata.get("windows_app_adapter_refs"),
            mount_metadata.get("windows_app_adapter_refs"),
            runtime_descriptor.get("windows_app_adapter_refs"),
            live_descriptor.get("windows_app_adapter_refs"),
            session_metadata.get("app_adapter_refs"),
            mount_metadata.get("app_adapter_refs"),
            runtime_descriptor.get("app_adapter_refs"),
            live_descriptor.get("app_adapter_refs"),
        )
        execution_guardrails = {
            **self._mapping(mount_metadata.get("execution_guardrails")),
            **self._mapping(runtime_descriptor.get("execution_guardrails")),
            **self._mapping(live_descriptor.get("execution_guardrails")),
            **self._mapping(session_metadata.get("execution_guardrails")),
        }
        execution_guardrails = self._merge_operator_abort_guardrails_projection(
            execution_guardrails,
            operator_abort_state,
        )
        preferred_path = self._first_string(
            session_metadata.get("preferred_execution_path"),
            mount_metadata.get("preferred_execution_path"),
            runtime_descriptor.get("preferred_execution_path"),
            live_descriptor.get("preferred_execution_path"),
        ) or "cooperative-native-first"
        fallback_mode = self._first_string(
            session_metadata.get("ui_fallback_mode"),
            mount_metadata.get("ui_fallback_mode"),
            runtime_descriptor.get("ui_fallback_mode"),
            live_descriptor.get("ui_fallback_mode"),
        ) or "ui-fallback-last"

        family_pairs = [
            ("browser-companion", browser_companion_available),
            ("document-bridge", document_bridge_available),
            ("filesystem-watcher", filesystem_watcher_available),
            ("download-watcher", download_watcher_available),
            ("notification-watcher", notification_watcher_available),
            ("windows-app-adapters", bool(app_adapter_refs)),
        ]
        available_families = [name for name, available in family_pairs if available is True]
        unavailable_families = [name for name, available in family_pairs if available is False]

        current_gap = self._first_string(
            session_metadata.get("adapter_gap_or_blocker"),
            mount_metadata.get("adapter_gap_or_blocker"),
            runtime_descriptor.get("adapter_gap_or_blocker"),
            live_descriptor.get("adapter_gap_or_blocker"),
        )
        if current_gap is None and not available_families:
            current_gap = "No cooperative adapters are currently available; UI fallback remains primary."

        return {
            "projection_kind": "cooperative_adapter_availability_projection",
            "is_projection": True,
            "environment_id": getattr(mount, "id", None) if mount is not None else None,
            "session_mount_id": session.id if session is not None else None,
            "preferred_execution_path": preferred_path,
            "fallback_mode": fallback_mode,
            "operator_abort_state": operator_abort_state,
            "browser_companion": {
                "available": browser_companion_available,
                "status": browser_companion_status,
                "transport_ref": browser_transport_ref,
                "provider_session_ref": browser_site_contract.get("provider_session_ref"),
                "execution_guardrails": browser_execution_guardrails,
            },
            "document_bridge": {
                "available": document_bridge_available,
                "status": document_bridge_status,
                "bridge_ref": document_bridge_ref,
                "supported_families": self._merge_string_lists(
                    session_metadata.get("document_bridge_supported_families"),
                    mount_metadata.get("document_bridge_supported_families"),
                    runtime_descriptor.get("document_bridge_supported_families"),
                    live_descriptor.get("document_bridge_supported_families"),
                ),
                "execution_guardrails": document_execution_guardrails,
            },
            "watchers": {
                "filesystem": {
                    "available": filesystem_watcher_available,
                    "status": filesystem_watcher_status,
                },
                "downloads": {
                    "available": download_watcher_available,
                    "status": download_watcher_status,
                    "download_policy": browser_site_contract.get("download_policy"),
                },
                "notifications": {
                    "available": notification_watcher_available,
                    "status": notification_watcher_status,
                },
            },
            "windows_app_adapters": {
                "available": bool(app_adapter_refs),
                "adapter_refs": app_adapter_refs,
                "app_identity": desktop_app_contract.get("app_identity"),
                "control_channel": desktop_app_contract.get("control_channel"),
                "execution_guardrails": execution_guardrails,
            },
            "available_families": available_families,
            "unavailable_families": unavailable_families,
            "host_mode": host_contract.get("host_mode"),
            "current_gap_or_blocker": current_gap,
            "projection_note": (
                "Cooperative adapter availability is a runtime visibility projection "
                "over mounts, live handles, and surface contracts; it is not a new "
                "truth store."
            ),
        }

    def build_seat_runtime_projection(
        self,
        *,
        mount,
        session: SessionMount | None,
        host_contract: dict[str, object],
        host_companion_session: dict[str, object],
        live_handle: dict[str, object] | None,
        session_count: int,
        multi_seat_context: dict[str, object] | None = None,
    ) -> dict[str, object]:
        mount_metadata = self._mapping(getattr(mount, "metadata", None))
        session_metadata = self._mapping(session.metadata if session is not None else None)
        live_handle_mapping = self._mapping(live_handle)
        live_descriptor = self._mapping(live_handle_mapping.get("descriptor"))
        bridge_registration = self._build_bridge_registration_projection(
            session_metadata,
            mount_metadata,
            live_handle_mapping,
            live_descriptor,
        )
        active_surface_mix = self._string_list(
            session_metadata.get("active_surface_mix"),
        ) or self._string_list(mount_metadata.get("active_surface_mix"))
        if not active_surface_mix and mount is not None:
            active_surface_mix = [str(mount.kind)]
        seat_ref = getattr(mount, "id", None) if mount is not None else None
        lease_status = self._first_string(host_contract.get("lease_status"))
        status = "inactive"
        if lease_status in {"leased", "idle"} or session is not None:
            status = "active"
        occupancy_state = "available"
        if session is not None or self._first_string(host_contract.get("lease_owner")) is not None:
            occupancy_state = "occupied"
        multi_seat_context = self._mapping(multi_seat_context)
        candidate_seat_refs = self._string_list(multi_seat_context.get("candidate_seat_refs"))
        if not candidate_seat_refs and seat_ref is not None:
            candidate_seat_refs = [seat_ref]
        candidate_seats = [
            self._mapping(item)
            for item in list(multi_seat_context.get("candidate_seats") or [])
            if isinstance(item, dict)
        ]
        selected_seat_ref = self._first_string(
            multi_seat_context.get("selected_seat_ref"),
            seat_ref,
        )
        selected_session_mount_id = self._first_string(
            multi_seat_context.get("selected_session_mount_id"),
            session.id if session is not None else None,
        )
        seat_selection_policy = self._first_string(
            multi_seat_context.get("seat_selection_policy"),
            "sticky-active-seat" if session is not None else "current-seat-only",
        )
        candidate_count = multi_seat_context.get("seat_count")
        if not isinstance(candidate_count, int):
            candidate_count = len(candidate_seat_refs) or max(0, int(session_count))
        return {
            "projection_kind": "seat_runtime_projection",
            "is_projection": True,
            "seat_ref": seat_ref,
            "environment_ref": getattr(mount, "ref", None) if mount is not None else None,
            "workspace_scope": self._first_string(
                session_metadata.get("workspace_scope"),
                mount_metadata.get("workspace_scope"),
            ),
            "work_context_id": self._first_string(
                session_metadata.get("work_context_id"),
                mount_metadata.get("work_context_id"),
                host_contract.get("work_context_id"),
            ),
            "session_scope": host_contract.get("session_scope"),
            "host_mode": host_contract.get("host_mode"),
            "lease_status": host_contract.get("lease_status"),
            "lease_owner": host_contract.get("lease_owner"),
            "host_id": host_contract.get("host_id"),
            "process_id": host_contract.get("process_id"),
            "session_count": max(0, int(candidate_count)),
            "active_session_mount_id": session.id if session is not None else None,
            "host_companion_status": host_companion_session.get("continuity_status"),
            "active_surface_mix": active_surface_mix,
            "status": status,
            "occupancy_state": occupancy_state,
            "bridge_registration": bridge_registration,
            "candidate_seat_refs": candidate_seat_refs,
            "candidate_seats": candidate_seats,
            "selected_seat_ref": selected_seat_ref,
            "selected_session_mount_id": selected_session_mount_id,
            "seat_selection_policy": seat_selection_policy,
            "expected_release_at": (
                session.lease_expires_at.isoformat()
                if session is not None and session.lease_expires_at is not None
                else (
                    mount.lease_expires_at.isoformat()
                    if mount is not None and getattr(mount, "lease_expires_at", None) is not None
                    else None
                )
            ),
            "live_handle_ref": (
                self._first_string(self._mapping(live_handle).get("ref"))
                if live_handle is not None
                else None
            ),
            "projection_note": (
                "Seat runtime is a durable execution-seat projection, not a second "
                "stored runtime object."
            ),
        }

    def _build_multi_seat_context(
        self,
        *,
        mount,
        session: SessionMount | None,
        host_contract: dict[str, object],
    ) -> dict[str, object]:
        current_seat_ref = self._first_string(
            getattr(mount, "id", None) if mount is not None else None,
        )
        current_session_mount_id = self._first_string(
            session.id if session is not None else None,
        )
        mount_metadata = self._mapping(getattr(mount, "metadata", None))
        session_metadata = self._mapping(session.metadata if session is not None else None)
        scope = {
            "work_context_id": self._first_string(
                session_metadata.get("work_context_id"),
                mount_metadata.get("work_context_id"),
                host_contract.get("work_context_id"),
            ),
            "workspace_scope": self._first_string(
                session_metadata.get("workspace_scope"),
                mount_metadata.get("workspace_scope"),
            ),
            "account_scope_ref": self._first_string(
                session_metadata.get("account_scope_ref"),
                mount_metadata.get("account_scope_ref"),
                host_contract.get("account_scope_ref"),
            ),
            "writer_lock_scope": self._first_string(
                session_metadata.get("writer_lock_scope"),
                mount_metadata.get("writer_lock_scope"),
            ),
        }
        current_owner_ref = self._first_string(
            getattr(session, "lease_owner", None) if session is not None else None,
            getattr(mount, "lease_owner", None) if mount is not None else None,
            host_contract.get("lease_owner"),
        )
        raw_sessions = self._service.list_sessions(limit=None)
        candidates: list[dict[str, object]] = []
        seen_seat_refs: set[str] = set()
        for candidate_session in raw_sessions:
            candidate_mount = self._service.get_environment(candidate_session.environment_id)
            if candidate_mount is None:
                continue
            if not self._matches_multi_seat_scope(
                session=candidate_session,
                mount=candidate_mount,
                scope=scope,
                current_seat_ref=current_seat_ref,
                current_session_mount_id=current_session_mount_id,
            ):
                continue
            entry = self._build_multi_seat_candidate_entry(
                session=candidate_session,
                mount=candidate_mount,
            )
            seat_ref = self._first_string(entry.get("seat_ref"))
            if seat_ref is None or seat_ref in seen_seat_refs:
                continue
            seen_seat_refs.add(seat_ref)
            candidates.append(entry)
        if not candidates and current_seat_ref is not None:
            candidates.append(
                {
                    "seat_ref": current_seat_ref,
                    "environment_id": current_seat_ref,
                    "environment_ref": getattr(mount, "ref", None) if mount is not None else None,
                    "session_mount_id": current_session_mount_id,
                    "owner_agent_id": current_owner_ref,
                    "writer_lock_scope": scope["writer_lock_scope"],
                    "workspace_scope": scope["workspace_scope"],
                    "account_scope_ref": scope["account_scope_ref"],
                    "ready": True,
                }
            )
        current_candidate = next(
            (
                item
                for item in candidates
                if self._first_string(item.get("session_mount_id")) == current_session_mount_id
            ),
            None,
        )
        ready_candidates = [item for item in candidates if item.get("ready") is True]
        same_owner_ready = [
            item
            for item in ready_candidates
            if self._first_string(item.get("owner_agent_id")) == current_owner_ref
        ]
        selected_candidate = None
        seat_selection_policy = "current-seat-only"
        if current_candidate is not None and current_candidate.get("ready") is True:
            selected_candidate = current_candidate
            seat_selection_policy = "sticky-active-seat"
        elif same_owner_ready:
            selected_candidate = sorted(
                same_owner_ready,
                key=lambda item: (
                    0
                    if self._first_string(item.get("session_mount_id")) == current_session_mount_id
                    else 1,
                    self._first_string(item.get("seat_ref")) or "",
                ),
            )[0]
            seat_selection_policy = "prefer-ready-seat"
        elif ready_candidates:
            selected_candidate = sorted(
                ready_candidates,
                key=lambda item: (
                    self._first_string(item.get("owner_agent_id")) != current_owner_ref,
                    self._first_string(item.get("seat_ref")) or "",
                ),
            )[0]
            seat_selection_policy = "prefer-ready-seat"
        elif current_candidate is not None:
            selected_candidate = current_candidate
            seat_selection_policy = "sticky-active-seat"
        elif candidates:
            selected_candidate = candidates[0]
            seat_selection_policy = "candidate-seat-fallback"
        candidate_seat_refs = [
            self._first_string(item.get("seat_ref"))
            for item in candidates
            if self._first_string(item.get("seat_ref")) is not None
        ]
        return {
            "seat_count": len(candidate_seat_refs),
            "candidate_seat_refs": candidate_seat_refs,
            "candidate_seats": candidates,
            "selected_seat_ref": self._first_string(
                selected_candidate.get("seat_ref") if isinstance(selected_candidate, dict) else None,
                current_seat_ref,
            ),
            "selected_session_mount_id": self._first_string(
                selected_candidate.get("session_mount_id")
                if isinstance(selected_candidate, dict)
                else None,
                current_session_mount_id,
            ),
            "seat_selection_policy": seat_selection_policy,
        }

    def _matches_multi_seat_scope(
        self,
        *,
        session: SessionMount,
        mount,
        scope: dict[str, object],
        current_seat_ref: str | None,
        current_session_mount_id: str | None,
    ) -> bool:
        candidate_session_mount_id = self._first_string(session.id)
        candidate_seat_ref = self._first_string(
            getattr(mount, "id", None) if mount is not None else None,
        )
        if candidate_session_mount_id == current_session_mount_id:
            return True
        if candidate_seat_ref == current_seat_ref:
            return True
        candidate_mount_metadata = self._mapping(getattr(mount, "metadata", None))
        candidate_session_metadata = self._mapping(session.metadata)
        candidate_workspace_scope = self._first_string(
            candidate_session_metadata.get("workspace_scope"),
            candidate_mount_metadata.get("workspace_scope"),
        )
        candidate_account_scope_ref = self._first_string(
            candidate_session_metadata.get("account_scope_ref"),
            candidate_mount_metadata.get("account_scope_ref"),
        )
        candidate_writer_lock_scope = self._first_string(
            candidate_session_metadata.get("writer_lock_scope"),
            candidate_mount_metadata.get("writer_lock_scope"),
        )
        candidate_work_context_id = self._first_string(
            candidate_session_metadata.get("work_context_id"),
            candidate_mount_metadata.get("work_context_id"),
        )
        work_context_id = self._first_string(scope.get("work_context_id"))
        if work_context_id is not None:
            return candidate_work_context_id == work_context_id
        workspace_scope = self._first_string(scope.get("workspace_scope"))
        account_scope_ref = self._first_string(scope.get("account_scope_ref"))
        writer_lock_scope = self._first_string(scope.get("writer_lock_scope"))
        return bool(
            (workspace_scope is not None and candidate_workspace_scope == workspace_scope)
            or (
                account_scope_ref is not None
                and candidate_account_scope_ref == account_scope_ref
            )
            or (
                writer_lock_scope is not None
                and candidate_writer_lock_scope == writer_lock_scope
            )
        )

    def _build_multi_seat_candidate_entry(
        self,
        *,
        session: SessionMount,
        mount,
    ) -> dict[str, object]:
        mount_metadata = self._mapping(getattr(mount, "metadata", None))
        session_metadata = self._mapping(session.metadata)
        handoff_state = self._first_string(
            session_metadata.get("handoff_state"),
            mount_metadata.get("handoff_state"),
        )
        handoff_owner_ref = self._first_string(
            session_metadata.get("handoff_owner_ref"),
            mount_metadata.get("handoff_owner_ref"),
        )
        gap = self._first_string(
            session_metadata.get("current_gap_or_blocker"),
            mount_metadata.get("current_gap_or_blocker"),
            session_metadata.get("pending_handoff_summary"),
            mount_metadata.get("pending_handoff_summary"),
        )
        contract_status = self._first_string(
            session_metadata.get("app_contract_status"),
            session_metadata.get("site_contract_status"),
            mount_metadata.get("app_contract_status"),
            mount_metadata.get("site_contract_status"),
        )
        access_mode = self._first_string(
            session_metadata.get("access_mode"),
            mount_metadata.get("access_mode"),
        )
        ready = bool(
            (session.status == "active" or self._first_string(session.lease_status) in {"leased", "idle"})
            and handoff_state not in {"active", "manual-only-terminal"}
            and handoff_owner_ref is None
            and gap is None
            and access_mode not in {"missing", "read-only"}
            and contract_status not in {"blocked", "handoff-required", "read-only"}
        )
        return {
            "seat_ref": self._first_string(
                getattr(mount, "id", None) if mount is not None else None,
            ),
            "environment_id": self._first_string(
                getattr(mount, "id", None) if mount is not None else None,
            ),
            "environment_ref": self._first_string(
                getattr(mount, "ref", None) if mount is not None else None,
            ),
            "session_mount_id": self._first_string(session.id),
            "owner_agent_id": self._first_string(
                session.lease_owner,
                getattr(mount, "lease_owner", None) if mount is not None else None,
            ),
            "workspace_scope": self._first_string(
                session_metadata.get("workspace_scope"),
                mount_metadata.get("workspace_scope"),
            ),
            "work_context_id": self._first_string(
                session_metadata.get("work_context_id"),
                mount_metadata.get("work_context_id"),
            ),
            "account_scope_ref": self._first_string(
                session_metadata.get("account_scope_ref"),
                mount_metadata.get("account_scope_ref"),
            ),
            "writer_lock_scope": self._first_string(
                session_metadata.get("writer_lock_scope"),
                mount_metadata.get("writer_lock_scope"),
            ),
            "active_surface_mix": self._merge_string_lists(
                session_metadata.get("active_surface_mix"),
                mount_metadata.get("active_surface_mix"),
            ),
            "handoff_state": handoff_state,
            "handoff_owner_ref": handoff_owner_ref,
            "current_gap_or_blocker": gap,
            "ready": ready,
        }

    def build_host_companion_projection(
        self,
        *,
        mount,
        session: SessionMount | None,
        live_handle: dict[str, object] | None,
        recovery: dict[str, object],
        host_contract: dict[str, object],
    ) -> dict[str, object]:
        mount_metadata = self._mapping(getattr(mount, "metadata", None))
        session_metadata = self._mapping(session.metadata if session is not None else None)
        live_handle_mapping = self._mapping(live_handle)
        live_descriptor = self._mapping(live_handle_mapping.get("descriptor"))
        bridge_registration = self._build_bridge_registration_projection(
            session_metadata,
            mount_metadata,
            live_handle_mapping,
            live_descriptor,
        )
        if session is None:
            return {
                "projection_kind": "host_companion_session_projection",
                "is_projection": True,
                "session_mount_id": None,
                "environment_id": getattr(mount, "id", None) if mount is not None else None,
                "continuity_status": "no-session",
                "continuity_source": "none",
                "bridge_registration": bridge_registration,
                "lease_runtime": {},
                "locality": {
                    "same_host": False,
                    "same_process": False,
                    "startup_recovery_required": False,
                },
                "live_handle": self._mapping(live_handle),
                "handoff_state": host_contract.get("handoff_state"),
                "resume_kind": host_contract.get("resume_kind"),
                "verification_channel": host_contract.get("verification_channel"),
                "current_gap_or_blocker": host_contract.get("current_gap_or_blocker"),
                "projection_note": (
                    "Host companion session is a continuity projection over session "
                    "lease runtime and live-handle state."
                ),
            }
        lease_service = self._service._lease_service
        lease_runtime = lease_service.lease_runtime_mapping(session.metadata)
        locality = lease_service.session_recovery_locality(session)
        status = self._first_string(recovery.get("status")) or "unknown"
        continuity_source = "unknown"
        if live_handle is not None:
            continuity_source = "live-handle"
        elif status == "restorable":
            continuity_source = "registered-restorer"
        elif status == "same-host-other-process":
            continuity_source = "same-host-other-process"
        elif status == "remote":
            continuity_source = "remote-host-lease"
        elif status == "ownership-unknown":
            continuity_source = "incomplete-lease-metadata"
        return {
            "projection_kind": "host_companion_session_projection",
            "is_projection": True,
            "session_mount_id": session.id,
            "environment_id": session.environment_id,
            "channel": session.channel,
            "session_id": session.session_id,
            "user_id": session.user_id,
            "continuity_status": status,
            "continuity_source": continuity_source,
            "bridge_registration": bridge_registration,
            "lease_status": session.lease_status,
            "lease_owner": session.lease_owner,
            "lease_runtime": {
                "host_id": self._first_string(lease_runtime.get("host_id")),
                "process_id": self._normalize_process_id(lease_runtime.get("process_id")),
                "seen_at": self._first_string(lease_runtime.get("seen_at")),
                "expires_at": self._first_string(lease_runtime.get("expires_at")),
            },
            "locality": {
                "same_host": bool(locality.get("same_host")),
                "same_process": bool(locality.get("same_process")),
                "startup_recovery_required": bool(
                    recovery.get("startup_recovery_required"),
                ),
            },
            "live_handle": self._mapping(live_handle),
            "handoff_state": host_contract.get("handoff_state"),
            "resume_kind": host_contract.get("resume_kind"),
            "verification_channel": host_contract.get("verification_channel"),
            "current_gap_or_blocker": host_contract.get("current_gap_or_blocker"),
            "projection_note": (
                "Host companion session is a continuity projection over session "
                "lease runtime and live-handle state."
            ),
        }

    def build_workspace_graph_projection(
        self,
        *,
        mount,
        session: SessionMount | None,
        host_contract: dict[str, object],
        browser_site_contract: dict[str, object],
        desktop_app_contract: dict[str, object],
        host_event_summary: dict[str, object],
        observations,
        replays,
        artifacts,
        live_handle: dict[str, object] | None,
    ) -> dict[str, object]:
        mount_metadata = self._mapping(getattr(mount, "metadata", None))
        session_metadata = self._mapping(session.metadata if session is not None else None)
        lease_service = self._service._lease_service
        lease_descriptor = (
            lease_service.lease_runtime_descriptor(session_metadata)
            if session is not None
            else lease_service.lease_runtime_descriptor(mount_metadata)
        )
        live_descriptor = self._mapping(
            self._mapping(live_handle).get("descriptor"),
        )
        # Prefer formal workspace refs and only fall back to raw handle identifiers when
        # the workspace/session mounts do not expose a stable projection yet.
        browser_context_refs = self._merge_projection_refs(
            session_metadata.get("browser_context_refs"),
            mount_metadata.get("browser_context_refs"),
            fallback_sources=(
                [lease_descriptor.get("browser"), lease_descriptor.get("page_id")],
                [live_descriptor.get("browser"), live_descriptor.get("page_id")],
            ),
        )
        app_window_refs = self._merge_projection_refs(
            session_metadata.get("app_window_refs"),
            mount_metadata.get("app_window_refs"),
            fallback_sources=(
                [lease_descriptor.get("active_window_ref"), lease_descriptor.get("window_scope")],
                [live_descriptor.get("active_window_ref"), live_descriptor.get("window_scope")],
            ),
        )
        file_doc_refs = self._merge_projection_refs(
            session_metadata.get("file_doc_refs"),
            mount_metadata.get("file_doc_refs"),
            fallback_sources=(
                [lease_descriptor.get("workspace"), lease_descriptor.get("cwd")],
                [live_descriptor.get("workspace"), live_descriptor.get("cwd")],
            ),
        )
        clipboard_refs = self._merge_string_lists(
            session_metadata.get("clipboard_refs"),
            mount_metadata.get("clipboard_refs"),
            lease_descriptor.get("clipboard_refs"),
            live_descriptor.get("clipboard_refs"),
        )
        download_artifact_refs = [
            item.artifact_id
            for item in artifacts
            if self._first_string(getattr(item, "artifact_type", None))
            in {"download", "download-bucket"}
            and self._first_string(getattr(item, "artifact_id", None))
        ]
        download_bucket_refs = self._merge_string_lists(
            session_metadata.get("download_bucket_refs"),
            mount_metadata.get("download_bucket_refs"),
            lease_descriptor.get("download_bucket_refs"),
            live_descriptor.get("download_bucket_refs"),
            [browser_site_contract.get("download_policy")],
            download_artifact_refs,
        )
        artifact_refs = [
            item.artifact_id
            for item in artifacts
            if self._first_string(getattr(item, "artifact_id", None))
        ]
        replay_refs = [
            item.replay_id
            for item in replays
            if self._first_string(getattr(item, "replay_id", None))
        ]
        observation_refs = [
            item.evidence_id
            for item in observations
            if self._first_string(getattr(item, "evidence_id", None))
        ]
        active_lock_summary = self._first_string(
            session_metadata.get("active_lock_summary"),
            mount_metadata.get("active_lock_summary"),
        )
        lock_refs = self._merge_string_lists(
            session_metadata.get("lock_refs"),
            mount_metadata.get("lock_refs"),
            lease_descriptor.get("lock_refs"),
            live_descriptor.get("lock_refs"),
            [
                active_lock_summary,
            ],
        )
        workspace_scope = self._first_string(
            session_metadata.get("workspace_scope"),
            mount_metadata.get("workspace_scope"),
            lease_descriptor.get("workspace_scope"),
            live_descriptor.get("workspace_scope"),
        )
        account_scope_ref = self._first_string(
            browser_site_contract.get("account_scope_ref"),
            desktop_app_contract.get("account_scope_ref"),
            host_contract.get("account_scope_ref"),
            session_metadata.get("account_scope_ref"),
            mount_metadata.get("account_scope_ref"),
        )
        owner_agent_id = self._first_string(
            getattr(session, "lease_owner", None) if session is not None else None,
            getattr(mount, "lease_owner", None) if mount is not None else None,
            host_contract.get("lease_owner"),
        )
        pending_handoff_summary = self._first_string(
            session_metadata.get("pending_handoff_summary"),
            mount_metadata.get("pending_handoff_summary"),
            host_contract.get("handoff_state"),
        )
        handoff_checkpoint = {
            "state": host_contract.get("handoff_state"),
            "reason": host_contract.get("handoff_reason"),
            "owner_ref": host_contract.get("handoff_owner_ref"),
            "resume_kind": host_contract.get("resume_kind"),
            "verification_channel": host_contract.get("verification_channel"),
            "checkpoint_ref": self._first_string(
                session_metadata.get("handoff_checkpoint_ref"),
                mount_metadata.get("handoff_checkpoint_ref"),
            ),
            "return_condition": self._first_string(
                session_metadata.get("handoff_return_condition"),
                mount_metadata.get("handoff_return_condition"),
            ),
            "summary": pending_handoff_summary,
        }
        active_surface_refs = self._merge_string_lists(
            browser_context_refs,
            app_window_refs,
            file_doc_refs,
            clipboard_refs,
            download_bucket_refs,
        )
        latest_download_event = self._host_event_latest(
            host_event_summary,
            "download-completed",
        )
        latest_lock_event = self._host_event_latest(
            host_event_summary,
            "lock-unlock",
        )
        latest_blocker_event = self._blocking_host_event(host_event_summary)
        locks = self._build_workspace_lock_projection(
            lock_refs=lock_refs,
            active_lock_summary=active_lock_summary,
            owner_agent_id=owner_agent_id,
            account_scope_ref=account_scope_ref,
            host_contract=host_contract,
            desktop_app_contract=desktop_app_contract,
            latest_lock_event=latest_lock_event,
        )
        surfaces = self._build_workspace_surface_projection(
            browser_context_refs=browser_context_refs,
            app_window_refs=app_window_refs,
            file_doc_refs=file_doc_refs,
            clipboard_refs=clipboard_refs,
            download_bucket_refs=download_bucket_refs,
            workspace_scope=workspace_scope,
            account_scope_ref=account_scope_ref,
            browser_site_contract=browser_site_contract,
            desktop_app_contract=desktop_app_contract,
            host_contract=host_contract,
            latest_download_event=latest_download_event,
            latest_blocker_event=latest_blocker_event,
            mount_metadata=mount_metadata,
            session_metadata=session_metadata,
        )
        ownership = {
            "owner_agent_id": owner_agent_id,
            "handoff_owner_ref": host_contract.get("handoff_owner_ref"),
            "account_scope_ref": account_scope_ref,
            "workspace_scope": workspace_scope,
            "work_context_id": self._first_string(
                session_metadata.get("work_context_id"),
                mount_metadata.get("work_context_id"),
                host_contract.get("work_context_id"),
            ),
            "session_scope": host_contract.get("session_scope"),
            "lease_class": host_contract.get("lease_class"),
            "access_mode": host_contract.get("access_mode"),
        }
        collision_facts = {
            "account_scope_ref": account_scope_ref,
            "writer_lock_scope": desktop_app_contract.get("writer_lock_scope"),
            "active_lock_summary": active_lock_summary,
            "handoff_state": host_contract.get("handoff_state"),
            "handoff_reason": host_contract.get("handoff_reason"),
            "handoff_owner_ref": host_contract.get("handoff_owner_ref"),
            "current_gap_or_blocker": self._first_string(
                host_contract.get("current_gap_or_blocker"),
                desktop_app_contract.get("current_gap_or_blocker"),
                browser_site_contract.get("current_gap_or_blocker"),
            ),
            "blocking_event_family": self._first_string(
                latest_blocker_event.get("event_family")
                if latest_blocker_event is not None
                else None,
                desktop_app_contract.get("blocker_event_family"),
            ),
            "shared_surface_owner": owner_agent_id,
            "requires_human_return": bool(
                self._first_string(
                    host_contract.get("handoff_owner_ref"),
                    host_contract.get("handoff_state"),
                    host_contract.get("current_gap_or_blocker"),
                ),
            ),
        }
        return {
            "projection_kind": "workspace_graph_projection",
            "is_projection": True,
            "workspace_id": self._first_string(
                session_metadata.get("workspace_id"),
                mount_metadata.get("workspace_id"),
                getattr(mount, "id", None) if mount is not None else None,
            ),
            "work_context_id": self._first_string(
                session_metadata.get("work_context_id"),
                mount_metadata.get("work_context_id"),
                host_contract.get("work_context_id"),
            ),
            "seat_ref": getattr(mount, "id", None) if mount is not None else None,
            "session_mount_id": session.id if session is not None else None,
            "browser_context_refs": browser_context_refs,
            "app_window_refs": app_window_refs,
            "file_doc_refs": file_doc_refs,
            "clipboard_refs": clipboard_refs,
            "download_bucket_refs": download_bucket_refs,
            "lock_refs": lock_refs,
            "active_surface_refs": active_surface_refs,
            "workspace_components": {
                "browser_context_count": len(browser_context_refs),
                "app_window_count": len(app_window_refs),
                "file_doc_count": len(file_doc_refs),
                "clipboard_count": len(clipboard_refs),
                "download_bucket_count": len(download_bucket_refs),
                "lock_count": len(lock_refs),
            },
            "artifact_refs": artifact_refs,
            "replay_refs": replay_refs,
            "observation_refs": observation_refs,
            "active_lock_summary": active_lock_summary,
            "pending_handoff_summary": pending_handoff_summary,
            "locks": locks,
            "surfaces": surfaces,
            "owner_agent_id": owner_agent_id,
            "account_scope_ref": account_scope_ref,
            "workspace_scope": workspace_scope,
            "handoff_owner_ref": host_contract.get("handoff_owner_ref"),
            "ownership": ownership,
            "ownership_summary": self._first_string(
                host_contract.get("handoff_owner_ref"),
                owner_agent_id,
                account_scope_ref,
            ),
            "collision_facts": collision_facts,
            "collision_summary": self._first_string(
                collision_facts["current_gap_or_blocker"],
                active_lock_summary,
                desktop_app_contract.get("writer_lock_scope"),
                host_contract.get("handoff_state"),
            ),
            "download_status": {
                "bucket_refs": download_bucket_refs,
                "active_bucket_ref": download_bucket_refs[0] if download_bucket_refs else None,
                "download_policy": browser_site_contract.get("download_policy"),
                "download_verification": browser_site_contract.get("download_verification"),
                "latest_download_event": (
                    {
                        "event_id": latest_download_event.get("event_id"),
                        "event_name": latest_download_event.get("event_name"),
                        "topic": latest_download_event.get("topic"),
                        "action": latest_download_event.get("action"),
                        "created_at": latest_download_event.get("created_at"),
                        "severity": latest_download_event.get("severity"),
                        "recommended_runtime_response": latest_download_event.get(
                            "recommended_runtime_response",
                        ),
                    }
                    if latest_download_event is not None
                    else None
                ),
            },
            "surface_contracts": {
                "browser_active_site": browser_site_contract.get("active_site"),
                "browser_site_contract_status": browser_site_contract.get(
                    "site_contract_status",
                ),
                "desktop_app_identity": desktop_app_contract.get("app_identity"),
                "desktop_app_contract_status": desktop_app_contract.get(
                    "app_contract_status",
                ),
            },
            "handoff_checkpoint": handoff_checkpoint,
            "latest_host_event_summary": self._mapping(
                host_event_summary.get("latest_event"),
            ),
            "projection_note": (
                "Workspace graph is a derived runtime projection over mounts, "
                "artifacts, replays, observations, live-handle descriptors, and "
                "workspace/runtime handoff facts."
            ),
        }

    def build_host_twin_projection(
        self,
        *,
        mount,
        session: SessionMount | None,
        host_contract: dict[str, object],
        recovery: dict[str, object],
        seat_runtime: dict[str, object],
        host_companion_session: dict[str, object],
        browser_site_contract: dict[str, object],
        desktop_app_contract: dict[str, object],
        workspace_graph: dict[str, object],
        host_event_summary: dict[str, object],
    ) -> dict[str, object]:
        ownership = self._build_host_twin_ownership(
            workspace_graph=workspace_graph,
            seat_runtime=seat_runtime,
            host_contract=host_contract,
        )
        surface_mutability = self._build_host_twin_surface_mutability(
            workspace_graph=workspace_graph,
            host_contract=host_contract,
            browser_site_contract=browser_site_contract,
            desktop_app_contract=desktop_app_contract,
            host_event_summary=host_event_summary,
            recovery=recovery,
        )
        blocked_surfaces = [
            {
                "surface_kind": surface_kind,
                "surface_ref": details.get("surface_ref"),
                "reason": self._first_string(
                    details.get("reason"),
                    host_contract.get("handoff_reason"),
                    host_contract.get("current_gap_or_blocker"),
                ),
                "event_family": details.get("blocker_family"),
            }
            for surface_kind, details in surface_mutability.items()
            if details.get("mutability") == "blocked"
        ]
        recovered_runtime_ready = self._host_twin_recovered_runtime_ready(
            host_contract=host_contract,
            recovery=recovery,
            host_event_summary=host_event_summary,
        )
        continuity = self._build_host_twin_continuity(
            host_contract=host_contract,
            recovery=recovery,
            host_companion_session=host_companion_session,
            recovered_runtime_ready=recovered_runtime_ready,
        )
        trusted_anchors = self._build_host_twin_trusted_anchors(
            workspace_graph=workspace_graph,
            browser_site_contract=browser_site_contract,
            desktop_app_contract=desktop_app_contract,
        )
        legal_recovery = self._build_host_twin_legal_recovery(
            workspace_graph=workspace_graph,
            host_contract=host_contract,
            recovery=recovery,
        )
        latest_blocking_event = self._build_host_twin_latest_blocking_event(
            workspace_graph=workspace_graph,
            host_event_summary=host_event_summary,
            surface_mutability=surface_mutability,
            host_contract=host_contract,
            recovery=recovery,
        )
        app_family_twins = self._build_host_twin_app_family_twins(
            browser_site_contract=browser_site_contract,
            desktop_app_contract=desktop_app_contract,
            surface_mutability=surface_mutability,
        )
        coordination = self._build_host_twin_coordination(
            workspace_graph=workspace_graph,
            ownership=ownership,
            seat_runtime=seat_runtime,
            host_contract=host_contract,
            latest_blocking_event=latest_blocking_event,
            recovered_runtime_ready=recovered_runtime_ready,
        )
        execution_mutation_ready = {
            "browser": bool(
                self._mapping(surface_mutability.get("browser")).get("safe_to_mutate"),
            ),
            "desktop_app": bool(
                self._mapping(surface_mutability.get("desktop_app")).get("safe_to_mutate"),
            ),
            "file_docs": bool(
                self._mapping(surface_mutability.get("file_docs")).get("safe_to_mutate"),
            ),
        }
        active_blocker_family = self._first_string(
            self._mapping(latest_blocking_event).get("event_family"),
        )
        active_blocker_families = [active_blocker_family] if active_blocker_family else []
        writable_surface_kinds = sorted(
            [
                surface_kind
                for surface_kind, is_ready in execution_mutation_ready.items()
                if is_ready is True
            ],
        )
        pending_recovery_families = sorted(
            {
                family
                for family in (
                    self._first_string(item.get("event_family"))
                    for item in list(host_event_summary.get("pending_recovery_events") or [])
                    if isinstance(item, dict)
                )
                if family is not None and family != "human-handoff-return"
            },
        )
        active_recovery_family = self._first_string(
            self._mapping(host_event_summary.get("scheduler_inputs")).get(
                "active_recovery_family",
            ),
        )
        if recovered_runtime_ready:
            active_recovery_family = None
        host_twin_summary = self._build_host_twin_summary_projection(
            ownership=ownership,
            coordination=coordination,
            app_family_twins=app_family_twins,
            host_companion_session=host_companion_session,
            seat_runtime=seat_runtime,
            blocked_surfaces=blocked_surfaces,
            continuity=continuity,
            legal_recovery=legal_recovery,
            latest_blocking_event=latest_blocking_event,
            execution_mutation_ready=execution_mutation_ready,
            writable_surface_kinds=writable_surface_kinds,
            trusted_anchors=trusted_anchors,
        )
        return {
            "projection_kind": "host_twin_projection",
            "is_projection": True,
            "is_truth_store": False,
            "seat_ref": getattr(mount, "id", None) if mount is not None else None,
            "environment_id": getattr(mount, "id", None) if mount is not None else None,
            "session_mount_id": session.id if session is not None else None,
            "seat": {
                "owner_ref": ownership.get("seat_owner_agent_id"),
                "ownership_source": ownership.get("ownership_source"),
            },
            "seat_owner_ref": ownership.get("seat_owner_agent_id"),
            "ownership_source": ownership.get("ownership_source"),
            "ownership": ownership,
            "surface_mutability": surface_mutability,
            "writable_surface_kinds": writable_surface_kinds,
            "writable_surfaces": [
                {
                    "surface_kind": surface_kind,
                    "surface_ref": self._mapping(surface_mutability.get(surface_kind)).get(
                        "surface_ref",
                    ),
                    "summary": self._mapping(surface_mutability.get(surface_kind)).get(
                        "surface_ref",
                    ),
                }
                for surface_kind in writable_surface_kinds
            ],
            "writable_surface_summary": (
                ", ".join(writable_surface_kinds) if writable_surface_kinds else None
            ),
            "blocked_surfaces": blocked_surfaces,
            "continuity": continuity,
            "trusted_evidence_anchors": trusted_anchors,
            "trusted_anchors": trusted_anchors,
            "legal_recovery_path": {
                "decision": legal_recovery.get("path"),
                "mode": legal_recovery.get("path"),
                "path": legal_recovery.get("path"),
                "resume_kind": legal_recovery.get("resume_kind"),
                "checkpoint_ref": legal_recovery.get("checkpoint_ref"),
                "verification_channel": legal_recovery.get("verification_channel"),
                "return_condition": legal_recovery.get("return_condition"),
                "summary": self._first_string(
                    legal_recovery.get("checkpoint_ref"),
                    legal_recovery.get("path"),
                ),
            },
            "legal_recovery": legal_recovery,
            "active_blocker_families": active_blocker_families,
            "latest_blocking_event": latest_blocking_event,
            "execution_mutation_ready": execution_mutation_ready,
            "app_family_twins": app_family_twins,
            "coordination": coordination,
            "host_twin_summary": host_twin_summary,
            "scheduler_inputs": {
                "active_blocker_family": active_blocker_family,
                "active_recovery_family": active_recovery_family,
                "recovery_family": active_recovery_family,
                "human_handoff_active": continuity["requires_human_return"],
                "requires_human_return": continuity["requires_human_return"],
                "environment_ref": self._first_string(
                    coordination.get("selected_seat_ref"),
                    getattr(mount, "ref", None) if mount is not None else None,
                    getattr(mount, "id", None) if mount is not None else None,
                ),
                "environment_id": self._first_string(
                    coordination.get("selected_seat_ref"),
                    getattr(mount, "id", None) if mount is not None else None,
                ),
                "session_mount_id": self._first_string(
                    coordination.get("selected_session_mount_id"),
                    session.id if session is not None else None,
                ),
                "recommended_scheduler_action": self._first_string(
                    coordination.get("recommended_scheduler_action"),
                ),
                "recommended_runtime_response": self._first_string(
                    self._mapping(latest_blocking_event).get(
                        "recommended_runtime_response",
                    ),
                ),
                "legal_recovery_path": legal_recovery.get("path"),
                "pending_recovery_event_count": len(
                    list(host_event_summary.get("pending_recovery_events") or []),
                ),
            },
            "recovery_inputs": {
                "pending_recovery_families": pending_recovery_families,
            },
            "projection_note": (
                "Execution-grade host twin is a derived runtime projection over "
                "seat/workspace/contracts/events/evidence anchors, not a second "
                "truth source."
            ),
        }

    def _build_host_twin_summary_projection(
        self,
        *,
        ownership: dict[str, object],
        coordination: dict[str, object],
        app_family_twins: dict[str, dict[str, object]],
        host_companion_session: dict[str, object],
        seat_runtime: dict[str, object],
        blocked_surfaces: list[dict[str, object]],
        continuity: dict[str, object],
        legal_recovery: dict[str, object],
        latest_blocking_event: dict[str, object],
        execution_mutation_ready: dict[str, bool],
        writable_surface_kinds: list[str],
        trusted_anchors: list[dict[str, object]],
    ) -> dict[str, object]:
        active_app_family_keys = sorted(
            family_key
            for family_key, value in app_family_twins.items()
            if isinstance(value, dict) and value.get("active") is True
        )
        ready_app_family_keys = sorted(
            family_key
            for family_key, value in app_family_twins.items()
            if isinstance(value, dict)
            and value.get("active") is True
            and self._first_string(value.get("contract_status")) not in {
                "blocked",
                "inactive",
            }
        )
        blocked_app_family_keys = sorted(
            family_key
            for family_key, value in app_family_twins.items()
            if isinstance(value, dict)
            and (
                value.get("active") is not True
                or self._first_string(value.get("contract_status")) in {
                    "blocked",
                    "inactive",
                }
            )
        )
        candidate_seat_refs = self._string_list(coordination.get("candidate_seat_refs"))
        selected_seat_ref = self._first_string(
            coordination.get("selected_seat_ref"),
            seat_runtime.get("selected_seat_ref"),
            seat_runtime.get("seat_ref"),
        )
        seat_count = seat_runtime.get("session_count")
        if not isinstance(seat_count, int):
            seat_count = len(candidate_seat_refs) or (1 if selected_seat_ref else 0)
        host_companion_status = self._first_string(
            host_companion_session.get("continuity_status"),
        )
        host_companion_source = self._first_string(
            host_companion_session.get("continuity_source"),
        )
        host_companion_locality = self._mapping(host_companion_session.get("locality"))
        selected_session_mount_id = self._first_string(
            coordination.get("selected_session_mount_id"),
            seat_runtime.get("selected_session_mount_id"),
            seat_runtime.get("active_session_mount_id"),
        )
        candidate_seats = [
            self._mapping(item)
            for item in list(seat_runtime.get("candidate_seats") or [])
            if isinstance(item, dict)
        ]
        selected_candidate = next(
            (
                item
                for item in candidate_seats
                if self._first_string(item.get("session_mount_id")) == selected_session_mount_id
                or self._first_string(item.get("seat_ref")) == selected_seat_ref
            ),
            None,
        )
        using_alternate_ready_seat = bool(
            isinstance(selected_candidate, dict)
            and selected_candidate.get("ready") is True
            and selected_seat_ref is not None
            and selected_seat_ref != seat_runtime.get("seat_ref")
        )
        blocked_surface_refs = [
            self._first_string(surface.get("surface_ref"), surface.get("surface_kind"))
            for surface in blocked_surfaces
            if isinstance(surface, dict)
        ]
        if using_alternate_ready_seat:
            blocked_surface_refs = []
        multi_seat_coordination = {
            "seat_count": seat_count,
            "candidate_seat_refs": candidate_seat_refs,
            "selected_seat_ref": selected_seat_ref,
            "selected_session_mount_id": selected_session_mount_id,
            "seat_selection_policy": self._first_string(
                coordination.get("seat_selection_policy"),
            ),
            "occupancy_state": self._first_string(
                seat_runtime.get("occupancy_state"),
            ),
            "status": self._first_string(seat_runtime.get("status")),
            "host_companion_status": host_companion_status,
            "active_surface_mix": self._string_list(
                seat_runtime.get("active_surface_mix"),
            ),
        }
        app_family_statuses = {
            family_key: {
                "active": bool(value.get("active")),
                "ready": family_key in ready_app_family_keys,
                "contract_status": self._first_string(value.get("contract_status")),
                "surface_ref": self._first_string(value.get("surface_ref")),
                "family_scope_ref": self._first_string(value.get("family_scope_ref")),
                "writer_lock_scope": self._first_string(value.get("writer_lock_scope")),
            }
            for family_key, value in app_family_twins.items()
            if isinstance(value, dict)
        }
        trusted_anchor_ref = None
        if trusted_anchors:
            first_anchor = trusted_anchors[0]
            if isinstance(first_anchor, dict):
                trusted_anchor_ref = self._first_string(
                    first_anchor.get("anchor_ref"),
                    first_anchor.get("anchor"),
                    first_anchor.get("label"),
                )
        return {
            "seat_owner_ref": self._first_string(
                coordination.get("seat_owner_ref"),
                ownership.get("seat_owner_ref"),
                ownership.get("seat_owner_agent_id"),
            ),
            "handoff_owner_ref": self._first_string(ownership.get("handoff_owner_ref")),
            "workspace_owner_ref": self._first_string(
                coordination.get("workspace_owner_ref"),
                ownership.get("workspace_owner_ref"),
            ),
            "writer_owner_ref": self._first_string(
                coordination.get("writer_owner_ref"),
                ownership.get("writer_owner_ref"),
            ),
            "selected_seat_ref": selected_seat_ref,
            "selected_session_mount_id": selected_session_mount_id,
            "seat_selection_policy": self._first_string(
                coordination.get("seat_selection_policy"),
            ),
            "recommended_scheduler_action": self._first_string(
                coordination.get("recommended_scheduler_action"),
            ),
            "contention_severity": self._first_string(
                self._mapping(coordination.get("contention_forecast")).get("severity"),
            ),
            "contention_reason": self._first_string(
                self._mapping(coordination.get("contention_forecast")).get("reason"),
            ),
            "host_companion_status": host_companion_status,
            "host_companion_source": host_companion_source,
            "host_companion_session_mount_id": self._first_string(
                host_companion_session.get("session_mount_id"),
            ),
            "host_companion_environment_id": self._first_string(
                host_companion_session.get("environment_id"),
            ),
            "host_companion_locality": host_companion_locality,
            "seat_count": seat_count,
            "candidate_seat_refs": candidate_seat_refs,
            "multi_seat_coordination": multi_seat_coordination,
            "ready_app_family_keys": ready_app_family_keys,
            "ready_app_family_count": len(ready_app_family_keys),
            "blocked_app_family_keys": blocked_app_family_keys,
            "blocked_app_family_count": len(blocked_app_family_keys),
            "app_family_readiness": {
                "active_family_keys": active_app_family_keys,
                "active_family_count": len(active_app_family_keys),
                "ready_family_keys": ready_app_family_keys,
                "ready_family_count": len(ready_app_family_keys),
                "blocked_family_keys": blocked_app_family_keys,
                "blocked_family_count": len(blocked_app_family_keys),
                "family_statuses": app_family_statuses,
            },
            "active_app_family_keys": active_app_family_keys,
            "active_app_family_count": len(active_app_family_keys),
            "blocked_surface_refs": blocked_surface_refs,
            "blocked_surface_count": len(blocked_surface_refs),
            "active_blocker_families": self._string_list(
                latest_blocking_event.get("event_family"),
            ),
            "legal_recovery_mode": self._first_string(
                "resume-environment" if using_alternate_ready_seat else None,
                legal_recovery.get("resume_kind"),
                legal_recovery.get("mode"),
                legal_recovery.get("path"),
            ),
            "legal_recovery_summary": self._first_string(
                (
                    f"selected-session:{selected_session_mount_id}"
                    if using_alternate_ready_seat
                    else None
                ),
                legal_recovery.get("checkpoint_ref"),
                legal_recovery.get("path"),
            ),
            "writable_surface_label": (
                ", ".join(writable_surface_kinds) if writable_surface_kinds else None
            ),
            "trusted_anchor_ref": trusted_anchor_ref,
        }

    def _build_workspace_lock_projection(
        self,
        *,
        lock_refs: list[str],
        active_lock_summary: str | None,
        owner_agent_id: str | None,
        account_scope_ref: str | None,
        host_contract: dict[str, object],
        desktop_app_contract: dict[str, object],
        latest_lock_event: dict[str, object] | None,
    ) -> list[dict[str, object]]:
        writer_lock_scope = self._first_string(
            desktop_app_contract.get("writer_lock_scope"),
        )
        surface_ref = self._first_string(
            desktop_app_contract.get("active_window_ref"),
            desktop_app_contract.get("window_scope"),
        )
        status = "held"
        if latest_lock_event is not None:
            action = self._first_string(latest_lock_event.get("action"))
            if action is not None and "unlock" in action.lower():
                status = "released"
        structured: list[dict[str, object]] = []
        seen: set[str] = set()
        writer_resource_ref = self._first_string(
            active_lock_summary,
            lock_refs[0] if lock_refs else None,
            writer_lock_scope,
        )
        if writer_resource_ref is not None:
            seen.add(writer_resource_ref)
            structured.append(
                {
                    "resource_ref": writer_resource_ref,
                    "summary": active_lock_summary or writer_lock_scope or writer_resource_ref,
                    "surface_ref": surface_ref,
                    "account_scope_ref": account_scope_ref,
                    "writer_lock": {
                        "status": status,
                        "scope": writer_lock_scope,
                        "owner_agent_id": owner_agent_id,
                        "lease_class": host_contract.get("lease_class"),
                        "access_mode": host_contract.get("access_mode"),
                        "handoff_state": host_contract.get("handoff_state"),
                        "handoff_owner_ref": host_contract.get("handoff_owner_ref"),
                    },
                },
            )
        for lock_ref in lock_refs:
            if lock_ref in seen:
                continue
            seen.add(lock_ref)
            structured.append(
                {
                    "resource_ref": lock_ref,
                    "summary": lock_ref,
                    "surface_ref": surface_ref,
                    "account_scope_ref": account_scope_ref,
                    "writer_lock": {
                        "status": status,
                        "scope": writer_lock_scope,
                        "owner_agent_id": owner_agent_id,
                        "lease_class": host_contract.get("lease_class"),
                        "access_mode": host_contract.get("access_mode"),
                        "handoff_state": host_contract.get("handoff_state"),
                        "handoff_owner_ref": host_contract.get("handoff_owner_ref"),
                    },
                },
            )
        return structured

    def _build_workspace_surface_projection(
        self,
        *,
        browser_context_refs: list[str],
        app_window_refs: list[str],
        file_doc_refs: list[str],
        clipboard_refs: list[str],
        download_bucket_refs: list[str],
        workspace_scope: str | None,
        account_scope_ref: str | None,
        browser_site_contract: dict[str, object],
        desktop_app_contract: dict[str, object],
        host_contract: dict[str, object],
        latest_download_event: dict[str, object] | None,
        latest_blocker_event: dict[str, object] | None,
        mount_metadata: dict[str, object],
        session_metadata: dict[str, object],
    ) -> dict[str, object]:
        windows_app_adapter_refs = self._merge_string_lists(
            session_metadata.get("windows_app_adapter_refs"),
            mount_metadata.get("windows_app_adapter_refs"),
        )
        return {
            "browser": {
                "context_refs": browser_context_refs,
                "active_tab": {
                    "tab_id": browser_site_contract.get("active_tab_ref"),
                    "site": browser_site_contract.get("active_site"),
                    "tab_scope": browser_site_contract.get("tab_scope"),
                    "login_state": browser_site_contract.get("login_state"),
                    "account_scope_ref": self._first_string(
                        browser_site_contract.get("account_scope_ref"),
                        account_scope_ref,
                    ),
                    "handoff_state": self._first_string(
                        browser_site_contract.get("handoff_state"),
                        host_contract.get("handoff_state"),
                    ),
                    "resume_kind": self._first_string(
                        browser_site_contract.get("resume_kind"),
                        host_contract.get("resume_kind"),
                    ),
                    "verification_channel": host_contract.get("verification_channel"),
                    "current_gap_or_blocker": self._first_string(
                        browser_site_contract.get("current_gap_or_blocker"),
                        host_contract.get("current_gap_or_blocker"),
                    ),
                },
                "site_contract_status": browser_site_contract.get("site_contract_status"),
                "download_policy": browser_site_contract.get("download_policy"),
            },
            "desktop": {
                "window_refs": app_window_refs,
                "active_window": {
                    "window_ref": desktop_app_contract.get("active_window_ref"),
                    "window_scope": desktop_app_contract.get("window_scope"),
                    "app_identity": desktop_app_contract.get("app_identity"),
                    "window_anchor_summary": desktop_app_contract.get("window_anchor_summary"),
                    "writer_lock_scope": desktop_app_contract.get("writer_lock_scope"),
                    "account_scope_ref": self._first_string(
                        desktop_app_contract.get("account_scope_ref"),
                        account_scope_ref,
                    ),
                    "handoff_state": self._first_string(
                        desktop_app_contract.get("handoff_state"),
                        host_contract.get("handoff_state"),
                    ),
                    "resume_kind": self._first_string(
                        desktop_app_contract.get("resume_kind"),
                        host_contract.get("resume_kind"),
                    ),
                    "verification_channel": host_contract.get("verification_channel"),
                    "current_gap_or_blocker": self._first_string(
                        desktop_app_contract.get("current_gap_or_blocker"),
                        host_contract.get("current_gap_or_blocker"),
                    ),
                },
                "app_contract_status": desktop_app_contract.get("app_contract_status"),
                "adapter_refs": windows_app_adapter_refs,
            },
            "file_docs": {
                "refs": file_doc_refs,
                "active_doc_ref": file_doc_refs[0] if file_doc_refs else None,
                "workspace_scope": workspace_scope,
            },
            "clipboard": {
                "refs": clipboard_refs,
                "active_clipboard_ref": clipboard_refs[0] if clipboard_refs else None,
                "workspace_scope": workspace_scope,
            },
            "downloads": {
                "bucket_refs": download_bucket_refs,
                "active_bucket": {
                    "bucket_ref": download_bucket_refs[0] if download_bucket_refs else None,
                    "download_policy": browser_site_contract.get("download_policy"),
                    "download_verification": browser_site_contract.get(
                        "download_verification",
                    ),
                    "latest_event_family": self._first_string(
                        latest_download_event.get("event_family")
                        if latest_download_event is not None
                        else None,
                    ),
                },
            },
            "host_blocker": {
                "event_family": self._first_string(
                    latest_blocker_event.get("event_family")
                    if latest_blocker_event is not None
                    else None,
                ),
                "event_name": self._first_string(
                    latest_blocker_event.get("event_name")
                    if latest_blocker_event is not None
                    else None,
                ),
                "recommended_runtime_response": self._first_string(
                    latest_blocker_event.get("recommended_runtime_response")
                    if latest_blocker_event is not None
                    else None,
                ),
            },
        }

    def build_host_events_projection(
        self,
        *,
        environment_id: str | None,
        environment_ref: str | None,
        session_mount_id: str | None,
        limit: int,
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        bounded_limit = max(1, min(50, int(limit) if isinstance(limit, int) else 20))
        summary = {
            "runtime_mechanism": "runtime_event_bus",
            "is_truth_store": False,
            "available": False,
            "note": self._HOST_EVENT_NOTE,
            "environment_id": environment_id,
            "session_mount_id": session_mount_id,
            "total_relevant_events": 0,
            "returned_events": 0,
            "limit": bounded_limit,
            "supported_families": list(self._HOST_EVENT_SUPPORTED_FAMILIES),
            "family_counts": {},
            "counts_by_topic": {},
            "latest_event_by_family": {},
            "active_alert_families": [],
            "latest_event": None,
            "last_event": None,
            "pending_recovery_events": [],
        }
        bus = self._service._runtime_event_bus
        if bus is None:
            return summary, []
        lister = getattr(bus, "list_events", None)
        if not callable(lister):
            return summary, []
        raw_events = lister(after_id=0, limit=max(50, bounded_limit * 10))
        normalized = [self._normalize_host_event(event) for event in raw_events]
        relevant = [
            event
            for event in normalized
            if self._is_relevant_host_event(
                event,
                environment_id=environment_id,
                environment_ref=environment_ref,
                session_mount_id=session_mount_id,
            )
        ]
        bounded = relevant[-bounded_limit:]
        for item in bounded:
            item["mechanism_backed"] = True
            item["is_truth_store"] = False
            item["note"] = self._HOST_EVENT_NOTE
        summary["available"] = True
        summary["total_relevant_events"] = len(relevant)
        summary["returned_events"] = len(bounded)
        family_counts = self._host_event_family_counts(relevant)
        topic_counts = self._host_event_topic_counts(relevant)
        latest_by_family = self._host_event_latest_by_family(relevant)
        summary["family_counts"] = family_counts
        summary["counts_by_topic"] = topic_counts
        summary["latest_event_by_family"] = latest_by_family
        summary["active_alert_families"] = [
            family
            for family, latest in latest_by_family.items()
            if self._first_string(latest.get("severity")) in {"medium", "high"}
            and self._first_string(latest.get("recommended_runtime_response"))
            in {"recover", "handoff", "retry"}
        ]
        summary["blocking_event_families"] = [
            family
            for family in summary["active_alert_families"]
            if self._first_string(
                self._mapping(latest_by_family.get(family)).get(
                    "recommended_runtime_response",
                ),
            )
            in {"handoff", "recover"}
        ]
        summary["recovery_event_families"] = [
            family
            for family in summary["active_alert_families"]
            if self._first_string(
                self._mapping(latest_by_family.get(family)).get(
                    "recommended_runtime_response",
                ),
            )
            in {"recover", "retry"}
        ]
        if bounded:
            latest = bounded[-1]
            summary["latest_event"] = {
                "event_id": latest.get("event_id"),
                "event_name": latest.get("event_name"),
                "topic": latest.get("topic"),
                "action": latest.get("action"),
                "event_family": latest.get("event_family"),
                "severity": latest.get("severity"),
                "recommended_runtime_response": latest.get(
                    "recommended_runtime_response",
                ),
                "created_at": latest.get("created_at"),
                "payload": self._mapping(latest.get("payload")),
            }
            summary["last_event"] = self._first_string(
                latest.get("event_name"),
                latest.get("action"),
            )
        summary["pending_recovery_events"] = self._host_event_pending_recovery_events(
            bounded,
        )
        latest_blocking_event = self._blocking_host_event(summary)
        summary["latest_blocking_event"] = latest_blocking_event
        summary["latest_recovery_event"] = self._latest_pending_recovery_event(summary)
        summary["latest_handoff_event"] = self._latest_handoff_event(relevant)
        summary["human_handoff_active"] = bool(
            self._mapping(summary["latest_handoff_event"]),
        )
        active_recovery_family = self._active_recovery_family(
            summary["pending_recovery_events"],
        )
        summary["scheduler_inputs"] = {
            "active_blocker_family": self._first_string(
                self._mapping(latest_blocking_event).get("event_family"),
            ),
            "active_recovery_family": active_recovery_family,
            "recovery_family": active_recovery_family,
            "pending_recovery_event_count": len(
                list(summary["pending_recovery_events"] or []),
            ),
            "human_handoff_active": bool(summary["human_handoff_active"]),
            "latest_recovery_response": self._first_string(
                self._mapping(summary["latest_recovery_event"]).get(
                    "recommended_runtime_response",
                ),
            ),
        }
        return summary, bounded

    def _normalize_host_event(self, event: object) -> dict[str, object]:
        payload = {}
        if isinstance(getattr(event, "payload", None), dict):
            payload = dict(getattr(event, "payload"))
        event_id = getattr(event, "event_id", None)
        if not isinstance(event_id, int):
            event_id = None
        topic = self._first_string(getattr(event, "topic", None)) or "unknown"
        action = self._first_string(getattr(event, "action", None)) or "unknown"
        event_name = self._first_string(getattr(event, "event_name", None))
        if event_name is None:
            event_name = f"{topic}.{action}"
        created_at = self._iso_timestamp(getattr(event, "created_at", None))
        event_family = self._classify_host_event_family(
            topic=topic,
            action=action,
            payload=payload,
        )
        return {
            "event_id": event_id,
            "event_name": event_name,
            "topic": topic,
            "action": action,
            "created_at": created_at,
            "event_family": event_family,
            "recommended_runtime_response": self._host_event_recommended_response(
                event_family,
                action=action,
                payload=payload,
            ),
            "severity": self._host_event_severity(event_family, action=action),
            "payload": payload,
        }

    def _is_relevant_host_event(
        self,
        event: dict[str, object],
        *,
        environment_id: str | None,
        environment_ref: str | None,
        session_mount_id: str | None,
    ) -> bool:
        topic = self._first_string(event.get("topic")) or "unknown"
        action = self._first_string(event.get("action")) or "unknown"
        event_family = self._first_string(event.get("event_family")) or "runtime-generic"
        payload = self._mapping(event.get("payload"))
        if topic == "system" and action == "recovery":
            return True
        if topic not in self._HOST_EVENT_TOPICS and event_family == "runtime-generic":
            return False
        if self._payload_matches_session(
            payload,
            session_mount_id=session_mount_id,
        ):
            return True
        if self._payload_matches_environment(
            payload,
            environment_id=environment_id,
            environment_ref=environment_ref,
        ):
            return True
        if self._payload_matches_host(payload):
            return True
        if event_family in {"lock-unlock", "network-power"}:
            return True
        return False

    def _payload_matches_environment(
        self,
        payload: dict[str, object],
        *,
        environment_id: str | None,
        environment_ref: str | None,
    ) -> bool:
        if environment_id is None and environment_ref is None:
            return False
        for key in (
            "environment_id",
            "env_id",
            "environment_mount_id",
            "environment_ref",
        ):
            candidate = self._first_string(payload.get(key))
            if candidate is None:
                continue
            if environment_id and candidate == environment_id:
                return True
            if environment_ref and candidate == environment_ref:
                return True
        return False

    def _payload_matches_session(
        self,
        payload: dict[str, object],
        *,
        session_mount_id: str | None,
    ) -> bool:
        if session_mount_id is None:
            return False
        for key in ("session_mount_id", "session_id", "lease_id"):
            candidate = self._first_string(payload.get(key))
            if candidate is None:
                continue
            if candidate == session_mount_id:
                return True
        return False

    def _payload_matches_host(self, payload: dict[str, object]) -> bool:
        host_id = self._first_string(self._service._registry.host_id)
        if host_id is None:
            return False
        for key in ("host_id", "runtime_host_id", "current_host_id"):
            candidate = self._first_string(payload.get(key))
            if candidate == host_id:
                return True
        return False

    def _classify_host_event_family(
        self,
        *,
        topic: str,
        action: str,
        payload: dict[str, object],
    ) -> str:
        topic_key = topic.strip().lower()
        action_key = action.strip().lower()
        prompt_kind = self._first_string(
            payload.get("prompt_kind"),
            payload.get("modal_kind"),
            payload.get("challenge_kind"),
        )
        prompt_key = prompt_kind.strip().lower() if isinstance(prompt_kind, str) else ""
        status_key = (
            self._first_string(payload.get("status"), payload.get("state")) or ""
        ).strip().lower()
        if (
            topic_key in {"window", "desktop"}
            and action_key in {"active-window-changed", "focus-changed", "window-focus-changed"}
        ) or (
            action_key in {"focus-changed", "active-window-changed"}
            and self._first_string(
                payload.get("window_ref"),
                payload.get("active_window_ref"),
            )
            is not None
        ):
            return "active-window"
        if (
            action_key
            in {
                "modal-appeared",
                "uac-appeared",
                "uac-prompt",
                "login-required",
                "captcha-required",
                "mfa-required",
                "handoff-required",
            }
            or prompt_key in {"modal", "uac", "login", "captcha", "mfa"}
        ):
            return "modal-uac-login"
        if topic_key == "host" and action_key in {
            "human-takeover",
            "human-return-ready",
            "human-returned",
            "handoff-returned",
        }:
            return "human-handoff-return"
        if (
            topic_key in {"download", "filesystem"}
            and action_key in {"download-completed", "download-finished"}
        ) or (
            self._first_string(payload.get("download_ref"), payload.get("download_id"))
            is not None
            and status_key in {"completed", "finished", "ready"}
        ):
            return "download-completed"
        if (
            topic_key in {"process", "system"}
            and action_key in {"process-exited", "process-restarted", "restarted", "crashed"}
        ) or action_key in {"process-exited", "process-restarted", "crashed"}:
            return "process-exit-restart"
        if action_key in {
            "lock",
            "unlock",
            "lock-state-changed",
            "desktop-locked",
            "desktop-unlocked",
        } or isinstance(payload.get("locked"), bool):
            return "lock-unlock"
        if (
            topic_key in {"network", "power"}
            and action_key
            in {
                "network-changed",
                "power-changed",
                "network-or-power-changed",
                "connectivity-changed",
                "battery-changed",
            }
        ) or self._first_string(payload.get("network_state"), payload.get("power_state")) is not None:
            return "network-power"
        return "runtime-generic"

    def _host_event_recommended_response(
        self,
        family: str,
        *,
        action: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> str:
        action_key = action.strip().lower() if isinstance(action, str) else ""
        if family == "human-handoff-return":
            if "return" in action_key:
                return "recover"
            return "handoff"
        return self._HOST_EVENT_RESPONSE_BY_FAMILY.get(family, "re-observe")

    def _host_event_severity(
        self,
        family: str,
        *,
        action: str | None = None,
    ) -> str:
        _ = action
        return self._HOST_EVENT_SEVERITY_BY_FAMILY.get(family, "medium")

    def _host_event_family_counts(
        self,
        events: list[dict[str, object]],
    ) -> dict[str, int]:
        counts: dict[str, int] = {}
        for event in events:
            family = self._first_string(event.get("event_family"))
            if family is None:
                continue
            counts[family] = counts.get(family, 0) + 1
        return counts

    def _host_event_topic_counts(
        self,
        events: list[dict[str, object]],
    ) -> dict[str, int]:
        counts: dict[str, int] = {}
        for event in events:
            topic = self._first_string(event.get("topic"))
            if topic is None:
                continue
            counts[topic] = counts.get(topic, 0) + 1
        return counts

    def _host_event_latest_by_family(
        self,
        events: list[dict[str, object]],
    ) -> dict[str, dict[str, object]]:
        latest_by_family: dict[str, dict[str, object]] = {}
        for event in events:
            family = self._first_string(event.get("event_family"))
            if family is None:
                continue
            latest_by_family[family] = {
                "event_id": event.get("event_id"),
                "event_name": event.get("event_name"),
                "topic": event.get("topic"),
                "action": event.get("action"),
                "event_family": family,
                "created_at": event.get("created_at"),
                "severity": event.get("severity"),
                "recommended_runtime_response": event.get(
                    "recommended_runtime_response",
                ),
                "payload": self._mapping(event.get("payload")),
            }
        return latest_by_family

    def _host_event_pending_recovery_events(
        self,
        events: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        pending: list[dict[str, object]] = []
        for event in events:
            recommended_response = self._first_string(
                event.get("recommended_runtime_response"),
            )
            if recommended_response not in {"handoff", "recover", "retry"}:
                continue
            payload = self._mapping(event.get("payload"))
            record = {
                "event_id": event.get("event_id"),
                "event_name": event.get("event_name"),
                "topic": event.get("topic"),
                "action": event.get("action"),
                "event_family": event.get("event_family"),
                "severity": event.get("severity"),
                "recommended_runtime_response": recommended_response,
                "created_at": event.get("created_at"),
                "payload": payload,
                "checkpoint": {
                    "resume_kind": self._host_event_resume_kind(event),
                    "checkpoint_ref": self._first_string(
                        payload.get("checkpoint_ref"),
                    ),
                    "verification_channel": self._first_string(
                        payload.get("verification_channel"),
                    ),
                },
            }
            if self._first_string(event.get("event_family")) == "human-handoff-return":
                record["legal_recovery_path"] = {
                    "decision": recommended_response,
                    "resume_kind": self._host_event_resume_kind(event),
                    "checkpoint_ref": self._first_string(
                        payload.get("checkpoint_ref"),
                    ),
                    "verification_channel": self._first_string(
                        payload.get("verification_channel"),
                    ),
                    "return_condition": self._first_string(
                        payload.get("return_condition"),
                    ),
                }
            pending.append(record)
        return pending

    def _latest_pending_recovery_event(
        self,
        host_event_summary: dict[str, object],
    ) -> dict[str, object] | None:
        pending = list(host_event_summary.get("pending_recovery_events") or [])
        if not pending:
            return None
        latest = pending[-1]
        return dict(latest) if isinstance(latest, dict) else None

    def _active_recovery_family(
        self,
        pending_recovery_events: object,
    ) -> str | None:
        if not isinstance(pending_recovery_events, list):
            return None
        for item in pending_recovery_events:
            if not isinstance(item, dict):
                continue
            decision = self._first_string(
                self._mapping(item.get("legal_recovery_path")).get("decision"),
                item.get("recommended_runtime_response"),
            )
            family = self._first_string(item.get("event_family"))
            if decision in {"recover", "retry"} and family != "human-handoff-return":
                return family
        for item in pending_recovery_events:
            if not isinstance(item, dict):
                continue
            family = self._first_string(item.get("event_family"))
            if family is not None and family != "human-handoff-return":
                return family
        return None

    def build_recovery_payload(
        self,
        *,
        session: SessionMount | None,
        environment_ref: str | None,
        live_handle: dict[str, object] | None,
        replay_count: int,
    ) -> dict[str, object]:
        lease_service = self._service._lease_service
        status = "attached" if live_handle is not None else "detached"
        recoverable = False
        note = (
            "Live handle is mounted in the current runtime host."
            if live_handle is not None
            else "No recovery path is currently available."
        )
        lease_runtime: dict[str, object] = {}
        locality = {
            "lease_host_id": None,
            "lease_process_id": None,
            "current_host_id": self._service._registry.host_id,
            "current_process_id": lease_service.normalize_process_id(
                self._service._registry.process_id,
            ),
            "host_known": False,
            "process_known": False,
            "same_host": False,
            "same_process": False,
        }
        startup_recovery_required = False
        if session is not None:
            lease_runtime = lease_service.lease_runtime_mapping(session.metadata)
            locality = lease_service.session_recovery_locality(session)
            if live_handle is not None:
                status = "attached"
                note = "Live handle is mounted in the current runtime host."
            elif not locality["host_known"]:
                status = "ownership-unknown"
                startup_recovery_required = True
                note = (
                    "Lease ownership metadata is incomplete, so runtime-center reads "
                    "will not reclaim it automatically. Run explicit startup recovery "
                    "or force-release it manually."
                )
            elif not locality["same_host"]:
                status = "remote"
                note = "Lease belongs to another host and will not be recovered locally."
            elif not locality["same_process"]:
                status = "same-host-other-process"
                startup_recovery_required = True
                note = (
                    "Lease belongs to another process on the same host. It will only "
                    "be reclaimed during explicit startup recovery to avoid cross-"
                    "process false takeover."
                )
            elif callable(
                lease_service._session_handle_restorers.get(session.channel),
            ):
                status = "restorable"
                recoverable = True
                note = (
                    "A session restorer is registered for this channel, so the live "
                    "handle can be rebound after restart on the same host."
                )
            elif session.lease_status == "leased":
                status = "leased-without-handle"
                note = (
                    "The lease metadata exists, but no restorer is registered for "
                    "this channel."
                )
        resume_kind = self._recovery_resume_kind({"status": status})
        return {
            "status": status,
            "recoverable": recoverable,
            "resume_kind": resume_kind,
            "mode": resume_kind,
            "host_id": locality["lease_host_id"] or lease_runtime.get("host_id"),
            "process_id": locality["lease_process_id"]
            or lease_runtime.get("process_id"),
            "current_host_id": locality["current_host_id"],
            "current_process_id": locality["current_process_id"],
            "same_host": bool(locality["same_host"]),
            "same_process": bool(locality["same_process"]),
            "startup_recovery_required": startup_recovery_required,
            "last_seen_at": lease_runtime.get("seen_at"),
            "note": note,
            "environment_ref": environment_ref,
            "replay_support": {
                "replay_count": replay_count,
                "executor_types": self._service._replay_service.executor_types,
                "fallback_mode": "kernel",
            },
        }

    def _select_primary_session(
        self,
        sessions: list[SessionMount],
    ) -> SessionMount | None:
        if not sessions:
            return None
        for item in sessions:
            if item.lease_status == "leased":
                return item
        return sessions[0]

    def _surface_runtime_context(
        self,
        *,
        mount,
        session: SessionMount | None,
        live_handle: dict[str, object] | None,
    ) -> tuple[
        dict[str, object],
        dict[str, object],
        dict[str, object],
        dict[str, object],
        dict[str, object],
    ]:
        mount_metadata = self._mapping(getattr(mount, "metadata", None))
        session_metadata = self._mapping(session.metadata if session is not None else None)
        lease_service = self._service._lease_service
        runtime_metadata = (
            lease_service.lease_runtime_mapping(session_metadata)
            if session is not None
            else lease_service.lease_runtime_mapping(mount_metadata)
        )
        runtime_descriptor = (
            lease_service.lease_runtime_descriptor(session_metadata)
            if session is not None
            else lease_service.lease_runtime_descriptor(mount_metadata)
        )
        live_descriptor = self._mapping(
            self._mapping(live_handle).get("descriptor"),
        )
        return (
            mount_metadata,
            session_metadata,
            runtime_metadata,
            runtime_descriptor,
            live_descriptor,
        )

    def _recovery_resume_kind(self, recovery: dict[str, object]) -> str | None:
        status = self._first_string(recovery.get("status"))
        if status in {"attached", "restorable"}:
            return "resume-environment"
        if status == "same-host-other-process":
            return "rebind-environment"
        if status == "remote":
            return "attach-environment"
        if status in {"detached", "ownership-unknown", "leased-without-handle"}:
            return "fresh"
        return None

    def _iso_timestamp(self, value: object) -> str | None:
        if isinstance(value, datetime):
            return value.isoformat()
        return self._first_string(value)

    def _mapping(self, value: object) -> dict[str, object]:
        return dict(value) if isinstance(value, dict) else {}

    def _first_mapping(self, *values: object) -> dict[str, object]:
        for value in values:
            if isinstance(value, dict):
                return dict(value)
        return {}

    def _first_string(self, *values: object) -> str | None:
        for value in values:
            if isinstance(value, str):
                normalized = value.strip()
                if normalized:
                    return normalized
        return None

    def _first_bool(self, *values: object) -> bool | None:
        for value in values:
            if isinstance(value, bool):
                return value
        return None

    def _positive_timeout(self, *values: object) -> float | None:
        for value in values:
            try:
                timeout = float(value)
            except (TypeError, ValueError):
                continue
            if timeout > 0:
                return timeout
        return None

    def _first_int(self, *values: object) -> int | None:
        for value in values:
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                return value
        return None

    def _build_bridge_registration_projection(
        self,
        *sources: object,
    ) -> dict[str, object]:
        mappings = [self._mapping(source) for source in sources]
        projection: dict[str, object] = {
            "worker_type": self._first_string(
                *(mapping.get("worker_type") for mapping in mappings),
            ),
            "max_sessions": self._first_int(
                *(mapping.get("max_sessions") for mapping in mappings),
            ),
            "spawn_mode": self._first_string(
                *(mapping.get("spawn_mode") for mapping in mappings),
            ),
            "reuse_environment_id": self._first_string(
                *(mapping.get("reuse_environment_id") for mapping in mappings),
            ),
        }
        optional_values = {
            "bridge_work_id": self._first_string(
                *(mapping.get("bridge_work_id") for mapping in mappings),
            ),
            "bridge_work_status": self._first_string(
                *(mapping.get("bridge_work_status") for mapping in mappings),
            ),
            "bridge_heartbeat_at": self._first_string(
                *(mapping.get("bridge_heartbeat_at") for mapping in mappings),
            ),
            "bridge_session_id": self._first_string(
                *(mapping.get("bridge_session_id") for mapping in mappings),
            ),
            "bridge_stopped_at": self._first_string(
                *(mapping.get("bridge_stopped_at") for mapping in mappings),
            ),
            "bridge_stop_mode": self._first_string(
                *(mapping.get("bridge_stop_mode") for mapping in mappings),
            ),
            "workspace_trusted": self._first_bool(
                *(mapping.get("workspace_trusted") for mapping in mappings),
            ),
            "elevated_auth_state": self._first_string(
                *(mapping.get("elevated_auth_state") for mapping in mappings),
            ),
        }
        for key, value in optional_values.items():
            if value is not None:
                projection[key] = value
        return projection

    def _build_operator_abort_state_projection(
        self,
        *sources: object,
    ) -> dict[str, object]:
        mappings = [self._mapping(source) for source in sources]
        channel = self._first_string(
            *(mapping.get("channel") for mapping in mappings),
            *(mapping.get("operator_abort_channel") for mapping in mappings),
        )
        requested = self._first_bool(
            *(mapping.get("requested") for mapping in mappings),
            *(mapping.get("operator_abort_requested") for mapping in mappings),
        )
        reason = self._first_string(
            *(mapping.get("reason") for mapping in mappings),
            *(mapping.get("abort_reason") for mapping in mappings),
        )
        requested_at = self._first_string(
            *(mapping.get("requested_at") for mapping in mappings),
            *(mapping.get("operator_abort_requested_at") for mapping in mappings),
        )
        projection: dict[str, object] = {}
        if channel is not None:
            projection["channel"] = channel
        if requested is not None:
            projection["requested"] = requested
        if reason is not None:
            projection["reason"] = reason
        if requested_at is not None:
            projection["requested_at"] = requested_at
        return projection

    def _merge_operator_abort_guardrails_projection(
        self,
        guardrails: dict[str, object],
        operator_abort_state: dict[str, object],
    ) -> dict[str, object]:
        merged = dict(guardrails)
        channel = self._first_string(
            merged.get("operator_abort_channel"),
            operator_abort_state.get("channel"),
        )
        if channel is not None:
            merged["operator_abort_channel"] = channel
        requested = merged.get("operator_abort_requested")
        if requested is not True:
            state_requested = operator_abort_state.get("requested")
            if state_requested is not None:
                requested = state_requested
        if requested is not None:
            merged["operator_abort_requested"] = requested
        reason = self._first_string(
            merged.get("abort_reason"),
            operator_abort_state.get("reason"),
        )
        if reason is not None:
            merged["abort_reason"] = reason
        requested_at = self._first_string(
            merged.get("operator_abort_requested_at"),
            operator_abort_state.get("requested_at"),
        )
        if requested_at is not None:
            merged["operator_abort_requested_at"] = requested_at
        return merged

    def _sanitize_prompt_facing_host_label(
        self,
        value: object,
        *,
        max_length: int = 80,
    ) -> str | None:
        normalized = self._first_string(value)
        if normalized is None:
            return None
        sanitized = self._HOST_LABEL_CONTROL_RE.sub(" ", normalized)
        sanitized = sanitized.replace("`", " ")
        sanitized = sanitized.replace("<", " ")
        sanitized = sanitized.replace(">", " ")
        sanitized = sanitized.replace("|", " ")
        sanitized = self._HOST_LABEL_WHITESPACE_RE.sub(" ", sanitized).strip()
        if not sanitized:
            return None
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length].rstrip()
        return sanitized or None

    def _sanitize_window_anchor_summary(self, value: object) -> str | None:
        normalized = self._first_string(value)
        if normalized is None:
            return None
        preserved = normalized.replace(" > ", "__COPAW_GT__")
        preserved = self._HOST_LABEL_CONTROL_RE.sub(" ", preserved)
        preserved = preserved.replace("`", " ")
        preserved = preserved.replace("<", " ")
        preserved = preserved.replace(">", " ")
        preserved = preserved.replace("|", " ")
        preserved = preserved.replace("__COPAW_GT__", " > ")
        sanitized = self._HOST_LABEL_WHITESPACE_RE.sub(" ", preserved).strip()
        if not sanitized:
            return None
        if len(sanitized) > 160:
            sanitized = sanitized[:160].rstrip()
        return sanitized or None

    def _normalize_process_id(self, value: object) -> int | None:
        return self._service._lease_service.normalize_process_id(value)

    def _string_list(self, value: object) -> list[str]:
        if isinstance(value, str):
            normalized = value.strip()
            return [normalized] if normalized else []
        if not isinstance(value, list):
            return []
        result: list[str] = []
        seen: set[str] = set()
        for item in value:
            if isinstance(item, str):
                normalized = item.strip()
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    result.append(normalized)
        return result

    def _merge_string_lists(self, *values: object) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for value in values:
            for item in self._string_list(value):
                if item in seen:
                    continue
                seen.add(item)
                merged.append(item)
        return merged

    def _merge_projection_refs(
        self,
        *primary_sources: object,
        fallback_sources: tuple[object, ...] = (),
    ) -> list[str]:
        merged = self._merge_string_lists(*primary_sources)
        if merged:
            return merged
        return self._merge_string_lists(*fallback_sources)

    def _host_event_latest(
        self,
        host_event_summary: dict[str, object],
        family: str,
    ) -> dict[str, object] | None:
        latest_by_family = self._mapping(host_event_summary.get("latest_event_by_family"))
        latest = self._mapping(latest_by_family.get(family))
        return latest or None

    def _blocking_host_event(
        self,
        host_event_summary: dict[str, object],
    ) -> dict[str, object] | None:
        explicit = self._mapping(host_event_summary.get("latest_blocking_event"))
        if explicit:
            return explicit
        for family in (
            "modal-uac-login",
            "process-exit-restart",
            "lock-unlock",
            "network-power",
        ):
            latest = self._host_event_latest(host_event_summary, family)
            if latest is not None:
                return latest
        latest_event = self._mapping(host_event_summary.get("latest_event"))
        return latest_event or None

    def _host_event_gap_or_blocker(
        self,
        event: dict[str, object] | None,
    ) -> str | None:
        if event is None:
            return None
        family = self._first_string(event.get("event_family"))
        action = self._first_string(event.get("action"))
        event_name = self._first_string(event.get("event_name"))
        payload = self._mapping(event.get("payload"))
        prompt_kind = self._first_string(
            payload.get("prompt_kind"),
            payload.get("modal_kind"),
            payload.get("challenge_kind"),
        )
        if family == "modal-uac-login":
            normalized = (prompt_kind or action or event_name or "").strip().lower()
            if normalized == "uac":
                return "uac-prompt"
            if normalized == "login":
                return "login-required"
            if normalized == "captcha":
                return "captcha-required"
            if normalized == "mfa":
                return "mfa-required"
            if normalized == "modal":
                return "modal-interruption"
        return self._first_string(
            action,
            event_name,
            payload.get("window_title"),
            payload.get("process_ref"),
            payload.get("network_state"),
            payload.get("power_state"),
        )

    def _host_event_handoff_state(
        self,
        event: dict[str, object] | None,
    ) -> str | None:
        family = self._first_string(event.get("event_family") if event is not None else None)
        if family == "modal-uac-login":
            return "handoff-required"
        return None

    def _latest_handoff_event(
        self,
        events: list[dict[str, object]],
    ) -> dict[str, object] | None:
        for event in reversed(events):
            payload = self._mapping(event.get("payload"))
            family = self._first_string(event.get("event_family"))
            action = self._first_string(event.get("action"))
            if family == "modal-uac-login":
                return dict(event)
            if self._first_string(
                payload.get("handoff_state"),
                payload.get("handoff_owner_ref"),
                payload.get("return_condition"),
            ):
                return dict(event)
            if action and action.lower() in {
                "handoff-required",
                "handoff-returned",
                "human-returned",
                "resume-attached",
            }:
                return dict(event)
        return None

    def _build_host_twin_app_family_twins(
        self,
        *,
        browser_site_contract: dict[str, object],
        desktop_app_contract: dict[str, object],
        surface_mutability: dict[str, dict[str, object]],
    ) -> dict[str, dict[str, object]]:
        browser_surface_ref = self._first_string(
            self._mapping(surface_mutability.get("browser")).get("surface_ref"),
        )
        desktop_surface_ref = self._first_string(
            self._mapping(surface_mutability.get("desktop_app")).get("surface_ref"),
        )
        active_site = self._first_string(browser_site_contract.get("active_site"))
        browser_contract_status = self._first_string(
            browser_site_contract.get("site_contract_status"),
        )
        app_identity = self._first_string(desktop_app_contract.get("app_identity"))
        desktop_contract_status = self._first_string(
            desktop_app_contract.get("app_contract_status"),
        )
        writer_lock_scope = self._first_string(
            desktop_app_contract.get("writer_lock_scope"),
        )
        messaging_markers = ("wechat", "slack", "telegram", "whatsapp", "qq")
        messaging_active = bool(
            active_site is not None
            and any(marker in active_site.lower() for marker in messaging_markers)
        )
        office_active = bool(
            writer_lock_scope is not None
            or (app_identity or "").lower() in {"excel", "word", "powerpoint", "wps"}
        )
        desktop_specialized_active = bool(app_identity is not None and not office_active)
        return {
            "browser_backoffice": {
                "active": active_site is not None and not messaging_active,
                "family_kind": "browser_backoffice",
                "surface_ref": (
                    browser_surface_ref
                    if active_site is not None and not messaging_active
                    else None
                ),
                "contract_status": (
                    browser_contract_status
                    if active_site is not None and not messaging_active
                    else "inactive"
                ),
                "family_scope_ref": (
                    f"site:{active_site}"
                    if active_site is not None and not messaging_active
                    else None
                ),
            },
            "messaging_workspace": {
                "active": messaging_active,
                "family_kind": "messaging_workspace",
                "surface_ref": browser_surface_ref if messaging_active else None,
                "contract_status": browser_contract_status if messaging_active else "inactive",
                "family_scope_ref": (
                    f"site:{active_site}"
                    if messaging_active and active_site is not None
                    else None
                ),
            },
            "office_document": {
                "active": office_active,
                "family_kind": "office_document",
                "surface_ref": desktop_surface_ref if office_active else None,
                "contract_status": (
                    desktop_contract_status if office_active else "inactive"
                ),
                "family_scope_ref": (
                    f"app:{app_identity}"
                    if office_active and app_identity is not None
                    else None
                ),
                "writer_lock_scope": writer_lock_scope if office_active else None,
            },
            "desktop_specialized": {
                "active": desktop_specialized_active,
                "family_kind": "desktop_specialized",
                "surface_ref": desktop_surface_ref if desktop_specialized_active else None,
                "contract_status": (
                    desktop_contract_status
                    if desktop_specialized_active
                    else "inactive"
                ),
                "family_scope_ref": (
                    f"app:{app_identity}"
                    if desktop_specialized_active and app_identity is not None
                    else None
                ),
            },
        }

    def _build_host_twin_coordination(
        self,
        *,
        workspace_graph: dict[str, object],
        ownership: dict[str, object],
        seat_runtime: dict[str, object],
        host_contract: dict[str, object],
        latest_blocking_event: dict[str, object],
        recovered_runtime_ready: bool,
    ) -> dict[str, object]:
        workspace_ownership = self._mapping(workspace_graph.get("ownership"))
        locks = list(workspace_graph.get("locks") or [])
        writer_owner_ref = None
        for lock in locks:
            if not isinstance(lock, dict):
                continue
            writer_lock = self._mapping(lock.get("writer_lock"))
            writer_owner_ref = self._first_string(
                writer_lock.get("owner_agent_id"),
                lock.get("owner_agent_id"),
            )
            if writer_owner_ref is not None:
                break
        seat_owner_ref = self._first_string(
            ownership.get("seat_owner_agent_id"),
            seat_runtime.get("lease_owner"),
            host_contract.get("lease_owner"),
        )
        workspace_owner_ref = self._first_string(
            workspace_ownership.get("owner_agent_id"),
            workspace_graph.get("owner_agent_id"),
            seat_owner_ref,
        )
        writer_owner_ref = self._first_string(writer_owner_ref, workspace_owner_ref)
        candidate_seats = [
            self._mapping(item)
            for item in list(seat_runtime.get("candidate_seats") or [])
            if isinstance(item, dict)
        ]
        candidate_seat_refs = self._string_list(seat_runtime.get("candidate_seat_refs"))
        selected_seat_ref = self._first_string(
            seat_runtime.get("selected_seat_ref"),
            seat_runtime.get("seat_ref"),
        )
        selected_session_mount_id = self._first_string(
            seat_runtime.get("selected_session_mount_id"),
            seat_runtime.get("active_session_mount_id"),
        )
        selected_candidate = next(
            (
                item
                for item in candidate_seats
                if self._first_string(item.get("session_mount_id")) == selected_session_mount_id
                or self._first_string(item.get("seat_ref")) == selected_seat_ref
            ),
            None,
        )
        selected_candidate_ready = bool(
            isinstance(selected_candidate, dict) and selected_candidate.get("ready") is True
        )
        blocking_family = self._first_string(latest_blocking_event.get("event_family"))
        active_handoff_owner_ref = None
        if not recovered_runtime_ready:
            active_handoff_owner_ref = self._first_string(
                host_contract.get("handoff_owner_ref"),
            )
        cross_owner_conflict = next(
            (
                item
                for item in candidate_seats
                if self._first_string(item.get("owner_agent_id")) not in {None, seat_owner_ref}
                and self._first_string(item.get("writer_lock_scope")) is not None
            ),
            None,
        )
        blocking_reason = self._first_string(
            None if recovered_runtime_ready else host_contract.get("handoff_reason"),
            None
            if recovered_runtime_ready
            else host_contract.get("current_gap_or_blocker"),
            (
                f"writer scope is contested by "
                f"{self._first_string(cross_owner_conflict.get('owner_agent_id'))} "
                f"on {self._first_string(cross_owner_conflict.get('seat_ref'))}"
                if cross_owner_conflict is not None
                else None
            ),
            latest_blocking_event.get("event_name"),
            workspace_graph.get("active_lock_summary"),
        )
        severity = "clear"
        if (
            blocking_family is not None
            or active_handoff_owner_ref is not None
            or cross_owner_conflict is not None
        ):
            severity = "blocked"
        if (
            selected_candidate_ready
            and selected_seat_ref is not None
            and selected_seat_ref != seat_runtime.get("seat_ref")
            and self._first_string(selected_candidate.get("owner_agent_id"))
            in {None, seat_owner_ref}
            and cross_owner_conflict is None
        ):
            severity = "clear"
            active_handoff_owner_ref = None
            blocking_family = None
            blocking_reason = self._first_string(
                f"canonical seat switched to {selected_seat_ref}",
                blocking_reason,
            )
        legal_owner_transition = {
            "allowed": severity != "blocked",
            "reason": (
                "human handoff is still active"
                if active_handoff_owner_ref is not None
                else (blocking_reason or "coordination-ready")
            ),
        }
        recommended_scheduler_action = "proceed"
        if severity == "blocked":
            recommended_scheduler_action = "handoff"
        elif selected_seat_ref is not None and selected_seat_ref != seat_runtime.get("seat_ref"):
            recommended_scheduler_action = "continue"
        return {
            "seat_owner_ref": seat_owner_ref,
            "workspace_owner_ref": workspace_owner_ref,
            "writer_owner_ref": writer_owner_ref,
            "candidate_seat_refs": candidate_seat_refs
            or ([selected_seat_ref] if selected_seat_ref is not None else []),
            "candidate_seats": candidate_seats,
            "selected_seat_ref": selected_seat_ref,
            "selected_session_mount_id": selected_session_mount_id,
            "seat_selection_policy": self._first_string(
                seat_runtime.get("seat_selection_policy"),
            ),
            "contention_forecast": {
                "severity": severity,
                "reason": blocking_reason,
            },
            "legal_owner_transition": legal_owner_transition,
            "recommended_scheduler_action": recommended_scheduler_action,
            "expected_release_at": seat_runtime.get("expected_release_at"),
        }

    def _build_host_twin_ownership(
        self,
        *,
        workspace_graph: dict[str, object],
        seat_runtime: dict[str, object],
        host_contract: dict[str, object],
    ) -> dict[str, object]:
        workspace_ownership = self._mapping(workspace_graph.get("ownership"))
        seat_owner_agent_id = self._first_string(
            workspace_ownership.get("owner_agent_id"),
            seat_runtime.get("lease_owner"),
            host_contract.get("lease_owner"),
        )
        handoff_owner_ref = self._first_string(
            workspace_ownership.get("handoff_owner_ref"),
            workspace_graph.get("handoff_owner_ref"),
            host_contract.get("handoff_owner_ref"),
        )
        ownership_source = "workspace_graph.ownership"
        if self._first_string(workspace_ownership.get("owner_agent_id")) is None:
            ownership_source = "seat_runtime.lease_owner"
        active_owner_kind = "unknown"
        if seat_owner_agent_id and handoff_owner_ref:
            active_owner_kind = "agent-with-human-handoff"
        elif seat_owner_agent_id:
            active_owner_kind = "agent"
        elif handoff_owner_ref:
            active_owner_kind = "human-handoff"
        return {
            "seat_owner_agent_id": seat_owner_agent_id,
            "handoff_owner_ref": handoff_owner_ref,
            "account_scope_ref": self._first_string(
                workspace_ownership.get("account_scope_ref"),
                workspace_graph.get("account_scope_ref"),
                host_contract.get("account_scope_ref"),
            ),
            "workspace_scope": self._first_string(
                workspace_ownership.get("workspace_scope"),
                workspace_graph.get("workspace_scope"),
                seat_runtime.get("workspace_scope"),
            ),
            "ownership_source": ownership_source,
            "active_owner_kind": active_owner_kind,
        }

    def _build_host_twin_surface_mutability(
        self,
        *,
        workspace_graph: dict[str, object],
        host_contract: dict[str, object],
        browser_site_contract: dict[str, object],
        desktop_app_contract: dict[str, object],
        host_event_summary: dict[str, object],
        recovery: dict[str, object],
    ) -> dict[str, dict[str, object]]:
        surfaces = self._mapping(workspace_graph.get("surfaces"))
        browser_surface = self._mapping(surfaces.get("browser"))
        desktop_surface = self._mapping(surfaces.get("desktop"))
        file_docs_surface = self._mapping(surfaces.get("file_docs"))
        host_blocker = self._mapping(surfaces.get("host_blocker"))
        recovered_runtime_ready = self._host_twin_recovered_runtime_ready(
            host_contract=host_contract,
            recovery=recovery,
            host_event_summary=host_event_summary,
        )
        blocking_family = self._first_string(
            host_blocker.get("event_family"),
            self._mapping(self._blocking_host_event(host_event_summary)).get(
                "event_family",
            ),
        )
        blocking_reason = self._first_string(
            host_contract.get("handoff_reason"),
            host_contract.get("current_gap_or_blocker"),
            host_blocker.get("event_name"),
        )
        if recovered_runtime_ready:
            blocking_family = None
            blocking_reason = None
        recovery_path = self._first_string(
            self._mapping(workspace_graph.get("handoff_checkpoint")).get("resume_kind"),
            host_contract.get("resume_kind"),
            recovery.get("mode"),
        )
        requires_handoff = bool(
            self._first_string(
                host_contract.get("handoff_state"),
                host_contract.get("handoff_owner_ref"),
                host_contract.get("current_gap_or_blocker"),
            ),
        )
        if recovered_runtime_ready:
            requires_handoff = False
        def _entry(surface_ref: str | None, writer_ready: bool) -> dict[str, object]:
            if surface_ref is None:
                return {
                    "surface_ref": None,
                    "mutability": "unavailable",
                    "safe_to_mutate": False,
                    "blocker_family": blocking_family,
                    "reason": blocking_reason,
                }
            if blocking_family is not None or requires_handoff:
                return {
                    "surface_ref": surface_ref,
                    "mutability": "blocked",
                    "safe_to_mutate": False,
                    "blocker_family": blocking_family,
                    "reason": blocking_reason,
                }
            if writer_ready:
                return {
                    "surface_ref": surface_ref,
                    "mutability": "writable",
                    "safe_to_mutate": True,
                    "blocker_family": None,
                    "reason": recovery_path,
                }
            return {
                "surface_ref": surface_ref,
                "mutability": "read-only",
                "safe_to_mutate": False,
                "blocker_family": None,
                "reason": recovery_path,
            }
        browser_ref = self._first_string(
            self._string_list(browser_surface.get("context_refs"))[0]
            if self._string_list(browser_surface.get("context_refs"))
            else None,
        )
        desktop_ref = self._first_string(
            self._string_list(desktop_surface.get("window_refs"))[0]
            if self._string_list(desktop_surface.get("window_refs"))
            else None,
            self._mapping(desktop_surface.get("active_window")).get("window_ref"),
        )
        file_doc_ref = self._first_string(
            file_docs_surface.get("active_doc_ref"),
        )
        browser_writer_ready = self._first_string(
            browser_site_contract.get("site_contract_status"),
        ) in {"verified-writer", "writer-ready", "ready"}
        desktop_writer_ready = self._first_string(
            desktop_app_contract.get("app_contract_status"),
        ) in {"verified-writer", "writer-ready", "ready"}
        file_doc_writer_ready = bool(file_doc_ref)
        return {
            "browser": _entry(browser_ref, browser_writer_ready),
            "desktop_app": _entry(desktop_ref, desktop_writer_ready),
            "file_docs": _entry(file_doc_ref, file_doc_writer_ready),
        }

    def _build_host_twin_continuity(
        self,
        *,
        host_contract: dict[str, object],
        recovery: dict[str, object],
        host_companion_session: dict[str, object],
        recovered_runtime_ready: bool,
    ) -> dict[str, object]:
        continuity_status = self._first_string(
            host_companion_session.get("continuity_status"),
            recovery.get("status"),
        )
        continuity_source = self._first_string(
            host_companion_session.get("continuity_source"),
        )
        valid = continuity_status in {
            "attached",
            "restorable",
            "same-host-other-process",
        }
        requires_human_return = bool(
            self._first_string(
                host_contract.get("handoff_owner_ref"),
                host_contract.get("handoff_state"),
                host_contract.get("current_gap_or_blocker"),
            ),
        )
        if recovered_runtime_ready:
            requires_human_return = False
        status = "blocked"
        if valid and requires_human_return:
            status = "guarded"
        elif valid:
            status = "ready"
        return {
            "status": status,
            "is_valid": valid,
            "valid": valid,
            "source": continuity_source,
            "continuity_source": continuity_source,
            "resume_kind": self._first_string(
                host_contract.get("resume_kind"),
                recovery.get("resume_kind"),
            ),
            "requires_human_return": requires_human_return,
        }

    def _build_host_twin_trusted_anchors(
        self,
        *,
        workspace_graph: dict[str, object],
        browser_site_contract: dict[str, object],
        desktop_app_contract: dict[str, object],
    ) -> list[dict[str, object]]:
        surfaces = self._mapping(workspace_graph.get("surfaces"))
        browser_surface = self._mapping(surfaces.get("browser"))
        desktop_surface = self._mapping(surfaces.get("desktop"))
        handoff_checkpoint = self._mapping(workspace_graph.get("handoff_checkpoint"))
        anchors: list[dict[str, object]] = []
        browser_anchor = self._first_string(
            browser_site_contract.get("last_verified_dom_anchor"),
            browser_site_contract.get("verification_anchor"),
        )
        if browser_anchor is not None:
            anchors.append(
                {
                    "anchor_kind": "browser-dom",
                    "surface_ref": self._first_string(
                        self._string_list(browser_surface.get("context_refs"))[0]
                        if self._string_list(browser_surface.get("context_refs"))
                        else None,
                    ),
                    "anchor_ref": browser_anchor,
                    "source": "browser_site_contract.last_verified_dom_anchor",
                },
            )
        desktop_anchor = self._first_string(
            desktop_app_contract.get("window_anchor_summary"),
            desktop_app_contract.get("verification_anchor"),
        )
        if desktop_anchor is not None:
            anchors.append(
                {
                    "anchor_kind": "desktop-window",
                    "surface_ref": self._first_string(
                        self._string_list(desktop_surface.get("window_refs"))[0]
                        if self._string_list(desktop_surface.get("window_refs"))
                        else None,
                        self._mapping(desktop_surface.get("active_window")).get(
                            "window_ref",
                        ),
                    ),
                    "anchor_ref": desktop_anchor,
                    "source": "desktop_app_contract.window_anchor_summary",
                },
            )
        checkpoint_ref = self._first_string(handoff_checkpoint.get("checkpoint_ref"))
        if checkpoint_ref is not None:
            anchors.append(
                {
                    "anchor_kind": "checkpoint",
                    "surface_ref": checkpoint_ref,
                    "anchor_ref": checkpoint_ref,
                    "source": "workspace_graph.handoff_checkpoint",
                },
            )
        return anchors

    def _build_host_twin_legal_recovery(
        self,
        *,
        workspace_graph: dict[str, object],
        host_contract: dict[str, object],
        recovery: dict[str, object],
    ) -> dict[str, object]:
        handoff_checkpoint = self._mapping(workspace_graph.get("handoff_checkpoint"))
        path = "handoff"
        if not self._first_string(
            handoff_checkpoint.get("state"),
            host_contract.get("handoff_state"),
            host_contract.get("handoff_owner_ref"),
        ):
            path = self._first_string(
                handoff_checkpoint.get("resume_kind"),
                host_contract.get("resume_kind"),
                recovery.get("mode"),
                recovery.get("resume_kind"),
            ) or "fresh"
        return {
            "path": path,
            "checkpoint_ref": self._first_string(handoff_checkpoint.get("checkpoint_ref")),
            "resume_kind": self._first_string(
                handoff_checkpoint.get("resume_kind"),
                host_contract.get("resume_kind"),
                recovery.get("resume_kind"),
            ),
            "verification_channel": self._first_string(
                handoff_checkpoint.get("verification_channel"),
                host_contract.get("verification_channel"),
            ),
            "return_condition": self._first_string(
                handoff_checkpoint.get("return_condition"),
            ),
        }

    def _build_host_twin_latest_blocking_event(
        self,
        *,
        workspace_graph: dict[str, object],
        host_event_summary: dict[str, object],
        surface_mutability: dict[str, dict[str, object]],
        host_contract: dict[str, object],
        recovery: dict[str, object],
    ) -> dict[str, object]:
        if self._host_twin_recovered_runtime_ready(
            host_contract=host_contract,
            recovery=recovery,
            host_event_summary=host_event_summary,
        ):
            return {
                "event_family": None,
                "event_name": None,
                "recommended_runtime_response": None,
                "surface_refs": [],
            }
        surfaces = self._mapping(workspace_graph.get("surfaces"))
        host_blocker = self._mapping(surfaces.get("host_blocker"))
        blocker_event = self._blocking_host_event(host_event_summary)
        event_family = self._first_string(
            host_blocker.get("event_family"),
            blocker_event.get("event_family") if blocker_event is not None else None,
        )
        event_name = self._first_string(
            host_blocker.get("event_name"),
            blocker_event.get("action") if blocker_event is not None else None,
            blocker_event.get("event_name") if blocker_event is not None else None,
        )
        recommended_runtime_response = self._first_string(
            host_blocker.get("recommended_runtime_response"),
            blocker_event.get("recommended_runtime_response")
            if blocker_event is not None
            else None,
        )
        surface_refs = [
            details.get("surface_ref")
            for details in surface_mutability.values()
            if self._first_string(details.get("surface_ref")) is not None
        ]
        return {
            "event_family": event_family,
            "event_name": event_name,
            "recommended_runtime_response": recommended_runtime_response,
            "surface_refs": surface_refs,
        }

    def _host_twin_recovered_runtime_ready(
        self,
        *,
        host_contract: dict[str, object],
        recovery: dict[str, object],
        host_event_summary: dict[str, object],
    ) -> bool:
        recovery_status = self._first_string(
            recovery.get("status"),
            recovery.get("state"),
        )
        if recovery_status not in {"attached", "completed", "ready", "stable"}:
            return False
        latest_handoff_event = self._mapping(host_event_summary.get("latest_handoff_event"))
        latest_handoff_name = self._first_string(
            latest_handoff_event.get("event_name"),
            latest_handoff_event.get("action"),
        )
        return latest_handoff_name in {
            "host.human-return-ready",
            "human-return-ready",
            "host.return-complete",
            "return-complete",
        }

    def _host_event_resume_kind(
        self,
        event: dict[str, object],
    ) -> str:
        _ = event
        return "resume-environment"

    def _derive_site_identity(self, *values: object) -> str | None:
        for value in values:
            normalized = self._first_string(value)
            if normalized is None:
                continue
            if "://" in normalized:
                return normalized
            parts = normalized.split(":")
            if parts and parts[0] in {"site-contract", "page"} and len(parts) >= 3:
                return ":".join(parts[1:-1])
            if parts and parts[0] == "site" and len(parts) >= 2:
                return ":".join(parts[1:])
        return None

    def _backfill_host_event_summary_contract(
        self,
        *,
        host_event_summary: dict[str, object],
        host_contract: dict[str, object],
    ) -> None:
        verification_channel = self._first_string(
            host_contract.get("verification_channel"),
        )
        resume_kind = self._first_string(
            host_contract.get("resume_kind"),
        ) or "resume-environment"
        pending_events = host_event_summary.get("pending_recovery_events")
        if not isinstance(pending_events, list):
            return
        for event in pending_events:
            if not isinstance(event, dict):
                continue
            checkpoint = self._mapping(event.get("checkpoint"))
            if self._first_string(checkpoint.get("resume_kind")) is None:
                checkpoint["resume_kind"] = resume_kind
            if (
                verification_channel is not None
                and self._first_string(checkpoint.get("verification_channel")) is None
            ):
                checkpoint["verification_channel"] = verification_channel
            event["checkpoint"] = checkpoint
