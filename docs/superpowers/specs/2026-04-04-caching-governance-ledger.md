# CoPaw Caching Governance Ledger

## Goal

把当前仓库中已经存在的缓存统一登记为正式账本，明确：

- 缓存属于哪一层
- 它缓存的是否只是 formal truth 的派生结果
- 它的 key / TTL / 容量 / 失效条件是什么
- 它是否存在演化成第二真相源的风险

本账本不是性能宣传材料，而是缓存纪律约束面。

---

## Rules

- 缓存只允许保存 `state / evidence / environment / runtime surface` 的派生结果，不得成为正式真相。
- 每个缓存必须显式定义 `key`、`ttl/max_entries`、`invalidation`。
- 高风险缓存必须有专项测试。
- 前端 fetch cache 只能服务降频和共享请求，不得承担 runtime truth。
- file-backed cache 只能用于 artifact / convenience，不得承担主链 runtime state。

---

## Ledger

### 1. MainBrainScopeSnapshotCache

- File: [main_brain_scope_snapshot_service.py](/D:/word/copaw/src/copaw/kernel/main_brain_scope_snapshot_service.py)
- Type: `derived cache`
- Value:
  - `stable_prefix`
  - `scope_snapshot`
- Key:
  - stable prefix: `(session_id, user_id)`
  - scope snapshot: `scope_key`
- Limit:
  - no TTL
  - rebuilt by signature / dirty contract
- Invalidation:
  - signature drift
  - `mark_dirty(work_context_id|industry_instance_id|agent_id)`
  - global dirty now marks all cached scope snapshots dirty
- Source truth:
  - request runtime context
  - industry detail / work-context runtime truth
- Risk: `low`

### 2. PureChatSessionCache

- File: [main_brain_chat_service.py](/D:/word/copaw/src/copaw/kernel/main_brain_chat_service.py)
- Type: `session runtime cache`
- Value:
  - session snapshot copy
  - prompt context body
  - memory handle
- Key: `(session_id, user_id)`
- Limit:
  - TTL + persist interval + dirty flush
- Invalidation:
  - TTL expiry
  - dirty writeback
  - explicit persist
- Source truth:
  - session snapshot backend
- Risk: `medium-low`
- Note:
  - must remain a derived staging cache, not a parallel session truth store

### 3. ResidentAgentCache

- File: [query_execution_resident_runtime.py](/D:/word/copaw/src/copaw/kernel/query_execution_resident_runtime.py)
- Type: `execution reuse cache`
- Value: resident query agent
- Key:
  - `channel:session_id:user_id:owner_agent_id`
  - plus capability/model/prompt signature
- Limit:
  - signature-based reuse
  - no explicit global TTL yet
- Invalidation:
  - signature change
- Source truth:
  - runtime provider / capability / prompt contract
- Risk: `medium`
- Follow-up:
  - later add explicit capacity/eviction policy

### 4. ObservationCache

- File: [runtime_bootstrap_observability.py](/D:/word/copaw/src/copaw/app/runtime_bootstrap_observability.py)
- Type: `formal environment projection cache`
- Value: observation projections derived from evidence
- Key: observation/replay ids
- Limit:
  - owned by environment/evidence boundary
- Invalidation:
  - evidence-derived rebuild
- Source truth:
  - `EvidenceLedger`
- Risk: `low`

### 5. McpRegistryHttpCache

- File: [mcp_registry.py](/D:/word/copaw/src/copaw/capabilities/mcp_registry.py)
- Type: `ttl micro-cache`
- Value: registry HTTP payload
- Key: URL sha1
- Limit:
  - TTL `600s`
  - max entries `256`
- Invalidation:
  - TTL expiry
  - `clear_mcp_registry_cache()`
- Source truth:
  - MCP registry HTTP response
- Risk: `medium-low`

### 6. WorkspaceStatsCache

- File: [system.py](/D:/word/copaw/src/copaw/app/routers/system.py)
- Type: `ttl micro-cache`
- Value: `(file_count, total_size)`
- Key: resolved workspace path
- Limit:
  - TTL `5s`
- Invalidation:
  - TTL expiry
  - `clear_workspace_stats_cache()`
- Source truth:
  - filesystem walk via `_dir_stats`
- Risk: `low`

### 7. ChatWritebackDecisionCache

- File: [query_execution_writeback.py](/D:/word/copaw/src/copaw/kernel/query_execution_writeback.py)
- Type: `decision cache`
- Value: `_ChatWritebackModelDecision`
- Key: normalized operator text
- Limit:
  - bounded LRU
  - max entries `128`
- Invalidation:
  - LRU eviction
  - `clear_chat_writeback_decision_cache()`
- Source truth:
  - writeback decision model / heuristics result
- Risk: `high`
- Required guardrail:
  - must stay bounded
  - must stay test-covered
  - must not silently absorb more context than its key expresses

### 8. Frontend ActiveModelsCache

- Files:
  - [activeModelsCache.ts](/D:/word/copaw/console/src/runtime/activeModelsCache.ts)
  - [runtimeTransport.ts](/D:/word/copaw/console/src/pages/Chat/runtimeTransport.ts)
- Type: `frontend convenience cache`
- Value: active model resolution payload
- Key: singleton
- Limit:
  - TTL `30s`
- Invalidation:
  - explicit `invalidateActiveModelsCache()`
  - provider/local-model/ollama write mutations
  - transport hard failure
- Source truth:
  - `/models/active`
- Risk: `medium`
- Note:
  - UI convenience only; must not shadow runtime provider truth

### 9. Frontend ExecutionPulseSharedFetch

- File: [useRuntimeExecutionPulse.ts](/D:/word/copaw/console/src/hooks/useRuntimeExecutionPulse.ts)
- Type: `frontend shared fetch cache`
- Value:
  - actor detail fetch promise
  - recent fetch payload
- Key: `maxItems:preferredAgentId`
- Limit:
  - TTL `1500ms`
- Invalidation:
  - force reload
  - TTL expiry
  - relevant runtime event trigger
- Source truth:
  - runtime-center actor detail APIs
- Risk: `medium`
- Follow-up:
  - continue moving from coarse prefix invalidation to topic-to-slice invalidation

---

## Immediate Follow-up

1. Keep new small caches on shared helpers instead of ad-hoc `dict + time` implementations.
2. Add capacity/eviction policy for resident execution caches before long-run load increases.
3. Continue turning frontend runtime invalidation into topic-to-slice contracts.
