# Memory VNext Plan

本文件用于把 `CoPaw` 下一阶段的记忆升级方向收口成正式方案。

这次升级的参考对象不是“照搬 OpenClaw 当前默认稳定版 memory”，而是借鉴其正在研究的 `Workspace Memory v2` 方向中真正有价值的部分：

- `derived index`
- `Retain / Recall / Reflect`
- `entity / opinion / confidence`
- hybrid recall 与可替换检索后端

同时，本方案明确拒绝把 `CoPaw` 拉回到 `MEMORY.md / memory/YYYY-MM-DD.md` 这类文件型真相源。

---

## 1. 一句话结论

`CoPaw` 的记忆升级应当做成：

> `state / evidence` 仍是单一真相源，在其上新增可重建的 `derived memory index`、正式 `Retain / Recall / Reflect` 服务，以及 `entity / opinion / confidence` 读模型。

而不是：

> 再造一套独立 memory store，或者把 Markdown 工作区文件升格为新的正式真相源。

---

## 2. 为什么不是直接照搬 OpenClaw

`OpenClaw` 当前公开的正式 memory 主链，仍偏向：

- workspace Markdown canonical source
- `MEMORY.md` + `memory/YYYY-MM-DD.md`
- `memory_search / memory_get`
- SQLite / QMD / vector sidecar 作为检索层

这套设计适合“单助手 + 工作区记忆”场景，但 `CoPaw` 当前已经进入：

- `StrategyMemoryRecord`
- `KnowledgeChunkRecord`
- `EvidenceRecord`
- `ExecutionRoutineRecord / RoutineRunRecord`
- `AssignmentRecord / AgentReportRecord`

这些对象都已经属于统一 `state / evidence / kernel` 主链。

如果直接照搬 OpenClaw 的 Markdown-first memory，会出现两个明显问题：

1. 会重新引入第二真相源。
2. 会把战略、执行、证据、报告之间已经建立好的正式关系重新打散。

因此这里真正要借的是它的“记忆能力层设计”，不是它的“文件型真相源落点”。

---

## 3. 本次升级的正式目标

### 3.1 必须得到的能力

- 让 recall 不再只是简单 `KnowledgeChunkRecord` 文本召回，而是支持混合排序、实体关联、时间衰减、观点置信度。
- 让 retain 不再只是“谁手动记了什么”，而是从 evidence / report / writeback / terminal outcome 中沉淀 durable facts。
- 让 reflect 成为正式后台作业，把近期事实编译成可读、可见、可治理的长期结论。
- 让前端能直接看到 `entity / opinion / confidence / recent supporting evidence`，而不是每次临时拼 prompt。

### 3.2 必须守住的边界

- 不新增第二真相源。
- 不让 `MemoryManager` 重新长回主链。
- 不把全文 prompt transcript、整页 HTML、长日志直接塞进长期记忆对象。
- 不允许 sidecar 向量库成为正式写入口。

---

## 4. 正式设计原则

### 4.1 Canonical source 仍然只有一套

记忆增强之后，正式真相源仍是：

- strategic truth: `StrategyMemoryRecord`
- long-term fact truth: `KnowledgeChunkRecord`
- execution truth: `Goal / Task / Schedule / RoutineRun / AgentReport`
- evidence truth: `EvidenceRecord / Artifact / Replay / ReportRecord / MetricRecord`

`derived memory index` 只允许是：

- rebuildable
- disposable
- query-oriented

它不能成为：

- canonical write target
- only-copy storage
- private agent brain

### 4.2 Retain 写入 canonical layer，而不是写进 sidecar

`Retain` 的职责是把高价值事实沉淀为正式长期记忆，而不是单纯“做一份 embedding”。

因此 retain 的正式落点应优先是：

- `KnowledgeChunkRecord`
- `StrategyMemoryRecord` 的受控刷新
- 必要时的 compiled summary read model

### 4.3 Recall 通过统一 recall facade 暴露

不允许 future caller 直接依赖某个向量库或 QMD CLI。

正式读入口应统一到：

- `MemoryRecallService` 或等价 facade

其内部可接：

- SQLite FTS
- local vector index
- QMD sidecar
- LanceDB sidecar

但对上层：

- `GoalService`
- `WorkflowTemplateService`
- `PredictionService`
- `KernelQueryExecutionService`
- Runtime Center / Knowledge / Industry read surfaces

都应只看统一 recall contract。

### 4.4 Reflect 是编译与治理，不是隐式人格漂移

`Reflect` 的职责不是偷偷改 agent，而是：

- 生成 `entity` read model
- 生成 `opinion` read model
- 计算 confidence 与 supporting/contradicting evidence
- 生成 compiled summary
- 必要时提出 patch / proposal

高风险反思结果仍应走：

- review
- decision
- patch

而不是直接静默改战略或改主脑长期身份。

---

## 5. CoPaw 的 Memory VNext 分层

## 5.1 Strategic memory

正式对象：

- `StrategyMemoryRecord`

职责：

- 长期使命
- 北极星
- 优先级
- 规划政策
- 委派原则
- 证据要求

不新增平行 strategic memory store。

## 5.2 Long-term fact memory

正式对象：

- `KnowledgeChunkRecord`

职责：

- durable facts
- agent/task/industry/global scope memory
- child-agent 经验回写
- 可被 recall 的长期知识与长期经验

## 5.3 Working memory

保留在本地执行位：

- mailbox
- checkpoint
- runtime frame
- resume cursor
- transient queue state

working memory 不默认升级为共享长期真相。

## 5.4 Operation memory

正式对象：

- `ExecutionRoutineRecord`
- `RoutineRunRecord`

职责：

- 叶子执行肌肉记忆
- deterministic replay
- drift diagnose
- fallback telemetry

## 5.5 Derived memory layer

这是本次新增层，但它不是新的真相层。

建议新增读模型或派生对象：

- `MemoryFactIndexEntry`
- `EntityMemoryView`
- `OpinionMemoryView`
- `MemoryRecallHit`
- `MemoryReflectionRun`

其中：

- `MemoryFactIndexEntry` 用于 recall 排序与引用，不作为唯一事实副本
- `EntityMemoryView` 汇总实体相关的事实、偏好、状态、最近变化
- `OpinionMemoryView` 汇总观点、置信度、支持证据、冲突证据、最近刷新时间
- `MemoryReflectionRun` 记录一次 reflect 编译作业的输入、输出与证据范围

第一阶段可以先不把这些全部做成正式 SQLite 表；允许先落成：

- rebuildable read model
- cache table
- materialized summary

但必须满足“可重建、可追溯、不可单独成为真相源”。

---

## 6. Retain / Recall / Reflect 正式接线

## 6.1 Retain

`Retain` 的输入应优先来自正式执行结果，而不是纯 prompt 习惯：

- terminal `TaskRecord / TaskRuntimeRecord`
- `AgentReportRecord`
- `ReportRecord`
- `EvidenceRecord`
- `RoutineRunRecord`
- execution-core chat writeback
- approved patch / review outcome

`Retain` 的输出应分两类：

1. canonical facts
   - 写入 `KnowledgeChunkRecord`
   - 在严格边界内刷新 `StrategyMemoryRecord`

2. derived indexing material
   - 更新 recall index
   - 更新 entity/opinion candidates

## 6.2 Recall

`Recall` 应支持至少四种检索维度：

- lexical recall
- semantic recall
- entity-linked recall
- temporal recall

建议排序信号：

- lexical score
- vector similarity
- scope affinity
- entity overlap
- recency / decay
- confidence / source quality

`Recall` 的返回必须带正式引用：

- `kind`
- `summary`
- `content_excerpt`
- `source_type`
- `source_ref`
- `evidence_refs`
- `confidence`
- `timestamp`

## 6.3 Reflect

`Reflect` 应是定时或事件驱动的正式后台作业：

- daily
- weekly
- heartbeat
- major execution milestone

它的职责：

- 聚合近期 retained facts
- 更新 entity summary
- 更新 opinion/confidence
- 生成 compiled summary
- 发现冲突和陈旧观点
- 必要时向 learning 层提交 proposal / patch candidate

---

## 7. 对 OpenClaw 的借鉴点与拒绝点

### 7.1 明确借鉴

- `Retain / Recall / Reflect`
- `entity / opinion / confidence`
- derived index
- hybrid retrieval
- optional sidecar backend

### 7.2 明确不借

- `MEMORY.md` 成为系统正式真相源
- `memory/YYYY-MM-DD.md` 成为 durable memory 主存储
- 让 agent 直接对 sidecar 写入 durable truth
- 让长期记忆只作为 prompt 附件存在

---

## 8. 服务与目录落点建议

建议新增：

```text
src/copaw/memory/
  retain_service.py
  recall_service.py
  reflection_service.py
  derived_index_service.py
  models.py
```

建议保持现有正式真相层不变：

```text
src/copaw/state/
src/copaw/evidence/
src/copaw/learning/
src/copaw/kernel/
```

兼容边界：

- 旧 `src/copaw/agents/memory/memory_manager.py` 继续存在，但逐步退化为：
  - prompt compaction
  - legacy search bridge
  - local helper

而不是 durable memory authority。

---

## 9. 建议施工顺序

`2026-03-18` 状态更新：
- `M1 -> M4` 已完成当前轮正式收口。
- canonical truth 仍然只有 `state / evidence`；derived index 继续保持可重建、可丢弃、不可单独写入。
- 默认正式检索后端已改为 `hybrid-local`；只有在 operator 显式设置 `COPAW_MEMORY_RECALL_BACKEND=qmd` 时才切到 `QMD`。`qmd / lancedb` 仍然只是统一 recall facade 后方的可替换 sidecar slot，不作为新的 canonical source。

### Phase M1：先做 derived recall，不动真相源

- 建 `MemoryRecallService`
- 从 `KnowledgeChunkRecord / StrategyMemoryRecord / AgentReport / Evidence summary` 构建 recall index
- Runtime Center 补 `memory recall` 调试入口
- 完成状态：已完成。统一 state 已新增 `MemoryFactIndexRecord` 与 rebuildable SQLite index；`MemoryRecallService` 已接入 goal compile、query execution 与 Runtime Center `/memory/recall`。

### Phase M2：接 retain

- 从 task terminal / report / routine / writeback 正式提炼 durable facts
- 统一写回 `KnowledgeChunkRecord`
- 明确哪些情形允许刷新 `StrategyMemoryRecord`
- 完成状态：已完成。`AgentReportRecord / RoutineRunRecord / execution chat writeback / KnowledgeChunkRecord / StrategyMemoryRecord` 已接到 retain 主链，仍未引入第二 durable store。

### Phase M3：接 reflect

- 生成 `EntityMemoryView / OpinionMemoryView`
- 引入 confidence 与 evidence-backed contradiction handling
- Runtime Center 显示 entity/opinion/confidence
- 完成状态：已完成。`MemoryReflectionService` 已产出 `entity / opinion / confidence / supporting_refs / contradicting_refs`，Runtime Center API 与 `/knowledge` 前端读面已可见。

### Phase M4：替换检索后端

- 默认先用 SQLite FTS + 当前本地排序
- 再接可选 vector backend
- 最后才考虑 `QMD / LanceDB` sidecar
- 完成状态：已完成当前阶段目标。正式 recall facade 已完成 backend 抽象、默认本地 backend 组合与 `qmd / lancedb` sidecar slot 暴露；sidecar 仍是可替换后端而不是新的真相源或默认写入面。

---

## 10. 验收标准

至少要满足以下 6 条：

1. recall 命中提升，但 canonical source 仍只有 `state / evidence`
2. derived index 可以从正式对象全量重建
3. 上层服务不直接依赖具体向量库
4. reflect 结果能追溯 supporting / contradicting evidence
5. Runtime Center 能看见 entity / opinion / confidence
6. 旧 `MemoryManager` 不再承担 durable truth 写入口

---

## 11. 参考来源

本方案借鉴的外部材料主要来自 `OpenClaw` 公开文档中的研究方向，而不是其默认稳定落点：

- Memory concepts: `https://docs.openclaw.ai/concepts/memory`
- Workspace memory research: `https://docs.openclaw.ai/experiments/research/memory`
- AGENTS / SOUL templates: `https://docs.openclaw.ai/reference/templates/AGENTS`

### M4+ QMD Sidecar

- `2026-03-19` 状态更新：`QMD` 已从 `Memory VNext M4` 的 placeholder slot 升级为真实可运行 sidecar backend。
- 新增 `src/copaw/memory/qmd_backend.py`，把 `derived memory index` 物化为本地 markdown corpus，并由 `DerivedMemoryIndexService` 通过 `replace_entries / upsert_entry / delete_entries` 保持 sidecar corpus 与 canonical fact index 同步。
- `MemoryRecallService` 现在支持 `backend=qmd` 的真实检索分发：会按需执行 `qmd collection add / update / query`，并在需要向量模式时再执行 `embed`；失败时自动回退到本地 `hybrid-local`，`qmd` 返回 0 hits 时也会继续回退，不会把 sidecar 变成新的真相源。
- 默认 QMD embedding 已固定为 `Qwen3-Embedding-0.6B`，实际环境变量为 `QMD_EMBED_MODEL=hf:Qwen/Qwen3-Embedding-0.6B-GGUF/Qwen3-Embedding-0.6B-Q8_0.gguf`。
- 当前产品面已不再把 Windows 轻量 `search` 当默认方案：QMD 默认 `query_mode=query`，前端设置也应只暴露 `hybrid-local / qmd` 两种主模式；operator 选择 `qmd` 时，除了 `COPAW_MEMORY_RECALL_BACKEND=qmd`，还应同步开启 `COPAW_MEMORY_QMD_PREWARM=true`。
- 当前实现已补上四层硬化，并已把在线 recall 主链切到“常驻 sidecar 快路径优先”：
  - `QmdRecallBackend` 会用真实 runtime probe 复核 `collection_path / indexed_documents / pending_embeddings`，不再把 manifest 里的 `bootstrapped=true` 直接等同于 ready。
  - backend 的 best-effort daemon 已不再依赖官方 `qmd mcp --http`，而是改成 CoPaw 自持有的 `src/copaw/memory/qmd_bridge_server.mjs`；bridge 通过 QMD SDK 直接提供 `/health /status /prewarm /query`，同时兼容 Windows 下 `file://` ESM import。
  - 在线 recall 现已优先走 bridge `/query`，并默认带上 `skipRerank=true`；也就是说，实时链路走的是常驻 lex+vec 语义召回快路径，bridge 失败时才回退到 CLI。
  - `warmup()` 的 `/prewarm` 也固定走 `skipRerank=true`，避免预热本身被重 rerank 卡死。
- 系统观测面也已同步修正：`/api/system/self-check` 的 `memory_qmd_sidecar` 现在不会只因为 “QMD 命令可执行” 就返回 `pass`，而是会把 `ready / runtime_problem / indexed_documents / pending_embeddings / daemon_state` 一起纳入状态与 meta，确保 sidecar 实际未就绪时直接暴露为 `warn`，而不是继续隐藏成“已安装可用”。
- 这意味着轻量默认已撤掉，在线 full semantic recall 的产品默认边界已切到常驻 sidecar 快路径；当前剩余未完成项不再是“在线 recall 不通”，而是“重 rerank / 深模式后台化”尚未作为单独产品能力开放，不应把这轮实现误记成“所有深检索问题都已解决”。
- Windows 全局 npm 安装的 `qmd.cmd/.ps1` 包装器当前不可靠，因此 CoPaw 会自动绕过它们，直接用 `node <npm-global>/node_modules/@tobilu/qmd/dist/cli/qmd.js` 启动 sidecar。
- 默认安装路径保持“内置但不新增第二真相源”的原则：`COPAW_MEMORY_QMD_INSTALL_MODE=auto` 时优先复用 PATH 中的 `qmd`，否则可退回 `npx @tobilu/qmd` 按需启动；这只影响 sidecar 检索层，不改变 canonical write path。
- 安装与观测面也已补齐：`scripts/install.{ps1,bat,sh}` 现在会默认尝试安装 `@tobilu/qmd`，`/api/system/overview` 与 `/api/system/self-check` 也会直接暴露 QMD sidecar 的可用状态、`command_mode / query_mode` 与默认 embedding 模型。

---

## 12. 最后一条边界

> `CoPaw` 可以借鉴 OpenClaw 的记忆能力设计，但不能为此退回文件型真相源或第二套 memory 主链。
