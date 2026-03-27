import { describe, expect, it } from "vitest";

import { presentInsightText } from "./presentation";

describe("Insights presentation", () => {
  it("maps retired workflow-template guidance onto automation and fixed SOP copy", () => {
    expect(
      presentInsightText(
        "The current scope has active goals but no visible workflow run context. Package the recurring work into a workflow template or runtime schedule.",
      ),
    ).toBe(
      "当前范围内存在活跃目标，但没有可见的自动化执行上下文。应把这类周期性工作沉淀为固定 SOP 或运行计划。",
    );
  });
});
