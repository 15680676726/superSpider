# -*- coding: utf-8 -*-
"""State-backed browser runtime profiles and product operations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..agents.tools.browser_control import (
    attach_browser_session,
    browser_use,
    get_browser_runtime_snapshot,
)
from ..constant import WORKING_DIR
from ..environments.cooperative.browser_attach_runtime import BrowserAttachRuntime
from ..environments.cooperative.browser_companion import BrowserCompanionRuntime
from ..state.store import SQLiteStateStore


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _bool_to_int(value: bool) -> int:
    return 1 if value else 0


def _positive_timeout(value: object) -> float | None:
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        return None
    return timeout if timeout > 0 else None


def _profile_storage_state_path(profile_id: str) -> str:
    safe_profile_id = "".join(
        character if character.isalnum() or character in {"-", "_"} else "-"
        for character in (profile_id or "").strip()
    ).strip("-") or "default"
    directory = WORKING_DIR / "state" / "browser_profiles"
    directory.mkdir(parents=True, exist_ok=True)
    return str((directory / f"{safe_profile_id}.json").resolve())


def _runtime_session_snapshot(
    runtime: dict[str, Any],
    session_id: str,
) -> dict[str, Any] | None:
    sessions = runtime.get("sessions") or []
    if not isinstance(sessions, list):
        return None
    for item in sessions:
        if not isinstance(item, dict):
            continue
        if str(item.get("session_id") or "").strip() == session_id:
            return item
    return None


def _browser_continuity_contract(
    *,
    session_id: str,
    runtime: dict[str, Any],
    profile: BrowserProfileRecord | None,
    persist_login_state: bool,
    attached: bool,
) -> dict[str, Any]:
    runtime_session = _runtime_session_snapshot(runtime, session_id) or {}
    configured_storage_state_path = (
        _profile_storage_state_path(profile.profile_id)
        if profile is not None and persist_login_state
        else ""
    )
    runtime_storage_state_path = str(runtime_session.get("storage_state_path") or "").strip()
    storage_state_path = str(
        runtime_storage_state_path
        or configured_storage_state_path
        or ""
    ).strip()
    storage_state_available = bool(
        runtime_session.get("storage_state_available")
    ) or bool(storage_state_path and Path(storage_state_path).exists())
    effective_persist_login_state = bool(
        runtime_session.get("persist_login_state")
    ) or persist_login_state
    page_count = int(runtime_session.get("page_count") or 0)
    downloads = runtime_session.get("downloads") or []
    if not isinstance(downloads, list):
        downloads = []
    download_verification = bool(runtime_session.get("download_verification")) or bool(
        runtime_session
    )
    save_reopen_verification = bool(
        runtime_session.get("save_reopen_verification")
    ) or bool(
        effective_persist_login_state
        and (
            storage_state_available
            or (attached and runtime_storage_state_path)
        )
    )
    authenticated_continuation = bool(
        runtime_session.get("authenticated_continuation")
    ) or bool(
        attached or save_reopen_verification or (effective_persist_login_state and runtime_session)
    )
    browser_mode = str(runtime_session.get("browser_mode") or "managed-isolated").strip() or "managed-isolated"
    navigation_guard = runtime_session.get("navigation_guard")
    if not isinstance(navigation_guard, dict):
        navigation_guard = {}
    action_timeout_seconds = _positive_timeout(
        runtime_session.get("action_timeout_seconds"),
    )
    return {
        "browser_mode": browser_mode,
        "host_mode": "managed-isolated",
        "resume_kind": (
            "attach-running-session"
            if attached
            else "reopen-from-storage-state"
            if storage_state_available
            else "fresh-session"
        ),
        "persist_login_state": effective_persist_login_state,
        "storage_state_path": storage_state_path or None,
        "storage_state_available": storage_state_available,
        "authenticated_continuation": authenticated_continuation,
        "cross_tab_continuation": bool(page_count > 1 or runtime_session),
        "file_upload": True,
        "download_verification": download_verification,
        "save_reopen_verification": save_reopen_verification,
        "navigation_guard": dict(navigation_guard),
        "action_timeout_seconds": action_timeout_seconds,
        "page_count": page_count,
        "page_ids": list(runtime_session.get("page_ids") or []),
        "verification": {
            "authenticated_continuation": {
                "verified": authenticated_continuation,
                "channel": (
                    "attach-running-session"
                    if attached
                    else "storage-state"
                    if storage_state_available
                    else "live-session"
                    if effective_persist_login_state and runtime_session
                    else "unverified"
                ),
            },
            "download": {
                "verified": download_verification,
                "channel": "playwright-download+filesystem" if download_verification else "unverified",
                "download_count": int(runtime_session.get("download_count") or len(downloads)),
                "completed_download_count": int(
                    runtime_session.get("completed_download_count") or len(downloads)
                ),
                "latest_download": downloads[-1] if downloads else None,
            },
            "save_reopen": {
                "verified": save_reopen_verification,
                "channel": (
                    "storage-state"
                    if storage_state_available
                    else "live-session-storage-config"
                    if attached and runtime_storage_state_path
                    else "unverified"
                ),
                "storage_state_path": storage_state_path or None,
                "storage_state_available": storage_state_available,
            },
        },
    }


class BrowserProfileRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    profile_id: str
    label: str
    headed: bool = True
    reuse_running_session: bool = True
    persist_login_state: bool = True
    entry_url: str = ""
    is_default: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


class BrowserSessionStartOptions(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    session_id: str = "default"
    profile_id: str | None = None
    headed: bool | None = None
    entry_url: str | None = None
    reuse_running_session: bool | None = None
    persist_login_state: bool | None = None
    navigation_guard: dict[str, Any] | None = None
    action_timeout_seconds: float | None = None


class BrowserRuntimeService:
    """Product-facing browser runtime service backed by the unified state DB."""

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS browser_runtime_profiles (
        profile_id TEXT PRIMARY KEY,
        label TEXT NOT NULL,
        headed INTEGER NOT NULL DEFAULT 0,
        reuse_running_session INTEGER NOT NULL DEFAULT 1,
        persist_login_state INTEGER NOT NULL DEFAULT 1,
        entry_url TEXT NOT NULL DEFAULT '',
        is_default INTEGER NOT NULL DEFAULT 0,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_browser_runtime_profiles_default
        ON browser_runtime_profiles(is_default DESC, updated_at DESC);
    """

    def __init__(
        self,
        state_store: SQLiteStateStore,
        browser_companion_runtime: BrowserCompanionRuntime | None = None,
        browser_attach_runtime: BrowserAttachRuntime | None = None,
    ) -> None:
        self._store = state_store
        self._browser_companion_runtime = browser_companion_runtime
        self._browser_attach_runtime = browser_attach_runtime
        self._store.initialize()
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        with self._store.connection() as conn:
            conn.executescript(self._SCHEMA)

    def list_profiles(self) -> list[BrowserProfileRecord]:
        with self._store.connection() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM browser_runtime_profiles
                ORDER BY is_default DESC, updated_at DESC, profile_id ASC
                """
            ).fetchall()
        return [self._profile_from_row(row) for row in rows]

    def get_profile(self, profile_id: str | None) -> BrowserProfileRecord | None:
        normalized = str(profile_id or "").strip()
        if not normalized:
            return None
        with self._store.connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM browser_runtime_profiles
                WHERE profile_id = ?
                """,
                (normalized,),
            ).fetchone()
        return self._profile_from_row(row)

    def get_default_profile(self) -> BrowserProfileRecord | None:
        with self._store.connection() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM browser_runtime_profiles
                WHERE is_default = 1
                ORDER BY updated_at DESC
                LIMIT 1
                """
            ).fetchone()
        return self._profile_from_row(row)

    def upsert_profile(self, record: BrowserProfileRecord) -> BrowserProfileRecord:
        if record.is_default:
            with self._store.connection() as conn:
                conn.execute(
                    "UPDATE browser_runtime_profiles SET is_default = 0 WHERE profile_id != ?",
                    (record.profile_id,),
                )
        payload = record.model_dump(mode="json")
        payload["headed"] = _bool_to_int(record.headed)
        payload["reuse_running_session"] = _bool_to_int(record.reuse_running_session)
        payload["persist_login_state"] = _bool_to_int(record.persist_login_state)
        payload["is_default"] = _bool_to_int(record.is_default)
        payload["metadata_json"] = json.dumps(record.metadata or {}, ensure_ascii=False)
        payload["created_at"] = record.created_at.isoformat()
        payload["updated_at"] = record.updated_at.isoformat()
        with self._store.connection() as conn:
            conn.execute(
                """
                INSERT INTO browser_runtime_profiles (
                    profile_id,
                    label,
                    headed,
                    reuse_running_session,
                    persist_login_state,
                    entry_url,
                    is_default,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :profile_id,
                    :label,
                    :headed,
                    :reuse_running_session,
                    :persist_login_state,
                    :entry_url,
                    :is_default,
                    :metadata_json,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(profile_id) DO UPDATE SET
                    label = excluded.label,
                    headed = excluded.headed,
                    reuse_running_session = excluded.reuse_running_session,
                    persist_login_state = excluded.persist_login_state,
                    entry_url = excluded.entry_url,
                    is_default = excluded.is_default,
                    metadata_json = excluded.metadata_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                payload,
            )
        return record

    def delete_profile(self, profile_id: str) -> bool:
        with self._store.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM browser_runtime_profiles WHERE profile_id = ?",
                (profile_id,),
            )
        storage_state_path = Path(_profile_storage_state_path(profile_id))
        if storage_state_path.exists():
            try:
                storage_state_path.unlink()
            except OSError:
                pass
        return cursor.rowcount > 0

    def ensure_default_profile(
        self,
        *,
        profile_id: str = "browser-local-default",
        label: str = "Default browser runtime",
        headed: bool = True,
        reuse_running_session: bool = True,
        persist_login_state: bool = True,
        entry_url: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> BrowserProfileRecord:
        existing = self.get_profile(profile_id)
        created_at = existing.created_at if existing is not None else _utc_now()
        record = BrowserProfileRecord(
            profile_id=profile_id,
            label=label,
            headed=headed,
            reuse_running_session=reuse_running_session,
            persist_login_state=persist_login_state,
            entry_url=entry_url,
            is_default=True,
            metadata=dict(metadata or {}),
            created_at=created_at,
            updated_at=_utc_now(),
        )
        return self.upsert_profile(record)

    def runtime_snapshot(
        self,
        *,
        environment_id: str | None = None,
        session_mount_id: str | None = None,
    ) -> dict[str, Any]:
        snapshot = {
            **get_browser_runtime_snapshot(),
            "profiles": [profile.model_dump(mode="json") for profile in self.list_profiles()],
        }
        if (
            self._browser_companion_runtime is not None
            and (environment_id is not None or session_mount_id is not None)
        ):
            snapshot["browser_companion"] = self.companion_snapshot(
                environment_id=environment_id,
                session_mount_id=session_mount_id,
            )
        if (
            self._browser_attach_runtime is not None
            and (environment_id is not None or session_mount_id is not None)
        ):
            snapshot["browser_attach"] = self.attach_snapshot(
                environment_id=environment_id,
                session_mount_id=session_mount_id,
            )
        return snapshot

    def register_companion(
        self,
        *,
        environment_id: str | None = None,
        session_mount_id: str | None = None,
        transport_ref: str | None = None,
        status: str | None = None,
        available: bool | None = None,
        preferred_execution_path: str | None = None,
        ui_fallback_mode: str | None = None,
        adapter_gap_or_blocker: str | None = None,
        provider_session_ref: str | None = None,
        execution_guardrails: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        if self._browser_companion_runtime is None:
            raise RuntimeError("Browser companion runtime is not configured.")
        return self._browser_companion_runtime.register_companion(
            environment_id=environment_id,
            session_mount_id=session_mount_id,
            transport_ref=transport_ref,
            status=status,
            available=available,
            preferred_execution_path=preferred_execution_path,
            ui_fallback_mode=ui_fallback_mode,
            adapter_gap_or_blocker=adapter_gap_or_blocker,
            provider_session_ref=provider_session_ref,
            execution_guardrails=execution_guardrails,
        )

    def companion_snapshot(
        self,
        *,
        environment_id: str | None = None,
        session_mount_id: str | None = None,
    ) -> dict[str, Any]:
        if self._browser_companion_runtime is None:
            return {
                "available": None,
                "status": None,
                "transport_ref": None,
                "provider_session_ref": None,
            }
        snapshot = self._browser_companion_runtime.snapshot(
            environment_id=environment_id,
            session_mount_id=session_mount_id,
        )
        browser_companion = snapshot.get("browser_companion")
        if not isinstance(browser_companion, dict):
            return {
                "available": None,
                "status": None,
                "transport_ref": None,
                "provider_session_ref": None,
                "environment_id": None,
                "session_mount_id": None,
                "work_context_id": None,
            }
        return {
            **dict(browser_companion),
            "environment_id": snapshot.get("environment_id"),
            "session_mount_id": snapshot.get("session_mount_id"),
            "work_context_id": snapshot.get("work_context_id"),
        }

    def register_attach_transport(
        self,
        *,
        session_mount_id: str,
        transport_ref: str | None = None,
        status: str | None = None,
        browser_session_ref: str | None = None,
        browser_scope_ref: str | None = None,
        reconnect_token: str | None = None,
        preferred_execution_path: str | None = None,
        ui_fallback_mode: str | None = None,
        adapter_gap_or_blocker: str | None = None,
    ) -> dict[str, Any]:
        if self._browser_attach_runtime is None:
            raise RuntimeError("Browser attach runtime is not configured.")
        self._browser_attach_runtime.register_transport(
            session_mount_id=session_mount_id,
            transport_ref=transport_ref or "",
            status=status,
            browser_session_ref=browser_session_ref,
            browser_scope_ref=browser_scope_ref,
            reconnect_token=reconnect_token,
            preferred_execution_path=preferred_execution_path,
            ui_fallback_mode=ui_fallback_mode,
            adapter_gap_or_blocker=adapter_gap_or_blocker,
        )
        return self._browser_attach_runtime.snapshot(
            session_mount_id=session_mount_id,
        )

    def clear_attach_transport(
        self,
        *,
        session_mount_id: str,
        preferred_execution_path: str | None = None,
        ui_fallback_mode: str | None = None,
        adapter_gap_or_blocker: str | None = None,
    ) -> dict[str, Any]:
        if self._browser_attach_runtime is None:
            raise RuntimeError("Browser attach runtime is not configured.")
        self._browser_attach_runtime.clear_transport(
            session_mount_id=session_mount_id,
            preferred_execution_path=preferred_execution_path,
            ui_fallback_mode=ui_fallback_mode,
            adapter_gap_or_blocker=adapter_gap_or_blocker,
        )
        return self._browser_attach_runtime.snapshot(
            session_mount_id=session_mount_id,
        )

    def attach_snapshot(
        self,
        *,
        environment_id: str | None = None,
        session_mount_id: str | None = None,
    ) -> dict[str, Any]:
        if self._browser_attach_runtime is None:
            return {
                "transport_ref": None,
                "status": None,
                "session_ref": None,
                "scope_ref": None,
                "reconnect_token": None,
                "environment_id": None,
                "session_mount_id": None,
            }
        snapshot = self._browser_attach_runtime.snapshot(
            environment_id=environment_id,
            session_mount_id=session_mount_id,
        )
        browser_attach = snapshot.get("browser_attach")
        if not isinstance(browser_attach, dict):
            return {
                "transport_ref": None,
                "status": None,
                "session_ref": None,
                "scope_ref": None,
                "reconnect_token": None,
                "environment_id": None,
                "session_mount_id": None,
            }
        return {
            **dict(browser_attach),
            "environment_id": snapshot.get("environment_id"),
            "session_mount_id": snapshot.get("session_mount_id"),
        }

    async def start_session(
        self,
        options: BrowserSessionStartOptions,
    ) -> dict[str, Any]:
        profile = (
            self.get_profile(options.profile_id)
            if options.profile_id
            else self.get_default_profile()
        )
        headed = (
            bool(options.headed)
            if options.headed is not None
            else bool(profile.headed)
            if profile is not None
            else True
        )
        reuse_running_session = (
            bool(options.reuse_running_session)
            if options.reuse_running_session is not None
            else bool(profile.reuse_running_session)
            if profile is not None
            else True
        )
        persist_login_state = (
            bool(options.persist_login_state)
            if options.persist_login_state is not None
            else bool(profile.persist_login_state)
            if profile is not None
            else True
        )
        entry_url = (
            str(options.entry_url or "").strip()
            or (str(profile.entry_url or "").strip() if profile is not None else "")
        )
        navigation_guard = (
            dict(options.navigation_guard)
            if isinstance(options.navigation_guard, dict)
            else dict(profile.metadata.get("navigation_guard") or {})
            if profile is not None and isinstance(profile.metadata, dict)
            else {}
        )
        action_timeout_seconds = (
            _positive_timeout(options.action_timeout_seconds)
            or (
                _positive_timeout(profile.metadata.get("action_timeout_seconds"))
                if profile is not None and isinstance(profile.metadata, dict)
                else None
            )
        )
        session_id = str(options.session_id or "default").strip() or "default"
        runtime_before = get_browser_runtime_snapshot()
        active_session_ids = {
            str(item.get("session_id") or "")
            for item in list(runtime_before.get("sessions") or [])
            if str(item.get("session_id") or "").strip()
        }
        if reuse_running_session and session_id in active_session_ids:
            attach_payload = attach_browser_session(session_id)
            runtime_after_attach = get_browser_runtime_snapshot()
            return {
                "status": "attached",
                "session_id": session_id,
                "profile_id": profile.profile_id if profile is not None else None,
                "runtime": runtime_after_attach,
                "result": attach_payload,
                "continuity": _browser_continuity_contract(
                    session_id=session_id,
                    runtime=runtime_after_attach,
                    profile=profile,
                    persist_login_state=persist_login_state,
                    attached=True,
                ),
            }
        response = await browser_use(
            action="start",
            session_id=session_id,
            headed=headed,
            profile_id=profile.profile_id if profile is not None else "",
            entry_url=entry_url,
            persist_login_state=persist_login_state,
            storage_state_path=(
                _profile_storage_state_path(profile.profile_id)
                if profile is not None and persist_login_state
                else ""
            ),
            navigation_guard_json=(
                json.dumps(navigation_guard, ensure_ascii=False)
                if navigation_guard
                else ""
            ),
            action_timeout_seconds=action_timeout_seconds or 0,
        )
        text = self._tool_response_text(response)
        runtime_after_start = get_browser_runtime_snapshot()
        return {
            "status": "started",
            "session_id": session_id,
            "profile_id": profile.profile_id if profile is not None else None,
            "runtime": runtime_after_start,
            "result": self._tool_response_json(text),
            "continuity": _browser_continuity_contract(
                session_id=session_id,
                runtime=runtime_after_start,
                profile=profile,
                persist_login_state=persist_login_state,
                attached=False,
            ),
        }

    async def stop_session(self, session_id: str) -> dict[str, Any]:
        normalized = str(session_id or "").strip()
        response = await browser_use(
            action="stop",
            session_id=normalized,
        )
        text = self._tool_response_text(response)
        return {
            "session_id": normalized,
            "runtime": get_browser_runtime_snapshot(),
            "result": self._tool_response_json(text),
        }

    def attach_session(self, session_id: str) -> dict[str, Any]:
        normalized = str(session_id or "").strip()
        attach_result = attach_browser_session(normalized)
        runtime = get_browser_runtime_snapshot()
        return {
            "session_id": normalized,
            "runtime": runtime,
            "result": attach_result,
            "continuity": _browser_continuity_contract(
                session_id=normalized,
                runtime=runtime,
                profile=None,
                persist_login_state=bool(
                    (_runtime_session_snapshot(runtime, normalized) or {}).get(
                        "persist_login_state"
                    )
                ),
                attached=bool(attach_result.get("ok")),
            ),
        }

    def _profile_from_row(self, row: Any) -> BrowserProfileRecord | None:
        if row is None:
            return None
        return BrowserProfileRecord(
            profile_id=str(row["profile_id"]),
            label=str(row["label"]),
            headed=bool(row["headed"]),
            reuse_running_session=bool(row["reuse_running_session"]),
            persist_login_state=bool(row["persist_login_state"]),
            entry_url=str(row["entry_url"] or ""),
            is_default=bool(row["is_default"]),
            metadata=self._json_payload(row["metadata_json"]),
            created_at=self._parse_datetime(row["created_at"]),
            updated_at=self._parse_datetime(row["updated_at"]),
        )

    def _json_payload(self, raw: Any) -> dict[str, Any]:
        try:
            payload = json.loads(str(raw or "{}"))
        except json.JSONDecodeError:
            payload = {}
        return payload if isinstance(payload, dict) else {}

    def _parse_datetime(self, raw: Any) -> datetime:
        text = str(raw or "").strip()
        if not text:
            return _utc_now()
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return _utc_now()

    def _tool_response_text(self, response: object) -> str:
        content = getattr(response, "content", None)
        if not isinstance(content, list) or not content:
            return ""
        block = content[0]
        if isinstance(block, dict):
            return str(block.get("text") or "")
        return str(getattr(block, "text", "") or "")

    def _tool_response_json(self, text: str) -> dict[str, Any]:
        if not text:
            return {}
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return {"ok": False, "raw_text": text}
        return payload if isinstance(payload, dict) else {"ok": False, "raw_text": text}
