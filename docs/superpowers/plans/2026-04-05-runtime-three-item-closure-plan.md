# Runtime Three-Item Closure Implementation Plan

**Goal:** 补齐完整任务闭环证明、收紧执行核纪律、统一 `cron / automation / workflow` 发车合同。

**Architecture:** 保留 CoPaw 现有 formal truth chain，不引入第二套真相或第二套 loop。先用真实 e2e 证明聊天前门可以闭环，再把执行核的 terminal discipline 和自动入口 launch contract 收到更小、更硬的一条主链。

**Tech Stack:** Python, FastAPI, pytest, SQLite state repositories, Runtime Center, IndustryService, Kernel turn/runtime stack.

---

## Task 1: 完整任务闭环 e2e 封板

**Files**
- `tests/app/test_runtime_canonical_flow_e2e.py`
- `src/copaw/industry/chat_writeback.py`
- `src/copaw/industry/service_lifecycle.py`
- `src/copaw/compiler/compiler.py`

**Status:** Completed

**What landed**
- 新增真实 canonical e2e：`chat/run -> writeback backlog -> assignment -> real fixed-SOP -> evidence -> terminal report`。
- `goal_metadata` 已可从 chat writeback 落进 backlog metadata。
- `work_context_id` 已贯穿 chat writeback -> compiler context -> KernelTask -> report writeback。

**Verification**
- `python -m pytest tests/app/test_runtime_canonical_flow_e2e.py -q`

---

## Task 2: 执行核阶段纪律收紧

**Files**
- `src/copaw/kernel/turn_executor.py`
- `tests/kernel/test_turn_executor.py`

**Status:** Completed

**What landed**
- `KernelTurnExecutor.handle_query(...)` 为 command/query 两条分支收口了共享 admission helper。
- terminal closeout 统一为同一套 helper，不再各分支各写一遍。
- `waiting-confirm` 不会误记 complete。
- `asyncio.CancelledError` 和“取消语义 runtime error”现在都会统一记成 `cancelled`，不再出现 UI 显示取消、内核却写 `failed` 的分叉。

**Verification**
- `python -m pytest tests/kernel/test_turn_executor.py -q`

---

## Task 3: 自动入口统一发车合同

**Files**
- `src/copaw/app/runtime_launch_contract.py`
- `src/copaw/app/runtime_lifecycle.py`
- `src/copaw/app/crons/executor.py`
- `src/copaw/kernel/query_execution_confirmation.py`
- `tests/app/test_runtime_lifecycle.py`
- `tests/app/test_cron_executor.py`

**Status:** Completed

**What landed**
- 新增共享 helper：`runtime_launch_contract.py`。
- `automation` payload 现在带统一 `entry_source` 与 durable launch fields，同时保留原有 `automation-coordinator` 字段。
- `cron` agent request 和 `request_context` 现在都带同源 durable coordinator metadata。
- workflow 既有 `workflow-run` durable coordinator contract 保持不变，并与这次共享 launch discipline 兼容。

**Verification**
- `python -m pytest tests/app/test_runtime_lifecycle.py tests/app/test_cron_executor.py tests/kernel/test_main_brain_orchestrator_roles.py -q`

---

## Mainline Verification

- `python -m pytest tests/kernel/test_turn_executor.py tests/app/test_runtime_lifecycle.py tests/app/test_cron_executor.py tests/kernel/test_main_brain_orchestrator_roles.py -q`
- `python -m pytest tests/app/test_runtime_canonical_flow_e2e.py tests/app/test_workflow_templates_api.py::test_workflow_template_service_launch_materializes_run tests/fixed_sops/test_service.py::test_fixed_sop_service_records_host_snapshot_in_run_and_evidence -q`

**Latest Result**
- `87 passed`
- `6 passed`
