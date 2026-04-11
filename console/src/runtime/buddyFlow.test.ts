import { describe, expect, it } from "vitest";

import {
  BUDDY_IDENTITY_CENTER_ROUTE,
  resolveBuddyEntryDecision,
} from "./buddyFlow";

describe("buddyFlow", () => {
  it("pins the identity center to buddy onboarding", () => {
    expect(BUDDY_IDENTITY_CENTER_ROUTE).toBe("/buddy-onboarding");
  });

  it("defaults to start-onboarding when backend entry is missing", () => {
    const decision = resolveBuddyEntryDecision(null);
    expect(decision).toEqual({
      mode: "start-onboarding",
      sessionId: null,
      profileId: null,
    });
  });

  it("maps backend start-onboarding entry directly", () => {
    const decision = resolveBuddyEntryDecision({
      mode: "start-onboarding",
      profile_id: null,
      session_id: null,
    });
    expect(decision).toEqual({
      mode: "start-onboarding",
      sessionId: null,
      profileId: null,
    });
  });

  it("maps backend resume-onboarding entry directly", () => {
    const decision = resolveBuddyEntryDecision({
      mode: "resume-onboarding",
      profile_id: "profile-1",
      session_id: "session-1",
    });
    expect(decision).toEqual({
      mode: "resume-onboarding",
      sessionId: "session-1",
      profileId: "profile-1",
    });
  });

  it("maps backend chat-ready entry directly", () => {
    const decision = resolveBuddyEntryDecision({
      mode: "chat-ready",
      profile_id: "profile-1",
      session_id: null,
    });
    expect(decision).toEqual({
      mode: "chat-ready",
      sessionId: null,
      profileId: "profile-1",
    });
  });
});
