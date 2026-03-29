import { describe, expect, it } from "vitest";

import { presentRuntimeStatusLabel } from "../../runtime/executionPresentation";
import {
  MAIN_BRAIN_COCKPIT_TEXT,
  formatMainBrainSignalLabel,
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

  it("maps leaf goal detail routes to the goal detail title", () => {
    expect(formatRouteTitle("/goals/goal-1/detail")).toBe("目标详情");
    expect(formatRouteTitle("/api/goals/goal-1/detail")).toBe("目标详情");
  });
  it("does not map retired runtime-center goal aliases to goal detail titles", () => {
    expect(formatRouteTitle("/runtime-center/goals/goal-1")).toBe(
      "/runtime-center/goals/goal-1",
    );
  });

  it("keeps explicit labels for execution-side host surfaces", () => {
    expect(formatRuntimeSectionLabel("host_twin")).toBe("Host Twin");
    expect(formatRuntimeSectionLabel("workspace_graph")).toBe("工作区图谱");
  });

  it("labels the main-brain cockpit signals explicitly", () => {
    expect(MAIN_BRAIN_COCKPIT_TEXT.title).toBe("Main-Brain Cockpit");
    expect(formatMainBrainSignalLabel("carrier")).toBe("Carrier");
    expect(formatMainBrainSignalLabel("current_cycle")).toBe("Current Cycle");
    expect(formatMainBrainSignalLabel("agent_reports")).toBe("Agent Reports");
    expect(formatMainBrainSignalLabel("patches")).toBe("Patches");
  });
});
