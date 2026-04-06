import { describe, expect, it } from "vitest";

import { presentRuntimeStatusLabel } from "../../runtime/executionPresentation";
import {
  MAIN_BRAIN_COCKPIT_TEXT,
  RUNTIME_CENTER_TEXT,
  formatMainBrainSignalLabel,
  localizeRuntimeText,
  formatRouteTitle,
  formatRuntimeSectionLabel,
  formatRuntimeStatus,
} from "./text";

describe("RuntimeCenter text", () => {
  it("reuses shared runtime status copy for common runtime states", () => {
    expect(formatRuntimeStatus("active")).toBe(
      presentRuntimeStatusLabel("active"),
    );
    expect(formatRuntimeStatus("idle")).toBe(presentRuntimeStatusLabel("idle"));
    expect(formatRuntimeStatus("queued")).toBe(
      presentRuntimeStatusLabel("queued"),
    );
    expect(formatRuntimeStatus("reviewing")).toBe(
      presentRuntimeStatusLabel("reviewing"),
    );
    expect(formatRuntimeStatus("enabled")).toBe(
      presentRuntimeStatusLabel("enabled"),
    );
  });

  it("keeps runtime-center-only statuses local", () => {
    expect(formatRuntimeStatus("state-service")).toBe("状态服务");
    expect(formatRuntimeStatus("unavailable")).toBe("未接入");
    expect(formatRuntimeStatus("scheduled")).toBe("已排程");
  });

  it("maps leaf goal detail routes to the neutral work detail title", () => {
    expect(formatRouteTitle("/goals/goal-1/detail")).toBe("事项详情");
    expect(formatRouteTitle("/api/goals/goal-1/detail")).toBe("事项详情");
  });

  it("localizes retired goal service copy to neutral work wording", () => {
    expect(localizeRuntimeText("Goals")).toBe("事项");
    expect(
      localizeRuntimeText("Top-level intent and plan objects from GoalService."),
    ).toBe("来自阶段事项服务的周期事项与执行计划对象。");
  });
  it("does not map retired runtime-center goal aliases to goal detail titles", () => {
    expect(formatRouteTitle("/runtime-center/goals/goal-1")).toBe(
      "/runtime-center/goals/goal-1",
    );
  });

  it("does not keep duplicate detail-label keys on the runtime center surface copy", () => {
    for (const key of [
      "detailSuffix",
      "runtimeDetail",
      "detailLoadFailed",
      "noDetailData",
      "routesTitle",
      "noContent",
      "requestFailed",
      "eyebrow",
      "metricCards",
      "metricEntries",
      "metricDecisions",
      "metricAgents",
      "taskDetail",
      "scheduleDetail",
      "decisionDetail",
      "patchDetail",
      "growthDetail",
      "agentDetail",
      "industryDetail",
      "goalDetail",
    ]) {
      expect(RUNTIME_CENTER_TEXT).not.toHaveProperty(key);
    }
  });

  it("keeps explicit labels for execution-side host surfaces", () => {
    expect(formatRuntimeSectionLabel("host_twin")).toBe("宿主孪生");
    expect(formatRuntimeSectionLabel("workspace_graph")).toBe("工作区图谱");
  });

  it("labels the main-brain cockpit signals explicitly", () => {
    expect(MAIN_BRAIN_COCKPIT_TEXT.title).toBe("主脑今日运行简报");
    expect(formatMainBrainSignalLabel("carrier")).toBe("载体");
    expect(formatMainBrainSignalLabel("current_cycle")).toBe("当前周期");
    expect(formatMainBrainSignalLabel("agent_reports")).toBe("智能体汇报");
    expect(formatMainBrainSignalLabel("patches")).toBe("补丁");
  });
});
