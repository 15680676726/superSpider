# -*- coding: utf-8 -*-
from __future__ import annotations

import itertools
import json
import os
import queue
import shutil
import socket
import subprocess
import threading
import time
from collections.abc import Iterable, Mapping, Sequence
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

import websocket

from ...__version__ import __version__

_CLOSE_SENTINEL = object()
_DEFAULT_REQUEST_TIMEOUT_SECONDS = 120.0
_DEFAULT_STARTUP_TIMEOUT_SECONDS = 20.0
_DEFAULT_LISTEN_HOST = "127.0.0.1"
_DEFAULT_HEALTH_PATH = "/healthz"
_OPT_OUT_NOTIFICATION_METHODS = [
    "command/exec/outputDelta",
    "item/agentMessage/delta",
    "item/plan/delta",
    "item/fileChange/outputDelta",
    "item/reasoning/summaryTextDelta",
    "item/reasoning/textDelta",
]


def _text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _mapping(value: object | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _find_free_port(host: str = _DEFAULT_LISTEN_HOST) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


def _as_health_url(websocket_url: str) -> str:
    base = websocket_url.rstrip("/")
    if base.startswith("ws://"):
        return "http://" + base[len("ws://") :] + _DEFAULT_HEALTH_PATH
    if base.startswith("wss://"):
        return "https://" + base[len("wss://") :] + _DEFAULT_HEALTH_PATH
    return base + _DEFAULT_HEALTH_PATH


def _message_thread_id(message: Mapping[str, Any]) -> str | None:
    params = _mapping(message.get("params"))
    if "threadId" in params:
        return _text(params.get("threadId"))
    if "thread_id" in params:
        return _text(params.get("thread_id"))
    return None


def _response_error_detail(payload: Mapping[str, Any]) -> str:
    error = _mapping(payload.get("error"))
    if not error:
        return "Codex App Server request failed."
    message = _text(error.get("message")) or "Codex App Server request failed."
    data = error.get("data")
    if data is None:
        return message
    return f"{message} ({data})"


class CodexAppServerTransport:
    def __init__(
        self,
        *,
        websocket_url: str | None = None,
        codex_command: Sequence[str] | None = None,
        request_timeout_seconds: float = _DEFAULT_REQUEST_TIMEOUT_SECONDS,
        startup_timeout_seconds: float = _DEFAULT_STARTUP_TIMEOUT_SECONDS,
    ) -> None:
        self._configured_websocket_url = _text(websocket_url) or _text(
            os.getenv("COPAW_CODEX_APP_SERVER_WS_URL"),
        )
        self._codex_command = tuple(codex_command or self._default_codex_command())
        self._request_timeout_seconds = max(1.0, float(request_timeout_seconds))
        self._startup_timeout_seconds = max(1.0, float(startup_timeout_seconds))
        self._websocket: websocket.WebSocket | None = None
        self._process: subprocess.Popen[Any] | None = None
        self._reader_thread: threading.Thread | None = None
        self._reader_error: str | None = None
        self._closed = False
        self._initialized = False
        self._request_ids = itertools.count(1)
        self._response_queues: dict[str, queue.Queue[object]] = {}
        self._event_queues: dict[str, queue.Queue[object]] = {}
        self._lock = threading.RLock()
        self._send_lock = threading.Lock()

    @staticmethod
    def _default_codex_command() -> tuple[str, ...]:
        configured = _text(os.getenv("COPAW_CODEX_APP_SERVER_BIN"))
        if configured is not None:
            return (configured, "app-server")
        if os.name == "nt":
            binary = shutil.which("codex.cmd") or shutil.which("codex")
        else:
            binary = shutil.which("codex")
        return ((binary or "codex"), "app-server")

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
        websocket_conn = self._websocket
        self._websocket = None
        if websocket_conn is not None:
            try:
                websocket_conn.close()
            except Exception:
                pass
        process = self._process
        self._process = None
        if process is not None:
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        self._signal_shutdown()

    def _ensure_connection(self) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError("Codex App Server transport is closed.")
            if self._websocket is not None:
                return
            websocket_url = self._configured_websocket_url or self._spawn_local_server()
            self._wait_for_health(websocket_url)
            self._websocket = websocket.create_connection(
                websocket_url,
                timeout=self._request_timeout_seconds,
                suppress_origin=True,
            )
            self._reader_thread = threading.Thread(
                target=self._reader_loop,
                name="copaw-codex-app-server-reader",
                daemon=True,
            )
            self._reader_thread.start()

    def _spawn_local_server(self) -> str:
        port = _find_free_port()
        websocket_url = f"ws://{_DEFAULT_LISTEN_HOST}:{port}"
        command = [
            *self._codex_command,
            "--listen",
            websocket_url,
        ]
        self._process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
        )
        return websocket_url

    def _wait_for_health(self, websocket_url: str) -> None:
        health_url = _as_health_url(websocket_url)
        deadline = time.monotonic() + self._startup_timeout_seconds
        last_error: str | None = None
        while time.monotonic() < deadline:
            process = self._process
            if process is not None and process.poll() is not None:
                raise RuntimeError("Codex App Server exited before it became ready.")
            try:
                with urllib_request.urlopen(health_url, timeout=2.0) as response:
                    if 200 <= int(getattr(response, "status", 200)) < 300:
                        return
            except (urllib_error.URLError, TimeoutError, OSError) as exc:
                last_error = str(exc)
                time.sleep(0.25)
        raise RuntimeError(
            f"Timed out waiting for Codex App Server health endpoint '{health_url}'"
            + (f": {last_error}" if last_error else ""),
        )

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
        self._initialized = True

    def _send_request(
        self,
        *,
        method: str,
        params: dict[str, object] | None = None,
    ) -> dict[str, object]:
        websocket_conn = self._websocket
        if websocket_conn is None:
            raise RuntimeError("Codex App Server websocket is not connected.")
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
                    f"Timed out waiting for Codex App Server response to '{method}'.",
                ) from exc
            if response is _CLOSE_SENTINEL:
                raise RuntimeError(self._reader_error or "Codex App Server connection closed.")
            if not isinstance(response, Mapping):
                raise RuntimeError(f"Unexpected Codex App Server response: {response!r}")
            return dict(response)
        finally:
            with self._lock:
                self._response_queues.pop(request_id, None)

    def _send_json(self, payload: Mapping[str, Any]) -> None:
        websocket_conn = self._websocket
        if websocket_conn is None:
            raise RuntimeError("Codex App Server websocket is not connected.")
        with self._send_lock:
            websocket_conn.send(json.dumps(dict(payload)))

    def _event_queue(self, thread_id: str) -> queue.Queue[object]:
        with self._lock:
            queue_for_thread = self._event_queues.get(thread_id)
            if queue_for_thread is None:
                queue_for_thread = queue.Queue()
                self._event_queues[thread_id] = queue_for_thread
            return queue_for_thread

    def _reader_loop(self) -> None:
        websocket_conn = self._websocket
        if websocket_conn is None:
            return
        try:
            while True:
                raw_message = websocket_conn.recv()
                if raw_message is None:
                    continue
                if isinstance(raw_message, bytes):
                    raw_message = raw_message.decode("utf-8")
                payload = json.loads(raw_message)
                if not isinstance(payload, Mapping):
                    continue
                message = dict(payload)
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
