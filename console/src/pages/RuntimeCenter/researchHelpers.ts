import type { RuntimeCenterResearchResponse } from "../../api/modules/runtimeCenter";
import { normalizeDisplayChinese } from "../../text";

export interface ResearchBriefSummary {
  goal: string;
  question: string | null;
  whyNeeded: string | null;
  doneWhen: string | null;
  requestedSources: string[];
  scopeType: string | null;
  scopeId: string | null;
}

export interface ResearchFindingSummary {
  id: string;
  findingType: string | null;
  summary: string;
}

export interface ResearchSourceSummary {
  id: string;
  title: string;
  sourceKind: string | null;
  sourceRef: string;
  snippet: string | null;
}

export interface ResearchWritebackTruthSummary {
  status: string | null;
  statusLabel: string;
  scopeType: string | null;
  scopeId: string | null;
  reportId: string | null;
}

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
  brief: ResearchBriefSummary;
  findings: ResearchFindingSummary[];
  sources: ResearchSourceSummary[];
  gaps: string[];
  conflicts: string[];
  writebackTruth: ResearchWritebackTruthSummary | null;
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

function firstRecord(...values: unknown[]): Record<string, unknown> | null {
  for (const value of values) {
    if (isRecord(value)) {
      return value;
    }
  }
  return null;
}

function recordList(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter(isRecord);
}

function textList(...values: unknown[]): string[] {
  const items: string[] = [];
  for (const value of values) {
    if (typeof value === "string" && value.trim()) {
      items.push(value.trim());
      continue;
    }
    if (!Array.isArray(value)) {
      continue;
    }
    for (const item of value) {
      if (typeof item === "string" && item.trim()) {
        items.push(item.trim());
      }
    }
  }
  return Array.from(new Set(items));
}

function localizeWritebackStatus(status: string | null): string {
  switch (status) {
    case "written":
    case "applied":
    case "committed":
      return "已回写正式真相";
    case "blocked":
    case "failed":
      return "回写真相受阻";
    case "pending":
    case "queued":
      return "待回写正式真相";
    default:
      return status ? normalizeDisplayChinese(status) : "待回写正式真相";
  }
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

  const root = payload as unknown as Record<string, unknown>;
  const session = isRecord(payload.session) ? payload.session : null;
  const latestRound = isRecord(payload.latest_round) ? payload.latest_round : null;
  const briefRecord = firstRecord(root.brief, session?.brief);
  const writebackTarget = firstRecord(
    briefRecord?.writeback_target,
    root.writeback_target,
    session?.writeback_target,
  );
  const writebackRecord = firstRecord(root.writeback_truth, session?.writeback_truth);

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
  const findings = recordList(root.findings).map((item, index) => ({
    id: firstText(item.finding_id, item.id) ?? `${id}:finding:${index + 1}`,
    findingType: firstText(item.finding_type, item.type),
    summary: normalizeDisplayChinese(firstText(item.summary, item.value) ?? ""),
  })).filter((item) => item.summary);
  const sources = recordList(root.sources).map((item, index) => ({
    id: firstText(item.source_id, item.id) ?? `${id}:source:${index + 1}`,
    title: normalizeDisplayChinese(
      firstText(item.title, item.label, item.source_ref, item.url) ?? "未命名来源",
    ),
    sourceKind: firstText(item.source_kind, item.kind),
    sourceRef: firstText(item.source_ref, item.url, item.normalized_ref) ?? "",
    snippet: firstText(item.snippet, item.summary),
  })).filter((item) => item.sourceRef || item.title);
  const gaps = textList(root.gaps, session?.gaps);
  const conflicts = textList(root.conflicts, session?.conflicts);
  const writebackStatus = firstText(writebackRecord?.status);
  const writebackTruth = writebackRecord || writebackTarget
    ? {
        status: writebackStatus,
        statusLabel: localizeWritebackStatus(writebackStatus),
        scopeType: firstText(writebackRecord?.scope_type, writebackTarget?.scope_type),
        scopeId: firstText(writebackRecord?.scope_id, writebackTarget?.scope_id),
        reportId: firstText(writebackRecord?.report_id),
      }
    : null;

  if (
    !goal &&
    !status &&
    roundCount <= 0 &&
    !waitingLogin &&
    !latestStatus &&
    findings.length === 0 &&
    sources.length === 0 &&
    gaps.length === 0 &&
    conflicts.length === 0 &&
    writebackTruth == null
  ) {
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
    brief: {
      goal: normalizeDisplayChinese(
        firstText(briefRecord?.goal, session?.goal, payload.goal) ?? "暂未收到研究目标",
      ),
      question: firstText(briefRecord?.question, latestRound?.question),
      whyNeeded: firstText(briefRecord?.why_needed),
      doneWhen: firstText(briefRecord?.done_when),
      requestedSources: textList(briefRecord?.requested_sources),
      scopeType: firstText(writebackTarget?.scope_type),
      scopeId: firstText(writebackTarget?.scope_id),
    },
    findings,
    sources,
    gaps,
    conflicts,
    writebackTruth,
  };
}
