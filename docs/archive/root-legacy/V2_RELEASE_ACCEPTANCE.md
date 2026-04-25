# V2_RELEASE_ACCEPTANCE.md

本文件记录 `implementation_plan.md` 中 `V2-B1 ~ V2-B5` 的正式收口结果。

完成日期：`2026-03-12`

---

## 1. 结论

`V2` 当前已真实完成，可作为“长期自治运营版”进入后续 `V3` 产品化阶段。

这次完成指的是：

- `V2-B1`：知识库、长期记忆、执行前 retrieve 注入、知识来源回溯已接入正式主链
- `V2-B2`：reports / performance 已进入正式对象与页面
- `V2-B3`：委派写路径、`parent/child task` 层级、child result 回流读面已接通
- `V2-B4`：环境恢复、startup recovery、direct replay executor / fallback kernel replay、session lease force-release 已形成正式验收链
- `V2-B5`：前端 build、operator E2E、approval / rollback / recovery 扩面、文档与删旧台账已同步

这次完成不包含：

- 删除旧 `runner / config / old routers / old console grouping`
- `AgentRunner` 最终退役
- legacy `bridge` alias/header 最终删除

上述删尾仍属于 `implementation_plan.md` 的 `V3-B4`，不是 `V2` 交付物。

---

## 2. 范围对应

### `V2-B1` 知识库与记忆层

- 正式对象：`KnowledgeChunkRecord`
- 正式服务：`src/copaw/state/knowledge_service.py`
- 执行接入：
  - `src/copaw/goals/service.py`
  - `src/copaw/compiler/compiler.py`
  - `src/copaw/kernel/query_execution.py`
- 产品/API：
  - `/api/runtime-center/knowledge*`
  - `console/src/pages/Knowledge/index.tsx`
- 当前能力：
  - knowledge import / split / retrieve
  - `memory:{scope_type}:{scope_id}` 长期记忆文档
  - compile / task seed / query execution 前的知识与记忆注入
  - task detail 中的 knowledge refs / memory refs / document trace

### `V2-B2` 报告中心与经营指标

- 正式对象：`MetricRecord`、`ReportRecord`
- 正式服务：`src/copaw/state/reporting_service.py`
- 产品/API：
  - `/api/runtime-center/reports`
  - `/api/runtime-center/performance`
  - `console/src/pages/Reports/index.tsx`
  - `console/src/pages/Performance/index.tsx`
- 当前能力：
  - evidence-driven daily / weekly / monthly report
  - metrics formula / source summary 可追溯
  - Reports / Performance 页面直接消费统一真相源

### `V2-B3` 长期节奏与多 Agent 协作

- 正式对象补充：`Task.parent_task_id`
- 正式服务：`src/copaw/kernel/delegation_service.py`
- 产品/API：
  - `/api/runtime-center/tasks/{task_id}/delegate`
  - `/api/runtime-center/tasks/{id}` delegation detail
  - `console/src/pages/Calendar/index.tsx`
- 当前能力：
  - Manager 可写入真实 child task
  - environment 冲突与 agent 过载具备最小治理检查
  - child task 状态计数、完成率、结果回流已进入 Runtime Center detail

### `V2-B4` 环境宿主深化

- 正式能力：
  - `run_startup_recovery()`
  - `/api/runtime-center/recovery/latest`
  - `/api/runtime-center/replays/{id}/execute`
  - `/api/runtime-center/sessions/{id}/lease/force-release`
  - direct replay executor / fallback kernel replay
- 当前边界：
  - startup recovery、异常恢复、手动 replay 都有正式入口
  - session / replay / recovery detail 已进入 Runtime Center
  - `EnvironmentMount / SessionMount` 的 recovery 与 replay_support 已成为正式运行元数据

### `V2-B5` 发布硬化与真实世界验收

- 正式前端入口：
  - `/industry`
  - `/knowledge`
  - `/reports`
  - `/performance`
  - `/calendar`
  - `/runtime-center`
- 正式文档：
  - 本文件 `V2_RELEASE_ACCEPTANCE.md`
  - `TASK_STATUS.md`
  - `DATA_MODEL_DRAFT.md`
  - `DEPRECATION_LEDGER.md`

---

## 3. 验证记录

以下命令已在 `2026-03-12` 实际执行通过：

```powershell
cmd.exe /c npm --prefix console run build
```

结果：前端生产构建通过，`Industry / Knowledge / Reports / Performance / Calendar / Runtime Center` 当前可一起编译。

```powershell
python -m pytest tests/app/test_runtime_center_api.py tests/app/test_runtime_center_task_hierarchy_api.py tests/app/test_industry_api.py tests/state/test_reporting_service.py tests/app/test_runtime_center_reporting_api.py tests/state/test_knowledge_service.py tests/app/test_runtime_center_knowledge_api.py tests/app/test_goals_api.py tests/kernel/test_query_execution_environment.py tests/app/test_runtime_center_task_delegation_api.py -q
```

结果：`41 passed`

```powershell
python -m pytest tests/environments/test_environment_registry.py tests/app/test_startup_recovery.py tests/app/test_runtime_center_events_api.py tests/app/test_operator_runtime_e2e.py tests/app/test_learning_api.py tests/providers/test_live_provider_smoke.py -q
```

结果：`27 passed, 1 skipped`

补充说明：

- skip 项来自 `tests/providers/test_live_provider_smoke.py`
- 该 smoke harness 已存在且纳入验收矩阵，但默认需要显式设置 `COPAW_RUN_LIVE_PROVIDER_SMOKE=1` 才会命中真实 provider
- 因此 `V2-B5` 的当前结论是“live smoke harness 已扩面并受环境门控”，不是“默认离线回归会触发真实 provider”

---

## 4. 风险边界

当前剩余风险不再属于 `V2` 未完成，而是下一版工作：

- `AgentRunner` 仍是薄适配壳，最终删除条件在 `V3-B4`
- 部分 old routers / legacy alias / old console grouping 仍存在，删除窗口在 `V3-B4`
- live provider smoke 默认仍是 opt-in，而不是所有 CI/本地回归默认执行

只要后续文档继续保持这个边界，`V2` 就不应再被回滚为“未完成”。
