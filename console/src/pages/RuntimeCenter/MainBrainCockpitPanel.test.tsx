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
});
