// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChatRuntimeSidebar } from "./ChatRuntimeSidebar";
import styles from "./index.module.less";

describe("ChatRuntimeSidebar", () => {
  it("keeps chat chrome minimal while surfacing thread kind, focus, and writeback", () => {
    render(
      <ChatRuntimeSidebar
        approvalButtonLabel="审批(2)"
        bindingLabel="Acme / 主脑"
        onOpenGovernanceApprovals={vi.fn()}
        runtimeFallbackLabel={null}
        runtimeHealthNotice={null}
        runtimeModelHint="当前模型"
        runtimeModelLabel="openai/gpt-5"
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

    expect(screen.getByText("Acme / 主脑")).toBeTruthy();
    expect(screen.getByText("审批(2)")).toBeTruthy();
    expect(screen.getByText("openai/gpt-5")).toBeTruthy();
    expect(screen.getByText("Thread: control-thread")).toBeTruthy();
    expect(screen.getByText("Focus: Launch runtime center")).toBeTruthy();
    expect(screen.getByText("Writeback: strategy/backlog")).toBeTruthy();
    expect(screen.queryByText("Capability card")).toBeNull();
    expect(screen.queryByText("Open workbench")).toBeNull();
  });

  it("uses the formal top bar style classes and exposes full text on hover", () => {
    const { container } = render(
      <ChatRuntimeSidebar
        approvalButtonLabel="审批"
        bindingLabel="这是一个非常长的绑定标签，用来验证顶部状态条是否会省略显示并保留完整标题"
        onOpenGovernanceApprovals={vi.fn()}
        runtimeFallbackLabel="回退链路"
        runtimeHealthNotice={null}
        runtimeModelHint="当前模型说明"
        runtimeModelLabel="openai/gpt-5.4-super-long-model-name-for-overflow-check"
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
        "这是一个非常长的绑定标签，用来验证顶部状态条是否会省略显示并保留完整标题",
      ),
    ).toBeTruthy();
    expect(
      screen.getByTitle("openai/gpt-5.4-super-long-model-name-for-overflow-check"),
    ).toBeTruthy();
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
});
