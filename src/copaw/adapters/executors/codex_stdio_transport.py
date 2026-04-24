# -*- coding: utf-8 -*-
from __future__ import annotations

import itertools
import json
import os
import queue
import subprocess
import tempfile
import threading
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any
from uuid import uuid4

from ...__version__ import __version__
from .codex_app_server_transport import (
    _CLOSE_SENTINEL,
    _OPT_OUT_NOTIFICATION_METHODS,
    _message_thread_id,
    _response_error_detail,
    _text,
)

_DEFAULT_REQUEST_TIMEOUT_SECONDS = 120.0
_DEFAULT_STARTUP_TIMEOUT_SECONDS = 20.0


class CodexStdioTransport:
    def __init__(
        self,
        *,
        codex_command: Sequence[str],
        request_timeout_seconds: float = _DEFAULT_REQUEST_TIMEOUT_SECONDS,
        startup_timeout_seconds: float = _DEFAULT_STARTUP_TIMEOUT_SECONDS,
    ) -> None:
        self._codex_command = tuple(codex_command)
        self._request_timeout_seconds = max(1.0, float(request_timeout_seconds))
        self._startup_timeout_seconds = max(1.0, float(startup_timeout_seconds))
        self._process: subprocess.Popen[str] | None = None
        self._reader_thread: threading.Thread | None = None
        self._reader_error: str | None = None
        self._closed = False
        self._initialized = False
        self._launch_env: dict[str, str] = {}
        self._launch_args: tuple[str, ...] = ()
        self._server_request_handler = None
        self._restart_count = 0
        self._request_ids = itertools.count(1)
        self._response_queues: dict[str, queue.Queue[object]] = {}
        self._event_queues: dict[str, queue.Queue[object]] = {}
        self._lock = threading.RLock()
        self._send_lock = threading.Lock()

    def request(
        self,
        method: str,
        params: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self._ensure_connection()
        if method != "initialize" and not self._initialized:
            self._initialize_session()
        response = self._send_request(method=method, params=params)
        if response.get("error") is not None:
            raise RuntimeError(_response_error_detail(response))
        return response

    def subscribe_events(self, thread_id: str) -> Iterable[dict[str, object]]:
        self._ensure_connection()
        event_queue = self._event_queue(thread_id)
        while True:
            try:
                payload = event_queue.get(timeout=0.5)
            except queue.Empty:
                if self._reader_error is not None:
                    raise RuntimeError(self._reader_error) from None
                if self._closed:
                    return
                continue
            if payload is _CLOSE_SENTINEL:
                return
            if isinstance(payload, Mapping):
                yield dict(payload)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._shutdown_process()
        self._signal_shutdown()

    def set_server_request_handler(self, handler) -> None:
        with self._lock:
            self._server_request_handler = handler

    def configure_launch(
        self,
        *,
        sidecar_launch_payload: dict[str, object] | None = None,
    ) -> None:
        payload = dict(sidecar_launch_payload or {})
        launch_env = {
            str(key): str(value)
            for key, value in dict(payload.get("env") or {}).items()
            if value is not None and str(value).strip()
        }
        launch_args = tuple(
            str(item)
            for item in list(payload.get("args") or [])
            if str(item).strip()
        )
        with self._lock:
            changed = launch_env != self._launch_env or launch_args != self._launch_args
            self._launch_env = launch_env
            self._launch_args = launch_args
        if changed:
            self._shutdown_process()
            self._initialized = False
            self._reader_error = None
            self._reset_queues()

    def describe_sidecar(self) -> dict[str, object]:
        process = self._process
        return {
            "transport_kind": "stdio",
            "connected": process is not None and process.poll() is None,
            "initialized": self._initialized,
            "process_id": getattr(process, "pid", None),
            "command": list(self._codex_command),
            "launch_args": list(self._launch_args),
            "restart_count": self._restart_count,
            "reader_error": self._reader_error,
        }

    def restart(self) -> dict[str, object]:
        with self._lock:
            if self._closed:
                raise RuntimeError("Codex stdio transport is closed.")
            self._restart_count += 1
        self._shutdown_process()
        self._initialized = False
        self._reader_error = None
        self._signal_shutdown()
        self._reset_queues()
        return self.describe_sidecar()

    def _ensure_connection(self) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("Codex stdio transport is closed.")
            if self._process is not None:
                return
            process = subprocess.Popen(
                [*self._codex_command, *self._launch_args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                bufsize=1,
                env=self._build_process_env(),
            )
            if process.stdin is None or process.stdout is None:
                raise RuntimeError("Codex stdio transport failed to open stdio pipes.")
            self._process = process
            self._reader_thread = threading.Thread(
                target=self._reader_loop,
                name="copaw-codex-stdio-reader",
                daemon=True,
            )
            self._reader_thread.start()

    def _build_process_env(self) -> dict[str, str]:
        launch_env = {**os.environ, **self._launch_env}
        if not str(launch_env.get("CODEX_HOME") or "").strip():
            launch_env["CODEX_HOME"] = str(self._ensure_default_codex_home())
        return launch_env

    def _ensure_default_codex_home(self) -> Path:
        executable_path = Path(str(self._codex_command[0])).expanduser()
        candidate_roots = []
        user_codex_home = Path.home() / ".codex"
        if user_codex_home.exists():
            candidate_roots.append(user_codex_home)
        candidate_roots.append(executable_path.parent / ".codex-home")
        candidate_roots.append(Path(tempfile.gettempdir()) / "copaw" / "codex-home")
        for candidate_root in candidate_roots:
            if self._codex_home_is_writable(candidate_root):
                return candidate_root
        raise RuntimeError("Failed to provision a writable CODEX_HOME for Codex stdio launch.")

    @staticmethod
    def _codex_home_is_writable(candidate_root: Path) -> bool:
        try:
            candidate_root.mkdir(parents=True, exist_ok=True)
            sessions_root = candidate_root / "sessions"
            sessions_root.mkdir(parents=True, exist_ok=True)
            probe_path = sessions_root / f".copaw-write-probe-{uuid4().hex}"
            probe_path.write_text("", encoding="utf-8")
            probe_path.unlink(missing_ok=True)
            return True
        except OSError:
            return False

    def _initialize_session(self) -> None:
        response = self._send_request(
            method="initialize",
            params={
                "clientInfo": {
                    "name": "copaw",
                    "version": __version__,
                },
                "capabilities": {
                    "experimentalApi": True,
                },
                "optOutNotificationMethods": list(_OPT_OUT_NOTIFICATION_METHODS),
            },
        )
        if response.get("error") is not None:
            raise RuntimeError(_response_error_detail(response))
        self._send_json(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            },
        )
        self._initialized = True

    def _send_request(
        self,
        *,
        method: str,
        params: dict[str, object] | None = None,
    ) -> dict[str, object]:
        request_id = str(next(self._request_ids))
        response_queue: queue.Queue[object] = queue.Queue(maxsize=1)
        with self._lock:
            self._response_queues[request_id] = response_queue
        try:
            self._send_json(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": method,
                    "params": dict(params or {}),
                },
            )
            try:
                response = response_queue.get(timeout=self._request_timeout_seconds)
            except queue.Empty as exc:
                raise TimeoutError(
                    f"Timed out waiting for Codex stdio response to '{method}'.",
                ) from exc
            if response is _CLOSE_SENTINEL:
                raise RuntimeError(self._reader_error or "Codex stdio connection closed.")
            if not isinstance(response, Mapping):
                raise RuntimeError(f"Unexpected Codex stdio response: {response!r}")
            return dict(response)
        finally:
            with self._lock:
                self._response_queues.pop(request_id, None)

    def _send_json(self, payload: Mapping[str, Any]) -> None:
        process = self._process
        if process is None or process.stdin is None or process.stdin.closed:
            raise RuntimeError("Codex stdio process is not connected.")
        with self._send_lock:
            process.stdin.write(json.dumps(dict(payload)) + "\n")
            process.stdin.flush()

    def _event_queue(self, thread_id: str) -> queue.Queue[object]:
        with self._lock:
            queue_for_thread = self._event_queues.get(thread_id)
            if queue_for_thread is None:
                queue_for_thread = queue.Queue()
                self._event_queues[thread_id] = queue_for_thread
            return queue_for_thread

    def _reader_loop(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return
        try:
            while True:
                raw_message = process.stdout.readline()
                if raw_message == "":
                    if process.poll() is not None:
                        return
                    continue
                payload = json.loads(raw_message)
                if not isinstance(payload, Mapping):
                    continue
                message = dict(payload)
                if (
                    _text(message.get("method")) is not None
                    and _text(message.get("id")) is not None
                    and "result" not in message
                    and "error" not in message
                ):
                    self._handle_server_request(message)
                    continue
                response_id = _text(message.get("id"))
                if response_id is not None:
                    self._deliver_response(response_id, message)
                    continue
                thread_id = _message_thread_id(message)
                if thread_id is None:
                    continue
                self._event_queue(thread_id).put(message)
        except Exception as exc:
            self._reader_error = str(exc)
        finally:
            self._signal_shutdown()

    def _handle_server_request(self, payload: Mapping[str, Any]) -> None:
        request_id = _text(payload.get("id"))
        method = _text(payload.get("method"))
        if request_id is None or method is None:
            return
        handler = self._server_request_handler
        if not callable(handler):
            self._send_json(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"No handler registered for sidecar request '{method}'.",
                    },
                }
            )
            return
        try:
            result = handler(dict(payload))
        except Exception as exc:
            self._send_json(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32000,
                        "message": str(exc),
                    },
                }
            )
            return
        self._send_json(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": dict(result or {}),
            }
        )

    def _deliver_response(self, request_id: str, payload: Mapping[str, Any]) -> None:
        with self._lock:
            response_queue = self._response_queues.get(request_id)
        if response_queue is not None:
            response_queue.put(dict(payload))

    def _signal_shutdown(self) -> None:
        with self._lock:
            response_queues = list(self._response_queues.values())
            event_queues = list(self._event_queues.values())
        for response_queue in response_queues:
            try:
                response_queue.put_nowait(_CLOSE_SENTINEL)
            except queue.Full:
                continue
        for event_queue in event_queues:
            try:
                event_queue.put_nowait(_CLOSE_SENTINEL)
            except queue.Full:
                continue

    def _shutdown_process(self) -> None:
        process = self._process
        self._process = None
        self._reader_thread = None
        if process is None:
            return
        try:
            if process.stdin is not None and not process.stdin.closed:
                process.stdin.close()
        except Exception:
            pass
        try:
            process.terminate()
            process.wait(timeout=5)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass

    def _reset_queues(self) -> None:
        with self._lock:
            self._response_queues = {}
            self._event_queues = {}
