// @vitest-environment jsdom

import { afterEach, describe, expect, it } from "vitest";

import {
  normalizeBuddyProfileId,
  readActiveBuddyProfileId,
  readBuddyProfileId,
  resetBuddyProfileBindingForTests,
  resolveCanonicalBuddyProfileId,
  writeBuddyProfileId,
} from "./buddyProfileBinding";

describe("buddyProfileBinding", () => {
  afterEach(() => {
    resetBuddyProfileBindingForTests();
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

  it("reads and writes the canonical buddy profile id through local storage", () => {
    writeBuddyProfileId("  profile-9  ");
    expect(readBuddyProfileId()).toBe("profile-9");

    writeBuddyProfileId("   ");
    expect(readBuddyProfileId()).toBeNull();
  });

  it("prefers the active thread buddy profile over storage when resolving the current buddy", () => {
    writeBuddyProfileId("profile-storage");

    expect(
      readActiveBuddyProfileId({
        buddy_profile_id: "profile-thread",
      }),
    ).toBe("profile-thread");
  });

  it("resets the stored buddy profile id for tests", () => {
    writeBuddyProfileId("profile-12");
    expect(readBuddyProfileId()).toBe("profile-12");

    resetBuddyProfileBindingForTests();
    expect(readBuddyProfileId()).toBeNull();
  });
});
