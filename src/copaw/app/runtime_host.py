# -*- coding: utf-8 -*-
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Awaitable, Callable

from dotenv import load_dotenv

from .runtime_session import SafeJSONSession
from ..agents.memory import MemoryManager
from ..constant import WORKING_DIR

logger = logging.getLogger(__name__)

RestartCallback = Callable[[], Awaitable[Any] | Any]


class RuntimeHost:
    """Own long-lived runtime host dependencies outside the app shell."""

    def __init__(
        self,
        *,
        session_backend: Any | None = None,
        memory_manager: MemoryManager | None = None,
    ) -> None:
        self._session_backend = session_backend
        self._memory_manager = memory_manager
        self._restart_callback: RestartCallback | None = None

    @property
    def session_backend(self) -> Any | None:
        return self._session_backend

    @property
    def memory_manager(self) -> MemoryManager | None:
        return self._memory_manager

    @property
    def restart_callback(self) -> RestartCallback | None:
        return self._restart_callback

    def set_session_backend(self, session_backend: Any) -> None:
        self._session_backend = session_backend

    def set_memory_manager(self, memory_manager: MemoryManager | None) -> None:
        self._memory_manager = memory_manager

    def set_restart_callback(
        self,
        restart_callback: RestartCallback | None,
    ) -> None:
        self._restart_callback = restart_callback

    def sync_turn_executor(self, turn_executor: Any | None) -> None:
        if turn_executor is None:
            return
        if self._session_backend is not None:
            setter = getattr(turn_executor, "set_session_backend", None)
            if callable(setter):
                setter(self._session_backend)
        memory_setter = getattr(turn_executor, "set_memory_manager", None)
        if callable(memory_setter):
            memory_setter(self._memory_manager)
        restart_setter = getattr(turn_executor, "set_restart_callback", None)
        if callable(restart_setter):
            restart_setter(self._restart_callback)

    async def start(self) -> None:
        env_path = Path(__file__).resolve().parents[3] / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            logger.debug("Loaded environment variables from %s", env_path)
        else:
            logger.debug(
                ".env file not found at %s, using existing environment variables",
                env_path,
            )

        if self._session_backend is None:
            self._session_backend = SafeJSONSession(
                database_path=WORKING_DIR / "state" / "phase1.sqlite3",
            )

        try:
            if self._memory_manager is None:
                self._memory_manager = MemoryManager(
                    working_dir=str(WORKING_DIR),
                )
            await self._memory_manager.start()
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("MemoryManager start failed: %s", exc)

    async def stop(self) -> None:
        try:
            if self._memory_manager is not None:
                await self._memory_manager.close()
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("MemoryManager stop failed: %s", exc)


__all__ = ["RuntimeHost", "RestartCallback"]
