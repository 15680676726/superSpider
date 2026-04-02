// @vitest-environment jsdom

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type {
  RuntimeCenterSurfaceInfo,
  RuntimeMainBrainResponse,
} from "../../api/modules/runtimeCenter";
import type { RuntimeCenterOverviewPayload } from "./useRuntimeCenter";
import MainBrainCockpitPanel from "./MainBrainCockpitPanel";

const surface: RuntimeCenterSurfaceInfo = {
  version: "runtime-center-v1",
  mode: "operator-surface",
  status: "state-service",
  read_only: false,
  source: "overseen",
  note: "Overview note",
};

const overviewPayload: RuntimeCenterOverviewPayload = {
  generated_at: "2026-03-29T09:00:00Z",
  surface,
  cards: [],
};

const dedicatedPayload: RuntimeMainBrainResponse = {
  generated_at: "2026-03-29T09:05:00Z",
  surface,
  strategy: {},
  carrier: {},
  lanes: [],
  cycles: [],
  backlog: [],
  current_cycle: {
    title: "Cycle 99",
    next_cycle_due_at: "2026-03-31T23:59:59Z",
    focus_count: 4,
  },
  assignments: [],
  reports: [],
  report_cognition: {},
  environment: {},
  governance: {},
  recovery: {},
  automation: {},
  evidence: { count: 0, summary: "", route: null, entries: [], meta: {} },
  decisions: { count: 0, summary: "", route: null, entries: [], meta: {} },
  patches: { count: 0, summary: "", route: null, entries: [], meta: {} },
  signals: {
    carrier: {
      key: "carrier",
      value: "Dedicated carrier value",
      detail: "Carrier detail from payload",
      route: "/api/runtime-center/carrier",
    },
    strategy: {
      key: "strategy",
      value: "Dedicated strategy",
    },
  },
  meta: { control_chain: [] },
};

const unifiedPayload = {
  generated_at: "2026-03-29T09:05:00Z",
  surface,
  strategy: {
    title: "Northwind field operations strategy",
    summary: "Keep the staffed handoff loop stable and evidence-backed.",
    route: "/api/runtime-center/strategy-memory?industry_instance_id=industry-v1-ops",
  },
  carrier: {
    industry_instance_id: "industry-v1-ops",
    label: "Northwind Ops",
    route: "/api/runtime-center/industry/industry-v1-ops",
  },
  lanes: [
    { lane_id: "lane-ops", title: "Operations lane", status: "active" },
    { lane_id: "lane-risk", title: "Risk lane", status: "queued" },
  ],
  cycles: [
    {
      cycle_id: "cycle-8",
      title: "Cycle 8",
      status: "completed",
      route: "/api/runtime-center/industry/industry-v1-ops",
    },
    {
      cycle_id: "cycle-9",
      title: "Cycle 9",
      status: "active",
      route: "/api/runtime-center/industry/industry-v1-ops",
    },
  ],
  backlog: [
    {
      backlog_item_id: "backlog-followup-1",
      title: "Resolve handoff return evidence gap",
      summary: "Dispatch a governed browser follow-up on the same control thread.",
      route: "/api/runtime-center/industry/industry-v1-ops?backlog_item_id=backlog-followup-1",
      status: "open",
    },
  ],
  current_cycle: {
    cycle_id: "cycle-9",
    title: "Cycle 9",
    status: "active",
    focus_count: 2,
    next_cycle_due_at: "2026-03-31T23:59:59Z",
  },
  assignments: [
    {
      assignment_id: "assignment-1",
      title: "Review handoff blockers",
      status: "active",
      route: "/api/runtime-center/industry/industry-v1-ops",
    },
  ],
  reports: [
    {
      report_id: "report-1",
      headline: "Need supervisor decision",
      summary: "Operator must compare the evidence gap before dispatching the next cycle.",
      status: "recorded",
      needs_followup: true,
      report_consumed: false,
      route: "/api/runtime-center/industry/industry-v1-ops",
    },
  ],
  report_cognition: {
    needs_replan: true,
    replan_reasons: [
      "Reports disagree on whether the handoff is cleared.",
      "Supervisor review is still missing for the handoff return.",
    ],
    judgment: {
      status: "attention",
      summary: "Main brain must compare unresolved reports and decide whether to dispatch follow-up work.",
      route: "/api/runtime-center/industry/industry-v1-ops",
    },
    next_action: {
      kind: "followup-backlog",
      title: "Resolve handoff return evidence gap",
      summary: "Dispatch a governed browser follow-up on the same control thread.",
      route: "/api/runtime-center/industry/industry-v1-ops?backlog_item_id=backlog-followup-1",
    },
    latest_findings: [
      {
        report_id: "report-1",
        title: "Delivery blocker needs supervisor review",
        summary: "Operator must compare the evidence gap before dispatching the next cycle.",
        route: "/api/runtime-center/industry/industry-v1-ops?report_id=report-1",
        needs_followup: true,
        report_consumed: false,
      },
    ],
    conflicts: [
      {
        conflict_id: "result-mismatch:report-1",
        title: "Report conflict",
        summary: "Reports disagree on whether the handoff is cleared.",
        route: "/api/runtime-center/industry/industry-v1-ops",
      },
    ],
    holes: [
      {
        hole_id: "followup-needed:report-1",
        title: "Follow-up gap",
        summary: "Supervisor review is still missing for the handoff return.",
        route: "/api/runtime-center/industry/industry-v1-ops?report_id=report-1",
      },
    ],
    followup_backlog: [
      {
        backlog_item_id: "backlog-followup-1",
        title: "Resolve handoff return evidence gap",
        summary: "Dispatch a governed browser follow-up on the same control thread.",
        route: "/api/runtime-center/industry/industry-v1-ops?backlog_item_id=backlog-followup-1",
      },
    ],
    unconsumed_reports: [
      {
        report_id: "report-1",
        title: "Need supervisor decision",
        summary: "Operator must compare the evidence gap before dispatching the next cycle.",
        route: "/api/runtime-center/industry/industry-v1-ops?report_id=report-1",
        report_consumed: false,
      },
    ],
    needs_followup_reports: [
      {
        report_id: "report-1",
        title: "Need supervisor decision",
        summary: "Operator must compare the evidence gap before dispatching the next cycle.",
        route: "/api/runtime-center/industry/industry-v1-ops?report_id=report-1",
        needs_followup: true,
      },
    ],
  },
  environment: {
    route: "/api/runtime-center/governance/status",
    summary: "Host twin ready on seat-b with multi-surface continuity.",
    host_twin_summary: {
      selected_seat_ref: "env:desktop:seat-b",
      recommended_scheduler_action: "proceed",
      continuity_state: "ready",
      active_app_family_keys: ["browser_backoffice", "office_document"],
    },
    handoff: {
      active: false,
    },
    staffing: {
      pending_confirmation_count: 1,
    },
    human_assist: {
      blocked_count: 2,
    },
  },
  governance: {
    route: "/api/runtime-center/governance/status",
    status: "blocked",
    summary: "Human handoff is active and runtime dispatch is gated.",
    pending_decisions: 1,
    pending_patches: 2,
  },
  recovery: {
    route: "/api/runtime-center/recovery/latest",
    available: true,
    status: "ready",
    summary: "Recovered expired decisions and runtime leases during startup.",
  },
  automation: {
    route: "/api/runtime-center/schedules",
    status: "active",
    summary: "2 schedule(s) visible; heartbeat success every 6h.",
    schedule_count: 2,
    active_schedule_count: 2,
    heartbeat: {
      route: "/api/runtime-center/heartbeat",
      status: "success",
      enabled: true,
      every: "6h",
    },
  },
  evidence: {
    count: 1,
    summary: "Evidence trace is ready.",
    route: "/api/runtime-center/evidence",
    entries: [
      {
        id: "evidence-1",
        title: "Checkpoint evidence",
        created_at: "2026-03-29T08:30:00Z",
      },
    ],
    meta: {},
  },
  decisions: {
    count: 1,
    summary: "One decision pending.",
    route: "/api/runtime-center/decisions",
    entries: [
      {
        id: "decision-1",
        title: "Approve host return",
        created_at: "2026-03-29T08:45:00Z",
      },
    ],
    meta: {},
  },
  patches: {
    count: 1,
    summary: "One patch pending.",
    route: "/api/runtime-center/learning/patches",
    entries: [
      {
        id: "patch-1",
        title: "Apply continuity patch",
        applied_at: "2026-03-29T09:00:00Z",
      },
    ],
    meta: {},
  },
  signals: {
    carrier: {
      key: "carrier",
      value: "Northwind Ops",
      route: "/api/runtime-center/industry/industry-v1-ops",
    },
    strategy: {
      key: "strategy",
      value: "Northwind field operations strategy",
    },
    governance: {
      key: "governance",
      count: 1,
      value: "blocked",
      detail: "Human handoff is active and runtime dispatch is gated.",
      route: "/api/runtime-center/governance/status",
    },
    automation: {
      key: "automation",
      count: 2,
      value: "active",
      detail: "2 schedule(s) visible; heartbeat success every 6h.",
      route: "/api/runtime-center/schedules",
    },
    recovery: {
      key: "recovery",
      count: 1,
      value: "ready",
      detail: "Recovered expired decisions and runtime leases during startup.",
      route: "/api/runtime-center/recovery/latest",
    },
    report_cognition: {
      key: "report_cognition",
      count: 4,
      value: "attention",
      detail: "Main brain must compare unresolved reports before dispatching more work.",
      route: "/api/runtime-center/industry/industry-v1-ops",
      status: "attention",
    },
  },
  meta: {
    report_cognition: undefined,
    control_chain: [
      { key: "carrier", value: "Northwind Ops" },
      { key: "strategy", value: "Northwind field operations strategy" },
      { key: "report_cognition", value: "attention" },
      { key: "governance", value: "blocked" },
      { key: "automation", value: "active" },
      { key: "recovery", value: "ready" },
    ],
  },
} as unknown as RuntimeMainBrainResponse;

function renderPanel(mainBrainData: RuntimeMainBrainResponse) {
  return render(
    <MainBrainCockpitPanel
      data={overviewPayload}
      loading={false}
      refreshing={false}
      error={null}
      mainBrainData={mainBrainData}
      mainBrainLoading={false}
      mainBrainError={null}
      mainBrainUnavailable={false}
      onRefresh={vi.fn()}
      onOpenRoute={vi.fn()}
    />,
  );
}

function findSectionBlock(title: string): HTMLElement {
  const heading = screen.getByRole("heading", { level: 3, name: title });
  return heading.parentElement?.parentElement?.parentElement?.parentElement as HTMLElement;
}

describe("MainBrainCockpitPanel", () => {
  it("renders dedicated payload signals when available", () => {
    renderPanel(dedicatedPayload);

    expect(screen.getAllByText("Dedicated carrier value").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Dedicated strategy").length).toBeGreaterThan(0);
  });

  it("renders unified operator sections from the dedicated cockpit payload", () => {
    renderPanel(unifiedPayload);

    expect(screen.getByText("统一运行链")).toBeInTheDocument();
    expect(screen.getAllByText("复核交接阻塞项").length).toBeGreaterThan(0);
    expect(screen.getAllByText("需要主管决策").length).toBeGreaterThan(0);
    expect(screen.getAllByText("运行治理").length).toBeGreaterThan(0);
    expect(screen.getAllByText("恢复").length).toBeGreaterThan(0);
    expect(screen.getAllByText("自动化").length).toBeGreaterThan(0);
    expect(screen.getByText("周期序列")).toBeInTheDocument();
    expect(screen.getByText("周期 8")).toBeInTheDocument();
    expect(screen.getAllByText("周期 9").length).toBeGreaterThan(0);
    expect(screen.getByText("待办")).toBeInTheDocument();
    expect(screen.getByText("连续性状态")).toBeInTheDocument();
    expect(screen.getByText("已就绪")).toBeInTheDocument();
    expect(screen.getByText("browser_backoffice, office_document")).toBeInTheDocument();
    expect(screen.getByText("待确认补位")).toBeInTheDocument();
    expect(screen.getByText("人工协作阻塞")).toBeInTheDocument();
    expect(screen.getAllByText("Resolve handoff return evidence gap").length).toBeGreaterThan(0);
    expect(screen.getByText("检查点证据")).toBeInTheDocument();
    expect(screen.getAllByText("批准宿主返回").length).toBeGreaterThan(0);
    expect(screen.getAllByText("应用连续性补丁").length).toBeGreaterThan(0);
  });

  it("renders report cognition and explicit replan visibility from the dedicated cockpit payload", () => {
    renderPanel(unifiedPayload);

    expect(screen.getAllByText("汇报认知").length).toBeGreaterThan(0);
    expect(
      screen.getByText(
        "Main brain must compare unresolved reports and decide whether to dispatch follow-up work.",
      ),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Resolve handoff return evidence gap").length).toBeGreaterThan(0);
    expect(
      screen.getAllByText("Reports disagree on whether the handoff is cleared.").length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText("Supervisor review is still missing for the handoff return.").length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText("需要重规划").length).toBeGreaterThan(0);
    expect(screen.getAllByText("待跟进").length).toBeGreaterThan(0);
    expect(screen.getAllByText("未消费汇报").length).toBeGreaterThan(0);
  });

  it("renders all six daily brief blocks", () => {
    renderPanel(unifiedPayload);

    expect(screen.getAllByText("主脑今日运行简报").length).toBeGreaterThan(0);
    expect(screen.getAllByText("今日目标").length).toBeGreaterThan(0);
    expect(screen.getAllByText("已完成").length).toBeGreaterThan(0);
    expect(screen.getAllByText("进行中").length).toBeGreaterThan(0);
    expect(screen.getAllByText("当前阻塞").length).toBeGreaterThan(0);
    expect(screen.getAllByText("待确认").length).toBeGreaterThan(0);
    expect(screen.getAllByText("下一步").length).toBeGreaterThan(0);
  });

  it("keeps only same-day report and trace records in the daily brief", () => {
    const scopedPayload = {
      ...unifiedPayload,
      reports: [
        {
          report_id: "report-today",
          title: "今日完成汇报",
          summary: "same-day report",
          status: "completed",
          completed_at: "2026-03-29T12:00:00Z",
          route: "/api/runtime-center/industry/industry-v1-ops?report_id=report-today",
        },
        {
          report_id: "report-old",
          title: "历史完成汇报",
          summary: "old report",
          status: "completed",
          completed_at: "2026-03-28T12:00:00Z",
          route: "/api/runtime-center/industry/industry-v1-ops?report_id=report-old",
        },
      ],
      evidence: {
        ...unifiedPayload.evidence,
        count: 2,
        entries: [
          {
            id: "evidence-today",
            title: "今日证据条目",
            created_at: "2026-03-29T08:00:00Z",
            route: "/api/runtime-center/evidence?entry=evidence-today",
          },
          {
            id: "evidence-old",
            title: "历史证据条目",
            created_at: "2026-03-27T08:00:00Z",
            route: "/api/runtime-center/evidence?entry=evidence-old",
          },
        ],
      },
    } as unknown as RuntimeMainBrainResponse;

    renderPanel(scopedPayload);

    expect(screen.getAllByText("今日完成汇报").length).toBeGreaterThan(0);
    expect(screen.queryByText("历史完成汇报")).not.toBeInTheDocument();
    expect(screen.getByText("今日证据条目")).toBeInTheDocument();
    expect(screen.queryByText("历史证据条目")).not.toBeInTheDocument();
    expect(within(findSectionBlock("证据")).getByText("1")).toBeInTheDocument();
  });

  it("shows explicit empty daily copy when only older or untimestamped records exist", () => {
    const scopedPayload = {
      ...unifiedPayload,
      reports: [
        {
          report_id: "report-old",
          title: "历史完成汇报",
          summary: "old report",
          status: "completed",
          completed_at: "2026-03-28T12:00:00Z",
          route: "/api/runtime-center/industry/industry-v1-ops?report_id=report-old",
        },
      ],
      evidence: {
        ...unifiedPayload.evidence,
        count: 1,
        entries: [
          {
            id: "evidence-no-time",
            title: "无时间证据条目",
            route: "/api/runtime-center/evidence?entry=evidence-no-time",
          },
        ],
      },
      environment: {
        ...unifiedPayload.environment,
        staffing: {
          pending_confirmation_count: 0,
        },
      },
      decisions: {
        ...unifiedPayload.decisions,
        count: 1,
        entries: [
          {
            id: "decision-old",
            title: "历史决策条目",
            created_at: "2026-03-27T12:00:00Z",
            route: "/api/runtime-center/decisions?entry=decision-old",
          },
        ],
      },
      patches: {
        ...unifiedPayload.patches,
        count: 1,
        entries: [
          {
            id: "patch-no-time",
            title: "无时间补丁条目",
            route: "/api/runtime-center/learning/patches?entry=patch-no-time",
          },
        ],
      },
    } as unknown as RuntimeMainBrainResponse;

    renderPanel(scopedPayload);

    expect(screen.getAllByText("今天暂无新完成记录。").length).toBeGreaterThan(0);
    expect(screen.getAllByText("今天暂无新增记录。").length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText("今天暂无待确认事项。")).toBeInTheDocument();
    expect(screen.queryByText("历史完成汇报")).not.toBeInTheDocument();
    expect(screen.queryByText("无时间证据条目")).not.toBeInTheDocument();
    expect(screen.queryByText("历史决策条目")).not.toBeInTheDocument();
    expect(screen.queryByText("无时间补丁条目")).not.toBeInTheDocument();
    expect(within(findSectionBlock("决策")).getByText("0")).toBeInTheDocument();
    expect(within(findSectionBlock("补丁")).getByText("0")).toBeInTheDocument();
  });
});
