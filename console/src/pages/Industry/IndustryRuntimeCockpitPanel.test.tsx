// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { IndustryInstanceDetail } from "../../api/modules/industry";
import IndustryRuntimeCockpitPanel from "./IndustryRuntimeCockpitPanel";
import { presentIndustryRuntimeStatus } from "./pageHelpers";

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
  autonomy_status: null,
  lifecycle_status: null,
  updated_at: "2026-03-26T08:00:00Z",
  stats: {},
  routes: {},
  execution: null,
  main_chain: null,
  focus_selection: null,
  strategy_memory: null,
  execution_core_identity: null,
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

describe("IndustryRuntimeCockpitPanel", () => {
  it("does not inherit top-level active status for empty backlog, assignment, and report subchains", () => {
    render(
      <IndustryRuntimeCockpitPanel
        detail={baseDetail}
        locale="zh-CN"
        onClearRuntimeFocus={vi.fn()}
        onOpenAgentReportChat={vi.fn()}
        onSelectAssignmentFocus={vi.fn()}
        onSelectBacklogFocus={vi.fn()}
      />,
    );

    expect(screen.getAllByText("待命").length).toBeGreaterThanOrEqual(3);
    expect(screen.queryByText("当前还没有活动待办。")).toBeInTheDocument();
    expect(screen.queryByText("当前还没有活动派工。")).toBeInTheDocument();
  });
  it("does not overstate empty lane and evidence subchains as active", () => {
    render(
      <IndustryRuntimeCockpitPanel
        detail={baseDetail}
        locale="zh-CN"
        onClearRuntimeFocus={vi.fn()}
        onOpenAgentReportChat={vi.fn()}
        onSelectAssignmentFocus={vi.fn()}
        onSelectBacklogFocus={vi.fn()}
      />,
    );

    expect(screen.getAllByText(presentIndustryRuntimeStatus("active")).length).toBe(1);
    expect(screen.getAllByText(presentIndustryRuntimeStatus("idle")).length).toBeGreaterThan(0);
  });
});
