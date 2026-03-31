import {
  Alert,
  Button,
  Card,
  Descriptions,
  Empty,
  List,
  Space,
  Tag,
  Typography,
} from "antd";
import { useCallback } from "react";

import type {
  IndustryInstanceDetail,
  IndustryReportSnapshot,
  IndustryRuntimeAgentReport,
} from "../../api/modules/industry";
import { buildStaffingPresentation } from "../../runtime/staffingGapPresentation";
import { normalizeSpiderMeshBrand } from "../../utils/brand";
import {
  buildIndustryRuntimeFocusSummary,
  isFocusedAssignment,
  isFocusedBacklog,
  resolveEvidenceLabel,
  resolveExecutionEnvironmentVisibility,
  resolveReportWorkContextId,
  runtimeSurfaceCardStyle,
} from "./industryPagePresentation";
import IndustryPlanningSurface from "./runtimePlanningSurface";
import { renderMediaAnalysisList } from "./runtimePresentation";
import {
  formatIndustryDisplayToken,
  formatTimestamp,
  presentIndustryRiskLevel,
  presentIndustryRuntimeStatus,
  presentList,
  presentText,
  runtimeStatusColor as pageRuntimeStatusColor,
} from "./pageHelpers";

const { Paragraph, Text } = Typography;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

interface IndustryRuntimeCockpitPanelProps {
  detail: IndustryInstanceDetail;
  locale: string;
  onClearRuntimeFocus: () => void;
  onOpenAgentReportChat: (report: IndustryRuntimeAgentReport) => void;
  onSelectAssignmentFocus: (assignmentId: string) => void;
  onSelectBacklogFocus: (backlogItemId: string) => void;
}

interface RuntimeChainNode {
  key: string;
  label: string;
  value: string;
  note?: string | null;
  status?: string | null;
  actionLabel?: string | null;
  onAction?: (() => void) | null;
}

export default function IndustryRuntimeCockpitPanel({
  detail,
  locale,
  onClearRuntimeFocus,
  onOpenAgentReportChat,
  onSelectAssignmentFocus,
  onSelectBacklogFocus,
}: IndustryRuntimeCockpitPanelProps) {
  const focusSelection = detail.focus_selection || null;
  const staffingPresentation = buildStaffingPresentation(detail.staffing);
  const mediaAnalyses = detail.media_analyses || [];
  const lanes = detail.lanes || [];
  const focusedAssignment =
    detail.assignments.find((assignment) => isFocusedAssignment(assignment, focusSelection)) || null;
  const focusedBacklog =
    detail.backlog.find((backlogItem) => isFocusedBacklog(backlogItem, focusSelection)) || null;
  const followupReports = detail.agent_reports.filter((report) => report.needs_followup);
  const environmentVisibility = resolveExecutionEnvironmentVisibility(detail);
  const runtimeSignalCounts = {
    assignment: detail.assignments.length,
    report: detail.agent_reports.length,
    evidence: detail.evidence.length,
    decision: detail.decisions.length,
    patch: detail.patches.length,
  };
  const runtimeChainNodes: RuntimeChainNode[] = [
    {
      key: "carrier",
      label: "载体",
      value: detail.execution_core_identity?.role_name
        ? normalizeSpiderMeshBrand(detail.execution_core_identity.role_name)
        : "执行中枢",
      note: detail.execution_core_identity?.mission || null,
      status: detail.status,
    },
    {
      key: "strategy",
      label: "策略",
      value:
        detail.strategy_memory?.north_star ||
        detail.strategy_memory?.summary ||
        "暂无策略记忆。",
      note: presentList(detail.strategy_memory?.current_focuses as string[] | undefined),
      status: String(detail.strategy_memory?.status || detail.status),
    },
    {
      key: "lane",
      label: "泳道",
      value: `${lanes.length} 条`,
      note: lanes[0]?.title || null,
      status: detail.status,
    },
    {
      key: "backlog",
      label: "待办",
      value: `${detail.backlog.length} 项`,
      note: focusedBacklog?.title || detail.backlog[0]?.title || null,
      status: focusedBacklog?.status || detail.backlog[0]?.status || detail.status,
      actionLabel:
        focusedBacklog?.backlog_item_id || detail.backlog[0]?.backlog_item_id
          ? "聚焦待办"
          : null,
      onAction:
        focusedBacklog?.backlog_item_id
          ? () => onSelectBacklogFocus(focusedBacklog.backlog_item_id)
          : detail.backlog[0]?.backlog_item_id
            ? () => onSelectBacklogFocus(detail.backlog[0].backlog_item_id)
            : null,
    },
    {
      key: "cycle",
      label: "周期",
      value: detail.current_cycle
        ? detail.current_cycle.title || detail.current_cycle.cycle_id
        : "暂无活动周期",
      note: detail.current_cycle?.summary || null,
      status: detail.current_cycle?.status || detail.status,
    },
    {
      key: "assignment",
      label: "派工",
      value: `${runtimeSignalCounts.assignment} 项`,
      note: focusedAssignment?.title || detail.assignments[0]?.title || null,
      status: focusedAssignment?.status || detail.assignments[0]?.status || detail.status,
      actionLabel:
        focusedAssignment?.assignment_id || detail.assignments[0]?.assignment_id
          ? "聚焦派工"
          : null,
      onAction:
        focusedAssignment?.assignment_id
          ? () => onSelectAssignmentFocus(focusedAssignment.assignment_id)
          : detail.assignments[0]?.assignment_id
            ? () => onSelectAssignmentFocus(detail.assignments[0].assignment_id)
            : null,
    },
    {
      key: "report",
      label: "汇报",
      value: `${runtimeSignalCounts.report} 项`,
      note:
        followupReports[0]?.headline ||
        detail.agent_reports[0]?.headline ||
        detail.agent_reports[0]?.report_id ||
        null,
      status: followupReports[0]?.status || detail.agent_reports[0]?.status || detail.status,
      actionLabel: detail.agent_reports[0] ? "打开汇报对话" : null,
      onAction: detail.agent_reports[0] ? () => onOpenAgentReportChat(detail.agent_reports[0]) : null,
    },
    {
      key: "environment",
      label: "环境",
      value: environmentVisibility.environment || "未暴露",
      note: environmentVisibility.hostTwinSummary || null,
      status: detail.status,
    },
    {
      key: "evidence",
      label: "证据",
      value: `${runtimeSignalCounts.evidence} 条`,
      note: detail.execution?.latest_evidence_summary || null,
      status: detail.status,
    },
    {
      key: "decision",
      label: "决策",
      value: `${runtimeSignalCounts.decision} 条`,
      note: runtimeSignalCounts.decision > 0 ? "等待治理链消费。" : null,
      status: runtimeSignalCounts.decision > 0 ? "guarded" : detail.status,
    },
    {
      key: "patch",
      label: "补丁",
      value: `${runtimeSignalCounts.patch} 条`,
      note: runtimeSignalCounts.patch > 0 ? "等待学习补丁审查。" : null,
      status: runtimeSignalCounts.patch > 0 ? "guarded" : detail.status,
    },
  ];

  const runtimeFocusSummary = buildIndustryRuntimeFocusSummary({
    focusSelection,
    focusedAssignment,
    focusedBacklog,
    followupReport: followupReports[0] || null,
    executionCurrentFocus: detail.execution?.current_focus || null,
    mainChainCurrentFocus: detail.main_chain?.current_focus || null,
  });

  const renderReportSnapshot = useCallback(
    (snapshot: IndustryReportSnapshot, title: string) => {
      return (
        <Card key={`snapshot:${title}`} size="small" title={title}>
          <Space direction="vertical" size={10} style={{ width: "100%" }}>
            <Space wrap>
              <Tag>{snapshot.window}</Tag>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {formatTimestamp(snapshot.since, locale)} - {formatTimestamp(snapshot.until, locale)}
              </Text>
            </Space>
            <Descriptions
              size="small"
              column={2}
              items={[
                { key: "evidence", label: "证据", children: String(snapshot.evidence_count) },
                { key: "decision", label: "决策", children: String(snapshot.decision_count) },
                { key: "proposal", label: "提案", children: String(snapshot.proposal_count) },
                { key: "patch", label: "补丁", children: String(snapshot.patch_count) },
                { key: "applied", label: "已应用", children: String(snapshot.applied_patch_count) },
                { key: "growth", label: "成长", children: String(snapshot.growth_count) },
                { key: "highlights", label: "Highlights", children: presentList(snapshot.highlights) },
              ]}
            />
            {snapshot.recent_evidence.length ? (
              <Card size="small" title={`最近证据（${snapshot.recent_evidence.length}）`}>
                <Space direction="vertical" size={6} style={{ width: "100%" }}>
                  {snapshot.recent_evidence.slice(0, 5).map((record, index) => {
                    const rec = isRecord(record) ? record : {};
                    return (
                      <Text key={`recent:${title}:${index}`} type="secondary">
                        {resolveEvidenceLabel(rec)}
                      </Text>
                    );
                  })}
                </Space>
              </Card>
            ) : (
              <Empty description="当前还没有采集到最近证据。" style={{ margin: "4px 0" }} />
            )}
          </Space>
        </Card>
      );
    },
    [locale],
  );

  return (
    <Space direction="vertical" size={24} style={{ width: "100%" }}>
      <Card className="baize-card" size="small">
        <Space direction="vertical" size={16} style={{ width: "100%" }}>
          <div>
            <Text
              strong
              style={{
                color: "var(--baize-text-muted)",
                fontSize: 12,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
              }}
            >
              运行驾驶舱
            </Text>
            <Paragraph type="secondary" style={{ margin: "8px 0 0" }}>
              把 carrier / strategy / lane / cycle / assignment / report / evidence / decision / patch 放到同一条运行面上。
            </Paragraph>
          </div>
          <Descriptions
            size="small"
            column={2}
            bordered
            items={[
              {
                key: "carrier",
                label: "载体",
                children: detail.execution_core_identity?.role_name
                  ? normalizeSpiderMeshBrand(detail.execution_core_identity.role_name)
                  : "执行中枢",
              },
              {
                key: "strategy",
                label: "策略",
                children:
                  detail.strategy_memory?.north_star ||
                  detail.strategy_memory?.summary ||
                  "暂无策略记忆。",
              },
              {
                key: "lane",
                label: "泳道",
                children: `${lanes.length} 条`,
              },
              {
                key: "cycle",
                label: "周期",
                children: detail.current_cycle
                  ? `${detail.current_cycle.title || detail.current_cycle.cycle_id} · ${presentIndustryRuntimeStatus(detail.current_cycle.status)}`
                  : "暂无活动周期",
              },
              {
                key: "assignment",
                label: "派工",
                children: `${runtimeSignalCounts.assignment} 项`,
              },
              {
                key: "report",
                label: "汇报",
                children: `${runtimeSignalCounts.report} 项`,
              },
              {
                key: "evidence",
                label: "证据",
                children: `${runtimeSignalCounts.evidence} 条`,
              },
              {
                key: "decision",
                label: "决策",
                children: `${runtimeSignalCounts.decision} 条`,
              },
              {
                key: "patch",
                label: "补丁",
                children: `${runtimeSignalCounts.patch} 条`,
              },
              {
                key: "runtime-focus",
                label: "运行焦点",
                children: runtimeFocusSummary,
              },
            ]}
          />
        </Space>
      </Card>

      <Card className="baize-card" size="small" title="统一运行链">
        <Space direction="vertical" size={8} style={{ width: "100%" }}>
          {runtimeChainNodes.map((node) => (
            <Card
              key={`chain:${node.key}`}
              size="small"
              style={{ ...runtimeSurfaceCardStyle(false), width: "100%" }}
            >
              <Space
                align="start"
                style={{ width: "100%", justifyContent: "space-between" }}
                wrap
              >
                <Space direction="vertical" size={2} style={{ minWidth: 0, flex: 1 }}>
                  <Space wrap size={[6, 6]}>
                    <Text strong style={{ color: "var(--baize-text-main)" }}>
                      {node.label}
                    </Text>
                    <Tag color={pageRuntimeStatusColor(node.status || detail.status)}>
                      {presentIndustryRuntimeStatus(node.status || detail.status)}
                    </Tag>
                  </Space>
                  <Text>{node.value}</Text>
                  {node.note ? <Text type="secondary">{node.note}</Text> : null}
                </Space>
                {node.actionLabel && node.onAction ? (
                  <Button size="small" onClick={node.onAction}>
                    {node.actionLabel}
                  </Button>
                ) : null}
              </Space>
            </Card>
          ))}
        </Space>
      </Card>

      {focusSelection ? (
        <Alert
          showIcon
          type="info"
          message={
            focusSelection.selection_kind === "assignment"
              ? "已聚焦派工"
              : "已聚焦待办"
          }
          description={[
            focusSelection.summary || focusSelection.title || "运行详情当前已收束到选中的子视图。",
            focusSelection.status
              ? `状态 ${presentIndustryRuntimeStatus(focusSelection.status)}`
              : null,
          ]
            .filter(Boolean)
            .join(" | ")}
          action={
            <Button size="small" onClick={() => onClearRuntimeFocus()}>
              查看完整面板
            </Button>
          }
        />
      ) : null}

      <Card className="baize-card" size="small" title="运行焦点">
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          {focusedAssignment || focusedBacklog || followupReports.length ? (
            <Card size="small" title="聚焦视图" style={runtimeSurfaceCardStyle(true)}>
              <Space direction="vertical" size={10} style={{ width: "100%" }}>
                {followupReports.length ? (
                  <Card
                    size="small"
                    title={`跟进（${followupReports.length}）`}
                    style={{
                      borderRadius: 12,
                      border: "1px solid rgba(250,173,20,0.55)",
                      background: "rgba(250,173,20,0.10)",
                    }}
                    extra={
                      <Button
                        size="small"
                        type="primary"
                        onClick={() => onOpenAgentReportChat(followupReports[0])}
                      >
                        打开跟进对话
                      </Button>
                    }
                  >
                    <Space direction="vertical" size={6} style={{ width: "100%" }}>
                      <Space wrap>
                        <Text strong style={{ color: "var(--baize-text-main)" }}>
                          {followupReports[0].headline || followupReports[0].report_id}
                        </Text>
                        <Tag color="orange">待跟进</Tag>
                        {followupReports[0].followup_reason ? (
                          <Tag>{followupReports[0].followup_reason}</Tag>
                        ) : null}
                        {resolveReportWorkContextId(followupReports[0]) ? (
                          <Tag color="blue">{resolveReportWorkContextId(followupReports[0])}</Tag>
                        ) : null}
                      </Space>
                      <Text type="secondary">
                        {followupReports[0].summary ||
                          followupReports[0].recommendation ||
                          followupReports[0].findings[0] ||
                          "已记录跟进汇报。"}
                      </Text>
                      <Space wrap>
                        {followupReports[0].assignment_id ? (
                          <Button
                            size="small"
                            onClick={() => onSelectAssignmentFocus(followupReports[0].assignment_id!)}
                          >
                            聚焦关联派工
                          </Button>
                        ) : null}
                        <Tag>{`证据 ${followupReports[0].evidence_ids.length}`}</Tag>
                      </Space>
                    </Space>
                  </Card>
                ) : null}

                {focusedBacklog ? (
                  <Card
                    size="small"
                    title="已聚焦待办"
                    style={runtimeSurfaceCardStyle(true)}
                    extra={
                      <Button
                        size="small"
                        type="primary"
                        onClick={() => onSelectBacklogFocus(focusedBacklog.backlog_item_id)}
                      >
                        聚焦待办
                      </Button>
                    }
                  >
                    <Space direction="vertical" size={6} style={{ width: "100%" }}>
                      <Space wrap>
                        <Text strong style={{ color: "var(--baize-text-main)" }}>
                          {focusedBacklog.title || focusedBacklog.backlog_item_id}
                        </Text>
                        <Tag color={pageRuntimeStatusColor(focusedBacklog.status)}>
                          {presentIndustryRuntimeStatus(focusedBacklog.status)}
                        </Tag>
                        <Tag>{`P${focusedBacklog.priority}`}</Tag>
                        <Tag>{focusedBacklog.source_kind}</Tag>
                      </Space>
                      <Text type="secondary">
                        {focusedBacklog.summary ||
                          focusedBacklog.source_ref ||
                          "No backlog summary captured yet."}
                      </Text>
                      <Space wrap>
                        <Tag>{`证据 ${focusedBacklog.evidence_ids.length}`}</Tag>
                        {focusedBacklog.updated_at ? (
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {formatTimestamp(focusedBacklog.updated_at, locale)}
                          </Text>
                        ) : null}
                      </Space>
                    </Space>
                  </Card>
                ) : null}

                {focusedAssignment ? (
                  <Card
                    size="small"
                    title="已聚焦派工"
                    style={runtimeSurfaceCardStyle(true)}
                    extra={
                      <Button
                        size="small"
                        type="primary"
                        onClick={() => onSelectAssignmentFocus(focusedAssignment.assignment_id)}
                      >
                        聚焦派工
                      </Button>
                    }
                  >
                    <Space direction="vertical" size={6} style={{ width: "100%" }}>
                      <Space wrap>
                        <Text strong style={{ color: "var(--baize-text-main)" }}>
                          {focusedAssignment.title || focusedAssignment.assignment_id}
                        </Text>
                        <Tag color={pageRuntimeStatusColor(focusedAssignment.status)}>
                          {presentIndustryRuntimeStatus(focusedAssignment.status)}
                        </Tag>
                        {focusedAssignment.report_back_mode ? (
                          <Tag>{focusedAssignment.report_back_mode}</Tag>
                        ) : null}
                      </Space>
                      <Text type="secondary">
                        {focusedAssignment.summary || "No assignment summary captured yet."}
                      </Text>
                      <Space wrap>
                        <Tag>{`证据 ${focusedAssignment.evidence_ids.length}`}</Tag>
                        {focusedAssignment.updated_at ? (
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {formatTimestamp(focusedAssignment.updated_at, locale)}
                          </Text>
                        ) : null}
                      </Space>
                    </Space>
                  </Card>
                ) : null}
              </Space>
            </Card>
          ) : null}

          {detail.execution ? (
            <div>
              <Space wrap style={{ marginBottom: 8 }}>
                <Tag color={pageRuntimeStatusColor(detail.execution.status)}>
                  {presentIndustryRuntimeStatus(detail.execution.status)}
                </Tag>
                {detail.execution.current_owner ? <Tag>{detail.execution.current_owner}</Tag> : null}
                {detail.execution.current_stage ? <Tag>{formatIndustryDisplayToken(detail.execution.current_stage)}</Tag> : null}
                {detail.execution.updated_at ? (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {formatTimestamp(detail.execution.updated_at, locale)}
                  </Text>
                ) : null}
              </Space>
              <Descriptions
                size="small"
                column={2}
                items={[
                  { key: "focus", label: "当前焦点", children: detail.execution.current_focus || "-" },
                  { key: "owner", label: "当前负责人", children: detail.execution.current_owner || "-" },
                  {
                    key: "risk",
                    label: "当前风险",
                    children: detail.execution.current_risk
                      ? presentIndustryRiskLevel(detail.execution.current_risk)
                      : "-",
                  },
                  {
                    key: "evidence",
                    label: "最新证据",
                    children:
                      detail.execution.latest_evidence_summary ||
                      (detail.execution.evidence_count > 0
                        ? `共 ${detail.execution.evidence_count} 条证据`
                        : "暂无证据"),
                  },
                  { key: "next", label: "下一步", children: detail.execution.next_step || "-" },
                  {
                    key: "trigger",
                    label: "触发来源",
                    children: detail.execution.trigger_reason || detail.execution.trigger_source || "-",
                  },
                ]}
              />
              {detail.execution.blocked_reason || detail.execution.stuck_reason ? (
                <Alert
                  showIcon
                  type={
                    detail.execution.status === "failed" || detail.execution.status === "idle-loop"
                      ? "warning"
                      : "info"
                  }
                  message={detail.execution.blocked_reason || detail.execution.stuck_reason || ""}
                  style={{ marginTop: 8 }}
                />
              ) : null}
            </div>
          ) : null}

          {focusSelection ? (
            <Space wrap>
              {focusSelection.selection_kind === "assignment" ? (
                <Button
                  size="small"
                  type="primary"
                  onClick={() => {
                    if (focusSelection.assignment_id) {
                      onSelectAssignmentFocus(focusSelection.assignment_id);
                    }
                  }}
                  disabled={!focusSelection.assignment_id}
                >
                  聚焦派工
                </Button>
              ) : null}
              {focusSelection.selection_kind === "backlog" ? (
                <Button
                  size="small"
                  type="primary"
                  onClick={() => {
                    if (focusSelection.backlog_item_id) {
                      onSelectBacklogFocus(focusSelection.backlog_item_id);
                    }
                  }}
                  disabled={!focusSelection.backlog_item_id}
                >
                  聚焦待办
                </Button>
              ) : null}
            </Space>
          ) : null}
        </Space>
      </Card>

      {environmentVisibility.environment ||
      environmentVisibility.hostTwinSummary ||
      environmentVisibility.constraints.length ? (
        <Card className="baize-card" size="small" title="执行环境">
          <Space direction="vertical" size={10} style={{ width: "100%" }}>
            <Paragraph type="secondary" style={{ margin: "8px 0 0" }}>
              只有当运行时载荷已经提供环境与宿主孪生线索时，这里才会显式展示。
            </Paragraph>
            <Descriptions
              size="small"
              column={2}
              items={[
                {
                  key: "environment",
                  label: "环境",
                  children: environmentVisibility.environment || "-",
                },
                {
                  key: "host-twin",
                  label: "宿主孪生",
                  children: environmentVisibility.hostTwinSummary || "-",
                },
                {
                  key: "constraints",
                  label: "约束",
                  children: environmentVisibility.constraints.length ? (
                    <Space wrap>
                      {environmentVisibility.constraints.slice(0, 8).map((constraint) => (
                        <Tag key={constraint}>{constraint}</Tag>
                      ))}
                    </Space>
                  ) : (
                    "-"
                  ),
                },
              ]}
            />
          </Space>
        </Card>
      ) : null}

      {detail.execution_core_identity || detail.strategy_memory ? (
        <Card className="baize-card" size="small" title="策略">
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            <Space wrap>
              {detail.strategy_memory?.status ? (
                <Tag color={pageRuntimeStatusColor(String(detail.strategy_memory.status))}>
                  {presentIndustryRuntimeStatus(String(detail.strategy_memory.status))}
                </Tag>
              ) : null}
              {detail.execution_core_identity?.role_name ? (
                <Tag>{normalizeSpiderMeshBrand(String(detail.execution_core_identity.role_name))}</Tag>
              ) : null}
              {detail.execution_core_identity?.operating_mode ? (
                <Tag>
                  {String(detail.execution_core_identity.operating_mode) === "control-core"
                    ? "主脑中控"
                    : formatIndustryDisplayToken(
                        detail.execution_core_identity.operating_mode as string | undefined,
                      )}
                </Tag>
              ) : null}
            </Space>
            <Descriptions
              size="small"
              column={2}
              items={[
                {
                  key: "mission",
                  label: "长期使命",
                  children: presentText(detail.execution_core_identity?.mission as string | undefined),
                },
                {
                  key: "north-star",
                  label: "北极星",
                  children: presentText(
                    (detail.strategy_memory?.north_star as string | undefined) ||
                      (detail.strategy_memory?.summary as string | undefined),
                  ),
                },
                {
                  key: "focuses",
                  label: "当前关注",
                  children: presentList(detail.strategy_memory?.current_focuses as string[] | undefined),
                },
                {
                  key: "priorities",
                  label: "优先顺序",
                  children: presentList(detail.strategy_memory?.priority_order as string[] | undefined),
                },
                {
                  key: "thinking-axes",
                  label: "思考轴",
                  children: presentList(detail.execution_core_identity?.thinking_axes as string[] | undefined),
                },
                {
                  key: "delegation-policy",
                  label: "分派原则",
                  children: presentList(detail.execution_core_identity?.delegation_policy as string[] | undefined),
                },
              ]}
            />
          </Space>
        </Card>
      ) : null}

      <Card className="baize-card" size="small" title="素材分析">
        <Paragraph type="secondary" style={{ margin: "8px 0 0" }}>
          这里只保留已经写回行业实例的素材分析结果，供主脑聊天和后续执行复用。
        </Paragraph>
        {renderMediaAnalysisList(mediaAnalyses, {
          emptyText: "当前行业实例还没有写回的素材分析。",
          adoptedTag: "已接入身份",
          showWriteback: true,
        })}
      </Card>

      <Card className="baize-card" size="small" title="汇报快照">
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Paragraph type="secondary" style={{ margin: "8px 0 0" }}>
            用证据驱动的快照做快速复核，不必每次都打开完整证据流。
          </Paragraph>
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            {renderReportSnapshot(detail.reports.daily, "日报")}
            {renderReportSnapshot(detail.reports.weekly, "周报")}
          </Space>
        </Space>
      </Card>

      <IndustryPlanningSurface detail={detail} locale={locale} />

      {staffingPresentation.hasAnyState ? (
        <Card className="baize-card" size="small" title="补位闭环">
          <Space direction="vertical" size={10} style={{ width: "100%" }}>
            {staffingPresentation.activeGap ? (
              <Alert
                showIcon
                type={
                  staffingPresentation.activeGap.badges.includes("Needs approval")
                    ? "warning"
                    : "info"
                }
                message={staffingPresentation.activeGap.title}
                description={[
                  staffingPresentation.activeGap.detail,
                  staffingPresentation.activeGap.meta.join(" / "),
                ]
                  .filter(Boolean)
                  .join(" | ")}
              />
            ) : null}
            {staffingPresentation.pendingProposals.length ? (
              <Card size="small" title="待处理提案">
                <Space direction="vertical" size={6} style={{ width: "100%" }}>
                  {staffingPresentation.pendingProposals.map((item) => (
                    <Text key={item}>{item}</Text>
                  ))}
                </Space>
              </Card>
            ) : null}
            {staffingPresentation.temporarySeats.length ? (
              <Card size="small" title="临时席位">
                <Space direction="vertical" size={6} style={{ width: "100%" }}>
                  {staffingPresentation.temporarySeats.map((item) => (
                    <Text key={item}>{item}</Text>
                  ))}
                </Space>
              </Card>
            ) : null}
            {staffingPresentation.researcher ? (
              <Card size="small" title="研究位">
                <Space direction="vertical" size={6} style={{ width: "100%" }}>
                  <Text strong>{staffingPresentation.researcher.headline}</Text>
                  <Text type="secondary">{staffingPresentation.researcher.detail}</Text>
                  <Space wrap>
                    {staffingPresentation.researcher.badges.map((badge) => (
                      <Tag key={badge}>{badge}</Tag>
                    ))}
                  </Space>
                </Space>
              </Card>
            ) : null}
          </Space>
        </Card>
      ) : null}

      <Card className="baize-card" size="small" title="待办">
        {detail.backlog.length === 0 ? (
          <Empty description="当前还没有活动待办。" style={{ margin: "8px 0" }} />
        ) : (
          <List
            size="small"
            style={{ marginTop: 8 }}
            dataSource={detail.backlog}
            renderItem={(backlogItem) => {
              const selected = isFocusedBacklog(backlogItem, focusSelection);
              return (
                <List.Item style={{ padding: "8px 0" }}>
                  <Card
                    size="small"
                    style={{ width: "100%", ...runtimeSurfaceCardStyle(selected) }}
                    extra={
                      <Button
                        size="small"
                        type={selected ? "primary" : "default"}
                        onClick={() => onSelectBacklogFocus(backlogItem.backlog_item_id)}
                      >
                        {selected ? "已聚焦" : "聚焦待办"}
                      </Button>
                    }
                  >
                    <Space direction="vertical" size={8} style={{ width: "100%" }}>
                      <Space wrap>
                        <Text strong style={{ color: "var(--baize-text-main)" }}>
                          {backlogItem.title || backlogItem.backlog_item_id}
                        </Text>
                        <Tag color={pageRuntimeStatusColor(backlogItem.status)}>
                          {presentIndustryRuntimeStatus(backlogItem.status)}
                        </Tag>
                        <Tag>{`P${backlogItem.priority}`}</Tag>
                        <Tag>{backlogItem.source_kind}</Tag>
                        {selected ? <Tag color="blue">已选中</Tag> : null}
                      </Space>
                      <Text type="secondary">
                        {backlogItem.summary || backlogItem.source_ref || "还没有记录摘要。"}
                      </Text>
                      <Space wrap>
                        {backlogItem.assignment_id ? (
                          <Tag>{`派工 ${backlogItem.assignment_id}`}</Tag>
                        ) : null}
                        <Tag>{`证据 ${backlogItem.evidence_ids.length}`}</Tag>
                        {backlogItem.updated_at ? (
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {formatTimestamp(backlogItem.updated_at, locale)}
                          </Text>
                        ) : null}
                      </Space>
                    </Space>
                  </Card>
                </List.Item>
              );
            }}
          />
        )}
      </Card>

      <Card className="baize-card" size="small" title="派工">
        {detail.assignments.length === 0 ? (
          <Empty description="当前还没有活动派工。" style={{ margin: "8px 0" }} />
        ) : (
          <List
            size="small"
            style={{ marginTop: 8 }}
            dataSource={detail.assignments}
            renderItem={(assignment) => {
              const selected = isFocusedAssignment(assignment, focusSelection);
              return (
                <List.Item style={{ padding: "8px 0" }}>
                  <Card
                    size="small"
                    style={{ width: "100%", ...runtimeSurfaceCardStyle(selected) }}
                    extra={
                      <Button
                        size="small"
                        type={selected ? "primary" : "default"}
                        onClick={() => onSelectAssignmentFocus(assignment.assignment_id)}
                      >
                        {selected ? "已聚焦" : "聚焦派工"}
                      </Button>
                    }
                  >
                    <Space direction="vertical" size={8} style={{ width: "100%" }}>
                      <Space wrap>
                        <Text strong style={{ color: "var(--baize-text-main)" }}>
                          {assignment.title || assignment.assignment_id}
                        </Text>
                        <Tag color={pageRuntimeStatusColor(assignment.status)}>
                          {presentIndustryRuntimeStatus(assignment.status)}
                        </Tag>
                        {assignment.report_back_mode ? (
                          <Tag>{assignment.report_back_mode}</Tag>
                        ) : null}
                        {selected ? <Tag color="blue">已选中</Tag> : null}
                      </Space>
                      <Text type="secondary">
                        {assignment.summary || "还没有记录派工摘要。"}
                      </Text>
                      <Space wrap>
                        {assignment.backlog_item_id ? (
                          <Tag>{`待办 ${assignment.backlog_item_id}`}</Tag>
                        ) : null}
                        {assignment.goal_id ? <Tag>{`目标 ${assignment.goal_id}`}</Tag> : null}
                        <Tag>{`证据 ${assignment.evidence_ids.length}`}</Tag>
                        {assignment.updated_at ? (
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {formatTimestamp(assignment.updated_at, locale)}
                          </Text>
                        ) : null}
                      </Space>
                    </Space>
                  </Card>
                </List.Item>
              );
            }}
          />
        )}
      </Card>

      <Card className="baize-card" size="small" title="智能体汇报">
        {detail.agent_reports.length === 0 ? (
          <Empty description="当前还没有智能体汇报。" style={{ margin: "8px 0" }} />
        ) : (
          <List
            size="small"
            style={{ marginTop: 8 }}
            dataSource={detail.agent_reports}
            renderItem={(report) => {
              const workContextId = resolveReportWorkContextId(report);
              const summary =
                report.summary ||
                report.recommendation ||
                report.findings[0] ||
                "还没有记录汇报摘要。";
              return (
                <List.Item style={{ padding: "8px 0" }}>
                  <Card
                    size="small"
                    style={{ width: "100%", ...runtimeSurfaceCardStyle(false) }}
                    extra={
                      <Space wrap>
                        {report.assignment_id ? (
                          <Button
                            size="small"
                            onClick={() => onSelectAssignmentFocus(report.assignment_id!)}
                          >
                            聚焦关联派工
                          </Button>
                        ) : null}
                        <Button
                          size="small"
                          type="primary"
                          onClick={() => onOpenAgentReportChat(report)}
                        >
                          打开汇报对话
                        </Button>
                      </Space>
                    }
                  >
                    <Space direction="vertical" size={8} style={{ width: "100%" }}>
                      <Space wrap>
                        <Text strong style={{ color: "var(--baize-text-main)" }}>
                          {report.headline || report.report_id}
                        </Text>
                        <Tag color={pageRuntimeStatusColor(report.status)}>
                          {presentIndustryRuntimeStatus(report.status)}
                        </Tag>
                        <Tag>{report.report_kind}</Tag>
                        {report.result ? <Tag>{report.result}</Tag> : null}
                        {report.processed ? <Tag color="green">已处理</Tag> : null}
                        {report.needs_followup ? <Tag color="orange">待跟进</Tag> : null}
                        {workContextId ? <Tag color="blue">{workContextId}</Tag> : null}
                      </Space>
                      <Text type="secondary">{summary}</Text>
                      <Space wrap>
                        {report.followup_reason ? <Tag>{report.followup_reason}</Tag> : null}
                        <Tag>{`发现 ${report.findings.length}`}</Tag>
                        <Tag>{`证据 ${report.evidence_ids.length}`}</Tag>
                        {report.updated_at ? (
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {formatTimestamp(report.updated_at, locale)}
                          </Text>
                        ) : null}
                      </Space>
                    </Space>
                  </Card>
                </List.Item>
              );
            }}
          />
        )}
      </Card>
    </Space>
  );
}
