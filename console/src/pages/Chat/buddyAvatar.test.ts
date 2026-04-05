import { describe, expect, it } from "vitest";

import type { BuddySurfaceResponse } from "../../api/modules/buddy";
import {
  BUDDY_SPECIES,
  buildBuddyAvatarView,
  renderBuddyFace,
  renderBuddyAvatarLines,
  resolveBuddyAvatarBones,
  spriteFrameCount,
} from "./buddyAvatar";

function makeSurface(overrides?: Partial<BuddySurfaceResponse>): BuddySurfaceResponse {
  return {
    profile: {
      profile_id: "profile-1",
      display_name: "Alex",
      profession: "Designer",
      current_stage: "transition",
      interests: [],
      strengths: [],
      constraints: [],
      goal_intention: "Grow into a durable creator",
    },
    presentation: {
      profile_id: "profile-1",
      buddy_name: "Nova",
      lifecycle_state: "named",
      presence_state: "available",
      mood_state: "warm",
      current_form: "default",
      rarity: "rare",
      current_goal_summary: "Become a durable creator",
      current_task_summary: "Ship one public proof of work",
      why_now_summary: "Momentum matters",
    },
    growth: {
      profile_id: "profile-1",
      intimacy: 28,
      affinity: 22,
      growth_level: 4,
      companion_experience: 96,
      knowledge_value: 24,
      skill_value: 18,
      pleasant_interaction_score: 35,
      communication_count: 14,
      completed_support_runs: 3,
      completed_assisted_closures: 1,
      evolution_stage: "capable",
      progress_to_next_stage: 52,
    },
    ...overrides,
  } as BuddySurfaceResponse;
}

describe("buddyAvatar", () => {
  it("keeps the broader donor species pool instead of a minimal skeleton subset", () => {
    expect(BUDDY_SPECIES.length).toBeGreaterThanOrEqual(16);
    expect(BUDDY_SPECIES).toContain("duck");
    expect(BUDDY_SPECIES).toContain("robot");
    expect(BUDDY_SPECIES).toContain("ghost");
    expect(BUDDY_SPECIES).toContain("mushroom");
  });

  it("derives stable donor-inspired avatar bones from the buddy surface", () => {
    const surface = makeSurface();

    expect(resolveBuddyAvatarBones(surface)).toEqual(resolveBuddyAvatarBones(surface));
    expect(resolveBuddyAvatarBones(surface)).toEqual(
      expect.objectContaining({
        species: expect.any(String),
        hat: expect.any(String),
        eye: expect.any(String),
        shiny: expect.any(Boolean),
      }),
    );
  });

  it("changes the rendered frame across evolution stages while preserving identity", () => {
    const surface = makeSurface();
    const seedView = buildBuddyAvatarView({
      ...surface,
      growth: {
        ...surface.growth,
        evolution_stage: "seed",
      },
    });
    const signatureView = buildBuddyAvatarView({
      ...surface,
      growth: {
        ...surface.growth,
        evolution_stage: "signature",
      },
      presentation: {
        ...surface.presentation,
        rarity: "signature",
      },
    });

    expect(seedView.species).toBe(signatureView.species);
    expect(seedView.lines).not.toEqual(signatureView.lines);
    expect(signatureView.rarityStars.length).toBeGreaterThan(seedView.rarityStars.length);
  });

  it("changes the rendered frame across visible presence states while preserving identity", () => {
    const surface = makeSurface({
      presentation: {
        ...makeSurface().presentation,
        presence_state: "focused",
      },
    });
    const focusedView = buildBuddyAvatarView(surface);
    const celebratingView = buildBuddyAvatarView({
      ...surface,
      presentation: {
        ...surface.presentation,
        presence_state: "celebrating",
      },
    });
    const restingView = buildBuddyAvatarView({
      ...surface,
      presentation: {
        ...surface.presentation,
        presence_state: "resting",
      },
    });

    expect(focusedView.species).toBe(celebratingView.species);
    expect(focusedView.lines).not.toEqual(celebratingView.lines);
    expect(restingView.lines).not.toEqual(focusedView.lines);
  });

  it("animates the same buddy across ticks for active presence states", () => {
    const surface = makeSurface({
      presentation: {
        ...makeSurface().presentation,
        presence_state: "supporting",
      },
    });
    const frameA = buildBuddyAvatarView(surface, { tick: 0 });
    const frameB = buildBuddyAvatarView(surface, { tick: 1 });
    const frameC = buildBuddyAvatarView(surface, { tick: 2 });

    expect(frameA.species).toBe(frameB.species);
    expect(frameA.lines).not.toEqual(frameB.lines);
    expect(frameB.lines).not.toEqual(frameC.lines);
  });

  it("renders a donor-style sprite with hat and species metadata", () => {
    const surface = makeSurface();
    const avatar = buildBuddyAvatarView(surface);

    expect(avatar.lines).toEqual(
      renderBuddyAvatarLines({
        ...avatar,
        evolutionStage: surface.growth.evolution_stage,
      }),
    );
    expect(avatar.lines.length).toBeGreaterThanOrEqual(4);
    expect(avatar.speciesLabel.length).toBeGreaterThan(0);
    expect(avatar.rarityStars.length).toBeGreaterThan(0);
  });

  it("exposes donor-style face and sprite helpers", () => {
    const surface = makeSurface();
    const avatar = buildBuddyAvatarView(surface);

    expect(renderBuddyFace(avatar)).toContain(avatar.eye);
    expect(spriteFrameCount(avatar.species)).toBeGreaterThanOrEqual(3);
  });

  it("overlays hats and celebratory accents on the sprite top line", () => {
    const lines = renderBuddyAvatarLines({
      species: "robot",
      hat: "crown",
      eye: "@",
      shiny: true,
      evolutionStage: "signature",
      presenceState: "celebrating",
      moodState: "proud",
      frameIndex: 0,
    });

    expect(lines[0]).toMatch(/[\\^+*]/);
  });
});
