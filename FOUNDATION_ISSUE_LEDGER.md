# FOUNDATION_ISSUE_LEDGER.md

本文件用于登记 `CoPaw` 的“底座级问题单”。

它只收录 3 类问题：

1. `真 bug`
2. `真回归`
3. `新范围进入底座合同`

不属于这 3 类的事项，不应登记到本台账。

---

## 1. 这份台账解决什么问题

目的不是把所有开发待办都塞进来，而是防止底座主链被以下几种模糊说法污染：

- “这里好像还能再优化一下”
- “这个顺手再抽象一层”
- “这里再做漂亮一点”
- “虽然不是 bug，但总感觉还差点”

底座一旦闭环，只允许因为以下 3 类原因再动：

1. 已承诺行为实现错了
2. 以前对的行为被后来改坏了
3. 以前不在底座范围内，现在被正式纳入底座承诺

---

## 2. 收录铁律

只有同时满足以下要求的问题，才允许登记：

- 问题直接影响 `state / kernel / continuity / runtime-center / host truth / evidence / main-brain cognition` 这类底座主链
- 问题能明确归入 `真 bug / 真回归 / 新范围进入底座合同`
- 问题有清晰的合同、现象、验证方式、验收标准

以下事项默认**不收录**：

- 纯文案优化
- 纯视觉调整
- 不改行为的普通重构
- “还能更快一点”的泛化性能愿望
- 仅属于上层产品扩展、但未进入底座合同的新增能力

---

## 3. 三类问题定义

### 3.1 真 bug

定义：

- 按当前底座合同，本来就应该是对的
- 但实际实现是错的

判定问题：

- 这条行为是否已经写进正式对象、正式路由、正式状态板或正式测试口径？
- 如果答案是“是”，而实现结果不符合预期，这就是 `真 bug`

标准表述：

- `预期`
- `实际`
- `违反的既有合同`

### 3.2 真回归

定义：

- 这条行为以前是对的
- 后来某次改动把它改坏了

判定问题：

- 是否存在已通过的回归、历史提交、既有测试、既有状态口径证明“它以前是好的”？
- 如果答案是“是”，而现在坏了，这就是 `真回归`

标准表述：

- `以前正确的基线`
- `当前退化现象`
- `疑似引入改动`

### 3.3 新范围进入底座合同

定义：

- 以前这个点不在底座正式承诺里
- 现在被明确提升为底座必须保证的范围

判定问题：

- 以前是否只是增强项/附属能力/未承诺范围？
- 现在是否被正式写进终态标准、状态板、架构图、验收门槛？
- 如果是，这就是 `新范围进入底座合同`

标准表述：

- `新增承诺范围`
- `为什么现在必须算底座`
- `新的验收门槛`

---

## 4. 判定流程

按顺序判断：

1. 这是不是底座主链问题？
   - 如果不是，不进本台账
2. 按当前正式定义，它本来就该是对的吗？
   - 是：记为 `真 bug`
3. 它以前是否明确是对的，现在被改坏了？
   - 是：记为 `真回归`
4. 它以前是否不在底座承诺里，现在被正式纳入？
   - 是：记为 `新范围进入底座合同`
5. 三条都答不上来：
   - 不进本台账

---

## 5. 状态枚举

- `open`
- `in_progress`
- `resolved`
- `rejected`

说明：

- `rejected` 不是“做不了”，而是“不属于底座问题单”

---

## 6. 登记模板

```md
## FI-YYYYMMDD-XXX 标题

- 状态：`open|in_progress|resolved|rejected`
- 类型：`真 bug | 真回归 | 新范围进入底座合同`
- 合同：
- 现象：
- 触发路径：
- 影响范围：
- 判断依据：
- 验证：
- 验收标准：
- owner：
- 备注：
```

---

## 7. 当前登记样例

说明：

- 下列条目主要用于把最近一轮真实问题具体化成标准问题单
- 当前没有额外未解决的底座级 active 条目；这些样例大多已经在代码中修复并通过回归

## FI-20260330-001 `work_context` 记忆优先级错误

- 状态：`resolved`
- 类型：`真 bug`
- 合同：`work_context_id` 是正式 continuity key；同一连续工作上下文的 recall 应优先于行业级粗粒度 recall
- 现象：同时存在 `industry_instance_id + work_context_id` 时，主脑 recall 仍优先锚到 `industry`
- 触发路径：`main_brain_chat_service -> truth-first recall`
- 影响范围：主脑 follow-up turn、媒体/记忆连续追问、控制线程连续性
- 判断依据：按既有 continuity 合同，这条优先级本来就应该正确
- 验证：`tests/kernel/test_main_brain_chat_service.py`
- 验收标准：同一请求同时带 `industry + work_context` 时，主脑与 recall consumer 都优先消费 `work_context`
- owner：`kernel`
- 备注：已修复

## FI-20260330-002 runtime chat media 连续性漏透传

- 状态：`resolved`
- 类型：`真 bug`
- 合同：`/media/analyses`、console chat、truth-first memory 应共享 `work_context` continuity contract
- 现象：仓储层已支持 `work_context_id`，但 API 和前台列表链路没透出来，恢复后同一工作上下文的素材分析拉不回来
- 触发路径：`media router -> media api -> useChatMedia`
- 影响范围：chat media follow-up、恢复后连续上下文、Runtime Center 读面
- 判断依据：媒体分析已经是正式对象，连续工作上下文也已是正式合同
- 验证：`tests/app/test_runtime_chat_media.py`、`console/src/pages/Chat/useChatMedia.test.tsx`
- 验收标准：恢复/换线程后，只要 `work_context_id` 未变，素材分析仍可重新加载
- owner：`media + console`
- 备注：已修复

## FI-20260330-003 media-backed memory 无法追回原始 analysis

- 状态：`resolved`
- 类型：`真 bug`
- 合同：`MediaAnalysisRecord` 是正式对象；media-backed memory hit 应能追回原始分析对象，而不是只停在 retain chunk
- 现象：truth-first recall 命中 `media-analysis:*` 后，路由仍落到 knowledge chunk
- 触发路径：`derived_index_service -> source_route_for_entry`
- 影响范围：Runtime Center trace closure、媒体证据追踪、后续审计/回放
- 判断依据：正式对象已经存在，route 应回原对象而不是派生临时块
- 验证：`tests/state/test_truth_first_memory_recall.py`
- 验收标准：media-backed recall hit 直接返回 `/api/media/analyses/{analysis_id}`
- owner：`memory`
- 备注：已修复

## FI-20260330-004 显式 interaction mode 被旧缓存污染

- 状态：`resolved`
- 类型：`真回归`
- 合同：显式 `interaction_mode=chat|orchestrate` 必须压过旧缓存
- 现象：旧 `_copaw_requested/_copaw_resolved_interaction_mode` 会错误影响当前 turn 的显式 mode
- 触发路径：`turn_executor -> _prepare_request_interaction_mode`
- 影响范围：chat/orchestrate 隔离、主脑前门稳定性、执行噪音回流
- 判断依据：已有 mode-isolation 基线与既有测试证明显式 mode 应该优先
- 验证：`tests/kernel/test_turn_executor.py`
- 验收标准：显式 mode 永远以当前请求为准，旧缓存只在严格同 key 下复用
- owner：`kernel`
- 备注：已修复

## FI-20260331-001 phase-next 长跑 smoke 纳入 multi-seat/shared-writer contention

- 状态：`resolved`
- 类型：`新范围进入底座合同`
- 合同：phase-next 长跑 smoke 不再只覆盖 `handoff -> human-assist -> resume -> replan`，还必须覆盖 `multi-seat candidate/selected seat` 与 `multi-agent shared-writer contention`
- 现象：这些场景原本只在环境层单测里出现，没有进入 phase-next 主 smoke
- 触发路径：`tests/app/test_phase_next_autonomy_smoke.py`
- 影响范围：真实世界覆盖、长期自治回归、Host Twin 成熟度门槛
- 判断依据：这次已明确把更长跑、更复杂宿主协调纳入底座验收
- 验证：phase-next autonomy smoke
- 验收标准：长跑 smoke 同时锁住 `multi-seat`、`selected seat`、`shared-writer contention`、`handoff/reentry/resume`
- owner：`tests / host continuity`
- 备注：已纳入并验证

## FI-20260331-002 短 inspection 聊天请求仍触发 intake classifier

- 状态：`resolved`
- 类型：`真 bug`
- 合同：纯聊天态必须保持轻量；短 inspection 聊天请求不应无脑触发 main-brain intake classifier
- 现象：像“帮我看一下”这类短请求在 `auto` 模式下仍会多跑一轮 intake 解析
- 触发路径：`turn_executor -> _resolve_auto_chat_mode`
- 影响范围：首字延迟、纯聊天轻量链、主脑聊天性能
- 判断依据：当前状态板已明确把纯聊天态定义为轻量低负载链
- 验证：`tests/kernel/test_turn_executor.py`
- 验收标准：短 inspection 聊天请求直接走 chat fast-path，不触发 intake classifier
- owner：`kernel`
- 备注：已修复

---

## 8. 当前结论

当前仓库后续如果再出现底座问题，必须先回答：

- 它是 `真 bug`？
- 它是 `真回归`？
- 还是 `新范围进入底座合同`？

如果三者都不是，就不应继续以“底座未完成”为由扩大施工面。
