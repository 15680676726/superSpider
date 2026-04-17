// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import MainBrainCockpitPanel, { type MainBrainCockpitPanelProps } from "./MainBrainCockpitPanel";

function createProps(): MainBrainCockpitPanelProps {
  return {
    title: "伙伴（主脑）",
    summaryFields: [
      { label: "职责", value: "统筹安排、盯进度、收结果。" },
      { label: "当前重点", value: "先处理待确认事项。" },
    ],
    morningReport: {
      title: "早报",
      items: ["今天先收口待确认事项。", "先看运营位回传。", "注意今天还有一个确认项。"],
    },
    eveningReport: {
      title: "晚报",
      items: ["今天已收回 1 份汇报。", "新增 2 条证据。", "明天继续推进交付说明。"],
    },
    trend: [
      { label: "周一", completed: 1, completionRate: 80, quality: 78 },
      { label: "周二", completed: 2, completionRate: 90, quality: 84 },
    ],
    trace: [
      {
        timestamp: "2026-04-16T09:20:00Z",
        level: "warn",
        message: "需要你决定：是否现在发送给用户",
        route: "/runtime-center/decisions/decision-1",
      },
    ],
    approvals: [
      {
        id: "decision-1",
        kind: "decision",
        title: "是否现在发给用户",
        reason: "运营位已经整理完主体内容，差最后确认。",
        recommendation: "建议现在确认并发送。",
        risk: "如果继续拖延，今天的交付会往后顺延。",
        initiator: "主脑",
        createdAt: "2026-04-12 16:30",
      },
    ],
    stageSummary: null,
    dayMode: "day",
    systemManagement: <div>自动化管理区</div>,
    onApproveApproval: vi.fn(),
    onRejectApproval: vi.fn(),
    onOpenChat: vi.fn(),
  };
}

describe("MainBrainCockpitPanel", () => {
  it("renders main brain tabs and shows approvals in a dedicated tab", () => {
    render(<MainBrainCockpitPanel {...createProps()} />);

    expect(screen.getByRole("tab", { name: "简介" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "日报" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "统计" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "追溯" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "阶段总结" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "审批" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "系统管理" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "审批" }));

    expect(screen.getByText("是否现在发给用户")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "同意" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "拒绝" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "去聊天处理" })).toBeInTheDocument();
  });

  it("shows system management content only inside the dedicated tab", () => {
    render(<MainBrainCockpitPanel {...createProps()} />);

    expect(screen.queryByText("自动化管理区")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "系统管理" }));

    expect(screen.getByText("自动化管理区")).toBeInTheDocument();
  });

  it("shows a dedicated trace tab for main brain trace lines", () => {
    render(<MainBrainCockpitPanel {...createProps()} />);

    fireEvent.click(screen.getByRole("tab", { name: "追溯" }));

    expect(screen.getByText("需要你决定：是否现在发送给用户")).toBeInTheDocument();
  });
});
