<div align="center">
  <img src="console/public/spider-mesh-symbol.svg" alt="superSpider logo" width="120" />

  # superSpider

  <p><b>A local autonomous execution system for goals, environments, evidence, and long-running multi-agent work.</b></p>
</div>

superSpider is a local-first runtime for long-running autonomous work. It brings goals, agents, tasks, environments, evidence, and patches into one Runtime Center so planning, execution, observation, and recovery happen on the same visible surface.

It is built around four operational ideas:

- main-brain execution over formal `assignment / backlog` truth
- managed external executors instead of hidden local worker state
- persistent environments and evidence-first runtime behavior
- one local operating surface instead of scattered control panels

## What superSpider does today

- Runs a main-brain driven execution chain over goals, backlog, assignments, runtime state, and evidence.
- Uses a managed local external executor path for real task execution and writeback.
- Keeps runtime continuity, evidence, and operator-visible state in one Runtime Center.
- Exposes a local control surface for execution, observation, governance, and recovery.

## Who it is for

superSpider is for operators and developers who want a local autonomous execution system instead of a chat-only assistant. It is intended for people who need long-running work, governed execution, visible runtime state, and evidence they can inspect after the fact.

## What this repository contains

- `src/copaw/`: runtime kernel, state, capability, execution, evidence, and compatibility layers
- `console/`: main frontend and Runtime Center
- `website/`: repository-hosted docs and product pages
- root planning/status docs: live architecture, migration, and acceptance records

## Naming

- Project name: `superSpider`
- Repository: `https://github.com/15680676726/superSpider`
- Current Python package / CLI name: `copaw`

The runtime package and CLI have not been renamed yet, so installation and commands still use `copaw`.

## Current status

The repository is public and open for issues, discussions, and pull requests. The current governance model is maintainer-led, and external contributors should start with an issue or discussion for larger changes.

## Current entry points

- `console/` is the main frontend and Runtime Center.
- `website/` contains the repository-hosted docs and product pages.
- Architecture and live progress are tracked in [System Architecture](COPAW_CARRIER_UPGRADE_MASTERPLAN.md) and [Task Status](TASK_STATUS.md).

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
