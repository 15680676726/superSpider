type DisplayTermReplacement = readonly [source: string, target: string];

const DISPLAY_TERM_REPLACEMENTS: readonly DisplayTermReplacement[] = [
  ["Model Context Protocol", "模型上下文协议"],
  ["Default browser runtime", "默认浏览器运行环境"],
  ["Workflow Templates", "自动化模板"],
  ["Install Templates", "安装模板"],
  ["Install Template", "安装模板"],
  ["Embedding API Key", "向量接口密钥"],
  ["Embedding Base URL", "向量服务地址"],
  ["Default Base URL", "默认服务地址"],
  ["Telegram Bot Token", "Telegram 机器人令牌"],
  ["Agent Workbench", "智能体工作台"],
  ["Runtime Center", "运行中心"],
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
