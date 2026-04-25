<div align="center">
  <img src="console/public/spider-mesh-symbol.svg" alt="superSpider logo" width="120" />

  # superSpider

  <p><b>The main brain for local autonomous execution.</b></p>
</div>

superSpider is not another chat wrapper. It is a local execution main brain built to drive long-running work through managed external executors, visible runtime state, persistent environments, and evidence-first writeback.

Today, the formal external executor path is `Codex`. The architecture is being shaped so the same main brain can govern more external executors over time, including `Hermes`-class runtimes, without turning those executors into a second brain or a second truth source.

## Why this project exists

Most AI projects stop at chat, prompts, and tool calls. That layer is useful, but it breaks down when work needs to continue, recover, prove what happened, remember why it matters, and stay operable after the model has already answered once.

superSpider is built for that harder operating problem:

- one main brain that decides what should happen next
- one memory and knowledge chain that survives beyond a single reply
- one Runtime Center where runtime state, evidence, recovery, and operator control stay visible
- managed external executors that actually do the work without becoming a second brain

## What makes superSpider different

superSpider is opinionated about where system intelligence should live.

- planning, delegation, supervision, recovery, and governance belong to the main brain
- memory and knowledge belong to the formal local truth chain, not to disposable prompt context
- execution belongs to managed external executors
- evidence, artifacts, replay, and operator visibility belong to the same writeback chain

That split is the core advantage of the system. It lets execution change without losing the control plane, and it lets the control plane stay coherent without collapsing everything into a single black-box agent loop.

## Core system capabilities

### Main Brain

superSpider has a formal main-brain orchestration layer rather than a chat-first request loop.

- it compiles goals, backlog, assignments, and operating context into execution
- it decides what should be done now, what should wait, what should be delegated, and what needs recovery or human confirmation
- it keeps the system coherent across long-running work instead of treating every turn as a fresh conversation

### Memory System

This system has formal memory, not just chat history.

- `StrategyMemory` carries mission, priorities, constraints, execution policy, and evidence expectations
- runtime continuity is preserved through work contexts, assignments, executor thread bindings, and durable metadata
- memory is local and truth-first: it is meant to support execution continuity, not just make prompts longer

### Knowledge System

superSpider separates knowledge from memory and gives it structure.

- `KnowledgeChunk` records store durable facts across global, industry, agent, task, and work-context scopes
- the system can activate a structured knowledge graph and task subgraph for the current query or assignment
- that subgraph can carry entities, constraints, contradictions, dependencies, blockers, recovery paths, and evidence references
- planners and Runtime Center reads can consume this structured knowledge directly instead of relying on ad-hoc prompt stuffing

### Evidence and Replay

superSpider is built to prove what happened.

- execution turns and external actions write back as runtime events, evidence records, artifacts, and replay pointers
- the system can show what ran, what changed, what failed, and why a decision was made
- this makes the platform usable for real operating loops where traceability matters as much as model quality

### Runtime Center

The Runtime Center is not an afterthought. It is the visible operating surface of the system.

- it exposes runtime state, evidence, governance, recovery, memory activation, and operator control
- it gives the operator a live view of what the system believes is true
- it turns long-running execution into something inspectable instead of hiding it in workers, logs, or scattered scripts

### External Executors

superSpider does not treat execution as a prompt trick. It treats execution as a managed surface.

- `superSpider` owns the main-brain logic, truth chain, recovery logic, and visible control plane
- the external executor owns the execution turn
- execution results come back through normalized runtime events, evidence, and structured writeback
- today the formal path is `Codex`
- the same contract is intended to govern future executors, including `Hermes`-class runtimes

## Where superSpider is useful

superSpider is aimed at work that is bigger than a single model response.

- long-running local research and operating loops
- systems that need memory, knowledge, evidence, and recovery to stay aligned over time
- operator-facing automation where runtime state must stay visible and governable
- execution chains that span browser, desktop, document, file, or external runtime surfaces and still need one control plane

## What works today

The current repository already supports these core behaviors:

- a formal main-brain execution chain over goals, backlog, assignments, runtime state, and evidence
- formal strategy memory and long-lived local memory reads for runtime and planning surfaces
- a structured knowledge path with knowledge chunks, task-subgraph activation, and Runtime Center knowledge projections
- a managed local external executor path using `Codex`
- runtime continuity, event ingestion, evidence writeback, and recovery
- a Runtime Center for execution, observation, governance, memory surfaces, and operator control
- a local-first workflow where the operator can inspect what ran, what failed, and what the system believes is true

## Why developers care

superSpider is aimed at developers who want more than a chat assistant:

- AI agent and automation developers who want a visible runtime instead of a black box
- independent developers who want local autonomous execution instead of a hosted orchestration layer
- builders who care about memory, knowledge structure, evidence, and recovery as first-class system concerns

## What this repository is not

superSpider is not:

- a generic chat UI
- a prompt wrapper around tools
- a random workflow marketplace
- a system where any imported project automatically becomes a formal executor

This repository is trying to build a disciplined execution architecture, not a loose collection of demos.

## Repository shape

- `src/copaw/`: runtime kernel, state, capability, execution, evidence, and compatibility layers
- `console/`: main frontend and Runtime Center
- `website/`: repository-hosted docs and product pages
- root planning and status docs: architecture, migration, and acceptance records

## Naming

- Project name: `superSpider`
- Repository: `https://github.com/15680676726/superSpider`
- Current Python package / CLI name: `copaw`

The runtime package and CLI have not been renamed yet, so installation and commands still use `copaw`.

## Current project status

- public repository
- issues, discussions, and pull requests are open
- governance is currently maintainer-led
- larger changes should start with an issue or discussion

Architecture and live progress are tracked in:

- [System Architecture](COPAW_CARRIER_UPGRADE_MASTERPLAN.md)
- [Task Status](TASK_STATUS.md)
- [Data Model Draft](DATA_MODEL_DRAFT.md)
- [API Transition Map](API_TRANSITION_MAP.md)

## Quick start

```bash
pip install -e .
copaw init --defaults
copaw app
```

Then open `http://127.0.0.1:8088/`.

## Frontend development

Main frontend:

```bash
cd console
npm install
npm run dev
```

Docs / website:

```bash
cd website
npm install
npm run dev
```

## Key docs

- [Master plan](COPAW_CARRIER_UPGRADE_MASTERPLAN.md)
- [Task status](TASK_STATUS.md)
- [Frontend upgrade plan](FRONTEND_UPGRADE_PLAN.md)
- [Runtime Center UI spec](RUNTIME_CENTER_UI_SPEC.md)
- [Agent visible model](AGENT_VISIBLE_MODEL.md)
- [Docs directory](website/public/docs/)

## Contributing

- [Contributing guide](CONTRIBUTING.md)
- [Code of conduct](CODE_OF_CONDUCT.md)
- [Support](SUPPORT.md)
- [Governance](GOVERNANCE.md)
- [Security policy](SECURITY.md)
- [Issues](https://github.com/15680676726/superSpider/issues)
- [Discussions](https://github.com/15680676726/superSpider/discussions)
