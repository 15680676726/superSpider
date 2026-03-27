import { request } from "../request";
import type {
  CapabilityMarketOverview,
  CapabilityMount,
  CapabilitySummary,
  CuratedSkillCatalogSearchResponse,
  CuratedSkillCatalogSource,
  HubSkillSpec,
  MCPClientCreateRequest,
  MCPClientInfo,
  MCPClientUpdateRequest,
  SkillSpec,
} from "../types";
import type { CapabilityMutationResponse } from "./capability";

export interface CapabilityMarketInstallTemplateSpec {
  id: string;
  name: string;
  description: string;
  install_kind: string;
  source_kind: string;
  platform: string;
  default_client_key?: string | null;
  default_capability_id?: string | null;
  capability_tags: string[];
  notes: string[];
  risk_level: string;
  capability_budget_cost: number;
  default_assignment_policy: string;
  installed: boolean;
  enabled?: boolean | null;
  ready: boolean;
  manifest?: {
    template_id: string;
    version: string;
    install_kind: string;
    source_kind: string;
    capability_ids: string[];
    supported_platforms: string[];
    environment_requirements: string[];
    evidence_contract: string[];
    tags: string[];
  } | null;
  config_schema?: {
    scope: "install" | "runtime" | "none";
    fields: Array<{
      key: string;
      label: string;
      field_type: string;
      required: boolean;
      secret: boolean;
      description: string;
      default?: unknown;
      choices: string[];
    }>;
  } | null;
  lifecycle: Array<{
    action: string;
    label: string;
    summary: string;
    available: boolean;
    risk_level: string;
  }>;
  execution_strategy?: {
    risk_level: string;
    admission_mode: string;
    allowlist_scope: string;
    approval_forwarding_supported: boolean;
    pending_approval_count: number;
    target_capability_ids: string[];
    host_policy: {
      host_kind: string;
      expected_platform: string;
      requires_interactive_session: boolean;
      supported: boolean;
      ready: boolean;
      reason: string;
    };
    routes: Record<string, string>;
  } | null;
  host_policy?: {
    host_kind: string;
    expected_platform: string;
    requires_interactive_session: boolean;
    supported: boolean;
    ready: boolean;
    reason: string;
  } | null;
  runtime: Record<string, unknown>;
  support: Record<string, unknown>;
  routes: Record<string, string>;
}

export interface CapabilityMarketInstallTemplateDoctorReport {
  template_id: string;
  status: "ready" | "degraded" | "blocked";
  summary: string;
  checked_at: string;
  checks: Array<{
    key: string;
    label: string;
    status: "pass" | "warn" | "fail" | "info";
    message: string;
    detail: string;
  }>;
  host_policy: NonNullable<CapabilityMarketInstallTemplateSpec["host_policy"]>;
  runtime: Record<string, unknown>;
  support: Record<string, unknown>;
  error?: {
    code: string;
    summary: string;
    detail: string;
    retryable: boolean;
    source: string;
  } | null;
}

export interface CapabilityMarketInstallTemplateExampleRunRecord {
  template_id: string;
  status: "success" | "error";
  started_at: string;
  finished_at: string;
  summary: string;
  operations: string[];
  runtime: Record<string, unknown>;
  support: Record<string, unknown>;
  payload: Record<string, unknown>;
  error?: {
    code: string;
    summary: string;
    detail: string;
    retryable: boolean;
    source: string;
  } | null;
}

export interface BrowserRuntimeProfileRecord {
  profile_id: string;
  label: string;
  headed: boolean;
  reuse_running_session: boolean;
  persist_login_state: boolean;
  entry_url: string;
  is_default: boolean;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface BrowserRuntimeSnapshot {
  running: boolean;
  headless: boolean;
  current_session_id?: string | null;
  session_count: number;
  sessions: Array<{
    session_id: string;
    profile_id?: string | null;
    entry_url?: string | null;
    persist_login_state: boolean;
    current_page_id?: string | null;
    page_count: number;
    page_ids: string[];
    created_at?: string | null;
    last_activity_time?: number | string | null;
  }>;
  current_page_id?: string | null;
  page_count: number;
  page_ids: string[];
  default_browser_kind?: string | null;
  default_browser_path?: string | null;
  reload_mode?: boolean;
  last_browser_error?: string | null;
  last_activity_time?: number | string | null;
  profiles?: BrowserRuntimeProfileRecord[];
}

export interface CapabilityMarketWorkflowResumePayload {
  template_id: string;
  industry_instance_id?: string | null;
  owner_agent_id?: string | null;
  preset_id?: string | null;
  parameters: Record<string, unknown>;
  resume_action: "preview";
  return_path: string;
}

export interface CapabilityMarketCapabilityAssignmentResult {
  agent_id: string;
  capability_ids: string[];
  mode: "replace" | "merge";
  success: boolean;
  summary: string;
  routes: Record<string, string>;
}

export interface CapabilityMarketInstallTemplateInstallResponse {
  template_id: string;
  install_status: "installed" | "already-installed" | "enabled-existing";
  source_kind: string;
  target_ref?: string | null;
  enabled?: boolean | null;
  ready: boolean;
  assigned_capability_ids: string[];
  assignment_results: CapabilityMarketCapabilityAssignmentResult[];
  workflow_resume?: CapabilityMarketWorkflowResumePayload | null;
  summary: string;
  routes: Record<string, string>;
}

export interface CapabilityMarketRemoteSkillInstallResponse {
  installed: boolean;
  name: string;
  enabled: boolean;
  source_url: string;
  assigned_capability_ids: string[];
  assignment_results: CapabilityMarketCapabilityAssignmentResult[];
}

export interface CapabilityMarketCuratedInstallResponse
  extends CapabilityMarketRemoteSkillInstallResponse {
  source_id: string;
  candidate_id: string;
  review_summary: string;
  review_notes: string[];
}

export interface McpRegistryCategory {
  key: string;
  label: string;
}

export interface McpRegistryInputField {
  key: string;
  label: string;
  source:
    | "environment"
    | "header"
    | "url-variable"
    | "runtime-argument"
    | "package-argument";
  required: boolean;
  secret: boolean;
  description: string;
  default_value?: unknown;
  format: string;
  choices: string[];
  argument_name: string;
  argument_mode: "named" | "positional" | "flag";
  repeated: boolean;
  value_hint: string;
}

export interface McpRegistryInstallOption {
  key: string;
  label: string;
  summary: string;
  install_kind: "package" | "remote";
  transport: "stdio" | "streamable_http" | "sse";
  supported: boolean;
  support_reason: string;
  registry_type: string;
  identifier: string;
  version: string;
  runtime_command: string;
  url_template: string;
  input_fields: McpRegistryInputField[];
}

export interface McpRegistryCatalogItem {
  server_name: string;
  title: string;
  description: string;
  version: string;
  source_label: string;
  source_url: string;
  repository_url: string;
  website_url: string;
  category_keys: string[];
  transport_types: string[];
  suggested_client_key: string;
  option_count: number;
  supported_option_count: number;
  install_supported: boolean;
  installed_client_key?: string | null;
  installed_via_registry: boolean;
  installed_version: string;
  update_available: boolean;
  routes: Record<string, string>;
}

export interface McpRegistryCatalogSearchResponse {
  items: McpRegistryCatalogItem[];
  categories: McpRegistryCategory[];
  cursor?: string | null;
  next_cursor?: string | null;
  has_more: boolean;
  page_size: number;
  source_label: string;
  warnings: string[];
}

export interface McpRegistryCatalogDetailResponse {
  item: McpRegistryCatalogItem;
  install_options: McpRegistryInstallOption[];
  categories: McpRegistryCategory[];
  matched_registry_client_key?: string | null;
  matched_registry_input_values: Record<string, unknown>;
}

export interface CapabilityMarketMCPRegistryInstallResponse
  extends MCPClientInfo {
  install_status:
    | "installed"
    | "already-installed"
    | "enabled-existing"
    | "updated-existing";
  server_name: string;
  registry_version: string;
  assigned_capability_ids: string[];
  assignment_results: CapabilityMarketCapabilityAssignmentResult[];
  summary: string;
}

export interface CapabilityMarketMCPRegistryUpgradeResponse
  extends MCPClientInfo {
  upgraded: boolean;
  server_name: string;
  previous_version: string;
  registry_version: string;
  summary: string;
}

export const capabilityMarketApi = {
  getCapabilityMarketOverview: () =>
    request<CapabilityMarketOverview>("/capability-market/overview"),

  listCapabilityMarketCapabilities: (params?: {
    kind?: string;
    enabledOnly?: boolean;
  }) => {
    const query = new URLSearchParams();
    if (params?.kind) {
      query.set("kind", params.kind);
    }
    if (params?.enabledOnly) {
      query.set("enabled_only", "true");
    }
    const suffix = query.toString();
    return request<CapabilityMount[]>(
      suffix
        ? `/capability-market/capabilities?${suffix}`
        : "/capability-market/capabilities",
    );
  },

  getCapabilityMarketSummary: () =>
    request<CapabilitySummary>("/capability-market/capabilities/summary"),

  listCapabilityMarketSkills: () =>
    request<SkillSpec[]>("/capability-market/skills"),

  createCapabilityMarketSkill: (payload: {
    name: string;
    content: string;
    references?: Record<string, unknown>;
    scripts?: Record<string, unknown>;
    overwrite?: boolean;
  }) =>
    request<Record<string, unknown>>("/capability-market/skills", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  searchCapabilityMarketHub: (query: string, limit = 20) =>
    request<HubSkillSpec[]>(
      `/capability-market/hub/search?q=${encodeURIComponent(query)}&limit=${limit}`,
    ),

  listCapabilityMarketCuratedSources: () =>
    request<CuratedSkillCatalogSource[]>("/capability-market/curated-sources"),

  searchCapabilityMarketCuratedCatalog: (query = "", limit = 20) => {
    const normalizedLimit = Math.max(limit || 0, 500);
    return request<CuratedSkillCatalogSearchResponse>(
      `/capability-market/curated-catalog?q=${encodeURIComponent(query)}&limit=${normalizedLimit}`,
    );
  },

  installCapabilityMarketCuratedCatalogEntry: (payload: {
    source_id: string;
    candidate_id: string;
    review_acknowledged: boolean;
    enable?: boolean;
    overwrite?: boolean;
    target_agent_ids?: string[];
    capability_ids?: string[];
    capability_assignment_mode?: "replace" | "merge";
  }) =>
    request<CapabilityMarketCuratedInstallResponse>("/capability-market/curated-catalog/install", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  installCapabilityMarketHub: (payload: {
    bundle_url: string;
    version?: string;
    enable?: boolean;
    overwrite?: boolean;
    target_agent_ids?: string[];
    capability_ids?: string[];
    capability_assignment_mode?: "replace" | "merge";
  }) =>
    request<CapabilityMarketRemoteSkillInstallResponse>("/capability-market/hub/install", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listCapabilityMarketMCPClients: () =>
    request<MCPClientInfo[]>("/capability-market/mcp"),

  searchCapabilityMarketMcpCatalog: (params?: {
    query?: string;
    category?: string;
    cursor?: string | null;
    limit?: number;
  }) => {
    const search = new URLSearchParams();
    if (params?.query) {
      search.set("q", params.query);
    }
    if (params?.category) {
      search.set("category", params.category);
    }
    if (params?.cursor) {
      search.set("cursor", params.cursor);
    }
    if (typeof params?.limit === "number") {
      search.set("limit", String(params.limit));
    }
    const suffix = search.toString();
    return request<McpRegistryCatalogSearchResponse>(
      suffix
        ? `/capability-market/mcp/catalog?${suffix}`
        : "/capability-market/mcp/catalog",
    );
  },

  getCapabilityMarketMcpCatalogDetail: (serverName: string) =>
    request<McpRegistryCatalogDetailResponse>(
      `/capability-market/mcp/catalog/${encodeURIComponent(serverName)}`,
    ),

  installCapabilityMarketMcpCatalogEntry: (
    serverName: string,
    payload: {
      option_key: string;
      client_key?: string;
      enabled?: boolean;
      actor?: string;
      target_agent_ids?: string[];
      capability_ids?: string[];
      capability_assignment_mode?: "replace" | "merge";
      input_values?: Record<string, unknown>;
    },
  ) =>
    request<CapabilityMarketMCPRegistryInstallResponse>(
      `/capability-market/mcp/catalog/${encodeURIComponent(serverName)}/install`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),

  upgradeCapabilityMarketMcpClient: (
    clientKey: string,
    payload?: {
      enabled?: boolean;
      actor?: string;
      input_values?: Record<string, unknown>;
    },
  ) =>
    request<CapabilityMarketMCPRegistryUpgradeResponse>(
      `/capability-market/mcp/${encodeURIComponent(clientKey)}/upgrade`,
      {
        method: "POST",
        body: JSON.stringify(payload || {}),
      },
    ),

  listCapabilityMarketInstallTemplates: () =>
    request<CapabilityMarketInstallTemplateSpec[]>(
      "/capability-market/install-templates",
    ),

  getCapabilityMarketInstallTemplate: (templateId: string) =>
    request<CapabilityMarketInstallTemplateSpec>(
      `/capability-market/install-templates/${encodeURIComponent(templateId)}`,
    ),

  getCapabilityMarketInstallTemplateDoctor: (templateId: string) =>
    request<CapabilityMarketInstallTemplateDoctorReport>(
      `/capability-market/install-templates/${encodeURIComponent(templateId)}/doctor`,
    ),

  runCapabilityMarketInstallTemplateExample: (templateId: string) =>
    request<CapabilityMarketInstallTemplateExampleRunRecord>(
      `/capability-market/install-templates/${encodeURIComponent(templateId)}/example-run`,
      {
        method: "POST",
      },
    ),

  runCapabilityMarketInstallTemplateExampleWithConfig: (
    templateId: string,
    payload?: { config?: Record<string, unknown> },
  ) =>
    request<CapabilityMarketInstallTemplateExampleRunRecord>(
      `/capability-market/install-templates/${encodeURIComponent(templateId)}/example-run`,
      {
        method: "POST",
        body: JSON.stringify(payload || {}),
      },
    ),

  installCapabilityMarketInstallTemplate: (
    templateId: string,
    payload?: {
      enabled?: boolean;
      actor?: string;
      target_agent_ids?: string[];
      capability_ids?: string[];
      config?: Record<string, unknown>;
      capability_assignment_mode?: "replace" | "merge";
      workflow_resume?: {
        template_id: string;
        industry_instance_id?: string;
        preset_id?: string;
        parameters?: Record<string, unknown>;
        resume_action?: "preview";
      };
    },
  ) =>
    request<CapabilityMarketInstallTemplateInstallResponse>(
      `/capability-market/install-templates/${encodeURIComponent(templateId)}/install`,
      {
        method: "POST",
        body: JSON.stringify(payload || {}),
      },
    ),

  listBrowserRuntimeProfiles: () =>
    request<BrowserRuntimeProfileRecord[]>(
      "/capability-market/install-templates/browser-local/profiles",
    ),

  upsertBrowserRuntimeProfile: (payload: {
    profile_id?: string;
    label?: string;
    headed?: boolean;
    reuse_running_session?: boolean;
    persist_login_state?: boolean;
    entry_url?: string;
    is_default?: boolean;
    metadata?: Record<string, unknown>;
  }) =>
    request<BrowserRuntimeProfileRecord>(
      "/capability-market/install-templates/browser-local/profiles",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),

  listBrowserRuntimeSessions: () =>
    request<BrowserRuntimeSnapshot>(
      "/capability-market/install-templates/browser-local/sessions",
    ),

  startBrowserRuntimeSession: (payload?: {
    session_id?: string;
    profile_id?: string;
    headed?: boolean;
    entry_url?: string;
    reuse_running_session?: boolean;
    persist_login_state?: boolean;
  }) =>
    request<Record<string, unknown>>(
      "/capability-market/install-templates/browser-local/sessions/start",
      {
        method: "POST",
        body: JSON.stringify(payload || {}),
      },
    ),

  attachBrowserRuntimeSession: (sessionId: string) =>
    request<Record<string, unknown>>(
      `/capability-market/install-templates/browser-local/sessions/${encodeURIComponent(sessionId)}/attach`,
      {
        method: "POST",
      },
    ),

  stopBrowserRuntimeSession: (sessionId: string) =>
    request<Record<string, unknown>>(
      `/capability-market/install-templates/browser-local/sessions/${encodeURIComponent(sessionId)}/stop`,
      {
        method: "POST",
      },
    ),

  createCapabilityMarketMCPClient: (body: MCPClientCreateRequest) =>
    request<MCPClientInfo>("/capability-market/mcp", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  updateCapabilityMarketMCPClient: (
    clientKey: string,
    body: MCPClientUpdateRequest,
  ) =>
    request<MCPClientInfo>(`/capability-market/mcp/${encodeURIComponent(clientKey)}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  toggleCapabilityMarketCapability: (id: string) =>
    request<CapabilityMutationResponse>(
      `/capability-market/capabilities/${encodeURIComponent(id)}/toggle`,
      { method: "PATCH" },
    ),

  deleteCapabilityMarketCapability: (id: string) =>
    request<CapabilityMutationResponse>(
      `/capability-market/capabilities/${encodeURIComponent(id)}`,
      { method: "DELETE" },
    ),
};
