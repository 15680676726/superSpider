# CoPaw Searching 统一检索底座升级设计

日期：`2026-04-20`

---

## 0. 目标

这次不是继续给 `search / web_page / github / artifact` adapter 追加规则，也不是只把某一个 source 做强。

这次要做的是把 CoPaw 的 Searching 从：

- `统一 research frontdoor`
- `统一 evidence/writeback`
- `统一 Runtime Center 读面`

升级为：

- `统一 retrieval substrate`
- `统一三源 planner`
- `统一 hit / ranking / trace 合同`
- `统一写回 formal research / evidence / report / writeback 主链`

一句话目标：

> 在不破坏 `truth-first / no-vector formal memory` 与现有 `ResearchBrief -> SourceCollectionFrontdoorService -> ResearchSession / Evidence / report / writeback truth -> Runtime Center` 主链的前提下，为本地仓库、GitHub、Web 三源补一层可重建的统一检索底座，让 CoPaw 从“会研究”升级成“会找、会排、会解释、会正式闭环”。

---

## 1. 当前真实情况

当前 CoPaw 在 Searching 相关能力上，已经有这些强项：

- 正式 `ResearchBrief` 前门
- `SourceCollectionFrontdoorService -> SourceCollectionService` 统一 collection 链
- 正式 `ResearchSessionRecord / ResearchSessionRoundRecord`
- 正式 `EvidenceRecord`
- `report / knowledge ingest / graph writeback / writeback truth`
- Runtime Center research surface

但当前真正的 Searching 底座还偏弱：

1. 没有本地仓库级 `semantic index / symbol graph / exact + semantic hybrid retrieval`
2. GitHub source 现在更多是 repo/object 页面读取，不是代码库级 intelligence retrieval
3. Web source 现在更多是普通搜索命中，不是 freshness / credibility / answerability 驱动的 retrieval
4. 没有统一 search planner；当前已有的是 `route_collection_mode()`，它负责 `light / heavy / execution_agent_id`，不是 retrieval strategy planner
5. 没有统一 `RetrievalHit / RetrievalRun / ranking rationale / dropped-hit reason` 合同
6. 现有系统强在“搜索结果正式回写”，弱在“结果本身搜得准、搜得深、搜得稳”

所以这次要补的不是“再多几个 provider”，而是：

- 本地 repo、GitHub、Web 三源共用的 retrieval substrate
- source-aware planner
- unified hit/ranking contract
- 与现有 formal research / evidence / report / writeback 主链的稳定接线

---

## 2. 设计结论

### 2.1 选定路线

本次采用路线 2：

- 新增统一 `retrieval substrate`
- 不把 retrieval index/cache 当正式真相源
- 保留现有 `SourceCollectionFrontdoorService -> SourceCollectionService -> research / evidence / report / writeback -> Runtime Center` 主链

不采用：

- 只继续增强现有 adapter 的路线
- 把向量 / graph 检索直接做成新的 formal memory 主链

### 2.2 架构铁律

本次升级必须同时满足：

1. retrieval cache/index 可重建、可清空、可增量更新，但**不是 formal truth**
2. `SourceCollectionFrontdoorService` 仍是正式 research frontdoor；`SourceCollectionService` 仍是统一 collection 层，不允许上层绕开 formal brief/evidence 主链各自私搜
3. local repo / GitHub / Web 必须共用统一 `RetrievalHit` 合同，不允许三套 source 各自返回不兼容结构
4. 当前 `route_collection_mode()` 负责 `light / heavy / execution_agent_id` 决策；新增 `RetrievalPlanner` 负责检索策略决策，两者不能混成一层

### 2.3 一期目标

一期目标不是“做成无限通用搜索平台”，而是：

- 本地 repo 主链定位明显变强
- GitHub repo/object/code retrieval 明显变强
- Web latest/credibility/answerability 明显变强
- 三源结果继续进入正式 `ResearchSession / Evidence / report / knowledge writeback / Runtime Center`

---

## 3. 总体结构

本次升级后的正式结构分为 4 层。

### 3.1 Retrieval Substrate

新增一层，负责：

- query normalization
- planner
- exact search
- symbol search
- semantic chunk retrieval
- rerank
- trace
- multi-source hit normalization

这一层是可重建的检索缓存/索引层，不是 formal truth。

### 3.2 Source Collection Frontdoor

保留现有 `SourceCollectionFrontdoorService -> SourceCollectionService` 正式前门。

升级后它负责：

- 接收 `ResearchBrief`
- 先执行 `route_collection_mode()`，决定 `light / heavy / execution_agent_id`
- 调用 retrieval substrate
- 把 selected hits 映射成：
  - `CollectedSource`
  - `ResearchFinding`
  - `ResearchAdapterResult`

### 3.3 Research Truth / Evidence / Writeback

继续沿用现有正式主链：

- `ResearchSessionRecord`
- `ResearchSessionRoundRecord`
- `EvidenceRecord`
- `AgentReportRecord`
- knowledge ingest
- knowledge graph writeback
- `writeback_truth`

禁止 retrieval substrate 直接写入 formal state 作为第二真相源。

### 3.4 Runtime Read Surfaces

继续由 Runtime Center / Chat / research surfaces 负责读面。

升级后至少要能显示：

- query intent
- planner 选了哪些 source / mode
- selected hits
- ranking rationale
- coverage / gaps / conflicts
- second-pass trace

---

## 4. 正式对象边界

### 4.1 RetrievalQuery

代表一次规范化的检索问题。

建议字段：

- `question`
- `goal`
- `intent`
- `requested_sources`
- `constraints`
- `workspace_root`
- `github_targets`
- `web_targets`
- `latest_required`

### 4.2 RetrievalPlan

代表 planner 的策略决策。

建议字段：

- `intent`
- `source_sequence`
- `mode_sequence`
- `allow_second_pass`
- `max_hits_per_stage`
- `budget`
- `fallback_policy`

### 4.3 RetrievalHit

三源统一命中对象。

建议字段：

- `source_kind`
- `provider_kind`
- `hit_kind`
- `ref`
- `normalized_ref`
- `title`
- `snippet`
- `span`
- `score`
- `relevance_score`
- `answerability_score`
- `freshness_score`
- `credibility_score`
- `structural_score`
- `why_matched`
- `metadata`

### 4.4 RetrievalRun

代表一次完整检索过程。

建议字段：

- `query`
- `plan`
- `stages`
- `selected_hits`
- `dropped_hits`
- `coverage_summary`
- `gaps`
- `conflicts`
- `trace`

### 4.5 RepositoryIndexSnapshot

代表本地仓库索引状态，属于 retrieval substrate 的派生缓存对象。

建议字段：

- `workspace_root`
- `commit_ref`
- `indexed_at`
- `file_count`
- `chunk_count`
- `symbol_count`
- `index_version`

### 4.6 CodeSymbolRecord

代表本地代码库中的 symbol 索引对象。

建议字段：

- `symbol_name`
- `symbol_kind`
- `file_path`
- `line`
- `container_name`
- `language`
- `signature`
- `reference_count`

### 4.7 非 formal truth 的边界

下列对象属于 retrieval substrate 的派生缓存，不是 formal truth：

- `RepositoryIndexSnapshot`
- `CodeSymbolRecord`
- chunk semantic index
- rerank cache
- query rewrite cache
- GitHub object retrieval cache
- Web snippet/credibility cache

下列对象仍然是正式真相：

- `ResearchBrief`
- `ResearchSessionRecord`
- `ResearchSessionRoundRecord`
- `EvidenceRecord`
- report / writeback truth

---

## 5. 三源统一检索流程

统一流程固定为：

1. `ResearchBrief -> SourceCollectionFrontdoorService`
2. `route_collection_mode()` 决定 `light / heavy / execution_agent_id`
3. planner 产出 `RetrievalPlan`
4. 执行第一轮 retrieval
5. 所有结果统一归一成 `RetrievalHit`
6. rerank
7. 必要时 query rewrite / second pass
8. selected hits 映射为 `CollectedSource / ResearchFinding / ResearchAdapterResult`
9. 正式写入 `ResearchSession / ResearchSessionRound / Evidence / report / writeback truth`

### 5.1 Frontdoor / Planner 分工

当前真实代码里已经存在两层不同职责，设计上必须保留：

- `route_collection_mode()`：
  - 负责 `light / heavy`
  - 负责 `execution_agent_id`
  - 负责当前由谁执行这次 collection
- `RetrievalPlanner`：
  - 负责 local repo / GitHub / Web / artifact 之间如何检索
  - 负责 `exact / symbol / semantic / hybrid`
  - 负责 second-pass / rerank / dropped hits

也就是说：

- `route_collection_mode()` 不是新的 search planner
- 新的 `RetrievalPlanner` 也不能取代现有 frontdoor 的 owner / mode 决策

### 5.2 Query Intent

一期固定 6 类 intent：

- `direct-ref`
- `repo-trace`
- `repo-explain`
- `external-latest`
- `cross-source-compare`
- `artifact-followup`

额外约束：

- `artifact-followup` 和 direct path read 不是这次 Searching 升级的 headline，但它们是当前系统已存在的正式 follow-up lane，一期不能回退
- 当前 `BaiduPageResearchService` 仍是 heavy path owner 之一；一期不强行把 heavy research 完全改写成 retrieval substrate owner，只要求 frontdoor 和 light path 先统一接到底座

### 5.3 Planner 默认策略

#### `direct-ref`

- 直接走目标 source
- 不先 semantic

#### `repo-trace`

- `symbol -> exact -> semantic`

#### `repo-explain`

- `semantic -> exact -> symbol backfill`

#### `external-latest`

- `github / web -> exact title/url -> semantic snippet rerank`

#### `cross-source-compare`

- 先按 source 分跑
- 再统一 rerank

#### `artifact-followup`

- 先 artifact truth
- 再回补 local/github/web

### 5.4 本地 repo 优先级

本地仓库问题默认：

- `symbol first`
- `exact second`
- `semantic third`

原因：

- 代码问题很多时候先要找到真实定义、引用和调用链
- 不是先做语义相似度

### 5.5 Rerank 维度

一期统一 5 个排序维度：

- `relevance_score`
- `answerability_score`
- `freshness_score`
- `credibility_score`
- `structural_score`

不同 source 的权重可以不同：

- local repo 更重 `structural_score`
- GitHub / Web 更重 `freshness + credibility`

---

## 6. 三源各自的一期补强能力

### 6.1 Local Repo

本地 repo 一期至少补：

1. 文件/path 索引
2. symbol 索引
3. import/reference/basic call graph
4. chunk semantic index
5. local repo answerability rerank

本地 repo 一期要显著提升的问题包括：

- 某接口从哪进来
- 某字段是谁写谁读
- 某能力如何挂到 main brain / agent / runtime
- 哪些测试覆盖这条链

### 6.2 GitHub

GitHub 一期至少补：

1. repo object retrieval
   - README
   - docs
   - releases
   - issues
   - PR
   - discussions
   - commits
2. GitHub structure awareness
3. known repo code/file retrieval seam
4. credibility / freshness scoring

GitHub 一期要显著提升的问题包括：

- 某外部 repo 某能力如何实现
- 某 issue / PR 是否解决某问题
- 哪个 release/doc 更应作为当前依据

### 6.3 Web

Web 一期至少补：

1. discover provider seam
2. read provider seam
3. domain/credibility heuristics
4. freshness model
5. answer extraction
6. multi-hit conflict detection

Web 一期要显著提升的问题包括：

- 最新官方规则/文档
- 官方 vs 二手解读冲突
- 某网页是否真正回答问题

### 6.4 三源统一要求

三源最终都必须输出：

- `RetrievalHit`
- `why_matched`
- `coverage`
- `ranking rationale`
- 可映射到 `CollectedSource / ResearchFinding`

---

## 7. 与现有正式主链接线

正式接线固定为：

`ResearchBrief -> SourceCollectionFrontdoorService -> route_collection_mode -> RetrievalPlanner -> RetrievalRun -> selected RetrievalHit -> SourceCollectionService -> ResearchSession / ResearchSessionRound / Evidence / report / writeback truth -> Runtime Center`

### 7.1 与 source_collection 的边界

现有正式前门保持两层：

- `SourceCollectionFrontdoorService`
  - 负责编译 brief、light/heavy 路由、frontdoor result、report/writeback 收口
- `SourceCollectionService`
  - 负责统一 source collection 与 selected hit -> formal collection result 映射

其中 `SourceCollectionService` 继续保留，但角色收窄为：

- 正式 collection 层
- selected hit -> formal collection result mapper

它不再承担全部底层搜索逻辑。

### 7.2 Adapter 重构方向

现有 adapter 后续拆成两类。

#### Retrieval Provider

- `local_repo_exact`
- `local_repo_symbol`
- `local_repo_semantic`
- `github_object`
- `github_code`
- `web_discover`
- `web_read`
- `artifact_read`

#### Source Collection Mapper

- 把 retrieval hits 映射为正式 `ResearchAdapterResult`

### 7.3 Evidence / Round 真相增强

light/heavy path 在写 research truth 时要补 richer payload：

- `retrieval_plan`
- `retrieval_trace`
- `selected_hits`
- `dropped_hits`
- `ranking_rationale`
- `coverage_summary`

但 phase-1 必须贴合现有 `ResearchSessionRecord / ResearchSessionRoundRecord`：

- `brief / sources / findings / conflicts / gaps / writeback_truth` 继续优先写现有 top-level formal fields
- planner/rerank/trace 这类新 payload，phase-1 可以先写进 `ResearchSessionRoundRecord.metadata`
- 不允许为了存 retrieval trace，反过来把已 formalized 的 `sources/findings/conflicts/gaps/writeback_truth` 重新退回只写 metadata

### 7.4 Writeback Truth 链

当前真实代码里，light path 完成后不只写 evidence，还会继续写：

- `AgentReportRecord`
- `knowledge_service.ingest_research_session(...)`
- `knowledge_writeback_service.build/apply_research_session_writeback(...)`
- `writeback_truth`

所以这次设计里的“正式闭环”必须指：

- session / round truth
- evidence
- report
- knowledge ingest
- graph/writeback truth

而不是只指 `EvidenceRecord`

### 7.5 Runtime Center Read Surface

Runtime Center 一期至少补以下 section：

- `Retrieval Summary`
- `Selected Hits`
- `Coverage / Gap`
- `Retrieval Trace`

让 operator 可以看到：

- 这次为什么查这些 source
- 为什么这些结果排前面
- 哪些结果被淘汰
- 还缺什么

---

## 8. 目录落位

建议新增正式目录：

```text
src/copaw/retrieval/
  contracts.py
  planner.py
  ranking.py
  run.py
  facade.py
  local_repo/
    index_models.py
    index_store.py
    chunker.py
    exact_search.py
    symbol_search.py
    semantic_search.py
    graph.py
  github/
    object_search.py
    code_search.py
    normalization.py
  web/
    discover.py
    read.py
    credibility.py
    freshness.py
```

现有：

- `src/copaw/research/source_collection/`
- `src/copaw/app/runtime_bootstrap_domains.py`
- `src/copaw/app/runtime_bootstrap_models.py`
- `src/copaw/app/routers/runtime_center_routes_research.py`
- `src/copaw/app/routers/runtime_center_payloads.py`

只负责正式 frontdoor、写链和读面消费，不继续膨胀为底层检索实现宿主。

---

## 9. 一期施工边界

### 9.1 一期要做

#### Local Repo

- file/path index
- symbol index
- exact search
- basic symbol/reference navigation
- semantic chunk retrieval
- local rerank

#### GitHub

- repo object retrieval
- issue/PR/readme/release/discussion normalization
- known repo code/file seam
- credibility/freshness normalization

#### Web

- discover/read provider abstraction
- credibility/freshness
- answer extraction
- conflict summary

#### Unified Layer

- planner
- rerank
- unified hit contract
- `SourceCollectionFrontdoorService / SourceCollectionService` integration
- `collect_sources` tool / frontdoor entry integration
- Runtime Center retrieval read surface

#### Existing Truth Compatibility

- phase-1 保持 `ResearchSessionRecord.brief`
- 保持 `ResearchSessionRoundRecord.sources/findings/conflicts/gaps/writeback_truth`
- 保持 `runtime_center_payloads.py` 现有 top-level field 优先、metadata fallback 次之的读链
- 允许 retrieval trace 先通过 metadata 暴露，不允许破坏现有 Runtime Center fallback surface

### 9.2 一期明确不做

- 不做无限 source 扩张
- 不做 graph DB 正式化
- 不做 retrieval cache 成为 formal memory
- 不做全语言完美 symbol analysis
- 不做 GitHub 官方 code search 的完全复制
- 不做分布式多租户大规模索引平台
- 不做 operator 可配置上百种 retrieval strategy
- 不在一期直接替换 `BaiduPageResearchService` 现有 heavy owner 身份

---

## 10. 统一验收与“90 分”口径

本次一期的“90 分”定义为三项同时成立：

1. 命中率高
2. 首轮答案可直接用
3. 结果正式回写且 Runtime Center 可见

### 10.1 基准题库

一期固定三组 benchmark。

#### A. Local Repo

- router -> service -> state -> test 主链问题
- 字段谁写谁读
- 能力如何挂到 runtime/agent/main brain

#### B. GitHub

- 外部 repo 某能力实现问题
- issue/PR/release/object 结论问题

#### C. Web

- 最新官方文档/规则
- 官方 vs 二手解读冲突
- 页面是否真正回答问题

### 10.2 量化门槛

建议一期写成：

- 三源综合命中率 `>= 90%`
- 任一单源命中率不得低于 `85%`
- 综合首轮可用率 `>= 85%`
- 正式闭环率 `= 100%`

这里的“正式闭环率”明确指：

- `ResearchSessionRecord / ResearchSessionRoundRecord` 已写
- `EvidenceRecord` 已写
- report / writeback truth 已写
- Runtime Center `/runtime-center/research` 能读到一致 surface

### 10.3 L1-L4 验收口径

#### `L1`

- planner/ranking/index/unit tests

#### `L2`

- retrieval contract
- `SourceCollectionService` integration
- `SourceCollectionFrontdoorService` integration
- `collect_sources` tool entry integration
- evidence / report / writeback truth integration
- `runtime_center_payloads.py` / runtime read surface integration tests

#### `L3`

- 6 条真实 smoke：
  - local repo 主链问题 2 条
  - GitHub 问题 2 条
  - Web 问题 2 条
- 至少再补 1 条 frontdoor HTTP / runtime-center read-surface smoke，验证 planner/hits/writeback 真进入 operator 可见链

#### `L4`

- 至少 1 组多轮/刷新/重建/混跑 soak

### 10.4 完成声明格式

后续完成声明必须显式写：

- `L1`
- `L2`
- `L3`
- `L4`
- 未跑项和原因

不得再把“局部回归通过”写成“Searching 升级已完成”。

---

## 11. 一句话收口

本设计的本质，不是继续给现有 search adapter 叠功能，而是：

> 在不破坏 CoPaw 现有 truth-first / evidence / Runtime Center 正式主链的前提下，新增一层统一的 retrieval substrate，把本地 repo、GitHub、Web 三源收进同一个 planner、hit、ranking、trace 合同中，并通过现有 `SourceCollectionFrontdoorService -> SourceCollectionService -> research/evidence/report/writeback` 主链收口，使 CoPaw 的 Searching 从“会研究”升级成“会找、会排、会解释、会正式闭环”。
