import type {
  RuntimeHumanAssistTaskDetail,
  RuntimeHumanAssistTaskSummary,
} from "../../api/modules/runtimeCenter";

export function firstNonEmptyString(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value !== "string") {
      continue;
    }
    const normalized = value.trim();
    if (normalized) {
      return normalized;
    }
  }
  return null;
}

export function normalizeTaskSummary(
  value: unknown,
): RuntimeHumanAssistTaskSummary | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const candidate = value as Partial<RuntimeHumanAssistTaskSummary>;
  const id = firstNonEmptyString(candidate.id);
  const title = firstNonEmptyString(candidate.title);
  const chatThreadId = firstNonEmptyString(candidate.chat_thread_id);
  const route = firstNonEmptyString(candidate.route);
  const status = firstNonEmptyString(candidate.status);
  if (!id || !title || !chatThreadId || !route || !status) {
    return null;
  }
  return {
    ...candidate,
    id,
    title,
    chat_thread_id: chatThreadId,
    route,
    status,
  } as RuntimeHumanAssistTaskSummary;
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => (typeof item === "string" ? item.trim() : ""))
    .filter(Boolean);
}

function entryList(value: unknown): Array<[string, string]> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return [];
  }
  return Object.entries(value as Record<string, unknown>)
    .filter(
      ([key, entryValue]) =>
        key !== "granted" && entryValue != null && entryValue !== "",
    )
    .map(([key, entryValue]) => [key, String(entryValue)]);
}

export function buildHumanAssistDetailPresentation(
  detail: RuntimeHumanAssistTaskDetail | null,
): {
  summary: string | null;
  action: string | null;
  hardAnchors: string[];
  resultAnchors: string[];
  negativeAnchors: string[];
  rewardPreview: Array<[string, string]>;
  rewardResult: Array<[string, string]>;
} {
  const acceptanceSpec =
    detail?.task.acceptance_spec &&
    typeof detail.task.acceptance_spec === "object"
      ? (detail.task.acceptance_spec as Record<string, unknown>)
      : {};
  return {
    summary: detail
      ? firstNonEmptyString(detail.task.summary, detail.task.reason_summary) ||
        null
      : null,
    action: detail
      ? firstNonEmptyString(detail.task.required_action) || null
      : null,
    hardAnchors: stringList(acceptanceSpec.hard_anchors),
    resultAnchors: stringList(acceptanceSpec.result_anchors),
    negativeAnchors: stringList(acceptanceSpec.negative_anchors),
    rewardPreview: entryList(detail?.task.reward_preview),
    rewardResult: entryList(detail?.task.reward_result),
  };
}
