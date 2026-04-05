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
  querySessionId: string | null | undefined,
): BuddyNamingState {
  const onboarding = surface?.onboarding;
  return {
    needsNaming: Boolean(onboarding?.requires_naming),
    sessionId: onboarding?.session_id ?? querySessionId ?? null,
  };
}
