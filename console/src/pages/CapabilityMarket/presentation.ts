import type { CapabilityMount, CuratedSkillCatalogEntry } from "../../api";
import type {
  CapabilityMarketInstallTemplateSpec,
  McpRegistryCatalogDetailResponse,
  McpRegistryCatalogItem,
  McpRegistryInstallOption,
} from "../../api/modules/capabilityMarket";

export const MARKET_TAB_KEYS = [
  "curated",
  "projects",
  "install-templates",
  "installed",
  "skills",
  "mcp",
] as const;
export type MarketTabKey = (typeof MARKET_TAB_KEYS)[number];
export const MARKET_TAB_KEY_SET = new Set<string>(MARKET_TAB_KEYS);

export const CURATED_FETCH_LIMIT = 500;
export const CURATED_PAGE_SIZE = 8;
export const MCP_PAGE_SIZE = 12;

export const CURATED_CATEGORY_DEFINITIONS = [
  { key: "all", label: "全部" },
  { key: "operations", label: "经营协同" },
  { key: "ecommerce", label: "电商" },
  { key: "customer", label: "客户" },
  { key: "content", label: "内容" },
  { key: "research", label: "研究" },
  { key: "browser", label: "浏览器" },
  { key: "data", label: "数据" },
  { key: "image", label: "图像" },
  { key: "code", label: "代码" },
  { key: "general", label: "通用" },
] as const;

export type CuratedCategoryKey = (typeof CURATED_CATEGORY_DEFINITIONS)[number]["key"];
export type ConcreteCuratedCategoryKey = Exclude<CuratedCategoryKey, "all">;

export type CuratedDisplayEntry = {
  item: CuratedSkillCatalogEntry;
  categoryKeys: ConcreteCuratedCategoryKey[];
};

export type TemplateConfigField = NonNullable<
  CapabilityMarketInstallTemplateSpec["config_schema"]
>["fields"][number];

const CURATED_CATEGORY_RULES: Record<Exclude<ConcreteCuratedCategoryKey, "general">, string[]> = {
  operations: ["operations", "ops", "marketing", "campaign", "calendar", "email"],
  ecommerce: ["ecommerce", "shop", "store", "sku", "inventory", "listing", "price", "product", "amazon", "shopify"],
  customer: ["customer", "crm", "sales", "support", "service", "lead"],
  content: ["content", "copy", "summary", "article", "seo", "blog", "script", "writer"],
  research: ["research", "analysis", "monitor", "intel", "search", "knowledge"],
  browser: ["browser", "playwright", "web", "page", "navigation"],
  data: ["data", "excel", "csv", "sheet", "spreadsheet", "report", "dashboard"],
  image: ["image", "visual", "ocr", "photo", "design"],
  code: ["github", "git", "code", "repo", "pull request", "developer"],
};

export function normalizeMarketTabKey(value: string | null): MarketTabKey {
  return MARKET_TAB_KEY_SET.has(value || "") ? (value as MarketTabKey) : "curated";
}

function normalizeText(value: unknown): string {
  return String(value ?? "").trim().toLowerCase();
}

export function buildCuratedInstallKey(item: CuratedSkillCatalogEntry): string {
  return `curated:${item.source_id}:${item.candidate_id}`;
}

export function inferCuratedCategoryKeys(item: CuratedSkillCatalogEntry): ConcreteCuratedCategoryKey[] {
  const haystack = normalizeText(
    [
      item.source_id,
      item.source_label,
      item.title,
      item.description,
      item.candidate_id,
      ...(item.tags || []),
      ...(item.capability_tags || []),
    ].join(" "),
  );
  const matches = Object.entries(CURATED_CATEGORY_RULES)
    .filter(([, keywords]) => keywords.some((keyword) => haystack.includes(keyword)))
    .map(([key]) => key as Exclude<ConcreteCuratedCategoryKey, "general">);
  return matches.length ? matches : ["general"];
}

export function buildTemplateConfigDefaults(
  template: CapabilityMarketInstallTemplateSpec | null,
): Record<string, string | boolean> {
  if (!template?.config_schema?.fields?.length) {
    return {};
  }
  return Object.fromEntries(
    template.config_schema.fields.map((field) => [field.key, stringifyTemplateConfigValue(field, field.default)]),
  );
}

function stringifyTemplateConfigValue(field: TemplateConfigField, value: unknown): string | boolean {
  const fieldType = String(field.field_type || "string").trim().toLowerCase();
  if (fieldType === "boolean") {
    return Boolean(value);
  }
  if (fieldType === "string[]") {
    return Array.isArray(value) ? value.map((item) => String(item ?? "")).filter(Boolean).join("\n") : String(value ?? "");
  }
  return value == null ? "" : String(value);
}

export function parseTemplateConfigValue(field: TemplateConfigField, value: unknown): string | boolean | string[] {
  const fieldType = String(field.field_type || "string").trim().toLowerCase();
  if (fieldType === "boolean") {
    return Boolean(value);
  }
  if (fieldType === "string[]") {
    if (Array.isArray(value)) {
      return value.map((item) => String(item ?? "").trim()).filter(Boolean);
    }
    return String(value ?? "")
      .split(/\r?\n|,/)
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return String(value ?? "").trim();
}

export function capabilityKindLabel(kind: CapabilityMount["kind"]): string {
  if (kind === "local-tool") return "本地工具";
  if (kind === "remote-mcp") return "MCP";
  if (kind === "skill-bundle") return "技能";
  if (kind === "provider-admin") return "模型提供方";
  if (kind === "system-op") return "系统";
  return kind;
}

export function capabilityKindColor(kind: CapabilityMount["kind"]): string {
  if (kind === "local-tool") return "blue";
  if (kind === "remote-mcp") return "purple";
  if (kind === "skill-bundle") return "cyan";
  if (kind === "provider-admin") return "gold";
  if (kind === "system-op") return "geekblue";
  return "default";
}

export function templateStatusColor(
  template: Pick<CapabilityMarketInstallTemplateSpec, "installed" | "ready">,
): string {
  if (template.ready) return "green";
  if (template.installed) return "gold";
  return "default";
}

export function doctorStatusColor(status: "ready" | "degraded" | "blocked"): string {
  if (status === "ready") return "green";
  if (status === "degraded") return "gold";
  return "red";
}

export function presentTemplateAvailabilityLabel(
  template: Pick<CapabilityMarketInstallTemplateSpec, "installed" | "ready">,
): string {
  if (template.ready) return "已就绪";
  if (template.installed) return "已安装";
  return "待安装";
}

export function presentMcpInstallStatus(item: McpRegistryCatalogItem): string {
  if (item.update_available) return "可更新";
  if (item.installed_client_key) return item.installed_via_registry ? "已安装" : "客户端已存在";
  if (!item.install_supported) return "暂不支持";
  return "可安装";
}

export function mcpInstallStatusColor(item: McpRegistryCatalogItem): string {
  if (item.update_available) return "gold";
  if (item.installed_client_key) return item.installed_via_registry ? "green" : "blue";
  if (!item.install_supported) return "default";
  return "cyan";
}

export function presentMcpTransportLabel(transport: string): string {
  if (transport === "streamable_http") return "HTTP";
  if (transport === "sse") return "SSE";
  return "标准输入输出";
}

export function presentMcpOptionSummary(option: McpRegistryInstallOption): string {
  if (option.install_kind === "remote") return option.url_template || option.summary || "远程 MCP";
  return [option.registry_type || "包", option.runtime_command || "-", option.identifier || option.summary || "-"]
    .filter(Boolean)
    .join(" / ");
}

export function buildMcpFieldDefaults(
  detail: McpRegistryCatalogDetailResponse,
  option: McpRegistryInstallOption | null,
): Record<string, unknown> {
  const values: Record<string, unknown> = {};
  Object.entries(detail.matched_registry_input_values || {}).forEach(([key, value]) => {
    values[key] = value;
  });
  (option?.input_fields || []).forEach((field) => {
    if (values[field.key] === undefined && field.default_value !== undefined) {
      values[field.key] = field.default_value;
    }
  });
  return values;
}
