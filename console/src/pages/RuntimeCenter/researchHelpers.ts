import type { RuntimeCenterResearchResponse } from "../../api/modules/runtimeCenter";
import { normalizeDisplayChinese } from "../../text";

export interface ResearchSessionSummary {
  id: string;
  status: string;
  statusLabel: string;
  goal: string;
  roundCount: number;
  roundLabel: string;
  waitingLogin: boolean;
  latestStatus: string;
  updatedAt: string | null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function firstText(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
    if (typeof value === "number" && Number.isFinite(value)) {
      return String(value);
    }
    if (isRecord(value)) {
      const nested = firstText(
        value.id,
        value.goal,
        value.status,
        value.summary,
        value.title,
        value.label,
        value.value,
        value.response_summary,
        value.latest_status,
      );
      if (nested) {
        return nested;
      }
    }
  }
  return null;
}

function firstNumber(...values: unknown[]): number | null {
  for (const value of values) {
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }
    if (typeof value === "string" && value.trim()) {
      const parsed = Number(value);
      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }
    if (isRecord(value)) {
      const nested = firstNumber(value.round_count, value.round_index, value.count, value.value);
      if (nested !== null) {
        return nested;
      }
    }
  }
  return null;
}

function firstBoolean(...values: unknown[]): boolean | null {
  for (const value of values) {
    if (typeof value === "boolean") {
      return value;
    }
    if (isRecord(value)) {
      const nested = firstBoolean(value.waiting_login, value.needs_login, value.value);
      if (nested !== null) {
        return nested;
      }
    }
  }
  return null;
}

function localizeResearchStatus(status: string, waitingLogin: boolean): string {
  if (waitingLogin || status === "waiting-login") {
    return "待登录百度";
  }
  switch (status) {
    case "queued":
      return "等待研究";
    case "running":
    case "deepening":
    case "summarizing":
      return "当前研究中";
    case "completed":
      return "研究已完成";
    case "failed":
      return "研究失败";
    case "cancelled":
      return "研究已取消";
    default:
      return "当前研究中";
  }
}

function normalizeRoundLabel(roundCount: number): string {
  if (roundCount <= 0) {
    return "尚未开始";
  }
  return `第 ${roundCount} 轮`;
}

export function normalizeResearchSessionSummary(
  payload: RuntimeCenterResearchResponse | null | undefined,
): ResearchSessionSummary | null {
  if (!payload) {
    return null;
  }

  const session = isRecord(payload.session) ? payload.session : null;
  const latestRound = isRecord(payload.latest_round) ? payload.latest_round : null;

  const id = firstText(session?.id, payload.id) ?? "runtime-center-research";
  const status = firstText(session?.status, payload.status) ?? "";
  const roundCount =
    firstNumber(session?.round_count, payload.round_count, latestRound?.round_index) ?? 0;
  const waitingLogin =
    firstBoolean(session?.waiting_login, payload.waiting_login) ?? status === "waiting-login";
  const goal = firstText(session?.goal, payload.goal);
  const latestStatus = firstText(
    payload.latest_status,
    session?.latest_status,
    latestRound?.response_summary,
    latestRound?.status,
  );

  if (!goal && !status && roundCount <= 0 && !waitingLogin && !latestStatus) {
    return null;
  }

  const statusLabel = localizeResearchStatus(status, waitingLogin);
  return {
    id,
    status: status || (waitingLogin ? "waiting-login" : "running"),
    statusLabel,
    goal: normalizeDisplayChinese(goal ?? "暂未收到研究目标"),
    roundCount,
    roundLabel: normalizeRoundLabel(roundCount),
    waitingLogin,
    latestStatus: normalizeDisplayChinese(latestStatus ?? statusLabel),
    updatedAt: firstText(session?.updated_at, payload.updated_at, latestRound?.updated_at),
  };
}
