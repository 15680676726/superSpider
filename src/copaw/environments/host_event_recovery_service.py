# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from ..app.runtime_events import RuntimeEvent, RuntimeEventBus


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _string(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _mapping(value: object | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


@dataclass(frozen=True)
class HostRecoveryAction:
    event_id: int
    event_name: str
    session_mount_id: str
    environment_id: str | None
    decision: str
    reason: str
    resume_kind: str | None = None
    verification_channel: str | None = None
    checkpoint_ref: str | None = None
    return_condition: str | None = None
    handoff_owner_ref: str | None = None
    event_family: str | None = None

    @property
    def action_id(self) -> str:
        return f"{self.session_mount_id}:{self.event_id}:{self.decision}"


class HostEventRecoveryService:
    def __init__(
        self,
        environment_service,
        runtime_event_bus: RuntimeEventBus | None = None,
    ) -> None:
        self._environment_service = environment_service
        self._runtime_event_bus = runtime_event_bus or getattr(
            environment_service,
            "_runtime_event_bus",
            None,
        )

    def plan_recovery(
        self,
        *,
        after_event_id: int = 0,
        limit: int = 100,
        session_mount_id: str | None = None,
        allow_cross_process_recovery: bool = False,
    ) -> dict[str, Any]:
        actions: list[HostRecoveryAction] = []
        skipped: list[dict[str, Any]] = []
        for event in self._list_actionable_events(after_event_id=after_event_id, limit=limit):
            planned = self._plan_event(
                event,
                session_mount_id=session_mount_id,
                allow_cross_process_recovery=allow_cross_process_recovery,
            )
            if isinstance(planned, HostRecoveryAction):
                actions.append(planned)
                continue
            if isinstance(planned, dict):
                skipped.append(planned)
        return {
            "actions": [self._serialize_action(action) for action in actions],
            "planned": len(actions),
            "skipped": len(skipped),
            "skipped_events": skipped,
            "last_seen_event_id": max(
                [after_event_id, *[action.event_id for action in actions], *[
                    int(item.get("event_id") or 0) for item in skipped
                ]],
            ),
        }

    def run_recovery_cycle(
        self,
        *,
        after_event_id: int = 0,
        limit: int = 100,
        session_mount_id: str | None = None,
        allow_cross_process_recovery: bool = False,
    ) -> dict[str, Any]:
        plan = self.plan_recovery(
            after_event_id=after_event_id,
            limit=limit,
            session_mount_id=session_mount_id,
            allow_cross_process_recovery=allow_cross_process_recovery,
        )
        executed_actions: list[dict[str, Any]] = []
        skipped = int(plan.get("skipped") or 0)
        failed = 0
        decisions: dict[str, int] = {}
        for payload in list(plan.get("actions") or []):
            action = HostRecoveryAction(
                **{key: value for key, value in payload.items() if key != "action_id"},
            )
            result = self._execute_action(action)
            if result.get("executed"):
                executed_actions.append(result)
                decisions[action.decision] = decisions.get(action.decision, 0) + 1
            elif result.get("skipped"):
                skipped += 1
            else:
                failed += 1
        return {
            "executed": len(executed_actions),
            "skipped": skipped,
            "failed": failed,
            "planned": int(plan.get("planned") or 0),
            "decisions": decisions,
            "actions": executed_actions,
            "last_seen_event_id": plan.get("last_seen_event_id"),
        }

    def _list_actionable_events(
        self,
        *,
        after_event_id: int,
        limit: int,
    ) -> list[RuntimeEvent]:
        if self._runtime_event_bus is None:
            return []
        events = self._runtime_event_bus.list_events(after_id=after_event_id, limit=limit)
        return [
            event
            for event in events
            if event.topic in {"host", "desktop", "download"}
            and isinstance(event.payload, dict)
            and _string(event.payload.get("session_mount_id")) is not None
        ]

    def _plan_event(
        self,
        event: RuntimeEvent,
        *,
        session_mount_id: str | None,
        allow_cross_process_recovery: bool,
    ) -> HostRecoveryAction | dict[str, Any] | None:
        payload = _mapping(event.payload)
        target_session_mount_id = _string(payload.get("session_mount_id"))
        if target_session_mount_id is None:
            return None
        if session_mount_id is not None and target_session_mount_id != session_mount_id:
            return None
        session = self._get_session_record(target_session_mount_id)
        if session is None:
            return {
                "event_id": event.event_id,
                "event_name": event.event_name,
                "reason": "missing-session",
            }
        if not self._session_recovery_allowed(
            session,
            allow_cross_process_recovery=allow_cross_process_recovery,
        ):
            return {
                "event_id": event.event_id,
                "event_name": event.event_name,
                "reason": "cross-process-recovery-disabled",
            }
        recovery_state = _mapping(session.metadata.get("host_recovery_state"))
        last_handled_event_id = recovery_state.get("last_handled_event_id")
        if isinstance(last_handled_event_id, int) and last_handled_event_id >= event.event_id:
            return {
                "event_id": event.event_id,
                "event_name": event.event_name,
                "reason": "already-handled",
            }
        host_contract = self._build_host_contract(session)
        cooperative = self._build_cooperative_detail(session)
        decision = self._resolve_decision(
            event=event,
            session=session,
            host_contract=host_contract,
            cooperative=cooperative,
        )
        if decision is None:
            return None
        reason = (
            _string(payload.get("reason"))
            or _string(host_contract.get("current_gap_or_blocker"))
            or _string(cooperative.get("current_gap_or_blocker"))
            or event.event_name
        )
        return HostRecoveryAction(
            event_id=event.event_id,
            event_name=event.event_name,
            session_mount_id=target_session_mount_id,
            environment_id=_string(payload.get("environment_id")) or session.environment_id,
            decision=decision,
            reason=reason,
            resume_kind=(
                _string(payload.get("resume_kind"))
                or _string(host_contract.get("resume_kind"))
                or "resume-environment"
            ),
            verification_channel=(
                _string(payload.get("verification_channel"))
                or _string(host_contract.get("verification_channel"))
            ),
            checkpoint_ref=_string(payload.get("checkpoint_ref")),
            return_condition=_string(payload.get("return_condition")),
            handoff_owner_ref=(
                _string(payload.get("handoff_owner_ref"))
                or _string(host_contract.get("handoff_owner_ref"))
            ),
            event_family=_event_family(event),
        )

    def _resolve_decision(
        self,
        *,
        event: RuntimeEvent,
        session,
        host_contract: dict[str, Any],
        cooperative: dict[str, Any],
    ) -> str | None:
        action = event.action.strip().lower()
        if action == "download-completed":
            return "reobserve"
        if action in {"uac-prompt", "human-takeover"}:
            return "handoff"
        if action == "human-return-ready":
            return "recover"
        if action in {"desktop-unlocked", "lock-unlock", "process-exit-restart"}:
            return "resume" if self._session_has_live_handle(session) else "recover"
        current_gap = _string(host_contract.get("current_gap_or_blocker")) or _string(
            cooperative.get("current_gap_or_blocker"),
        )
        verification_channel = _string(host_contract.get("verification_channel"))
        if current_gap is not None and verification_channel is not None:
            return "reobserve"
        return None

    def _session_has_live_handle(self, session) -> bool:
        if _string(getattr(session, "live_handle_ref", None)) is None:
            return False
        registry = getattr(self._environment_service, "_registry", None)
        has_live_handle = getattr(registry, "has_live_handle", None)
        if not callable(has_live_handle):
            return True
        try:
            return bool(
                has_live_handle(
                    session.environment_id,
                    lease_token=getattr(session, "lease_token", None),
                ),
            )
        except TypeError:
            return bool(has_live_handle(session.environment_id))

    def _session_recovery_allowed(
        self,
        session,
        *,
        allow_cross_process_recovery: bool,
    ) -> bool:
        lease_service = getattr(self._environment_service, "_lease_service", None)
        checker = getattr(lease_service, "session_should_be_recovered_locally", None)
        if not callable(checker):
            return True
        return bool(
            checker(
                session,
                allow_cross_process_recovery=allow_cross_process_recovery,
            ),
        )

    def _execute_action(self, action: HostRecoveryAction) -> dict[str, Any]:
        session = self._get_session_record(action.session_mount_id)
        if session is None:
            return {
                "action_id": action.action_id,
                "event_id": action.event_id,
                "decision": action.decision,
                "executed": False,
                "skipped": True,
                "reason": "missing-session",
            }
        if action.decision == "recover":
            return self._execute_recover(action, session)
        if action.decision == "handoff":
            updated = self._touch_recovery_state(
                session,
                metadata_patch={
                    "handoff_state": "active" if action.handoff_owner_ref else "handoff-required",
                    "handoff_reason": action.reason,
                    "handoff_owner_ref": action.handoff_owner_ref,
                    "resume_kind": action.resume_kind,
                    "verification_channel": action.verification_channel,
                },
                action=action,
            )
            self._publish_runtime_recovery_event("handoff", action, updated)
            return self._result_payload(action=action, executed=True)
        if action.decision == "resume":
            updated = self._touch_recovery_state(
                session,
                metadata_patch={
                    "handoff_state": "agent-attached",
                    "handoff_reason": None,
                    "handoff_owner_ref": None,
                    "resume_kind": action.resume_kind,
                    "verification_channel": action.verification_channel,
                    "pending_handoff_summary": None,
                },
                action=action,
            )
            self._publish_runtime_recovery_event("resumed", action, updated)
            return self._result_payload(action=action, executed=True)
        if action.decision == "reobserve":
            updated = self._touch_recovery_state(
                session,
                metadata_patch={
                    "resume_kind": action.resume_kind,
                    "verification_channel": action.verification_channel,
                },
                action=action,
            )
            self._publish_runtime_recovery_event("reobserved", action, updated)
            return self._result_payload(action=action, executed=True)
        return self._result_payload(action=action, executed=False, skipped=True, reason="unknown-decision")

    def _execute_recover(self, action: HostRecoveryAction, session) -> dict[str, Any]:
        lease_service = getattr(self._environment_service, "_lease_service", None)
        restore = getattr(lease_service, "_try_restore_session_live_handle", None)
        if not callable(restore):
            return self._result_payload(
                action=action,
                executed=False,
                skipped=True,
                reason="restore-unavailable",
            )
        restored = restore(session, now=_utc_now())
        if restored is None:
            return self._result_payload(
                action=action,
                executed=False,
                skipped=True,
                reason="restore-unavailable",
            )
        updated = self._touch_recovery_state(
            restored,
            metadata_patch={
                "handoff_state": "agent-attached",
                "handoff_reason": None,
                "handoff_owner_ref": None,
                "resume_kind": action.resume_kind,
                "verification_channel": action.verification_channel,
                "handoff_checkpoint_ref": action.checkpoint_ref,
                "handoff_return_condition": action.return_condition,
                "pending_handoff_summary": None,
            },
            action=action,
        )
        self._publish_runtime_recovery_event("restored", action, updated)
        return self._result_payload(action=action, executed=True)

    def _touch_recovery_state(
        self,
        session,
        *,
        metadata_patch: dict[str, Any],
        action: HostRecoveryAction,
    ):
        session_repository = getattr(self._environment_service, "_session_repository", None)
        if session_repository is None:
            raise RuntimeError("EnvironmentService session repository is not available")
        now = _utc_now()
        host_recovery_state = {
            **_mapping(session.metadata.get("host_recovery_state")),
            "last_handled_event_id": action.event_id,
            "last_handled_event_name": action.event_name,
            "last_handled_decision": action.decision,
            "last_action_id": action.action_id,
            "last_handled_at": now.isoformat(),
        }
        patch = {
            **metadata_patch,
            "host_recovery_state": host_recovery_state,
        }
        updated = session_repository.touch_session(
            session_mount_id=session.id,
            environment_id=session.environment_id,
            channel=session.channel,
            session_id=session.session_id,
            user_id=session.user_id,
            status=session.status,
            metadata=patch,
            last_active_at=now,
        )
        self._touch_environment_metadata(updated, patch=patch, now=now)
        return updated

    def _touch_environment_metadata(self, session, *, patch: dict[str, Any], now: datetime) -> None:
        registry = getattr(self._environment_service, "_registry", None)
        repository = getattr(registry, "_repository", None)
        if repository is None:
            return
        environment = repository.get_environment(session.environment_id)
        if environment is None:
            return
        repository.touch_environment(
            env_id=environment.id,
            kind=environment.kind,
            display_name=environment.display_name,
            ref=environment.ref,
            status=environment.status,
            metadata=patch,
            last_active_at=now,
            evidence_delta=0,
        )

    def _publish_runtime_recovery_event(self, action_name: str, action: HostRecoveryAction, session) -> None:
        if self._runtime_event_bus is None:
            return
        self._runtime_event_bus.publish(
            topic="runtime",
            action=f"recovery-{action_name}",
            payload={
                "session_mount_id": action.session_mount_id,
                "environment_id": action.environment_id,
                "source_event_id": action.event_id,
                "source_event_name": action.event_name,
                "decision": action.decision,
                "resume_kind": action.resume_kind,
                "verification_channel": action.verification_channel,
                "checkpoint_ref": action.checkpoint_ref,
                "return_condition": action.return_condition,
                "live_handle_ref": getattr(session, "live_handle_ref", None),
            },
        )

    def _result_payload(
        self,
        *,
        action: HostRecoveryAction,
        executed: bool,
        skipped: bool = False,
        reason: str | None = None,
    ) -> dict[str, Any]:
        return {
            "action_id": action.action_id,
            "event_id": action.event_id,
            "event_name": action.event_name,
            "decision": action.decision,
            "executed": executed,
            "skipped": skipped,
            "reason": reason,
        }

    def _serialize_action(self, action: HostRecoveryAction) -> dict[str, Any]:
        payload = asdict(action)
        payload["action_id"] = action.action_id
        return payload

    def _get_session_record(self, session_mount_id: str):
        session_repository = getattr(self._environment_service, "_session_repository", None)
        if session_repository is None:
            return None
        return session_repository.get_session(session_mount_id)

    def _build_host_contract(self, session) -> dict[str, Any]:
        metadata = _mapping(getattr(session, "metadata", None))
        embedded = _mapping(metadata.get("host_contract"))
        if embedded:
            return embedded
        return {
            key: metadata.get(key)
            for key in (
                "handoff_state",
                "handoff_reason",
                "handoff_owner_ref",
                "resume_kind",
                "verification_channel",
                "current_gap_or_blocker",
            )
            if metadata.get(key) is not None
        }

    def _build_cooperative_detail(self, session) -> dict[str, Any]:
        metadata = _mapping(getattr(session, "metadata", None))
        embedded = _mapping(metadata.get("cooperative_adapter_availability"))
        if embedded:
            return embedded
        return {
            key: metadata.get(key)
            for key in (
                "current_gap_or_blocker",
                "verification_channel",
            )
            if metadata.get(key) is not None
        }


def _event_family(event: RuntimeEvent) -> str:
    event_name = event.event_name
    action = event.action.strip().lower()
    if event_name == "download.download-completed":
        return "download-completed"
    if action in {"uac-prompt"}:
        return "modal-uac-login"
    if action in {"desktop-unlocked", "lock-unlock"}:
        return "lock-unlock"
    if action in {"process-exit-restart"}:
        return "process-exit-restart"
    if action in {"human-return-ready", "human-takeover"}:
        return "human-handoff-return"
    return "runtime-generic"


__all__ = ["HostEventRecoveryService", "HostRecoveryAction"]
