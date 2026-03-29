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
  IndustryRuntimeAgentReport,
  IndustryRuntimeAssignment,
  IndustryRuntimeBacklogItem,
  IndustryRuntimeSchedule,
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
  const runtimeSignalCounts = {
    assignment: detail.assignments.length,
    report: detail.agent_reports.length,
    evidence: detail.evidence.length,
    decision: detail.decisions.length,
    patch: detail.patches.length,
  };

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
                children:
                  detail.execution?.current_focus ||
                  focusSelection?.summary ||
                  focusSelection?.title ||
                  "No focused subview yet.",
              },
            ]}
          />
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
