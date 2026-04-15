# CoPaw 记忆睡眠整理层 B+ 设计与 C 路线规划

日期：`2026-04-15`

## 1. 目标

这次不是重写整套记忆系统，而是在现有 `truth-first` 基础上补上正式的“睡眠整理层”。

本轮正式目标：

- 落地 `B+`：`truth-first` 底座不变，但让大模型在夜间拥有更强的上层解释权
- 把第二天的 `memory surface / cockpit / recall` 主读链，从“旧文本派生优先”切到“对象/图真相 + 睡眠整理结果优先”
- 停止继续把 `stop words` 当长期主方案；它们只保留为展示兜底
- 同时把 `C` 的升级路线整理清楚，但不在本轮实现

一句话：

> 白天系统继续稳定写真相，夜里由大模型像“睡眠整理”一样归并、归纳、提炼、暂存软规则，并在第二天主导上层解释口径，但不改底层原始事实。

## 2. 结论先说死

### 2.1 本轮做什么

本轮正式做：

- `industry / work_context` 两类 scope 的睡眠整理
- 脏 scope 增量整理
- 结构化睡眠产物落库
- 第二天主读链切换
- 软规则的自动生效与升级条件
- 冲突/长期规则变更的提案化处理

### 2.2 本轮不做什么

本轮明确不做：

- 不碰私有聊天压缩主链
- 不让模型改写原始 `evidence / report / assignment / knowledge chunk`
- 不把夜间模型结果升级成第二套底层真相
- 不直接进入 `C` 的“夜间重构主导态”
- 不引入向量库作为正式主链依赖
- 不引入第二套 graph 数据库

### 2.3 最终定位

本轮不是纯 `B`，也不是 `C`，而是：

`B+ = truth-first 底座 + model-steered sleep layer`

含义是：

- 底层真相仍由 canonical state / evidence / graph projection 锚定
- 大模型开始掌控“次日的上层解释权”
- 但大模型仍不能直接掌控“底层原始真相写死权”

## 3. 为什么是 B+，不是纯 B，也不是直接上 C

### 3.1 纯 B 不够

如果只是夜里生成一些摘要，但第二天系统仍主要读旧的文本派生链，那系统只是在原结构上“多贴一层皮”，不能真正解决：

- 展示机器味重
- 仍然依赖补词表救火
- 主读链仍受旧 lexical 派生拖累

### 3.2 直接上 C 太激进

`C` 的本质是“夜间模型开始重建高层 memory view，并更深地主导第二天运行入口”。

当前阶段直接上 `C` 风险过高：

- 模型漂移会直接放大
- 回滚难度明显增大
- 验收标准会从“能不能跑”变成“会不会长期漂”
- 当前主链刚收口，先把 `B+` 跑稳更合理

### 3.3 B+ 正好卡在正确位置

`B+` 的价值是：

- 比纯 `B` 更强，模型真的开始掌解释权
- 比 `C` 更稳，底层原始真相仍然硬锚在 state/evidence/object/graph 上
- 最适合当前仓库已经存在的 `truth-first + graph projection` 基线

## 4. 当前基线与挂载位置

当前仓库已经有这些正式基础：

- `StateKnowledgeService`
- `MemoryRetainService`
- `DerivedMemoryIndexService`
- `MemoryReflectionService`
- `MemoryRecallService`
- `MemoryActivationService`
- `KnowledgeGraphService`
- `KnowledgeWritebackService`

当前正式边界已经明确：

- 正式共享记忆是 `truth-first`
- 正式 durable memory 不走 vector 主链
- `ConversationCompactionService` 只负责私有聊天压缩，不再充当正式共享记忆真相

因此，这次睡眠整理层的正确落位是：

- 输入层：消费 canonical `state / evidence / graph projection`
- 整理层：新增 `memory sleep layer`
- 读层：由 `Runtime Center / memory surface / recall` 优先消费整理结果

不是：

- 在私有聊天压缩层上继续堆功能
- 让模型直接决定底层原始事实
- 在 `state` 旁边再造第二套 memory truth store

## 5. B+ 的正式边界

### 5.1 整理对象边界

只整理正式共享记忆：

- `industry`
- `work_context`
- 后续可扩 `global`

本轮不整理：

- 私有聊天压缩
- 单线程私聊 sidecar
- 临时 prompt cache
- 非正式草稿

### 5.2 模型权限边界

大模型在 B+ 里拥有的是：

- 上层摘要权
- 归并权
- 别名归一权
- 低风险软规则生成权
- 次日默认展示口径控制权

大模型在 B+ 里不拥有的是：

- 底层原始事实改写权
- 原始 evidence 删除权
- 原始 report 篡改权
- assignment / work_context 原始真相改写权

### 5.3 风险边界

自动生效只允许发生在低风险上层派生对象：

- digest
- alias
- merge
- 低风险 soft-rule
- 低风险次日解释口径

高风险变化只能提案：

- 冲突结论
- 长期规则变更
- 涉及审批、资金、合规、外部动作的长期约束变化

## 6. 输入边界

### 6.1 可作为主输入的正式材料

每个 scope 的夜间整理，主输入只能来自正式共享真相：

- `StrategyMemoryRecord`
- `KnowledgeChunkRecord`（只限正式 memory scope）
- `EvidenceRecord`
- execution graph projection
- `Assignment / WorkContext / AgentReport / Backlog / Cycle` 的正式投影
- 当前 scope 已生效的 `digest / alias / soft-rule / conflict proposal`

### 6.2 可作为补充输入的材料

这些可以喂，但只能是补充，不得压过正式对象关系：

- 原始 text memory 自然语言内容
- report summary 自由文本
- chat writeback 的自然语言说明

### 6.3 明确禁止作为主输入的材料

本轮硬禁止进入 B+ 睡眠整理主输入：

- 私有聊天压缩内容
- 单线程 sidecar 摘要
- prompt cache
- 只存在于前端的字符串拼装结果
- 非正式草稿和未入真相链的临时说明

### 6.4 输入打包结构

每个 scope 的睡眠整理输入应打成 4 组，不允许只丢全文文本给模型：

1. `formal_facts`
   - strategy
   - knowledge chunks
   - evidence
   - report anchors

2. `formal_relations`
   - graph projection
   - dependency / blocker / support / contradiction paths
   - ownership / handoff / work-context 关系

3. `current_memory_views`
   - current digest
   - alias map
   - soft rules
   - active proposals

4. `recent_changes`
   - 新增什么
   - 失效什么
   - 哪些关系迁移了
   - 哪些 scope 被标记为 dirty

原则：

> B+ 的睡眠整理必须以正式对象和正式关系为主输入，自由文本只能做补充，不得反客为主。

## 7. 正式对象设计

### 7.1 `MemorySleepJob`

用途：

- 记录一次睡眠整理任务

建议字段：

- `job_id`
- `scope_type`
- `scope_id`
- `trigger_kind`：`scheduled / idle / manual`
- `window_start`
- `window_end`
- `status`：`queued / running / completed / failed / skipped`
- `input_refs`
- `output_refs`
- `model_ref`
- `started_at`
- `completed_at`
- `metadata`

### 7.2 `MemoryScopeDigest`

用途：

- scope 的阶段摘要
- 第二天默认主读的高层口径

建议字段：

- `digest_id`
- `scope_type`
- `scope_id`
- `headline`
- `summary`
- `current_constraints`
- `current_focus`
- `top_entities`
- `top_relations`
- `evidence_refs`
- `source_job_id`
- `version`
- `status`：`active / superseded`
- `created_at`
- `updated_at`

### 7.3 `MemoryAliasMap`

用途：

- 同义表达归一
- recall / activation / display 的别名辅助层

建议字段：

- `alias_id`
- `scope_type`
- `scope_id`
- `canonical_term`
- `aliases`
- `confidence`
- `evidence_refs`
- `source_job_id`
- `status`
- `created_at`
- `updated_at`

### 7.4 `MemoryMergeResult`

用途：

- 把多条相近记忆合并成统一主题

建议字段：

- `merge_id`
- `scope_type`
- `scope_id`
- `merged_title`
- `merged_summary`
- `merged_source_refs`
- `evidence_refs`
- `source_job_id`
- `status`：`active / superseded`
- `created_at`
- `updated_at`

### 7.5 `MemorySoftRule`

用途：

- 夜间整理得出的软规则

建议字段：

- `rule_id`
- `scope_type`
- `scope_id`
- `rule_text`
- `rule_kind`
- `evidence_refs`
- `hit_count`
- `day_span`
- `conflict_count`
- `risk_level`
- `state`：`candidate / active / promoted / rejected / expired`
- `source_job_id`
- `expires_at`
- `created_at`
- `updated_at`

### 7.6 `MemoryConflictProposal`

用途：

- 冲突结论提案
- 长期规则变更提案

建议字段：

- `proposal_id`
- `scope_type`
- `scope_id`
- `proposal_kind`：`conflict / long_term_rule_change`
- `title`
- `summary`
- `conflicting_refs`
- `supporting_refs`
- `recommended_action`
- `risk_level`
- `status`：`pending / accepted / rejected / expired`
- `source_job_id`
- `created_at`
- `updated_at`

## 8. 夜间模型输出合同

夜间模型不能只写作文，必须先产出结构化结果。

每个 scope 的睡眠整理最少输出这 5 块：

### 8.1 `digest`

- `headline`
- `summary`
- `current_constraints`
- `current_focus`
- `top_entities`
- `top_relations`
- `evidence_refs`

### 8.2 `alias_updates`

- `canonical_term`
- `aliases`
- `confidence`
- `evidence_refs`

### 8.3 `merge_updates`

- 哪些 source 可以归并
- 归并后的主题标题
- 归并摘要
- 归并依据

### 8.4 `soft_rule_updates`

- `rule_text`
- `rule_kind`
- `evidence_refs`
- `hit_count`
- `day_span`
- `conflict_count`
- `risk_level`
- `recommend_state`

### 8.5 `conflict_proposals`

- `proposal_kind`
- `title`
- `summary`
- `conflicting_refs`
- `supporting_refs`
- `recommended_action`
- `risk_level`

### 8.6 可选自然语言说明

只做解释，不是正式对象：

- `operator_explanation`
- `why_this_changed`
- `why_not_promoted`
- `why_conflict_exists`

硬规则：

> B+ 里，模型夜间整理的正式产物必须是结构化对象，不允许只有自然语言长文。

## 9. 自动生效与提案分层

### 9.1 自动生效

这些结果允许自动落库并生效：

- `MemoryScopeDigest`
- `MemoryAliasMap`
- `MemoryMergeResult`
- 低风险 `MemorySoftRule`
- 低风险的次日展示口径和主读排序

### 9.2 自动生效但必须可回滚

这些允许自动生效，但必须显式可回滚：

- `active` 状态的低风险 soft-rule
- 低风险冲突裁决写出的上层摘要
- recall / activation 的上层优先级微调结果

### 9.3 只能挂提案

这些只允许生成提案：

- 高风险冲突结论
- 高风险长期规则变更
- 审批、合规、资金、对外动作相关规则变化
- 强冲突且证据未收敛的大结论

## 10. 模型权限分层

### 10.1 `L1` 模型直接掌权

模型可以直接决定：

- digest
- alias
- merge
- 次日默认展示摘要
- 主读排序
- 人话化解释口径

### 10.2 `L2` 模型可自动生效，但必须可回滚

模型可以自动生效：

- soft-rule
- 低风险冲突裁决
- 低风险长期偏好更新
- 次日主读视图的上层解释顺序

### 10.3 `L3` 模型只能提案

模型不能直接决定：

- 高风险长期规则
- 合规/审批/资金/外部动作相关长期约束
- 强冲突且证据不收敛的最终结论

一句话：

> B+ 里，大模型拥有的是“上层解释权”，不是“底层原始真相写死权”。

## 11. 触发策略

### 11.1 主触发

- 固定时间触发，默认建议凌晨

### 11.2 补触发

- 如果固定时间系统仍忙，则顺延到空闲时补跑

### 11.3 手动触发

后续允许聊天触发，但不是本轮重点：

- “今晚整理一下行业记忆”
- “现在先跑一次记忆睡眠整理”

## 12. dirty-scope 增量机制

### 12.1 原则

不是每天全量整理所有 scope，而是：

- 白天谁变脏了，就标记谁
- 夜里优先整理 dirty scope

### 12.2 dirty 标记来源

以下事件应标记对应 scope dirty：

- strategy 更新
- formal knowledge 写入
- report 写回
- evidence 写入
- assignment / backlog / work_context / cycle graph projection 更新
- 软规则升降级
- 冲突提案状态变化

### 12.3 dirty 清理

只有 `MemorySleepJob` 完整成功并产出结构化结果后，scope 才能清脏。

## 13. 软规则流转

### 13.1 状态

- `candidate`
- `active`
- `promoted`
- `rejected`
- `expired`

### 13.2 升级条件

软规则不按固定天数升级，按稳定性条件升级：

- 至少 `3` 次独立命中
- 跨 `2` 个自然日
- 没有强冲突证据

### 13.3 生效策略

- 低风险规则：
  - 满足稳定条件后可自动从 `active -> promoted`
- 高风险规则：
  - 满足稳定条件后只生成 proposal，不直接转正

### 13.4 过期与回滚

一旦后续出现：

- 强冲突证据
- 命中持续下降
- 作用范围明显收缩

则规则应：

- 自动降级
- 或进入 `expired`
- 或重新进入 proposal 审查

## 14. 冲突提案流转

### 14.1 处理方式

冲突提案不能覆盖旧事实，也不能删除旧事实。

正确流转是：

1. 发现冲突
2. 生成 `MemoryConflictProposal`
3. 低风险的先写上层摘要
4. 高风险的进入 proposal/pending
5. 如果后续人工或系统确认，写入新的上层规则摘要
6. 保留原始事实可追溯

### 14.2 批准后的变化

批准后允许更新的是上层派生对象：

- digest
- alias
- soft-rule
- planning constraints
- 展示层解释

批准后不允许更新的是底层原始对象：

- 原始 evidence
- 原始 report
- 原始 knowledge chunk
- 原始 assignment 历史

## 15. 第二天主读链切换

这是 B+ 相比纯 B 的关键升级。

第二天 `memory surface / cockpit / recall` 的正式读优先级应变成：

1. canonical object / graph truth
2. sleep digest / alias / merge / soft-rule
3. raw text memory
4. lexical fallback

意味着：

- 旧文本派生链不再是主读层
- 旧 lexical 机制退到补充/兜底层
- 第二天系统首先读“经过夜间整理的上层解释结果”

## 16. 与现有模块的关系

### 16.1 保留并继续作为底座的模块

- `StateKnowledgeService`
- `MemoryRetainService`
- `DerivedMemoryIndexService`
- `MemoryReflectionService`
- `KnowledgeGraphService`
- `KnowledgeWritebackService`

### 16.2 明确不升格的模块

- `ConversationCompactionService`

它继续只做：

- 私有聊天压缩
- 线程内对话节流
- 私有 sidecar 辅助

它不应承担：

- 正式共享记忆写入 owner
- 正式共享记忆召回 owner
- 睡眠整理主输入

## 17. 本轮实现范围

### 17.1 本轮实现

- `industry` scope
- `work_context` scope
- sleep job
- digest / alias / merge / soft-rule / conflict-proposal
- dirty scope 增量整理
- 第二天主读链切换

### 17.2 本轮不实现

- 私有聊天压缩睡眠整理
- `agent` 私有长期偏好睡眠层
- 多模态记忆睡眠整理
- `C` 的夜间重构主导态

## 18. 验收标准

本轮完成后必须满足：

1. 白天正式真相仍只由 canonical state/evidence/object/graph 锚定
2. 夜间整理只消费正式共享记忆，不碰私有聊天压缩主链
3. `industry / work_context` 能生成稳定的 digest / alias / merge / soft-rule / proposal
4. 第二天 `memory surface / cockpit / recall` 已优先读取睡眠整理结果
5. 低风险结果可自动生效，且保留回滚路径
6. 高风险长期规则和冲突结论只生成提案，不直接改底层原始事实
7. 旧 lexical/stop-word 机制退回补充层，而不是继续当主方案

## 19. C 的后续规划

### 19.1 C 的定义

`C` 不是简单把 B+ 做大，而是：

> 让夜间模型开始拥有更强的“夜间重构权”，即模型不只是整理，而是开始重建第二天的高层 memory view。

### 19.2 C 和 B+ 的区别

`B+`

- 模型掌上层解释权
- object/graph truth 仍是第一锚点
- 第二天读链仍明显 anchored on canonical truth

`C`

- 模型开始主导“夜间重构后的高层 memory view”
- digest / relation / focus / rule 之间的次日入口更强依赖夜间重构结果
- object/graph truth 仍然存在，但更多退居底层锚点

### 19.3 C 的前置条件

以下条件没满足前，禁止直接上 C：

1. B+ 的 sleep 对象已经稳定运行
2. graph/object truth 已成为主读底座
3. B+ 的 digest / alias / soft-rule 在真实长跑里足够稳定
4. 自动回滚和 proposal 审计链已经成熟
5. 真实验证证明夜间整理不会明显漂移

### 19.4 C 适合新增的能力

等 B+ 稳定后，C 可以考虑新增：

- 夜间“主题重建”
- 次日 memory view 整体重排
- 跨 scope 的长期规律整合
- 更强的模型驱动 recall entrance
- 模型主导的阶段认知重构

但 C 仍然必须遵守一条底线：

> 即使进入 C，模型也不能直接篡改底层原始事实。

## 20. 非目标

这份设计明确不是：

- 引入新的底层 memory truth store
- 重建一套 graph-native 独立数据库
- 让私有聊天压缩重新升级为正式真相源
- 把大模型升级成“白天实时裁判”
- 用外部通用聊天记忆框架直接替换这套执行系统的正式记忆主链

## 21. 一句话总结

这次 `B+` 的本质不是“给记忆系统多加一个夜间任务”，而是：

> 在不动底层原始真相的前提下，让大模型正式接管第二天的上层记忆解释权，同时为未来 `C` 的夜间重构能力提前铺好对象、边界、调度和风险治理框架。
