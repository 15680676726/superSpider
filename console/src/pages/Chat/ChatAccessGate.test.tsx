// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { IndustryInstanceSummary } from "../../api/modules/industry";
import { ChatAccessGate } from "./ChatAccessGate";

const suggestedInstance: IndustryInstanceSummary = {
  instance_id: "industry-1",
  label: "Northwind Robotics",
  summary: "Inspection orchestration",
  owner_scope: "industry",
  bootstrap_kind: "industry-v1",
  profile: {
    schema_version: "industry-profile-v1",
    industry: "manufacturing",
    target_customers: [],
    channels: [],
    goals: [],
    constraints: [],
    experience_mode: "system-led",
    operator_requirements: [],
  },
  team: {
    schema_version: "industry-team-blueprint-v1",
    team_id: "team-1",
    label: "Robotics Team",
    summary: "Handles inspection",
    agents: [],
  },
  execution_core_identity: null,
  strategy_memory: null,
  status: "active",
  updated_at: null,
  stats: { total_goals: 0 },
  routes: {},
};

describe("ChatAccessGate", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders the binding notice and action shortcuts", async () => {
    const onOpenIndustryCenter = vi.fn();
    const onOpenWorkbench = vi.fn();
    const onReload = vi.fn();
    const onOpenSuggestedIndustryChat = vi.fn().mockResolvedValue(true);

    render(
      <ChatAccessGate
        chatNoticeVariant="binding"
        threadBootstrapError={null}
        autoBindingPending={true}
        requestedThreadId={null}
        industryTeamsError={null}
        hasSuggestedTeams={true}
        executionCoreSuggestions={[suggestedInstance]}
        effectiveThreadPending={false}
        showModelPrompt={true}
        onCloseModelPrompt={vi.fn()}
        onOpenModelSettings={vi.fn()}
        onOpenIndustryCenter={onOpenIndustryCenter}
        onOpenWorkbench={onOpenWorkbench}
        onReload={onReload}
        onOpenSuggestedIndustryChat={onOpenSuggestedIndustryChat}
      />,
    );

    expect(screen.getByText("正在绑定主脑控制线程")).toBeTruthy();
    expect(screen.getByRole("button", { name: "打开身份中心" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "智能体工作台" })).toBeTruthy();
    expect(screen.getByText("需要配置对话模型")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "打开身份中心" }));
    fireEvent.click(screen.getByRole("button", { name: "智能体工作台" }));

    expect(onOpenIndustryCenter).toHaveBeenCalledTimes(1);
    expect(onOpenWorkbench).toHaveBeenCalledTimes(1);
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
        executionCoreSuggestions={[]}
        effectiveThreadPending={true}
        showModelPrompt={false}
        onCloseModelPrompt={vi.fn()}
        onOpenModelSettings={vi.fn()}
        onOpenIndustryCenter={vi.fn()}
        onOpenWorkbench={vi.fn()}
        onReload={vi.fn()}
        onOpenSuggestedIndustryChat={vi.fn()}
      />,
    );

    expect(container.querySelector(".ant-spin")).not.toBeNull();
    expect(screen.queryByText("需要配置对话模型")).toBeNull();
  });
});
