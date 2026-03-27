export interface CapabilityMount {
  id: string;
  name: string;
  summary: string;
  kind:
    | "local-tool"
    | "remote-mcp"
    | "skill-bundle"
    | "provider-admin"
    | "system-op";
  source_kind: "tool" | "skill" | "mcp" | "system";

  // --- risk contract ---
  risk_level: string;
  risk_description: string;

  // --- environment contract ---
  environment_requirements: string[];
  environment_description: string;

  // --- evidence contract ---
  evidence_contract: string[];
  evidence_description: string;

  // --- access & policy ---
  role_access_policy: string[];
  tags: string[];

  // --- executor metadata ---
  executor_ref?: string | null;
  provider_ref?: string | null;
  timeout_policy?: string | null;
  replay_support: boolean;
  enabled: boolean;
  metadata: Record<string, unknown>;
}

export interface CapabilitySummary {
  total: number;
  enabled: number;
  by_kind: Record<string, number>;
  by_source: Record<string, number>;
}
