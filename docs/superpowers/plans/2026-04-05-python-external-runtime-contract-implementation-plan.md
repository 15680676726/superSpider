# Python Donor Runtime Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn supported GitHub/Python external-source projects into formally installable and operable `project-package / adapter / runtime-component` capabilities with typed runtime contracts, scoped runtime instances, governed lifecycle actions, and Runtime Center visibility.

**Architecture:** Keep declarative runtime contract truth on installed external capability package truth, project that contract into `CapabilityMount`, and add a separate scoped runtime-instance state chain for actual `run/start/stop/restart/healthcheck` operations. Runtime actions must go through governed service facades and Runtime Center read surfaces instead of falling back to raw shell-wrapper behavior.

**Tech Stack:** Python, FastAPI, Pydantic, SQLite state store, existing `capabilities/`, `state/`, `app/runtime_center/`, pytest

---

## File Structure

### Existing files to modify

- `src/copaw/config/config.py`
  - Extend `ExternalCapabilityPackageConfig` with canonical runtime-contract fields owned by package truth.
- `src/copaw/capabilities/project_donor_contracts.py`
  - Resolve install-time predicted runtime contract without starting service runtime sources.
- `src/copaw/app/routers/capability_market.py`
  - Stop install-time active verification, persist canonical runtime-contract truth, and return predicted contract projections.
- `src/copaw/capabilities/sources/external_packages.py`
  - Project runtime contract into `CapabilityMount` metadata/environment/evidence/action fields.
- `src/copaw/capabilities/execution.py`
  - Remove supported-external-source raw-shell fallback and route external external-source actions through a typed runtime-operation service.
- `src/copaw/app/runtime_service_graph.py`
  - Wire runtime repositories/services into bootstrap and query layers.
- `src/copaw/app/runtime_center/state_query.py`
  - Expose external runtime contract/runtime-instance read surfaces.
- `src/copaw/app/routers/runtime_center_routes_core.py`
  - Add Runtime Center external runtime endpoints.
- `src/copaw/state/models.py`
  - Re-export new runtime model(s).
- `src/copaw/state/__init__.py`
  - Re-export new service(s).
- `src/copaw/state/store.py`
  - Register new SQLite table(s).
- `src/copaw/state/repositories/base.py`
  - Define repository protocol(s) for runtime instances.
- `src/copaw/state/repositories/sqlite.py`
  - Export concrete repository implementation.
- `src/copaw/state/repositories/sqlite_shared.py`
  - Add row encode/decode helpers if needed.

### New files to create

- `src/copaw/state/models_external_runtime.py`
  - `ExternalCapabilityRuntimeInstanceRecord` and typed enums/policies.
- `src/copaw/state/repositories/sqlite_external_runtimes.py`
  - SQLite-backed persistence for external runtime instances.
- `src/copaw/state/external_runtime_service.py`
  - Scoped runtime-instance CRUD, uniqueness, reconcile, and action recording.
- `src/copaw/capabilities/external_runtime_actions.py`
  - Typed runtime action payload models and validation helpers.
- `src/copaw/capabilities/external_runtime_execution.py`
  - Typed executor for `run/start/healthcheck/stop/restart`.

### Tests to add or extend

- `tests/capabilities/test_project_donor_contracts.py`
- `tests/capabilities/test_external_packages.py`
- `tests/app/test_capability_market_api.py`
- `tests/app/test_capabilities_execution.py`
- `tests/app/test_runtime_center_events_api.py`
- `tests/app/test_runtime_bootstrap_helpers.py`
- `tests/state/test_external_runtime_service.py`
- `tests/app/test_runtime_center_external_runtime_api.py`

---

### Task 1: Canonical Runtime Contract On Installed Package Truth

**Files:**
- Modify: `src/copaw/config/config.py`
- Modify: `src/copaw/capabilities/project_donor_contracts.py`
- Modify: `src/copaw/app/routers/capability_market.py`
- Modify: `src/copaw/capabilities/sources/external_packages.py`
- Test: `tests/capabilities/test_project_donor_contracts.py`
- Test: `tests/capabilities/test_external_packages.py`
- Test: `tests/app/test_capability_market_api.py`

- [ ] **Step 1: Write failing tests for install-time runtime contract projection**

```python
def test_external_project_install_returns_predicted_runtime_contract_not_live_fields():
    payload = install_project(...)
    assert payload["runtime_contract"]["runtime_kind"] == "service"
    assert payload["runtime_contract"]["predicted_default_port"] == 8080
    assert "port" not in payload["runtime_contract"]
    assert "health_url" not in payload["runtime_contract"]
```

```python
def test_install_does_not_run_service_healthcheck_during_contract_prediction():
    called = []
    monkeypatch.setattr(module, "_run_external_project_shell_command", lambda *a, **k: called.append(a))
    install_project(...)
    assert called == []
```

- [ ] **Step 2: Run failing tests**

Run: `python -m pytest tests/capabilities/test_project_donor_contracts.py tests/capabilities/test_external_packages.py tests/app/test_capability_market_api.py -q -k "runtime_contract or external_project_install"`

Expected: FAIL because runtime-contract fields are not canonicalized and install still verifies by running a shell command.

- [ ] **Step 3: Extend config truth and contract resolver**

```python
class ExternalCapabilityPackageConfig(BaseModel):
    runtime_kind: Literal["cli", "service"] | None = None
    supported_actions: list[str] = Field(default_factory=list)
    scope_policy: str = "session"
    ready_probe_kind: str = "none"
    ready_probe_config: dict[str, Any] = Field(default_factory=dict)
    stop_strategy: str = "terminate"
    startup_entry_ref: str = ""
```

```python
def resolve_installed_python_project_contract(...):
    return InstalledPythonProjectContract(
        runtime_kind="service" if looks_like_service else "cli",
        supported_actions=["describe", "start", "healthcheck", "stop", "restart"],
        predicted_default_port=port_hint,
        predicted_health_path=health_hint,
        ...
    )
```

- [ ] **Step 4: Persist contract truth and remove install-time active validation**

```python
resolved_contract = resolve_installed_python_project_contract(...)
packages[capability_id] = ExternalCapabilityPackageConfig(
    ...,
    runtime_kind=resolved_contract.runtime_kind,
    supported_actions=list(resolved_contract.supported_actions),
    ready_probe_kind=resolved_contract.ready_probe_kind,
    ready_probe_config=dict(resolved_contract.ready_probe_config),
    stop_strategy=resolved_contract.stop_strategy,
    startup_entry_ref=resolved_contract.startup_entry_ref,
)
```

- [ ] **Step 5: Project runtime contract into `CapabilityMount`**

```python
metadata.update(
    {
        "runtime_contract": {
            "runtime_kind": package.runtime_kind,
            "supported_actions": package.supported_actions,
            "scope_policy": package.scope_policy,
            "ready_probe_kind": package.ready_probe_kind,
        }
    }
)
```

- [ ] **Step 6: Re-run tests**

Run: `python -m pytest tests/capabilities/test_project_donor_contracts.py tests/capabilities/test_external_packages.py tests/app/test_capability_market_api.py -q -k "runtime_contract or external_project_install"`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/copaw/config/config.py src/copaw/capabilities/project_donor_contracts.py src/copaw/app/routers/capability_market.py src/copaw/capabilities/sources/external_packages.py tests/capabilities/test_project_donor_contracts.py tests/capabilities/test_external_packages.py tests/app/test_capability_market_api.py
git commit -m "feat: add canonical python external-runtime contracts"
```

### Task 2: Add Scoped External Runtime Instance State

**Files:**
- Create: `src/copaw/state/models_external_runtime.py`
- Create: `src/copaw/state/repositories/sqlite_external_runtimes.py`
- Create: `src/copaw/state/external_runtime_service.py`
- Modify: `src/copaw/state/models.py`
- Modify: `src/copaw/state/__init__.py`
- Modify: `src/copaw/state/store.py`
- Modify: `src/copaw/state/repositories/base.py`
- Modify: `src/copaw/state/repositories/sqlite.py`
- Test: `tests/state/test_external_runtime_service.py`

- [ ] **Step 1: Write failing tests for scoped runtime instance truth**

```python
def test_starting_same_service_in_same_scope_reuses_or_rejects_duplicate_instance(tmp_path):
    service = build_runtime_service(tmp_path)
    first = service.create_starting_instance(capability_id="runtime:openspace", scope_kind="session", session_mount_id="session-1")
    second = service.create_starting_instance(capability_id="runtime:openspace", scope_kind="session", session_mount_id="session-1")
    assert second.runtime_id == first.runtime_id
```

```python
def test_cli_run_creates_historical_execution_instance(tmp_path):
    service = build_runtime_service(tmp_path)
    run = service.record_cli_run(...)
    assert run.runtime_kind == "cli"
    assert run.status in {"completed", "failed"}
```

- [ ] **Step 2: Run failing tests**

Run: `python -m pytest tests/state/test_external_runtime_service.py -q`

Expected: FAIL because no external runtime instance model/service exists.

- [ ] **Step 3: Add model and repository contracts**

```python
class ExternalCapabilityRuntimeInstanceRecord(UpdatedRecord):
    runtime_id: str = Field(default_factory=_new_record_id)
    capability_id: str
    runtime_kind: Literal["cli", "service"]
    scope_kind: Literal["session", "work_context", "seat"]
    work_context_id: str | None = None
    environment_ref: str | None = None
    session_mount_id: str | None = None
    status: Literal["starting", "restarting", "ready", "degraded", "completed", "stopped", "failed", "orphaned"]
```

- [ ] **Step 4: Add SQLite table and service logic**

```python
CREATE TABLE external_capability_runtime_instances (
    runtime_id TEXT PRIMARY KEY,
    capability_id TEXT NOT NULL,
    runtime_kind TEXT NOT NULL,
    scope_kind TEXT NOT NULL,
    work_context_id TEXT,
    environment_ref TEXT,
    session_mount_id TEXT,
    status TEXT NOT NULL,
    ...
)
```

```python
def resolve_active_service_instance(...):
    # Enforce max 1 active service runtime per capability + canonical scope ref
```

- [ ] **Step 5: Re-run tests**

Run: `python -m pytest tests/state/test_external_runtime_service.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/state/models_external_runtime.py src/copaw/state/repositories/sqlite_external_runtimes.py src/copaw/state/external_runtime_service.py src/copaw/state/models.py src/copaw/state/__init__.py src/copaw/state/store.py src/copaw/state/repositories/base.py src/copaw/state/repositories/sqlite.py tests/state/test_external_runtime_service.py
git commit -m "feat: add scoped external runtime instance state"
```

### Task 3: Add Typed Runtime Actions And Governed Executor

**Files:**
- Create: `src/copaw/capabilities/external_runtime_actions.py`
- Create: `src/copaw/capabilities/external_runtime_execution.py`
- Modify: `src/copaw/capabilities/execution.py`
- Modify: `src/copaw/capabilities/service.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Test: `tests/app/test_capabilities_execution.py`

- [ ] **Step 1: Write failing tests for typed action admission**

```python
def test_supported_service_donor_rejects_raw_shell_payload():
    response = execute_external_capability(
        capability_id="runtime:openspace",
        payload={"action": "start", "command": "openspace --weird-shell-override"},
    )
    assert response["success"] is False
    assert "typed runtime action" in response["error"]
```

```python
def test_service_healthcheck_requires_runtime_id():
    response = execute_external_capability(
        capability_id="runtime:openspace",
        payload={"action": "healthcheck"},
    )
    assert response["success"] is False
    assert "runtime_id" in response["error"]
```

- [ ] **Step 2: Run failing tests**

Run: `python -m pytest tests/app/test_capabilities_execution.py -q -k "external_runtime or supported_service_donor or runtime_id"`

Expected: FAIL because `_execute_external_package` still accepts generic shell payloads.

- [ ] **Step 3: Add typed payload models**

```python
class StartExternalRuntimePayload(BaseModel):
    arg_profile: str | None = None
    port_override: int | None = None
    health_path_override: str | None = None
    retention_policy: str | None = None
```

```python
class RunExternalRuntimePayload(BaseModel):
    args: list[str] = Field(default_factory=list)
    timeout_sec: int | None = None
    input_artifact_ref: str | None = None
```

- [ ] **Step 4: Replace generic shell executor path for supported donors**

```python
if mount.metadata.get("runtime_contract", {}).get("runtime_kind") == "service":
    return await self._external_runtime_execution.start(...)
```

- [ ] **Step 5: Route through governed service facade**

```python
external_runtime_service = ExternalRuntimeService(...)
capability_execution = CapabilityExecutionService(
    ...,
    external_runtime_service=external_runtime_service,
)
```

- [ ] **Step 6: Re-run tests**

Run: `python -m pytest tests/app/test_capabilities_execution.py -q -k "external_runtime or supported_service_donor or runtime_id"`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/copaw/capabilities/external_runtime_actions.py src/copaw/capabilities/external_runtime_execution.py src/copaw/capabilities/execution.py src/copaw/capabilities/service.py src/copaw/app/runtime_service_graph.py tests/app/test_capabilities_execution.py
git commit -m "feat: govern external runtime-provider actions"
```

### Task 4: Add Runtime Center External Runtime APIs And Read Models

**Files:**
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_core.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Test: `tests/app/test_runtime_center_external_runtime_api.py`
- Test: `tests/app/test_runtime_center_events_api.py`

- [ ] **Step 1: Write failing API/read-model tests**

```python
def test_runtime_center_lists_external_runtime_instances(client):
    response = client.get("/runtime-center/capabilities/external-runtimes")
    assert response.status_code == 200
    assert response.json()[0]["runtime"]["capability_id"] == "runtime:openspace"
```

```python
def test_runtime_center_runtime_contract_route_returns_projected_contract(client):
    response = client.get("/runtime-center/capabilities/runtime:openspace/runtime-contract")
    assert response.status_code == 200
    assert response.json()["runtime_kind"] == "service"
```

- [ ] **Step 2: Run failing tests**

Run: `python -m pytest tests/app/test_runtime_center_external_runtime_api.py tests/app/test_runtime_center_events_api.py -q -k "external_runtime or runtime_contract"`

Expected: FAIL because these routes/read models do not exist.

- [ ] **Step 3: Extend Runtime Center state query service**

```python
def list_external_runtime_instances(self, *, capability_id: str | None = None) -> list[dict[str, object]]:
    ...

def get_external_runtime_contract(self, capability_id: str) -> dict[str, object] | None:
    ...
```

- [ ] **Step 4: Add Runtime Center routes**

```python
@router.get("/capabilities/external-runtimes")
def list_external_runtimes(...): ...

@router.get("/capabilities/{capability_id:path}/runtime-contract")
def get_runtime_contract(...): ...
```

- [ ] **Step 5: Re-run tests**

Run: `python -m pytest tests/app/test_runtime_center_external_runtime_api.py tests/app/test_runtime_center_events_api.py -q -k "external_runtime or runtime_contract"`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/app/runtime_center/state_query.py src/copaw/app/routers/runtime_center_routes_core.py src/copaw/app/runtime_service_graph.py tests/app/test_runtime_center_external_runtime_api.py tests/app/test_runtime_center_events_api.py
git commit -m "feat: expose external runtime providers in runtime center"
```

### Task 5: Bootstrap Reconcile, Orphan Detection, And Recovery Paths

**Files:**
- Modify: `src/copaw/state/external_runtime_service.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Modify: `src/copaw/app/test_runtime_bootstrap_helpers.py`
- Test: `tests/app/test_runtime_bootstrap_helpers.py`
- Test: `tests/state/test_external_runtime_service.py`

- [ ] **Step 1: Write failing reconcile/orphan tests**

```python
def test_runtime_bootstrap_marks_orphaned_instance_when_process_is_gone(tmp_path):
    service = build_runtime_service(tmp_path)
    runtime = persisted_ready_runtime(process_id=99999)
    service.reconcile_instances(process_probe=lambda pid: False)
    refreshed = service.get_runtime(runtime.runtime_id)
    assert refreshed.status == "orphaned"
```

```python
def test_runtime_bootstrap_reclaims_instance_when_probe_matches_scope(tmp_path):
    ...
    assert refreshed.status == "ready"
```

- [ ] **Step 2: Run failing tests**

Run: `python -m pytest tests/state/test_external_runtime_service.py tests/app/test_runtime_bootstrap_helpers.py -q -k "orphaned or reconcile or external_runtime"`

Expected: FAIL because no reconcile/orphan flow exists.

- [ ] **Step 3: Implement reconcile paths**

```python
def reconcile_instances(...):
    if process_missing:
        return mark_orphaned(...)
    if scope_matches and probe_ready:
        return reclaim(...)
```

- [ ] **Step 4: Wire bootstrap reconciliation**

```python
external_runtime_service.reconcile_instances(
    environment_service=environment_service,
    process_probe=...,
)
```

- [ ] **Step 5: Re-run tests**

Run: `python -m pytest tests/state/test_external_runtime_service.py tests/app/test_runtime_bootstrap_helpers.py -q -k "orphaned or reconcile or external_runtime"`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/state/external_runtime_service.py src/copaw/app/runtime_service_graph.py tests/state/test_external_runtime_service.py tests/app/test_runtime_bootstrap_helpers.py
git commit -m "feat: reconcile external runtime-provider instances"
```

### Task 6: Live Smoke, Regression Sweep, And Docs Sync

**Files:**
- Modify: `TASK_STATUS.md`
- Optionally Create: `tests/app/test_runtime_center_external_runtime_live_smoke.py`
- Modify: any touched tests from previous tasks as needed

- [ ] **Step 1: Add or extend gated live smoke coverage**

```python
def test_live_python_donor_cli_and_service_smoke(...):
    cli = discover_install_run("https://github.com/psf/black")
    service = discover_install_start_ready_stop("https://github.com/HKUDS/OpenSpace")
    assert cli["success"] is True
    assert service["start"]["success"] is True
    assert service["stop"]["success"] is True
```

- [ ] **Step 2: Run focused regression**

Run: `python -m pytest tests/capabilities/test_project_donor_contracts.py tests/capabilities/test_external_packages.py tests/state/test_external_runtime_service.py tests/app/test_capability_market_api.py tests/app/test_capabilities_execution.py tests/app/test_runtime_center_external_runtime_api.py tests/app/test_runtime_center_events_api.py tests/app/test_runtime_bootstrap_helpers.py -q`

Expected: PASS

- [ ] **Step 3: Run broader adjacent regression**

Run: `python -m pytest tests/app/test_runtime_center_donor_api.py tests/app/runtime_center_api_parts/overview_governance.py tests/kernel/test_query_execution_runtime.py tests/predictions/test_skill_candidate_service.py tests/predictions/test_skill_trial_service.py -q`

Expected: PASS

- [ ] **Step 4: Run gated live smoke**

Run: `python scripts/channel_live_smoke.py --scenario <python-external-runtime-smoke-scenario>`

Expected:
- `psf/black`: discover -> install -> run succeeds
- `HKUDS/OpenSpace`: discover -> install -> start -> ready -> stop succeeds

- [ ] **Step 5: Update status docs truthfully**

```markdown
- install now predicts runtime contract without hidden service start
- supported Python runtime providers now create scoped runtime instances
- Runtime Center exposes runtime contract + runtime instances + lifecycle actions
- live smoke validated one CLI runtime provider and one service runtime provider
```

- [ ] **Step 6: Commit**

```bash
git add TASK_STATUS.md tests/app/test_runtime_center_external_runtime_live_smoke.py
git commit -m "docs: record python external-runtime closure"
```
