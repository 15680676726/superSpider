# Introduction

This page explains what `superSpider` is and how to approach the current public docs.

---

## What is superSpider?

`superSpider` is a local autonomous execution system built around one main brain.

It is not positioned as a generic personal assistant or a chat wrapper. The project is aimed at longer-running work where planning, memory, knowledge, runtime state, evidence, and operator control need to stay inside one visible system.

Today the formal external executor path is `Codex`. The system is being shaped so more executors can be governed later without becoming a second brain or a second truth source.

---

## What makes it different?

- **Main-brain control plane**: planning, delegation, supervision, and recovery stay in one formal runtime.
- **Formal memory and knowledge**: long-running context is not treated as disposable prompt stuffing.
- **Evidence-first execution**: runtime events, evidence, and replay come back into the same writeback chain.
- **Visible Runtime Center**: runtime state is meant to stay inspectable instead of disappearing into workers and logs.
- **Managed external executors**: execution can evolve without replacing the control plane.

---

## How should you read the docs?

Use this order:

1. **[Quick start](./quickstart)**: get the local service running.
2. **[Console](./console)**: understand the Runtime Center and operator-facing surface.
3. **[Models](./models)** and **[Config](./config)**: configure the runtime properly.
4. **[FAQ](./faq)**: understand current boundaries, naming, and project status.

---

## Current naming boundary

- Public project name: `superSpider`
- Current Python package / CLI name: `copaw`

That means the product is presented publicly as `superSpider`, but installation and local commands still use `copaw` for now.
