import { request } from "../request";

export interface FixedSopTemplateRecord {
  template_id: string;
  name: string;
  summary: string;
  description: string;
  status: string;
  version: string;
  source_kind: string;
  source_ref?: string | null;
  owner_role_id?: string | null;
  suggested_role_ids: string[];
  industry_tags: string[];
  capability_tags: string[];
  risk_baseline: string;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  writeback_contract: Record<string, unknown>;
  node_graph: Array<Record<string, unknown>>;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface FixedSopTemplateSummary {
  template: FixedSopTemplateRecord;
  binding_count: number;
  routes: Record<string, string>;
}

export interface FixedSopTemplateListResponse {
  items: FixedSopTemplateSummary[];
  total: number;
}

export interface FixedSopBindingRecord {
  binding_id: string;
  template_id: string;
  binding_name: string;
  status: string;
  owner_scope?: string | null;
  owner_agent_id?: string | null;
  industry_instance_id?: string | null;
  workflow_template_id?: string | null;
  trigger_mode: string;
  trigger_ref?: string | null;
  input_mapping: Record<string, unknown>;
  output_mapping: Record<string, unknown>;
  timeout_policy: Record<string, unknown>;
  retry_policy: Record<string, unknown>;
  risk_baseline: string;
  last_run_id?: string | null;
  last_verified_at?: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface FixedSopBindingDetail {
  binding: FixedSopBindingRecord;
  template: FixedSopTemplateRecord;
  routes: Record<string, string>;
}

export interface FixedSopBindingCreatePayload {
  template_id: string;
  binding_name?: string;
  status?: string;
  owner_scope?: string;
  owner_agent_id?: string;
  industry_instance_id?: string;
  workflow_template_id?: string;
  trigger_mode?: string;
  trigger_ref?: string;
  input_mapping?: Record<string, unknown>;
  output_mapping?: Record<string, unknown>;
  timeout_policy?: Record<string, unknown>;
  retry_policy?: Record<string, unknown>;
  risk_baseline?: string;
  metadata?: Record<string, unknown>;
}

export interface FixedSopDoctorCheck {
  key: string;
  label: string;
  status: "pass" | "warn" | "fail" | "info";
  message: string;
}

export interface FixedSopDoctorReport {
  binding_id: string;
  template_id: string;
  status: "ready" | "degraded" | "blocked";
  summary: string;
  checks: FixedSopDoctorCheck[];
  environment_id?: string | null;
  session_mount_id?: string | null;
  host_requirement: Record<string, unknown>;
  host_preflight: Record<string, unknown>;
  routes: Record<string, string>;
}

export interface FixedSopRunRequest {
  input_payload?: Record<string, unknown>;
  workflow_run_id?: string;
  owner_agent_id?: string;
  owner_scope?: string;
  environment_id?: string;
  session_mount_id?: string;
  dry_run?: boolean;
  metadata?: Record<string, unknown>;
}

export interface FixedSopRunResponse {
  binding_id: string;
  status: "success" | "error";
  summary: string;
  workflow_run_id?: string | null;
  evidence_id?: string | null;
  routes: Record<string, string>;
}

export interface WorkflowRunRecord {
  run_id: string;
  template_id: string;
  title: string;
  summary: string;
  status: string;
  owner_scope?: string | null;
  owner_agent_id?: string | null;
  industry_instance_id?: string | null;
  parameter_payload: Record<string, unknown>;
  preview_payload: Record<string, unknown>;
  goal_ids: string[];
  schedule_ids: string[];
  task_ids: string[];
  decision_ids: string[];
  evidence_ids: string[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface FixedSopRunDetail {
  run: WorkflowRunRecord;
  binding?: FixedSopBindingRecord | null;
  template?: FixedSopTemplateRecord | null;
  environment_id?: string | null;
  session_mount_id?: string | null;
  host_requirement: Record<string, unknown>;
  host_preflight: Record<string, unknown>;
}

export const fixedSopsApi = {
  listFixedSopTemplates: (params?: { status?: string }) => {
    const search = new URLSearchParams();
    if (params?.status) {
      search.set("status", params.status);
    }
    const suffix = search.toString();
    return request<FixedSopTemplateListResponse>(
      `/fixed-sops/templates${suffix ? `?${suffix}` : ""}`,
    );
  },

  getFixedSopTemplate: (templateId: string) =>
    request<FixedSopTemplateRecord>(
      `/fixed-sops/templates/${encodeURIComponent(templateId)}`,
    ),

  listFixedSopBindings: (params?: {
    template_id?: string;
    status?: string;
    industry_instance_id?: string;
    owner_agent_id?: string;
    limit?: number;
  }) => {
    const search = new URLSearchParams();
    if (params?.template_id) {
      search.set("template_id", params.template_id);
    }
    if (params?.status) {
      search.set("status", params.status);
    }
    if (params?.industry_instance_id) {
      search.set("industry_instance_id", params.industry_instance_id);
    }
    if (params?.owner_agent_id) {
      search.set("owner_agent_id", params.owner_agent_id);
    }
    if (typeof params?.limit === "number") {
      search.set("limit", String(params.limit));
    }
    const suffix = search.toString();
    return request<FixedSopBindingDetail[]>(
      `/fixed-sops/bindings${suffix ? `?${suffix}` : ""}`,
    );
  },

  getFixedSopBinding: (bindingId: string) =>
    request<FixedSopBindingDetail>(
      `/fixed-sops/bindings/${encodeURIComponent(bindingId)}`,
    ),

  createFixedSopBinding: (payload: FixedSopBindingCreatePayload) =>
    request<FixedSopBindingDetail>("/fixed-sops/bindings", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updateFixedSopBinding: (
    bindingId: string,
    payload: FixedSopBindingCreatePayload,
  ) =>
    request<FixedSopBindingDetail>(
      `/fixed-sops/bindings/${encodeURIComponent(bindingId)}`,
      {
        method: "PUT",
        body: JSON.stringify(payload),
      },
    ),

  runFixedSopDoctor: (bindingId: string) =>
    request<FixedSopDoctorReport>(
      `/fixed-sops/bindings/${encodeURIComponent(bindingId)}/doctor`,
      {
        method: "POST",
      },
    ),

  runFixedSopBinding: (bindingId: string, payload: FixedSopRunRequest) =>
    request<FixedSopRunResponse>(
      `/fixed-sops/bindings/${encodeURIComponent(bindingId)}/run`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),

  getFixedSopRun: (runId: string) =>
    request<FixedSopRunDetail>(`/fixed-sops/runs/${encodeURIComponent(runId)}`),
};
