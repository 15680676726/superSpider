const EXACT_TEXT_MAP: Record<string, string> = {
  "Acts as the team's visible main brain: decomposes goals, delegates concrete subtasks to specialist teammates, supervises execution, verifies evidence, and does not become the leaf worker.":
    "作为团队可见的 Spider Mesh 主脑：负责拆解目标、分派具体子任务给专业协作角色、监督执行、核验证据，不再亲自承担叶子执行。",
  "Turn the current industry brief into delegated child tasks with explicit owners, collect evidence and status back, and surface staffing gaps instead of executing directly.":
    "将当前行业简报拆解为带明确负责人的子任务，回收证据与状态；若没有合适协作角色承接，就显式暴露补位或路由缺口。",
  "Collects domain, stakeholder, peer, and operating signals and turns them into usable evidence.":
    "负责收集行业、干系人、同业与经营信号，并整理为可直接使用的证据。",
  "Produce the highest-signal research the execution core can directly convert into action.":
    "产出 Spider Mesh 主脑可以直接转化为行动的高信号研究结果。",
  "Turn the current brief into the next highest-leverage move inside this role envelope.":
    "在当前角色职责边界内，把现有简报转化为下一步最高杠杆动作。",
  "kernel-governed dispatch only": "仅允许通过内核治理后的分派链路执行",
  "workspace draft/edit allowed": "允许在工作区内起草和编辑",
  "browser research allowed": "允许使用浏览器开展调研",
  "no shell or admin capability access": "不开放 shell 或管理级能力",
  "kernel-governed query dispatch only": "仅允许通过内核治理后的查询分派链路执行",
  "read-only workspace access": "工作区只读访问",
  "no shell, edit, or admin capability access": "不开放 shell、编辑或管理级能力",
  "operating brief": "经营简报",
  "dispatch summary": "分派摘要",
  "next-step recommendation": "下一步建议",
  "market signal summary": "市场信号摘要",
  "stakeholder insight summary": "干系人洞察摘要",
  "operating context summary": "经营上下文摘要",
  "Patch executor failed.": "补丁执行失败。",
  "Patch rollback failed.": "补丁回滚失败。",
  "Evidence ledger is not available for strategy automation.":
    "证据台账当前不可用，无法执行策略自动化。",
  "Read the latest evidence and current constraints before proposing changes.":
    "在提出变更前，先阅读最新证据与当前约束。",
  "Return the next evidence-backed recommendation and the evidence that should be produced.":
    "返回下一步有证据支撑的建议，并说明应该产出的证据。",
  "Review current evidence and risks.": "复核当前证据与风险。",
  "Choose the next coordinated move.": "确定下一步协同动作。",
  "Return a concise operating brief.": "返回简洁的经营简报。",
  "Scan current market and channel signals.": "扫描当前市场与渠道信号。",
  "Extract high-signal findings for the control core.": "提炼高信号发现，反馈给执行中枢。",
  "Collect the week's strongest signals.": "收集本周最强信号。",
  "Synthesize the implications for the team.": "综合分析这些信号对团队的含义。",
  "Review the signal synthesis.": "复核信号综述结果。",
  "Choose the next operating recommendation.": "确定下一步经营建议。",
  "Confirm the target app, recipient, and message.": "确认目标应用、接收对象与消息内容。",
  "Choose whether a specialist should run the desktop action.": "判断是否需要由专业角色执行桌面动作。",
  "Return a concise guarded execution brief.": "返回简洁的受控执行简报。",
  "Launch or focus the target desktop application.": "启动或聚焦目标桌面应用。",
  "Locate the intended recipient conversation.": "定位目标接收对象的会话窗口。",
  "Prepare the outbound message for guarded send confirmation.":
    "准备待发送消息，等待受控发送确认。",
};

const REGEX_TEXT_MAP: Array<{
  pattern: RegExp;
  replace: (...matches: string[]) => string;
}> = [
  {
    pattern: /^execute capability (.+)$/i,
    replace: (capabilityId) => `执行能力 ${capabilityId}`,
  },
  {
    pattern: /^Applied patch: (.+)$/,
    replace: (title) => `已应用补丁：${title}`,
  },
  {
    pattern: /^Applied patch ['"](.+?)['"]\.$/,
    replace: (title) => `已应用补丁“${title}”。`,
  },
  {
    pattern: /^Approved patch ['"](.+?)['"]\.$/,
    replace: (title) => `已批准补丁“${title}”。`,
  },
  {
    pattern: /^Rejected patch ['"](.+?)['"]\.$/,
    replace: (title) => `已驳回补丁“${title}”。`,
  },
  {
    pattern: /^Rolled back patch ['"](.+?)['"]\.$/,
    replace: (title) => `已回滚补丁“${title}”。`,
  },
  {
    pattern: /^Approved by (.+)\.$/,
    replace: (actor) => `已由 ${actor} 批准。`,
  },
  {
    pattern: /^Rejected by (.+)\.$/,
    replace: (actor) => `已由 ${actor} 驳回。`,
  },
  {
    pattern: /^Applied by (.+)\.$/,
    replace: (actor) => `已由 ${actor} 应用。`,
  },
  {
    pattern: /^Rolled back by (.+)\.$/,
    replace: (actor) => `已由 ${actor} 回滚。`,
  },
  {
    pattern: /^Auto-applied by (.+)\.$/,
    replace: (actor) => `已由 ${actor} 自动应用。`,
  },
  {
    pattern: /^Auto-rolled back by (.+)\.$/,
    replace: (actor) => `已由 ${actor} 自动回滚。`,
  },
  {
    pattern: /^Approve patch ['"](.+?)['"] before apply\.$/,
    replace: (title) => `应用前需先批准补丁“${title}”。`,
  },
  {
    pattern: /^patch-(approval|rejection|apply|rollback|auto-apply|auto-rollback) for patch ['"](.+?)['"]\.$/,
    replace: (kind, title) => {
      const kindMap: Record<string, string> = {
        approval: "补丁审批",
        rejection: "补丁驳回",
        apply: "补丁应用",
        rollback: "补丁回滚",
        "auto-apply": "补丁自动应用",
        "auto-rollback": "补丁自动回滚",
      };
      return `${kindMap[kind] || "补丁处理"}：${title}`;
    },
  },
  {
    pattern: /^Reduce failures for (.+)$/,
    replace: (capabilityId) => `降低 ${capabilityId} 的失败率`,
  },
  {
    pattern: /^Mitigate failures for (.+)$/,
    replace: (capabilityId) => `缓解 ${capabilityId} 的失败问题`,
  },
  {
    pattern: /^Detected (\d+) failed execution\(s\) for (.+?)\. Recent errors: (.+)\.$/,
    replace: (count, capabilityId, errors) =>
      `检测到 ${capabilityId} 近期出现 ${count} 次失败执行。最近错误：${errors}。`,
  },
  {
    pattern: /^Introduce guardrails and retries for (.+?) based on recent failure evidence\.$/,
    replace: (capabilityId) => `基于近期失败证据，为 ${capabilityId} 增加防护与重试机制。`,
  },
  {
    pattern: /^Auto-applied (\d+) patch\(es\)\.$/,
    replace: (count) => `已自动应用 ${count} 个补丁。`,
  },
  {
    pattern: /^Strategy created (\d+) proposal\(s\), (\d+) patch\(es\); auto-applied (\d+), auto-rolled back (\d+)\.$/,
    replace: (proposals, patches, applied, rolledBack) =>
      `策略已创建 ${proposals} 个提案、${patches} 个补丁；自动应用 ${applied} 个，自动回滚 ${rolledBack} 个。`,
  },
  {
    pattern: /^AI-generated industry team draft for (.+?) in (.+?)\.$/,
    replace: (label, industry) => `${label} 在 ${industry} 场景下的 Spider Mesh 行业身份草案。`,
  },
  {
    pattern: /^AI generated a (.+?) industry draft for (.+?) with (\d+) non-core role\(s\)\.$/,
    replace: (topology, label, count) =>
      `系统已为 ${label} 生成 ${topology} 行业身份草案，包含 ${count} 个非中枢角色。`,
  },
  {
    pattern: /^Review the current runtime state for (.+?) in (.+?)\.$/,
    replace: (label, industry) => `复核 ${label} 在 ${industry} 场景下的当前运行状态。`,
  },
  {
    pattern: /^You are operating as (.+?)\.$/,
    replace: (roleName) => `你当前以“${roleName}”身份执行。`,
  },
  {
    pattern: /^Focus on the goal: (.+?)\.$/,
    replace: (goalTitle) => `当前聚焦目标：${goalTitle}。`,
  },
  {
    pattern: /^Review the current (.+?) brief\.$/,
    replace: (roleName) => `查看当前“${roleName}”职责的工作简报。`,
  },
  {
    pattern: /^Identify the next evidence-backed move\.$/,
    replace: () => "识别下一步有证据支撑的动作。",
  },
  {
    pattern: /^Return a concise recommendation and the expected evidence\.$/,
    replace: () => "返回简洁建议，并说明预期应产出的证据。",
  },
  {
    pattern: /^Recurring review for the team's execution core loop\.$/,
    replace: () => "围绕团队执行中枢闭环的定期复盘。",
  },
  {
    pattern: /^Recurring review for the (.+?) loop\.$/,
    replace: (roleName) => `围绕“${roleName}”职责闭环的定期复盘。`,
  },
  {
    pattern: /^Recurring control-core review for (.+)$/,
    replace: (goal) => `围绕“${goal}”的执行中枢定期复盘`,
  },
  {
    pattern: /^Recurring weekly synthesis around (.+)$/,
    replace: (focusArea) => `围绕“${focusArea}”的周度信号综述`,
  },
  {
    pattern: /^Run the daily control review for (.+?)\. Goal: (.+)$/,
    replace: (label, goal) => `请执行 ${label} 的每日中枢复盘。目标：${goal}`,
  },
  {
    pattern: /^Run the weekly signal synthesis for (.+?)\. Focus: (.+)$/,
    replace: (label, focusArea) => `请执行 ${label} 的周度信号综述。关注点：${focusArea}`,
  },
  {
    pattern: /^Daily control loop for (.+)$/,
    replace: (label) => `${label} 每日执行中枢循环`,
  },
  {
    pattern: /^Evidence signal sweep for (.+)$/,
    replace: (label) => `${label} 证据信号扫描`,
  },
  {
    pattern: /^Daily control review for (.+)$/,
    replace: (label) => `${label} 每日执行复盘`,
  },
  {
    pattern: /^Weekly synthesis for (.+)$/,
    replace: (label) => `${label} 周度信号综述`,
  },
  {
    pattern: /^Control brief for (.+)$/,
    replace: (label) => `${label} 执行简报`,
  },
  {
    pattern: /^Weekly signal synthesis for (.+)$/,
    replace: (label) => `${label} 周度信号综述`,
  },
  {
    pattern: /^Desktop outreach brief for (.+)$/,
    replace: (label) => `${label} 桌面外联简报`,
  },
  {
    pattern: /^Prepare desktop follow-up in (.+)$/,
    replace: (target) => `在 ${target} 中准备桌面跟进动作`,
  },
  {
    pattern: /^(.+?) Researcher$/,
    replace: (label) => `${label} 研究员`,
  },
  {
    pattern: /^Industry Researcher$/,
    replace: () => "行业研究员",
  },
  {
    pattern: /^(.+?) Solution Lead$/,
    replace: (label) => `${label} 方案负责人`,
  },
  {
    pattern: /^Solution Lead$/,
    replace: () => "方案负责人",
  },
  {
    pattern: /^Business Specialist$/,
    replace: () => "业务专员",
  },
];

function translatePlainLine(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) {
    return value;
  }
  if (Object.prototype.hasOwnProperty.call(EXACT_TEXT_MAP, trimmed)) {
    return EXACT_TEXT_MAP[trimmed];
  }
  let translated = trimmed;
  for (const item of REGEX_TEXT_MAP) {
    translated = translated.replace(item.pattern, (...matches) =>
      item.replace(...matches.slice(1, -2)),
    );
  }
  return translated;
}

export function localizeWorkbenchText(value: string | null | undefined): string {
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
        return normalizeSpiderMeshBrand(translatePlainLine(line));
      }
      return normalizeSpiderMeshBrand(`${bullet[1]}${translatePlainLine(bullet[2])}`);
    })
    .join("\n");
}

export function localizeWorkbenchList(
  values: Array<string | null | undefined> | null | undefined,
): string[] {
  return (values ?? [])
    .map((value) => localizeWorkbenchText(value))
    .filter((value) => value.length > 0);
}
import { normalizeSpiderMeshBrand } from "../../utils/brand";
