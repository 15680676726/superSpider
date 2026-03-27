import type { CapabilityMount, CapabilitySummary } from "./capability";
import type { MCPClientInfo } from "./mcp";
import type { ModelSlotConfig, ProviderFallbackConfig } from "./provider";
import type { SkillSpec } from "./skill";

export interface StartupRecoverySummary {
  reason?: string;
  recovered_orphan_leases?: number;
  expired_leases?: number;
  expired_decisions?: number;
  hydrated_waiting_tasks?: number;
  resumed_schedules?: number;
  [key: string]: unknown;
}

export interface SystemOverview {
  generated_at: string;
  backup: {
    root_path: string;
    download_route: string;
    restore_route: string;
    workspace_download_route: string;
    workspace_restore_route: string;
    file_count: number;
    total_size: number;
  };
  self_check: {
    route: string;
    state_db_path: string;
    evidence_db_path: string;
  };
  providers: {
    active_model?: ModelSlotConfig | null;
    fallback_slots: ModelSlotConfig[];
    fallback_route: string;
    active_route: string;
  };
  runtime: {
    governance_route: string;
    recovery_route: string;
    events_route: string;
    startup_recovery?: StartupRecoverySummary | null;
  };
}

export interface SystemSelfCheckItem {
  name: string;
  status: "pass" | "warn" | "fail";
  summary: string;
  meta: Record<string, unknown>;
}

export interface SystemSelfCheck {
  generated_at: string;
  overall_status: "pass" | "warn" | "fail";
  checks: SystemSelfCheckItem[];
}

export interface GovernanceStatus {
  control_id: string;
  emergency_stop_active: boolean;
  emergency_reason?: string | null;
  emergency_actor?: string | null;
  paused_schedule_ids: string[];
  channel_shutdown_applied: boolean;
  blocked_capability_refs: string[];
  pending_decisions: number;
  proposed_patches: number;
  pending_patches: number;
  metadata: Record<string, unknown>;
  updated_at: string;
}

export interface GovernanceBatchResult {
  action: string;
  requested: number;
  succeeded: number;
  failed: number;
  actor: string;
  results: Array<Record<string, unknown>>;
  errors: Array<Record<string, unknown>>;
  evidence_id?: string | null;
}

export interface CapabilityMarketOverview {
  summary: CapabilitySummary;
  installed: CapabilityMount[];
  skills: SkillSpec[];
  available_skills: SkillSpec[];
  mcp_clients: MCPClientInfo[];
  routes: {
    capabilities: string;
    skills: string;
    mcp: string;
    mcp_catalog?: string;
    install_templates?: string;
    curated_sources?: string;
    curated_catalog?: string;
    curated_install?: string;
    hub_search: string;
    hub_install?: string;
  };
}

export type { ProviderFallbackConfig };
