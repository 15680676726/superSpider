const BUDDY_PROFILE_STORAGE_KEY = "copaw.buddy_profile_id";

function safeStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function normalizeBuddyProfileId(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : null;
}

export function resolveCanonicalBuddyProfileId(...values: unknown[]): string | null {
  for (const value of values) {
    const normalized = normalizeBuddyProfileId(value);
    if (normalized) {
      return normalized;
    }
  }
  return null;
}

export function readBuddyProfileId(): string | null {
  const storage = safeStorage();
  if (!storage) {
    return null;
  }
  return normalizeBuddyProfileId(storage.getItem(BUDDY_PROFILE_STORAGE_KEY));
}

export function writeBuddyProfileId(profileId: string | null | undefined): void {
  const storage = safeStorage();
  if (!storage) {
    return;
  }
  const normalized = resolveCanonicalBuddyProfileId(profileId);
  if (!normalized) {
    storage.removeItem(BUDDY_PROFILE_STORAGE_KEY);
    return;
  }
  storage.setItem(BUDDY_PROFILE_STORAGE_KEY, normalized);
}

export function resetBuddyProfileBindingForTests(): void {
  writeBuddyProfileId(null);
}
