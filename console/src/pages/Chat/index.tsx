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
  type RuntimeWaitState,
} from "./runtimeDiagnostics";
import sessionApi from "./sessionApi";
import { ChatComposerAdapter } from "./ChatComposerAdapter";
import { ChatHumanAssistPanel } from "./ChatHumanAssistPanel";
import { ChatRuntimeSidebar } from "./ChatRuntimeSidebar";
import { useChatMedia } from "./useChatMedia";
import { useChatRuntimeState } from "./useChatRuntimeState";
import styles from "./index.module.less";
import { useRuntimeBinding } from "./useRuntimeBinding";

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

  const {
    activeAgentId,
    activeChatThreadId,
    activeIndustryId,
    activeIndustryRoleId,
    openWorkbench,
    requestedIndustryThread,
    requestedThreadLooksBound,
  } = useRuntimeBinding({
    navigate,
    requestedThreadId,
    threadMeta,
    windowThreadId: window.currentThreadId,
  });

  const [autoBindingPending, setAutoBindingPending] = useState(!Boolean(requestedThreadId));
  const [runtimeWaitState, setRuntimeWaitState] = useState<RuntimeWaitState | null>(null);
  const [runtimeHealthNotice, setRuntimeHealthNotice] = useState<RuntimeHealthNotice | null>(null);
  const [runtimeWaitClock, setRuntimeWaitClock] = useState(() => Date.now());
  const [governanceStatus, setGovernanceStatus] = useState<GovernanceStatus | null>(null);
  const recoveryAttemptsRef = useRef<Set<string>>(new Set());
  const defaultAutoBindAttemptedRef = useRef(false);
  const optionsConfig: OptionsConfig = defaultConfig;
  const activeModels = useModelStore((s) => s.activeModels);
  const refreshActiveModels = useModelStore((s) => s.refreshActiveModels);

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
  } = useChatMedia({ activeChatThreadId });

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
  }, [requestedThreadId]);

  useEffect(() => { void refreshActiveModels(); }, [refreshActiveModels]);

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
    if (requestedThreadId) defaultAutoBindAttemptedRef.current = false;
  }, [requestedThreadId]);

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
  });

  const {
    bindingLabel,
    currentGoal,
    executionCoreSuggestions,
    hasBoundAgentContext,
    hasSuggestedTeams,
    options,
    openSuggestedIndustryChat,
    sessionKind,
  } = runtimeState;

  const {
    focusLabel,
    focusHint,
    threadKindLabel,
    threadKindHint,
    writebackLabel,
    writebackHint,
  } = resolveThreadRuntimePresentation({
    currentGoal,
    sessionKind: sessionKind || "",
    threadMeta,
  });

  const effectiveThreadPending = threadBootstrapPending || autoBindingPending;
  const activeWindowThreadId = normalizeThreadId(window.currentThreadId);
  const { shouldRenderChatUi } = resolveChatUiVisibility({
    requestedThreadId,
    activeWindowThreadId,
    requestedThreadLooksBound,
    threadBootstrapError,
    hasBoundAgentContext,
    effectiveThreadPending,
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
        executionCoreSuggestions={executionCoreSuggestions}
        effectiveThreadPending={effectiveThreadPending}
        showModelPrompt={showModelPrompt}
        onCloseModelPrompt={() => setShowModelPrompt(false)}
        onOpenModelSettings={() => {
          setShowModelPrompt(false);
          navigate("/settings/models");
        }}
        onOpenIndustryCenter={() => navigate("/industry")}
        onOpenWorkbench={openWorkbench}
        onReload={() => window.location.reload()}
        onOpenSuggestedIndustryChat={openSuggestedIndustryChat}
      />

      {/* 主聊天区 */}
      {shouldRenderChatUi ? (
        <div className={styles.chatWrap}>
          {/* 顶部状态条 */}
          <ChatRuntimeSidebar
            bindingLabel={bindingLabel}
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
            approvalButtonLabel={approvalButtonLabel}
            onOpenGovernanceApprovals={openGovernanceApprovals}
          />
          <ChatHumanAssistPanel
            activeChatThreadId={activeChatThreadId}
            threadMeta={threadMeta}
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
            <ChatComposerAdapter chatUiKey={chatUiKey} options={options} />

            {/* 媒体附件区 */}
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
          </div>
        </div>
      ) : null}

    </div>
  );
}
