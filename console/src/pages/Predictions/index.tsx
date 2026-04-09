import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Empty,
  Form,
  Input,
  InputNumber,
  List,
  Modal,
  Row,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import api from "../../api";
import type {
  PredictionCaseDetail,
  PredictionCaseSummary,
  PredictionDecisionRecord,
  PredictionRecommendationView,
} from "../../api/modules/predictions";
import { runtimeRiskLabel } from "../../runtime/tagSemantics";
import {
  presentCapabilityLabel,
  presentInsightCaseKind,
  presentInsightRecommendationType,
  presentInsightScenarioKind,
  presentInsightSourceKind,
  presentInsightStatsEntries,
  presentInsightStatusLabel,
  presentInsightText,
} from "../Insights/presentation";
import { RecommendationOptimizationMeta } from "../Insights/RecommendationOptimizationMeta";
import { PageHeader } from "../../components/PageHeader";

const { Paragraph, Text, Title } = Typography;

const DIRECTION_LABELS: Record<string, string> = {
  positive: "正向",
  negative: "负向",
  neutral: "中性",
};

const OUTCOME_LABELS: Record<string, string> = {
  unknown: "待定",
  hit: "命中",
  partial: "部分命中",
  miss: "未命中",
};

function formatTime(value?: string | null): string {
  if (!value) {
    return "-";
  }
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

function statusColor(status?: string | null) {
  if (!status) {
    return "default";
  }
  if (["executed", "approved", "hit"].includes(status)) {
    return "success";
  }
  if (["failed", "rejected", "miss"].includes(status)) {
    return "error";
  }
  if (["open", "proposed"].includes(status)) {
    return "processing";
  }
  if (
    [
      "waiting-confirm",
      "throttled",
      "queued",
      "manual-only",
      "partial",
      "reviewing",
    ].includes(status)
  ) {
    return "warning";
  }
  return "default";
}

function directionColor(direction?: string | null) {
  if (direction === "positive") {
    return "success";
  }
  if (direction === "negative") {
    return "error";
  }
  return "default";
}

function readString(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed || null;
}

function readStringArrayCount(value: unknown): number {
  if (!Array.isArray(value)) {
    return 0;
  }
  return value
    .map((item) => readString(item))
    .filter((item): item is string => Boolean(item)).length;
}

function readRecordCount(value: unknown): number {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return 0;
  }
  return Object.keys(value as Record<string, unknown>).length;
}

function isFrontendRoute(route?: string | null): route is string {
  return typeof route === "string" && route.startsWith("/") && !route.startsWith("/api/");
}

function getDecisionPreferredRoute(
  decision?: PredictionDecisionRecord | null,
): string | null {
  if (!decision) {
    return null;
  }
  if (isFrontendRoute(decision.preferred_route)) {
    return decision.preferred_route;
  }
  if (isFrontendRoute(decision.chat_route)) {
    return decision.chat_route;
  }
  return null;
}

function canCoordinateRecommendation(
  item: Pick<PredictionRecommendationView, "recommendation" | "routes">,
): boolean {
  return Boolean(readString(item.routes?.coordinate));
}

function presentRecommendationActionKind(actionKind?: string | null): string {
  const normalized = readString(actionKind);
  if (normalized === "manual:coordinate-main-brain") {
    return "主脑协调";
  }
  return normalized || "-";
}

export { canCoordinateRecommendation, presentRecommendationActionKind };

export default function PredictionsPage() {
  const navigate = useNavigate();
  const [cases, setCases] = useState<PredictionCaseSummary[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [detail, setDetail] = useState<PredictionCaseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reviewTarget, setReviewTarget] = useState<
    PredictionRecommendationView | "case" | null
  >(null);
  const [busyRecommendationId, setBusyRecommendationId] = useState<
    string | null
  >(null);
  const [reviewForm] = Form.useForm();

  const statusLabel = useCallback(
    (status?: string | null) => presentInsightStatusLabel(status),
    [],
  );
  const caseKindLabel = useCallback(
    (kind?: string | null) => presentInsightCaseKind(kind),
    [],
  );
  const scenarioKindLabel = useCallback(
    (kind?: string | null) => presentInsightScenarioKind(kind),
    [],
  );
  const directionLabel = useCallback(
    (direction?: string | null) =>
      direction ? DIRECTION_LABELS[direction] || direction : "-",
    [],
  );
  const riskLevelLabel = useCallback(
    (level?: string | null) => (level ? runtimeRiskLabel(level) || level : "-"),
    [],
  );
  const recommendationTypeLabel = useCallback(
    (type?: string | null) => presentInsightRecommendationType(type),
    [],
  );
  const outcomeLabel = useCallback(
    (outcome: string) => OUTCOME_LABELS[outcome] || outcome,
    [],
  );

  const loadCases = useCallback(async () => {
    setLoading(true);
    try {
      setError(null);
      const payload = await api.listPredictions({
        limit: 50,
        case_kind: "cycle",
      });
      setCases(payload);
      const nextCaseId =
        selectedCaseId &&
        payload.some((item) => item.case.case_id === selectedCaseId)
          ? selectedCaseId
          : payload[0]?.case.case_id ?? null;
      setSelectedCaseId(nextCaseId);
    } catch (fetchError) {
      setError(
        fetchError instanceof Error ? fetchError.message : String(fetchError),
      );
    } finally {
      setLoading(false);
    }
  }, [selectedCaseId]);

  const loadDetail = useCallback(async (caseId: string) => {
    setDetailLoading(true);
    try {
      const payload = await api.getPredictionCase(caseId);
      setDetail(payload);
    } catch (fetchError) {
      setError(
        fetchError instanceof Error ? fetchError.message : String(fetchError),
      );
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCases();
  }, [loadCases]);

  useEffect(() => {
    if (selectedCaseId) {
      void loadDetail(selectedCaseId);
      return;
    }
    setDetail(null);
  }, [selectedCaseId, loadDetail]);

  const handleCoordinateRecommendation = async (recommendationId: string) => {
    if (!detail) {
      return;
    }
    setBusyRecommendationId(recommendationId);
    try {
      const payload = await api.coordinatePredictionRecommendation(
        detail.case.case_id,
        recommendationId,
        { actor: "copaw-operator" },
      );
      setDetail(payload.detail);
      await loadCases();
      message.success(
        payload.summary || "\u5df2\u4ea4\u7ed9\u4e3b\u8111\u5904\u7406\u3002",
      );
      if (payload.chat_route && isFrontendRoute(payload.chat_route)) {
        navigate(payload.chat_route);
      }
    } catch (submitError) {
      message.error(
        submitError instanceof Error
          ? submitError.message
          : String(submitError),
      );
    } finally {
      setBusyRecommendationId(null);
    }
  };

  const openCaseReviewModal = () => {
    reviewForm.setFieldsValue({
      recommendation_id: undefined,
      reviewer: "main-brain-operator",
      outcome: "unknown",
      adopted: undefined,
      benefit_score: undefined,
      summary: undefined,
    });
    setReviewTarget("case");
  };

  const openRecommendationReviewModal = (
    recommendationView: PredictionRecommendationView,
  ) => {
    reviewForm.setFieldsValue({
      recommendation_id: recommendationView.recommendation.recommendation_id,
      reviewer: "main-brain-operator",
      outcome: "unknown",
      adopted: undefined,
      benefit_score: undefined,
      summary: undefined,
    });
    setReviewTarget(recommendationView);
  };

  const handleCreateReview = async () => {
    if (!detail) {
      return;
    }
    try {
      const values = await reviewForm.validateFields();
      const payload = await api.addPredictionReview(
        detail.case.case_id,
        values,
      );
      setDetail(payload);
      setReviewTarget(null);
      reviewForm.resetFields();
      await loadCases();
      message.success("周期复盘已保存。");
    } catch (submitError) {
      if (submitError instanceof Error) {
        message.error(submitError.message);
      }
    }
  };

  const openCaseCount = cases.filter((item) =>
    ["open", "reviewing"].includes(item.case.status),
  ).length;
  const pendingDecisionCount = cases.reduce(
    (total, item) => total + item.pending_decision_count,
    0,
  );
  const totalOpportunityCount = cases.reduce(
    (total, item) => total + item.recommendation_count,
    0,
  );
  const reviewedCaseCount = cases.filter((item) => item.review_count > 0).length;
  const latestUpdatedAt = cases[0]?.case.updated_at ?? null;

  const cycleId = readString(detail?.case.metadata?.cycle_id);
  const triggerSource = readString(detail?.case.metadata?.trigger_source);
  const triggerActor = readString(detail?.case.metadata?.trigger_actor);
  const pendingReportCount = readStringArrayCount(
    detail?.case.metadata?.pending_report_ids,
  );
  const openBacklogCount = readStringArrayCount(
    detail?.case.metadata?.open_backlog_ids,
  );
  const goalStatusCount = readRecordCount(detail?.case.metadata?.goal_statuses);
  const meetingWindow = readString(detail?.case.metadata?.meeting_window);
  const reviewDateLocal = readString(detail?.case.metadata?.review_date_local);
  const participantInputCount = readStringArrayCount(
    detail?.case.metadata?.participant_inputs,
  );
  const assignmentSummaryCount = readStringArrayCount(
    detail?.case.metadata?.assignment_summaries,
  );
  const laneSummaryCount = readStringArrayCount(
    detail?.case.metadata?.lane_summaries,
  );

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }} className="page-container">
      <PageHeader
        eyebrow="晨晚复盘"
        title="主脑晨会 / 晚会复盘中心"
        description="这里只展示由主脑运行周期自动生成的正式复盘案例。这里不是独立预测开关，而是主脑晨会 / 晚会统一查看周期、回流、待办与决策机会的入口。"
        stats={[
          { label: "复盘案例", value: String(cases.length).padStart(2, "0") },
          { label: "待完成", value: String(openCaseCount).padStart(2, "0") },
          { label: "待决策", value: String(pendingDecisionCount).padStart(2, "0") },
          { label: "已归档", value: String(reviewedCaseCount).padStart(2, "0") },
        ]}
        aside={
          latestUpdatedAt ? (
            <Text type="secondary">{`最近更新 ${formatTime(latestUpdatedAt)}`}</Text>
          ) : null
        }
        actions={(
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => void loadCases()}>
              刷新
            </Button>
          </Space>
        )}
      />

      <Alert
        type="info"
        showIcon
        message="预测中心已升级为主脑正式复盘中心"
        description={
          <Space direction="vertical" size={2}>
            <Text>
              案例由主脑运行周期自动生成，当前正式窗口只有晨会复盘和晚会复盘。
            </Text>
            <Text>
              推荐动作执行后统一进入正式决策主链，再回流待办、派工与下一轮周期。
            </Text>
            <Text>
              如果这里暂时为空，说明当前还没有新的复盘事实，而不是前台开关没有打开。
            </Text>
          </Space>
        }
      />

      {error ? <Alert type="error" showIcon message={error} /> : null}

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} xl={6}>
          <Card size="small">
            <Space direction="vertical" size={4}>
              <Text type="secondary">复盘案例</Text>
              <Title level={3} style={{ margin: 0 }}>
                {cases.length}
              </Title>
            </Space>
          </Card>
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <Card size="small">
            <Space direction="vertical" size={4}>
              <Text type="secondary">待完成复盘</Text>
              <Title level={3} style={{ margin: 0 }}>
                {openCaseCount}
              </Title>
            </Space>
          </Card>
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <Card size="small">
            <Space direction="vertical" size={4}>
              <Text type="secondary">主脑机会</Text>
              <Title level={3} style={{ margin: 0 }}>
                {totalOpportunityCount}
              </Title>
              <Text type="secondary">待决策 {pendingDecisionCount}</Text>
            </Space>
          </Card>
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <Card size="small">
            <Space direction="vertical" size={4}>
              <Text type="secondary">已归档复盘</Text>
              <Title level={3} style={{ margin: 0 }}>
                {reviewedCaseCount}
              </Title>
              <Text type="secondary">最近更新 {formatTime(latestUpdatedAt)}</Text>
            </Space>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={8}>
          <Card title="复盘案例" extra={<Tag>{cases.length}</Tag>}>
            {loading ? (
              <Spin />
            ) : cases.length === 0 ? (
              <Empty description="当前还没有主脑晨会 / 晚会复盘案例。" />
            ) : (
              <List
                itemLayout="vertical"
                dataSource={cases}
                renderItem={(item) => {
                  const itemCycleId = readString(item.case.metadata?.cycle_id);
                  const itemMeetingWindow = readString(
                    item.case.metadata?.meeting_window,
                  );
                  const itemReviewDateLocal = readString(
                    item.case.metadata?.review_date_local,
                  );
                  return (
                    <List.Item
                      key={item.case.case_id}
                      style={{
                        cursor: "pointer",
                        borderRadius: 12,
                        padding: 12,
                        background:
                          item.case.case_id === selectedCaseId
                            ? "rgba(22, 119, 255, 0.06)"
                            : "transparent",
                      }}
                      onClick={() => setSelectedCaseId(item.case.case_id)}
                    >
                      <Space
                        direction="vertical"
                        size={6}
                        style={{ width: "100%" }}
                      >
                        <Space wrap>
                          <Text strong>
                            {presentInsightText(item.case.title) ||
                              "未命名周期案例"}
                          </Text>
                          <Tag color={statusColor(item.case.status)}>
                            {statusLabel(item.case.status)}
                          </Tag>
                          <Tag>{caseKindLabel(item.case.case_kind)}</Tag>
                          {itemCycleId ? <Tag>周期 {itemCycleId}</Tag> : null}
                          {itemMeetingWindow ? <Tag>{itemMeetingWindow}</Tag> : null}
                          {itemReviewDateLocal ? (
                            <Tag>{`Review ${itemReviewDateLocal}`}</Tag>
                          ) : null}
                          {item.pending_decision_count > 0 ? (
                            <Tag color="warning">
                              待决策 {item.pending_decision_count}
                            </Tag>
                          ) : null}
                        </Space>
                        <Text type="secondary">
                          {presentInsightText(
                            item.case.summary || item.case.question,
                          )}
                        </Text>
                        <Space wrap size={4}>
                          <Tag>场景 {item.scenario_count}</Tag>
                          <Tag>信号 {item.signal_count}</Tag>
                          <Tag>机会 {item.recommendation_count}</Tag>
                          <Tag>复盘 {item.review_count}</Tag>
                        </Space>
                        <Text type="secondary">
                          {formatTime(item.case.updated_at)}
                        </Text>
                      </Space>
                    </List.Item>
                  );
                }}
              />
            )}
          </Card>
        </Col>

        <Col xs={24} xl={16}>
          <Card
            title={presentInsightText(detail?.case.title) || "主脑复盘详情"}
            extra={
              detail ? (
                <Space wrap>
                  <Tag color={statusColor(detail.case.status)}>
                    {statusLabel(detail.case.status)}
                  </Tag>
                  <Tag>{caseKindLabel(detail.case.case_kind)}</Tag>
                  {cycleId ? <Tag>周期 {cycleId}</Tag> : null}
                  {meetingWindow ? <Tag>{meetingWindow}</Tag> : null}
                  {reviewDateLocal ? <Tag>{`Review ${reviewDateLocal}`}</Tag> : null}
                  <Tag>
                    置信度 {(detail.case.overall_confidence * 100).toFixed(0)}%
                  </Tag>
                  <Button onClick={openCaseReviewModal}>新增复盘</Button>
                </Space>
              ) : null
            }
          >
            {detailLoading ? (
              <Spin />
            ) : !detail ? (
              <Empty description="选择一个复盘案例查看主脑机会、场景与复盘。" />
            ) : (
              <Space direction="vertical" size={16} style={{ width: "100%" }}>
                <Descriptions
                  size="small"
                  column={2}
                  bordered
                  items={[
                    {
                      key: "question",
                      label: "复盘问题",
                      children: presentInsightText(detail.case.question) || "-",
                    },
                    {
                      key: "scope",
                      label: "归属范围",
                      children:
                        presentInsightText(detail.case.owner_scope) || "全局",
                    },
                    {
                      key: "instance",
                      label: "行业实例",
                      children: detail.case.industry_instance_id || "-",
                    },
                    {
                      key: "window",
                      label: "观察窗口",
                      children: `${detail.case.time_window_days} 天`,
                    },
                    {
                      key: "updated",
                      label: "最近更新",
                      children: formatTime(detail.case.updated_at),
                    },
                    {
                      key: "meeting-window",
                      label: "正式窗口",
                      children: meetingWindow || "-",
                    },
                    {
                      key: "review-date",
                      label: "复盘日期",
                      children: reviewDateLocal || "-",
                    },
                    {
                      key: "actor",
                      label: "触发 actor",
                      children: triggerActor || "-",
                    },
                  ]}
                />

                <Card size="small" title="主脑复盘输入">
                  <Space wrap size={[8, 8]}>
                    {cycleId ? <Tag>当前周期 {cycleId}</Tag> : null}
                    {triggerSource ? <Tag>来源 {triggerSource}</Tag> : null}
                    {meetingWindow ? <Tag>{meetingWindow}</Tag> : null}
                    <Tag>待处理汇报 {pendingReportCount}</Tag>
                    <Tag>未消化待办 {openBacklogCount}</Tag>
                    <Tag>焦点状态面 {goalStatusCount}</Tag>
                    <Tag>参与输入 {participantInputCount}</Tag>
                    <Tag>派单摘要 {assignmentSummaryCount}</Tag>
                    <Tag>泳道摘要 {laneSummaryCount}</Tag>
                  </Space>
                  <Paragraph
                    type="secondary"
                    style={{ marginTop: 12, marginBottom: 0 }}
                  >
                    运营周期会把当前周期、回流、派单、泳道与待办快照固化成正式晨会 /
                    晚会复盘案例，供主脑统一决策。
                  </Paragraph>
                </Card>

                <Space wrap>
                  {presentInsightStatsEntries(detail.stats).map(
                    ({ key, label, value }) => (
                      <Tag key={key}>
                        {label}: {value}
                      </Tag>
                    ),
                  )}
                </Space>

                <Card size="small" title="场景对比">
                  {detail.scenarios.length === 0 ? (
                    <Empty description="当前没有场景对比结果。" />
                  ) : (
                    <Row gutter={[12, 12]}>
                      {detail.scenarios.map((scenario) => (
                        <Col xs={24} md={8} key={scenario.scenario_id}>
                          <Card size="small">
                            <Space direction="vertical" size={6}>
                              <Space wrap>
                                <Text strong>
                                  {presentInsightText(scenario.title) ||
                                    "未命名场景"}
                                </Text>
                                <Tag>
                                  {scenarioKindLabel(scenario.scenario_kind)}
                                </Tag>
                                <Tag>
                                  {(scenario.confidence * 100).toFixed(0)}%
                                </Tag>
                              </Space>
                              <Text type="secondary">
                                {presentInsightText(scenario.summary)}
                              </Text>
                              <Space wrap size={4}>
                                <Tag>焦点 {scenario.goal_delta}</Tag>
                                <Tag>负载 {scenario.task_load_delta}</Tag>
                                <Tag>风险 {scenario.risk_delta}</Tag>
                              </Space>
                            </Space>
                          </Card>
                        </Col>
                      ))}
                    </Row>
                  )}
                </Card>

                <Card size="small" title="信号">
                  {detail.signals.length === 0 ? (
                    <Empty description="当前没有信号。" />
                  ) : (
                    <List
                      size="small"
                      dataSource={detail.signals}
                      renderItem={(signal) => (
                        <List.Item key={signal.signal_id}>
                          <Space
                            direction="vertical"
                            size={4}
                            style={{ width: "100%" }}
                          >
                            <Space wrap>
                              <Text strong>
                                {presentInsightText(signal.label) ||
                                  "未命名信号"}
                              </Text>
                              <Tag color={directionColor(signal.direction)}>
                                {directionLabel(signal.direction)}
                              </Tag>
                              <Tag>
                                {presentInsightSourceKind(signal.source_kind)}
                              </Tag>
                              <Tag>{Math.round(signal.strength * 100)}%</Tag>
                            </Space>
                            <Text type="secondary">
                              {presentInsightText(signal.summary)}
                            </Text>
                          </Space>
                        </List.Item>
                      )}
                    />
                  )}
                </Card>

                <Card size="small" title="主脑机会">
                  {detail.recommendations.length === 0 ? (
                    <Empty description="当前没有新的主脑机会。" />
                  ) : (
                    <List
                      itemLayout="vertical"
                      dataSource={detail.recommendations}
                      renderItem={(item) => (
                        <List.Item
                          key={item.recommendation.recommendation_id}
                          actions={[
                            item.decision?.requires_human_confirmation &&
                            getDecisionPreferredRoute(item.decision) ? (
                              <Button
                                key="chat-confirm"
                                size="small"
                                onClick={() =>
                                  navigate(
                                    getDecisionPreferredRoute(item.decision) as string,
                                  )
                                }
                              >
                                去聊天确认
                              </Button>
                            ) : null,
                            canCoordinateRecommendation(item) ? (
                              <Button
                                key="execute"
                                type="primary"
                                size="small"
                                loading={
                                  busyRecommendationId ===
                                  item.recommendation.recommendation_id
                                }
                                onClick={() =>
                                  void handleCoordinateRecommendation(
                                    item.recommendation.recommendation_id,
                                  )
                                }
                              >
                                交给主脑
                              </Button>
                            ) : (
                              <Button
                                key="review"
                                size="small"
                                onClick={() =>
                                  openRecommendationReviewModal(item)
                                }
                              >
                                记录复盘
                              </Button>
                            ),
                          ]}
                        >
                          <Space
                            direction="vertical"
                            size={4}
                            style={{ width: "100%" }}
                          >
                            <Space wrap>
                              <Text strong>
                                {presentInsightText(
                                  item.recommendation.title,
                                ) || "未命名机会"}
                              </Text>
                              <Tag
                                color={statusColor(
                                  item.recommendation.status,
                                )}
                              >
                                {statusLabel(item.recommendation.status)}
                              </Tag>
                              <Tag>
                                {recommendationTypeLabel(
                                  item.recommendation.recommendation_type,
                                )}
                              </Tag>
                              <Tag>
                                {riskLevelLabel(item.recommendation.risk_level)}
                              </Tag>
                              <Tag>
                                {presentRecommendationActionKind(
                                  item.recommendation.action_kind,
                                )}
                              </Tag>
                              {item.recommendation.decision_request_id ? (
                                <Tag color="warning">
                                  决策 {item.recommendation.decision_request_id}
                                </Tag>
                              ) : null}
                              {item.decision?.requested_by === "copaw-main-brain" ? (
                                <Tag color="geekblue">主脑裁决</Tag>
                              ) : null}
                              {item.decision?.requires_human_confirmation ? (
                                <Tag color="orange">需人类确认</Tag>
                              ) : null}
                            </Space>
                            <Text type="secondary">
                              {presentInsightText(
                                item.recommendation.summary,
                              )}
                            </Text>
                            <Space wrap size={4}>
                              <Tag>优先级 {item.recommendation.priority}</Tag>
                              <Tag>
                                置信度{" "}
                                {(
                                  item.recommendation.confidence * 100
                                ).toFixed(0)}
                                %
                              </Tag>
                              {item.recommendation.target_capability_ids.map(
                                (capabilityId) => (
                                  <Tag key={capabilityId}>
                                    {presentCapabilityLabel(capabilityId)}
                                  </Tag>
                                ),
                              )}
                            </Space>
                            <RecommendationOptimizationMeta
                              recommendation={item.recommendation}
                            />
                          </Space>
                        </List.Item>
                      )}
                    />
                  )}
                </Card>

                <Card size="small" title="复盘">
                  {detail.reviews.length === 0 ? (
                    <Empty description="当前还没有周期复盘记录。" />
                  ) : (
                    <List
                      size="small"
                      dataSource={detail.reviews}
                      renderItem={(review) => (
                        <List.Item key={review.review_id}>
                          <Space
                            direction="vertical"
                            size={4}
                            style={{ width: "100%" }}
                          >
                            <Space wrap>
                              <Text strong>
                                {presentInsightText(review.reviewer) || "复盘"}
                              </Text>
                              <Tag color={statusColor(review.outcome)}>
                                {outcomeLabel(review.outcome)}
                              </Tag>
                              {typeof review.benefit_score === "number" ? (
                                <Tag>{review.benefit_score}</Tag>
                              ) : null}
                            </Space>
                            <Text type="secondary">
                              {presentInsightText(review.summary)}
                            </Text>
                          </Space>
                        </List.Item>
                      )}
                    />
                  )}
                </Card>
              </Space>
            )}
          </Card>
        </Col>
      </Row>

      <Modal
        open={reviewTarget !== null}
        title={reviewTarget === "case" ? "新增周期复盘" : "复盘主脑机会"}
        onCancel={() => {
          setReviewTarget(null);
          reviewForm.resetFields();
        }}
        onOk={() => void handleCreateReview()}
        okText="保存"
      >
        <Form form={reviewForm} layout="vertical">
          <Form.Item name="recommendation_id" hidden>
            <Input />
          </Form.Item>
          <Form.Item
            name="reviewer"
            label="复盘人"
            initialValue="main-brain-operator"
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="outcome"
            label="结果"
            rules={[{ required: true }]}
            initialValue="unknown"
          >
            <Select
              options={[
                { value: "unknown", label: outcomeLabel("unknown") },
                { value: "hit", label: outcomeLabel("hit") },
                { value: "partial", label: outcomeLabel("partial") },
                { value: "miss", label: outcomeLabel("miss") },
              ]}
            />
          </Form.Item>
          <Form.Item name="adopted" label="是否采纳">
            <Select
              allowClear
              options={[
                { value: true, label: "是" },
                { value: false, label: "否" },
              ]}
            />
          </Form.Item>
          <Form.Item name="benefit_score" label="收益分">
            <InputNumber min={0} max={1} step={0.1} style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="summary" label="摘要" rules={[{ required: true }]}>
            <Input.TextArea rows={4} />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
