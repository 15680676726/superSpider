import { describe, expect, it } from "vitest";

import {
  presentBuddyRarityLabel,
  resolveBuddyEvolutionStage,
  resolveBuddyEvolutionView,
} from "./buddyEvolution";

describe("buddyEvolution", () => {
  it("maps capability score bands into evolution stages", () => {
    expect(resolveBuddyEvolutionStage({ capabilityScore: 0 })).toBe("seed");
    expect(resolveBuddyEvolutionStage({ capabilityScore: 24 })).toBe("bonded");
    expect(resolveBuddyEvolutionStage({ capabilityScore: 45 })).toBe("capable");
    expect(resolveBuddyEvolutionStage({ capabilityScore: 63 })).toBe("seasoned");
    expect(resolveBuddyEvolutionStage({ capabilityScore: 88 })).toBe("signature");
  });

  it("falls back to old experience thresholds only when capability score is missing", () => {
    expect(resolveBuddyEvolutionStage({ companionExperience: 170 })).toBe("seasoned");
  });

  it("builds a stable presentation view from stage and rarity", () => {
    expect(presentBuddyRarityLabel("epic")).toBe("史诗");
    expect(
      resolveBuddyEvolutionView({
        evolutionStage: "",
        currentForm: "seasoned",
        capabilityScore: 20,
        rarity: "epic",
      }),
    ).toEqual(
      expect.objectContaining({
        stage: "seasoned",
        accentTone: "violet",
        rarityLabel: "史诗",
      }),
    );
  });
});
