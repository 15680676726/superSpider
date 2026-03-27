// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChatRuntimeSidebar } from "./ChatRuntimeSidebar";

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
});
