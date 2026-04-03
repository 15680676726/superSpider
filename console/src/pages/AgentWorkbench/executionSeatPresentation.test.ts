import { describe, expect, it } from "vitest";

import type {
  IndustryInstanceDetail,
  IndustryRuntimeAgentReport,
  IndustryStrategyTeammateContract,
} from "../../api/modules/industry";
import {
  buildNeedsBrainConfirmation,
  reportNeedsAttention,
  resolveEscalations,
  resolveRoleContract,
} from "./executionSeatPresentation";
import type { AgentCapabilityDecision, AgentProfile } from "./useAgentWorkbench";

const agentFixture: AgentProfile = {
  agent_id: "agent-1",
  name: "Operator",
  role_name: "Operator",
  role_summary: "Handles delivery work.",
  agent_class: "business",
  employment_mode: "career",
  activation_mode: "persistent",
  suspendable: false,
  reports_to: "execution-core",
  mission: "Keep execution moving.",
  status: "active",
  risk_level: "guarded",
  current_focus_kind: null,
  current_focus_id: null,
  current_focus: "",
  current_task_id: null,
  industry_instance_id: "industry-1",
  industry_role_id: "operator",
  environment_summary: "",
  environment_constraints: [],
  evidence_expectations: [],
  today_output_summary: "",
  latest_evidence_summary: "",
  capabilities: [],
  updated_at: "2026-03-24T08:00:00Z",
};

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
  updated_at: "2026-03-24T08:00:00Z",
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
      since: "2026-03-24T00:00:00Z",
      until: "2026-03-24T23:59:59Z",
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
      since: "2026-03-18T00:00:00Z",
      until: "2026-03-24T23:59:59Z",
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

describe("executionSeatPresentation", () => {
  it("uses typed teammate contracts before falling back to the team blueprint", () => {
    const teammateContracts: IndustryStrategyTeammateContract[] = [
      {
        agent_id: "agent-1",
        role_id: "operator",
        role_name: "Typed Contract Operator",
        role_summary: "Owns typed contract output.",
        mission: "Deliver from strategy memory.",
        reports_to: "execution-core",
        goal_kind: "delivery",
        risk_level: "guarded",
        employment_mode: "temporary",
        capabilities: ["browser"],
        evidence_expectations: ["summary"],
        environment_constraints: ["desktop"],
      },
    ];
    const detail = {
      ...baseDetail,
      strategy_memory: {
        teammate_contracts: teammateContracts,
      },
      team: {
        ...baseDetail.team,
        agents: [
          {
            schema_version: "industry-role-blueprint-v1",
            role_id: "operator",
            agent_id: "agent-1",
            name: "Fallback Operator",
            role_name: "Fallback Operator",
            role_summary: "Fallback summary",
            mission: "Fallback mission",
            goal_kind: "fallback",
            agent_class: "business",
            employment_mode: "career",
            activation_mode: "persistent",
            suspendable: false,
            reports_to: "execution-core",
            risk_level: "auto",
            environment_constraints: [],
            allowed_capabilities: [],
            preferred_capability_families: [],
            evidence_expectations: [],
          },
        ],
      },
    } as IndustryInstanceDetail;

    const contract = resolveRoleContract(agentFixture, detail);

    expect(contract).toMatchObject({
      role_name: "Typed Contract Operator",
      role_summary: "Owns typed contract output.",
      employment_mode: "temporary",
      capabilities: ["browser"],
      evidence_expectations: ["summary"],
      environment_constraints: ["desktop"],
    });
  });

  it("keeps pending decisions separate from escalated reports", () => {
    const pendingDecisions: AgentCapabilityDecision[] = [
      {
        id: "decision-1",
        summary: "Enable browser surface",
        reason: "Need operator approval",
        decision_type: "capability-assign",
        capabilities: ["browser"],
      },
    ];
    const escalation: IndustryRuntimeAgentReport = {
      report_id: "report-1",
      report_kind: "task-closeout",
      headline: "Blocked by missing credentials",
      summary: "Need fresh credential package.",
      status: "review",
      result: "blocked",
      findings: [],
      uncertainties: [],
      needs_followup: true,
      followup_reason: "Awaiting credentials",
      risk_level: "guarded",
      evidence_ids: [],
      decision_ids: ["decision-77"],
      processed: false,
      metadata: {},
      owner_agent_id: "agent-1",
      created_at: "2026-03-24T08:00:00Z",
      updated_at: "2026-03-24T09:00:00Z",
    };

    expect(buildNeedsBrainConfirmation(pendingDecisions)).toEqual([
      {
        id: "decision-1",
        title: "Enable browser surface",
        detail: "Need operator approval",
        color: "orange",
      },
    ]);
    expect(reportNeedsAttention(escalation)).toBe(true);
    expect(
      resolveEscalations(agentFixture, {
        ...baseDetail,
        agent_reports: [escalation],
      } as IndustryInstanceDetail).map((item) => item.report_id),
    ).toEqual(["report-1"]);
  });
});
