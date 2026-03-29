import { describe, expect, it } from "vitest";

import {
  presentRecommendationSubsectionTitle,
  resolveReportWorkContextId,
} from "./industryPagePresentation";

describe("industryPagePresentation", () => {
  it("maps capability recommendation subsection titles by canonical section kind", () => {
    expect(
      presentRecommendationSubsectionTitle({
        section_kind: "execution-core",
        section_id: "s-1",
        title: "Execution Core",
        role_name: "Execution Core",
        items: [],
      } as never),
    ).toBe("编排能力");
    expect(
      presentRecommendationSubsectionTitle({
        section_kind: "system-baseline",
        section_id: "s-2",
        title: "System Baseline",
        items: [],
      } as never),
    ).toBe("基础运行");
  });

  it("resolves report work_context_id from top-level field then metadata fallback", () => {
    expect(
      resolveReportWorkContextId({
        report_id: "report-1",
        work_context_id: "work-context-1",
      } as never),
    ).toBe("work-context-1");

    expect(
      resolveReportWorkContextId({
        report_id: "report-2",
        metadata: {
          work_context_id: "work-context-2",
        },
      } as never),
    ).toBe("work-context-2");
  });
});
