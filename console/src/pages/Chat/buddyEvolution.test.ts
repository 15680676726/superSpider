import { describe, expect, it } from "vitest";

import {
  presentBuddyRarityLabel,
  resolveBuddyEvolutionStage,
  resolveBuddyEvolutionView,
} from "./buddyEvolution";

describe("buddyEvolution", () => {
  it("maps growth thresholds into evolution stages", () => {
    expect(resolveBuddyEvolutionStage({ companionExperience: 0 })).toBe("seed");
    expect(resolveBuddyEvolutionStage({ companionExperience: 45 })).toBe("bonded");
    expect(resolveBuddyEvolutionStage({ companionExperience: 95 })).toBe("capable");
    expect(resolveBuddyEvolutionStage({ companionExperience: 170 })).toBe("seasoned");
    expect(resolveBuddyEvolutionStage({ companionExperience: 250 })).toBe("signature");
  });

  it("builds a stable presentation view from stage and rarity", () => {
    expect(presentBuddyRarityLabel("epic")).toBe("史诗");
    expect(
      resolveBuddyEvolutionView({
        evolutionStage: "seasoned",
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
