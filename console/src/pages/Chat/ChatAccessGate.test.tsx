// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChatAccessGate } from "./ChatAccessGate";

describe("ChatAccessGate", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders the binding notice with buddy-first wording and only exposes identity-first shortcuts", async () => {
    const onOpenIdentityCenter = vi.fn();
    const onReload = vi.fn();

    render(
      <ChatAccessGate
        chatNoticeVariant="binding"
        threadBootstrapError={null}
        autoBindingPending={true}
        requestedThreadId={null}
        industryTeamsError={null}
        hasSuggestedTeams={true}
        effectiveThreadPending={false}
        showModelPrompt={true}
        onCloseModelPrompt={vi.fn()}
        onOpenModelSettings={vi.fn()}
        onOpenIdentityCenter={onOpenIdentityCenter}
        onReload={onReload}
      />,
    );

    expect(screen.getByText("正在接入伙伴主场")).toBeInTheDocument();
    expect(screen.getByText("打开身份中心")).toBeTruthy();
    expect(screen.queryByText(/线程/)).toBeNull();
    expect(screen.queryByRole("button", { name: "智能体工作台" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "打开身份中心" }));

    expect(onOpenIdentityCenter).toHaveBeenCalledTimes(1);
    expect(onReload).not.toHaveBeenCalled();
  });

  it("renders the loading notice without showing the gate modal when closed", () => {
    const { container } = render(
      <ChatAccessGate
        chatNoticeVariant="loading"
        threadBootstrapError={null}
        autoBindingPending={false}
        requestedThreadId={null}
        industryTeamsError={null}
        hasSuggestedTeams={false}
        effectiveThreadPending={true}
        showModelPrompt={false}
        onCloseModelPrompt={vi.fn()}
        onOpenModelSettings={vi.fn()}
        onOpenIdentityCenter={vi.fn()}
        onReload={vi.fn()}
      />,
    );

    expect(container.querySelector(".ant-spin")).not.toBeNull();
    expect(screen.getByText("正在进入伙伴对话...")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
