# V6_RELEASE_ACCEPTANCE.md

本文档记录 `V6 routine / muscle memory` 首轮实现的正式验收结果。
完成日期：`2026-03-17`

---

## 1. 结论

`V6` 当前已达到“首轮实现完成并完成基础 live 验收”的状态，可作为后续删旧、硬化和更深真实世界扩面的基线。

本次验收确认的范围是：

- `V6-1`：正式 `ExecutionRoutineRecord / RoutineRunRecord`、SQLite schema / repository、`/api/routines*`
- `V6-2`：browser deterministic replay、failure classify、canonical fallback、synthetic `routine-run:*` evidence write-back
- `V6-3`：Runtime Center routines overview card、detail / diagnosis deep-link
- `V6-4`：`resource-slot:*` pseudo session mount 细粒度资源锁
- `V6-5`：薄 `n8n` SOP webhook bridge
- `V6-6`：Windows-only desktop routine 手工 action_contract replay

本次验收不包含：

- 更深桌面录制能力
- 非 Windows 桌面宿主
- 大规模真实业务站点 SOP 覆盖

---

## 2. 范围对应

### `V6-1` routine 对象化

- 正式对象：`ExecutionRoutineRecord`、`RoutineRunRecord`
- 正式仓储：`execution_routines`、`routine_runs`
- 正式 API：
  - `POST /api/routines`
  - `POST /api/routines/from-evidence`
  - `GET /api/routines`
  - `GET /api/routines/{routine_id}`
  - `GET /api/routines/runs`
  - `GET /api/routines/runs/{run_id}`

### `V6-2` replay / fallback

- 浏览器 replay：`BrowserRuntimeService + EnvironmentService`
- 失败分类：`precondition-miss / page-drift / auth-expired / lock-conflict / confirmation-required / executor-unavailable / execution-error / host-unsupported`
- fallback mode：`retry-same-session / reattach-or-recover-session / pause-for-confirm / return-to-llm-replan / hard-fail`
- 证据：统一回写 `EvidenceRecord`，任务锚点为 `routine-run:{routine_run_id}`

### `V6-3` Runtime Center routine 结果面

- Runtime Center overview 已有 routines card
- detail / diagnosis 已可钻取到 routine 和 routine run
- 前端不再自造 routine 状态，只消费后端真相

### `V6-4` 资源锁

- 继续复用 `EnvironmentService + SessionMountRepository`
- `browser-profile / browser-session / domain-account / page-tab / artifact-target` 已落入 `resource-slot:*` 语义

### `V6-5` `n8n` SOP bridge

- 仅负责 webhook trigger / timeout / response normalize
- 不持有 workflow / routine / execution history 真相

### `V6-6` desktop routine

- 复用 `WindowsDesktopHost`
- 第一版支持手工 action_contract replay
- 非 Windows 主机返回 `host-unsupported`

---

## 3. 验证记录

以下命令已在 `2026-03-17` 实际执行通过：

```powershell
python -m pytest -q
```

结果：`560 passed, 3 skipped`

说明：

- 新增 `tests/routines/test_live_routine_smoke.py` 后，默认全量回归会额外出现 2 个 opt-in live smoke skip
- 这两个 skip 不代表 `V6` 未完成，只表示真实浏览器/桌面宿主覆盖默认受环境变量门控

```powershell
cmd /c npm --prefix console run build
```

结果：通过

```powershell
set COPAW_RUN_V6_LIVE_ROUTINE_SMOKE=1
python -m pytest tests/routines/test_live_routine_smoke.py -q
```

结果：`2 passed`

live smoke 覆盖内容：

- browser routine：真实 `RoutineService.replay_routine()` 打开 `https://example.com` 并生成截图 evidence
- desktop routine：真实 `RoutineService.replay_routine()` 调用 `WindowsDesktopHost.list_windows()` 并生成 desktop evidence

---

## 4. 当前边界

- `V6` 当前已经具备 formal object / replay / diagnosis / locks / SOP bridge / desktop extension 的第一轮主链
- live smoke 已进入正式测试资产，但默认仍保持 opt-in，不强行并入所有本地与 CI 回归
- 后续深化应继续围绕真实浏览器站点、更多 desktop action、锁冲突诊断和删旧推进，而不是重造第二套 workflow 或第二套 lock 真相源

---

## 5. 2026-03-18 Addendum

- `/api/routines/{routine_id}/replay` 已不再直连 `RoutineService.replay_routine()`；该入口现正式改走 `system:replay_routine -> KernelDispatcher -> CapabilityService`
- opt-in live smoke 已从首轮 `1 browser + 1 desktop` 扩到 `4 browser + 1 desktop`
- 当前显式启用 `COPAW_RUN_V6_LIVE_ROUTINE_SMOKE=1` 的真实主机结果为：

```powershell
set COPAW_RUN_V6_LIVE_ROUTINE_SMOKE=1
python -m pytest tests/routines/test_live_routine_smoke.py -q
```

- 结果：`5 passed`
- 浏览器 live smoke 覆盖：
  - `example.com` open + screenshot
  - `example.com` open + click anchor + screenshot
  - `example.com` open + navigate to `iana reserved` + screenshot
  - same-session dual replay reuse
- 桌面 live smoke 覆盖：
  - Windows desktop `list_windows`
