// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChatRuntimeSidebar } from "./ChatRuntimeSidebar";
import styles from "./index.module.less";

describe("ChatRuntimeSidebar", () => {
  it("keeps chat chrome minimal: binding label, approvals, and status rail only", () => {
    render(
      <ChatRuntimeSidebar
        approvalButtonLabel="审批(2)"
        bindingLabel="Acme / 主脑"
        onOpenGovernanceApprovals={vi.fn()}
        runtimeFallbackLabel={null}
        runtimeHealthNotice={null}
        runtimeModelHint="当前模型"
        runtimeModelLabel="openai/gpt-5"
        runtimeWaitDescription={null}
        runtimeWaitSeconds={0}
        runtimeWaitState={null}
      />,
    );

    expect(screen.getByText("Acme / 主脑")).toBeTruthy();
    expect(screen.getByText("审批(2)")).toBeTruthy();
    expect(screen.getByText("openai/gpt-5")).toBeTruthy();
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
        runtimeWaitDescription={null}
        runtimeWaitSeconds={0}
        runtimeWaitState={null}
      />,
    );

    expect(container.firstElementChild).toHaveClass(styles.topBar);
    expect(
      screen.getByTitle(
        "这是一个非常长的绑定标签，用来验证顶部状态条是否会省略显示并保留完整标题",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByTitle("openai/gpt-5.4-super-long-model-name-for-overflow-check"),
    ).toBeInTheDocument();
  });
});
