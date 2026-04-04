import { describe, expect, it } from "vitest";

import {
  buildBuddyStatusLine,
  presentBuddyMoodLabel,
  presentBuddyStageLabel,
} from "./buddyPresentation";

describe("buddyPresentation", () => {
  it("maps evolution and mood labels into readable text", () => {
    expect(presentBuddyStageLabel("seed")).toBe("初生");
    expect(presentBuddyStageLabel("signature")).toBe("标志形态");
    expect(presentBuddyMoodLabel("determined")).toBe("很笃定");
  });

  it("builds a compact buddy status line", () => {
    expect(
      buildBuddyStatusLine({
        presentation: {
          buddy_name: "Nova",
          mood_state: "warm",
        },
        growth: {
          evolution_stage: "bonded",
        },
      } as never),
    ).toContain("Nova");
  });
});

