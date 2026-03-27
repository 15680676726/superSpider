# PHASE5_ACCEPTANCE.md

本文件用于收敛当前剩余的 3 类尾项验收：

1. `Phase1RuntimeBridge` 删除验收与 post-bridge 行为确认
2. operator / manual E2E
3. 真实 provider / environment 覆盖

---

## 1. 自动化验收入口

### 1.1 `Phase1RuntimeBridge` 删除验收与统一状态面

运行：

```bash
python -m pytest \
  tests/app/test_chat_manager.py \
  tests/app/test_cron_manager.py \
  tests/app/test_chat_state_repo.py \
  tests/app/test_cron_state_repo.py \
  tests/app/test_runtime_query_services.py -q
```

验收目标：

- `ChatManager / CronManager` 不再依赖 `Phase1RuntimeBridge` shadow-sync hook
- chat / schedule 的正式读写面只剩 state-backed repository
- Runtime Center 查询服务直接读取正式 `state / evidence / decision`

### 1.2 Operator E2E

运行：

```bash
python -m pytest \
  tests/app/test_operator_runtime_e2e.py \
  tests/app/test_goals_api.py \
  tests/app/test_capabilities_execution.py \
  tests/app/test_runtime_center_api.py -q
```

验收目标：

- `Goal -> compile -> dispatch -> Runtime Center detail` 串成一条 operator 可见链
- confirm-risk capability 能经过 `DecisionRequest -> approve/reject -> execute/cancel`
- learning `patch / growth` 能反哺下一轮 compile
- `2026-03-19` 起 `tests/app/test_operator_runtime_e2e.py` 已补齐：
  - `review -> reject -> runtime-center task/decision/evidence/overview`
  - 真实 `session lease force-release + recovery/latest`

### 1.3 Environment 执行链路

运行：

```bash
python -m pytest \
  tests/kernel/test_query_execution_environment.py \
  tests/environments/test_environment_registry.py \
  tests/app/test_startup_recovery.py -q
```

验收目标：

- `KernelQueryExecutionService` 真正触发 `acquire -> heartbeat -> release`
- `SessionMount.lease_status / live_handle_ref` 在执行前后符合预期
- same-host 但 different-process 的 lease 不会再在普通 Runtime Center 读面里被误判为 orphan
- 跨进程接管只允许在显式 `startup recovery` 中发生
- `/api/runtime-center/sessions/{id}` 会暴露 `same_host / same_process / startup_recovery_required`

---

## 2. 手工 Operator 验收清单

建议在本地启动完整服务后执行。

### 2.1 Goal / Runtime Center

1. 创建一个 `active` goal
2. 调用 `POST /api/goals/{id}/compile`
3. 调用 `POST /api/goals/{id}/dispatch`
4. 打开 Runtime Center，确认：
   - overview 能看到 goal / task / patch / growth 卡片
   - goal detail 能继续深链到 task / patch / growth / evidence

### 2.2 Decision 治理

1. 调用一个 `confirm` 风险的 capability
2. 在 Runtime Center 打开 decision detail
3. 分别执行 approve / reject
4. 验证 task detail / decision detail / evidence / overview 同步更新

### 2.3 Environment

1. 发起一次真实 `/api/agent/process` 或 `system:dispatch_query`
2. 执行过程中查看：
   - `/api/runtime-center/sessions`
   - `/api/runtime-center/environments`
3. 验证执行中 lease 为 `leased`
4. 验证执行完成后变为 `released` 且 `live_handle_ref` 被回收
5. 对运行中的 session 执行 `/api/runtime-center/sessions/{id}/lease/force-release`
6. 再查看 `/api/runtime-center/recovery/latest` 与 session detail，确认人工治理动作已可见

---

## 3. Live Provider Smoke

默认自动化不访问真实外部 provider。

如需运行 live smoke：

```bash
set COPAW_RUN_LIVE_PROVIDER_SMOKE=1
set COPAW_LIVE_PROVIDER_IDS=openai,anthropic,ollama
set COPAW_LIVE_PROVIDER_MODEL_OPENAI=gpt-5-mini
set COPAW_LIVE_PROVIDER_MODEL_ANTHROPIC=claude-3-5-haiku
set COPAW_LIVE_PROVIDER_MODEL_OLLAMA=qwen2:7b
set COPAW_LIVE_PROVIDER_GENERATION_TIMEOUT_SECONDS=45
python -m pytest tests/providers/test_live_provider_smoke.py -q
```

规则：

- `COPAW_LIVE_PROVIDER_IDS` 为逗号分隔的 provider id 列表
- 某 provider 若不能稳定返回 model list，必须显式提供对应 `COPAW_LIVE_PROVIDER_MODEL_*`
- smoke 不只做 SDK 握手，还会经 `ProviderManager.build_chat_model_for_slot()` 做一轮最小真实生成，要求返回包含 `COPAW_PROVIDER_SMOKE_OK` 的非空回答
- 如需更细控制，可额外设置：
  - `COPAW_LIVE_PROVIDER_CONNECTION_TIMEOUT_SECONDS`
  - `COPAW_LIVE_PROVIDER_DISCOVER_TIMEOUT_SECONDS`
  - `COPAW_LIVE_PROVIDER_MODEL_TIMEOUT_SECONDS`
  - `COPAW_LIVE_PROVIDER_GENERATION_TIMEOUT_SECONDS`
- live smoke 失败优先视为真实外部依赖覆盖不足，不应回退成“本地假闭环已通过”

---

## 4. 当前覆盖结论

- `Phase1RuntimeBridge`：生产路径已删除，自动化已覆盖 post-bridge 行为；后续剩余工作是更深的真实世界 smoke 与更深删旧，不再是 bridge 主链本身
- operator E2E：当前已具备 `approve + reject + manual force-release + recovery/latest` 组合验收；剩余工作是更复杂的真实操作矩阵和更厚的治理动作覆盖
- provider 覆盖：已从“仅连通性”扩到“连通 + 模型可用 + 最小生成 round-trip”；剩余工作是更广 provider 矩阵与更复杂失败诊断
- environment 覆盖：已补上跨进程误接管保护与 startup recovery 接管边界；剩余工作是更复杂宿主恢复、更多 provider/environment live smoke、以及更深 operator 手工路径
