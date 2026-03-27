// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { IndustryInstanceDetail } from "../../api/modules/industry";
import { renderRuntimeDetailDrawer } from "./runtimeDetailDrawer";

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

describe("runtimeDetailDrawer", () => {
  it("renders industry focus and main chain through specialized sections without jsdom pseudo-element warnings", () => {
    render(
      renderRuntimeDetailDrawer(
        {
          route: "/api/runtime-center/industry/industry-1",
          title: "Industry detail",
          payload: {
            ...baseDetail,
            execution: {
              status: "active",
              current_goal: "Handle backlog",
              current_owner: "Execution Core",
              current_risk: "auto",
              evidence_count: 0,
              latest_evidence_summary: "",
            },
            main_chain: {
              schema_version: "industry-main-chain-v1",
              loop_state: "active",
              current_goal: "Handle backlog",
              current_owner: "Execution Core",
              current_risk: "auto",
              nodes: [],
            },
          },
        },
        false,
        null,
        vi.fn(),
        vi.fn(),
      ) as React.ReactElement,
    );

    expect(screen.getByText("Runtime Focus")).toBeTruthy();
    expect(screen.getByText("Spider Main Chain")).toBeTruthy();
    expect(screen.queryByText("Execution")).toBeNull();
    expect(screen.queryByText("Main Chain")).toBeNull();
  });
});
