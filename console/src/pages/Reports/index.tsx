import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  List,
  Row,
  Space,
  Spin,
  Tag,
  Typography,
} from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { request } from "../../api";
import {
  presentInsightMetricFormula,
  presentInsightMetricLabel,
  presentInsightMetricSource,
  presentInsightText,
} from "../Insights/presentation";
import { PageHeader } from "../../components/PageHeader";

const { Paragraph, Text } = Typography;

interface MetricItem {
  id: string;
  key: string;
  label: string;
  display_value: string;
  formula: string;
  source_summary: string;
}

interface ReportItem {
  id: string;
  title: string;
  summary: string;
  window: "daily" | "weekly" | "monthly";
  highlights: string[];
  evidence_count: number;
  proposal_count: number;
  patch_count: number;
  applied_patch_count: number;
  decision_count: number;
  prediction_count: number;
  recommendation_count: number;
  review_count: number;
  auto_execution_count: number;
  task_count: number;
  agent_count: number;
  task_status_counts: Record<string, number>;
  metrics: MetricItem[];
  since: string;
  until: string;
}

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

function localizeReportTitle(window: ReportItem["window"]): string {
  if (window === "daily") {
    return "日报";
  }
  if (window === "weekly") {
    return "周报";
  }
  return "月报";
}

function localizeTaskStatus(status: string): string {
  return TASK_STATUS_LABELS[status] || status;
}

function localizeReportMetric(metric: MetricItem): MetricItem {
  return {
    ...metric,
    label: presentInsightMetricLabel(metric.key, metric.label),
    formula: presentInsightMetricFormula(metric.formula),
    source_summary: presentInsightMetricSource(metric.source_summary),
  };
}

function hasWindowActivity(report: ReportItem): boolean {
  return (
    report.task_count > 0 ||
    report.evidence_count > 0 ||
    report.proposal_count > 0 ||
    report.patch_count > 0 ||
    report.decision_count > 0 ||
    report.prediction_count > 0 ||
    report.review_count > 0
  );
}

function buildReportSummary(report: ReportItem): string {
  const windowLabel = localizeReportTitle(report.window);
  const localizedSummary = presentInsightText(report.summary);
  if (!hasWindowActivity(report)) {
    return localizedSummary || `${windowLabel}窗口内暂无任务、证据或决策活动。`;
  }
  return (
    localizedSummary ||
    `${windowLabel}共记录 ${report.task_count} 个任务、${report.evidence_count} 条证据、${report.decision_count} 次决策。`
  );
}

function buildReportHighlights(report: ReportItem): string[] {
  const items: string[] = [];
  if (report.task_count > 0) {
    items.push(`任务产出 ${report.task_count}`);
  }
  if (report.evidence_count > 0) {
    items.push(`证据沉淀 ${report.evidence_count}`);
  }
  if (report.proposal_count > 0) {
    items.push(`提案生成 ${report.proposal_count}`);
  }
  if (report.patch_count > 0) {
    items.push(`补丁产出 ${report.patch_count}`);
  }
  if (report.applied_patch_count > 0) {
    items.push(`补丁应用 ${report.applied_patch_count}`);
  }
  if (report.decision_count > 0) {
    items.push(`决策记录 ${report.decision_count}`);
  }
  if (report.prediction_count > 0) {
    items.push(`预测 ${report.prediction_count}`);
  }
  if (report.recommendation_count > 0) {
    items.push(`建议 ${report.recommendation_count}`);
  }
  if (report.review_count > 0) {
    items.push(`复盘 ${report.review_count}`);
  }
  if (report.auto_execution_count > 0) {
    items.push(`自动执行 ${report.auto_execution_count}`);
  }
  return items;
}

function formatTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(parsed);
}

export default function ReportsPage() {
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadReports = useCallback(async () => {
    setLoading(true);
    try {
      setError(null);
      const payload = await request<ReportItem[]>("/runtime-center/reports");
      setReports(Array.isArray(payload) ? payload : []);
    } catch (fetchError) {
      setError(
        fetchError instanceof Error ? fetchError.message : String(fetchError),
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadReports();
  }, [loadReports]);
  const activeReports = reports.filter((report) => hasWindowActivity(report)).length;
  const totalEvidence = reports.reduce(
    (sum, report) => sum + report.evidence_count,
    0,
  );

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }} className="page-container">
      <PageHeader
        eyebrow="报告"
        title="报告中心"
        description="汇总日报、周报、月报窗口内的运行事实、关键亮点和指标变化。"
        stats={[
          { label: "报告窗口", value: String(reports.length).padStart(2, "0") },
          { label: "活跃窗口", value: String(activeReports).padStart(2, "0") },
          { label: "证据累计", value: String(totalEvidence).padStart(2, "0") },
        ]}
        actions={(
          <Button icon={<ReloadOutlined />} onClick={() => void loadReports()}>
            刷新
          </Button>
        )}
      />

      <Alert type="info" showIcon message="报告数据来自运行中心汇总视图。" />
      {error ? <Alert type="error" showIcon message={error} /> : null}
      {loading ? (
        <Card>
          <Spin />
        </Card>
      ) : reports.length === 0 ? (
        <Card>
          <Empty description="暂无报告" />
        </Card>
      ) : (
        <Row gutter={[16, 16]}>
          {reports.map((report) => (
            <Col xs={24} xl={8} key={report.id}>
              <Card title={localizeReportTitle(report.window)}>
                <Paragraph>{buildReportSummary(report)}</Paragraph>
                <Descriptions
                  size="small"
                  column={1}
                  bordered
                  items={[
                    {
                      key: "range",
                      label: "统计窗口",
                      children: `${formatTime(report.since)} -> ${formatTime(
                        report.until,
                      )}`,
                    },
                    {
                      key: "status",
                      label: "任务状态",
                      children:
                        Object.entries(report.task_status_counts)
                          .map(
                            ([key, value]) => `${localizeTaskStatus(key)}: ${value}`,
                          )
                          .join(", ") || "本窗口暂无任务活动",
                    },
                  ]}
                />
                {hasWindowActivity(report) ? (
                  <>
                    <Space wrap style={{ marginTop: 12, marginBottom: 32 }}>
                      <Tag>任务 {report.task_count}</Tag>
                      <Tag>执行位 {report.agent_count}</Tag>
                      <Tag>证据 {report.evidence_count}</Tag>
                      <Tag>提案 {report.proposal_count}</Tag>
                      <Tag>补丁 {report.patch_count}</Tag>
                      <Tag>已应用 {report.applied_patch_count}</Tag>
                      <Tag>决策 {report.decision_count}</Tag>
                      <Tag>预测 {report.prediction_count}</Tag>
                      <Tag>建议 {report.recommendation_count}</Tag>
                      <Tag>复盘 {report.review_count}</Tag>
                      <Tag>自动执行 {report.auto_execution_count}</Tag>
                    </Space>
                    <List
                      size="small"
                      header="亮点"
                      style={{ marginTop: 12 }}
                      dataSource={buildReportHighlights(report)}
                      renderItem={(item) => <List.Item>{item}</List.Item>}
                    />
                    <List
                      size="small"
                      header="指标"
                      style={{ marginTop: 12 }}
                      dataSource={report.metrics.map((metric) =>
                        localizeReportMetric(metric),
                      )}
                      renderItem={(metric) => (
                        <List.Item>
                          <Space direction="vertical" size={2}>
                            <Space>
                              <Text strong>{metric.label}</Text>
                              <Tag color="processing">{metric.display_value}</Tag>
                            </Space>
                            {metric.formula ? (
                              <Text type="secondary">
                                计算方式：{metric.formula}
                              </Text>
                            ) : null}
                            {metric.source_summary ? (
                              <Text type="secondary">
                                数据来源：{metric.source_summary}
                              </Text>
                            ) : null}
                          </Space>
                        </List.Item>
                      )}
                    />
                  </>
                ) : (
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description="本统计窗口暂无可展示内容"
                    style={{ marginTop: 16 }}
                  />
                )}
              </Card>
            </Col>
          ))}
        </Row>
      )}
    </Space>
  );
}
