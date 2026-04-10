import { describe, expect, it } from "vitest";

import {
  resolveChatRouteRecoveryTarget,
  resolveChatThreadBootstrapState,
  shouldRefreshBoundThreadFromRuntimeEvent,
} from "./chatPageHelpers";

describe("chatPageHelpers", () => {
  it("recovers the active formal runtime thread for a bare chat entry", () => {
    expect(
      resolveChatRouteRecoveryTarget({
        requestedThreadId: null,
        activeThreadId: "industry-chat:industry-1:execution-core",
      }),
    ).toBe("/chat?threadId=industry-chat%3Aindustry-1%3Aexecution-core");
  });

  it("does not recover a plain /chat visit when the active thread is not a formal runtime thread", () => {
    expect(
      resolveChatRouteRecoveryTarget({
        requestedThreadId: null,
        activeThreadId: "chat:transient",
      }),
    ).toBeNull();
  });

  it("restores the active formal runtime thread immediately for a bare chat revisit", () => {
    expect(
      resolveChatThreadBootstrapState({
        requestedThreadId: null,
        activeThreadId: "industry-chat:industry-1:execution-core",
        activeThreadMeta: {
          session_kind: "industry-control-thread",
          industry_instance_id: "industry-1",
        },
      }),
    ).toEqual({
      effectiveThreadId: "industry-chat:industry-1:execution-core",
      initialThreadMeta: {
        session_kind: "industry-control-thread",
        industry_instance_id: "industry-1",
      },
      initialThreadBootstrapPending: false,
      initialAutoBindingPending: false,
      recoveryTarget: "/chat?threadId=industry-chat%3Aindustry-1%3Aexecution-core",
    });
  });

  it("keeps a bare /chat visit empty when there is no formal runtime thread to recover", () => {
    expect(
      resolveChatThreadBootstrapState({
        requestedThreadId: null,
        activeThreadId: null,
        activeThreadMeta: {},
      }),
    ).toEqual({
      effectiveThreadId: null,
      initialThreadMeta: {},
      initialThreadBootstrapPending: false,
      initialAutoBindingPending: false,
      recoveryTarget: null,
    });
  });

  it("refreshes a bound formal thread when execution-progress events arrive", () => {
    expect(
      shouldRefreshBoundThreadFromRuntimeEvent({
        requestedThreadId: "industry-chat:industry-1:execution-core",
        requestedThreadLooksBound: true,
        eventName: "assignment.updated",
      }),
    ).toBe(true);
    expect(
      shouldRefreshBoundThreadFromRuntimeEvent({
        requestedThreadId: "industry-chat:industry-1:execution-core",
        requestedThreadLooksBound: true,
        eventName: "report.created",
      }),
    ).toBe(true);
    expect(
      shouldRefreshBoundThreadFromRuntimeEvent({
        requestedThreadId: "industry-chat:industry-1:execution-core",
        requestedThreadLooksBound: true,
        eventName: "task.completed",
      }),
    ).toBe(true);
  });

  it("ignores heartbeat and unrelated events for bound thread refresh", () => {
    expect(
      shouldRefreshBoundThreadFromRuntimeEvent({
        requestedThreadId: "industry-chat:industry-1:execution-core",
        requestedThreadLooksBound: true,
        eventName: "runtime.heartbeat",
      }),
    ).toBe(false);
    expect(
      shouldRefreshBoundThreadFromRuntimeEvent({
        requestedThreadId: "industry-chat:industry-1:execution-core",
        requestedThreadLooksBound: true,
        eventName: "model.changed",
      }),
    ).toBe(false);
    expect(
      shouldRefreshBoundThreadFromRuntimeEvent({
        requestedThreadId: null,
        requestedThreadLooksBound: false,
        eventName: "report.created",
      }),
    ).toBe(false);
  });
});
