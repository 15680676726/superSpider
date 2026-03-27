#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Benchmark main-brain chat latency over the runtime-center API.

Note: The legacy orchestration front-door ("/runtime-center/chat/orchestrate") is retired.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class BenchmarkResult:
    mode: str
    endpoint: str
    session_id: str
    prompt: str
    http_status: int
    first_event_seconds: float | None = None
    first_message_seconds: float | None = None
    completed_seconds: float | None = None
    final_status: str | None = None
    error: str | None = None


def _build_payload(args: argparse.Namespace, *, mode: str, session_id: str) -> dict[str, Any]:
    return {
        "id": f"benchmark-{mode}-{int(time.time() * 1000)}",
        "session_id": session_id,
        "user_id": args.user_id,
        "channel": args.channel,
        "interaction_mode": mode,
        "industry_instance_id": args.industry_instance_id or None,
        "industry_role_id": args.industry_role_id or None,
        "control_thread_id": args.control_thread_id or None,
        "input": [
            {
                "role": "user",
                "type": "message",
                "content": [{"type": "text", "text": args.prompt}],
            }
        ],
    }


def _iter_sse_payloads(response) -> Any:
    while True:
        raw_line = response.readline()
        if not raw_line:
            break
        line = raw_line.decode("utf-8").strip()
        if not line or not line.startswith("data:"):
            continue
        body = line[5:].strip()
        if not body:
            continue
        yield json.loads(body)


def _measure_once(args: argparse.Namespace, *, mode: str) -> BenchmarkResult:
    endpoint = f"{args.base_url.rstrip('/')}/runtime-center/chat/run"
    timestamp = int(time.time())
    session_id = f"{args.session_prefix}:{mode}:{timestamp}"
    payload = _build_payload(args, mode=mode, session_id=session_id)
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        method="POST",
    )
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            result = BenchmarkResult(
                mode=mode,
                endpoint=endpoint,
                session_id=session_id,
                prompt=args.prompt,
                http_status=getattr(response, "status", 200),
            )
            for payload_item in _iter_sse_payloads(response):
                now = time.perf_counter()
                elapsed = round(now - start, 4)
                if result.first_event_seconds is None:
                    result.first_event_seconds = elapsed
                if (
                    result.first_message_seconds is None
                    and payload_item.get("object") == "message"
                ):
                    result.first_message_seconds = elapsed
                if payload_item.get("object") == "response":
                    status = str(payload_item.get("status") or "").lower()
                    if status in {"completed", "failed", "canceled"}:
                        result.completed_seconds = elapsed
                        result.final_status = status
                        break
            if result.completed_seconds is None:
                result.completed_seconds = round(time.perf_counter() - start, 4)
            return result
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return BenchmarkResult(
            mode=mode,
            endpoint=endpoint,
            session_id=session_id,
            prompt=args.prompt,
            http_status=exc.code,
            error=detail or str(exc),
        )
    except Exception as exc:
        return BenchmarkResult(
            mode=mode,
            endpoint=endpoint,
            session_id=session_id,
            prompt=args.prompt,
            http_status=0,
            error=str(exc),
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark runtime-center main-brain chat latency (orchestration entry retired).",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000/api",
        help="Runtime Center API base URL, e.g. http://127.0.0.1:8000/api",
    )
    parser.add_argument(
        "--mode",
        choices=("chat", "orchestrate", "both"),
        default="both",
        help="Which mode to benchmark.",
    )
    parser.add_argument(
        "--prompt",
        default="请先解释当前团队谁负责什么，再给出下一步建议，不要直接开始执行。",
        help="Prompt sent to both chat surfaces.",
    )
    parser.add_argument("--user-id", default="benchmark-user")
    parser.add_argument("--channel", default="console")
    parser.add_argument("--session-prefix", default="benchmark:main-brain-chat-split")
    parser.add_argument("--industry-instance-id", default="")
    parser.add_argument("--industry-role-id", default="")
    parser.add_argument("--control-thread-id", default="")
    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="Per-request timeout in seconds.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    modes = ["chat"]
    if args.mode != "chat":
        print("[notice] orchestration front-door is retired; benchmarking chat only")
    results = [_measure_once(args, mode=mode) for mode in modes]
    print(json.dumps([asdict(item) for item in results], ensure_ascii=False, indent=2))
    return 0 if all(item.error is None for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
