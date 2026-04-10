import { Input } from "antd";
import type {
  IndustryCapabilityRecommendationSection,
  IndustryBootstrapInstallItem,
  IndustryCapabilityRecommendation,
  IndustryDraftGoal,
  IndustryDraftPlan,
  IndustryDraftSchedule,
  IndustryInstanceDetail,
  IndustryPreviewPayload,
  IndustryReadinessCheck,
  IndustryRoleBlueprint,
} from "../../api/modules/industry";
import type {
  AnalysisMode,
  MediaSourceSpec,
} from "../../api/modules/media";
import {
  presentRecommendationCapabilityFamily,
} from "../../utils/remoteSkillPresentation";
import {
  presentEmploymentModeLabel,
  presentRuntimeStatusLabel,
} from "../../runtime/executionPresentation";
import { normalizeDisplayChinese } from "../../text";
import { runtimeRiskLabel, runtimeStatusColor } from "../../runtime/tagSemantics";
const { TextArea } = Input;

const INDUSTRY_TEXT = {
  pageTitle: "行业工作台",
  prepareBrief: "填写载体调整简报",
  formIndustry: "正式方向",
  formIndustryRequired: "请输入正式方向",
  formIndustryPlaceholder: "例如：独立创作 / 设计系统 / 策略运营",
  formCompany: "公司/品牌",
  formCompanyPlaceholder: "输入公司、品牌或客户名称",
  formProduct: "产品/服务",
  formProductPlaceholder: "说明你要推进的产品、服务或交付内容",
  formTargetCustomers: "目标客户",
  formTargetCustomersPlaceholder: "描述核心客户群体、决策人和使用者",
  formGoals: "阶段目标",
  formGoalsPlaceholder: "写下本阶段最重要的目标，可用换行分隔",
  formConstraints: "约束条件",
  formConstraintsPlaceholder: "填写预算、合规、资源、时限或渠道限制",
  formNotes: "补充说明",
  formNotesPlaceholder: "补充上下文、历史信息或特殊要求",
  previewPlan: "生成预览",
  previewBeforeActivate: "先预览执行载体调整草案、目标、节奏与能力安装建议，再决定是否应用。",
  previewBlockedWarning: "还有必填信息或关键检查未通过，当前不能正式启动。",
  previewTitle: "执行载体调整预览",
  currentCarrierAdjustment: "当前执行载体调整",
  regenerateDraft: "重新生成调整草案",
  activateTeam: "应用执行载体调整",
  updateTeam: "应用执行载体调整",
  previewMediaAnalysisSummary: "这里会展示预览阶段生成的素材分析，身份确认后也会继续作为共享上下文保留。",
  previewMediaAnalysisEmpty: "当前预览还没有素材分析。",
  previewMediaAnalysisAdoptedTag: "已纳入",
  activationLabel: "激活状态",
  readyToActivate: "可启动",
  blocked: "受阻",
  detailStats: "统计",
  carrierLabel: "载体名称",
  carrierSummaryLabel: "载体摘要",
  summaryLabel: "摘要",
  carrierSummaryPlaceholder: "用一句话概括这个载体当前要承接的执行目标和边界。",
  draftSummary: "生成摘要",
  teamRoles: "执行位角色",
  addRole: "添加角色",
  systemRolesLockedHint: "系统核心角色由主链维护，不建议在这里直接删除或改成其他身份。",
  roleDisplayName: "显示名称",
  roleTitle: "角色标题",
  roleFallback: "未命名角色",
  goalKind: "目标类型",
  roleReportsTo: "汇报对象",
  roleReportsToPlaceholder: "选择该角色默认向谁回流结果",
  roleEnvironment: "环境约束",
  roleEnvironmentPlaceholder: "例如：仅浏览器、仅工作区、禁止外发等",
  roleEvidence: "证据要求",
  roleEvidencePlaceholder: "例如：日报、研究摘要、交付稿、截图",
  roleMission: "角色使命",
  roleMissionPlaceholder: "描述这个角色长期负责的结果，而不是一次性动作。",
  goalsTitle: "目标列表",
  addGoal: "添加目标",
  goalOwner: "目标负责人",
  goalTitle: "目标标题",
  goalSummaryPlaceholder: "说明这个目标为什么重要、输出什么结果",
  planStepsLabel: "计划步骤",
  goalPlanStepsPlaceholder: "按行填写步骤，帮助系统理解执行顺序",
  schedulesTitle: "节奏计划",
  addSchedule: "添加计划",
  scheduleOwner: "计划负责人",
  scheduleTitle: "计划标题",
  scheduleSummaryPlaceholder: "说明这个计划触发时要做什么",
  cron: "定时表达式",
  scheduleTimezone: "时区",
  dispatchMode: "派发模式",
  readinessChecks: "准备度检查",
  noInstances: "还没有可调整的执行载体。",
  industryDetail: "执行载体详情",
  loadIntoDraft: "载入到编辑区",
  detailInstance: "实例信息",
  detailOwnerScope: "归属范围",
  detailStatus: "状态",
  statsLabel: "统计",
  detailAgents: "角色列表",
  detailStrategy: "战略记忆",
  detailCurrentCycle: "当前周期",
  detailLanes: "工作泳道",
  detailBacklog: "待办",
  detailAssignments: "派单记录",
  detailAgentReports: "智能体汇报",
  metricRoles: "角色",
  metricGoals: "目标",
  metricSchedules: "计划",
  metricAgents: "执行位",
  capabilityRecommendations: "能力推荐",
  installed: "已安装",
  recommended: "推荐",
  installTargets: "安装目标",
  selectTeamHint: "先从左侧选择一个执行载体，右侧才会显示详情或编辑草案。",
  noSchedules: "当前没有正式节奏计划。",
  dailyReport: "日报",
  reportEvidence: "证据",
  reportDecisions: "决策",
  reportProposals: "提案",
  reportPatches: "补丁",
  noHighlights: "当前窗口内还没有高亮结果。",
  updateSuccess: "执行载体已更新，主链状态已重新对齐。",
  chatOpenFailed: "打开主脑聊天失败。",
  readinessBlocked: "环境与依赖受阻，无法启动执行。",
  readinessWarning: "有重要节点尚未就绪，建议检查。",
  readinessReady: "全节点就绪，可无缝启动执行。",
} as const;

const INDUSTRY_EXPERIENCE_TEXT = {
  pageDescription:
    "这里查看当前主方向对应的执行载体、团队分工、运行状态和调整入口，不是重新建档页。",
  prepareBriefHint:
    "尽量把当前要承接的正式方向、客户、目标和限制写清楚。这里调整的是主脑当前执行方向对应的行业执行载体，不是用户当前职业档案的重填。",
  formExperienceMode: "协作模式",
  formExperienceModeSystemLed: "系统主导",
  formExperienceModeOperatorGuided: "人工引导",
  formExperienceNotes: "协作备注",
  formExperienceNotesPlaceholder: "说明你希望系统如何汇报、何时打断你、哪些事情必须谨慎处理。",
  formOperatorRequirements: "人工要求",
  formOperatorRequirementsPlaceholder: "填写必须遵守的人类规则、审批要求或禁区。",
  openExecutionCoreChat: "打开主脑聊天",
  activateSuccess: "执行载体调整已生效，主脑会继续按新的编排推进执行。",
} as const;

const INDUSTRY_ROLE_CLASS_LABELS: Record<string, string> = {
  system: "系统核心",
  business: "业务角色",
};

function formatIndustryDisplayToken(value?: string | null): string {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return "-";
  }
  return normalizeDisplayChinese(normalized.replace(/[_-]+/g, " "));
}

function presentIndustryRuntimeStatus(status?: string | null): string {
  return presentRuntimeStatusLabel(status || "active");
}

function presentIndustryRoleClass(value?: string | null): string {
  if (!value) {
    return "-";
  }
  return INDUSTRY_ROLE_CLASS_LABELS[value] || String(value);
}

function presentIndustryEmploymentMode(value?: string | null): string {
  return value ? presentEmploymentModeLabel(value) : "-";
}

function presentIndustryRiskLevel(value?: string | null): string {
  if (!value) {
    return "-";
  }
  return runtimeRiskLabel(value) || String(value);
}

function presentIndustryReadinessStatus(
  status: IndustryReadinessCheck["status"],
): string {
  if (status === "missing") {
    return INDUSTRY_TEXT.readinessBlocked;
  }
  if (status === "warning") {
    return INDUSTRY_TEXT.readinessWarning;
  }
  return INDUSTRY_TEXT.readinessReady;
}

function formatCountLabel(label: string, count: number): string {
  return label + " " + count;
}

function formatIndustryDetailStats(stats?: {
  agent_count?: number | null;
  schedule_count?: number | null;
  lane_count?: number | null;
  backlog_count?: number | null;
  assignment_count?: number | null;
} | null): string {
  if (!stats) {
    return "-";
  }
  const items: string[] = [];
  if (typeof stats.agent_count === "number") {
    items.push(formatCountLabel(INDUSTRY_TEXT.metricAgents, stats.agent_count));
  }
  if (typeof stats.schedule_count === "number") {
    items.push(formatCountLabel(INDUSTRY_TEXT.metricSchedules, stats.schedule_count));
  }
  if (typeof stats.lane_count === "number") {
    items.push(formatCountLabel("泳道", stats.lane_count));
  }
  if (typeof stats.backlog_count === "number") {
    items.push(formatCountLabel("待办", stats.backlog_count));
  }
  if (typeof stats.assignment_count === "number") {
    items.push(formatCountLabel("派单", stats.assignment_count));
  }
  return items.length ? items.join(" / ") : "-";
}

interface IndustryBriefFormValues {
  industry: string;
  company_name?: string;
  sub_industry?: string;
  product?: string;
  business_model?: string;
  region?: string;
  target_customers?: string;
  channels?: string;
  goals?: string;
  constraints?: string;
  budget_summary?: string;
  notes?: string;
  owner_scope?: string;
  experience_mode?: "system-led" | "operator-guided";
  experience_notes?: string;
  operator_requirements?: string;
}

interface IndustryBriefMediaItem {
  id: string;
  source: MediaSourceSpec;
  analysis_mode_options: AnalysisMode[];
  warnings: string[];
}

type InstallPlanDraftItem = IndustryBootstrapInstallItem & {
  plan_item_key: string;
};

const RECOMMENDATION_SECTION_LABELS: Record<
  IndustryCapabilityRecommendationSection["section_kind"],
  string
> = {
  "system-baseline": "系统基线能力",
  "execution-core": "主脑调度能力",
  shared: "载体共享能力",
  role: "角色专属能力",
};

const CAPABILITY_FAMILY_OPTIONS = [
  "workflow",
  "research",
  "content",
  "crm",
  "browser",
  "data",
  "email",
  "image",
  "desktop",
  "github",
].map((value) => ({
  label: presentRecommendationCapabilityFamily(value),
  value,
}));

const INSTALL_ASSIGNMENT_MODE_OPTIONS = [
  { label: "与现有能力合并", value: "merge" as const },
  { label: "替换现有能力", value: "replace" as const },
];


let installPlanItemSeed = 0;

interface LinesTextAreaProps {
  value?: string[];
  onChange?: (value: string[]) => void;
  rows?: number;
  placeholder?: string;
}

function parseLines(value?: string): string[] {
  return (value || "")
    .split(/\r?\n|,/) 
    .map((item) => item.trim())
    .filter(Boolean);
}

function uniqueStrings(values: Array<string | undefined | null>): string[] {
  return values.reduce<string[]>((items, value) => {
    const normalized = value?.trim();
    if (!normalized || items.includes(normalized)) {
      return items;
    }
    items.push(normalized);
    return items;
  }, []);
}

function nextInstallPlanItemKey(prefix = "custom"): string {
  installPlanItemSeed += 1;
  return `${prefix}:${installPlanItemSeed}`;
}

function recommendationPlanItemKey(recommendationId: string): string {
  return `recommendation:${recommendationId}`;
}

function stripInstallPlanDraftItem(
  item: InstallPlanDraftItem,
): IndustryBootstrapInstallItem {
  return Object.fromEntries(
    Object.entries(item).filter(([key]) => key !== "plan_item_key"),
  ) as IndustryBootstrapInstallItem;
}

function createBlankInstallPlanItem(defaultTargetAgentId?: string): InstallPlanDraftItem {
  return {
    plan_item_key: nextInstallPlanItemKey(),
    install_kind: "mcp-template",
    template_id: "",
    source_kind: "install-template",
    enabled: true,
    required: false,
    capability_assignment_mode: "merge",
    capability_ids: [],
    target_agent_ids: defaultTargetAgentId ? [defaultTargetAgentId] : [],
    target_role_ids: [],
  };
}

function buildFallbackRecommendationSections(
  items: IndustryCapabilityRecommendation[],
  roles: IndustryRoleBlueprint[],
): IndustryCapabilityRecommendationSection[] {
  if (!items.length) {
    return [];
  }
  const sections: IndustryCapabilityRecommendationSection[] = [];
  const pushSection = (
    section: IndustryCapabilityRecommendationSection | null,
  ): void => {
    if (section && section.items.length) {
      sections.push(section);
    }
  };
  pushSection({
    section_id: "system-baseline",
    section_kind: "system-baseline",
    title: "系统基线能力",
    summary: "维持运行中心与执行网格正常运转的基础应用，默认全局共享。",
    items: items.filter((item) => item.recommendation_group === "system-baseline"),
  });
  const executionCoreRole =
    roles.find((role) => role.role_id === "execution-core") || null;
  pushSection({
    section_id: "execution-core",
    section_kind: "execution-core",
    title: executionCoreRole?.role_name || "主脑调度能力",
    summary: "提供执行载体目标拆解、节点调度以及状态监控的核心管理能力。",
    role_id: executionCoreRole?.role_id,
    role_name: executionCoreRole?.role_name,
    target_agent_id: executionCoreRole?.agent_id,
    items: items.filter((item) => item.recommendation_group === "execution-core"),
  });
  pushSection({
    section_id: "shared",
    section_kind: "shared",
    title: "载体共享能力",
    summary: "推荐当前载体各执行位统一配备或相互调用的通用效率工具。",
    items: items.filter((item) => item.recommendation_group === "shared"),
  });
  roles
    .filter((role) => role.role_id !== "execution-core" && role.agent_id)
    .forEach((role) => {
      pushSection({
        section_id: `role:${role.role_id}`,
        section_kind: "role",
        title: role.role_name || role.name || role.role_id,
        summary: `${role.role_name || role.name || role.role_id} 专属的能力与工具集合。`,
        role_id: role.role_id,
        role_name: role.role_name,
        target_agent_id: role.agent_id,
        items: items.filter(
          (item) =>
            item.recommendation_group === "role-specific" &&
            item.target_agent_ids?.includes(role.agent_id),
        ),
      });
    });
  return sections;
}

function LinesTextArea({
  value,
  onChange,
  rows = 3,
  placeholder,
}: LinesTextAreaProps) {
  return (
    <TextArea
      rows={rows}
      placeholder={placeholder}
      value={(value || []).join("\n")}
      onChange={(event) => onChange?.(parseLines(event.target.value))}
    />
  );
}

function toPreviewPayload(
  values: IndustryBriefFormValues,
  mediaItems: IndustryBriefMediaItem[] = [],
): IndustryPreviewPayload {
  return {
    industry: values.industry.trim(),
    company_name: values.company_name?.trim() || undefined,
    sub_industry: values.sub_industry?.trim() || undefined,
    product: values.product?.trim() || undefined,
    business_model: values.business_model?.trim() || undefined,
    region: values.region?.trim() || undefined,
    target_customers: parseLines(values.target_customers),
    channels: parseLines(values.channels),
    goals: parseLines(values.goals),
    constraints: parseLines(values.constraints),
    budget_summary: values.budget_summary?.trim() || undefined,
    notes: values.notes?.trim() || undefined,
    owner_scope: values.owner_scope?.trim() || undefined,
    experience_mode: values.experience_mode || "system-led",
    experience_notes: values.experience_notes?.trim() || undefined,
    operator_requirements: parseLines(values.operator_requirements),
    media_inputs: mediaItems.map((item) => item.source),
  };
}

function normalizeRoleBlueprint(
  role?: Partial<IndustryRoleBlueprint> | null,
): IndustryRoleBlueprint {
  return {
    schema_version: "industry-role-blueprint-v1",
    role_id: role?.role_id || "",
    agent_id: role?.agent_id || "",
    name: role?.name || "",
    role_name: role?.role_name || "",
    role_summary: role?.role_summary || "",
    mission: role?.mission || "",
    goal_kind: role?.goal_kind || "",
    agent_class: role?.agent_class === "system" ? "system" : "business",
    employment_mode:
      role?.employment_mode === "temporary" ? "temporary" : "career",
    activation_mode:
      role?.activation_mode === "on-demand" ? "on-demand" : "persistent",
    suspendable: Boolean(role?.suspendable),
    reports_to: role?.reports_to || undefined,
    risk_level:
      role?.risk_level === "auto" ||
      role?.risk_level === "guarded" ||
      role?.risk_level === "confirm"
        ? role.risk_level
        : "guarded",
    environment_constraints: Array.isArray(role?.environment_constraints)
      ? role.environment_constraints.filter(Boolean)
      : [],
    allowed_capabilities: Array.isArray(role?.allowed_capabilities)
      ? role.allowed_capabilities.filter(Boolean)
      : [],
    preferred_capability_families: Array.isArray(role?.preferred_capability_families)
      ? role.preferred_capability_families.filter(Boolean)
      : [],
    evidence_expectations: Array.isArray(role?.evidence_expectations)
      ? role.evidence_expectations.filter(Boolean)
      : [],
  };
}

function normalizeGoal(goal?: Partial<IndustryDraftGoal> | null): IndustryDraftGoal {
  return {
    goal_id: goal?.goal_id || "",
    kind: goal?.kind || "",
    owner_agent_id: goal?.owner_agent_id || "",
    title: goal?.title || "",
    summary: goal?.summary || "",
    plan_steps: Array.isArray(goal?.plan_steps) ? goal.plan_steps.filter(Boolean) : [],
  };
}

function normalizeSchedule(
  schedule?: Partial<IndustryDraftSchedule> | null,
): IndustryDraftSchedule {
  return {
    schedule_id: schedule?.schedule_id || "",
    owner_agent_id: schedule?.owner_agent_id || "",
    title: schedule?.title || "",
    summary: schedule?.summary || "",
    cron: schedule?.cron || "0 9 * * *",
    timezone: schedule?.timezone || "UTC",
    dispatch_channel: schedule?.dispatch_channel || "console",
    dispatch_mode: schedule?.dispatch_mode === "final" ? "final" : "stream",
  };
}

function normalizeDraftPlan(values?: Partial<IndustryDraftPlan> | null): IndustryDraftPlan {
  return {
    schema_version: "industry-draft-v1",
    team: {
      schema_version: "industry-team-blueprint-v1",
      team_id: values?.team?.team_id || "",
      label: values?.team?.label || "",
      summary: values?.team?.summary || "",
      topology: values?.team?.topology || null,
      agents: Array.isArray(values?.team?.agents)
        ? values.team.agents.map((role) => normalizeRoleBlueprint(role))
        : [],
    },
    goals: Array.isArray(values?.goals)
      ? values.goals.map((goal) => normalizeGoal(goal))
      : [],
    schedules: Array.isArray(values?.schedules)
      ? values.schedules.map((schedule) => normalizeSchedule(schedule))
      : [],
    generation_summary: values?.generation_summary?.trim() || undefined,
  };
}

function detailToDraftPlan(detail: IndustryInstanceDetail): IndustryDraftPlan {
  return normalizeDraftPlan({
    team: detail.team,
    goals: detail.goals.map((goal) =>
      normalizeGoal({
        goal_id: goal.kind || goal.goal_id,
        kind: goal.kind,
        owner_agent_id: goal.owner_agent_id || "",
        title: goal.title,
        summary: goal.summary,
        plan_steps: Array.isArray(goal.plan_steps) ? goal.plan_steps : [],
      }),
    ),
    schedules: detail.schedules.map((schedule) =>
      normalizeSchedule({
        schedule_id: schedule.schedule_id,
        owner_agent_id: schedule.owner_agent_id || "",
        title: schedule.title,
        summary: schedule.summary || "",
        cron: schedule.cron,
        timezone: schedule.timezone,
        dispatch_channel: schedule.dispatch_channel || "console",
        dispatch_mode: schedule.dispatch_mode === "final" ? "final" : "stream",
      }),
    ),
  });
}

function createBlankRole(): IndustryRoleBlueprint {
  return normalizeRoleBlueprint();
}

function createBlankGoal(ownerAgentId?: string): IndustryDraftGoal {
  return normalizeGoal({ owner_agent_id: ownerAgentId || "" });
}

function createBlankSchedule(ownerAgentId?: string): IndustryDraftSchedule {
  return normalizeSchedule({ owner_agent_id: ownerAgentId || "" });
}

function recommendationToInstallItem(
  recommendation: IndustryCapabilityRecommendation,
): InstallPlanDraftItem {
  return {
    plan_item_key: recommendationPlanItemKey(recommendation.recommendation_id),
    recommendation_id: recommendation.recommendation_id,
    install_kind: recommendation.install_kind,
    template_id: recommendation.template_id,
    install_option_key: recommendation.install_option_key || undefined,
    client_key: recommendation.default_client_key,
    bundle_url: recommendation.source_url || undefined,
    version: recommendation.version || undefined,
    source_kind: recommendation.source_kind,
    source_label: recommendation.source_label || undefined,
    review_acknowledged: recommendation.review_required ? false : undefined,
    enabled: recommendation.default_enabled,
    required: recommendation.required,
    capability_assignment_mode: "merge",
    capability_ids: recommendation.capability_ids,
    target_agent_ids: recommendation.target_agent_ids,
    target_role_ids: recommendation.suggested_role_ids,
  };
}

function readinessColor(status: IndustryReadinessCheck["status"]): string {
  if (status === "ready") {
    return "success";
  }
  if (status === "warning") {
    return "warning";
  }
  return "error";
}

function roleColor(role?: Partial<IndustryRoleBlueprint> | null): string {
  return role?.agent_class === "system" ? "blue" : "processing";
}

function isSystemRole(role?: Partial<IndustryRoleBlueprint> | null): boolean {
  return role?.role_id === "execution-core" || role?.agent_class === "system";
}

function formatTimestamp(value?: string | null, locale?: string): string {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(locale, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

function presentText(value?: string | null): string {
  return value && value.trim() ? normalizeDisplayChinese(value.trim()) : "-";
}

function presentList(values?: Array<string | null | undefined>): string {
  const items = (values || [])
    .map((item) =>
      typeof item === "string" ? normalizeDisplayChinese(item.trim()) : "",
    )
    .filter(Boolean);
  return items.length ? items.join(" / ") : "-";
}

function deriveIndustryAgentStatus(agent: IndustryInstanceDetail["agents"][number]): string {
  const runtimeStatus = String(agent.runtime_status || "").trim();
  const surfaceStatus = String(agent.status || "").trim();
  const capabilities = Array.isArray(agent.capabilities)
    ? agent.capabilities.filter(Boolean)
    : [];
  if (
    runtimeStatus === "waiting-confirm" ||
    surfaceStatus === "waiting-confirm" ||
    surfaceStatus === "needs-confirm"
  ) {
    return "waiting-confirm";
  }
  if (
    runtimeStatus === "waiting-verification" ||
    surfaceStatus === "waiting-verification"
  ) {
    return "waiting-verification";
  }
  if (
    runtimeStatus === "waiting-resource" ||
    surfaceStatus === "waiting-resource"
  ) {
    return "waiting-resource";
  }
  if (runtimeStatus === "blocked" || surfaceStatus === "blocked") {
    return "blocked";
  }
  if (capabilities.length === 0 && runtimeStatus !== "paused" && surfaceStatus !== "paused") {
    return "degraded";
  }
  if (
    runtimeStatus === "running" ||
    runtimeStatus === "active" ||
    runtimeStatus === "waiting" ||
    runtimeStatus === "queued" ||
    surfaceStatus === "running" ||
    surfaceStatus === "active"
  ) {
    return "active";
  }
  return runtimeStatus || surfaceStatus || "idle";
}

function deriveIndustryScheduleStatus(
  schedule: IndustryInstanceDetail["schedules"][number],
): string {
  const status = String(schedule.status || "").trim();
  if (!schedule.enabled) {
    return "paused";
  }
  if (status === "waiting-confirm") {
    return "waiting-confirm";
  }
  if (status === "running" || status === "active" || status === "scheduled") {
    return "active";
  }
  return status || "scheduled";
}

function deriveIndustryTeamStatus(detail: IndustryInstanceDetail | null): string {
  if (!detail) {
    return "draft";
  }
  const executionStatus = String(detail.execution?.status || "").trim();
  if (executionStatus) {
    return executionStatus;
  }
  if (detail.agents.some((agent) => deriveIndustryAgentStatus(agent) === "waiting-confirm")) {
    return "waiting-confirm";
  }
  if (
    detail.agents.length > 0 &&
    detail.agents.every((agent) => deriveIndustryAgentStatus(agent) === "degraded")
  ) {
    return "degraded";
  }
  if (
    detail.schedules.some((schedule) => schedule.enabled) ||
    detail.agents.some((agent) => deriveIndustryAgentStatus(agent) === "active")
  ) {
    return "active";
  }
  const detailStatus = String(detail.status || "").trim();
  if (detailStatus === "draft") {
    return "draft";
  }
  if (
    ["waiting-confirm", "degraded", "blocked", "retired", "paused"].includes(
      detailStatus,
    )
  ) {
    return detailStatus;
  }
  return "idle";
}


export {
  type IndustryBriefFormValues,
  type IndustryBriefMediaItem,
  type InstallPlanDraftItem,
  INDUSTRY_TEXT,
  INDUSTRY_EXPERIENCE_TEXT,
  INDUSTRY_ROLE_CLASS_LABELS,
  formatIndustryDisplayToken,
  presentIndustryRuntimeStatus,
  presentIndustryRoleClass,
  presentIndustryEmploymentMode,
  presentIndustryRiskLevel,
  presentIndustryReadinessStatus,
  formatCountLabel,
  formatIndustryDetailStats,
  RECOMMENDATION_SECTION_LABELS,
  CAPABILITY_FAMILY_OPTIONS,
  INSTALL_ASSIGNMENT_MODE_OPTIONS,
  parseLines,
  uniqueStrings,
  nextInstallPlanItemKey,
  recommendationPlanItemKey,
  stripInstallPlanDraftItem,
  createBlankInstallPlanItem,
  buildFallbackRecommendationSections,
  LinesTextArea,
  toPreviewPayload,
  normalizeRoleBlueprint,
  normalizeGoal,
  normalizeSchedule,
  normalizeDraftPlan,
  detailToDraftPlan,
  createBlankRole,
  createBlankGoal,
  createBlankSchedule,
  recommendationToInstallItem,
  readinessColor,
  roleColor,
  isSystemRole,
  formatTimestamp,
  presentText,
  presentList,
  runtimeStatusColor,
  deriveIndustryAgentStatus,
  deriveIndustryScheduleStatus,
  deriveIndustryTeamStatus,
};


