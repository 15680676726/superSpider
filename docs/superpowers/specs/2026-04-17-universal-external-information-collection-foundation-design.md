# Universal External Information Collection Foundation Design

Date: `2026-04-17`
Status: `draft`
Owner: `Codex`

## 1. Problem

CoPaw already has partial external-information capabilities, but they are still fragmented:

- explicit research can already be triggered from main-brain chat
- monitoring briefs can already wake formal research sessions
- Baidu page research already has formal session persistence
- browser / environment / evidence chains already exist

However, the current live chain is still not one universal foundation:

- the formal research chain is still mainly represented as a Baidu-specific vertical flow
- the default heavy execution path still leans toward the `researcher` seat
- ordinary profession agents do not yet share one formal external-information collection contract
- GitHub / generic web page / artifact collection are not yet first-class adapters on one formal chain

The system therefore feels weaker than donor systems that already unify search, fetch, browser deepening, tasking, and evidence into one front-door.

The real gap is not "CoPaw has zero research ability". The real gap is:

- collection ability exists, but it is not yet unified
- some flows are profession- or provider-shaped
- the product still lacks one profession-agnostic external-information collection foundation

## 2. Goal

Build one formal, profession-agnostic external-information collection foundation that:

- can be invoked by any profession agent
- can be planned and governed by the main brain
- can route simple information collection directly to the requesting agent
- can route heavy multi-round research to the `researcher` seat by default
- can unify collection-action selection, source collection, finding synthesis, evidence writing, and writeback

The foundation must use stable collection action models:

- `discover`
- `read`
- `interact`
- `capture`

Phase 1 should additionally land four first-class adapters:

- `search`
- `web_page`
- `github`
- `artifact`

This design is not a Baidu-only research upgrade. It is the formal generalization of external information collection.

## 3. Non-Goals

This round does not:

- make `researcher` the exclusive owner of information collection
- let every profession agent autonomously roam the internet without a task reason
- replace the main-brain planning chain
- create a second state system for research
- create a second evidence system
- create a giant cross-session external knowledge warehouse in phase 1
- require every future source/provider to be implemented immediately

Phase 1 only needs one universal foundation with real first adapters and formal integration.

## 4. Hard Boundaries

### 4.1 Invocation Boundary

All profession agents may invoke external-information collection.

But invocation and execution are not the same thing:

- any agent may request collection when its current task has an information gap
- the system decides whether the request is light collection or heavy research
- heavy research defaults to the `researcher` seat

This means:

- `researcher` is not the only entry
- `researcher` is the default heavy research execution seat

### 4.2 Planning Boundary

The main brain remains responsible for planning and adoption.

The main brain or requesting profession agent must define the collection need:

- what to find
- why it is needed
- what "good enough" means
- where the result should write back

The collection foundation does not become a second strategist.

### 4.3 Truth Boundary

This design must not introduce a parallel truth source.

It must reuse the existing formal chain:

- `ResearchSessionRecord`
- `ResearchSessionRoundRecord`
- `EvidenceRecord`
- `EnvironmentMount`
- `SessionMount`
- existing work/assignment/report writeback paths

If a new structure cannot map back to these objects, it should not be introduced.

### 4.4 Reuse-First Boundary

This design must not rebuild the current provider-specific chains from scratch.

Mandatory reuse targets include:

- `src/copaw/research/baidu_page_research_service.py`
- `src/copaw/state/models_research.py`
- `src/copaw/state/repositories/sqlite_research.py`
- `src/copaw/kernel/main_brain_chat_service.py`
- `src/copaw/app/crons/executor.py`
- `src/copaw/environments/models.py`
- `src/copaw/environments/surface_control_service.py`
- `src/copaw/evidence/models.py`
- `src/copaw/evidence/ledger.py`

The new work is allowed to add one orchestration layer above them. It is not allowed to create a parallel research subsystem.

## 5. Current Repo Truth

### 5.1 Formal Research Sessions Already Exist

The repo already has formal research objects:

- `ResearchSessionRecord`
- `ResearchSessionRoundRecord`

These live in:

- `src/copaw/state/models_research.py`
- `src/copaw/state/repositories/sqlite_research.py`

So phase 1 does not start from zero and should not invent a second session model.

### 5.2 Baidu Page Research Already Exists

The repo already has a vertical research service:

- `src/copaw/research/baidu_page_research_service.py`

It already supports:

- session creation
- multi-round execution
- link deepening
- artifact/download handling
- summary writeback

This service proves that a formal research chain is already possible.

But it is currently still a provider-shaped vertical implementation, not the universal external-information collection foundation.

### 5.3 Main-Brain Direct Research Trigger Already Exists

`src/copaw/kernel/main_brain_chat_service.py` already contains an explicit research trigger front-door.

It can:

- detect explicit research requests
- resolve a research owner agent
- start a formal research session
- run the session
- summarize it

The current truth is therefore:

- CoPaw does not lack research triggering
- CoPaw lacks a generalized cross-source foundation behind that trigger

### 5.4 Monitoring Wake-Up Already Exists

`src/copaw/app/crons/executor.py` already supports the monitoring wake-up path for research sessions.

This means:

- scheduled research already has a formal wake-up chain
- but it is still tied to the current provider/mode contract

### 5.5 Browser / Environment / Evidence Already Exist

The repo already has:

- `EnvironmentMount`
- `SessionMount`
- browser/document/windows surface execution routes
- formal `EvidenceRecord`

So external-information collection does not need to invent a second execution runtime or a second evidence chain.

## 6. Formal Architecture

The new universal foundation should sit above the existing provider/surface primitives and below profession-specific planning.

Recommended placement:

`src/copaw/research/source_collection/`

Recommended modules:

- `service.py`
  - universal orchestration owner
- `contracts.py`
  - typed request/result contracts
- `routing.py`
  - light-collection vs heavy-research routing
- `synthesis.py`
  - dedupe, merge, conflict/gap marking
- `writeback.py`
  - evidence/session/work-context/report writeback
- `adapters/search.py`
- `adapters/web_page.py`
- `adapters/github.py`
- `adapters/artifact.py`
- `providers/baidu_page.py`
  - optional provider adapter that wraps current Baidu logic

This layer should own the universal collection chain, while providers/adapters only own source-specific execution.

## 7. Formal Typed Contracts

Phase 1 should first introduce typed contracts, while keeping persistence reuse-first.

### 7.1 `ResearchBrief`

Represents one formal external-information collection request.

Required fields:

- `requester_agent_id`
- `supervisor_agent_id`
- `goal`
- `question`
- `why_needed`
- `done_when`
- `writeback_target`
- `urgency`
- `collection_mode_hint`
  - `light` or `heavy` or `auto`
- `source_preferences`
- `source_constraints`

Phase 1 does not need a dedicated table for this object.

It may initially be stored as typed payload under `ResearchSessionRecord.metadata`.

### 7.2 `CollectedSource`

Represents one collected source item.

Required fields:

- `source_kind`
  - open source taxonomy, for example:
  - `page`
  - `repo`
  - `artifact`
  - `api`
  - `forum`
  - `document`
- `collection_action`
  - `discover | read | interact | capture`
- `source_ref`
  - url, repo ref, artifact path, or equivalent source identity
- `title`
- `snippet`
- `adapter_kind`
- `provider_kind`
- `relevance_score`
- `credibility_hint`
- `collected_at`
- `evidence_refs`

Phase 1 may store these inside round payloads and evidence payloads instead of a dedicated repository.

### 7.3 `ResearchFinding`

Represents one synthesized finding from one or more sources.

Required fields:

- `finding_type`
  - for example:
  - `fact`
  - `comparison`
  - `constraint`
  - `conflict`
  - `gap`
  - `next-probe`
- `summary`
- `supporting_source_refs`
- `conflicting_source_refs`
- `gaps`
- `next_probe`

This is the key structure that stops the system from having only raw page text or raw research dialogue.

### 7.4 `ResearchAdapterResult`

Represents the output of one source adapter execution.

Required fields:

- `adapter_kind`
- `collection_action`
- `status`
  - `succeeded | partial | blocked | failed`
- `collected_sources`
- `candidate_findings`
- `followup_links`
- `artifacts`
- `blockers`
- `continuation_hint`

## 8. Formal Collection Action Models

The stable top-level model should not be a closed source taxonomy.

If CoPaw hardcodes a small list of source families as the permanent ontology, the list will keep expanding forever.

The stable layer should instead be the collection action model.

Phase 1 should fix these action models:

### 8.1 `discover`

Role:

- discover candidate sources
- search indexes or search engines
- browse source entry points
- identify possible next probes

### 8.2 `read`

Role:

- read one source directly
- extract content from a page, repo surface, issue, doc page, or equivalent source
- return structured evidence-backed content

### 8.3 `interact`

Role:

- continue through a source when passive reading is not enough
- click, navigate, expand, paginate, ask follow-up questions, or otherwise interact to get the needed information
- later reuse the universal surface execution foundation when browser interaction is required

### 8.4 `capture`

Role:

- capture downloadable or structured outputs into the formal chain
- record artifact identity and provenance
- persist snippets, downloads, extracted outputs, or equivalent collected results

This keeps the stable architecture on "how collection happens", not "what the world contains".

## 9. Phase 1 Adapters

The phase-1 adapter set should still be explicit, but it should be understood as the first adapter batch, not the permanent ontology.

### 9.1 `search`

Role:

- discover candidate sources
- generate hit lists
- provide entry points for deeper collection

This adapter should not be treated as the final answer by default.

### 9.2 `web_page`

Role:

- open and read ordinary web pages
- extract key page content
- continue through relevant next links where needed

This adapter should later reuse the universal surface execution foundation for page interaction.

### 9.3 `github`

Role:

- read repository entry pages
- read README/docs/release notes/issues/PR pages
- extract repo-structured findings

GitHub is intentionally an adapter here because it is a high-value recurring source shape in CoPaw's likely workflows, not because it should become the permanent top-level ontology.

### 9.4 `artifact`

Role:

- capture downloaded or attached artifacts
- record artifact identity and provenance
- support artifact-level summary or follow-up extraction

Artifacts are outputs or evidence sources. They are not just another search hit.

## 10. Formal Routing

The universal collection chain should route requests through one decision:

- `light collection`
- `heavy research`

### 10.1 Light Collection

Light collection should be used when the request is:

- narrow
- single-source or near-single-source
- unlikely to require multiple rounds
- low-cost to answer

In this mode, the current requesting profession agent may execute the collection directly through the shared foundation.

Examples:

- check one README
- verify one platform rule page
- read one official pricing/spec page

### 10.2 Heavy Research

Heavy research should be used when the request is:

- multi-round
- cross-source
- comparison-heavy
- artifact-heavy
- monitoring-oriented
- expected to need deeper follow-up

In this mode, the collection should be routed to the `researcher` seat by default.

This preserves the boundary:

- all agents can invoke
- `researcher` remains the default heavy research executor

## 11. Formal Data Flow

The target collection chain should be:

1. a profession agent or the main brain creates a formal `ResearchBrief`
2. kernel decides `light` vs `heavy`
3. if `light`, current agent executes through the shared collection foundation
4. if `heavy`, the task is routed to `researcher`
5. the orchestration layer selects one or more source adapters
6. adapters collect `CollectedSource` and candidate findings
7. synthesis merges, dedupes, marks conflicts and gaps
8. the result writes back into formal evidence, session truth, and downstream work/report/context truth

The system should therefore preserve both:

- raw source provenance
- synthesized, operator-usable findings

## 12. Integration Boundaries

### 12.1 Main Brain

The main brain is responsible for:

- recognizing information gaps
- forming or approving the brief
- deciding whether findings should be adopted
- deciding whether a follow-up is needed

The main brain is not the low-level collector.

### 12.2 Researcher

The `researcher` seat is responsible for:

- heavy multi-round research
- deeper follow-up
- multi-source comparison
- monitoring-oriented collection

The `researcher` seat is a default heavy executor, not an exclusive gate.

### 12.3 Profession Agents

Ordinary profession agents may:

- request collection
- perform light collection
- consume findings
- escalate to heavy research when needed

This ensures the system does not force every information need through one specialist seat.

## 13. Writeback Requirements

Collection results must not stop at chat text.

At minimum, phase 1 must write back into:

- `ResearchSessionRecord / ResearchSessionRoundRecord`
- `EvidenceRecord`
- work-context/report/assignment-facing downstream truth where relevant
- main-brain visible summary surfaces

The foundation is incomplete if it can collect but cannot formally feed the system's truth chain.

## 14. Runtime Center Visibility

The Runtime Center should eventually show at least:

- current `ResearchBrief`
- current research owner
- current source list
- current findings
- current conflicts/gaps
- current artifact captures
- current writeback state

Important results must not remain trapped in logs or provider-specific traces.

## 15. Phase 1 Construction Order

1. Write this formal spec
2. Write an implementation plan
3. Introduce typed contracts:
   - `ResearchBrief`
   - `CollectedSource`
   - `ResearchFinding`
   - `ResearchAdapterResult`
4. Add one universal orchestration owner
5. Demote the current Baidu-specific service into a provider adapter shape where appropriate
6. Add first formal source adapters:
   - `search`
   - `web_page`
   - `github`
   - `artifact`
7. Connect main-brain trigger and profession-agent trigger through the same universal front-door
8. Expose the result in Runtime Center read surfaces

## 16. Completion Criteria

This round is complete only when all of the following are true:

1. all profession agents can formally request external-information collection
2. the main brain can form or approve a formal `ResearchBrief`
3. the system can route `light` vs `heavy` collection correctly
4. the `researcher` seat can execute heavy research as the default heavy path
5. the stable collection action model is formalized:
   - `discover`
   - `read`
   - `interact`
   - `capture`
6. the first phase-1 adapters are all connected:
   - `search`
   - `web_page`
   - `github`
   - `artifact`
7. results formally write back into:
   - research session truth
   - evidence truth
   - downstream work/report/context truth where relevant
8. Runtime Center can show collection truth
9. multi-round collection can continue without breaking the session chain
10. the system no longer treats one provider-specific service as the universal collection model

If any of these are missing, the collection foundation is not formally complete.

## 17. Deletion / Demotion Intent

This round should not delete the current Baidu research chain.

But it should demote the current assumption that:

- one provider-specific service equals the universal research system
- one `researcher` seat equals the only information collection entry

The intended end state is:

- one universal external-information collection foundation
- multiple source adapters
- optional provider adapters
- one shared formal truth and evidence chain

This is the correct generalization path for CoPaw.
