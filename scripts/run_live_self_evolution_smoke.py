# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import http.client
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request


def _default_working_dir() -> Path:
    return Path(os.environ.get("COPAW_WORKING_DIR", "~/.copaw")).expanduser().resolve()


def _default_secret_dir(working_dir: Path) -> Path:
    return Path(
        os.environ.get("COPAW_SECRET_DIR", f"{working_dir}.secret"),
    ).expanduser().resolve()


def _copy_file_if_exists(source: Path, destination: Path) -> None:
    if source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _copy_tree_if_exists(source: Path, destination: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)


def _write_browser_smoke_page(artifacts_dir: Path) -> str:
    page_path = artifacts_dir / "browser-smoke-page.html"
    page_path.write_text(
        """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>CoPaw Browser Smoke</title>
</head>
<body>
  <h1>CoPaw Browser Smoke</h1>
  <label for="query">Query</label>
  <input id="query" name="query" type="text" value="" />
  <button id="save" type="button" onclick="saveQuery()">Save</button>
  <p id="status">Idle</p>
  <script>
    function saveQuery() {
      const value = document.getElementById('query').value;
      document.getElementById('status').textContent = 'Saved: ' + value;
      window.location.hash = 'saved';
      document.title = 'Saved ' + value;
    }
  </script>
</body>
</html>
""",
        encoding="utf-8",
    )
    return page_path.resolve().as_uri()


def _prepare_runtime_root(
    *,
    runtime_root: Path,
    source_working_dir: Path,
    source_secret_dir: Path,
) -> tuple[Path, Path, Path]:
    target_runtime_root = runtime_root
    if runtime_root.exists():
        try:
            shutil.rmtree(runtime_root)
        except PermissionError:
            target_runtime_root = runtime_root.parent / (
                f"{runtime_root.name}_{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
            )
    working_dir = target_runtime_root / "working"
    secret_dir = target_runtime_root / "secret"
    working_dir.mkdir(parents=True, exist_ok=True)
    secret_dir.mkdir(parents=True, exist_ok=True)
    _copy_file_if_exists(source_working_dir / "config.json", working_dir / "config.json")
    _copy_tree_if_exists(source_secret_dir / "providers", secret_dir / "providers")
    _copy_file_if_exists(source_secret_dir / "envs.json", secret_dir / "envs.json")
    return target_runtime_root, working_dir, secret_dir


def _pick_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _build_env(*, repo_root: Path, working_dir: Path, secret_dir: Path) -> dict[str, str]:
    env = dict(os.environ)
    existing_pythonpath = env.get("PYTHONPATH", "").strip()
    src_path = str((repo_root / "src").resolve())
    env["PYTHONPATH"] = (
        src_path
        if not existing_pythonpath
        else src_path + os.pathsep + existing_pythonpath
    )
    env["PYTHONUTF8"] = "1"
    env["COPAW_WORKING_DIR"] = str(working_dir)
    env["COPAW_SECRET_DIR"] = str(secret_dir)
    env.setdefault("COPAW_LOG_LEVEL", "info")
    return env


def _start_server(
    *,
    repo_root: Path,
    env: dict[str, str],
    host: str,
    port: int,
    log_path: Path,
) -> tuple[subprocess.Popen[str], Any]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "copaw.app._app:app",
            "--host",
            host,
            "--port",
            str(port),
            "--log-level",
            env.get("COPAW_LOG_LEVEL", "info"),
        ],
        cwd=str(repo_root),
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return process, log_handle


def _stop_server(process: subprocess.Popen[str], log_handle: Any) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
    log_handle.close()


def _parse_json_body(body: str) -> Any:
    return json.loads(body) if body.strip() else None


def _request(
    *,
    base_url: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 300.0,
) -> tuple[int, dict[str, str], str]:
    data = None
    request_headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    parsed = urllib.parse.urlsplit(base_url)
    connection = http.client.HTTPConnection(
        host=parsed.hostname,
        port=parsed.port,
        timeout=timeout,
    )
    try:
        connection.request(
            method=method,
            url=path,
            body=data,
            headers=request_headers,
        )
        response = connection.getresponse()
        body = response.read().decode("utf-8", errors="replace")
        return int(response.status), dict(response.getheaders()), body
    finally:
        connection.close()


def _request_json(
    *,
    base_url: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 300.0,
) -> tuple[int, dict[str, str], Any]:
    status, headers, body = _request(
        base_url=base_url,
        method=method,
        path=path,
        payload=payload,
        timeout=timeout,
    )
    return status, headers, _parse_json_body(body)


def _request_text(
    *,
    base_url: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 300.0,
) -> tuple[int, dict[str, str], str]:
    return _request(
        base_url=base_url,
        method=method,
        path=path,
        payload=payload,
        timeout=timeout,
    )


def _wait_for_server(
    *,
    base_url: str,
    process: subprocess.Popen[str],
    timeout_seconds: float = 420.0,
) -> None:
    started = time.time()
    last_error: str | None = None
    while time.time() - started < timeout_seconds:
        if process.poll() is not None:
            raise RuntimeError(f"Server exited early with code {process.returncode}.")
        try:
            status, _headers, payload = _request_json(
                base_url=base_url,
                method="GET",
                path="/api/system/overview",
                timeout=10.0,
            )
            if status == 200 and isinstance(payload, dict):
                return None
            last_error = f"unexpected status {status}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(2.0)
    raise RuntimeError(f"Timed out waiting for server readiness. Last error: {last_error}")


def _parse_sse_events(raw_text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for chunk in raw_text.strip().split("\n\n"):
        if not chunk:
            continue
        data_lines: list[str] = []
        for line in chunk.splitlines():
            if not line.startswith("data:"):
                continue
            payload = line[len("data:"):].lstrip()
            if payload:
                data_lines.append(payload)
        if not data_lines:
            continue
        try:
            events.append(json.loads("\n".join(data_lines)))
        except json.JSONDecodeError:
            continue
    return events


def _self_check_by_name(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    checks = list(payload.get("checks") or [])
    return {
        str(item.get("name") or ""): dict(item)
        for item in checks
        if isinstance(item, dict)
    }


def _load_self_check_by_name(base_url: str) -> dict[str, dict[str, Any]]:
    status, _headers, payload = _request_json(
        base_url=base_url,
        method="GET",
        path="/api/system/self-check",
        timeout=120.0,
    )
    if status != 200 or not isinstance(payload, dict):
        raise RuntimeError(f"System self-check failed. status={status}")
    return _self_check_by_name(payload)


def _load_learning_items_for_failed_chain(
    *,
    base_url: str,
    endpoint: str,
    failed_turns: list[dict[str, Any]],
    failed_browser_evidence: list[dict[str, Any]],
) -> tuple[str | None, list[dict[str, Any]]]:
    candidate_task_ids: list[str] = []
    seen_task_ids: set[str] = set()
    for item in failed_turns:
        task_id = str(item.get("task_id") or "").strip()
        if task_id and task_id not in seen_task_ids:
            seen_task_ids.add(task_id)
            candidate_task_ids.append(task_id)
    for item in failed_browser_evidence:
        task_id = str(item.get("task_id") or "").strip()
        if task_id and task_id not in seen_task_ids:
            seen_task_ids.add(task_id)
            candidate_task_ids.append(task_id)

    fallback_task_id = candidate_task_ids[0] if candidate_task_ids else None
    for task_id in candidate_task_ids:
        status, _headers, payload = _request_json(
            base_url=base_url,
            method="GET",
            path=f"/api/runtime-center/learning/{endpoint}?task_id={urllib.parse.quote(task_id)}",
            timeout=120.0,
        )
        if status != 200 or not isinstance(payload, list):
            raise RuntimeError(
                f"{endpoint} list failed for task '{task_id}'. status={status}",
            )
        items = [dict(item) for item in payload if isinstance(item, dict)]
        if items:
            return task_id, items
    return fallback_task_id, []


def _first_business_role(team_payload: dict[str, Any]) -> dict[str, Any]:
    for role in list(team_payload.get("agents") or []):
        if not isinstance(role, dict):
            continue
        role_id = str(role.get("role_id") or "").strip()
        if role_id and role_id not in {"execution-core", "researcher"}:
            return role
    raise RuntimeError("Preview draft did not materialize a non-core business role.")


def _resolve_team_role(team_payload: dict[str, Any], role_id: str) -> dict[str, Any]:
    for role in list(team_payload.get("agents") or []):
        if isinstance(role, dict) and str(role.get("role_id") or "").strip() == role_id:
            return role
    raise RuntimeError(f"Role '{role_id}' was not found in the bootstrapped team payload.")


def _list_tasks(base_url: str) -> list[dict[str, Any]]:
    status, _headers, payload = _request_json(
        base_url=base_url,
        method="GET",
        path="/api/runtime-center/tasks?limit=200",
        timeout=60.0,
    )
    if status != 200 or not isinstance(payload, list):
        raise RuntimeError(f"Failed to list tasks. status={status}")
    return [dict(item) for item in payload if isinstance(item, dict)]


def _list_task_evidence(
    *,
    base_url: str,
    task_id: str,
) -> list[dict[str, Any]]:
    evidence_status, _evidence_headers, evidence_payload = _request_json(
        base_url=base_url,
        method="GET",
        path=f"/api/runtime-center/evidence?task_id={urllib.parse.quote(task_id)}",
        timeout=60.0,
    )
    if evidence_status != 200 or not isinstance(evidence_payload, list):
        raise RuntimeError(
            f"Failed to read evidence for task '{task_id or 'unknown'}'. status={evidence_status}",
        )
    return [dict(item) for item in evidence_payload if isinstance(item, dict)]


def _run_chat_turn(
    *,
    base_url: str,
    instance_id: str,
    role_id: str,
    agent_id: str,
    request_id: str,
    prompt: str,
) -> dict[str, Any]:
    before_tasks = {
        str(item.get("id") or "")
        for item in _list_tasks(base_url)
        if str(item.get("id") or "").strip()
    }
    status, headers, body = _request_text(
        base_url=base_url,
        method="POST",
        path="/api/runtime-center/chat/run",
        payload={
            "id": request_id,
            "session_id": f"industry-chat:{instance_id}:{role_id}",
            "thread_id": f"industry-chat:{instance_id}:{role_id}",
            "user_id": agent_id,
            "channel": "console",
            "agent_id": agent_id,
            "industry_instance_id": instance_id,
            "industry_role_id": role_id,
            "session_kind": "industry-agent-chat",
            "interaction_mode": "auto",
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": prompt}],
                }
            ],
        },
        timeout=420.0,
    )
    after_tasks = _list_tasks(base_url)
    new_tasks = [
        dict(item)
        for item in after_tasks
        if str(item.get("id") or "").strip() not in before_tasks
        and str(item.get("owner_agent_id") or "").strip() == agent_id
    ]
    events = _parse_sse_events(body)
    matching_tasks = [
        item
        for item in new_tasks
        if request_id in str(item.get("id") or "")
    ]
    root_task_candidates = [
        item
        for item in matching_tasks
        if ":tool:" not in str(item.get("id") or "")
        and ":skill:" not in str(item.get("id") or "")
        and ":mcp:" not in str(item.get("id") or "")
    ]
    task_payload = None
    if root_task_candidates:
        task_payload = sorted(
            root_task_candidates,
            key=lambda item: len(str(item.get("id") or "")),
        )[0]
    elif matching_tasks:
        task_payload = sorted(
            matching_tasks,
            key=lambda item: len(str(item.get("id") or "")),
        )[0]
    elif new_tasks:
        task_payload = new_tasks[0]
    task_id = str(task_payload.get("id") or "") if isinstance(task_payload, dict) else ""
    related_task_ids: list[str] = []
    if task_id:
        related_task_ids.append(task_id)
    related_task_ids.extend(
        str(item.get("id") or "").strip()
        for item in matching_tasks
        if str(item.get("id") or "").strip()
    )
    deduped_related_task_ids: list[str] = []
    seen_task_ids: set[str] = set()
    for related_task_id in related_task_ids:
        if related_task_id in seen_task_ids:
            continue
        seen_task_ids.add(related_task_id)
        deduped_related_task_ids.append(related_task_id)
    evidence_records: list[dict[str, Any]] = []
    for related_task_id in deduped_related_task_ids:
        evidence_records.extend(
            _list_task_evidence(
                base_url=base_url,
                task_id=related_task_id,
            ),
        )
    return {
        "response_status": status,
        "content_type": headers.get("Content-Type", ""),
        "events": events,
        "body": body,
        "task": task_payload,
        "task_id": task_id or None,
        "evidence": evidence_records,
    }


def _find_latest_failed_task(
    run_results: list[dict[str, Any]],
) -> tuple[str | None, str | None]:
    for item in run_results:
        task_id = str(item.get("task_id") or "").strip()
        evidence_records = list(item.get("evidence") or [])
        if not task_id:
            continue
        if any(str(record.get("status") or "").strip() == "failed" for record in evidence_records):
            return task_id, next(
                (
                    str(record.get("id") or "").strip()
                    for record in evidence_records
                    if str(record.get("status") or "").strip() == "failed"
                ),
                None,
            )
    return None, None


def _extract_browser_action(record: dict[str, Any]) -> str | None:
    metadata = dict(record.get("metadata") or {})
    action = metadata.get("action")
    if isinstance(action, str) and action.strip():
        return action.strip()
    execution = dict(metadata.get("execution") or {})
    payload = dict(execution.get("payload") or {})
    payload_action = payload.get("action")
    if isinstance(payload_action, str) and payload_action.strip():
        return payload_action.strip()
    return None


def _browser_sequence_summary(
    evidence_records: list[dict[str, Any]],
) -> dict[str, Any]:
    browser_records = [
        dict(record)
        for record in evidence_records
        if isinstance(record, dict)
        and str(record.get("capability_ref") or "").strip() == "tool:browser_use"
    ]
    actions: list[str] = []
    for record in browser_records:
        action = _extract_browser_action(record)
        if action:
            actions.append(action)
    serialized_records = json.dumps(browser_records, ensure_ascii=False)
    saw_saved_state = "Saved: OpenAI API" in serialized_records
    saw_model_slot_failure = "MODEL_SLOT_UNAVAILABLE" in json.dumps(
        evidence_records,
        ensure_ascii=False,
    )
    action_set = set(actions)
    return {
        "actions": actions,
        "verified": {
            "opened": "open" in action_set,
            "typed": "type" in action_set,
            "clicked": "click" in action_set,
            "snapshotted": "snapshot" in action_set,
            "saved_state_visible": saw_saved_state,
        },
        "browser_records": len(browser_records),
        "model_slot_failure_observed": saw_model_slot_failure,
        "sequence_ok": (
            "open" in action_set
            and "type" in action_set
            and "click" in action_set
            and "snapshot" in action_set
            and saw_saved_state
        ),
    }


def _list_capability_evidence(
    *,
    base_url: str,
    capability_ref: str,
    limit: int = 200,
) -> list[dict[str, Any]]:
    status, _headers, payload = _request_json(
        base_url=base_url,
        method="GET",
        path=(
            "/api/runtime-center/evidence"
            f"?capability_ref={urllib.parse.quote(capability_ref)}&limit={limit}"
        ),
        timeout=120.0,
    )
    if status != 200 or not isinstance(payload, list):
        raise RuntimeError(
            f"Capability evidence query failed for '{capability_ref}'. status={status}",
    )
    return [dict(item) for item in payload if isinstance(item, dict)]


def _ensure_clean_browser_runtime_session(
    *,
    base_url: str,
    session_id: str,
    entry_url: str,
    allowed_hosts: list[str] | None = None,
) -> dict[str, Any]:
    list_status, _list_headers, list_payload = _request_json(
        base_url=base_url,
        method="GET",
        path="/api/capability-market/install-templates/browser-local/sessions",
        timeout=120.0,
    )
    if list_status != 200 or not isinstance(list_payload, dict):
        raise RuntimeError(
            f"Browser runtime session list failed. status={list_status}",
        )
    active_session_ids = [
        str(item.get("session_id") or "").strip()
        for item in list(list_payload.get("sessions") or [])
        if isinstance(item, dict) and str(item.get("session_id") or "").strip()
    ]
    for active_session_id in active_session_ids:
        stop_status, _stop_headers, stop_payload = _request_json(
            base_url=base_url,
            method="POST",
            path=(
                "/api/capability-market/install-templates/browser-local/sessions/"
                f"{urllib.parse.quote(active_session_id)}/stop"
            ),
            timeout=120.0,
        )
        stop_result = dict(stop_payload.get("result") or {}) if isinstance(stop_payload, dict) else {}
        if stop_status != 200 or not stop_result.get("ok"):
            raise RuntimeError(
                f"Browser runtime session stop failed for '{active_session_id}'. "
                f"status={stop_status} payload={stop_payload}",
            )
    browser_session_status, _session_headers, browser_session_payload = _request_json(
        base_url=base_url,
        method="POST",
        path="/api/capability-market/install-templates/browser-local/sessions/start",
        payload={
            "session_id": session_id,
            "headed": True,
            "entry_url": entry_url,
            "reuse_running_session": False,
            "allowed_hosts": list(allowed_hosts or []),
        },
        timeout=240.0,
    )
    if browser_session_status != 200 or not isinstance(browser_session_payload, dict):
        raise RuntimeError(
            f"Browser session start failed. status={browser_session_status}",
        )
    return browser_session_payload


def _run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    runtime_root = args.runtime_root.resolve()
    source_working_dir = args.source_working_dir.resolve()
    source_secret_dir = args.source_secret_dir.resolve()
    runtime_root, working_dir, secret_dir = _prepare_runtime_root(
        runtime_root=runtime_root,
        source_working_dir=source_working_dir,
        source_secret_dir=source_secret_dir,
    )
    artifacts_dir = runtime_root / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    browser_smoke_page_url = _write_browser_smoke_page(artifacts_dir)
    port = args.port or _pick_port()
    host = "127.0.0.1"
    base_url = f"http://{host}:{port}"
    env = _build_env(repo_root=repo_root, working_dir=working_dir, secret_dir=secret_dir)
    log_path = runtime_root / "server.log"

    process, log_handle = _start_server(
        repo_root=repo_root,
        env=env,
        host=host,
        port=port,
        log_path=log_path,
    )
    try:
        _wait_for_server(base_url=base_url, process=process)
        self_check_by_name = _load_self_check_by_name(base_url)

        preview_status, _preview_headers, preview_payload = _request_json(
            base_url=base_url,
            method="POST",
            path="/api/industry/v1/preview",
            payload={
                "industry": "Customer Operations",
                "company_name": "Northwind Robotics",
                "product": "browser onboarding workflows",
                "goals": [
                    "run a governed browser onboarding loop and let the system improve itself from evidence",
                ],
            },
            timeout=600.0,
        )
        if preview_status != 200 or not isinstance(preview_payload, dict):
            raise RuntimeError(f"Preview failed. status={preview_status} payload={preview_payload}")

        draft = dict(preview_payload["draft"])
        selected_role = _first_business_role(draft["team"])
        selected_role_id = str(selected_role["role_id"])
        selected_agent_id = str(selected_role["agent_id"])

        bootstrap_status, _bootstrap_headers, bootstrap_payload = _request_json(
            base_url=base_url,
            method="POST",
            path="/api/industry/v1/bootstrap",
            payload={
                "profile": preview_payload["profile"],
                "draft": preview_payload["draft"],
                "install_plan": [
                    {
                        "install_kind": "builtin-runtime",
                        "template_id": "browser-local",
                        "client_key": "browser-local-default",
                        "source_kind": "install-template",
                        "capability_assignment_mode": "merge",
                        "target_agent_ids": [selected_agent_id],
                    }
                ],
                "auto_activate": True,
                "auto_dispatch": False,
                "execute": False,
            },
            timeout=600.0,
        )
        if bootstrap_status != 200 or not isinstance(bootstrap_payload, dict):
            raise RuntimeError(
                f"Bootstrap failed. status={bootstrap_status} payload={bootstrap_payload}",
            )

        team_payload = dict(bootstrap_payload["team"])
        instance_id = str(team_payload["team_id"])
        bootstrapped_role = _resolve_team_role(team_payload, selected_role_id)
        selected_agent_id = str(bootstrapped_role["agent_id"])

        acquisition_status, _acquisition_headers, acquisition_payload = _request_json(
            base_url=base_url,
            method="POST",
            path="/api/learning/acquisition/run",
            payload={"industry_instance_id": instance_id},
            timeout=420.0,
        )
        if acquisition_status != 200 or not isinstance(acquisition_payload, dict):
            raise RuntimeError(
                f"Acquisition failed. status={acquisition_status} payload={acquisition_payload}",
            )

        browser_session_payload = _ensure_clean_browser_runtime_session(
            base_url=base_url,
            session_id="live-self-evolution-browser",
            entry_url=browser_smoke_page_url,
        )

        success_screenshot = artifacts_dir / "live-success-browser.png"
        browser_evidence_before = {
            str(item.get("id") or "").strip()
            for item in _list_capability_evidence(
                base_url=base_url,
                capability_ref="tool:browser_use",
            )
            if str(item.get("id") or "").strip()
        }
        success_turn = _run_chat_turn(
            base_url=base_url,
            instance_id=instance_id,
            role_id=selected_role_id,
            agent_id=selected_agent_id,
            request_id="req-live-self-evolution-success",
            prompt=(
                "Use the mounted browser capability right now. "
                f"Open {browser_smoke_page_url}, type 'OpenAI API' into the Query input, "
                "click the Save button, wait until the page shows 'Saved: OpenAI API', then save a screenshot to "
                f"{success_screenshot}. "
                "Do not answer until the screenshot is really saved, then report the final screenshot path."
            ),
        )
        success_browser_summary = _browser_sequence_summary(
            list(success_turn.get("evidence") or []),
        )

        failure_prompts = [
            (
                "req-live-self-evolution-fail-1",
                (
                    "Use the mounted browser capability right now. "
                    f"Open {browser_smoke_page_url}, type 'OpenAI API' into the Query input, "
                    "click the Save button, wait until the page shows 'Saved: OpenAI API', then save a screenshot to "
                    "Z:\\__copaw_live_smoke__\\missing\\failure.png. "
                    "Do not choose another path."
                ),
            ),
            (
                "req-live-self-evolution-fail-2",
                (
                    "Use the mounted browser capability right now. "
                    f"Open {browser_smoke_page_url}, type 'OpenAI API' into the Query input, "
                    "click the Save button, wait until the page shows 'Saved: OpenAI API', then click the exact text "
                    "'THIS_SELECTOR_SHOULD_NOT_EXIST_9D3F', and only finish if the click succeeded."
                ),
            ),
        ]
        failed_turns: list[dict[str, Any]] = []
        for request_id, prompt in failure_prompts:
            result = _run_chat_turn(
                base_url=base_url,
                instance_id=instance_id,
                role_id=selected_role_id,
                agent_id=selected_agent_id,
                request_id=request_id,
                prompt=prompt,
            )
            evidence_records = list(result.get("evidence") or [])
            if any(str(item.get("status") or "").strip() == "failed" for item in evidence_records):
                failed_turns.append(result)
            if len(failed_turns) >= 2:
                break

        browser_evidence_after = _list_capability_evidence(
            base_url=base_url,
            capability_ref="tool:browser_use",
        )
        failed_browser_evidence = [
            item
            for item in browser_evidence_after
            if str(item.get("status") or "").strip() == "failed"
            and str(item.get("id") or "").strip() not in browser_evidence_before
        ]

        strategy_status, _strategy_headers, strategy_payload = _request_json(
            base_url=base_url,
            method="POST",
            path="/api/learning/automation/strategy",
            payload={
                "actor": "copaw-main-brain",
                "limit": 20,
                "auto_apply": True,
                "auto_rollback": False,
                "failure_threshold": 2,
                "confirm_threshold": 6,
                "max_proposals": 3,
            },
            timeout=300.0,
        )
        if strategy_status != 200 or not isinstance(strategy_payload, dict):
            raise RuntimeError(
                f"Strategy automation failed. status={strategy_status} payload={strategy_payload}",
            )

        detail_status, _detail_headers, detail_payload = _request_json(
            base_url=base_url,
            method="GET",
            path=f"/api/runtime-center/industry/{urllib.parse.quote(instance_id)}",
            timeout=120.0,
        )
        if detail_status != 200 or not isinstance(detail_payload, dict):
            raise RuntimeError(f"Runtime detail failed. status={detail_status}")
        optimization_closure = dict(detail_payload.get("optimization_closure") or {})

        failed_task_id, failed_evidence_id = _find_latest_failed_task(failed_turns)
        learning_anchor_task_id, applied_patches = _load_learning_items_for_failed_chain(
            base_url=base_url,
            endpoint="patches",
            failed_turns=failed_turns,
            failed_browser_evidence=failed_browser_evidence,
        )
        growth_anchor_task_id, growth_items = _load_learning_items_for_failed_chain(
            base_url=base_url,
            endpoint="growth",
            failed_turns=failed_turns,
            failed_browser_evidence=failed_browser_evidence,
        )
        if learning_anchor_task_id:
            failed_task_id = learning_anchor_task_id
        elif growth_anchor_task_id:
            failed_task_id = growth_anchor_task_id

    finally:
        _stop_server(process, log_handle)

    restart_process, restart_log_handle = _start_server(
        repo_root=repo_root,
        env=env,
        host=host,
        port=port,
        log_path=runtime_root / "server-restart.log",
    )
    try:
        _wait_for_server(base_url=base_url, process=restart_process)
        restart_self_check_by_name = _load_self_check_by_name(base_url)
        restart_detail_status, _restart_detail_headers, restart_detail_payload = _request_json(
            base_url=base_url,
            method="GET",
            path=f"/api/runtime-center/industry/{urllib.parse.quote(instance_id)}",
            timeout=120.0,
        )
        if restart_detail_status != 200 or not isinstance(restart_detail_payload, dict):
            raise RuntimeError(
                f"Runtime detail after restart failed. status={restart_detail_status}",
            )
        restart_patch_status, _restart_patch_headers, restart_patch_payload = _request_json(
            base_url=base_url,
            method="GET",
            path=(
                "/api/runtime-center/learning/patches"
                f"?task_id={urllib.parse.quote(failed_task_id)}"
                if failed_task_id
                else "/api/runtime-center/learning/patches?limit=20"
            ),
            timeout=120.0,
        )
        if restart_patch_status != 200 or not isinstance(restart_patch_payload, list):
            raise RuntimeError(
                f"Patch list after restart failed. status={restart_patch_status}",
            )
    finally:
        _stop_server(restart_process, restart_log_handle)

    result = {
        "success": True,
        "runtime_root": str(runtime_root),
        "port": port,
        "instance_id": instance_id,
        "selected_role_id": selected_role_id,
        "selected_agent_id": selected_agent_id,
        "self_check_chat_decision_status": (
            self_check_by_name.get("chat_decision_model", {}).get("status")
        ),
        "self_check_chat_decision_summary": (
            self_check_by_name.get("chat_decision_model", {}).get("summary")
        ),
        "browser_session_status": browser_session_payload.get("status"),
        "preview_goal_count": len(list((preview_payload.get("draft") or {}).get("goals") or [])),
        "acquisition_success": acquisition_payload.get("success"),
        "acquisition_proposals_processed": acquisition_payload.get("proposals_processed"),
        "acquisition_plans_materialized": acquisition_payload.get("plans_materialized"),
        "acquisition_onboarding_passed": acquisition_payload.get("onboarding_passed"),
        "success_task_id": success_turn.get("task_id"),
        "success_task_status": (
            dict(success_turn.get("task") or {}).get("status")
            if isinstance(success_turn.get("task"), dict)
            else None
        ),
        "success_screenshot": str(success_screenshot),
        "success_screenshot_exists": success_screenshot.exists(),
        "success_evidence_count": len(list(success_turn.get("evidence") or [])),
        "success_browser_summary": success_browser_summary,
        "failed_turn_count": len(failed_turns),
        "failed_task_ids": [item.get("task_id") for item in failed_turns],
        "failed_evidence_id": failed_evidence_id,
        "failed_browser_evidence_count": len(failed_browser_evidence),
        "failed_browser_evidence_ids": [
            str(item.get("id") or "").strip()
            for item in failed_browser_evidence
            if str(item.get("id") or "").strip()
        ],
        "strategy_success": strategy_payload.get("success"),
        "strategy_proposals_created": strategy_payload.get("proposals_created"),
        "strategy_patches_created": strategy_payload.get("patches_created"),
        "optimization_closure": optimization_closure,
        "patch_count_for_failed_task": len(applied_patches),
        "growth_count_for_failed_task": len(growth_items),
        "restart_patch_count_for_failed_task": len(restart_patch_payload),
        "restart_closure": restart_detail_payload.get("optimization_closure"),
        "restart_chat_decision_status": restart_self_check_by_name.get(
            "chat_decision_model",
            {},
        ).get("status"),
        "server_log": str(log_path),
        "restart_server_log": str(runtime_root / "server-restart.log"),
    }

    if result["preview_goal_count"] < 1:
        raise RuntimeError("Preview did not materialize any goals.")
    if result["acquisition_success"] is not True:
        raise RuntimeError(f"Acquisition did not succeed: {acquisition_payload}")
    if dict(result["success_browser_summary"]).get("sequence_ok") is not True:
        raise RuntimeError(
            f"Successful browser run did not complete the expected browser sequence: "
            f"{result['success_browser_summary']}",
        )
    if result["failed_browser_evidence_count"] < 2:
        raise RuntimeError(
            "Did not observe two failed browser evidence records from real prompts.",
        )
    closure_counts = dict((optimization_closure or {}).get("counts") or {})
    if int(closure_counts.get("proposals") or 0) < 1:
        raise RuntimeError(f"optimization_closure does not contain proposals: {optimization_closure}")
    if int(closure_counts.get("patches") or 0) < 1:
        raise RuntimeError(f"optimization_closure does not contain patches: {optimization_closure}")
    if int(closure_counts.get("growth") or 0) < 1:
        raise RuntimeError(f"optimization_closure does not contain growth: {optimization_closure}")
    if result["patch_count_for_failed_task"] < 1:
        raise RuntimeError("No patch was readable for the failed task after strategy automation.")
    if result["restart_patch_count_for_failed_task"] < 1:
        raise RuntimeError("Applied patches were not readable after restart.")
    return result


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    default_runtime_root = repo_root / "tmp" / "live_self_evolution_smoke"
    default_working_dir = _default_working_dir()
    default_secret_dir = _default_secret_dir(default_working_dir)

    parser = argparse.ArgumentParser(
        description="Run a real self-evolution smoke against a live CoPaw service process.",
    )
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=default_runtime_root,
        help="Isolated runtime root used for the smoke.",
    )
    parser.add_argument(
        "--source-working-dir",
        type=Path,
        default=default_working_dir,
        help="Source working dir to copy config.json from.",
    )
    parser.add_argument(
        "--source-secret-dir",
        type=Path,
        default=default_secret_dir,
        help="Source secret dir to copy providers/envs from.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Port for the live uvicorn process. Default picks a free port.",
    )
    args = parser.parse_args()
    result = _run_smoke(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
