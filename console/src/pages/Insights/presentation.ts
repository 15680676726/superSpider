import { normalizeDisplayChinese } from "../../text";
import { localizeWorkbenchText } from "../AgentWorkbench/localize";

const CAPABILITY_LABELS: Record<string, string> = {
  "system:dispatch_query": "智能体协作分派",
  "system:run_learning_strategy": "系统自我优化",
  "system:enqueue_task": "任务入队",
  "system:pause_actor": "暂停执行体",
  "system:resume_actor": "恢复执行体",
  "system:cancel_actor_task": "取消执行任务",
  "system:list_teammates": "查看协作成员",
  "system:update_mcp_client": "更新模型上下文协议客户端",
  "system:apply_role": "调整角色能力",
  "tool:execute_shell_command": "命令行执行",
  "tool:read_file": "读取文件",
  "tool:write_file": "写入文件",
  "tool:edit_file": "编辑文件",
  "tool:browser_use": "浏览器操作",
  "tool:desktop_click": "桌面点击",
  "tool:desktop_type": "桌面输入",
  "tool:desktop_keypress": "桌面按键",
  "tool:window_control": "窗口控制",
};

const CAPABILITY_PREFIX_LABELS: Record<string, string> = {
  system: "系统能力",
  tool: "工具能力",
  skill: "技能能力",
  mcp: "外接能力",
  learning: "学习能力",
  manual: "人工动作",
};

const CAPABILITY_ACTION_LABELS: Record<string, string> = {
  dispatch_query: "智能体协作分派",
  run_learning_strategy: "系统自我优化",
  enqueue_task: "任务入队",
  pause_actor: "暂停执行体",
  resume_actor: "恢复执行体",
  cancel_actor_task: "取消执行任务",
  list_teammates: "查看协作成员",
  update_mcp_client: "更新模型上下文协议客户端",
  apply_role: "调整角色能力",
  "install-capability": "安装能力",
  "reassign-leaf": "重新分配叶子执行",
  "create-schedule": "创建自动化计划",
  review: "人工复核",
  execute_shell_command: "命令行执行",
  read_file: "读取文件",
  write_file: "写入文件",
  edit_file: "编辑文件",
  browser_use: "浏览器操作",
  desktop_click: "桌面点击",
  desktop_type: "桌面输入",
  desktop_keypress: "桌面按键",
  window_control: "窗口控制",
};

const METRIC_LABELS: Record<string, string> = {
  active_agents: "活跃智能体数",
  active_agent_count: "活跃智能体数",
  task_count: "任务总数",
  success_rate: "成功率",
  task_success_rate: "任务完成率",
  manual_intervention_rate: "人工介入率",
  exception_rate: "异常率",
  patch_apply_rate: "修复生效率",
  rollback_rate: "回滚率",
  active_task_load: "单智能体负载",
  evidence_count: "证据数",
  decision_count: "决策数",
  patch_count: "补丁数",
  recommendation_count: "建议数",
  prediction_count: "预测数",
  prediction_hit_rate: "预测命中率",
  recommendation_adoption_rate: "建议采纳率",
  recommendation_execution_benefit: "平均执行收益",
};

const METRIC_FORMULA_LABELS: Record<string, string> = {
  "completed_tasks / terminal_tasks": "已完成任务 ÷ 已结束任务",
  "tasks_with_decisions / window_tasks": "发生人工决策的任务数 ÷ 窗口任务数",
  "failed_evidence_records / evidence_records": "失败证据数 ÷ 全部证据数",
  "applied_patches / patches_created": "已应用修复数 ÷ 新增修复数",
  "rolled_back_patches / applied_patches": "已回滚修复数 ÷ 已应用修复数",
  "active_window_tasks / agent_count": "窗口内活跃任务数 ÷ 参与智能体数",
  "(hit_reviews + partial_reviews) / reviewed_predictions":
    "命中与部分命中的复盘数 ÷ 已复盘预测数",
  "adopted_reviews / reviewed_predictions": "已采纳复盘数 ÷ 已复盘预测数",
  "average(review.benefit_score)": "复盘收益分的平均值",
};

const METRIC_SOURCE_LABELS: Record<string, string> = {
  "TaskRecord.status over the report window.": "统计窗口内的任务状态记录。",
  "DecisionRequestRecord.task_id over the report window.":
    "统计窗口内发生人工决策的任务记录。",
  "EvidenceRecord.status over the report window.": "统计窗口内的证据状态记录。",
  "Patch.status over the report window.": "统计窗口内的系统修复状态记录。",
  "Window-scoped active tasks divided by participating agents.":
    "统计窗口内的活跃任务总量，按参与智能体数量平均。",
  "PredictionReviewRecord.outcome over the report window.":
    "统计窗口内的预测复盘结果。",
  "PredictionReviewRecord.adopted over the report window.":
    "统计窗口内的建议采纳结果。",
  "PredictionReviewRecord.benefit_score over the report window.":
    "统计窗口内的复盘收益评分。",
};

const RECOMMENDATION_TYPE_LABELS: Record<string, string> = {
  execute: "执行建议",
  review: "复核建议",
  observe: "观察建议",
  escalate: "升级建议",
  capability_recommendation: "能力补全建议",
  role_recommendation: "角色分配建议",
  plan_recommendation: "执行计划建议",
  risk_recommendation: "风险处置建议",
  schedule_recommendation: "自动化编排建议",
};

const SOURCE_KIND_LABELS: Record<string, string> = {
  metric: "指标信号",
  report: "报告信号",
  "workflow-run": "工作流运行",
  agent: "智能体反馈",
  industry: "身份信息",
  manual: "人工录入",
  compiler: "编译结果",
  delegation: "协作分派",
  tool: "工具输出",
  skill: "技能输出",
  mcp: "外接能力",
  system: "系统输出",
};

const CASE_KIND_LABELS: Record<string, string> = {
  manual: "人工发起",
  cycle: "周期巡检",
  proactive: "主动发现",
  reactive: "被动响应",
  scheduled: "定时巡检",
  forecast: "趋势预测",
  unknown: "未说明来源",
};

const SCENARIO_KIND_LABELS: Record<string, string> = {
  best: "最佳情况",
  base: "基准情况",
  worst: "保守情况",
  optimistic: "乐观情况",
  baseline: "基准情况",
  pessimistic: "保守情况",
};

const STATUS_LABELS: Record<string, string> = {
  open: "待处理",
  proposed: "已提出",
  reviewing: "评审中",
  closed: "已关闭",
  queued: "排队中",
  "waiting-confirm": "待确认",
  throttled: "已限流",
  "manual-only": "需人工处理",
  executed: "已执行",
  approved: "已批准",
  rejected: "已拒绝",
  failed: "执行失败",
  unknown: "待定",
  hit: "命中",
  miss: "未命中",
  partial: "部分命中",
};

const STAT_LABELS: Record<string, string> = {
  scenario_count: "场景数",
  signal_count: "信号数",
  recommendation_count: "建议数",
  review_count: "复盘数",
  pending_decision_count: "待确认决策数",
  latest_review_outcome: "最近复盘结果",
  pending_queue: "待处理建议数",
  executed_auto: "自动执行次数",
  hit_rate: "命中率",
  adoption_rate: "采纳率",
  average_benefit: "平均收益",
  prediction_count: "预测数",
  auto_execution_count: "自动执行数",
  prediction_hit_rate: "预测命中率",
  recommendation_adoption_rate: "建议采纳率",
  recommendation_execution_benefit: "平均执行收益",
};

const EXACT_TEXT_MAP: Record<string, string> = {
  Global: "全局",
  Prediction: "预测案例",
  "Task success rate": "任务完成率",
  "Manual intervention rate": "人工介入率",
  "Exception rate": "异常率",
  "Patch apply rate": "补丁生效率",
  "Rollback rate": "回滚率",
  "Active task load per agent": "单智能体活跃负载",
  "Prediction hit rate": "预测命中率",
  "Recommendation adoption rate": "建议采纳率",
  "Recommendation execution benefit": "建议执行收益",
  "Report highlight": "报告亮点",
  "Industry scope": "行业范围",
  "Operator question": "操作员问题",
  "Runtime baseline": "运行基线",
  "Best case": "最佳情况",
  "Base case": "基准情况",
  "Worst case": "保守情况",
  "Move leaf execution away from execution-core": "将叶子执行从 Spider Mesh 主脑迁出",
  "Add a recurring automation schedule": "补充周期性自动化计划",
  "Review the prediction case manually": "人工复核该预测案例",
  "Scan recent runtime performance and propose governed optimizations.":
    "扫描近期运行表现，并提出受治理的优化建议。",
  "Highest-value recommendations are adopted, missing capability blockers are cleared, and load is redistributed before instability compounds.":
    "最高价值建议得到采纳，缺失能力阻断被清除，负载会在失稳扩大前重新分配。",
  "Current runtime trajectory continues with selective operator follow-up and no major structural change to capability distribution.":
    "当前运行轨迹会延续，由操作员进行选择性跟进，能力分配结构不会发生重大变化。",
  "Current blockers stay unresolved, overloaded actors continue to absorb work, and runtime quality degrades into more manual intervention.":
    "当前阻断项持续未解，过载执行体继续吸收工作，运行质量会继续退化并引发更多人工介入。",
  "The current scope has active execution context but no visible workflow run contract. Package the recurring work into a workflow template or runtime schedule.":
    "当前范围内存在活跃执行上下文，但没有可见的自动化执行合同。应把这类周期性工作沉淀为固定 SOP 或运行计划。",
  "Current facts do not safely map to a governed kernel action yet. Review the case and decide the next change manually.":
    "当前事实还不能安全映射到受治理的内核动作，需要人工复核后决定下一步变更。",
  "No strong structured signals were available, so the case falls back to baseline runtime facts.":
    "当前没有足够强的结构化信号，因此该案例回退为基线运行事实分析。",
};

const REGEX_TEXT_MAP: Array<{
  pattern: RegExp;
  replace: (...matches: string[]) => string;
}> = [
  {
    pattern: /^Recommendations (\d+)$/i,
    replace: (count) => `建议 ${count}`,
  },
  {
    pattern: /^Prediction reviews (\d+)$/i,
    replace: (count) => `预测复盘 ${count}`,
  },
  {
    pattern: /^Agent (.+)$/i,
    replace: () => "指定智能体范围",
  },
  {
    pattern: /^Scan recent runtime performance for (.+?) and propose governed optimizations\.$/i,
    replace: (label) =>
      `扫描 ${presentInsightText(label) || label} 的近期运行表现，并提出受治理的优化建议。`,
  },
  {
    pattern: /^(.+?) is currently (.+)\.$/,
    replace: (label, value) =>
      `${presentInsightText(label) || label}当前为 ${presentInsightText(value) || value}。`,
  },
  {
    pattern: /^(.+?) dropped to (.+), which increases delivery risk\.$/,
    replace: (label, value) =>
      `${presentInsightText(label) || label}已降至 ${presentInsightText(value) || value}，交付风险正在上升。`,
  },
  {
    pattern: /^(.+?) is (.+), supporting current execution stability\.$/,
    replace: (label, value) =>
      `${presentInsightText(label) || label}为 ${presentInsightText(value) || value}，支撑当前执行稳定性。`,
  },
  {
    pattern: /^(.+?) is (.+), suggesting the runtime needs more operator intervention than expected\.$/,
    replace: (label, value) =>
      `${presentInsightText(label) || label}为 ${presentInsightText(value) || value}，说明运行面需要比预期更多的人工介入。`,
  },
  {
    pattern: /^(.+?) is (.+), indicating elevated failure pressure\.$/,
    replace: (label, value) =>
      `${presentInsightText(label) || label}为 ${presentInsightText(value) || value}，表明失败压力正在上升。`,
  },
  {
    pattern: /^(.+?) is (.+), showing improvement actions are landing\.$/,
    replace: (label, value) =>
      `${presentInsightText(label) || label}为 ${presentInsightText(value) || value}，说明改进行动正在落地。`,
  },
  {
    pattern: /^(.+?) is (.+), so recent changes may be unstable\.$/,
    replace: (label, value) =>
      `${presentInsightText(label) || label}为 ${presentInsightText(value) || value}，说明近期变更可能仍不稳定。`,
  },
  {
    pattern: /^(.+?) is (.+), which may overload active agents\.$/,
    replace: (label, value) =>
      `${presentInsightText(label) || label}为 ${presentInsightText(value) || value}，可能导致活跃智能体过载。`,
  },
  {
    pattern: /^(.+?) is (.+), so recent prediction quality is holding\.$/,
    replace: (label, value) =>
      `${presentInsightText(label) || label}为 ${presentInsightText(value) || value}，说明近期预测质量保持稳定。`,
  },
  {
    pattern: /^(.+?) is only (.+), so recommendation quality needs review\.$/,
    replace: (label, value) =>
      `${presentInsightText(label) || label}仅为 ${presentInsightText(value) || value}，建议质量需要进一步复核。`,
  },
  {
    pattern: /^Workflow run ['"](.+?)['"] is in status ['"](.+?)['"]\.$/,
    replace: (title, status) =>
      `工作流运行“${presentInsightText(title) || title}”当前状态为“${presentInsightStatusLabel(status)}”。`,
  },
  {
    pattern: /^Workflow ['"](.+?)['"] has capability blockers \(missing=(\d+), assignment_gap=(\d+)\)\.$/,
    replace: (title, missing, gap) =>
      `工作流“${presentInsightText(title) || title}”存在能力阻断，缺失能力 ${missing} 项、分配缺口 ${gap} 项。`,
  },
  {
    pattern: /^Workflow ['"](.+?)['"] is active and can absorb coordinated follow-up work\.$/,
    replace: (title) =>
      `工作流“${presentInsightText(title) || title}”当前活跃，可继续承接协同后续动作。`,
  },
  {
    pattern: /^Agent ['"](.+?)['"] currently has (\d+) active task\(s\)\.$/,
    replace: (name, count) =>
      `智能体“${presentInsightText(name) || name}”当前有 ${count} 个活跃任务。`,
  },
  {
    pattern: /^Agent ['"](.+?)['"] owns (\d+) failed task\(s\) in the current window\.$/,
    replace: (name, count) =>
      `智能体“${presentInsightText(name) || name}”在当前窗口内有 ${count} 个失败任务。`,
  },
  {
    pattern: /^Agent ['"](.+?)['"] is carrying (\d+) active task\(s\), which may create overload\.$/,
    replace: (name, count) =>
      `智能体“${presentInsightText(name) || name}”当前承载 ${count} 个活跃任务，可能出现过载。`,
  },
  {
    pattern: /^Agent ['"](.+?)['"] is sustaining a ([\d.]+)% success rate\.$/,
    replace: (name, rate) =>
      `智能体“${presentInsightText(name) || name}”当前维持在 ${rate}% 成功率。`,
  },
  {
    pattern: /^Prediction scope is anchored to industry instance ['"](.+?)['"]\.$/,
    replace: (instanceId) => `该预测范围锚定在行业实例“${instanceId}”。`,
  },
  {
    pattern: /^Enable MCP client ['"](.+?)['"]$/,
    replace: (clientKey) => `启用模型上下文协议客户端“${clientKey}”`,
  },
  {
    pattern: /^Workflow ['"](.+?)['"] is blocked on ['"](.+?)['"]\. Enable the existing MCP client ['"](.+?)['"] so the workflow can run\.$/,
    replace: (title, capabilityId, clientKey) =>
      `工作流“${presentInsightText(title) || title}”被“${presentCapabilityLabel(capabilityId)}”阻断，需要启用已有客户端“${clientKey}”后才能继续运行。`,
  },
  {
    pattern: /^Install capability ['"](.+?)['"]$/,
    replace: (capabilityId) => `安装能力“${presentCapabilityLabel(capabilityId)}”`,
  },
  {
    pattern: /^Workflow ['"](.+?)['"] is blocked because ['"](.+?)['"] is not installed yet\. Use the capability market install template first\.$/,
    replace: (title, capabilityId) =>
      `工作流“${presentInsightText(title) || title}”被“${presentCapabilityLabel(capabilityId)}”阻断，该能力尚未安装，应先通过能力市场安装模板完成接入。`,
  },
  {
    pattern: /^Assign ['"](.+?)['"] to ['"](.+?)['"]$/,
    replace: (capabilityId, agentId) =>
      `将“${presentCapabilityLabel(capabilityId)}”分配给“${presentInsightText(agentId) || agentId}”`,
  },
  {
    pattern: /^Workflow ['"](.+?)['"] already has the capability installed, but target agent ['"](.+?)['"] does not currently own ['"](.+?)['"]\.$/,
    replace: (title, agentId, capabilityId) =>
      `工作流“${presentInsightText(title) || title}”已安装“${presentCapabilityLabel(capabilityId)}”，但目标智能体“${presentInsightText(agentId) || agentId}”尚未拥有该能力。`,
  },
  {
    pattern: /^Workflow ['"](.+?)['"] still places a leaf step on the control core\. Move leaf execution to a specialist agent so the control core stays supervisory\.$/,
    replace: (title) =>
      `工作流“${presentInsightText(title) || title}”仍把叶子步骤放在执行中枢上，应迁给专业智能体执行，以保持中枢只负责监督与分派。`,
  },
  {
    pattern: /^Dispatch goal ['"](.+?)['"]$/,
    replace: (goalTitle) => `派发目标“${presentInsightText(goalTitle) || goalTitle}”`,
  },
  {
    pattern: /^Goal ['"](.+?)['"] is available in scope but has not yet been pushed through the governed execution chain for this case\.$/,
    replace: (goalTitle) =>
      `目标“${presentInsightText(goalTitle) || goalTitle}”已在当前范围内可用，但尚未通过受治理的执行链正式推进。`,
  },
  {
    pattern: /^Pause actor ['"](.+?)['"] for inspection$/,
    replace: (actorId) => `暂停执行体“${presentInsightText(actorId) || actorId}”待检查`,
  },
  {
    pattern: /^Agent ['"](.+?)['"] is showing (\d+) failed task\(s\) and (\d+) active task\(s\)\. Pause the actor before it amplifies further runtime instability\.$/,
    replace: (name, failed, active) =>
      `智能体“${presentInsightText(name) || name}”当前有 ${failed} 个失败任务、${active} 个活跃任务。应先暂停该执行体，避免进一步放大运行不稳定性。`,
  },
  {
    pattern: /^Window: (\d+) day\(s\)\.$/,
    replace: (days) => `窗口：${days} 天。`,
  },
  {
    pattern: /^Signals analyzed: (\d+)\.$/,
    replace: (count) => `已分析信号：${count} 条。`,
  },
  {
    pattern: /^Recommendations generated: (\d+)\.$/,
    replace: (count) => `已生成建议：${count} 条。`,
  },
  {
    pattern: /^Governed recommendations are adopted quickly\.$/,
    replace: () => "受治理建议能被快速采纳。",
  },
  {
    pattern: /^No governed recommendation is adopted in time\.$/,
    replace: () => "没有受治理建议被及时采纳。",
  },
  {
    pattern: /^Recommendation backlog continues to grow\.$/,
    replace: () => "建议积压仍在继续增长。",
  },
];

function humanizeFallback(value: string): string {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .trim();
}

function translatePlainLine(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    return value;
  }
  let translated = EXACT_TEXT_MAP[trimmed] || trimmed;
  for (const item of REGEX_TEXT_MAP) {
    translated = translated.replace(item.pattern, (...matches) =>
      item.replace(...matches.slice(1, -2)),
    );
  }
  translated = translated.replace(
    /\b(?:system|tool|skill|mcp|learning|manual):[a-z0-9._-]+\b/gi,
    (capabilityId) => `“${presentCapabilityLabel(capabilityId)}”`,
  );
  return normalizeDisplayChinese(translated);
}

export function presentCapabilityLabel(capabilityId?: string | null): string {
  if (!capabilityId) {
    return "系统功能";
  }
  const normalized = capabilityId.trim();
  if (!normalized) {
    return "系统功能";
  }
  if (CAPABILITY_LABELS[normalized]) {
    return CAPABILITY_LABELS[normalized];
  }
  const [prefix, tail] = normalized.split(":", 2);
  const tailLabel = tail ? CAPABILITY_ACTION_LABELS[tail] : null;
  if (tailLabel) {
    return tailLabel;
  }
  const prefixLabel = CAPABILITY_PREFIX_LABELS[prefix] || "系统功能";
  const fallbackTail = tail ? humanizeFallback(tail) : "";
  if (fallbackTail && !/[A-Za-z]/.test(fallbackTail)) {
    return `${prefixLabel}·${fallbackTail}`;
  }
  return prefixLabel;
}

export function presentInsightText(value: string | null | undefined): string {
  if (!value) {
    return "";
  }
  const normalized = localizeWorkbenchText(value);
  if (!normalized) {
    return "";
  }
  return normalized
    .split("\n")
    .map((line) => {
      const bullet = line.match(/^(\s*(?:[-*]|\d+\.)\s+)(.*)$/);
      if (!bullet) {
        return translatePlainLine(line);
      }
      return `${bullet[1]}${translatePlainLine(bullet[2])}`;
    })
    .join("\n");
}

export function presentInsightMetricLabel(
  key?: string | null,
  label?: string | null,
): string {
  const normalizedKey = typeof key === "string" ? key.trim() : "";
  if (normalizedKey && METRIC_LABELS[normalizedKey]) {
    return METRIC_LABELS[normalizedKey];
  }
  return presentInsightText(label) || label || normalizedKey || "指标";
}

export function presentInsightMetricFormula(formula?: string | null): string {
  if (!formula) {
    return "";
  }
  return METRIC_FORMULA_LABELS[formula] || formula;
}

export function presentInsightMetricSource(summary?: string | null): string {
  if (!summary) {
    return "";
  }
  return METRIC_SOURCE_LABELS[summary] || presentInsightText(summary);
}

export function presentInsightSourceKind(kind?: string | null): string {
  if (!kind) {
    return "未说明来源";
  }
  return SOURCE_KIND_LABELS[kind] || presentInsightText(kind) || kind;
}

export function presentInsightCaseKind(kind?: string | null): string {
  if (!kind) {
    return "未说明来源";
  }
  return CASE_KIND_LABELS[kind] || presentInsightText(kind) || kind;
}

export function presentInsightScenarioKind(kind?: string | null): string {
  if (!kind) {
    return "未说明场景";
  }
  return SCENARIO_KIND_LABELS[kind] || presentInsightText(kind) || kind;
}

export function presentInsightStatusLabel(status?: string | null): string {
  if (!status) {
    return "-";
  }
  return STATUS_LABELS[status] || presentInsightText(status) || status;
}

export function presentInsightRecommendationType(type?: string | null): string {
  if (!type) {
    return "-";
  }
  return RECOMMENDATION_TYPE_LABELS[type] || presentInsightText(type) || type;
}

export function presentInsightScopeLabel(
  scopeType?: string | null,
  scopeLabel?: string | null,
  scopeId?: string | null,
): string {
  if (scopeType === "global" || scopeLabel === "Global") {
    return "全局";
  }
  if (scopeType === "industry") {
    return presentInsightText(scopeLabel) || "当前身份";
  }
  if (scopeType === "agent") {
    return presentInsightText(scopeLabel) || "指定智能体";
  }
  if (scopeLabel && scopeLabel.startsWith("Agent ")) {
    return "指定智能体";
  }
  if (scopeId && scopeType === "agent") {
    return "指定智能体";
  }
  return presentInsightText(scopeLabel) || "未命名范围";
}

export function presentInsightStatLabel(key: string): string {
  return STAT_LABELS[key] || presentInsightText(key) || key;
}

export function presentInsightStatValue(key: string, value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "暂无";
  }
  if (typeof value === "boolean") {
    return value ? "是" : "否";
  }
  if (typeof value === "number") {
    if (
      [
        "hit_rate",
        "adoption_rate",
        "prediction_hit_rate",
        "recommendation_adoption_rate",
      ].includes(key)
    ) {
      return `${value.toFixed(1)}%`;
    }
    if (key === "average_benefit" || key === "recommendation_execution_benefit") {
      return value.toFixed(2);
    }
    return String(value);
  }
  if (key === "latest_review_outcome") {
    return presentInsightStatusLabel(String(value));
  }
  return presentInsightText(String(value)) || String(value);
}

export function presentInsightStatsEntries(
  stats: Record<string, unknown> | null | undefined,
): Array<{ key: string; label: string; value: string }> {
  return Object.entries(stats || {}).map(([key, value]) => ({
    key,
    label: presentInsightStatLabel(key),
    value: presentInsightStatValue(key, value),
  }));
}
