// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import MainBrainCockpitPanel, { type MainBrainCockpitPanelProps } from "./MainBrainCockpitPanel";


function createProps(): MainBrainCockpitPanelProps {
  return {
    title: "主脑驾驶舱",
    summaryFields: [],
    morningReport: null,
    eveningReport: null,
    trend: [],
    trace: [],
    approvals: [],
    stageSummary: null,
    dayMode: "day",
    systemManagement: <div>system</div>,
    onApproveApproval: vi.fn(),
    onRejectApproval: vi.fn(),
    onOpenChat: vi.fn(),
    researchSummary: {
      id: "research-session-1",
      status: "running",
      statusLabel: "当前研究中",
      goal: "trace source collection frontdoor",
      roundCount: 1,
      roundLabel: "第 1 轮",
      waitingLogin: false,
      latestStatus: "frontdoor resolved",
      updatedAt: null,
      brief: {
        goal: "trace source collection frontdoor",
        question: "run_source_collection_frontdoor",
        whyNeeded: "verify retrieval read surface",
        doneWhen: "frontdoor chain is visible",
        requestedSources: ["local_repo"],
        scopeType: "work_context",
        scopeId: "ctx-1",
      },
      findings: [],
      sources: [],
      gaps: [],
      conflicts: [],
      retrieval: {
        intent: "repo-trace",
        requestedSources: ["local_repo"],
        modeSequence: ["symbol", "exact", "semantic"],
        coverage: { local_repo: 2 },
        selectedHits: [
          {
            id: "hit-1",
            sourceKind: "local_repo",
            providerKind: "symbol",
            hitKind: "symbol",
            title: "run_source_collection_frontdoor",
            ref: "src/copaw/app/runtime_bootstrap_domains.py",
            whyMatched: "matched requested frontdoor symbol",
          },
        ],
        droppedHits: [],
      },
      writebackTruth: null,
    },
  };
}

describe("MainBrainCockpitPanel retrieval surface", () => {
  it("renders retrieval summary inside the research card", () => {
    render(<MainBrainCockpitPanel {...createProps()} />);

    expect(screen.getByText("repo-trace")).toBeInTheDocument();
    expect(screen.getByText("local_repo")).toBeInTheDocument();
    expect(screen.getByText("symbol -> exact -> semantic")).toBeInTheDocument();
    expect(screen.getAllByText("run_source_collection_frontdoor").length).toBeGreaterThan(0);
  });
});
