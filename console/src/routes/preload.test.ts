import { describe, expect, it, vi } from "vitest";

import {
  preloadRoutesByPath,
  resolveRoutePreloadPaths,
  type PreloadableRouteConfig,
} from "./preload";

describe("route preload helpers", () => {
  it("excludes the active route and routes without preload handlers", () => {
    const routes: PreloadableRouteConfig[] = [
      { path: "/chat", preload: vi.fn() },
      { path: "/runtime-center", preload: vi.fn() },
      { path: "/settings/system" },
      { path: "/runtime-center" as string, preload: vi.fn() },
    ];

    expect(resolveRoutePreloadPaths(routes, "/chat")).toEqual([
      "/runtime-center",
    ]);
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
