import { describe, expect, it } from "vitest";

import type { IndustryInstanceDetail } from "../api/modules/industry";
import { presentControlChain } from "./controlChainPresentation";

const detailFixture = {
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
  updated_at: "2026-03-25T08:00:00Z",
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
  current_cycle: {
    cycle_id: "cycle-1",
    cycle_kind: "weekly",
    title: "Weekly operating cycle",
    status: "active",
    focus_lane_ids: [],
    backlog_item_ids: [],
    goal_ids: [],
    assignment_ids: ["assignment-1"],
    report_ids: ["report-1"],
    synthesis: {
      latest_findings: [
        {
          report_id: "report-1",
          findings: ["Finding A"],
          uncertainties: [],
          needs_followup: false,
        },
        {
          report_id: "report-2",
          findings: ["Finding B"],
          uncertainties: ["Missing evidence"],
          needs_followup: true,
        },
      ],
      conflicts: [
        {
          conflict_id: "conflict-1",
          kind: "report-conflict",
          report_ids: ["report-1", "report-2"],
          owner_agent_ids: ["agent-1", "agent-2"],
        },
      ],
      holes: [
        {
          hole_id: "hole-1",
          kind: "follow-up",
        },
      ],
      recommended_actions: [
        {
          action_id: "action-1",
          action_type: "reassign",
        },
        {
          action_id: "action-2",
          action_type: "research",
        },
      ],
      needs_replan: true,
      control_core_contract: ["synthesize-before-reassign"],
    },
    metadata: {},
  },
  cycles: [],
  assignments: [],
  agent_reports: [],
  tasks: [],
  decisions: [],
  evidence: [],
  patches: [],
  growth: [],
  proposals: [],
  execution: {
    status: "active",
    current_focus: "Recover the live operating chain",
    current_owner: "Main Brain",
    current_risk: "guarded",
    evidence_count: 3,
    latest_evidence_summary: "Latest execution evidence",
  },
  main_chain: {
    schema_version: "industry-main-chain-v1",
    loop_state: "active",
    current_focus: "Recover the live operating chain",
    current_owner: "Main Brain",
    current_risk: "guarded",
    latest_evidence_summary: "Latest execution evidence",
    nodes: [
      {
        node_id: "report",
        label: "Report",
        status: "recorded",
        truth_source: "agent_reports",
        current_ref: "report-1",
        summary: "Execution seat reported back",
        metrics: {
          report_count: 1,
        },
      },
      {
        node_id: "goal",
        label: "Goal",
        status: "active",
        truth_source: "legacy-goals",
        current_ref: "goal-legacy",
        summary: "Legacy node should not appear",
        metrics: {},
      },
      {
        node_id: "assignment",
        label: "Assignment",
        status: "assigned",
        truth_source: "assignments",
        current_ref: "assignment-1",
        summary: "Main brain delegated work",
        metrics: {
          assignment_count: 1,
        },
      },
      {
        node_id: "writeback",
        label: "Writeback",
        status: "completed",
        truth_source: "strategy_writeback",
        current_ref: "writeback-1",
        summary: "Chat writeback landed in state",
        metrics: {
          writes: 1,
        },
      },
      {
        node_id: "replan",
        label: "Replan",
        status: "review",
        truth_source: "cycle_synthesis",
        current_ref: "cycle-1",
        summary: "Conflict review required",
        metrics: {
          needs_replan: 1,
        },
      },
      {
        node_id: "backlog",
        label: "Backlog",
        status: "queued",
        truth_source: "backlog_items",
        current_ref: "backlog-1",
        summary: "Backlog item materialized",
        metrics: {
          backlog_count: 1,
        },
      },
      {
        node_id: "cycle",
        label: "Cycle",
        status: "active",
        truth_source: "cycles",
        current_ref: "cycle-1",
        summary: "Cycle is supervising current work",
        metrics: {
          cycle_kind: "weekly",
        },
      },
    ],
  },
  reports: {
    daily: {
      window: "daily",
      since: "2026-03-25T00:00:00Z",
      until: "2026-03-25T23:59:59Z",
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
      since: "2026-03-19T00:00:00Z",
      until: "2026-03-25T23:59:59Z",
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

describe("controlChainPresentation", () => {
  it("renders the supervision chain from writeback to replan", () => {
    const model = presentControlChain(detailFixture);

    expect(model.nodes.map((node) => node.id)).toEqual([
      "writeback",
      "backlog",
      "cycle",
      "assignment",
      "report",
      "replan",
    ]);
    expect(model.nodes.map((node) => node.label)).toEqual([
      "Writeback",
      "Backlog",
      "Cycle",
      "Assignment",
      "Report",
      "Replan",
    ]);
    expect(model.currentFocus).toBe("Recover the live operating chain");
    expect(model.currentOwner).toBe("Main Brain");
    expect(model.currentRisk).toBe("guarded");
    expect(model.synthesis).toMatchObject({
      findingCount: 2,
      conflictCount: 1,
      holeCount: 1,
      actionCount: 2,
      needsReplan: true,
      summary: "Findings 2 / Conflicts 1 / Holes 1 / Actions 2",
    });
  });

  it("does not mutate the input main chain when presenting", () => {
    const payload = structuredClone(detailFixture);
    const originalNodeIds = payload.main_chain?.nodes.map((node) => node.node_id);

    void presentControlChain(payload);

    expect(payload.main_chain?.nodes.map((node) => node.node_id)).toEqual(
      originalNodeIds,
    );
    expect(payload.main_chain?.nodes[0]?.node_id).toBe("report");
  });

  it("returns an empty presentation when no runtime chain is available", () => {
    const model = presentControlChain(null);

    expect(model.nodes).toEqual([]);
    expect(model.synthesis).toBeNull();
    expect(model.hasAnyState).toBe(false);
  });
});
