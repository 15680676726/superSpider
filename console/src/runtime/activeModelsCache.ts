import type { ActiveModelsInfo } from "../api/types/provider";

const ACTIVE_MODELS_CACHE_TTL_MS = 30_000;

type ActiveModelsCacheEntry = {
  fetchedAt: number;
  value: ActiveModelsInfo | null;
};

const activeModelsCache: ActiveModelsCacheEntry = {
  fetchedAt: 0,
  value: null,
};

export function getCachedActiveModels(
  options?: { now?: number; ttlMs?: number },
): ActiveModelsInfo | null {
  const now = options?.now ?? Date.now();
  const ttlMs = options?.ttlMs ?? ACTIVE_MODELS_CACHE_TTL_MS;
  if (
    activeModelsCache.value &&
    now - activeModelsCache.fetchedAt < ttlMs
  ) {
    return activeModelsCache.value;
  }
  return null;
}

export function setCachedActiveModels(
  value: ActiveModelsInfo | null,
  options?: { now?: number },
): ActiveModelsInfo | null {
  activeModelsCache.fetchedAt = options?.now ?? Date.now();
  activeModelsCache.value = value;
  return value;
}

export function invalidateActiveModelsCache(): void {
  activeModelsCache.fetchedAt = 0;
  activeModelsCache.value = null;
}

export function resetActiveModelsCacheForTests(): void {
  invalidateActiveModelsCache();
}

export { ACTIVE_MODELS_CACHE_TTL_MS };
