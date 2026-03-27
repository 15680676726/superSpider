export interface ActiveHoursConfig {
  start: string;
  end: string;
}

export interface RuntimeHeartbeatConfig {
  enabled: boolean;
  every: string;
  target: string;
  activeHours?: ActiveHoursConfig | null;
}

export interface RuntimeHeartbeatRuntime {
  status: string;
  enabled: boolean;
  every: string;
  target: string;
  activeHours?: ActiveHoursConfig | null;
  last_run_at?: string | null;
  next_run_at?: string | null;
  last_error?: string | null;
  query_path: string;
}

export interface RuntimeHeartbeatDetail {
  heartbeat: RuntimeHeartbeatConfig;
  runtime: RuntimeHeartbeatRuntime;
  route: string;
  actions: Record<string, string>;
}

export interface RuntimeHeartbeatMutationResult {
  updated?: boolean;
  started?: boolean;
  result?: Record<string, unknown>;
  heartbeat: RuntimeHeartbeatDetail;
}
