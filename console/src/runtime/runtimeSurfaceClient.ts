import { request } from "../api";

type RuntimeQueryValue = string | number | boolean | null | undefined;

function buildRuntimeQuery(
  params: Record<string, RuntimeQueryValue>,
): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === null || value === undefined || value === "") {
      return;
    }
    search.set(key, String(value));
  });
  return search.toString();
}

export function normalizeRuntimePath(path: string): string {
  if (path.startsWith("/api/")) {
    return path.slice(4);
  }
  if (path === "/api") {
    return "/";
  }
  return path;
}

export function buildRuntimeBusinessAgentsPath(
  industryInstanceId?: string | null,
): string {
  const params = new URLSearchParams({ view: "business" });
  if (industryInstanceId) {
    params.set("industry_instance_id", industryInstanceId);
  }
  return `/runtime-center/agents?${params.toString()}`;
}

export function buildRuntimeGoalsPath(options?: {
  industryInstanceId?: string | null;
  status?: string | null;
  limit?: number | null;
}): string {
  const query = buildRuntimeQuery({
    status: options?.status,
    limit: options?.limit ?? undefined,
    industry_instance_id: options?.industryInstanceId,
  });
  return query ? `/goals?${query}` : "/goals";
}

export function buildRuntimeConversationsPath(threadId: string): string {
  return `/runtime-center/conversations/${encodeURIComponent(threadId)}`;
}

export async function requestRuntimeOverview<T>(): Promise<T> {
  return request<T>("/runtime-center/overview");
}

export async function requestRuntimeRecord<T>(path: string): Promise<T> {
  return request<T>(normalizeRuntimePath(path));
}

export async function requestRuntimeBusinessAgents<T>(
  industryInstanceId?: string | null,
): Promise<T> {
  return request<T>(buildRuntimeBusinessAgentsPath(industryInstanceId));
}

export async function requestRuntimeAgentDetail<T>(agentId: string): Promise<T> {
  return request<T>(
    `/runtime-center/agents/${encodeURIComponent(agentId)}`,
  );
}

export async function requestRuntimeEnvironmentList<T>(
  limit: number,
): Promise<T> {
  return request<T>(`/runtime-center/environments?limit=${limit}`);
}

export async function requestRuntimeEvidenceList<T>(limit: number): Promise<T> {
  return request<T>(`/runtime-center/evidence?limit=${limit}`);
}

export async function requestRuntimeGovernanceStatus<T>(): Promise<T> {
  return request<T>("/runtime-center/governance/status");
}

export async function requestRuntimeConversation<T>(
  threadId: string,
): Promise<T> {
  return request<T>(buildRuntimeConversationsPath(threadId));
}

export async function requestRuntimeGoals<T>(options?: {
  industryInstanceId?: string | null;
  status?: string | null;
  limit?: number | null;
}): Promise<T> {
  return request<T>(buildRuntimeGoalsPath(options));
}
