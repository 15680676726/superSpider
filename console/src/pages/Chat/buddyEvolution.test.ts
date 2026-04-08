import { describe, expect, it } from "vitest";

import {
  presentBuddyRarityLabel,
  resolveBuddyEvolutionStage,
  resolveBuddyEvolutionView,
} from "./buddyEvolution";

describe("buddyEvolution", () => {
  it("maps capability points bands into evolution stages", () => {
    expect(resolveBuddyEvolutionStage({ capabilityPoints: 0 })).toBe("seed");
    expect(resolveBuddyEvolutionStage({ capabilityPoints: 20 })).toBe("bonded");
    expect(resolveBuddyEvolutionStage({ capabilityPoints: 40 })).toBe("capable");
    expect(resolveBuddyEvolutionStage({ capabilityPoints: 100 })).toBe("seasoned");
    expect(resolveBuddyEvolutionStage({ capabilityPoints: 200 })).toBe("signature");
  });

  it("ignores capability score when points are available", () => {
    expect(
      resolveBuddyEvolutionStage({
        capabilityPoints: 2,
        capabilityScore: 88,
      }),
    ).toBe("seed");
  });

  it("falls back to old experience thresholds only when points are missing", () => {
    expect(resolveBuddyEvolutionStage({ companionExperience: 170 })).toBe("seasoned");
  });

  it("builds a stable presentation view from stage and rarity", () => {
    expect(presentBuddyRarityLabel("epic")).toBe("史诗");
    expect(
      resolveBuddyEvolutionView({
        evolutionStage: "",
        currentForm: "seasoned",
        capabilityPoints: 40,
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
