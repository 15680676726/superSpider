# MEDIA_ANALYSIS_INGEST_PLAN.md

> 日期：`2026-03-19`
>
> 本文档用于规划 `CoPaw` 的“视频 / 音频 / 文档”统一接入、分析、学习与运行闭环。
>
> 它不是实现完成态说明，而是正式施工前的全链路方案。

---

## 0. 文档定位与优先级

本规划同时受以下文档约束：

1. `AGENTS.md`
2. `COPAW_CARRIER_UPGRADE_MASTERPLAN.md`
3. `TASK_STATUS.md`
4. `DATA_MODEL_DRAFT.md`
5. `API_TRANSITION_MAP.md`
6. `implementation_plan.md`
7. `MEMORY_VNEXT_PLAN.md`
8. 本文档 `MEDIA_ANALYSIS_INGEST_PLAN.md`

如果本文件与上层文档冲突，以上层文档为准。

---

## 1. 一句话结论

这次要做的不是“前端多一个上传按钮”，而是把：

`链接 / 本地文件 -> 媒体接入 -> 结构化分析 -> 证据 -> 记忆 -> backlog/goal/assignment/report/strategy`

接成现有 `V7 main brain + Memory VNext` 的正式闭环。

其中：

- `视频` 支持两种分析模式：`节约版`、`深度分析版`
- `音频`、`文档` 先只做一条标准分析链
- `链接` 不是一种最终媒体类型，而是一个待解析入口；同一个链接可能最终被识别为 `网页文章 / 视频 / 音频 / 文档`
- `团队创建入口` 与 `聊天入口` 必须共用同一套媒体接入与分析服务
- 不能新增平行真相源，不能把分析结果只留在 prompt 或临时缓存里

---

## 2. 为什么现在要单独立项

当前仓库已经具备：

- `V7` 的正式主链：`chat writeback -> backlog -> cycle -> assignment -> goal -> task -> report -> strategy`
- `Memory VNext` 的正式主链：`retain -> derived index -> reflect`
- `Industry` 的 draft-first 正式入口：`/api/industry/v1/preview` 与 `/api/industry/v1/bootstrap`

但当前还没有“跨模态媒体理解”的正式入口和正式对象，因此会出现两个现实问题：

1. 用户想在创建团队时提供一个行业视频、音频访谈或文档资料，系统没有正式接线。
2. 用户在行业运行中想在聊天里补充一个重要视频/音频/文档，让系统分析学习并回写主脑，当前也没有正式接线。
3. 用户也可能只丢一个链接过来，而这个链接背后到底是文章、视频、音频还是 PDF/文档，当前系统没有正式判别与分流链。

如果不单独规划，这个能力极容易被做成：

- 只在前端临时上传
- 只在 prompt 里塞一段转写
- 只在聊天里一次性看完就丢
- 不进 evidence、不进 memory、不进 backlog、不进 strategy

那会再次形成“看起来能分析，实际上不能闭环”的假功能。

---

## 3. 当前真实基线与断点

基于当前仓库实况，这个能力还没落地，主要断点如下。

### 3.1 团队创建入口还是纯文本 brief

- `console/src/api/modules/industry.ts` 的 `IndustryPreviewPayload` 目前只有文本字段，没有媒体输入字段。
- `console/src/pages/Industry/pageHelpers.tsx` 的 `toPreviewPayload()` 目前只把表单转换为文本 brief。
- `src/copaw/industry/models.py` 的 `IndustryPreviewRequest` / `IndustryProfile` 也还没有正式 `media_inputs` 语义。

### 3.2 聊天前端显式关闭了 attachments

- `console/src/pages/Chat/OptionsPanel/defaultConfig.ts` 当前 `sender.attachments = false`。
- 这意味着聊天页现在产品层面没有开放上传入口。

### 3.3 聊天协议本身并不是完全不支持媒体

- `AgentRequest.input` 本身可以承载 runtime message content parts。
- `src/copaw/app/channels/base.py` 已支持把 `content_parts` 组装成正式 `AgentRequest`。
- 也就是说，协议层不是完全做不了，而是前端没打开、主链没补齐。

### 3.4 后端能下载媒体块，但“视频理解”没有正式接上

- `src/copaw/agents/utils/message_processing.py` 已会处理 `file / image / audio / video` 块并下载到本地。
- `src/copaw/app/runtime_agentscope.py` 当前正式转换只覆盖了 `image` 与 `audio`。
- `video` 目前没有进入正式多模态理解链，实际上会退化。

### 3.5 聊天写回还是“文本写回”，不是“媒体写回”

- `src/copaw/industry/chat_writeback.py` 现已退为“已批准 writeback 的结构化展开器”；真正的 execution-core `chat -> intent/kickoff/writeback/policy-change/risky-confirmation/team-gap-action` 前门已统一切到 active chat model 的结构化判定，不再保留关键词放行兜底或“规则先分流、模型后补洞”的混合链；`IndustryService.apply_execution_chat_writeback()` 也不再对原始文本做二次关键词重解析。
- `src/copaw/industry/service_lifecycle.py` 的 `apply_execution_chat_writeback()` 已能把文本写回到 `profile / backlog / schedule / strategy / memory`，但还没有“媒体分析结果 -> 正式写回”的对象链。

### 3.6 记忆与证据侧已有承接基础，但缺一个正式媒体分析对象

- `EvidenceRecord` / `ArtifactRecord` 已可承接原始文件、转写、截图、摘要等产物。
- `MemoryRetainService` 已可把 chat writeback、report、routine、evidence 接入 retain/reflect 主链。
- `KnowledgeService.import_document()` 已能把整理后的文档写入 canonical knowledge。

当前缺的是：

- 一个可复用的 `MediaAnalysisRecord`
- 一个统一的 `MediaIngestService / MediaAnalysisService`
- 一个把媒体分析结果回写到 `Industry / Chat / Memory / Backlog / Strategy` 的正式桥

---

## 4. 设计目标与非目标

## 4.1 目标

- 支持两类入口：
  - `团队创建` 页上传或粘贴链接
  - `聊天窗口` 运行中补充媒体材料
- 支持三类输入：
  - `视频`
  - `音频`
  - `文档`
- 视频支持两种分析模式：
  - `节约版`
  - `深度分析版`
- 输出必须可复用，而不是一次性 prompt 消耗品
- 输出必须进入现有：
  - `evidence`
  - `knowledge / memory`
  - `V7 main brain` 写回链
- 前端只增加必要入口，不新开平行“媒体管理后台”

## 4.2 非目标

- 不在本轮把“所有媒体类型都做成最强多模态实验室”
- 不在本轮做完整视频编辑器、知识图谱编辑器、素材库产品线
- 不在本轮复制 OpenClaw 的 Markdown memory truth source
- 不把“媒体分析”做成独立于 `Industry / Chat / Runtime Center` 的第四套产品心智

---

## 5. 外部参考：Codex 与 OpenClaw 值不值得借鉴

## 5.1 Codex：不适合作为视频/音频/文档分析主参考

查到的官方信息说明：

- `openai/codex` 官方仓库把 Codex CLI 定位为“本地 coding agent”，不是通用媒体分析系统。
- 官方 `GPT-5-Codex` 模型页当前明确写的是：
  - 输入：`Text, image`
  - `Audio: Not supported`
  - `Video: Not supported`
- OpenAI 官方 API 文档另有通用 `input_file` 能力，可处理 PDF、文档、表格等文件，但这是 OpenAI API 的通用文件输入能力，不等于 `Codex` 仓库本身有成熟的视频/音频/文档理解产品链。

因此，对本项目的结论是：

- `Codex` 值得借鉴：
  - 把输入当作正式内容项，而不是前端私有字段
  - 让 agent 使用统一运行入口消费输入，而不是各处拼装 prompt
  - 对文件输入使用正式 API contract，而不是页面私藏上传逻辑
- `Codex` 不值得直接借鉴：
  - 视频理解链路
  - 音频理解链路
  - 文档知识沉淀链路

换句话说：

> `Codex` 更像“输入契约与 agent 交互形态”的参考，不是“跨模态媒体分析产品设计”的参考。

## 5.2 OpenClaw：值得借“媒体预消化 + 回退链 + 限额策略”，但不能照搬记忆真相源

查到的官方信息说明：

- OpenClaw 已有 `Media Understanding`：
  - 在回复管线前，对入站 `image / audio / video` 做 pre-digest
  - 同时保留原始附件继续传给模型
  - 支持 provider 与 CLI fallback
  - 有 `attachments` 策略、`maxBytes` 限额、失败回退
- OpenClaw 在功能页明确写了：
  - `Images, audio, and documents in and out`
- OpenClaw 还单独提供了 `PDF tool`：
  - 对 PDF 支持 native provider mode
  - 对其他 provider 走“先抽文本、必要时再抽页图”的 fallback 模式
- 但 OpenClaw 的 memory 官方文档明确说明：
  - `MEMORY.md` 与 `memory/YYYY-MM-DD.md` 是 source of truth
  - `memory_search / memory_get / QMD` 建立在 Markdown truth source 之上

因此，对本项目的结论是：

- `OpenClaw` 值得借鉴：
  - 媒体先预消化，再决定如何进入主回复链
  - 原始媒体与摘要并存，不丢原始附件
  - provider / CLI 多级 fallback
  - 每种媒体单独限额、限时、限并发
  - 视频不要默认全量深读，先做短摘要与附件策略
  - PDF / 文档先抽文本，必要时再加图像页
- `OpenClaw` 不值得照搬：
  - Markdown memory 作为正式真相源
  - `MEMORY.md` / `memory/*.md` 主导长期记忆
  - 把 sidecar 检索或工作区文件提升为 canonical truth

对 CoPaw 来说，正确做法是：

> 借 OpenClaw 的“媒体预消化与回退链”思想，但坚持 CoPaw 的 `state / evidence / strategy / memory` 单一真相源。

---

## 6. CoPaw 的正式方案总览

## 6.1 顶层原则

这次能力必须回答 6 个问题：

1. 属于哪一层？
   - 接入与存储：`evidence / state`
   - 分析编译：`media service + compiler`
   - 写回与学习：`industry / memory / kernel`
2. 接入哪个单一真相源？
   - 原始媒体进 `EvidenceRecord + ArtifactRecord`
   - 结构化分析进 `MediaAnalysisRecord`
   - 长期可复用知识进 `KnowledgeChunkRecord / StrategyMemoryRecord`
3. 是否绕过统一内核？
   - 不能。聊天入口必须仍走 runtime / kernel / industry writeback 主链
4. 是否新增第四套能力语义？
   - 不能。媒体分析只是正式能力挂载或服务，不另造第四套概念
5. 产生什么证据？
   - 原始文件、转写文本、关键帧、OCR、分析摘要、写回证据
6. 未来准备替换什么旧逻辑？
   - 逐步替换“文本关键词式写回”对媒体场景的不足
   - 替换一次性 prompt 塞媒体摘要的做法

## 6.2 用户可见的最小心智

用户只需要理解：

- 在 `生成团队` 时可以补充：
  - 链接
  - 本地视频
  - 本地音频
  - 本地文档
- 在 `聊天` 时也可以随时补充以上内容
- 一旦识别到上传或粘贴的是 `视频`，系统应立即提示：
  - `节约版`
  - `深度分析版`
- 如果用户只给一个链接，系统应先自动判断它是：
  - 网页文章
  - 视频
  - 音频
  - 文档
  - 或暂时无法识别
- `深度分析版` 对用户的含义是“尽可能完整分析整段视频”，而不是让用户理解后台拆帧、ASR、关键帧这些技术步骤
- 系统会把这些材料分析后：
  - 用于当前回答
  - 视情况写入团队记忆 / backlog / strategy
  - 在 Runtime Center 可见

用户不需要理解内部 provider、OCR、ASR、关键帧、QMD 之类细节。

---

## 7. 正式对象模型

## 7.1 API 输入对象：`MediaSourceSpec`

这是 API 层对象，不是长期真相源。

建议字段：

- `source_id`
- `source_kind`: `link | upload | existing-artifact`
- `media_type`: `unknown | article | video | audio | document`
- `declared_media_type`
- `detected_media_type`
- `analysis_mode`: `standard | video-lite | video-deep`
- `title`
- `url`
- `filename`
- `mime_type`
- `size_bytes`
- `entry_point`: `industry-preview | industry-bootstrap | chat | runtime-center`
- `purpose`: `draft-enrichment | chat-answer | learn-and-writeback | reference-only`

说明：

- 对 `upload`，`detected_media_type` 主要来自文件扩展名、mime type 与探测结果。
- 对 `link`，`media_type` 初始可以是 `unknown`，需要经过 link resolver 后再落为正式类型。

## 7.2 正式状态对象：`MediaAnalysisRecord`

这是建议新增的一等对象，进入 `state`。

建议字段：

- `analysis_id`
- `industry_instance_id`
- `thread_id`
- `source_ref`
- `entry_point`
- `media_type`
- `analysis_mode`
- `status`: `queued | running | completed | failed | skipped`
- `asset_artifact_ids`
- `derived_artifact_ids`
- `transcript_artifact_id`
- `structured_summary`
- `timeline_summary`
- `entities`
- `claims`
- `recommended_actions`
- `knowledge_document_ids`
- `evidence_ids`
- `strategy_writeback_status`
- `backlog_writeback_status`
- `created_at`
- `updated_at`

为什么需要这个对象：

- 证据层只适合记录“发生了什么”
- `KnowledgeChunkRecord` 只适合沉淀可复用知识
- 但媒体分析还需要：
  - 状态
  - 模式
  - 产物引用
  - 写回结果
  - 重用缓存

如果没有这个对象，后续一定会回到“分析结果只散落在 evidence/knowledge 文本里”的旧问题。

## 7.3 继续复用的正式对象

- 原始文件与中间产物：`ArtifactRecord`
- 分析动作与写回动作：`EvidenceRecord`
- 长期知识沉淀：`KnowledgeChunkRecord`
- 主脑长期战略：`StrategyMemoryRecord`
- 聊天转运营：`BacklogItemRecord / OperatingCycleRecord / AssignmentRecord / AgentReportRecord`

---

## 8. 两个正式入口

## 8.1 入口 A：团队创建页

### 用户路径

1. 用户填写行业 brief
2. 用户补充：
   - 一个或多个链接
   - 一个或多个本地文件
3. 如果输入的是链接，系统先做链接解析与类型识别
4. 系统再做媒体接入与标准化
5. 系统生成结构化媒体分析
6. draft generator 在生成团队草案时消费“精炼后的媒体上下文”
7. preview 返回：
   - 团队草案
   - 媒体分析摘要
   - 风险 / 成本提示
8. bootstrap 时把用户确认采用的媒体分析结果写入正式实例

### 这里媒体扮演的角色

它不是“聊天附件”，而是：

- `draft enrichment input`
- `team/goal/strategy compiler context`

### bootstrap 后必须落地的内容

- 原始媒体 artifact
- 分析 evidence
- 结构化 `MediaAnalysisRecord`
- 必要的知识沉淀
- 与行业实例绑定的分析引用

## 8.2 入口 B：聊天窗口

### 用户路径

1. 用户在行业运行中发送文字 + 链接 / 上传文件
2. 如果是链接，系统先判断它到底是文章、视频、音频还是文档
3. 系统再注册媒体，并判断是否要立即分析
4. 分析结果进入当前对话上下文
5. 执行中枢再决定这份结果是：
   - 只用于本轮回答
   - 写入团队记忆
   - 形成 backlog
   - 更新 strategy
   - 触发专项任务

### 这里媒体扮演的角色

它不是单纯“客服附件”，而是：

- `runtime context enrichment`
- `writeback candidate`
- `learnable evidence`

### 正式落地要求

聊天里上传媒体后，不能只回答一句总结就结束，至少要做到：

- 当前线程能看到分析状态
- Runtime Center 能看到对应 evidence / analysis
- 必要时能看到它是否已经：
  - 写入 backlog
  - 写入 strategy
  - 写入 knowledge

---

## 9. 三类媒体的分析策略

链接是入口，不是最终媒体类型。

正式分流应为：

- `link -> article`
- `link -> video`
- `link -> audio`
- `link -> document`
- `link -> unknown`

| 类型 | V1 模式 | 主要流程 | 主要产物 |
|---|---|---|---|
| `article` | `standard` | 网页正文抽取、结构摘要、必要时页面元数据/OCR | 摘要、章节要点、结论、行动建议 |
| `video` | `video-lite` / `video-deep` | 优先走原生视频理解；不支持时再走提取式 fallback | 摘要、时间线、关键观点、行动建议 |
| `audio` | `standard` | ASR/转写、说话主题提炼、行动项提炼 | transcript、摘要、要点、行动项 |
| `document` | `standard` | 文本抽取、结构切分、必要时页图/OCR | 结构化摘要、章节要点、关键数据与结论 |

## 9.0 链接解析：`link-resolve`

这一步必须先于具体分析。

系统拿到链接后，先做轻量解析：

1. URL provider 识别
2. `HEAD/GET` 的 content-type
3. 页面 `OpenGraph / oEmbed / schema.org` 元数据
4. 文件后缀与跳转结果
5. 必要时下载少量头部内容做快速探测

解析后给出：

- `resolved_url`
- `detected_media_type`
- `provider_kind`
- `title`
- `thumbnail`
- `duration_seconds`
- `mime_type`
- `size_bytes`

前端规则：

- 如果解析结果是 `video`，立即弹出 `节约版 / 深度分析版`
- 如果解析结果是 `audio / article / document`，直接走标准分析
- 如果解析结果仍是 `unknown`，提示用户确认类型或仅按网页标准模式处理

## 9.1 视频：节约版 `video-lite`

目标：

- 低成本
- 快速判断“这段视频值不值得纳入当前行业闭环”

默认流程：

1. 拉取页面标题、描述、字幕、发布时间等元数据
2. 若有字幕，优先用字幕
3. 若无字幕，再做 ASR
4. 抽稀关键帧，不做高密度逐帧理解
5. 生成：
   - 视频摘要
   - 关键观点
   - 行动建议
   - 是否建议深度分析

适用场景：

- 创建团队时先快速理解行业公开视频
- 聊天里临时补充一个参考视频
- 先判断是否值得进入主脑 backlog

## 9.2 视频：深度分析版 `video-deep`

目标：

- 对用户来说，目标是“让模型尽可能完整理解整段视频”
- 对系统来说，目标是输出更完整的时间线、章节、论点、证据与可执行知识

正式定义：

- `video-deep` 应被定义成一个产品模式，不应被定义成一组强绑定的后台步骤
- 它的首选执行策略应是：
  - 如果当前 provider/model 原生支持整段视频理解，直接让模型分析完整视频
- 它的 fallback 策略应是：
  - 当当前模型不支持原生视频理解时，后台才退回到 `ASR + 时间段切片 + 关键帧/关键页 + 结构化整合` 的提取式深度分析
- 如果当前运行时连可靠的深度 fallback 都没有，则不应伪装成可用深度版，而应：
  - 禁用 `深度分析版`
  - 或只开放 `节约版`

深度版的产物要求保持不变：

- 章节摘要
- 时间线
- 论点 / 证据 / 反证
- 可执行 SOP / 研究问题 / 主脑建议

适用场景：

- 用户明确要求“深度学习这个视频”
- 行业研究视频、课程视频、操作演示视频
- 需要生成后续 backlog / routine / knowledge document

当前实现边界：

- 以当前仓库状态，不应假设已经具备“模型原生整段视频理解”主链
- 因此首轮落地应把 `video-deep` 设计成 capability-gated 模式，而不是默认承诺一定可用

## 9.3 音频：标准版

目标：

- 低摩擦得到 transcript 与结论

默认流程：

1. 转写
2. 说话主题与观点提炼
3. 行动项与术语提炼
4. 写成结构化摘要

## 9.4 文档：标准版

目标：

- 对 PDF / doc/docx / txt / md / ppt / xlsx/csv 等做统一入口

默认流程：

1. 根据文件类型选抽取器
2. 尽量优先抽文本
3. 对 PDF 或需要版面信息的文件，必要时补页图/OCR
4. 对表格类文档生成结构化统计摘要
5. 输出：
   - 结构摘要
   - 关键数据
   - 关键结论
   - 可执行建议

## 9.5 网页文章：标准版

目标：

- 支持用户只给一个普通网页链接的场景

默认流程：

1. 抽取正文
2. 提取标题、作者、发布时间、站点来源
3. 去除导航、广告、评论等噪声
4. 生成结构化摘要
5. 输出：
   - 摘要
   - 关键结论
   - 可执行建议
   - 是否建议沉淀到知识库

---

## 10. 后端正式链路

## 10.1 服务拆分建议

建议新增统一服务，而不是把逻辑继续塞进 `industry/service.py` 或聊天页路由。

建议最小拆分：

- `LinkResolverService`
  - 负责 URL 探测、provider 识别、content-type 判别、跳转归一化
- `MediaIngestService`
  - 负责链接/上传标准化
  - 负责 URL 拉取、文件落盘、hash、去重、类型识别
  - 负责写入原始 asset evidence
- `MediaAnalysisService`
  - 负责任务编排、模式分流、缓存命中、状态推进
- `VideoLiteAnalyzer`
- `VideoDeepAnalyzer`
- `AudioAnalyzer`
- `DocumentAnalyzer`
- `MediaContextCompiler`
  - 把大体量原始媒体分析压缩成 prompt-safe 摘要
- `MediaWritebackBridge`
  - 把分析结果接到 `knowledge / strategy / backlog / assignment`

## 10.2 落位建议

建议按职责落位：

- `src/copaw/state/`
  - `MediaAnalysisRecord`
  - repository / state service
- `src/copaw/evidence/`
  - 原始媒体与派生产物 artifact
- `src/copaw/media/`
  - ingest / analysis / compiler / writeback bridge
- `src/copaw/app/routers/`
  - 低层 `/api/media/*`
- `src/copaw/industry/`
  - 只保留与 `preview/bootstrap` 的接线
- `src/copaw/kernel/`
  - 只保留聊天执行入口的接线

## 10.3 正式数据流

### 统一接入流

1. 接收 `MediaSourceSpec`
2. 如果是 `link`，先经 `LinkResolverService` 解析成最终媒体类型
3. 标准化为本地/远程可访问资源
4. 写 `media-ingest` evidence
5. 生成原始 `ArtifactRecord`
6. 提交分析任务
7. 生成 `MediaAnalysisRecord`
8. 派生：
   - transcript artifact
   - keyframe artifact
   - OCR artifact
   - summary artifact
9. 写 `media-analysis` evidence
10. 根据入口决定后续：
   - 进入 industry draft compiler
   - 进入 chat response context
   - 进入 writeback / memory

### 写回流

媒体分析完成后，不直接偷偷修改运行态，而是走明确桥：

- `reference-only`
  - 只回答，不写回
- `learn-and-writeback`
  - 写 `KnowledgeChunkRecord`
  - 必要时更新 `StrategyMemoryRecord`
  - 必要时创建 `BacklogItemRecord`
  - 再进入 operating cycle

---

## 11. 前端方案

## 11.1 团队创建页 `/industry`

只做最小必要变更。

新增一个“参考材料”区域，放在行业 brief 表单中，不新增独立页面。

### UI 要求

- 支持两种输入方式：
  - `粘贴链接`
  - `本地上传`
- 支持三类文件：
  - `视频`
  - `音频`
  - `文档`
- 视频显示模式选择：
  - `节约版`
  - `深度分析版`
- 对纯链接输入，不要求用户先手动选“这是视频/音频/文档”；系统应先自动识别，再决定后续交互
- 当检测到输入是视频时，应立即弹出模式选择，不应让用户先提交、后台再二次追问
- 如果当前模型/运行时不支持 `深度分析版`，仍然展示两个选项，但 `深度分析版` 应置灰并明确说明“当前模型未接入原生视频理解，暂仅支持节约版”
- 音频、文档默认：
  - `标准分析`

### 预览期展示

preview 结果区新增“材料分析摘要”卡片，显示：

- 文件/链接名称
- 类型
- 分析模式
- 状态
- 摘要
- 风险与成本提示
- 是否被纳入当前草案

## 11.2 聊天页 `/chat`

聊天输入区开放附件入口，但不改变“主脑聊天优先”的整体产品心智。

### UI 要求

- 输入框旁增加：
  - `上传`
  - `链接`
- 视频上传/链接时弹出模式选择：
  - `节约版`
  - `深度分析版`
- 普通链接先自动解析类型；只有当链接被识别为视频时，才弹出这两个视频选项
- 该弹层应在识别出视频后立即出现
- 若当前能力检查不支持深度版，则深度选项禁用并解释原因
- 消息发送后，消息卡片显示媒体分析进度：
  - `上传中`
  - `分析中`
  - `已纳入本轮回答`
  - `已写入团队记忆`
  - `已创建待办`

### 不做的事

- 不在聊天页做复杂媒体资产管理台
- 不把聊天页变成素材库页面

---

## 12. API 规划

## 12.1 新增低层通用媒体接口

建议新增：

- `POST /api/media/ingest`
  - 接受 `link` 或 `multipart upload`
  - 返回标准化媒体引用
- `POST /api/media/resolve-link`
  - 对纯链接做轻量解析与类型识别
  - 返回 `article / video / audio / document / unknown`
- `POST /api/media/analyses`
  - 创建分析任务
- `GET /api/media/analyses/{analysis_id}`
  - 查询分析状态与结果
- `GET /api/media/analyses`
  - 按 `industry_instance_id / thread_id / entry_point` 查询

这样做的原因：

- `Industry` 与 `Chat` 都要复用
- 未来 Runtime Center 也要能直接展示
- 避免 `/industry`、`/chat`、`/knowledge` 各自造上传逻辑

## 12.2 扩展行业接口

### `POST /api/industry/v1/preview`

新增字段：

- `media_inputs: MediaSourceSpec[]`

新增返回：

- `media_analyses: MediaAnalysisSummary[]`
- `media_warnings: string[]`

### `POST /api/industry/v1/bootstrap`

新增字段：

- `media_analysis_ids: string[]`
- 或 `accepted_media_inputs: ...`

目标是让 bootstrap 激活时能显式绑定“哪些媒体分析被采纳为正式上下文”。

## 12.3 扩展聊天入口

聊天不建议另造一个“聊天上传 API”，而应让 runtime chat 直接支持带媒体 content。

建议：

- 前端发送的 `AgentRequest.input[].content[]` 正式支持：
  - `text`
  - `file`
  - `image`
  - `audio`
  - `video`
- 同时允许 message metadata 带：
  - `analysis_mode`
  - `purpose`
  - `writeback_preference`

## 12.4 Runtime Center 读面

建议新增或扩展：

- `GET /api/runtime-center/industry/{id}`
  - 返回最近媒体分析摘要
- `GET /api/runtime-center/conversations/{thread_id}`
  - 能看到媒体消息及分析结果引用
- `GET /api/runtime-center/media/analyses/{id}`
  - detail drawer 读面

---

## 13. Token / 成本控制策略

这次功能如果不设计缓存和分层，成本会非常高。

正式策略如下。

## 13.1 先抽取，再推理

不要把完整原始视频反复喂给大模型。

正确顺序：

1. 元数据
2. 字幕 / ASR
3. OCR / 页面文本
4. 关键帧 / 关键页
5. 结构化摘要
6. 最后才让高阶模型做整合推理

## 13.2 一次分析，多处复用

同一视频/文档/音频的分析结果必须：

- 可缓存
- 可按 hash / URL / etag 去重
- 可在 preview、bootstrap、chat、runtime-center 间复用

## 13.3 视频两档

这是用户要求，也是成本控制关键。

### `节约版`

- 默认
- 只做足够回答与初步学习的分析
- 适合大多数场景

### `深度分析版`

- 明确高成本模式
- 更适合研究、课程、复杂操作视频
- 建议在 UI 上明确标识“更慢 / 更贵 / 更完整”
- 产品语义上应优先理解为“模型完整分析整段视频”
- 后台提取式多步处理只是 fallback，不应成为用户心智
- 如果当前模型或运行时不支持原生视频理解，则应通过 capability check 禁用该模式，而不是默认伪实现

## 13.4 文档不要盲目转图片

文档优先文本抽取。

只有以下情况再补视觉页图：

- PDF 版面信息很重要
- 图表很多
- OCR 文档

## 13.5 聊天默认不自动深挖

聊天入口默认：

- 文档/音频：标准分析
- 视频：默认 `节约版`

只有用户明确选择，或主脑明确需要更深材料时，再转深度分析。

---

## 14. 与 V7 主脑链路的接法

## 14.1 建队阶段

`media analysis -> draft context -> team/goals/schedules draft -> bootstrap -> strategy/memory bind`

作用：

- 让团队一开始就带着真实材料启动
- 不只靠 operator 手填 brief

## 14.2 聊天阶段

`chat media -> media analysis -> current answer + writeback candidate -> backlog/cycle/assignment/strategy`

作用：

- 用户运行中发现重要材料，可以直接喂给系统
- 系统不是“看一眼就忘”，而是进入正式学习与运营闭环

## 14.3 Memory VNext

媒体分析不是直接成为长期真相。

正确顺序：

- 原始文件与中间产物 -> evidence/artifact
- 结构化分析 -> `MediaAnalysisRecord`
- 被确认有长期价值的部分 -> `KnowledgeChunkRecord`
- 涉及长期方向的部分 -> `StrategyMemoryRecord`
- 再经 `retain -> reflect`

---

## 15. 为什么现在还不能完整跑通

如果今天直接在前端加上传按钮，项目仍然跑不通，原因不是一个，是一组断层：

1. `/industry` 预览与创建接口没有媒体字段
2. `/chat` 前端关闭了 attachments
3. 聊天虽然能携带 content parts，但产品层没开放
4. 纯链接还没有正式 `article / video / audio / document` 判别链
5. 后端下载了 `video`，但没有正式视频理解链
6. 没有 `MediaAnalysisRecord`，无法跨入口复用结果
7. 没有通用 `/api/media/*`，容易重复造轮子
8. 聊天写回目前仍是文本 heuristic，不足以承接媒体结果
9. Runtime Center 还没有媒体分析 detail read surface
10. 没有异步任务与进度面，深度视频分析用户体验会断

所以这件事必须按阶段做，不适合“前端先加一个按钮试试”。

---

## 16. 交付分期

## Phase 1：基础接入与团队创建闭环

目标：

- `/industry` 支持链接 + 本地上传
- 支持 `video/audio/document`
- 纯链接能先自动识别为 `article / video / audio / document`
- 视频在 UI 上支持 `节约版/深度版` 选择
- 但首轮稳定交付以 `video-lite` 为主；`video-deep` 只有在当前模型/运行时能力检查通过时才开放
- preview/bootstrap 能消费媒体分析结果

交付：

- `MediaSourceSpec`
- `MediaAnalysisRecord`
- `/api/media/ingest`
- `/api/media/analyses`
- `/industry` 入口接线

## Phase 2：聊天入口闭环

目标：

- `/chat` 开放附件与链接
- 分析结果能进入当前回答
- 能显式写入 memory/backlog/strategy
- 纯链接在聊天里也能先自动识别类型，再走对应分析链
- 视频上传后即时弹出 `节约版/深度版` 选择，并按当前能力动态决定是否开放深度版

交付：

- 聊天前端上传入口
- runtime chat 带媒体 content
- `MediaWritebackBridge`
- 媒体 detail drawer

## Phase 3：深度分析、缓存与可观测性

目标：

- 视频深度分析异步化
- 去重缓存
- Runtime Center 显示历史分析

交付：

- analysis job progress
- hash/url reuse
- runtime-center media read surface

## Phase 4：模型判断写回替代简单关键词规则

目标：

- 媒体写回不再依赖关键词
- 由模型对“是否写回、写去哪、写成什么”做正式判定

说明：

- 这一步与当前你们对聊天“从关键词匹配改成模型判断”的方向一致
- 但可以后置，不阻塞媒体接入第一阶段

---

## 17. 测试与验收

## 17.1 单元测试

- 媒体类型识别
- 分析模式选择
- URL / 文件标准化
- hash 去重
- video-lite / video-deep 分流
- 写回路由判定

## 17.2 集成测试

- `industry preview` 带媒体
- `industry bootstrap` 绑定媒体分析结果
- `chat media -> analysis -> knowledge/backlog/strategy`
- `retain -> reflect` 在媒体场景可用

## 17.3 端到端测试

- 本地上传视频
- 远程视频链接
- 本地上传音频
- 本地上传 PDF / docx / csv
- 视频深度分析异步完成
- 分析失败时 graceful degrade

## 17.4 验收标准

至少要满足：

- 建队入口可上传/贴链接
- 聊天入口可上传/贴链接
- 三类媒体都能得到结构化分析结果
- 视频确实分 `节约版 / 深度分析版`
- 分析结果能进入 evidence
- 至少一部分结果能进入 memory / strategy / backlog 闭环
- Runtime Center 能看到它，而不是只存在日志里

## 17.5 风险与边界清单

以下项目不应留到实现后期才补。

- `链接误判纠正`
  - 自动识别后应允许用户手动改成 `article / video / audio / document`
- `私有链接 / 登录态链接`
  - 要明确打不开时是提示绑定浏览器会话，还是要求用户直接上传文件
- `深度版能力矩阵`
  - 需要正式 capability check，不能靠前端硬编码猜测当前模型是否支持原生视频理解
- `异步、取消与重试`
  - 深度视频分析必须支持 `queued / running / cancel / retry`
- `建队阶段不卡死`
  - preview 不应被长视频深度分析长期阻塞；必要时应先给草案，再异步补媒体增强结果
- `证据可追溯`
  - 视频结论要尽量带时间戳，文档结论带页码/段落，音频结论带 transcript 片段
- `写回治理边界`
  - 自动分析不等于自动改战略；`strategy / backlog / 长期方向` 写回必须保留明确治理档位
- `存储、去重与清理`
  - 要提前定义原始视频、转写、抽帧、OCR 结果的保留期、去重键和删除条件
- `多语言处理`
  - 需要定义语言检测、是否翻译、保存原文还是译文
- `失败降级链`
  - 例如 `video-deep -> video-lite`、`字幕失败 -> ASR`、`正文抽取失败 -> 浏览器抓取`
- `安全边界`
  - 不执行宏、不信任可执行文件、不把外部 HTML/脚本当可运行内容
- `分析版本化`
  - `MediaAnalysisRecord` 最好记录 `provider / model / pipeline_version`，便于未来重跑与比对
- `批量材料包`
  - 用户一次可能给多个链接和文件，需要定义是逐个分析，还是聚合成一个材料包上下文
- `系统自发现材料复用`
  - 后续 agent 自己在浏览器里发现的文章/视频/文档，也应尽量复用同一套 media ingest，而不是再造第二条链

---

## 18. 施工建议与边界

建议实际施工顺序：

1. 先做 `MediaAnalysisRecord + /api/media/*`
2. 再接 `/industry`
3. 再接 `/chat`
4. 再做 Runtime Center 可见化
5. 最后再把媒体写回判断升级为模型判定

不建议的顺序：

- 先只改前端上传
- 先只做聊天附件
- 先把视频深度分析做很重
- 先把结果塞进 Markdown 或浏览器缓存

---

## 19. 最终架构判断

这次能力的正确交付物不是：

- 一个上传组件
- 一个视频总结 prompt
- 一段临时转写文本

真正的交付物应该是：

- 一个统一媒体接入层
- 一个正式媒体分析对象
- 一个可复用、可证据化、可学习、可写回的跨模态闭环

只有这样，这个能力才符合 CoPaw 当前从 `多渠道 AI 助手平台` 升级为 `长期自主执行载体` 的方向。

---

## 20. 外部参考链接

### Codex / OpenAI

- `openai/codex`：<https://github.com/openai/codex>
- `GPT-5-Codex` 模型能力：<https://developers.openai.com/api/docs/models/gpt-5-codex>
- OpenAI 文件输入：<https://developers.openai.com/api/docs/guides/file-inputs>

### OpenClaw

- OpenClaw GitHub：<https://github.com/openclaw/openclaw>
- Media Understanding：<https://docs.openclaw.ai/nodes/media-understanding>
- Features：<https://docs.openclaw.ai/concepts/features>
- PDF Tool：<https://docs.openclaw.ai/tools/pdf>
- Memory：<https://docs.openclaw.ai/concepts/memory>
