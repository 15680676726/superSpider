// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChatAccessGate } from "./ChatAccessGate";

describe("ChatAccessGate", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders a single identity path for binding notice", () => {
    const onOpenIdentityCenter = vi.fn();

    render(
      <ChatAccessGate
        chatNoticeVariant="binding"
        threadBootstrapError={null}
        autoBindingPending={false}
        requestedThreadId={null}
        industryTeamsError={null}
        hasSuggestedTeams={false}
        effectiveThreadPending={false}
        showModelPrompt={false}
        onCloseModelPrompt={vi.fn()}
        onOpenModelSettings={vi.fn()}
        onOpenIdentityCenter={onOpenIdentityCenter}
        onReload={vi.fn()}
      />,
    );

    expect(screen.getByText("正在准备聊天通道")).toBeInTheDocument();
    expect(screen.getByText("完成身份确认后即可继续使用，系统已在后台接续。")).toBeInTheDocument();

    const identityButton = screen.getByRole("button", { name: "前往身份中心" });
    fireEvent.click(identityButton);
    expect(onOpenIdentityCenter).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("shows a loading spinner before chat is ready", () => {
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
    expect(screen.getByText("正在进入聊天，请稍候")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("shows the model prompt using Chinese copy", () => {
    const onCloseModelPrompt = vi.fn();
    const onOpenModelSettings = vi.fn();

    render(
      <ChatAccessGate
        chatNoticeVariant={null}
        threadBootstrapError={null}
        autoBindingPending={false}
        requestedThreadId={null}
        industryTeamsError={null}
        hasSuggestedTeams={false}
        effectiveThreadPending={false}
        showModelPrompt={true}
        onCloseModelPrompt={onCloseModelPrompt}
        onOpenModelSettings={onOpenModelSettings}
        onOpenIdentityCenter={vi.fn()}
        onReload={vi.fn()}
      />,
    );

    expect(screen.getByText("请先完成模型配置")).toBeInTheDocument();
    expect(screen.getByText("确认模型设置后才能继续使用聊天。")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "稍后再说" }));
    expect(onCloseModelPrompt).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: /去模型设置/ }));
    expect(onOpenModelSettings).toHaveBeenCalledTimes(1);
  });

  it("offers reload first when a bound chat thread fails to recover", () => {
    const onReload = vi.fn();
    const onOpenIdentityCenter = vi.fn();

    render(
      <ChatAccessGate
        chatNoticeVariant="binding"
        threadBootstrapError="session missing"
        autoBindingPending={false}
        requestedThreadId="industry-chat:industry-1:execution-core"
        industryTeamsError={null}
        hasSuggestedTeams={false}
        effectiveThreadPending={false}
        showModelPrompt={false}
        onCloseModelPrompt={vi.fn()}
        onOpenModelSettings={vi.fn()}
        onOpenIdentityCenter={onOpenIdentityCenter}
        onReload={onReload}
      />,
    );

    expect(screen.getByText("这段聊天暂时打不开")).toBeInTheDocument();
    expect(
      screen.getByText("先重新加载这段聊天；如果还是不行，再回到建档入口。"),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "重新加载" }));
    expect(onReload).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "前往身份中心" }));
    expect(onOpenIdentityCenter).toHaveBeenCalledTimes(1);
  });
});
