// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { IndustryInstanceDetail } from "../../api/modules/industry";
import { renderIndustryExecutionFocusSection } from "./viewHelpers";

const baseDetail = {
  instance_id: "industry-1",
  bootstrap_kind: "industry-v1",
  label: "Demo Industry",
  summary: "Demo",
  owner_scope: "operator",
  profile: {
    schema_version: "industry-profile-v1",
    industry: "demo",
    target_customers: [],
    channels: [],
    goals: [],
    constraints: [],
    experience_mode: "operator-guided",
    operator_requirements: [],
  },
  team: {
    schema_version: "industry-team-blueprint-v1",
    team_id: "team-1",
    label: "Demo Team",
    summary: "Demo Team",
    agents: [],
  },
  status: "active",
  updated_at: "2026-03-26T08:00:00Z",
  stats: {},
  routes: {},
  goals: [],
  agents: [],
  schedules: [],
  lanes: [],
  backlog: [],
  staffing: {
    pending_proposals: [],
    temporary_seats: [],
  },
  current_cycle: null,
  cycles: [],
  assignments: [],
  agent_reports: [],
  tasks: [],
  decisions: [],
  evidence: [],
  patches: [],
  growth: [],
  proposals: [],
  reports: {
    daily: {
      window: "daily",
      since: "2026-03-26T00:00:00Z",
      until: "2026-03-26T23:59:59Z",
      evidence_count: 0,
      proposal_count: 0,
      patch_count: 0,
      applied_patch_count: 0,
      growth_count: 0,
      decision_count: 0,
      recent_evidence: [],
      highlights: [],
    },
    weekly: {
      window: "weekly",
      since: "2026-03-20T00:00:00Z",
      until: "2026-03-26T23:59:59Z",
      evidence_count: 0,
      proposal_count: 0,
      patch_count: 0,
      applied_patch_count: 0,
      growth_count: 0,
      decision_count: 0,
      recent_evidence: [],
      highlights: [],
    },
  },
  media_analyses: [],
} as IndustryInstanceDetail;

describe("runtimeCenter viewHelpers", () => {
  it("labels the runtime focus card as current focus instead of current goal", () => {
    render(
      renderIndustryExecutionFocusSection(
        {
          ...baseDetail,
          execution: {
            status: "active",
            current_goal: "Handle the current backlog",
            current_owner: "Execution Core",
            current_risk: "auto",
            evidence_count: 0,
            latest_evidence_summary: "",
          },
        },
        vi.fn(),
      ) as React.ReactElement,
    );

    expect(screen.getByText("Current Focus")).toBeTruthy();
    expect(screen.queryByText("Current Goal")).toBeNull();
  });

  it("uses no active focus as the empty-state copy", () => {
    render(
      renderIndustryExecutionFocusSection(
        {
          ...baseDetail,
          execution: {
            status: "idle",
            current_goal: "",
            current_owner: "Execution Core",
            current_risk: "unknown",
            evidence_count: 0,
            latest_evidence_summary: "",
          },
        },
        vi.fn(),
      ) as React.ReactElement,
    );

    expect(screen.getByText("No active focus")).toBeTruthy();
    expect(screen.queryByText("No active goal")).toBeNull();
  });

  it("renders shared risk labels instead of raw runtime risk tokens", () => {
    render(
      renderIndustryExecutionFocusSection(
        {
          ...baseDetail,
          execution: {
            status: "active",
            current_goal: "Handle the current backlog",
            current_owner: "Execution Core",
            current_risk: "guarded",
            evidence_count: 0,
            latest_evidence_summary: "",
          },
        },
        vi.fn(),
      ) as React.ReactElement,
    );

    expect(screen.getAllByText("守护").length).toBeGreaterThan(0);
    expect(screen.queryByText("guarded")).toBeNull();
  });

  it("uses the shared runtime status color tags for execution focus", () => {
    render(
      renderIndustryExecutionFocusSection(
        {
          ...baseDetail,
          execution: {
            status: "active",
            current_goal: "Handle the current backlog",
            current_owner: "Execution Core",
            current_risk: "auto",
            evidence_count: 0,
            latest_evidence_summary: "",
          },
        },
        vi.fn(),
      ) as React.ReactElement,
    );

    expect(
      screen
        .getAllByText("自治运行中")
        .some((node) => node.className.includes("ant-tag-green")),
    ).toBe(true);
  });
});
