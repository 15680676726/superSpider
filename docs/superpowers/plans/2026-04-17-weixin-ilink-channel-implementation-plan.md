# Weixin iLink Channel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land `weixin_ilink` as a first-class personal WeChat channel so private chat, group chat triggers, QR login, proactive reports, and runtime visibility all run through CoPaw's canonical channel and main-brain paths.

**Architecture:** Extend the existing built-in channel system instead of creating a sidecar ingress. Keep formal truth split clean: persisted config stays in `ChannelConfig`, while QR login and polling status live in a dedicated runtime projection service that the config router and Runtime Center both read. The channel itself stays a normal `BaseChannel` implementation that translates iLink HTTP payloads into canonical `content_parts + meta`, then routes replies and proactive reports back out through `sendmessage`.

**Tech Stack:** Python, FastAPI, Pydantic, aiohttp/httpx-style HTTP client patterns, React, Ant Design, Vitest, pytest

---

### File Map

**Create**
- `src/copaw/app/channels/weixin_ilink/__init__.py`
  - Built-in package export for the new channel.
- `src/copaw/app/channels/weixin_ilink/client.py`
  - iLink HTTP API client, token-file helpers, QR/login status helpers, media download helpers.
- `src/copaw/app/channels/weixin_ilink/channel.py`
  - `BaseChannel` implementation for long-poll receive, trigger rules, message normalization, and outbound text replies.
- `src/copaw/app/channels/weixin_ilink/runtime_state.py`
  - Process-local runtime projection for `login_status / polling_status / last_error / last_send_at / last_receive_at`.
- `tests/channels/test_weixin_ilink_client.py`
  - Unit coverage for token persistence, QR/login state, and API request normalization.
- `tests/channels/test_weixin_ilink_channel.py`
  - Unit coverage for DM/group routing, trigger rules, message parsing, and outbound send behavior.
- `tests/app/test_weixin_ilink_config_api.py`
  - Integration coverage for `/config/channels/weixin_ilink/*` control-plane APIs.
- `tests/app/test_runtime_center_channel_runtime_api.py`
  - Integration coverage for Runtime Center read surfaces exposing `weixin_ilink` runtime projection.
- `console/src/pages/Settings/Channels/components/ChannelDrawer.test.tsx`
  - UI regression coverage for new QR-login controls and `weixin_ilink` form fields.
- `console/src/pages/Settings/Channels/useChannels.test.ts`
  - Hook-level regression for channel ordering and `weixin_ilink` availability.

**Modify**
- `src/copaw/config/config.py`
  - Add `WeixinILinkConfig`, wire it into `ChannelConfig`, and extend `ChannelConfigUnion`.
- `src/copaw/app/channels/registry.py`
  - Register `weixin_ilink` as a built-in channel key.
- `src/copaw/app/routers/config.py`
  - Keep normal config CRUD working and add QR/status/rebind endpoints under `/config/channels/weixin_ilink/*`.
- `src/copaw/app/runtime_bootstrap_query.py`
  - Inject the `weixin_ilink` runtime projection service into `RuntimeCenterStateQueryService`.
- `src/copaw/app/runtime_service_graph.py`
  - Construct and expose the `weixin_ilink` runtime projection service at app startup.
- `src/copaw/app/runtime_center/state_query.py`
  - Expose channel-runtime list/detail helpers for Runtime Center.
- `src/copaw/app/runtime_center/overview_cards.py`
  - Surface `weixin_ilink` runtime/evidence status in overview cards without inventing a second dashboard.
- `tests/app/test_capabilities_write_api.py`
  - Extend governed config-write coverage to the new channel shape.
- `console/src/api/modules/channel.ts`
  - Add frontend API calls for QR/status/rebind.
- `console/src/api/types/channel.ts`
  - Add `WeixinILinkConfig` and QR/runtime response types.
- `console/src/pages/Settings/Channels/components/constants.ts`
  - Add the product label `Weixin Personal (iLink)` while the user-facing zh copy stays in the actual UI text layer.
- `console/src/pages/Settings/Channels/components/ChannelDrawer.tsx`
  - Add iLink-specific form fields, QR-login controls, and runtime status strip.
- `console/src/pages/Settings/Channels/index.tsx`
  - Orchestrate QR/status actions and save flow.
- `console/src/pages/Settings/Channels/useChannels.ts`
  - Keep `weixin_ilink` in built-in ordering and expose any extra runtime refresh needed by the drawer.
- `console/src/pages/RuntimeCenter/useRuntimeCenter.ts`
  - Pull the new runtime projection into the existing Runtime Center surface.
- `console/src/pages/RuntimeCenter/viewHelpers.test.tsx`
  - Lock down human-readable runtime/evidence copy once the new channel appears in Runtime Center.
- `TASK_STATUS.md`
  - Record feature status and exact acceptance level once implementation is actually green.

---

### Task 1: Lock the backend config and channel-registration contract

**Files:**
- Modify: `src/copaw/config/config.py`
- Modify: `src/copaw/app/channels/registry.py`
- Test: `tests/app/test_weixin_ilink_config_api.py`
- Test: `tests/app/test_capabilities_write_api.py`

- [ ] **Step 1: Write the failing integration tests for config shape and registration**

```python
def test_list_channel_types_includes_weixin_ilink_when_builtin_registry_loads():
    ...


def test_put_channel_accepts_weixin_ilink_config_shape():
    ...
```

- [ ] **Step 2: Run the targeted backend API tests and verify they fail**

Run:

```powershell
python -m pytest tests/app/test_weixin_ilink_config_api.py -q -k "channel_types or config_shape"
```

Expected: FAIL because `weixin_ilink` is not yet a known built-in channel or config model.

- [ ] **Step 3: Add the minimal config model and built-in registration**

Implement:
- `WeixinILinkConfig` in `src/copaw/config/config.py`
- `weixin_ilink` entry in `src/copaw/app/channels/registry.py`
- `ChannelConfigUnion` inclusion so `/config/channels/{channel}` round-trips formally

- [ ] **Step 4: Re-run the focused config tests**

Run:

```powershell
python -m pytest tests/app/test_weixin_ilink_config_api.py tests/app/test_capabilities_write_api.py -q -k "weixin_ilink or channel_update_route"
```

Expected: PASS for the new config/registration contract.

- [ ] **Step 5: Commit**

```powershell
git add src/copaw/config/config.py src/copaw/app/channels/registry.py tests/app/test_weixin_ilink_config_api.py tests/app/test_capabilities_write_api.py
git commit -m "feat: add weixin ilink channel config contract"
```

### Task 2: Land the iLink client and token-file lifecycle

**Files:**
- Create: `src/copaw/app/channels/weixin_ilink/client.py`
- Test: `tests/channels/test_weixin_ilink_client.py`

- [ ] **Step 1: Write the failing unit tests for token persistence and login API normalization**

```python
def test_token_file_round_trip_uses_utf8_and_expands_user_home():
    ...


def test_request_login_qr_uses_default_base_url_when_config_is_blank():
    ...


def test_poll_login_status_maps_authorized_result_to_runtime_status():
    ...
```

- [ ] **Step 2: Run the new client tests and verify they fail**

Run:

```powershell
python -m pytest tests/channels/test_weixin_ilink_client.py -q
```

Expected: FAIL because `client.py` does not exist yet.

- [ ] **Step 3: Implement the minimal client module**

Implement in `src/copaw/app/channels/weixin_ilink/client.py`:
- base URL resolution
- `bot_token_file` read/write helpers using explicit `encoding="utf-8"`
- QR request helper
- login status helper
- `getupdates`
- `sendmessage`
- media download helper stubs for image/file payloads

- [ ] **Step 4: Re-run the client unit tests**

Run:

```powershell
python -m pytest tests/channels/test_weixin_ilink_client.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/copaw/app/channels/weixin_ilink/client.py tests/channels/test_weixin_ilink_client.py
git commit -m "feat: add weixin ilink api client"
```

### Task 3: Land the channel class with DM/group routing and proactive send support

**Files:**
- Create: `src/copaw/app/channels/weixin_ilink/__init__.py`
- Create: `src/copaw/app/channels/weixin_ilink/channel.py`
- Test: `tests/channels/test_weixin_ilink_channel.py`

- [ ] **Step 1: Write the failing unit tests for ingress routing**

```python
def test_dm_message_always_enters_main_brain():
    ...


def test_group_message_requires_mention_or_prefix_by_default():
    ...


def test_allowlisted_group_can_run_full_open_mode():
    ...
```

- [ ] **Step 2: Write the failing unit tests for message normalization and outbound send**

```python
def test_voice_payload_uses_asr_text_and_keeps_media_reference():
    ...


def test_send_uses_sendmessage_text_only_contract():
    ...


def test_proactive_targets_reject_non_allowlisted_group_send():
    ...
```

- [ ] **Step 3: Run the focused channel unit tests and verify they fail**

Run:

```powershell
python -m pytest tests/channels/test_weixin_ilink_channel.py -q
```

Expected: FAIL because the channel class does not exist yet.

- [ ] **Step 4: Implement the minimal `BaseChannel` subclass**

Implement in `src/copaw/app/channels/weixin_ilink/channel.py`:
- long-poll loop over `getupdates`
- trigger logic for DM/group/mention/prefix/allowlist
- `content_parts + meta` normalization
- thread/session key generation
- text outbound reply
- proactive report send path
- runtime-state updates for receive/send/error timestamps

- [ ] **Step 5: Re-run the channel unit tests**

Run:

```powershell
python -m pytest tests/channels/test_weixin_ilink_channel.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/copaw/app/channels/weixin_ilink/__init__.py src/copaw/app/channels/weixin_ilink/channel.py tests/channels/test_weixin_ilink_channel.py
git commit -m "feat: add weixin ilink channel runtime"
```

### Task 4: Add QR login control-plane endpoints and runtime projection wiring

**Files:**
- Create: `src/copaw/app/channels/weixin_ilink/runtime_state.py`
- Modify: `src/copaw/app/routers/config.py`
- Modify: `src/copaw/app/runtime_bootstrap_query.py`
- Modify: `src/copaw/app/runtime_service_graph.py`
- Test: `tests/app/test_weixin_ilink_config_api.py`

- [ ] **Step 1: Write the failing API tests for QR, status, and rebind**

```python
def test_weixin_ilink_login_qr_returns_waiting_scan_runtime_projection():
    ...


def test_weixin_ilink_login_status_returns_authorized_pending_save_until_channel_config_is_saved():
    ...


def test_weixin_ilink_rebind_marks_old_token_expired_without_mutating_formal_config():
    ...
```

- [ ] **Step 2: Run the focused config API tests and verify they fail**

Run:

```powershell
python -m pytest tests/app/test_weixin_ilink_config_api.py -q -k "login_qr or login_status or rebind"
```

Expected: FAIL because the endpoints and runtime projection service do not exist yet.

- [ ] **Step 3: Implement runtime-state service and config-router endpoints**

Implement:
- `runtime_state.py` to hold process-local runtime truth
- `POST /config/channels/weixin_ilink/login/qr`
- `GET /config/channels/weixin_ilink/login/status`
- `POST /config/channels/weixin_ilink/login/rebind`
- startup wiring so the router and channel share one runtime-state service instance

- [ ] **Step 4: Re-run the config API tests**

Run:

```powershell
python -m pytest tests/app/test_weixin_ilink_config_api.py tests/app/test_capabilities_write_api.py -q -k "weixin_ilink or channel_update_route"
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/copaw/app/channels/weixin_ilink/runtime_state.py src/copaw/app/routers/config.py src/copaw/app/runtime_bootstrap_query.py src/copaw/app/runtime_service_graph.py tests/app/test_weixin_ilink_config_api.py tests/app/test_capabilities_write_api.py
git commit -m "feat: add weixin ilink login control plane"
```

### Task 5: Expose runtime truth and evidence in Runtime Center

**Files:**
- Modify: `src/copaw/app/runtime_center/state_query.py`
- Modify: `src/copaw/app/runtime_center/overview_cards.py`
- Test: `tests/app/test_runtime_center_channel_runtime_api.py`
- Test: `tests/app/test_runtime_center_external_runtime_api.py`

- [ ] **Step 1: Write the failing Runtime Center tests**

```python
def test_runtime_center_lists_weixin_ilink_runtime_projection():
    ...


def test_runtime_center_channel_runtime_detail_surfaces_login_polling_and_last_error_truth():
    ...
```

- [ ] **Step 2: Run the focused Runtime Center tests and verify they fail**

Run:

```powershell
python -m pytest tests/app/test_runtime_center_channel_runtime_api.py -q
```

Expected: FAIL because the state query service does not yet expose the channel runtime projection.

- [ ] **Step 3: Implement the Runtime Center read path**

Implement:
- state-query list/detail helpers for channel runtime truth
- overview-card entry or signal showing whether `weixin_ilink` is online
- evidence summary based on recent ingress/egress events, not string-only logging

- [ ] **Step 4: Re-run the Runtime Center tests**

Run:

```powershell
python -m pytest tests/app/test_runtime_center_channel_runtime_api.py tests/app/test_runtime_center_external_runtime_api.py -q -k "weixin_ilink or external_runtime"
```

Expected: PASS with no regression to existing external-runtime routes.

- [ ] **Step 5: Commit**

```powershell
git add src/copaw/app/runtime_center/state_query.py src/copaw/app/runtime_center/overview_cards.py tests/app/test_runtime_center_channel_runtime_api.py tests/app/test_runtime_center_external_runtime_api.py
git commit -m "feat: expose weixin ilink runtime in runtime center"
```

### Task 6: Add the formal Settings product surface

**Files:**
- Modify: `console/src/api/modules/channel.ts`
- Modify: `console/src/api/types/channel.ts`
- Modify: `console/src/pages/Settings/Channels/components/constants.ts`
- Modify: `console/src/pages/Settings/Channels/components/ChannelDrawer.tsx`
- Modify: `console/src/pages/Settings/Channels/index.tsx`
- Modify: `console/src/pages/Settings/Channels/useChannels.ts`
- Create: `console/src/pages/Settings/Channels/components/ChannelDrawer.test.tsx`
- Create: `console/src/pages/Settings/Channels/useChannels.test.ts`

- [ ] **Step 1: Write the failing frontend tests for product naming, ordering, and QR controls**

```tsx
it("renders 微信个人（iLink） as a built-in channel label", () => {
  ...
});

it("shows QR login controls and runtime status for weixin_ilink", async () => {
  ...
});

it("keeps weixin_ilink in built-in ordering returned by useChannels", async () => {
  ...
});
```

- [ ] **Step 2: Run the focused frontend tests and verify they fail**

Run:

```powershell
npm --prefix console test -- src/pages/Settings/Channels/components/ChannelDrawer.test.tsx src/pages/Settings/Channels/useChannels.test.ts
```

Expected: FAIL because the UI and API types do not yet support `weixin_ilink`.

- [ ] **Step 3: Implement the minimal Settings UI**

Implement:
- `WeixinILinkConfig` frontend type
- QR/status/rebind API calls
- drawer fields for `bot_token_file / base_url / media_dir / group_reply_mode / group_allowlist / proactive_targets`
- runtime status strip for `login_status / polling_status / token_source / last_error`
- save flow that keeps QR auth separate from formal config write

- [ ] **Step 4: Re-run the focused frontend tests**

Run:

```powershell
npm --prefix console test -- src/pages/Settings/Channels/components/ChannelDrawer.test.tsx src/pages/Settings/Channels/useChannels.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add console/src/api/modules/channel.ts console/src/api/types/channel.ts console/src/pages/Settings/Channels/components/constants.ts console/src/pages/Settings/Channels/components/ChannelDrawer.tsx console/src/pages/Settings/Channels/index.tsx console/src/pages/Settings/Channels/useChannels.ts console/src/pages/Settings/Channels/components/ChannelDrawer.test.tsx console/src/pages/Settings/Channels/useChannels.test.ts
git commit -m "feat: add weixin ilink channel settings ui"
```

### Task 7: Finish Runtime Center UI and run the three-layer acceptance matrix

**Files:**
- Modify: `console/src/pages/RuntimeCenter/useRuntimeCenter.ts`
- Modify: `console/src/pages/RuntimeCenter/viewHelpers.test.tsx`
- Modify: `TASK_STATUS.md`

- [ ] **Step 1: Write the failing Runtime Center UI regression test**

```tsx
it("renders human-readable weixin ilink runtime status instead of raw internal keys", () => {
  ...
});
```

- [ ] **Step 2: Run the focused Runtime Center UI test and verify it fails**

Run:

```powershell
npm --prefix console test -- src/pages/RuntimeCenter/viewHelpers.test.tsx
```

Expected: FAIL because Runtime Center does not yet surface the new channel runtime payload.

- [ ] **Step 3: Implement the minimal Runtime Center UI binding and update status docs**

Implement:
- Runtime Center fetch/binding for the `weixin_ilink` runtime projection
- human-readable labels for login/polling/error status
- `TASK_STATUS.md` entry only after L1/L2/L3 evidence exists

- [ ] **Step 4: Run the complete L1/L2 backend matrix**

Run:

```powershell
python -m pytest tests/channels/test_weixin_ilink_client.py tests/channels/test_weixin_ilink_channel.py tests/app/test_weixin_ilink_config_api.py tests/app/test_runtime_center_channel_runtime_api.py tests/app/test_capabilities_write_api.py -q
```

Expected: PASS.

- [ ] **Step 5: Run the focused frontend matrix**

Run:

```powershell
npm --prefix console test -- src/pages/Settings/Channels/components/ChannelDrawer.test.tsx src/pages/Settings/Channels/useChannels.test.ts src/pages/RuntimeCenter/viewHelpers.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Run the live acceptance checklist on a qualified iLink account**

Run manually in a live environment:
- obtain a real QR code from `POST /config/channels/weixin_ilink/login/qr`
- scan and authorize with a qualified iLink-capable account
- save the formal channel config
- send a real DM to main brain and verify reply
- send a real group `@主脑` message and verify reply
- trigger a proactive report to a DM target
- trigger a proactive report to an allowlisted group
- restart the app and verify `bot_token_file` restores login without rescanning

Expected: PASS for `L3` only when an account with real iLink capability is available.

- [ ] **Step 7: Commit**

```powershell
git add console/src/pages/RuntimeCenter/useRuntimeCenter.ts console/src/pages/RuntimeCenter/viewHelpers.test.tsx TASK_STATUS.md
git commit -m "feat: complete weixin ilink runtime surfaces"
```

---

## Execution Notes

- Use `@superpowers:test-driven-development` for every implementation task in this plan.
- Use `@superpowers:systematic-debugging` immediately if any of the new polling/login flows behave unexpectedly.
- Use `@superpowers:verification-before-completion` before any claim that `weixin_ilink` is complete.
- Do not claim the feature is complete unless the result is labeled explicitly by acceptance layer:
  - `L1`: backend/frontend unit coverage
  - `L2`: config router + Runtime Center integration coverage
  - `L3`: live QR/login/chat/proactive-report proof on a qualified iLink account

## Review Note

This plan was written without dispatching a plan-review subagent because the current turn did not include fresh user authorization for delegation. If the user explicitly re-enables delegation for this plan, run the normal review loop before large-scale execution.
