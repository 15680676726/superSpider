import type { NavigateFunction } from "react-router-dom";
import type { BuddyExecutionCarrier } from "../api/modules/buddy";
import type {
  IndustryInstanceSummary,
  IndustryRoleBlueprint,
} from "../api/modules/industry";
import type { RuntimeChatAgentProfile } from "../runtime/runtimeChatTypes";
import sessionApi from "../pages/Chat/sessionApi";
import { normalizeSpiderMeshBrand } from "./brand";

export interface RuntimeChatBinding {
  name: string;
  threadId: string;
  userId: string;
  channel?: string;
  meta?: Record<string, unknown>;
}

interface BuddyCarrierChatBindingParams {
  sessionId?: string | null;
  profileId: string;
  profileDisplayName?: string | null;
  executionCarrier: BuddyExecutionCarrier;
  entrySource?: string;
}

interface RuntimeThreadBinding {
  thread_id: string;
  channel?: string | null;
  binding_kind?: string | null;
  industry_instance_id?: string | null;
  industry_role_id?: string | null;
  work_context_id?: string | null;
  context_key?: string | null;
  owner_scope?: string | null;
  metadata?: Record<string, unknown>;
}

type IndustryChatContext = Pick<
  IndustryInstanceSummary,
  "instance_id" | "label" | "owner_scope" | "team"
>;

const EXECUTION_CORE_ROLE_ID = "execution-core";
const EXECUTION_CORE_LABEL = "Spider Mesh 主脑";

function normalizeThreadId(threadId: string | null | undefined): string | null {
  if (!threadId) {
    return null;
  }
  const trimmed = threadId.trim();
  if (!trimmed || trimmed === "undefined" || trimmed === "null") {
    return null;
  }
  return trimmed;
}

function pickPreferredThreadBinding(
  bindings: RuntimeThreadBinding[] | null | undefined,
): RuntimeThreadBinding | null {
  if (!Array.isArray(bindings) || bindings.length === 0) {
    return null;
  }
  const bindingPriority: Record<string, number> = {
    "industry-role-alias": 0,
    "agent-primary": 1,
    "agent-alias": 2,
  };
  const sorted = [...bindings].sort((left, right) => {
    const leftPriority = bindingPriority[left.binding_kind || ""] ?? 99;
    const rightPriority = bindingPriority[right.binding_kind || ""] ?? 99;
    if (leftPriority !== rightPriority) {
      return leftPriority - rightPriority;
    }
    return (left.thread_id || "").localeCompare(right.thread_id || "");
  });
  return sorted[0] || null;
}

function resolveIndustryControlThreadId(
  industryInstanceId?: string | null,
): string | undefined {
  if (!industryInstanceId) {
    return undefined;
  }
  return `industry-chat:${industryInstanceId}:${EXECUTION_CORE_ROLE_ID}`;
}

function resolveBuddyCarrierThreadId(
  executionCarrier: BuddyExecutionCarrier,
): { threadId: string | null; controlThreadId: string | null; contextKey: string | null } {
  const chatBinding =
    executionCarrier.chat_binding && typeof executionCarrier.chat_binding === "object"
      ? executionCarrier.chat_binding
      : null;
  const controlThreadId =
    normalizeThreadId(chatBinding?.control_thread_id) ||
    normalizeThreadId(executionCarrier.control_thread_id) ||
    null;
  const threadId =
    normalizeThreadId(chatBinding?.thread_id) ||
    normalizeThreadId(executionCarrier.thread_id) ||
    controlThreadId ||
    resolveIndustryControlThreadId(executionCarrier.instance_id) ||
    null;
  const contextKey =
    (typeof chatBinding?.context_key === "string" && chatBinding.context_key.trim()) ||
    (threadId ? `control-thread:${threadId}` : null);
  return { threadId, controlThreadId: controlThreadId || threadId, contextKey };
}

export function buildBuddyExecutionCarrierChatBinding(
  params: BuddyCarrierChatBindingParams,
): RuntimeChatBinding {
  const profileId = params.profileId.trim();
  if (!profileId) {
    throw new Error("Buddy profile id is required to open runtime chat.");
  }
  const sessionId =
    typeof params.sessionId === "string" && params.sessionId.trim()
      ? params.sessionId.trim()
      : null;
  const { threadId, controlThreadId, contextKey } = resolveBuddyCarrierThreadId(
    params.executionCarrier,
  );
  if (!threadId) {
    throw new Error("Buddy execution carrier does not provide a runtime chat thread.");
  }
  const chatBinding =
    params.executionCarrier.chat_binding &&
    typeof params.executionCarrier.chat_binding === "object"
      ? params.executionCarrier.chat_binding
      : null;
  const userId =
    (typeof chatBinding?.user_id === "string" && chatBinding.user_id.trim()) ||
    `buddy:${profileId}`;
  const channel =
    (typeof chatBinding?.channel === "string" && chatBinding.channel.trim()) ||
    "console";
  return {
    name:
      normalizeSpiderMeshBrand(
        params.executionCarrier.label || params.profileDisplayName || "Buddy",
      ) || "Buddy",
    threadId,
    userId,
    channel,
    meta: {
      session_kind: "industry-control-thread",
      entry_source: params.entrySource || "buddy-onboarding",
      buddy_profile_id: profileId,
      buddy_session_id: sessionId || undefined,
      industry_instance_id: params.executionCarrier.instance_id || undefined,
      owner_scope: params.executionCarrier.owner_scope || profileId,
      control_thread_id: controlThreadId || undefined,
      context_key: contextKey || undefined,
      current_cycle_id: params.executionCarrier.current_cycle_id || undefined,
      thread_binding_kind:
        (typeof chatBinding?.binding_kind === "string" && chatBinding.binding_kind.trim()) ||
        "buddy-execution-carrier",
      team_generated: params.executionCarrier.team_generated,
      ...(chatBinding?.metadata && typeof chatBinding.metadata === "object"
        ? chatBinding.metadata
        : {}),
    },
  };
}

export function buildBoundAgentChatBinding(params: {
  agentId: string;
  agentName?: string | null;
  roleName?: string | null;
  currentFocusKind?: string | null;
  currentFocusId?: string | null;
  currentFocus?: string | null;
  industryInstanceId?: string | null;
  industryLabel?: string | null;
  industryRoleId?: string | null;
  ownerScope?: string | null;
  channel?: string | null;
  threadId?: string | null;
  threadBindings?: RuntimeThreadBinding[] | null;
  entrySource?: string;
}): RuntimeChatBinding {
  const preferredBinding = pickPreferredThreadBinding(params.threadBindings);
  const industryInstanceId =
    preferredBinding?.industry_instance_id || params.industryInstanceId;
  const industryRoleId = preferredBinding?.industry_role_id || params.industryRoleId;
  const controlThreadId = resolveIndustryControlThreadId(industryInstanceId);
  const threadId =
    controlThreadId ||
    normalizeThreadId(preferredBinding?.thread_id) ||
    normalizeThreadId(params.threadId);
  if (!threadId) {
    throw new Error(
      `Agent '${params.agentName || params.agentId}' does not have a live chat binding.`,
    );
  }
  const bindingMeta =
    preferredBinding?.metadata && typeof preferredBinding.metadata === "object"
      ? preferredBinding.metadata
      : {};
  const roleName =
    normalizeSpiderMeshBrand(
      params.roleName ||
        (typeof bindingMeta.role_name === "string" ? bindingMeta.role_name : null),
    ) || null;
  const agentName = normalizeSpiderMeshBrand(params.agentName || params.agentId);
  const isIndustryControlThread = Boolean(controlThreadId);
  return {
    name: isIndustryControlThread
      ? normalizeSpiderMeshBrand(params.industryLabel || EXECUTION_CORE_LABEL) || EXECUTION_CORE_LABEL
      : roleName
      ? `${agentName} - ${roleName}`
      : agentName,
    threadId,
    userId: params.agentId,
    channel: params.channel || preferredBinding?.channel || "console",
    meta: {
      session_kind: isIndustryControlThread ? "industry-control-thread" : "agent-chat",
      entry_source: params.entrySource || "agent-workbench",
      agent_id: params.agentId,
      agent_name: agentName,
      industry_instance_id: industryInstanceId || undefined,
      industry_label: normalizeSpiderMeshBrand(params.industryLabel) || undefined,
      industry_role_id: isIndustryControlThread
        ? EXECUTION_CORE_ROLE_ID
        : industryRoleId || undefined,
      industry_role_name: isIndustryControlThread
        ? EXECUTION_CORE_LABEL
        : roleName || undefined,
      requested_industry_role_id:
        isIndustryControlThread && industryRoleId && industryRoleId !== EXECUTION_CORE_ROLE_ID
          ? industryRoleId
          : undefined,
      owner_scope: params.ownerScope || preferredBinding?.owner_scope || undefined,
      current_focus_kind: params.currentFocusKind || undefined,
      current_focus_id: params.currentFocusId || undefined,
      current_focus: params.currentFocus || undefined,
      thread_binding_kind: preferredBinding?.binding_kind || undefined,
      control_thread_id: controlThreadId,
      work_context_id: preferredBinding?.work_context_id || undefined,
      context_key:
        preferredBinding?.context_key ||
        (controlThreadId ? `control-thread:${controlThreadId}` : undefined),
    },
  };
}

export function resolveIndustryExecutionCoreRole(
  detail: IndustryChatContext,
): IndustryRoleBlueprint | null {
  return detail.team.agents.find((agent) => agent.role_id === EXECUTION_CORE_ROLE_ID) || null;
}

export function buildIndustryRoleChatBinding(
  detail: IndustryChatContext,
  role: IndustryRoleBlueprint,
): RuntimeChatBinding {
  const executionCoreRole = resolveIndustryExecutionCoreRole(detail) || role;
  const industryLabel = normalizeSpiderMeshBrand(detail.label);
  const controlThreadId = resolveIndustryControlThreadId(detail.instance_id);
  if (!controlThreadId) {
    throw new Error("Industry control thread is not available.");
  }
  return {
    name: `${industryLabel} - ${EXECUTION_CORE_LABEL}`,
    threadId: controlThreadId,
    userId: executionCoreRole.agent_id,
    channel: "console",
    meta: {
      session_kind: "industry-control-thread",
      entry_source: "industry",
      agent_id: executionCoreRole.agent_id,
      agent_name: normalizeSpiderMeshBrand(executionCoreRole.name),
      industry_instance_id: detail.instance_id,
      industry_label: industryLabel,
      industry_role_id: EXECUTION_CORE_ROLE_ID,
      industry_role_name: EXECUTION_CORE_LABEL,
      requested_industry_role_id:
        role.role_id !== EXECUTION_CORE_ROLE_ID ? role.role_id : undefined,
      owner_scope: detail.owner_scope,
      control_thread_id: controlThreadId,
      context_key: `control-thread:${controlThreadId}`,
    },
  };
}

export function buildAgentChatBinding(
  agent: RuntimeChatAgentProfile,
): RuntimeChatBinding {
  if (!agent.industry_instance_id) {
    throw new Error(
      "当前前台只保留主脑聊天入口，非行业执行位不再提供独立聊天线程。请直接进入主脑聊天。",
    );
  }
  return buildBoundAgentChatBinding({
    agentId: agent.agent_id,
    agentName: agent.name,
    roleName: agent.role_name || undefined,
    currentFocusKind: agent.current_focus_kind || undefined,
    currentFocusId: agent.current_focus_id || undefined,
    currentFocus: agent.current_focus || undefined,
    industryInstanceId: agent.industry_instance_id,
    industryRoleId: agent.industry_role_id,
    threadId: resolveIndustryControlThreadId(agent.industry_instance_id),
    entrySource: "agent-workbench",
  });
}

export async function openRuntimeChat(
  binding: RuntimeChatBinding,
  navigate: NavigateFunction,
  options?: {
    shouldNavigate?: () => boolean;
  },
): Promise<void> {
  const thread = await sessionApi.openBoundThread(binding);
  if (options?.shouldNavigate && !options.shouldNavigate()) {
    return;
  }
  navigate(`/chat?threadId=${encodeURIComponent(thread.id)}`);
}
