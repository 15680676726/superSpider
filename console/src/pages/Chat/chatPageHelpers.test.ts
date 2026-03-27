import { describe, expect, it } from "vitest";

import { countPendingChatApprovals } from "./chatPageHelpers";

describe("countPendingChatApprovals", () => {
  it("counts only decisions and proposed patches as pending approvals", () => {
    expect(
      countPendingChatApprovals({
        pending_decisions: 3,
        proposed_patches: 2,
        pending_patches: 12,
      }),
    ).toBe(5);
  });

  it("returns zero when governance payload is absent", () => {
    expect(countPendingChatApprovals(null)).toBe(0);
  });
});
