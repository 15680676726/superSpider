import { describe, expect, it } from "vitest";

import { presentRuntimeStatusLabel } from "../../runtime/executionPresentation";
import { runtimeStatusColor as sharedRuntimeStatusColor } from "../../runtime/tagSemantics";
import {
  INDUSTRY_TEXT,
  formatIndustryDetailStats,
  formatIndustryDisplayToken,
  presentIndustryEmploymentMode,
  presentIndustryReadinessStatus,
  presentIndustryRuntimeStatus,
  runtimeStatusColor,
} from "./pageHelpers";

describe("formatIndustryDetailStats", () => {
  it("drops goal counts from runtime detail stats while keeping the runtime chain counts", () => {
    const summary = formatIndustryDetailStats({
      goal_count: 9,
      agent_count: 3,
      schedule_count: 4,
      lane_count: 5,
      backlog_count: 6,
      assignment_count: 7,
    });

    expect(summary).not.toContain(INDUSTRY_TEXT.metricGoals);
    expect(summary).toContain(INDUSTRY_TEXT.metricAgents);
    expect(summary).toContain(INDUSTRY_TEXT.metricSchedules);
    expect(summary).toContain("泳道 5");
    expect(summary).toContain("待办 6");
    expect(summary).toContain("派单 7");
  });
});

describe("industry page helpers", () => {
  it("centralizes runtime-first status copy in the shared formatter", () => {
    expect(presentIndustryRuntimeStatus("executing")).toContain("执行");
    expect(presentIndustryRuntimeStatus("")).toBe(presentIndustryRuntimeStatus("active"));
    expect(presentIndustryRuntimeStatus("scheduled")).toBe(
      presentRuntimeStatusLabel("scheduled"),
    );
    expect(presentIndustryRuntimeStatus("waiting-resource")).toBe(
      presentRuntimeStatusLabel("waiting-resource"),
    );
  });

  it("normalizes display tokens and falls back for empty values", () => {
    expect(formatIndustryDisplayToken("waiting_confirm")).toBe("waiting confirm");
    expect(formatIndustryDisplayToken("")).toBe("-");
  });

  it("keeps employment and readiness labels in the shared helper layer", () => {
    expect(presentIndustryEmploymentMode("temporary")).toContain("临时");
    expect(presentIndustryReadinessStatus("missing")).toBe(INDUSTRY_TEXT.readinessBlocked);
    expect(presentIndustryReadinessStatus("warning")).toBe(INDUSTRY_TEXT.readinessWarning);
    expect(presentIndustryReadinessStatus("ready")).toBe(INDUSTRY_TEXT.readinessReady);
  });

  it("reuses the shared runtime status color mapping", () => {
    expect(runtimeStatusColor("waiting-resource")).toBe(
      sharedRuntimeStatusColor("waiting-resource"),
    );
    expect(runtimeStatusColor("idle-loop")).toBe(
      sharedRuntimeStatusColor("idle-loop"),
    );
  });
});
