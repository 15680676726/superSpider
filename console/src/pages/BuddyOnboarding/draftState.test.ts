// @vitest-environment jsdom

import { describe, expect, it } from "vitest";

import {
  clearBuddyOnboardingDraft,
  loadBuddyOnboardingDraft,
  saveBuddyOnboardingDraft,
} from "./draftState";

describe("draftState", () => {
  it("round-trips the onboarding draft", () => {
    clearBuddyOnboardingDraft();

    saveBuddyOnboardingDraft({
      identity: { display_name: "Alex" },
      naming: { buddy_name: "Nova" },
      step: 2,
    });

    expect(loadBuddyOnboardingDraft()).toEqual({
      identity: { display_name: "Alex" },
      naming: { buddy_name: "Nova" },
      step: 2,
    });

    clearBuddyOnboardingDraft();
    expect(loadBuddyOnboardingDraft()).toBeNull();
  });
});
