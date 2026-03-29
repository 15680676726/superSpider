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
  IndustryRuntimeAssignment,
  IndustryRuntimeBacklogItem,
} from "../../api/modules/industry";
import type { MediaAnalysisSummary } from "../../api/modules/media";
import { buildStaffingPresentation } from "../../runtime/staffingGapPresentation";
import { normalizeSpiderMeshBrand } from "../../utils/brand";
import IndustryPlanningSurface from "./runtimePlanningSurface";
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

function stringValue(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function summarizeHostTwin(value: unknown): string | null {
  if (!isRecord(value)) {
    return null;
  }
  const coordination = isRecord(value.coordination) ? value.coordination : value;
  return (
    stringValue(coordination.recommended_scheduler_action) ||
    stringValue(coordination.selected_seat_ref) ||
    stringValue(coordination.seat_selection_policy) ||
    stringValue(coordination.active_app_family_count) ||
    stringValue(coordination.contention_severity) ||
    stringValue(coordination.blocked_surface_count) ||
    null
  );
}

function resolveEvidenceLabel(record: Record<string, unknown>): string {
  return (
    stringValue(record.summary) ||
    stringValue(record.title) ||
    stringValue(record.headline) ||
    stringValue(record.evidence_id) ||
    stringValue(record.id) ||
    "Evidence record"
  );
}

function resolveExecutionEnvironmentVisibility(detail: IndustryInstanceDetail): {
  environment: string | null;
  hostTwinSummary: string | null;
  constraints: string[];
} {
  const anyDetail = detail as unknown as Record<string, unknown>;
  const identity = (detail.execution_core_identity || null) as unknown as Record<string, unknown> | null;

  const directEnv =
    anyDetail.execution_environment ||
    anyDetail.executionEnvironment ||
    anyDetail.environment ||
    null;
  const envRecord = isRecord(directEnv) ? directEnv : null;

  const hostTwin =
    (envRecord && isRecord(envRecord.host_twin) ? envRecord.host_twin : null) ||
    (envRecord && isRecord(envRecord.hostTwin) ? envRecord.hostTwin : null) ||
    (identity && isRecord(identity.host_twin) ? identity.host_twin : null) ||
    (identity && isRecord(identity.hostTwin) ? identity.hostTwin : null) ||
    (isRecord(anyDetail.host_twin) ? anyDetail.host_twin : null) ||
    (isRecord(anyDetail.hostTwin) ? anyDetail.hostTwin : null) ||
    null;

  const constraintsFromIdentity = Array.isArray(detail.execution_core_identity?.environment_constraints)
    ? detail.execution_core_identity!.environment_constraints.filter(
        (item): item is string => typeof item === "string" && item.trim(),
      )
    : [];
  const constraintsFromEnv =
    envRecord && Array.isArray(envRecord.environment_constraints)
      ? envRecord.environment_constraints.filter(
          (item): item is string => typeof item === "string" && item.trim(),
        )
      : [];

  return {
    environment:
      stringValue(envRecord?.environment_summary) ||
      stringValue(envRecord?.environment) ||
      stringValue(identity?.environment_summary) ||
      stringValue(identity?.environment) ||
      null,
    hostTwinSummary:
      stringValue(envRecord?.host_twin_summary) ||
      stringValue(identity?.host_twin_summary) ||
      summarizeHostTwin(hostTwin) ||
      null,
    constraints: Array.from(new Set([...constraintsFromIdentity, ...constraintsFromEnv])),
  };
}

function isFocusedAssignment(
  assignment: IndustryRuntimeAssignment,
  selection: { selection_kind: "assignment" | "backlog"; assignment_id?: string | null } | null | undefined,
): boolean {
  return Boolean(
    assignment.selected ||
      (selection?.selection_kind === "assignment" &&
        selection.assignment_id === assignment.assignment_id),
  );
}

function isFocusedBacklog(
  backlogItem: IndustryRuntimeBacklogItem,
  selection: { selection_kind: "assignment" | "backlog"; backlog_item_id?: string | null } | null | undefined,
): boolean {
  return Boolean(
    backlogItem.selected ||
      (selection?.selection_kind === "backlog" &&
        selection.backlog_item_id === backlogItem.backlog_item_id),
  );
}

function resolveReportWorkContextId(report: IndustryRuntimeAgentReport): string | null {
  const workContextId = report.work_context_id?.trim();
  if (workContextId) {
    return workContextId;
  }
  const metadata = report.metadata;
  if (
    metadata &&
    typeof metadata === "object" &&
    typeof metadata.work_context_id === "string" &&
    metadata.work_context_id.trim()
  ) {
    return metadata.work_context_id.trim();
  }
  return null;
}

function runtimeSurfaceCardStyle(selected: boolean) {
  return {
    borderRadius: 12,
    border: `1px solid ${selected ? "var(--ant-primary-color, #1677ff)" : "var(--baize-border-color)"}`,
    background: selected ? "rgba(22,119,255,0.08)" : "rgba(255,255,255,0.02)",
    boxShadow: selected ? "0 0 0 1px rgba(22,119,255,0.12)" : "none",
  } as const;
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
      label: "Carrier",
      value: detail.execution_core_identity?.role_name
        ? normalizeSpiderMeshBrand(detail.execution_core_identity.role_name)
        : "Execution core",
      note: detail.execution_core_identity?.mission || null,
      status: detail.status,
    },
    {
      key: "strategy",
      label: "Strategy",
      value:
        detail.strategy_memory?.north_star ||
        detail.strategy_memory?.summary ||
        "No strategy memory yet.",
      note: presentList(detail.strategy_memory?.current_focuses as string[] | undefined),
      status: String(detail.strategy_memory?.status || detail.status),
    },
    {
      key: "lane",
      label: "Lane",
      value: `${lanes.length} lanes`,
      note: lanes[0]?.title || null,
      status: detail.status,
    },
    {
      key: "backlog",
      label: "Backlog",
      value: `${detail.backlog.length} live`,
      note: focusedBacklog?.title || detail.backlog[0]?.title || null,
      status: focusedBacklog?.status || detail.backlog[0]?.status || detail.status,
      actionLabel:
        focusedBacklog?.backlog_item_id || detail.backlog[0]?.backlog_item_id
          ? "Focus backlog"
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
      label: "Cycle",
      value: detail.current_cycle
        ? detail.current_cycle.title || detail.current_cycle.cycle_id
        : "No active cycle",
      note: detail.current_cycle?.summary || null,
      status: detail.current_cycle?.status || detail.status,
    },
    {
      key: "assignment",
      label: "Assignment",
      value: `${runtimeSignalCounts.assignment} live`,
      note: focusedAssignment?.title || detail.assignments[0]?.title || null,
      status: focusedAssignment?.status || detail.assignments[0]?.status || detail.status,
      actionLabel:
        focusedAssignment?.assignment_id || detail.assignments[0]?.assignment_id
          ? "Focus assignment"
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
      label: "Report",
      value: `${runtimeSignalCounts.report} live`,
      note:
        followupReports[0]?.headline ||
        detail.agent_reports[0]?.headline ||
        detail.agent_reports[0]?.report_id ||
        null,
      status: followupReports[0]?.status || detail.agent_reports[0]?.status || detail.status,
      actionLabel: detail.agent_reports[0] ? "Open report chat" : null,
      onAction: detail.agent_reports[0] ? () => onOpenAgentReportChat(detail.agent_reports[0]) : null,
    },
    {
      key: "environment",
      label: "Environment",
      value: environmentVisibility.environment || "Not exposed",
      note: environmentVisibility.hostTwinSummary || null,
      status: detail.status,
    },
    {
      key: "evidence",
      label: "Evidence",
      value: `${runtimeSignalCounts.evidence} records`,
      note: detail.execution?.latest_evidence_summary || null,
      status: detail.status,
    },
    {
      key: "decision",
      label: "Decision",
      value: `${runtimeSignalCounts.decision} records`,
      note: runtimeSignalCounts.decision > 0 ? "Awaiting governance consumption." : null,
      status: runtimeSignalCounts.decision > 0 ? "guarded" : detail.status,
    },
    {
      key: "patch",
      label: "Patch",
      value: `${runtimeSignalCounts.patch} records`,
      note: runtimeSignalCounts.patch > 0 ? "Pending learning patch review." : null,
      status: runtimeSignalCounts.patch > 0 ? "guarded" : detail.status,
    },
  ];

  const runtimeFocusSummary =
    focusSelection?.summary ||
    focusSelection?.title ||
    (focusedAssignment
      ? `Assignment: ${focusedAssignment.title || focusedAssignment.assignment_id}`
      : null) ||
    (focusedBacklog ? `Backlog: ${focusedBacklog.title || focusedBacklog.backlog_item_id}` : null) ||
    (followupReports[0]
      ? `Follow-up: ${followupReports[0].headline || followupReports[0].report_id}`
      : null) ||
    detail.execution?.current_focus ||
    detail.main_chain?.current_focus ||
    "No focused subview yet.";

  const renderMediaAnalysisList = useCallback(
    (
      analyses: MediaAnalysisSummary[],
      options?: {
        emptyText?: string;
        adoptedTag?: string;
        showWriteback?: boolean;
      },
    ) => {
      if (!analyses.length) {
        return (
          <Empty
            description={options?.emptyText || "暂无素材分析结果"}
            style={{ margin: "8px 0" }}
          />
        );
      }
      return (
        <List
          size="small"
          style={{ marginTop: 8 }}
          dataSource={analyses}
          renderItem={(analysis) => {
            const summary =
              analysis.summary ||
              analysis.key_points?.slice(0, 2).join(" / ") ||
              "暂无摘要";
            return (
              <List.Item style={{ padding: "10px 0" }}>
                <div style={{ width: "100%" }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      gap: 12,
                      alignItems: "flex-start",
                      flexWrap: "wrap",
                    }}
                  >
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <Space wrap>
                        <Text strong style={{ color: "var(--baize-text-main)" }}>
                          {analysis.title || analysis.filename || analysis.source_ref || analysis.url || "素材分析"}
                        </Text>
                        {options?.adoptedTag ? <Tag color="green">{options.adoptedTag}</Tag> : null}
                        {options?.showWriteback && analysis.strategy_writeback_status ? (
                          <Tag>{`策略 ${analysis.strategy_writeback_status}`}</Tag>
                        ) : null}
                        {options?.showWriteback && analysis.backlog_writeback_status ? (
                          <Tag>{`待办 ${analysis.backlog_writeback_status}`}</Tag>
                        ) : null}
                      </Space>
                      <Paragraph style={{ margin: "8px 0 0" }}>{summary}</Paragraph>
                      {analysis.key_points?.length ? (
                        <Text type="secondary" style={{ display: "block" }}>
                          {analysis.key_points.slice(0, 3).join(" / ")}
                        </Text>
                      ) : null}
                      {(analysis.warnings || []).map((warning) => (
                        <Alert
                          key={`${analysis.analysis_id}:${warning}`}
                          type="warning"
                          showIcon
                          message={warning}
                          style={{ marginTop: 8 }}
                        />
                      ))}
                    </div>
                  </div>
                </div>
              </List.Item>
            );
          }}
        />
      );
    },
    [],
  );

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
                { key: "evidence", label: "Evidence", children: String(snapshot.evidence_count) },
                { key: "decision", label: "Decision", children: String(snapshot.decision_count) },
                { key: "proposal", label: "Proposal", children: String(snapshot.proposal_count) },
                { key: "patch", label: "Patch", children: String(snapshot.patch_count) },
                { key: "applied", label: "Applied", children: String(snapshot.applied_patch_count) },
                { key: "growth", label: "Growth", children: String(snapshot.growth_count) },
                { key: "highlights", label: "Highlights", children: presentList(snapshot.highlights) },
              ]}
            />
            {snapshot.recent_evidence.length ? (
              <Card size="small" title={`Recent Evidence (${snapshot.recent_evidence.length})`}>
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
              <Empty description="No recent evidence captured yet." style={{ margin: "4px 0" }} />
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
              Runtime Cockpit
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
                label: "Carrier",
                children: detail.execution_core_identity?.role_name
                  ? normalizeSpiderMeshBrand(detail.execution_core_identity.role_name)
                  : "Execution core",
              },
              {
                key: "strategy",
                label: "Strategy",
                children:
                  detail.strategy_memory?.north_star ||
                  detail.strategy_memory?.summary ||
                  "No strategy memory yet.",
              },
              {
                key: "lane",
                label: "Lane",
                children: `${lanes.length} lanes`,
              },
              {
                key: "cycle",
                label: "Cycle",
                children: detail.current_cycle
                  ? `${detail.current_cycle.title || detail.current_cycle.cycle_id} · ${presentIndustryRuntimeStatus(detail.current_cycle.status)}`
                  : "No active cycle",
              },
              {
                key: "assignment",
                label: "Assignment",
                children: `${runtimeSignalCounts.assignment} live`,
              },
              {
                key: "report",
                label: "Report",
                children: `${runtimeSignalCounts.report} live`,
              },
              {
                key: "evidence",
                label: "Evidence",
                children: `${runtimeSignalCounts.evidence} records`,
              },
              {
                key: "decision",
                label: "Decision",
                children: `${runtimeSignalCounts.decision} records`,
              },
              {
                key: "patch",
                label: "Patch",
                children: `${runtimeSignalCounts.patch} records`,
              },
              {
                key: "runtime-focus",
                label: "Runtime Focus",
                children: runtimeFocusSummary,
              },
            ]}
          />
        </Space>
      </Card>

      <Card className="baize-card" size="small" title="Unified Runtime Chain">
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
              ? "Focused Assignment"
              : "Focused Backlog"
          }
          description={[
            focusSelection.summary || focusSelection.title || "Runtime detail is scoped to a selected subview.",
            focusSelection.status
              ? `Status ${presentIndustryRuntimeStatus(focusSelection.status)}`
              : null,
          ]
            .filter(Boolean)
            .join(" | ")}
          action={
            <Button size="small" onClick={() => onClearRuntimeFocus()}>
              Show full surface
            </Button>
          }
        />
      ) : null}

      <Card className="baize-card" size="small" title="Runtime Focus">
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          {focusedAssignment || focusedBacklog || followupReports.length ? (
            <Card size="small" title="Focus Surfaces" style={runtimeSurfaceCardStyle(true)}>
              <Space direction="vertical" size={10} style={{ width: "100%" }}>
                {followupReports.length ? (
                  <Card
                    size="small"
                    title={`Follow-up (${followupReports.length})`}
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
                        Open follow-up chat
                      </Button>
                    }
                  >
                    <Space direction="vertical" size={6} style={{ width: "100%" }}>
                      <Space wrap>
                        <Text strong style={{ color: "var(--baize-text-main)" }}>
                          {followupReports[0].headline || followupReports[0].report_id}
                        </Text>
                        <Tag color="orange">Follow-up</Tag>
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
                          "Follow-up report recorded."}
                      </Text>
                      <Space wrap>
                        {followupReports[0].assignment_id ? (
                          <Button
                            size="small"
                            onClick={() => onSelectAssignmentFocus(followupReports[0].assignment_id!)}
                          >
                            Focus linked assignment
                          </Button>
                        ) : null}
                        <Tag>{`Evidence ${followupReports[0].evidence_ids.length}`}</Tag>
                      </Space>
                    </Space>
                  </Card>
                ) : null}

                {focusedBacklog ? (
                  <Card
                    size="small"
                    title="Focused Backlog"
                    style={runtimeSurfaceCardStyle(true)}
                    extra={
                      <Button
                        size="small"
                        type="primary"
                        onClick={() => onSelectBacklogFocus(focusedBacklog.backlog_item_id)}
                      >
                        Focus backlog
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
                        <Tag>{`Evidence ${focusedBacklog.evidence_ids.length}`}</Tag>
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
                    title="Focused Assignment"
                    style={runtimeSurfaceCardStyle(true)}
                    extra={
                      <Button
                        size="small"
                        type="primary"
                        onClick={() => onSelectAssignmentFocus(focusedAssignment.assignment_id)}
                      >
                        Focus assignment
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
                        <Tag>{`Evidence ${focusedAssignment.evidence_ids.length}`}</Tag>
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
                  Focus assignment
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
                  Focus backlog
                </Button>
              ) : null}
            </Space>
          ) : null}
        </Space>
      </Card>

      {environmentVisibility.environment ||
      environmentVisibility.hostTwinSummary ||
      environmentVisibility.constraints.length ? (
        <Card className="baize-card" size="small" title="Execution Environment">
          <Space direction="vertical" size={10} style={{ width: "100%" }}>
            <Paragraph type="secondary" style={{ margin: "8px 0 0" }}>
              Environment and host-twin hints are surfaced when the runtime payload already provides them.
            </Paragraph>
            <Descriptions
              size="small"
              column={2}
              items={[
                {
                  key: "environment",
                  label: "Environment",
                  children: environmentVisibility.environment || "-",
                },
                {
                  key: "host-twin",
                  label: "Host Twin",
                  children: environmentVisibility.hostTwinSummary || "-",
                },
                {
                  key: "constraints",
                  label: "Constraints",
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
        <Card className="baize-card" size="small" title="Strategy">
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

      <Card className="baize-card" size="small" title="Report Snapshot">
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Paragraph type="secondary" style={{ margin: "8px 0 0" }}>
            Evidence-driven snapshots for quick review without opening the full evidence stream.
          </Paragraph>
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            {renderReportSnapshot(detail.reports.daily, "Daily")}
            {renderReportSnapshot(detail.reports.weekly, "Weekly")}
          </Space>
        </Space>
      </Card>

      <IndustryPlanningSurface detail={detail} locale={locale} />

      {staffingPresentation.hasAnyState ? (
        <Card className="baize-card" size="small" title="Staffing Closure">
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
              <Card size="small" title="Pending Proposals">
                <Space direction="vertical" size={6} style={{ width: "100%" }}>
                  {staffingPresentation.pendingProposals.map((item) => (
                    <Text key={item}>{item}</Text>
                  ))}
                </Space>
              </Card>
            ) : null}
            {staffingPresentation.temporarySeats.length ? (
              <Card size="small" title="Temporary Seats">
                <Space direction="vertical" size={6} style={{ width: "100%" }}>
                  {staffingPresentation.temporarySeats.map((item) => (
                    <Text key={item}>{item}</Text>
                  ))}
                </Space>
              </Card>
            ) : null}
            {staffingPresentation.researcher ? (
              <Card size="small" title="Researcher">
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

      <Card className="baize-card" size="small" title="Backlog">
        {detail.backlog.length === 0 ? (
          <Empty description="No backlog is active yet." style={{ margin: "8px 0" }} />
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
                        {selected ? "Focused" : "Focus backlog"}
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
                        {selected ? <Tag color="blue">Selected</Tag> : null}
                      </Space>
                      <Text type="secondary">
                        {backlogItem.summary || backlogItem.source_ref || "No summary captured yet."}
                      </Text>
                      <Space wrap>
                        {backlogItem.assignment_id ? (
                          <Tag>{`Assignment ${backlogItem.assignment_id}`}</Tag>
                        ) : null}
                        <Tag>{`Evidence ${backlogItem.evidence_ids.length}`}</Tag>
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

      <Card className="baize-card" size="small" title="Assignments">
        {detail.assignments.length === 0 ? (
          <Empty description="No live assignments yet." style={{ margin: "8px 0" }} />
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
                        {selected ? "Focused" : "Focus assignment"}
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
                        {selected ? <Tag color="blue">Selected</Tag> : null}
                      </Space>
                      <Text type="secondary">
                        {assignment.summary || "No assignment summary captured yet."}
                      </Text>
                      <Space wrap>
                        {assignment.backlog_item_id ? (
                          <Tag>{`Backlog ${assignment.backlog_item_id}`}</Tag>
                        ) : null}
                        {assignment.goal_id ? <Tag>{`Goal ${assignment.goal_id}`}</Tag> : null}
                        <Tag>{`Evidence ${assignment.evidence_ids.length}`}</Tag>
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

      <Card className="baize-card" size="small" title="Agent Reports">
        {detail.agent_reports.length === 0 ? (
          <Empty description="No agent reports yet." style={{ margin: "8px 0" }} />
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
                "No report summary captured yet.";
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
                            Focus linked assignment
                          </Button>
                        ) : null}
                        <Button
                          size="small"
                          type="primary"
                          onClick={() => onOpenAgentReportChat(report)}
                        >
                          Open report chat
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
                        {report.processed ? <Tag color="green">Processed</Tag> : null}
                        {report.needs_followup ? <Tag color="orange">Follow-up</Tag> : null}
                        {workContextId ? <Tag color="blue">{workContextId}</Tag> : null}
                      </Space>
                      <Text type="secondary">{summary}</Text>
                      <Space wrap>
                        {report.followup_reason ? <Tag>{report.followup_reason}</Tag> : null}
                        <Tag>{`Findings ${report.findings.length}`}</Tag>
                        <Tag>{`Evidence ${report.evidence_ids.length}`}</Tag>
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
