import { describe, expect, it } from "vitest";

import {
  buildBuddyStatusLine,
  presentBuddyEncouragementStyleLabel,
  presentBuddyMoodLabel,
  presentBuddyPresenceLabel,
  presentBuddyStageLabel,
} from "./buddyPresentation";

describe("buddyPresentation", () => {
  it("maps evolution, presence, mood, and encouragement labels into readable text", () => {
    expect(presentBuddyStageLabel("seed")).toBe("初生");
    expect(presentBuddyStageLabel("signature")).toBe("标志形态");
    expect(presentBuddyPresenceLabel("focused")).toBe("专注陪你");
    expect(presentBuddyMoodLabel("determined")).toBe("很坚定");
    expect(presentBuddyEncouragementStyleLabel("old-friend")).toBe("像老朋友");
  });

  it("builds a compact buddy status line", () => {
    expect(
      buildBuddyStatusLine({
        presentation: {
          buddy_name: "Nova",
          presence_state: "focused",
          mood_state: "warm",
        },
        growth: {
          evolution_stage: "bonded",
        },
      } as never),
    ).toBe("Nova · 结伴 · 专注陪你 · 温暖");
  });
});
