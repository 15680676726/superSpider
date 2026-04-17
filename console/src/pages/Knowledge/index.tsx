import { useCallback, useEffect, useRef, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Empty,
  Form,
  Input,
  List,
  Select,
  Space,
  Spin,
  Switch,
  Tabs,
  Tag,
  Typography,
  message,
} from "antd";
import {
  DatabaseOutlined,
  DeploymentUnitOutlined,
  ReloadOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import { request } from "../../api";
import type {
  AgentDetail,
  AgentProfile,
} from "../AgentWorkbench/useAgentWorkbench";
import {
  presentExecutionActorName,
  presentRuntimeStatusLabel,
} from "../../runtime/executionPresentation";
import {
  getChangeTypeLabel,
  getLeaseKindLabel,
  getPhaseLabel,
  getStatusLabel,
} from "../AgentWorkbench/copy";
import { normalizeSpiderMeshBrand } from "../../utils/brand";

const { Paragraph, Text, Title } = Typography;
const { TextArea } = Input;
const EXECUTION_CORE_ROLE_ID = "execution-core";

type StrategyItem = {
  strategy_id: string;
  scope_type: "global" | "industry";
  title: string;
  summary: string;
  mission: string;
  north_star: string;
  thinking_axes: string[];
  delegation_policy: string[];
  evidence_requirements: string[];
  status: string;
};

type DocItem = {
  document_id: string;
  title: string;
  chunk_count: number;
  tags: string[];
};

type ChunkItem = {
  id: string;
  document_id: string;
  title: string;
  content: string;
  tags: string[];
};

type MemoryItem = {
  id: string;
  title: string;
  summary?: string;
  scope_type?: string;
  scope_id?: string;
  tags: string[];
};

type MemoryScopeType =
  | "global"
  | "industry"
  | "agent"
  | "task"
  | "work_context";

export const MEMORY_SCOPE_OPTIONS: Array<{
  label: string;
  value: MemoryScopeType;
}> = [
  { label: "全局", value: "global" },
  { label: "行业", value: "industry" },
  { label: "执行位", value: "agent" },
  { label: "任务", value: "task" },
  { label: "工作上下文", value: "work_context" },
];

type MemoryBackendItem = {
  backend_id: string;
  label: string;
  available: boolean;
  is_default?: boolean;
  reason?: string | null;
};

const FORMAL_MEMORY_BACKENDS: MemoryBackendItem[] = [
  {
    backend_id: "truth-first",
    label: "正式共享记忆（truth-first）",
    available: true,
    is_default: true,
  },
];

type MemoryRecallHit = {
  entry_id: string;
  kind: string;
  title: string;
  summary: string;
  content_excerpt: string;
  source_type: string;
  source_ref: string;
  source_route?: string | null;
  scope_type: string;
  scope_id: string;
  confidence: number;
  quality_score: number;
  score: number;
  backend: string;
  evidence_refs: string[];
  entity_keys: string[];
  opinion_keys: string[];
  source_updated_at?: string | null;
};

type MemoryRecallResponse = {
  query: string;
  backend_requested?: string | null;
  backend_used: string;
  fallback_reason?: string | null;
  hits: MemoryRecallHit[];
};

type MemoryFactIndexEntry = {
  id: string;
  source_type: string;
  source_ref: string;
  scope_type: string;
  scope_id: string;
  owner_agent_id?: string | null;
  industry_instance_id?: string | null;
  title: string;
  summary: string;
  content_excerpt: string;
  entity_keys: string[];
  opinion_keys: string[];
  tags: string[];
  evidence_refs: string[];
  confidence: number;
  quality_score: number;
  source_updated_at?: string | null;
};

type MemoryEntityView = {
  entity_id: string;
  entity_key: string;
  scope_type: string;
  scope_id: string;
  display_name: string;
  entity_type: string;
  summary: string;
  confidence: number;
  supporting_refs: string[];
  contradicting_refs: string[];
  related_entities: string[];
  source_refs: string[];
  updated_at?: string | null;
};

type MemoryOpinionView = {
  opinion_id: string;
  subject_key: string;
  scope_type: string;
  scope_id: string;
  opinion_key: string;
  stance: string;
  summary: string;
  confidence: number;
  supporting_refs: string[];
  contradicting_refs: string[];
  entity_keys: string[];
  source_refs: string[];
  updated_at?: string | null;
};

type MemoryRelationView = {
  relation_id: string;
  source_node_id: string;
  target_node_id: string;
  relation_kind: string;
  scope_type: string;
  scope_id: string;
  owner_agent_id?: string | null;
  industry_instance_id?: string | null;
  summary: string;
  confidence: number;
  source_refs: string[];
  metadata?: Record<string, unknown>;
  updated_at?: string | null;
};

type MemoryActivationSummary = {
  scope_type: string;
  scope_id: string;
  activated_count: number;
  contradiction_count: number;
  top_entities: string[];
  top_opinions: string[];
  top_relations: string[];
  top_relation_kinds: string[];
  top_constraints: string[];
  top_next_actions: string[];
  support_refs: string[];
  top_evidence_refs: string[];
  evidence_refs: string[];
  strategy_refs: string[];
};

type MemorySleepDigest = {
  headline: string;
  summary: string;
  current_constraints: string[];
  current_focus: string[];
  top_entities: string[];
  top_relations: string[];
  evidence_refs: string[];
};

type MemorySleepSoftRule = {
  rule_id: string;
  rule_text: string;
  rule_kind: string;
  state: string;
  risk_level: string;
  hit_count: number;
  conflict_count: number;
  day_span: number;
  evidence_refs: string[];
};

type MemorySleepConflict = {
  proposal_id: string;
  title: string;
  summary: string;
  recommended_action: string;
  risk_level: string;
  status: string;
  conflicting_refs: string[];
  supporting_refs: string[];
};

type MemoryIndustryProfile = {
  profile_id: string;
  industry_instance_id: string;
  headline: string;
  summary: string;
  strategic_direction: string;
  active_constraints: string[];
  active_focuses: string[];
  key_entities: string[];
  key_relations: string[];
  evidence_refs: string[];
  version?: number | null;
  status?: string | null;
  metadata?: Record<string, unknown>;
};

type MemoryWorkContextOverlay = {
  overlay_id: string;
  work_context_id: string;
  industry_instance_id?: string | null;
  headline: string;
  summary: string;
  focus_summary: string;
  active_constraints: string[];
  active_focuses: string[];
  active_entities: string[];
  active_relations: string[];
  evidence_refs: string[];
  version?: number | null;
  status?: string | null;
  metadata?: Record<string, unknown>;
};

type MemoryStructureProposal = {
  proposal_id: string;
  title: string;
  summary: string;
  recommended_action: string;
  risk_level: string;
  status: string;
};

type MemorySlotPreference = {
  preference_id: string;
  industry_instance_id: string;
  slot_key: string;
  slot_label: string;
  promotion_count: number;
  status: string;
};

type MemoryContinuityDetail = {
  detail_id: string;
  scope_type: string;
  scope_id: string;
  detail_key: string;
  detail_text: string;
  detail_label: string;
  source_kind: string;
  pinned: boolean;
  status: string;
};

type MemorySleepOverlay = {
  digest?: MemorySleepDigest | null;
  industry_profile?: MemoryIndustryProfile | null;
  work_context_overlay?: MemoryWorkContextOverlay | null;
  structure_proposals: MemoryStructureProposal[];
  soft_rules: MemorySleepSoftRule[];
  conflicts: MemorySleepConflict[];
  slot_preferences: MemorySlotPreference[];
  continuity_details: MemoryContinuityDetail[];
};

type MemorySurfacePayload = {
  scope_type: string;
  scope_id: string;
  query?: string | null;
  activation?: MemoryActivationSummary | null;
  sleep?: MemorySleepOverlay | null;
  relation_count: number;
  relation_kind_counts: Record<string, number>;
  relations: MemoryRelationView[];
};

type MemorySleepVersionChange = {
  field: string;
  from: unknown;
  to: unknown;
};

type MemorySleepVersionDiff = {
  scope_type: string;
  scope_id: string;
  from_version: number;
  to_version: number;
  changes: MemorySleepVersionChange[];
};

type MemoryReflectionRun = {
  run_id: string;
  scope_type: string;
  scope_id: string;
  trigger_kind: string;
  status: string;
  summary: string;
  generated_entity_ids: string[];
  generated_opinion_ids: string[];
  metadata?: {
    proposal_ids?: string[];
    entity_count?: number;
    opinion_count?: number;
  };
  started_at?: string | null;
  completed_at?: string | null;
};

type MemoryRebuildSummary = {
  fact_index_count: number;
  relation_view_count?: number;
  completed_at?: string | null;
};

type MemoryReflectionSummary = {
  entity_count: number;
  opinion_count: number;
  proposal_ids: string[];
  summary: string;
};

function parseCsv(value: string): string[] {
  return value
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function isExecutionCore(agent: AgentProfile | null | undefined): boolean {
  return Boolean(
    agent &&
      (agent.industry_role_id === EXECUTION_CORE_ROLE_ID ||
        agent.agent_id === "copaw-agent-runner"),
  );
}

function appendSearchParam(
  search: URLSearchParams,
  key: string,
  value: string | number | boolean | null | undefined,
) {
  if (value === null || value === undefined) {
    return;
  }
  const normalized =
    typeof value === "string" ? value.trim() : String(value).trim();
  if (!normalized) {
    return;
  }
  search.set(key, normalized);
}

export function buildMemoryScopeSearch(scopeType: MemoryScopeType, scopeId: string) {
  const normalizedScopeId = scopeId.trim() || (scopeType === "global" ? "runtime" : "");
  const search = new URLSearchParams();
  appendSearchParam(search, "scope_type", scopeType);
  appendSearchParam(search, "scope_id", normalizedScopeId);
  if (scopeType === "industry") {
    appendSearchParam(search, "industry_instance_id", normalizedScopeId);
  }
  if (scopeType === "agent") {
    appendSearchParam(search, "owner_agent_id", normalizedScopeId);
    appendSearchParam(search, "agent_id", normalizedScopeId);
  }
  if (scopeType === "task") {
    appendSearchParam(search, "task_id", normalizedScopeId);
  }
  if (scopeType === "work_context") {
    appendSearchParam(search, "work_context_id", normalizedScopeId);
  }
  if (scopeType === "global") {
    appendSearchParam(search, "global_scope_id", normalizedScopeId);
  }
  return { scopeId: normalizedScopeId, search };
}

function formatScope(scopeType?: string | null, scopeId?: string | null): string {
  if (!scopeType && !scopeId) {
    return "n/a";
  }
  return `${scopeType || "scope"}:${scopeId || "runtime"}`;
}

function formatPercent(value?: number | null): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "n/a";
  }
  return `${Math.round(value * 100)}%`;
}

function normalizeNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function describeMemoryDiffValue(value: unknown): string {
  if (Array.isArray(value)) {
    const items = value
      .map((item) => String(item ?? "").trim())
      .filter(Boolean);
    return items.length > 0 ? items.join(" / ") : "空";
  }
  if (value === null || value === undefined || value === "") {
    return "空";
  }
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

function formatDateTime(value?: string | null): string {
  if (!value) {
    return "n/a";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function compactText(value: string | null | undefined, maxLength = 180): string {
  const normalized = (value || "").trim();
  if (!normalized) {
    return "n/a";
  }
  if (normalized.length <= maxLength) {
    return normalized;
  }
  return `${normalized.slice(0, maxLength - 3).trimEnd()}...`;
}

function normalizeTextList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => String(item ?? "").trim())
    .filter(Boolean);
}

function normalizeRecord(value: unknown): Record<string, unknown> | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return undefined;
  }
  return value as Record<string, unknown>;
}

function normalizeMemorySleepDigest(value: unknown): MemorySleepDigest | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const payload = value as Record<string, unknown>;
  const headline = String(payload.headline || "").trim();
  const summary = String(payload.summary || "").trim();
  const currentConstraints = normalizeTextList(payload.current_constraints);
  const currentFocus = normalizeTextList(payload.current_focus);
  const topEntities = normalizeTextList(payload.top_entities);
  const topRelations = normalizeTextList(payload.top_relations);
  const evidenceRefs = normalizeTextList(payload.evidence_refs);
  if (
    !headline &&
    !summary &&
    currentConstraints.length === 0 &&
    currentFocus.length === 0 &&
    topEntities.length === 0 &&
    topRelations.length === 0 &&
    evidenceRefs.length === 0
  ) {
    return null;
  }
  return {
    headline: headline || "记忆整理摘要",
    summary,
    current_constraints: currentConstraints,
    current_focus: currentFocus,
    top_entities: topEntities,
    top_relations: topRelations,
    evidence_refs: evidenceRefs,
  };
}

function normalizeMemorySleepRules(value: unknown): MemorySleepSoftRule[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item, index) => {
      if (!item || typeof item !== "object" || Array.isArray(item)) {
        return null;
      }
      const payload = item as Record<string, unknown>;
      const ruleText = String(payload.rule_text || "").trim();
      if (!ruleText) {
        return null;
      }
      return {
        rule_id: String(payload.rule_id || `rule-${index + 1}`),
        rule_text: ruleText,
        rule_kind: String(payload.rule_kind || "guidance"),
        state: String(payload.state || "candidate"),
        risk_level: String(payload.risk_level || "low"),
        hit_count: Number(payload.hit_count || 0),
        conflict_count: Number(payload.conflict_count || 0),
        day_span: Number(payload.day_span || 0),
        evidence_refs: normalizeTextList(payload.evidence_refs),
      };
    })
    .filter((item): item is MemorySleepSoftRule => Boolean(item));
}

function normalizeMemorySleepConflicts(value: unknown): MemorySleepConflict[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item, index) => {
      if (!item || typeof item !== "object" || Array.isArray(item)) {
        return null;
      }
      const payload = item as Record<string, unknown>;
      const title = String(payload.title || "").trim();
      const summary = String(payload.summary || "").trim();
      const recommendedAction = String(payload.recommended_action || "").trim();
      if (!title && !summary && !recommendedAction) {
        return null;
      }
      return {
        proposal_id: String(payload.proposal_id || `conflict-${index + 1}`),
        title: title || "待处理冲突",
        summary,
        recommended_action: recommendedAction,
        risk_level: String(payload.risk_level || "high"),
        status: String(payload.status || "pending"),
        conflicting_refs: normalizeTextList(payload.conflicting_refs),
        supporting_refs: normalizeTextList(payload.supporting_refs),
      };
    })
    .filter((item): item is MemorySleepConflict => Boolean(item));
}

function normalizeMemoryIndustryProfile(value: unknown): MemoryIndustryProfile | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const payload = value as Record<string, unknown>;
  const industryInstanceId = String(payload.industry_instance_id || "").trim();
  const headline = String(payload.headline || "").trim();
  const summary = String(payload.summary || "").trim();
  const strategicDirection = String(payload.strategic_direction || "").trim();
  const activeConstraints = normalizeTextList(payload.active_constraints);
  const activeFocuses = normalizeTextList(payload.active_focuses);
  const keyEntities = normalizeTextList(payload.key_entities);
  const keyRelations = normalizeTextList(payload.key_relations);
  const evidenceRefs = normalizeTextList(payload.evidence_refs);
  if (
    !industryInstanceId &&
    !headline &&
    !summary &&
    !strategicDirection &&
    activeConstraints.length === 0 &&
    activeFocuses.length === 0
  ) {
    return null;
  }
  return {
    profile_id: String(payload.profile_id || ""),
    industry_instance_id: industryInstanceId,
    headline: headline || "行业长期记忆",
    summary,
    strategic_direction: strategicDirection,
    active_constraints: activeConstraints,
    active_focuses: activeFocuses,
    key_entities: keyEntities,
    key_relations: keyRelations,
    evidence_refs: evidenceRefs,
    version: normalizeNumber(payload.version),
    status: String(payload.status || "").trim() || null,
    metadata: normalizeRecord(payload.metadata),
  };
}

function normalizeMemoryWorkContextOverlay(value: unknown): MemoryWorkContextOverlay | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const payload = value as Record<string, unknown>;
  const workContextId = String(payload.work_context_id || "").trim();
  const headline = String(payload.headline || "").trim();
  const summary = String(payload.summary || "").trim();
  const focusSummary = String(payload.focus_summary || "").trim();
  const activeConstraints = normalizeTextList(payload.active_constraints);
  const activeFocuses = normalizeTextList(payload.active_focuses);
  const activeEntities = normalizeTextList(payload.active_entities);
  const activeRelations = normalizeTextList(payload.active_relations);
  const evidenceRefs = normalizeTextList(payload.evidence_refs);
  if (
    !workContextId &&
    !headline &&
    !summary &&
    !focusSummary &&
    activeConstraints.length === 0 &&
    activeFocuses.length === 0
  ) {
    return null;
  }
  return {
    overlay_id: String(payload.overlay_id || ""),
    work_context_id: workContextId,
    headline: headline || "工作记忆 overlay",
    summary,
    focus_summary: focusSummary,
    active_constraints: activeConstraints,
    active_focuses: activeFocuses,
    active_entities: activeEntities,
    active_relations: activeRelations,
    evidence_refs: evidenceRefs,
    version: normalizeNumber(payload.version),
    status: String(payload.status || "").trim() || null,
    metadata: normalizeRecord(payload.metadata),
  };
}

function normalizeMemoryStructureProposals(value: unknown): MemoryStructureProposal[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item, index) => {
      if (!item || typeof item !== "object" || Array.isArray(item)) {
        return null;
      }
      const payload = item as Record<string, unknown>;
      const title = String(payload.title || "").trim();
      const summary = String(payload.summary || "").trim();
      const recommendedAction = String(payload.recommended_action || "").trim();
      if (!title && !summary && !recommendedAction) {
        return null;
      }
      return {
        proposal_id: String(payload.proposal_id || `structure-${index + 1}`),
        title: title || "记忆结构优化提案",
        summary,
        recommended_action: recommendedAction,
        risk_level: String(payload.risk_level || "medium"),
        status: String(payload.status || "pending"),
      };
    })
    .filter((item): item is MemoryStructureProposal => Boolean(item));
}

function normalizeMemorySlotPreferences(value: unknown): MemorySlotPreference[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item, index) => {
      if (!item || typeof item !== "object" || Array.isArray(item)) {
        return null;
      }
      const payload = item as Record<string, unknown>;
      const slotKey = String(payload.slot_key || "").trim();
      const slotLabel = String(payload.slot_label || "").trim();
      if (!slotKey && !slotLabel) {
        return null;
      }
      return {
        preference_id: String(payload.preference_id || `slot-preference-${index + 1}`),
        industry_instance_id: String(payload.industry_instance_id || "").trim(),
        slot_key: slotKey,
        slot_label: slotLabel,
        promotion_count: Number(payload.promotion_count || 0),
        status: String(payload.status || "active").trim() || "active",
      };
    })
    .filter((item): item is MemorySlotPreference => Boolean(item));
}

function normalizeMemoryContinuityDetails(value: unknown): MemoryContinuityDetail[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item, index) => {
      if (!item || typeof item !== "object" || Array.isArray(item)) {
        return null;
      }
      const payload = item as Record<string, unknown>;
      const detailText = String(payload.detail_text || "").trim();
      const detailKey = String(payload.detail_key || "").trim();
      if (!detailText && !detailKey) {
        return null;
      }
      return {
        detail_id: String(payload.detail_id || `continuity-detail-${index + 1}`),
        scope_type: String(payload.scope_type || "").trim(),
        scope_id: String(payload.scope_id || "").trim(),
        detail_key: detailKey,
        detail_text: detailText,
        detail_label: String(payload.detail_label || "").trim(),
        source_kind: String(payload.source_kind || "model").trim() || "model",
        pinned: Boolean(payload.pinned),
        status: String(payload.status || "active").trim() || "active",
      };
    })
    .filter((item): item is MemoryContinuityDetail => Boolean(item));
}

function normalizeMemorySleepOverlay(value: unknown): MemorySleepOverlay | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const payload = value as Record<string, unknown>;
  const digest = normalizeMemorySleepDigest(payload.digest);
  const industryProfile = normalizeMemoryIndustryProfile(payload.industry_profile);
  const workContextOverlay = normalizeMemoryWorkContextOverlay(payload.work_context_overlay);
  const structureProposals = normalizeMemoryStructureProposals(payload.structure_proposals);
  const softRules = normalizeMemorySleepRules(payload.soft_rules);
  const conflicts = normalizeMemorySleepConflicts(payload.conflicts);
  const slotPreferences = normalizeMemorySlotPreferences(payload.slot_preferences);
  const continuityDetails = normalizeMemoryContinuityDetails(payload.continuity_details);
  if (
    !digest &&
    !industryProfile &&
    !workContextOverlay &&
    structureProposals.length === 0 &&
    softRules.length === 0 &&
    conflicts.length === 0 &&
    slotPreferences.length === 0 &&
    continuityDetails.length === 0
  ) {
    return null;
  }
  return {
    digest,
    industry_profile: industryProfile,
    work_context_overlay: workContextOverlay,
    structure_proposals: structureProposals,
    soft_rules: softRules,
    conflicts,
    slot_preferences: slotPreferences,
    continuity_details: continuityDetails,
  };
}

function normalizeMemorySleepVersionDiff(value: unknown): MemorySleepVersionDiff | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const payload = value as Record<string, unknown>;
  const changes = Array.isArray(payload.changes)
    ? payload.changes
        .map((item) => {
          if (!item || typeof item !== "object" || Array.isArray(item)) {
            return null;
          }
          const change = item as Record<string, unknown>;
          const field = String(change.field || "").trim();
          if (!field) {
            return null;
          }
          return {
            field,
            from: change.from,
            to: change.to,
          };
        })
        .filter((item): item is MemorySleepVersionChange => Boolean(item))
    : [];
  return {
    scope_type: String(payload.scope_type || "").trim(),
    scope_id: String(payload.scope_id || "").trim(),
    from_version: normalizeNumber(payload.from_version) || 0,
    to_version: normalizeNumber(payload.to_version) || 0,
    changes,
  };
}

function stanceColor(stance: string): "default" | "blue" | "gold" | "red" | "green" {
  switch (stance) {
    case "recommendation":
      return "blue";
    case "requirement":
      return "gold";
    case "caution":
      return "red";
    case "preference":
      return "green";
    default:
      return "default";
  }
}

export default function KnowledgePage() {
  const [docForm] = Form.useForm();
  const [memoryForm] = Form.useForm();

  const [strategies, setStrategies] = useState<StrategyItem[]>([]);
  const [documents, setDocuments] = useState<DocItem[]>([]);
  const [chunks, setChunks] = useState<ChunkItem[]>([]);
  const [memoryItems, setMemoryItems] = useState<MemoryItem[]>([]);
  const [agents, setAgents] = useState<AgentProfile[]>([]);
  const [detail, setDetail] = useState<AgentDetail | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [memoryLoading, setMemoryLoading] = useState(false);
  const [memoryBusy, setMemoryBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [memoryScopeType, setMemoryScopeType] = useState<MemoryScopeType>("global");
  const [memoryScopeId, setMemoryScopeId] = useState("runtime");
  const [memoryRole, setMemoryRole] = useState("");
  const [memoryBackend, setMemoryBackend] = useState(
    FORMAL_MEMORY_BACKENDS[0]?.backend_id || "truth-first",
  );
  const [recallQuery, setRecallQuery] = useState("");
  const [createLearningProposals, setCreateLearningProposals] = useState(true);

  const [recallResponse, setRecallResponse] = useState<MemoryRecallResponse | null>(null);
  const [memoryIndex, setMemoryIndex] = useState<MemoryFactIndexEntry[]>([]);
  const [entityViews, setEntityViews] = useState<MemoryEntityView[]>([]);
  const [opinionViews, setOpinionViews] = useState<MemoryOpinionView[]>([]);
  const [memorySurface, setMemorySurface] = useState<MemorySurfacePayload | null>(null);
  const [reflectionRuns, setReflectionRuns] = useState<MemoryReflectionRun[]>([]);
  const [lastRebuildSummary, setLastRebuildSummary] = useState<MemoryRebuildSummary | null>(null);
  const [lastReflectSummary, setLastReflectSummary] = useState<MemoryReflectionSummary | null>(null);
  const [sleepActionBusyKey, setSleepActionBusyKey] = useState<string | null>(null);
  const [industryVersionDiff, setIndustryVersionDiff] = useState<MemorySleepVersionDiff | null>(null);
  const [workContextVersionDiff, setWorkContextVersionDiff] = useState<MemorySleepVersionDiff | null>(null);
  const [manualPinKey, setManualPinKey] = useState("");
  const [manualPinText, setManualPinText] = useState("");
  const detailRequestSeqRef = useRef(0);

  const selectedAgent =
    agents.find((agent) => agent.agent_id === selectedAgentId) ||
    agents.find((agent) => isExecutionCore(agent)) ||
    agents[0] ||
    null;
  const sleepIndustryProfile = memorySurface?.sleep?.industry_profile ?? null;
  const sleepWorkContextOverlay = memorySurface?.sleep?.work_context_overlay ?? null;
  const activeSleepScopeType = (memorySurface?.scope_type || memoryScopeType) as MemoryScopeType;
  const activeSleepScopeId = String(
    memorySurface?.scope_id || buildMemoryScopeSearch(memoryScopeType, memoryScopeId).scopeId || "",
  ).trim();
  const previousIndustryVersion =
    typeof sleepIndustryProfile?.version === "number" && sleepIndustryProfile.version > 1
      ? sleepIndustryProfile.version - 1
      : null;
  const previousWorkContextVersion =
    typeof sleepWorkContextOverlay?.version === "number" && sleepWorkContextOverlay.version > 1
      ? sleepWorkContextOverlay.version - 1
      : null;
  const sleepSlotPreferences = memorySurface?.sleep?.slot_preferences || [];
  const sleepContinuityDetails = memorySurface?.sleep?.continuity_details || [];
  const sleepContinuityAnchors = normalizeTextList(
    sleepWorkContextOverlay?.metadata?.continuity_anchors,
  );
  const sleepIndustryAppliedProposalIds = normalizeTextList(
    sleepIndustryProfile?.metadata?.applied_proposal_ids,
  );
  const sleepOverlayAppliedProposalIds = normalizeTextList(
    sleepWorkContextOverlay?.metadata?.applied_proposal_ids,
  );
  const sleepLastAppliedProposalIds = Array.from(
    new Set(
      normalizeTextList([
        sleepIndustryProfile?.metadata?.last_applied_proposal_id,
        sleepWorkContextOverlay?.metadata?.last_applied_proposal_id,
      ]),
    ),
  );

  const loadPage = useCallback(async () => {
    setLoading(true);
    try {
      setError(null);
      const factParams = query.trim()
        ? `?query=${encodeURIComponent(query.trim())}`
        : "";
      const [
        strategyPayload,
        documentPayload,
        chunkPayload,
        memoryPayload,
        agentPayload,
      ] = await Promise.all([
        request<StrategyItem[]>("/runtime-center/strategy-memory?status=active&limit=20"),
        request<DocItem[]>(`/runtime-center/knowledge/documents${factParams}`),
        request<ChunkItem[]>(`/runtime-center/knowledge${factParams}`),
        request<MemoryItem[]>(`/runtime-center/knowledge/memory${factParams}`),
        request<AgentProfile[]>("/runtime-center/agents?view=business"),
      ]);
      const nextAgents = Array.isArray(agentPayload) ? agentPayload : [];
      setStrategies(Array.isArray(strategyPayload) ? strategyPayload : []);
      setDocuments(Array.isArray(documentPayload) ? documentPayload : []);
      setChunks(Array.isArray(chunkPayload) ? chunkPayload : []);
      setMemoryItems(Array.isArray(memoryPayload) ? memoryPayload : []);
      setAgents(nextAgents);
      setSelectedAgentId((current) =>
        current && nextAgents.some((agent) => agent.agent_id === current)
          ? current
          : nextAgents.find((agent) => isExecutionCore(agent))?.agent_id ||
            nextAgents[0]?.agent_id ||
            null,
      );
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : String(fetchError));
    } finally {
      setLoading(false);
    }
  }, [query]);

  async function loadDetail(agentId: string) {
    const requestSeq = detailRequestSeqRef.current + 1;
    detailRequestSeqRef.current = requestSeq;
    setDetailLoading(true);
    try {
      const payload = await request<AgentDetail>(
        `/runtime-center/agents/${encodeURIComponent(agentId)}`,
      );
      if (detailRequestSeqRef.current !== requestSeq) {
        return;
      }
      setDetail(payload);
    } catch (fetchError) {
      if (detailRequestSeqRef.current !== requestSeq) {
        return;
      }
      setDetail(null);
      setError(fetchError instanceof Error ? fetchError.message : String(fetchError));
    } finally {
      if (detailRequestSeqRef.current === requestSeq) {
        setDetailLoading(false);
      }
    }
  }

  const loadMemoryWorkspace = useCallback(async (options?: { includeRecall?: boolean }) => {
    const { scopeId, search } = buildMemoryScopeSearch(
      memoryScopeType,
      memoryScopeId,
    );
    if (!scopeId) {
      return;
    }
    setMemoryLoading(true);
    try {
      const normalizedRecallQuery = recallQuery.trim();
      const indexSearch = new URLSearchParams(search);
      indexSearch.set("limit", "40");
      const entitySearch = new URLSearchParams(search);
      entitySearch.set("limit", "24");
      const opinionSearch = new URLSearchParams(search);
      opinionSearch.set("limit", "24");
      const reflectionSearch = new URLSearchParams(search);
      reflectionSearch.set("limit", "20");
      const surfaceSearch = new URLSearchParams(search);
      appendSearchParam(surfaceSearch, "query", normalizedRecallQuery || null);
      appendSearchParam(surfaceSearch, "role", memoryRole.trim() || null);
      appendSearchParam(surfaceSearch, "limit", 12);
      appendSearchParam(surfaceSearch, "relation_limit", 12);

      const [
        indexPayload,
        entityPayload,
        opinionPayload,
        reflectionPayload,
        surfacePayload,
      ] = await Promise.all([
        request<MemoryFactIndexEntry[]>(
          `/runtime-center/memory/index?${indexSearch.toString()}`,
        ),
        request<MemoryEntityView[]>(
          `/runtime-center/memory/entities?${entitySearch.toString()}`,
        ),
        request<MemoryOpinionView[]>(
          `/runtime-center/memory/opinions?${opinionSearch.toString()}`,
        ),
        request<MemoryReflectionRun[]>(
          `/runtime-center/memory/reflections?${reflectionSearch.toString()}`,
        ),
        request<MemorySurfacePayload>(
          `/runtime-center/memory/surface?${surfaceSearch.toString()}`,
        ),
      ]);

      setMemoryIndex(Array.isArray(indexPayload) ? indexPayload : []);
      setEntityViews(Array.isArray(entityPayload) ? entityPayload : []);
      setOpinionViews(Array.isArray(opinionPayload) ? opinionPayload : []);
      setReflectionRuns(Array.isArray(reflectionPayload) ? reflectionPayload : []);
      setMemorySurface(
        surfacePayload && !Array.isArray(surfacePayload)
          ? {
              scope_type: String(surfacePayload.scope_type || memoryScopeType),
              scope_id: String(surfacePayload.scope_id || scopeId),
              query: surfacePayload.query || null,
              activation: surfacePayload.activation || null,
              sleep: normalizeMemorySleepOverlay(surfacePayload.sleep),
              relation_count: Number(surfacePayload.relation_count || 0),
              relation_kind_counts:
                surfacePayload.relation_kind_counts &&
                typeof surfacePayload.relation_kind_counts === "object"
                  ? surfacePayload.relation_kind_counts
                  : {},
              relations: Array.isArray(surfacePayload.relations)
                ? surfacePayload.relations
                : [],
            }
          : null,
      );

      if (options?.includeRecall) {
        if (!normalizedRecallQuery) {
          setRecallResponse(null);
        } else {
          const recallSearch = new URLSearchParams(search);
          appendSearchParam(recallSearch, "query", normalizedRecallQuery);
          appendSearchParam(recallSearch, "role", memoryRole.trim() || null);
          appendSearchParam(recallSearch, "backend", memoryBackend || null);
          appendSearchParam(
            recallSearch,
            "include_related_scopes",
            memoryScopeType === "task" ? false : true,
          );
          appendSearchParam(recallSearch, "limit", 8);
          const recallPayload = await request<MemoryRecallResponse>(
            `/runtime-center/memory/recall?${recallSearch.toString()}`,
          );
          setRecallResponse(recallPayload);
        }
      }
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : String(fetchError));
    } finally {
      setMemoryLoading(false);
    }
  }, [memoryBackend, memoryRole, memoryScopeId, memoryScopeType, recallQuery]);

  useEffect(() => {
    let disposed = false;
    void (async () => {
      await loadPage();
      if (disposed) {
        return;
      }
      await loadMemoryWorkspace();
    })();
    return () => {
      disposed = true;
    };
  }, [loadMemoryWorkspace, loadPage]);

  useEffect(() => {
    if (selectedAgent?.agent_id) {
      void loadDetail(selectedAgent.agent_id);
    }
  }, [selectedAgent?.agent_id]);

  const handleImport = async (values: Record<string, string>) => {
    try {
      await request("/runtime-center/knowledge/import", {
        method: "POST",
        body: JSON.stringify({
          title: values.title,
          content: values.content,
          source_ref: values.source_ref || null,
          role_bindings: parseCsv(values.role_bindings || ""),
          tags: parseCsv(values.tags || ""),
        }),
      });
      message.success("已将文档导入核心知识库。");
      docForm.resetFields();
      await loadPage();
    } catch (saveError) {
      message.error(saveError instanceof Error ? saveError.message : String(saveError));
    }
  };

  const handleRemember = async (values: Record<string, string>) => {
    try {
      await request("/runtime-center/knowledge/memory", {
        method: "POST",
        body: JSON.stringify({
          title: values.memory_title,
          content: values.memory_content,
          scope_type: values.scope_type || "agent",
          scope_id: values.scope_id,
          source_ref: values.memory_source_ref || null,
          tags: parseCsv(values.memory_tags || ""),
        }),
      });
      message.success("持久事实已保存至核心记忆。");
      memoryForm.resetFields();
      await loadPage();
      await loadMemoryWorkspace();
    } catch (saveError) {
      message.error(saveError instanceof Error ? saveError.message : String(saveError));
    }
  };

  const handleRefreshMemory = async (includeRecall = false) => {
    await loadMemoryWorkspace({ includeRecall });
  };

  const handleRunRecall = async () => {
    if (!recallQuery.trim()) {
      message.warning("请先输入查询条件。");
      return;
    }
    setMemoryBusy(true);
    try {
      await loadMemoryWorkspace({ includeRecall: true });
    } finally {
      setMemoryBusy(false);
    }
  };

  const handleRebuild = async () => {
    const { scopeId } = buildMemoryScopeSearch(memoryScopeType, memoryScopeId);
    if (!scopeId) {
      message.warning("索引重建需要作用域 ID。");
      return;
    }
    setMemoryBusy(true);
    try {
      const summary = await request<MemoryRebuildSummary>("/runtime-center/memory/rebuild", {
        method: "POST",
        body: JSON.stringify({
          scope_type: memoryScopeType,
          scope_id: scopeId,
          include_reporting: true,
          include_learning: true,
          evidence_limit: 200,
        }),
      });
      setLastRebuildSummary(summary);
      void loadMemoryWorkspace({ includeRecall: Boolean(recallQuery.trim()) });
      message.success("派生记忆索引重建完成。");
    } catch (saveError) {
      message.error(saveError instanceof Error ? saveError.message : String(saveError));
    } finally {
      setMemoryBusy(false);
    }
  };

  const handleReflect = async () => {
    const { scopeId } = buildMemoryScopeSearch(memoryScopeType, memoryScopeId);
    if (!scopeId) {
      message.warning("进行反思需要作用域 ID。");
      return;
    }
    setMemoryBusy(true);
    try {
      const summary = await request<MemoryReflectionSummary>("/runtime-center/memory/reflect", {
        method: "POST",
        body: JSON.stringify({
          scope_type: memoryScopeType,
          scope_id: scopeId,
          owner_agent_id: memoryScopeType === "agent" ? scopeId : null,
          industry_instance_id: memoryScopeType === "industry" ? scopeId : null,
          trigger_kind: "manual",
          create_learning_proposals: createLearningProposals,
        }),
      });
      setLastReflectSummary(summary);
      void loadMemoryWorkspace({ includeRecall: Boolean(recallQuery.trim()) });
      message.success("记忆反思完成。");
    } catch (saveError) {
      message.error(saveError instanceof Error ? saveError.message : String(saveError));
    } finally {
      setMemoryBusy(false);
    }
  };

  const handleSleepRebuild = async () => {
    if (!activeSleepScopeId || !["industry", "work_context"].includes(activeSleepScopeType)) {
      message.warning("睡眠记忆重建只支持行业或工作上下文作用域。");
      return;
    }
    setMemoryBusy(true);
    try {
      await request("/runtime-center/memory/sleep/rebuild", {
        method: "POST",
        body: JSON.stringify({
          scope_type: activeSleepScopeType,
          scope_id: activeSleepScopeId,
          trigger_kind: "rebuild",
        }),
      });
      setIndustryVersionDiff(null);
      setWorkContextVersionDiff(null);
      void loadMemoryWorkspace({ includeRecall: Boolean(recallQuery.trim()) });
      message.success("睡眠记忆重建完成。");
    } catch (saveError) {
      message.error(saveError instanceof Error ? saveError.message : String(saveError));
    } finally {
      setMemoryBusy(false);
    }
  };

  const handleStructureProposalDecision = async (
    proposalId: string,
    action: "apply" | "reject",
  ) => {
    const normalizedProposalId = proposalId.trim();
    if (!normalizedProposalId) {
      return;
    }
    const busyKey = `${action}:${normalizedProposalId}`;
    setSleepActionBusyKey(busyKey);
    try {
      await request(
        `/runtime-center/memory/sleep/structure-proposals/${encodeURIComponent(normalizedProposalId)}/${action}`,
        {
          method: "POST",
          body: JSON.stringify({
            actor: "knowledge-page",
            note:
              action === "apply"
                ? "前台确认采用该结构提案。"
                : "前台明确驳回该结构提案。",
          }),
        },
      );
      void loadMemoryWorkspace({ includeRecall: Boolean(recallQuery.trim()) });
      message.success(action === "apply" ? "结构提案已应用。" : "结构提案已驳回。");
    } catch (saveError) {
      message.error(saveError instanceof Error ? saveError.message : String(saveError));
    } finally {
      setSleepActionBusyKey(null);
    }
  };

  const handleIndustryVersionDiff = async () => {
    if (!sleepIndustryProfile?.industry_instance_id || previousIndustryVersion === null) {
      return;
    }
    setSleepActionBusyKey("industry-diff");
    try {
      const payload = await request<MemorySleepVersionDiff>(
        `/runtime-center/memory/sleep/industry-profiles/${encodeURIComponent(
          sleepIndustryProfile.industry_instance_id,
        )}/diff?from_version=${previousIndustryVersion}&to_version=${sleepIndustryProfile.version}`,
      );
      setIndustryVersionDiff(normalizeMemorySleepVersionDiff(payload));
    } catch (saveError) {
      message.error(saveError instanceof Error ? saveError.message : String(saveError));
    } finally {
      setSleepActionBusyKey(null);
    }
  };

  const handleIndustryRollback = async () => {
    if (!sleepIndustryProfile?.industry_instance_id || previousIndustryVersion === null) {
      return;
    }
    setSleepActionBusyKey("industry-rollback");
    try {
      await request(
        `/runtime-center/memory/sleep/industry-profiles/${encodeURIComponent(
          sleepIndustryProfile.industry_instance_id,
        )}/rollback`,
        {
          method: "POST",
          body: JSON.stringify({
            version: previousIndustryVersion,
            actor: "knowledge-page",
          }),
        },
      );
      setIndustryVersionDiff(null);
      void loadMemoryWorkspace({ includeRecall: Boolean(recallQuery.trim()) });
      message.success(`行业记忆已回滚到 v${previousIndustryVersion}。`);
    } catch (saveError) {
      message.error(saveError instanceof Error ? saveError.message : String(saveError));
    } finally {
      setSleepActionBusyKey(null);
    }
  };

  const handleWorkContextVersionDiff = async () => {
    if (!sleepWorkContextOverlay?.work_context_id || previousWorkContextVersion === null) {
      return;
    }
    setSleepActionBusyKey("work-context-diff");
    try {
      const payload = await request<MemorySleepVersionDiff>(
        `/runtime-center/memory/sleep/work-context-overlays/${encodeURIComponent(
          sleepWorkContextOverlay.work_context_id,
        )}/diff?from_version=${previousWorkContextVersion}&to_version=${sleepWorkContextOverlay.version}`,
      );
      setWorkContextVersionDiff(normalizeMemorySleepVersionDiff(payload));
    } catch (saveError) {
      message.error(saveError instanceof Error ? saveError.message : String(saveError));
    } finally {
      setSleepActionBusyKey(null);
    }
  };

  const handleWorkContextRollback = async () => {
    if (!sleepWorkContextOverlay?.work_context_id || previousWorkContextVersion === null) {
      return;
    }
    setSleepActionBusyKey("work-context-rollback");
    try {
      await request(
        `/runtime-center/memory/sleep/work-context-overlays/${encodeURIComponent(
          sleepWorkContextOverlay.work_context_id,
        )}/rollback`,
        {
          method: "POST",
          body: JSON.stringify({
            version: previousWorkContextVersion,
            actor: "knowledge-page",
          }),
        },
      );
      setWorkContextVersionDiff(null);
      await loadMemoryWorkspace({ includeRecall: Boolean(recallQuery.trim()) });
      message.success(`工作记忆已回滚到 v${previousWorkContextVersion}。`);
    } catch (saveError) {
      message.error(saveError instanceof Error ? saveError.message : String(saveError));
    } finally {
      setSleepActionBusyKey(null);
    }
  };

  const handleManualPinSubmit = async () => {
    const normalizedScopeType =
      activeSleepScopeType === "industry" || activeSleepScopeType === "work_context"
        ? activeSleepScopeType
        : null;
    if (!normalizedScopeType || !activeSleepScopeId) {
      message.warning("当前记忆读面还没有可钉住的正式范围。");
      return;
    }
    if (!manualPinKey.trim() || !manualPinText.trim()) {
      message.warning("请先填写细节标识和细节内容。");
      return;
    }
    setSleepActionBusyKey("manual-pin");
    try {
      await request("/runtime-center/memory/continuity-details/pin", {
        method: "POST",
        body: JSON.stringify({
          scope_type: normalizedScopeType,
          scope_id: activeSleepScopeId,
          detail_key: manualPinKey.trim(),
          detail_text: manualPinText.trim(),
          industry_instance_id:
            sleepWorkContextOverlay?.industry_instance_id ||
            sleepIndustryProfile?.industry_instance_id ||
            (normalizedScopeType === "industry" ? activeSleepScopeId : null),
          work_context_id:
            normalizedScopeType === "work_context"
              ? activeSleepScopeId
              : sleepWorkContextOverlay?.work_context_id || null,
        }),
      });
      setManualPinKey("");
      setManualPinText("");
      await loadMemoryWorkspace({ includeRecall: Boolean(recallQuery.trim()) });
      message.success("手动钉住已写入正式记忆。");
    } catch (saveError) {
      message.error(saveError instanceof Error ? saveError.message : String(saveError));
    } finally {
      setSleepActionBusyKey(null);
    }
  };

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Card className="baize-card">
        <Space style={{ width: "100%", justifyContent: "space-between" }}>
          <div>
            <Title level={3} style={{ margin: 0 }}>
              记忆控制台
            </Title>
            <Paragraph type="secondary" style={{ margin: "8px 0 0" }}>
              战略记忆、系统事实、派生召回、反思视图与执行上下文，现已统一至该操作台。
            </Paragraph>
          </div>
          <Space>
            <Input
              placeholder="搜索核心事实"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              style={{ width: 240 }}
            />
            <Button icon={<ReloadOutlined />} onClick={() => void loadPage()}>
              刷新记忆
            </Button>
          </Space>
        </Space>
      </Card>

      {error ? <Alert type="error" showIcon message={error} /> : null}

      <Tabs
        items={[
          {
            key: "strategy",
            label: (
              <span>
                <DeploymentUnitOutlined /> 战略记忆
              </span>
            ),
            children: loading ? (
              <Spin />
            ) : (
              <List
                locale={{ emptyText: <Empty description="暂无活跃战略记忆。" /> }}
                dataSource={strategies}
                renderItem={(item) => (
                  <List.Item key={item.strategy_id}>
                    <Card className="baize-card" style={{ width: "100%" }}>
                      <Space direction="vertical" size={10} style={{ width: "100%" }}>
                        <Space wrap>
                          <Text strong>{item.title}</Text>
                          <Tag color="blue">
                            {item.scope_type === "industry" ? "industry" : "global"}
                          </Tag>
                          <Tag>{item.status}</Tag>
                        </Space>
                        <Paragraph style={{ marginBottom: 0 }}>
                          {item.summary || "暂无战略摘要。"}
                        </Paragraph>
                        {item.mission ? (
                          <Text>使命: {normalizeSpiderMeshBrand(item.mission)}</Text>
                        ) : null}
                        {item.north_star ? (
                          <Text>北极星指标: {item.north_star}</Text>
                        ) : null}
                        {item.thinking_axes.length > 0 ? (
                          <Text>思考轴线: {item.thinking_axes.join(" / ")}</Text>
                        ) : null}
                        {item.delegation_policy.length > 0 ? (
                          <Text>
                            委派策略: {item.delegation_policy.join(" | ")}
                          </Text>
                        ) : null}
                        {item.evidence_requirements.length > 0 ? (
                          <Text>
                            证据预期:{" "}
                            {item.evidence_requirements.join(" | ")}
                          </Text>
                        ) : null}
                      </Space>
                    </Card>
                  </List.Item>
                )}
              />
            ),
          },
          {
            key: "facts",
            label: (
              <span>
                <DatabaseOutlined /> 事实仓库
              </span>
            ),
            children: (
              <Space direction="vertical" size={16} style={{ width: "100%" }}>
                <Card className="baize-card" title="导入核心知识">
                  <Form
                    form={docForm}
                    layout="vertical"
                    onFinish={(values) =>
                      void handleImport(values as Record<string, string>)
                    }
                  >
                    <Form.Item
                      name="title"
                      label="标题"
                      rules={[{ required: true, message: "标题不能为空。" }]}
                    >
                      <Input />
                    </Form.Item>
                    <Form.Item name="source_ref" label="来源引用">
                      <Input />
                    </Form.Item>
                    <Form.Item name="role_bindings" label="绑定角色">
                      <Input placeholder="以逗号分隔" />
                    </Form.Item>
                    <Form.Item name="tags" label="标签">
                      <Input placeholder="以逗号分隔" />
                    </Form.Item>
                    <Form.Item
                      name="content"
                      label="内容"
                      rules={[{ required: true, message: "内容不能为空。" }]}
                    >
                      <TextArea rows={6} />
                    </Form.Item>
                    <Button type="primary" htmlType="submit">
                      导入文档
                    </Button>
                  </Form>
                </Card>

                <Card className="baize-card" title="写入持久事实">
                  <Form
                    form={memoryForm}
                    layout="vertical"
                    onFinish={(values) =>
                      void handleRemember(values as Record<string, string>)
                    }
                  >
                    <Form.Item name="scope_type" label="作用域类型" initialValue="agent">
                      <Select
                        options={MEMORY_SCOPE_OPTIONS}
                      />
                    </Form.Item>
                    <Form.Item
                      name="scope_id"
                      label="作用域 ID"
                      rules={[{ required: true, message: "作用域 ID 不能为空。" }]}
                    >
                      <Input />
                    </Form.Item>
                    <Form.Item
                      name="memory_title"
                      label="标题"
                      rules={[{ required: true, message: "标题不能为空。" }]}
                    >
                      <Input />
                    </Form.Item>
                    <Form.Item name="memory_source_ref" label="来源引用">
                      <Input />
                    </Form.Item>
                    <Form.Item name="memory_tags" label="标签">
                      <Input placeholder="以逗号分隔" />
                    </Form.Item>
                    <Form.Item
                      name="memory_content"
                      label="事实内容"
                      rules={[{ required: true, message: "事实内容不能为空。" }]}
                    >
                      <TextArea rows={4} />
                    </Form.Item>
                    <Button type="primary" htmlType="submit">
                      保存持久事实
                    </Button>
                  </Form>
                </Card>

                <Card className="baize-card" title={`文档库 ${documents.length}`}>
                  <List
                    locale={{ emptyText: <Empty description="暂无文档。" /> }}
                    dataSource={documents}
                    renderItem={(item) => (
                      <List.Item key={item.document_id}>
                        <Space direction="vertical" size={4} style={{ width: "100%" }}>
                          <Space wrap>
                            <Text strong>{item.title}</Text>
                            <Tag>{item.document_id}</Tag>
                            <Tag color="blue">{item.chunk_count} 个切片</Tag>
                          </Space>
                          {item.tags.length > 0 ? (
                            <Space wrap>
                              {item.tags.slice(0, 6).map((tag) => (
                                <Tag key={tag}>{tag}</Tag>
                              ))}
                            </Space>
                          ) : null}
                        </Space>
                      </List.Item>
                    )}
                  />
                </Card>

                <Card className="baize-card" title={`知识切片 ${chunks.length}`}>
                  <List
                    locale={{ emptyText: <Empty description="暂无切片。" /> }}
                    dataSource={chunks.slice(0, 12)}
                    renderItem={(item) => (
                      <List.Item key={item.id}>
                        <Space direction="vertical" size={4} style={{ width: "100%" }}>
                          <Space wrap>
                            <Text strong>{item.title}</Text>
                            <Tag>{item.document_id}</Tag>
                          </Space>
                          <Paragraph style={{ marginBottom: 0 }}>
                            {compactText(item.content, 220)}
                          </Paragraph>
                        </Space>
                      </List.Item>
                    )}
                  />
                </Card>

                <Card className="baize-card" title={`持久事实 ${memoryItems.length}`}>
                  <List
                    locale={{ emptyText: <Empty description="暂无持久事实。" /> }}
                    dataSource={memoryItems.slice(0, 12)}
                    renderItem={(item) => (
                      <List.Item key={item.id}>
                        <Space direction="vertical" size={4} style={{ width: "100%" }}>
                          <Space wrap>
                            <Text strong>{item.title}</Text>
                            <Tag>{formatScope(item.scope_type, item.scope_id)}</Tag>
                          </Space>
                          <Paragraph style={{ marginBottom: 0 }}>
                            {compactText(item.summary, 220)}
                          </Paragraph>
                          {item.tags.length > 0 ? (
                            <Space wrap>
                              {item.tags.slice(0, 6).map((tag) => (
                                <Tag key={tag}>{tag}</Tag>
                              ))}
                            </Space>
                          ) : null}
                        </Space>
                      </List.Item>
                    )}
                  />
                </Card>
              </Space>
            ),
          },
          {
            key: "memory",
            label: (
              <span>
                <SearchOutlined /> 检索与反思
              </span>
            ),
            children: (
              <Space direction="vertical" size={16} style={{ width: "100%" }}>
                <Card className="baize-card" title="派生记忆工作台">
                  <Space direction="vertical" size={12} style={{ width: "100%" }}>
                    <Space wrap>
                      <Select<MemoryScopeType>
                        value={memoryScopeType}
                        onChange={setMemoryScopeType}
                        style={{ width: 140 }}
                        options={MEMORY_SCOPE_OPTIONS}
                      />
                      <Input
                        value={memoryScopeId}
                        onChange={(event) => setMemoryScopeId(event.target.value)}
                        placeholder="填入作用域 ID"
                        style={{ width: 220 }}
                      />
                      <Input
                        value={memoryRole}
                        onChange={(event) => setMemoryRole(event.target.value)}
                        placeholder="角色过滤"
                        style={{ width: 180 }}
                      />
                      <Select
                        value={memoryBackend || undefined}
                        onChange={(value) => setMemoryBackend(value)}
                        style={{ width: 220 }}
                        placeholder="召回引擎"
                        options={FORMAL_MEMORY_BACKENDS.map((backend) => ({
                          label: backend.label,
                          value: backend.backend_id,
                          disabled: !backend.available,
                        }))}
                      />
                    </Space>
                    <Space wrap>
                      <Input
                        value={recallQuery}
                        onChange={(event) => setRecallQuery(event.target.value)}
                        placeholder="输入查询进行记忆召回"
                        style={{ width: 420 }}
                      />
                      <Button
                        icon={<ReloadOutlined />}
                        onClick={() => void handleRefreshMemory(Boolean(recallQuery.trim()))}
                      >
                        加载作用域
                      </Button>
                      <Button
                        type="primary"
                        icon={<SearchOutlined />}
                        loading={memoryBusy}
                        onClick={() => void handleRunRecall()}
                      >
                        召回检索
                      </Button>
                      <Button loading={memoryBusy} onClick={() => void handleRebuild()}>
                        重建索引
                      </Button>
                      <Button loading={memoryBusy} onClick={() => void handleReflect()}>
                        反思总结
                      </Button>
                      <Space>
                        <Text type="secondary">生成学习提案</Text>
                        <Switch
                          checked={createLearningProposals}
                          onChange={setCreateLearningProposals}
                        />
                      </Space>
                    </Space>
                  </Space>
                </Card>

                <Card className="baize-card" title="记忆统计摘要">
                  <Descriptions bordered size="small" column={2}>
                    <Descriptions.Item label="当前作用域">
                      {formatScope(memoryScopeType, memoryScopeId)}
                    </Descriptions.Item>
                    <Descriptions.Item label="召回使用引擎">
                      {recallResponse?.backend_used || memoryBackend || "n/a"}
                    </Descriptions.Item>
                    <Descriptions.Item label="事实索引数">
                      {memoryIndex.length}
                    </Descriptions.Item>
                    <Descriptions.Item label="实体对象数">
                      {entityViews.length}
                    </Descriptions.Item>
                    <Descriptions.Item label="主观观点数">
                      {opinionViews.length}
                    </Descriptions.Item>
                    <Descriptions.Item label="反思执行次数">
                      {reflectionRuns.length}
                    </Descriptions.Item>
                    <Descriptions.Item label="最近一次重建">
                      {lastRebuildSummary
                        ? `${lastRebuildSummary.fact_index_count} entries at ${formatDateTime(
                            lastRebuildSummary.completed_at,
                          )}`
                        : "n/a"}
                    </Descriptions.Item>
                    <Descriptions.Item label="最近一次反思">
                      {lastReflectSummary
                        ? `${lastReflectSummary.entity_count} entities / ${lastReflectSummary.opinion_count} opinions`
                        : "n/a"}
                    </Descriptions.Item>
                  </Descriptions>
                </Card>

                <Card className="baize-card" title="可用召回引擎">
                  <Space wrap>
                    {FORMAL_MEMORY_BACKENDS.length === 0 ? (
                      <Empty description="尚未接入任何引擎。" />
                    ) : (
                      FORMAL_MEMORY_BACKENDS.map((backend) => (
                        <Tag
                          key={backend.backend_id}
                          color={backend.available ? "blue" : "default"}
                        >
                          {backend.label}
                          {backend.is_default ? " / default" : ""}
                          {!backend.available && backend.reason
                            ? ` / ${backend.reason}`
                            : ""}
                        </Tag>
                      ))
                    )}
                  </Space>
                </Card>

                {memoryLoading ? (
                  <Spin />
                ) : (
                  <>
                    <Card
                      className="baize-card"
                      title={`记忆整理 (${memorySurface?.sleep?.soft_rules.length ?? 0} 条规则 / ${memorySurface?.sleep?.structure_proposals.length ?? 0} 个结构提案 / ${memorySurface?.sleep?.conflicts.length ?? 0} 个待处理)`}
                      data-testid="memory-sleep-surface"
                      extra={
                        memorySurface?.sleep &&
                        activeSleepScopeId &&
                        ["industry", "work_context"].includes(activeSleepScopeType) ? (
                          <Button loading={memoryBusy} onClick={() => void handleSleepRebuild()}>
                            重建睡眠记忆
                          </Button>
                        ) : null
                      }
                    >
                      {memorySurface?.sleep ? (
                        <Space direction="vertical" size={12} style={{ width: "100%" }}>
                          <Descriptions bordered size="small" column={2}>
                            <Descriptions.Item label="当前作用域">
                              {formatScope(
                                memorySurface.scope_type || memoryScopeType,
                                memorySurface.scope_id || memoryScopeId,
                              )}
                            </Descriptions.Item>
                            <Descriptions.Item label="整理摘要">
                              {memorySurface.sleep.digest?.headline || "n/a"}
                            </Descriptions.Item>
                            <Descriptions.Item label="规则数量">
                              {memorySurface.sleep.soft_rules.length}
                            </Descriptions.Item>
                            <Descriptions.Item label="结构提案">
                              {memorySurface.sleep.structure_proposals.length}
                            </Descriptions.Item>
                            <Descriptions.Item label="待处理冲突">
                              {memorySurface.sleep.conflicts.length}
                            </Descriptions.Item>
                            <Descriptions.Item label="长期偏好">
                              {memorySurface.sleep.slot_preferences.length}
                            </Descriptions.Item>
                            <Descriptions.Item label="强记细节">
                              {memorySurface.sleep.continuity_details.length}
                            </Descriptions.Item>
                          </Descriptions>

                          {memorySurface.sleep.digest ? (
                            <Space direction="vertical" size={8} style={{ width: "100%" }}>
                              <div>
                                <Text strong>{memorySurface.sleep.digest.headline}</Text>
                              </div>
                              {memorySurface.sleep.digest.summary ? (
                                <Paragraph style={{ marginBottom: 0 }}>
                                  {compactText(memorySurface.sleep.digest.summary, 280)}
                                </Paragraph>
                              ) : null}
                              <Space wrap>
                                {memorySurface.sleep.digest.current_constraints
                                  .slice(0, 4)
                                  .map((constraint) => (
                                    <Tag key={constraint} color="gold">
                                      {constraint}
                                    </Tag>
                                  ))}
                                {memorySurface.sleep.digest.current_focus
                                  .slice(0, 4)
                                  .map((focus) => (
                                    <Tag key={focus} color="blue">
                                      {focus}
                                    </Tag>
                                  ))}
                                {memorySurface.sleep.digest.evidence_refs
                                  .slice(0, 3)
                                  .map((ref) => (
                                    <Tag key={ref} color="green">
                                      {ref}
                                    </Tag>
                                  ))}
                              </Space>
                            </Space>
                          ) : null}

                          {memorySurface.sleep.industry_profile ? (
                            <Space direction="vertical" size={8} style={{ width: "100%" }}>
                              <Space wrap>
                                <Text strong>{memorySurface.sleep.industry_profile.headline}</Text>
                                {typeof memorySurface.sleep.industry_profile.version === "number" ? (
                                  <Tag color="green">{`v${memorySurface.sleep.industry_profile.version}`}</Tag>
                                ) : null}
                                {memorySurface.sleep.industry_profile.status ? (
                                  <Tag>{memorySurface.sleep.industry_profile.status}</Tag>
                                ) : null}
                              </Space>
                              {memorySurface.sleep.industry_profile.summary ? (
                                <Paragraph style={{ marginBottom: 0 }}>
                                  {compactText(memorySurface.sleep.industry_profile.summary, 280)}
                                </Paragraph>
                              ) : null}
                              {memorySurface.sleep.industry_profile.strategic_direction ? (
                                <Text type="secondary">
                                  长期方向:{" "}
                                  {compactText(
                                    memorySurface.sleep.industry_profile.strategic_direction,
                                    180,
                                  )}
                                </Text>
                              ) : null}
                              <Space wrap>
                                {memorySurface.sleep.industry_profile.active_constraints
                                  .slice(0, 4)
                                  .map((constraint) => (
                                    <Tag key={constraint} color="gold">
                                      {constraint}
                                    </Tag>
                                  ))}
                                {memorySurface.sleep.industry_profile.active_focuses
                                  .slice(0, 4)
                                  .map((focus) => (
                                    <Tag key={focus} color="blue">
                                      {focus}
                                    </Tag>
                                  ))}
                                {previousIndustryVersion !== null ? (
                                  <Button
                                    size="small"
                                    loading={sleepActionBusyKey === "industry-diff"}
                                    onClick={() => void handleIndustryVersionDiff()}
                                  >
                                    查看行业差异
                                  </Button>
                                ) : null}
                                {previousIndustryVersion !== null ? (
                                  <Button
                                    size="small"
                                    loading={sleepActionBusyKey === "industry-rollback"}
                                    onClick={() => void handleIndustryRollback()}
                                  >
                                    回滚行业版本
                                  </Button>
                                ) : null}
                              </Space>
                              {sleepIndustryAppliedProposalIds.length > 0 ||
                              sleepLastAppliedProposalIds.length > 0 ? (
                                <Space direction="vertical" size={4} style={{ width: "100%" }}>
                                  <Text type="secondary">已应用提案</Text>
                                  <Space wrap>
                                    {sleepIndustryAppliedProposalIds.map((proposalId) => (
                                      <Tag key={`industry-applied-${proposalId}`} color="green">
                                        {proposalId}
                                      </Tag>
                                    ))}
                                    {sleepLastAppliedProposalIds
                                      .filter(
                                        (proposalId) =>
                                          !sleepIndustryAppliedProposalIds.includes(proposalId),
                                      )
                                      .map((proposalId) => (
                                        <Tag key={`industry-latest-${proposalId}`} color="green">
                                          {proposalId}
                                        </Tag>
                                      ))}
                                  </Space>
                                </Space>
                              ) : null}
                              {sleepSlotPreferences.length > 0 ? (
                                <Space direction="vertical" size={4} style={{ width: "100%" }}>
                                  <Text type="secondary">行业长期偏好</Text>
                                  <Space wrap>
                                    {sleepSlotPreferences.map((item) => (
                                      <Tag key={item.preference_id} color="blue">
                                        {item.slot_label || item.slot_key}
                                      </Tag>
                                    ))}
                                  </Space>
                                </Space>
                              ) : null}
                              {industryVersionDiff ? (
                                <Space direction="vertical" size={6} style={{ width: "100%" }}>
                                  <Text type="secondary">
                                    {`行业版本差异 v${industryVersionDiff.from_version} -> v${industryVersionDiff.to_version}`}
                                  </Text>
                                  {industryVersionDiff.changes.length > 0 ? (
                                    <List
                                      size="small"
                                      dataSource={industryVersionDiff.changes}
                                      renderItem={(change) => (
                                        <List.Item
                                          key={`${change.field}-${describeMemoryDiffValue(change.to)}`}
                                        >
                                          <Space
                                            direction="vertical"
                                            size={2}
                                            style={{ width: "100%" }}
                                          >
                                            <Text strong>{change.field}</Text>
                                            <Text type="secondary">
                                              {`旧值: ${compactText(
                                                describeMemoryDiffValue(change.from),
                                                200,
                                              )}`}
                                            </Text>
                                            <Text type="secondary">
                                              {`新值: ${compactText(
                                                describeMemoryDiffValue(change.to),
                                                200,
                                              )}`}
                                            </Text>
                                          </Space>
                                        </List.Item>
                                      )}
                                    />
                                  ) : (
                                    <Text type="secondary">当前行业版本没有字段变化。</Text>
                                  )}
                                </Space>
                              ) : null}
                            </Space>
                          ) : null}

                          {memorySurface.sleep.work_context_overlay ? (
                            <Space direction="vertical" size={8} style={{ width: "100%" }}>
                              <Space wrap>
                                <Text strong>{memorySurface.sleep.work_context_overlay.headline}</Text>
                                {typeof memorySurface.sleep.work_context_overlay.version === "number" ? (
                                  <Tag color="green">{`v${memorySurface.sleep.work_context_overlay.version}`}</Tag>
                                ) : null}
                                {memorySurface.sleep.work_context_overlay.status ? (
                                  <Tag>{memorySurface.sleep.work_context_overlay.status}</Tag>
                                ) : null}
                              </Space>
                              {memorySurface.sleep.work_context_overlay.focus_summary ? (
                                <Paragraph style={{ marginBottom: 0 }}>
                                  {compactText(
                                    memorySurface.sleep.work_context_overlay.focus_summary,
                                    240,
                                  )}
                                </Paragraph>
                              ) : null}
                              {memorySurface.sleep.work_context_overlay.summary ? (
                                <Text type="secondary">
                                  {compactText(memorySurface.sleep.work_context_overlay.summary, 220)}
                                </Text>
                              ) : null}
                              <Space wrap>
                                {memorySurface.sleep.work_context_overlay.active_constraints
                                  .slice(0, 4)
                                  .map((constraint) => (
                                    <Tag key={constraint} color="gold">
                                      {constraint}
                                    </Tag>
                                  ))}
                                {memorySurface.sleep.work_context_overlay.active_focuses
                                  .slice(0, 4)
                                  .map((focus) => (
                                    <Tag key={focus} color="blue">
                                      {focus}
                                    </Tag>
                                  ))}
                                {previousWorkContextVersion !== null ? (
                                  <Button
                                    size="small"
                                    loading={sleepActionBusyKey === "work-context-diff"}
                                    onClick={() => void handleWorkContextVersionDiff()}
                                  >
                                    查看上下文差异
                                  </Button>
                                ) : null}
                                {previousWorkContextVersion !== null ? (
                                  <Button
                                    size="small"
                                    loading={sleepActionBusyKey === "work-context-rollback"}
                                    onClick={() => void handleWorkContextRollback()}
                                  >
                                    回滚上下文版本
                                  </Button>
                                ) : null}
                              </Space>
                              {sleepOverlayAppliedProposalIds.length > 0 ||
                              sleepLastAppliedProposalIds.length > 0 ? (
                                <Space direction="vertical" size={4} style={{ width: "100%" }}>
                                  <Text type="secondary">当前已应用提案</Text>
                                  <Space wrap>
                                    {sleepOverlayAppliedProposalIds.map((proposalId) => (
                                      <Tag key={`overlay-applied-${proposalId}`} color="green">
                                        {proposalId}
                                      </Tag>
                                    ))}
                                    {sleepLastAppliedProposalIds
                                      .filter(
                                        (proposalId) =>
                                          !sleepOverlayAppliedProposalIds.includes(proposalId),
                                      )
                                      .map((proposalId) => (
                                        <Tag key={`overlay-latest-${proposalId}`} color="green">
                                          {proposalId}
                                        </Tag>
                                      ))}
                                  </Space>
                                </Space>
                              ) : null}
                              {sleepContinuityAnchors.length > 0 ? (
                                <Space direction="vertical" size={4} style={{ width: "100%" }}>
                                  <Text type="secondary">连续性锚点</Text>
                                  <List
                                    size="small"
                                    dataSource={sleepContinuityAnchors}
                                    renderItem={(item) => <List.Item>{item}</List.Item>}
                                  />
                                </Space>
                              ) : null}
                              {activeSleepScopeType === "industry" ||
                              activeSleepScopeType === "work_context" ? (
                                <Space direction="vertical" size={8} style={{ width: "100%" }}>
                                  <Text type="secondary">手动钉住</Text>
                                  <Input
                                    aria-label="manual-pin-key"
                                    placeholder="细节标识，如 risk-boundary"
                                    value={manualPinKey}
                                    onChange={(event) => setManualPinKey(event.target.value)}
                                  />
                                  <TextArea
                                    aria-label="manual-pin-text"
                                    placeholder="写下必须长期记住的细节"
                                    value={manualPinText}
                                    onChange={(event) => setManualPinText(event.target.value)}
                                    autoSize={{ minRows: 2, maxRows: 4 }}
                                  />
                                  <Space>
                                    <Button
                                      type="primary"
                                      loading={sleepActionBusyKey === "manual-pin"}
                                      onClick={() => void handleManualPinSubmit()}
                                    >
                                      保存手动钉住
                                    </Button>
                                  </Space>
                                </Space>
                              ) : null}
                              {sleepContinuityDetails.length > 0 ? (
                                <Space direction="vertical" size={4} style={{ width: "100%" }}>
                                  <Text type="secondary">强记细节</Text>
                                  <List
                                    size="small"
                                    dataSource={sleepContinuityDetails}
                                    renderItem={(item) => (
                                      <List.Item key={item.detail_id}>
                                        <Space direction="vertical" size={2} style={{ width: "100%" }}>
                                          <Space wrap>
                                            <Tag color={item.pinned ? "gold" : "default"}>
                                              {item.pinned ? "已钉住" : item.source_kind}
                                            </Tag>
                                            {item.detail_label ? <Tag>{item.detail_label}</Tag> : null}
                                          </Space>
                                          <Text>{item.detail_text}</Text>
                                        </Space>
                                      </List.Item>
                                    )}
                                  />
                                </Space>
                              ) : null}
                              {workContextVersionDiff ? (
                                <Space direction="vertical" size={6} style={{ width: "100%" }}>
                                  <Text type="secondary">
                                    {`上下文版本差异 v${workContextVersionDiff.from_version} -> v${workContextVersionDiff.to_version}`}
                                  </Text>
                                  {workContextVersionDiff.changes.length > 0 ? (
                                    <List
                                      size="small"
                                      dataSource={workContextVersionDiff.changes}
                                      renderItem={(change) => (
                                        <List.Item
                                          key={`${change.field}-${describeMemoryDiffValue(change.to)}`}
                                        >
                                          <Space
                                            direction="vertical"
                                            size={2}
                                            style={{ width: "100%" }}
                                          >
                                            <Text strong>{change.field}</Text>
                                            <Text type="secondary">
                                              {`旧值: ${compactText(
                                                describeMemoryDiffValue(change.from),
                                                200,
                                              )}`}
                                            </Text>
                                            <Text type="secondary">
                                              {`新值: ${compactText(
                                                describeMemoryDiffValue(change.to),
                                                200,
                                              )}`}
                                            </Text>
                                          </Space>
                                        </List.Item>
                                      )}
                                    />
                                  ) : (
                                    <Text type="secondary">当前上下文版本没有字段变化。</Text>
                                  )}
                                </Space>
                              ) : null}
                            </Space>
                          ) : null}

                          {memorySurface.sleep.soft_rules.length > 0 ? (
                            <List
                              header={<Text strong>整理后规则</Text>}
                              dataSource={memorySurface.sleep.soft_rules}
                              renderItem={(item) => (
                                <List.Item key={item.rule_id}>
                                  <Space direction="vertical" size={6} style={{ width: "100%" }}>
                                    <Space wrap>
                                      <Tag color="gold">{item.rule_kind}</Tag>
                                      <Tag>{item.state}</Tag>
                                      <Tag>{`风险 ${item.risk_level}`}</Tag>
                                      <Tag>{`命中 ${item.hit_count}`}</Tag>
                                    </Space>
                                    <Paragraph style={{ marginBottom: 0 }}>
                                      {compactText(item.rule_text, 240)}
                                    </Paragraph>
                                  </Space>
                                </List.Item>
                              )}
                            />
                              ) : null}

                          {memorySurface.sleep.conflicts.length > 0 ? (
                            <List
                              header={<Text strong>待处理冲突</Text>}
                              dataSource={memorySurface.sleep.conflicts}
                              renderItem={(item) => (
                                <List.Item key={item.proposal_id}>
                                  <Space direction="vertical" size={6} style={{ width: "100%" }}>
                                    <Space wrap>
                                      <Text strong>{item.title}</Text>
                                      <Tag color="red">{item.status}</Tag>
                                      <Tag>{`风险 ${item.risk_level}`}</Tag>
                                    </Space>
                                    {item.summary ? (
                                      <Paragraph style={{ marginBottom: 0 }}>
                                        {compactText(item.summary, 240)}
                                      </Paragraph>
                                    ) : null}
                                    {item.recommended_action ? (
                                      <Text type="secondary">
                                        {`建议处理: ${compactText(item.recommended_action, 160)}`}
                                      </Text>
                                    ) : null}
                                  </Space>
                                </List.Item>
                              )}
                            />
                          ) : null}

                          {memorySurface.sleep.structure_proposals.length > 0 ? (
                            <List
                              header={<Text strong>结构优化提案</Text>}
                              dataSource={memorySurface.sleep.structure_proposals}
                              renderItem={(item) => (
                                <List.Item key={item.proposal_id}>
                                  <Space direction="vertical" size={6} style={{ width: "100%" }}>
                                    <Space wrap>
                                      <Text strong>{item.title}</Text>
                                      <Tag
                                        color={
                                          item.status === "accepted"
                                            ? "green"
                                            : item.status === "rejected"
                                              ? "red"
                                              : "blue"
                                        }
                                      >
                                        {item.status}
                                      </Tag>
                                      <Tag>{item.proposal_id}</Tag>
                                      <Tag>{`风险 ${item.risk_level}`}</Tag>
                                    </Space>
                                    {item.summary ? (
                                      <Paragraph style={{ marginBottom: 0 }}>
                                        {compactText(item.summary, 220)}
                                      </Paragraph>
                                    ) : null}
                                    {item.status === "pending" ? (
                                      <Space wrap>
                                        <Button
                                          type="link"
                                          loading={
                                            sleepActionBusyKey === `apply:${item.proposal_id}`
                                          }
                                          onClick={() =>
                                            void handleStructureProposalDecision(
                                              item.proposal_id,
                                              "apply",
                                            )
                                          }
                                        >
                                          应用提案
                                        </Button>
                                        <Button
                                          type="link"
                                          danger
                                          loading={
                                            sleepActionBusyKey === `reject:${item.proposal_id}`
                                          }
                                          onClick={() =>
                                            void handleStructureProposalDecision(
                                              item.proposal_id,
                                              "reject",
                                            )
                                          }
                                        >
                                          驳回提案
                                        </Button>
                                      </Space>
                                    ) : null}
                                    {item.recommended_action ? (
                                      <Text type="secondary">
                                        建议处理: {compactText(item.recommended_action, 160)}
                                      </Text>
                                    ) : null}
                                  </Space>
                                </List.Item>
                              )}
                            />
                          ) : null}

                          {!memorySurface.sleep.digest &&
                          !memorySurface.sleep.industry_profile &&
                          !memorySurface.sleep.work_context_overlay &&
                          memorySurface.sleep.structure_proposals.length === 0 &&
                          memorySurface.sleep.soft_rules.length === 0 &&
                          memorySurface.sleep.conflicts.length === 0 ? (
                            <Text type="secondary">
                              当前作用域还没有生成正式的记忆整理结果。
                            </Text>
                          ) : null}
                        </Space>
                      ) : (
                        <Text type="secondary">
                          当前作用域还没有生成正式的记忆整理结果。
                        </Text>
                      )}
                    </Card>
                    <Card
                      className="baize-card"
                      title={`激活与关系 (${memorySurface?.relation_count ?? 0})`}
                      data-testid="memory-activation-surface"
                    >
                      <Space direction="vertical" size={12} style={{ width: "100%" }}>
                        <Descriptions bordered size="small" column={2}>
                          <Descriptions.Item label="当前作用域">
                            {formatScope(
                              memorySurface?.scope_type || memoryScopeType,
                              memorySurface?.scope_id || memoryScopeId,
                            )}
                          </Descriptions.Item>
                          <Descriptions.Item label="当前查询">
                            {memorySurface?.query || "未输入"}
                          </Descriptions.Item>
                          <Descriptions.Item label="激活条目">
                            {memorySurface?.activation?.activated_count ?? 0}
                          </Descriptions.Item>
                          <Descriptions.Item label="关系视图">
                            {memorySurface?.relation_count ?? 0}
                          </Descriptions.Item>
                        </Descriptions>

                        {memorySurface?.activation ? (
                          <Space direction="vertical" size={8} style={{ width: "100%" }}>
                            <Space wrap>
                              {memorySurface.activation.top_entities
                                .slice(0, 4)
                                .map((entity) => (
                                  <Tag key={entity} color="blue">
                                    {entity}
                                  </Tag>
                                ))}
                              {memorySurface.activation.top_constraints
                                .slice(0, 3)
                                .map((constraint) => (
                                  <Tag key={constraint} color="gold">
                                    {constraint}
                                  </Tag>
                                ))}
                              {memorySurface.activation.top_relation_kinds
                                .slice(0, 3)
                                .map((kind) => (
                                  <Tag key={kind}>{kind}</Tag>
                                ))}
                              {memorySurface.activation.top_evidence_refs
                                .slice(0, 2)
                                .map((ref) => (
                                  <Tag key={ref} color="green">
                                    {ref}
                                  </Tag>
                                ))}
                            </Space>
                            {memorySurface.activation.top_relations.length > 0 ? (
                              <Paragraph style={{ marginBottom: 0 }}>
                                {compactText(memorySurface.activation.top_relations[0], 240)}
                              </Paragraph>
                            ) : null}
                          </Space>
                        ) : (
                          <Text type="secondary">
                            输入查询后，这里会显示当前作用域的激活结果和关系重点。
                          </Text>
                        )}

                        <Space wrap>
                          {Object.entries(memorySurface?.relation_kind_counts || {}).map(
                            ([kind, count]) => (
                              <Tag key={kind}>{`${kind} x${count}`}</Tag>
                            ),
                          )}
                        </Space>

                        <List
                          locale={{
                            emptyText: <Empty description="当前作用域暂无关系视图。" />,
                          }}
                          dataSource={memorySurface?.relations || []}
                          renderItem={(item) => (
                            <List.Item key={item.relation_id}>
                              <Space direction="vertical" size={6} style={{ width: "100%" }}>
                                <Space wrap>
                                  <Text strong>{item.relation_kind}</Text>
                                  <Tag>{formatScope(item.scope_type, item.scope_id)}</Tag>
                                  <Tag>{item.source_node_id}</Tag>
                                  <Tag>{item.target_node_id}</Tag>
                                  <Tag>{`置信度 ${formatPercent(item.confidence)}`}</Tag>
                                </Space>
                                <Paragraph style={{ marginBottom: 0 }}>
                                  {compactText(item.summary, 240)}
                                </Paragraph>
                                <Space wrap>
                                  {item.source_refs.slice(0, 3).map((ref) => (
                                    <Tag key={ref} color="green">
                                      {ref}
                                    </Tag>
                                  ))}
                                </Space>
                              </Space>
                            </List.Item>
                          )}
                        />
                      </Space>
                    </Card>
                    <Card
                      className="baize-card"
                      title={
                        recallResponse
                          ? `召回命中 (${recallResponse.hits.length})`
                          : "召回命中"
                      }
                    >
                      <List
                        locale={{
                          emptyText: (
                            <Empty description="请输入查询条件以查看召回结果。" />
                          ),
                        }}
                        dataSource={recallResponse?.hits || []}
                        renderItem={(item) => (
                          <List.Item key={item.entry_id}>
                            <Space direction="vertical" size={6} style={{ width: "100%" }}>
                              <Space wrap>
                                <Text strong>{item.title}</Text>
                                <Tag color="blue">{item.kind}</Tag>
                                <Tag>{formatScope(item.scope_type, item.scope_id)}</Tag>
                                <Tag>{`得分 ${item.score.toFixed(2)}`}</Tag>
                                <Tag>{`置信度 ${formatPercent(item.confidence)}`}</Tag>
                              </Space>
                              <Paragraph style={{ marginBottom: 0 }}>
                                {compactText(item.summary || item.content_excerpt, 240)}
                              </Paragraph>
                              <Space wrap>
                                <Tag>{`来源 ${item.source_type}:${item.source_ref}`}</Tag>
                                {item.entity_keys.slice(0, 4).map((entityKey) => (
                                  <Tag key={entityKey}>{entityKey}</Tag>
                                ))}
                                {item.opinion_keys.slice(0, 3).map((opinionKey) => (
                                  <Tag key={opinionKey} color="gold">
                                    {opinionKey}
                                  </Tag>
                                ))}
                              </Space>
                            </Space>
                          </List.Item>
                        )}
                      />
                    </Card>

                    <Card className="baize-card" title={`事实索引 (${memoryIndex.length})`}>
                      <List
                        locale={{ emptyText: <Empty description="暂无事实索引条目。" /> }}
                        dataSource={memoryIndex}
                        renderItem={(item) => (
                          <List.Item key={item.id}>
                            <Space direction="vertical" size={6} style={{ width: "100%" }}>
                              <Space wrap>
                                <Text strong>{item.title}</Text>
                                <Tag color="blue">{item.source_type}</Tag>
                                <Tag>{formatScope(item.scope_type, item.scope_id)}</Tag>
                                <Tag>{`质量 ${formatPercent(item.quality_score)}`}</Tag>
                                <Tag>{`置信度 ${formatPercent(item.confidence)}`}</Tag>
                              </Space>
                              <Paragraph style={{ marginBottom: 0 }}>
                                {compactText(item.summary || item.content_excerpt, 240)}
                              </Paragraph>
                              <Space wrap>
                                <Tag>{`来源引用 ${item.source_ref}`}</Tag>
                                {item.entity_keys.slice(0, 5).map((entityKey) => (
                                  <Tag key={entityKey}>{entityKey}</Tag>
                                ))}
                                {item.tags.slice(0, 5).map((tag) => (
                                  <Tag key={tag} color="green">
                                    {tag}
                                  </Tag>
                                ))}
                                {item.evidence_refs.slice(0, 3).map((ref) => (
                                  <Tag key={ref} color="gold">
                                    {ref}
                                  </Tag>
                                ))}
                              </Space>
                            </Space>
                          </List.Item>
                        )}
                      />
                    </Card>

                    <Card className="baize-card" title={`实体对象视图 (${entityViews.length})`}>
                      <List
                        locale={{ emptyText: <Empty description="暂无实体对象。" /> }}
                        dataSource={entityViews}
                        renderItem={(item) => (
                          <List.Item key={item.entity_id}>
                            <Space direction="vertical" size={6} style={{ width: "100%" }}>
                              <Space wrap>
                                <Text strong>{item.display_name}</Text>
                                <Tag>{item.entity_type}</Tag>
                                <Tag>{formatScope(item.scope_type, item.scope_id)}</Tag>
                                <Tag>{`置信度 ${formatPercent(item.confidence)}`}</Tag>
                              </Space>
                              <Paragraph style={{ marginBottom: 0 }}>
                                {compactText(item.summary, 240)}
                              </Paragraph>
                              <Space wrap>
                                {item.related_entities.slice(0, 5).map((entityKey) => (
                                  <Tag key={entityKey} color="blue">
                                    {entityKey}
                                  </Tag>
                                ))}
                                {item.supporting_refs.slice(0, 3).map((ref) => (
                                  <Tag key={ref} color="green">
                                    {ref}
                                  </Tag>
                                ))}
                                {item.contradicting_refs.slice(0, 3).map((ref) => (
                                  <Tag key={ref} color="red">
                                    {ref}
                                  </Tag>
                                ))}
                              </Space>
                            </Space>
                          </List.Item>
                        )}
                      />
                    </Card>

                    <Card className="baize-card" title={`主观观点视图 (${opinionViews.length})`}>
                      <List
                        locale={{ emptyText: <Empty description="暂无主观观点。" /> }}
                        dataSource={opinionViews}
                        renderItem={(item) => (
                          <List.Item key={item.opinion_id}>
                            <Space direction="vertical" size={6} style={{ width: "100%" }}>
                              <Space wrap>
                                <Text strong>{item.subject_key}</Text>
                                <Tag color={stanceColor(item.stance)}>{item.stance}</Tag>
                                <Tag>{formatScope(item.scope_type, item.scope_id)}</Tag>
                                <Tag>{`置信度 ${formatPercent(item.confidence)}`}</Tag>
                              </Space>
                              <Paragraph style={{ marginBottom: 0 }}>
                                {compactText(item.summary, 240)}
                              </Paragraph>
                              <Space wrap>
                                {item.entity_keys.slice(0, 5).map((entityKey) => (
                                  <Tag key={entityKey}>{entityKey}</Tag>
                                ))}
                                {item.supporting_refs.slice(0, 3).map((ref) => (
                                  <Tag key={ref} color="green">
                                    {ref}
                                  </Tag>
                                ))}
                                {item.contradicting_refs.slice(0, 3).map((ref) => (
                                  <Tag key={ref} color="red">
                                    {ref}
                                  </Tag>
                                ))}
                              </Space>
                            </Space>
                          </List.Item>
                        )}
                      />
                    </Card>

                    <Card className="baize-card" title={`反思执行记录 (${reflectionRuns.length})`}>
                      <List
                        locale={{ emptyText: <Empty description="暂无反思执行记录。" /> }}
                        dataSource={reflectionRuns}
                        renderItem={(item) => (
                          <List.Item key={item.run_id}>
                            <Space direction="vertical" size={6} style={{ width: "100%" }}>
                              <Space wrap>
                                <Text strong>{item.run_id}</Text>
                                <Tag>{item.status}</Tag>
                                <Tag>{formatScope(item.scope_type, item.scope_id)}</Tag>
                                <Tag>{item.trigger_kind}</Tag>
                              </Space>
                              <Paragraph style={{ marginBottom: 0 }}>
                                {compactText(item.summary, 240)}
                              </Paragraph>
                              <Space wrap>
                                <Tag>
                                  {`实体数 ${item.metadata?.entity_count ?? item.generated_entity_ids.length}`}
                                </Tag>
                                <Tag>
                                  {`观点数 ${item.metadata?.opinion_count ?? item.generated_opinion_ids.length}`}
                                </Tag>
                                <Tag>{`开始时间 ${formatDateTime(item.started_at)}`}</Tag>
                                <Tag>{`完成时间 ${formatDateTime(item.completed_at)}`}</Tag>
                                {(item.metadata?.proposal_ids || []).slice(0, 3).map((proposalId) => (
                                  <Tag key={proposalId} color="gold">
                                    {proposalId}
                                  </Tag>
                                ))}
                              </Space>
                            </Space>
                          </List.Item>
                        )}
                      />
                    </Card>
                  </>
                )}
              </Space>
            ),
          },
          {
            key: "records",
            label: (
              <span>
                <DatabaseOutlined /> 执行记录
              </span>
            ),
            children: loading ? (
              <Spin />
            ) : (
              <Space direction="vertical" size={16} style={{ width: "100%" }}>
                <Card className="baize-card" title="执行器列表">
                  <Space wrap>
                    {agents.map((agent) => (
                      <Card
                        className="baize-card"
                        key={agent.agent_id}
                        size="small"
                        hoverable
                        onClick={() => setSelectedAgentId(agent.agent_id)}
                        style={{
                          minWidth: 220,
                          borderColor:
                            selectedAgent?.agent_id === agent.agent_id
                              ? "var(--baize-selected-border)"
                              : undefined,
                        }}
                      >
                        <Space wrap>
                          <Text strong>
                            {presentExecutionActorName(agent.agent_id, agent.name)}
                          </Text>
                          <Tag color={isExecutionCore(agent) ? "blue" : "default"}>
                            {isExecutionCore(agent) ? "主脑" : "执行位"}
                          </Tag>
                          <Tag>{presentRuntimeStatusLabel(agent.status)}</Tag>
                        </Space>
                        <div style={{ marginTop: 8 }}>
                          <Text type="secondary">
                            {normalizeSpiderMeshBrand(agent.role_name) ||
                              "尚未分配角色"}
                          </Text>
                        </div>
                      </Card>
                    ))}
                  </Space>
                </Card>

                {detailLoading ? (
                  <Spin />
                ) : detail ? (
                  <>
                    <Card className="baize-card">
                      <Space direction="vertical" size={8}>
                        <Space wrap>
                          <Title level={4} style={{ margin: 0 }}>
                            {presentExecutionActorName(
                              selectedAgent?.agent_id || detail.agent.agent_id,
                              selectedAgent?.name || detail.agent.name,
                            )}
                          </Title>
                          <Tag color={isExecutionCore(selectedAgent) ? "blue" : "default"}>
                            {isExecutionCore(selectedAgent)
                              ? "超级伙伴核心主脑"
                              : "全职执行位"}
                          </Tag>
                        </Space>
                        <Text>
                          {normalizeSpiderMeshBrand(
                            selectedAgent?.current_focus ||
                              selectedAgent?.role_summary ||
                              "暂无执行摘要。",
                          )}
                        </Text>
                        <Space wrap>
                          <Tag>{`信件 ${detail.mailbox.length}`}</Tag>
                          <Tag>{`检查点 ${detail.checkpoints.length}`}</Tag>
                          <Tag>{`租约 ${detail.leases.length}`}</Tag>
                          <Tag>{`成长轨迹 ${detail.growth.length}`}</Tag>
                        </Space>
                      </Space>
                    </Card>

                    <Card className="baize-card" title="信箱 / 检查点 / 租约 / 成长记录">
                      <List
                        dataSource={[
                          ...detail.mailbox
                            .slice(0, 4)
                            .map(
                              (item) =>
                                `信件 | ${item.title} | ${getStatusLabel(item.status)}`,
                            ),
                          ...detail.checkpoints
                            .slice(0, 4)
                            .map(
                              (item) =>
                                `检查点 | ${getPhaseLabel(item.phase || item.checkpoint_kind)} | ${getStatusLabel(item.status)}`,
                            ),
                          ...detail.leases
                            .slice(0, 4)
                            .map(
                              (item) =>
                                `租约 | ${getLeaseKindLabel(item.lease_kind)} | ${getStatusLabel(item.lease_status)}`,
                            ),
                          ...detail.growth
                            .slice(0, 4)
                            .map(
                              (item) =>
                                `成长 | ${getChangeTypeLabel(item.change_type)} | ${item.description}`,
                            ),
                        ]}
                        locale={{ emptyText: <Empty description="暂无执行记录。" /> }}
                        renderItem={(item) => <List.Item>{item}</List.Item>}
                      />
                    </Card>
                  </>
                ) : (
                  <Empty description="请在左侧选择一个执行器以查看记录。" />
                )}
              </Space>
            ),
          },
        ]}
      />
    </Space>
  );
}
