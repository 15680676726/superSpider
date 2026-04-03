import { request } from "../api";

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

export function buildRuntimeConversationsPath(threadId: string): string {
  return `/runtime-center/conversations/${encodeURIComponent(threadId)}`;
}

export async function requestRuntimeOverview<T>(): Promise<T> {
  return request<T>("/runtime-center/overview");
}

export async function requestRuntimeSurface<T>(): Promise<T> {
  return request<T>("/runtime-center/surface");
}

export async function requestRuntimeRecord<T>(path: string): Promise<T> {
  return request<T>(normalizeRuntimePath(path));
}

export async function requestRuntimeBusinessAgents<T>(
  industryInstanceId?: string | null,
): Promise<T> {
  return request<T>(buildRuntimeBusinessAgentsPath(industryInstanceId));
}

export async function requestRuntimeMainBrain<T>(): Promise<T> {
  return request<T>("/runtime-center/main-brain");
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
