import { message } from "antd";
import {
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
  useCallback,
  useEffect,
  useMemo,
  useRef,
} from "react";
import type { IAgentScopeRuntimeWebUIOptions } from "@agentscope-ai/chat/lib/AgentScopeRuntimeWebUI/core/types";
import type { NavigateFunction } from "react-router-dom";
import type {
  IndustryInstanceSummary,
} from "../../api/modules/industry";
import type { DefaultConfig } from "./OptionsPanel/defaultConfig";
import {
  buildIndustryRoleChatBinding,
  openRuntimeChat,
  resolveIndustryExecutionCoreRole,
} from "../../utils/runtimeChat";
import { normalizeSpiderMeshBrand } from "../../utils/brand";
import {
  type RuntimeHealthNotice,
  type RuntimeWaitState,
} from "./runtimeDiagnostics";
import {
  createRuntimeTransport,
  firstNonEmptyString,
  type RuntimeWindowContext,
} from "./runtimeTransport";
import { useChatBindingRecovery } from "./chatBindingRecovery";
import sessionApi from "./sessionApi";
import type { MediaSourceSpec } from "../../api/modules/media";

type UseChatRuntimeStateArgs = {
  activeAgentId: string | null;
  activeIndustryId: string | null;
  activeIndustryRoleId: string | null;
  autoBindingPending: boolean;
  defaultAutoBindAttemptedRef: MutableRefObject<boolean>;
  navigate: NavigateFunction;
  optionsConfig: DefaultConfig;
  requestedIndustryThread: { instanceId: string; roleId?: string | null } | null;
  requestedThreadId: string | null;
  requestedThreadLooksBound: boolean;
  recoveryAttemptsRef: MutableRefObject<Set<string>>;
  pendingMediaSourcesRef: MutableRefObject<MediaSourceSpec[]>;
  clearPendingMediaDraftsRef: MutableRefObject<(() => void) | null>;
  refreshThreadMediaAnalysesRef: MutableRefObject<
    ((threadId?: string | null) => Promise<void>) | null
  >;
  selectedMediaAnalysisIdsRef: MutableRefObject<string[]>;
  setAutoBindingPending: Dispatch<SetStateAction<boolean>>;
  setRuntimeHealthNotice: Dispatch<SetStateAction<RuntimeHealthNotice | null>>;
  setRuntimeWaitState: Dispatch<SetStateAction<RuntimeWaitState | null>>;
  setShowModelPrompt: Dispatch<SetStateAction<boolean>>;
  suggestedTeams: IndustryInstanceSummary[];
  threadBootstrapError: string | null;
  threadBootstrapPending: boolean;
  threadMeta: Record<string, unknown>;
};

type UseChatRuntimeStateResult = {
  agentLabel: string;
  bindingLabel: string | null;
  currentGoal: string;
  executionCoreSuggestions: IndustryInstanceSummary[];
  hasAgentBinding: boolean;
  hasBoundAgentContext: boolean;
  hasIndustryContext: boolean;
  hasSuggestedTeams: boolean;
  industryLabel: string;
  options: IAgentScopeRuntimeWebUIOptions;
  openSuggestedIndustryChat: (
    instance: IndustryInstanceSummary,
  ) => Promise<boolean>;
  roleLabel: string;
  sessionKind: string;
};

declare global {
  interface WindowEventMap {
    "copaw:governance-status-dirty": CustomEvent<void>;
    "copaw:human-assist-dirty": CustomEvent<void>;
  }
}

export function useChatRuntimeState({
  activeAgentId,
  activeIndustryId,
  activeIndustryRoleId,
  autoBindingPending,
  defaultAutoBindAttemptedRef,
  navigate,
  optionsConfig,
  requestedIndustryThread,
  requestedThreadId,
  requestedThreadLooksBound,
  recoveryAttemptsRef,
  pendingMediaSourcesRef,
  clearPendingMediaDraftsRef,
  refreshThreadMediaAnalysesRef,
  selectedMediaAnalysisIdsRef,
  setAutoBindingPending,
  setRuntimeHealthNotice,
  setRuntimeWaitState,
  setShowModelPrompt,
  suggestedTeams,
  threadBootstrapError,
  threadBootstrapPending,
  threadMeta,
}: UseChatRuntimeStateArgs): UseChatRuntimeStateResult {
  const runtimeWindow = window as RuntimeWindowContext;
  const chatRouteAliveRef = useRef(true);

  const threadMetaRef = useRef(threadMeta);
  useEffect(() => {
    threadMetaRef.current = threadMeta;
  }, [threadMeta]);
  useEffect(() => {
    chatRouteAliveRef.current = true;
    return () => {
      chatRouteAliveRef.current = false;
    };
  }, []);

  const options = useMemo(() => {
    const runtimeTransport = createRuntimeTransport({
      runtimeWindow,
      requestedThreadId,
      optionsBaseUrl: optionsConfig?.api?.baseURL,
      getThreadMeta: () => threadMetaRef.current,
      getPendingMediaSources: () => pendingMediaSourcesRef.current,
      clearPendingMediaDrafts: () => clearPendingMediaDraftsRef.current?.(),
      refreshThreadMediaAnalyses: (threadId) =>
        refreshThreadMediaAnalysesRef.current?.(threadId),
      getSelectedMediaAnalysisIds: () => selectedMediaAnalysisIdsRef.current,
      setRuntimeHealthNotice,
      setRuntimeWaitState,
      setShowModelPrompt,
      dispatchGovernanceDirty: () =>
        window.dispatchEvent(new CustomEvent("copaw:governance-status-dirty")),
      dispatchHumanAssistDirty: () =>
        window.dispatchEvent(new CustomEvent("copaw:human-assist-dirty")),
    });

    return {
      ...optionsConfig,
      session: {
        multiple: false,
        api: sessionApi,
      },
      theme: {
        ...optionsConfig.theme,
        locale: "cn",
        leftHeader: {
          ...optionsConfig.theme?.leftHeader,
          logo: "",
          title: "",
        },
      },
      sender: {
        ...optionsConfig.sender,
        disclaimer: "",
      },
      welcome: {
        ...optionsConfig.welcome,
      },
      api: {
        ...optionsConfig.api,
        fetch: runtimeTransport.fetch,
        responseParser: runtimeTransport.responseParser,
        cancel(payload: { session_id: string }) {
          runtimeTransport.cancelSession(payload.session_id);
        },
      },
    } as unknown as IAgentScopeRuntimeWebUIOptions;
  }, [
    optionsConfig,
    pendingMediaSourcesRef,
      clearPendingMediaDraftsRef,
      refreshThreadMediaAnalysesRef,
      requestedThreadId,
      runtimeWindow,
      selectedMediaAnalysisIdsRef,
      setRuntimeHealthNotice,
      setRuntimeWaitState,
      setShowModelPrompt,
  ]);

  const industryLabel =
    typeof threadMeta.industry_label === "string"
      ? normalizeSpiderMeshBrand(threadMeta.industry_label)
      : activeIndustryId || "";
  const roleLabel =
    typeof threadMeta.industry_role_name === "string"
      ? normalizeSpiderMeshBrand(threadMeta.industry_role_name)
      : activeIndustryRoleId || "";
  const sessionKind =
    typeof threadMeta.session_kind === "string"
      ? threadMeta.session_kind
      : requestedIndustryThread
      ? "industry-control-thread"
      : "";
  const agentLabel =
    typeof threadMeta.agent_name === "string"
      ? normalizeSpiderMeshBrand(threadMeta.agent_name)
      : activeAgentId || runtimeWindow.currentUserId || "";
  const currentGoal =
    typeof threadMeta.current_focus === "string"
      ? threadMeta.current_focus
      : "";
  const hasIndustryContext = Boolean(activeIndustryId);
  const hasAgentBinding =
    (typeof threadMeta.agent_id === "string" &&
      threadMeta.agent_id.trim().length > 0) ||
    sessionKind === "industry-agent-chat" ||
    sessionKind === "industry-control-thread";
  const hasBoundAgentContext = hasIndustryContext || hasAgentBinding;
  const hasSuggestedTeams = suggestedTeams.length > 0;
  const bindingLabel =
    industryLabel && roleLabel
      ? `${industryLabel} / ${roleLabel}`
      : firstNonEmptyString(industryLabel, agentLabel, activeAgentId);
  const executionCoreSuggestions = useMemo(
    () =>
      suggestedTeams.filter((instance) =>
        resolveIndustryExecutionCoreRole(instance),
      ),
    [suggestedTeams],
  );

  const openSuggestedIndustryChat = useCallback(
    async (instance: IndustryInstanceSummary): Promise<boolean> => {
      const executionCoreRole = resolveIndustryExecutionCoreRole(instance);
      if (!executionCoreRole) {
        setAutoBindingPending(false);
        return false;
      }
      try {
        await openRuntimeChat(
          buildIndustryRoleChatBinding(instance, executionCoreRole),
          navigate,
          {
            shouldNavigate: () => chatRouteAliveRef.current,
          },
        );
        return true;
      } catch (error) {
        setAutoBindingPending(false);
        message.error(error instanceof Error ? error.message : String(error));
        return false;
      }
    },
    [navigate, setAutoBindingPending],
  );

  useChatBindingRecovery({
    requestedThreadId,
    requestedThreadLooksBound,
    threadBootstrapError,
    threadBootstrapPending,
    autoBindingPending,
    hasBoundAgentContext,
    defaultAutoBindAttemptedRef,
    recoveryAttemptsRef,
    executionCoreSuggestions,
    navigate,
    openSuggestedIndustryChat,
    setAutoBindingPending,
  });

  return {
    agentLabel,
    bindingLabel,
    currentGoal,
    executionCoreSuggestions,
    hasAgentBinding,
    hasBoundAgentContext,
    hasIndustryContext,
    hasSuggestedTeams,
    industryLabel,
    options,
    openSuggestedIndustryChat,
    roleLabel,
    sessionKind,
  };
}
