import { normalizeDisplayChinese } from "../text";

interface RemoteSkillPresentationInput {
  slug?: string | null;
  title?: string | null;
  description?: string | null;
}

const LEGACY_BRAND_TOKEN_RE = /\b(?:openclaw|copaw)\b/gi;

const RISK_LEVEL_LABELS: Record<string, string> = {
  auto: "自动",
  guarded: "受控",
  confirm: "需确认",
};

const SOURCE_KIND_LABELS: Record<string, string> = {
  "install-template": "安装模板",
  "mcp-registry": "官方 MCP Registry",
  "hub-search": "SkillHub 搜索",
  "skillhub-curated": "SkillHub 精选",
  "github-curated": "SkillHub 精选",
};

const INSTALL_KIND_LABELS: Record<string, string> = {
  "mcp-template": "MCP 模板",
  "mcp-registry": "官方 MCP Registry",
  "builtin-runtime": "内置运行时",
  "hub-skill": "远程技能",
};

const SOURCE_LABELS: Record<string, string> = {
  "Official MCP Registry": "官方 MCP Registry",
  "SkillHub 商店": "SkillHub 商店",
  "SkillHub 精选": "SkillHub 精选",
  "SkillHub 精选检索": "SkillHub 精选检索",
  "Capability Market": "能力市场",
  ClawHub: "SkillHub 精选",
  "Awesome OpenClaw Skills": "SkillHub 精选",
};

const MANIFEST_STATUS_LABELS: Record<string, string> = {
  verified: "结构化清单",
  "legacy-readme": "SkillHub 目录",
  "skillhub-curated": "SkillHub 精选",
};

const CAPABILITY_TAG_LABELS: Record<string, string> = {
  skill: "技能",
  hub: "技能商店",
  remote: "远程",
  "skillhub-curated": "SkillHub 精选",
  curated: "精选",
  verified: "结构化清单",
  "legacy-readme": "SkillHub 目录",
  browser: "网页",
  workflow: "流程",
  automation: "自动化",
  ecommerce: "经营",
  operations: "经营协同",
  crm: "客户",
  research: "研究",
  image: "图像",
  excel: "数据",
  email: "邮件",
  github: "代码协作",
};

const CAPABILITY_FAMILY_LABELS: Record<string, string> = {
  browser: "网页执行",
  desktop: "桌面执行",
  research: "研究分析",
  workflow: "流程编排",
  content: "内容产出",
  image: "图像素材",
  data: "数据表格",
  crm: "客户协作",
  email: "邮件协作",
  github: "代码协作",
};

const TERM_REPLACEMENTS: Array<[RegExp, string]> = [
  [/\bpublic rankings?\b/gi, "公开榜单"],
  [/\bworkflow(s)?\b/gi, "流程"],
  [/\bautomation\b/gi, "自动化"],
  [/\bbrowser\b/gi, "浏览器"],
  [/\bimage(s)?\b/gi, "图像"],
  [/\bexcel\b/gi, "Excel"],
  [/\bspreadsheet(s)?\b/gi, "表格"],
  [/\bcrm\b/gi, "客户管理"],
  [/\bemail\b/gi, "邮件"],
  [/\bresearch\b/gi, "研究"],
  [/\bsummary\b/gi, "总结"],
  [/\binstall\b/gi, "安装"],
  [/\bskill(s)?\b/gi, "技能"],
  [/\bremote\b/gi, "远程"],
];

const REMOTE_SKILL_PRESETS: Array<{
  matches: RegExp[];
  title: string;
  summary: string;
}> = [
  {
    matches: [/\bfind-skills\b/i],
    title: "技能发现助手",
    summary: "帮助发现、筛选并安装合适的远程技能包。",
  },
  {
    matches: [/\bsummarize\b/i],
    title: "内容总结助手",
    summary: "总结网页、PDF、图片、音频和视频等内容。",
  },
  {
    matches: [/\bbrowser-use\b/i],
    title: "网页自动化执行器",
    summary: "处理网页登录、表单填写、截图采集和网页数据提取。",
  },
  {
    matches: [/\bbrowser-automation\b/i],
    title: "网页自动化助手",
    summary: "自动执行网页登录、页面导航、表单填写、点击和数据提取。",
  },
  {
    matches: [/\bagent-browser\b/i],
    title: "代理浏览器执行器",
    summary: "通过结构化命令执行网页导航、点击、输入和页面快照。",
  },
  {
    matches: [/\bimage-ocr\b/i],
    title: "图片识别工具",
    summary: "从图片中提取文字并输出可继续处理的文本结果。",
  },
  {
    matches: [/\bimage-cog\b/i],
    title: "图像创作助手",
    summary: "生成创意素材、视觉内容和批量图像结果。",
  },
  {
    matches: [/\bimage\b/i],
    title: "图像处理工具",
    summary: "处理图片格式、尺寸、压缩、元数据和平台适配。",
  },
  {
    matches: [/\bcrm-manager\b/i],
    title: "客户管理助手",
    summary: "维护客户管道、跟进节点与本地 CRM 数据。",
  },
  {
    matches: [/\bcustomer-service-reply\b/i],
    title: "客服回复模板",
    summary: "生成常见问题、售前售后和评价回复的标准话术。",
  },
  {
    matches: [/\bcrm\b/i],
    title: "客户关系助手",
    summary: "管理客户、联系人、跟进计划与销售线索。",
  },
  {
    matches: [/\becommerce-price-comparison\b/i],
    title: "价格比较工具",
    summary: "比较多来源价格信息并输出差异结论。",
  },
  {
    matches: [/\becommerce-price-watcher\b/i],
    title: "价格监控助手",
    summary: "持续追踪价格变化、波动和预警信息。",
  },
  {
    matches: [/\becommerce\b/i],
    title: "经营协同工具",
    summary: "支撑目录维护、信息处理、价格跟踪和经营协同。",
  },
  {
    matches: [/\bgithub\b/i],
    title: "GitHub 助手",
    summary: "处理仓库、议题、拉取请求和 CI 运行等代码协作动作。",
  },
  {
    matches: [/\bautomation-workflows\b/i],
    title: "流程自动化工作台",
    summary: "设计、编排并落地跨步骤自动化执行流程。",
  },
  {
    matches: [/\bcontent-strategy\b/i],
    title: "内容策略助手",
    summary: "规划内容主题、发布节奏和转化导向的内容动作。",
  },
  {
    matches: [/\bgoogle-calendar\b/i],
    title: "日历协作助手",
    summary: "处理日程安排、会议同步和时间协同。",
  },
  {
    matches: [/\bgoogle-drive\b/i],
    title: "云盘协作助手",
    summary: "处理文件整理、共享协作和资料归档。",
  },
  {
    matches: [/\bsmart-customer-service-cn\b/i],
    title: "智能客服助手",
    summary: "承接中文客服问答、问题分流和回复辅助。",
  },
];

function normalizeText(value?: string | null): string {
  if (!value) {
    return "";
  }
  return normalizeDisplayChinese(
    String(value)
      .replace(LEGACY_BRAND_TOKEN_RE, " ")
      .replace(/_/g, " ")
      .replace(/\s{2,}/g, " ")
      .trim(),
  );
}

function applyTermReplacements(value: string): string {
  return TERM_REPLACEMENTS.reduce(
    (current, [pattern, replacement]) => current.replace(pattern, replacement),
    value,
  ).replace(/\s{2,}/g, " ").trim();
}

function inferPreset(input: RemoteSkillPresentationInput) {
  const haystack = [input.slug, input.title, input.description]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return (
    REMOTE_SKILL_PRESETS.find((item) => item.matches.every((pattern) => pattern.test(haystack))) ||
    null
  );
}

export function presentRemoteSkillName(input: RemoteSkillPresentationInput): string {
  const preset = inferPreset(input);
  if (preset) {
    return preset.title;
  }
  return applyTermReplacements(normalizeText(input.title || input.slug || "")) || "-";
}

export function presentRemoteSkillSummary(input: RemoteSkillPresentationInput): string {
  const preset = inferPreset(input);
  if (preset) {
    return preset.summary;
  }
  return (
    applyTermReplacements(normalizeText(input.description || input.title || input.slug || "")) || "-"
  );
}

export function presentRecommendationRiskLevel(value?: string | null): string {
  const normalized = String(value || "").trim();
  return RISK_LEVEL_LABELS[normalized] || normalizeText(normalized) || "-";
}

export function presentRecommendationSourceKind(value?: string | null): string {
  const normalized = String(value || "").trim();
  return SOURCE_KIND_LABELS[normalized] || normalizeText(normalized) || "-";
}

export function presentRecommendationInstallKind(value?: string | null): string {
  const normalized = String(value || "").trim();
  return INSTALL_KIND_LABELS[normalized] || normalizeText(normalized) || "-";
}

export function presentRecommendationSourceLabel(value?: string | null): string {
  const normalized = String(value || "").trim();
  return SOURCE_LABELS[normalized] || normalizeText(normalized) || "-";
}

export function presentRecommendationCapabilityTag(value?: string | null): string {
  const normalized = String(value || "").trim();
  return CAPABILITY_TAG_LABELS[normalized] || applyTermReplacements(normalizeText(normalized)) || "-";
}

export function presentRecommendationCapabilityFamily(value?: string | null): string {
  const normalized = String(value || "").trim();
  return CAPABILITY_FAMILY_LABELS[normalized] || applyTermReplacements(normalizeText(normalized)) || "-";
}

export function presentRecommendationManifestStatus(value?: string | null): string {
  const normalized = String(value || "").trim();
  return MANIFEST_STATUS_LABELS[normalized] || normalizeText(normalized) || "-";
}

export function presentRemoteVersion(value?: string | null): string {
  const normalized = String(value || "").trim();
  return normalized || "最新版本";
}

export function localizeRemoteSkillText(value?: string | null): string {
  return applyTermReplacements(normalizeText(value || "")) || "-";
}
