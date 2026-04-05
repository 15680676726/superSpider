// @vitest-environment jsdom

import { afterEach, describe, expect, it } from "vitest";

import {
  readBuddyProfileId,
  resetBuddyProfileBindingForTests,
  writeBuddyProfileId,
} from "./buddyProfileBinding";

describe("buddyProfileBinding", () => {
  afterEach(() => {
    resetBuddyProfileBindingForTests();
  });

  it("stores and reads trimmed buddy profile ids", () => {
    writeBuddyProfileId("  profile-1  ");

    expect(readBuddyProfileId()).toBe("profile-1");
  });

  it("clears the binding when an empty id is written", () => {
    writeBuddyProfileId("profile-1");
    writeBuddyProfileId("   ");

    expect(readBuddyProfileId()).toBeNull();
  });
});
