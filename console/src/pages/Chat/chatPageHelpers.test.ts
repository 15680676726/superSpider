import { describe, expect, it } from "vitest";

import {
  countPendingChatApprovals,
  resolveChatThreadBootstrapState,
  resolveChatRouteRecoveryTarget,
  shouldAutoRefreshRuntimeThread,
} from "./chatPageHelpers";

describe("countPendingChatApprovals", () => {
  it("counts only decisions and proposed patches as pending approvals", () => {
    expect(
      countPendingChatApprovals({
        pending_decisions: 3,
        proposed_patches: 2,
        pending_patches: 12,
      }),
    ).toBe(5);
  });

  it("returns zero when governance payload is absent", () => {
    expect(countPendingChatApprovals(null)).toBe(0);
  });

  it("recovers the active formal runtime thread for a bare chat entry", () => {
    expect(
      resolveChatRouteRecoveryTarget({
        requestedThreadId: null,
        buddySessionId: null,
        requestedBuddyProfileId: null,
        activeThreadId: "industry-chat:industry-1:execution-core",
      }),
    ).toBe("/chat?threadId=industry-chat%3Aindustry-1%3Aexecution-core");
  });

  it("does not override the buddy onboarding entry with a stale active thread", () => {
    expect(
      resolveChatRouteRecoveryTarget({
        requestedThreadId: null,
        buddySessionId: "session-1",
        requestedBuddyProfileId: "profile-1",
        activeThreadId: "industry-chat:industry-1:execution-core",
      }),
    ).toBeNull();
  });

  it("restores the active formal runtime thread immediately for a bare chat revisit", () => {
    expect(
      resolveChatThreadBootstrapState({
        requestedThreadId: null,
        buddySessionId: null,
        requestedBuddyProfileId: null,
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

  it("does not overwrite a fresh onboarding entry with the previously active thread", () => {
    expect(
      resolveChatThreadBootstrapState({
        requestedThreadId: null,
        buddySessionId: "session-1",
        requestedBuddyProfileId: "profile-1",
        activeThreadId: "industry-chat:industry-1:execution-core",
        activeThreadMeta: {
          session_kind: "industry-control-thread",
        },
      }),
    ).toEqual({
      effectiveThreadId: null,
      initialThreadMeta: {},
      initialThreadBootstrapPending: false,
      initialAutoBindingPending: true,
      recoveryTarget: null,
    });
  });

  it("auto refreshes bound runtime control threads so background writeback can surface", () => {
    expect(
      shouldAutoRefreshRuntimeThread({
        threadId: "industry-chat:buddy:profile-1:domain-stock:execution-core",
        threadMeta: {
          session_kind: "industry-control-thread",
        },
      }),
    ).toBe(true);
  });

  it("does not auto refresh unbound or generic chat threads", () => {
    expect(
      shouldAutoRefreshRuntimeThread({
        threadId: "chat:transient",
        threadMeta: {},
      }),
    ).toBe(false);
  });

  it("does not auto refresh a bound thread after bootstrap has already failed", () => {
    expect(
      shouldAutoRefreshRuntimeThread({
        threadId: "industry-chat:buddy:profile-1:domain-stock:execution-core",
        threadMeta: {
          session_kind: "industry-control-thread",
        },
        threadBootstrapError: "[404] thread missing",
      }),
    ).toBe(false);
  });
});
