# P0 Runtime Terminal Closure Program Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按固定顺序完成 P0 终态收口程序，并立即开始 `P0-1 宿主真相统一` 的第一批实现。

**Architecture:** 先把程序拆成 5 个顺序 gate，再把 `P0-1` 压缩成一批共享 helper 收口任务。第一批不做大面积 UI 改版，不做长跑 smoke 扩面，只解决 `workflow / cron / fixed-SOP / runtime` 继续各自解析 canonical host truth 的问题。

**Tech Stack:** Python 3.11, FastAPI, Pydantic, Pytest, TypeScript/React read surfaces, SQLite state repositories.

---

## Program Sequence

### P0-1 宿主真相统一

当前轮必须先完成：

- `host_snapshot / host_preflight / host_twin_summary / coordination / scheduler_inputs` 的共享 canonical 解析
- `workflow / cron / fixed-SOP / Runtime Center / industry runtime` 的 host truth 同口径
- `selected_seat_ref / selected_session_mount_id / environment_ref / environment_id / legal_recovery` 的 shared contract

### P0-2 单行业长跑闭环

在 `P0-1` 通过后推进：

- `staffing -> handoff -> human assist -> report -> synthesis -> replan`
- multi-cycle continuity
- supervisor / manager / researcher / operator 长跑协作不掉线

### P0-3 主脑驾驶舱

在 `P0-2` 通过后推进：

- Runtime Center cockpit 化
- 主脑对象、执行对象、证据对象、治理对象同一视图

### P0-4 宽回归与 live smoke

在 `P0-3` 通过后推进：

- 长跑 smoke
- 组合回归
- 发布门槛
- 正式 gate 入口：`python scripts/run_p0_runtime_terminal_gate.py`

### P0-5 持续删旧

贯穿全程，但最终要单独关账：

- 删除旧入口
- 删除旧主脑心智
- 删除 compat 分支
- 同步文档、测试、前端、路由

---

## Immediate Slice: P0-1 Batch 1

### Task 1: 落总设计文档

**Files:**
- Create: `docs/superpowers/specs/2026-03-31-p0-runtime-terminal-closure-program.md`

- [ ] **Step 1: 写程序级总设计**
- [ ] **Step 2: 保存到 spec 路径**

### Task 2: 写程序级实施计划

**Files:**
- Create: `docs/superpowers/plans/2026-03-31-p0-runtime-terminal-closure-program.md`

- [ ] **Step 1: 写顺序 gate、完成定义和 immediate slice**
- [ ] **Step 2: 保存到 plan 路径**

### Task 3: 为 canonical host identity 共享 helper 写失败测试

**Files:**
- Modify: `tests/app/test_runtime_projection_contracts.py`

- [ ] **Step 1: 增加 helper 级失败测试**

```python
def test_resolve_canonical_host_identity_prefers_scheduler_inputs_environment_ref():
    ...

def test_resolve_canonical_host_identity_falls_back_to_host_environment_ref():
    ...
```

- [ ] **Step 2: 运行目标测试确认红灯**

Run: `python -m pytest tests/app/test_runtime_projection_contracts.py -k canonical_host_identity -q`

Expected: FAIL

### Task 4: 为 workflow run preview request 写失败测试

**Files:**
- Modify: `tests/app/test_workflow_templates_api.py`

- [ ] **Step 1: 增加一个失败测试，锁住 `_build_run_preview_request(...)` 在只有 `environment_ref` 时也必须读到 canonical host truth**
- [ ] **Step 2: 运行目标测试确认红灯**

Run: `python -m pytest tests/app/test_workflow_templates_api.py -k run_preview_request_environment_ref -q`

Expected: FAIL

### Task 5: 为 cron canonical host meta 写失败测试

**Files:**
- Modify: `tests/app/test_cron_executor.py`

- [ ] **Step 1: 增加一个失败测试，锁住 cron meta 必须带 canonical `environment_id`，不只带 `environment_ref`**
- [ ] **Step 2: 运行目标测试确认红灯**

Run: `python -m pytest tests/app/test_cron_executor.py -k canonical_environment_id -q`

Expected: FAIL

### Task 6: 为 fixed-SOP canonical host context 写失败测试

**Files:**
- Modify: `tests/fixed_sops/test_service.py`

- [ ] **Step 1: 增加一个失败测试，锁住 fixed-SOP host context 在只有 `environment_ref` / selected seat 时也必须 canonicalize 出 environment/session**
- [ ] **Step 2: 运行目标测试确认红灯**

Run: `python -m pytest tests/fixed_sops/test_service.py -k canonicalize_host_context -q`

Expected: FAIL

### Task 7: 实现共享 canonical host identity helper

**Files:**
- Modify: `src/copaw/app/runtime_center/task_review_projection.py`

- [ ] **Step 1: 新增共享 helper**

```python
def resolve_canonical_host_identity(
    host_payload: dict[str, object] | None,
    *,
    metadata: dict[str, object] | None = None,
    fallback_environment_ref: str | None = None,
    fallback_environment_id: str | None = None,
    fallback_session_mount_id: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    ...
```

- [ ] **Step 2: 让 helper 对 `scheduler_inputs -> host_twin_summary -> coordination -> payload -> metadata -> fallback` 用单一优先级**
- [ ] **Step 3: 回跑 helper 目标测试**

Run: `python -m pytest tests/app/test_runtime_projection_contracts.py -k canonical_host_identity -q`

Expected: PASS

### Task 8: 让 workflow / cron / fixed-SOP 复用共享 helper

**Files:**
- Modify: `src/copaw/workflows/service_preview.py`
- Modify: `src/copaw/workflows/service_runs.py`
- Modify: `src/copaw/app/crons/executor.py`
- Modify: `src/copaw/sop_kernel/service.py`

- [ ] **Step 1: `service_preview._build_run_preview_request(...)` 改走共享 helper**
- [ ] **Step 2: `service_runs._resolve_host_identity_from_snapshot(...)` 改走共享 helper**
- [ ] **Step 3: `CronExecutor._host_meta(...)` 改走共享 helper，并补 canonical `environment_id`**
- [ ] **Step 4: `FixedSopService._canonicalize_host_context(...)` 改走共享 helper**
- [ ] **Step 5: 回跑各自目标测试**

Run:
`python -m pytest tests/app/test_workflow_templates_api.py -k run_preview_request_environment_ref -q`

`python -m pytest tests/app/test_cron_executor.py -k canonical_environment_id -q`

`python -m pytest tests/fixed_sops/test_service.py -k canonicalize_host_context -q`

Expected: PASS

### Task 9: 做第一轮聚合验证

**Files:**
- Modify: touched files above

- [ ] **Step 1: 跑聚合 Python 回归**

Run:
`python -m pytest tests/app/test_runtime_projection_contracts.py tests/app/test_workflow_templates_api.py tests/app/test_cron_executor.py tests/fixed_sops/test_service.py -q`

Expected: PASS

- [ ] **Step 2: 只在上述通过后，继续下一批 P0-1 工作**

### Task 10: 分批提交

**Files:**
- Modify: staged implementation files

- [ ] **Step 1: 提交文档**
- [ ] **Step 2: 提交 helper + consumer 收口**
- [ ] **Step 3: 提交测试**
