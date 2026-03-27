import { describe, expect, it } from "vitest";

import {
  employmentModeColor,
  presentEmploymentModeLabel,
  presentRuntimeStatusLabel,
} from "./executionPresentation";

describe("executionPresentation", () => {
  it("uses one shared employment mode color mapping", () => {
    expect(employmentModeColor("temporary")).toBe("orange");
    expect(employmentModeColor("career")).toBe("green");
    expect(employmentModeColor("contractor")).toBe("green");
    expect(employmentModeColor()).toBe("green");
  });

  it("keeps employment mode labels in the shared presentation layer", () => {
    expect(presentEmploymentModeLabel("temporary")).toContain("临时");
    expect(presentEmploymentModeLabel("career")).toContain("岗位");
  });

  it("covers the extended runtime status labels shared by runtime surfaces", () => {
    expect(presentRuntimeStatusLabel("scheduled")).toBe("已排程");
    expect(presentRuntimeStatusLabel("inactive")).toBe("未激活");
    expect(presentRuntimeStatusLabel("archived")).toBe("已归档");
    expect(presentRuntimeStatusLabel("waiting-verification")).toBe("等待验证");
    expect(presentRuntimeStatusLabel("waiting-resource")).toBe("等待资源");
    expect(presentRuntimeStatusLabel("idle-loop")).toBe("空转中");
  });

  it("covers shared governance and rollout statuses used across runtime pages", () => {
    expect(presentRuntimeStatusLabel("approved")).toBe("已批准");
    expect(presentRuntimeStatusLabel("applied")).toBe("已应用");
    expect(presentRuntimeStatusLabel("reviewing")).toBe("审核中");
    expect(presentRuntimeStatusLabel("proposed")).toBe("已提议");
    expect(presentRuntimeStatusLabel("rejected")).toBe("已拒绝");
    expect(presentRuntimeStatusLabel("open")).toBe("待处理");
    expect(presentRuntimeStatusLabel("disabled")).toBe("已禁用");
    expect(presentRuntimeStatusLabel("enabled")).toBe("已启用");
  });
});
