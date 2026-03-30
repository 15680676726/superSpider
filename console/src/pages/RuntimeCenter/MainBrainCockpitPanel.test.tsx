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
  current_cycle: {
    title: "Cycle 99",
    next_cycle_due_at: "2026-03-31T23:59:59Z",
    focus_count: 4,
  },
  assignments: [],
  reports: [],
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
      status: "recorded",
      needs_followup: true,
      route: "/api/runtime-center/industry/industry-v1-ops",
    },
  ],
  environment: {
    route: "/api/runtime-center/governance/status",
    summary: "Host twin ready on seat-b with multi-surface continuity.",
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
  },
  meta: {
    control_chain: [
      { key: "carrier", value: "Northwind Ops" },
      { key: "strategy", value: "Northwind field operations strategy" },
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

    expect(screen.getByText("Unified Runtime Chain")).toBeInTheDocument();
    expect(screen.getByText("Review handoff blockers")).toBeInTheDocument();
    expect(screen.getByText("Need supervisor decision")).toBeInTheDocument();
    expect(screen.getAllByText("Runtime Governance").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Recovery").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Automation").length).toBeGreaterThan(0);
    expect(screen.getByText("Checkpoint evidence")).toBeInTheDocument();
    expect(screen.getByText("Approve host return")).toBeInTheDocument();
    expect(screen.getByText("Apply continuity patch")).toBeInTheDocument();
  });
});
