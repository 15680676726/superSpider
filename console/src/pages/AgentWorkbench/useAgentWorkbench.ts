import { useCallback, useEffect, useState } from "react";
import { api, request } from "../../api";
import type { CapabilityMount } from "../../api";
import type { IndustryInstanceDetail } from "../../api/modules/industry";
import {
  requestRuntimeAgentDetail,
  requestRuntimeBusinessAgents,
  requestRuntimeEnvironmentList,
  requestRuntimeEvidenceList,
} from "../../runtime/runtimeSurfaceClient";

const DASHBOARD_ENV_LIMIT = 20;
const DASHBOARD_EVIDENCE_LIMIT = 20;

export interface ActorRuntimeDetail {
  agent_id: string;
  actor_key: string;
  actor_fingerprint: string | null;
  actor_class: string;
  desired_state: string;
  runtime_status: string;
  activation_mode: string;
  employment_mode: string;
  persistent: boolean;
  industry_instance_id: string | null;
  industry_role_id: string | null;
  display_name: string | null;
  role_name: string | null;
  current_task_id: string | null;
  current_mailbox_id: string | null;
  current_environment_id: string | null;
  queue_depth: number;
  last_started_at: string | null;
  last_heartbeat_at: string | null;
  last_stopped_at: string | null;
  last_error_summary: string | null;
  last_result_summary: string | null;
  last_checkpoint_id: string | null;
  metadata?: Record<string, unknown>;
}

export interface ActorMailboxItem {
  id: string;
  agent_id: string;
  task_id: string | null;
  parent_mailbox_id: string | null;
  source_agent_id: string | null;
  envelope_type: string;
  title: string;
  summary: string;
  status: string;
  priority: number;
  capability_ref: string | null;
  conversation_thread_id: string | null;
  payload?: Record<string, unknown>;
  result_summary: string | null;
  error_summary: string | null;
  lease_owner: string | null;
  lease_token: string | null;
  claimed_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  retry_after_at: string | null;
  attempt_count: number;
  max_attempts: number;
  metadata?: Record<string, unknown>;
  route?: string;
}

export interface ActorCheckpointItem {
  id: string;
  agent_id: string;
  mailbox_id: string | null;
  task_id: string | null;
  checkpoint_kind: string;
  status: string;
  phase: string;
  conversation_thread_id: string | null;
  environment_ref: string | null;
  summary: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ActorLeaseItem {
  id: string;
  agent_id: string;
  lease_kind: string;
  resource_ref: string;
  lease_status: string;
  lease_token: string | null;
  owner: string | null;
  acquired_at: string | null;
  expires_at: string | null;
  heartbeat_at: string | null;
  released_at: string | null;
  metadata?: Record<string, unknown>;
}

export interface ActorThreadBindingItem {
  thread_id: string;
  agent_id: string;
  session_id: string;
  channel: string;
  binding_kind: string;
  industry_instance_id: string | null;
  industry_role_id: string | null;
  owner_scope: string | null;
  active: boolean;
  alias_of_thread_id: string | null;
  metadata?: Record<string, unknown>;
}

export interface ActorTeammateItem {
  agent_id: string;
  display_name?: string | null;
  role_name?: string | null;
  runtime_status?: string | null;
  desired_state?: string | null;
  queue_depth?: number;
  current_task_id?: string | null;
  current_mailbox_id?: string | null;
  current_environment_id?: string | null;
  industry_instance_id?: string | null;
  industry_role_id?: string | null;
  last_result_summary?: string | null;
  last_error_summary?: string | null;
  thread_bindings?: ActorThreadBindingItem[];
}

export interface AgentProfile {
  agent_id: string;
  name: string;
  role_name: string;
  role_summary: string;
  agent_class: "system" | "business";
  employment_mode: "career" | "temporary";
  activation_mode: "persistent" | "on-demand";
  suspendable: boolean;
  reports_to: string | null;
  mission: string;
  actor_key?: string | null;
  actor_fingerprint?: string | null;
  desired_state?: string | null;
  runtime_status?: string | null;
  resident?: boolean;
  status: string;
  risk_level: string;
  current_focus_kind?: string | null;
  current_focus_id?: string | null;
  current_focus?: string | null;
  current_task_id: string | null;
  current_mailbox_id?: string | null;
  queue_depth?: number;
  industry_instance_id: string | null;
  industry_role_id: string | null;
  environment_summary: string;
  current_environment_id?: string | null;
  last_checkpoint_id?: string | null;
  thread_id?: string | null;
  environment_constraints: string[];
  evidence_expectations: string[];
  today_output_summary: string;
  latest_evidence_summary: string;
  capabilities: string[];
  updated_at: string | null;
}

export interface EnvironmentItem {
  id: string;
  kind: string;
  display_name: string;
  ref: string;
  status: string;
  last_active_at: string | null;
  evidence_count: number;
  route?: string;
  metadata?: Record<string, unknown>;
  live_handle?: Record<string, unknown> | null;
  recovery?: Record<string, unknown> | null;
  host_contract?: HostContractProjection | null;
  seat_runtime?: SeatRuntimeProjection | null;
  workspace_graph?: WorkspaceGraphProjection | null;
  host_twin?: HostTwinProjection | null;
  host_companion_session?: HostCompanionSessionProjection | null;
  host_event_summary?: HostEventSummary | null;
  observations?: EnvironmentObservationItem[];
  replays?: EnvironmentReplayItem[];
  artifacts?: EnvironmentArtifactItem[];
  stats?: EnvironmentRuntimeStats;
}

export interface EnvironmentRuntimeStats {
  session_count?: number;
  observation_count?: number;
  replay_count?: number;
  artifact_count?: number;
}

export interface HostContractProjection {
  projection_kind?: string;
  is_projection?: boolean;
  surface_kind?: string | null;
  environment_id?: string | null;
  session_mount_id?: string | null;
  host_mode?: string | null;
  lease_class?: string | null;
  access_mode?: string | null;
  session_scope?: string | null;
  account_scope_ref?: string | null;
  handoff_state?: string | null;
  handoff_reason?: string | null;
  handoff_owner_ref?: string | null;
  resume_kind?: string | null;
  verification_channel?: string | null;
}

export interface SeatRuntimeProjection {
  projection_kind?: string;
  is_projection?: boolean;
  seat_ref?: string | null;
  environment_ref?: string | null;
  workspace_scope?: string | null;
  session_scope?: string | null;
  host_mode?: string | null;
  lease_status?: string | null;
  lease_owner?: string | null;
  host_id?: string | null;
  process_id?: number | null;
  session_count?: number | null;
  active_session_mount_id?: string | null;
  host_companion_status?: string | null;
  active_surface_mix?: string[];
  status?: string | null;
  occupancy_state?: string | null;
  candidate_seat_refs?: string[];
  selected_seat_ref?: string | null;
  seat_selection_policy?: string | null;
  expected_release_at?: string | null;
  live_handle_ref?: string | null;
}

export interface WorkspaceGraphWriterLock {
  owner_agent_id?: string | null;
  status?: string | null;
  scope?: string | null;
}

export interface WorkspaceGraphLock {
  resource_ref?: string | null;
  writer_lock?: WorkspaceGraphWriterLock | null;
}

export interface WorkspaceGraphHandoffCheckpoint {
  state?: string | null;
  owner_ref?: string | null;
  checkpoint_ref?: string | null;
}

export interface WorkspaceGraphProjection {
  projection_kind?: string;
  is_projection?: boolean;
  workspace_id?: string | null;
  seat_ref?: string | null;
  session_mount_id?: string | null;
  workspace_scope?: string | null;
  owner_agent_id?: string | null;
  account_scope_ref?: string | null;
  active_lock_summary?: string | null;
  collision_summary?: string | null;
  locks?: WorkspaceGraphLock[];
  handoff_checkpoint?: WorkspaceGraphHandoffCheckpoint | null;
}

export interface HostTwinOwnershipProjection {
  seat_owner_agent_id?: string | null;
  handoff_owner_ref?: string | null;
  account_scope_ref?: string | null;
  workspace_scope?: string | null;
  ownership_source?: string | null;
  active_owner_kind?: string | null;
}

export interface HostTwinAppFamilyProjection {
  active?: boolean;
  family_kind?: string | null;
  surface_ref?: string | null;
  contract_status?: string | null;
  family_scope_ref?: string | null;
  writer_lock_scope?: string | null;
}

export interface HostTwinContentionForecast {
  severity?: string | null;
  reason?: string | null;
}

export interface HostTwinLegalOwnerTransition {
  allowed?: boolean | null;
  reason?: string | null;
}

export interface HostTwinCoordinationProjection {
  seat_owner_ref?: string | null;
  workspace_owner_ref?: string | null;
  writer_owner_ref?: string | null;
  candidate_seat_refs?: string[];
  selected_seat_ref?: string | null;
  seat_selection_policy?: string | null;
  contention_forecast?: HostTwinContentionForecast | null;
  legal_owner_transition?: HostTwinLegalOwnerTransition | null;
  recommended_scheduler_action?: string | null;
  expected_release_at?: string | null;
}

export interface HostTwinProjection {
  projection_kind?: string;
  is_projection?: boolean;
  is_truth_store?: boolean;
  seat_ref?: string | null;
  environment_id?: string | null;
  session_mount_id?: string | null;
  projection_note?: string | null;
  ownership?: HostTwinOwnershipProjection | null;
  app_family_twins?: Record<string, HostTwinAppFamilyProjection>;
  coordination?: HostTwinCoordinationProjection | null;
}

export interface HostCompanionSessionProjection {
  projection_kind?: string;
  is_projection?: boolean;
  session_mount_id?: string | null;
  status?: string | null;
  resume_kind?: string | null;
}

export interface HostEventSummary {
  event_name?: string | null;
  severity?: string | null;
  recommended_runtime_response?: string | null;
}

export interface EnvironmentObservationItem {
  id?: string;
  replay_id?: string;
  artifact_id?: string;
  action_summary?: string;
  result_summary?: string;
  capability_ref?: string | null;
  storage_uri?: string | null;
  content_type?: string | null;
  replay_type?: string;
  artifact_kind?: string;
  created_at?: string | null;
}

export interface EnvironmentReplayItem {
  id?: string;
  replay_id?: string;
  artifact_id?: string;
  replay_type?: string;
  action_summary?: string;
  result_summary?: string;
  storage_uri?: string | null;
  content_type?: string | null;
  artifact_kind?: string;
  created_at?: string | null;
}

export interface EnvironmentArtifactItem {
  id?: string;
  replay_id?: string;
  artifact_id?: string;
  artifact_kind?: string;
  action_summary?: string;
  result_summary?: string;
  storage_uri?: string | null;
  content_type?: string | null;
  replay_type?: string;
  created_at?: string | null;
}

export interface EvidenceListItem {
  id: string;
  task_id?: string | null;
  trace_id?: string | null;
  actor_ref?: string | null;
  action_summary: string;
  result_summary: string;
  risk_level: string;
  environment_ref: string | null;
  capability_ref: string | null;
  created_at: string | null;
  status?: string | null;
  metadata?: Record<string, unknown>;
  artifact_count?: number;
  replay_count?: number;
}

export interface GoalTaskDetail {
  task: {
    id: string;
    title: string;
    summary: string;
    task_type: string;
    status: string;
    priority: number;
    owner_agent_id: string | null;
    parent_task_id?: string | null;
    current_risk_level: string;
    updated_at: string | null;
  };
  runtime: {
    runtime_status: string;
    current_phase: string;
    risk_level: string;
    active_environment_id: string | null;
    last_result_summary: string | null;
    last_error_summary: string | null;
    last_owner_agent_id: string | null;
    last_evidence_id: string | null;
    updated_at: string | null;
  } | null;
  frames: Array<{
    id: string;
    current_phase: string;
    environment_summary: string;
    evidence_summary: string;
    created_at: string | null;
  }>;
  decision_count: number;
  evidence_count: number;
  latest_evidence_id: string | null;
}

export interface GoalDecisionItem {
  id: string;
  task_id: string;
  decision_type: string;
  risk_level: string;
  summary: string;
  status: string;
  requested_by: string | null;
  resolution: string | null;
  created_at: string | null;
  route?: string | null;
}

export interface GoalPatchItem {
  id: string;
  kind: string;
  title: string;
  description: string;
  status: string;
  risk_level: string;
  created_at: string | null;
  applied_at: string | null;
}

export interface GoalGrowthItem {
  id: string;
  agent_id: string;
  change_type: string;
  description: string;
  source_patch_id: string | null;
  source_evidence_id: string | null;
  risk_level: string;
  result: string;
  created_at: string | null;
}

export interface AgentTaskListItem {
  task: {
    id: string;
    title?: string;
    summary?: string;
    task_type?: string;
    status?: string;
    priority?: number;
    owner_agent_id?: string | null;
    parent_task_id?: string | null;
    current_risk_level?: string;
    updated_at?: string | null;
  };
  runtime?: GoalTaskDetail["runtime"];
  route?: string;
}

export interface AgentWorkspaceSummary {
  current_environment_id: string | null;
  current_environment_ref: string | null;
  current_environment: EnvironmentItem | null;
  files_supported: boolean;
}

export interface AgentDetail {
  agent: AgentProfile;
  runtime: ActorRuntimeDetail | null;
  tasks: AgentTaskListItem[];
  mailbox: ActorMailboxItem[];
  checkpoints: ActorCheckpointItem[];
  leases: ActorLeaseItem[];
  thread_bindings: ActorThreadBindingItem[];
  teammates: ActorTeammateItem[];
  latest_collaboration: ActorMailboxItem[];
  decisions: GoalDecisionItem[];
  evidence: EvidenceListItem[];
  patches: GoalPatchItem[];
  growth: GoalGrowthItem[];
  environments: EnvironmentItem[];
  workspace: AgentWorkspaceSummary;
  capability_surface?: AgentCapabilitySurface | null;
  stats: {
    task_count: number;
    mailbox_count: number;
    checkpoint_count: number;
    lease_count: number;
    binding_count: number;
    teammate_count: number;
    decision_count: number;
    evidence_count: number;
    patch_count: number;
    growth_count: number;
    environment_count: number;
  };
}

export interface AgentCapabilitySurfaceItem {
  id: string;
  name: string;
  summary: string;
  kind: string;
  source_kind: string;
  risk_level: string;
  enabled: boolean;
  available: boolean;
  assignment_sources: string[];
  route?: string | null;
  role_access_policy?: string[];
  tags?: string[];
  environment_requirements?: string[];
  evidence_contract?: string[];
}

export interface AgentCapabilityDecision {
  id: string;
  task_id?: string | null;
  decision_type?: string | null;
  risk_level?: string | null;
  summary?: string | null;
  status?: string | null;
  requested_by?: string | null;
  resolution?: string | null;
  created_at?: string | null;
  resolved_at?: string | null;
  expires_at?: string | null;
  task_route?: string | null;
  route?: string | null;
  capabilities: string[];
  capability_assignment_mode?: string | null;
  reason?: string | null;
  actor?: string | null;
  actions?: Record<string, string>;
}

export interface AgentCapabilitySurface {
  agent_id: string;
  actor_present: boolean;
  industry_instance_id?: string | null;
  industry_role_id?: string | null;
  default_mode: string;
  baseline_capabilities: string[];
  blueprint_capabilities: string[];
  explicit_capabilities: string[];
  recommended_capabilities: string[];
  effective_capabilities: string[];
  items: AgentCapabilitySurfaceItem[];
  pending_decisions: AgentCapabilityDecision[];
  recent_decisions: AgentCapabilityDecision[];
  drift_detected: boolean;
  stats: {
    baseline_count: number;
    blueprint_count: number;
    explicit_count: number;
    recommended_count: number;
    effective_count: number;
    pending_decision_count: number;
    recent_decision_count: number;
  };
  routes: {
    detail?: string;
    actor_detail?: string;
    governed_assign?: string;
    actor_governed_assign?: string;
    direct_assign?: string;
    actor_direct_assign?: string;
  };
}

export interface GovernedCapabilityAssignmentRequest {
  capabilities: string[];
  mode: "replace" | "merge";
  actor?: string;
  reason?: string | null;
  use_recommended?: boolean;
}

export interface GovernedCapabilityAssignmentResult {
  submitted?: boolean;
  updated?: boolean;
  result?: {
    success?: boolean;
    summary?: string;
    error?: string | null;
    phase?: string;
    decision_request_id?: string | null;
  };
  decision?: AgentCapabilityDecision | null;
  capability_surface?: AgentCapabilitySurface | null;
}

const EXECUTION_CORE_ROLE_ID = "execution-core";

function resolveRuntimeIndustryFocus(agent: AgentProfile | null | undefined): {
  assignmentId?: string;
  backlogItemId?: string;
} {
  const focusKind = agent?.current_focus_kind?.trim().toLowerCase();
  const focusId = agent?.current_focus_id?.trim() || "";
  if (!focusId) {
    return {};
  }
  if (focusKind === "assignment") {
    return { assignmentId: focusId };
  }
  if (focusKind === "backlog" || focusKind === "backlog-item") {
    return { backlogItemId: focusId };
  }
  return {};
}

function pickPreferredAgent(agents: AgentProfile[]): AgentProfile | null {
  return (
    agents.find(
      (agent) =>
        agent.agent_class === "business" &&
        agent.industry_role_id !== EXECUTION_CORE_ROLE_ID,
    ) ||
    agents.find((agent) => agent.agent_class === "business") ||
    agents.find((agent) => agent.industry_role_id === EXECUTION_CORE_ROLE_ID) ||
    agents[0] ||
    null
  );
}

interface AgentWorkbenchOptions {
  industryInstanceId?: string | null;
}

export function useAgentWorkbench(options: AgentWorkbenchOptions = {}) {
  const industryInstanceId = options.industryInstanceId?.trim() || null;
  const [agents, setAgents] = useState<AgentProfile[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<AgentProfile | null>(null);
  const [agentDetail, setAgentDetail] = useState<AgentDetail | null>(null);
  const [industryDetail, setIndustryDetail] = useState<IndustryInstanceDetail | null>(
    null,
  );
  const [capabilityCatalog, setCapabilityCatalog] = useState<CapabilityMount[]>([]);
  const [environments, setEnvironments] = useState<EnvironmentItem[]>([]);
  const [evidence, setEvidence] = useState<EvidenceListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [agentDetailLoading, setAgentDetailLoading] = useState(false);
  const [industryDetailLoading, setIndustryDetailLoading] = useState(false);
  const [capabilityCatalogLoading, setCapabilityCatalogLoading] = useState(false);
  const [dashboardError, setDashboardError] = useState<string | null>(null);
  const [agentDetailError, setAgentDetailError] = useState<string | null>(null);
  const [industryDetailError, setIndustryDetailError] = useState<string | null>(null);
  const [capabilityActionKey, setCapabilityActionKey] = useState<string | null>(null);
  const [actorActionKey, setActorActionKey] = useState<string | null>(null);
  const selectedIndustryInstanceId =
    selectedAgent?.industry_instance_id?.trim() || industryInstanceId;

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    try {
      setDashboardError(null);
      const [agentList, envList, evidenceList] = await Promise.all([
        requestRuntimeBusinessAgents<AgentProfile[]>(industryInstanceId),
        requestRuntimeEnvironmentList<EnvironmentItem[]>(
          DASHBOARD_ENV_LIMIT,
        ),
        requestRuntimeEvidenceList<EvidenceListItem[]>(
          DASHBOARD_EVIDENCE_LIMIT,
        ),
      ]);

      const normalizedAgents = Array.isArray(agentList) ? agentList : [];

      setAgents(normalizedAgents);
      setEnvironments(Array.isArray(envList) ? envList : []);
      setEvidence(Array.isArray(evidenceList) ? evidenceList : []);

      setSelectedAgent((current) => {
        if (current) {
          const refreshed = normalizedAgents.find(
            (item) => item.agent_id === current.agent_id,
          );
          if (refreshed) {
            return refreshed;
          }
        }
        return pickPreferredAgent(normalizedAgents);
      });
    } catch (error) {
      console.error("Failed to load agent workbench data:", error);
      setDashboardError(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
    }
  }, [industryInstanceId]);

  const fetchAgentDetail = useCallback(async (agentId: string) => {
    setAgentDetailLoading(true);
    setAgentDetail(null);
    try {
      setAgentDetailError(null);
      const detail = await requestRuntimeAgentDetail<AgentDetail>(agentId);
      setAgentDetail(detail);
    } catch (error) {
      console.error("Failed to load agent detail:", error);
      setAgentDetail(null);
      setAgentDetailError(error instanceof Error ? error.message : String(error));
    } finally {
      setAgentDetailLoading(false);
    }
  }, []);

  const refreshIndustryDetail = useCallback(
    async (
      overrideIndustryInstanceId?: string | null,
      focusAgent?: AgentProfile | null,
    ) => {
      const targetIndustryInstanceId =
        overrideIndustryInstanceId?.trim() || selectedIndustryInstanceId;
      if (!targetIndustryInstanceId) {
        setIndustryDetail(null);
        setIndustryDetailLoading(false);
        setIndustryDetailError(null);
        return null;
      }
      setIndustryDetailLoading(true);
      try {
        setIndustryDetailError(null);
        const detail = await api.getRuntimeIndustryDetail(
          targetIndustryInstanceId,
          resolveRuntimeIndustryFocus(focusAgent ?? selectedAgent),
        );
        setIndustryDetail(detail);
        return detail;
      } catch (error) {
        console.error("Failed to load industry runtime detail:", error);
        setIndustryDetail(null);
        setIndustryDetailError(error instanceof Error ? error.message : String(error));
        return null;
      } finally {
        setIndustryDetailLoading(false);
      }
    },
    [selectedAgent, selectedIndustryInstanceId],
  );

  const fetchCapabilityCatalog = useCallback(async () => {
    setCapabilityCatalogLoading(true);
    try {
      const catalog = await request<CapabilityMount[]>("/capabilities");
      setCapabilityCatalog(Array.isArray(catalog) ? catalog : []);
    } catch (error) {
      console.error("Failed to load capability catalog:", error);
    } finally {
      setCapabilityCatalogLoading(false);
    }
  }, [industryInstanceId]);

  useEffect(() => {
    void fetchDashboard();
  }, [fetchDashboard]);

  useEffect(() => {
    void fetchCapabilityCatalog();
  }, [fetchCapabilityCatalog]);

  useEffect(() => {
    if (!selectedAgent?.agent_id) {
      setAgentDetail(null);
      setAgentDetailError(null);
      return;
    }
    void fetchAgentDetail(selectedAgent.agent_id);
  }, [fetchAgentDetail, selectedAgent?.agent_id]);

  useEffect(() => {
    if (!selectedIndustryInstanceId) {
      setIndustryDetail(null);
      setIndustryDetailLoading(false);
      setIndustryDetailError(null);
      return;
    }
    void refreshIndustryDetail(selectedIndustryInstanceId, selectedAgent);
  }, [refreshIndustryDetail, selectedAgent, selectedIndustryInstanceId]);

  const refresh = useCallback(async () => {
    await Promise.all([
      fetchDashboard(),
      fetchCapabilityCatalog(),
      refreshIndustryDetail(selectedIndustryInstanceId, selectedAgent),
    ]);
  }, [
    fetchCapabilityCatalog,
    fetchDashboard,
    refreshIndustryDetail,
    selectedAgent,
    selectedIndustryInstanceId,
  ]);

  const refreshAgentDetail = useCallback(async () => {
    if (!selectedAgent?.agent_id) {
      return;
    }
    await Promise.all([
      fetchAgentDetail(selectedAgent.agent_id),
      refreshIndustryDetail(selectedAgent.industry_instance_id, selectedAgent),
    ]);
  }, [
    fetchAgentDetail,
    refreshIndustryDetail,
    selectedAgent?.agent_id,
    selectedAgent?.industry_instance_id,
  ]);

  const refreshActorSurface = useCallback(
    async (agentId: string) => {
      await Promise.all([
        fetchDashboard(),
        fetchAgentDetail(agentId),
        refreshIndustryDetail(
          selectedIndustryInstanceId,
          agents.find((item) => item.agent_id === agentId) || selectedAgent,
        ),
      ]);
    },
    [
      agents,
      fetchAgentDetail,
      fetchDashboard,
      refreshIndustryDetail,
      selectedAgent,
      selectedIndustryInstanceId,
    ],
  );

  const submitGovernedCapabilityAssignment = useCallback(
    async (
      agentId: string,
      payload: GovernedCapabilityAssignmentRequest,
      options?: { requireActor?: boolean },
    ) => {
      const route = options?.requireActor
        ? `/runtime-center/actors/${encodeURIComponent(agentId)}/capabilities/governed`
        : `/runtime-center/agents/${encodeURIComponent(agentId)}/capabilities/governed`;
      const actionKey = `govern:${options?.requireActor ? "actor" : "agent"}:${agentId}`;
      setCapabilityActionKey(actionKey);
      try {
        const result = await request<GovernedCapabilityAssignmentResult>(route, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        if (selectedAgent?.agent_id === agentId) {
          await fetchAgentDetail(agentId);
        } else {
          await fetchDashboard();
        }
        return result;
      } finally {
        setCapabilityActionKey(null);
      }
    },
    [fetchAgentDetail, fetchDashboard, selectedAgent?.agent_id],
  );

  const resolveCapabilityDecision = useCallback(
    async (
      decisionId: string,
      action: "approve" | "reject" | "review",
      payload?: Record<string, unknown>,
    ) => {
      const route =
        action === "review"
          ? `/runtime-center/governed/decisions/${encodeURIComponent(decisionId)}/review`
          : `/runtime-center/decisions/${encodeURIComponent(decisionId)}/${action}`;
      const actionKey = `decision:${action}:${decisionId}`;
      setCapabilityActionKey(actionKey);
      try {
        const result = await request<Record<string, unknown>>(route, {
          method: "POST",
          body: payload ? JSON.stringify(payload) : undefined,
        });
        if (selectedAgent?.agent_id) {
          await fetchAgentDetail(selectedAgent.agent_id);
        } else {
          await fetchDashboard();
        }
        return result;
      } finally {
        setCapabilityActionKey(null);
      }
    },
    [fetchAgentDetail, fetchDashboard, selectedAgent?.agent_id],
  );

  const pauseActorRuntime = useCallback(
    async (agentId: string, reason?: string | null) => {
      const actionKey = `actor:pause:${agentId}`;
      setActorActionKey(actionKey);
      try {
        const result = await api.pauseActorRuntime(agentId, {
          actor: "agent-workbench",
          reason: reason ?? undefined,
        });
        await refreshActorSurface(agentId);
        return result;
      } finally {
        setActorActionKey(null);
      }
    },
    [refreshActorSurface],
  );

  const resumeActorRuntime = useCallback(
    async (agentId: string) => {
      const actionKey = `actor:resume:${agentId}`;
      setActorActionKey(actionKey);
      try {
        const result = await api.resumeActorRuntime(agentId, {
          actor: "agent-workbench",
        });
        await refreshActorSurface(agentId);
        return result;
      } finally {
        setActorActionKey(null);
      }
    },
    [refreshActorSurface],
  );

  const retryActorMailboxRuntime = useCallback(
    async (agentId: string, mailboxId: string) => {
      const actionKey = `actor:retry:${agentId}:${mailboxId}`;
      setActorActionKey(actionKey);
      try {
        const result = await api.retryActorMailboxRuntime(agentId, mailboxId, {
          actor: "agent-workbench",
        });
        await refreshActorSurface(agentId);
        return result;
      } finally {
        setActorActionKey(null);
      }
    },
    [refreshActorSurface],
  );

  const cancelActorRuntime = useCallback(
    async (agentId: string, taskId?: string | null) => {
      const actionKey = `actor:cancel:${agentId}:${taskId ?? "all"}`;
      setActorActionKey(actionKey);
      try {
        const result = await api.cancelActorRuntime(agentId, {
          actor: "agent-workbench",
          task_id: taskId ?? undefined,
        });
        await refreshActorSurface(agentId);
        return result;
      } finally {
        setActorActionKey(null);
      }
    },
    [refreshActorSurface],
  );

  return {
    agents,
    selectedAgent,
    setSelectedAgent,
    agentDetail,
    industryDetail,
    capabilityCatalog,
    environments,
    evidence,
    loading,
    agentDetailLoading,
    industryDetailLoading,
    capabilityCatalogLoading,
    dashboardError,
    agentDetailError,
    industryDetailError,
    capabilityActionKey,
    actorActionKey,
    refresh,
    refreshAgentDetail,
    refreshIndustryDetail,
    submitGovernedCapabilityAssignment,
    resolveCapabilityDecision,
    pauseActorRuntime,
    resumeActorRuntime,
    retryActorMailboxRuntime,
    cancelActorRuntime,
  };
}

