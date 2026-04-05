import { describe, expect, it } from "vitest";

import { BUDDY_BODY_FRAMES } from "./base/bodyFrames";
import { BUDDY_PRESENCE_AURAS, BUDDY_STAGE_AURAS } from "./effects/auras";
import { BUDDY_EYES, BUDDY_HATS, BUDDY_SPECIES } from "./forms/catalog";
import { BUDDY_HAT_LINES } from "./parts/hats";

describe("buddy asset namespace", () => {
  it("exposes donor-style base, parts, effects, and forms from the formal asset namespace", () => {
    expect(Object.keys(BUDDY_BODY_FRAMES).length).toBeGreaterThanOrEqual(16);
    expect(BUDDY_SPECIES).toContain("duck");
    expect(BUDDY_HATS).toContain("crown");
    expect(BUDDY_EYES).toContain("@");
    expect(BUDDY_HAT_LINES.crown).toContain("^");
    expect(BUDDY_STAGE_AURAS.signature).toContain("=");
    expect(BUDDY_PRESENCE_AURAS.celebrating).toContain("+");
  });
});
