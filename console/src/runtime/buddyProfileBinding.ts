const BUDDY_PROFILE_STORAGE_KEY = "copaw.buddy_profile_id";

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

function canUseStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

export function readBuddyProfileId(): string | null {
  if (!canUseStorage()) {
    return null;
  }
  try {
    return normalizeBuddyProfileId(window.localStorage.getItem(BUDDY_PROFILE_STORAGE_KEY));
  } catch {
    return null;
  }
}

export function writeBuddyProfileId(profileId: string | null | undefined): void {
  if (!canUseStorage()) {
    return;
  }
  const normalized = normalizeBuddyProfileId(profileId);
  try {
    if (normalized) {
      window.localStorage.setItem(BUDDY_PROFILE_STORAGE_KEY, normalized);
      return;
    }
    window.localStorage.removeItem(BUDDY_PROFILE_STORAGE_KEY);
  } catch {
    // Ignore storage failures and keep the backend/runtime truth as primary.
  }
}

export function resetBuddyProfileBindingForTests(): void {
  if (!canUseStorage()) {
    return;
  }
  try {
    window.localStorage.removeItem(BUDDY_PROFILE_STORAGE_KEY);
  } catch {
    // Ignore storage failures in test cleanup.
  }
}
