# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from ..constant import EnvVarLoader, MEMORY_DIR
from ..state import MemoryFactIndexRecord
from .derived_index_service import slugify, source_route_for_entry
from .models import (
    MemoryBackendDescriptor,
    MemoryRecallHit,
    MemoryRecallResponse,
    MemoryScopeSelector,
    utc_now,
)

_DEFAULT_QMD_EMBED_MODEL = (
    "hf:Qwen/Qwen3-Embedding-0.6B-GGUF/Qwen3-Embedding-0.6B-Q8_0.gguf"
)
_DEFAULT_QMD_QUERY_MODE = "query"
_DEFAULT_QMD_CONTEXT = (
    "CoPaw derived memory corpus rebuilt from canonical state and evidence. "
    "Use it as a disposable retrieval sidecar, not as the truth source."
)
_RUNTIME_PROBE_TTL_SECONDS = 10.0


def _isoformat(value: object) -> str | None:
    isoformat = getattr(value, "isoformat", None)
    if not callable(isoformat):
        return None
    return str(isoformat())


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_mapping_payload(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    return dict(payload)


@dataclass(slots=True)
class QmdBackendConfig:
    enabled: bool = True
    required: bool = False
    install_mode: str = "auto"
    binary_name: str = "qmd"
    npm_package: str = "@tobilu/qmd"
    index_name: str = "copaw-memory"
    collection_name: str = "copaw-memory"
    base_dir: Path = MEMORY_DIR / "qmd"
    corpus_dir: Path = MEMORY_DIR / "qmd" / "corpus"
    manifest_path: Path = MEMORY_DIR / "qmd" / "manifest.json"
    xdg_cache_home: Path = MEMORY_DIR / "qmd" / "xdg-cache"
    embed_model: str = _DEFAULT_QMD_EMBED_MODEL
    query_mode: str = _DEFAULT_QMD_QUERY_MODE
    collection_context: str = _DEFAULT_QMD_CONTEXT
    min_score: float = 0.08
    query_candidate_limit: int = 32
    online_skip_rerank: bool = True
    command_timeout_seconds: int = 120
    embed_timeout_seconds: int = 1800
    daemon_enabled: bool = False
    daemon_host: str = "127.0.0.1"
    daemon_port: int = 8765
    daemon_start_timeout_seconds: int = 30
    daemon_health_timeout_seconds: int = 2

    @classmethod
    def from_env(cls) -> "QmdBackendConfig":
        base_dir_raw = EnvVarLoader.get_str(
            "COPAW_MEMORY_QMD_BASE_DIR",
            str(MEMORY_DIR / "qmd"),
        ).strip()
        base_dir = Path(base_dir_raw).expanduser().resolve()
        install_mode = EnvVarLoader.get_str(
            "COPAW_MEMORY_QMD_INSTALL_MODE",
            "auto",
        ).strip().lower() or "auto"
        prewarm_enabled = EnvVarLoader.get_bool(
            "COPAW_MEMORY_QMD_PREWARM",
            False,
        )
        return cls(
            enabled=EnvVarLoader.get_bool("COPAW_MEMORY_QMD_ENABLED", True),
            required=EnvVarLoader.get_bool("COPAW_MEMORY_QMD_REQUIRED", False),
            install_mode=install_mode,
            binary_name=EnvVarLoader.get_str(
                "COPAW_MEMORY_QMD_BINARY",
                "qmd",
            ).strip()
            or "qmd",
            npm_package=EnvVarLoader.get_str(
                "COPAW_MEMORY_QMD_NPM_PACKAGE",
                "@tobilu/qmd",
            ).strip()
            or "@tobilu/qmd",
            index_name=EnvVarLoader.get_str(
                "COPAW_MEMORY_QMD_INDEX_NAME",
                "copaw-memory",
            ).strip()
            or "copaw-memory",
            collection_name=EnvVarLoader.get_str(
                "COPAW_MEMORY_QMD_COLLECTION_NAME",
                "copaw-memory",
            ).strip()
            or "copaw-memory",
            base_dir=base_dir,
            corpus_dir=base_dir / "corpus",
            manifest_path=base_dir / "manifest.json",
            xdg_cache_home=base_dir / "xdg-cache",
            embed_model=EnvVarLoader.get_str(
                "COPAW_MEMORY_QMD_EMBED_MODEL",
                _DEFAULT_QMD_EMBED_MODEL,
            ).strip()
            or _DEFAULT_QMD_EMBED_MODEL,
            query_mode=EnvVarLoader.get_str(
                "COPAW_MEMORY_QMD_QUERY_MODE",
                _DEFAULT_QMD_QUERY_MODE,
            ).strip().lower()
            or _DEFAULT_QMD_QUERY_MODE,
            collection_context=EnvVarLoader.get_str(
                "COPAW_MEMORY_QMD_COLLECTION_CONTEXT",
                _DEFAULT_QMD_CONTEXT,
            ).strip()
            or _DEFAULT_QMD_CONTEXT,
            min_score=EnvVarLoader.get_float(
                "COPAW_MEMORY_QMD_MIN_SCORE",
                0.08,
                min_value=0.0,
                max_value=1.0,
            ),
            query_candidate_limit=EnvVarLoader.get_int(
                "COPAW_MEMORY_QMD_QUERY_CANDIDATE_LIMIT",
                32,
                min_value=8,
                max_value=128,
            ),
            online_skip_rerank=EnvVarLoader.get_bool(
                "COPAW_MEMORY_QMD_ONLINE_SKIP_RERANK",
                True,
            ),
            command_timeout_seconds=EnvVarLoader.get_int(
                "COPAW_MEMORY_QMD_COMMAND_TIMEOUT_SECONDS",
                120,
                min_value=10,
                max_value=3600,
            ),
            embed_timeout_seconds=EnvVarLoader.get_int(
                "COPAW_MEMORY_QMD_EMBED_TIMEOUT_SECONDS",
                1800,
                min_value=30,
                max_value=7200,
            ),
            daemon_enabled=EnvVarLoader.get_bool(
                "COPAW_MEMORY_QMD_DAEMON_ENABLED",
                prewarm_enabled,
            ),
            daemon_host=EnvVarLoader.get_str(
                "COPAW_MEMORY_QMD_DAEMON_HOST",
                "127.0.0.1",
            ).strip()
            or "127.0.0.1",
            daemon_port=EnvVarLoader.get_int(
                "COPAW_MEMORY_QMD_DAEMON_PORT",
                8765,
                min_value=1024,
                max_value=65535,
            ),
            daemon_start_timeout_seconds=EnvVarLoader.get_int(
                "COPAW_MEMORY_QMD_DAEMON_START_TIMEOUT_SECONDS",
                30,
                min_value=3,
                max_value=300,
            ),
            daemon_health_timeout_seconds=EnvVarLoader.get_int(
                "COPAW_MEMORY_QMD_DAEMON_HEALTH_TIMEOUT_SECONDS",
                2,
                min_value=1,
                max_value=30,
            ),
        )


class QmdBackendError(RuntimeError):
    """Raised when the QMD sidecar cannot satisfy a request."""


@dataclass(slots=True)
class QmdRuntimeProbe:
    checked_at: str
    collection_path: Path | None = None
    index_path: str | None = None
    documents_total: int | None = None
    embedded_vectors: int | None = None
    pending_embeddings: int | None = None
    mcp_running: bool | None = None
    mcp_pid: int | None = None
    gpu_backend: str | None = None
    problem: str | None = None


@dataclass(slots=True)
class QmdDaemonState:
    state: str
    owned: bool = False
    pid: int | None = None
    last_error: str | None = None
    last_started_at: str | None = None


class QmdRecallBackend:
    """QMD-backed sidecar retrieval over exported derived memory facts."""

    backend_id = "qmd"
    label = "QMD Sidecar"

    def __init__(
        self,
        *,
        config: QmdBackendConfig | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
        which: Callable[[str], str | None] | None = None,
        popen_factory: Callable[..., Any] | None = None,
        health_checker: Callable[[str, float], bool] | None = None,
        json_requester: Callable[[str, str, dict[str, Any] | None, float], dict[str, Any]]
        | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        self._config = config or QmdBackendConfig.from_env()
        self._runner = runner or subprocess.run
        self._which = which or shutil.which
        self._popen_factory = popen_factory or subprocess.Popen
        self._health_checker = health_checker or self._default_daemon_healthcheck
        self._json_requester = json_requester or self._default_json_request
        self._sleep = sleeper or time.sleep
        self._dirty = False
        self._bootstrapped = False
        self._last_sync_at: str | None = None
        self._last_error: str | None = None
        self._runtime_probe: QmdRuntimeProbe | None = None
        self._runtime_probe_monotonic: float | None = None
        self._daemon_process: Any | None = None
        self._daemon_state = QmdDaemonState(
            state="stopped" if self._config.daemon_enabled else "disabled",
        )
        self._manifest = self._load_manifest()
        self._ensure_dirs()
        self._dirty = bool(self._manifest.get("dirty", False))
        self._bootstrapped = bool(self._manifest.get("bootstrapped", False))
        self._last_sync_at = self._manifest.get("last_sync_at")
        last_error = self._manifest.get("last_error")
        self._last_error = str(last_error).strip() if last_error else None

    @property
    def enabled(self) -> bool:
        return bool(self._config.enabled)

    def descriptor(self, *, is_default: bool = False) -> MemoryBackendDescriptor:
        command, command_mode = self._resolve_command()
        available = self.enabled and command is not None
        runtime_probe: QmdRuntimeProbe | None = None
        runtime_problem: str | None = None
        if available and self._bootstrapped and not self._dirty:
            runtime_probe = self._probe_runtime_state(command, allow_cached=True)
            runtime_problem = runtime_probe.problem
        ready = (
            self._bootstrapped
            and not self._dirty
            and self._last_error is None
            and runtime_problem is None
        )
        metadata = {
            "enabled": self.enabled,
            "required": self._config.required,
            "install_mode": self._config.install_mode,
            "command_mode": command_mode,
            "command": list(command or []),
            "ready": ready,
            "dirty": self._dirty,
            "bootstrapped": self._bootstrapped,
            "last_sync_at": self._last_sync_at,
            "last_error": self._last_error,
            "embed_model": self._config.embed_model,
            "query_mode": self._normalize_query_mode(),
            "online_skip_rerank": self._online_skip_rerank_enabled(),
            "index_name": self._config.index_name,
            "collection_name": self._config.collection_name,
            "corpus_dir": str(self._config.corpus_dir),
            "manifest_path": str(self._config.manifest_path),
            "manifest_entries": len(self._manifest_entries()),
            "install_hint": self._install_hint(command_mode),
        }
        metadata.update(self._runtime_probe_metadata(runtime_probe))
        metadata.update(self._daemon_metadata())
        reason: str | None = None
        if not self.enabled:
            reason = "QMD sidecar backend is disabled"
        elif command is None:
            reason = (
                "QMD command is not available. "
                "Install it globally or let CoPaw use npx on demand."
            )
        elif runtime_problem and not ready:
            reason = runtime_problem
        elif self._last_error and not metadata["ready"]:
            reason = self._last_error
        return MemoryBackendDescriptor(
            backend_id=self.backend_id,
            label=self.label,
            available=available,
            is_default=is_default,
            reason=reason,
            metadata=metadata,
        )

    def replace_entries(self, entries: Sequence[MemoryFactIndexRecord]) -> None:
        if not self.enabled:
            return
        self._ensure_dirs()
        manifest_entries: dict[str, dict[str, Any]] = {}
        keep_paths: set[Path] = set()
        for entry in entries:
            relative_path = self._relative_path_for_entry(entry)
            target_path = self._config.corpus_dir / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(
                self._render_entry_markdown(entry),
                encoding="utf-8",
            )
            manifest_entries[relative_path.as_posix()] = self._manifest_payload_for_entry(
                entry,
            )
            keep_paths.add(target_path.resolve())
        if self._config.corpus_dir.exists():
            for path in self._config.corpus_dir.rglob("*.md"):
                if path.resolve() not in keep_paths:
                    path.unlink(missing_ok=True)
        self._cleanup_empty_dirs()
        self._manifest["entries"] = manifest_entries
        self._mark_dirty()

    def upsert_entry(self, entry: MemoryFactIndexRecord) -> None:
        if not self.enabled:
            return
        self._ensure_dirs()
        relative_path = self._relative_path_for_entry(entry)
        target_path = self._config.corpus_dir / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(
            self._render_entry_markdown(entry),
            encoding="utf-8",
        )
        entries = self._manifest_entries()
        entries[relative_path.as_posix()] = self._manifest_payload_for_entry(entry)
        self._manifest["entries"] = entries
        self._mark_dirty()

    def delete_entries(self, entry_ids: Sequence[str]) -> None:
        if not self.enabled or not entry_ids:
            return
        entry_id_set = {str(item).strip() for item in entry_ids if str(item).strip()}
        if not entry_id_set:
            return
        entries = self._manifest_entries()
        remaining: dict[str, dict[str, Any]] = {}
        deleted_any = False
        for relative_name, payload in entries.items():
            mapped_entry_id = str(payload.get("entry_id") or "").strip()
            if mapped_entry_id in entry_id_set:
                target_path = self._config.corpus_dir / Path(relative_name)
                target_path.unlink(missing_ok=True)
                deleted_any = True
                continue
            remaining[relative_name] = payload
        if not deleted_any:
            return
        self._manifest["entries"] = remaining
        self._cleanup_empty_dirs()
        self._mark_dirty()

    def recall(
        self,
        *,
        query: str,
        selector: MemoryScopeSelector,
        role: str | None,
        limit: int,
        entries: Sequence[MemoryFactIndexRecord],
    ) -> MemoryRecallResponse:
        allowed_entries = {
            entry.id: entry
            for entry in entries
            if self._entry_matches_selector(entry=entry, selector=selector, role=role)
        }
        if not allowed_entries:
            return MemoryRecallResponse(
                query=query,
                backend_requested=self.backend_id,
                backend_used=self.backend_id,
                hits=[],
            )
        command = self._ensure_ready()
        self._ensure_daemon_best_effort(command)
        candidate_limit = max(
            int(limit),
            min(max(int(limit) * 4, 12), int(self._config.query_candidate_limit)),
        )
        bridge_payload: list[dict[str, Any]] | None = None
        if self._daemon_state.state in {"running", "external"}:
            try:
                bridge_payload = self._run_bridge_query(
                    query=query,
                    limit=max(1, int(limit)),
                    candidate_limit=candidate_limit,
                )
            except QmdBackendError:
                bridge_payload = None
        query_mode = self._normalize_query_mode()
        if bridge_payload is None:
            query_argument = (
                self._build_query_document(query)
                if query_mode == "query"
                else self._normalize_query_text(query)
            )
            query_args = [
                *command,
                "--index",
                self._config.index_name,
                query_mode,
                query_argument,
                "--json",
                "-c",
                self._config.collection_name,
                "-n",
                str(candidate_limit),
            ]
            if query_mode != "search":
                query_args.extend(
                    [
                        "--min-score",
                        str(self._config.min_score),
                    ],
                )
            completed = self._run_command(
                query_args,
                timeout_seconds=self._config.command_timeout_seconds,
            )
            payload = self._parse_query_payload(completed.stdout)
        else:
            payload = bridge_payload
        path_map = {
            relative_path: str(item.get("entry_id") or "").strip()
            for relative_path, item in self._manifest_entries().items()
        }
        hits: list[MemoryRecallHit] = []
        seen: set[str] = set()
        for item in payload:
            relative_name = self._relative_name_from_result(item)
            if relative_name is None:
                continue
            entry_id = path_map.get(relative_name)
            if not entry_id or entry_id in seen:
                continue
            entry = allowed_entries.get(entry_id)
            if entry is None:
                continue
            score = _safe_float(
                item.get("score")
                or item.get("similarity")
                or item.get("rank_score")
                or item.get("normalized_score"),
            )
            metadata = dict(entry.metadata or {})
            metadata["qmd"] = {
                "docid": item.get("docid") or item.get("id"),
                "filepath": relative_name,
                "context": item.get("context"),
                "snippet": item.get("snippet") or item.get("excerpt"),
            }
            hits.append(
                MemoryRecallHit(
                    entry_id=entry.id,
                    kind=entry.source_type,
                    title=entry.title,
                    summary=entry.summary,
                    content_excerpt=(
                        str(item.get("snippet") or item.get("excerpt") or "").strip()
                        or entry.content_excerpt
                    ),
                    source_type=entry.source_type,
                    source_ref=entry.source_ref,
                    source_route=source_route_for_entry(entry),
                    scope_type=entry.scope_type,
                    scope_id=entry.scope_id,
                    owner_agent_id=entry.owner_agent_id,
                    owner_scope=entry.owner_scope,
                    industry_instance_id=entry.industry_instance_id,
                    evidence_refs=list(entry.evidence_refs or []),
                    entity_keys=list(entry.entity_keys or []),
                    opinion_keys=list(entry.opinion_keys or []),
                    confidence=entry.confidence,
                    quality_score=entry.quality_score,
                    score=max(0.0, score),
                    backend=self.backend_id,
                    source_updated_at=entry.source_updated_at,
                    metadata=metadata,
                ),
            )
            seen.add(entry_id)
            if len(hits) >= max(1, int(limit)):
                break
        return MemoryRecallResponse(
            query=query,
            backend_requested=self.backend_id,
            backend_used=self.backend_id,
            hits=hits,
        )

    def warmup(self) -> None:
        if not self.enabled:
            return
        command = self._ensure_ready()
        self._ensure_daemon_best_effort(command)
        self._prewarm_daemon_best_effort()

    def close(self) -> None:
        self._stop_daemon()

    def _ensure_ready(self) -> list[str]:
        if not self.enabled:
            raise QmdBackendError("QMD backend is disabled")
        command, _command_mode = self._resolve_command()
        if command is None:
            raise QmdBackendError(
                "QMD command is unavailable. Install it or enable npx-based bootstrap."
            )
        needs_sync = self._dirty or not self._bootstrapped
        if not needs_sync:
            runtime_probe = self._probe_runtime_state(command, allow_cached=False)
            needs_sync = runtime_probe.problem is not None
        if needs_sync:
            force_reembed = (
                str(self._manifest.get("embed_model") or "").strip()
                != self._config.embed_model
            )
            query_mode = self._normalize_query_mode()
            try:
                self._ensure_collection(command)
                self._run_command(
                    [
                        *command,
                        "--index",
                        self._config.index_name,
                        "update",
                    ],
                    timeout_seconds=self._config.command_timeout_seconds,
                )
                if query_mode in {"query", "vsearch"}:
                    embed_args = [
                        *command,
                        "--index",
                        self._config.index_name,
                        "embed",
                        "--model",
                        self._config.embed_model,
                    ]
                    if force_reembed:
                        embed_args.append("-f")
                    self._run_command(
                        embed_args,
                        timeout_seconds=self._config.embed_timeout_seconds,
                    )
            except QmdBackendError as exc:
                self._clear_runtime_probe()
                self._last_error = str(exc)
                self._manifest["last_error"] = self._last_error
                self._persist_manifest()
                raise
        self._clear_runtime_probe()
        runtime_probe = self._probe_runtime_state(command, allow_cached=False)
        if runtime_probe.problem is not None:
            self._last_error = runtime_probe.problem
            self._manifest["last_error"] = self._last_error
            self._persist_manifest()
            raise QmdBackendError(runtime_probe.problem)
        if needs_sync:
            self._bootstrapped = True
            self._dirty = False
            self._last_sync_at = _isoformat(utc_now())
        self._last_error = None
        self._manifest["bootstrapped"] = True
        self._manifest["dirty"] = False
        self._manifest["embed_model"] = self._config.embed_model
        self._manifest["last_sync_at"] = self._last_sync_at
        self._manifest["last_error"] = None
        self._persist_manifest()
        return command

    def _ensure_collection(self, command: list[str]) -> None:
        current_path = self._collection_path(command)
        expected_path = self._config.corpus_dir.resolve()
        if current_path is not None and current_path != expected_path:
            remove_result = self._run_command(
                [
                    *command,
                    "--index",
                    self._config.index_name,
                    "collection",
                    "remove",
                    self._config.collection_name,
                ],
                timeout_seconds=self._config.command_timeout_seconds,
                check=False,
            )
            if remove_result.returncode != 0:
                raise QmdBackendError(
                    "QMD collection path does not match corpus_dir and could not be reset"
                )
        add_args = [
            *command,
            "--index",
            self._config.index_name,
            "collection",
            "add",
            str(self._config.corpus_dir),
            "--name",
            self._config.collection_name,
            "--mask",
            "**/*.md",
        ]
        add_result = self._run_command(
            add_args,
            timeout_seconds=self._config.command_timeout_seconds,
            check=False,
        )
        if add_result.returncode != 0:
            combined = f"{add_result.stdout}\n{add_result.stderr}".strip().lower()
            if "already exists" not in combined:
                raise QmdBackendError(
                    f"QMD collection add failed: {add_result.stderr or add_result.stdout}"
                )
        context_value = self._config.collection_context.strip()
        if not context_value:
            return
        context_result = self._run_command(
            [
                *command,
                "--index",
                self._config.index_name,
                "context",
                "add",
                f"qmd://{self._config.collection_name}",
                context_value,
            ],
            timeout_seconds=self._config.command_timeout_seconds,
            check=False,
        )
        if context_result.returncode != 0:
            combined = f"{context_result.stdout}\n{context_result.stderr}".strip().lower()
            if "already exists" not in combined and "duplicate" not in combined:
                raise QmdBackendError(
                    f"QMD context add failed: {context_result.stderr or context_result.stdout}"
                )

    def _collection_path(self, command: list[str]) -> Path | None:
        result = self._run_command(
            [
                *command,
                "--index",
                self._config.index_name,
                "collection",
                "show",
                self._config.collection_name,
            ],
            timeout_seconds=self._config.command_timeout_seconds,
            check=False,
        )
        if result.returncode != 0:
            return None
        for line in str(result.stdout or "").splitlines():
            stripped = line.strip()
            if not stripped.lower().startswith("path:"):
                continue
            path_text = stripped.split(":", 1)[1].strip()
            if not path_text:
                return None
            return Path(path_text).expanduser().resolve()
        return None

    def _run_command(
        self,
        args: Sequence[str],
        *,
        timeout_seconds: int,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = self._runner(
                list(args),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                env=self._command_env(),
                cwd=str(self._config.base_dir),
                shell=False,
                check=False,
            )
        except FileNotFoundError as exc:
            raise QmdBackendError(f"QMD command not found: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise QmdBackendError(
                f"QMD command timed out after {timeout_seconds}s: {' '.join(args)}"
            ) from exc
        if check and result.returncode != 0:
            stderr = str(result.stderr or "").strip()
            stdout = str(result.stdout or "").strip()
            detail = stderr or stdout or f"exit code {result.returncode}"
            raise QmdBackendError(f"QMD command failed: {detail}")
        return result

    def _probe_runtime_state(
        self,
        command: list[str],
        *,
        allow_cached: bool,
    ) -> QmdRuntimeProbe:
        cached = self._cached_runtime_probe() if allow_cached else None
        if cached is not None:
            return cached
        collection_path = self._collection_path(command)
        status_result = self._run_command(
            [
                *command,
                "--index",
                self._config.index_name,
                "status",
            ],
            timeout_seconds=self._config.command_timeout_seconds,
            check=False,
        )
        probe = QmdRuntimeProbe(
            checked_at=_isoformat(utc_now()) or "",
            collection_path=collection_path,
        )
        if status_result.returncode != 0:
            detail = (
                str(status_result.stderr or "").strip()
                or str(status_result.stdout or "").strip()
                or f"exit code {status_result.returncode}"
            )
            probe.problem = f"QMD status probe failed: {detail}"
            return self._cache_runtime_probe(probe)
        stdout = str(status_result.stdout or "")
        probe.index_path = self._extract_status_value(stdout, "Index")
        probe.documents_total = self._extract_status_metric(stdout, "Total")
        probe.embedded_vectors = self._extract_status_metric(stdout, "Vectors")
        probe.pending_embeddings = self._extract_status_metric(stdout, "Pending")
        probe.gpu_backend = self._extract_status_value(stdout, "GPU")
        probe.mcp_running, probe.mcp_pid = self._extract_mcp_state(stdout)
        probe.problem = self._runtime_problem_for_probe(probe)
        return self._cache_runtime_probe(probe)

    def _resolve_command(self) -> tuple[list[str] | None, str]:
        if not self.enabled:
            return None, "disabled"
        install_mode = self._config.install_mode
        if install_mode not in {"auto", "path", "npx", "bunx"}:
            install_mode = "auto"
        if install_mode in {"auto", "path"}:
            resolved = self._resolve_binary(self._config.binary_name)
            windows_node_dist = self._resolve_windows_node_dist_command(resolved)
            if windows_node_dist is not None:
                return windows_node_dist, "node-dist-cli"
            if resolved is not None:
                return [resolved], "path"
            if install_mode == "path":
                return None, "path"
        if install_mode in {"auto", "npx"}:
            npx = self._resolve_binary("npx")
            if npx is not None:
                return [npx, "-y", self._config.npm_package], "npx"
            if install_mode == "npx":
                return None, "npx"
        if install_mode in {"auto", "bunx"}:
            bunx = self._resolve_binary("bunx")
            if bunx is not None:
                return [bunx, self._config.npm_package], "bunx"
            if install_mode == "bunx":
                return None, "bunx"
        return None, install_mode

    def _resolve_binary(self, value: str) -> str | None:
        normalized = str(value or "").strip()
        if not normalized:
            return None
        candidate = Path(normalized)
        if candidate.exists():
            return str(candidate.resolve())
        return self._which(normalized)

    def _resolve_windows_node_dist_command(
        self,
        resolved_binary: str | None,
    ) -> list[str] | None:
        if os.name != "nt":
            return None
        node_binary = self._resolve_binary("node")
        if node_binary is None:
            return None
        candidates: list[Path] = []
        seen: set[str] = set()

        def _append_candidate(path: Path | None) -> None:
            if path is None:
                return
            normalized = str(path).strip()
            if not normalized or normalized in seen:
                return
            seen.add(normalized)
            candidates.append(path)

        resolved_path = Path(resolved_binary).resolve() if resolved_binary else None
        if resolved_path is not None:
            if resolved_path.is_file() and resolved_path.name.lower() == "qmd.js":
                _append_candidate(resolved_path)
            if resolved_path.parent.name.lower() in {"bin", "scripts"}:
                _append_candidate(
                    self._qmd_dist_cli_path(resolved_path.parent.parent),
                )
            _append_candidate(self._qmd_dist_cli_path(resolved_path.parent))
        npm_prefix = self._resolve_npm_global_prefix()
        if npm_prefix is not None:
            _append_candidate(self._qmd_dist_cli_path(npm_prefix))
        for candidate in candidates:
            if candidate.exists():
                return [node_binary, str(candidate.resolve())]
        return None

    def _resolve_npm_global_prefix(self) -> Path | None:
        prefix_raw = (
            str(os.environ.get("NPM_CONFIG_PREFIX", "") or "").strip()
            or str(os.environ.get("npm_config_prefix", "") or "").strip()
        )
        if prefix_raw:
            return Path(prefix_raw).expanduser().resolve()
        npm_binary = self._resolve_binary("npm.cmd") or self._resolve_binary("npm")
        if npm_binary is None:
            return None
        try:
            result = self._runner(
                [npm_binary, "config", "get", "prefix"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=min(20, self._config.command_timeout_seconds),
                env=os.environ.copy(),
                cwd=str(self._config.base_dir),
                shell=False,
                check=False,
            )
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0:
            return None
        prefix_text = str(result.stdout or "").strip()
        if not prefix_text or prefix_text.lower() in {"undefined", "null"}:
            return None
        return Path(prefix_text).expanduser().resolve()

    def _qmd_dist_cli_path(self, prefix: Path) -> Path:
        path = prefix / "node_modules"
        for part in self._npm_package_parts():
            path = path / part
        return path / "dist" / "cli" / "qmd.js"

    def _npm_package_parts(self) -> tuple[str, ...]:
        package_name = str(self._config.npm_package or "").strip().replace("\\", "/")
        if not package_name:
            package_name = "@tobilu/qmd"
        return tuple(part for part in package_name.split("/") if part)

    def _render_entry_markdown(self, entry: MemoryFactIndexRecord) -> str:
        metadata = dict(entry.metadata or {})
        lines = [
            "---",
            f"entry_id: {entry.id}",
            f"source_type: {entry.source_type}",
            f"source_ref: {entry.source_ref}",
            f"scope_type: {entry.scope_type}",
            f"scope_id: {entry.scope_id}",
        ]
        if entry.owner_agent_id:
            lines.append(f"owner_agent_id: {entry.owner_agent_id}")
        if entry.owner_scope:
            lines.append(f"owner_scope: {entry.owner_scope}")
        if entry.industry_instance_id:
            lines.append(f"industry_instance_id: {entry.industry_instance_id}")
        lines.extend(
            [
                f"confidence: {entry.confidence:.4f}",
                f"quality_score: {entry.quality_score:.4f}",
                f"source_updated_at: {_isoformat(entry.source_updated_at) or ''}",
                f"source_route: {source_route_for_entry(entry) or ''}",
            ],
        )
        lines.append("---")
        lines.append("")
        lines.append(f"# {entry.title}")
        lines.append("")
        lines.append("## Summary")
        lines.append(entry.summary or entry.content_excerpt or entry.title)
        lines.append("")
        lines.append("## Content")
        lines.append(entry.content_text or entry.content_excerpt or entry.summary or entry.title)
        lines.append("")
        if entry.entity_keys:
            lines.append("## Entities")
            lines.extend(f"- {item}" for item in entry.entity_keys)
            lines.append("")
        if entry.opinion_keys:
            lines.append("## Opinions")
            lines.extend(f"- {item}" for item in entry.opinion_keys)
            lines.append("")
        if entry.tags:
            lines.append("## Tags")
            lines.extend(f"- {item}" for item in entry.tags)
            lines.append("")
        if entry.role_bindings:
            lines.append("## Role Bindings")
            lines.extend(f"- {item}" for item in entry.role_bindings)
            lines.append("")
        if entry.evidence_refs:
            lines.append("## Evidence Refs")
            lines.extend(f"- {item}" for item in entry.evidence_refs)
            lines.append("")
        if metadata:
            lines.append("## Metadata")
            lines.append(json.dumps(metadata, ensure_ascii=False, sort_keys=True, indent=2))
            lines.append("")
        return "\n".join(lines).strip() + "\n"

    def _relative_path_for_entry(self, entry: MemoryFactIndexRecord) -> Path:
        digest = hashlib.sha1(entry.id.encode("utf-8")).hexdigest()[:20]
        scope_slug = slugify(entry.scope_id, fallback="runtime")
        source_slug = slugify(entry.source_type, fallback="source")
        return Path("entries") / entry.scope_type / scope_slug / source_slug / f"{digest}.md"

    def _manifest_payload_for_entry(self, entry: MemoryFactIndexRecord) -> dict[str, Any]:
        return {
            "entry_id": entry.id,
            "source_type": entry.source_type,
            "source_ref": entry.source_ref,
            "scope_type": entry.scope_type,
            "scope_id": entry.scope_id,
            "title": entry.title,
            "source_updated_at": _isoformat(entry.source_updated_at),
        }

    def _entry_matches_selector(
        self,
        *,
        entry: MemoryFactIndexRecord,
        selector: MemoryScopeSelector,
        role: str | None,
    ) -> bool:
        normalized_role = str(role or "").strip().lower()
        if normalized_role and entry.role_bindings:
            bindings = {str(item).strip().lower() for item in entry.role_bindings}
            if normalized_role not in bindings:
                return False
        return True

    def _parse_query_payload(self, stdout: str) -> list[dict[str, Any]]:
        raw = str(stdout or "").strip()
        if not raw:
            return []
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise QmdBackendError(f"QMD query returned invalid JSON: {exc}") from exc
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("results", "hits", "items", "documents"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
            return [payload]
        return []

    def _relative_name_from_result(self, item: dict[str, Any]) -> str | None:
        candidates = (
            item.get("filepath"),
            item.get("path"),
            item.get("file"),
            item.get("filename"),
            item.get("relative_path"),
        )
        for candidate in candidates:
            text = str(candidate or "").strip()
            if not text:
                continue
            normalized = text.replace("\\", "/")
            if normalized.lower().startswith("qmd://"):
                trimmed = normalized[6:]
                _collection, _sep, relative_path = trimmed.partition("/")
                normalized_relative = relative_path.strip().lstrip("./")
                if normalized_relative:
                    return normalized_relative
                return None
            if Path(text).is_absolute() or normalized.startswith("/"):
                try:
                    return (
                        Path(text)
                        .resolve()
                        .relative_to(self._config.corpus_dir.resolve())
                        .as_posix()
                    )
                except ValueError:
                    return Path(text).name
            return normalized.lstrip("./")
        return None

    def _ensure_dirs(self) -> None:
        self._config.base_dir.mkdir(parents=True, exist_ok=True)
        self._config.corpus_dir.mkdir(parents=True, exist_ok=True)
        self._config.xdg_cache_home.mkdir(parents=True, exist_ok=True)
        self._config.manifest_path.parent.mkdir(parents=True, exist_ok=True)

    def _cleanup_empty_dirs(self) -> None:
        if not self._config.corpus_dir.exists():
            return
        directories = sorted(
            [path for path in self._config.corpus_dir.rglob("*") if path.is_dir()],
            key=lambda item: len(item.parts),
            reverse=True,
        )
        for directory in directories:
            try:
                directory.rmdir()
            except OSError:
                continue

    def _mark_dirty(self) -> None:
        self._dirty = True
        self._bootstrapped = False
        self._clear_runtime_probe()
        self._manifest["dirty"] = True
        self._manifest["bootstrapped"] = False
        self._manifest["last_error"] = self._last_error
        self._persist_manifest()

    def _load_manifest(self) -> dict[str, Any]:
        try:
            raw = self._config.manifest_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {"version": 1, "entries": {}}
        except OSError:
            return {"version": 1, "entries": {}}
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return {"version": 1, "entries": {}}
        normalized = _normalize_mapping_payload(payload)
        normalized.setdefault("version", 1)
        entries = normalized.get("entries")
        normalized["entries"] = dict(entries) if isinstance(entries, dict) else {}
        return normalized

    def _persist_manifest(self) -> None:
        payload = dict(self._manifest)
        payload["dirty"] = self._dirty
        payload["bootstrapped"] = self._bootstrapped
        payload["last_sync_at"] = self._last_sync_at
        payload["last_error"] = self._last_error
        payload.setdefault("embed_model", self._config.embed_model)
        payload.setdefault("version", 1)
        self._config.manifest_path.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )

    def _manifest_entries(self) -> dict[str, dict[str, Any]]:
        entries = self._manifest.get("entries")
        return dict(entries) if isinstance(entries, dict) else {}

    def _build_query_document(self, query: str) -> str:
        normalized = self._normalize_query_text(query)
        return "\n".join(
            [
                f"lex: {normalized}",
                f"vec: {normalized}",
            ],
        )

    def _normalize_query_text(self, query: str) -> str:
        normalized = " ".join(str(query or "").strip().split())
        return normalized or "memory"

    def _normalize_query_mode(self) -> str:
        query_mode = str(self._config.query_mode or "").strip().lower()
        if query_mode in {"query", "search", "vsearch"}:
            return query_mode
        return _DEFAULT_QMD_QUERY_MODE

    def _online_skip_rerank_enabled(self) -> bool:
        return bool(self._config.online_skip_rerank)

    def _install_hint(self, command_mode: str) -> str:
        if command_mode == "path":
            return "qmd is expected on PATH"
        if command_mode == "node-dist-cli":
            return "Windows npm wrapper bypassed via node dist/cli/qmd.js"
        if command_mode == "npx":
            return "npx will fetch @tobilu/qmd on demand"
        if command_mode == "bunx":
            return "bunx will fetch @tobilu/qmd on demand"
        return "Install qmd or expose npx on PATH"

    def _command_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["QMD_EMBED_MODEL"] = self._config.embed_model
        env.setdefault("NO_COLOR", "1")
        env.setdefault("XDG_CACHE_HOME", str(self._config.xdg_cache_home))
        return env

    def _cached_runtime_probe(self) -> QmdRuntimeProbe | None:
        if self._runtime_probe is None or self._runtime_probe_monotonic is None:
            return None
        if (time.monotonic() - self._runtime_probe_monotonic) > _RUNTIME_PROBE_TTL_SECONDS:
            self._clear_runtime_probe()
            return None
        return self._runtime_probe

    def _cache_runtime_probe(self, probe: QmdRuntimeProbe) -> QmdRuntimeProbe:
        self._runtime_probe = probe
        self._runtime_probe_monotonic = time.monotonic()
        return probe

    def _clear_runtime_probe(self) -> None:
        self._runtime_probe = None
        self._runtime_probe_monotonic = None

    def _runtime_problem_for_probe(self, probe: QmdRuntimeProbe) -> str | None:
        expected_path = self._config.corpus_dir.resolve()
        manifest_entries = len(self._manifest_entries())
        if probe.collection_path is None:
            return "QMD collection is not registered for the current corpus."
        if probe.collection_path != expected_path:
            return (
                "QMD collection path does not match corpus_dir "
                f"({probe.collection_path} != {expected_path})."
            )
        if manifest_entries <= 0:
            return None
        if probe.documents_total is None:
            return "QMD status did not report indexed document count."
        if probe.documents_total < manifest_entries:
            return (
                "QMD indexed document count is behind manifest entries "
                f"({probe.documents_total} < {manifest_entries})."
            )
        if self._normalize_query_mode() not in {"query", "vsearch"}:
            return None
        if probe.pending_embeddings is None:
            return "QMD status did not report pending embeddings."
        if probe.pending_embeddings > 0:
            return (
                "QMD still has pending embeddings for semantic recall "
                f"({probe.pending_embeddings})."
            )
        return None

    def _runtime_probe_metadata(
        self,
        probe: QmdRuntimeProbe | None,
    ) -> dict[str, Any]:
        if probe is None:
            return {
                "runtime_checked_at": None,
                "runtime_problem": None,
                "collection_path_detected": None,
                "collection_path_matches": None,
                "index_path": None,
                "indexed_documents": None,
                "embedded_vectors": None,
                "pending_embeddings": None,
                "mcp_running": None,
                "mcp_pid": None,
                "gpu_backend": None,
            }
        return {
            "runtime_checked_at": probe.checked_at,
            "runtime_problem": probe.problem,
            "collection_path_detected": (
                str(probe.collection_path) if probe.collection_path is not None else None
            ),
            "collection_path_matches": (
                probe.collection_path == self._config.corpus_dir.resolve()
                if probe.collection_path is not None
                else False
            ),
            "index_path": probe.index_path,
            "indexed_documents": probe.documents_total,
            "embedded_vectors": probe.embedded_vectors,
            "pending_embeddings": probe.pending_embeddings,
            "mcp_running": probe.mcp_running,
            "mcp_pid": probe.mcp_pid,
            "gpu_backend": probe.gpu_backend,
        }

    def _daemon_metadata(self) -> dict[str, Any]:
        return {
            "daemon_enabled": self._config.daemon_enabled,
            "daemon_url": self._daemon_base_url(),
            "daemon_impl": "copaw-qmd-bridge",
            "daemon_state": self._daemon_state.state,
            "daemon_owned": self._daemon_state.owned,
            "daemon_pid": self._daemon_state.pid,
            "daemon_last_error": self._daemon_state.last_error,
            "daemon_last_started_at": self._daemon_state.last_started_at,
        }

    def _daemon_base_url(self) -> str:
        return f"http://{self._config.daemon_host}:{self._config.daemon_port}"

    def _ensure_daemon_best_effort(self, command: list[str]) -> None:
        if not self._config.daemon_enabled:
            self._daemon_state.state = "disabled"
            return
        try:
            self._ensure_daemon_started(command)
        except QmdBackendError as exc:
            self._daemon_state.state = "failed"
            self._daemon_state.owned = False
            self._daemon_state.pid = None
            self._daemon_state.last_error = str(exc)

    def _ensure_daemon_started(self, command: list[str]) -> None:
        if not self._config.daemon_enabled:
            self._daemon_state.state = "disabled"
            return
        if self._daemon_process is not None and self._daemon_process.poll() is None:
            self._daemon_state.state = "running"
            self._daemon_state.owned = True
            self._daemon_state.pid = getattr(self._daemon_process, "pid", None)
            self._daemon_state.last_error = None
            return
        self._daemon_process = None
        daemon_url = self._daemon_base_url()
        health_url = f"{daemon_url}/health"
        health_payload = self._daemon_health_payload()
        if health_payload is not None:
            service_name = str(health_payload.get("service") or "").strip().lower()
            if service_name == "copaw-qmd-bridge":
                self._daemon_state.state = "external"
                self._daemon_state.owned = False
                self._daemon_state.pid = None
                self._daemon_state.last_error = None
                return
            raise QmdBackendError(
                "Configured QMD daemon port is occupied by an incompatible service."
            )
        bridge_command = self._bridge_launch_command(command)
        try:
            process = self._popen_factory(
                list(bridge_command),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=self._bridge_env(command),
                cwd=str(self._config.base_dir),
                shell=False,
            )
        except (FileNotFoundError, OSError) as exc:
            raise QmdBackendError(f"QMD daemon failed to start: {exc}") from exc
        self._daemon_state.state = "starting"
        deadline = time.monotonic() + float(self._config.daemon_start_timeout_seconds)
        while time.monotonic() < deadline:
            health_payload = self._daemon_health_payload()
            if health_payload is not None:
                self._daemon_process = process
                self._daemon_state.state = "running"
                self._daemon_state.owned = True
                self._daemon_state.pid = getattr(process, "pid", None)
                self._daemon_state.last_error = None
                self._daemon_state.last_started_at = _isoformat(utc_now())
                return
            if process.poll() is not None:
                startup_error = self._process_output(process)
                self._stop_process(process)
                raise QmdBackendError(
                    "QMD daemon exited before becoming healthy on the configured port. "
                    f"{startup_error}".strip()
                )
            self._sleep(0.2)
        self._stop_process(process)
        raise QmdBackendError(
            "QMD daemon did not become healthy before the startup timeout elapsed."
        )

    def _prewarm_daemon_best_effort(self) -> None:
        if self._daemon_state.state not in {"running", "external"}:
            return
        try:
            self._json_requester(
                f"{self._daemon_base_url()}/prewarm",
                "POST",
                {
                    "query": self._normalize_query_text("memory"),
                    "collections": [self._config.collection_name],
                    "skipRerank": True,
                },
                float(self._config.embed_timeout_seconds),
            )
        except QmdBackendError as exc:
            self._daemon_state.last_error = str(exc)

    def _stop_daemon(self) -> None:
        process = self._daemon_process
        self._daemon_process = None
        if process is not None:
            self._stop_process(process)
        if self._config.daemon_enabled:
            self._daemon_state.state = "stopped"
        else:
            self._daemon_state.state = "disabled"
        self._daemon_state.owned = False
        self._daemon_state.pid = None

    def _stop_process(self, process: Any) -> None:
        poll = getattr(process, "poll", None)
        if not callable(poll):
            return
        if poll() is not None:
            wait = getattr(process, "wait", None)
            if callable(wait):
                try:
                    wait(timeout=1)
                except Exception:
                    pass
            return
        terminate = getattr(process, "terminate", None)
        if callable(terminate):
            terminate()
        wait = getattr(process, "wait", None)
        if callable(wait):
            try:
                wait(timeout=5)
                return
            except subprocess.TimeoutExpired:
                pass
            except Exception:
                return
        kill = getattr(process, "kill", None)
        if callable(kill):
            kill()
            if callable(wait):
                try:
                    wait(timeout=2)
                except Exception:
                    pass

    def _default_daemon_healthcheck(self, url: str, timeout_seconds: float) -> bool:
        payload = self._daemon_health_payload()
        if payload is None:
            return False
        return str(payload.get("status") or "").strip().lower() == "ok"

    def _daemon_health_payload(self) -> dict[str, Any] | None:
        try:
            payload = self._json_requester(
                f"{self._daemon_base_url()}/health",
                "GET",
                None,
                float(self._config.daemon_health_timeout_seconds),
            )
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def _run_bridge_query(
        self,
        *,
        query: str,
        limit: int,
        candidate_limit: int,
    ) -> list[dict[str, Any]]:
        payload = self._json_requester(
            f"{self._daemon_base_url()}/query",
            "POST",
            {
                "searches": self._bridge_searches(query),
                "collections": [self._config.collection_name],
                "limit": limit,
                "minScore": self._config.min_score
                if self._normalize_query_mode() != "search"
                else 0.0,
                "candidateLimit": candidate_limit,
                "skipRerank": self._online_skip_rerank_enabled(),
            },
            float(self._config.command_timeout_seconds),
        )
        if not isinstance(payload, dict):
            raise QmdBackendError("QMD bridge returned an invalid response payload.")
        results = payload.get("results")
        if not isinstance(results, list):
            raise QmdBackendError("QMD bridge response did not include a results array.")
        return [item for item in results if isinstance(item, dict)]

    def _bridge_searches(self, query: str) -> list[dict[str, str]]:
        normalized = self._normalize_query_text(query)
        query_mode = self._normalize_query_mode()
        if query_mode == "search":
            return [{"type": "lex", "query": normalized}]
        if query_mode == "vsearch":
            return [{"type": "vec", "query": normalized}]
        return [
            {"type": "lex", "query": normalized},
            {"type": "vec", "query": normalized},
        ]

    def _bridge_launch_command(self, command: list[str]) -> list[str]:
        node_binary = self._resolve_bridge_node_binary(command)
        if node_binary is None:
            raise QmdBackendError("Node runtime is unavailable for the CoPaw QMD bridge.")
        return [
            node_binary,
            str(self._bridge_script_path()),
        ]

    def _resolve_bridge_node_binary(self, command: list[str]) -> str | None:
        if command and Path(command[0]).name.lower() in {"node", "node.exe"}:
            return command[0]
        return self._resolve_binary("node")

    def _bridge_script_path(self) -> Path:
        return Path(__file__).resolve().with_name("qmd_bridge_server.mjs")

    def _bridge_env(self, command: list[str]) -> dict[str, str]:
        env = self._command_env()
        sdk_entries = self._resolve_bridge_sdk_entries(command)
        if sdk_entries is None:
            raise QmdBackendError(
                "Could not resolve QMD SDK entry points for the CoPaw bridge."
            )
        index_entry, store_entry = sdk_entries
        env["INDEX_PATH"] = str(self._index_db_path())
        env["COPAW_QMD_BRIDGE_DB_PATH"] = str(self._index_db_path())
        env["COPAW_QMD_BRIDGE_HOST"] = self._config.daemon_host
        env["COPAW_QMD_BRIDGE_PORT"] = str(self._config.daemon_port)
        env["COPAW_QMD_BRIDGE_COLLECTION_NAME"] = self._config.collection_name
        env["COPAW_QMD_BRIDGE_SDK_INDEX_ENTRY"] = index_entry
        env["COPAW_QMD_BRIDGE_SDK_STORE_ENTRY"] = store_entry
        return env

    def _resolve_bridge_sdk_entries(self, command: list[str]) -> tuple[str, str] | None:
        cli_candidate: Path | None = None
        if len(command) >= 2:
            cli_candidate = Path(command[1]).expanduser().resolve()
        elif len(command) == 1:
            single = Path(command[0]).expanduser()
            if single.name.lower() == "qmd.js" and single.exists():
                cli_candidate = single.resolve()
        if cli_candidate is not None and cli_candidate.name.lower() == "qmd.js":
            dist_dir = cli_candidate.parent.parent
            index_js = dist_dir / "index.js"
            store_js = dist_dir / "store.js"
            if index_js.exists() and store_js.exists():
                return index_js.resolve().as_uri(), store_js.resolve().as_uri()
        return None

    def _index_db_path(self) -> Path:
        return self._config.xdg_cache_home / "qmd" / f"{self._config.index_name}.sqlite"

    def _process_output(self, process: Any) -> str:
        stdout_getter = getattr(process, "stdout", None)
        stderr_getter = getattr(process, "stderr", None)
        parts: list[str] = []
        for stream in (stdout_getter, stderr_getter):
            if stream is None:
                continue
            try:
                if hasattr(stream, "read"):
                    value = stream.read()
                else:
                    value = None
            except Exception:
                value = None
            text = str(value or "").strip()
            if text:
                parts.append(text)
        return " ".join(parts).strip()

    def _default_json_request(
        self,
        url: str,
        method: str,
        payload: dict[str, Any] | None,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        data = None
        headers = {"Content-Type": "application/json"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers=headers,
            method=method.upper(),
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise QmdBackendError(
                f"QMD bridge request failed ({exc.code}): {detail or exc.reason}"
            ) from exc
        except (OSError, urllib.error.URLError, ValueError) as exc:
            raise QmdBackendError(f"QMD bridge request failed: {exc}") from exc
        try:
            parsed = json.loads(raw or "{}")
        except json.JSONDecodeError as exc:
            raise QmdBackendError(f"QMD bridge returned invalid JSON: {exc}") from exc
        if isinstance(parsed, dict) and parsed.get("error"):
            raise QmdBackendError(str(parsed.get("error")))
        if not isinstance(parsed, dict):
            raise QmdBackendError("QMD bridge returned an unexpected JSON payload.")
        return parsed

    def _extract_status_value(self, stdout: str, label: str) -> str | None:
        match = re.search(
            rf"(?mi)^\s*{re.escape(label)}:\s*(.+?)\s*$",
            str(stdout or ""),
        )
        if match is None:
            return None
        value = str(match.group(1) or "").strip()
        return value or None

    def _extract_status_metric(self, stdout: str, label: str) -> int | None:
        value = self._extract_status_value(stdout, label)
        if not value:
            return None
        match = re.search(r"(\d+)", value)
        if match is None:
            return None
        return int(match.group(1))

    def _extract_mcp_state(self, stdout: str) -> tuple[bool | None, int | None]:
        value = self._extract_status_value(stdout, "MCP")
        if not value:
            return None, None
        pid_match = re.search(r"\bpid\s+(\d+)\b", value, flags=re.IGNORECASE)
        pid = int(pid_match.group(1)) if pid_match is not None else None
        normalized = value.lower()
        return normalized.startswith("running"), pid
