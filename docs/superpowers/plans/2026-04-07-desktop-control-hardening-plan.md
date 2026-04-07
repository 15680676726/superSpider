# Desktop Control Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tighten the desktop-control chain so formal runtime replay enforces capability mounting, health checks reflect semantic-control readiness, and document writes share stable writer locks across sessions.

**Architecture:** Keep the Windows desktop control chain Windows-host-first and evidence-first, but fail closed at the formal runtime front door. Preserve low-level harness flexibility by only enforcing capability ownership when the formal runtime wiring provides agent/capability services. Make health/readiness and cooperative writer-lock semantics explicit instead of relying on weak defaults.

**Tech Stack:** Python, FastAPI services, Pydantic, pytest

---

### Task 1: Formal Desktop Replay Capability Enforcement

**Files:**
- Modify: `src/copaw/routines/service.py`
- Modify: `src/copaw/app/runtime_bootstrap_domains.py`
- Test: `tests/routines/test_routine_service.py`

- [ ] Add a failing test proving desktop replay fails closed in formal runtime mode when the owning agent lacks `mcp:desktop_windows`.
- [ ] Run the targeted routine-service test to verify the failure is real.
- [ ] Add the minimal `RoutineService` runtime capability guard and wire the optional services from runtime bootstrap.
- [ ] Re-run the targeted routine-service tests until green.

### Task 2: Desktop Doctor And Example-Run Depth

**Files:**
- Modify: `src/copaw/capabilities/install_templates.py`
- Test: `tests/app/test_capability_market_api.py`

- [ ] Add a failing test proving the desktop doctor exposes semantic-control readiness separately from bare Win32 readiness.
- [ ] Run the targeted capability-market test to verify the failure is real.
- [ ] Implement the minimal doctor/example-run changes so the report no longer overclaims desktop readiness.
- [ ] Re-run the targeted capability-market tests until green.

### Task 3: Stable Writer Scope For Desktop Document Actions

**Files:**
- Modify: `src/copaw/environments/surface_control_service.py`
- Test: `tests/environments/test_cooperative_document_bridge.py`

- [ ] Add a failing test proving document actions against the same file derive the same writer scope even across different sessions when no explicit scope is supplied.
- [ ] Run the targeted document-bridge test to verify the failure is real.
- [ ] Implement the minimal writer-scope derivation from stable document identity before falling back to `session_mount_id`.
- [ ] Re-run the targeted document-bridge tests until green.

### Task 4: Focused Verification And Delivery

**Files:**
- Verify: `tests/routines/test_routine_service.py`
- Verify: `tests/app/test_capability_market_api.py`
- Verify: `tests/environments/test_cooperative_document_bridge.py`
- Verify: `tests/routines/test_routine_execution_paths.py`
- Verify: `tests/environments/test_cooperative_windows_apps.py`

- [ ] Run the focused regression matrix that covers the hardened desktop replay, doctor/example-run surface, and cooperative desktop document execution.
- [ ] Update status docs only if the external contract or audit wording materially changes.
- [ ] Commit and push the desktop-control hardening bundle.
