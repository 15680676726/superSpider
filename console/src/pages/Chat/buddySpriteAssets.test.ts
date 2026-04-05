import { describe, expect, it } from "vitest";

import {
  BUDDY_BODY_FRAMES,
  BUDDY_HAT_LINES,
  BUDDY_PRESENCE_AURAS,
  BUDDY_STAGE_AURAS,
} from "./buddySpriteAssets";

describe("buddySpriteAssets", () => {
  it("keeps a donor-scale body asset pack for every buddy species", () => {
    expect(Object.keys(BUDDY_BODY_FRAMES).length).toBeGreaterThanOrEqual(18);
    for (const frames of Object.values(BUDDY_BODY_FRAMES)) {
      expect(frames.length).toBeGreaterThanOrEqual(3);
      for (const frame of frames) {
        expect(frame.length).toBeGreaterThanOrEqual(5);
      }
    }
  });

  it("keeps hat and aura packs available for sprite composition", () => {
    expect(BUDDY_HAT_LINES.crown.trim().length).toBeGreaterThan(0);
    expect(BUDDY_STAGE_AURAS.signature.trim().length).toBeGreaterThan(0);
    expect(BUDDY_PRESENCE_AURAS.celebrating.trim().length).toBeGreaterThan(0);
  });
});
