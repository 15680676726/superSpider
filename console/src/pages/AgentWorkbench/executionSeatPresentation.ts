import type {
  IndustryInstanceDetail,
  IndustryRoleBlueprint,
  IndustryRuntimeAgentReport,
  IndustryStrategyTeammateContract,
} from "../../api/modules/industry";
import { runtimeRiskColor } from "../../runtime/tagSemantics";
import type { AgentCapabilityDecision, AgentProfile } from "./useAgentWorkbench";

export type SeatRoleContract = {
  role_name?: string | null;
  role_summary?: string | null;
  mission?: string | null;
  reports_to?: string | null;
  goal_kind?: string | null;
  risk_level?: string | null;
  employment_mode?: string | null;
  capabilities: string[];
  evidence_expectations: string[];
  environment_constraints: string[];
};

export type NeedsBrainConfirmationItem = {
  id: string;
  title: string;
  detail: string;
  color: string;
};

function normalizeNonEmpty(value: string | null | undefined): string | null {
  const normalized = value?.trim();
  return normalized ? normalized : null;
}

function stringList(value: string[] | null | undefined): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => normalizeNonEmpty(typeof item === "string" ? item : String(item ?? "")))
    .filter((item): item is string => Boolean(item));
}

function matchesAgent(value: string | null | undefined, agentId: string): boolean {
  return normalizeNonEmpty(value) === agentId;
}

function contractMatchesAgent(
  contract: IndustryStrategyTeammateContract,
  agent: AgentProfile,
): boolean {
  return (
    normalizeNonEmpty(contract.agent_id || undefined) === agent.agent_id ||
    normalizeNonEmpty(contract.role_id || undefined) === agent.industry_role_id
  );
}

function normalizeRoleContract(
  contract: IndustryStrategyTeammateContract,
): SeatRoleContract {
  return {
    role_name: normalizeNonEmpty(contract.role_name || undefined),
    role_summary: normalizeNonEmpty(contract.role_summary || undefined),
    mission: normalizeNonEmpty(contract.mission || undefined),
    reports_to: normalizeNonEmpty(contract.reports_to || undefined),
    goal_kind: normalizeNonEmpty(contract.goal_kind || undefined),
    risk_level: normalizeNonEmpty(contract.risk_level || undefined),
    employment_mode: normalizeNonEmpty(contract.employment_mode || undefined),
    capabilities: stringList(contract.capabilities),
    evidence_expectations: stringList(contract.evidence_expectations),
    environment_constraints: stringList(contract.environment_constraints),
  };
}

export function resolveRoleContract(
  agent: AgentProfile,
  detail: IndustryInstanceDetail,
): SeatRoleContract | null {
  const teammateContracts = detail.strategy_memory?.teammate_contracts || [];
  const matchedContract = teammateContracts.find((item) => contractMatchesAgent(item, agent));
  if (matchedContract) {
    return normalizeRoleContract(matchedContract);
  }
  const matchedRole = detail.team.agents.find(
    (item: IndustryRoleBlueprint) =>
      item.agent_id === agent.agent_id || item.role_id === agent.industry_role_id,
  );
  if (!matchedRole) {
    return null;
  }
  return {
    role_name: matchedRole.role_name,
    role_summary: matchedRole.role_summary,
    mission: matchedRole.mission,
    reports_to: matchedRole.reports_to || null,
    goal_kind: matchedRole.goal_kind,
    risk_level: matchedRole.risk_level,
    employment_mode: matchedRole.employment_mode,
    capabilities: matchedRole.allowed_capabilities,
    evidence_expectations: matchedRole.evidence_expectations,
    environment_constraints: matchedRole.environment_constraints,
  };
}

export function reportNeedsAttention(report: IndustryRuntimeAgentReport): boolean {
  if (["blocked", "failed", "cancelled"].includes(String(report.result || "").toLowerCase())) {
    return true;
  }
  if (["review", "waiting-confirm"].includes(String(report.status || "").toLowerCase())) {
    return true;
  }
  if ((report.decision_ids || []).length > 0) {
    return true;
  }
  return ["confirm", "guarded"].includes(String(report.risk_level || "").toLowerCase());
}

export function resolveEscalations(
  agent: AgentProfile,
  detail: IndustryInstanceDetail,
): IndustryRuntimeAgentReport[] {
  return [...detail.agent_reports]
    .filter(
      (report) =>
        matchesAgent(report.owner_agent_id, agent.agent_id) && reportNeedsAttention(report),
    )
    .sort((left, right) => {
      const leftTime = Date.parse(left.updated_at || left.created_at || "") || 0;
      const rightTime = Date.parse(right.updated_at || right.created_at || "") || 0;
      return rightTime - leftTime;
    })
    .slice(0, 4);
}

export function buildNeedsBrainConfirmation(
  pendingCapabilityDecisions: AgentCapabilityDecision[],
): NeedsBrainConfirmationItem[] {
  return pendingCapabilityDecisions
    .map((decision) => ({
      id: decision.id,
      title: decision.summary || decision.id,
      detail: decision.reason || decision.decision_type || "能力治理待确认",
      color: decision.risk_level ? runtimeRiskColor(decision.risk_level) : "orange",
    }))
    .slice(0, 6);
}
