import { describe, expect, it } from "vitest";

import {
  runtimeRiskColor,
  runtimeRiskLabel,
  runtimeStatusColor,
} from "./tagSemantics";

describe("tagSemantics", () => {
  it("uses one shared runtime risk color mapping", () => {
    expect(runtimeRiskColor("auto")).toBe("default");
    expect(runtimeRiskColor("guarded")).toBe("orange");
    expect(runtimeRiskColor("confirm")).toBe("red");
  });

  it("uses one shared runtime risk label mapping", () => {
    expect(runtimeRiskLabel("auto")).toBe("自动");
    expect(runtimeRiskLabel("guarded")).toBe("守护");
    expect(runtimeRiskLabel("confirm")).toBe("确认");
    expect(runtimeRiskLabel("unknown")).toBe("未知");
    expect(runtimeRiskLabel("custom-risk")).toBe("custom-risk");
  });

  it("uses one shared runtime status color mapping", () => {
    expect(runtimeStatusColor("assigned")).toBe("blue");
    expect(runtimeStatusColor("queued")).toBe("blue");
    expect(runtimeStatusColor("running")).toBe("green");
    expect(runtimeStatusColor("approved")).toBe("green");
    expect(runtimeStatusColor("leased")).toBe("green");
    expect(runtimeStatusColor("pass")).toBe("green");
    expect(runtimeStatusColor("reviewing")).toBe("gold");
    expect(runtimeStatusColor("warn")).toBe("gold");
    expect(runtimeStatusColor("waiting-verification")).toBe("blue");
    expect(runtimeStatusColor("waiting-resource")).toBe("orange");
    expect(runtimeStatusColor("blocked")).toBe("red");
    expect(runtimeStatusColor("terminated")).toBe("red");
    expect(runtimeStatusColor("fail")).toBe("red");
    expect(runtimeStatusColor("degraded")).toBe("red");
    expect(runtimeStatusColor("idle-loop")).toBe("red");
    expect(runtimeStatusColor("idle")).toBe("default");
    expect(runtimeStatusColor("inactive")).toBe("default");
  });
});
