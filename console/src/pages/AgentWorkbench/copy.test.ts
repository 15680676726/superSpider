import { describe, expect, it } from "vitest";

import { presentRuntimeStatusLabel } from "../../runtime/executionPresentation";
import { getStatusLabel } from "./copy";

describe("AgentWorkbench copy", () => {
  it("reuses the shared runtime status copy for common runtime states", () => {
    expect(getStatusLabel("active")).toBe(presentRuntimeStatusLabel("active"));
    expect(getStatusLabel("idle")).toBe(presentRuntimeStatusLabel("idle"));
    expect(getStatusLabel("assigned")).toBe(presentRuntimeStatusLabel("assigned"));
    expect(getStatusLabel("approved")).toBe(
      presentRuntimeStatusLabel("approved"),
    );
    expect(getStatusLabel("open")).toBe(presentRuntimeStatusLabel("open"));
  });

  it("keeps workbench-specific statuses local", () => {
    expect(getStatusLabel("scheduled")).toBe("已排期");
    expect(getStatusLabel("warn")).toBe("警告");
  });
});
