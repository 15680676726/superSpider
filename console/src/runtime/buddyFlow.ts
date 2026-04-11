import type {
  BuddyEntryResponse,
  BuddyExecutionCarrier,
} from "../api/modules/buddy";

export const BUDDY_IDENTITY_CENTER_ROUTE = "/buddy-onboarding";

export type BuddyEntryDecision =
  | { mode: "start-onboarding"; sessionId: null; profileId: null }
  | { mode: "resume-onboarding"; sessionId: string | null; profileId: string | null }
  | {
      mode: "chat-ready";
      sessionId: null;
      profileId: string | null;
      profileDisplayName: string | null;
      executionCarrier: BuddyExecutionCarrier;
    };

function normalizeId(value: string | null | undefined): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function normalizeExecutionCarrier(
  value: BuddyEntryResponse["execution_carrier"],
): BuddyExecutionCarrier | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const instanceId =
    typeof value.instance_id === "string" ? value.instance_id.trim() : "";
  if (!instanceId) {
    return null;
  }
  return value;
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
  const profileDisplayName = normalizeId(entry.profile_display_name);
  const executionCarrier = normalizeExecutionCarrier(entry.execution_carrier);
  if (mode === "chat-ready") {
    if (executionCarrier) {
      return {
        mode: "chat-ready",
        sessionId: null,
        profileId,
        profileDisplayName,
        executionCarrier,
      };
    }
    return { mode: "resume-onboarding", sessionId, profileId };
  }
  if (mode === "resume-onboarding") {
    return { mode: "resume-onboarding", sessionId, profileId };
  }
  return { mode: "start-onboarding", sessionId: null, profileId: null };
}
