<div align="center">
  <img src="console/public/spider-mesh-symbol.svg" alt="Spider Mesh logo" width="120" />

  # Spider Mesh

  <p><b>A local execution system for goals, environments, evidence, and long-running work.</b></p>
</div>

Spider Mesh is a local execution system for long-running autonomous work. It brings goals, agents, tasks, environments, evidence, and patches into one Runtime Center so execution, observation, and evolution happen on the same visible surface.

Its design is centered on four things: main-brain execution over assignment/backlog truth, persistent environments, evidence-first runtime behavior, and one local operating surface instead of scattered control panels.

## Current entry points

- `console/` is the main frontend and Runtime Center.
- `website/` is the outward-facing product site for Spider Mesh.
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

Placeholder website:

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
