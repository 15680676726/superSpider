import {
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

import type { IndustryInstanceSummary } from "../../api/modules/industry";
import type {
  MediaAnalysisSummary,
  MediaSourceSpec,
} from "../../api/modules/media";
import { subscribe } from "../../runtime/eventBus";
import { resolveMediaTitle } from "../../utils/mediaPresentation";
import type { ChatMediaDraftItem } from "./useChatMedia";
import { ChatAccessGate } from "./ChatAccessGate";
import {
  normalizeThreadId,
  normalizeThreadMeta,
  resolveChatThreadBootstrapState,
  shouldRefreshBoundThreadFromRuntimeEvent,
} from "./chatPageHelpers";
import {
  resolveChatComposerKey,
  resolveChatUiKey,
  resolveChatUiVisibility,
} from "./chatRuntimePresentation";
import defaultConfig, { type DefaultConfig } from "./OptionsPanel/defaultConfig";
import { resolveChatNoticeVariant } from "./noticeState";
import { type RuntimeWaitState } from "./runtimeDiagnostics";
import sessionApi from "./sessionApi";
import { ChatComposerAdapter } from "./ChatComposerAdapter";
import { ChatIntentShellCard } from "./ChatIntentShellCard";
import { useChatMedia } from "./useChatMedia";
import { useChatRuntimeState } from "./useChatRuntimeState";
import styles from "./index.module.less";
import { useRuntimeBinding } from "./useRuntimeBinding";
import { readBuddyProfileId } from "../../runtime/buddyProfileBinding";
import { resumeBuddyChatFromProfile } from "../../runtime/buddyChatEntry";
import { BUDDY_IDENTITY_CENTER_ROUTE } from "../../runtime/buddyFlow";
import {
  mergeBuddyProfileIntoThreadMeta,
  resolveRequestedBuddyProfileId,
} from "./buddyProfileSource";

interface CustomWindow extends Window {
  currentChannel?: string;
  currentThreadId?: string;
  currentThreadMeta?: Record<string, unknown>;
  currentUserId?: string;
}

declare const window: CustomWindow;

type OptionsConfig = DefaultConfig;
const EMPTY_SUGGESTED_TEAMS: IndustryInstanceSummary[] = [];

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
          message="材料处理失败，请稍后重试。"
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
                    <CheckCircleOutlined style={{ fontSize: 12, color: "#7170FF" }} />
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

  const requestedThreadIdFromQuery = useMemo(
    () => normalizeThreadId(new URLSearchParams(location.search).get("threadId")),
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
  const threadBootstrapState = resolveChatThreadBootstrapState({
    requestedThreadId: requestedThreadIdFromQuery,
    activeThreadId: sessionApi.getActiveThreadId(),
    activeThreadMeta: window.currentThreadMeta,
  });
  const requestedThreadId = threadBootstrapState.effectiveThreadId;

  const [showModelPrompt, setShowModelPrompt] = useState(false);
  const [threadBootstrapPending, setThreadBootstrapPending] = useState(
    threadBootstrapState.initialThreadBootstrapPending,
  );
  const [threadBootstrapError, setThreadBootstrapError] = useState<string | null>(null);
  const [threadMeta, setThreadMeta] = useState<Record<string, unknown>>(
    threadBootstrapState.initialThreadMeta,
  );
  const effectiveThreadMeta = useMemo<Record<string, unknown>>(
    () =>
      mergeBuddyProfileIntoThreadMeta({
        threadMeta,
        requestedProfileId: requestedBuddyProfileId,
      }),
    [requestedBuddyProfileId, threadMeta],
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

  const [autoBindingPending, setAutoBindingPending] = useState(
    threadBootstrapState.initialAutoBindingPending,
  );
  const [, setRuntimeWaitState] = useState<RuntimeWaitState | null>(null);
  const [, setRuntimeHealthNotice] = useState<unknown>(null);
  const [, setRuntimeLifecycleState] = useState<unknown>(null);
  const recoveryAttemptsRef = useRef<Set<string>>(new Set());
  const threadRefreshTimerRef = useRef<number | null>(null);
  const optionsConfig: OptionsConfig = defaultConfig;

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

  // ---- effects ----
  useEffect(() => {
    setRuntimeWaitState(null);
  }, [requestedThreadId]);

  useEffect(() => {
    if (!requestedThreadIdFromQuery) {
      const recoveryTarget = threadBootstrapState.recoveryTarget;
      if (recoveryTarget) {
        sessionApi.setPreferredThreadId(requestedThreadId);
        navigate(recoveryTarget, { replace: true });
        return;
      }
      const storedBuddyProfileId = readBuddyProfileId();
      let cancelled = false;
      setThreadBootstrapError(null);
      setAutoBindingPending(true);
      void resumeBuddyChatFromProfile({
        profileId: storedBuddyProfileId,
        navigate,
        entrySource: "chat-page",
        shouldNavigate: () => !cancelled,
      })
        .catch(() => {
          if (!cancelled) {
            navigate(BUDDY_IDENTITY_CENTER_ROUTE, { replace: true });
          }
        })
        .finally(() => {
          if (!cancelled) {
            setAutoBindingPending(false);
          }
        });
      return () => {
        cancelled = true;
      };
    }
    if (!requestedThreadLooksBound || !requestedThreadId) {
      sessionApi.setPreferredThreadId(null);
      sessionApi.clearBoundThreadContext(requestedThreadId);
      setThreadBootstrapPending(false);
      setThreadBootstrapError(null);
      setThreadMeta({});
      setAutoBindingPending(true);
      navigate("/chat", { replace: true });
      return;
    }
    const activeRequestedThreadId = requestedThreadId;
    setAutoBindingPending(false);
    let cancelled = false;
    setThreadBootstrapPending(true);
    setThreadBootstrapError(null);
    sessionApi.setPreferredThreadId(activeRequestedThreadId);
    void sessionApi.getSession(activeRequestedThreadId)
      .then((thread) => {
        if (!cancelled) setThreadMeta(normalizeThreadMeta((thread as { meta?: Record<string, unknown> }).meta));
      })
      .catch((err) => {
        if (!cancelled) {
          setThreadBootstrapError(err instanceof Error ? err.message : String(err));
        }
      })
      .finally(() => { if (!cancelled) setThreadBootstrapPending(false); });
    return () => { cancelled = true; };
  }, [
    navigate,
    requestedThreadIdFromQuery,
    requestedThreadId,
    requestedThreadLooksBound,
    threadBootstrapState.recoveryTarget,
  ]);

  useEffect(() => {
    const sync = (e: Event) => {
      const ce = e as CustomEvent<{ meta?: Record<string, unknown> }>;
      setThreadMeta(normalizeThreadMeta(ce.detail?.meta));
    };
    window.addEventListener("copaw:thread-context", sync);
    return () => window.removeEventListener("copaw:thread-context", sync);
  }, []);

  useEffect(() => {
    if (!requestedThreadId || !requestedThreadLooksBound) {
      return;
    }
    let cancelled = false;
    const scheduleRefresh = () => {
      if (threadRefreshTimerRef.current !== null) {
        window.clearTimeout(threadRefreshTimerRef.current);
      }
      threadRefreshTimerRef.current = window.setTimeout(() => {
        threadRefreshTimerRef.current = null;
        void sessionApi.getSession(requestedThreadId)
          .then((thread) => {
            if (cancelled) {
              return;
            }
            setThreadMeta(
              normalizeThreadMeta((thread as { meta?: Record<string, unknown> }).meta),
            );
          })
          .catch(() => {
            // Keep the current chat stable when a background refresh misses.
          });
      }, 350);
    };

    const unsubscribe = subscribe("*", (event) => {
      if (
        !shouldRefreshBoundThreadFromRuntimeEvent({
          requestedThreadId,
          requestedThreadLooksBound,
          eventName: event.event_name,
        })
      ) {
        return;
      }
      scheduleRefresh();
    });

    return () => {
      cancelled = true;
      unsubscribe();
      if (threadRefreshTimerRef.current !== null) {
        window.clearTimeout(threadRefreshTimerRef.current);
        threadRefreshTimerRef.current = null;
      }
    };
  }, [requestedThreadId, requestedThreadLooksBound]);

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
    suggestedTeams: EMPTY_SUGGESTED_TEAMS,
    threadBootstrapError,
    threadBootstrapPending,
    threadMeta: effectiveThreadMeta,
  });

  const {
    hasBoundAgentContext,
    hasSuggestedTeams,
    options,
    runtimeCommitState,
    runtimeIntentShell,
  } = runtimeState;

  const effectiveThreadPending = threadBootstrapPending || autoBindingPending;
  const activeWindowThreadId = normalizeThreadId(window.currentThreadId);
  const { shouldRenderChatComposer, shouldRenderChatUi } = resolveChatUiVisibility({
    requestedThreadId,
    activeWindowThreadId,
    requestedThreadLooksBound,
    threadBootstrapError,
    hasBoundAgentContext,
    effectiveThreadPending,
    allowUnboundBuddyShell: false,
    disableComposer: false,
  });

  const chatNoticeVariant = resolveChatNoticeVariant({
    threadBootstrapPending,
    requestedThreadLooksBound,
    autoBindingPending,
    shouldRenderChatUi,
  });

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
  const chatComposerKey = useMemo(
    () =>
      resolveChatComposerKey(
        chatUiKey,
        runtimeCommitState.lastReplyDoneAt,
        runtimeCommitState.lastTerminalResponseAt,
      ),
    [
      chatUiKey,
      runtimeCommitState.lastReplyDoneAt,
      runtimeCommitState.lastTerminalResponseAt,
    ],
  );

  // ============================================================
  return (
    <div className={styles.page}>
      <ChatAccessGate
        chatNoticeVariant={chatNoticeVariant}
        threadBootstrapError={threadBootstrapError}
        autoBindingPending={autoBindingPending}
        requestedThreadId={requestedThreadId}
        industryTeamsError={null}
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
          <ChatIntentShellCard
            shell={runtimeIntentShell}
            onViewDetails={() => navigate("/runtime-center")}
          />
          {runtimeCommitState.currentReplyResult ? (
            <Alert
              type="success"
              showIcon
              message={runtimeCommitState.currentReplyResult.title}
              description={
                <>
                  <div>
                    {runtimeCommitState.currentReplyResult.summary ||
                      "这轮执行已经产出可查看结果。"}
                  </div>
                  {runtimeCommitState.currentReplyResult.resultItems.length > 0 ? (
                    <Space wrap size={[6, 6]} className={styles.replyResultTags}>
                      {runtimeCommitState.currentReplyResult.resultItems.map(
                        (item, index) => (
                          <Tag
                            key={`${item.kind}:${item.ref ?? item.label}:${index}`}
                            className={styles.replyResultTag}
                            title={item.summary ?? item.label}
                          >
                            {item.label}
                          </Tag>
                        ),
                      )}
                    </Space>
                  ) : null}
                </>
              }
              action={
                <Button size="small" onClick={() => navigate("/runtime-center")}>
                  查看结果
                </Button>
              }
              className={styles.inlineAlert}
            />
          ) : null}

          {/* 错误提示 */}
          {threadBootstrapError ? (
            <Alert
              type="warning"
              showIcon
              message="聊天连接出现问题"
              description="暂时无法恢复这段聊天，请稍后重试。"
              className={styles.inlineAlert}
            />
          ) : null}

          {/* 聊天画布 */}
          <div className={styles.canvas}>
            {shouldRenderChatComposer ? (
              <ChatComposerAdapter chatUiKey={chatComposerKey} options={options} />
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
        </div>
      ) : null}

    </div>
  );
}
