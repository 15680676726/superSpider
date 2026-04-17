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
        timestamp: "2026-04-16 09:00:00",
        level: "info",
        message: "派出任务：整理交付证据",
      },
      {
        timestamp: "2026-04-16 09:10:00",
        level: "warn",
        message: "等待决定：是否现在发给用户",
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

  it("shows waiting-login when baidu research needs user login", () => {
    const props = {
      ...createProps(),
      researchSummary: {
        id: "research-session-1",
        status: "waiting-login",
        statusLabel: "待登录百度",
        goal: "研究百度搜索里的行业竞品动态",
        roundCount: 1,
        roundLabel: "第 1 轮",
        waitingLogin: true,
        latestStatus: "等待你先登录百度，研究才能继续。",
      },
    } as unknown as MainBrainCockpitPanelProps;

    render(<MainBrainCockpitPanel {...props} />);

    expect(screen.getByText("待登录百度")).toBeInTheDocument();
    expect(screen.getByText("当前研究目标")).toBeInTheDocument();
  });

  it("shows current research goal and round progress for researcher", () => {
    const props = {
      ...createProps(),
      researchSummary: {
        id: "research-session-2",
        status: "running",
        statusLabel: "当前研究中",
        goal: "研究飞书与多维表格相关竞品能力",
        roundCount: 2,
        roundLabel: "第 2 轮",
        waitingLogin: false,
        latestStatus: "正在整理第二轮抓到的页面线索。",
        brief: {
          goal: "研究飞书与多维表格相关竞品能力",
          question: "最近有哪些官网能力更新值得主脑跟进？",
          whyNeeded: "主脑要决定本周产品定位说明。",
          doneWhen: "拿到能力变化、来源和剩余缺口。",
          requestedSources: ["search", "web_page"],
          scopeType: "work_context",
          scopeId: "ctx-research-1",
        },
        findings: [
          {
            id: "finding-1",
            summary: "官网能力页新增了自动化编排和模板市场描述。",
            findingType: "capability",
          },
        ],
        sources: [
          {
            id: "source-1",
            title: "官网能力页",
            sourceKind: "web_page",
            sourceRef: "https://example.com/capabilities",
            snippet: "自动化编排与模板市场",
          },
        ],
        gaps: ["还缺一条官方案例证据。"],
        conflicts: ["第三方解读还在引用旧版本页面。"],
        writebackTruth: {
          status: "written",
          statusLabel: "已回写正式真相",
          scopeType: "work_context",
          scopeId: "ctx-research-1",
          reportId: "report-1",
        },
      },
    } as unknown as MainBrainCockpitPanelProps;

    render(<MainBrainCockpitPanel {...props} />);

    expect(screen.getByText("当前研究目标")).toBeInTheDocument();
    expect(screen.getByText("研究飞书与多维表格相关竞品能力")).toBeInTheDocument();
    expect(screen.getByText("第 2 轮")).toBeInTheDocument();
    expect(screen.getByText("最近状态")).toBeInTheDocument();
    expect(screen.getByText("研究简报")).toBeInTheDocument();
    expect(screen.getByText("最近有哪些官网能力更新值得主脑跟进？")).toBeInTheDocument();
    expect(screen.getByText("核心发现")).toBeInTheDocument();
    expect(
      screen.getByText("官网能力页新增了自动化编排和模板市场描述。"),
    ).toBeInTheDocument();
    expect(screen.getByText("来源")).toBeInTheDocument();
    expect(screen.getByText("官网能力页")).toBeInTheDocument();
    expect(screen.getByText("缺口")).toBeInTheDocument();
    expect(screen.getByText("还缺一条官方案例证据。")).toBeInTheDocument();
    expect(screen.getByText("冲突")).toBeInTheDocument();
    expect(screen.getByText("第三方解读还在引用旧版本页面。")).toBeInTheDocument();
    expect(screen.getByText("回写真相")).toBeInTheDocument();
    expect(screen.getByText("已回写正式真相")).toBeInTheDocument();
  });

  it("renders trace lines inside the trace tab", () => {
    render(<MainBrainCockpitPanel {...createProps()} />);

    fireEvent.click(screen.getByRole("tab", { name: "追溯" }));

    expect(screen.getByText("2026-04-16 09:00:00")).toBeInTheDocument();
    expect(screen.getByText("派出任务：整理交付证据")).toBeInTheDocument();
    expect(screen.getByText("等待决定：是否现在发给用户")).toBeInTheDocument();
  });
});
