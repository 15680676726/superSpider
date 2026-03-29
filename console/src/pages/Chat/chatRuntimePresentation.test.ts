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

  it("keeps chat hidden while pending and visible when bound context is ready", () => {
    expect(
      resolveChatUiVisibility({
        requestedThreadId: "thread-1",
        activeWindowThreadId: "thread-1",
        requestedThreadLooksBound: true,
        threadBootstrapError: null,
        hasBoundAgentContext: true,
        effectiveThreadPending: true,
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
      }).shouldRenderChatUi,
    ).toBe(true);
  });

  it("presents canonical session kind labels", () => {
    expect(presentSessionKindLabel("industry-control-thread")).toBe(
      "control-thread",
    );
    expect(presentSessionKindLabel("industry-agent-chat")).toBe(
      "execution-thread",
    );
    expect(presentSessionKindLabel("agent-chat")).toBe("agent-thread");
  });
});
