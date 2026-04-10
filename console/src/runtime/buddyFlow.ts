import type { BuddySurfaceResponse } from "../api/modules/buddy";

export const BUDDY_IDENTITY_CENTER_ROUTE = "/buddy-onboarding";

export type BuddyEntryDecision =
  | { mode: "start-onboarding"; sessionId: null }
  | { mode: "resume-onboarding"; sessionId: string | null }
  | { mode: "chat-ready"; sessionId: null };

function hasProfile(surface: BuddySurfaceResponse | null | undefined): boolean {
  return Boolean(surface?.profile?.profile_id);
}

function hasExecutionCarrier(
  surface: BuddySurfaceResponse | null | undefined,
): boolean {
  if (!surface?.execution_carrier) {
    return false;
  }
  const instanceId = surface.execution_carrier.instance_id;
  return typeof instanceId === "string" && instanceId.trim().length > 0;
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
  if (onboarding.completed && hasExecutionCarrier(surface)) {
    return { mode: "chat-ready", sessionId: null };
  }
  return { mode: "resume-onboarding", sessionId };
}
