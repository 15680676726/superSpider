# 执行纪律与主链收口设计说明

## 1. 目标

本轮不是继续“顺手优化一点”，而是把 CoPaw 当前仍然影响长期任务质量、多人协作稳定性、主链可读性和删旧确定性的硬骨头一次性收成正式施工对象。

本设计只关注两个结果：

1. 把 `cc` 里真正值得借鉴的执行纪律壳，落到 CoPaw 自己的正式真相链上。
2. 把 CoPaw 当前已经成型但仍显杂乱的主链实现层继续收口，直到可以用“只有一条正式主链、每类正式写动作都只有一条 canonical ingress、只有一套正式命名”来描述。

## 2. 非目标

本轮明确不做：

- 不复制 `cc` 的产品壳、会话壳、插件壳、文件记忆壳。
- 不引入第二套规划真相、第二套运行真相、第二套工具语义。
- 不把兼容桥、迁移桥重新散落回核心目录。
- 不把“继续优化”当作完成定义。

## 3. 当前判断

截至当前主线，CoPaw 的整体状态可以概括为：

- 主链真相已经基本成型。
- 运行中心、规划链、行业执行链已经不再是散乱的旧系统。
- 但执行纪律层仍然弱于 `cc`。
- 实现层仍有大文件、重复投影、历史命名、兼容壳和过长调用路径残留。

换句话说，CoPaw 现在已经不是“没主链”，而是“主链已有，但执行纪律和实现层收口还没打到硬结束态”。

## 4. donor 边界

本轮只借 `cc` 的执行纪律壳，不借其规划真相。

允许借鉴的 donor 面：

- `tool-result budget`
- `microcompact`
- `autocompact`
- `tool-use summary`
- `plan mode`
- `plan file`
- `resume / fork continuity`
- 读并发、写串行的 planner 纪律
- agent-scoped additive MCP + cleanup 壳

明确不借的 donor 面：

- `cc` 的产品前门
- `cc` 的 planner truth
- `cc` 的 session/app/plugin 真相
- 文件型记忆真相
- 环境变量或设置位驱动的隐式真相

## 5. 完成定义

只有同时满足下面 8 条，本轮才允许宣称“执行纪律与主链收口完成”：

1. `StrategyMemory -> OperatingLane -> BacklogItem -> OperatingCycle -> Assignment -> AgentReport -> Replan` 仍是唯一正式规划主链。
2. 每类正式写动作都只有一条 canonical ingress / contract；这条要求按语义理解，不按 URL 数量理解。
3. 长任务上下文不会明显越跑越脏，大工具结果不会直接污染主转录链。
4. `plan shell` 成为正式执行纪律，而不是 prompt 里的临时约定。
5. 多 agent、多环境、多工具执行遵守统一的读并发、写串行纪律。
6. agent 级增量 MCP/环境挂载在成功、失败、取消后都能正确清理，不污染父级。
7. `current_focus` 口径统一到底，旧 `current_goal/current_goal_id` 残留被删掉或被硬性阻断。
8. 上述结果由回归测试、运行中心读面、删除账本共同证明，不靠口头描述。

补充解释：

- “只有一个正式前门”不等于整个系统物理上只剩一个路由。
- CoPaw 允许 `Runtime Center`、`industry`、`chat/run`、`governed mutation` 等不同 surface 共存。
- 关键要求是：每类正式写动作只能回到同一条 kernel/state/evidence 主链，不能存在第二条真正可写的平行 ingress。

## 6. 六个施工包

### 包 A：上下文熵控制补齐

目标：

- 让 CoPaw 的长任务对话、运行转录、工具结果、恢复继续跑时保持稳定，不因为工具输出过大而腐烂。

应借 `cc` 的点：

- 消息级 `tool-result budget`
- 大结果外置与稳定替身
- `microcompact`
- `autocompact`
- `tool-use summary`

落位原则：

- 统一落到 CoPaw 现有 `conversation_compaction_service`、`query_execution_runtime`、聊天运行时传输和运行中心读面上。
- 不能引入第二套 transcript truth。
- `summary / artifact / replay / compact state` 必须成为正式可见结果，而不是 provider/chat 私有技巧。

必须看到的系统变化：

- 大工具结果进入 artifact / spill，而不是永久塞进主上下文。
- compact 前后有稳定替身，不因 resume / replay / fork 改变引用。
- 运行中心能显示 compact 结果、summary 和 spill 信息。

### 包 B：planning shell 补齐

目标：

- 把“有 planning truth”升级成“有 planning 纪律”。

应借 `cc` 的点：

- `plan mode`
- `plan file`
- `todo reminder`
- `verify reminder`
- `resume / fork continuity`

落位原则：

- 壳必须围绕 CoPaw 既有正式对象链工作，不能替代 `StrategyMemory / OperatingCycle / Assignment` 等正式对象。
- assignment 内部 planning scratch 可以存在，但只能是执行壳，不是真相源。
- `plan mode / plan file / todo / verify / resume / fork continuity` 只允许挂在正式 `Strategy / Cycle / Assignment / Report` 主链上，不允许长出 prompt 私有 planning truth。

必须看到的系统变化：

- 长任务和多 agent 任务有正式 plan shell。
- plan shell 在运行中心或工作台可见，而不是只藏在 prompt 里。
- 恢复、续跑、fork 时能继承 planning shell 上下文。

### 包 C：读并发、写串行纪律系统化

目标：

- 把当前已有的底层写保护，升级成 planner、executor、environment 全链路都理解的统一纪律。

应借 `cc` 的点：

- planner 显式要求“先并发读，再串行写”
- 不在多轮里交错读写

落位原则：

- 继续复用 CoPaw 的共享写租约、child-run shell、capability execution contract。
- 不允许为 browser、desktop、file、subagent 各写一套自己的并发规则。

必须看到的系统变化：

- planner 和运行时都知道什么是 `parallel-read`、什么是 `serial-write`。
- agent 对同一写目标不会并发乱写。
- browser / desktop / file 的写操作经过统一 gate。

### 包 D：agent-scoped additive MCP + cleanup 壳

目标：

- 让子 agent / worker 能临时挂自己的 MCP/环境能力，并在结束时只清自己新增的部分。

应借 `cc` 的点：

- additive mount
- 只清自己新增的 mount
- 父子 agent 边界清晰

落位原则：

- 继续落在 CoPaw 的 `CapabilityMount / EnvironmentMount / SessionMount` 真相链上。
- 不让子 agent 的附加挂载变成新的全局真相源。

必须看到的系统变化：

- worker 结束后无脏挂载残留。
- 失败、取消、超时、abort 都能正确清理。
- 运行中心能看到 agent 级增量 mount 的来源和回收结果。

### 包 E：主链收口、前门唯一化、命名统一、重复逻辑归并

目标：

- 彻底把“看起来能跑，但路径太长、命名太杂、还存在旧绕路”的实现层收起来。

必须完成的四件事：

1. 前门唯一化  
   不允许旧 workflow / preview / query-write 混合入口继续作为正式绕路；验收看 canonical ingress 是否唯一，而不是只看 URL 数量。

2. 命名统一  
   `current_focus`、`runtime`、`execution`、`lifecycle`、`projection`、`service`、`router` 的职责命名必须稳定。

3. 重复逻辑归并  
   重复 normalize、重复 fallback、重复 projection、重复 payload shaping 必须收成单实现。

4. 路径压短  
   `页面 -> router -> facade -> kernel -> state` 这条链里多余桥接层必须删除，但不能把必要的 projection-only read 层也一起砍掉。

必须看到的系统变化：

- `current_goal` 旧残留被真正清理，而不是只是不再提。
- Runtime Center、Industry、Kernel 的主链读写路径更短。
- shared/helper/builder 垃圾桶文件继续被拆到单职责模块。
- projection / facade / query collaborator 允许继续存在，但它们只能组装 read-model，不能回写 truth，也不能在 query 面偷偷做写。

### 包 F：可见化、文档、删除账本、回归矩阵闭环

目标：

- 把“已经做完”变成能被看见、能被测试、能被删旧账本证明的事情。

必须完成的四件事：

1. 运行中心可见化  
   当前 focus、plan、assignment、risk、evidence、compact、environment、mount、MCP 状态可见。

2. 删除账本  
   所有兼容壳、临时桥、历史入口写出删除条件、owner、退出条件。

3. 文档同步  
   迁移图、状态文档、蓝图文档同步更新。

4. 分层验证  
   执行纪律、主链收口、环境回收、运行中心读面分别有回归矩阵。

## 7. 串行与并行关系

必须串行的关系：

- 包 A 必须先于包 B 和包 F 收口，因为 planning shell 和可见化要消费 compact/summary/spill 结果。
- 包 C 必须先于包 D 收口，因为 additive MCP cleanup 需要建立在统一的执行纪律和写 gate 之上。
- 包 E 必须在包 A-D 的接口稳定后再做最终删旧，否则容易一边重命名、一边继续扩散新旧并存逻辑。
- 包 F 最后完成最终账本和全矩阵验收。

允许并行的关系：

- 包 A 与包 C 可以并行推进，但不能写同一文件。
- 包 B 与包 D 可以在 A/C 接口明确后并行推进。
- 包 E 可以分两波：先做只读审计和删除账本，等 A-D 落完再执行实删。

## 8. 明确的退出标准

本轮退出必须满足下面全部条件：

- `tool-result budget / spill / summary / compact` 有正式实现和回归。
- `plan shell` 有正式实现和回归。
- planner/runtime/environment 的读并发、写串行纪律可见且可测。
- agent 级 additive MCP + cleanup 在成功、失败、取消、abort 下都可测。
- 正式前门唯一，旧入口退役或硬阻断。
- 命名统一到 `current_focus` 和当前主链词汇，不再保留模糊旧词。
- 兼容壳、删除账本、蓝图文档同步。
- 分层矩阵通过，且 `git diff --check` 通过。

额外验收补充：

- “删旧”不以文件物理删除数量为标准。
- 重点看：
  - 旧入口是否还能写正式状态
  - query 面是否还在偷偷做写
  - fallback 是否还在旁路旧状态
  - projection 是否反向成为 truth

## 9. 当前施工约束

当前根工作区仍然有其他 agent 在并行写入，因此本轮真实代码施工必须在隔离 worktree 中执行。

根工作区当前只能用于：

- 审计
- 设计
- 写计划
- 列出 owner 和文件边界

不应用于：

- 在脏根目录直接做大规模收口重构
- 在多人并写状态下删除共享文件

## 10. 一句话结论

这轮不再允许把“继续优化”当作完成口径。只有把执行纪律补成硬壳、把主链收成单线、把旧入口和旧命名删掉、把运行中心读面和删除账本补齐，CoPaw 才能被称为真正接近 `95%+` 收口。
## 11. `2026-04-03` 落地补充

- `current_focus` writer 迁移已跨过 live runtime metadata 这条最后双写线；industry runtime sync 现在只持久化 `current_focus_*`
- planning shell 已进入 Runtime Center 正式消费面：`/runtime-center/main-brain` 有 dedicated `main_brain_planning` contract，主脑 cockpit 直接展示 cycle / assignment / replan shell 的 `resume_key / fork_key / verify_reminder`
