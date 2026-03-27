import type {
  AnalysisMode,
  MediaAnalysisSummary,
  MediaSourceSpec,
} from "../api/modules/media";
import { normalizeDisplayChinese } from "../text";

const MEDIA_TYPE_LABELS: Record<string, string> = {
  unknown: "未识别",
  article: "文章",
  video: "视频",
  audio: "音频",
  document: "文档",
};

const ANALYSIS_MODE_LABELS: Record<string, string> = {
  standard: "标准分析",
  "video-lite": "视频轻量分析",
  "video-deep": "视频深度分析",
};

const ANALYSIS_STATUS_LABELS: Record<string, string> = {
  queued: "排队中",
  pending: "待处理",
  running: "分析中",
  in_progress: "分析中",
  completed: "已完成",
  failed: "失败",
};

const WRITEBACK_STATUS_LABELS: Record<string, string> = {
  pending: "待写回",
  written: "已写回",
  failed: "写回失败",
  skipped: "已跳过",
  unavailable: "暂不可写回",
};

function normalizeMediaType(value?: string | null): string {
  const normalized = String(value || "unknown").trim();
  return normalized || "unknown";
}

function normalizeAnalysisMode(value?: string | null): string {
  const normalized = String(value || "standard").trim();
  return normalized || "standard";
}

function formatMediaType(value?: string | null): string {
  const normalized = normalizeMediaType(value);
  return MEDIA_TYPE_LABELS[normalized] || normalizeDisplayChinese(normalized);
}

function formatAnalysisMode(value?: string | null): string {
  const normalized = normalizeAnalysisMode(value);
  return ANALYSIS_MODE_LABELS[normalized] || normalizeDisplayChinese(normalized);
}

function formatAnalysisStatus(value?: string | null): string {
  const normalized = String(value || "pending").trim();
  return ANALYSIS_STATUS_LABELS[normalized] || normalizeDisplayChinese(normalized);
}

function formatAnalysisWritebackStatus(value?: string | null): string {
  const normalized = String(value || "pending").trim();
  return (
    WRITEBACK_STATUS_LABELS[normalized] ||
    normalizeDisplayChinese(normalized.replace(/[_-]+/g, " "))
  );
}

function mediaTypeColor(value?: string | null): string {
  const normalized = normalizeMediaType(value);
  if (normalized === "video") {
    return "magenta";
  }
  if (normalized === "audio") {
    return "purple";
  }
  if (normalized === "document") {
    return "blue";
  }
  if (normalized === "article") {
    return "geekblue";
  }
  return "default";
}

function analysisStatusColor(value?: string | null): string {
  const normalized = String(value || "pending").trim();
  if (normalized === "completed") {
    return "green";
  }
  if (normalized === "failed") {
    return "red";
  }
  if (["running", "in_progress", "queued"].includes(normalized)) {
    return "processing";
  }
  return "default";
}

function resolveMediaTitle(
  value?: Partial<MediaAnalysisSummary> | Partial<MediaSourceSpec> | null,
): string {
  if (!value) {
    return "未命名材料";
  }
  const sourceId =
    "source_id" in value && typeof value.source_id === "string"
      ? value.source_id.trim()
      : "";
  const analysisId =
    "analysis_id" in value && typeof value.analysis_id === "string"
      ? value.analysis_id.trim()
      : "";
  const candidate =
    (typeof value.title === "string" && value.title.trim()) ||
    (typeof value.filename === "string" && value.filename.trim()) ||
    (typeof value.url === "string" && value.url.trim()) ||
    sourceId ||
    analysisId;
  return candidate || "未命名材料";
}

function dedupeStrings(
  values: Array<string | null | undefined>,
): string[] {
  return values.reduce<string[]>((items, value) => {
    const normalized = String(value || "").trim();
    if (!normalized || items.includes(normalized)) {
      return items;
    }
    items.push(normalized);
    return items;
  }, []);
}

function buildAnalysisModeOptions(
  mediaType?: string | null,
  availableModes: Array<AnalysisMode | string> = [],
): Array<{ label: string; value: AnalysisMode; disabled?: boolean }> {
  const normalizedType = normalizeMediaType(mediaType);
  const normalizedModes = dedupeStrings(
    availableModes.map((item) => String(item || "").trim()),
  ) as AnalysisMode[];
  if (normalizedType === "video") {
    return [
      {
        label: ANALYSIS_MODE_LABELS["video-lite"],
        value: "video-lite",
      },
      {
        label: ANALYSIS_MODE_LABELS["video-deep"],
        value: "video-deep",
        disabled: !normalizedModes.includes("video-deep"),
      },
    ];
  }
  return [
    {
      label: ANALYSIS_MODE_LABELS.standard,
      value: "standard",
    },
  ];
}

export {
  analysisStatusColor,
  buildAnalysisModeOptions,
  dedupeStrings,
  formatAnalysisMode,
  formatAnalysisStatus,
  formatAnalysisWritebackStatus,
  formatMediaType,
  mediaTypeColor,
  resolveMediaTitle,
};
