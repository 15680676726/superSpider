// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  RuntimeCenterSurfaceInfo,
  RuntimeMainBrainMeta,
  RuntimeMainBrainPlanning,
  RuntimeMainBrainQueryRuntimeEntropy,
  RuntimeMainBrainResponse,
} from "../../api/modules/runtimeCenter";
import type { RuntimeCenterOverviewPayload } from "./useRuntimeCenter";
import MainBrainCockpitPanel from "./MainBrainCockpitPanel";


afterEach(() => {
  cleanup();
});
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

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
  main_brain_planning: {},
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

const unifiedPlanning: RuntimeMainBrainPlanning = {
  strategy_constraints: {
    planning_policy: ["prefer-followup-before-net-new"],
    strategic_uncertainties: [{ uncertainty_id: "uncertainty-followup-pressure" }],
    lane_budgets: [{ lane_id: "lane-ops", budget: 2 }],
  },
  latest_cycle_decision: {
    cycle_id: "cycle-9",
    summary: "Cycle shell for Runtime Center.",
    selected_backlog_item_ids: ["backlog-followup-1"],
    selected_assignment_ids: ["assignment-1"],
    planning_shell: {
      verify_reminder: "Verify cycle lane pressure before materializing assignments.",
      resume_key: "industry:industry-v1-ops:cycle-9",
      fork_key: "cycle:daily",
    },
  },
  focused_assignment_plan: {
    summary: "Assignment shell keeps the browser follow-up on the same control thread.",
    checkpoints: [{ kind: "verify", label: "Verify browser evidence." }],
    acceptance_criteria: ["Browser evidence captured and linked."],
    planning_shell: {
      verify_reminder: "Verify browser evidence before closing the assignment.",
      resume_key: "assignment:assignment-1",
      fork_key: "assignment:followup",
    },
  },
  replan: {
    status: "needs-replan",
    decision_kind: "lane_reweight",
    summary: "Replan shell is waiting for main-brain judgment.",
    strategy_trigger_rules: [
      { rule_id: "review-rule:0" },
      { rule_id: "uncertainty:uncertainty-followup-pressure:confidence-drop" },
    ],
    uncertainty_register: {
      summary: {
        uncertainty_count: 1,
        lane_budget_count: 1,
        trigger_rule_count: 2,
      },
      items: [{ uncertainty_id: "uncertainty-followup-pressure" }],
    },
    planning_shell: {
      verify_reminder: "Verify synthesis pressure before mutating planning truth.",
      resume_key: "report:report-1",
      fork_key: "decision:lane_reweight",
    },
  },
};

const unifiedMeta: RuntimeMainBrainMeta = {
  control_chain: [
    { key: "carrier", value: "Northwind Ops" },
    { key: "strategy", value: "Northwind field operations strategy" },
    { key: "report_cognition", value: "attention" },
    { key: "governance", value: "blocked" },
    { key: "automation", value: "active" },
    { key: "recovery", value: "ready" },
  ],
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
  main_brain_planning: unifiedPlanning,
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
  meta: unifiedMeta,
} satisfies RuntimeMainBrainResponse;

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

describe("MainBrainCockpitPanel", () => {
  it("renders dedicated payload signals when available", () => {
    renderPanel(dedicatedPayload);

    expect(screen.getAllByText("Dedicated carrier value").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Dedicated strategy").length).toBeGreaterThan(0);
  });

  it("does not fall back to overview surface metadata when dedicated metadata is missing", () => {
    render(
      <MainBrainCockpitPanel
        data={{
          ...overviewPayload,
          generated_at: "overview-generated-at",
          surface: {
            ...surface,
            source: "overview-surface-source",
            note: "Overview surface note should stay hidden",
          },
        }}
        loading={false}
        refreshing={false}
        error="overview error should stay hidden"
        mainBrainData={
          {
            ...dedicatedPayload,
            generated_at: undefined,
            surface: undefined,
          } as unknown as RuntimeMainBrainResponse
        }
        mainBrainLoading={false}
        mainBrainError={null}
        mainBrainUnavailable={false}
        onRefresh={vi.fn()}
        onOpenRoute={vi.fn()}
      />,
    );

    expect(screen.queryByText("Overview surface note should stay hidden")).toBeNull();
    expect(screen.queryByText("overview-surface-source")).toBeNull();
    expect(screen.queryByText(/overview-generated-at/)).toBeNull();
    expect(screen.queryByText(/overview error should stay hidden/)).toBeNull();
  });

  it("does not fall back to overview-assembled runtime facts when the dedicated payload is missing", () => {
    render(
      <MainBrainCockpitPanel
        data={{
          ...overviewPayload,
          cards: [
            {
              key: "industry",
              title: "Industry",
              source: "state-service",
              status: "state-service",
              count: 1,
              summary: "fallback overview",
              entries: [],
              meta: {
                carrier: {
                  value: "Fallback carrier",
                },
              },
            },
          ],
        }}
        loading={false}
        refreshing={false}
        error={null}
        mainBrainData={null}
        mainBrainLoading={false}
        mainBrainError={null}
        mainBrainUnavailable={true}
        onRefresh={vi.fn()}
        onOpenRoute={vi.fn()}
      />,
    );

    expect(screen.getByText("主脑驾驶舱暂未接入正式读面。")).toBeInTheDocument();
    expect(screen.queryByText("Fallback carrier")).toBeNull();
  });

  it("renders unified operator sections from the dedicated cockpit payload", () => {
    renderPanel(unifiedPayload);

    expect(screen.getAllByText("Resolve handoff return evidence gap").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Northwind field operations strategy").length).toBeGreaterThan(0);
    expect(screen.getAllByText("browser_backoffice, office_document").length).toBeGreaterThan(0);
  });

  it("renders report cognition and explicit replan visibility from the dedicated cockpit payload", () => {
    renderPanel(unifiedPayload);

    expect(screen.getAllByText("Resolve handoff return evidence gap").length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(
        "Main brain must compare unresolved reports and decide whether to dispatch follow-up work.",
      ).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText("Reports disagree on whether the handoff is cleared.").length,
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText("Supervisor review is still missing for the handoff return.").length,
    ).toBeGreaterThan(0);
  });

  it("renders structured formal planning shell visibility in the main-brain cockpit", () => {
    renderPanel(unifiedPayload);

    expect(screen.getByText("Cycle shell for Runtime Center.")).toBeInTheDocument();
    expect(
      screen.getByText("Verify cycle lane pressure before materializing assignments."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Assignment shell keeps the browser follow-up on the same control thread.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Verify browser evidence before closing the assignment."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Replan shell is waiting for main-brain judgment."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Verify synthesis pressure before mutating planning truth."),
    ).toBeInTheDocument();
  });

  it("renders query runtime entropy visibility in the main-brain cockpit", () => {
    const queryRuntimeEntropy: RuntimeMainBrainQueryRuntimeEntropy = {
      status: "available",
      runtime_entropy: {
        status: "available",
        sidecar_memory_status: "available",
        carry_forward_contract: "private-compaction-sidecar",
      },
      sidecar_memory: {
        status: "available",
      },
      compaction_state: {
        mode: "microcompact",
        summary: "Compacted 2 oversized tool results.",
        spill_count: 1,
        replacement_count: 2,
      },
      tool_result_budget: {
        message_budget: 2400,
        used_budget: 1800,
        remaining_budget: 600,
      },
      tool_use_summary: {
        summary: "2 tool results compacted into artifact previews.",
        artifact_refs: [
          "artifact://tool-result-1",
          "artifact://tool-result-2",
        ],
      },
    };
    const entropyPayload = {
      ...unifiedPayload,
      governance: {
        ...unifiedPayload.governance,
        query_runtime_entropy: queryRuntimeEntropy,
      },
    } satisfies RuntimeMainBrainResponse;

    renderPanel(entropyPayload);

    const entropyHeadings = screen.getAllByRole("heading", {
      level: 3,
      name: "Query runtime entropy",
    });
    const entropyBlock = entropyHeadings[entropyHeadings.length - 1]
      ?.parentElement?.parentElement?.parentElement?.parentElement as HTMLElement;
    expect(within(entropyBlock).getAllByText("available").length).toBeGreaterThan(0);
    expect(within(entropyBlock).getByText("microcompact")).toBeInTheDocument();
    expect(
      within(entropyBlock).getByText("Compacted 2 oversized tool results."),
    ).toBeInTheDocument();
    expect(within(entropyBlock).getByText("600 / 2400")).toBeInTheDocument();
    expect(
      within(entropyBlock).getByText("2 tool results compacted into artifact previews."),
    ).toBeInTheDocument();
    expect(
      within(entropyBlock).getByText(
        "artifact://tool-result-1, artifact://tool-result-2",
      ),
    ).toBeInTheDocument();
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
          title: "Today report",
          summary: "same-day report",
          status: "completed",
          completed_at: "2026-03-29T12:00:00Z",
          route: "/api/runtime-center/industry/industry-v1-ops?report_id=report-today",
        },
        {
          report_id: "report-old",
          title: "Old report",
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
            title: "Today evidence",
            created_at: "2026-03-29T08:00:00Z",
            route: "/api/runtime-center/evidence?entry=evidence-today",
          },
          {
            id: "evidence-old",
            title: "Old evidence",
            created_at: "2026-03-27T08:00:00Z",
            route: "/api/runtime-center/evidence?entry=evidence-old",
          },
        ],
      },
    } satisfies RuntimeMainBrainResponse;

    renderPanel(scopedPayload);

    expect(screen.getAllByText("Today report").length).toBeGreaterThan(0);
    expect(screen.queryByText("Old report")).toBeNull();
    expect(screen.getAllByText("Today evidence").length).toBeGreaterThan(0);
    expect(screen.queryByText("Old evidence")).toBeNull();
  });

  it("shows explicit empty daily copy when only older or untimestamped records exist", () => {
    const scopedPayload = {
      ...unifiedPayload,
      reports: [
        {
          report_id: "report-old",
          title: "Old report",
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
            title: "Untimed evidence",
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
            title: "Old decision",
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
            title: "Untimed patch",
            route: "/api/runtime-center/learning/patches?entry=patch-no-time",
          },
        ],
      },
    } satisfies RuntimeMainBrainResponse;

    renderPanel(scopedPayload);

    expect(screen.queryByText("Old report")).toBeNull();
    expect(screen.queryByText("Untimed evidence")).toBeNull();
    expect(screen.queryByText("Old decision")).toBeNull();
    expect(screen.queryByText("Untimed patch")).toBeNull();
  });
});
