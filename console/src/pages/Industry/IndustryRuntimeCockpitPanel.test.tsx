// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
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

  it("prefers the latest backlog, assignment, and follow-up report instead of the first array item", () => {
    const onSelectBacklogFocus = vi.fn();
    const onSelectAssignmentFocus = vi.fn();
    const onOpenAgentReportChat = vi.fn();
    const detail = {
      ...baseDetail,
      backlog: [
        {
          backlog_item_id: "backlog-old",
          title: "Old backlog",
          summary: "Old backlog summary",
          status: "active",
          priority: 2,
          source_kind: "manual",
          evidence_ids: [],
          metadata: {},
          updated_at: "2026-03-26T08:00:00Z",
        },
        {
          backlog_item_id: "backlog-new",
          title: "Latest backlog",
          summary: "Latest backlog summary",
          status: "completed",
          priority: 1,
          source_kind: "manual",
          evidence_ids: [],
          metadata: {},
          updated_at: "2026-03-26T10:00:00Z",
        },
      ],
      assignments: [
        {
          assignment_id: "assignment-old",
          title: "Old assignment",
          summary: "Old assignment summary",
          status: "active",
          evidence_ids: [],
          metadata: {},
          updated_at: "2026-03-26T08:00:00Z",
        },
        {
          assignment_id: "assignment-new",
          title: "Latest assignment",
          summary: "Latest assignment summary",
          status: "completed",
          evidence_ids: [],
          metadata: {},
          updated_at: "2026-03-26T10:00:00Z",
        },
      ],
      agent_reports: [
        {
          report_id: "report-old",
          headline: "Old follow-up",
          report_kind: "summary",
          status: "submitted",
          summary: "Old summary",
          findings: [],
          uncertainties: [],
          needs_followup: true,
          followup_reason: "Need old follow-up",
          evidence_ids: [],
          decision_ids: [],
          processed: false,
          metadata: {},
          updated_at: "2026-03-26T08:00:00Z",
        },
        {
          report_id: "report-new",
          headline: "Latest follow-up",
          report_kind: "summary",
          status: "recorded",
          summary: "Latest summary",
          findings: [],
          uncertainties: [],
          needs_followup: true,
          followup_reason: "Need latest follow-up",
          evidence_ids: [],
          decision_ids: [],
          processed: false,
          metadata: {},
          updated_at: "2026-03-26T10:00:00Z",
        },
      ],
    } as IndustryInstanceDetail;

    render(
      <IndustryRuntimeCockpitPanel
        detail={detail}
        locale="zh-CN"
        onClearRuntimeFocus={vi.fn()}
        onOpenAgentReportChat={onOpenAgentReportChat}
        onSelectAssignmentFocus={onSelectAssignmentFocus}
        onSelectBacklogFocus={onSelectBacklogFocus}
      />,
    );

    fireEvent.click(screen.getAllByRole("button", { name: "聚焦待办" })[0]);
    fireEvent.click(screen.getAllByRole("button", { name: "聚焦派工" })[0]);
    fireEvent.click(screen.getByRole("button", { name: "打开跟进对话" }));

    expect(onSelectBacklogFocus).toHaveBeenCalledWith("backlog-new");
    expect(onSelectAssignmentFocus).toHaveBeenCalledWith("assignment-new");
    expect(onOpenAgentReportChat).toHaveBeenCalledWith(
      expect.objectContaining({ report_id: "report-new" }),
    );
  });
});
