// @vitest-environment jsdom

import { describe, expect, it } from "vitest";

describe("test browser api setup", () => {
  it("provides matchMedia and pseudo-safe getComputedStyle from the shared test setup", () => {
    expect(typeof window.matchMedia).toBe("function");

    const element = document.createElement("div");
    document.body.appendChild(element);

    expect(() => window.getComputedStyle(element, "::before")).not.toThrow();
  });
});
