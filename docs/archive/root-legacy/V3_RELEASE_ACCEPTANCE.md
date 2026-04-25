# V3_RELEASE_ACCEPTANCE.md

本文件记录 `implementation_plan.md` 中 `V3-B1 ~ V3-B4` 的正式收口结果。

它不是新的产品规划，也不是新的开发任务单，而是：

1. `V3` 产品化与规模化阶段的正式验收记录
2. 自动化回归、前端构建、删尾完成情况的落地证据
3. `V3` 是否可以作为当前稳定基线进入 `V4` 的放行依据

---

## 0. 当前放行结论

截至 `2026-03-12`，当前代码状态可以定义为：

- `V3 accepted`

当前已满足的前提：

- `Capability Market` 已成为正式能力集成入口，前端当前读写已统一切到 `/api/capability-market/*` canonical surface
- `Runtime Center` 已具备 `overview / governance / recovery / automation` 四个正式工作面
- `/settings/system` 已承接启动恢复、自检、备份恢复、provider fallback 与 runtime route 暴露
- `AgentRunner` 与 runtime-center `bridge` 旧壳已真实退役
- 自动化验收、全量回归与前端构建已重跑通过

---

## 1. 范围对应

### `V3-B1` 能力市场

- 正式 router：`src/copaw/app/routers/capability_market.py`
- 正式产品/API：
  - `/api/capability-market/overview`
  - `/api/capability-market/capabilities`
  - `/api/capability-market/capabilities/summary`
  - `/api/capability-market/skills`
  - `/api/capability-market/mcp`
  - `/api/capability-market/hub/search`
  - `/api/capability-market/hub/install`
  - `/api/capability-market/capabilities/{id}/toggle`
  - `/api/capability-market/capabilities/{id}`
  - `console/src/pages/CapabilityMarket/index.tsx`
  - `console/src/api/modules/capabilityMarket.ts`
- 当前边界：
  - 旧独立前端入口 `/capabilities`、`/skills`、`/mcp` 已降级为 redirect/compat entry
  - `/api/skills` 与 `/api/mcp` 仍作为 legacy/compat 管理 API 保留，不再承担正式产品入口
  - `/api/capabilities` 保留为统一 capability service / execute contract，不再承担 Capability Market 的产品写面
  - `skills/mcp` 旧 router 的删除条件是：legacy 客户端迁移完成、skill file/load 等剩余兼容能力找到归宿，并补齐等价自动化回归

### `V3-B2` 治理中心终态

- 正式 router：
  - `src/copaw/app/routers/runtime_center.py`
- 正式产品/API：
  - `/api/runtime-center/governance/status`
  - `/api/runtime-center/governance/emergency-stop`
  - `/api/runtime-center/governance/resume`
  - `/api/runtime-center/governance/decisions/*`
  - `/api/runtime-center/governance/patches/*`
  - `console/src/pages/RuntimeCenter/index.tsx`
- 当前能力：
  - 批量审批
  - patch approve / reject / apply / rollback
  - emergency stop / resume
  - recovery / self-check / automation 正式工作面

### `V3-B3` 备份恢复与产品交付

- 正式能力：
  - `src/copaw/app/startup_recovery.py`
  - `src/copaw/app/routers/system.py`
  - `src/copaw/providers/provider_manager.py`
- 正式产品/API：
  - `/api/system/overview`
  - `/api/system/self-check`
  - `/api/system/backup/download`
  - `/api/system/backup/restore`
  - `/api/runtime-center/recovery/latest`
  - `console/src/pages/Settings/System/index.tsx`
- 当前能力：
  - startup recovery summary
  - system self-check
  - provider fallback
  - backup download / restore 正式入口

### `V3-B4` 最终删尾与规模化收口

- 已删除：
  - `src/copaw/app/runner/runner.py`
  - `src/copaw/app/runtime_center/bridge.py`
- 已移除：
  - `RuntimeOverviewResponse.bridge`
  - `X-CoPaw-Bridge-*`
  - 前端 `data?.bridge`
  - runtime-center bridge fallback
- 当前宿主组合：
  - `_app.py` 直接装配 `RuntimeHost + KernelQueryExecutionService + KernelTurnExecutor`

---

## 2. 验证记录

以下命令已在 `2026-03-12` 实际执行通过：

```powershell
python -m pytest tests/app/test_system_api.py tests/app/test_capability_market_api.py tests/app/test_runtime_center_api.py tests/app/test_runtime_center_events_api.py tests/providers/test_provider_manager.py tests/app/test_models_api.py tests/kernel/test_turn_executor.py tests/test_mcp_resilience.py -q
```

结果：`58 passed`

补充说明：

- 本轮已把 `/system/backup/download` 与 `/system/backup/restore` 纳入 `tests/app/test_system_api.py`
- 本轮已把 Capability Market canonical read/write surface 纳入 `tests/app/test_capability_market_api.py` 与 `tests/app/test_capabilities_write_api.py`

```powershell
python -m pytest -q
```

结果：`331 passed, 1 skipped`

补充说明：

- `pyproject.toml` 已显式限定 `pytest` 默认收集范围为 `tests/`，避免仓库 `tmp/` 下的外部样例/虚拟环境污染全量回归结果

```powershell
cmd.exe /c npm --prefix console run build
```

结果：前端生产构建通过，`CapabilityMarket / RuntimeCenter / Settings/System` 与既有页面当前可一起编译。

---

## 3. 风险边界

当前剩余边界不再属于 `V3` 主链未落地，但需要在后续阶段明确处理：

- `/api/skills` 与 `/api/mcp` 仍是 legacy/compat API；它们不是“只剩 redirect”，不能在未迁移 legacy 客户端与 skill file/load 辅助面的前提下直接删除
- `/api/capabilities` 仍是统一 capability service / execute contract；它不是需要跟 `/skills`、`/mcp` 一起退役的同类遗留接口
- live provider smoke 仍是 opt-in，不属于默认离线回归
- console build 通过，但仍存在大体积 chunk 告警，这属于后续前端性能治理，不构成 `V3` blocker
