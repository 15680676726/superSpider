import { describe, expect, it } from "vitest";

import { presentRuntimeStatusLabel } from "../../runtime/executionPresentation";
import { runtimeStatusColor as sharedRuntimeStatusColor } from "../../runtime/tagSemantics";
import {
  INDUSTRY_EXPERIENCE_TEXT,
  INDUSTRY_TEXT,
  deriveIndustryTeamStatus,
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
  it("does not treat an empty industry as active only because the carrier status is active", () => {
    expect(
      deriveIndustryTeamStatus({
        status: "active",
        execution: null,
        agents: [],
        schedules: [],
      } as never),
    ).toBe("idle");
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
    expect(presentIndustryRuntimeStatus("materialized")).toBe("已生成任务");
    expect(presentIndustryRuntimeStatus("pending_staffing")).toBe("待补位");
    expect(presentIndustryRuntimeStatus("waiting-confirm")).toBe("待确认");
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

  it("frames carrier adjustment around formal direction instead of the human's current profession", () => {
    expect(INDUSTRY_TEXT.formIndustry).toBe("正式方向");
    expect(INDUSTRY_TEXT.formIndustryRequired).toBe("请输入正式方向");
    expect(INDUSTRY_EXPERIENCE_TEXT.prepareBriefHint).toContain("主脑当前执行方向");
    expect(INDUSTRY_EXPERIENCE_TEXT.prepareBriefHint).toContain("不是用户当前职业");
  });
});
