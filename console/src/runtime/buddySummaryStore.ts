import type { BuddySurfaceResponse } from "../api/modules/buddy";
import { api } from "../api";

export const BUDDY_SUMMARY_REFRESH_MS = 5 * 60 * 1000;

export type BuddySummarySnapshot = {
  loading: boolean;
  error: string | null;
  surface: BuddySurfaceResponse | null;
};

type BuddySummaryEntry = BuddySummarySnapshot & {
  listeners: Set<(snapshot: BuddySummarySnapshot) => void>;
  inFlight: Promise<BuddySurfaceResponse | null> | null;
  refreshTimerId: number | null;
};

const buddySummaryEntries = new Map<string, BuddySummaryEntry>();

function createEntry(): BuddySummaryEntry {
  return {
    loading: false,
    error: null,
    surface: null,
    listeners: new Set(),
    inFlight: null,
    refreshTimerId: null,
  };
}

function getOrCreateEntry(profileId: string): BuddySummaryEntry {
  const existing = buddySummaryEntries.get(profileId);
  if (existing) {
    return existing;
  }
  const entry = createEntry();
  buddySummaryEntries.set(profileId, entry);
  return entry;
}

function publish(profileId: string): void {
  const entry = getOrCreateEntry(profileId);
  const snapshot = getBuddySummarySnapshot(profileId);
  entry.listeners.forEach((listener) => listener(snapshot));
}

function stopRefreshTimer(profileId: string): void {
  const entry = buddySummaryEntries.get(profileId);
  if (!entry || entry.refreshTimerId === null) {
    return;
  }
  window.clearInterval(entry.refreshTimerId);
  entry.refreshTimerId = null;
}

function ensureRefreshTimer(profileId: string): void {
  const entry = getOrCreateEntry(profileId);
  if (entry.refreshTimerId !== null || entry.listeners.size === 0) {
    return;
  }
  entry.refreshTimerId = window.setInterval(() => {
    if (typeof document !== "undefined" && document.visibilityState === "hidden") {
      return;
    }
    void refreshBuddySummary(profileId);
  }, BUDDY_SUMMARY_REFRESH_MS);
}

async function fetchBuddySummary(profileId: string): Promise<BuddySurfaceResponse | null> {
  return api.getBuddySurface(profileId);
}

export function getBuddySummarySnapshot(profileId: string): BuddySummarySnapshot {
  const normalizedProfileId = profileId.trim();
  if (!normalizedProfileId) {
    return {
      loading: false,
      error: null,
      surface: null,
    };
  }
  const entry = getOrCreateEntry(normalizedProfileId);
  return {
    loading: entry.loading,
    error: entry.error,
    surface: entry.surface,
  };
}

export async function refreshBuddySummary(
  profileId: string,
): Promise<BuddySurfaceResponse | null> {
  const normalizedProfileId = profileId.trim();
  if (!normalizedProfileId) {
    return null;
  }
  const entry = getOrCreateEntry(normalizedProfileId);
  if (entry.inFlight) {
    return entry.inFlight;
  }

  entry.loading = true;
  entry.error = null;
  publish(normalizedProfileId);

  const request = fetchBuddySummary(normalizedProfileId)
    .then((surface) => {
      entry.surface = surface;
      return surface;
    })
    .catch((error: unknown) => {
      entry.error = error instanceof Error ? error.message : String(error);
      return entry.surface;
    })
    .finally(() => {
      entry.loading = false;
      entry.inFlight = null;
      publish(normalizedProfileId);
    });

  entry.inFlight = request;
  return request;
}

export function seedBuddySummary(
  profileId: string,
  surface: BuddySurfaceResponse | null | undefined,
): void {
  const normalizedProfileId = profileId.trim();
  if (!normalizedProfileId) {
    return;
  }
  const entry = getOrCreateEntry(normalizedProfileId);
  entry.surface = surface ?? null;
  entry.loading = false;
  entry.error = null;
  publish(normalizedProfileId);
}

export function subscribeBuddySummary(
  profileId: string,
  listener: (snapshot: BuddySummarySnapshot) => void,
): () => void {
  const normalizedProfileId = profileId.trim();
  if (!normalizedProfileId) {
    listener({
      loading: false,
      error: null,
      surface: null,
    });
    return () => undefined;
  }

  const entry = getOrCreateEntry(normalizedProfileId);
  entry.listeners.add(listener);
  listener(getBuddySummarySnapshot(normalizedProfileId));
  ensureRefreshTimer(normalizedProfileId);

  if (!entry.surface && !entry.loading) {
    void refreshBuddySummary(normalizedProfileId);
  }

  return () => {
    const currentEntry = buddySummaryEntries.get(normalizedProfileId);
    if (!currentEntry) {
      return;
    }
    currentEntry.listeners.delete(listener);
    if (currentEntry.listeners.size === 0) {
      stopRefreshTimer(normalizedProfileId);
    }
  };
}

export function resetBuddySummaryStoreForTests(): void {
  buddySummaryEntries.forEach((entry) => {
    if (entry.refreshTimerId !== null) {
      window.clearInterval(entry.refreshTimerId);
    }
  });
  buddySummaryEntries.clear();
}
