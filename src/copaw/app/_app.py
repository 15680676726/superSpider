# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name,unused-argument
import mimetypes
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .agent_runtime import create_agent_runtime_app
from .runtime_host import RuntimeHost
from .runtime_recovery_report import build_latest_recovery_report
from ..config import (  # pylint: disable=no-name-in-module
    load_config,
)
from ..constant import DOCS_ENABLED, LOG_LEVEL_ENV, CORS_ORIGINS, WORKING_DIR
from ..__version__ import __version__
from ..utils.logging import setup_logger, add_copaw_file_handler
from .runtime_lifecycle import (
    RuntimeRestartCoordinator,
    start_automation_tasks,
    stop_automation_tasks,
)
from .startup_recovery import run_startup_recovery
from .runtime_bootstrap import (
    attach_runtime_state,
    build_runtime_bootstrap,
    initialize_mcp_manager,
    runtime_manager_stack_from_app_state,
    start_runtime_manager_stack,
    stop_runtime_manager_stack,
)
from .startup_environment_preflight import (
    assert_startup_environment_ready,
    resolve_environment_preflight_paths,
)
from .routers import router as api_router
from .routers.voice import voice_router
from ..envs import load_envs_into_environ

# Apply log level on load so reload child process gets same level as CLI.
logger = setup_logger(os.environ.get(LOG_LEVEL_ENV, "info"))

# Ensure static assets are served with browser-compatible MIME types across
# platforms (notably Windows may miss .js/.mjs mappings).
mimetypes.init()
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".mjs")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/wasm", ".wasm")

# Load persisted env vars into os.environ at module import time
# so they are available before the lifespan starts.
load_envs_into_environ()

runtime_host = RuntimeHost()


agent_runtime_app = create_agent_runtime_app()

@asynccontextmanager
async def lifespan(
    app: FastAPI,
):  # pylint: disable=too-many-statements,too-many-branches
    startup_environment_preflight = assert_startup_environment_ready(
        **resolve_environment_preflight_paths(working_dir=WORKING_DIR),
    )
    app.state.startup_environment_preflight = startup_environment_preflight
    add_copaw_file_handler(WORKING_DIR / "copaw.log")
    await runtime_host.start()
    session_backend = runtime_host.session_backend
    conversation_compaction_service = runtime_host.conversation_compaction_service
    config = load_config()
    mcp_manager = await initialize_mcp_manager(
        config=config,
        logger=logger,
        strict=False,
    )
    bootstrap = build_runtime_bootstrap(
        session_backend=session_backend,
        conversation_compaction_service=conversation_compaction_service,
        mcp_manager=mcp_manager,
    )
    runtime_host.sync_turn_executor(bootstrap.turn_executor)
    resolve_exception_absorption_service = getattr(
        bootstrap.actor_supervisor,
        "exception_absorption_service",
        None,
    )

    startup_recovery_summary = run_startup_recovery(
        environment_service=bootstrap.environment_service,
        actor_mailbox_service=bootstrap.actor_mailbox_service,
        decision_request_repository=bootstrap.repositories.decision_request_repository,
        kernel_dispatcher=bootstrap.kernel_dispatcher,
        kernel_task_store=bootstrap.kernel_task_store,
        schedule_repository=bootstrap.repositories.schedule_repository,
        runtime_repository=bootstrap.repositories.agent_runtime_repository,
        exception_absorption_service=(
            resolve_exception_absorption_service()
            if callable(resolve_exception_absorption_service)
            else None
        ),
        human_assist_task_service=bootstrap.human_assist_task_service,
        backlog_item_repository=bootstrap.repositories.backlog_item_repository,
        assignment_repository=bootstrap.repositories.assignment_repository,
        goal_repository=bootstrap.repositories.goal_repository,
        goal_override_repository=bootstrap.repositories.goal_override_repository,
        task_repository=bootstrap.repositories.task_repository,
        task_runtime_repository=bootstrap.repositories.task_runtime_repository,
        runtime_event_bus=bootstrap.runtime_event_bus,
        reason="startup",
    )
    manager_stack = await start_runtime_manager_stack(
        config=config,
        kernel_dispatcher=bootstrap.kernel_dispatcher,
        capability_service=bootstrap.capability_service,
        governance_service=bootstrap.governance_service,
        schedule_repository=bootstrap.repositories.bootstrap_schedule_repository,
        mcp_manager=mcp_manager,
        memory_sleep_service=bootstrap.memory_sleep_service,
        logger=logger,
        strict_mcp_watcher=False,
    )
    bootstrap.industry_service.set_schedule_runtime(
        schedule_writer=manager_stack.job_repository,
        cron_manager=manager_stack.cron_manager,
    )
    bootstrap.workflow_template_service.set_schedule_runtime(
        schedule_writer=manager_stack.job_repository,
        cron_manager=manager_stack.cron_manager,
    )
    attach_runtime_state(
        app,
        runtime_host=runtime_host,
        bootstrap=bootstrap,
        manager_stack=manager_stack,
        startup_recovery_summary=startup_recovery_summary,
    )

    actor_supervisor = bootstrap.actor_supervisor
    turn_executor = bootstrap.turn_executor

    await actor_supervisor.start()
    automation_tasks = start_automation_tasks(
        kernel_dispatcher=bootstrap.kernel_dispatcher,
        capability_service=bootstrap.capability_service,
        environment_service=bootstrap.environment_service,
        industry_service=bootstrap.industry_service,
        learning_service=bootstrap.learning_service,
        automation_loop_runtime_repository=(
            bootstrap.repositories.automation_loop_runtime_repository
        ),
        logger=logger,
    )
    app.state.automation_tasks = automation_tasks
    app.state.latest_recovery_report = build_latest_recovery_report(
        startup_recovery_summary=app.state.startup_recovery_summary,
        automation_tasks=automation_tasks,
        automation_loop_runtime_repository=(
            bootstrap.repositories.automation_loop_runtime_repository
        ),
    )
    set_latest_recovery_report_sink = getattr(
        bootstrap.environment_service,
        "set_latest_recovery_report_sink",
        None,
    )
    if callable(set_latest_recovery_report_sink):
        set_latest_recovery_report_sink(
            lambda payload: setattr(app.state, "latest_recovery_report", payload),
        )
    set_latest_recovery_report = getattr(
        bootstrap.environment_service,
        "set_latest_recovery_report",
        None,
    )
    if callable(set_latest_recovery_report):
        set_latest_recovery_report(app.state.latest_recovery_report)
    restart_coordinator = RuntimeRestartCoordinator(
        app=app,
        agent_runtime_app=agent_runtime_app,
        bootstrap=bootstrap,
        runtime_host=runtime_host,
        logger=logger,
    )
    runtime_host.set_restart_callback(restart_coordinator.restart_services)
    runtime_host.sync_turn_executor(turn_executor)

    try:
        yield
    finally:
        await stop_automation_tasks(
            list(getattr(app.state, "automation_tasks", []) or []),
        )
        evidence_ledger = getattr(app.state, "evidence_ledger", None)
        actor_supervisor = getattr(app.state, "actor_supervisor", None)
        memory_recall_service = getattr(app.state, "memory_recall_service", None)
        await stop_runtime_manager_stack(
            runtime_manager_stack_from_app_state(app.state),
            logger=logger,
            error_mode="ignore",
            context="shutdown",
        )
        if actor_supervisor is not None:
            try:
                await actor_supervisor.stop()
            except Exception:
                pass
        if memory_recall_service is not None:
            close_sidecars = getattr(
                memory_recall_service,
                "close_sidecar_backends",
                None,
            )
            if callable(close_sidecars):
                try:
                    close_sidecars()
                except Exception:
                    pass
        if evidence_ledger is not None:
            try:
                evidence_ledger.close()
            except Exception:
                pass
        await runtime_host.stop()
        runtime_event_bus = getattr(app.state, "runtime_event_bus", None)
        close_runtime_event_bus = getattr(runtime_event_bus, "close", None)
        if callable(close_runtime_event_bus):
            try:
                await close_runtime_event_bus()
            except Exception:
                pass


app = FastAPI(
    lifespan=lifespan,
    docs_url="/docs" if DOCS_ENABLED else None,
    redoc_url="/redoc" if DOCS_ENABLED else None,
    openapi_url="/openapi.json" if DOCS_ENABLED else None,
)
agent_runtime_app.state.parent_app = app
app.state.agent_runtime_app = agent_runtime_app

# Apply CORS middleware if CORS_ORIGINS is set
if CORS_ORIGINS:
    origins = [o.strip() for o in CORS_ORIGINS.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Console static dir: env, or copaw package data (console), or cwd.
_CONSOLE_STATIC_ENV = "COPAW_CONSOLE_STATIC_DIR"


def _candidate_console_static_dirs() -> list[Path]:
    candidates: list[Path] = []
    seen: set[str] = set()

    def _add(path: Path) -> None:
        normalized = str(path.resolve())
        if normalized in seen:
            return
        seen.add(normalized)
        candidates.append(path)

    pkg_dir = Path(__file__).resolve().parent.parent
    _add(pkg_dir / "console")

    app_file = Path(__file__).resolve()
    for parent in app_file.parents:
        _add(parent / "console" / "dist")
        _add(parent / "console_dist")

    cwd = Path(os.getcwd()).resolve()
    _add(cwd / "console" / "dist")
    _add(cwd / "console_dist")
    return candidates


def _resolve_console_static_dir() -> str:
    if os.environ.get(_CONSOLE_STATIC_ENV):
        return os.environ[_CONSOLE_STATIC_ENV]
    for candidate in _candidate_console_static_dirs():
        if candidate.is_dir() and (candidate / "index.html").exists():
            return str(candidate)
    return str(Path(os.getcwd()).resolve() / "console" / "dist")


_CONSOLE_STATIC_DIR = _resolve_console_static_dir()
_CONSOLE_INDEX = (
    Path(_CONSOLE_STATIC_DIR) / "index.html" if _CONSOLE_STATIC_DIR else None
)
logger.info(f"STATIC_DIR: {_CONSOLE_STATIC_DIR}")


def _console_index_response() -> FileResponse:
    return FileResponse(
        _CONSOLE_INDEX,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/")
def read_root():
    if _CONSOLE_INDEX and _CONSOLE_INDEX.exists():
        return _console_index_response()
    return {
        "message": (
            "Spider Mesh Runtime Center is not available. "
            "If you installed from source, please run "
            "`npm ci && npm run build` in the repository's `console/` "
            "directory, then restart the service."
        ),
    }


@app.get("/api/version")
def get_version():
    """Return the current application version."""
    return {"version": __version__}


app.include_router(api_router, prefix="/api")
app.mount("/api/agent", agent_runtime_app)

# Voice channel: Twilio-facing endpoints at root level (not under /api/).
# POST /voice/incoming, WS /voice/ws, POST /voice/status-callback
app.include_router(voice_router, tags=["voice"])

# Mount console: root static files (logo.png etc.) then assets, then SPA
# fallback.
if os.path.isdir(_CONSOLE_STATIC_DIR):
    _console_path = Path(_CONSOLE_STATIC_DIR)

    @app.get("/logo.png")
    def _console_logo():
        f = _console_path / "logo.png"
        if f.is_file():
            return FileResponse(f, media_type="image/png")

        raise HTTPException(status_code=404, detail="Not Found")

    @app.get("/copaw-symbol.svg")
    def _console_icon():
        preferred = _console_path / "baize-symbol.svg"
        fallback = _console_path / "copaw-symbol.svg"
        f = preferred if preferred.is_file() else fallback
        if f.is_file():
            return FileResponse(f, media_type="image/svg+xml")

        raise HTTPException(status_code=404, detail="Not Found")

    @app.get("/spider-mesh-symbol.svg")
    def _console_spider_mesh_icon():
        preferred = _console_path / "spider-mesh-symbol.svg"
        fallback = _console_path / "baize-symbol.svg"
        fallback2 = _console_path / "copaw-symbol.svg"
        f = preferred if preferred.is_file() else fallback if fallback.is_file() else fallback2
        if f.is_file():
            return FileResponse(f, media_type="image/svg+xml")

        raise HTTPException(status_code=404, detail="Not Found")

    @app.get("/baize-symbol.svg")
    def _console_baize_icon():
        preferred = _console_path / "spider-mesh-symbol.svg"
        fallback = _console_path / "baize-symbol.svg"
        fallback2 = _console_path / "copaw-symbol.svg"
        f = preferred if preferred.is_file() else fallback if fallback.is_file() else fallback2
        if f.is_file():
            return FileResponse(f, media_type="image/svg+xml")

        raise HTTPException(status_code=404, detail="Not Found")

    _assets_dir = _console_path / "assets"
    if _assets_dir.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=str(_assets_dir)),
            name="assets",
        )

    @app.get("/{full_path:path}")
    def _console_spa(full_path: str):
        if _CONSOLE_INDEX and _CONSOLE_INDEX.exists():
            return _console_index_response()

        raise HTTPException(status_code=404, detail="Not Found")
