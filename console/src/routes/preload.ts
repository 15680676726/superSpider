import { lazy, type ComponentType, type LazyExoticComponent } from "react";

export type PreloadableRouteConfig = {
  path: string;
  preload?: (() => Promise<unknown>) | undefined;
};

type PreloadableComponent<TProps extends object> =
  LazyExoticComponent<ComponentType<TProps>> & {
  preload: () => Promise<unknown>;
};

export function lazyWithPreload<TProps extends object>(
  importer: () => Promise<{ default: ComponentType<TProps> }>,
): PreloadableComponent<TProps> {
  const Component = lazy(importer) as PreloadableComponent<TProps>;
  Component.preload = importer;
  return Component;
}

export function resolveRoutePreloadPaths(
  routes: readonly PreloadableRouteConfig[],
  candidatePaths: readonly string[],
): string[] {
  const seen = new Set<string>();
  const next: string[] = [];
  for (const path of candidatePaths) {
    if (seen.has(path)) {
      continue;
    }
    seen.add(path);
    const route = routes.find((item) => item.path === path);
    if (!route?.preload) {
      continue;
    }
    next.push(route.path);
  }
  return next;
}

export function resolveLikelyNextRoutePaths(activePathname: string): string[] {
  if (activePathname === "/buddy-onboarding") {
    return ["/chat"];
  }
  return [];
}

export async function preloadRoutesByPath(
  routes: readonly PreloadableRouteConfig[],
  paths: readonly string[],
): Promise<void> {
  const seen = new Set<string>();
  const pending: Promise<unknown>[] = [];
  for (const path of paths) {
    if (seen.has(path)) {
      continue;
    }
    seen.add(path);
    const route = routes.find((item) => item.path === path);
    if (!route?.preload) {
      continue;
    }
    pending.push(route.preload());
  }
  await Promise.all(pending);
}

export function scheduleRoutePreload(
  routes: readonly PreloadableRouteConfig[],
  candidatePaths: readonly string[],
): () => void {
  const paths = resolveRoutePreloadPaths(routes, candidatePaths);
  if (paths.length === 0) {
    return () => undefined;
  }

  const preload = () => {
    void preloadRoutesByPath(routes, paths);
  };

  if (typeof window !== "undefined" && "requestIdleCallback" in window) {
    const idleWindow = window as Window & {
      requestIdleCallback: (
        callback: IdleRequestCallback,
        options?: IdleRequestOptions,
      ) => number;
      cancelIdleCallback: (handle: number) => void;
    };
    const handle = idleWindow.requestIdleCallback(() => preload(), {
      timeout: 1200,
    });
    return () => idleWindow.cancelIdleCallback(handle);
  }

  const handle = globalThis.setTimeout(preload, 250);
  return () => globalThis.clearTimeout(handle);
}
