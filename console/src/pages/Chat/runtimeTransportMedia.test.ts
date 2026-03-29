import { describe, expect, it } from "vitest";

import { normalizeRuntimeMediaSources } from "./runtimeTransportMedia";

describe("normalizeRuntimeMediaSources", () => {
  it("dedupes runtime media sources by key and preserves the first valid entry for each source", () => {
    const sources = normalizeRuntimeMediaSources([
      null,
      {
        source_kind: "upload",
        source_id: "artifact-1",
        filename: "one.png",
      },
      {
        source_kind: "upload",
        source_id: "artifact-1",
        filename: "duplicate.png",
      },
      {
        source_kind: "url",
        url: "https://example.com/spec",
      },
      {
        source_kind: "url",
        url: "https://example.com/spec",
        filename: "duplicate-url.png",
      },
      {
        source_kind: "upload",
        source_id: "artifact-2",
        filename: "two.png",
      },
    ]);

    expect(sources).toEqual([
      {
        source_kind: "upload",
        source_id: "artifact-1",
        filename: "one.png",
      },
      {
        source_kind: "url",
        url: "https://example.com/spec",
      },
      {
        source_kind: "upload",
        source_id: "artifact-2",
        filename: "two.png",
      },
    ]);
  });
});
