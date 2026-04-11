import type { NavigateFunction } from "react-router-dom";

import api from "../api";
import {
  buildBuddyExecutionCarrierChatBinding,
  openRuntimeChat,
} from "../utils/runtimeChat";
import { writeBuddyProfileId } from "./buddyProfileBinding";
import { resolveBuddyEntryDecision } from "./buddyFlow";

const BUDDY_ONBOARDING_ROUTE = "/buddy-onboarding";

export async function resumeBuddyChatFromProfile(params: {
  profileId: string;
  navigate: NavigateFunction;
  entrySource: string;
  shouldNavigate?: () => boolean;
}): Promise<"opened" | "onboarding"> {
  const profileId = params.profileId.trim();
  if (!profileId) {
    if (!params.shouldNavigate || params.shouldNavigate()) {
      params.navigate(BUDDY_ONBOARDING_ROUTE, { replace: true });
    }
    return "onboarding";
  }

  const surface = await api.getBuddySurface(profileId);
  const resolvedProfileId = surface?.profile?.profile_id;
  if (!resolvedProfileId) {
    if (!params.shouldNavigate || params.shouldNavigate()) {
      params.navigate(BUDDY_ONBOARDING_ROUTE, { replace: true });
    }
    return "onboarding";
  }

  writeBuddyProfileId(resolvedProfileId);

  const decision = resolveBuddyEntryDecision(surface);
  if (decision.mode !== "chat-ready" || !surface.execution_carrier) {
    if (!params.shouldNavigate || params.shouldNavigate()) {
      params.navigate(BUDDY_ONBOARDING_ROUTE, { replace: true });
    }
    return "onboarding";
  }

  const binding = buildBuddyExecutionCarrierChatBinding({
    sessionId: surface.onboarding?.session_id ?? null,
    profileId: resolvedProfileId,
    profileDisplayName: surface.profile.display_name,
    executionCarrier: surface.execution_carrier,
    entrySource: params.entrySource,
  });

  await openRuntimeChat(binding, params.navigate, {
    replace: true,
    shouldNavigate: params.shouldNavigate,
  });
  return "opened";
}
