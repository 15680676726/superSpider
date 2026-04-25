# MCP-First Donor Adapter Assimilation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one common `MCP -> API/SDK -> adapter` assimilation seam on top of the existing external-source/runtime base so external donors can become formally callable CoPaw `adapter` capabilities, while `CLI/runtime`-only donors remain lower-tier `project-package / runtime-component` landings.

**Architecture:** Reuse the current external-source/package/candidate/trial/lifecycle/runtime-center spine and add a bounded adapter layer: protocol classification -> compiled adapter contract -> typed adapter execution -> scoped trial/evidence/lifecycle attribution. External protocols remain intake and transport facts only; the main brain and execution agents consume only CoPaw formal `adapter / runtime / project` capability truth.

**Tech Stack:** Python, FastAPI, Pydantic, SQLite state store, existing `src/copaw/capabilities`, `src/copaw/state`, `src/copaw/app/runtime_center`, pytest

---

## Scope Guard

This plan does **not** redo the already-landed external-source/source/runtime work:

- external-source/source normalization
- source-chain execution
- open-source project install/materialization
- scoped runtime instance lifecycle
- Runtime Center external-source/package/trust/scout read surfaces

This plan adds only the missing adapter-assimilation seam:

1. classify external-source callable surfaces
2. compile eligible donors into formal CoPaw `adapter` contracts
3. execute typed adapter actions through governed transport bridges
4. carry adapter attribution through trial/lifecycle/evidence/read models

Success criteria for this plan:

- `native_mcp` donors can compile into formal `adapter` contracts without project-specific branches
- `api` and `sdk` donors can compile into the same formal `adapter` shape when they provide a stable typed callable surface
- `cli_runtime` donors are explicitly blocked from pretending to be business adapters
- the main brain only sees `adapter:*`, never raw MCP method names, raw HTTP endpoints, or raw SDK imports
- Runtime Center can distinguish discovered, compiled, trialed, promoted, and blocked adapter candidates without inventing a second truth chain

## File Structure

### Existing files to modify

- `src/copaw/config/config.py`
  - Extend `ExternalCapabilityPackageConfig` with bounded adapter-assimilation fields such as `intake_protocol_kind`, `call_surface_ref`, and `adapter_contract`.
- `src/copaw/discovery/models.py`
  - Add protocol-surface metadata to `DiscoveryHit` and `NormalizedDiscoveryHit`.
- `src/copaw/capabilities/project_donor_contracts.py`
  - Extract generic callable-surface hints from installed external-source packages without adding external-source-specific branches.
- `src/copaw/app/routers/capability_market.py`
  - Persist protocol classification and compiled adapter contracts during project install/materialization.
- `src/copaw/state/skill_candidate_service.py`
  - Persist protocol classification and adapter-attribution metadata on candidate truth.
- `src/copaw/state/skill_trial_service.py`
  - Persist adapter-attribution metadata on scoped trial truth.
- `src/copaw/state/skill_lifecycle_decision_service.py`
  - Persist adapter-attribution metadata on lifecycle decisions.
- `src/copaw/capabilities/sources/external_packages.py`
  - Project compiled adapter contracts into `CapabilityMount` without leaking raw transport details to the main brain.
- `src/copaw/capabilities/execution.py`
  - Route `adapter:*` calls through typed adapter execution instead of the runtime-only executor.
- `src/copaw/capabilities/service.py`
  - Wire the new adapter executor into the existing `CapabilityExecutionFacade`.
- `src/copaw/app/runtime_center/state_query.py`
  - Extend existing external-source/candidate/portfolio read surfaces with protocol/adapter status.
- `src/copaw/app/routers/runtime_center_routes_core.py`
  - Expose the new adapter status fields through existing Runtime Center capability routes.
- `src/copaw/kernel/query_execution_runtime.py`
  - Preserve adapter attribution in runtime evidence metadata.
- `src/copaw/predictions/service_recommendations.py`
  - Carry protocol/adapter attribution through recommendation and lifecycle summaries.

### New files to create

- `src/copaw/capabilities/external_adapter_contracts.py`
  - Typed protocol-surface models, generic external-source hints contract, compiled adapter contract, and metadata serialization helpers.
- `src/copaw/capabilities/external_adapter_compiler.py`
  - Generic compiler that turns `native_mcp` / `api` / `sdk` surfaces into CoPaw-owned adapter contracts and blocks unsupported shapes.
- `src/copaw/capabilities/external_adapter_execution.py`
  - Governed execution bridge for compiled adapter actions across `mcp`, `http`, and bounded `sdk` transports.

### Tests to add or extend

- `tests/capabilities/test_external_adapter_contracts.py`
- `tests/capabilities/test_external_adapter_compiler.py`
- `tests/capabilities/test_external_adapter_execution.py`
- `tests/capabilities/test_external_packages.py`
- `tests/app/test_capability_market_api.py`
- `tests/app/test_capabilities_execution.py`
- `tests/app/test_runtime_center_donor_api.py`
- `tests/predictions/test_skill_candidate_service.py`
- `tests/predictions/test_skill_trial_service.py`
- `tests/predictions/test_donor_recommendations.py`
- `tests/kernel/test_query_execution_runtime.py`

---

### Task 1: Add Formal Protocol-Surface And Donor-Hints Contracts

**Files:**
- Create: `src/copaw/capabilities/external_adapter_contracts.py`
- Modify: `src/copaw/discovery/models.py`
- Modify: `src/copaw/state/skill_candidate_service.py`
- Test: `tests/capabilities/test_external_adapter_contracts.py`
- Test: `tests/predictions/test_skill_candidate_service.py`

- [ ] **Step 1: Write the failing protocol classification tests**

```python
def test_native_mcp_surface_is_adapter_eligible():
    surface = classify_external_protocol_surface(
        metadata={
            "mcp_server_ref": "mcp:openspace",
            "mcp_tools": [{"name": "execute_task", "input_schema": {"type": "object"}}],
        }
    )
    assert surface.protocol_surface_kind == "native_mcp"
    assert surface.transport_kind == "mcp"
    assert surface.formal_adapter_eligible is True

def test_cli_runtime_surface_is_not_adapter_eligible():
    surface = classify_external_protocol_surface(
        metadata={"execute_command": "python -m donor_app"}
    )
    assert surface.protocol_surface_kind == "cli_runtime"
    assert surface.formal_adapter_eligible is False
    assert "no-stable-callable-surface" in surface.blockers
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/capabilities/test_external_adapter_contracts.py tests/predictions/test_skill_candidate_service.py -q -k "protocol or adapter"
```

Expected: FAIL because protocol-surface contracts and classification helpers do not exist yet.

- [ ] **Step 3: Implement the typed protocol-surface contract**

```python
class ExternalProtocolSurface(BaseModel):
    protocol_surface_kind: Literal["native_mcp", "api", "sdk", "cli_runtime", "unknown"] = "unknown"
    transport_kind: Literal["mcp", "http", "sdk"] | None = None
    call_surface_ref: str | None = None
    schema_ref: str | None = None
    formal_adapter_eligible: bool = False
    blockers: list[str] = Field(default_factory=list)
    hints: dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 4: Add reusable classification and metadata serialization helpers**

```python
def classify_external_protocol_surface(*, metadata: Mapping[str, Any]) -> ExternalProtocolSurface:
    if metadata.get("mcp_server_ref") and metadata.get("mcp_tools"):
        return ExternalProtocolSurface(
            protocol_surface_kind="native_mcp",
            transport_kind="mcp",
            call_surface_ref=str(metadata["mcp_server_ref"]),
            formal_adapter_eligible=True,
            hints={"actions": metadata.get("mcp_tools", [])},
        )
    if metadata.get("openapi_url") or metadata.get("api_base_url"):
        ...
    if metadata.get("sdk_entry_ref") and metadata.get("sdk_actions"):
        ...
    return ExternalProtocolSurface(
        protocol_surface_kind="cli_runtime",
        formal_adapter_eligible=False,
        blockers=["no-stable-callable-surface"],
    )
```

- [ ] **Step 5: Persist the normalized protocol metadata on candidate truth**

```python
metadata_payload.update(
    {
        "protocol_surface_kind": surface.protocol_surface_kind,
        "transport_kind": surface.transport_kind,
        "call_surface_ref": surface.call_surface_ref,
        "formal_adapter_eligible": surface.formal_adapter_eligible,
        "adapter_blockers": list(surface.blockers),
    }
)
```

- [ ] **Step 6: Re-run tests**

Run:

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/capabilities/test_external_adapter_contracts.py tests/predictions/test_skill_candidate_service.py -q -k "protocol or adapter"
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/copaw/capabilities/external_adapter_contracts.py src/copaw/discovery/models.py src/copaw/state/skill_candidate_service.py tests/capabilities/test_external_adapter_contracts.py tests/predictions/test_skill_candidate_service.py
git commit -m "feat: add external-source protocol surface contracts"
```

### Task 2: Compile Eligible Donors Into Formal Adapter Contracts During Materialization

**Files:**
- Create: `src/copaw/capabilities/external_adapter_compiler.py`
- Modify: `src/copaw/config/config.py`
- Modify: `src/copaw/capabilities/project_donor_contracts.py`
- Modify: `src/copaw/app/routers/capability_market.py`
- Test: `tests/capabilities/test_external_adapter_compiler.py`
- Test: `tests/app/test_capability_market_api.py`

- [ ] **Step 1: Write the failing compiler tests**

```python
def test_native_mcp_surface_compiles_into_formal_adapter_contract():
    contract = compile_external_adapter_contract(
        capability_id="adapter:demo",
        surface=ExternalProtocolSurface(
            protocol_surface_kind="native_mcp",
            transport_kind="mcp",
            call_surface_ref="mcp:demo",
            formal_adapter_eligible=True,
            hints={"actions": [{"action_id": "execute_task", "tool_name": "execute_task"}]},
        ),
    )
    assert contract.transport_kind == "mcp"
    assert contract.actions[0].action_id == "execute_task"

def test_cli_runtime_only_surface_is_blocked_from_adapter_compilation():
    blocked = compile_external_adapter_contract(
        capability_id="adapter:demo",
        surface=ExternalProtocolSurface(protocol_surface_kind="cli_runtime"),
    )
    assert blocked is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/capabilities/test_external_adapter_compiler.py tests/app/test_capability_market_api.py -q -k "adapter_contract or project_install"
```

Expected: FAIL because no generic adapter compiler or install-time adapter persistence exists yet.

- [ ] **Step 3: Implement the compiled adapter contract model**

```python
class CompiledAdapterAction(BaseModel):
    action_id: str
    summary: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    transport_action_ref: str

class CompiledAdapterContract(BaseModel):
    compiled_adapter_id: str
    transport_kind: Literal["mcp", "http", "sdk"]
    call_surface_ref: str
    actions: list[CompiledAdapterAction] = Field(default_factory=list)
    promotion_blockers: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Add generic compile rules and bounded blocking behavior**

```python
def compile_external_adapter_contract(*, capability_id: str, surface: ExternalProtocolSurface) -> CompiledAdapterContract | None:
    if not surface.formal_adapter_eligible:
        return None
    if surface.transport_kind == "mcp":
        return _compile_mcp_adapter_contract(capability_id=capability_id, surface=surface)
    if surface.transport_kind == "http":
        return _compile_http_adapter_contract(capability_id=capability_id, surface=surface)
    if surface.transport_kind == "sdk":
        return _compile_sdk_adapter_contract(capability_id=capability_id, surface=surface)
    return None
```

- [ ] **Step 5: Persist protocol classification and adapter contracts on installed package truth**

```python
class ExternalCapabilityPackageConfig(BaseModel):
    ...
    intake_protocol_kind: str = "unknown"
    call_surface_ref: str = ""
    adapter_contract: Dict[str, object] = Field(default_factory=dict)
```

```python
package.intake_protocol_kind = surface.protocol_surface_kind
package.call_surface_ref = surface.call_surface_ref or ""
package.adapter_contract = (
    compiled_contract.model_dump(mode="json") if compiled_contract is not None else {}
)
```

- [ ] **Step 6: Re-run tests**

Run:

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/capabilities/test_external_adapter_compiler.py tests/app/test_capability_market_api.py -q -k "adapter_contract or project_install"
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/copaw/capabilities/external_adapter_compiler.py src/copaw/config/config.py src/copaw/capabilities/project_donor_contracts.py src/copaw/app/routers/capability_market.py tests/capabilities/test_external_adapter_compiler.py tests/app/test_capability_market_api.py
git commit -m "feat: compile external-source protocol surfaces into adapter contracts"
```

### Task 3: Project Compiled Adapters Into The Capability Graph Without Leaking Raw Protocols

**Files:**
- Modify: `src/copaw/capabilities/sources/external_packages.py`
- Test: `tests/capabilities/test_external_packages.py`

- [ ] **Step 1: Write the failing projection tests**

```python
def test_adapter_mount_projects_compiled_actions_not_raw_transport_details():
    mounts = list_external_package_capabilities()
    adapter = next(item for item in mounts if item.id == "adapter:demo")
    assert adapter.kind == "adapter"
    assert adapter.metadata["adapter_contract"]["transport_kind"] == "mcp"
    assert adapter.metadata["adapter_contract"]["actions"][0]["action_id"] == "execute_task"
    assert "raw_tool_name" not in adapter.summary.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/capabilities/test_external_packages.py -q -k "adapter_mount"
```

Expected: FAIL because compiled adapter contracts are not yet projected into `CapabilityMount`.

- [ ] **Step 3: Project the compiled adapter contract into mount metadata**

```python
metadata.update(
    {
        "intake_protocol_kind": str(getattr(package, "intake_protocol_kind", "") or "unknown"),
        "call_surface_ref": str(getattr(package, "call_surface_ref", "") or "") or None,
        "adapter_contract": dict(getattr(package, "adapter_contract", {}) or {}),
    }
)
```

- [ ] **Step 4: Keep the main-brain facing surface formal**

```python
if kind == "adapter":
    summary = "Governed external adapter compiled into formal CoPaw business actions."
    executor_ref = "external-adapter"
```

- [ ] **Step 5: Re-run tests**

Run:

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/capabilities/test_external_packages.py -q -k "adapter_mount"
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/capabilities/sources/external_packages.py src/copaw/capabilities/service.py tests/capabilities/test_external_packages.py
git commit -m "feat: project compiled external adapters into capability mounts"
```

### Task 4: Execute Typed Adapter Actions Through Governed Transport Bridges

**Files:**
- Create: `src/copaw/capabilities/external_adapter_execution.py`
- Modify: `src/copaw/capabilities/execution.py`
- Modify: `src/copaw/capabilities/service.py`
- Test: `tests/capabilities/test_external_adapter_execution.py`
- Test: `tests/app/test_capabilities_execution.py`

- [ ] **Step 1: Write the failing adapter execution tests**

```python
async def test_compiled_mcp_adapter_action_calls_bound_transport(monkeypatch):
    execution = ExternalAdapterExecution(mcp_manager=fake_mcp_manager(), environment_service=None)
    result = await execution.execute_action(
        mount=build_adapter_mount(
            transport_kind="mcp",
            action_id="execute_task",
            transport_action_ref="execute_task",
        ),
        action_id="execute_task",
        payload={"task": "hello"},
    )
    assert result["success"] is True
    assert result["adapter_action"] == "execute_task"

async def test_runtime_only_capability_rejects_business_adapter_action():
    result = await facade.execute_task(build_runtime_task("runtime:demo", action="execute_task"))
    assert result["success"] is False
    assert "formal adapter" in result["summary"].lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/capabilities/test_external_adapter_execution.py tests/app/test_capabilities_execution.py -q -k "adapter_action or runtime_only"
```

Expected: FAIL because `adapter:*` still routes through the runtime-only executor.

- [ ] **Step 3: Implement the generic adapter executor**

```python
class ExternalAdapterExecution:
    async def execute_action(self, *, mount: CapabilityMount, action_id: str, payload: dict[str, Any]) -> dict[str, object]:
        contract = _adapter_contract(mount)
        if contract.transport_kind == "mcp":
            return await self._execute_mcp_action(contract, action_id, payload)
        if contract.transport_kind == "http":
            return await self._execute_http_action(contract, action_id, payload)
        if contract.transport_kind == "sdk":
            return await self._execute_sdk_action(contract, action_id, payload)
        return {"success": False, "summary": "Unsupported adapter transport."}
```

- [ ] **Step 4: Route `adapter:*` through the new executor and keep runtime-only external sources blocked**

```python
if mount.kind == "adapter" and metadata.get("adapter_contract"):
    response = await self._external_adapter_execution.execute_action(
        mount=mount,
        action_id=resolved_action,
        payload=resolved_payload,
    )
elif runtime_contract.get("runtime_kind") in {"cli", "service"}:
    ...
else:
    return _json_tool_response({"success": False, "summary": "Capability is not a formal adapter."})
```

- [ ] **Step 5: Wire the adapter executor through `CapabilityService`**

```python
self._execution = CapabilityExecutionFacade(
    ...,
    external_adapter_execution=ExternalAdapterExecution(
        mcp_manager=self._mcp_manager,
        environment_service=self._environment_service,
    ),
)
```

- [ ] **Step 6: Re-run tests**

Run:

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/capabilities/test_external_adapter_execution.py tests/app/test_capabilities_execution.py -q -k "adapter_action or runtime_only"
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/copaw/capabilities/external_adapter_execution.py src/copaw/capabilities/execution.py src/copaw/capabilities/service.py tests/capabilities/test_external_adapter_execution.py tests/app/test_capabilities_execution.py
git commit -m "feat: execute compiled external adapter actions"
```

### Task 5: Carry Adapter Attribution Through Trial, Lifecycle, Recommendations, And Evidence

**Files:**
- Modify: `src/copaw/state/skill_trial_service.py`
- Modify: `src/copaw/state/skill_lifecycle_decision_service.py`
- Modify: `src/copaw/kernel/query_execution_runtime.py`
- Modify: `src/copaw/predictions/service_recommendations.py`
- Test: `tests/predictions/test_skill_trial_service.py`
- Test: `tests/predictions/test_donor_recommendations.py`
- Test: `tests/kernel/test_query_execution_runtime.py`

- [ ] **Step 1: Write the failing attribution tests**

```python
def test_trial_summary_keeps_protocol_and_compiled_adapter_ids():
    trial = service.create_or_update_trial(
        candidate_id="cand-1",
        scope_type="seat",
        scope_ref="seat-1",
        metadata={
            "protocol_surface_kind": "native_mcp",
            "transport_kind": "mcp",
            "compiled_adapter_id": "adapter:demo",
        },
    )
    assert trial.metadata["compiled_adapter_id"] == "adapter:demo"

def test_runtime_evidence_carries_adapter_action_attribution():
    metadata = normalize_execution_attribution(
        {
            "skill_trial_id": "trial-1",
            "external_source_id": "source-1",
            "package_id": "pkg-1",
            "protocol_surface_kind": "api",
            "transport_kind": "http",
            "compiled_adapter_id": "adapter:demo",
            "selected_adapter_action_id": "search",
        }
    )
    assert metadata["selected_adapter_action_id"] == "search"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/predictions/test_skill_trial_service.py tests/predictions/test_donor_recommendations.py tests/kernel/test_query_execution_runtime.py -q -k "adapter or attribution"
```

Expected: FAIL because adapter attribution is not yet carried consistently.

- [ ] **Step 3: Standardize adapter attribution keys across trial and lifecycle writes**

```python
metadata = {
    **dict(metadata or {}),
    "protocol_surface_kind": surface.protocol_surface_kind,
    "transport_kind": compiled_contract.transport_kind,
    "compiled_adapter_id": compiled_contract.compiled_adapter_id,
    "compiled_action_ids": [item.action_id for item in compiled_contract.actions],
}
```

- [ ] **Step 4: Extend runtime evidence normalization with adapter-specific keys**

```python
for key in (
    "protocol_surface_kind",
    "transport_kind",
    "compiled_adapter_id",
    "selected_adapter_action_id",
):
    if _first_non_empty(raw_payload.get(key)) is not None:
        normalized[key] = _first_non_empty(raw_payload.get(key))
```

- [ ] **Step 5: Re-run tests**

Run:

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/predictions/test_skill_trial_service.py tests/predictions/test_donor_recommendations.py tests/kernel/test_query_execution_runtime.py -q -k "adapter or attribution"
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/state/skill_trial_service.py src/copaw/state/skill_lifecycle_decision_service.py src/copaw/kernel/query_execution_runtime.py src/copaw/predictions/service_recommendations.py tests/predictions/test_skill_trial_service.py tests/predictions/test_donor_recommendations.py tests/kernel/test_query_execution_runtime.py
git commit -m "feat: preserve adapter attribution across lifecycle and evidence"
```

### Task 6: Extend Runtime Center Read Surfaces For Protocol And Adapter Status

**Files:**
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/routers/runtime_center_routes_core.py`
- Test: `tests/app/test_runtime_center_donor_api.py`

- [ ] **Step 1: Write the failing Runtime Center tests**

```python
def test_candidate_payload_includes_protocol_and_compiled_adapter_status(client):
    response = client.get("/api/runtime-center/capabilities/candidates")
    payload = response.json()["items"][0]
    assert payload["protocol_surface_kind"] == "native_mcp"
    assert payload["compiled_adapter_id"] == "adapter:demo"
    assert payload["promotion_blockers"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/app/test_runtime_center_donor_api.py -q -k "compiled_adapter or protocol_surface"
```

Expected: FAIL because Runtime Center does not yet expose the adapter-assimilation fields.

- [ ] **Step 3: Extend existing candidate/external-source/portfolio projections**

```python
payload["protocol_surface_kind"] = metadata.get("protocol_surface_kind")
payload["transport_kind"] = metadata.get("transport_kind")
payload["compiled_adapter_id"] = metadata.get("compiled_adapter_id")
payload["compiled_action_ids"] = list(metadata.get("compiled_action_ids") or [])
payload["promotion_blockers"] = list(metadata.get("adapter_blockers") or [])
```

- [ ] **Step 4: Keep the routes on existing Runtime Center surfaces**

```python
@router.get("/capabilities/candidates")
async def get_runtime_center_capability_candidates(...):
    ...
```

No new second capability UI path should be added; extend the existing routes only.

- [ ] **Step 5: Re-run tests**

Run:

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/app/test_runtime_center_donor_api.py -q -k "compiled_adapter or protocol_surface"
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/copaw/app/runtime_center/state_query.py src/copaw/app/routers/runtime_center_routes_core.py tests/app/test_runtime_center_donor_api.py
git commit -m "feat: expose adapter assimilation status in runtime center"
```

### Task 7: Run Focused Regression And Common-Base Proof Samples

**Files:**
- Modify: `docs/superpowers/specs/2026-04-06-mcp-first-external-adapter-assimilation-design.md`
- Modify: `TASK_STATUS.md`

- [ ] **Step 1: Run the focused regression slices**

Run:

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/capabilities/test_external_adapter_contracts.py tests/capabilities/test_external_adapter_compiler.py tests/capabilities/test_external_adapter_execution.py tests/capabilities/test_external_packages.py tests/app/test_capability_market_api.py tests/app/test_capabilities_execution.py tests/app/test_runtime_center_donor_api.py tests/predictions/test_skill_candidate_service.py tests/predictions/test_skill_trial_service.py tests/predictions/test_donor_recommendations.py tests/kernel/test_query_execution_runtime.py -q
```

Expected: PASS

- [ ] **Step 2: Run one real `native_mcp` proof sample through the common base**

Run the existing install/search path against a real MCP-native external-source and verify:

- install succeeds
- compiled adapter contract exists
- at least one typed adapter action executes
- Runtime Center shows `protocol_surface_kind=native_mcp`

- [ ] **Step 3: Run one real `api` or `sdk` proof sample through the same common base**

Verify:

- no project-specific branch was added
- external-source compiles into the same `adapter_contract` shape
- at least one typed adapter action executes
- trial/lifecycle/evidence attribution contains `compiled_adapter_id`

- [ ] **Step 4: Update architecture status docs with only verified reality**

Document:

- what protocol shapes are truly live-verified
- what remains blocked by design
- that `MCP-first but not MCP-only` is now implemented as the common external-source adapter base

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-04-06-mcp-first-external-adapter-assimilation-design.md TASK_STATUS.md
git commit -m "docs: record verified external-source adapter assimilation coverage"
```

## Notes For Implementers

- Do not add `if provider == "OpenSpace"` or any other external-source-specific branch anywhere in the common base.
- Do not let `project-package` or `runtime-component` masquerade as formal business adapters.
- Prefer first-class typed contracts over ad-hoc metadata parsing; when metadata is used, keep the keys centralized in `external_adapter_contracts.py`.
- If a external-source lacks a stable typed callable surface, keep it installable as `project-package / runtime-component` and stop there.
- `sdk` transport may use a bounded bridge runner internally, but the main brain must still only see formal adapter actions.
