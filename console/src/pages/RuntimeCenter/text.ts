import { normalizeDisplayChinese } from "../../text";
import { presentRuntimeStatusLabel } from "../../runtime/executionPresentation";
import { runtimeRiskLabel } from "../../runtime/tagSemantics";
import { presentInsightText } from "../Insights/presentation";

const DEFAULT_RUNTIME_SURFACE_NOTE =
  "运行中心是由共享状态、证据、目标、学习与环境服务支撑的统一操作面。";
const DEFAULT_RUNTIME_GOVERNANCE_TITLE = "运行治理";
const DEFAULT_RUNTIME_ACCEPTING_SUMMARY = "运行时正在接收新工作。";

const MAIN_BRAIN_SIGNAL_LABELS: Record<string, string> = {
  carrier: "载体",
  strategy: "策略",
  lanes: "泳道",
  backlog: "待办",
  current_cycle: "当前周期",
  assignments: "派工",
  agent_reports: "智能体汇报",
  environment: "环境",
  governance: "运行治理",
  automation: "自动化",
  recovery: "恢复",
  evidence: "证据",
  decisions: "决策",
  patches: "补丁",
};

const ACTION_LABELS: Record<string, string> = {
  compile: "编译",
  dispatch: "派发",
  approve: "批准",
  reject: "驳回",
  review: "审查",
  apply: "应用",
  delete: "删除",
  run: "执行",
  diagnosis: "诊断",
  pause: "暂停",
  resume: "恢复",
  rollback: "回滚",
  "emergency-stop": "紧急停止",
  "decisions-approve": "批量批准决策",
  "decisions-reject": "批量驳回决策",
  "patches-approve": "批量批准补丁",
  "patches-apply": "批量应用补丁",
  "patches-rollback": "批量回滚补丁",
  "patches-reject": "批量驳回补丁",
};

const STATUS_LABEL_OVERRIDES: Record<string, string> = {
  "state-service": "状态服务",
  unavailable: "未接入",
  terminated: "已终止",
  scheduled: "已排程",
};

const ENTRY_KIND_LABELS: Record<string, string> = {
  task: "任务",
  goal: "目标",
  schedule: "计划",
  agent: "智能体",
  capability: "能力",
  evidence: "证据",
  decision: "决策",
  patch: "补丁",
  growth: "成长",
  industry: "行业",
  runtime: "运行时",
  environment: "环境",
  routine: "例行",
};

const SOURCE_LABELS: Record<string, string> = {
  state_query_service: "状态查询服务",
  industry_service: "行业服务",
  agent_profile_service: "智能体画像服务",
  prediction_service: "预测服务",
  capability_service: "能力服务",
  evidence_query_service: "证据查询服务",
  governance_service: "治理服务",
  learning_service: "学习服务",
  routine_service: "例行服务",
  unavailable: "未接入源",
};

const FIELD_LABELS: Record<string, string> = {
  id: "编号",
  name: "名称",
  core_runtime_ready: "核心运行时就绪",
  memory_vector_ready: "记忆向量检索就绪",
  memory_embedding_config: "记忆嵌入配置",
  browser_surface_ready: "浏览器执行面就绪",
  desktop_surface_ready: "桌面执行面就绪",
  path: "路径",
  exists: "是否存在",
  count: "数量",
  slots: "回退槽位",
  active_model: "活跃模型",
  recovery_summary: "恢复摘要",
  control_id: "控制编号",
  emergency_stop_active: "紧急停止状态",
  emergency_actor: "紧急停止执行体",
  emergency_reason: "紧急停止原因",
  read_only: "只读",
  services: "关联服务",
  mode: "模式",
  version: "版本",
  source: "来源",
  total: "总数",
  visible_count: "可见数量",
  truncated: "是否截断",
  recent_count: "最近数量",
  by_status: "按状态统计",
  by_kind: "按类型统计",
  pending_decisions: "待处理决策",
  pending_patches: "待处理补丁",
  paused_schedule_ids: "已暂停计划编号",
  channel_shutdown_applied: "渠道关闭已生效",
  reason: "原因",
  recovered_at: "恢复时间",
  reaped_expired_leases: "已回收过期租约",
  recovered_orphaned_leases: "已恢复孤儿租约",
  reaped_expired_actor_leases: "已回收过期执行体租约",
  recovered_orphaned_actor_leases: "已恢复孤儿执行体租约",
  recovered_orphaned_mailbox_items: "已恢复孤儿邮箱项",
  requeued_orphaned_mailbox_items: "已重新入队邮箱项",
  blocked_orphaned_mailbox_items: "已阻塞孤儿邮箱项",
  resolved_orphaned_mailbox_items: "已落终态邮箱项",
  expired_decisions: "已过期决策",
  hydrated_waiting_confirm_tasks: "已补水待确认任务",
  active_schedules: "激活计划",
  current_progress_summary: "当前进展摘要",
  latest_evidence_summary: "最新证据摘要",
  role_summary: "角色摘要",
  current_environment_id: "当前环境",
  last_result_summary: "最近结果摘要",
  last_error_summary: "最近错误摘要",
  current_task_id: "当前任务编号",
  current_mailbox_id: "当前邮箱编号",
  last_checkpoint_id: "最近检查点编号",
  queue_depth: "队列深度",
  desired_state: "调度目标",
  runtime_status: "运行状态",
  actor_class: "执行体类型",
  actor_key: "执行体键",
  actor_fingerprint: "执行体指纹",
  industry_instance_id: "行业实例",
  industry_role_id: "行业角色",
  owner_agent_id: "负责人智能体",
  task_id: "任务编号",
  mailbox_id: "邮箱编号",
  checkpoint_kind: "检查点类型",
  phase: "阶段",
  created_at: "创建时间",
  started_at: "开始时间",
  completed_at: "完成时间",
  notes: "备注",
  updated_at: "更新时间",
  blocked_capability_refs: "阻断能力引用",
  required_services: "必需服务",
  missing_services: "缺失服务",
  doctor_status: "诊断状态",
  template_id: "模板编号",
  vector_enabled: "向量检索已启用",
  vector_disable_reason_code: "向量降级代码",
  vector_disable_reason: "向量降级原因",
  embedding_api_key_configured: "已配置嵌入 API Key",
  embedding_base_url: "嵌入基础地址",
  embedding_model_name: "嵌入模型名",
  embedding_model_inferred: "嵌入模型为推断值",
  embedding_follow_active_provider: "跟随当前激活提供方",
  embedding_provider_inherited: "已继承提供方配置",
  embedding_provider_id: "嵌入提供方编号",
  embedding_provider_name: "嵌入提供方名称",
  embedding_provider_model_slot: "继承模型槽位",
  fts_enabled: "全文检索已启用",
  memory_store_backend: "记忆存储后端",
  headline: "Review headline",
  objective: "Task objective",
  execution_state: "Execution state",
  current_stage: "Current stage",
  recent_failures: "Recent failures",
  effective_actions: "Effective moves",
  avoid_repeats: "Avoid repeats",
  feedback_evidence_refs: "Evidence refs",
  blocked_reason: "Blocked reason",
  stuck_reason: "Stuck reason",
  next_step: "Next step",
  summary_lines: "Review summary",
  next_actions: "Next actions",
  risks: "Risks",
  owner_agent_name: "Owner",
  routine_id: "例行编号",
  routine_run_id: "例行运行编号",
  fixed_sop_binding_id: "固定 SOP 绑定编号",
  fixed_sop_run_id: "固定 SOP 运行编号",
  fixed_sop_evidence_id: "固定 SOP 证据编号",
  routine_key: "例行键",
  last_run_id: "最近运行编号",
  diagnosis: "诊断",
  drift_status: "漂移状态",
  selector_health: "选择器健康度",
  session_health: "会话健康度",
  lock_health: "锁健康度",
  evidence_health: "证据健康度",
  failure_class: "失败分类",
  fallback_mode: "回退模式",
  fallback_summary: "回退摘要",
  resource_conflicts: "资源冲突",
  recommended_actions: "建议动作",
  engine_kind: "执行引擎",
  trigger_kind: "触发方式",
  success_rate: "成功率",
  recent_success_rate: "最近成功率",
  last_verified_at: "最近验证时间",
  last_failure_class: "最近失败分类",
  last_fallback: "最近回退",
};

const SECTION_LABELS: Record<string, string> = {
  schedule: "计划",
  state: "状态",
  spec: "规格",
  task: "任务",
  runtime: "运行时",
  host_contract: "主机合同",
  seat_runtime: "席位运行态",
  host_companion_session: "主机伴随会话",
  browser_site_contract: "浏览器站点合同",
  desktop_app_contract: "桌面应用合同",
  cooperative_adapter_availability: "协作适配器可用性",
  workspace_graph: "工作区图谱",
  host_twin: "宿主孪生",
  host_event_summary: "主机事件摘要",
  host_events: "主机事件",
  goal: "目标",
  decision: "决策",
  patch: "补丁",
  event: "事件",
  agent: "智能体",
  mailbox: "邮箱",
  checkpoints: "检查点",
  teammates: "协作对象",
  leases: "租约",
  industry: "行业",
  kernel: "内核",
  profile: "画像",
  team: "团队",
  reports: "报告",
  stats: "统计",
  routes: "路由",
  tasks: "任务列表",
  agents: "智能体列表",
  patches: "补丁列表",
  growth: "成长",
  evidence: "证据",
  decisions: "决策列表",
  frames: "帧",
  detail: "详情",
  diagnosis: "诊断",
  capability_surface: "能力面",
  review: "执行审查",
  focus: "当前焦点",
  knowledge: "知识",
  delegation: "委派",
  routine: "例行",
  routines: "例行列表",
};

const CARD_TITLE_LABELS: Record<string, string> = {
  goals: "目标",
  tasks: "任务",
  routines: "例行",
  schedules: "计划",
  decisions: "决策",
  patches: "补丁",
  agents: "智能体",
  industry: "行业",
  governance: "运行治理",
  evidence: "证据",
  capabilities: "能力",
  growth: "成长",
  runtime: "运行时",
  predictions: "预测",
};

const ROUTE_TITLE_LABELS: Array<[string, string]> = [
  ["/api/routines/runs/", "例行运行详情"],
  ["/routines/runs/", "例行运行详情"],
  ["/diagnosis", "例行诊断"],
  ["/api/routines/", "例行详情"],
  ["/routines/", "例行详情"],
  ["/runtime-center/tasks/", "任务详情"],
  ["/runtime-center/schedules/", "计划详情"],
  ["/api/goals/", "目标详情"],
  ["/goals/", "目标详情"],
  ["/runtime-center/decisions/", "决策详情"],
  ["/runtime-center/learning/patches/", "补丁详情"],
  ["/runtime-center/learning/growth/", "成长详情"],
  ["/runtime-center/agents/", "智能体详情"],
  ["/runtime-center/actors/", "执行体详情"],
  ["/runtime-center/industry/", "行业详情"],
  ["/runtime-center/recovery/latest", "恢复详情"],
];

const RECOVERY_FIELD_LABELS: Record<string, string> = {
  reason: "恢复原因",
  recovered_at: "恢复时间",
  reaped_expired_leases: "已回收过期租约",
  recovered_orphaned_leases: "已恢复孤儿租约",
  expired_decisions: "已过期决策",
  hydrated_waiting_confirm_tasks: "已补水待确认任务",
  active_schedules: "激活计划",
  notes: "备注",
};

const CAPABILITY_MODE_LABELS: Record<string, string> = {
  replace: "替换",
  merge: "合并",
};

const CAPABILITY_ASSIGNMENT_SOURCE_LABELS: Record<string, string> = {
  baseline: "基线",
  blueprint: "蓝图",
  explicit: "显式",
  recommended: "推荐",
  effective: "生效",
};

const SCHEDULE_TASK_TYPE_LABELS: Record<string, string> = {
  text: "文本任务",
  agent: "智能体任务",
};

const DISPATCH_MODE_LABELS: Record<string, string> = {
  stream: "流式",
  final: "最终结果",
};

const IDENTIFIER_LABELS: Record<string, string> = {
  working_dir: "工作目录",
  state_store: "状态存储",
  evidence_ledger: "证据台账",
  capability_service: "能力服务",
  kernel_dispatcher: "内核分发器",
  runtime_event_bus: "运行事件总线",
  governance_service: "治理服务",
  cron_manager: "自动化调度器",
  provider_active_model: "活跃模型",
  provider_fallback: "回退链",
  startup_recovery: "启动恢复",
  startup: "启动",
  restart: "重启",
};

const EXACT_RUNTIME_TEXT_MAP: Record<string, string> = {
  Tasks: "任务",
  Goals: "目标",
  Schedules: "计划",
  Agents: "智能体",
  "Industry Teams": "身份",
  Capabilities: "能力",
  Predictions: "预测",
  Evidence: "证据",
  Decisions: "确认事项",
  Patches: "主脑建议",
  Growth: "成长",
  Governance: "治理",
  "Runtime governance": "运行治理",
  "Tracked runtime tasks from the unified state store.":
    "来自统一状态存储的运行任务。",
  "Top-level intent and plan objects from GoalService.":
    "来自目标服务的顶层意图与计划对象。",
  "Scheduled jobs and automation state from ScheduleRecord.":
    "来自计划记录的定时任务与自动化状态。",
  "Visible agent profiles merged from defaults, overrides, and runtime state.":
    "由默认配置、覆盖项与运行时状态合并得到的可见智能体画像。",
  "Formal industry instances, team blueprints, and linked runtime objects.":
    "正式行业实例、团队蓝图及其关联运行对象。",
  "Structured prediction cases, governed recommendations, and operating-cycle outcomes.":
    "结构化预测案例、受治理建议与主脑周期结果。",
  "Pending and resolved governance decisions from DecisionRequestRecord.":
    "主脑已判断后沉淀的确认事项与治理记录。",
  "Patch proposals and applications from the learning layer.":
    "主脑学习层提出并执行的系统修复与优化建议。",
  "Applied learning changes and growth events by agent.":
    "按智能体聚合的已应用学习变更与成长事件。",
  "Capability graph is not available.": "能力图谱当前不可用。",
  "Evidence view is not available.": "证据视图当前不可用。",
  "Governance controls are not available.": "治理控制当前不可用。",
  "Runtime is accepting new work.": "运行时正在接收新工作。",
  "Working directory exists.": "工作目录存在。",
  "Working directory is missing.": "工作目录缺失。",
  "Unified state store is wired.": "统一状态存储已接入。",
  "State store is not attached to app.state.": "状态存储尚未挂载到 app.state。",
  "Evidence ledger is wired.": "证据台账已接入。",
  "Evidence ledger is not attached to app.state.":
    "证据台账尚未挂载到 app.state。",
  "Active provider/model is missing or unresolved.":
    "当前活跃提供方或模型缺失，或尚未解析。",
  "Fallback chain is configured.": "回退链已配置。",
  "Fallback chain is empty.": "回退链为空。",
  "Startup recovery summary is available.": "启动恢复摘要可用。",
  "Startup recovery summary is missing.": "启动恢复摘要缺失。",
  "Recovered expired decision during startup.":
    "已在启动阶段回收过期决策。",
  "Started interactive query turn": "已启动交互式查询轮次",
  "Loaded session state for interactive query turn": "已加载交互式查询轮次的会话状态",
  "Query completed": "查询已完成",
  "Command completed": "命令已完成",
  "Task requires human confirmation before execution.":
    "任务需要人工确认后才能执行。",
  "Task admitted to the kernel and is ready for execution.":
    "任务已进入内核并准备执行。",
  "Task approved and released for execution.": "任务已批准并释放执行。",
  "Decision expired before confirmation.": "决策在确认前已过期。",
  "workspace + browser + session": "工作区 + 浏览器 + 会话",
  "kernel confirmation required": "内核确认中",
  "kernel task approved": "内核任务已批准",
  "kernel task completed": "内核任务已完成",
  "kernel task failed": "内核任务失败",
  "kernel task cancelled": "内核任务已取消",
  "kernel decision expired": "内核决策已过期",
  "runtime emergency stop": "运行紧急停止",
  "runtime governance resume": "运行治理恢复",
  "Emergency stop activated for runtime operations.":
    "已对运行操作生效紧急停止。",
  "Runtime operations resumed.": "运行操作已恢复。",
  "Dispatched command through the kernel-owned command execution service.":
    "已通过内核托管的命令执行服务派发命令。",
  "Dispatched query through the kernel-owned query execution service.":
    "已通过内核托管的查询执行服务派发查询。",
};

const RUNTIME_REGEX_TEXT_MAP: Array<{
  pattern: RegExp;
  replace: (...matches: string[]) => string;
}> = [
  {
    pattern: /^(.+?) view is not available\.$/,
    replace: (title) => `${localizeRuntimeText(title)}视图当前不可用。`,
  },
  {
    pattern: /^([a-z_]+) is available\.$/,
    replace: (name) => `${localizeRuntimeIdentifier(name)}已可用。`,
  },
  {
    pattern: /^([a-z_]+) is not available\.$/,
    replace: (name) => `${localizeRuntimeIdentifier(name)}当前不可用。`,
  },
  {
    pattern: /^Active provider ['"](.+?)['"] is available\.$/,
    replace: (providerId) => `活跃提供方“${providerId}”可用。`,
  },
  {
    pattern: /^Streaming message (\d+)$/,
    replace: (count) => `流式消息片段 ${count}`,
  },
  {
    pattern: /^Replay shell command: (.+)$/,
    replace: (command) => `回放 shell 命令：${command}`,
  },
  {
    pattern: /^Task ['"](.+?)['"] is held for operator confirmation\.$/,
    replace: (title) => `任务“${localizeRuntimeText(title)}”正在等待人工确认。`,
  },
  {
    pattern: /^Task ['"](.+?)['"] was approved for execution\.$/,
    replace: (title) => `任务“${localizeRuntimeText(title)}”已获批准并进入执行。`,
  },
  {
    pattern: /^Task ['"](.+?)['"] executed\.$/,
    replace: (title) => `任务“${localizeRuntimeText(title)}”已执行完成。`,
  },
  {
    pattern: /^Approve kernel task ['"](.+?)['"] before execution\.$/,
    replace: (title) => `任务“${localizeRuntimeText(title)}”执行前需要先通过内核批准。`,
  },
  {
    pattern: /^Claimed mailbox item (.+)$/i,
    replace: (mailboxId) => `已领取邮箱项 ${mailboxId}`,
  },
  {
    pattern: /^session closed as (.+)$/i,
    replace: (status) => `会话已按“${formatRuntimeStatus(status)}”状态关闭`,
  },
  {
    pattern: /^lease expired$/i,
    replace: () => "租约已过期",
  },
  {
    pattern: /^live handle unavailable during runtime recovery$/i,
    replace: () => "运行恢复期间活动句柄不可用",
  },
  {
    pattern: /^reap_expired_leases failed: (.+)$/,
    replace: (detail) => `回收过期租约失败：${detail}`,
  },
  {
    pattern: /^recover_orphaned_leases failed: (.+)$/,
    replace: (detail) => `恢复孤儿租约失败：${detail}`,
  },
  {
    pattern: /^reap_expired_actor_leases failed: (.+)$/,
    replace: (detail) => `回收过期执行体租约失败：${detail}`,
  },
  {
    pattern: /^recover_orphaned_actor_leases failed: (.+)$/,
    replace: (detail) => `恢复孤儿执行体租约失败：${detail}`,
  },
  {
    pattern: /^recover_orphaned_mailbox_items failed: (.+)$/,
    replace: (detail) => `恢复孤儿邮箱项失败：${detail}`,
  },
  {
    pattern: /^expire_decision failed for (.+?): (.+)$/,
    replace: (decisionId, detail) => `将决策 ${decisionId} 标记为过期失败：${detail}`,
  },
  {
    pattern: /^expire_decision_request failed for (.+?): (.+)$/,
    replace: (decisionId, detail) => `将决策请求 ${decisionId} 标记为过期失败：${detail}`,
  },
  {
    pattern: /^hydrate waiting-confirm task failed for (.+?): (.+)$/,
    replace: (taskId, detail) => `补水待确认任务 ${taskId} 失败：${detail}`,
  },
  {
    pattern: /^schedule scan failed: (.+)$/,
    replace: (detail) => `扫描计划失败：${detail}`,
  },
  {
    pattern: /^(.+?) Researcher$/,
    replace: (label) => `${label}研究员`,
  },
  {
    pattern: /^Industry Researcher$/,
    replace: () => "行业研究员",
  },
  {
    pattern: /^(.+?) Solution Lead$/,
    replace: (label) => `${label}方案负责人`,
  },
  {
    pattern: /^Solution Lead$/,
    replace: () => "方案负责人",
  },
  {
    pattern: /^Daily control loop for (.+)$/,
    replace: (label) => `${label}每日执行中枢循环`,
  },
  {
    pattern: /^Evidence signal sweep for (.+)$/,
    replace: (label) => `${label}证据信号扫描`,
  },
  {
    pattern: /^Daily control review for (.+)$/,
    replace: (label) => `${label}每日执行复盘`,
  },
  {
    pattern: /^Weekly synthesis for (.+)$/,
    replace: (label) => `${label}周度信号综述`,
  },
  {
    pattern: /^Control brief for (.+)$/,
    replace: (label) => `${label}执行简报`,
  },
  {
    pattern: /^Weekly signal synthesis for (.+)$/,
    replace: (label) => `${label}周度信号综述`,
  },
  {
    pattern: /^No recovery path is currently available\.$/,
    replace: () => "当前没有可用的恢复路径。",
  },
  {
    pattern: /^Live handle is mounted in the current runtime host\.$/,
    replace: () => "当前运行主机已挂载活动句柄。",
  },
];

function localizeRuntimeIdentifier(value: string): string {
  const normalized = value.trim();
  if (!normalized) {
    return value;
  }
  return IDENTIFIER_LABELS[normalized] || humanizeToken(normalized);
}

function localizeRuntimePlainLine(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    return value;
  }
  if (Object.prototype.hasOwnProperty.call(EXACT_RUNTIME_TEXT_MAP, trimmed)) {
    return EXACT_RUNTIME_TEXT_MAP[trimmed];
  }
  let translated = trimmed;
  for (const item of RUNTIME_REGEX_TEXT_MAP) {
    translated = translated.replace(item.pattern, (...matches) =>
      item.replace(...matches.slice(1, -2)),
    );
  }
  if (translated === trimmed) {
    const insightTranslated = presentInsightText(trimmed);
    if (insightTranslated && insightTranslated !== trimmed) {
      return insightTranslated;
    }
  }
  return normalizeDisplayChinese(translated);
}

export function localizeRuntimeText(value: string | null | undefined): string {
  if (!value) {
    return "";
  }
  const normalized = String(value).trim();
  if (!normalized) {
    return "";
  }
  return normalized
    .split("\n")
    .map((line) => {
      const bullet = line.match(/^(\s*(?:[-*]|\d+\.)\s+)(.*)$/);
      if (!bullet) {
        return localizeRuntimePlainLine(line);
      }
      return `${bullet[1]}${localizeRuntimePlainLine(bullet[2])}`;
    })
    .join("\n");
}

export const COMMON_TEXT = {
  refresh: "刷新",
  save: "保存",
  cancel: "取消",
  edit: "编辑",
  delete: "删除",
  status: "状态",
  actions: "操作",
  create: "创建",
} as const;

export const RUNTIME_CENTER_TEXT = {
  capabilitySurfaceSectionTitle: "角色能力面",
  pageTitle: "运行中心",
  pageDescription: "从统一运行面查看状态、治理、恢复与自动化。",
  tabGovernanceDescription:
    "在统一治理面控制紧急停止、处理守护型决策，并管理学习补丁。",
  tabRecoveryDescription:
    "查看启动恢复结果，并在恢复自主执行前运行实时自检。",
  automationPageDescription:
    "在统一运行中心自动化面管理心跳和定时任务。",
  generatedAt: (timestamp: string) => `生成时间：${timestamp}`,
  waitingForData: "等待数据返回",
  tabOverview: "总览",
  tabGovernance: "治理",
  tabRecovery: "恢复",
  tabAutomation: "自动化",
  cardEmpty: (title: string) => `${title}暂无内容`,
  governanceState: "运行状态",
  runtimePaused: "已暂停",
  runtimeAccepting: "接收中",
  runtimeAcceptingSummary: "运行时正在接收新工作。",
  pendingDecisions: "待你确认",
  pendingPatches: "待生效建议",
  pausedSchedules: "已暂停计划",
  governanceControls: "治理控制",
  governanceControlsSummary:
    "紧急停止会阻止新工作进入；恢复前请先检查仍需你授权的事项和待生效的主脑建议。",
  operatorActor: "操作执行体",
  emergencyReason: "紧急停止原因",
  emergencyStop: "紧急停止",
  resumeRuntime: "恢复运行",
  resumeReason: "恢复说明",
  blockedCapabilities: "已阻断能力",
  channelShutdown: "渠道关闭",
  updatedAt: "更新时间",
  decisionBatchTitle: "需要你确认",
  decisionBatchSummary:
    "主脑默认先做判断；只有主脑无法独立判断或动作触及外部责任边界时，才会在这里请你确认。",
  batchResolution: "确认说明",
  executeApprovedDecisions: "确认后立即执行",
  selectAll: "全选",
  clearSelection: "清空",
  batchApprove: "批准所选",
  batchReject: "驳回所选",
  noPendingDecisions: "当前没有需要你确认的事项。",
  patchBatchTitle: "主脑变更建议",
  patchBatchSummary:
    "主脑提出的系统修复与优化建议。低风险建议应默认自动生效，这里只保留需要人工把关的例外。",
  batchApply: "应用所选",
  batchRollback: "回滚所选",
  noVisiblePatches: "当前没有待处理的主脑变更建议。",
  recoveryReason: "恢复原因",
  selfCheckStatus: "自检状态",
  recoveryItems: "恢复字段",
  selfCheckChecks: "检查项",
  recoveryLedger: "最近恢复账本",
  recoveryLedgerSummary: "运行主机记录的最近一次启动或重启恢复摘要。",
  openDetail: "查看详情",
  noRecoverySummary: "当前没有恢复摘要。",
  selfCheckPanel: "实时自检",
  selfCheckPanelSummary:
    "在恢复自主执行前，运行文件系统、状态和证据健康检查。",
  selfCheckCompleted: "自检已完成。",
  runSelfCheck: "运行自检",
  noSelfCheck: "运行一次自检以检查运行时健康状态。",
  actionCompleted: (action: string) => `${action}已完成`,
  actionFailed: "操作失败",
  confirmationRequired: "操作已进入确认流程。",
  confirmationRequiredWithId: (id: string) =>
    `操作已进入确认流程，决策单 ${id}。`,
  resolutionApproved: "批准",
  resolutionRejected: "驳回",
  defaultEmergencyReason: "运行中心人工触发紧急停止",
  defaultResumeReason: "运行中心确认后恢复运行",
  selectDecisionBatch: "请至少选择一个需要确认的事项。",
  selectPatchBatch: "请至少选择一个主脑变更建议。",
  noTimestamp: "无时间",
  emptyValue: "--",
  booleanTrue: "是",
  booleanFalse: "否",
  surfaceUnavailable: "运行面暂不可用",
  loadingSurfaceMetadata: "正在加载运行面元数据",
  surfaceNote:
    "运行中心是由共享状态、证据、目标、学习与环境服务支撑的统一操作面。",
} as const;

export const AUTOMATION_TEXT = {
  saved: "已保存",
  deleted: "已删除",
  confirmDelete: "确认删除",
  deleteConfirm: "删除后不可恢复，确认继续吗？",
  heartbeat: {
    title: "心跳",
    enabled: "启用",
    every: "执行频率",
    everyRequired: "请输入执行频率",
    everyMin: "频率必须大于等于 1",
    target: "监督目标",
    targetMain: "主脑监督",
    targetLast: "最近会话",
    activeHours: "启用活跃时段",
    activeStart: "开始时间",
    activeEnd: "结束时间",
    saveSuccess: "心跳配置已保存。",
    loadFailed: "加载心跳配置失败",
    summary: "心跳现已纳入运行中心自动化面，并作为主脑监督脉冲运行。",
    hint:
      "心跳会触发 `system:run_operating_cycle`，由主脑统一执行监督、检查回流、推动下一轮正式 operating cycle。",
    queryPathLabel: "查询路径",
  },
  schedules: {
    title: "定时任务",
    summary: "定时任务已直接并入运行中心，不再依赖旧版定时任务页面。",
    hint:
      "定时任务现在是运行中心的一等对象，创建、编辑、执行、暂停、恢复和删除都通过统一计划面完成。",
    createJob: "创建任务",
    editJob: "编辑任务",
    id: "编号",
    name: "名称",
    enabled: "启用",
    scheduleCronLabel: "定时表达式",
    cronTypeHourly: "每小时",
    cronTypeDaily: "每天",
    cronTypeWeekly: "每周",
    cronTypeCustom: "自定义",
    cronTime: "执行时间",
    cronDaysOfWeek: "执行星期",
    cronDayMon: "周一",
    cronDayTue: "周二",
    cronDayWed: "周三",
    cronDayThu: "周四",
    cronDayFri: "周五",
    cronDaySat: "周六",
    cronDaySun: "周日",
    cronCustomExpression: "自定义定时表达式",
    scheduleTimezone: "时区",
    taskType: "任务类型",
    taskTypeTextLabel: "文本任务",
    taskTypeAgentLabel: "智能体任务",
    text: "文本内容",
    requestInput: "请求输入 JSON",
    requestInputPlaceholder: '{\n  "goal": "示例"\n}',
    dispatchChannel: "派发渠道",
    dispatchTargetUserId: "目标用户编号",
    dispatchTargetSessionId: "目标会话编号",
    dispatchMode: "派发模式",
    dispatchModeStreamLabel: "流式",
    dispatchModeFinalLabel: "最终结果",
    runtimeMaxConcurrency: "最大并发",
    runtimeTimeoutSeconds: "超时秒数",
    runtimeMisfireGraceSeconds: "误触发宽限秒数",
    pleaseInputId: "请输入任务编号",
    pleaseInputName: "请输入任务名称",
    pleaseInputCron: "请输入定时表达式",
    pleaseSelectTaskType: "请选择任务类型",
    pleaseInputRequest: "请输入任务内容",
    invalidJsonFormat: "JSON 格式无效",
    pleaseInputChannel: "请输入派发渠道",
    pleaseInputUserId: "请输入目标用户编号",
    pleaseInputSessionId: "请输入目标会话编号",
    confirmDelete: "确认删除该定时任务吗？",
  },
  scheduleLastRunLabel: "上次运行",
  scheduleNextRunLabel: "下次运行",
} as const;

export const CAPABILITY_SURFACE_TEXT = {
  noCapabilityGovernance: "当前没有能力治理请求。",
  capabilityDecisionTitle: "能力治理决策",
  openCapabilityDecision: "查看决策",
  capabilityDecisionTaskTitle: "能力治理任务",
  openCapabilityTask: "查看任务",
  capabilityDecisionExpires: (time: string) => `到期 ${time}`,
  capabilitySurfaceUnavailable: "当前还没有可展示的能力面。",
  capabilitySurfaceEyebrow: "角色能力面",
  capabilityModeTag: (mode: string) => `默认 ${formatCapabilityMode(mode)}`,
  capabilityActorMounted: "执行体已挂载",
  capabilityProfileOnly: "仅配置投影",
  capabilityApplyRoleMounted: "角色调整能力已挂载",
  capabilityApplyRoleMissing: "角色调整能力未挂载",
  capabilityDriftDetected: "推荐集与生效集存在漂移",
  capabilityAligned: "推荐集与生效集已对齐",
  capabilityGovernedWritePath: "治理写入口可用",
  capabilityDirectWritePath: "直写入口存在",
  capabilitySurfaceSummary:
    "这里直接展示当前角色的分派权、治理权、工具、技能、模型上下文协议构成，以及这些能力需要的环境和应产出的证据。",
  capabilityEffectiveCount: "生效能力",
  capabilityDispatchCount: "分派能力",
  capabilityGovernanceCount: "治理能力",
  capabilityPendingDecisionCount: "待治理请求",
  capabilityRightsTitle: "执行权与治理权",
  capabilityDispatchTitle: "分派权",
  noDispatchCapabilities: "当前没有系统分派能力。",
  capabilityGovernanceTitle: "治理权",
  noGovernanceCapabilities: "当前没有治理能力。",
  capabilityCompositionTitle: "能力构成",
  capabilityToolsTitle: "工具",
  noToolCapabilities: "当前没有生效工具能力。",
  capabilitySkillsTitle: "技能",
  noSkillCapabilities: "当前没有生效技能能力。",
  capabilityMcpTitle: "模型上下文协议",
  noMcpCapabilities: "当前没有生效的模型上下文协议能力。",
  capabilityOtherTitle: "其他",
  noOtherCapabilities: "当前没有其他来源能力。",
  capabilityDriftTitle: "推荐差异",
  capabilityRecommendedMissingTitle: "推荐但未生效",
  capabilityRecommendedMissingEmpty: "系统推荐集已经全部生效。",
  capabilityExplicitAdditionTitle: "显式附加",
  capabilityExplicitAdditionEmpty: "当前没有超出推荐集的显式附加能力。",
  capabilityRuntimeContractTitle: "运行约束",
  capabilityEnvironmentTitle: "环境依赖",
  capabilityEnvironmentEmpty: "当前生效能力没有额外环境依赖声明。",
  capabilityEvidenceTitle: "证据契约",
  capabilityEvidenceEmpty: "当前生效能力没有额外证据契约声明。",
  capabilityRiskMixTitle: "风险分布",
  capabilityRiskAuto: (count: number) => `自动 ${count}`,
  capabilityRiskGuarded: (count: number) => `守护 ${count}`,
  capabilityRiskConfirm: (count: number) => `确认 ${count}`,
  capabilityDecisionQueueTitle: "治理队列",
} as const;

export const MAIN_BRAIN_COCKPIT_TEXT = {
  title: "主脑今日运行简报",
  description:
    "先看主脑今天要完成什么、做到哪里、卡在哪里，再决定是否进入治理、恢复和更深的运行细节。",
} as const;

export function humanizeToken(value: string): string {
  return normalizeDisplayChinese(
    value
      .replace(/[_-]/g, " ")
      .replace(/([a-z])([A-Z])/g, "$1 $2")
      .replace(/\b\w/g, (chunk) => chunk.toUpperCase()),
  );
}

export function formatRuntimeActionLabel(action: string): string {
  return ACTION_LABELS[action] || humanizeToken(action);
}

export function formatRuntimeStatus(value: string): string {
  return STATUS_LABEL_OVERRIDES[value] || presentRuntimeStatusLabel(value);
}

export function formatRuntimeEntryKind(value: string): string {
  if (value === "work-context") {
    return "工作上下文";
  }
  return ENTRY_KIND_LABELS[value] || humanizeToken(value);
}

export function formatRuntimeCardTitle(key: string, fallback: string): string {
  if (key === "work-contexts") {
    return "工作上下文";
  }
  return CARD_TITLE_LABELS[key] || localizeRuntimeText(fallback);
}

export function formatRuntimeCardSummary(key: string, fallback: string): string {
  if (key === "governance" && fallback === DEFAULT_RUNTIME_ACCEPTING_SUMMARY) {
    return RUNTIME_CENTER_TEXT.runtimeAcceptingSummary;
  }
  return localizeRuntimeText(fallback);
}

export function formatRuntimeSourceToken(value: string): string {
  const normalized = value.trim();
  return SOURCE_LABELS[normalized] || humanizeToken(normalized);
}

export function formatRuntimeSourceList(value?: string | null): string {
  if (!value) {
    return RUNTIME_CENTER_TEXT.surfaceUnavailable;
  }
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => formatRuntimeSourceToken(item))
    .join(" / ");
}

export function formatRuntimeSurfaceNote(value?: string | null): string {
  if (!value) {
    return RUNTIME_CENTER_TEXT.loadingSurfaceMetadata;
  }
  if (value === DEFAULT_RUNTIME_SURFACE_NOTE) {
    return RUNTIME_CENTER_TEXT.surfaceNote;
  }
  return localizeRuntimeText(value);
}

export function formatRuntimeEntryTitle(cardKey: string, title: string): string {
  if (cardKey === "governance" && title === DEFAULT_RUNTIME_GOVERNANCE_TITLE) {
    return "运行治理";
  }
  return localizeRuntimeText(title);
}

export function formatRuntimeEntrySummary(
  cardKey: string,
  summary?: string | null,
): string | null | undefined {
  if (!summary) {
    return summary;
  }
  if (cardKey === "governance" && summary === DEFAULT_RUNTIME_ACCEPTING_SUMMARY) {
    return RUNTIME_CENTER_TEXT.runtimeAcceptingSummary;
  }
  return localizeRuntimeText(summary);
}

export function formatRuntimeSectionLabel(key: string): string {
  if (key === "work_context") {
    return "工作上下文";
  }
  if (key === "child_contexts") {
    return "子工作上下文";
  }
  if (key === "threads") {
    return "关联线程";
  }
  return SECTION_LABELS[key] || humanizeToken(key);
}

export function formatMainBrainSignalLabel(key: string): string {
  return MAIN_BRAIN_SIGNAL_LABELS[key] || humanizeToken(key);
}

export function formatRuntimeFieldLabel(key: string): string {
  if (key === "work_context_id") {
    return "工作上下文编号";
  }
  if (key === "work_context_title") {
    return "工作上下文标题";
  }
  if (key === "work_context_key" || key === "context_key") {
    return "工作上下文锚点";
  }
  if (key === "context_type") {
    return "上下文类型";
  }
  if (key === "primary_thread_id") {
    return "主线程";
  }
  if (key === "parent_work_context_id") {
    return "父工作上下文";
  }
  if (key === "task_count") {
    return "任务数";
  }
  if (key === "active_task_count") {
    return "活跃任务数";
  }
  if (key === "terminal_task_count") {
    return "已终态任务数";
  }
  if (key === "owner_agent_count") {
    return "参与智能体数";
  }
  if (key === "child_context_count") {
    return "子工作上下文数";
  }
  return FIELD_LABELS[key] || humanizeToken(key);
}

export function formatRecoveryFieldLabel(key: string): string {
  return RECOVERY_FIELD_LABELS[key] || formatRuntimeFieldLabel(key);
}

export function formatCnTimestamp(value?: string | null): string {
  if (!value) {
    return RUNTIME_CENTER_TEXT.noTimestamp;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(parsed);
}

function localizeStructuredValue(value: unknown): unknown {
  if (value === null || value === undefined || value === "") {
    return RUNTIME_CENTER_TEXT.emptyValue;
  }
  if (typeof value === "string") {
    return localizeRuntimeText(value);
  }
  if (typeof value === "boolean") {
    return value ? RUNTIME_CENTER_TEXT.booleanTrue : RUNTIME_CENTER_TEXT.booleanFalse;
  }
  if (typeof value === "number") {
    return value;
  }
  if (Array.isArray(value)) {
    return value.map((item) => localizeStructuredValue(item));
  }
  if (typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, item]) => [
        formatRuntimeFieldLabel(key),
        localizeStructuredValue(item),
      ]),
    );
  }
  return String(value);
}

export function formatPrimitiveValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return RUNTIME_CENTER_TEXT.emptyValue;
  }
  if (typeof value === "string") {
    return localizeRuntimeText(value);
  }
  if (typeof value === "boolean") {
    return value ? RUNTIME_CENTER_TEXT.booleanTrue : RUNTIME_CENTER_TEXT.booleanFalse;
  }
  if (typeof value === "number") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.every((item) => typeof item !== "object")
      ? value.map((item) => formatPrimitiveValue(item)).join(", ")
      : JSON.stringify(localizeStructuredValue(value), null, 2);
  }
  return JSON.stringify(localizeStructuredValue(value), null, 2);
}

export function formatRouteTitle(route: string): string {
  if (route.includes("/runtime-center/goals/")) {
    return route;
  }
  if (route.includes("/runtime-center/work-contexts/")) {
    return "工作上下文详情";
  }
  for (const [prefix, title] of ROUTE_TITLE_LABELS) {
    if (route.includes(prefix)) {
      return title;
    }
  }
  return route;
}

export function formatRiskLevel(value?: string | null): string {
  if (!value) {
    return "";
  }
  return runtimeRiskLabel(value) || humanizeToken(value);
}

export function formatCapabilityMode(value?: string | null): string {
  if (!value) {
    return "";
  }
  return CAPABILITY_MODE_LABELS[value] || humanizeToken(value);
}

export function formatCapabilityAssignmentSource(value: string): string {
  return CAPABILITY_ASSIGNMENT_SOURCE_LABELS[value] || humanizeToken(value);
}

export function formatScheduleTaskType(value?: string | null): string {
  if (!value) {
    return "";
  }
  return SCHEDULE_TASK_TYPE_LABELS[value] || humanizeToken(value);
}

export function formatDispatchMode(value?: string | null): string {
  if (!value) {
    return "";
  }
  return DISPATCH_MODE_LABELS[value] || humanizeToken(value);
}
