# PHASEA_PHASEB_PARALLEL_PLAN.md

本文件用于把 `Phase A 载体硬化收口` 与 `Phase B 行业初始化 MVP` 放到同一张执行图里，避免后续开发再次出现：

- A、B 边界混乱
- 行业功能反向污染载体主链
- 为了赶 B 再次引入平行真相源、平行执行器、静态假报告
- 临时兼容承载位没有删除条件，最终留下新尾巴

本文件是：

- `Phase A + Phase B` 的并行推进图
- A/B 两条线的 gate 与依赖图
- “什么叫 A 收尾完成”和“什么叫 B 全部完成”的统一定义
- 后续每轮开发时的优先级与删尾检查表

优先级说明：

1. `AGENTS.md`
2. `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
3. `TASK_STATUS.md`
4. `implementation_plan.md`
5. `PHASEB_EXECUTION_PLAN.md`
6. 本文件 `PHASEA_PHASEB_PARALLEL_PLAN.md`

如果本文件与以上文档冲突，以上文档优先。

---

## 1. 总体判断

`Phase A` 和 `Phase B` 不冲突，但：

> `Phase B` 不能替代 `Phase A`，`Phase A` 也不能无限拖住 `Phase B`。

正确关系是：

- `Phase A` 负责把载体剩余硬债收口，继续守住单一真相源、单一运行内核、单一能力图谱、单一证据链
- `Phase B` 负责把行业初始化做成正式 MVP，但所有产品层能力都必须建立在 `Phase A` 继续硬化后的同一载体上

所以正确推进方式不是：

- 先彻底做完 A 再开始 B
- 或者先把 B 堆满再回头补 A

而是：

> 按 gate 受控并行推进，边收 A 的尾，边完成 B 的 MVP，但任何一侧都不能破坏另一侧的完成条件。

---

## 2. 最终目标

这张并行推进图服务的最终目标只有一个：

> 一次把“载体硬化剩余尾项”与“行业初始化 MVP”都推进到可正式接棒开发的状态，后续不再因为文档、兼容位、删旧条件不清而返工。

这里的“一次完成”不是指盲目一轮大补丁，而是指：

- 有统一推进图
- 有分波次 gate
- 有同步文档规范
- 有明确删尾标准
- 有最终验收口径

---

## 3. 两条执行线

## 3.1 Phase A 载体硬化收口线

Phase A 的剩余工作聚焦 5 个尾项：

- `A1 AgentRunner 退壳`
- `A2 环境宿主硬化`
- `A3 治理面继续收紧`
- `A4 真实世界验收深化`
- `A5 兼容壳与命名残留退役`

### A1 AgentRunner 退壳

目标：

- 继续把 `session_backend / memory_manager / restart callback / turn-executor wiring` 这类宿主职责从旧 runner 公共地位中移出

完成标准：

- `AgentRunner` 不再是公开宿主中心
- direct `/api/agent`、channel ingress、cron ingress 不依赖旧 runner 作为唯一外部宿主
- 剩余 runner 只保留边缘 adapter 或可删除壳

### A2 环境宿主硬化

目标：

- 强化 `EnvironmentMount / SessionMount / ObservationCache / ActionReplay / ArtifactStore`
- 明确 `live_handle` 跨进程恢复语义
- 把 replay 从“经 kernel 再执行”继续推进到更强恢复/回放语义

完成标准：

- 环境 lease、host/process、recovery、replay 的边界清晰
- 至少有稳定的跨进程宿主恢复策略和测试

### A3 治理面继续收紧

目标：

- 把角色授权、环境约束、config/admin 写面继续收口到统一治理面

完成标准：

- Manager/Researcher/其他角色不再默认无限能力
- 高风险配置写操作不存在旁路

### A4 真实世界验收深化

目标：

- 补齐真实 provider/operator manual E2E、重启恢复、审批流、patch 回滚

完成标准：

- 不只存在本地假闭环自动化
- 至少有清晰的 smoke/manual/auto 三层验收矩阵

### A5 兼容壳与命名残留退役

目标：

- 持续清理 Phase 1 / bridge / compatibility 壳与误导性命名

完成标准：

- 所有剩余兼容位都已登记、可解释、可删除
- 不存在“明明已进主链，名字还像桥接/临时态”的长期误导

---

## 3.2 Phase B 行业初始化 MVP 线

Phase B 的正式执行内容以 `PHASEB_EXECUTION_PLAN.md` 为准，这里只保留并行图所需摘要。

Phase B 共 12 个 Task Group：

- `B1 行业输入对象稳定化`
- `B2 团队蓝图/角色蓝图稳定化`
- `B3 行业 goal seed 编译器拆分`
- `B4 Runtime Center 行业 detail 可见化`
- `B5 行业启动入口产品化`
- `B6 默认 schedule 接入`
- `B7 evidence-driven 日报起点`
- `B8 角色授权与环境约束基础版`
- `B9 最小前端工作台`
- `B10 自动化测试矩阵`
- `B11 文档同步与删旧准备`
- `B12 MVP 验收`

---

## 4. 并行推进图

下面这张图说明什么能并行，什么必须过 gate 才能继续。

```text
Wave 0: 边界冻结
  A-side: 冻结剩余载体尾项边界、登记兼容位
  B-side: 冻结行业 MVP 边界、登记临时承载位
  Gate G0:
    - 不新增平行真相源
    - 不新增平行主链
    - 不新增第四套能力语义

Wave 1: 模型与宿主基础
  A1 AgentRunner 退壳 --------------------+
  A3 治理面基础收紧 ----------------------+----> Gate G1
  B1 行业输入对象稳定化 ------------------+
  B2 团队蓝图/角色蓝图稳定化 ------------+
  B3 goal seed 编译器拆分 ----------------+

Gate G1:
  - 行业对象/团队对象/seed 边界稳定
  - 角色授权基础模型稳定
  - 行业初始化不再继续扩散零散 dict/context 语义

Wave 2: 可见化与持续运行
  A2 环境宿主硬化 ------------------------+
  A5 兼容壳退役与命名收口 ---------------+----> Gate G2
  B4 Runtime Center 行业 detail ----------+
  B5 行业启动入口产品化 ------------------+
  B6 默认 schedule 接入 ------------------+

Gate G2:
  - 行业实例已成为 Runtime Center 内可操作对象
  - schedule 进入统一主链
  - 兼容位没有继续扩张

Wave 3: 报告、验收、交付收口
  A4 真实世界验收深化 --------------------+
  B7 evidence-driven 日报 ----------------+
  B8 角色授权与环境约束基础版 ------------+
  B9 最小前端工作台 ----------------------+
  B10 自动化测试矩阵 ---------------------+----> Final Gate
  B11 文档同步与删旧准备 -----------------+
  B12 MVP 验收 ---------------------------+

Final Gate:
  - Phase A 收尾完成
  - Phase B MVP 全部完成
  - 所有兼容位、临时承载位、删旧条件已登记
  - 不留下未解释的尾巴
```

当前状态（`2026-03-11`）：

- `Wave 1` 已完成，`Gate G1` 已达成
- 已落地 `RuntimeHost` 退壳、config/admin 写面 kernel 化、`IndustryProfile / RoleBlueprint / TeamBlueprint / GoalSeed` 稳定化
- `Wave 2` 已完成，`Gate G2` 已达成：`A2` 环境宿主硬化、`A5` 命名/兼容壳收口、`B4` 行业 detail、`B5` 启动入口产品化、`B6` 默认 schedule 已全部落地
- `Wave 3` 已完成，`Final Gate` 已达成：`A4` 真实世界验收深化、`B7` evidence-driven 日报、`B9` 最小前端工作台、`B10/B11/B12` 测试/文档/验收已全部收口
- `B8` 基础版已随 `A3` 提前落地，并在本轮验收中保持稳定
- 本文件当前从“活跃施工图”转为“已收口 gate 台账”；后续工作不再重开 A/B，而是转入 `Phase C`

---

## 5. Gate 定义

## 5.1 Gate G0：边界冻结

必须满足：

- 行业线不新增独立 JSON/store
- 行业线不新增独立 manager executor
- A 线不允许为了硬化再次回退到旧路径
- 已登记当前 Phase B 临时承载位：
  - `GoalOverrideRecord.compiler_context`
  - `AgentProfileOverrideRecord`

未过 G0，不允许开始大规模 UI 与 schedule 扩展。

## 5.2 Gate G1：模型与授权稳定

必须满足：

- 行业输入模型稳定
- 团队蓝图/角色蓝图边界稳定
- goal seed 逻辑独立可测
- 角色默认 capability/risk 边界已有基础规则
- A1/A3 没有因为 B 扩展而倒退

未过 G1，不允许开始大规模行业 detail、前端工作台与默认 schedule 扩展。

当前状态：

- `2026-03-11` 已满足本 gate 条件
- `A1 + A3 + B1 + B2 + B3` 已完成，且未引入新的平行真相源或旁路写面

## 5.3 Gate G2：运行面接通

必须满足：

- 行业实例可在 Runtime Center 内稳定查看与跳转
- 行业实例可生成默认 schedule 且进入统一主链
- 兼容壳未继续膨胀
- 环境宿主语义足够支持行业实例后续运行

未过 G2，不允许把日报/验收宣传成“正式 MVP 已完成”。

当前状态：

- `2026-03-11` 已满足本 gate 条件
- 行业实例已具备 `/industry/v1/instances*` 与 `/runtime-center/industry*` 正式读面
- 默认 schedule 已写入既有 schedule 主链，Runtime Center 可直接查看 detail/run/pause/resume
- 环境宿主已具备 channel restorer、same-host orphan lease recovery、direct replay executor/fallback kernel replay 的当前阶段能力

## 5.4 Final Gate：A 收尾 + B 完成

必须同时满足：

- A 线完成定义达成
- B 线完成定义达成
- 自动化测试与真实验收矩阵就位
- 文档、台账、删旧条件全部同步

当前状态：

- `2026-03-11` 已满足本 gate 条件
- `Phase A` 已完成 `A1/A2/A3/A4/A5`
- `Phase B` 已完成 `B1` 到 `B12`
- 仍保留的兼容位已登记到 `DEPRECATION_LEDGER.md`，并明确转入下一阶段删除

---

## 6. 什么叫 Phase A 收尾完成

只有以下条件全部成立，才算 `Phase A 收尾完成`：

### 6.1 宿主完成

- `AgentRunner` 不再持有关键公开宿主职责
- `session_backend / memory_manager / restart callback` 已迁移或显式退化为边缘 adapter

### 6.2 环境完成

- `live_handle` 的跨进程恢复语义明确
- recovery / replay / lease 的关键链路具备测试

### 6.3 治理完成

- 角色授权与环境约束已有统一规则
- 重要 config/admin 写面无旁路

### 6.4 验收完成

- operator manual E2E
- live provider smoke
- restart recovery
- decision approval flow
- patch rollback

以上验收都有明确状态，不再是模糊 TODO。

### 6.5 删尾完成

- 剩余 bridge / compatibility / Phase 1 残壳都已登记并明确删除条件
- 没有新的未登记兼容建筑

---

## 7. 什么叫 Phase B 全部完成

只有以下条件全部成立，才算 `Phase B 全部完成`：

### 7.1 行业输入完成

- 有正式行业输入模型
- 输入规范化、校验、默认值稳定

### 7.2 团队蓝图完成

- 有稳定 `TeamBlueprint / RoleBlueprint`
- Manager/Researcher 及后续扩展角色有明确最小模型

### 7.3 编译完成

- 行业初始化到 goals/steps/context 的编译链独立可测
- bootstrap service 不再内嵌大段临时规则

### 7.4 运行面完成

- 行业实例在 Runtime Center 中可见
- 有启动入口
- 有默认 schedule

### 7.5 报告完成

- 至少有一版 evidence-driven 日报或状态摘要

### 7.6 约束完成

- Manager/Researcher 基础 capability allowlist 和风险边界已落地

### 7.7 交付完成

- 有最小前端工作台
- 有自动化测试矩阵
- 有文档同步与删旧准备
- 已完成正式 MVP 验收

---

## 8. 当前推荐施工顺序

如果目标是“别留下尾巴”，A/B 本轮已经按以下顺序收口完成；本节保留为复盘台账，而不再作为活跃待办。

### 第一波

- A1
- A3
- B1
- B2
- B3

状态：

- 已完成（`2026-03-11`）
- `Gate G1` 已达成

原因：

- 先钉死模型与宿主边界
- 防止后续 UI、schedule、日报建立在漂移模型上

### 第二波

- A2
- A5
- B4
- B5
- B6

状态：

- 已完成（`2026-03-11`）
- `Gate G2` 已达成

原因：

- 先接通可见化与持续运行
- 同时继续收掉旧兼容壳，避免新旧两边一起膨胀

### 第三波

- A4
- B7
- B8（若前序未随 `A3` 提前完成，则在此收口正式角色授权模型）
- B9
- B10
- B11
- B12

状态：

- 已完成（`2026-03-11`）
- `Final Gate` 已达成

原因：

- 最后统一做“真实可交付”的部分：报告、验收、测试、文档、删尾

---

## 9. 删尾检查表

每完成一波，必须检查下面这张表。

### 9.1 新增内容

- 本波新增了哪些对象
- 本波新增了哪些 API
- 本波新增了哪些前端入口

### 9.2 兼容内容

- 本波引入了哪些临时承载位
- 是否已登记到 `DEPRECATION_LEDGER.md`
- 删除条件是否明确

### 9.3 删除内容

- 本波退役了哪些旧逻辑
- 本波删除了哪些兼容代码
- 是否仍有“双写但未登记”的路径

### 9.4 验收内容

- 本波新增了哪些测试
- 哪些是真实环境 smoke
- 哪些是 operator/manual E2E

### 9.5 文档内容

- 是否同步 `TASK_STATUS.md`
- 是否同步 `implementation_plan.md`
- 是否同步 `PHASEB_EXECUTION_PLAN.md`
- 是否同步 `DEPRECATION_LEDGER.md`

---

## 10. 当前结论

这张并行推进图的结论现在很简单：

> `Phase A` 与 `Phase B` 的当前目标已经按 gate 受控并行推进并全部收口，且每一波都同步了进度、兼容位、删旧条件和验收结果。

截至 `2026-03-11`：

- 第一波已经收口
- 第二波已经收口
- 第三波已经收口
- `Phase A` 与 `Phase B` 的当前并行推进图已经完成其使命

接下来的要求不是重开 A/B，而是：

- 沿着 `DEPRECATION_LEDGER.md` 清理剩余 carrier 与兼容别名
- 把行业对象与环境宿主继续推进到更正式的仓储/恢复形态
- 在扩大真实世界覆盖前不再扩散新的表层能力

本文件创建后，后续凡是需要复盘“为什么 A/B 能一次收口”的任务，都应以本文件作为 gate 台账入口。
