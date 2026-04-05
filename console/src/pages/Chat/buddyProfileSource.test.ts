import { describe, expect, it } from "vitest";

import {
  resolveBuddyProfileIdFromBuddySurface,
  resolveRequestedBuddyProfileId,
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
});
