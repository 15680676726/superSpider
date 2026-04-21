import { Alert, Button, Card, Empty, Space, Spin, Tag, Typography } from "antd";
import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { localizeWorkbenchText } from "../pages/AgentWorkbench/localize";
import { useRuntimeExecutionPulse } from "../hooks/useRuntimeExecutionPulse";
import {
  formatRuntimeRelativeAge,
  presentDesiredStateLabel,
  presentExecutionActorName,
  presentExecutionClassLabel,
  presentRuntimeStatusLabel,
  presentRuntimeTaskLabel,
} from "../runtime/executionPresentation";
import { runtimeStatusColor } from "../runtime/tagSemantics";
import styles from "./RuntimeExecutionStrip.module.less";

const { Text } = Typography;

export interface RuntimeExecutionStripPulse {
  items: ReturnType<typeof useRuntimeExecutionPulse>["items"];
  loading: ReturnType<typeof useRuntimeExecutionPulse>["loading"];
  error: ReturnType<typeof useRuntimeExecutionPulse>["error"];
}

export interface RuntimeExecutionStripProps {
  actor?: string;
  preferredAgentId?: string | null;
  maxItems?: number;
  sticky?: boolean;
  title?: string;
  summary?: string;
  pulse?: RuntimeExecutionStripPulse;
}

function signalColor(level: "good" | "watch" | "danger"): string {
  if (level === "danger") {
    return "error";
  }
  if (level === "watch") {
    return "warning";
  }
  return "success";
}

function executionStateColor(state: string | null | undefined): string {
  if (state === "failed" || state === "idle-loop") {
    return "error";
  }
  if (
    state === "waiting-confirm" ||
    state === "waiting-resource" ||
    state === "waiting-verification"
  ) {
    return "warning";
  }
  if (state === "executing") {
    return "processing";
  }
  return "default";
}

function formatExecutionStateLabel(state: string | null | undefined): string | null {
  switch (state) {
    case "executing":
      return "执行中";
    case "waiting-confirm":
      return "待确认";
    case "waiting-verification":
      return "待人工验证";
    case "waiting-resource":
      return "待外部资源";
    case "idle-loop":
      return "疑似空转";
    case "failed":
      return "失败";
    case "idle":
      return "空闲";
    default:
      return typeof state === "string" && state.trim() ? state.trim() : null;
  }
}

function formatAssignmentStatusLabel(status: string | null | undefined): string | null {
  switch (status) {
    case "planned":
      return "已规划";
    case "queued":
      return "待执行";
    case "running":
      return "执行中";
    case "waiting-report":
      return "待回报";
    default:
      return typeof status === "string" && status.trim() ? status.trim() : null;
  }
}

export default function RuntimeExecutionStrip({
  actor = "runtime-strip",
  preferredAgentId = null,
  maxItems = 4,
  sticky = true,
  title = "当前执行总览",
  summary = "直接查看谁在执行、当前在做什么、为何触发，以及卡在哪一步。",
  pulse,
}: RuntimeExecutionStripProps) {
  const navigate = useNavigate();
  const hookPulse = useRuntimeExecutionPulse({
    actor,
    preferredAgentId,
    maxItems,
    autoLoad: pulse ? false : true,
    enableEvents: pulse ? false : true,
  });
  const {
    items,
    loading,
    error,
  } = pulse ?? hookPulse;

  const metrics = useMemo(
    () => ({
      running: items.filter(
        (item) =>
          item.currentTaskId ||
          item.queueDepth > 0 ||
          item.currentAssignmentId ||
          item.runtimeStatus === "waiting",
      ).length,
      suspicious: items.filter((item) =>
        item.signals.some((signal) => signal.level !== "good"),
      ).length,
      blocked: items.filter(
        (item) =>
          item.executionState === "waiting-confirm" ||
          item.executionState === "waiting-verification" ||
          item.runtimeStatus === "blocked",
      ).length,
    }),
    [items],
  );

  return (
    <section className={`${styles.strip}${sticky ? ` ${styles.sticky}` : ""}`}>
      <Card className={styles.card}>
        <div className={styles.header}>
          <div>
            <div className={styles.titleRow}>
              <h2 className={styles.title}>{title}</h2>
              <Tag color={items.length > 0 ? "processing" : "default"}>
                {items.length > 0 ? "实时同步中" : "当前没有活跃执行体"}
              </Tag>
            </div>
            <p className={styles.summary}>{summary}</p>
          </div>
          <Space wrap size={8}>
            <Tag>{`执行中 ${metrics.running}`}</Tag>
            <Tag color={metrics.suspicious > 0 ? "warning" : "default"}>
              {`需关注 ${metrics.suspicious}`}
            </Tag>
            <Tag color={metrics.blocked > 0 ? "error" : "default"}>
              {`待确认 ${metrics.blocked}`}
            </Tag>
            <Button
              onClick={() => {
                navigate("/runtime-center");
              }}
            >
              打开运行中心
            </Button>
          </Space>
        </div>

        {error ? (
          <Alert
            showIcon
            type="warning"
            message="执行总览有部分数据未能加载"
            description={error}
            style={{ marginBottom: 16 }}
          />
        ) : null}

        {loading && items.length === 0 ? (
          <div className={styles.loadingWrap}>
            <Spin />
          </div>
        ) : items.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="当前没有处于执行中、阻塞中或排队中的执行体。"
          />
        ) : (
          <div className={styles.grid}>
            {items.map((item) => {
              const currentSignal = item.signals[0];
              const displayName = presentExecutionActorName(item.agentId, item.title);
              const classLabel = presentExecutionClassLabel(item.actorClass, item.agentId);
              const workTitle = localizeWorkbenchText(
                item.currentWorkTitle ||
                  presentRuntimeTaskLabel(item.currentTaskId) ||
                  "当前没有排队或执行中的任务",
              );
              const workSummary = localizeWorkbenchText(
                item.currentWorkSummary ||
                  item.latestCheckpointSummary ||
                  item.latestResultSummary ||
                  item.latestErrorSummary ||
                  "",
              );
              const executionStateLabel = formatExecutionStateLabel(item.executionState);
              const assignmentStatusLabel = formatAssignmentStatusLabel(
                item.currentAssignmentStatus,
              );
              const triggerText = localizeWorkbenchText(
                item.triggerReason || item.triggerSource || "",
              );
              const nextStepText = localizeWorkbenchText(
                item.nextStep || item.blockedReason || item.stuckReason || "",
              );
              const currentFocusText = item.currentFocus
                ? `焦点：${localizeWorkbenchText(item.currentFocus)}`
                : null;
              const currentOwnerText = item.currentOwnerName
                ? `负责人：${localizeWorkbenchText(item.currentOwnerName)}`
                : null;
              const currentEnvironmentText = item.currentEnvironmentId
                ? `环境：${item.currentEnvironmentId}`
                : null;
              const triggerLabel = triggerText ? `触发：${triggerText}` : null;
              const nextStepLabel = nextStepText ? `下一步：${nextStepText}` : null;
              const primaryRiskText = item.primaryRisk
                ? `风险：${localizeWorkbenchText(item.primaryRisk)}`
                : null;
              const evidenceText = item.latestEvidenceSummary
                ? `证据：${localizeWorkbenchText(item.latestEvidenceSummary)}`
                : null;
              const assessmentText = localizeWorkbenchText(
                currentSignal?.detail ||
                  item.blockedReason ||
                  item.stuckReason ||
                  item.nextStep ||
                  item.currentWorkSummary ||
                  "暂无补充说明。",
              );
              return (
                <div key={item.agentId} className={styles.itemCard}>
                  <div className={styles.itemHeader}>
                    <div>
                      <div className={styles.itemTitleRow}>
                        <h3 className={styles.itemTitle}>{displayName}</h3>
                        {item.roleName ? (
                          <Tag color="blue">{localizeWorkbenchText(item.roleName)}</Tag>
                        ) : null}
                        {classLabel ? <Tag>{classLabel}</Tag> : null}
                      </div>
                      <p className={styles.itemWork} title={workTitle}>
                        {workTitle}
                      </p>
                      {workSummary ? (
                        <p className={styles.itemSummary} title={workSummary}>
                          {workSummary}
                        </p>
                      ) : null}
                    </div>
                    <Space wrap size={6}>
                      <Tag color={runtimeStatusColor(item.runtimeStatus)}>
                        {`当前状态：${presentRuntimeStatusLabel(item.runtimeStatus)}`}
                      </Tag>
                      {executionStateLabel ? (
                        <Tag color={executionStateColor(item.executionState)}>
                          {`执行态：${executionStateLabel}`}
                        </Tag>
                      ) : null}
                      {assignmentStatusLabel && !item.currentTaskId ? (
                        <Tag color={runtimeStatusColor(item.currentAssignmentStatus || "queued")}>
                          {`派单：${assignmentStatusLabel}`}
                        </Tag>
                      ) : null}
                      {currentFocusText ? (
                        <Tag color="cyan" title={currentFocusText}>
                          <span className={styles.tagText} title={currentFocusText}>
                            {currentFocusText}
                          </span>
                        </Tag>
                      ) : null}
                      {item.desiredState !== item.runtimeStatus ? (
                        <Tag>{`调度目标：${presentDesiredStateLabel(item.desiredState)}`}</Tag>
                      ) : null}
                      {item.queueDepth > 0 ? <Tag>{`队列 ${item.queueDepth}`}</Tag> : null}
                    </Space>
                  </div>

                  <div className={styles.metaRow}>
                    <Text
                      type="secondary"
                      className={styles.metaText}
                      title={`最近心跳：${formatRuntimeRelativeAge(item.lastHeartbeatAt)}`}
                    >
                      {`最近心跳：${formatRuntimeRelativeAge(item.lastHeartbeatAt)}`}
                    </Text>
                    {currentOwnerText ? (
                      <Text
                        type="secondary"
                        className={styles.metaText}
                        title={currentOwnerText}
                      >
                        {currentOwnerText}
                      </Text>
                    ) : null}
                    {currentEnvironmentText ? (
                      <Text
                        type="secondary"
                        className={styles.metaText}
                        title={currentEnvironmentText}
                      >
                        {currentEnvironmentText}
                      </Text>
                    ) : null}
                  </div>

                  {triggerLabel || nextStepLabel ? (
                    <div className={styles.metaRow}>
                      {triggerLabel ? (
                        <Text
                          type="secondary"
                          className={styles.metaText}
                          title={triggerLabel}
                        >
                          {triggerLabel}
                        </Text>
                      ) : null}
                      {nextStepLabel ? (
                        <Text
                          type="secondary"
                          className={styles.metaText}
                          title={nextStepLabel}
                        >
                          {nextStepLabel}
                        </Text>
                      ) : null}
                    </div>
                  ) : null}

                  {primaryRiskText || evidenceText ? (
                    <div className={styles.metaRow}>
                      {primaryRiskText ? (
                        <Text
                          type="secondary"
                          className={styles.metaText}
                          title={primaryRiskText}
                        >
                          {primaryRiskText}
                        </Text>
                      ) : null}
                      {evidenceText ? (
                        <Text
                          type="secondary"
                          className={styles.metaText}
                          title={evidenceText}
                        >
                          {evidenceText}
                        </Text>
                      ) : null}
                    </div>
                  ) : null}

                  <div className={styles.signalRow}>
                    {item.signals.map((signal) => (
                      <Tag
                        key={`${item.agentId}:${signal.label}`}
                        color={signalColor(signal.level)}
                      >
                        {signal.label}
                      </Tag>
                    ))}
                  </div>

                  <div className={styles.assessment}>
                    <div className={styles.assessmentTitle}>
                      {currentSignal?.label || "当前状态"}
                    </div>
                    <p className={styles.assessmentText} title={assessmentText}>
                      {assessmentText}
                    </p>
                  </div>

                  <div className={styles.actions}>
                    <Text type="secondary">只读兼容视图，控制动作已迁到正式执行体主链。</Text>
                    <Button
                      size="small"
                      type="link"
                      onClick={() => {
                        navigate("/runtime-center");
                      }}
                    >
                      查看完整执行面
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </section>
  );
}
