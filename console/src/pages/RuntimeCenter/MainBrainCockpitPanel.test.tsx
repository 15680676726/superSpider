// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
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
    entries: [{ id: "evidence-1", title: "Checkpoint evidence" }],
    meta: {},
  },
  decisions: {
    count: 1,
    summary: "One decision pending.",
    route: "/api/runtime-center/decisions",
    entries: [{ id: "decision-1", title: "Approve host return" }],
    meta: {},
  },
  patches: {
    count: 1,
    summary: "One patch pending.",
    route: "/api/runtime-center/learning/patches",
    entries: [{ id: "patch-1", title: "Apply continuity patch" }],
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

describe("MainBrainCockpitPanel", () => {
  it("renders dedicated payload signals when available", () => {
    render(
      <MainBrainCockpitPanel
        data={overviewPayload}
        loading={false}
        refreshing={false}
        error={null}
        mainBrainData={dedicatedPayload}
        mainBrainLoading={false}
        mainBrainError={null}
        mainBrainUnavailable={false}
        onRefresh={vi.fn()}
        onOpenRoute={vi.fn()}
      />,
    );

    expect(screen.getAllByText("Dedicated carrier value").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Dedicated strategy").length).toBeGreaterThan(0);
  });

  it("renders unified operator sections from the dedicated cockpit payload", () => {
    render(
      <MainBrainCockpitPanel
        data={overviewPayload}
        loading={false}
        refreshing={false}
        error={null}
        mainBrainData={unifiedPayload}
        mainBrainLoading={false}
        mainBrainError={null}
        mainBrainUnavailable={false}
        onRefresh={vi.fn()}
        onOpenRoute={vi.fn()}
      />,
    );

    expect(screen.getByText("统一运行链")).toBeInTheDocument();
    expect(screen.getByText("复核交接阻塞项")).toBeInTheDocument();
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
    expect(screen.getByText("批准宿主返回")).toBeInTheDocument();
    expect(screen.getByText("应用连续性补丁")).toBeInTheDocument();
  });

  it("renders report cognition and explicit replan visibility from the dedicated cockpit payload", () => {
    render(
      <MainBrainCockpitPanel
        data={overviewPayload}
        loading={false}
        refreshing={false}
        error={null}
        mainBrainData={unifiedPayload}
        mainBrainLoading={false}
        mainBrainError={null}
        mainBrainUnavailable={false}
        onRefresh={vi.fn()}
        onOpenRoute={vi.fn()}
      />,
    );

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
});
