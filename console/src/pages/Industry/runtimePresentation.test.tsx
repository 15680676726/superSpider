// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { IndustryCapabilityRecommendationSection } from "../../api/modules/industry";
import type { MediaAnalysisSummary } from "../../api/modules/media";
import {
  presentRecommendationSubsectionTitle,
  renderMediaAnalysisList,
} from "./runtimePresentation";

describe("runtimePresentation", () => {
  it("maps recommendation subsection titles by canonical section kind", () => {
    expect(
      presentRecommendationSubsectionTitle({
        section_kind: "execution-core",
        section_id: "s-1",
        title: "Execution Core",
        summary: "",
        items: [],
      } as IndustryCapabilityRecommendationSection),
    ).toBe("编排能力");
    expect(
      presentRecommendationSubsectionTitle({
        section_kind: "system-baseline",
        section_id: "s-2",
        title: "System Baseline",
        summary: "",
        items: [],
      } as IndustryCapabilityRecommendationSection),
    ).toBe("基础运行");
    expect(
      presentRecommendationSubsectionTitle({
        section_kind: "shared",
        section_id: "s-3",
        title: "Shared",
        summary: "",
        items: [],
      } as IndustryCapabilityRecommendationSection),
    ).toBe("多人共用");
  });

  it("renders media analysis empty state copy when no analyses exist", () => {
    render(renderMediaAnalysisList([], { emptyText: "当前预览还没有素材分析。" }));
    expect(screen.getByText("当前预览还没有素材分析。")).toBeInTheDocument();
  });

  it("renders media analysis rows with summary and adopted tag", () => {
    const analyses = [
      {
        analysis_id: "analysis-1",
        entry_point: "industry-preview",
        purpose: "bootstrap",
        source_kind: "url",
        detected_media_type: "article",
        analysis_mode: "standard",
        status: "completed",
        title: "Northwind insight",
        summary: "A structured summary from the analysis pipeline.",
        key_points: ["Point 1", "Point 2"],
        entities: [],
        claims: [],
        recommended_actions: [],
        warnings: [],
        asset_artifact_ids: [],
        derived_artifact_ids: [],
        knowledge_document_ids: [],
        evidence_ids: [],
        metadata: {},
      },
    ] as MediaAnalysisSummary[];

    render(
      renderMediaAnalysisList(analyses, {
        adoptedTag: "已纳入",
      }),
    );

    expect(screen.getByText("Northwind insight")).toBeInTheDocument();
    expect(screen.getByText("A structured summary from the analysis pipeline.")).toBeInTheDocument();
    expect(screen.getByText("已纳入")).toBeInTheDocument();
  });
});
