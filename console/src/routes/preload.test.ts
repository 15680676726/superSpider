import { describe, expect, it, vi } from "vitest";

import {
  preloadRoutesByPath,
  resolveLikelyNextRoutePaths,
  resolveRoutePreloadPaths,
  type PreloadableRouteConfig,
} from "./preload";

describe("route preload helpers", () => {
  it("only keeps explicit likely-next routes with preload handlers", () => {
    const routes: PreloadableRouteConfig[] = [
      { path: "/chat", preload: vi.fn() },
      { path: "/runtime-center", preload: vi.fn() },
      { path: "/settings/system" },
      { path: "/runtime-center" as string, preload: vi.fn() },
    ];

    expect(resolveRoutePreloadPaths(routes, ["/runtime-center", "/settings/system"])).toEqual([
      "/runtime-center",
    ]);
  });

  it("only suggests chat after onboarding and nothing for regular page switches", () => {
    expect(resolveLikelyNextRoutePaths("/buddy-onboarding")).toEqual(["/chat"]);
    expect(resolveLikelyNextRoutePaths("/chat")).toEqual([]);
    expect(resolveLikelyNextRoutePaths("/runtime-center")).toEqual([]);
  });

  it("invokes each preload target at most once", async () => {
    const preloadChat = vi.fn(async () => undefined);
    const preloadRuntimeCenter = vi.fn(async () => undefined);
    const routes: PreloadableRouteConfig[] = [
      { path: "/chat", preload: preloadChat },
      { path: "/runtime-center", preload: preloadRuntimeCenter },
      { path: "/runtime-center", preload: vi.fn(async () => undefined) },
    ];

    await preloadRoutesByPath(routes, ["/chat", "/runtime-center", "/chat"]);

    expect(preloadChat).toHaveBeenCalledTimes(1);
    expect(preloadRuntimeCenter).toHaveBeenCalledTimes(1);
  });
});
