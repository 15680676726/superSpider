import {
  Alert,
  Button,
  Card,
  Empty,
  Space,
  Spin,
  Tag,
  Typography,
} from "antd";
import type {
  RuntimeCapabilityOptimizationItem,
  RuntimeCapabilityOptimizationOverview,
} from "../../api/modules/runtimeCenter";
import { RecommendationOptimizationMeta } from "../Insights/RecommendationOptimizationMeta";
import {
  presentInsightRecommendationType,
  presentInsightStatusLabel,
  presentInsightText,
} from "../Insights/presentation";
import { formatCnTimestamp } from "./text";

const { Paragraph, Text } = Typography;

function statusColor(status?: string | null) {
  if (!status) {
    return "default";
  }
  if (["executed", "approved"].includes(status)) {
    return "success";
  }
  if (["failed", "rejected"].includes(status)) {
    return "error";
  }
  if (["waiting-confirm", "manual-only"].includes(status)) {
    return "warning";
  }
  return "processing";
}

interface CapabilityOptimizationPanelProps {
  loading: boolean;
  error: string | null;
  overview: RuntimeCapabilityOptimizationOverview | null;
  busyRecommendationId: string | null;
  onExecute: (item: RuntimeCapabilityOptimizationItem) => void;
  onOpenRoute: (route: string, title: string) => void;
}

interface OptimizationItemActions {
  busyRecommendationId: string | null;
  onExecute: (item: RuntimeCapabilityOptimizationItem) => void;
  onOpenRoute: (route: string, title: string) => void;
}

function renderOptimizationItem(
  item: RuntimeCapabilityOptimizationItem,
  { busyRecommendationId, onExecute, onOpenRoute }: OptimizationItemActions,
) {
  const recommendation = item.recommendation.recommendation;
  const decision = item.recommendation.decision;
  const recommendationId = recommendation.recommendation_id;
  const caseTitle =
    presentInsightText(item.case.title) || item.case.title || "未命名案例";
  const recommendationTitle =
    presentInsightText(recommendation.title) ||
    recommendation.title ||
    "未命名建议";
  const recommendationSummary =
    presentInsightText(recommendation.summary) || recommendation.summary || "";
  const caseRoute = item.routes.case || item.recommendation.routes.case;
  const decisionRoute =
    decision?.preferred_route ||
    decision?.chat_route ||
    item.recommendation.routes.decision ||
    item.routes.decision;
  const decisionButtonLabel = decision?.requires_human_confirmation
    ? "去聊天确认"
    : "查看治理";
  const executable =
    Boolean(recommendation.executable) &&
    !["executed", "rejected", "failed", "manual-only"].includes(
      String(recommendation.status || ""),
    );
  const confidence =
    typeof recommendation.confidence === "number"
      ? Math.round(recommendation.confidence * 100)
      : null;

  return (
    <div
      key={recommendationId}
      style={{
        padding: 16,
        borderRadius: 16,
        border: "1px solid rgba(255,255,255,0.08)",
        background: "rgba(255,255,255,0.02)",
      }}
    >
      <Space
        align="start"
        style={{ width: "100%", justifyContent: "space-between" }}
      >
        <Space direction="vertical" size={8} style={{ width: "100%" }}>
          <Space wrap>
            <Text strong>{recommendationTitle}</Text>
            <Tag color={statusColor(recommendation.status)}>
              {presentInsightStatusLabel(recommendation.status)}
            </Tag>
            <Tag>
              {presentInsightRecommendationType(
                recommendation.recommendation_type,
              )}
            </Tag>
            <Tag>{caseTitle}</Tag>
          </Space>
          <Paragraph type="secondary" style={{ marginBottom: 0 }}>
            {recommendationSummary}
          </Paragraph>
          <Space wrap size={[4, 4]}>
            <Tag>优先级 {recommendation.priority || "-"}</Tag>
            <Tag>置信度 {confidence !== null ? `${confidence}%` : "-"}</Tag>
            <Tag>案例状态 {presentInsightStatusLabel(item.case.status)}</Tag>
            <Tag>{formatCnTimestamp(recommendation.updated_at)}</Tag>
          </Space>
          <RecommendationOptimizationMeta recommendation={recommendation} />
        </Space>
        <Space direction="vertical" size={8}>
          {executable ? (
            <Button
              type="primary"
              loading={busyRecommendationId === recommendationId}
              onClick={() => onExecute(item)}
            >
              交给主脑
            </Button>
          ) : null}
          {caseRoute ? (
            <Button onClick={() => onOpenRoute(caseRoute, `${caseTitle}详情`)}>
              打开案例
            </Button>
          ) : null}
          {decisionRoute ? (
            <Button
              onClick={() =>
                onOpenRoute(decisionRoute, `${recommendationTitle}决策`)
              }
            >
              {decisionButtonLabel}
            </Button>
          ) : null}
        </Space>
      </Space>
    </div>
  );
}

export default function CapabilityOptimizationPanel({
  loading,
  error,
  overview,
  busyRecommendationId,
  onExecute,
  onOpenRoute,
}: CapabilityOptimizationPanelProps) {
  const summary = overview?.summary;

  return (
    <Card className="baize-card">
      <Space
        align="start"
        style={{ width: "100%", justifyContent: "space-between" }}
      >
        <div>
          <Text strong style={{ fontSize: 18 }}>
            能力缺口治理
          </Text>
          <Paragraph type="secondary" style={{ marginTop: 4, marginBottom: 0 }}>
            执行中枢在这里统一观察团队能力缺口、试点替换、稳定扩容和旧能力退役，不再需要在预测页里分散查找。
          </Paragraph>
        </div>
        <Space wrap size={[4, 4]}>
          <Tag color="geekblue">待处理 {summary?.actionable_count ?? 0}</Tag>
          <Tag color="orange">试点 {summary?.trial_count ?? 0}</Tag>
          <Tag color="purple">扩容 {summary?.rollout_count ?? 0}</Tag>
          <Tag color="volcano">退役 {summary?.retire_count ?? 0}</Tag>
        </Space>
      </Space>

      <div style={{ marginTop: 16 }}>
        {error ? (
          <Alert
            type="error"
            showIcon
            message={error}
            style={{ marginBottom: 32 }}
          />
        ) : null}
        {loading && !overview ? (
          <Spin />
        ) : !overview ? (
          <Empty description="当前没有能力缺口治理数据" />
        ) : (
          <Space direction="vertical" size={16} style={{ width: "100%" }}>
            <Space wrap size={[4, 4]}>
              <Tag>涉及案例 {summary?.case_count ?? 0}</Tag>
              <Tag>缺少能力 {summary?.missing_capability_count ?? 0}</Tag>
              <Tag>
                能力效果差 {summary?.underperforming_capability_count ?? 0}
              </Tag>
              <Tag>待确认 {summary?.waiting_confirm_count ?? 0}</Tag>
              <Tag>仅人工处理 {summary?.manual_only_count ?? 0}</Tag>
              <Tag>已执行 {summary?.executed_count ?? 0}</Tag>
            </Space>

            <div>
              <Text strong>当前待处理</Text>
              <div style={{ marginTop: 12, display: "grid", gap: 12 }}>
                {overview.actionable.length === 0 ? (
                  <Empty description="当前没有待处理的能力治理建议" />
                ) : (
                  overview.actionable.map((item) =>
                    renderOptimizationItem(item, {
                      busyRecommendationId,
                      onExecute,
                      onOpenRoute,
                    }),
                  )
                )}
              </div>
            </div>

            <div>
              <Text strong>最近闭环记录</Text>
              <div style={{ marginTop: 12, display: "grid", gap: 12 }}>
                {overview.history.length === 0 ? (
                  <Empty description="当前没有最近闭环记录" />
                ) : (
                  overview.history.map((item) =>
                    renderOptimizationItem(item, {
                      busyRecommendationId,
                      onExecute,
                      onOpenRoute,
                    }),
                  )
                )}
              </div>
            </div>
          </Space>
        )}
      </div>
    </Card>
  );
}
