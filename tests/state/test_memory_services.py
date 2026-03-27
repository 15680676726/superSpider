# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from copaw.memory import (
    DerivedMemoryIndexService,
    MemoryRecallService,
    MemoryReflectionService,
    MemoryRetainService,
    QmdBackendConfig,
    QmdRecallBackend,
)
from copaw.state import AgentReportRecord, SQLiteStateStore, StrategyMemoryRecord
from copaw.state.knowledge_service import StateKnowledgeService
from copaw.state.repositories import (
    SqliteAgentReportRepository,
    SqliteKnowledgeChunkRepository,
    SqliteMemoryEntityViewRepository,
    SqliteMemoryFactIndexRepository,
    SqliteMemoryOpinionViewRepository,
    SqliteMemoryReflectionRunRepository,
    SqliteStrategyMemoryRepository,
)
from copaw.state.strategy_memory_service import StateStrategyMemoryService


class _FakeQmdRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.query_payload = "[]"
        self.fail_query = False
        self.collection_show_payloads: list[str | None] = []
        self.status_payloads: list[str | None] = []

    def __call__(self, args, **kwargs):
        args_list = list(args)
        self.calls.append(
            {
                "args": args_list,
                "env": dict(kwargs.get("env") or {}),
            },
        )
        if "collection" in args_list and "show" in args_list:
            stdout = self._next_collection_show(kwargs.get("cwd"))
            return subprocess.CompletedProcess(
                args=args_list,
                returncode=0 if stdout else 1,
                stdout=stdout,
                stderr="" if stdout else "collection not found",
            )
        if "status" in args_list:
            stdout = self._next_status(kwargs.get("cwd"))
            return subprocess.CompletedProcess(
                args=args_list,
                returncode=0,
                stdout=stdout,
                stderr="",
            )
        if any(command in args_list for command in ("query", "search", "vsearch")):
            if self.fail_query:
                return subprocess.CompletedProcess(
                    args=args_list,
                    returncode=1,
                    stdout="",
                    stderr="query failed",
                )
            return subprocess.CompletedProcess(
                args=args_list,
                returncode=0,
                stdout=self.query_payload,
                stderr="",
            )
        return subprocess.CompletedProcess(
            args=args_list,
            returncode=0,
            stdout="",
            stderr="",
        )

    def _next_collection_show(self, cwd: object) -> str | None:
        if self.collection_show_payloads:
            return self.collection_show_payloads.pop(0)
        corpus_dir = Path(str(cwd or "")).resolve() / "corpus"
        return (
            "Collection: copaw-memory\n"
            f"  Path:     {corpus_dir}\n"
            "  Pattern:  **/*.md\n"
            "  Include:  yes (default)\n"
        )

    def _next_status(self, cwd: object) -> str:
        if self.status_payloads:
            payload = self.status_payloads.pop(0)
            if payload is not None:
                return payload
        corpus_dir = Path(str(cwd or "")).resolve() / "corpus"
        document_count = len(list(corpus_dir.rglob("*.md"))) if corpus_dir.exists() else 0
        return self.render_status(
            documents_total=document_count,
            embedded_vectors=document_count,
            pending_embeddings=0,
        )

    @staticmethod
    def render_status(
        *,
        documents_total: int,
        embedded_vectors: int,
        pending_embeddings: int,
        mcp_running: bool = False,
        mcp_pid: int | None = None,
    ) -> str:
        mcp_text = "running" if mcp_running else "stopped"
        if mcp_running and mcp_pid is not None:
            mcp_text = f"{mcp_text} (PID {mcp_pid})"
        return (
            "QMD Status\n\n"
            "Index: /tmp/.cache/qmd/copaw-memory.sqlite\n"
            "Size:  1.0 MB\n"
            f"MCP:   {mcp_text}\n\n"
            "Documents\n"
            f"  Total:    {documents_total} files indexed\n"
            f"  Vectors:  {embedded_vectors} embedded\n"
            f"  Pending:  {pending_embeddings} need embedding (run 'qmd embed')\n"
        )


def _build_qmd_backend(tmp_path, runner: _FakeQmdRunner) -> QmdRecallBackend:
    base_dir = tmp_path / "qmd-sidecar"
    return QmdRecallBackend(
        config=QmdBackendConfig(
            enabled=True,
            install_mode="path",
            binary_name="qmd",
            base_dir=base_dir,
            corpus_dir=base_dir / "corpus",
            manifest_path=base_dir / "manifest.json",
            xdg_cache_home=base_dir / "xdg-cache",
        ),
        runner=runner,
        which=lambda _name: "qmd",
    )


class _FakeQmdProcess:
    def __init__(self, pid: int = 43210) -> None:
        self.pid = pid
        self.returncode: int | None = None
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 0

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    def wait(self, timeout=None) -> int:
        return 0 if self.returncode is None else self.returncode


class _FakePopenFactory:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.processes: list[_FakeQmdProcess] = []

    def __call__(self, args, **kwargs):
        process = _FakeQmdProcess(pid=43000 + len(self.processes))
        self.processes.append(process)
        self.calls.append(
            {
                "args": list(args),
                "kwargs": dict(kwargs),
                "process": process,
            },
        )
        return process


class _HealthChecker:
    def __init__(self, responses: list[bool]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def __call__(self, url: str, timeout: float) -> bool:
        self.calls.append({"url": url, "timeout": timeout})
        if self._responses:
            return self._responses.pop(0)
        return True


class _FakeJsonRequester:
    def __init__(self, responses: list[object] | None = None) -> None:
        self._responses = list(responses or [])
        self.calls: list[dict[str, object]] = []

    def __call__(
        self,
        url: str,
        method: str,
        payload: dict[str, object] | None,
        timeout: float,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "url": url,
                "method": method,
                "payload": payload,
                "timeout": timeout,
            },
        )
        if not self._responses:
            raise RuntimeError("No fake JSON response configured")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return dict(response)


def _prepare_fake_qmd_sdk(tmp_path):
    prefix = tmp_path / "node-global"
    dist_dir = prefix / "node_modules" / "@tobilu" / "qmd" / "dist"
    cli_dir = dist_dir / "cli"
    cli_dir.mkdir(parents=True)
    (dist_dir / "index.js").write_text("export {};\n", encoding="utf-8")
    (dist_dir / "store.js").write_text("export {};\n", encoding="utf-8")
    qmd_js = cli_dir / "qmd.js"
    qmd_js.write_text("// qmd cli stub\n", encoding="utf-8")
    node_exe = tmp_path / "node.exe"
    node_exe.write_text("", encoding="utf-8")
    return qmd_js, node_exe


def _build_memory_services(tmp_path, *, sidecar_backends=None):
    store = SQLiteStateStore(tmp_path / "state.db")
    knowledge_repo = SqliteKnowledgeChunkRepository(store)
    strategy_repo = SqliteStrategyMemoryRepository(store)
    agent_report_repo = SqliteAgentReportRepository(store)
    fact_repo = SqliteMemoryFactIndexRepository(store)
    entity_repo = SqliteMemoryEntityViewRepository(store)
    opinion_repo = SqliteMemoryOpinionViewRepository(store)
    reflection_repo = SqliteMemoryReflectionRunRepository(store)
    derived = DerivedMemoryIndexService(
        fact_index_repository=fact_repo,
        entity_view_repository=entity_repo,
        opinion_view_repository=opinion_repo,
        reflection_run_repository=reflection_repo,
        knowledge_repository=knowledge_repo,
        strategy_repository=strategy_repo,
        agent_report_repository=agent_report_repo,
        sidecar_backends=list(sidecar_backends or []),
    )
    reflection = MemoryReflectionService(
        derived_index_service=derived,
        entity_view_repository=entity_repo,
        opinion_view_repository=opinion_repo,
        reflection_run_repository=reflection_repo,
    )
    knowledge = StateKnowledgeService(
        repository=knowledge_repo,
        derived_index_service=derived,
        reflection_service=reflection,
    )
    strategy = StateStrategyMemoryService(
        repository=strategy_repo,
        derived_index_service=derived,
        reflection_service=reflection,
    )
    retain = MemoryRetainService(
        knowledge_service=knowledge,
        derived_index_service=derived,
        reflection_service=reflection,
    )
    recall = MemoryRecallService(
        derived_index_service=derived,
        sidecar_backends=list(sidecar_backends or []),
    )
    return store, knowledge, strategy, retain, recall, reflection, derived


def test_memory_vnext_rebuild_recall_and_reflect(tmp_path) -> None:
    _store, knowledge, strategy, _retain, recall, reflection, derived = _build_memory_services(tmp_path)

    knowledge.remember_fact(
        title="Outbound policy",
        content="The team should only send outbound messages after evidence review.",
        scope_type="industry",
        scope_id="industry-1",
        role_bindings=["execution-core"],
        tags=["policy", "outbound"],
    )
    strategy.upsert_strategy(
        StrategyMemoryRecord(
            strategy_id="strategy:industry:industry-1:copaw-agent-runner",
            scope_type="industry",
            scope_id="industry-1",
            owner_agent_id="copaw-agent-runner",
            industry_instance_id="industry-1",
            title="Industry memory strategy",
            summary="Operate with evidence-first outbound discipline.",
            north_star="Protect quality before throughput.",
            evidence_requirements=["Evidence review before outbound action"],
        ),
    )

    rebuild = derived.rebuild_all(
        scope_type="industry",
        scope_id="industry-1",
        include_reporting=False,
        include_learning=False,
        evidence_limit=0,
    )
    assert rebuild.fact_index_count >= 2
    assert rebuild.source_counts["knowledge_chunk"] >= 1
    assert rebuild.source_counts["strategy_memory"] >= 1

    reflected = reflection.reflect(
        scope_type="industry",
        scope_id="industry-1",
        trigger_kind="test",
        create_learning_proposals=False,
    )
    assert reflected.entity_count >= 1
    assert reflected.opinion_count >= 1

    recalled = recall.recall(
        query="evidence review before outbound",
        scope_type="industry",
        scope_id="industry-1",
        role="execution-core",
        limit=5,
    )
    assert recalled.backend_used == "hybrid-local"
    assert recalled.hits
    assert any(hit.source_type == "knowledge_chunk" for hit in recalled.hits)

    entities = derived.list_entity_views(scope_type="industry", scope_id="industry-1")
    opinions = derived.list_opinion_views(scope_type="industry", scope_id="industry-1")
    assert entities
    assert opinions


def test_memory_retain_service_turns_agent_report_into_canonical_memory(tmp_path) -> None:
    _store, knowledge, _strategy, retain, _recall, _reflection, derived = _build_memory_services(tmp_path)

    report = AgentReportRecord(
        id="report-1",
        industry_instance_id="industry-1",
        owner_agent_id="worker-1",
        owner_role_id="researcher",
        headline="Weekly review completed",
        summary="Weekly review recommends holding outbound until evidence is updated.",
        status="recorded",
        result="completed",
        evidence_ids=["evidence-1"],
    )
    retain.retain_agent_report(report)

    memory_records = knowledge.list_memory(
        industry_instance_id="industry-1",
        query="holding outbound until evidence is updated",
        limit=10,
    )
    assert any(item.title == "Weekly review completed" for item in memory_records)

    fact_entries = derived.list_fact_entries(
        source_type="agent_report",
        source_ref="report-1",
        limit=None,
    )
    assert len(fact_entries) == 1
    assert fact_entries[0].industry_instance_id == "industry-1"


def test_qmd_sidecar_materializes_derived_entries_and_reports_metadata(tmp_path) -> None:
    runner = _FakeQmdRunner()
    qmd_backend = _build_qmd_backend(tmp_path, runner)
    _store, knowledge, _strategy, _retain, recall, _reflection, derived = _build_memory_services(
        tmp_path,
        sidecar_backends=[qmd_backend],
    )

    knowledge.remember_fact(
        title="Outbound policy",
        content="The team should only send outbound messages after evidence review.",
        scope_type="industry",
        scope_id="industry-1",
        role_bindings=["execution-core"],
        tags=["policy", "outbound"],
    )

    manifest_payload = json.loads((tmp_path / "qmd-sidecar" / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest_payload["entries"]) >= 1
    assert derived.list_fact_entries(limit=None)
    backends = {item.backend_id: item for item in recall.list_backends()}
    assert "qmd" in backends
    assert backends["qmd"].available is True
    assert "Qwen3-Embedding-0.6B" in backends["qmd"].metadata["embed_model"]


def test_qmd_backend_defaults_to_full_query_mode(tmp_path) -> None:
    runner = _FakeQmdRunner()
    qmd_backend = _build_qmd_backend(tmp_path, runner)

    assert qmd_backend.descriptor().metadata["query_mode"] == "query"
    assert qmd_backend.descriptor().metadata["online_skip_rerank"] is True


def test_qmd_descriptor_marks_stale_runtime_state_not_ready(tmp_path) -> None:
    runner = _FakeQmdRunner()
    qmd_backend = _build_qmd_backend(tmp_path, runner)
    _store, knowledge, _strategy, _retain, recall, _reflection, _derived = _build_memory_services(
        tmp_path,
        sidecar_backends=[qmd_backend],
    )

    knowledge.remember_fact(
        title="Outbound policy",
        content="The team should only send outbound messages after evidence review.",
        scope_type="industry",
        scope_id="industry-1",
        role_bindings=["execution-core"],
        tags=["policy", "outbound"],
    )
    qmd_backend._dirty = False  # pylint: disable=protected-access
    qmd_backend._bootstrapped = True  # pylint: disable=protected-access
    qmd_backend._last_error = None  # pylint: disable=protected-access
    qmd_backend._manifest["dirty"] = False  # pylint: disable=protected-access
    qmd_backend._manifest["bootstrapped"] = True  # pylint: disable=protected-access
    qmd_backend._persist_manifest()  # pylint: disable=protected-access
    runner.collection_show_payloads = [
        "Collection: copaw-memory\n  Path:     C:\\stale\\corpus\n  Pattern:  **/*.md\n",
    ]
    runner.status_payloads = [
        _FakeQmdRunner.render_status(
            documents_total=0,
            embedded_vectors=0,
            pending_embeddings=1,
        ),
    ]

    descriptor = next(item for item in recall.list_backends() if item.backend_id == "qmd")

    assert descriptor.metadata["ready"] is False
    assert descriptor.metadata["collection_path_matches"] is False
    assert descriptor.metadata["indexed_documents"] == 0
    assert "does not match corpus_dir" in str(descriptor.reason or "")


def test_qmd_warmup_rebuilds_when_runtime_state_is_stale(tmp_path) -> None:
    runner = _FakeQmdRunner()
    qmd_backend = _build_qmd_backend(tmp_path, runner)
    _store, knowledge, _strategy, _retain, _recall, _reflection, _derived = _build_memory_services(
        tmp_path,
        sidecar_backends=[qmd_backend],
    )

    knowledge.remember_fact(
        title="Outbound policy",
        content="The team should only send outbound messages after evidence review.",
        scope_type="industry",
        scope_id="industry-1",
        role_bindings=["execution-core"],
        tags=["policy", "outbound"],
    )
    qmd_backend._dirty = False  # pylint: disable=protected-access
    qmd_backend._bootstrapped = True  # pylint: disable=protected-access
    qmd_backend._last_error = None  # pylint: disable=protected-access
    qmd_backend._manifest["dirty"] = False  # pylint: disable=protected-access
    qmd_backend._manifest["bootstrapped"] = True  # pylint: disable=protected-access
    qmd_backend._persist_manifest()  # pylint: disable=protected-access
    runner.collection_show_payloads = [
        "Collection: copaw-memory\n  Path:     C:\\stale\\corpus\n  Pattern:  **/*.md\n",
        "Collection: copaw-memory\n  Path:     C:\\stale\\corpus\n  Pattern:  **/*.md\n",
    ]
    runner.status_payloads = [
        _FakeQmdRunner.render_status(
            documents_total=0,
            embedded_vectors=0,
            pending_embeddings=1,
        ),
    ]

    qmd_backend.warmup()

    commands = [call["args"] for call in runner.calls]
    assert any("remove" in args for args in commands)
    assert any("update" in args for args in commands)
    assert any("embed" in args for args in commands)
    descriptor = qmd_backend.descriptor()
    assert descriptor.metadata["ready"] is True
    assert descriptor.metadata["collection_path_matches"] is True


def test_qmd_warmup_starts_best_effort_daemon_when_enabled(tmp_path) -> None:
    runner = _FakeQmdRunner()
    popen_factory = _FakePopenFactory()
    json_requester = _FakeJsonRequester(
        [
            RuntimeError("not ready"),
            {
                "status": "ok",
                "service": "copaw-qmd-bridge",
            },
            {"ok": True},
        ],
    )
    base_dir = tmp_path / "qmd-sidecar"
    qmd_js, node_exe = _prepare_fake_qmd_sdk(tmp_path)
    qmd_backend = QmdRecallBackend(
        config=QmdBackendConfig(
            enabled=True,
            install_mode="path",
            binary_name=str(qmd_js.resolve()),
            base_dir=base_dir,
            corpus_dir=base_dir / "corpus",
            manifest_path=base_dir / "manifest.json",
            xdg_cache_home=base_dir / "xdg-cache",
            daemon_enabled=True,
            daemon_port=8777,
        ),
        runner=runner,
        which=lambda name: str(node_exe.resolve()) if name == "node" else None,
        popen_factory=popen_factory,
        json_requester=json_requester,
        sleeper=lambda _seconds: None,
    )
    _store, knowledge, _strategy, _retain, _recall, _reflection, _derived = _build_memory_services(
        tmp_path,
        sidecar_backends=[qmd_backend],
    )

    knowledge.remember_fact(
        title="Outbound policy",
        content="The team should only send outbound messages after evidence review.",
        scope_type="industry",
        scope_id="industry-1",
        role_bindings=["execution-core"],
        tags=["policy", "outbound"],
    )

    qmd_backend.warmup()

    assert popen_factory.calls
    daemon_call = popen_factory.calls[0]["args"]
    assert str(node_exe.resolve()) == daemon_call[0]
    assert daemon_call[1].endswith("qmd_bridge_server.mjs")
    descriptor = qmd_backend.descriptor()
    assert descriptor.metadata["daemon_state"] == "running"
    assert descriptor.metadata["daemon_owned"] is True
    assert descriptor.metadata["daemon_url"] == "http://127.0.0.1:8777"
    assert descriptor.metadata["daemon_impl"] == "copaw-qmd-bridge"
    daemon_env = popen_factory.calls[0]["kwargs"]["env"]
    assert daemon_env["COPAW_QMD_BRIDGE_SDK_INDEX_ENTRY"].startswith("file:///")
    assert daemon_env["COPAW_QMD_BRIDGE_SDK_STORE_ENTRY"].startswith("file:///")
    prewarm_call = next(
        call for call in json_requester.calls if call["url"].endswith("/prewarm")
    )
    assert prewarm_call["payload"]["skipRerank"] is True


def test_qmd_backend_close_stops_owned_daemon(tmp_path) -> None:
    runner = _FakeQmdRunner()
    popen_factory = _FakePopenFactory()
    json_requester = _FakeJsonRequester(
        [
            RuntimeError("not ready"),
            {
                "status": "ok",
                "service": "copaw-qmd-bridge",
            },
            {"ok": True},
        ],
    )
    base_dir = tmp_path / "qmd-sidecar"
    qmd_js, node_exe = _prepare_fake_qmd_sdk(tmp_path)
    qmd_backend = QmdRecallBackend(
        config=QmdBackendConfig(
            enabled=True,
            install_mode="path",
            binary_name=str(qmd_js.resolve()),
            base_dir=base_dir,
            corpus_dir=base_dir / "corpus",
            manifest_path=base_dir / "manifest.json",
            xdg_cache_home=base_dir / "xdg-cache",
            daemon_enabled=True,
            daemon_port=8778,
        ),
        runner=runner,
        which=lambda name: str(node_exe.resolve()) if name == "node" else None,
        popen_factory=popen_factory,
        json_requester=json_requester,
        sleeper=lambda _seconds: None,
    )
    _store, knowledge, _strategy, _retain, _recall, _reflection, _derived = _build_memory_services(
        tmp_path,
        sidecar_backends=[qmd_backend],
    )

    knowledge.remember_fact(
        title="Outbound policy",
        content="The team should only send outbound messages after evidence review.",
        scope_type="industry",
        scope_id="industry-1",
        role_bindings=["execution-core"],
        tags=["policy", "outbound"],
    )
    qmd_backend.warmup()

    process = popen_factory.processes[0]
    qmd_backend.close()

    assert process.terminated is True
    assert qmd_backend.descriptor().metadata["daemon_state"] == "stopped"


def test_qmd_backend_recall_prefers_bridge_results_when_available(tmp_path) -> None:
    runner = _FakeQmdRunner()
    json_requester = _FakeJsonRequester(
        [
            {
                "status": "ok",
                "service": "copaw-qmd-bridge",
            },
            {
                "results": [
                    {
                        "filepath": "entries/industry/industry-1/knowledge-chunk/example.md",
                        "score": 0.91,
                        "snippet": "evidence review before outbound action",
                    },
                ],
            },
        ],
    )
    qmd_backend = _build_qmd_backend(tmp_path, runner)
    qmd_backend = QmdRecallBackend(
        config=QmdBackendConfig(
            enabled=True,
            install_mode="path",
            binary_name="qmd",
            base_dir=tmp_path / "qmd-sidecar",
            corpus_dir=tmp_path / "qmd-sidecar" / "corpus",
            manifest_path=tmp_path / "qmd-sidecar" / "manifest.json",
            xdg_cache_home=tmp_path / "qmd-sidecar" / "xdg-cache",
            daemon_enabled=True,
        ),
        runner=runner,
        which=lambda _name: "qmd",
        json_requester=json_requester,
    )
    _store, knowledge, _strategy, _retain, recall, _reflection, _derived = _build_memory_services(
        tmp_path,
        sidecar_backends=[qmd_backend],
    )

    knowledge.remember_fact(
        title="Outbound policy",
        content="The team should only send outbound messages after evidence review.",
        scope_type="industry",
        scope_id="industry-1",
        role_bindings=["execution-core"],
        tags=["policy", "outbound"],
    )
    manifest_payload = json.loads((tmp_path / "qmd-sidecar" / "manifest.json").read_text(encoding="utf-8"))
    relative_path = next(iter(manifest_payload["entries"]))
    json_requester.calls.clear()
    json_requester._responses = [  # pylint: disable=protected-access
        {
            "status": "ok",
            "service": "copaw-qmd-bridge",
        },
        {
            "results": [
                {
                    "filepath": relative_path,
                    "score": 0.91,
                    "snippet": "evidence review before outbound action",
                },
            ],
        },
    ]

    recalled = recall.recall(
        query="evidence review before outbound action",
        backend="qmd",
        scope_type="industry",
        scope_id="industry-1",
        role="execution-core",
        limit=5,
    )

    assert recalled.backend_used == "qmd"
    assert recalled.hits
    assert not any("query" in call["args"] for call in runner.calls if isinstance(call, dict))
    bridge_call = next(
        call for call in json_requester.calls if call["url"].endswith("/query")
    )
    assert bridge_call["payload"]["skipRerank"] is True


def test_memory_recall_service_closes_sidecar_backends() -> None:
    calls: list[str] = []

    class _ClosableBackend:
        backend_id = "qmd"
        label = "QMD Sidecar"

        def close(self) -> None:
            calls.append("closed")

    service = MemoryRecallService(
        derived_index_service=object(),
        sidecar_backends=[_ClosableBackend()],
    )

    service.close_sidecar_backends()

    assert calls == ["closed"]


def test_qmd_backend_recall_returns_hits_with_canonical_refs(tmp_path) -> None:
    runner = _FakeQmdRunner()
    qmd_backend = _build_qmd_backend(tmp_path, runner)
    _store, knowledge, _strategy, _retain, recall, _reflection, _derived = _build_memory_services(
        tmp_path,
        sidecar_backends=[qmd_backend],
    )

    knowledge.remember_fact(
        title="Outbound policy",
        content="The team should only send outbound messages after evidence review.",
        scope_type="industry",
        scope_id="industry-1",
        role_bindings=["execution-core"],
        tags=["policy", "outbound"],
    )
    manifest_payload = json.loads((tmp_path / "qmd-sidecar" / "manifest.json").read_text(encoding="utf-8"))
    relative_path = next(iter(manifest_payload["entries"]))
    runner.query_payload = json.dumps(
        [
            {
                "filepath": relative_path,
                "score": 0.91,
                "snippet": "evidence review before outbound action",
            },
        ],
    )

    recalled = recall.recall(
        query="evidence review before outbound action",
        backend="qmd",
        scope_type="industry",
        scope_id="industry-1",
        role="execution-core",
        limit=5,
    )
    assert recalled.backend_used == "qmd"
    assert recalled.hits
    assert recalled.hits[0].source_type == "knowledge_chunk"
    assert recalled.hits[0].source_ref
    assert recalled.hits[0].metadata["qmd"]["filepath"] == relative_path
    embed_calls = [call for call in runner.calls if "embed" in call["args"]]
    query_mode = qmd_backend.descriptor().metadata["query_mode"]
    if query_mode in {"query", "vsearch"}:
        assert embed_calls
        assert "Qwen3-Embedding-0.6B" in embed_calls[0]["env"]["QMD_EMBED_MODEL"]
    else:
        assert not embed_calls


def test_memory_recall_falls_back_to_hybrid_local_when_qmd_fails(tmp_path) -> None:
    runner = _FakeQmdRunner()
    runner.fail_query = True
    qmd_backend = _build_qmd_backend(tmp_path, runner)
    _store, knowledge, _strategy, _retain, recall, _reflection, _derived = _build_memory_services(
        tmp_path,
        sidecar_backends=[qmd_backend],
    )

    knowledge.remember_fact(
        title="Outbound policy",
        content="The team should only send outbound messages after evidence review.",
        scope_type="industry",
        scope_id="industry-1",
        role_bindings=["execution-core"],
        tags=["policy", "outbound"],
    )

    recalled = recall.recall(
        query="evidence review before outbound action",
        backend="qmd",
        scope_type="industry",
        scope_id="industry-1",
        role="execution-core",
        limit=5,
    )
    assert recalled.backend_used == "hybrid-local"
    assert recalled.fallback_reason is not None
    assert "failed" in recalled.fallback_reason.lower()
    assert recalled.hits


def test_memory_recall_falls_back_to_hybrid_local_when_qmd_returns_no_hits(
    tmp_path,
) -> None:
    runner = _FakeQmdRunner()
    qmd_backend = _build_qmd_backend(tmp_path, runner)
    _store, knowledge, _strategy, _retain, recall, _reflection, _derived = _build_memory_services(
        tmp_path,
        sidecar_backends=[qmd_backend],
    )

    knowledge.remember_fact(
        title="Outbound policy",
        content="The team should only send outbound messages after evidence review.",
        scope_type="industry",
        scope_id="industry-1",
        role_bindings=["execution-core"],
        tags=["policy", "outbound"],
    )

    recalled = recall.recall(
        query="evidence review before outbound action",
        backend="qmd",
        scope_type="industry",
        scope_id="industry-1",
        role="execution-core",
        limit=5,
    )
    assert recalled.backend_used == "hybrid-local"
    assert recalled.fallback_reason is not None
    assert "no hits" in recalled.fallback_reason.lower()
    assert recalled.hits


def test_qmd_backend_prefers_windows_node_dist_cli_when_wrapper_is_broken(
    tmp_path,
) -> None:
    if os.name != "nt":
        pytest.skip("Windows-specific QMD command resolution")
    prefix = tmp_path / "node-global"
    cli_dir = prefix / "node_modules" / "@tobilu" / "qmd" / "dist" / "cli"
    cli_dir.mkdir(parents=True)
    qmd_js = cli_dir / "qmd.js"
    qmd_js.write_text("// qmd cli stub\n", encoding="utf-8")
    qmd_cmd = prefix / "qmd.cmd"
    qmd_cmd.write_text("@echo off\n", encoding="utf-8")
    node_exe = tmp_path / "node.exe"
    node_exe.write_text("", encoding="utf-8")

    backend = QmdRecallBackend(
        config=QmdBackendConfig(
            enabled=True,
            install_mode="path",
            binary_name="qmd",
            base_dir=tmp_path / "qmd-sidecar",
            corpus_dir=tmp_path / "qmd-sidecar" / "corpus",
            manifest_path=tmp_path / "qmd-sidecar" / "manifest.json",
            xdg_cache_home=tmp_path / "qmd-sidecar" / "xdg-cache",
        ),
        runner=_FakeQmdRunner(),
        which=lambda name: (
            str(qmd_cmd.resolve())
            if name == "qmd"
            else str(node_exe.resolve())
            if name == "node"
            else None
        ),
    )

    descriptor = backend.descriptor()
    assert descriptor.available is True
    assert descriptor.metadata["command_mode"] == "node-dist-cli"
    assert descriptor.metadata["command"] == [
        str(node_exe.resolve()),
        str(qmd_js.resolve()),
    ]
