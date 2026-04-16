import { describe, expect, it } from "vitest";

import type { IndustryStaffingState } from "../api/modules/industry";
import {
  buildStaffingPresentation,
  presentSeatLifecycleState,
} from "./staffingGapPresentation";

const staffingFixture: IndustryStaffingState = {
  active_gap: {
    backlog_item_id: "backlog-seat-1",
    kind: "career-seat-proposal",
    reason: "Need a long-term browser execution seat",
    requested_surfaces: ["browser"],
    target_role_id: "platform-trader",
    target_role_name: "Platform Trader",
    target_agent_id: "industry-platform-trader-demo",
    decision_request_id: "decision-seat-1",
    proposal_status: "waiting-confirm",
    status: "open",
    requires_confirmation: true,
    title: "Platform Trader seat proposal",
    summary: "Add a governed long-term browser execution role",
    route: "/api/runtime-center/decisions/decision-seat-1",
    updated_at: "2026-03-24T08:00:00Z",
  },
  pending_proposals: [
    {
      backlog_item_id: "backlog-seat-1",
      kind: "career-seat-proposal",
      target_role_name: "Platform Trader",
      target_agent_id: "industry-desktop-clerk-demo",
      decision_request_id: "decision-seat-1",
      status: "open",
      requested_surfaces: ["browser"],
      requires_confirmation: true,
    },
  ],
  temporary_seats: [
    {
      role_id: "desktop-clerk",
      role_name: "Desktop Clerk",
      agent_id: "industry-desktop-clerk-demo",
      status: "assigned",
      employment_mode: "temporary",
      activation_mode: "on-demand",
      reports_to: "execution-core",
      route: "/api/runtime-center/agents/industry-desktop-clerk-demo",
      auto_retire_hint:
        "Retire this temporary seat after the delegated workload closes.",
      current_assignment: {
        assignment_id: "assignment-1",
        title: "Desktop folder cleanup",
        status: "active",
      },
      latest_report: {
        report_id: "report-1",
        headline: "Desktop cleanup in progress",
        status: "recorded",
      },
      origin: {
        backlog_item_id: "backlog-seat-2",
        kind: "temporary-seat-auto",
        title: "Desktop Clerk temporary seat",
        status: "assigned",
        requested_surfaces: ["desktop", "file"],
        requires_confirmation: false,
      },
    },
  ],
  researcher: {
    role_id: "researcher",
    role_name: "Researcher",
    agent_id: "industry-researcher-demo",
    status: "waiting-review",
    route: "/api/runtime-center/agents/industry-researcher-demo",
    pending_signal_count: 2,
    waiting_for_main_brain: true,
    current_assignment: {
      assignment_id: "assignment-2",
      title: "Weekly signal scan",
      status: "active",
    },
    latest_report: {
      report_id: "report-2",
      headline: "Signal summary ready",
      status: "recorded",
    },
  },
};

describe("staffingGapPresentation", () => {
  it("summarizes the canonical staffing state for UI surfaces", () => {
    const presentation = buildStaffingPresentation(staffingFixture);

    expect(presentation.activeGap?.title).toContain("Platform Trader");
    expect(presentation.activeGap?.badges).toContain("Needs approval");
    expect(presentation.activeGap?.meta).toContain("browser");
    expect(presentation.pendingProposals[0]).toContain("decision-seat-1");
    expect(presentation.temporarySeats[0]).toContain("Desktop Clerk");
    expect(presentation.temporarySeats[0]).toContain("auto-retire");
    expect(presentation.researcher?.headline).toContain("研究位");
    expect(presentation.researcher?.detail).toContain("待主脑处理研究汇报 2");
    expect(presentation.researcher?.badges).toContain("待主脑处理");
  });

  it("maps seat lifecycle states for Agent Workbench", () => {
    expect(
      presentSeatLifecycleState({
        staffing: staffingFixture,
        agentId: "industry-desktop-clerk-demo",
        employmentMode: "temporary",
      }),
    ).toBe("Pending promotion");

    expect(
      presentSeatLifecycleState({
        staffing: staffingFixture,
        agentId: "industry-platform-trader-demo",
        employmentMode: "career",
      }),
    ).toBe("Pending approval");

    expect(
      presentSeatLifecycleState({
        staffing: staffingFixture,
        agentId: "copaw-agent-runner",
        employmentMode: "career",
      }),
    ).toBe("Permanent seat");
  });

  it("keeps browser seat proposals visible and governed in the runtime surface", () => {
    const browserProposalFixture: IndustryStaffingState = {
      ...staffingFixture,
      active_gap: {
        ...staffingFixture.active_gap,
        kind: "temporary-seat-proposal",
        target_role_id: "browser-operator",
        target_role_name: "Browser Operator",
        target_agent_id: "industry-browser-operator-demo",
        requested_surfaces: ["browser"],
        requires_confirmation: true,
        proposal_status: "open",
      },
      pending_proposals: [
        {
          ...staffingFixture.pending_proposals[0],
          kind: "temporary-seat-proposal",
          target_role_name: "Browser Operator",
          target_agent_id: "industry-browser-operator-demo",
          requested_surfaces: ["browser"],
          requires_confirmation: true,
        },
      ],
      temporary_seats: [],
      researcher: null,
    };

    const presentation = buildStaffingPresentation(browserProposalFixture);

    expect(presentation.hasAnyState).toBe(true);
    expect(presentation.activeGap?.badges).toContain("Needs approval");
    expect(presentation.activeGap?.meta).toContain("browser");
    expect(
      presentSeatLifecycleState({
        staffing: browserProposalFixture,
        agentId: "industry-browser-operator-demo",
        employmentMode: "temporary",
      }),
    ).toBe("Pending approval");
  });
});
