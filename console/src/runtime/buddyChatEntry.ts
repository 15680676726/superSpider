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

  const entry = await api.getBuddyEntry(profileId);
  const decision = resolveBuddyEntryDecision(entry);
  if (decision.mode !== "chat-ready") {
    if (!params.shouldNavigate || params.shouldNavigate()) {
      params.navigate(BUDDY_ONBOARDING_ROUTE, { replace: true });
    }
    return "onboarding";
  }

  const resolvedProfileId = decision.profileId ?? profileId;
  if (!resolvedProfileId) {
    if (!params.shouldNavigate || params.shouldNavigate()) {
      params.navigate(BUDDY_ONBOARDING_ROUTE, { replace: true });
    }
    return "onboarding";
  }

  writeBuddyProfileId(resolvedProfileId);

  const binding = buildBuddyExecutionCarrierChatBinding({
    sessionId: null,
    profileId: resolvedProfileId,
    profileDisplayName: decision.profileDisplayName,
    executionCarrier: decision.executionCarrier,
    entrySource: params.entrySource,
  });

  await openRuntimeChat(binding, params.navigate, {
    replace: true,
    shouldNavigate: params.shouldNavigate,
  });
  return "opened";
}
