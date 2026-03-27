import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Card,
  Descriptions,
  Empty,
  List,
  Space,
  Spin,
  Tag,
  Timeline,
  Tooltip,
  Typography,
} from "antd";
import {
  BarChartOutlined,
  BulbOutlined,
  CalendarOutlined,
  CheckCircleOutlined,
  FileTextOutlined,
  ReloadOutlined,
  RiseOutlined,
  ToolOutlined,
} from "@ant-design/icons";
import {
  agentReportsText,
  commonText,
  getChangeTypeLabel,
  getRiskLabel,
  getStatusLabel,
} from "./copy";
import { localizeWorkbenchText } from "./localize";
import { request } from "../../api";
import {
  runtimeRiskColor,
  runtimeStatusColor,
} from "../../runtime/tagSemantics";

const { Paragraph, Text } = Typography;

const CAPABILITY_LABELS: Record<string, string> = {
  "system:dispatch_query": "智能体协作分派",
  "tool:execute_shell_command": "命令行执行",
  "system:run_learning_strategy": "系统自我优化",
};

const CAPABILITY_IMPACTS: Record<string, string> = {
  "system:dispatch_query": "智能体之间分派查询、协作拿结果",
  "tool:execute_shell_command": "在工作机上执行命令、脚本和检查动作",
  "system:run_learning_strategy": "系统自动复盘、自我修复和优化",
};

function extractCapabilityRef(
  ...values: Array<string | null | undefined>
): string | null {
  for (const value of values) {
    if (!value) {
      continue;
    }
    const match = value.match(/\b(?:system|tool|mcp|learning):[a-z0-9._-]+\b/i);
    if (match) {
      return match[0];
    }
  }
  return null;
}

function humanizeCapabilityRef(capabilityRef: string | null): string {
  if (!capabilityRef) {
    return "系统功能";
  }
  return (
    CAPABILITY_LABELS[capabilityRef] ||
    capabilityRef
      .replace(/^[^:]+:/, "")
      .replace(/[_-]+/g, " ")
      .trim()
  );
}

function capabilityImpact(capabilityRef: string | null): string | null {
  if (!capabilityRef) {
    return null;
  }
  return CAPABILITY_IMPACTS[capabilityRef] || null;
}

function summarizeTechnicalError(
  errorText: string | null | undefined,
  capabilityRef: string | null,
): string | null {
  if (!errorText) {
    return null;
  }
  if (errorText.includes("Query was cancelled before completion")) {
    return "执行在完成前被中断，结果没有成功回流。";
  }
  if (errorText.includes("_TOOL_EXECUTORS") && errorText.includes("not defined")) {
    return "内部执行器注册异常，导致自动优化或自动推进流程无法继续。";
  }
  if (
    capabilityRef === "tool:execute_shell_command" &&
    /python\s+-\s*<<["']?PY["']?/i.test(errorText)
  ) {
    return "命令写法与当前终端不兼容，脚本实际上没有成功执行。";
  }
  if (errorText.includes("returned non-zero exit status 1")) {
    return "命令执行失败并提前退出。";
  }
  return localizeWorkbenchText(errorText);
}

function presentLearningHandlingMode(riskLevel: string): string {
  if (riskLevel === "confirm") {
    return agentReportsText.userFacingHandledConfirm;
  }
  if (riskLevel === "guarded") {
    return agentReportsText.userFacingHandledGuarded;
  }
  return agentReportsText.userFacingHandledAuto;
}

function presentProposalStatus(status: string): string {
  if (status === "open") {
    return "已发现";
  }
  if (status === "accepted") {
    return "已采纳";
  }
  if (status === "deferred") {
    return "稍后处理";
  }
  if (status === "rejected") {
    return "已忽略";
  }
  return getStatusLabel(status);
}

function presentProposalTitle(proposal: Proposal): string {
  const capabilityRef = extractCapabilityRef(proposal.title, proposal.description);
  const capabilityName = humanizeCapabilityRef(capabilityRef);
  if (/^Reduce failures for /i.test(proposal.title)) {
    return `提升“${capabilityName}”稳定性`;
  }
  if (/^Mitigate failures for /i.test(proposal.title)) {
    return `修复“${capabilityName}”异常`;
  }
  return localizeWorkbenchText(proposal.title);
}

function presentProposalSummary(proposal: Proposal): {
  summary: string;
  impact: string | null;
  symptom: string | null;
} {
  const capabilityRef = extractCapabilityRef(proposal.title, proposal.description);
  const capabilityName = humanizeCapabilityRef(capabilityRef);
  const impact = capabilityImpact(capabilityRef);
  const detectedFailure = proposal.description.match(
    /^Detected (\d+) failed execution\(s\) for (.+?)\. Recent errors: (.+)\.$/i,
  );
  if (detectedFailure) {
    const count = detectedFailure[1];
    const symptom = summarizeTechnicalError(detectedFailure[3], capabilityRef);
    return {
      summary: `系统发现“${capabilityName}”近期失败 ${count} 次，正在准备稳定性修复。`,
      impact,
      symptom,
    };
  }
  return {
    summary: localizeWorkbenchText(proposal.description),
    impact,
    symptom: null,
  };
}

function presentPatchTitle(patch: PatchItem): string {
  const capabilityRef = extractCapabilityRef(patch.title, patch.description);
  const capabilityName = humanizeCapabilityRef(capabilityRef);
  if (/^Mitigate failures for /i.test(patch.title)) {
    return `已为“${capabilityName}”执行稳定性修复`;
  }
  return localizeWorkbenchText(patch.title);
}

function presentPatchSummary(patch: PatchItem): {
  summary: string;
  impact: string | null;
} {
  const capabilityRef = extractCapabilityRef(patch.title, patch.description);
  const capabilityName = humanizeCapabilityRef(capabilityRef);
  const impact = capabilityImpact(capabilityRef);
  if (/^Introduce guardrails and retries for /i.test(patch.description)) {
    return {
      summary: `系统已为“${capabilityName}”增加防护和重试，降低偶发失败对运行的影响。`,
      impact,
    };
  }
  return {
    summary: localizeWorkbenchText(patch.description),
    impact,
  };
}

interface GrowthEvent {
  id: string;
  agent_id: string;
  change_type: string;
  description: string;
  source_patch_id: string | null;
  risk_level: string;
  result: string;
  created_at: string;
}

interface Proposal {
  id: string;
  title: string;
  description: string;
  source_agent_id: string;
  status: string;
  created_at: string;
}

interface PatchItem {
  id: string;
  kind: string;
  title: string;
  description: string;
  status: string;
  risk_level: string;
  applied_at: string | null;
  created_at: string;
}

interface EvidenceItem {
  id: string;
  task_id?: string | null;
  action_summary: string;
  result_summary: string;
  risk_level: string;
  environment_ref: string | null;
  capability_ref: string | null;
  created_at: string | null;
}

interface ReportData {
  events: GrowthEvent[];
  proposals: Proposal[];
  patches: PatchItem[];
  evidence: EvidenceItem[];
}

type FormalReportWindow = "daily" | "weekly";

interface FormalReportMetric {
  key: string;
  label: string;
  display_value: string;
}

interface FormalReportTaskDigest {
  task_id: string;
  title: string;
  summary: string;
  status: string;
  runtime_status?: string | null;
  current_phase?: string | null;
  last_result_summary?: string | null;
  last_error_summary?: string | null;
  updated_at?: string | null;
  route?: string | null;
}

interface FormalReportEvidenceDigest {
  evidence_id: string;
  task_id?: string | null;
  action_summary: string;
  result_summary: string;
  risk_level: string;
  capability_ref?: string | null;
  created_at?: string | null;
}

interface FormalReportRecord {
  id: string;
  title: string;
  summary: string;
  window: FormalReportWindow | "monthly";
  scope_type: string;
  scope_id: string | null;
  since: string;
  until: string;
  highlights: string[];
  metrics: FormalReportMetric[];
  evidence_count: number;
  decision_count: number;
  task_count: number;
  focus_items: string[];
  completed_tasks: FormalReportTaskDigest[];
  key_results: string[];
  primary_evidence: FormalReportEvidenceDigest[];
  blockers: string[];
  next_steps: string[];
}

function formatTime(
  value: string | null | undefined,
  fallback: string,
): string {
  if (!value) {
    return fallback;
  }
  const parsed = new Date(value.endsWith("Z") ? value : `${value}Z`);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

function statusColor(status: string): string {
  return runtimeStatusColor(status);
}

function riskColor(level: string): string {
  return runtimeRiskColor(level);
}

function changeTypeIcon(type: string) {
  if (type.includes("capability")) return <ToolOutlined />;
  if (type.includes("role")) return <BulbOutlined />;
  if (type.includes("patch")) return <CheckCircleOutlined />;
  if (type.includes("performance")) return <RiseOutlined />;
  return <FileTextOutlined />;
}

function parseTimestamp(value: string | null | undefined): number | null {
  if (!value) {
    return null;
  }
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? null : parsed;
}

function recentItems<T>(
  items: T[],
  pickTime: (item: T) => string | null | undefined,
  limit: number,
): T[] {
  return [...items]
    .sort((left, right) => {
      const leftTime = parseTimestamp(pickTime(left)) ?? 0;
      const rightTime = parseTimestamp(pickTime(right)) ?? 0;
      return rightTime - leftTime;
    })
    .slice(0, limit);
}

const REPORT_GROWTH_LIMIT = 50;
const REPORT_PROPOSAL_LIMIT = 50;
const REPORT_PATCH_LIMIT = 50;
const REPORT_EVIDENCE_LIMIT = 50;

function useReportData() {
  const [data, setData] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      setError(null);
      const [events, proposals, patches, evidence] = await Promise.all([
        request<GrowthEvent[]>(
          `/runtime-center/learning/growth?limit=${REPORT_GROWTH_LIMIT}`,
        ),
        request<Proposal[]>(
          `/runtime-center/learning/proposals?limit=${REPORT_PROPOSAL_LIMIT}`,
        ),
        request<PatchItem[]>(
          `/runtime-center/learning/patches?limit=${REPORT_PATCH_LIMIT}`,
        ),
        request<EvidenceItem[]>(
          `/runtime-center/evidence?limit=${REPORT_EVIDENCE_LIMIT}`,
        ),
      ]);
      setData({
        events: Array.isArray(events) ? events : [],
        proposals: Array.isArray(proposals) ? proposals : [],
        patches: Array.isArray(patches) ? patches : [],
        evidence: Array.isArray(evidence) ? evidence : [],
      });
    } catch (fetchError) {
      console.error("Failed to load agent report data", fetchError);
      setError(
        fetchError instanceof Error ? fetchError.message : String(fetchError),
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  return {
    data,
    loading,
    error,
    refresh: fetchData,
  };
}

function RenderError({ error }: { error: string | null }) {
  if (!error) {
    return null;
  }
  return (
    <Alert
      showIcon
      type="error"
      message={agentReportsText.runtimeUnavailable}
      description={error}
      style={{ marginBottom: 32 }}
    />
  );
}

function RenderEmpty({ description }: { description: string }) {
  return <Empty description={description} image={Empty.PRESENTED_IMAGE_SIMPLE} />;
}

function useFormalReport(window: FormalReportWindow, agentId: string | null) {
  const [report, setReport] = useState<FormalReportRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchReport = useCallback(async () => {
    if (!agentId) {
      setReport(null);
      setError(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      setError(null);
      const payload = await request<FormalReportRecord[]>(
        `/runtime-center/reports?window=${window}&scope_type=agent&scope_id=${encodeURIComponent(agentId)}`,
      );
      setReport(Array.isArray(payload) ? payload[0] ?? null : null);
    } catch (fetchError) {
      console.error("Failed to load formal agent report", fetchError);
      setError(
        fetchError instanceof Error ? fetchError.message : String(fetchError),
      );
      setReport(null);
    } finally {
      setLoading(false);
    }
  }, [agentId, window]);

  useEffect(() => {
    void fetchReport();
  }, [fetchReport]);

  return {
    report,
    loading,
    error,
    refresh: fetchReport,
  };
}

function formatDate(value: string | null | undefined, fallback: string): string {
  if (!value) {
    return fallback;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return fallback;
  }
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  }).format(parsed);
}

function metricDisplay(report: FormalReportRecord | null, key: string): string {
  return report?.metrics.find((item) => item.key === key)?.display_value || "-";
}

function ReportStringList({
  title,
  items,
  emptyText,
}: {
  title: string;
  items: string[];
  emptyText: string;
}) {
  return (
    <Card size="small" title={title}>
      {items.length === 0 ? (
        <RenderEmpty description={emptyText} />
      ) : (
        <List
          size="small"
          dataSource={items}
          renderItem={(item) => (
            <List.Item>
              <Text>{localizeWorkbenchText(item)}</Text>
            </List.Item>
          )}
        />
      )}
    </Card>
  );
}

function ReportTaskList({
  title,
  items,
  emptyText,
}: {
  title: string;
  items: FormalReportTaskDigest[];
  emptyText: string;
}) {
  return (
    <Card size="small" title={title}>
      {items.length === 0 ? (
        <RenderEmpty description={emptyText} />
      ) : (
        <List
          size="small"
          dataSource={items}
          renderItem={(item) => (
            <List.Item key={item.task_id}>
              <Space direction="vertical" size={2} style={{ width: "100%" }}>
                <Space wrap>
                  <Text strong>{localizeWorkbenchText(item.title) || item.task_id}</Text>
                  {item.status ? (
                    <Tag color={statusColor(item.status)}>
                      {getStatusLabel(item.status)}
                    </Tag>
                  ) : null}
                  {item.runtime_status ? <Tag>{getStatusLabel(item.runtime_status)}</Tag> : null}
                </Space>
                {item.summary ? (
                  <Text type="secondary">{localizeWorkbenchText(item.summary)}</Text>
                ) : null}
                {item.last_result_summary ? (
                  <Text type="secondary">
                    {localizeWorkbenchText(item.last_result_summary)}
                  </Text>
                ) : null}
                {item.last_error_summary ? (
                  <Text type="secondary">
                    {localizeWorkbenchText(item.last_error_summary)}
                  </Text>
                ) : null}
                <Text type="secondary">
                  {formatTime(item.updated_at, agentReportsText.noTimestamp)}
                </Text>
              </Space>
            </List.Item>
          )}
        />
      )}
    </Card>
  );
}

function ReportEvidenceList({
  title,
  items,
  emptyText,
}: {
  title: string;
  items: FormalReportEvidenceDigest[];
  emptyText: string;
}) {
  return (
    <Card size="small" title={title}>
      {items.length === 0 ? (
        <RenderEmpty description={emptyText} />
      ) : (
        <List
          size="small"
          dataSource={items}
          renderItem={(item) => (
            <List.Item key={item.evidence_id}>
              <Space direction="vertical" size={2} style={{ width: "100%" }}>
                <Space wrap>
                  <Text strong>{localizeWorkbenchText(item.action_summary) || item.evidence_id}</Text>
                  <Tag color={riskColor(item.risk_level)}>
                    {getRiskLabel(item.risk_level)}
                  </Tag>
                </Space>
                {item.result_summary ? (
                  <Text type="secondary">
                    {localizeWorkbenchText(item.result_summary)}
                  </Text>
                ) : null}
                <Text type="secondary">
                  {formatTime(item.created_at, agentReportsText.noTimestamp)}
                </Text>
              </Space>
            </List.Item>
          )}
        />
      )}
    </Card>
  );
}

function AgentFormalReport({
  window,
  agentId,
  agentName,
}: {
  window: FormalReportWindow;
  agentId: string | null;
  agentName: string | null;
}) {
  const { report, loading, error, refresh } = useFormalReport(window, agentId);
  const title =
    window === "daily"
      ? agentReportsText.dailyTitle(
          formatDate(report?.since, formatDate(new Date().toISOString(), "-")),
        )
      : agentReportsText.weeklyTitle(
          formatDate(report?.since, formatDate(new Date().toISOString(), "-")),
        );

  if (!agentId) {
    return <RenderEmpty description={agentReportsText.noAgentSelected} />;
  }

  if (loading) {
    return <Spin />;
  }

  return (
    <Card
      className="baize-card"
      style={{
        background: "rgba(10, 22, 60, 0.45)",
        backdropFilter: "blur(20px)",
        border: "1px solid rgba(201, 168, 76, 0.15)",
        marginBottom: 32,
      }}
      title={
        <Space>
          {window === "daily" ? (
            <CalendarOutlined style={{ color: "#C9A84C" }} />
          ) : (
            <BarChartOutlined style={{ color: "#C9A84C" }} />
          )}
          <span style={{ color: "white" }}>{title}</span>
          {agentName ? <Tag color="blue">{agentName}</Tag> : null}
          <Tooltip title={commonText.refresh}>
            <ReloadOutlined
              onClick={() => {
                void refresh();
              }}
              style={{ cursor: "pointer", fontSize: 14, color: "var(--baize-text-main)" }}
            />
          </Tooltip>
        </Space>
      }
    >
      <RenderError error={error} />
      {!report ? (
        <RenderEmpty description={agentReportsText.noFormalReport} />
      ) : (
        <>
          <Descriptions
            size="small"
            column={2}
            bordered
            items={[
              {
                key: "completed",
                label: agentReportsText.completedTaskCountLabel,
                children: report.completed_tasks.length,
              },
              {
                key: "task-count",
                label: agentReportsText.taskCoverageLabel,
                children: report.task_count,
              },
              {
                key: "evidence",
                label: agentReportsText.evidenceCountLabel,
                children: report.evidence_count,
              },
              {
                key: "decisions",
                label: agentReportsText.decisionCountLabel,
                children: report.decision_count,
              },
              {
                key: "success-rate",
                label: agentReportsText.successRateLabel,
                children: metricDisplay(report, "task_success_rate"),
              },
              {
                key: "exception-rate",
                label: agentReportsText.exceptionRateLabel,
                children: metricDisplay(report, "exception_rate"),
              },
            ]}
          />
          {report.summary ? (
            <Paragraph style={{ marginTop: 16, marginBottom: 12 }}>
              <Text strong>{agentReportsText.reportSummaryLabel}:</Text>{" "}
              {localizeWorkbenchText(report.summary)}
            </Paragraph>
          ) : null}
          <Space wrap size={[8, 8]} style={{ marginBottom: 16 }}>
            {report.focus_items.map((item) => (
              <Tag key={item}>{localizeWorkbenchText(item)}</Tag>
            ))}
          </Space>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
              gap: 16,
            }}
          >
            <ReportTaskList
              title={agentReportsText.completedTasksTitle}
              items={report.completed_tasks}
              emptyText={agentReportsText.noCompletedTasks}
            />
            <ReportStringList
              title={agentReportsText.keyResultsTitle}
              items={report.key_results}
              emptyText={agentReportsText.noKeyResults}
            />
            <ReportEvidenceList
              title={agentReportsText.primaryEvidenceTitle}
              items={report.primary_evidence}
              emptyText={agentReportsText.noPrimaryEvidence}
            />
            <ReportStringList
              title={agentReportsText.blockersTitle}
              items={report.blockers}
              emptyText={agentReportsText.noBlockers}
            />
            <ReportStringList
              title={agentReportsText.nextStepsTitle}
              items={report.next_steps}
              emptyText={agentReportsText.noNextSteps}
            />
          </div>
        </>
      )}
    </Card>
  );
}

export function AgentDailyReport({
  agentId,
  agentName,
}: {
  agentId: string | null;
  agentName: string | null;
}) {
  return <AgentFormalReport window="daily" agentId={agentId} agentName={agentName} />;
}

export function AgentWeeklyReport({
  agentId,
  agentName,
}: {
  agentId: string | null;
  agentName: string | null;
}) {
  return <AgentFormalReport window="weekly" agentId={agentId} agentName={agentName} />;
}

export function AgentGrowthTrajectory() {
  const { data, loading, error, refresh } = useReportData();

  if (loading) {
    return <Spin />;
  }

  const dataset = data ?? { events: [], proposals: [], patches: [], evidence: [] };
  const growthEvents = recentItems(dataset.events, (item) => item.created_at, 12);
  const recentProposals = recentItems(dataset.proposals, (item) => item.created_at, 8);
  const recentPatches = recentItems(
    dataset.patches,
    (item) => item.applied_at || item.created_at,
    8,
  );

  return (
    <div>
      <Alert
        showIcon
        type="info"
        message={agentReportsText.learningFeedTitle}
        description={agentReportsText.learningFeedDescription}
        style={{ marginBottom: 32 }}
      />

      <Card
        title={
          <Space>
            <RiseOutlined />
            {agentReportsText.growthTrajectory}
            <Tooltip title={commonText.refresh}>
              <ReloadOutlined
                onClick={() => {
                  void refresh();
                }}
                style={{ cursor: "pointer", fontSize: 14 }}
              />
            </Tooltip>
          </Space>
        }
        style={{ marginBottom: 32 }}
      >
        <RenderError error={error} />
        {growthEvents.length === 0 ? (
          <RenderEmpty description={agentReportsText.noGrowthEvents} />
        ) : (
          <Timeline
            items={growthEvents.map((event) => ({
              dot: changeTypeIcon(event.change_type),
              children: (
                <div>
                  <Text strong>{getChangeTypeLabel(event.change_type)}</Text>
                  <br />
                  <Text>{localizeWorkbenchText(event.description)}</Text>
                  <br />
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    {`${formatTime(event.created_at, agentReportsText.noTimestamp)} | ${
                      event.agent_id
                    }${
                      event.result
                        ? ` | ${getStatusLabel(event.result)}`
                        : ""
                    }`}
                  </Text>
                </div>
              ),
            }))}
          />
        )}
      </Card>

      <Card title={agentReportsText.improvementProposals} style={{ marginBottom: 32 }}>
        {recentProposals.length === 0 ? (
          <RenderEmpty description={agentReportsText.noProposals} />
        ) : (
          <List
            size="small"
            dataSource={recentProposals}
            renderItem={(proposal) => (
              <List.Item>
                {(() => {
                  const presentation = presentProposalSummary(proposal);
                  const capabilityRef = extractCapabilityRef(
                    proposal.title,
                    proposal.description,
                  );
                  return (
                <Space direction="vertical" size={2}>
                  <Space wrap>
                    <BulbOutlined />
                    <Text strong>{presentProposalTitle(proposal)}</Text>
                    <Tag color={statusColor(proposal.status)}>
                      {presentProposalStatus(proposal.status)}
                    </Tag>
                  </Space>
                  <Text type="secondary">
                    {presentation.summary}
                  </Text>
                  {presentation.impact ? (
                    <Text type="secondary">
                      {`${agentReportsText.userFacingImpactLabel}：${presentation.impact}`}
                    </Text>
                  ) : null}
                  {presentation.symptom ? (
                    <Text type="secondary">
                      {`${agentReportsText.userFacingSymptomLabel}：${presentation.symptom}`}
                    </Text>
                  ) : null}
                  {capabilityRef ? (
                    <Text type="secondary">
                      {`${agentReportsText.userFacingTechRefLabel}：${capabilityRef}`}
                    </Text>
                  ) : null}
                  <Text type="secondary">
                    {formatTime(proposal.created_at, agentReportsText.noTimestamp)}
                  </Text>
                </Space>
                  );
                })()}
              </List.Item>
            )}
          />
        )}
      </Card>

      <Card title={agentReportsText.patchStream} style={{ marginBottom: 32 }}>
        {recentPatches.length === 0 ? (
          <RenderEmpty description={agentReportsText.noPatches} />
        ) : (
          <List
            size="small"
            dataSource={recentPatches}
            renderItem={(patch) => (
              <List.Item>
                {(() => {
                  const presentation = presentPatchSummary(patch);
                  const capabilityRef = extractCapabilityRef(
                    patch.title,
                    patch.description,
                  );
                  return (
                <Space direction="vertical" size={2}>
                  <Space wrap>
                    <ToolOutlined />
                    <Text strong>{presentPatchTitle(patch)}</Text>
                    <Tag>系统修复</Tag>
                    <Tag color={statusColor(patch.status)}>
                      {getStatusLabel(patch.status)}
                    </Tag>
                    <Tag color={riskColor(patch.risk_level)}>
                      {presentLearningHandlingMode(patch.risk_level)}
                    </Tag>
                  </Space>
                  <Text type="secondary">
                    {presentation.summary}
                  </Text>
                  {presentation.impact ? (
                    <Text type="secondary">
                      {`${agentReportsText.userFacingImpactLabel}：${presentation.impact}`}
                    </Text>
                  ) : null}
                  {capabilityRef ? (
                    <Text type="secondary">
                      {`${agentReportsText.userFacingTechRefLabel}：${capabilityRef}`}
                    </Text>
                  ) : null}
                  <Text type="secondary">
                    {formatTime(
                      patch.applied_at || patch.created_at,
                      agentReportsText.noTimestamp,
                    )}
                  </Text>
                </Space>
                  );
                })()}
              </List.Item>
            )}
          />
        )}
      </Card>
    </div>
  );
}
