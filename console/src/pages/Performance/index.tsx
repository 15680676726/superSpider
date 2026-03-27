import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Row,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
} from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { request } from "../../api";
import {
  presentInsightMetricFormula,
  presentInsightMetricLabel,
  presentInsightMetricSource,
  presentInsightScopeLabel,
  presentInsightStatLabel,
  presentInsightStatValue,
  presentInsightText,
} from "../Insights/presentation";

const { Paragraph, Text, Title } = Typography;

interface MetricItem {
  id: string;
  key: string;
  label: string;
  display_value: string;
  formula: string;
  source_summary: string;
}

interface AgentBreakdownItem {
  agent_id: string;
  name: string;
  task_count: number;
  window_task_count: number;
  active_task_count: number;
  completed_task_count: number;
  failed_task_count: number;
  success_rate: number;
  evidence_count: number;
  decision_count: number;
  patch_count: number;
  applied_patch_count: number;
  rollback_patch_count: number;
  route: string;
}

interface PerformanceOverview {
  window: "daily" | "weekly" | "monthly";
  scope_type?: "global" | "agent" | "industry";
  scope_id?: string | null;
  scope_label: string;
  metrics: MetricItem[];
  prediction_stats?: {
    prediction_count: number;
    recommendation_count: number;
    review_count: number;
    auto_execution_count: number;
    prediction_hit_rate: number;
    recommendation_adoption_rate: number;
    recommendation_execution_benefit: number;
  };
  agent_breakdown: AgentBreakdownItem[];
  task_status_counts: Record<string, number>;
}

const WINDOW_OPTIONS = [
  { value: "daily", label: "日度" },
  { value: "weekly", label: "周度" },
  { value: "monthly", label: "月度" },
] as const;

const TASK_STATUS_LABELS: Record<string, string> = {
  waiting: "待处理",
  queued: "排队中",
  running: "运行中",
  completed: "已完成",
  failed: "失败",
  cancelled: "已取消",
  blocked: "阻塞",
  "needs-confirm": "待确认",
};

function localizePerformanceMetric(metric: MetricItem): MetricItem {
  return {
    ...metric,
    label: presentInsightMetricLabel(metric.key, metric.label),
    formula: presentInsightMetricFormula(metric.formula),
    source_summary: presentInsightMetricSource(metric.source_summary),
  };
}

function localizeScopeLabel(overview: PerformanceOverview): string {
  return presentInsightScopeLabel(
    overview.scope_type,
    overview.scope_label,
    overview.scope_id,
  );
}

function localizeTaskStatus(status: string): string {
  return TASK_STATUS_LABELS[status] || status;
}

function formatPredictionTag(label: string, value: string): string {
  return `${label} ${value}`;
}

export default function PerformancePage() {
  const [window, setWindow] = useState<"daily" | "weekly" | "monthly">(
    "weekly",
  );
  const [overview, setOverview] = useState<PerformanceOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadOverview = useCallback(async () => {
    setLoading(true);
    try {
      setError(null);
      const payload = await request<PerformanceOverview>(
        `/runtime-center/performance?window=${window}`,
      );
      setOverview(payload);
    } catch (fetchError) {
      setError(
        fetchError instanceof Error ? fetchError.message : String(fetchError),
      );
    } finally {
      setLoading(false);
    }
  }, [window]);

  useEffect(() => {
    void loadOverview();
  }, [loadOverview]);

  const windowLabel =
    WINDOW_OPTIONS.find((item) => item.value === window)?.label || "周度";

  const localizedMetrics = useMemo(
    () => overview?.metrics.map((metric) => localizePerformanceMetric(metric)) ?? [],
    [overview?.metrics],
  );
  const localizedScope = useMemo(
    () => (overview ? localizeScopeLabel(overview) : ""),
    [overview],
  );
  const localizedTaskStatuses = useMemo(
    () =>
      overview
        ? Object.entries(overview.task_status_counts).map(([key, value]) => ({
            key,
            label: localizeTaskStatus(key),
            value,
          }))
        : [],
    [overview],
  );

  const columns = [
    {
      title: "智能体",
      dataIndex: "name",
      key: "name",
      render: (_: string, record: AgentBreakdownItem) => (
        <Text strong>{presentInsightText(record.name) || "未命名智能体"}</Text>
      ),
    },
    {
      title: "负载",
      dataIndex: "active_task_count",
      key: "active_task_count",
      render: (value: number, record: AgentBreakdownItem) => (
        <Space>
          <Tag color={value > 0 ? "processing" : "default"}>{value}</Tag>
          <Text type="secondary">/ {record.task_count}</Text>
        </Space>
      ),
    },
    {
      title: "成功率",
      dataIndex: "success_rate",
      key: "success_rate",
      render: (value: number) => `${value.toFixed(1)}%`,
    },
    {
      title: "证据",
      dataIndex: "evidence_count",
      key: "evidence_count",
    },
    {
      title: "决策",
      dataIndex: "decision_count",
      key: "decision_count",
    },
    {
      title: "补丁",
      key: "patches",
      render: (_: unknown, record: AgentBreakdownItem) => (
        <Space>
          <Tag>{record.patch_count}</Tag>
          <Tag color="green">已应用 {record.applied_patch_count}</Tag>
          <Tag color="orange">已回滚 {record.rollback_patch_count}</Tag>
        </Space>
      ),
    },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Card>
        <Space
          align="start"
          style={{ width: "100%", justifyContent: "space-between" }}
        >
          <div>
            <Title level={3} style={{ marginTop: 0, marginBottom: 8 }}>
              绩效概览
            </Title>
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              查看窗口内的核心指标、任务状态和智能体负载分布。
            </Paragraph>
          </div>
          <Space>
            <Select
              style={{ width: 120 }}
              value={window}
              options={[...WINDOW_OPTIONS]}
              onChange={(value) =>
                setWindow(value as "daily" | "weekly" | "monthly")
              }
            />
            <Button icon={<ReloadOutlined />} onClick={() => void loadOverview()}>
              刷新
            </Button>
          </Space>
        </Space>
      </Card>

      {error ? <Alert type="error" showIcon message={error} /> : null}
      {loading ? (
        <Card>
          <Spin />
        </Card>
      ) : !overview ? (
        <Card>
          <Empty description="暂无绩效数据" />
        </Card>
      ) : (
        <>
          <Row gutter={[16, 16]}>
            {localizedMetrics.map((metric) => (
              <Col xs={24} md={12} xl={8} key={metric.id}>
                <Card>
                  <Text type="secondary">{metric.label}</Text>
                  <Title level={2} style={{ marginTop: 8, marginBottom: 8 }}>
                    {metric.display_value}
                  </Title>
                  {metric.formula ? (
                    <Paragraph type="secondary" style={{ marginBottom: 4 }}>
                      计算方式：{metric.formula}
                    </Paragraph>
                  ) : null}
                  {metric.source_summary ? (
                    <Text type="secondary">数据来源：{metric.source_summary}</Text>
                  ) : null}
                </Card>
              </Col>
            ))}
          </Row>

          <Card
            title={`${localizedScope} / ${windowLabel}`}
            extra={
              <Space wrap>
                {localizedTaskStatuses.map(({ key, label, value }) => (
                  <Tag key={key}>
                    {label}: {value}
                  </Tag>
                ))}
              </Space>
            }
          >
            {overview.prediction_stats ? (
              <Space wrap style={{ marginBottom: 32 }}>
                <Tag>
                  {formatPredictionTag(
                    "预测",
                    presentInsightStatValue(
                      "prediction_count",
                      overview.prediction_stats.prediction_count,
                    ),
                  )}
                </Tag>
                <Tag>
                  {formatPredictionTag(
                    "建议",
                    presentInsightStatValue(
                      "recommendation_count",
                      overview.prediction_stats.recommendation_count,
                    ),
                  )}
                </Tag>
                <Tag>
                  {formatPredictionTag(
                    "复盘",
                    presentInsightStatValue(
                      "review_count",
                      overview.prediction_stats.review_count,
                    ),
                  )}
                </Tag>
                <Tag>
                  {formatPredictionTag(
                    "自动执行",
                    presentInsightStatValue(
                      "auto_execution_count",
                      overview.prediction_stats.auto_execution_count,
                    ),
                  )}
                </Tag>
                <Tag>
                  {formatPredictionTag(
                    presentInsightStatLabel("prediction_hit_rate"),
                    presentInsightStatValue(
                      "prediction_hit_rate",
                      overview.prediction_stats.prediction_hit_rate,
                    ),
                  )}
                </Tag>
                <Tag>
                  {formatPredictionTag(
                    presentInsightStatLabel("recommendation_adoption_rate"),
                    presentInsightStatValue(
                      "recommendation_adoption_rate",
                      overview.prediction_stats.recommendation_adoption_rate,
                    ),
                  )}
                </Tag>
                <Tag>
                  {formatPredictionTag(
                    presentInsightStatLabel("recommendation_execution_benefit"),
                    presentInsightStatValue(
                      "recommendation_execution_benefit",
                      overview.prediction_stats.recommendation_execution_benefit,
                    ),
                  )}
                </Tag>
              </Space>
            ) : null}
            <Table
              rowKey="agent_id"
              columns={columns}
              dataSource={overview.agent_breakdown}
              pagination={false}
            />
          </Card>
        </>
      )}
    </Space>
  );
}

