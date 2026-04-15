type DisplayTermReplacement = readonly [source: string, target: string];

const DISPLAY_TERM_REPLACEMENTS: readonly DisplayTermReplacement[] = [
  ["Carrier healthy", "载体健康"],
  ["Workspace drift detected", "检测到工作区漂移"],
  ["North star: weekly alignment", "北极星：周节奏对齐"],
  ["Workspace bound", "工作区已绑定"],
  ["Need supervisor decision", "需要主管决策"],
  ["Review handoff blockers", "复核交接阻塞项"],
  ["Checkpoint evidence", "检查点证据"],
  ["Approve host return", "批准宿主返回"],
  ["Approve closer staffing", "批准补充岗位编制"],
  ["Focused runtime assignment", "已聚焦运行派工"],
  ["Apply continuity patch", "应用连续性补丁"],
  ["Awaiting explicit approval", "等待明确批准"],
  ["Need follow-up from the main brain.", "需要主脑继续跟进。"],
  ["Review handoff and approve the next step.", "复核交接情况并批准下一步动作。"],
  ["No backlog summary captured yet.", "还没有记录待办摘要。"],
  ["No assignment summary captured yet.", "还没有记录派工摘要。"],
  ["Needs replan", "需要重规划"],
  ["Needs Replan", "需要重规划"],
  ["Needs follow-up", "待跟进"],
  ["Consumed", "已处理"],
  ["Unconsumed", "未处理"],
  ["Needs Follow-up", "待跟进"],
  ["Unconsumed reports", "未消费汇报"],
  ["Unconsumed Reports", "未消费汇报"],
  ["Overseen", "已接管"],
  ["Overview note", "概览说明"],
  ["Needs replan", "需要重规划"],
  ["Needs follow-up", "待跟进"],
  ["Unconsumed reports", "未消费汇报"],
  ["Cycle Deadline", "周期截止时间"],
  ["Focus Count", "焦点数量"],
  ["Latest Findings", "最新发现"],
  ["Conflicts", "冲突"],
  ["Holes", "缺口"],
  ["Follow-up backlog", "跟进待办"],
  ["Review handoff blockers", "复核交接阻塞项"],
  ["Need supervisor decision", "需要主管决策"],
  ["Checkpoint evidence", "检查点证据"],
  ["Approve host return", "批准宿主返回"],
  ["Apply continuity patch", "应用连续性补丁"],
  ["Main-Brain Cockpit", "主脑驾驶舱"],
  ["Main-Brain Planning", "主脑规划"],
  ["Main Brain", "主脑"],
  ["Spider Main Chain", "主脑控制链"],
  ["Current Focus", "当前焦点"],
  ["Current Owner", "当前负责人"],
  ["Current Risk", "当前风险"],
  ["Latest Evidence", "最新证据"],
  ["Media Analyses", "媒体分析"],
  ["Seller brief", "销售简报"],
  ["Open Analysis", "打开分析"],
  ["Work context", "工作上下文"],
  ["Human return required", "需要人工回接"],
  ["Runtime Focus", "运行焦点"],
  ["Execution Environment", "执行环境"],
  ["Report Snapshot", "汇报快照"],
  ["Focused Assignment", "已聚焦派工"],
  ["Focused Backlog", "已聚焦待办"],
  ["Open Detail", "打开详情"],
  ["Carrier", "载体"],
  ["Strategy", "策略"],
  ["Lanes", "泳道"],
  ["Lane", "泳道"],
  ["Backlog", "待办"],
  ["Current Cycle", "当前周期"],
  ["Cycle", "周期"],
  ["Assignments", "派工"],
  ["Assignment", "派工"],
  ["Agent Reports", "智能体汇报"],
  ["Reports", "汇报"],
  ["Report", "汇报"],
  ["Replan", "重规划"],
  ["Environment", "环境"],
  ["Runtime Governance", "运行治理"],
  ["Automation", "自动化"],
  ["Recovery", "恢复"],
  ["Evidence", "证据"],
  ["Decisions", "决策"],
  ["Decision", "决策"],
  ["Patches", "补丁"],
  ["Patch", "补丁"],
  ["Host Twin", "宿主孪生"],
  ["Model Context Protocol", "模型上下文协议"],
  ["Default browser runtime", "默认浏览器运行环境"],
  ["Workflow Templates", "自动化模板"],
  ["Install Templates", "安装模板"],
  ["Install Template", "安装模板"],
  ["Embedding API Key", "退役私有压缩接口密钥"],
  ["Embedding Base URL", "退役私有压缩服务地址"],
  ["Default Base URL", "默认服务地址"],
  ["Telegram Bot Token", "Telegram 机器人令牌"],
  ["Agent Workbench", "智能体工作台"],
  ["Runtime Center", "主脑驾驶舱"],
  ["MCP Clients", "模型上下文协议客户端"],
  ["MCP Client", "模型上下文协议客户端"],
  ["Remote MCP", "远程模型上下文协议"],
  ["API Key prefix", "接口密钥前缀"],
  ["Client Secret", "客户端密钥"],
  ["Discover Models", "发现模型"],
  ["Runtime governance", "运行治理"],
  ["Predictions", "晨晚复盘"],
  ["Prediction", "复盘"],
  ["Base URL", "服务地址"],
  ["API Key", "接口密钥"],
  ["Bot Token", "机器人令牌"],
  ["Client ID", "客户端编号"],
  ["Owner Scope", "归属范围"],
  ["Apex Operations", "Apex 运营"],
  ["publish Topic", "发布主题"],
  ["subscribe Topic", "订阅主题"],
  ["Workflow", "工作流"],
  ["GitHub", "GitHub 仓库"],
  ["URL", "地址"],
  ["API", "接口"],
  ["LLM", "大模型"],
  ["MCP", "模型上下文协议"],
  ["Hub", "资源中心"],
  ["Cron", "定时任务"],
  ["Agent", "智能体"],
  ["Actor", "执行体"],
  ["Manager", "管理中枢"],
  ["Researcher", "研究员"],
  ["Provider", "提供方"],
  ["Owner", "归属主体"],
  ["Shell", "命令行"],
  ["ID", "编号"],
] as const;

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

const DISPLAY_TERM_PATTERNS = [...DISPLAY_TERM_REPLACEMENTS]
  .sort((left, right) => right[0].length - left[0].length)
  .map(
    ([source, target]) =>
      [new RegExp(`\\b${escapeRegExp(source)}\\b`, "g"), target] as const,
  );

const MOJIBAKE_MARKERS = ["Ã", "Â", "â", "Ð", "Ñ", "ä", "å", "æ", "ç", "é", "è"] as const;

function looksLikeMojibake(value: string): boolean {
  return MOJIBAKE_MARKERS.reduce(
    (count, marker) => count + value.split(marker).length - 1,
    0,
  ) >= 2;
}

export function repairLikelyMojibake(value: string): string {
  if (!value || !looksLikeMojibake(value)) {
    return value;
  }
  const decoders = ["utf-8"] as const;
  for (const encoding of decoders) {
    try {
      const bytes = Uint8Array.from(value, (char) => char.charCodeAt(0) & 0xff);
      const repaired = new TextDecoder(encoding, { fatal: true }).decode(bytes);
      if (!repaired || repaired === value || looksLikeMojibake(repaired)) {
        continue;
      }
      if (/[\u4e00-\u9fff]/.test(repaired) || /[A-Za-z]/.test(repaired)) {
        return repaired;
      }
    } catch {
      continue;
    }
  }
  return value;
}

export function normalizeDisplayChinese(value: string): string {
  return DISPLAY_TERM_PATTERNS.reduce(
    (current, [pattern, replacement]) => current.replace(pattern, replacement),
    repairLikelyMojibake(value),
  );
}
