# Chat-First Human Assist Tasks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land `HumanAssistTask` as a formal chat-first runtime feature for blocked-by-proof or human-owned steps, with evidence-backed acceptance and resume.

**Architecture:** Add a dedicated `HumanAssistTaskRecord` truth object plus repository/service/query layers, then thread it through Runtime Center conversation surfaces and the existing `/api/runtime-center/chat/run` execution front door. Verification must read formal runtime/evidence/environment facts and emit resume-ready outcomes instead of relying on prompt-only wording.

**Tech Stack:** Python, FastAPI, Pydantic, SQLite state repositories, existing runtime/evidence services, pytest

---

## File Map

- Create: `src/copaw/state/human_assist_task_service.py`
- Create: `src/copaw/state/repositories/sqlite_human_assist_tasks.py`
- Create: `tests/state/test_human_assist_task_service.py`
- Create: `tests/app/test_runtime_human_assist_tasks_api.py`
- Modify: `src/copaw/state/models_core.py`
- Modify: `src/copaw/state/models_goals_tasks.py`
- Modify: `src/copaw/state/models.py`
- Modify: `src/copaw/state/store.py`
- Modify: `src/copaw/state/repositories/base.py`
- Modify: `src/copaw/state/repositories/sqlite.py`
- Modify: `src/copaw/state/repositories/__init__.py`
- Modify: `src/copaw/app/runtime_bootstrap_models.py`
- Modify: `src/copaw/app/runtime_bootstrap_repositories.py`
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/runtime_center/conversations.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_core.py`
- Modify: `tests/state/test_sqlite_repositories.py`
- Modify: `tests/app/test_runtime_query_services.py`
- Modify: `tests/app/test_runtime_conversations_api.py`
- Modify: `TASK_STATUS.md`

## Task 1: Add the formal state object and schema

**Files:**
- Modify: `src/copaw/state/models_core.py`
- Modify: `src/copaw/state/models_goals_tasks.py`
- Modify: `src/copaw/state/models.py`
- Modify: `src/copaw/state/store.py`
- Modify: `tests/state/test_sqlite_repositories.py`

- [ ] Write a failing repository round-trip test for `HumanAssistTaskRecord` creation, status update, list filtering, and delete.
- [ ] Run: `python -m pytest tests/state/test_sqlite_repositories.py -q`
- [ ] Add `HumanAssistTaskStatus` and `HumanAssistTaskAcceptanceMode` literals.
- [ ] Add `HumanAssistTaskRecord` with issue/submission/verification/reward fields and JSON-compatible acceptance/evidence payloads.
- [ ] Add the SQLite table and indexes in `state/store.py`.
- [ ] Re-run: `python -m pytest tests/state/test_sqlite_repositories.py -q`

## Task 2: Add repository and state service

**Files:**
- Create: `src/copaw/state/repositories/sqlite_human_assist_tasks.py`
- Modify: `src/copaw/state/repositories/base.py`
- Modify: `src/copaw/state/repositories/sqlite.py`
- Modify: `src/copaw/state/repositories/__init__.py`
- Create: `src/copaw/state/human_assist_task_service.py`
- Create: `tests/state/test_human_assist_task_service.py`

- [ ] Write failing tests for issue, submit, verify-accept, verify-reject, and current-thread lookup behavior.
- [ ] Run: `python -m pytest tests/state/test_human_assist_task_service.py -q`
- [ ] Implement the base repository contract and SQLite repository.
- [ ] Implement `HumanAssistTaskService` for issuing tasks, recording submissions, verifying against acceptance specs, and queuing resume metadata.
- [ ] Re-run: `python -m pytest tests/state/test_human_assist_task_service.py tests/state/test_sqlite_repositories.py -q`

## Task 3: Wire runtime bootstrap and query surfaces

**Files:**
- Modify: `src/copaw/app/runtime_bootstrap_models.py`
- Modify: `src/copaw/app/runtime_bootstrap_repositories.py`
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Create: `tests/app/test_runtime_human_assist_tasks_api.py`
- Modify: `tests/app/test_runtime_query_services.py`

- [ ] Write failing tests for current active task lookup, history listing, and task detail serialization on the Runtime Center read side.
- [ ] Run: `python -m pytest tests/app/test_runtime_query_services.py tests/app/test_runtime_human_assist_tasks_api.py -q`
- [ ] Register the repository/service in runtime bootstrap and expose it through `RuntimeRepositories` / domain services.
- [ ] Add read-side query methods for current chat task, thread task history, and detail payloads including rewards and verification state.
- [ ] Re-run: `python -m pytest tests/app/test_runtime_query_services.py tests/app/test_runtime_human_assist_tasks_api.py -q`

## Task 4: Enrich conversation facade and chat read model

**Files:**
- Modify: `src/copaw/app/runtime_center/conversations.py`
- Modify: `tests/app/test_runtime_conversations_api.py`

- [ ] Write failing tests proving a control thread can expose current human assist task metadata in conversation payloads without introducing a second thread type.
- [ ] Run: `python -m pytest tests/app/test_runtime_conversations_api.py -q`
- [ ] Extend conversation metadata to return the current task strip payload and task-list navigation data.
- [ ] Keep `industry-chat:*` as the only foreground control thread and reject any design that revives `task-chat:*`.
- [ ] Re-run: `python -m pytest tests/app/test_runtime_conversations_api.py tests/app/test_runtime_query_services.py -q`

## Task 5: Add chat submission and automatic verification flow

**Files:**
- Modify: `src/copaw/app/routers/runtime_center_routes_core.py`
- Modify: `src/copaw/state/human_assist_task_service.py`
- Modify: `tests/app/test_runtime_human_assist_tasks_api.py`

- [ ] Write failing API tests for host submission through `/api/runtime-center/chat/run`, auto-verification, accepted/rejected outcomes, and resume-queued projection.
- [ ] Run: `python -m pytest tests/app/test_runtime_human_assist_tasks_api.py -q`
- [ ] Detect active `HumanAssistTask` submissions in the chat front door before normal orchestration continues.
- [ ] Route "I finished it" style turns into formal submission + verification, not direct success.
- [ ] Emit response payloads/messages for `verifying / accepted / rejected / need_more_evidence`.
- [ ] Re-run: `python -m pytest tests/app/test_runtime_human_assist_tasks_api.py tests/app/test_runtime_conversations_api.py -q`

## Task 6: Close docs/status loop and verify the slice

**Files:**
- Modify: `TASK_STATUS.md`

- [ ] Update `TASK_STATUS.md` with the landed `HumanAssistTask` baseline and the next remaining gaps after implementation.
- [ ] Run the focused backend acceptance slice:

```bash
python -m pytest tests/state/test_sqlite_repositories.py tests/state/test_human_assist_task_service.py tests/app/test_runtime_query_services.py tests/app/test_runtime_conversations_api.py tests/app/test_runtime_human_assist_tasks_api.py -q
```

- [ ] Run a broader regression over the chat/runtime/state chain:

```bash
python -m pytest tests/kernel/test_main_brain_chat_service.py tests/kernel/test_turn_executor.py tests/app/test_runtime_center_api.py tests/app/test_runtime_conversations_api.py tests/app/test_runtime_query_services.py -q
```
