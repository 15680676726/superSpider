import { normalizeDisplayChinese } from "../../text";
import { presentRuntimeStatusLabel } from "../../runtime/executionPresentation";
import { runtimeRiskLabel } from "../../runtime/tagSemantics";

function humanizeToken(value: string): string {
  return value
    .replace(/[_-]/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/\b\w/g, (chunk) => chunk.toUpperCase());
}

function fallbackLabel(value: string | undefined | null): string {
  if (!value) {
    return "";
  }
  return normalizeDisplayChinese(humanizeToken(value));
}

const STATUS_LABEL_OVERRIDES: Record<string, string> = {
  rolled_back: "已回滚",
  "needs-confirm": "待确认",
  scheduled: "已排期",
  deferred: "已延后",
  recorded: "已记录",
  pending: "待处理",
  pass: "通过",
  warn: "警告",
  fail: "失败",
};

const ENV_KIND_LABELS: Record<string, string> = {
  workspace: "工作区",
  browser: "浏览器",
  session: "会话",
  terminal: "终端",
};

const ASSIGNMENT_SOURCE_LABELS: Record<string, string> = {
  baseline: "基线",
  blueprint: "蓝图",
  explicit: "显式指定",
  recommended: "系统推荐",
  effective: "当前生效",
};

const MODE_LABELS: Record<string, string> = {
  replace: "替换",
  merge: "合并",
};

const PATCH_KIND_LABELS: Record<string, string> = {
  capability_patch: "能力补丁",
  role_patch: "角色补丁",
  profile_patch: "画像补丁",
  plan_patch: "计划补丁",
};

const CHANGE_TYPE_LABELS: Record<string, string> = {
  capability: "能力变更",
  role: "角色变更",
  patch: "补丁变更",
  performance: "性能优化",
  capability_patch: "能力补丁",
  role_patch: "角色补丁",
  profile_patch: "画像补丁",
  plan_patch: "计划补丁",
};

const DECISION_TYPE_LABELS: Record<string, string> = {
  review: "审查",
  approve: "批准",
  reject: "拒绝",
  confirm: "确认",
};

const PHASE_LABELS: Record<string, string> = {
  resume: "恢复",
  pause: "暂停",
  snapshot: "快照",
  checkpoint: "检查点",
  "query-start": "查询开始",
  "query-loaded": "查询已加载",
  "query-streaming": "查询流式中",
  "query-complete": "查询完成",
};

const LEASE_KIND_LABELS: Record<string, string> = {
  "actor-runtime": "执行席运行时",
  session: "会话",
  workspace: "工作区",
  browser: "浏览器",
  terminal: "终端",
};

const REPLAY_TYPE_LABELS: Record<string, string> = {
  shell: "命令行",
  snapshot: "快照",
  browser: "浏览器",
  session: "会话",
  workspace: "工作区",
};

const ARTIFACT_KIND_LABELS: Record<string, string> = {
  file: "文件",
  folder: "文件夹",
  directory: "目录",
  archive: "压缩包",
  log: "日志",
  report: "报告",
  screenshot: "截图",
};

const INDUSTRY_ROLE_CLASS_LABELS: Record<string, string> = {
  system: "主脑",
  business: "岗位执行",
};

export const commonText = {
  refresh: "刷新",
  upload: "上传",
  download: "下载",
  openInChat: "在聊天中打开",
  cancel: "取消",
  retry: "重试",
} as const;

export const runtimeCenterText = {
  agentDetail: "智能体详情",
  routesTitle: "路由",
  noTimestamp: "暂无时间",
  actionApprove: "批准",
  actionReject: "拒绝",
  actionPause: "暂停",
  actionResume: "恢复",
} as const;

export const workspaceText = {
  tabTitle: "环境 / 文件",
  title: "环境 / 文件工作区",
  description: "这里显示这个执行位挂载的环境、回放、产物和文件，不展示任务汇总。",
  taskProgressHint: "任务进展请看任务 / 汇报、日报和周报。",
  filePanelTitle: "工作文件",
  currentEnvironment: "当前环境",
  environmentRef: "环境引用",
  runtimeStats: "运行统计",
  runtimeBindingMissing: "这个智能体还没有绑定工作区。",
  runtimeBindingHint:
    "请通过任务执行或证据链绑定工作区，让编辑器进入主运行链。",
  observationsTitle: "观察记录",
  replaysTitle: "回放",
  artifactsTitle: "产物",
  noObservations: "暂无观察记录",
  noReplays: "暂无回放",
  noArtifacts: "暂无产物",
  filesUnavailable: "当前没有绑定工作区，暂时无法查看文件。",
  downloadSuccess: "工作区下载成功。",
  downloadFailed: "工作区下载失败",
  zipOnly: "上传只支持 zip 压缩包",
  uploadSuccess: "工作区上传成功。",
  uploadFailed: "工作区上传失败",
  uploadTooltip: "上传工作区压缩包",
  zipInputTitle: "选择工作区压缩包",
  observationsTag: (count: number) => `观察 ${count}`,
  replaysTag: (count: number) => `回放 ${count}`,
  artifactsTag: (count: number) => `产物 ${count}`,
  fileSizeExceeded: (size: string) => `文件过大：${size} MB`,
} as const;

export const agentReportsText = {
  runtimeUnavailable: "运行时数据不可用。",
  dailyTitle: (date: string) => `每日报告 · ${date}`,
  reportSummaryLabel: "报告摘要",
  completedTaskCountLabel: "完成任务",
  taskCoverageLabel: "任务覆盖",
  evidenceCountLabel: "证据数",
  decisionCountLabel: "决策事项",
  successRateLabel: "任务成功率",
  exceptionRateLabel: "异常率",
  completedTasksTitle: "已完成任务",
  keyResultsTitle: "任务成果",
  primaryEvidenceTitle: "关键证据",
  blockersTitle: "阻塞与风险",
  nextStepsTitle: "下一步",
  noAgentSelected: "请先选择一个智能体。",
  noFormalReport: "当前没有可展示的正式报告。",
  noCompletedTasks: "当前没有已完成任务",
  noKeyResults: "当前没有可汇总成果",
  noPrimaryEvidence: "当前没有关键证据",
  noBlockers: "当前没有阻塞",
  noNextSteps: "当前没有下一步",
  evidenceToday: "今日证据",
  growthToday: "今日成长",
  proposalsToday: "今日提议",
  patchesToday: "今日已应用补丁",
  dailyFocusLabel: "今日关注",
  dailyFocusTraceable: "今天证据链可追溯，主链运行正常。",
  dailyFocusGap: "今天还没有新证据，先补齐可追溯产出。",
  noEvidenceToday: "今天暂无证据",
  latestEvidence: "最新证据",
  noTimestamp: "暂无时间",
  weeklyTitle: (since: string) => `周报 · 近 7 天（自 ${since} 起）`,
  evidenceIn7d: "近 7 天证据",
  growthIn7d: "近 7 天成长",
  proposalsIn7d: "近 7 天提议",
  patchesIn7d: "近 7 天补丁",
  weeklySignalLabel: "本周信号",
  weeklySignalActive: (summary: string) => `近期已落地修复：${summary}`,
  weeklySignalIncomplete: "近 7 天没有补丁落地。",
  noAppliedPatches: "近 7 天暂无已应用补丁",
  appliedPatchHighlights: "近期已应用修复",
  growthTrajectory: "成长轨迹",
  noGrowthEvents: "暂无成长事件",
  improvementProposals: "发现的问题与建议",
  noProposals: "近期没有发现待处理问题",
  patchStream: "已执行修复",
  noPatches: "近期暂无新修复",
  learningFeedTitle: "自修复动态",
  learningFeedDescription:
    "这里展示系统自动发现的问题、计划中的修复，以及已经执行的修复。",
  userFacingImpactLabel: "影响范围",
  userFacingSymptomLabel: "表现症状",
  userFacingTechRefLabel: "技术引用",
  userFacingHandledAuto: "已自动处理",
  userFacingHandledGuarded: "守护处理",
  userFacingHandledConfirm: "待人工确认",
} as const;

export const agentWorkbenchText = {
  pageTitle: "智能体任务中心",
  pageDescription: "查看智能体职责、当前任务、正式汇报与成长轨迹。",
  loading: "正在加载智能体任务中心...",
  noAgents: "暂无智能体",
  unassignedRole: "未分配角色",
  goalsTitle: "关联目标",
  noActiveGoals: "暂无激活目标",
  roleLabel: "角色",
  classLabel: "类别",
  employmentLabel: "任用方式",
  activationLabel: "激活方式",
  suspendable: "可暂停",
  runtimeLabel: "运行态",
  missionLabel: "使命",
  reportsToLabel: "汇报对象",
  industryTeamLabel: "身份",
  linkedGoalLabel: "关联目标",
  currentGoalLabel: "当前目标",
  environmentLabel: "环境摘要",
  environmentConstraintsLabel: "环境约束",
  todayLabel: "今日产出",
  latestEvidenceLabel: "最新证据",
  capabilitiesLabel: "能力",
  evidenceExpectationsLabel: "证据要求",
  capabilityGovernanceTitle: "能力治理",
  capabilityGovernanceUnavailable: "这个智能体当前不可进行能力治理。",
  capabilityGovernanceMode: "能力变更默认进入治理队列",
  capabilityDriftDetected: "发现漂移",
  capabilityAligned: "已对齐",
  capabilityGovernanceSummary:
    "能力变更默认进入治理队列，不直接绕过运行主链。",
  recommendedCapabilitiesLabel: "推荐能力",
  noRecommendedCapabilities: "暂无推荐能力",
  effectiveCapabilitiesLabel: "当前生效能力",
  capabilityChangeRequestTitle: "提交能力变更",
  capabilityChangeRequestSummary:
    "选择替换或合并后提交请求。运行中的智能体会保持治理路径。",
  capabilityAssignmentModeLabel: "变更方式",
  capabilityModeReplace: "替换",
  capabilityModeMerge: "合并",
  capabilityPickerLabel: "能力选择",
  capabilityPickerPlaceholder: "选择要提交的能力",
  capabilityReasonLabel: "变更原因",
  capabilityReasonPlaceholder: "说明为什么需要这次变更",
  useRecommendedCapabilities: "使用推荐能力",
  submitRecommendedGovernance: "提交推荐治理请求",
  submitGovernedChange: "提交治理变更",
  capabilityDecisionQueueTitle: "治理队列",
  noCapabilityDecisions: "暂无能力决策",
  actorRuntimeTitle: "执行位运行态",
  threadBindingsLabel: "线程绑定",
  mailboxSectionTitle: "邮箱队列",
  noMailboxWork: "暂无邮箱任务",
  checkpointsSectionTitle: "检查点",
  noCheckpoints: "暂无检查点",
  leasesSectionTitle: "活动租约",
  noActiveLeases: "暂无活动租约",
  teammatesSectionTitle: "协作成员",
  noTeammates: "暂无协作成员",
  openChatAction: "打开聊天",
  latestCollaborationLabel: "最新协作",
  goalDetailTitle: "目标详情",
  goalDetailUnavailable: "目标详情不可用",
  goalDetailHint: "选择一个目标后，可查看编译、任务、证据、决策和补丁链。",
  linkedAgentsTitle: "关联智能体",
  noLinkedAgents: "暂无关联智能体",
  compiledTaskSpecsTitle: "编译任务规格",
  noCompiledSpecs: "暂无编译规格",
  linkedTasksTitle: "关联任务",
  noLinkedTasks: "暂无关联任务",
  decisionRequestsTitle: "决策请求",
  noDecisionRequests: "暂无决策请求",
  linkedPatchesTitle: "关联补丁",
  noLinkedPatches: "暂无关联补丁",
  growthTitle: "成长记录",
  noLinkedGrowth: "暂无成长记录",
  activeEnvironmentsTitle: "活动环境",
  noActiveEnvironments: "暂无活动环境",
  recentEvidenceTitle: "最近证据",
  noEvidenceRecords: "暂无证据记录",
  dataUnavailable: "数据不可用",
  scopeMessage: "当前按身份过滤",
  clearScope: "显示全部智能体",
  tabWorkbench: "任务 / 汇报",
  tabDaily: "日报",
  tabWeekly: "周报",
  tabGrowth: "成长",
  ownerLabel: "负责人",
  planStepsLabel: "计划步骤",
  industryContextLabel: "行业上下文",
  recorded: "已记录",
  chatOpenFailed: "打开聊天失败",
  queueTag: (count: number) => `队列 ${count}`,
  mailboxTag: (id: string) => `邮箱 ${id}`,
  taskTag: (id: string) => `任务 ${id}`,
  environmentTag: (id: string) => `环境 ${id}`,
  checkpointTag: (id: string) => `检查点 ${id}`,
  capabilityDecisionQueued: (id: string) => `能力变更已进入治理队列：${id}`,
  capabilityDecisionQueuedNoId: "能力变更已进入治理队列。",
  capabilityUpdated: "能力已更新。",
  capabilityDecisionResult: (action: "approve" | "reject" | "review") =>
    action === "approve"
      ? "能力申请已批准。"
      : action === "reject"
        ? "能力申请已拒绝。"
        : "能力申请已标记待复核。",
  capabilityBaselineCount: (count: number) => `基线 ${count}`,
  capabilityBlueprintCount: (count: number) => `蓝图 ${count}`,
  capabilityExplicitCount: (count: number) => `显式 ${count}`,
  capabilityEffectiveCount: (count: number) => `生效 ${count}`,
  capabilityPendingCount: (count: number) => `待处理 ${count}`,
  environmentEvidenceLine: (kind: string, evidence: number) => `${kind} | 证据 ${evidence}`,
  lastActiveLine: (timestamp: string) => `最近活跃：${timestamp}`,
  taskEvidenceDecisionLine: (evidence: number, decisions: number) =>
    `证据 ${evidence} | 决策 ${decisions}`,
  metricTasks: (count: number) => `任务 ${count}`,
  metricDecisions: (count: number) => `决策 ${count}`,
  metricEvidence: (count: number) => `证据 ${count}`,
  metricPatches: (count: number) => `补丁 ${count}`,
  metricGrowth: (count: number) => `成长 ${count}`,
  metricAgents: (count: number) => `智能体 ${count}`,
} as const;

export function getStatusLabel(value: string | undefined | null): string {
  if (!value) {
    return "";
  }
  return STATUS_LABEL_OVERRIDES[value] ?? presentRuntimeStatusLabel(value);
}

export function getRiskLabel(value: string | undefined | null): string {
  if (!value) {
    return "";
  }
  return runtimeRiskLabel(value) || fallbackLabel(value);
}

export function getEnvironmentKindLabel(value: string | undefined | null): string {
  if (!value) {
    return "";
  }
  return ENV_KIND_LABELS[value] ?? fallbackLabel(value);
}

export function getAssignmentSourceLabel(value: string | undefined | null): string {
  if (!value) {
    return "";
  }
  return ASSIGNMENT_SOURCE_LABELS[value] ?? fallbackLabel(value);
}

export function getModeLabel(value: string | undefined | null): string {
  if (!value) {
    return "";
  }
  return MODE_LABELS[value] ?? fallbackLabel(value);
}

export function getPatchKindLabel(value: string | undefined | null): string {
  if (!value) {
    return "";
  }
  return PATCH_KIND_LABELS[value] ?? fallbackLabel(value);
}

export function getChangeTypeLabel(value: string | undefined | null): string {
  if (!value) {
    return "";
  }
  return CHANGE_TYPE_LABELS[value] ?? fallbackLabel(value);
}

export function getDecisionTypeLabel(value: string | undefined | null): string {
  if (!value) {
    return "";
  }
  return DECISION_TYPE_LABELS[value] ?? fallbackLabel(value);
}

export function getPhaseLabel(value: string | undefined | null): string {
  if (!value) {
    return "";
  }
  return PHASE_LABELS[value] ?? getStatusLabel(value);
}

export function getLeaseKindLabel(value: string | undefined | null): string {
  if (!value) {
    return "";
  }
  return LEASE_KIND_LABELS[value] ?? fallbackLabel(value);
}

export function getReplayTypeLabel(value: string | undefined | null): string {
  if (!value) {
    return "";
  }
  return REPLAY_TYPE_LABELS[value] ?? fallbackLabel(value);
}

export function getArtifactKindLabel(value: string | undefined | null): string {
  if (!value) {
    return "";
  }
  return ARTIFACT_KIND_LABELS[value] ?? fallbackLabel(value);
}

export function getEnvironmentDisplayName(
  kind: string | undefined | null,
  displayName: string | undefined | null,
): string {
  if (!displayName) {
    return getEnvironmentKindLabel(kind);
  }
  const normalized = displayName.trim().toLowerCase();
  if (normalized in ENV_KIND_LABELS) {
    return getEnvironmentKindLabel(normalized);
  }
  return displayName;
}

export function getIndustryRoleClassLabel(
  value: string | undefined | null,
): string {
  if (!value) {
    return "";
  }
  return INDUSTRY_ROLE_CLASS_LABELS[value] ?? fallbackLabel(value);
}

export function getIndustryRuntimeStatusLabel(
  value: string | undefined | null,
): string {
  return getStatusLabel(value);
}

export function formatPriorityTag(priority: number): string {
  return `P${priority}`;
}

