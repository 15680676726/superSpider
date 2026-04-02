import { message } from "antd";
import {
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { IAgentScopeRuntimeWebUIOptions } from "@agentscope-ai/chat/lib/AgentScopeRuntimeWebUI/core/types";
import type { NavigateFunction } from "react-router-dom";
import api from "../../api";
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
import {
  hydrateRuntimeSidecarState,
  parseRuntimeSidecarEvent,
  reduceRuntimeSidecarEvent,
  type RuntimeIntentShellSurface,
  type RuntimeSidecarState,
} from "./runtimeSidecarEvents";
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
  approveCommitBusy: boolean;
  approveCommitDecisions: (decisionIds: string[]) => Promise<void>;
  rejectCommitBusy: boolean;
  rejectCommitDecisions: (decisionIds: string[]) => Promise<void>;
  roleLabel: string;
  runtimeCommitState: RuntimeSidecarState;
  runtimeIntentShell: RuntimeIntentShellSurface | null;
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
  suggestedTeams,
  threadBootstrapError,
  threadBootstrapPending,
  threadMeta,
}: UseChatRuntimeStateArgs): UseChatRuntimeStateResult {
  const runtimeWindow = window as RuntimeWindowContext;
  const chatRouteAliveRef = useRef(true);
  const currentControlThreadId = firstNonEmptyString(
    typeof threadMeta.control_thread_id === "string"
      ? threadMeta.control_thread_id
      : null,
    requestedThreadId,
    runtimeWindow.currentThreadId,
  );
  const persistedMainBrainCommit =
    typeof threadMeta.main_brain_commit === "object" &&
    threadMeta.main_brain_commit !== null
      ? (threadMeta.main_brain_commit as Record<string, unknown>)
      : null;
  const hydratedRuntimeCommitState = useMemo(
    () =>
      hydrateRuntimeSidecarState(
        persistedMainBrainCommit,
        currentControlThreadId,
      ),
    [currentControlThreadId, persistedMainBrainCommit],
  );
  const [runtimeCommitState, setRuntimeCommitState] =
    useState<RuntimeSidecarState>(() =>
      hydratedRuntimeCommitState,
    );
  const [approveCommitBusy, setApproveCommitBusy] = useState(false);
  const [rejectCommitBusy, setRejectCommitBusy] = useState(false);

  const threadMetaRef = useRef(threadMeta);
  useEffect(() => {
    threadMetaRef.current = threadMeta;
  }, [threadMeta]);
  useEffect(() => {
    setRuntimeCommitState((currentState) => {
      if (currentState.controlThreadId !== currentControlThreadId) {
        return hydratedRuntimeCommitState;
      }
      if (currentState.currentCommitStatus) {
        return currentState;
      }
      if (hydratedRuntimeCommitState.currentCommitStatus) {
        return hydratedRuntimeCommitState;
      }
      return currentState;
    });
  }, [currentControlThreadId, hydratedRuntimeCommitState]);
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
        responseParser(rawChunk: string) {
          const parsed = runtimeTransport.responseParser(rawChunk);
          const sidecarEvent = parseRuntimeSidecarEvent(
            parsed,
            currentControlThreadId,
          );
          if (sidecarEvent) {
            setRuntimeCommitState((currentState) =>
              reduceRuntimeSidecarEvent(currentState, sidecarEvent),
            );
          }
          return parsed;
        },
        cancel(payload: { session_id: string }) {
          runtimeTransport.cancelSession(payload.session_id);
        },
      },
    } as unknown as IAgentScopeRuntimeWebUIOptions;
  }, [
    optionsConfig,
    pendingMediaSourcesRef,
    clearPendingMediaDraftsRef,
    currentControlThreadId,
    refreshThreadMediaAnalysesRef,
    requestedThreadId,
    runtimeWindow,
    selectedMediaAnalysisIdsRef,
    setRuntimeHealthNotice,
    setRuntimeWaitState,
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
  const commitSnapshotContext = useMemo(
    () => ({
      controlThreadId: currentControlThreadId,
      sessionId: firstNonEmptyString(
        currentControlThreadId,
        requestedThreadId,
        runtimeWindow.currentThreadId,
      ),
      userId: firstNonEmptyString(runtimeWindow.currentUserId),
      agentId:
        typeof threadMeta.agent_id === "string" && threadMeta.agent_id.trim()
          ? threadMeta.agent_id.trim()
          : null,
      workContextId:
        typeof threadMeta.work_context_id === "string" &&
        threadMeta.work_context_id.trim()
          ? threadMeta.work_context_id.trim()
          : null,
    }),
    [
      currentControlThreadId,
      requestedThreadId,
      runtimeWindow.currentThreadId,
      runtimeWindow.currentUserId,
      threadMeta.agent_id,
      threadMeta.work_context_id,
    ],
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

  const resolveGovernanceActor = useCallback(() => {
    return (
      firstNonEmptyString(
        runtimeWindow.currentUserId,
        typeof threadMetaRef.current.agent_id === "string"
          ? threadMetaRef.current.agent_id
          : null,
        "copaw-operator",
      ) || "copaw-operator"
    );
  }, [runtimeWindow.currentUserId]);

  const approveCommitDecisions = useCallback(
    async (decisionIds: string[]) => {
      const normalizedDecisionIds = decisionIds.filter(
        (item) => typeof item === "string" && item.trim().length > 0,
      );
      if (normalizedDecisionIds.length === 0) {
        return;
      }
      setApproveCommitBusy(true);
      try {
        const result = await api.approveRuntimeDecisions({
          decision_ids: normalizedDecisionIds,
          actor: resolveGovernanceActor(),
          execute: true,
          control_thread_id: commitSnapshotContext.controlThreadId || undefined,
          session_id: commitSnapshotContext.sessionId || undefined,
          user_id: commitSnapshotContext.userId || undefined,
          agent_id: commitSnapshotContext.agentId || undefined,
          work_context_id: commitSnapshotContext.workContextId || undefined,
        });
        const firstResult =
          Array.isArray(result.results) && result.results.length > 0
            ? (result.results[0] as Record<string, unknown>)
            : null;
        const output =
          firstResult && typeof firstResult.output === "object"
            ? (firstResult.output as Record<string, unknown>)
            : null;
        setRuntimeCommitState((currentState) =>
          reduceRuntimeSidecarEvent(currentState, {
            event: "committed",
            payload: {
              decision_ids: normalizedDecisionIds,
              decision_id:
                normalizedDecisionIds.length === 1
                  ? normalizedDecisionIds[0]
                  : undefined,
              summary:
                (typeof firstResult?.summary === "string" &&
                firstResult.summary.trim()
                  ? firstResult.summary
                  : "\u5df2\u6279\u51c6\uff0c\u6b63\u5f0f\u63d0\u4ea4\u5df2\u6267\u884c\u3002"),
              record_id:
                typeof output?.record_id === "string"
                  ? output.record_id
                  : undefined,
              control_thread_id: commitSnapshotContext.controlThreadId,
            },
          }),
        );
        window.dispatchEvent(new CustomEvent("copaw:governance-status-dirty"));
      } catch (error) {
        message.error(error instanceof Error ? error.message : String(error));
      } finally {
        setApproveCommitBusy(false);
      }
    },
    [commitSnapshotContext, resolveGovernanceActor],
  );

  const rejectCommitDecisions = useCallback(
    async (decisionIds: string[]) => {
      const normalizedDecisionIds = decisionIds.filter(
        (item) => typeof item === "string" && item.trim().length > 0,
      );
      if (normalizedDecisionIds.length === 0) {
        return;
      }
      setRejectCommitBusy(true);
      try {
        const result = await api.rejectRuntimeDecisions({
          decision_ids: normalizedDecisionIds,
          actor: resolveGovernanceActor(),
          control_thread_id: commitSnapshotContext.controlThreadId || undefined,
          session_id: commitSnapshotContext.sessionId || undefined,
          user_id: commitSnapshotContext.userId || undefined,
          agent_id: commitSnapshotContext.agentId || undefined,
          work_context_id: commitSnapshotContext.workContextId || undefined,
        });
        const firstResult =
          Array.isArray(result.results) && result.results.length > 0
            ? (result.results[0] as Record<string, unknown>)
            : null;
        setRuntimeCommitState((currentState) =>
          reduceRuntimeSidecarEvent(currentState, {
            event: "commit_failed",
            payload: {
              decision_ids: normalizedDecisionIds,
              decision_id:
                normalizedDecisionIds.length === 1
                  ? normalizedDecisionIds[0]
                  : undefined,
              reason: "governance_denied",
              summary:
                (typeof firstResult?.summary === "string" &&
                firstResult.summary.trim()
                  ? firstResult.summary
                  : "\u5f53\u524d\u7a97\u53e3\u5df2\u62d2\u7edd\u8be5\u6b63\u5f0f\u63d0\u4ea4\u52a8\u4f5c\u3002"),
              control_thread_id: commitSnapshotContext.controlThreadId,
            },
          }),
        );
        window.dispatchEvent(new CustomEvent("copaw:governance-status-dirty"));
      } catch (error) {
        message.error(error instanceof Error ? error.message : String(error));
      } finally {
        setRejectCommitBusy(false);
      }
    },
    [commitSnapshotContext, resolveGovernanceActor],
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
    approveCommitBusy,
    approveCommitDecisions,
    rejectCommitBusy,
    rejectCommitDecisions,
    roleLabel,
    runtimeCommitState,
    runtimeIntentShell: runtimeCommitState.currentIntentShell,
    sessionKind,
  };
}
