import type { ReactNode } from "react";
import { Alert, Card, Empty, List, Space, Tag, Typography } from "antd";
import type {
  IndustryInstanceDetail,
  IndustryRuntimeAssignment,
  IndustryRuntimeAgentReport,
} from "../../api/modules/industry";
import { normalizeSpiderMeshBrand } from "../../utils/brand";
import { getRiskLabel, getStatusLabel } from "./copy";
import {
  employmentModeColor,
  presentEmploymentModeLabel,
  presentExecutionActorName,
} from "../../runtime/executionPresentation";
import {
  runtimeRiskColor,
  runtimeStatusColor,
} from "../../runtime/tagSemantics";
import {
  buildStaffingPresentation,
  presentSeatLifecycleState,
} from "../../runtime/staffingGapPresentation";
import { presentControlChain } from "../../runtime/controlChainPresentation";
import {
  buildNeedsBrainConfirmation,
  resolveEscalations,
  resolveRoleContract,
} from "./executionSeatPresentation";
import type {
  AgentDetail,
  AgentProfile,
  AgentTaskListItem,
} from "./useAgentWorkbench";

const { Paragraph, Text } = Typography;

type Props = {
  agent: AgentProfile;
  agents: AgentProfile[];
  agentDetail: AgentDetail | null;
  industryDetail: IndustryInstanceDetail | null;
  industryDetailLoading: boolean;
  industryDetailError: string | null;
};

function normalizeNonEmpty(value: string | null | undefined): string | null {
  const normalized = value?.trim();
  return normalized ? normalized : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function formatTime(value: string | null | undefined, fallback: string): string {
  if (!value) {
    return fallback;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

function sortByUpdatedAtDesc<
  T extends { updated_at?: string | null; created_at?: string | null },
>(items: T[]): T[] {
  return [...items].sort((left, right) => {
    const leftTime = Date.parse(left.updated_at || left.created_at || "") || 0;
    const rightTime = Date.parse(right.updated_at || right.created_at || "") || 0;
    return rightTime - leftTime;
  });
}

function matchesAgent(value: string | null | undefined, agentId: string): boolean {
  return normalizeNonEmpty(value) === agentId;
}

function resolveLaneLabel(
  detail: IndustryInstanceDetail,
  laneId: string | null | undefined,
): string | null {
  const normalizedLaneId = normalizeNonEmpty(laneId);
  if (!normalizedLaneId) {
    return null;
  }
  const matched = detail.lanes.find((lane) => lane.lane_id === normalizedLaneId);
  return matched?.title || matched?.lane_key || normalizedLaneId;
}

function resolveAgentLabel(
  agents: AgentProfile[],
  agentId: string | null | undefined,
): string | null {
  const normalizedAgentId = normalizeNonEmpty(agentId);
  if (!normalizedAgentId) {
    return null;
  }
  const matched = agents.find((item) => item.agent_id === normalizedAgentId);
  if (!matched) {
    return normalizedAgentId;
  }
  return presentExecutionActorName(matched.agent_id, matched.name || matched.agent_id);
}

function resolveCurrentAssignment(
  agent: AgentProfile,
  detail: IndustryInstanceDetail,
): IndustryRuntimeAssignment | null {
  const matchedAssignments = detail.assignments.filter((assignment) =>
    matchesAgent(assignment.owner_agent_id, agent.agent_id),
  );
  const prioritized = sortByUpdatedAtDesc(matchedAssignments).sort((left, right) => {
    const priority = (status: string) => {
      if (["active", "running", "executing", "claimed", "assigned", "waiting-report", "planned", "queued"].includes(status)) {
        return 0;
      }
      if (["blocked", "review", "waiting-confirm"].includes(status)) {
        return 1;
      }
      if (status === "completed") {
        return 2;
      }
      return 3;
    };
    return priority(left.status) - priority(right.status);
  });
  return prioritized[0] || null;
}

function resolveLatestReport(
  agent: AgentProfile,
  detail: IndustryInstanceDetail,
): IndustryRuntimeAgentReport | null {
  const matched = sortByUpdatedAtDesc(
    detail.agent_reports.filter((report) => matchesAgent(report.owner_agent_id, agent.agent_id)),
  );
  return matched[0] || null;
}

function renderTagList(items: string[]): ReactNode {
  if (items.length === 0) {
    return <Text type="secondary">暂无</Text>;
  }
  return (
    <Space wrap size={[6, 6]}>
      {items.map((item) => (
        <Tag key={item}>{normalizeSpiderMeshBrand(item)}</Tag>
      ))}
    </Space>
  );
}

function taskPriority(status: string | null | undefined): number {
  const normalized = String(status || "").toLowerCase();
  if (["running", "active", "executing", "claimed", "assigned", "queued", "planned", "waiting"].includes(normalized)) {
    return 0;
  }
  if (["blocked", "failed", "review", "waiting-confirm"].includes(normalized)) {
    return 1;
  }
  if (normalized === "completed") {
    return 2;
  }
  return 3;
}

function sortAgentTasks(tasks: AgentTaskListItem[]): AgentTaskListItem[] {
  return [...tasks].sort((left, right) => {
    const leftPriority = taskPriority(left.task.status);
    const rightPriority = taskPriority(right.task.status);
    if (leftPriority !== rightPriority) {
      return leftPriority - rightPriority;
    }
    const leftTime = Date.parse(left.task.updated_at || left.runtime?.updated_at || "") || 0;
    const rightTime = Date.parse(right.task.updated_at || right.runtime?.updated_at || "") || 0;
    return rightTime - leftTime;
  });
}

export default function V7ExecutionSeatPanel({
  agent,
  agents,
  agentDetail,
  industryDetail,
  industryDetailLoading,
  industryDetailError,
}: Props) {
  if (industryDetailLoading) {
    return (
      <Card className="baize-card" style={{ marginBottom: 32 }} title="执行位任务与汇报">
        <Text type="secondary">正在读取这个执行位的任务、汇报和周期信息。</Text>
      </Card>
    );
  }

  if (industryDetailError) {
    return (
      <Alert
        showIcon
        type="warning"
        message="执行位任务与汇报暂不可用"
        description={industryDetailError}
        style={{ marginBottom: 32 }}
      />
    );
  }

  if (!industryDetail) {
    return (
      <Card className="baize-card" style={{ marginBottom: 32 }} title="执行位任务与汇报">
        <Empty description="当前执行位还没有绑定正式行业运行视图。" />
      </Card>
    );
  }

  const roleContract = resolveRoleContract(agent, industryDetail);
  const currentAssignment = resolveCurrentAssignment(agent, industryDetail);
  const latestReport = resolveLatestReport(agent, industryDetail);
  const escalations = resolveEscalations(agent, industryDetail);
  const taskItems = sortAgentTasks(agentDetail?.tasks ?? []).slice(0, 6);
  const activeTaskCount = taskItems.filter(
    (item) =>
      !["completed", "failed", "cancelled"].includes(
        String(item.task.status || "").toLowerCase(),
      ),
  ).length;
  const completedTaskCount = taskItems.filter(
    (item) => String(item.task.status || "").toLowerCase() === "completed",
  ).length;
  const pendingCapabilityDecisions =
    agentDetail?.capability_surface?.pending_decisions ?? [];
  const focusLaneLabels = (industryDetail.current_cycle?.focus_lane_ids || [])
    .map((laneId) => resolveLaneLabel(industryDetail, laneId))
    .filter((item): item is string => Boolean(item));
  const assignmentMetadata = isRecord(currentAssignment?.metadata)
    ? currentAssignment.metadata
    : {};
  const fixedFlowName = normalizeNonEmpty(
    String(
      assignmentMetadata.fixed_sop_binding_name ?? assignmentMetadata.routine_name ?? "",
    ),
  );
  const fixedFlowId = normalizeNonEmpty(
    String(
      assignmentMetadata.fixed_sop_binding_id ?? assignmentMetadata.routine_id ?? "",
    ),
  );
  const seatEmploymentMode =
    roleContract?.employment_mode || agent.employment_mode || "career";
  const seatLifecycleState = presentSeatLifecycleState({
    staffing: industryDetail.staffing,
    agentId: agent.agent_id,
    employmentMode: seatEmploymentMode,
  });
  const staffingPresentation = buildStaffingPresentation(industryDetail.staffing);
  const targetedProposal = industryDetail.staffing.pending_proposals.find(
    (proposal) => normalizeNonEmpty(proposal.target_agent_id || undefined) === agent.agent_id,
  );
  const needsBrainConfirmation = buildNeedsBrainConfirmation(pendingCapabilityDecisions);
  const controlChain = presentControlChain(industryDetail);
  const seatRefs = new Set(
    [currentAssignment?.assignment_id, latestReport?.report_id].filter(
      (value): value is string => Boolean(value),
    ),
  );

  return (
    <Card
      className="baize-card"
      style={{ marginBottom: 32 }}
      title="执行位任务与汇报"
      extra={
        industryDetail.current_cycle ? (
          <Space wrap size={[6, 6]}>
            <Tag color={runtimeStatusColor(industryDetail.current_cycle.status)}>
              {getStatusLabel(industryDetail.current_cycle.status)}
            </Tag>
            <Tag>{normalizeSpiderMeshBrand(industryDetail.current_cycle.cycle_kind)}</Tag>
            {industryDetail.current_cycle.due_at ? (
              <Tag>{`截止 ${formatTime(industryDetail.current_cycle.due_at, "-")}`}</Tag>
            ) : null}
          </Space>
        ) : null
      }
    >
      <Paragraph type="secondary">
        这里直接显示这个执行位当前接到的任务、最近汇报、阻塞事项和需要主脑确认的内容，不再使用
        V7 等内部术语做主标题。
      </Paragraph>
      <Alert
        showIcon
        type={
          seatLifecycleState === "Pending approval" || seatLifecycleState === "Pending promotion"
            ? "warning"
            : seatLifecycleState === "Temporary seat"
              ? "info"
              : "success"
        }
        message={`Seat lifecycle: ${seatLifecycleState}`}
        description={
          seatLifecycleState === "Pending promotion"
            ? `当前临时 seat 正在等待长期岗位审批${targetedProposal?.decision_request_id ? `，decision ${targetedProposal.decision_request_id}` : ""}。`
            : seatLifecycleState === "Pending approval"
              ? `当前 seat 变更尚未获批${targetedProposal?.decision_request_id ? `，decision ${targetedProposal.decision_request_id}` : ""}。`
              : seatLifecycleState === "Temporary seat"
                ? "临时岗位用于承接阶段性任务，当前派单、任务和汇报清空后会自动退出。"
                : "这个 seat 属于正式长期岗位。"
        }
        style={{ marginBottom: 16 }}
      />
      {seatEmploymentMode === "temporary" ? (
        <Alert
          showIcon
          type="info"
          message="这个执行位是临时岗位"
          description="临时岗位用于承接阶段性任务，当前派单、任务和汇报清空后会自动退出，不会长期保留在正式团队编制中。"
          style={{ marginBottom: 16 }}
        />
      ) : null}
      {staffingPresentation.activeGap && targetedProposal ? (
        <Alert
          showIcon
          type="warning"
          message={staffingPresentation.activeGap.title}
          description={staffingPresentation.activeGap.detail}
          style={{ marginBottom: 16 }}
        />
      ) : null}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: 16,
        }}
      >
        <Card className="baize-card" size="small" title="当前接收任务">
          <Space wrap size={[6, 6]} style={{ marginBottom: 12 }}>
            <Tag color="blue">{`任务 ${taskItems.length}`}</Tag>
            <Tag color="processing">{`进行中 ${activeTaskCount}`}</Tag>
            <Tag color="green">{`已完成 ${completedTaskCount}`}</Tag>
          </Space>
          {taskItems.length > 0 ? (
            <List
              size="small"
              dataSource={taskItems}
              renderItem={(item) => {
                const runtimeRisk = item.runtime?.risk_level || item.task.current_risk_level;
                const runtimeStatus = item.runtime?.runtime_status;
                const runtimePhase = item.runtime?.current_phase;
                const summary =
                  item.task.summary ||
                  item.runtime?.last_result_summary ||
                  item.runtime?.last_error_summary ||
                  "";
                return (
                  <List.Item key={item.task.id}>
                    <Space direction="vertical" size={2} style={{ width: "100%" }}>
                      <Space wrap size={[6, 6]}>
                        <Text strong>
                          {normalizeSpiderMeshBrand(item.task.title || item.task.id)}
                        </Text>
                        {item.task.status ? (
                          <Tag color={runtimeStatusColor(item.task.status)}>
                            {getStatusLabel(item.task.status)}
                          </Tag>
                        ) : null}
                        {runtimeStatus ? <Tag>{getStatusLabel(runtimeStatus)}</Tag> : null}
                        {runtimePhase ? <Tag>{normalizeSpiderMeshBrand(runtimePhase)}</Tag> : null}
                        {runtimeRisk ? (
                          <Tag color={runtimeRiskColor(runtimeRisk)}>
                            {getRiskLabel(runtimeRisk)}
                          </Tag>
                        ) : null}
                      </Space>
                      {summary ? (
                        <Text type="secondary">{normalizeSpiderMeshBrand(summary)}</Text>
                      ) : (
                        <Text type="secondary">暂无任务摘要</Text>
                      )}
                      <Text type="secondary">
                        {formatTime(item.task.updated_at || item.runtime?.updated_at, "-")}
                      </Text>
                    </Space>
                  </List.Item>
                );
              }}
            />
          ) : (
            <Empty
              description="当前还没有分派到这个执行位的任务。"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          )}
        </Card>

        <Card className="baize-card" size="small" title="最新汇报">
          {latestReport ? (
            <>
              <Space wrap size={[6, 6]} style={{ marginBottom: 12 }}>
                <Tag color={runtimeStatusColor(latestReport.status)}>
                  {getStatusLabel(latestReport.status)}
                </Tag>
                {latestReport.result ? <Tag>{getStatusLabel(latestReport.result)}</Tag> : null}
                {latestReport.risk_level ? (
                  <Tag color={runtimeRiskColor(latestReport.risk_level)}>
                    {getRiskLabel(latestReport.risk_level)}
                  </Tag>
                ) : null}
                {latestReport.needs_followup ? (
                  <Tag color="orange">需要跟进</Tag>
                ) : (
                  <Tag color="green">无需追加跟进</Tag>
                )}
                <Tag color={latestReport.processed ? "green" : "orange"}>
                  {latestReport.processed ? "已回流主脑" : "待主脑处理"}
                </Tag>
              </Space>
              <Paragraph>
                <Text strong>标题：</Text> {latestReport.headline || latestReport.report_id}
              </Paragraph>
              <Paragraph>
                <Text strong>摘要：</Text>{" "}
                {normalizeSpiderMeshBrand(latestReport.summary || "") || "暂无摘要"}
              </Paragraph>
              {(latestReport.findings || []).length > 0 ? (
                <Paragraph>
                  <Text strong>发现：</Text>
                  <div style={{ marginTop: 6 }}>{renderTagList((latestReport.findings || []).slice(0, 6))}</div>
                </Paragraph>
              ) : null}
              {(latestReport.uncertainties || []).length > 0 ? (
                <Paragraph>
                  <Text strong>不确定项：</Text>
                  <div style={{ marginTop: 6 }}>
                    {renderTagList((latestReport.uncertainties || []).slice(0, 6))}
                  </div>
                </Paragraph>
              ) : null}
              {latestReport.recommendation ? (
                <Paragraph>
                  <Text strong>建议：</Text>{" "}
                  {normalizeSpiderMeshBrand(latestReport.recommendation) || latestReport.recommendation}
                </Paragraph>
              ) : null}
              {latestReport.followup_reason ? (
                <Paragraph>
                  <Text strong>跟进原因：</Text>{" "}
                  {normalizeSpiderMeshBrand(latestReport.followup_reason) || latestReport.followup_reason}
                </Paragraph>
              ) : null}
              <Paragraph>
                <Text strong>证据：</Text> {latestReport.evidence_ids.length}
                {" / "}
                <Text strong>决策：</Text> {latestReport.decision_ids.length}
              </Paragraph>
              <Paragraph style={{ marginBottom: 0 }}>
                <Text strong>更新时间：</Text>{" "}
                {formatTime(latestReport.updated_at || latestReport.created_at, "-")}
              </Paragraph>
            </>
          ) : (
            <Empty
              description="当前还没有正式汇报。"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          )}
        </Card>

        <Card className="baize-card" size="small" title="待主脑确认">
          {needsBrainConfirmation.length > 0 ? (
            <List
              size="small"
              dataSource={needsBrainConfirmation}
              renderItem={(item) => (
                <List.Item key={item.id}>
                  <Space direction="vertical" size={2} style={{ width: "100%" }}>
                    <Space wrap size={[6, 6]}>
                      <Text strong>{normalizeSpiderMeshBrand(item.title)}</Text>
                      <Tag color={item.color}>待确认</Tag>
                    </Space>
                    <Text type="secondary">{normalizeSpiderMeshBrand(item.detail)}</Text>
                  </Space>
                </List.Item>
              )}
            />
          ) : (
            <Empty
              description="当前没有待主脑确认的事项。"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          )}
        </Card>

        <Card className="baize-card" size="small" title="风险与阻塞">
          {escalations.length > 0 ? (
            <List
              size="small"
              dataSource={escalations}
              renderItem={(report) => (
                <List.Item key={report.report_id}>
                  <Space direction="vertical" size={2} style={{ width: "100%" }}>
                    <Space wrap size={[6, 6]}>
                      <Text strong>
                        {normalizeSpiderMeshBrand(report.headline || report.report_id)}
                      </Text>
                      <Tag color={runtimeStatusColor(report.status)}>
                        {getStatusLabel(report.status)}
                      </Tag>
                      {report.result ? <Tag>{getStatusLabel(report.result)}</Tag> : null}
                      {report.risk_level ? (
                        <Tag color={runtimeRiskColor(report.risk_level)}>
                          {getRiskLabel(report.risk_level)}
                        </Tag>
                      ) : null}
                    </Space>
                    <Text type="secondary">
                      {normalizeSpiderMeshBrand(report.summary || "") || "这条汇报需要主脑处理。"}
                    </Text>
                  </Space>
                </List.Item>
              )}
            />
          ) : (
            <Empty
              description="当前没有需要升级处理的阻塞。"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          )}
        </Card>

        <Card className="baize-card" size="small" title="当前派单">
          {currentAssignment ? (
            <>
              <Space wrap size={[6, 6]} style={{ marginBottom: 12 }}>
                <Tag color={runtimeStatusColor(currentAssignment.status)}>
                  {getStatusLabel(currentAssignment.status)}
                </Tag>
                {currentAssignment.lane_id ? (
                  <Tag>{resolveLaneLabel(industryDetail, currentAssignment.lane_id)}</Tag>
                ) : null}
                {currentAssignment.report_back_mode ? (
                  <Tag>{`回流 ${normalizeSpiderMeshBrand(currentAssignment.report_back_mode)}`}</Tag>
                ) : null}
              </Space>
              <Paragraph>
                <Text strong>标题：</Text>{" "}
                {currentAssignment.title || currentAssignment.assignment_id}
              </Paragraph>
              <Paragraph>
                <Text strong>摘要：</Text>{" "}
                {normalizeSpiderMeshBrand(currentAssignment.summary || "") || "暂无摘要"}
              </Paragraph>
              <Paragraph>
                <Text strong>Backlog：</Text> {currentAssignment.backlog_item_id || "-"}
              </Paragraph>
              <Paragraph>
                <Text strong>Goal：</Text> {currentAssignment.goal_id || "-"}
              </Paragraph>
              <Paragraph style={{ marginBottom: 0 }}>
                <Text strong>最近更新：</Text>{" "}
                {formatTime(currentAssignment.updated_at || currentAssignment.created_at, "-")}
              </Paragraph>
            </>
          ) : (
            <Empty
              description="当前没有挂接中的派单。"
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          )}
        </Card>

        <Card className="baize-card" size="small" title="岗位职责">
          <Paragraph>
            <Text strong>角色：</Text>{" "}
            {normalizeSpiderMeshBrand(roleContract?.role_name || agent.role_name) || "-"}
          </Paragraph>
          <Paragraph>
            <Text strong>职责：</Text>{" "}
            {normalizeSpiderMeshBrand(
              roleContract?.role_summary || agent.role_summary || agent.current_focus,
            ) || "暂无职责摘要"}
          </Paragraph>
          <Paragraph>
            <Text strong>使命：</Text>{" "}
            {normalizeSpiderMeshBrand(roleContract?.mission || agent.mission) || "暂无使命定义"}
          </Paragraph>
          <Paragraph>
            <Text strong>汇报给：</Text>{" "}
            {resolveAgentLabel(agents, roleContract?.reports_to || agent.reports_to) || "Spider Mesh 主脑"}
          </Paragraph>
          <Paragraph>
            <Text strong>岗位约束：</Text>{" "}
            <Tag color={runtimeRiskColor(roleContract?.risk_level || agent.risk_level)}>
              {getRiskLabel(roleContract?.risk_level || agent.risk_level || "auto")}
            </Tag>
            {roleContract?.goal_kind ? (
              <Tag>{normalizeSpiderMeshBrand(roleContract.goal_kind)}</Tag>
            ) : null}
            <Tag color={employmentModeColor(seatEmploymentMode)}>
              {presentEmploymentModeLabel(seatEmploymentMode)}
            </Tag>
            <Tag>{agent.activation_mode === "on-demand" ? "按需唤起" : "常驻"}</Tag>
          </Paragraph>
          <div style={{ marginBottom: 12 }}>
            <Text strong>能力合同：</Text>
            <div style={{ marginTop: 8 }}>{renderTagList(roleContract?.capabilities || [])}</div>
          </div>
          <div style={{ marginBottom: 12 }}>
            <Text strong>证据要求：</Text>
            <div style={{ marginTop: 8 }}>
              {renderTagList(roleContract?.evidence_expectations || agent.evidence_expectations)}
            </div>
          </div>
          <div>
            <Text strong>环境约束：</Text>
            <div style={{ marginTop: 8 }}>
              {renderTagList(roleContract?.environment_constraints || agent.environment_constraints)}
            </div>
          </div>
        </Card>

        <Card className="baize-card" size="small" title="运行线程与例行任务">
          <Paragraph>
            <Text strong>当前任务：</Text>{" "}
            {currentAssignment?.task_id ||
              agentDetail?.runtime?.current_task_id ||
              agent.current_task_id ||
              "-"}
          </Paragraph>
          <Paragraph>
            <Text strong>当前固定流程：</Text>{" "}
            {fixedFlowName || fixedFlowId || "暂无固定流程挂接"}
          </Paragraph>
          <Paragraph>
            <Text strong>线程：</Text>{" "}
            {agentDetail?.runtime?.metadata && isRecord(agentDetail.runtime.metadata)
              ? normalizeNonEmpty(String(agentDetail.runtime.metadata.session_kind ?? "")) ||
                agent.thread_id ||
                "-"
              : agent.thread_id || "-"}
          </Paragraph>
          <Paragraph>
            <Text strong>Mailbox：</Text>{" "}
            {agentDetail?.runtime?.current_mailbox_id || agent.current_mailbox_id || "-"}
          </Paragraph>
          <Paragraph style={{ marginBottom: 0 }}>
            <Text strong>当前焦点车道：</Text>{" "}
            {focusLaneLabels.length > 0 ? focusLaneLabels.join(" / ") : "当前周期没有声明 focus lane"}
          </Paragraph>
        </Card>
        <Card className="baize-card" size="small" title="Main-brain control chain">
          {controlChain.nodes.length > 0 ? (
            <>
              <Space wrap size={[6, 6]} style={{ marginBottom: 12 }}>
                {controlChain.loopState ? (
                  <Tag color={runtimeStatusColor(controlChain.loopState)}>
                    {controlChain.loopStateLabel}
                  </Tag>
                ) : null}
                {controlChain.currentOwner ? <Tag>{controlChain.currentOwner}</Tag> : null}
                {controlChain.currentRisk ? (
                  <Tag color={runtimeRiskColor(controlChain.currentRisk)}>
                    {getRiskLabel(controlChain.currentRisk)}
                  </Tag>
                ) : null}
              </Space>
              <List
                size="small"
                dataSource={controlChain.nodes}
                renderItem={(node) => (
                  <List.Item key={node.id}>
                    <Space direction="vertical" size={2} style={{ width: "100%" }}>
                      <Space wrap size={[6, 6]}>
                        <Text strong>{normalizeSpiderMeshBrand(node.label)}</Text>
                        <Tag color={runtimeStatusColor(node.status)}>{node.statusLabel}</Tag>
                        {node.currentRef ? <Tag>{node.currentRef}</Tag> : null}
                        {node.currentRef && seatRefs.has(node.currentRef) ? (
                          <Tag color="blue">This seat</Tag>
                        ) : null}
                      </Space>
                      <Text type="secondary">
                        {normalizeSpiderMeshBrand(node.summary || "") || "No chain summary yet."}
                      </Text>
                    </Space>
                  </List.Item>
                )}
              />
              {controlChain.synthesis ? (
                <Paragraph style={{ marginBottom: 0, marginTop: 12 }}>
                  <Text strong>Synthesis:</Text> {controlChain.synthesis.summary}
                </Paragraph>
              ) : null}
            </>
          ) : (
            <Empty
              description="No main-brain control chain is available yet."
              image={Empty.PRESENTED_IMAGE_SIMPLE}
            />
          )}
        </Card>
      </div>
    </Card>
  );
}
