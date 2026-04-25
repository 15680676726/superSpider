# 执行纪律与主链收口 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在隔离 worktree 中把执行纪律与主链收口推进到接近硬结束态，不再留下“主链已成型但执行纪律仍然松散、旧入口和旧命名仍然残留”的尾巴。

**Architecture:** 继续把所有改动压在 CoPaw 的唯一正式真相链上：`StrategyMemory -> OperatingLane -> BacklogItem -> OperatingCycle -> Assignment -> AgentReport -> Replan`。这里保留的只是执行纪律壳：熵控制、plan shell、读并发写串行、agent-scoped additive MCP cleanup；不复制外部产品前门、planner truth、session truth 或文件型记忆真相。这里的“前门收口”按 canonical ingress / contract 理解，不按物理 URL 数量理解。

**Tech Stack:** Python 3.11, FastAPI, Pydantic, pytest, existing CoPaw kernel/capabilities/environments/runtime-center services, console React frontend for focused visibility updates.

---

## 前置约束

- 本计划必须在隔离 worktree 中执行，不在当前脏根工作区直接动手。
- 每个施工包都必须先补失败测试，再写实现，再跑聚焦回归。
- 同一文件同一时刻只能有一个 owner。
- 不把 `cc/`、未跟踪文档和其他并行 agent 的改动混进本轮提交。
- 允许保留 projection-only read 层；不允许 query/projection/facade 反向承担 truth 写入。

### Task 1: 包 A - 上下文熵控制补齐

**Files:**
- Modify: `src/copaw/memory/conversation_compaction_service.py`
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Modify: `src/copaw/app/runtime_chat_stream_events.py`
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/runtime_center/overview_cards.py`
- Modify: `console/src/pages/Chat/runtimeTransport.ts`
- Modify: `console/src/pages/Chat/useChatRuntimeState.ts`
- Test: `tests/kernel/test_query_execution_runtime.py`
- Test: `tests/app/test_runtime_center_events_api.py`
- Test: `tests/app/runtime_center_api_parts/overview_governance.py`
- Test: `console/src/pages/Chat/runtimeTransport.test.ts`

- [ ] **Step 1: 写失败测试**
  增加 `tool-result budget`、大结果 spill、稳定替身、`microcompact`、`autocompact`、`tool-use summary` 的回归，覆盖普通长任务、resume、fork、回复后 commit tail 持续运行几类情况。

- [ ] **Step 2: 运行测试确认失败**
  Run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/kernel/test_query_execution_runtime.py tests/app/test_runtime_center_events_api.py tests/app/runtime_center_api_parts/overview_governance.py -q
  cmd /c npm --prefix console run test -- src/pages/Chat/runtimeTransport.test.ts
  ```
  Expected: 新增熵控制断言失败，说明当前实现还没有达到目标。

- [ ] **Step 3: 写最小实现**
  在现有 compaction/runtime shell 上补统一预算、spill、summary 和稳定替身，不引入第二套 transcript truth，并把 `summary / artifact / replay / compact state` 接成正式可见结果。

- [ ] **Step 4: 运行测试确认通过**
  重新运行同一组测试，确认新增熵控制路径全部变绿。

### Task 2: 包 B - planning shell 补齐

**Files:**
- Modify: `src/copaw/compiler/planning/models.py`
- Modify: `src/copaw/compiler/planning/assignment_planner.py`
- Modify: `src/copaw/compiler/planning/cycle_planner.py`
- Modify: `src/copaw/kernel/query_execution_shared.py`
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Modify: `src/copaw/industry/service_runtime_views.py`
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
- Modify: `console/src/pages/AgentWorkbench/useAgentWorkbench.ts`
- Test: `tests/compiler/test_cycle_planner.py`
- Test: `tests/compiler/test_report_replan_engine.py`
- Test: `tests/app/test_runtime_query_services.py`
- Test: `tests/kernel/test_query_execution_runtime.py`

- [ ] **Step 1: 写失败测试**
  增加 `plan mode / plan shell / verify reminder / resume continuity / fork continuity / assignment scratch` 回归，证明计划外壳在长任务中可见、可续跑、可复核。

- [ ] **Step 2: 运行测试确认失败**
  Run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/compiler/test_cycle_planner.py tests/compiler/test_report_replan_engine.py tests/app/test_runtime_query_services.py tests/kernel/test_query_execution_runtime.py -q
  ```
  Expected: 计划壳相关新断言失败。

- [ ] **Step 3: 写最小实现**
  让 plan shell 成为现有正式对象链的执行壳，而不是新的真相源；所有 `plan mode / plan file / todo / verify / resume / fork continuity` 都必须锚到正式 `Strategy / Cycle / Assignment / Report` 链。

- [ ] **Step 4: 运行测试确认通过**
  重新运行同一组测试，确认 plan shell 行为可见且稳定。

### Task 3: 包 C - 读并发、写串行纪律系统化

**Files:**
- Modify: `src/copaw/capabilities/execution.py`
- Modify: `src/copaw/capabilities/execution_context.py`
- Modify: `src/copaw/kernel/child_run_shell.py`
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Modify: `src/copaw/environments/lease_service.py`
- Modify: `src/copaw/environments/surface_control_service.py`
- Test: `tests/app/test_capabilities_execution.py`
- Test: `tests/capabilities/test_execution_context.py`
- Test: `tests/kernel/test_query_execution_runtime.py`
- Test: `tests/environments/test_cooperative_windows_apps.py`
- Test: `tests/environments/test_cooperative_browser_attach_runtime.py`

- [ ] **Step 1: 写失败测试**
  增加 planner/runtime/environment 共同遵守 `parallel-read -> serial-write` 的回归，覆盖 file、browser、desktop、child-run、mixed batch。

- [ ] **Step 2: 运行测试确认失败**
  Run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/app/test_capabilities_execution.py tests/capabilities/test_execution_context.py tests/kernel/test_query_execution_runtime.py tests/environments/test_cooperative_windows_apps.py tests/environments/test_cooperative_browser_attach_runtime.py -q
  ```
  Expected: 新增纪律断言失败。

- [ ] **Step 3: 写最小实现**
  统一 planner、runtime、environment 对读并发写串行的词汇、执行顺序和写 gate。

- [ ] **Step 4: 运行测试确认通过**
  重新运行同一组测试，确认 mixed batch 和 child-run 都服从统一纪律。

### Task 4: 包 D - agent-scoped additive MCP + cleanup 壳

**Files:**
- Modify: `src/copaw/app/mcp/manager.py`
- Modify: `src/copaw/app/mcp/runtime_contract.py`
- Modify: `src/copaw/capabilities/mcp_registry.py`
- Modify: `src/copaw/capabilities/catalog.py`
- Modify: `src/copaw/capabilities/service.py`
- Modify: `src/copaw/kernel/child_run_shell.py`
- Modify: `src/copaw/kernel/delegation_service.py`
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Test: `tests/app/test_mcp_runtime_contract.py`
- Test: `tests/app/test_capability_catalog.py`
- Test: `tests/app/test_runtime_center_api.py`
- Test: `tests/kernel/test_query_execution_runtime.py`

- [ ] **Step 1: 写失败测试**
  增加 worker/child-run 的增量 MCP 挂载、失败清理、取消清理、abort 清理、父子边界隔离回归。

- [ ] **Step 2: 运行测试确认失败**
  Run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/app/test_mcp_runtime_contract.py tests/app/test_capability_catalog.py tests/app/test_runtime_center_api.py tests/kernel/test_query_execution_runtime.py -q
  ```
  Expected: 新增 additive MCP cleanup 断言失败。

- [ ] **Step 3: 写最小实现**
  让 agent 级增量 mount 有正式来源、正式回收、正式读面，不污染父级和全局。

- [ ] **Step 4: 运行测试确认通过**
  重新运行同一组测试，确认成功、失败、取消、abort 都可回收。

### Task 5: 包 E - 主链收口、命名统一、重复逻辑归并

**Files:**
- Modify: `src/copaw/app/routers/runtime_center_routes_core.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_overview.py`
- Modify: `src/copaw/app/routers/runtime_center_shared.py`
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/runtime_center/task_list_projection.py`
- Modify: `src/copaw/app/runtime_center/work_context_projection.py`
- Modify: `src/copaw/industry/service_runtime_views.py`
- Modify: `src/copaw/kernel/agent_profile_service.py`
- Modify: `console/src/pages/AgentWorkbench/useAgentWorkbench.ts`
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.ts`
- Test: `tests/app/test_runtime_center_router_split.py`
- Test: `tests/app/test_runtime_query_services.py`
- Test: `tests/kernel/test_agent_profile_service.py`
- Test: `console/src/pages/AgentWorkbench/useAgentWorkbench.test.tsx`

- [ ] **Step 1: 写失败测试**
  增加旧前门阻断、`current_focus` 统一、重复 projection/fallback 归并、路径压短后的读面稳定性回归。

- [ ] **Step 2: 运行测试确认失败**
  Run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/app/test_runtime_center_router_split.py tests/app/test_runtime_query_services.py tests/kernel/test_agent_profile_service.py -q
  cmd /c npm --prefix console run test -- src/pages/AgentWorkbench/useAgentWorkbench.test.tsx
  ```
  Expected: 新增主链收口断言失败。

- [ ] **Step 3: 写最小实现**
  删除旧前门、统一命名、归并重复逻辑、压短路由到真相源的路径；保留必要 projection/facade/read collaborator，但阻断它们的旁路写入能力。

- [ ] **Step 4: 运行测试确认通过**
  重新运行同一组测试，确认旧口径被阻断且新主链稳定。

### Task 6: 包 F - 可见化、删除账本、文档与全矩阵验收

**Files:**
- Modify: `TASK_STATUS.md`
- Modify: `API_TRANSITION_MAP.md`
- Modify: `docs/2026-04-02-current-system-construction-blueprint.md`
- Modify: `docs/superpowers/specs/2026-04-03-execution-discipline-and-mainline-closure-design.md`
- Create: `DEPRECATION_LEDGER.md`
- Modify: `src/copaw/app/runtime_center/overview_cards.py`
- Modify: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.tsx`
- Modify: `console/src/pages/RuntimeCenter/text.ts`
- Test: `tests/app/runtime_center_api_parts/overview_governance.py`
- Test: `tests/app/test_runtime_center_events_api.py`
- Test: `console/src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx`

- [ ] **Step 1: 写失败测试**
  增加运行中心可见化与删除账本读面相关回归，确保 compact、plan、focus、risk、evidence、environment、mount、MCP 状态都能被看见，并且旧入口写入、query 偷写、fallback 旁路旧状态这几类断层会直接红。

- [ ] **Step 2: 运行测试确认失败**
  Run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_runtime_center_events_api.py -q
  cmd /c npm --prefix console run test -- src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx
  ```
  Expected: 新增可见化和账本断言失败。

- [ ] **Step 3: 写最小实现**
  补齐可见化、同步文档、建立删除账本，并确保文档与代码不打架。

- [ ] **Step 4: 运行测试确认通过**
  重新运行同一组测试，确认运行中心和文档链路闭合。

## 最终验证

**Files:**
- Verify only; no new files

- [ ] **Step 1: 跑执行纪律聚焦矩阵**
  Run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/kernel/test_query_execution_runtime.py tests/app/test_capabilities_execution.py tests/capabilities/test_execution_context.py tests/app/test_mcp_runtime_contract.py tests/app/test_capability_catalog.py -q
  ```

- [ ] **Step 2: 跑主链收口聚焦矩阵**
  Run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/compiler/test_cycle_planner.py tests/compiler/test_report_replan_engine.py tests/app/test_runtime_query_services.py tests/app/test_runtime_center_router_split.py tests/kernel/test_agent_profile_service.py tests/industry/test_report_synthesis.py -q
  ```

- [ ] **Step 3: 跑环境与运行中心聚焦矩阵**
  Run:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/environments/test_cooperative_windows_apps.py tests/environments/test_cooperative_browser_attach_runtime.py tests/app/runtime_center_api_parts/overview_governance.py tests/app/test_runtime_center_events_api.py tests/app/test_operator_runtime_e2e.py -q
  ```

- [ ] **Step 4: 跑前端聚焦矩阵**
  Run:
  ```powershell
  cmd /c npm --prefix console run test -- src/pages/Chat/runtimeTransport.test.ts src/pages/AgentWorkbench/useAgentWorkbench.test.tsx src/pages/RuntimeCenter/MainBrainCockpitPanel.test.tsx
  ```

- [ ] **Step 5: 运行差异检查**
  Run:
  ```powershell
  git diff --check
  ```

- [ ] **Step 6: 按施工包分提交**
  至少拆成：
  - `feat: harden runtime entropy shell`
  - `feat: add planning shell continuity`
  - `feat: enforce parallel-read serial-write discipline`
  - `feat: add agent-scoped additive mcp cleanup`
  - `refactor: close remaining runtime front-door and naming tails`
  - `docs: sync deprecation ledger and runtime visibility`
