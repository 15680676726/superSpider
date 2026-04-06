import {
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
  useEffect,
} from "react";
import type { NavigateFunction } from "react-router-dom";

import type { IndustryInstanceSummary } from "../../api/modules/industry";
import { parseIndustryThreadId } from "./chatPageHelpers";

type ResolveChatBindingRecoveryActionArgs = {
  requestedThreadId: string | null;
  requestedThreadLooksBound: boolean;
  threadBootstrapError: string | null;
  threadBootstrapPending: boolean;
  autoBindingPending: boolean;
  hasBoundAgentContext: boolean;
  recoveryAttempts: ReadonlySet<string>;
  executionCoreSuggestions: readonly IndustryInstanceSummary[];
};

type BindInstanceRecoveryAction = {
  type: "bind-instance";
  instance: IndustryInstanceSummary;
  recoveryToken: string | null;
  markDefaultAttempt: boolean;
};

type ResetChatRecoveryAction = {
  type: "reset-chat";
  recoveryToken: string;
};

export type ChatBindingRecoveryAction =
  | BindInstanceRecoveryAction
  | ResetChatRecoveryAction
  | null;

function resolveChatBindingRecoveryReason(
  threadBootstrapError: string | null,
): "bootstrap-error" | "missing-owner" {
  return threadBootstrapError ? "bootstrap-error" : "missing-owner";
}

function resolveMatchedExecutionCoreInstance(
  requestedThreadId: string | null,
  executionCoreSuggestions: readonly IndustryInstanceSummary[],
): IndustryInstanceSummary | null {
  const parsedThread = parseIndustryThreadId(requestedThreadId);
  if (!parsedThread) {
    return null;
  }
  return (
    executionCoreSuggestions.find(
      (instance) => instance.instance_id === parsedThread.instanceId,
    ) ?? null
  );
}

export function resolveChatBindingRecoveryAction({
  requestedThreadId,
  requestedThreadLooksBound,
  threadBootstrapError,
  threadBootstrapPending,
  autoBindingPending,
  hasBoundAgentContext,
  recoveryAttempts,
  executionCoreSuggestions,
}: ResolveChatBindingRecoveryActionArgs): ChatBindingRecoveryAction {
  const matchedInstance = resolveMatchedExecutionCoreInstance(
    requestedThreadId,
    executionCoreSuggestions,
  );

  if (
    requestedThreadId &&
    threadBootstrapError &&
    matchedInstance &&
    !recoveryAttempts.has(requestedThreadId)
  ) {
    return {
      type: "bind-instance",
      instance: matchedInstance,
      recoveryToken: requestedThreadId,
      markDefaultAttempt: false,
    };
  }

  if (
    !requestedThreadId ||
    !requestedThreadLooksBound ||
    threadBootstrapPending ||
    autoBindingPending ||
    hasBoundAgentContext
  ) {
    return null;
  }

  const recoveryToken = `rebind:${requestedThreadId}:${resolveChatBindingRecoveryReason(
    threadBootstrapError,
  )}`;
  if (recoveryAttempts.has(recoveryToken)) {
    return null;
  }

  if (matchedInstance) {
    return {
      type: "bind-instance",
      instance: matchedInstance,
      recoveryToken,
      markDefaultAttempt: false,
    };
  }

  return {
    type: "reset-chat",
    recoveryToken,
  };
}

type UseChatBindingRecoveryArgs = Omit<
  ResolveChatBindingRecoveryActionArgs,
  "recoveryAttempts"
> & {
  recoveryAttemptsRef: MutableRefObject<Set<string>>;
  navigate: NavigateFunction;
  openSuggestedIndustryChat: (
    instance: IndustryInstanceSummary,
  ) => Promise<boolean>;
  setAutoBindingPending: Dispatch<SetStateAction<boolean>>;
};

export function useChatBindingRecovery({
  requestedThreadId,
  requestedThreadLooksBound,
  threadBootstrapError,
  threadBootstrapPending,
  autoBindingPending,
  hasBoundAgentContext,
  recoveryAttemptsRef,
  executionCoreSuggestions,
  navigate,
  openSuggestedIndustryChat,
  setAutoBindingPending,
}: UseChatBindingRecoveryArgs) {
  useEffect(() => {
    const action = resolveChatBindingRecoveryAction({
      requestedThreadId,
      requestedThreadLooksBound,
      threadBootstrapError,
      threadBootstrapPending,
      autoBindingPending,
      hasBoundAgentContext,
      recoveryAttempts: recoveryAttemptsRef.current,
      executionCoreSuggestions,
    });

    if (!action) {
      return;
    }

    if (action.recoveryToken) {
      recoveryAttemptsRef.current.add(action.recoveryToken);
    }
    setAutoBindingPending(true);

    if (action.type === "bind-instance") {
      void openSuggestedIndustryChat(action.instance);
      return;
    }

    navigate("/chat", { replace: true });
  }, [
    autoBindingPending,
    executionCoreSuggestions,
    hasBoundAgentContext,
    navigate,
    openSuggestedIndustryChat,
    recoveryAttemptsRef,
    requestedThreadId,
    requestedThreadLooksBound,
    setAutoBindingPending,
    threadBootstrapError,
    threadBootstrapPending,
  ]);
}
