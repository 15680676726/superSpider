<div align="center">
  <img src="console/public/spider-mesh-symbol.svg" alt="superSpider logo" width="120" />

  # superSpider

  <p><b>The main brain for local autonomous execution.</b></p>
</div>

superSpider is not another chat wrapper. It is a local execution main brain built to drive long-running work through managed external executors, visible runtime state, persistent environments, and evidence-first writeback.

Today, the formal external executor path is `Codex`. The architecture is being shaped so the same main brain can govern more external executors over time, including `Hermes`-class runtimes, without turning those executors into a second brain or a second truth source.

## Why this project exists

Most AI projects stop at chat, prompts, and tool calls. That is useful, but it breaks down when work needs to continue, recover, prove what happened, or stay visible after the model has already answered once.

superSpider is built for that harder operating problem:

- one main brain that decides what should happen next
- external executors that actually do the work
- one Runtime Center where runtime state, evidence, recovery, and operator control stay visible
- one local operating surface instead of scattered scripts, panels, and hidden worker state

## What superSpider is

superSpider is a local-first autonomous execution system with a clear split:

- `superSpider` is the main brain
- external executors are the execution layer
- the Runtime Center is the visible operating surface
- evidence and runtime state are written back into the same local truth chain

That split matters. The executor should execute. The main brain should plan, delegate, supervise, recover, and keep the system coherent over time.

## What works today

The current repository already supports these core behaviors:

- a formal main-brain execution chain over goals, backlog, assignments, runtime state, and evidence
- a managed local external executor path using `Codex`
- runtime continuity, event ingestion, evidence writeback, and recovery
- a Runtime Center for execution, observation, governance, and operator control
- a local-first workflow where the operator can inspect what ran, what failed, and what the system believes is true

## External executor model

superSpider does not treat external executors as plugins hidden behind a chat prompt.

It treats them as managed execution surfaces.

- `superSpider` owns the main-brain logic, task truth, recovery logic, and operator-visible state
- the external executor owns the execution turn
- execution results come back as runtime events, evidence, and structured writeback

Current formal path:

- `Codex` as the active external executor path

Planned path:

- `Hermes`-class runtimes and other formal executor providers that can fit the same execution contract

## Why developers care

superSpider is aimed at developers who want more than a chat assistant:

- AI agent and automation developers who want a visible runtime instead of a black box
- independent developers who want local autonomous execution instead of a hosted orchestration layer
- people building long-running work where evidence, recovery, and state continuity matter as much as model output

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
