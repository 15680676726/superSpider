// @vitest-environment jsdom

import { afterEach, describe, expect, it } from "vitest";

import {
  normalizeBuddyProfileId,
  resolveCanonicalBuddyProfileId,
} from "./buddyProfileBinding";

describe("buddyProfileBinding", () => {
  afterEach(() => {
    window.localStorage.clear();
  });

  it("normalizes buddy profile ids without relying on browser storage", () => {
    expect(normalizeBuddyProfileId("  profile-1  ")).toBe("profile-1");
    expect(normalizeBuddyProfileId("   ")).toBeNull();
    expect(normalizeBuddyProfileId(null)).toBeNull();
  });

  it("resolves the first canonical buddy profile id from provided inputs", () => {
    expect(resolveCanonicalBuddyProfileId(null, "  ", "profile-2", "profile-3")).toBe(
      "profile-2",
    );
    expect(resolveCanonicalBuddyProfileId(null, "")).toBeNull();
  });
});
