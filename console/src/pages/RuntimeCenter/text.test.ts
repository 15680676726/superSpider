import { describe, expect, it } from "vitest";

import { presentRuntimeStatusLabel } from "../../runtime/executionPresentation";
import { formatRuntimeStatus } from "./text";

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
});
