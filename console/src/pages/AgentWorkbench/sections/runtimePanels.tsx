import {
  Button,
  Card,
  List,
  Space,
  Tag,
  Typography,
  message,
} from "antd";
import { ThunderboltOutlined } from "@ant-design/icons";

import {
  agentWorkbenchText,
  commonText,
  getLeaseKindLabel,
  getPhaseLabel,
  getStatusLabel,
  runtimeCenterText,
} from "../copy";
import { localizeWorkbenchText } from "../localize";
import type {
  AgentDetail,
  EnvironmentItem,
} from "../useAgentWorkbench";
import {
  presentDesiredStateLabel,
  presentRuntimeStatusLabel,
} from "../../../runtime/executionPresentation";
import {
  formatTime,
  statusColor,
} from "./shared";

const { Text } = Typography;

function pickRuntimeEnvironment(detail: AgentDetail): EnvironmentItem | null {
  const runtimeEnvironmentId = detail.runtime?.current_environment_id || null;
  if (
    runtimeEnvironmentId &&
    detail.workspace.current_environment?.id === runtimeEnvironmentId
  ) {
    return detail.workspace.current_environment;
  }
  if (runtimeEnvironmentId) {
    const matched = detail.environments.find((item) => item.id === runtimeEnvironmentId);
    if (matched) {
      return matched;
    }
  }
  return detail.workspace.current_environment || detail.environments[0] || null;
}

export function ActorRuntimePanel({
  detail,
  actorActionKey,
  onPauseActor,
  onResumeActor,
  onRetryMailbox,
  onCancelActor,
}: {
  detail: AgentDetail | null;
  actorActionKey: string | null;
  onPauseActor: (agentId: string) => Promise<unknown>;
  onResumeActor: (agentId: string) => Promise<unknown>;
  onRetryMailbox: (agentId: string, mailboxId: string) => Promise<unknown>;
  onCancelActor: (agentId: string, taskId?: string | null) => Promise<unknown>;
}) {
  if (!detail) {
    return null;
  }
  const runtime = detail.runtime;
  const agentId = detail.agent.agent_id;
  const runtimeEnvironment = pickRuntimeEnvironment(detail);
  const hostContract = runtimeEnvironment?.host_contract ?? null;
  const seatRuntime = runtimeEnvironment?.seat_runtime ?? null;
  const coordination = runtimeEnvironment?.host_twin?.coordination ?? null;
  const hostOwnership = runtimeEnvironment?.host_twin?.ownership ?? null;
  const officeDocumentTwin =
    runtimeEnvironment?.host_twin?.app_family_twins?.office_document ?? null;
  const writerLockScope =
    officeDocumentTwin?.writer_lock_scope ||
    runtimeEnvironment?.workspace_graph?.active_lock_summary ||
    runtimeEnvironment?.workspace_graph?.locks?.[0]?.writer_lock?.scope ||
    null;
  const handoffState =
    hostContract?.handoff_state ||
    runtimeEnvironment?.workspace_graph?.handoff_checkpoint?.state ||
    null;
  const handoffOwner =
    hostContract?.handoff_owner_ref ||
    hostOwnership?.handoff_owner_ref ||
    runtimeEnvironment?.workspace_graph?.handoff_checkpoint?.owner_ref ||
    null;
  const seatOwner =
    coordination?.seat_owner_ref ||
    hostOwnership?.seat_owner_agent_id ||
    seatRuntime?.lease_owner ||
    null;
  const workspaceOwner =
    coordination?.workspace_owner_ref ||
    runtimeEnvironment?.workspace_graph?.owner_agent_id ||
    null;
  const writerOwner =
    coordination?.writer_owner_ref ||
    runtimeEnvironment?.workspace_graph?.locks?.[0]?.writer_lock?.owner_agent_id ||
    null;
  const contentionSeverity = coordination?.contention_forecast?.severity || null;
  const contentionReason = coordination?.contention_forecast?.reason || null;
  const selectedSeatRef =
    coordination?.selected_seat_ref || seatRuntime?.selected_seat_ref || null;
  const seatSelectionPolicy =
    coordination?.seat_selection_policy || seatRuntime?.seat_selection_policy || null;
  const schedulerAction = coordination?.recommended_scheduler_action || null;
  const currentTaskId = runtime?.current_task_id || detail.agent.current_task_id || null;
  const pauseKey = `actor:pause:${agentId}`;
  const resumeKey = `actor:resume:${agentId}`;
  const cancelKey = `actor:cancel:${agentId}:${currentTaskId ?? "all"}`;
  return (
    <Card className="baize-card"
      title={
        <Space wrap>
          <ThunderboltOutlined />
          <span>{agentWorkbenchText.actorRuntimeTitle}</span>
          {runtime?.runtime_status ? (
            <Tag color={statusColor(runtime.runtime_status)}>
              {`运行态：${presentRuntimeStatusLabel(runtime.runtime_status)}`}
            </Tag>
          ) : null}
          {typeof runtime?.queue_depth === "number" ? (
            <Tag>{agentWorkbenchText.queueTag(runtime.queue_depth)}</Tag>
          ) : null}
        </Space>
      }
      extra={
        <Space wrap>
          <Button className="baize-btn"
            size="small"
            loading={actorActionKey === pauseKey}
            disabled={!runtime || runtime.desired_state === "paused"}
            onClick={() => {
              void onPauseActor(agentId).catch((err) => {
                message.error(err instanceof Error ? err.message : String(err));
              });
            }}
          >
            {runtimeCenterText.actionPause}
          </Button>
          <Button className="baize-btn"
            size="small"
            loading={actorActionKey === resumeKey}
            disabled={!runtime || runtime.desired_state === "active"}
            onClick={() => {
              void onResumeActor(agentId).catch((err) => {
                message.error(err instanceof Error ? err.message : String(err));
              });
            }}
          >
            {runtimeCenterText.actionResume}
          </Button>
          <Button className="baize-btn"
            size="small"
            danger
            loading={actorActionKey === cancelKey}
            disabled={!runtime && !currentTaskId}
            onClick={() => {
              void onCancelActor(agentId, currentTaskId).catch((err) => {
                message.error(err instanceof Error ? err.message : String(err));
              });
            }}
          >
            {commonText.cancel}
          </Button>
        </Space>
      }
      style={{ marginBottom: 32 }}
    >
      <Space wrap style={{ marginBottom: 32 }}>
        {runtime?.desired_state ? (
          <Tag>{`调度目标：${presentDesiredStateLabel(runtime.desired_state)}`}</Tag>
        ) : null}
        {runtime?.current_task_id ? (
          <Tag>{agentWorkbenchText.taskTag(runtime.current_task_id)}</Tag>
        ) : null}
        {runtime?.current_mailbox_id ? (
          <Tag>{agentWorkbenchText.mailboxTag(runtime.current_mailbox_id)}</Tag>
        ) : null}
        {runtime?.current_environment_id ? (
          <Tag>{agentWorkbenchText.environmentTag(runtime.current_environment_id)}</Tag>
        ) : null}
        {runtime?.last_checkpoint_id ? (
          <Tag>{agentWorkbenchText.checkpointTag(runtime.last_checkpoint_id)}</Tag>
        ) : null}
      </Space>

      {runtimeEnvironment &&
      (seatOwner ||
        handoffState ||
        handoffOwner ||
        writerOwner ||
        contentionSeverity ||
        schedulerAction ||
        writerLockScope) ? (
        <Card
          className="baize-card"
          size="small"
          title="Host coordination"
          style={{ marginBottom: 32 }}
        >
          <Space wrap style={{ marginBottom: 16 }}>
            {selectedSeatRef ? <Tag>{`Seat ${selectedSeatRef}`}</Tag> : null}
            {seatSelectionPolicy ? <Tag>{seatSelectionPolicy}</Tag> : null}
            {handoffState ? <Tag color="orange">{handoffState}</Tag> : null}
            {contentionSeverity ? (
              <Tag color={contentionSeverity === "blocked" ? "red" : "gold"}>
                {`Contention ${contentionSeverity}`}
              </Tag>
            ) : null}
            {schedulerAction ? <Tag color="blue">{`Action ${schedulerAction}`}</Tag> : null}
          </Space>
          <Space direction="vertical" size={4}>
            {seatOwner ? <Text>{`Seat owner: ${seatOwner}`}</Text> : null}
            {workspaceOwner ? <Text>{`Workspace owner: ${workspaceOwner}`}</Text> : null}
            {writerOwner ? <Text>{`Writer owner: ${writerOwner}`}</Text> : null}
            {handoffState ? <Text>{`Handoff: ${handoffState}`}</Text> : null}
            {handoffOwner ? <Text>{`Handoff owner: ${handoffOwner}`}</Text> : null}
            {contentionSeverity ? (
              <Text>
                {`Contention: ${contentionSeverity}${
                  contentionReason ? ` (${contentionReason})` : ""
                }`}
              </Text>
            ) : null}
            {schedulerAction ? <Text>{`Scheduler action: ${schedulerAction}`}</Text> : null}
            {writerLockScope ? <Text>{`Writer lock: ${writerLockScope}`}</Text> : null}
          </Space>
        </Card>
      ) : null}

      {detail.thread_bindings.length > 0 ? (
        <div style={{ marginBottom: 32 }}>
          <Text strong>{agentWorkbenchText.threadBindingsLabel}:</Text>{" "}
          {detail.thread_bindings.slice(0, 6).map((binding) => (
            <Tag key={binding.thread_id}>{binding.thread_id}</Tag>
          ))}
        </div>
      ) : null}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
          gap: 16,
        }}
      >
        <Card className="baize-card" size="small" title={agentWorkbenchText.mailboxSectionTitle}>
          <List
            dataSource={detail.mailbox.slice(0, 6)}
            locale={{ emptyText: agentWorkbenchText.noMailboxWork }}
            renderItem={(item) => (
              <List.Item
                key={item.id}
                actions={[
                  ["failed", "blocked", "retry-wait", "cancelled"].includes(item.status) ? (
                    <Button className="baize-btn"
                      key={`retry-${item.id}`}
                      size="small"
                      type="link"
                      loading={actorActionKey === `actor:retry:${agentId}:${item.id}`}
                      onClick={() => {
                        void onRetryMailbox(agentId, item.id).catch((err) => {
                          message.error(err instanceof Error ? err.message : String(err));
                        });
                      }}
                    >
                      {commonText.retry}
                    </Button>
                  ) : null,
                ].filter(Boolean)}
              >
                <Space direction="vertical" size={0}>
                  <Text strong>{localizeWorkbenchText(item.title)}</Text>
                  <Space wrap>
                    <Tag color={statusColor(item.status)}>{getStatusLabel(item.status)}</Tag>
                    {item.capability_ref ? <Tag>{item.capability_ref}</Tag> : null}
                  </Space>
                  <Text type="secondary">
                    {formatTime(
                      item.completed_at ||
                        item.started_at ||
                        item.claimed_at ||
                        item.retry_after_at,
                      runtimeCenterText.noTimestamp,
                    )}
                  </Text>
                </Space>
              </List.Item>
            )}
          />
        </Card>

        <Card className="baize-card" size="small" title={agentWorkbenchText.leasesSectionTitle}>
          <List
            dataSource={detail.leases.slice(0, 6)}
            locale={{ emptyText: agentWorkbenchText.noActiveLeases }}
            renderItem={(lease) => (
              <List.Item key={lease.id}>
                <Space direction="vertical" size={0}>
                  <Text strong>{lease.resource_ref}</Text>
                  <Space wrap>
                    <Tag>{getLeaseKindLabel(lease.lease_kind)}</Tag>
                    <Tag color={statusColor(lease.lease_status)}>
                      {getStatusLabel(lease.lease_status)}
                    </Tag>
                  </Space>
                  <Text type="secondary">
                    {formatTime(
                      lease.heartbeat_at ||
                        lease.acquired_at ||
                        lease.expires_at ||
                        lease.released_at,
                      runtimeCenterText.noTimestamp,
                    )}
                  </Text>
                </Space>
              </List.Item>
            )}
          />
        </Card>

        <Card className="baize-card" size="small" title={agentWorkbenchText.checkpointsSectionTitle}>
          <List
            dataSource={detail.checkpoints.slice(0, 6)}
            locale={{ emptyText: agentWorkbenchText.noCheckpoints }}
            renderItem={(item) => (
              <List.Item key={item.id}>
                <Space direction="vertical" size={0}>
                  <Text strong>
                    {localizeWorkbenchText(item.summary || item.checkpoint_kind)}
                  </Text>
                  <Space wrap>
                    <Tag color={statusColor(item.status)}>{getStatusLabel(item.status)}</Tag>
                    <Tag>{getPhaseLabel(item.phase)}</Tag>
                    {item.environment_ref ? <Tag>{item.environment_ref}</Tag> : null}
                  </Space>
                  <Text type="secondary">
                    {formatTime(
                      item.updated_at || item.created_at,
                      runtimeCenterText.noTimestamp,
                    )}
                  </Text>
                </Space>
              </List.Item>
            )}
          />
        </Card>
      </div>
    </Card>
  );
}
