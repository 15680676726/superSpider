# CoPaw 系统全貌深度阅读报告

> 阅读范围：`src/copaw/` 后端核心层、`console/src/` Runtime Center / Agent Workbench 前端，以及当前架构文档
> 校准时间：`2026-03-11`
> 说明：本版按当前代码现场重写，重点校正此前已经过时的“假闭环”判断

---

## 一、总判断

CoPaw 现在已经不是“主逻辑没搭起来”的系统。

更准确的判断是：

> 统一 `state / evidence / capabilities / environments / kernel / goals / learning` 主骨架已经成立，之前一批关键伪闭环已基本打穿；系统当前的主瓶颈，已经从“链路断没断”转成“宿主化够不够硬、真实世界验收够不够严”。

也就是说，今天最强的部分已经不是某个单独功能，而是：

- 后端统一 kernel 治理主链
- 统一 state/evidence 真相源
- Runtime Center 作为真实 operator surface
- learning / patch / growth 的持久化闭环
- environment mount / lease / replay / recovery 的宿主骨架

---

## 二、你之前点名的问题，现在的状态

### 1. Runtime Center 的 Goal 动作断链

已修。

- Runtime Center 现在不再只是返回可点的 `actionPath`。
- `/api/runtime-center/goals/{id}/compile|dispatch` 已有真实写入口。
- 前端触发 Goal action 时，已经能走通后端统一动作链。

### 2. Chat 前端保留本地真相源

已修。

- chat/session 前端层不再用 localStorage / 本地造 ID 兜底制造 session 假对象。
- `/chats/{id}` 已回到统一 session snapshot / state-backed 路径。

### 3. `chat:{chat_id}` 与 kernel query task id 语义碰撞

已修。

- query 生命周期现在使用稳定的 kernel task id 命名空间，例如 `query:chat:{chat_id}`。
- chat 兼容对象 ID 与 query task id 已从语义上拆开。

### 4. `/command` 绕过 kernel admission / risk / decision / evidence

已修。

- `/command` 不再是旁路。
- 它现在通过 `system:dispatch_command` 进入同一条 kernel 治理链。
- command 虽然仍走专门执行路径，但 admission / risk / decision / evidence 已统一。

### 5. capability toggle/delete 绕过治理和证据链

已修，而且这次把兼容旁门也一起收了。

- `/api/capabilities/{id}/toggle|delete` 已经统一走 `system:set_capability_enabled` / `system:delete_capability`。
- confirm-risk delete 会生成 `decision_request_id`，必须经 Runtime Center review/approve 才执行。
- 旧 `/skills/{name}/enable|disable|delete` 与 `/mcp/{key}/toggle|delete` 兼容写入口，现在也桥接回同一条 kernel-governed capability write 路径，不再保留直写旁路。

### 6. Decision detail 读接口带副作用

已修。

- `GET /runtime-center/decisions/{id}` 现在是纯读。
- 只有显式调用 `/review` 才会把 `open` 推进到 `reviewing`。

### 7. Schedule 不是 Runtime Center 一等对象

主问题已修。

- Runtime Center 现在有 state-backed 的 `/runtime-center/schedules`、detail、run、pause、resume。
- route 不再回指旧 `/api/cron/jobs/{id}`。
- schedule runtime 状态会持续回写 `ScheduleRecord`。

还没完全终态的部分是：

- `CronManager` 仍有宿主职责残留
- 调度编排与 heartbeat 宿主化还没完全 service 化

### 8. Operator 读面“假可见性”

这个点现在也不再成立。

- Agent Workbench 的日报/周报已经改为直接基于 `/runtime-center/evidence`、`/runtime-center/learning/proposals|patches|growth` 计算，而不是静态文案。
- Workbench 失败时会显式暴露 `dashboardError / goalError`，不再把接口失败吞成“空数组=今天没数据”。

### 9. 装配和文档语义漂移

大头已修，小漂移仍有。

已修部分：

- `capabilities.py`、`learning.py` 等核心 router 已回到 `app.state` 注入的 service，不再在 app.state 缺失时临时 `new service`。
- Runtime Center 模型已不再把自己描述成 read-only bridge，而是 operator surface。
- `TASK_STATUS.md`、`API_TRANSITION_MAP.md`、本文件已按本轮代码现场重写。

仍在的轻量漂移：

- `runtime_center` 包和 bridge header 里仍保留一些 `Phase 1 / bridge` 命名，这是兼容语义残留，不再代表真实读写能力。
- `GET /runtime-center/overview` 仍是按请求临时实例化 `RuntimeCenterQueryService()`，但它现在是轻量 query facade，而不是第二真相源。

---

## 三、此前已经过时、现在必须纠正的旧结论

下面这些说法，今天都已经不对了：

### 1. “`role/profile patch` 不会进入 query prompt”

这个结论已过时。

- query 执行装配阶段现在会读取 agent profile。
- `KernelQueryExecutionService` 会构建 profile prompt appendix，把 `role_name / role_summary / current_goal_id / current_task_id` 投影进运行时 system prompt 语义。

### 2. “`capability_patch` 不影响 query-time toolkit”

这个结论已过时。

- query 执行前会通过 `CapabilityService.list_accessible_capabilities()` 解析当前 agent 可访问的能力。
- tool / skill / MCP 的 query-time 注入，现在会经过 enabled 状态、profile allowlist、role access policy 过滤。

### 3. “`_compile_role()` 生成的任务没有执行器”

这个结论已过时。

- `SemanticCompiler._compile_role()` 现在生成的是 `system:apply_role`。
- `system:apply_role` 已在 system capability graph 中注册，并能写入 agent profile override。

### 4. “learning 没有宿主级自动守护任务”

这个结论已过时。

- app 启动时现在会启动两个自动化 loop：
  - `system:dispatch_active_goals`
  - `system:run_learning_strategy`

### 5. “Runtime Center 没有实时观测”

这个结论已过时。

- 现在已有 `RuntimeEventBus`。
- `/api/runtime-center/events` 已提供 SSE event stream。
- 前端已接入 SSE，并在收到事件后做去抖 reload。

### 6. “replay 只有只读指针，没有执行语义”

这个结论已过时。

- replay pointer 仍然不是“原地物理重放”，但已不再只是只读记录。
- `/api/runtime-center/replays/{id}/execute` 会根据 replay metadata 重新向 kernel 提交动作，因此 replay 已进入治理链中的“可再执行语义”。

### 7. “启动恢复只有懒恢复，没有显式 recovery orchestration”

这个结论已过时。

- 现在已有 `run_startup_recovery()`。
- startup/restart 时会显式：
  - reap 过期 lease
  - recover 本机 orphan lease
  - expire 超时 decision
  - hydrate `waiting-confirm` task
  - 发布 `system.recovery` 事件

---

## 四、当前分层评估

### 1. `kernel / state`

完成度：高。

- 统一 submit / risk / decision / execute / evidence 主链已经成立。
- state 已成为运行真相源，不再依赖 `jobs.json / chats.json / sessions/*.json` 恢复 steady-state 世界。

当前缺口：

- `AgentRunner` 仍持有 `session_backend / memory_manager / restart callback` 等宿主职责。

### 2. `capabilities`

完成度：高。

- `tool / skill / MCP / system` 已统一到 capability graph。
- execute / toggle / delete 都已进入治理链。
- 旧 `/skills`、`/mcp` 写入口这次也已收口。

当前缺口：

- create / update / import 这类 admin/config 写面仍未完全 kernel 化。
- 更严格的角色授权、环境约束还需要继续补强。

### 3. `compiler / learning`

完成度：高。

- goal compile / dispatch、proposal / patch / growth、feedback -> next compile 主链已经打通。
- `system:apply_role`、`system:dispatch_active_goals`、`system:run_learning_strategy` 都已接进 capability graph。

当前缺口：

- 高阶策略仍偏 override 驱动，不是更强的代码级自治。
- 真实 provider 覆盖和 operator manual E2E 仍是主要验收瓶颈。

### 4. `environments / evidence`

完成度：中高。

- `EnvironmentMount + SessionMount`
- lease acquire / heartbeat / release / reap
- host-aware orphan lease recovery
- replay pointer 持久化
- replay execute through kernel
- recovery summary / force-release / runtime events

都已到位。

当前缺口：

- `live_handle` 仍不能跨进程恢复，只能判定失效并回收。
- replay 现在是“重新经 kernel 再执行”，还不是“恢复原宿主句柄后原位回放”。

### 5. `Runtime Center / Agent Workbench`

完成度：高。

- overview、detail drawer、goal/schedule/decision/patch/growth/environment 操作面已成型。
- SSE 已补上。
- 日报/周报已 evidence-driven。
- Workbench 不再吞错伪装成空数据。

当前缺口：

- chat 流事件与 Runtime Center runtime event 还没有统一成一套总线模型。
- 少数系统级全局动作仍可继续上浮为更明显的 operator 入口。

---

## 五、如果把这套系统当作“载体”，现在最该继续做什么

现在已经不该再回头优先处理你之前列出的那批伪闭环，它们大部分已经收口。下一阶段最值得做的是：

1. 继续压缩 `AgentRunner` 宿主职责。
   目标不是再给 runner 加功能，而是把它继续切薄成边缘接入壳。

2. 继续做环境宿主硬化。
   重点是跨进程 `live_handle` 恢复、稳定宿主句柄、以及更强 replay 语义。

3. 对真实世界负责的验收。
   包括 operator manual E2E、live provider smoke、重启恢复、审批流、patch 回滚。

4. 继续清理兼容 admin 写面。
   尤其是 `/skills` create/import、`/mcp` create/update 这类声明式配置写入，后续要么显式归入 config/admin 面，要么继续收回统一治理。

5. 继续压缩 `Phase 1 / bridge` 命名残留。
   现在语义上已经不是 read-only bridge 了，剩下的是文义和兼容头的历史壳。

---

## 六、一句话总结

> 以今天的代码现场看，CoPaw 已经跨过“主链是不是假的”这道坎了。
> 现在真正决定它上限的，不再是把更多页面补齐，而是把宿主化、恢复、真实环境验收和兼容壳退役继续做深。
