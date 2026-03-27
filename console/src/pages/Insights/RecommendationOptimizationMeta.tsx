import { Descriptions, Space, Tag, Typography } from "antd";
import type { DescriptionsProps } from "antd";
import type { PredictionRecommendationRecord } from "../../api/modules/predictions";
import {
  presentCapabilityLabel,
  presentInsightText,
} from "./presentation";

const { Text } = Typography;

const GAP_KIND_LABELS: Record<string, string> = {
  missing_capability: "缺少能力",
  underperforming_capability: "能力效果差",
  capability_rollout: "稳定后扩容",
  capability_retirement: "旧能力退役",
};

const OPTIMIZATION_STAGE_LABELS: Record<string, string> = {
  trial: "单点试投放",
  rollout: "治理扩容",
  retire: "退役收口",
};

const CHECK_STATUS_LABELS: Record<string, string> = {
  pass: "通过",
  warn: "警告",
  fail: "失败",
};

const CHECK_STATUS_COLORS: Record<string, string> = {
  pass: "success",
  warn: "warning",
  fail: "error",
};

const ASSIGNMENT_MODE_LABELS: Record<string, string> = {
  merge: "合并分配",
  replace: "替换分配",
};

const ROLLOUT_SCOPE_LABELS: Record<string, string> = {
  "single-agent": "单个智能体试点",
};

type UnknownRecord = Record<string, unknown>;

function asRecord(value: unknown): UnknownRecord {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value as UnknownRecord;
}

function asRecordList(value: unknown): UnknownRecord[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item) => item && typeof item === "object" && !Array.isArray(item))
    .map((item) => item as UnknownRecord);
}

function asString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function asBoolean(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function toStringList(...values: unknown[]): string[] {
  const seen = new Set<string>();
  const items: string[] = [];
  for (const value of values) {
    if (!Array.isArray(value)) {
      continue;
    }
    for (const entry of value) {
      const normalized = asString(entry);
      if (!normalized || seen.has(normalized)) {
        continue;
      }
      seen.add(normalized);
      items.push(normalized);
    }
  }
  return items;
}

function formatPercent(value: unknown): string | null {
  const numeric = asNumber(value);
  if (numeric === null) {
    return null;
  }
  return `${Math.round(numeric * 100)}%`;
}

function formatDurationSeconds(value: unknown): string | null {
  const numeric = asNumber(value);
  if (numeric === null) {
    return null;
  }
  if (numeric >= 60) {
    return `${(numeric / 60).toFixed(1)} 分钟`;
  }
  return `${numeric.toFixed(1)} 秒`;
}

function presentGapKind(value: string): string {
  return GAP_KIND_LABELS[value] || presentInsightText(value) || value;
}

function presentOptimizationStage(value: string): string {
  return OPTIMIZATION_STAGE_LABELS[value] || presentInsightText(value) || value;
}

function buildStatsTags(
  label: string,
  stats: UnknownRecord,
): Array<{ key: string; color?: string; text: string }> {
  if (!Object.keys(stats).length) {
    return [];
  }
  const tags: Array<{ key: string; color?: string; text: string }> = [];
  const failureRate = formatPercent(stats.failure_rate);
  const manualRate = formatPercent(stats.manual_intervention_rate);
  const blockageRate = formatPercent(stats.workflow_blockage_rate);
  const avgDuration = formatDurationSeconds(stats.avg_duration_seconds);
  const taskCount = asNumber(stats.task_count);
  if (failureRate) {
    tags.push({
      key: `${label}:failure`,
      color: "error",
      text: `${label}失败率 ${failureRate}`,
    });
  }
  if (manualRate) {
    tags.push({
      key: `${label}:manual`,
      color: "warning",
      text: `${label}人工接管率 ${manualRate}`,
    });
  }
  if (blockageRate) {
    tags.push({
      key: `${label}:blockage`,
      color: "volcano",
      text: `${label}工作流阻断率 ${blockageRate}`,
    });
  }
  if (avgDuration) {
    tags.push({
      key: `${label}:duration`,
      color: "blue",
      text: `${label}平均耗时 ${avgDuration}`,
    });
  }
  if (taskCount !== null) {
    tags.push({
      key: `${label}:tasks`,
      text: `${label}样本任务 ${taskCount}`,
    });
  }
  return tags;
}

interface RecommendationOptimizationMetaProps {
  recommendation: PredictionRecommendationRecord;
}

export function RecommendationOptimizationMeta({
  recommendation,
}: RecommendationOptimizationMetaProps) {
  const metadata = asRecord(recommendation.metadata);
  const gapKind = asString(metadata.gap_kind);
  const optimizationStage = asString(metadata.optimization_stage);
  const candidate = asRecord(metadata.resolved_candidate);
  const fallbackCandidate = asRecord(metadata.candidate);
  const effectiveCandidate = Object.keys(candidate).length
    ? candidate
    : fallbackCandidate;
  const preflight = asRecord(metadata.preflight);
  const trialPlan = asRecord(preflight.trial_plan);
  const stats = asRecord(metadata.stats);
  const oldStats = asRecord(stats.old_stats);
  const newStats = asRecord(stats.new_stats);
  const checkItems = asRecordList(preflight.checks);
  const requestedCapabilityIds = toStringList(
    metadata.requested_capability_ids,
    recommendation.target_capability_ids,
  );
  const replacementCapabilityIds = toStringList(
    metadata.replacement_capability_ids,
  );
  const installedCapabilityIds = toStringList(
    metadata.installed_capability_ids,
    metadata.requested_capability_ids,
  );
  const searchQueries = toStringList(metadata.search_queries);
  const reviewNotes = toStringList(effectiveCandidate.review_notes);
  const candidateTitle =
    presentInsightText(asString(effectiveCandidate.title)) ||
    asString(effectiveCandidate.title);
  const candidateSource =
    presentInsightText(asString(effectiveCandidate.source_label)) ||
    asString(effectiveCandidate.source_label);
  const workflowTitle =
    presentInsightText(asString(metadata.workflow_title)) ||
    asString(metadata.workflow_title);
  const targetAgentId =
    presentInsightText(recommendation.target_agent_id || undefined) ||
    recommendation.target_agent_id ||
    "";
  const oldCapabilityId = asString(metadata.old_capability_id);
  const newCapabilityId = asString(metadata.new_capability_id);
  const preflightReady = asBoolean(preflight.ready);
  const preflightSummary =
    presentInsightText(asString(preflight.summary)) ||
    asString(preflight.summary);
  const reviewSummary =
    presentInsightText(asString(effectiveCandidate.review_summary)) ||
    asString(effectiveCandidate.review_summary);
  const sourceRecommendationId = asString(metadata.source_recommendation_id);
  const assignmentMode = asString(trialPlan.capability_assignment_mode);
  const rolloutScope = asString(trialPlan.rollout_scope);
  const trialAgentId =
    presentInsightText(asString(stats.trial_agent_id)) ||
    asString(stats.trial_agent_id);
  const preflightRisk = asString(preflight.risk_level);
  const reviewRequired = asBoolean(preflight.review_required);

  const hasContent =
    Boolean(gapKind) ||
    Boolean(optimizationStage) ||
    Boolean(candidateTitle) ||
    Boolean(preflightSummary) ||
    Boolean(oldCapabilityId) ||
    Boolean(newCapabilityId) ||
    Boolean(requestedCapabilityIds.length) ||
    Boolean(replacementCapabilityIds.length) ||
    Boolean(checkItems.length) ||
    Boolean(Object.keys(stats).length);

  if (!hasContent) {
    return null;
  }

  const infoItems: NonNullable<DescriptionsProps["items"]> = [];
  if (targetAgentId) {
    infoItems.push({
      key: "target-agent",
      label: "目标智能体",
      children: targetAgentId,
    });
  }
  if (workflowTitle) {
    infoItems.push({
      key: "workflow-title",
      label: "关联工作流",
      children: workflowTitle,
    });
  }
  if (candidateTitle) {
    infoItems.push({
      key: "candidate-title",
      label: "候选能力",
      children: candidateTitle,
    });
  }
  if (candidateSource) {
    infoItems.push({
      key: "candidate-source",
      label: "候选来源",
      children: candidateSource,
    });
  }
  if (rolloutScope) {
    infoItems.push({
      key: "rollout-scope",
      label: "试点范围",
      children:
        ROLLOUT_SCOPE_LABELS[rolloutScope] ||
        presentInsightText(rolloutScope) ||
        rolloutScope,
    });
  }
  if (assignmentMode) {
    infoItems.push({
      key: "assignment-mode",
      label: "分配方式",
      children:
        ASSIGNMENT_MODE_LABELS[assignmentMode] ||
        presentInsightText(assignmentMode) ||
        assignmentMode,
    });
  }
  if (sourceRecommendationId) {
    infoItems.push({
      key: "source-recommendation",
      label: "来源建议",
      children: sourceRecommendationId,
    });
  }
  if (preflightSummary) {
    infoItems.push({
      key: "preflight-summary",
      label: "预检结论",
      children: preflightSummary,
    });
  }

  return (
    <Space direction="vertical" size={8} style={{ width: "100%" }}>
      <Space wrap size={[4, 4]}>
        {gapKind ? (
          <Tag color="geekblue">{presentGapKind(gapKind)}</Tag>
        ) : null}
        {optimizationStage ? (
          <Tag color="purple">
            {presentOptimizationStage(optimizationStage)}
          </Tag>
        ) : null}
        {preflightReady !== null ? (
          <Tag color={preflightReady ? "success" : "warning"}>
            {preflightReady ? "可直接试投放" : "需人工处理"}
          </Tag>
        ) : null}
        {preflightRisk ? (
          <Tag color={preflightRisk === "confirm" ? "error" : "gold"}>
            {preflightRisk === "confirm" ? "确认风险" : "守护风险"}
          </Tag>
        ) : null}
        {reviewRequired ? <Tag color="orange">安装前需审查</Tag> : null}
      </Space>

      {infoItems.length ? (
        <Descriptions
          bordered
          size="small"
          column={2}
          items={infoItems}
        />
      ) : null}

      {requestedCapabilityIds.length || replacementCapabilityIds.length ? (
        <Space wrap size={[4, 4]}>
          {requestedCapabilityIds.map((capabilityId) => (
            <Tag key={`requested:${capabilityId}`} color="blue">
              试投放: {presentCapabilityLabel(capabilityId)}
            </Tag>
          ))}
          {replacementCapabilityIds.map((capabilityId) => (
            <Tag key={`replace:${capabilityId}`} color="volcano">
              待替换: {presentCapabilityLabel(capabilityId)}
            </Tag>
          ))}
        </Space>
      ) : null}

      {oldCapabilityId || newCapabilityId || installedCapabilityIds.length ? (
        <Space wrap size={[4, 4]}>
          {oldCapabilityId ? (
            <Tag color="volcano">
              旧能力: {presentCapabilityLabel(oldCapabilityId)}
            </Tag>
          ) : null}
          {newCapabilityId ? (
            <Tag color="green">
              新能力: {presentCapabilityLabel(newCapabilityId)}
            </Tag>
          ) : null}
          {installedCapabilityIds
            .filter(
              (capabilityId) =>
                capabilityId !== oldCapabilityId &&
                capabilityId !== newCapabilityId,
            )
            .map((capabilityId) => (
              <Tag key={`installed:${capabilityId}`} color="cyan">
                已安装: {presentCapabilityLabel(capabilityId)}
              </Tag>
            ))}
        </Space>
      ) : null}

      {checkItems.length ? (
        <Space wrap size={[4, 4]}>
          {checkItems.map((check) => {
            const code = asString(check.code) || asString(check.label);
            const label =
              presentInsightText(asString(check.label)) ||
              asString(check.label) ||
              code;
            const detail =
              presentInsightText(asString(check.detail)) ||
              asString(check.detail);
            const status = asString(check.status) || "pass";
            return (
              <Tag
                key={`check:${code}`}
                color={CHECK_STATUS_COLORS[status] || "default"}
              >
                {CHECK_STATUS_LABELS[status] || status}:{" "}
                {detail ? `${label} (${detail})` : label}
              </Tag>
            );
          })}
        </Space>
      ) : null}

      {buildStatsTags("当前能力", oldStats)
        .concat(buildStatsTags("候选能力", newStats))
        .concat(buildStatsTags("观测窗口", Object.keys(newStats).length ? {} : stats))
        .length ? (
        <Space wrap size={[4, 4]}>
          {buildStatsTags("当前能力", oldStats)
            .concat(buildStatsTags("候选能力", newStats))
            .concat(
              buildStatsTags(
                "观测窗口",
                Object.keys(newStats).length ? {} : stats,
              ),
            )
            .map((item) => (
              <Tag key={item.key} color={item.color}>
                {item.text}
              </Tag>
            ))}
          {trialAgentId ? (
            <Tag color="processing">试点智能体: {trialAgentId}</Tag>
          ) : null}
        </Space>
      ) : null}

      {searchQueries.length ? (
        <Text type="secondary">
          搜索语句: {searchQueries.map((item) => presentInsightText(item) || item).join(" | ")}
        </Text>
      ) : null}
      {reviewSummary ? (
        <Text type="secondary">审查摘要: {reviewSummary}</Text>
      ) : null}
      {reviewNotes.length ? (
        <Text type="secondary">
          审查备注: {reviewNotes.map((item) => presentInsightText(item) || item).join("；")}
        </Text>
      ) : null}
    </Space>
  );
}
