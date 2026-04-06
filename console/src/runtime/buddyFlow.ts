import type { BuddySurfaceResponse } from "../api/modules/buddy";

export const BUDDY_IDENTITY_CENTER_ROUTE = "/buddy-onboarding";

export type BuddyEntryDecision =
  | { mode: "start-onboarding"; sessionId: null }
  | { mode: "resume-onboarding"; sessionId: string | null }
  | { mode: "chat-needs-naming"; sessionId: string | null }
  | { mode: "chat-ready"; sessionId: null };

export type BuddyNamingState = {
  needsNaming: boolean;
  sessionId: string | null;
};

function normalizeSessionId(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : null;
}

function resolveCanonicalSessionId(...values: unknown[]): string | null {
  for (const value of values) {
    const normalized = normalizeSessionId(value);
    if (normalized) {
      return normalized;
    }
  }
  return null;
}

function hasProfile(surface: BuddySurfaceResponse | null | undefined): boolean {
  return Boolean(surface?.profile?.profile_id);
}

export function resolveBuddyEntryDecision(
  surface: BuddySurfaceResponse | null | undefined,
): BuddyEntryDecision {
  if (!hasProfile(surface)) {
    return { mode: "start-onboarding", sessionId: null };
  }
  const onboarding = surface?.onboarding;
  const sessionId = onboarding?.session_id ?? null;
  if (!onboarding) {
    return { mode: "resume-onboarding", sessionId };
  }
  if (onboarding.completed) {
    return { mode: "chat-ready", sessionId: null };
  }
  if (onboarding.requires_naming) {
    return { mode: "chat-needs-naming", sessionId };
  }
  return { mode: "resume-onboarding", sessionId };
}

export function resolveBuddyNamingState(
  surface: BuddySurfaceResponse | null | undefined,
  ...fallbackSessionIds: Array<string | null | undefined>
): BuddyNamingState {
  const onboarding = surface?.onboarding;
  return {
    needsNaming: Boolean(onboarding?.requires_naming),
    sessionId: resolveCanonicalSessionId(
      onboarding?.session_id,
      ...fallbackSessionIds,
    ),
  };
}
