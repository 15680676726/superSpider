import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { IndustryInstanceDetail } from "../../api/modules/industry";
import IndustryPlanningSurface from "./runtimePlanningSurface";

const detail = {
  current_cycle: {
    cycle_id: "cycle-1",
    cycle_kind: "weekly",
    title: "本周增长与交付协调",
    summary: "优先稳住履约，再补获客节奏。",
    status: "active",
    focus_lane_ids: ["lane-growth"],
    backlog_item_ids: ["backlog-1"],
    assignment_ids: ["assignment-1"],
    report_ids: ["report-1"],
    synthesis: {
      latest_findings: [
        {
          report_id: "report-1",
          headline: "Weekly handoff",
          summary: "Need follow-up from the main brain.",
          findings: [],
          uncertainties: [],
          needs_followup: true,
          followup_reason: "Awaiting explicit approval",
        },
      ],
      conflicts: [],
      holes: [],
      recommended_actions: [
        {
          action_id: "action-1",
          action_type: "staffing-follow-up",
          title: "Approve closer staffing",
          summary: "Approve closer seating for live follow-up.",
        },
      ],
      needs_replan: false,
      control_core_contract: ["synthesize-before-reassign"],
    },
  },
  lanes: [
    {
      lane_id: "lane-growth",
      lane_key: "growth",
      title: "增长获客",
      summary: "推进新增获客。",
      status: "active",
      priority: 3,
      metadata: {},
    },
  ],
  assignments: [],
  agent_reports: [],
  evidence: [],
  decisions: [],
  patches: [],
  staffing: {
    pending_proposals: [],
    temporary_seats: [],
    researcher: {
      pending_signal_count: 0,
    },
  },
} as unknown as IndustryInstanceDetail;

describe("IndustryPlanningSurface", () => {
  it("localizes synthesis follow-up and recommended action copy", () => {
    render(<IndustryPlanningSurface detail={detail} locale="zh-CN" />);

    expect(screen.getByText(/等待明确批准/)).toBeTruthy();
    expect(screen.getByText(/批准补充岗位编制/)).toBeTruthy();
    expect(screen.getByText("控制契约")).toBeTruthy();
    expect(screen.queryByText("Approve closer staffing")).toBeNull();
    expect(screen.queryByText("Awaiting explicit approval")).toBeNull();
  });
});
