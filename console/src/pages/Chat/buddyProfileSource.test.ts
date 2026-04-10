import { describe, expect, it } from "vitest";

import {
  mergeBuddyProfileIntoThreadMeta,
  resolveBuddyProfileIdFromBuddySurface,
  resolveRequestedBuddyProfileId,
  shouldLoadBuddySurface,
  resolveBuddySurfaceProfileRequest,
  resolveThreadBuddyProfileId,
} from "./buddyProfileSource";

describe("buddyProfileSource", () => {
  it("uses only the explicit chat entry binding as the requested buddy profile id", () => {
    expect(resolveRequestedBuddyProfileId("  profile-query  ")).toBe("profile-query");
    expect(resolveRequestedBuddyProfileId("   ")).toBeNull();
    expect(resolveRequestedBuddyProfileId(null)).toBeNull();
  });

  it("prefers the canonical surface profile over the requested id without any browser storage fallback", () => {
    expect(
      resolveBuddyProfileIdFromBuddySurface({
        requestedProfileId: "profile-query",
        surfaceProfileId: "profile-canonical",
      }),
    ).toBe("profile-canonical");
    expect(
      resolveBuddyProfileIdFromBuddySurface({
        requestedProfileId: "profile-query",
        surfaceProfileId: null,
      }),
    ).toBe("profile-query");
    expect(
      resolveBuddyProfileIdFromBuddySurface({
        requestedProfileId: null,
        surfaceProfileId: null,
      }),
    ).toBeNull();
  });

  it("prefers the canonical thread buddy profile over the query when requesting buddy surface", () => {
    expect(
      resolveBuddySurfaceProfileRequest({
        threadMeta: { buddy_profile_id: "profile-thread" },
        requestedProfileId: "profile-query",
      }),
    ).toBe("profile-thread");
    expect(
      resolveBuddySurfaceProfileRequest({
        threadMeta: {},
        requestedProfileId: "profile-query",
      }),
    ).toBe("profile-query");
  });

  it("only loads buddy surface when a canonical buddy profile id exists", () => {
    expect(shouldLoadBuddySurface("profile-1")).toBe(true);
    expect(shouldLoadBuddySurface("   ")).toBe(false);
    expect(shouldLoadBuddySurface(null)).toBe(false);
  });

  it("does not overwrite a canonical thread buddy profile id with a query fallback", () => {
    expect(resolveThreadBuddyProfileId({ buddy_profile_id: "profile-thread" })).toBe(
      "profile-thread",
    );
    expect(
      mergeBuddyProfileIntoThreadMeta({
        threadMeta: { buddy_profile_id: "profile-thread", owner_scope: "profile-thread" },
        requestedProfileId: "profile-query",
      }),
    ).toEqual({
      buddy_profile_id: "profile-thread",
      owner_scope: "profile-thread",
    });
    expect(
      mergeBuddyProfileIntoThreadMeta({
        threadMeta: { owner_scope: "profile-query" },
        requestedProfileId: "profile-query",
      }),
    ).toEqual({
      owner_scope: "profile-query",
      buddy_profile_id: "profile-query",
    });
  });
});
