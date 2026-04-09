import { lazy, type ComponentType, type LazyExoticComponent } from "react";

export type PreloadableRouteConfig = {
  path: string;
  preload?: (() => Promise<unknown>) | undefined;
};

type PreloadableComponent<T extends ComponentType<any>> = LazyExoticComponent<T> & {
  preload: () => Promise<unknown>;
};

export function lazyWithPreload<T extends ComponentType<any>>(
  importer: () => Promise<{ default: T }>,
): PreloadableComponent<T> {
  const Component = lazy(importer) as PreloadableComponent<T>;
  Component.preload = importer;
  return Component;
}

export function resolveRoutePreloadPaths(
  routes: readonly PreloadableRouteConfig[],
  activePathname: string,
): string[] {
  const seen = new Set<string>();
  const next: string[] = [];
  for (const route of routes) {
    if (!route.preload || route.path === activePathname || seen.has(route.path)) {
      continue;
    }
    seen.add(route.path);
    next.push(route.path);
  }
  return next;
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
  activePathname: string,
): () => void {
  const paths = resolveRoutePreloadPaths(routes, activePathname);
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
