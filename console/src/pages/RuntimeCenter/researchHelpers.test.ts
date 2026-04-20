import { describe, expect, it } from "vitest";

import type { RuntimeCenterResearchResponse } from "../../api/modules/runtimeCenter";
import { normalizeResearchSessionSummary } from "./researchHelpers";

describe("normalizeResearchSessionSummary", () => {
  it("normalizes retrieval summary and selected hits", () => {
    const summary = normalizeResearchSessionSummary({
      id: "research-session-1",
      status: "running",
      goal: "trace source collection frontdoor",
      round_count: 1,
      latest_status: "frontdoor resolved",
      findings: [],
      sources: [],
      gaps: [],
      conflicts: [],
      retrieval: {
        intent: "repo-trace",
        requested_sources: ["local_repo"],
        mode_sequence: ["symbol", "exact", "semantic"],
        coverage: { local_repo: 2 },
        selected_hits: [
          {
            source_kind: "local_repo",
            provider_kind: "symbol",
            hit_kind: "symbol",
            ref: "src/copaw/app/runtime_bootstrap_domains.py",
            title: "run_source_collection_frontdoor",
            why_matched: "matched requested frontdoor symbol",
          },
        ],
        dropped_hits: [
          {
            source_kind: "local_repo",
            provider_kind: "exact",
            hit_kind: "file",
            ref: "src/copaw/kernel/query_execution_tools.py",
            title: "query_execution_tools.py",
            why_matched: "exact text match",
          },
        ],
      },
    } satisfies RuntimeCenterResearchResponse);

    expect(summary?.retrieval).toEqual({
      intent: "repo-trace",
      requestedSources: ["local_repo"],
      modeSequence: ["symbol", "exact", "semantic"],
      coverage: { local_repo: 2 },
      selectedHits: [
        {
          id: "src/copaw/app/runtime_bootstrap_domains.py",
          sourceKind: "local_repo",
          providerKind: "symbol",
          hitKind: "symbol",
          title: "run_source_collection_frontdoor",
          ref: "src/copaw/app/runtime_bootstrap_domains.py",
          whyMatched: "matched requested frontdoor symbol",
        },
      ],
      droppedHits: [
        {
          id: "src/copaw/kernel/query_execution_tools.py",
          sourceKind: "local_repo",
          providerKind: "exact",
          hitKind: "file",
          title: "query_execution_tools.py",
          ref: "src/copaw/kernel/query_execution_tools.py",
          whyMatched: "exact text match",
        },
      ],
    });
  });
});
