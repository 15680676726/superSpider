# V1_RELEASE_ACCEPTANCE.md

本文件用于 `V1` 行业团队正式化版本的页面级手工验收与上线放行。

它不是新的产品规划，也不是新的开发任务单，而是：

1. 上线前最后一轮人工验收清单
2. 自动化回归之后的页面闭环确认
3. `V1` 是否可以正式上线的放行依据

---

## 0. 当前放行结论

截至 `2026-03-11`，当前代码状态可以定义为：

- `V1 release candidate`

当前已满足的前提：

- 行业正式对象真相源已落到 `IndustryInstanceRecord / industry_instances`
- `/industry` 与 `/runtime-center/industry` steady-state 已读取正式 instance store
- 前后端构建与类型已对齐
- 全量自动化回归已通过

当前分级规则：

- `P0 blocker`
  - 白屏
  - 页面成功提示与后端实际对象不一致
  - 激活成功后 Runtime Center / Agent Workbench 查不到对象
  - goal/task/detail 深链断开
  - 错误被吞成空页面或“暂无数据”
- `P1 blocker`
  - 主要信息缺失，但主链仍能跑通
  - 某个 detail 面板字段缺失或错位
  - 文案、排版、标签颜色等非主链错误

放行标准：

- 所有 `P0` 必须为 `pass`
- `P1` 不允许影响 operator 判断系统当前状态

---

## 1. 执行前准备

### 1.1 自动化基线

执行前应确认以下命令已通过：

```bash
python -m pytest
cmd /c npm --prefix console run build
```

本轮实际基线：

- `python -m pytest` -> `291 passed, 1 skipped`
- `cmd /c npm --prefix console run build` -> `passed`

### 1.2 启动方式

优先方式：

```bash
copaw app --host 127.0.0.1 --port 8088
```

如果当前终端没有 `copaw` 命令，可用：

```bash
python -m uvicorn copaw.app._app:app --host 127.0.0.1 --port 8088
```

浏览器打开：

```text
http://127.0.0.1:8088/
```

如果根页面提示 Console 不可用，先重新执行：

```bash
cmd /c npm --prefix console run build
```

### 1.3 建议验收样例

建议使用一组全新行业样例，避免与旧数据混淆：

- `Industry`: `Industrial AI`
- `Company Name`: `Northwind Robotics RC`
- `Product`: `factory monitoring copilots`
- `Business Model`: `B2B SaaS`
- `Channels`: `events, content`
- `Goals`: `land three design partners`
- `Notes`: `V1 release acceptance`
- 打开 `Auto Activate`
- 打开 `Auto Dispatch`
- 打开 `Execute`

---

## 2. 页面级手工验收

## 2.1 入口与基础加载

路径：

- `/industry`
- `/runtime-center`
- `/agents`

操作：

1. 打开首页，确认左侧栏存在 `Industry Teams` 与 `Runtime Center`
2. 直接访问 `/industry`
3. 直接访问 `/runtime-center`
4. 直接访问 `/agents`

通过标准：

- 三个页面都可正常加载
- 不出现白屏
- 不出现无限 loading
- 不出现明显的前端异常栈

失败判定：

- 任一页面白屏 -> `P0`
- 任一页面无法进入主内容区 -> `P0`

## 2.2 Industry Preview

路径：

- `/industry`

操作：

1. 填写上面的样例 brief
2. 点击 `Preview Team Plan`

通过标准：

- 页面出现 `Preview Team Plan`
- 顶部出现 `Ready to activate` 或明确的阻塞说明
- 页面能看到 `System Roles`
- 页面能看到 `Business Roles`
- `Manager` 与 `Researcher` 同时存在
- 至少出现一个 `business` specialist
- 页面能看到 preview goals 与 preview schedules
- 页面能看到 readiness checks，而不是只给一个成功提示

失败判定：

- 仍然只生成 `Manager + Researcher` -> `P0`
- preview 成功但没有 goals/schedules -> `P0`
- readiness checks 被吞掉 -> `P1`

## 2.3 Industry Activation

路径：

- `/industry`

操作：

1. 在完成 preview 后，点击 `Activate Industry Team`

通过标准：

- 出现成功提示 `Industry team activated`
- `Recent Industry Teams` 列表刷新
- 新实例出现在列表中
- 列表条目显示：
  - `label`
  - `status`
  - `goal_count`
  - `roles`
- 点击新实例后，右侧 detail 正常展开

失败判定：

- 激活提示成功，但 `Recent Industry Teams` 没有实例 -> `P0`
- 激活成功但 detail 为空 -> `P0`
- 激活后只能看到旧数据，看不到新实例 -> `P0`

## 2.4 Industry Detail

路径：

- `/industry`

操作：

1. 在 `Recent Industry Teams` 中点选刚创建的实例
2. 检查右侧 detail 面板

通过标准：

- 顶部能看到：
  - `label`
  - `status`
  - `instance_id`
- 指标区至少能看到：
  - `goals`
  - `active`
  - `agents`
  - `tasks`
  - `schedules`
  - `evidence`
- `System Roles` 与 `Business Roles` 都能看到角色卡
- `Goals` 列表中每项都带 `task_count / evidence_count`
- `Schedules` 列表非空
- `Daily Report` 与 `Weekly Report` 正常显示

失败判定：

- detail 只显示 team 外壳，不显示 goals/schedules/reports -> `P0`
- reports 永远空白且没有错误提示 -> `P1`
- 角色卡缺少 `mission / constraints / evidence expectations` -> `P1`

## 2.5 Runtime Center

路径：

- `/runtime-center`

操作：

1. 打开 `Runtime Center`
2. 点击刷新
3. 找到 `Industry Teams` 卡片
4. 点击刚创建的行业实例条目
5. 在 detail drawer 中继续打开：
  - `Industry Detail`
  - `Goal Detail`
  - `Task Detail`

通过标准：

- 概览中存在 `Industry Teams` 卡片
- 行业条目能打开 `Industry Detail`
- `Industry Detail` 内能继续深链到 `Goal Detail` / `Task Detail`
- detail drawer 中如果有 `route` 按钮，点击后能继续打开，不断链
- 不出现“前一个对象能看到，下一层 detail 404”的情况

失败判定：

- 没有 `Industry Teams` 卡片 -> `P0`
- 卡片能看到条目，但点不开 detail -> `P0`
- goal detail / task detail 深链断掉 -> `P0`

## 2.6 Agent Workbench

路径：

- `/agents`

操作：

1. 打开 `Agent Workbench`
2. 选择刚创建行业团队中的 `manager`
3. 再选择一个 `business` agent
4. 查看 `Workbench` tab
5. 查看 `Daily / Weekly / Growth` tabs

通过标准：

- 页面顶部能看到 `Agent Workbench`
- 角色切换正常
- `ProfileCard` 中能看到：
  - `Role`
  - `Class`
  - `Activation`
  - `Mission`
  - `Reports to`
  - `Environment constraints`
  - `Evidence expectations`
- `Goal detail` 中能看到行业上下文标签
- 不再只是旧 agent 壳信息

失败判定：

- 选中 agent 后看不到新元数据字段 -> `P0`
- manager 与 business agent 没有明显角色区分 -> `P1`
- `Goal detail unavailable` 无法恢复 -> `P0`

## 2.7 Goal/Task 闭环确认

路径：

- `/runtime-center`
- `/agents`

操作：

1. 在 `Runtime Center` 打开行业对应的 `Goal Detail`
2. 确认 `tasks` 非空
3. 检查 task 数量是否符合预期，不只剩最后一次 dispatch 的任务
4. 返回 `Agent Workbench`，确认该 goal 与行业上下文一致

通过标准：

- `Goal Detail` 有 task 列表
- task 不是空数组
- task 不会因为批量激活发生覆盖丢失
- 行业上下文中的 `instance_id / label / role` 正常

失败判定：

- `Goal Detail` 没 task -> `P0`
- 批量生成后只剩最后一个 goal 的 task -> `P0`

## 2.8 错误显式化验收

目标：

- 确认页面不会把“接口失败”伪装成“今天没数据”

操作：

1. 打开浏览器 DevTools
2. 切换 `Network -> Offline`，或者临时停止后端进程
3. 分别刷新：
  - `/industry`
  - `/runtime-center`
  - `/agents`

通过标准：

- `/industry` 出现 `Industry runtime unavailable`
- `/runtime-center` 出现 `运行中心请求失败`
- `/agents` 出现 `Workbench data unavailable`
- 页面可以明确看出是错误，不是静默空数据

失败判定：

- 请求失败后页面只显示空数组或 `No data`，没有错误 -> `P0`

---

## 3. 放行判定

### 3.1 可以上线

满足以下条件即可放行：

1. `2.1` 到 `2.8` 全部完成
2. 没有 `P0 blocker`
3. `P1 blocker` 不影响 operator 判断系统真实运行状态

### 3.2 暂缓上线

出现以下任一情况应暂缓：

1. 激活成功但对象查不到
2. Runtime Center 深链断掉
3. Agent Workbench 不显示行业角色元数据
4. 错误被吞成空数据
5. Goal/Task 因 ID 撞车或覆盖而缺失

---

## 4. 验收记录模板

建议每次手工验收都记录以下信息：

```text
验收日期：
执行人：
代码版本：
服务地址：

2.1 入口与基础加载：pass / fail
2.2 Industry Preview：pass / fail
2.3 Industry Activation：pass / fail
2.4 Industry Detail：pass / fail
2.5 Runtime Center：pass / fail
2.6 Agent Workbench：pass / fail
2.7 Goal/Task 闭环确认：pass / fail
2.8 错误显式化验收：pass / fail

P0 blocker：
P1 blocker：
最终结论：go / no-go
备注：
```

---

## 5. 当前建议

当前建议不是继续开发 `V1` 新功能，而是：

1. 按本文件跑完一轮页面级手工验收
2. 通过后把当前版本视为 `V1` 正式上线版
3. 后续工作转入 `V2`，不再回头给 `V1` 补对象真相源或行业主链清理
