import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Alert,
  Button,
  Input,
  Popover,
  Space,
  Spin,
  Tag,
  Tooltip,
} from "antd";
import {
  CheckCircleOutlined,
  DeleteOutlined,
  FileTextOutlined,
  LinkOutlined,
  PaperClipOutlined,
} from "@ant-design/icons";
import { useLocation, useNavigate } from "react-router-dom";

import api from "../../api";
import type { GovernanceStatus } from "../../api";
import type { BuddySurfaceResponse } from "../../api/modules/buddy";
import type { IndustryInstanceSummary } from "../../api/modules/industry";
import type {
  MediaAnalysisSummary,
  MediaSourceSpec,
} from "../../api/modules/media";
import { useModelStore } from "../../stores/useModelStore";
import { resolveMediaTitle } from "../../utils/mediaPresentation";
import type { ChatMediaDraftItem } from "./useChatMedia";
import { ChatAccessGate } from "./ChatAccessGate";
import {
  countPendingChatApprovals,
  normalizeThreadId,
  normalizeThreadMeta,
} from "./chatPageHelpers";
import {
  resolveChatUiKey,
  resolveChatUiVisibility,
} from "./chatRuntimePresentation";
import defaultConfig, { type DefaultConfig } from "./OptionsPanel/defaultConfig";
import { resolveChatNoticeVariant } from "./noticeState";
import { resolveThreadRuntimePresentation } from "./pagePresentation";
import {
  formatRuntimeWaitDescription,
  type RuntimeHealthNotice,
  type RuntimeLifecycleState,
  type RuntimeWaitState,
} from "./runtimeDiagnostics";
import sessionApi from "./sessionApi";
import { ChatComposerAdapter } from "./ChatComposerAdapter";
import { BuddyCompanion } from "./BuddyCompanion";
import { BuddyPanel } from "./BuddyPanel";
import { ChatCommitConfirmationCard } from "./ChatCommitConfirmationCard";
import { ChatHumanAssistPanel } from "./ChatHumanAssistPanel";
import { ChatIntentShellCard } from "./ChatIntentShellCard";
import { ChatRuntimeSidebar } from "./ChatRuntimeSidebar";
import { useChatMedia } from "./useChatMedia";
import { useChatRuntimeState } from "./useChatRuntimeState";
import styles from "./index.module.less";
import { useRuntimeBinding } from "./useRuntimeBinding";
import { resolveCanonicalBuddyProfileId } from "../../runtime/buddyProfileBinding";
import {
  BUDDY_IDENTITY_CENTER_ROUTE,
  resolveBuddyNamingState,
} from "../../runtime/buddyFlow";
import {
  mergeBuddyProfileIntoThreadMeta,
  resolveBuddyProfileIdFromBuddySurface,
  resolveBuddySurfaceProfileRequest,
  resolveRequestedBuddyProfileId,
  resolveThreadBuddyProfileId,
} from "./buddyProfileSource";

interface CustomWindow extends Window {
  currentChannel?: string;
  currentThreadId?: string;
  currentThreadMeta?: Record<string, unknown>;
  currentUserId?: string;
}

declare const window: CustomWindow;

type OptionsConfig = DefaultConfig;

type RuntimeModelsSnapshot = {
  resolved_llm?: { provider_id: string; model: string } | null;
  active_llm?: { provider_id: string; model: string } | null;
  fallback_enabled?: boolean;
  fallback_chain?: unknown[];
  resolution_reason?: string | null;
} | null;

function resolveRuntimeModelPresentation(
  activeModels: RuntimeModelsSnapshot,
): {
  runtimeModelLabel: string;
  runtimeFallbackLabel: string | null;
  runtimeModelHint: string;
} {
  const resolvedRuntimeModel =
    activeModels?.resolved_llm || activeModels?.active_llm || null;
  const runtimeModelLabel = resolvedRuntimeModel
    ? `${resolvedRuntimeModel.provider_id}/${resolvedRuntimeModel.model}`
    : "模型未配置";
  const runtimeFallbackLabel =
    activeModels?.fallback_enabled === false
      ? null
      : activeModels?.fallback_chain?.length
      ? `备用 ${activeModels.fallback_chain.length}`
      : null;
  const runtimeModelHint =
    activeModels?.resolution_reason?.trim() ||
    (runtimeFallbackLabel ? "已启用备用模型" : "当前对话模型");
  return {
    runtimeModelLabel,
    runtimeFallbackLabel,
    runtimeModelHint,
  };
}

function resolveRuntimeWaitPresentation(
  runtimeWaitState: RuntimeWaitState | null,
  runtimeWaitClock: number,
): { runtimeWaitDescription: string | null; runtimeWaitSeconds: number } {
  if (!runtimeWaitState) {
    return {
      runtimeWaitDescription: null,
      runtimeWaitSeconds: 0,
    };
  }
  return {
    runtimeWaitDescription: formatRuntimeWaitDescription(runtimeWaitState),
    runtimeWaitSeconds: Math.max(
      0,
      Math.floor((runtimeWaitClock - runtimeWaitState.startedAt) / 1000),
    ),
  };
}

// ============================================================
// 媒体附件面板
// ============================================================
function MediaPanel({
  mediaError,
  clearMediaError,
  mediaPendingItems,
  removePendingMedia,
  mediaAnalyses,
  selectedMediaAnalysisIds,
  toggleMediaAnalysis,
  mediaBusy,
  mediaLinkValue,
  setMediaLinkValue,
  handleAddMediaLink,
  handleMediaUploadChange,
  uploadMediaInputRef,
}: {
  mediaError: string | null;
  clearMediaError: () => void;
  mediaPendingItems: ChatMediaDraftItem[];
  removePendingMedia: (id: string) => void;
  mediaAnalyses: MediaAnalysisSummary[];
  selectedMediaAnalysisIds: string[];
  toggleMediaAnalysis: (id: string) => void;
  mediaBusy: boolean;
  mediaLinkValue: string;
  setMediaLinkValue: (v: string) => void;
  handleAddMediaLink: () => Promise<void>;
  handleMediaUploadChange: (e: React.ChangeEvent<HTMLInputElement>) => Promise<void>;
  uploadMediaInputRef: React.RefObject<HTMLInputElement | null>;
}) {
  const hasAttachments = mediaPendingItems.length > 0 || mediaAnalyses.length > 0;

  return (
    <div className={styles.mediaPanel}>
      {mediaError ? (
        <Alert
          type="warning"
          showIcon
          message={mediaError}
          closable
          onClose={clearMediaError}
          style={{ marginBottom: 6, borderRadius: 10 }}
        />
      ) : null}

      {hasAttachments ? (
        <div className={styles.attachmentRow}>
          {mediaPendingItems.map((item) => (
            <div key={item.id} className={styles.attachmentChip}>
              <Spin size="small" />
              <span className={styles.attachmentChipLabel}>{resolveMediaTitle(item.source as Partial<MediaSourceSpec>)}</span>
              <button
                type="button"
                className={styles.attachmentChipRemove}
                onClick={() => removePendingMedia(item.id)}
              >
                <DeleteOutlined style={{ fontSize: 11 }} />
              </button>
            </div>
          ))}
          {mediaAnalyses.map((a) => {
            const on = selectedMediaAnalysisIds.includes(a.analysis_id);
            return (
              <Tooltip key={a.analysis_id} title={a.summary ?? "参考材料"} placement="top">
                <div
                  className={`${styles.attachmentChip} ${on ? styles.attachmentChipOn : ""}`}
                  onClick={() => toggleMediaAnalysis(a.analysis_id)}
                >
                  {on ? (
                    <CheckCircleOutlined style={{ fontSize: 12, color: "#C9A84C" }} />
                  ) : (
                    <FileTextOutlined style={{ fontSize: 12 }} />
                  )}
                  <span className={styles.attachmentChipLabel}>{resolveMediaTitle({ ...a, summary: a.summary ?? undefined } as Partial<MediaAnalysisSummary>)}</span>
                </div>
              </Tooltip>
            );
          })}
        </div>
      ) : null}

      <div className={styles.mediaToolbar}>
        <button
          type="button"
          className={styles.mediaToolbarBtn}
          onClick={() => uploadMediaInputRef.current?.click()}
          disabled={mediaBusy}
        >
          <PaperClipOutlined style={{ fontSize: 13 }} />
          <span>上传文件</span>
        </button>

        <Popover
          trigger="click"
          placement="topLeft"
          title="粘贴网页链接"
          content={
            <Space.Compact style={{ width: 300 }}>
              <Input
                size="small"
                placeholder="粘贴文章或文档链接"
                value={mediaLinkValue}
                onChange={(e) => setMediaLinkValue(e.target.value)}
                onPressEnter={() => void handleAddMediaLink()}
              />
              <Button size="small" type="primary" onClick={() => void handleAddMediaLink()}>
                添加
              </Button>
            </Space.Compact>
          }
        >
          <button type="button" className={styles.mediaToolbarBtn} disabled={mediaBusy}>
            <LinkOutlined style={{ fontSize: 13 }} />
            <span>网页链接</span>
          </button>
        </Popover>

        {mediaPendingItems.length > 0 ? (
          <Tag bordered={false} color="processing" style={{ borderRadius: 6, fontSize: 11 }}>
            发送时自动分析
          </Tag>
        ) : null}
      </div>

      <input
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        ref={uploadMediaInputRef as any}
        type="file"
        hidden
        multiple
        accept="video/*,audio/*,.pdf,.doc,.docx,.txt,.md,.markdown,.csv,.tsv,.json,.html,.htm,.xml,.yml,.yaml,.ppt,.pptx,.xlsx,.xls,.rtf"
        onChange={(e) => void handleMediaUploadChange(e)}
      />
    </div>
  );
}

// ============================================================
// 主页面
// ============================================================
export default function ChatPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const requestedThreadId = useMemo(
    () => normalizeThreadId(new URLSearchParams(location.search).get("threadId")),
    [location.search],
  );
  const buddySessionId = useMemo(
    () => new URLSearchParams(location.search).get("buddy_session"),
    [location.search],
  );
  const buddyProfileIdFromQuery = useMemo(
    () => new URLSearchParams(location.search).get("buddy_profile"),
    [location.search],
  );
  const requestedBuddyProfileId = useMemo(
    () => resolveRequestedBuddyProfileId(buddyProfileIdFromQuery),
    [buddyProfileIdFromQuery],
  );
  const [resolvedBuddyProfileId, setResolvedBuddyProfileId] = useState<string | null>(
    () => requestedBuddyProfileId,
  );

  const [showModelPrompt, setShowModelPrompt] = useState(false);
  const [suggestedTeams, setSuggestedTeams] = useState<IndustryInstanceSummary[]>([]);
  const [industryTeamsError, setIndustryTeamsError] = useState<string | null>(null);
  const [threadBootstrapPending, setThreadBootstrapPending] = useState(
    Boolean(requestedThreadId),
  );
  const [threadBootstrapError, setThreadBootstrapError] = useState<string | null>(null);
  const [threadMeta, setThreadMeta] = useState<Record<string, unknown>>(
    normalizeThreadMeta(requestedThreadId ? window.currentThreadMeta : null),
  );
  const canonicalThreadBuddyProfileId = useMemo(
    () => resolveThreadBuddyProfileId(threadMeta),
    [threadMeta],
  );
  const effectiveThreadMeta = useMemo<Record<string, unknown>>(
    () =>
      mergeBuddyProfileIntoThreadMeta({
        threadMeta,
        requestedProfileId: requestedBuddyProfileId,
      }),
    [requestedBuddyProfileId, threadMeta],
  );
  const buddyProfileId = useMemo(
    () =>
      resolveCanonicalBuddyProfileId(
        canonicalThreadBuddyProfileId,
        resolvedBuddyProfileId,
        requestedBuddyProfileId,
      ),
    [canonicalThreadBuddyProfileId, requestedBuddyProfileId, resolvedBuddyProfileId],
  );

  const {
    activeAgentId,
    activeChatThreadId,
    activeIndustryId,
    activeIndustryRoleId,
    requestedThreadLooksBound,
  } = useRuntimeBinding({
    navigate,
    requestedThreadId,
    threadMeta: effectiveThreadMeta,
    windowThreadId: window.currentThreadId,
  });

  const [autoBindingPending, setAutoBindingPending] = useState(!Boolean(requestedThreadId));
  const [runtimeWaitState, setRuntimeWaitState] = useState<RuntimeWaitState | null>(null);
  const [runtimeHealthNotice, setRuntimeHealthNotice] = useState<RuntimeHealthNotice | null>(null);
  const [runtimeLifecycleState, setRuntimeLifecycleState] =
    useState<RuntimeLifecycleState | null>(null);
  const [runtimeWaitClock, setRuntimeWaitClock] = useState(() => Date.now());
  const [governanceStatus, setGovernanceStatus] = useState<GovernanceStatus | null>(null);
  const [buddySurface, setBuddySurface] = useState<BuddySurfaceResponse | null>(null);
  const [buddyPanelOpen, setBuddyPanelOpen] = useState(false);
  const [buddyLoading, setBuddyLoading] = useState(false);
  const [buddyError, setBuddyError] = useState<string | null>(null);
  const [buddyNameDraft, setBuddyNameDraft] = useState("");
  const [buddyNamingBusy, setBuddyNamingBusy] = useState(false);
  const recoveryAttemptsRef = useRef<Set<string>>(new Set());
  const optionsConfig: OptionsConfig = defaultConfig;
  const activeModels = useModelStore((s) => s.activeModels);
  const refreshActiveModels = useModelStore((s) => s.refreshActiveModels);

  const activeWorkContextId =
    typeof effectiveThreadMeta.work_context_id === "string" && effectiveThreadMeta.work_context_id.trim()
      ? effectiveThreadMeta.work_context_id.trim()
      : null;
  const {
    clearMediaError,
    clearPendingMediaDraftsRef,
    handleAddMediaLink,
    handleMediaUploadChange,
    mediaAnalyses,
    mediaBusy,
    mediaError,
    mediaLinkValue,
    mediaPendingItems,
    pendingMediaSourcesRef,
    refreshThreadMediaAnalysesRef,
    removePendingMedia,
    selectedMediaAnalysisIds,
    selectedMediaAnalysisIdsRef,
    setMediaLinkValue,
    toggleMediaAnalysis,
    uploadMediaInputRef,
  } = useChatMedia({ activeChatThreadId, activeWorkContextId });

  const loadGovernanceStatus = useCallback(async () => {
    try { setGovernanceStatus(await api.getGovernanceStatus()); }
    catch { setGovernanceStatus(null); }
  }, []);

  const openGovernanceApprovals = useCallback(() => {
    navigate("/runtime-center?tab=governance");
  }, [navigate]);

  // ---- effects ----
  useEffect(() => {
    if (!runtimeWaitState) return;
    setRuntimeWaitClock(Date.now());
    const t = window.setInterval(() => setRuntimeWaitClock(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [runtimeWaitState]);

  useEffect(() => {
    setRuntimeWaitState(null);
    setRuntimeHealthNotice(null);
    setRuntimeLifecycleState(null);
  }, [requestedThreadId]);

  useEffect(() => { void refreshActiveModels(); }, [refreshActiveModels]);

  const loadBuddySurface = useCallback(async () => {
    setBuddyLoading(true);
    setBuddyError(null);
    try {
      const explicitProfileId =
        resolveBuddySurfaceProfileRequest({
          threadMeta,
          requestedProfileId: requestedBuddyProfileId,
        }) || undefined;
      const surface = await api.getBuddySurface(explicitProfileId);
      setBuddySurface(surface);
      const surfaceProfileId = resolveRequestedBuddyProfileId(
        surface?.profile?.profile_id,
      );
      const nextProfileId = resolveBuddyProfileIdFromBuddySurface({
        requestedProfileId: explicitProfileId,
        surfaceProfileId,
      });
      setResolvedBuddyProfileId(nextProfileId || null);
      setBuddyNameDraft("");
    } catch (error) {
      setBuddySurface(null);
      setResolvedBuddyProfileId(
        resolveCanonicalBuddyProfileId(
          canonicalThreadBuddyProfileId,
          requestedBuddyProfileId,
        ),
      );
      if (error instanceof Error) {
        setBuddyError(error.message);
      }
    } finally {
      setBuddyLoading(false);
    }
  }, [canonicalThreadBuddyProfileId, requestedBuddyProfileId, threadMeta]);

  useEffect(() => {
    void loadBuddySurface();
  }, [loadBuddySurface]);

  const buddyNamingState = useMemo(
    () =>
      resolveBuddyNamingState(
        buddySurface,
        buddySessionId,
        typeof effectiveThreadMeta.buddy_session_id === "string"
          ? effectiveThreadMeta.buddy_session_id
          : null,
      ),
    [buddySessionId, buddySurface, effectiveThreadMeta.buddy_session_id],
  );

  useEffect(() => {
    setResolvedBuddyProfileId(
      resolveCanonicalBuddyProfileId(
        canonicalThreadBuddyProfileId,
        requestedBuddyProfileId,
      ),
    );
  }, [canonicalThreadBuddyProfileId, requestedBuddyProfileId]);

  useEffect(() => {
    if (location.pathname !== "/chat") return;
    void loadGovernanceStatus();
  }, [loadGovernanceStatus, location.key, location.pathname, requestedThreadId]);

  useEffect(() => {
    const onFocus = () => { if (document.visibilityState !== "hidden") void loadGovernanceStatus(); };
    const onVisible = () => { if (document.visibilityState === "visible") void loadGovernanceStatus(); };
    const onDirty = () => void loadGovernanceStatus();
    window.addEventListener("focus", onFocus);
    window.addEventListener("copaw:governance-status-dirty", onDirty);
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("copaw:governance-status-dirty", onDirty);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [loadGovernanceStatus]);

  useEffect(() => {
    if (!requestedThreadId) {
      sessionApi.setPreferredThreadId(null);
      sessionApi.clearBoundThreadContext();
      setThreadBootstrapPending(false);
      setThreadBootstrapError(null);
      setThreadMeta({});
      return;
    }
    if (!requestedThreadLooksBound) {
      sessionApi.setPreferredThreadId(null);
      sessionApi.clearBoundThreadContext(requestedThreadId);
      setThreadBootstrapPending(false);
      setThreadBootstrapError(null);
      setThreadMeta({});
      setAutoBindingPending(true);
      navigate("/chat", { replace: true });
      return;
    }
    setAutoBindingPending(false);
    let cancelled = false;
    setThreadBootstrapPending(true);
    setThreadBootstrapError(null);
    sessionApi.setPreferredThreadId(requestedThreadId);
    void sessionApi.getSession(requestedThreadId)
      .then((thread) => {
        if (!cancelled) setThreadMeta(normalizeThreadMeta((thread as { meta?: Record<string, unknown> }).meta));
      })
      .catch((err) => {
        if (!cancelled) {
          sessionApi.clearBoundThreadContext(requestedThreadId);
          setThreadBootstrapError(err instanceof Error ? err.message : String(err));
          setThreadMeta({});
        }
      })
      .finally(() => { if (!cancelled) setThreadBootstrapPending(false); });
    return () => { cancelled = true; };
  }, [navigate, requestedThreadId, requestedThreadLooksBound]);

  useEffect(() => {
    const sync = (e: Event) => {
      const ce = e as CustomEvent<{ meta?: Record<string, unknown> }>;
      setThreadMeta(normalizeThreadMeta(ce.detail?.meta));
    };
    window.addEventListener("copaw:thread-context", sync);
    return () => window.removeEventListener("copaw:thread-context", sync);
  }, []);

  useEffect(() => {
    if (activeIndustryId) { setSuggestedTeams([]); setIndustryTeamsError(null); return; }
    let cancelled = false;
    setIndustryTeamsError(null);
    void api.listIndustryInstances(3)
      .then((ins) => { if (!cancelled) setSuggestedTeams(Array.isArray(ins) ? ins : []); })
      .catch((err) => { if (!cancelled) { setSuggestedTeams([]); setIndustryTeamsError(err instanceof Error ? err.message : String(err)); } });
    return () => { cancelled = true; };
  }, [activeIndustryId]);

  const runtimeState = useChatRuntimeState({
    activeAgentId,
    activeIndustryId,
    activeIndustryRoleId,
    autoBindingPending,
    navigate,
    optionsConfig,
    requestedThreadId,
    requestedThreadLooksBound,
    recoveryAttemptsRef,
    pendingMediaSourcesRef,
    clearPendingMediaDraftsRef,
    refreshThreadMediaAnalysesRef,
    selectedMediaAnalysisIdsRef,
    setAutoBindingPending,
    setRuntimeHealthNotice,
    setRuntimeLifecycleState,
    setRuntimeWaitState,
    suggestedTeams,
    threadBootstrapError,
    threadBootstrapPending,
    threadMeta: effectiveThreadMeta,
  });

  const {
    bindingLabel,
    currentFocus,
    hasBoundAgentContext,
    hasSuggestedTeams,
    options,
    approveCommitBusy,
    approveCommitDecisions,
    rejectCommitBusy,
    rejectCommitDecisions,
    sessionKind,
    runtimeCommitState,
    runtimeIntentShell,
  } = runtimeState;

  const {
    focusLabel,
    focusHint,
    threadKindLabel,
    threadKindHint,
    writebackLabel,
    writebackHint,
  } = resolveThreadRuntimePresentation({
    currentFocus,
    sessionKind: sessionKind || "",
    threadMeta: effectiveThreadMeta,
  });

  const effectiveThreadPending = threadBootstrapPending || autoBindingPending;
  const activeWindowThreadId = normalizeThreadId(window.currentThreadId);
  const allowUnboundBuddyShell = Boolean(
    buddyNamingState.needsNaming && buddyNamingState.sessionId,
  );
  const hasBuddyNamingGate = allowUnboundBuddyShell;
  const { shouldRenderChatComposer, shouldRenderChatUi } = resolveChatUiVisibility({
    requestedThreadId,
    activeWindowThreadId,
    requestedThreadLooksBound,
    threadBootstrapError,
    hasBoundAgentContext,
    effectiveThreadPending,
    allowUnboundBuddyShell,
    disableComposer: hasBuddyNamingGate,
  });

  const chatNoticeVariant = resolveChatNoticeVariant({
    threadBootstrapPending,
    requestedThreadLooksBound,
    autoBindingPending,
    shouldRenderChatUi,
  });

  const { runtimeWaitDescription, runtimeWaitSeconds } =
    resolveRuntimeWaitPresentation(runtimeWaitState, runtimeWaitClock);
  const { runtimeModelLabel, runtimeFallbackLabel, runtimeModelHint } =
    resolveRuntimeModelPresentation(activeModels);

  const pendingApprovalCount = countPendingChatApprovals(governanceStatus);
  const approvalButtonLabel = pendingApprovalCount > 0 ? `审批(${pendingApprovalCount})` : "审批";

  const chatUiKey = useMemo(
    () =>
      resolveChatUiKey({
        requestedThreadId,
        activeIndustryId,
        activeIndustryRoleId,
        activeAgentId,
      }),
    [activeAgentId, activeIndustryId, activeIndustryRoleId, requestedThreadId],
  );

  const submitBuddyNaming = useCallback(async () => {
    if (!buddyNamingState.sessionId || !buddyNameDraft.trim()) return;
    setBuddyNamingBusy(true);
    try {
      await api.nameBuddy({
        session_id: buddyNamingState.sessionId,
        buddy_name: buddyNameDraft.trim(),
      });
      await loadBuddySurface();
      const params = new URLSearchParams(location.search);
      params.delete("buddy_session");
      if (buddyProfileId) {
        params.set("buddy_profile", buddyProfileId);
      }
      const nextSearch = params.toString();
      navigate(nextSearch ? `/chat?${nextSearch}` : "/chat", { replace: true });
    } catch (error) {
      setBuddyError(error instanceof Error ? error.message : "伙伴命名失败");
    } finally {
      setBuddyNamingBusy(false);
    }
  }, [buddyNameDraft, buddyNamingState.sessionId, buddyProfileId, loadBuddySurface, location.search, navigate]);

  // ============================================================
  return (
    <div className={styles.page}>
      <ChatAccessGate
        chatNoticeVariant={chatNoticeVariant}
        threadBootstrapError={threadBootstrapError}
        autoBindingPending={autoBindingPending}
        requestedThreadId={requestedThreadId}
        industryTeamsError={industryTeamsError}
        hasSuggestedTeams={hasSuggestedTeams}
        effectiveThreadPending={effectiveThreadPending}
        showModelPrompt={showModelPrompt}
        onCloseModelPrompt={() => setShowModelPrompt(false)}
        onOpenModelSettings={() => {
          setShowModelPrompt(false);
          navigate("/settings/models");
        }}
        onOpenIdentityCenter={() => navigate(BUDDY_IDENTITY_CENTER_ROUTE)}
        onReload={() => window.location.reload()}
      />

      {/* 主聊天区 */}
      {shouldRenderChatUi ? (
        <div className={styles.chatWrap}>
          {/* 顶部状态条 */}
          <ChatRuntimeSidebar
            bindingLabel={bindingLabel}
            runtimeIntentShell={runtimeIntentShell}
            threadKindLabel={threadKindLabel}
            threadKindHint={threadKindHint}
            focusLabel={focusLabel}
            focusHint={focusHint}
            writebackLabel={writebackLabel}
            writebackHint={writebackHint}
            runtimeModelLabel={runtimeModelLabel}
            runtimeModelHint={runtimeModelHint}
            runtimeFallbackLabel={runtimeFallbackLabel}
            runtimeWaitState={runtimeWaitState}
            runtimeWaitSeconds={runtimeWaitSeconds}
            runtimeWaitDescription={runtimeWaitDescription}
            runtimeHealthNotice={runtimeHealthNotice}
            runtimeLifecycleState={runtimeLifecycleState}
            approvalButtonLabel={approvalButtonLabel}
            onOpenGovernanceApprovals={openGovernanceApprovals}
          />
          {shouldRenderChatComposer ? (
            <ChatHumanAssistPanel
              activeChatThreadId={activeChatThreadId}
              threadMeta={effectiveThreadMeta}
            />
          ) : null}
          {buddyNamingState.needsNaming && buddyNamingState.sessionId ? (
            <Alert
              type="info"
              showIcon
              className={styles.inlineAlert}
              message="请给你的伙伴起个名字"
              description={(
                <Space direction="vertical" size={8} style={{ width: "100%" }}>
                  <Input
                    value={buddyNameDraft}
                    onChange={(event) => setBuddyNameDraft(event.target.value)}
                    placeholder="它以后会一直以这个名字陪着你"
                    maxLength={40}
                  />
                  <Space>
                    <Button
                      type="primary"
                      onClick={() => void submitBuddyNaming()}
                      loading={buddyNamingBusy}
                      disabled={!buddyNameDraft.trim()}
                    >
                      确认名字
                    </Button>
                  </Space>
                </Space>
              )}
            />
          ) : null}
          <ChatIntentShellCard shell={runtimeIntentShell} />
          <ChatCommitConfirmationCard
            state={runtimeCommitState}
            approveBusy={approveCommitBusy}
            rejectBusy={rejectCommitBusy}
            onApprove={approveCommitDecisions}
            onReject={rejectCommitDecisions}
          />

          {/* 错误提示 */}
          {threadBootstrapError ? (
            <Alert
              type="warning"
              showIcon
              message="线程绑定出现问题"
              description={threadBootstrapError}
              className={styles.inlineAlert}
            />
          ) : null}

          {/* 聊天画布 */}
          <div className={styles.canvas}>
            {buddyLoading ? (
              <div className={styles.buddyLoading}>伙伴正在靠近你…</div>
            ) : null}
            {buddySurface ? (
              <BuddyCompanion
                surface={buddySurface}
                onOpen={() => setBuddyPanelOpen(true)}
              />
            ) : null}
            {shouldRenderChatComposer ? (
              <ChatComposerAdapter chatUiKey={chatUiKey} options={options} />
            ) : null}

            {/* 媒体附件区 */}
            {shouldRenderChatComposer ? (
              <MediaPanel
                mediaError={mediaError}
                clearMediaError={clearMediaError}
                mediaPendingItems={mediaPendingItems}
                removePendingMedia={removePendingMedia}
                mediaAnalyses={mediaAnalyses}
                selectedMediaAnalysisIds={selectedMediaAnalysisIds}
                toggleMediaAnalysis={toggleMediaAnalysis}
                mediaBusy={mediaBusy}
                mediaLinkValue={mediaLinkValue}
                setMediaLinkValue={setMediaLinkValue}
                handleAddMediaLink={handleAddMediaLink}
                handleMediaUploadChange={handleMediaUploadChange}
                uploadMediaInputRef={uploadMediaInputRef}
              />
            ) : null}
          </div>
          <BuddyPanel
            open={buddyPanelOpen}
            surface={buddySurface}
            onClose={() => setBuddyPanelOpen(false)}
          />
          {buddyError ? (
            <Alert
              type="warning"
              showIcon
              message={buddyError}
              className={styles.inlineAlert}
            />
          ) : null}
        </div>
      ) : null}

    </div>
  );
}
