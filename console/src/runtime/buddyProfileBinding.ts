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

export function readBuddyProfileId(): string | null {
  const storage = safeStorage();
  if (!storage) {
    return null;
  }
  const value = storage.getItem(BUDDY_PROFILE_STORAGE_KEY);
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

export function writeBuddyProfileId(profileId: string | null | undefined): void {
  const storage = safeStorage();
  if (!storage) {
    return;
  }
  const normalized = typeof profileId === "string" ? profileId.trim() : "";
  if (!normalized) {
    storage.removeItem(BUDDY_PROFILE_STORAGE_KEY);
    return;
  }
  storage.setItem(BUDDY_PROFILE_STORAGE_KEY, normalized);
}

export function resetBuddyProfileBindingForTests(): void {
  writeBuddyProfileId(null);
}
