const RUNTIME_RISK_COLOR_MAP: Record<string, string> = {
  auto: "default",
  guarded: "orange",
  confirm: "red",
};

const RUNTIME_RISK_LABEL_MAP: Record<string, string> = {
  auto: "自动",
  guarded: "守护",
  confirm: "确认",
};

const RUNTIME_STATUS_COLOR_MAP: Record<string, string> = {
  active: "green",
  running: "green",
  executing: "green",
  completed: "green",
  processed: "green",
  approved: "green",
  applied: "green",
  leased: "green",
  pass: "green",
  persistent: "green",
  assigned: "blue",
  queued: "blue",
  planned: "blue",
  waiting: "blue",
  scheduled: "blue",
  "waiting-verification": "blue",
  learning: "blue",
  coordinating: "blue",
  open: "blue",
  recorded: "blue",
  proposed: "blue",
  accepted: "blue",
  claimed: "gold",
  review: "gold",
  reviewing: "gold",
  warn: "gold",
  "waiting-confirm": "gold",
  paused: "gold",
  "retry-wait": "gold",
  "waiting-resource": "orange",
  blocked: "red",
  failed: "red",
  fail: "red",
  rejected: "red",
  expired: "red",
  terminated: "red",
  degraded: "red",
  "idle-loop": "red",
  cancelled: "default",
  idle: "default",
  inactive: "default",
  draft: "default",
  archived: "default",
  deferred: "default",
  "on-demand": "default",
};

function normalize(value: string | null | undefined): string {
  return typeof value === "string" ? value.trim().toLowerCase() : "";
}

export function runtimeRiskColor(level?: string | null): string {
  return RUNTIME_RISK_COLOR_MAP[normalize(level)] || "default";
}

export function runtimeRiskLabel(level?: string | null): string {
  const normalizedLevel = normalize(level);
  return RUNTIME_RISK_LABEL_MAP[normalizedLevel] || (level?.trim() ?? "");
}

export function runtimeStatusColor(status?: string | null): string {
  return RUNTIME_STATUS_COLOR_MAP[normalize(status)] || "default";
}
