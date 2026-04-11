import type { BuddyEntryResponse } from "../api/modules/buddy";

export const BUDDY_IDENTITY_CENTER_ROUTE = "/buddy-onboarding";

export type BuddyEntryDecision =
  | { mode: "start-onboarding"; sessionId: null; profileId: null }
  | { mode: "resume-onboarding"; sessionId: string | null; profileId: string | null }
  | { mode: "chat-ready"; sessionId: null; profileId: string | null };

function normalizeId(value: string | null | undefined): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

export function resolveBuddyEntryDecision(
  entry: BuddyEntryResponse | null | undefined,
): BuddyEntryDecision {
  if (!entry) {
    return { mode: "start-onboarding", sessionId: null, profileId: null };
  }
  const mode = String(entry.mode || "").trim();
  const profileId = normalizeId(entry.profile_id);
  const sessionId = normalizeId(entry.session_id);
  if (mode === "chat-ready") {
    return { mode: "chat-ready", sessionId: null, profileId };
  }
  if (mode === "resume-onboarding") {
    return { mode: "resume-onboarding", sessionId, profileId };
  }
  return { mode: "start-onboarding", sessionId: null, profileId: null };
}
