import { authenticatedFetch, request } from "../request";

export type MediaSourceKind = "link" | "upload" | "existing-artifact";
export type MediaType = "unknown" | "article" | "video" | "audio" | "document";
export type AnalysisMode = "standard" | "video-lite" | "video-deep";
export type MediaEntryPoint =
  | "industry-preview"
  | "industry-bootstrap"
  | "chat"
  | "runtime-center";
export type MediaPurpose =
  | "draft-enrichment"
  | "chat-answer"
  | "learn-and-writeback"
  | "reference-only";

export interface MediaCapabilityState {
  video_deep_available: boolean;
  native_video_enabled: boolean;
  native_audio_enabled: boolean;
  local_asr_enabled: boolean;
  supported_video_modes: AnalysisMode[];
}

export interface MediaSourceSpec {
  source_id?: string;
  source_kind: MediaSourceKind;
  media_type?: MediaType;
  declared_media_type?: MediaType | null;
  detected_media_type?: MediaType | null;
  analysis_mode?: AnalysisMode | null;
  title?: string | null;
  url?: string | null;
  filename?: string | null;
  mime_type?: string | null;
  size_bytes?: number | null;
  artifact_id?: string | null;
  storage_uri?: string | null;
  upload_base64?: string | null;
  entry_point?: MediaEntryPoint;
  purpose?: MediaPurpose;
  metadata?: Record<string, unknown>;
}

export interface MediaResolveLinkPayload {
  url: string;
  entry_point?: MediaEntryPoint;
  purpose?: MediaPurpose;
}

export interface MediaResolveLinkResponse {
  url: string;
  normalized_url: string;
  detected_media_type: MediaType;
  mime_type?: string | null;
  title?: string | null;
  filename?: string | null;
  size_bytes?: number | null;
  analysis_mode_options: AnalysisMode[];
  resolved_source: MediaSourceSpec;
  warnings: string[];
  capabilities: MediaCapabilityState;
}

export interface MediaIngestResponse {
  source: MediaSourceSpec;
  detected_media_type: MediaType;
  analysis_mode_options: AnalysisMode[];
  asset_artifact_ids: string[];
  evidence_ids: string[];
  warnings: string[];
  capabilities: MediaCapabilityState;
}

export interface MediaAnalysisSummary {
  analysis_id: string;
  industry_instance_id?: string | null;
  thread_id?: string | null;
  entry_point: string;
  purpose: string;
  source_kind: string;
  source_ref?: string | null;
  detected_media_type: MediaType | string;
  analysis_mode: AnalysisMode | string;
  status: string;
  title: string;
  url?: string | null;
  filename?: string | null;
  mime_type?: string | null;
  size_bytes?: number | null;
  summary: string;
  key_points: string[];
  entities: string[];
  claims: string[];
  recommended_actions: string[];
  warnings: string[];
  asset_artifact_ids: string[];
  derived_artifact_ids: string[];
  transcript_artifact_id?: string | null;
  knowledge_document_ids: string[];
  evidence_ids: string[];
  strategy_writeback_status?: string | null;
  backlog_writeback_status?: string | null;
  error_message?: string | null;
  metadata: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface MediaAnalysisPayload {
  sources: MediaSourceSpec[];
  industry_instance_id?: string | null;
  thread_id?: string | null;
  entry_point?: MediaEntryPoint;
  purpose?: MediaPurpose;
  writeback?: boolean;
}

export interface MediaAnalysisResponse {
  analyses: MediaAnalysisSummary[];
  warnings: string[];
  capabilities: MediaCapabilityState;
}

async function uploadIngestedMedia(
  source: MediaSourceSpec,
  file: File,
): Promise<MediaIngestResponse> {
  const body = new FormData();
  body.set("source", JSON.stringify(source));
  body.set("file", file);
  const response = await authenticatedFetch("/media/ingest", {
    method: "POST",
    body,
  });
  return (await response.json()) as MediaIngestResponse;
}

export const mediaApi = {
  getMediaCapabilities(): Promise<MediaCapabilityState> {
    return request<MediaCapabilityState>("/media/capabilities");
  },

  resolveMediaLink(
    payload: MediaResolveLinkPayload,
  ): Promise<MediaResolveLinkResponse> {
    return request<MediaResolveLinkResponse>("/media/resolve-link", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  ingestMedia(
    source: MediaSourceSpec,
    file?: File | null,
  ): Promise<MediaIngestResponse> {
    if (file) {
      return uploadIngestedMedia(source, file);
    }
    return request<MediaIngestResponse>("/media/ingest", {
      method: "POST",
      body: JSON.stringify({ source }),
    });
  },

  analyzeMedia(payload: MediaAnalysisPayload): Promise<MediaAnalysisResponse> {
    return request<MediaAnalysisResponse>("/media/analyses", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listMediaAnalyses(params?: {
    industry_instance_id?: string;
    thread_id?: string;
    entry_point?: string;
    status?: string;
    limit?: number;
  }): Promise<MediaAnalysisSummary[]> {
    const query = new URLSearchParams();
    if (params?.industry_instance_id) {
      query.set("industry_instance_id", params.industry_instance_id);
    }
    if (params?.thread_id) {
      query.set("thread_id", params.thread_id);
    }
    if (params?.entry_point) {
      query.set("entry_point", params.entry_point);
    }
    if (params?.status) {
      query.set("status", params.status);
    }
    if (typeof params?.limit === "number") {
      query.set("limit", String(params.limit));
    }
    return request<MediaAnalysisSummary[]>(
      `/media/analyses${query.toString() ? `?${query.toString()}` : ""}`,
    );
  },

  getMediaAnalysis(analysisId: string): Promise<MediaAnalysisSummary> {
    return request<MediaAnalysisSummary>(`/media/analyses/${analysisId}`);
  },
};
