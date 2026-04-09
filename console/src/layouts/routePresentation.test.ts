import { describe, expect, it } from "vitest";

import { getRoutePresentation } from "./routePresentation";

describe("getRoutePresentation", () => {
  it("returns runtime-centered copy for runtime center route", () => {
    const presentation = getRoutePresentation("runtime-center");

    expect(presentation.title).toBe("主脑驾驶舱");
    expect(presentation.groupLabel).toBe("运行中心");
    expect(presentation.shortLabel).toBe("驾驶舱");
    expect(presentation.description).toContain("运行");
  });

  it("returns super-partner copy for chat route", () => {
    const presentation = getRoutePresentation("chat");

    expect(presentation.title).toBe("超级伙伴聊天主场");
    expect(presentation.shortLabel).toBe("聊天");
    expect(presentation.description).toContain("主场");
  });

  it("treats capability market as a runtime-center first-class entry", () => {
    const presentation = getRoutePresentation("capability-market");

    expect(presentation.title).toBe("能力市场");
    expect(presentation.groupLabel).toBe("运行中心");
    expect(presentation.shortLabel).toBe("市场");
  });
});
