import { describe, expect, it } from "vitest";

import { getRoutePresentation } from "./routePresentation";

describe("getRoutePresentation", () => {
  it("returns runtime-centered copy for runtime center route", () => {
    const presentation = getRoutePresentation("runtime-center");

    expect(presentation.title).toBe("主脑驾驶舱");
    expect(presentation.groupLabel).toBe("运行中心");
    expect(presentation.shortLabel).toBe("Runtime");
    expect(presentation.description).toContain("运行");
  });

  it("returns buddy-first copy for chat route", () => {
    const presentation = getRoutePresentation("chat");

    expect(presentation.title).toBe("Buddy 聊天主场");
    expect(presentation.shortLabel).toBe("Buddy");
    expect(presentation.description).toContain("主场");
  });
});
