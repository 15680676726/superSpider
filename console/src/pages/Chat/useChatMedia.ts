import { message } from "antd";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
} from "react";

import api from "../../api";
import type {
  AnalysisMode,
  MediaEntryPoint,
  MediaAnalysisSummary,
  MediaPurpose,
  MediaSourceSpec,
} from "../../api/modules/media";
import { dedupeStrings } from "../../utils/mediaPresentation";
import { normalizeThreadId } from "./chatPageHelpers";

export type ChatMediaDraftItem = {
  id: string;
  source: MediaSourceSpec;
  analysis_mode_options: AnalysisMode[];
  warnings: string[];
};

const CHAT_MEDIA_ENTRY_POINT: MediaEntryPoint = "chat";
const CHAT_MEDIA_PURPOSE: MediaPurpose = "chat-answer";

export function useChatMedia({
  activeChatThreadId,
}: {
  activeChatThreadId: string | null;
}) {
  const [mediaLinkValue, setMediaLinkValue] = useState("");
  const [mediaPendingItems, setMediaPendingItems] = useState<ChatMediaDraftItem[]>(
    [],
  );
  const [mediaAnalyses, setMediaAnalyses] = useState<MediaAnalysisSummary[]>([]);
  const [selectedMediaAnalysisIds, setSelectedMediaAnalysisIds] = useState<string[]>(
    [],
  );
  const [mediaBusy, setMediaBusy] = useState(false);
  const [mediaError, setMediaError] = useState<string | null>(null);

  const uploadMediaInputRef = useRef<HTMLInputElement | null>(null);
  const pendingMediaSourcesRef = useRef<MediaSourceSpec[]>([]);
  const selectedMediaAnalysisIdsRef = useRef<string[]>([]);
  const clearPendingMediaDraftsRef = useRef<(() => void) | null>(null);
  const refreshThreadMediaAnalysesRef = useRef<
    ((threadId?: string | null) => Promise<void>) | null
  >(null);

  useEffect(() => {
    selectedMediaAnalysisIdsRef.current = selectedMediaAnalysisIds;
  }, [selectedMediaAnalysisIds]);

  useEffect(() => {
    pendingMediaSourcesRef.current = mediaPendingItems.map((item) => ({
      ...item.source,
      entry_point: CHAT_MEDIA_ENTRY_POINT,
      purpose: CHAT_MEDIA_PURPOSE,
    }));
  }, [mediaPendingItems]);

  useEffect(() => {
    clearPendingMediaDraftsRef.current = () => {
      setMediaPendingItems([]);
      setMediaLinkValue("");
      setMediaError(null);
    };
    return () => {
      clearPendingMediaDraftsRef.current = null;
    };
  }, []);

  const handleAddMediaLink = useCallback(async () => {
    const url = mediaLinkValue.trim();
    if (!url) {
      return;
    }
    setMediaBusy(true);
    setMediaError(null);
    try {
      const resolved = await api.resolveMediaLink({
        url,
        entry_point: CHAT_MEDIA_ENTRY_POINT,
        purpose: CHAT_MEDIA_PURPOSE,
      });
      setMediaPendingItems((prev) => [
        ...prev,
        {
          id: `chat-link-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          source: {
            ...resolved.resolved_source,
            analysis_mode: resolved.resolved_source.analysis_mode || "standard",
            entry_point: CHAT_MEDIA_ENTRY_POINT,
            purpose: CHAT_MEDIA_PURPOSE,
          },
          analysis_mode_options: resolved.analysis_mode_options || [],
          warnings: resolved.warnings || [],
        },
      ]);
      setMediaLinkValue("");
      message.success("Link added.");
    } catch (error) {
      setMediaError(error instanceof Error ? error.message : String(error));
      message.error("链接材料添加失败");
    } finally {
      setMediaBusy(false);
    }
  }, [mediaLinkValue]);

  const handleMediaUploadChange = useCallback(
    async (event: ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(event.target.files || []);
      if (!files.length) {
        return;
      }
      setMediaBusy(true);
      setMediaError(null);
      try {
        const ingested = await Promise.all(
          files.map((file) =>
            api.ingestMedia(
              {
                source_kind: "upload",
                filename: file.name,
                mime_type: file.type || null,
                size_bytes: file.size,
                entry_point: CHAT_MEDIA_ENTRY_POINT,
                purpose: CHAT_MEDIA_PURPOSE,
                analysis_mode: file.type.startsWith("video/")
                  ? "video-lite"
                  : "standard",
              },
              file,
            ),
          ),
        );
        setMediaPendingItems((prev) => [
          ...prev,
          ...ingested.map((item, index) => ({
            id: `chat-upload-${Date.now()}-${index}`,
            source: {
              ...item.source,
              analysis_mode: item.source.analysis_mode || "standard",
              entry_point: CHAT_MEDIA_ENTRY_POINT,
              purpose: CHAT_MEDIA_PURPOSE,
            },
            analysis_mode_options: item.analysis_mode_options || [],
            warnings: item.warnings || [],
          })),
        ]);
        message.success(`Added ${files.length} local file(s).`);
      } catch (error) {
        setMediaError(error instanceof Error ? error.message : String(error));
        message.error("本地材料上传失败");
      } finally {
        event.target.value = "";
        setMediaBusy(false);
      }
    },
    [],
  );

  const loadThreadMediaAnalyses = useCallback(
    async (threadId?: string | null) => {
      const resolvedThreadId = normalizeThreadId(threadId || activeChatThreadId);
      if (!resolvedThreadId) {
        setMediaAnalyses([]);
        setSelectedMediaAnalysisIds([]);
        selectedMediaAnalysisIdsRef.current = [];
        return;
      }
      setMediaError(null);
      const items = await api.listMediaAnalyses({
        thread_id: resolvedThreadId,
        entry_point: CHAT_MEDIA_ENTRY_POINT,
        status: "completed",
        limit: 60,
      });
      setMediaAnalyses(items || []);
      setSelectedMediaAnalysisIds((prev) => {
        const completedIds = (items || [])
          .filter((item) => String(item.status || "").toLowerCase() === "completed")
          .map((item) => item.analysis_id);
        const existing = new Set(completedIds);
        const nextSelected = prev.length
          ? prev.filter((id) => existing.has(id))
          : completedIds;
        selectedMediaAnalysisIdsRef.current = nextSelected;
        return nextSelected;
      });
    },
    [activeChatThreadId],
  );

  useEffect(() => {
    refreshThreadMediaAnalysesRef.current = loadThreadMediaAnalyses;
    return () => {
      refreshThreadMediaAnalysesRef.current = null;
    };
  }, [loadThreadMediaAnalyses]);

  useEffect(() => {
    if (!activeChatThreadId) {
      setMediaAnalyses([]);
      setSelectedMediaAnalysisIds([]);
      selectedMediaAnalysisIdsRef.current = [];
      return;
    }
    let cancelled = false;
    void loadThreadMediaAnalyses(activeChatThreadId).catch((error) => {
      if (cancelled) {
        return;
      }
      setMediaError(error instanceof Error ? error.message : String(error));
    });
    return () => {
      cancelled = true;
    };
  }, [activeChatThreadId, loadThreadMediaAnalyses]);

  const removePendingMedia = useCallback((itemId: string) => {
    setMediaPendingItems((prev) =>
      prev.filter((candidate) => candidate.id !== itemId),
    );
  }, []);

  const toggleMediaAnalysis = useCallback((analysisId: string) => {
    setSelectedMediaAnalysisIds((prev) => {
      const checked = prev.includes(analysisId);
      const nextSelected = checked
        ? prev.filter((id) => id !== analysisId)
        : dedupeStrings([...prev, analysisId]);
      selectedMediaAnalysisIdsRef.current = nextSelected;
      return nextSelected;
    });
  }, []);

  const clearMediaError = useCallback(() => {
    setMediaError(null);
  }, []);

  return {
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
  };
}
