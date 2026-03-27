export interface RuntimeScheduleConfig {
  id: string;
  name: string;
  enabled?: boolean;
  schedule: {
    type: "cron";
    cron: string;
    timezone?: string;
  };
  task_type?: "text" | "agent";
  text?: string;
  request?: {
    input: unknown;
    session_id?: string | null;
    user_id?: string | null;
    [key: string]: unknown;
  };
  dispatch: {
    type: "channel";
    channel?: string;
    target: {
      user_id: string;
      session_id: string;
    };
    mode?: "stream" | "final";
    meta?: Record<string, unknown>;
  };
  runtime?: {
    max_concurrency?: number;
    timeout_seconds?: number;
    misfire_grace_seconds?: number;
  };
  meta?: Record<string, unknown>;
}

export interface RuntimeScheduleSummary {
  id: string;
  title?: string;
  name?: string;
  status: string;
  owner?: string | null;
  cron?: string | null;
  enabled?: boolean;
  task_type?: string | null;
  updated_at?: string | null;
  last_run_at?: string | null;
  next_run_at?: string | null;
  last_error?: string | null;
  route?: string | null;
  actions?: Record<string, string>;
}

export interface RuntimeScheduleRecord {
  id: string;
  title: string;
  status: string;
  enabled: boolean;
  cron: string;
  timezone?: string | null;
  task_type?: string | null;
  target_channel?: string | null;
  target_user_id?: string | null;
  target_session_id?: string | null;
  last_run_at?: string | null;
  next_run_at?: string | null;
  last_error?: string | null;
}

export interface RuntimeScheduleDetail {
  schedule: RuntimeScheduleRecord;
  spec: RuntimeScheduleConfig;
  runtime: {
    status: string;
    enabled: boolean;
    last_run_at?: string | null;
    next_run_at?: string | null;
    last_error?: string | null;
  };
  route: string;
  actions: Record<string, string>;
}

export interface RuntimeScheduleMutationResult {
  created?: boolean;
  updated?: boolean;
  deleted?: boolean;
  started?: boolean;
  paused?: boolean;
  resumed?: boolean;
  schedule?: RuntimeScheduleDetail;
  schedule_id?: string;
  route?: string;
}
