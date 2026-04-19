# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from uuid import uuid4

from agentscope.message import Msg
from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.agents.tools.browser_control import list_browser_downloads, run_browser_use_json
from copaw.app.crons.executor import CronExecutor
from copaw.app.crons.models import CronJobSpec
from copaw.app.routers.runtime_center import router as runtime_center_router
from copaw.app.runtime_bootstrap_domains import SourceCollectionFrontdoorService
from copaw.kernel.main_brain_chat_service import MainBrainChatService
from copaw.research import BaiduPageResearchService
from copaw.state import SQLiteStateStore
from copaw.state.repositories import SqliteResearchSessionRepository


class _FakeSessionBackend:
    def __init__(self) -> None:
        self.snapshots: dict[tuple[str, str], dict] = {}

    def load_session_snapshot(
        self,
        *,
        session_id: str,
        user_id: str,
        allow_not_exist: bool = False,
    ) -> dict:
        _ = allow_not_exist
        return dict(self.snapshots.get((session_id, user_id), {}))

    def save_session_snapshot(
        self,
        *,
        session_id: str,
        user_id: str,
        payload: dict,
        source_ref: str,
    ) -> None:
        _ = source_ref
        self.snapshots[(session_id, user_id)] = dict(payload)


class _ExplodingModel:
    stream = True

    async def __call__(self, *, messages, **kwargs):
        _ = (messages, kwargs)
        raise AssertionError("model should not be called for research trigger")


class _IndustryService:
    def __init__(self, researcher_agent_id: str) -> None:
        self._researcher_agent_id = researcher_agent_id

    def get_instance_detail(self, instance_id: str):
        _ = instance_id
        return {
            "staffing": {
                "researcher": {
                    "agent_id": self._researcher_agent_id,
                    "role_name": "Researcher",
                }
            }
        }


async def _run_main_brain_chat(service, request, text: str) -> str:
    events = [
        item
        async for item in service.execute_stream(
            msgs=[Msg(name="user", role="user", content=text)],
            request=request,
        )
    ]
    return events[-1][0].get_text_content()


def _build_runtime_client(repository: SqliteResearchSessionRepository) -> TestClient:
    app = FastAPI()
    app.state.research_session_repository = repository
    app.include_router(runtime_center_router)
    return TestClient(app)


def _normalize_runtime_payload(payload: dict[str, object]) -> dict[str, object]:
    return {
        "brief": payload.get("brief"),
        "writeback_truth": payload.get("writeback_truth"),
        "findings_count": len(payload.get("findings") or []),
        "sources_count": len(payload.get("sources") or []),
        "gaps": payload.get("gaps"),
        "conflicts": payload.get("conflicts"),
    }


def _latest_session(repository: SqliteResearchSessionRepository):
    sessions = list(repository.list_research_sessions())
    return max(sessions, key=lambda item: str(item.updated_at or item.created_at))


def _stop_all_browser_sessions(repository: SqliteResearchSessionRepository) -> None:
    for session in repository.list_research_sessions():
        session_id = str(getattr(session, "browser_session_id", None) or session.id)
        try:
            run_browser_use_json(action="stop", session_id=session_id)
        except Exception:
            pass


def run_acceptance(*, cron_owner: str) -> dict[str, object]:
    with TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        tmp_path = Path(tmp)
        repository = SqliteResearchSessionRepository(SQLiteStateStore(tmp_path / "state.sqlite3"))
        heavy = BaiduPageResearchService(
            research_session_repository=repository,
            browser_action_runner=run_browser_use_json,
            browser_download_resolver=list_browser_downloads,
        )
        frontdoor = SourceCollectionFrontdoorService(
            heavy_research_service=heavy,
            research_session_repository=repository,
        )
        client = _build_runtime_client(repository)

        clean_owner = f"longchain-clean-{uuid4().hex[:8]}"
        probe_session = heavy.start_session(
            goal="probe",
            trigger_source="probe",
            owner_agent_id=clean_owner,
        ).session
        storage_path = Path(heavy._default_storage_state_path(probe_session))
        if storage_path.exists():
            storage_path.unlink()

        main_brain = MainBrainChatService(
            session_backend=_FakeSessionBackend(),
            industry_service=_IndustryService(clean_owner),
            research_session_service=frontdoor,
            model_factory=lambda: _ExplodingModel(),
        )
        main_request = SimpleNamespace(
            session_id="main-brain-live-1",
            user_id="user-live-1",
            industry_instance_id="industry-v1-demo",
            industry_role_id="execution-core",
            agent_id="copaw-agent-runner",
            channel="console",
            work_context_id="ctx-main-live-1",
            _copaw_research_brief={
                "goal": "补齐紫微斗数基础知识和可信来源",
                "question": "继续补齐紫微斗数基础知识和可信来源，并标注最值得先看的资料",
                "trigger_source": "main-brain-followup",
                "why_needed": "主脑要判断后续是否要继续扩展研究",
                "done_when": "至少拿到基础概念、一个可信来源和一个常见误解",
                "requested_sources": ["search", "web_page"],
                "collection_mode_hint": "heavy",
                "writeback_target": {
                    "scope_type": "work_context",
                    "scope_id": "ctx-main-live-1",
                },
            },
        )
        main_reply = asyncio.run(_run_main_brain_chat(main_brain, main_request, "继续"))
        latest_main = _latest_session(repository)
        main_runtime_payload = client.get("/runtime-center/research").json()

        cron_executor = CronExecutor(
            kernel_dispatcher=SimpleNamespace(
                submit=lambda task: SimpleNamespace(phase="executing", task_id=task.id),
                execute_task=lambda task_id: None,
            ),
            research_session_service=frontdoor,
        )
        cron_job = CronJobSpec.model_validate(
            {
                "id": "cron-live-heavy-1",
                "name": "Live heavy monitoring",
                "enabled": True,
                "schedule": {
                    "type": "cron",
                    "cron": "0 9 * * 1",
                    "timezone": "UTC",
                },
                "task_type": "agent",
                "request": {
                    "input": [
                        {
                            "role": "user",
                            "content": [{"type": "text", "text": "run monitoring brief"}],
                        }
                    ],
                    "industry_instance_id": "industry-v1-demo",
                    "work_context_id": "ctx-monitoring-live-1",
                },
                "dispatch": {
                    "type": "channel",
                    "channel": "console",
                    "target": {
                        "user_id": "workflow",
                        "session_id": "monitoring-live-1",
                    },
                    "mode": "final",
                    "meta": {"summary": "monitoring live follow-up"},
                },
                "runtime": {
                    "max_concurrency": 1,
                    "timeout_seconds": 60,
                    "misfire_grace_seconds": 30,
                },
                "meta": {
                    "research_provider": "baidu-page",
                    "research_mode": "monitoring-brief",
                    "research_goal": "每天早上整理持仓股票相关新闻和监管变化",
                    "research_question": "每天早上整理持仓股票相关新闻、监管变化和官网公告",
                    "research_why_needed": "主脑要判断是否需要发起新的 follow-up assignment",
                    "research_done_when": "至少形成 3 条可疑变化并标注来源",
                    "requested_sources": ["search", "web_page"],
                    "collection_mode_hint": "heavy",
                    "owner_agent_id": cron_owner,
                    "industry_instance_id": "industry-v1-demo",
                    "work_context_id": "ctx-monitoring-live-1",
                    "supervisor_agent_id": "copaw-agent-runner",
                },
            }
        )
        asyncio.run(cron_executor.execute(cron_job))
        latest_cron = _latest_session(repository)
        cron_runtime_payload = client.get("/runtime-center/research").json()

        payload = {
            "main_brain": {
                "reply": main_reply,
                "session_id": latest_main.id,
                "status": latest_main.status,
                "trigger_source": latest_main.trigger_source,
                "owner_agent_id": latest_main.owner_agent_id,
                "brief": latest_main.brief,
                "runtime": _normalize_runtime_payload(main_runtime_payload),
            },
            "cron": {
                "session_id": latest_cron.id,
                "status": latest_cron.status,
                "trigger_source": latest_cron.trigger_source,
                "owner_agent_id": latest_cron.owner_agent_id,
                "brief": latest_cron.brief,
                "runtime": _normalize_runtime_payload(cron_runtime_payload),
            },
        }
        _stop_all_browser_sessions(repository)
        return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run live external information chain acceptance in UTF-8-safe mode.",
    )
    parser.add_argument(
        "--output",
        default="tmp/live_external_information_chain_acceptance_result.json",
        help="UTF-8 result file path.",
    )
    parser.add_argument(
        "--cron-owner",
        default="industry-researcher-live-smoke",
        help="Researcher owner used for the cron monitoring phase.",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = run_acceptance(cron_owner=args.cron_owner)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(str(output_path.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
