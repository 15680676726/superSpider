import { describe, expect, it } from "vitest";

import {
  inferWritebackTargetsFromFocus,
  normalizeWritebackTargetsFromThreadMeta,
  presentSessionKindLabel,
  resolveChatUiKey,
  resolveChatUiVisibility,
} from "./chatRuntimePresentation";

describe("chatRuntimePresentation", () => {
  it("normalizes writeback targets from thread meta and keeps strategy first", () => {
    expect(
      normalizeWritebackTargetsFromThreadMeta({
        chat_writeback_targets: ["backlog", "lane", "backlog"],
        chat_writeback_classes: ["immediate_goal", "lane"],
      }),
    ).toEqual(["strategy", "backlog", "lane", "immediate-goal"]);
  });

  it("infers writeback targets from focus kind and session kind", () => {
    expect(
      inferWritebackTargetsFromFocus({
        sessionKind: "industry-control-thread",
        focusKind: "backlog-item",
      }),
    ).toEqual(["strategy", "backlog"]);
    expect(
      inferWritebackTargetsFromFocus({
        sessionKind: "industry-control-thread",
        focusKind: "",
      }),
    ).toEqual(["strategy"]);
  });

  it("resolves chat ui key with thread/industry/agent precedence", () => {
    expect(
      resolveChatUiKey({
        requestedThreadId: "thread-1",
        activeIndustryId: "industry-1",
        activeIndustryRoleId: "execution-core",
        activeAgentId: "agent-1",
      }),
    ).toBe("thread-1");
    expect(
      resolveChatUiKey({
        requestedThreadId: null,
        activeIndustryId: "industry-1",
        activeIndustryRoleId: "execution-core",
        activeAgentId: "agent-1",
      }),
    ).toBe("industry:industry-1:execution-core");
  });

  it("keeps chat hidden while a directly bound thread is still pending without verified context", () => {
    expect(
      resolveChatUiVisibility({
        requestedThreadId: "thread-1",
        activeWindowThreadId: "thread-1",
        requestedThreadLooksBound: true,
        threadBootstrapError: null,
        hasBoundAgentContext: false,
        effectiveThreadPending: true,
        allowUnboundBuddyShell: false,
        disableComposer: false,
      }).shouldRenderChatUi,
    ).toBe(false);

    expect(
      resolveChatUiVisibility({
        requestedThreadId: "thread-1",
        activeWindowThreadId: "thread-1",
        requestedThreadLooksBound: true,
        threadBootstrapError: null,
        hasBoundAgentContext: true,
        effectiveThreadPending: false,
        allowUnboundBuddyShell: false,
        disableComposer: false,
      }).shouldRenderChatUi,
    ).toBe(true);
  });

  it("keeps chat hidden while pending if there is no direct bound thread and no verified context", () => {
    expect(
      resolveChatUiVisibility({
        requestedThreadId: "thread-1",
        activeWindowThreadId: "thread-1",
        requestedThreadLooksBound: false,
        threadBootstrapError: null,
        hasBoundAgentContext: false,
        effectiveThreadPending: true,
        allowUnboundBuddyShell: false,
        disableComposer: false,
      }).shouldRenderChatUi,
    ).toBe(false);
  });

  it("keeps chat visible while bootstrap refresh runs if verified bound context already exists", () => {
    const visibility = resolveChatUiVisibility({
      requestedThreadId: "industry-chat:industry-1:execution-core",
      activeWindowThreadId: "industry-chat:industry-1:execution-core",
      requestedThreadLooksBound: true,
      threadBootstrapError: null,
      hasBoundAgentContext: true,
      effectiveThreadPending: true,
      allowUnboundBuddyShell: false,
      disableComposer: false,
    });

    expect(visibility.shouldRenderChatUi).toBe(true);
    expect(visibility.shouldRenderChatComposer).toBe(true);
  });

  it("keeps the buddy naming shell visible without unlocking the live composer", () => {
    const visibility = resolveChatUiVisibility({
      requestedThreadId: null,
      activeWindowThreadId: null,
      requestedThreadLooksBound: false,
      threadBootstrapError: null,
      hasBoundAgentContext: false,
      effectiveThreadPending: false,
      allowUnboundBuddyShell: true,
      disableComposer: false,
    });

    expect(visibility.shouldRenderChatUi).toBe(true);
    expect(visibility.shouldRenderChatComposer).toBe(false);
  });

  it("keeps the naming gate visible on a bound thread while the live composer stays locked", () => {
    const visibility = resolveChatUiVisibility({
      requestedThreadId: "industry-chat:buddy:profile-1:execution-core",
      activeWindowThreadId: "industry-chat:buddy:profile-1:execution-core",
      requestedThreadLooksBound: true,
      threadBootstrapError: null,
      hasBoundAgentContext: true,
      effectiveThreadPending: false,
      allowUnboundBuddyShell: true,
      disableComposer: true,
    });

    expect(visibility.shouldRenderChatUi).toBe(true);
    expect(visibility.shouldRenderChatComposer).toBe(false);
  });

  it("presents human-facing session kind labels instead of thread jargon", () => {
    expect(presentSessionKindLabel("industry-control-thread")).toBe("主脑协作");
    expect(presentSessionKindLabel("industry-agent-chat")).toBe("执行协作");
    expect(presentSessionKindLabel("agent-chat")).toBe("智能体协作");
  });
});
