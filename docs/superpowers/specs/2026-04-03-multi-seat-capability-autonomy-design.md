# 2026-04-03 多执行位能力自治设计

## 1. 文档目的

本文只解决一件事：

把 CoPaw 当前已经具备雏形的 `skill / MCP / install-template / capability assignment / MCP overlay`
收成一条真正适合长期自治、多执行位协作的后端主链。

这轮设计不讨论前端术语替换，不要求把 `skill` 和 `MCP` 从产品界面物理隐藏。
懂的用户仍然可以看到这些术语；真正要改变的是后端逻辑，系统应尽量替用户完成：

- 能力缺口识别
- 自动安装
- 自动启用
- 自动分配
- 自动挂载
- 自动恢复
- 单执行位试用
- 升级、替换与回滚

本文的目标不是再造一套新系统，而是把现有正式对象和运行时收成更硬的自治能力纪律。

---

## 2. 已确认前提

### 2.1 当前正式边界

本设计继续遵守仓库既有硬约束：

- 不新增第二真相源
- 不新增平行运行主链
- 不新增第四套能力语义
- 继续以 `CapabilityMount` 作为正式能力对象
- 继续以 `EnvironmentMount / SessionMount` 作为正式 live environment truth
- 继续以 `IndustryRoleBlueprint.allowed_capabilities` 作为角色原型层的正式能力入口

### 2.2 当前代码已有底座

当前仓库已经具备以下基线：

- 角色正式能力入口：
  - `src/copaw/industry/models.py`
- 角色能力分配与 `merge / replace`：
  - `src/copaw/app/routers/capability_market.py`
  - `src/copaw/capabilities/system_team_handlers.py`
- agent 运行时 skill / tool allowlist：
  - `src/copaw/agents/react_agent.py`
  - `src/copaw/kernel/query_execution_runtime.py`
- child-run MCP overlay：
  - `src/copaw/app/mcp/manager.py`
  - `src/copaw/kernel/child_run_shell.py`
- bootstrap/install plan：
  - `src/copaw/industry/service_activation.py`
- capability discovery / recommendation：
  - `src/copaw/capabilities/capability_discovery.py`
- 远程 skill trial / rollout donor 基线：
  - `src/copaw/capabilities/remote_skill_contract.py`
  - `src/copaw/capabilities/system_skill_handlers.py`
  - `src/copaw/predictions/service_recommendations.py`
  - `src/copaw/predictions/service_context.py`

因此，这轮不是从零开始做能力系统，而是把已有能力安装、分配、挂载、运行时过滤、试用与 rollout 收成同一条自治闭环。

---

## 3. 核心判断

### D1. 长期自治系统不能按“每个任务重跑推荐包”工作

如果每个任务都重新计算 skill/MCP 推荐，再决定安装或替换，系统会退化成“每轮重新配环境”的短会话产品。

长期自治的正确做法是：

- 任务现场优先复用已有能力
- 缺口现场优先临时挂载
- 安装是能力底座动作，不是每轮任务动作
- 升格、替换、淘汰应由慢循环异步决定

### D2. 多执行位场景不能只保留“角色一层能力”

同一角色原型可能派生多个执行位。
这些执行位会共享职责方向，但不一定共享完全相同的能力面。

因此正式能力状态必须至少区分：

- 角色原型能力包
- 执行位实例能力包
- 周期/车道增量包
- 会话级临时 overlay

否则多个执行位会互相污染，主脑也无法判断某能力到底该下沉到哪个层级。

### D3. 时间不是能力保留标准

时间只能证明“在使用”，不能证明“最契合、最好用、最稳定”。

能力升格、替换、淘汰必须优先按以下维度判断：

- 角色契合度
- 任务结果质量
- 执行摩擦
- 稳定性
- 证据质量

时间与频率只可作为辅证，不可作为主判据。

### D4. `skill` 和 `MCP` 都属于能力系统，但其运行语义不同

- `skill` 更像角色 SOP / 场景知识 / 操作包
- `MCP` 更像外部连接器 / transport / remote tool surface

因此两者在自治链中的处理方式不能完全相同：

- `skill` 更适合进入角色原型或执行位实例能力包
- `MCP` 更适合底座安装 + 会话挂载 + 必要时角色授权

### D5. 自动接管不等于删除人工治理入口

系统应该尽量自动完成安装、分配、挂载与恢复，但不意味着删掉管理员或高级用户的显式增删改能力。

正式边界应为：

- 自动链优先复用现有 mutation/front-door
- 手工 `merge / replace / remove / enable / disable` 仍然保留
- 自动链与手工链必须共用同一条正式写链，而不是各写各的配置

### D6. 升级与替换必须是有证据的治理动作

新 skill / MCP 的引入不能只靠“感觉更好”或“一次成功”。

安装、试用、rollout、替换、回滚必须至少留下：

- 来源与版本
- 作用域（role / seat / session）
- 风险级别
- 试用或 rollout 阶段
- 替换目标
- 结果证据

否则长期自治的能力系统会再次退化成不可审计的隐式配置堆。

---

## 4. `cc` 借鉴边界

本设计明确借 `cc` 的纪律，但不复制 `cc` 的产品壳。

值得借的部分：

- agent 级 `tools / skills / mcpServers` 作用域化配置
- child-run 生命周期内的 MCP 挂载与清理纪律
- “共享底座 + agent 局部增强”的配置方式
- 新能力先试用再扩大 rollout 的保守升级思路

不借的部分：

- 第二套 session-first runtime truth
- file-backed continuity truth
- 让主脑直接背满执行型 skills
- 把所有角色暴露为同一套全局 skill/MCP 面

CoPaw 继续以自己的正式对象链为准：

- `StrategyMemory -> OperatingLane -> BacklogItem -> OperatingCycle -> Assignment -> AgentReport`
- `CapabilityMount`
- `EnvironmentMount / SessionMount`

---

## 5. 正式对象关系

### 5.1 全局能力底座

表示系统当前已经安装并可供复用的能力底座。

它回答的是：

- 系统里已经安装了哪些 skill
- 系统里已经存在哪些 MCP client / template runtime
- 它们的来源、版本、风险级别、升级状态是什么

这一层不回答“谁可以用”，只回答“系统里有什么”。

### 5.2 角色原型能力包

继续以 `IndustryRoleBlueprint.allowed_capabilities` 为正式入口。

它回答的是：

- 这类执行位通常应拥有哪些默认能力
- 哪些能力是角色长期常驻能力
- 哪些能力与该角色的职责、风险边界、环境约束长期绑定

这层是模板，不是某个具体执行位的实时状态。

### 5.3 执行位实例能力包

同一角色原型可派生多个执行位实例。

执行位实例能力包回答的是：

- 这个 seat 当前被允许使用哪些能力
- 它和角色原型相比有哪些 seat-level 差异
- 哪些能力只适合该 seat，而不适合整个角色族

这层是多执行位自治的关键。
没有这一层，系统无法对多个 seat 做能力差异化治理。

### 5.4 周期/车道增量包

当某一组执行位在当前 `lane / cycle` 内反复需要一类额外能力时，可在正式链上记录周期级增量能力包。

这层回答的是：

- 当前周期哪些 seat 被临时增强
- 这些增强何时过期
- 周期结束后是否升格、保留或回收

这层不应成为新的长期真相中心，只应作为 operating-cycle sidecar。

### 5.5 会话级 overlay

会话级 overlay 只服务当前任务执行。

它回答的是：

- 这次执行临时挂载了什么 skill / MCP / runtime handle
- 它绑定到哪个 session / seat / work context
- 执行结束后是否保留复用，还是立即清理

`MCP` 的临时挂载最适合放在这一层。

---

## 6. 双循环主链

### 6.1 快循环：任务现场闭环

快循环只面向“当前任务能不能马上干活”，不做长期治理裁决。

顺序固定为：

1. 选定目标执行位
2. 计算该 seat 当前有效能力面
   - 角色原型能力包
   - 执行位实例能力包
   - 周期/车道增量包
   - 当前 session overlay
3. 若命中能力，直接执行
4. 若未命中但系统底座已安装，优先 `assign -> mount -> execute`
5. 若底座也没有，但来源可信且风险允许，执行 `install -> enable -> assign -> mount -> execute`
6. 若需要凭据、登录、未知高风险权限，进入 `guarded / confirm`
7. 记录能力使用与缺口证据

快循环不负责决定长期保留、替换或淘汰。

### 6.2 慢循环：长期优化闭环

慢循环异步运行，不阻塞当前任务。

它负责：

- 评估新能力是否值得保留
- 判断能力应归属到哪个层级
- 决定是增量、替换还是回滚
- 决定旧能力是否进入 `deprecated / retired`

慢循环只依据正式证据做判断，不依据聊天印象或单次成功。

---

## 7. 主脑职责

主脑不是“背最多 skill 的万能执行者”，而是能力治理者。

主脑只负责 4 类判断：

1. 当前缺口属于：
   - 已有能力未挂载
   - 已安装但未分配
   - 根本未安装
2. 该能力应落在哪一层：
   - 角色原型
   - 执行位实例
   - 周期增量
   - 会话 overlay
3. 新能力是补充，还是应替换旧能力
4. 这次动作的治理级别是：
   - `auto`
   - `guarded`
   - `confirm`

主脑不应因为某执行 skill 常用，就把它收成自己的长期常驻能力。

---

## 8. skill 治理规则

### 8.1 skill 不是越多越好

更多 skill 不会自动提升执行质量，反而会增加：

- 提示器噪音
- 角色漂移
- 执行歧义
- 重叠能力冲突

### 8.2 skill 保留标准

skill 是否保留，优先按以下维度判断：

- 是否直接服务该角色或该执行位的正式职责
- 是否提高任务完成质量
- 是否降低人工接管和额外解释成本
- 是否稳定、少漂移、少冲突
- 是否带来更好的正式证据

### 8.3 skill 替换纪律

如果新 skill 明显覆盖旧 skill，则应走：

- `candidate`
- `trial`
- `active`
- `deprecated`
- `retired`

不允许长期并存两个高度重叠的常驻 skill。

### 8.4 建议上限

建议只作为治理上限，不作为“越满越好”的目标。

- 主脑：常驻 `4-6`，硬上限 `8`
- 研究/分析角色：常驻 `6-8`，硬上限 `10`
- 执行/运营角色：常驻 `6-8`，硬上限 `12`
- 临时角色：常驻 `3-5`

这里的核心原则是“少而硬”，不是凑满配额。

---

## 9. MCP 治理规则

### 9.1 底座可共享，暴露不可全局共享

`MCP` 的物理安装可以共享，但角色可见面、seat 挂载态、session 占用态必须分开。

### 9.2 MCP 分层

- 全局底座：系统安装了哪些连接器
- 角色授权：哪些角色允许使用哪些 MCP 能力
- seat 配额：哪些执行位默认可挂载
- session 挂载：本次任务到底挂了哪个 client / transport / session

### 9.3 MCP 升级规则

新 MCP 或新版本出现时，不能直接全局升级。

必须走：

1. `candidate`
2. 兼容预检
3. 单 seat 试用
4. 小范围 rollout
5. 正式替换
6. 旧连接器 `deprecated / retired`

只要试用结果不优于现有连接器，就不应升格。

---

## 10. 自动安装与自动接管规则

### 10.1 自动接管边界

系统应尽量接管一切，但不能无边界自动化。

允许自动执行的情况：

- 内建 template/runtime
- allowlisted MCP/template
- curated skill
- 已通过预检的可信远程来源

必须进入 `guarded / confirm` 的情况：

- 需要新凭据、登录、API key
- 需要新账户授权
- 会产生高风险外部写动作
- 来源未受控

### 10.2 安装不是任务级默认动作

任务现场优先级固定为：

1. 复用
2. 挂载
3. 自动安装
4. 慢循环决定是否升格为长期包

系统不应把“安装推荐包”当成每个任务的默认前置动作。

---

## 11. 多执行位规则

### 11.1 多执行位不是多份角色副本

同一角色原型可以有多个执行位实例。
这些实例共享角色方向，但不共享完全相同的实时能力面。

### 11.2 seat 差异必须正式化

系统必须支持：

- 某一 seat 拥有额外 CRM 能力
- 某一 seat 只承担夜间轻量值守
- 某一 seat 暂时承担特定工单/站点/桌面应用职责

这类差异不应全部写回角色原型包。

### 11.3 session overlay 只影响当前 seat

任一任务现场的临时 skill/MCP 挂载，只应影响：

- 当前 seat
- 当前 session
- 当前 work context

不应直接污染同角色其他执行位。

---

## 12. 能力升级闭环

新 skill / MCP 出现后，正式链路应固定为：

1. `candidate`
2. `preflight`
3. `trial`
4. `rollout`
5. `active`
6. `deprecated`
7. `retired`
8. `blocked`

判断是否升格、替换或回滚时，优先依据：

- 角色契合度
- 成功率
- 结果质量
- 人工接管率
- 执行摩擦
- 稳定性
- 证据完整性

频率和时间只可作为辅证。

---

## 13. 观测与证据要求

本设计新增的任何自动动作，都必须继续留在正式证据链上。

至少应能追踪：

- 本次是复用、挂载、安装、试用、rollout、替换还是回滚
- 动作作用于哪个 role / seat / session
- 动作来源于哪个 candidate / recommendation / operator mutation
- 新旧能力分别是什么
- 风险级别与治理结果是什么

Runtime Center 和后端读面后续至少应能看见：

- 某角色的原型能力边界
- 某执行位的实例能力差异
- 当前 session overlay
- 新能力当前所处的生命周期阶段

---

## 14. 不做的事

本设计明确不做：

- 不把 `skill / MCP` 从前端术语层面强制删除
- 不再造一套新的“能力推荐中心”真相源
- 不让每个任务都跑一次完整推荐包
- 不把主脑改成满载执行技能的大执行位
- 不让所有角色共享同一套全局可见 MCP 面
- 不让两个高度重叠的常驻 skill 长期并存

---

## 15. 实现落点建议

### 15.1 优先扩展现有模块

- `src/copaw/industry/models.py`
  - 继续承接角色原型能力包
- `src/copaw/industry/service_team_runtime.py`
  - 承接执行位实例能力快照
- `src/copaw/kernel/query_execution_runtime.py`
  - 承接快循环 resolver
- `src/copaw/app/mcp/manager.py`
  - 承接 session overlay 和 MCP lifecycle
- `src/copaw/industry/service_activation.py`
  - 承接安装/启用/分配主链
- `src/copaw/capabilities/capability_discovery.py`
  - 承接 candidate 发现与 upgrade 入口
- `src/copaw/capabilities/remote_skill_contract.py`
  - 承接 skill 试用、替换与 rollout 合同
- `src/copaw/predictions/service_recommendations.py`
  - 承接慢循环 candidate 推荐与 rollout 扩面判断
- `src/copaw/app/routers/capability_market.py`
  - 继续作为 mutation/front-door surface，不另开新入口

### 15.2 不建议另起平行模块

不建议新增：

- 第二套 skill manager
- 第二套 MCP manager
- 第二套 recommendation truth
- 第二套 runtime capability state store

---

## 16. 接受标准

本设计视为实现到位，至少需要满足以下条件：

1. 多执行位下，每个 seat 都能计算出自己的有效能力面
2. 任务执行默认优先复用和挂载，而不是重跑全量推荐包
3. 自动安装只在可信且低到中风险边界内发生
4. 新 skill / MCP 的升级支持单 seat 试用和小范围 rollout
5. 替换逻辑支持 `deprecated / retired / rollback`
6. 主脑只做能力治理决策，不背满执行 skill
7. 自动链和手工链共用同一条正式 mutation/front-door
8. `skill` 和 `MCP` 的状态变化都能留下正式证据
9. 全链路不引入第二真相源，不绕过 `CapabilityMount / EnvironmentMount / SessionMount`

---

## 17. 一句话总结

CoPaw 的长期自治能力系统，应收口为：

**共享能力底座 + 角色原型默认边界 + 执行位实例差异层 + 周期增量层 + session overlay 临时挂载 + 主脑驱动的自动安装/升级/替换/回滚闭环**，

而不是“每个任务重跑推荐包”或“所有角色共享同一套 skill/MCP 面”。
