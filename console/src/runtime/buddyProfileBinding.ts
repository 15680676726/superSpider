const BUDDY_PROFILE_STORAGE_KEY = "copaw.buddy_profile_id";
const BUDDY_PROFILE_CHANGED_EVENT = "copaw:buddy-profile-changed";

function normalizeThreadMeta(
  meta: unknown,
): Record<string, unknown> | null {
  if (!meta || typeof meta !== "object" || Array.isArray(meta)) {
    return null;
  }
  return meta as Record<string, unknown>;
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

function canUseStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function dispatchBuddyProfileChanged(profileId: string | null): void {
  if (typeof window === "undefined") {
    return;
  }
  window.dispatchEvent(
    new CustomEvent(BUDDY_PROFILE_CHANGED_EVENT, {
      detail: { profileId },
    }),
  );
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

export function resolveBuddyProfileIdFromThreadMeta(
  threadMeta: unknown,
): string | null {
  const meta = normalizeThreadMeta(threadMeta);
  if (!meta) {
    return null;
  }
  return resolveCanonicalBuddyProfileId(
    typeof meta.buddy_profile_id === "string" ? meta.buddy_profile_id : null,
  );
}

export function readActiveBuddyProfileId(
  threadMeta?: unknown,
): string | null {
  return resolveCanonicalBuddyProfileId(
    resolveBuddyProfileIdFromThreadMeta(threadMeta),
    readBuddyProfileId(),
  );
}

export function writeBuddyProfileId(profileId: string | null | undefined): void {
  if (!canUseStorage()) {
    return;
  }
  const normalized = normalizeBuddyProfileId(profileId);
  try {
    if (normalized) {
      window.localStorage.setItem(BUDDY_PROFILE_STORAGE_KEY, normalized);
      dispatchBuddyProfileChanged(normalized);
      return;
    }
    window.localStorage.removeItem(BUDDY_PROFILE_STORAGE_KEY);
    dispatchBuddyProfileChanged(null);
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
    dispatchBuddyProfileChanged(null);
  } catch {
    // Ignore storage failures in test cleanup.
  }
}

export { BUDDY_PROFILE_CHANGED_EVENT };
