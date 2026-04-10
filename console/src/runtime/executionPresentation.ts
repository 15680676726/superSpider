import { normalizeSpiderMeshBrand } from "../utils/brand";
import { normalizeDisplayChinese } from "../text";

const KNOWN_AGENT_NAMES: Record<string, string> = {
  "copaw-agent-runner": "超级伙伴主脑",
  "copaw-governance": "超级伙伴治理核心",
  "copaw-scheduler": "超级伙伴调度核心",
};

const RUNTIME_STATUS_LABELS: Record<string, string> = {
  active: "已激活",
  approved: "已批准",
  applied: "已应用",
  archived: "已归档",
  running: "运行中",
  executing: "执行中",
  claimed: "已认领",
  assigned: "已派发",
  dispatched: "已派发",
  materialized: "已生成任务",
  disabled: "已禁用",
  enabled: "已启用",
  expired: "已过期",
  open: "待处理",
  idle: "空闲",
  waiting: "等待中",
  queued: "排队中",
  blocked: "受阻",
  paused: "已暂停",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
  leased: "租约中",
  proposed: "已提议",
  rejected: "已拒绝",
  reviewing: "审核中",
  "retry-wait": "重试等待",
  "waiting-confirm": "待确认",
  pending_staffing: "待补位",
  "routing-pending": "待补位",
  learning: "学习中",
  coordinating: "协调中",
  persistent: "常驻",
  "on-demand": "按需",
  draft: "草稿",
  accepted: "已接受",
};

const RUNTIME_STATUS_LABEL_OVERRIDES: Record<string, string> = {
  active: "自治运行中",
  running: "运行中",
  executing: "执行中",
  claimed: "已认领",
  assigned: "已派发",
  dispatched: "已派发",
  materialized: "已生成任务",
  idle: "待命",
  waiting: "等待中",
  queued: "排队中",
  scheduled: "已排程",
  blocked: "受阻",
  paused: "已暂停",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
  leased: "租约中",
  "retry-wait": "重试等待",
  "waiting-confirm": "待确认",
  pending_staffing: "待补位",
  "routing-pending": "待补位",
  "waiting-verification": "等待验证",
  "waiting-resource": "等待资源",
  learning: "学习中",
  coordinating: "协调中",
  persistent: "常驻",
  "on-demand": "按需",
  draft: "草稿",
  inactive: "未激活",
  "idle-loop": "空转中",
  accepted: "已接受",
  expired: "已过期",
  degraded: "暂无可执行能力",
};

const DESIRED_STATE_LABELS: Record<string, string> = {
  active: "保持运行",
  paused: "暂停处理",
  retired: "已退役",
};

const EMPLOYMENT_MODE_LABELS: Record<string, string> = {
  career: "长期岗位",
  temporary: "临时岗位",
};

const RUNTIME_CLASS_LABELS: Record<string, string> = {
  agent: "执行位",
  business: "业务位",
  system: "系统核心",
};

function humanize(value: string): string {
  return normalizeDisplayChinese(
    value
      .replace(/[_-]+/g, " ")
      .replace(/([a-z])([A-Z])/g, "$1 $2")
      .trim(),
  );
}

export function presentExecutionActorName(
  agentId: string,
  displayName?: string | null,
): string {
  if (displayName && displayName.trim()) {
    if (displayName === agentId && KNOWN_AGENT_NAMES[agentId]) {
      return KNOWN_AGENT_NAMES[agentId];
    }
    return normalizeSpiderMeshBrand(displayName.trim());
  }
  return normalizeSpiderMeshBrand(
    KNOWN_AGENT_NAMES[agentId] || humanize(agentId) || agentId,
  );
}

export function presentExecutionClassLabel(
  actorClass?: string | null,
  agentId?: string | null,
): string | null {
  const normalized = typeof actorClass === "string" ? actorClass.trim().toLowerCase() : "";
  if (agentId === "copaw-agent-runner") {
    return "主脑";
  }
  if (agentId === "copaw-governance" || agentId === "copaw-scheduler") {
    return "系统核心";
  }
  return RUNTIME_CLASS_LABELS[normalized] || (normalized ? humanize(normalized) : null);
}

export function presentRuntimeStatusLabel(status?: string | null): string {
  if (!status) {
    return "未知";
  }
  return (
    RUNTIME_STATUS_LABEL_OVERRIDES[status] ||
    RUNTIME_STATUS_LABELS[status] ||
    humanize(status)
  );
}

export function presentDesiredStateLabel(status?: string | null): string {
  if (!status) {
    return "未指定";
  }
  return DESIRED_STATE_LABELS[status] || presentRuntimeStatusLabel(status);
}

export function presentEmploymentModeLabel(mode?: string | null): string {
  if (!mode) {
    return "未知";
  }
  return EMPLOYMENT_MODE_LABELS[mode] || humanize(mode);
}

export function employmentModeColor(mode?: string | null): string {
  return mode === "temporary" ? "orange" : "green";
}

export function presentRuntimeTaskLabel(taskId?: string | null): string | null {
  if (!taskId) {
    return null;
  }
  if (taskId.startsWith("query:session:")) {
    return "当前聊天任务";
  }
  if (taskId.startsWith("ctask:")) {
    return "协作任务";
  }
  if (taskId.startsWith("ktask:")) {
    return "内核任务";
  }
  return `任务 ${taskId.slice(0, 12)}`;
}

export function formatRuntimeRelativeAge(value?: string | null): string {
  if (!value) {
    return "无心跳";
  }
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) {
    return value;
  }
  const diffSeconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000));
  if (diffSeconds < 60) {
    return `${diffSeconds} 秒前`;
  }
  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) {
    return `${diffMinutes} 分钟前`;
  }
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours} 小时前`;
  }
  return `${Math.floor(diffHours / 24)} 天前`;
}

