// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChatRuntimeSidebar } from "./ChatRuntimeSidebar";
import styles from "./index.module.less";

type ChatRuntimeSidebarProps = Parameters<typeof ChatRuntimeSidebar>[0];
type RuntimeLifecycleState = NonNullable<ChatRuntimeSidebarProps["runtimeLifecycleState"]>;

describe("ChatRuntimeSidebar", () => {
  it("keeps chat chrome minimal while surfacing thread kind, focus, writeback, and shell mode", () => {
    render(
      <ChatRuntimeSidebar
        approvalButtonLabel={"\u5ba1\u6279(2)"}
        bindingLabel={"Acme / \u4e3b\u8111"}
        onOpenGovernanceApprovals={vi.fn()}
        runtimeFallbackLabel={null}
        runtimeHealthNotice={null}
        runtimeModelHint={"\u5f53\u524d\u6a21\u578b"}
        runtimeModelLabel="openai/gpt-5"
        runtimeIntentShell={{
          mode: "plan",
          label: "PLAN",
          summary: "这次回复使用精简计划模式。",
          hint: null,
          triggerSource: "keyword",
          matchedText: "\u8ba1\u5212",
          confidence: 0.95,
          triggerSourceLabel: "\u6765\u6e90\uff1a\u5173\u952e\u8bcd\u547d\u4e2d",
          matchedTextLabel: "\u547d\u4e2d\uff1a\u8ba1\u5212",
          confidenceLabel: "\u7f6e\u4fe1\u5ea6 95%",
          metaSummary:
            "\u6765\u6e90\uff1a\u5173\u952e\u8bcd\u547d\u4e2d \u00b7 \u547d\u4e2d\uff1a\u8ba1\u5212 \u00b7 \u7f6e\u4fe1\u5ea6 95%",
          updatedAt: 500,
          payload: {
            mode_hint: "plan",
          },
        }}
        threadKindLabel="Thread: control-thread"
        threadKindHint="session_kind=industry-control-thread"
        focusLabel="Focus: Launch runtime center"
        focusHint="kind=goal | id=goal-1"
        writebackLabel="Writeback: strategy/backlog"
        writebackHint="targets=strategy,backlog"
        runtimeWaitDescription={null}
        runtimeWaitSeconds={0}
        runtimeWaitState={null}
      />,
    );

    expect(screen.getByText("Acme / \u4e3b\u8111")).toBeTruthy();
    expect(screen.getByText("\u5ba1\u6279(2)")).toBeTruthy();
    expect(screen.getByText("openai/gpt-5")).toBeTruthy();
    expect(screen.getByText("Shell: PLAN")).toBeTruthy();
    expect(screen.getByText("Thread: control-thread")).toBeTruthy();
    expect(screen.getByText("Focus: Launch runtime center")).toBeTruthy();
    expect(screen.getByText("Writeback: strategy/backlog")).toBeTruthy();
    expect(screen.queryByTitle(/trigger=/)).toBeNull();
    expect(screen.queryByText("Capability card")).toBeNull();
    expect(screen.queryByText("Open workbench")).toBeNull();
  });

  it("uses the formal top bar style classes and exposes full text on hover", () => {
    const { container } = render(
      <ChatRuntimeSidebar
        approvalButtonLabel={"\u5ba1\u6279"}
        bindingLabel={
          "\u8fd9\u662f\u4e00\u4e2a\u975e\u5e38\u957f\u7684\u7ed1\u5b9a\u6807\u7b7e\uff0c\u7528\u6765\u9a8c\u8bc1\u9876\u90e8\u72b6\u6001\u6761\u662f\u5426\u4f1a\u7701\u7565\u663e\u793a\u5e76\u4fdd\u7559\u5b8c\u6574\u6807\u9898"
        }
        onOpenGovernanceApprovals={vi.fn()}
        runtimeFallbackLabel={"\u56de\u9000\u94fe\u8def"}
        runtimeHealthNotice={null}
        runtimeModelHint={"\u5f53\u524d\u6a21\u578b\u8bf4\u660e"}
        runtimeModelLabel="openai/gpt-5.4-super-long-model-name-for-overflow-check"
        runtimeIntentShell={{
          mode: "review",
          label: "REVIEW",
          summary: "这次回复使用聚焦审查模式。",
          hint: null,
          triggerSource: "keyword",
          matchedText: null,
          confidence: null,
          triggerSourceLabel: "\u6765\u6e90\uff1a\u5173\u952e\u8bcd\u547d\u4e2d",
          matchedTextLabel: null,
          confidenceLabel: null,
          metaSummary: "\u6765\u6e90\uff1a\u5173\u952e\u8bcd\u547d\u4e2d",
          updatedAt: 501,
          payload: {
            mode_hint: "review",
          },
        }}
        threadKindLabel="Thread: control-thread"
        threadKindHint="session_kind=industry-control-thread | thread_binding_kind=control | owner_scope=operator"
        focusLabel="Focus: This is a super long focus label to check truncation and title preservation"
        focusHint="kind=backlog | id=backlog-123"
        writebackLabel="Writeback: strategy/lane/backlog/immediate-goal"
        writebackHint="targets=strategy,lane,backlog,immediate-goal | role=execution-core | match_signals=2"
        runtimeWaitDescription={null}
        runtimeWaitSeconds={0}
        runtimeWaitState={null}
      />,
    );

    expect(container.firstElementChild?.className).toContain(styles.topBar);
    expect(
      screen.getByTitle(
        "\u8fd9\u662f\u4e00\u4e2a\u975e\u5e38\u957f\u7684\u7ed1\u5b9a\u6807\u7b7e\uff0c\u7528\u6765\u9a8c\u8bc1\u9876\u90e8\u72b6\u6001\u6761\u662f\u5426\u4f1a\u7701\u7565\u663e\u793a\u5e76\u4fdd\u7559\u5b8c\u6574\u6807\u9898",
      ),
    ).toBeTruthy();
    expect(
      screen.getByTitle("openai/gpt-5.4-super-long-model-name-for-overflow-check"),
    ).toBeTruthy();
    expect(
      screen.getByTitle(
        "这次回复使用聚焦审查模式。 \u00b7 \u6765\u6e90\uff1a\u5173\u952e\u8bcd\u547d\u4e2d",
      ),
    ).toBeTruthy();
    expect(screen.queryByTitle(/trigger=/)).toBeNull();
    expect(
      screen.getByTitle(
        "session_kind=industry-control-thread | thread_binding_kind=control | owner_scope=operator",
      ),
    ).toBeTruthy();
    expect(screen.getByTitle("kind=backlog | id=backlog-123")).toBeTruthy();
    expect(
      screen.getByTitle(
        "targets=strategy,lane,backlog,immediate-goal | role=execution-core | match_signals=2",
      ),
    ).toBeTruthy();
  });

  it("renders lifecycle failure state instead of collapsing back to ready", () => {
    const baseProps: ChatRuntimeSidebarProps = {
      approvalButtonLabel: "\u5ba1\u6279",
      bindingLabel: "Acme / main-brain",
      onOpenGovernanceApprovals: vi.fn(),
      runtimeFallbackLabel: null,
      runtimeHealthNotice: null,
      runtimeModelHint: "current model",
      runtimeModelLabel: "openai/gpt-5",
      runtimeWaitDescription: null,
      runtimeWaitSeconds: 0,
      runtimeWaitState: null,
    };
    const acceptedState: RuntimeLifecycleState = {
      phase: "accepted",
      title: "\u5df2\u63a5\u6536",
      description: "accepted boundary persisted",
      tone: "busy",
      updatedAt: 100,
    };
    const replyDoneState: RuntimeLifecycleState = {
      phase: "reply_done",
      title: "\u56de\u590d\u5b8c\u6210",
      description: "reply complete",
      tone: "busy",
      updatedAt: 101,
    };
    const commitFailedState: RuntimeLifecycleState = {
      phase: "commit_failed",
      title: "\u63d0\u4ea4\u5931\u8d25",
      description: "db commit blew up",
      tone: "error",
      updatedAt: 102,
    };
    const deferredState: RuntimeLifecycleState = {
      phase: "commit_deferred",
      title: "待补位",
      description: "Execution was recorded and is waiting for staffing or routing resolution.",
      tone: "warning",
      updatedAt: 103,
    };

    const { rerender } = render(
      <ChatRuntimeSidebar
        {...baseProps}
        runtimeLifecycleState={acceptedState}
      />,
    );

    expect(screen.getByText("\u5df2\u63a5\u6536")).toBeTruthy();
    expect(screen.queryByText("\u5c31\u7eea")).toBeNull();

    rerender(
      <ChatRuntimeSidebar
        {...baseProps}
        runtimeLifecycleState={replyDoneState}
      />,
    );

    expect(screen.getByText("\u56de\u590d\u5b8c\u6210")).toBeTruthy();
    expect(screen.queryByText("\u5c31\u7eea")).toBeNull();

    rerender(
      <ChatRuntimeSidebar
        {...baseProps}
        runtimeLifecycleState={commitFailedState}
      />,
    );

    expect(screen.getByText("\u63d0\u4ea4\u5931\u8d25")).toBeTruthy();
    expect(screen.queryByText("\u5c31\u7eea")).toBeNull();

    rerender(
      <ChatRuntimeSidebar
        {...baseProps}
        runtimeLifecycleState={deferredState}
      />,
    );

    expect(screen.getByText("待补位")).toBeTruthy();
    expect(screen.queryByText("\u5c31\u7eea")).toBeNull();
  });
});
