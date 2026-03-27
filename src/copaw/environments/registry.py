# -*- coding: utf-8 -*-
"""Environment registry for mounted execution contexts."""
from __future__ import annotations

import os
import re
import socket
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ..evidence import EvidenceLedger

from .models import EnvironmentKind, EnvironmentMount
from .repository import EnvironmentRepository, SessionMountRepository


class EnvironmentRegistry:
    """Registry that stores mounted environments and can seed from evidence."""

    def __init__(
        self,
        *,
        ledger: EvidenceLedger | None = None,
        repository: EnvironmentRepository | None = None,
        session_repository: SessionMountRepository | None = None,
        host_id: str | None = None,
        process_id: int | None = None,
    ) -> None:
        self._ledger = ledger
        self._repository = repository
        self._session_repository = session_repository
        self._live_handles: dict[str, _LiveHandle] = {}
        self._host_id = host_id or _default_host_id()
        self._process_id = int(process_id or os.getpid())

    @property
    def host_id(self) -> str:
        return self._host_id

    @property
    def process_id(self) -> int:
        return self._process_id

    def collect(self) -> list[EnvironmentMount]:
        """Return mounted environments, seeding from evidence if needed."""
        if self._repository is not None:
            mounts = self._repository.list_environments()
            if mounts:
                return mounts
            if self._ledger is None:
                return mounts
            seeded = self._collect_from_evidence()
            for mount in seeded:
                self._repository.upsert_environment(mount)
            return seeded

        if self._ledger is None:
            return []
        return self._collect_from_evidence()

    def get(self, env_id: str) -> EnvironmentMount | None:
        if self._repository is not None:
            return self._repository.get_environment(env_id)
        for mount in self.collect():
            if mount.id == env_id:
                return mount
        return None

    def upsert(self, mount: EnvironmentMount) -> EnvironmentMount | None:
        if self._repository is None:
            return None
        return self._repository.upsert_environment(mount)

    def register(
        self,
        *,
        ref: str | None,
        kind: EnvironmentKind | None = None,
        status: str | None = None,
        metadata: dict[str, Any] | None = None,
        last_active_at: datetime | None = None,
        evidence_delta: int = 0,
    ) -> EnvironmentMount | None:
        """Create or update a mount entry in the registry."""
        if not ref or self._repository is None:
            return None
        resolved_kind = kind or self._classify(ref)
        env_id = self._ref_to_id(ref)
        display_name = self._display_name(ref, resolved_kind)
        mount = self._repository.touch_environment(
            env_id=env_id,
            kind=resolved_kind,
            display_name=display_name,
            ref=ref,
            status=status,
            metadata=metadata,
            last_active_at=last_active_at or datetime.now(timezone.utc),
            evidence_delta=evidence_delta,
        )
        self._touch_session_mount(
            ref=ref,
            env_id=env_id,
            kind=resolved_kind,
            status=status,
            metadata=metadata,
            last_active_at=last_active_at,
        )
        return mount

    def touch(
        self,
        *,
        ref: str | None,
        kind: EnvironmentKind | None = None,
        status: str | None = None,
        metadata: dict[str, Any] | None = None,
        last_active_at: datetime | None = None,
        evidence_delta: int = 1,
    ) -> EnvironmentMount | None:
        if not ref or self._repository is None:
            return None
        resolved_kind = kind or self._classify(ref)
        env_id = self._ref_to_id(ref)
        display_name = self._display_name(ref, resolved_kind)
        mount = self._repository.touch_environment(
            env_id=env_id,
            kind=resolved_kind,
            display_name=display_name,
            ref=ref,
            status=status,
            metadata=metadata,
            last_active_at=last_active_at,
            evidence_delta=evidence_delta,
        )
        self._touch_session_mount(
            ref=ref,
            env_id=env_id,
            kind=resolved_kind,
            status=status,
            metadata=metadata,
            last_active_at=last_active_at,
        )
        return mount

    def close(self, env_id: str, *, status: str = "closed") -> EnvironmentMount | None:
        if self._repository is None:
            return None
        self.detach_live_handle(env_id)
        return self._repository.close_environment(env_id, status=status)

    def attach_live_handle(
        self,
        env_id: str,
        *,
        handle: object,
        owner: str | None = None,
        lease_token: str | None = None,
        handle_ref: str | None = None,
        descriptor: dict[str, Any] | None = None,
        seen_at: datetime | None = None,
    ) -> str:
        timestamp = seen_at or datetime.now(timezone.utc)
        existing = self._live_handles.get(env_id)
        live_handle_ref = handle_ref or f"live:{env_id}:{uuid4().hex[:8]}"
        self._live_handles[env_id] = _LiveHandle(
            ref=live_handle_ref,
            handle=handle,
            owner=owner,
            lease_token=lease_token,
            host_id=self._host_id,
            process_id=self._process_id,
            descriptor=dict(descriptor or {}),
            attached_at=(
                existing.attached_at
                if existing is not None and existing.ref == live_handle_ref
                else timestamp
            ),
            last_seen_at=timestamp,
        )
        return live_handle_ref

    def detach_live_handle(self, env_id: str) -> None:
        self._live_handles.pop(env_id, None)

    def get_live_handle(self, env_id: str) -> object | None:
        live = self._live_handles.get(env_id)
        return None if live is None else live.handle

    def get_live_handle_ref(self, env_id: str) -> str | None:
        live = self._live_handles.get(env_id)
        return None if live is None else live.ref

    def get_live_handle_info(self, env_id: str) -> dict[str, Any] | None:
        live = self._live_handles.get(env_id)
        return None if live is None else live.to_dict()

    def touch_live_handle(
        self,
        env_id: str,
        *,
        lease_token: str | None = None,
        seen_at: datetime | None = None,
        descriptor: dict[str, Any] | None = None,
        handle: object | None = None,
    ) -> bool:
        live = self._live_handles.get(env_id)
        if live is None:
            return False
        if lease_token is not None and live.lease_token and live.lease_token != lease_token:
            return False
        if handle is not None:
            live.handle = handle
        if descriptor:
            live.descriptor.update(dict(descriptor))
        live.last_seen_at = seen_at or datetime.now(timezone.utc)
        return True

    def has_live_handle(
        self,
        env_id: str,
        *,
        lease_token: str | None = None,
    ) -> bool:
        live = self._live_handles.get(env_id)
        if live is None:
            return False
        if lease_token is not None and live.lease_token and live.lease_token != lease_token:
            return False
        return True

    def _collect_from_evidence(self) -> list[EnvironmentMount]:
        if self._ledger is None:
            return []
        records = self._ledger.list_recent(limit=500)
        env_map: dict[str, _EnvAccum] = {}

        for record in records:
            ref = record.environment_ref
            if not ref:
                continue

            env_id = self._ref_to_id(ref)
            if env_id in env_map:
                acc = env_map[env_id]
                acc.count += 1
                if record.created_at and (
                    acc.last_active is None or record.created_at > acc.last_active
                ):
                    acc.last_active = record.created_at
            else:
                env_map[env_id] = _EnvAccum(
                    ref=ref,
                    kind=self._classify(ref),
                    count=1,
                    last_active=record.created_at,
                )

        mounts: list[EnvironmentMount] = []
        for env_id, acc in env_map.items():
            mounts.append(
                EnvironmentMount(
                    id=env_id,
                    kind=acc.kind,
                    display_name=self._display_name(acc.ref, acc.kind),
                    ref=acc.ref,
                    status="active",
                    last_active_at=acc.last_active,
                    evidence_count=acc.count,
                ),
            )

        min_dt = datetime.min.replace(tzinfo=timezone.utc)
        mounts.sort(
            key=lambda m: m.last_active_at or min_dt,
            reverse=True,
        )
        return mounts

    # ── Classification helpers ──────────────────────────────────────

    @staticmethod
    def _classify(ref: str) -> EnvironmentKind:
        """Classify an environment_ref string into a kind."""
        lower = ref.lower()
        if lower.startswith("session:"):
            return "session"
        if lower.startswith("terminal:"):
            return "terminal"
        # Browser-like refs
        if lower.startswith(("http://", "https://", "chrome://", "about:")):
            return "browser"
        # Session refs (channel:session_id pattern)
        if ":" in ref and not ref.startswith("/") and not ref.startswith("\\"):
            # Heuristic: if it looks like channel:session_id
            parts = ref.split(":", 1)
            if len(parts) == 2 and not parts[1].startswith(("/", "\\")):
                # Could be session or terminal
                if parts[0] in ("legacy", "api", "feishu", "wechat", "cli", "session"):
                    return "session"
        # File paths
        if ref.startswith(("/", "\\")) or (len(ref) > 2 and ref[1] == ":"):
            return "workspace"
        # Default
        return "workspace"

    @staticmethod
    def _ref_to_id(ref: str) -> str:
        """Convert raw environment_ref to a stable ID."""
        lower = ref.lower()
        if lower.startswith(("http://", "https://")):
            return f"env:browser:{ref}"
        if lower.startswith("terminal:"):
            return f"env:terminal:{ref}"
        if lower.startswith("session:"):
            return f"env:session:{ref}"
        if ":" in ref and not ref.startswith(("/", "\\")) and not (len(ref) > 2 and ref[1] == ":"):
            return f"env:session:{ref}"
        return f"env:workspace:{ref}"

    @staticmethod
    def _display_name(ref: str, kind: EnvironmentKind) -> str:
        """Generate a human readable name from ref."""
        if kind == "browser":
            # Show domain + path
            match = re.match(r"https?://([^/]+)(.*)", ref)
            if match:
                domain = match.group(1)
                path = match.group(2)[:30] if match.group(2) else ""
                return f"{domain}{path}"
            return ref[:60]
        if kind == "session":
            return ref
        if kind == "terminal":
            return ref
        # workspace: show last 2 path segments
        parts = ref.replace("\\", "/").rstrip("/").split("/")
        if len(parts) >= 2:
            return "/".join(parts[-2:])
        return ref

    def _touch_session_mount(
        self,
        *,
        ref: str,
        env_id: str,
        kind: EnvironmentKind,
        status: str | None,
        metadata: dict[str, Any] | None,
        last_active_at: datetime | None,
    ) -> None:
        if self._session_repository is None:
            return
        if kind not in {"session", "channel-session"}:
            return
        channel, session_id, user_id = self._extract_session_meta(ref, metadata)
        if not channel or not session_id:
            return
        session_mount_id = f"session:{channel}:{session_id}"
        self._session_repository.touch_session(
            session_mount_id=session_mount_id,
            environment_id=env_id,
            channel=channel,
            session_id=session_id,
            user_id=user_id,
            status=status,
            metadata=metadata,
            last_active_at=last_active_at,
        )

    @staticmethod
    def _extract_session_meta(
        ref: str,
        metadata: dict[str, Any] | None,
    ) -> tuple[str | None, str | None, str | None]:
        channel = None
        session_id = None
        user_id = None
        if metadata:
            channel = metadata.get("channel") or metadata.get("channel_id")
            session_id = metadata.get("session_id")
            user_id = metadata.get("user_id")

        normalized = ref or ""
        if normalized.startswith("session:"):
            parts = normalized.split(":", 2)
            if len(parts) == 3:
                channel = channel or parts[1]
                session_id = session_id or parts[2]
        elif ":" in normalized and not normalized.startswith(("/", "\\")) and not (
            len(normalized) > 2 and normalized[1] == ":"
        ):
            parts = normalized.split(":", 1)
            if len(parts) == 2:
                channel = channel or parts[0]
                session_id = session_id or parts[1]

        return (
            str(channel) if channel else None,
            str(session_id) if session_id else None,
            str(user_id) if user_id else None,
        )


class _EnvAccum:
    """Accumulator for building EnvironmentMount from evidence scan."""

    __slots__ = ("ref", "kind", "count", "last_active")

    def __init__(
        self,
        *,
        ref: str,
        kind: EnvironmentKind,
        count: int,
        last_active: datetime | None,
    ) -> None:
        self.ref = ref
        self.kind = kind
        self.count = count
        self.last_active = last_active


class _LiveHandle:
    __slots__ = (
        "ref",
        "handle",
        "owner",
        "lease_token",
        "host_id",
        "process_id",
        "descriptor",
        "attached_at",
        "last_seen_at",
    )

    def __init__(
        self,
        *,
        ref: str,
        handle: object,
        owner: str | None,
        lease_token: str | None,
        host_id: str,
        process_id: int,
        descriptor: dict[str, Any],
        attached_at: datetime,
        last_seen_at: datetime,
    ) -> None:
        self.ref = ref
        self.handle = handle
        self.owner = owner
        self.lease_token = lease_token
        self.host_id = host_id
        self.process_id = process_id
        self.descriptor = descriptor
        self.attached_at = attached_at
        self.last_seen_at = last_seen_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref": self.ref,
            "owner": self.owner,
            "lease_token": self.lease_token,
            "host_id": self.host_id,
            "process_id": self.process_id,
            "descriptor": dict(self.descriptor),
            "attached_at": self.attached_at.isoformat(),
            "last_seen_at": self.last_seen_at.isoformat(),
        }


def _default_host_id() -> str:
    return (
        os.getenv("COPAW_RUNTIME_HOST_ID", "").strip()
        or socket.gethostname().strip()
        or "unknown-host"
    )
