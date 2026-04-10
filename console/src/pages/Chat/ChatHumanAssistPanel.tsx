import { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, Button, Empty, Modal, Skeleton, Space, Tag } from "antd";

import api from "../../api";
import { isApiError } from "../../api/errors";
import type {
  RuntimeHumanAssistTaskDetail,
  RuntimeHumanAssistTaskSummary,
} from "../../api/modules/runtimeCenter";
import {
  buildHumanAssistDetailPresentation,
  firstNonEmptyString,
  normalizeTaskSummary,
} from "./chatHumanAssistPresentation";
import { queueHumanAssistSubmissionForNextMessage } from "./runtimeTransport";
import styles from "./index.module.less";

type ChatHumanAssistPanelProps = {
  activeChatThreadId: string | null;
  threadMeta: Record<string, unknown>;
};

export function resolveHumanAssistStatusPresentation(
  status: string | null | undefined,
): { label: string; color: string } {
  const normalized = String(status || "").trim().toLowerCase();
  if (normalized === "issued") return { label: "待你完成", color: "blue" };
  if (normalized === "submitted") return { label: "已提交", color: "gold" };
  if (normalized === "verifying") return { label: "验证中", color: "processing" };
  if (normalized === "accepted") return { label: "已通过", color: "success" };
  if (normalized === "need_more_evidence") {
    return { label: "待补证", color: "warning" };
  }
  if (normalized === "resume_queued") return { label: "\u6062\u590d\u4e2d", color: "processing" };
  if (normalized === "handoff_blocked") {
    return { label: "恢复受阻", color: "warning" };
  }
  if (normalized === "rejected") return { label: "未通过", color: "warning" };
  if (normalized === "closed") return { label: "已关闭", color: "default" };
  if (normalized === "expired") return { label: "已过期", color: "default" };
  if (normalized === "cancelled") return { label: "已取消", color: "default" };
  return { label: status || "未知状态", color: "default" };
}

function formatDateTime(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", { hour12: false });
}

function buildErrorMessage(error: unknown, fallback: string): string {
  if (isApiError(error)) {
    return error.message || fallback;
  }
  return error instanceof Error ? error.message : fallback;
}

export function ChatHumanAssistPanel({
  activeChatThreadId,
  threadMeta,
}: ChatHumanAssistPanelProps) {
  const seededCurrentTask = useMemo(
    () => normalizeTaskSummary(threadMeta.human_assist_task),
    [threadMeta],
  );
  const [currentTask, setCurrentTask] = useState<RuntimeHumanAssistTaskSummary | null>(
    seededCurrentTask,
  );
  const [taskListOpen, setTaskListOpen] = useState(false);
  const [taskListLoading, setTaskListLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [tasks, setTasks] = useState<RuntimeHumanAssistTaskSummary[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(
    seededCurrentTask?.id || null,
  );
  const [selectedTaskDetail, setSelectedTaskDetail] = useState<RuntimeHumanAssistTaskDetail | null>(
    null,
  );
  const [panelError, setPanelError] = useState<string | null>(null);

  useEffect(() => {
    setCurrentTask(seededCurrentTask);
    setSelectedTaskId((prev) => prev || seededCurrentTask?.id || null);
  }, [seededCurrentTask]);

  useEffect(() => {
    setTaskListOpen(false);
    setTasks([]);
    setSelectedTaskId(seededCurrentTask?.id || null);
    setSelectedTaskDetail(null);
    setPanelError(null);
  }, [activeChatThreadId, seededCurrentTask?.id]);

  const refreshCurrentTask = useCallback(async () => {
    if (!activeChatThreadId) {
      setCurrentTask(null);
      return;
    }
    try {
      const task = await api.getCurrentRuntimeHumanAssistTask(activeChatThreadId);
      setCurrentTask(task);
      setPanelError(null);
    } catch (error) {
      if (isApiError(error) && error.status === 404) {
        setCurrentTask(null);
        setPanelError(null);
        return;
      }
      setPanelError(buildErrorMessage(error, "现实动作状态刷新失败"));
    }
  }, [activeChatThreadId]);

  const loadTaskDetail = useCallback(async (taskId: string) => {
    setDetailLoading(true);
    try {
      const detail = await api.getRuntimeHumanAssistTaskDetail(taskId);
      setSelectedTaskDetail(detail);
      setPanelError(null);
    } catch (error) {
      setSelectedTaskDetail(null);
      setPanelError(buildErrorMessage(error, "协作详情加载失败"));
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const loadTaskList = useCallback(
    async (preferredTaskId?: string | null) => {
      if (!activeChatThreadId) {
        setTasks([]);
        setSelectedTaskDetail(null);
        setSelectedTaskId(null);
        return;
      }
      setTaskListLoading(true);
      try {
        const items = await api.listRuntimeHumanAssistTasks({
          chat_thread_id: activeChatThreadId,
          limit: 50,
        });
        setTasks(items);
        setPanelError(null);
        const nextTaskId = preferredTaskId || currentTask?.id || items[0]?.id || null;
        setSelectedTaskId(nextTaskId);
        if (nextTaskId) {
          await loadTaskDetail(nextTaskId);
        } else {
          setSelectedTaskDetail(null);
        }
      } catch (error) {
        setTasks([]);
        setSelectedTaskDetail(null);
        setPanelError(buildErrorMessage(error, "协作记录加载失败"));
      } finally {
        setTaskListLoading(false);
      }
    },
    [activeChatThreadId, currentTask?.id, loadTaskDetail],
  );

  const openTaskList = useCallback(
    async (preferredTaskId?: string | null) => {
      setTaskListOpen(true);
      await loadTaskList(preferredTaskId);
    },
    [loadTaskList],
  );

  useEffect(() => {
    void refreshCurrentTask();
  }, [refreshCurrentTask]);

  useEffect(() => {
    if (!activeChatThreadId) {
      return;
    }
    const refresh = () => {
      void refreshCurrentTask();
      if (taskListOpen) {
        void loadTaskList(selectedTaskId);
      }
    };
    window.addEventListener("focus", refresh);
    window.addEventListener("copaw:human-assist-dirty", refresh);
    return () => {
      window.removeEventListener("focus", refresh);
      window.removeEventListener("copaw:human-assist-dirty", refresh);
    };
  }, [activeChatThreadId, loadTaskList, refreshCurrentTask, selectedTaskId, taskListOpen]);

  const detailPresentation = buildHumanAssistDetailPresentation(selectedTaskDetail);
  const {
    hardAnchors,
    negativeAnchors,
    resultAnchors,
    rewardPreview,
    rewardResult,
  } = detailPresentation;
  const currentTaskStatusPresentation = resolveHumanAssistStatusPresentation(
    currentTask?.status,
  );
  const currentTaskTitle = currentTask?.title || "";
  const currentTaskSummary = currentTask
    ? firstNonEmptyString(
        currentTask.summary,
        currentTask.reason_summary,
        currentTask.required_action,
      ) || "这一步必须由你亲自完成，完成后直接在聊天里告诉我。"
    : "";
  const detailSummary = selectedTaskDetail
    ? firstNonEmptyString(
        selectedTaskDetail.task.summary,
        selectedTaskDetail.task.reason_summary,
      ) || "暂无补充说明"
    : null;
  const detailAction = selectedTaskDetail
    ? firstNonEmptyString(selectedTaskDetail.task.required_action) || "暂无"
    : null;
  const detailStatusPresentation = selectedTaskDetail
    ? resolveHumanAssistStatusPresentation(selectedTaskDetail.task.status)
    : null;
  const showExceptionStrip = Boolean(activeChatThreadId && currentTask);
  const armHumanAssistSubmission = useCallback(() => {
    if (!activeChatThreadId || !currentTask) {
      return;
    }
    queueHumanAssistSubmissionForNextMessage(activeChatThreadId);
  }, [activeChatThreadId, currentTask]);

  if (!activeChatThreadId) {
    return null;
  }

  if (!showExceptionStrip && !taskListOpen) {
    return null;
  }

  return (
    <>
      {showExceptionStrip ? (
        <div className={`${styles.humanAssistStrip} ${styles.humanAssistStripActive}`}>
          <div className={styles.humanAssistStripMain}>
            <div className={styles.humanAssistStripBadge}>伙伴提醒</div>
            <div className={styles.humanAssistStripBody}>
              <div className={styles.humanAssistStripTitleRow}>
                <span
                  className={styles.humanAssistStripTitle}
                  title={currentTaskTitle}
                >
                  {currentTaskTitle}
                </span>
                <Tag bordered={false} color={currentTaskStatusPresentation.color}>
                  {currentTaskStatusPresentation.label}
                </Tag>
              </div>
              <div
                className={styles.humanAssistStripSummary}
                title={currentTaskSummary}
              >
                {currentTaskSummary}
              </div>
            </div>
          </div>
          <div className={styles.humanAssistStripActions}>
            <Button size="small" type="primary" onClick={armHumanAssistSubmission}>
              我已在聊天里完成
            </Button>
            <Button
              size="small"
              type="default"
              onClick={() => void openTaskList(currentTask?.id || null)}
            >
              查看协作记录
            </Button>
          </div>
        </div>
      ) : null}

      <Modal
        open={taskListOpen}
        onCancel={() => setTaskListOpen(false)}
        footer={null}
        width={980}
        centered
        destroyOnHidden={false}
        title="需要你亲自完成的现实动作"
      >
        {panelError ? (
          <Alert
            type="warning"
            showIcon
            message={panelError}
            style={{ marginBottom: 12, borderRadius: 12 }}
          />
        ) : null}

        <div className={styles.humanAssistModalLayout}>
          <div className={styles.humanAssistTaskList}>
            <div className={styles.humanAssistSectionTitle}>协作记录</div>
            {taskListLoading ? (
              <Skeleton active paragraph={{ rows: 8 }} />
            ) : tasks.length === 0 ? (
              <Empty description="当前线程还没有需要你亲自处理的现实动作。" />
            ) : (
              <div className={styles.humanAssistTaskListInner}>
                {tasks.map((item) => {
                  const selected = item.id === selectedTaskId;
                  const statusPresentation = resolveHumanAssistStatusPresentation(
                    item.status,
                  );
                  const itemSummary =
                    firstNonEmptyString(
                      item.required_action,
                      item.summary,
                      item.reason_summary,
                    ) || "暂无说明";
                  return (
                    <button
                      key={item.id}
                      type="button"
                      className={`${styles.humanAssistTaskCard} ${
                        selected ? styles.humanAssistTaskCardActive : ""
                      }`}
                      onClick={() => {
                        setSelectedTaskId(item.id);
                        void loadTaskDetail(item.id);
                      }}
                    >
                      <div className={styles.humanAssistTaskCardTop}>
                        <span
                          className={styles.humanAssistTaskCardTitle}
                          title={item.title}
                        >
                          {item.title}
                        </span>
                        <Tag bordered={false} color={statusPresentation.color}>
                          {statusPresentation.label}
                        </Tag>
                      </div>
                      <div
                        className={styles.humanAssistTaskCardSummary}
                        title={itemSummary}
                      >
                        {itemSummary}
                      </div>
                      <div className={styles.humanAssistTaskCardMeta}>
                        {formatDateTime(
                          item.verified_at || item.submitted_at || item.issued_at,
                        ) || "等待时间记录"}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className={styles.humanAssistDetailPane}>
            <div className={styles.humanAssistSectionTitle}>现实动作详情</div>
            {detailLoading ? (
              <Skeleton active paragraph={{ rows: 10 }} />
            ) : selectedTaskDetail ? (
              <div className={styles.humanAssistDetailBody}>
                <div className={styles.humanAssistDetailHeader}>
                  <div className={styles.humanAssistDetailHeading}>
                    <div
                      className={styles.humanAssistDetailTitle}
                      title={selectedTaskDetail.task.title}
                    >
                      {selectedTaskDetail.task.title}
                    </div>
                    <div
                      className={styles.humanAssistDetailSubtitle}
                      title={detailSummary || undefined}
                    >
                      {detailSummary}
                    </div>
                  </div>
                  <Tag bordered={false} color={detailStatusPresentation?.color || "default"}>
                    {detailStatusPresentation?.label || "未知状态"}
                  </Tag>
                </div>

                <div className={styles.humanAssistDetailBlock}>
                  <div className={styles.humanAssistDetailLabel}>你需要亲自完成的动作</div>
                  <div
                    className={styles.humanAssistDetailValue}
                    title={detailAction || undefined}
                  >
                    {detailAction}
                  </div>
                </div>

                <div className={styles.humanAssistDetailGrid}>
                  <div className={styles.humanAssistDetailBlock}>
                    <div className={styles.humanAssistDetailLabel}>强制锚点</div>
                    <Space size={[6, 6]} wrap>
                      {hardAnchors.length > 0 ? (
                        hardAnchors.map((item) => <Tag key={item}>{item}</Tag>)
                      ) : (
                        <span className={styles.humanAssistMuted}>未定义</span>
                      )}
                    </Space>
                  </div>
                  <div className={styles.humanAssistDetailBlock}>
                    <div className={styles.humanAssistDetailLabel}>结果锚点</div>
                    <Space size={[6, 6]} wrap>
                      {resultAnchors.length > 0 ? (
                        resultAnchors.map((item) => <Tag key={item}>{item}</Tag>)
                      ) : (
                        <span className={styles.humanAssistMuted}>未定义</span>
                      )}
                    </Space>
                  </div>
                </div>

                <div className={styles.humanAssistDetailBlock}>
                  <div className={styles.humanAssistDetailLabel}>负向锚点</div>
                  <Space size={[6, 6]} wrap>
                    {negativeAnchors.length > 0 ? (
                      negativeAnchors.map((item) => (
                        <Tag key={item} color="warning">
                          {item}
                        </Tag>
                      ))
                    ) : (
                      <span className={styles.humanAssistMuted}>未定义</span>
                    )}
                  </Space>
                </div>

                <div className={styles.humanAssistDetailGrid}>
                  <div className={styles.humanAssistDetailBlock}>
                    <div className={styles.humanAssistDetailLabel}>预览奖励</div>
                    <Space size={[6, 6]} wrap>
                      {rewardPreview.length > 0 ? (
                        rewardPreview.map(([key, value]) => (
                          <Tag key={`${key}:${value}`} color="blue">
                            {`${key} +${value}`}
                          </Tag>
                        ))
                      ) : (
                        <span className={styles.humanAssistMuted}>暂无</span>
                      )}
                    </Space>
                  </div>
                  <div className={styles.humanAssistDetailBlock}>
                    <div className={styles.humanAssistDetailLabel}>已发奖励</div>
                    <Space size={[6, 6]} wrap>
                      {rewardResult.length > 0 ? (
                        rewardResult.map(([key, value]) => (
                          <Tag key={`${key}:${value}`} color="success">
                            {`${key} +${value}`}
                          </Tag>
                        ))
                      ) : (
                        <span className={styles.humanAssistMuted}>暂无</span>
                      )}
                    </Space>
                  </div>
                </div>

                <div className={styles.humanAssistDetailGrid}>
                  <div className={styles.humanAssistDetailBlock}>
                    <div className={styles.humanAssistDetailLabel}>发布时间</div>
                    <div className={styles.humanAssistDetailValue}>
                      {formatDateTime(selectedTaskDetail.task.issued_at) || "未记录"}
                    </div>
                  </div>
                  <div className={styles.humanAssistDetailBlock}>
                    <div className={styles.humanAssistDetailLabel}>提交时间</div>
                    <div className={styles.humanAssistDetailValue}>
                      {formatDateTime(selectedTaskDetail.task.submitted_at) || "未提交"}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <Empty description="选择左侧记录以查看详情" />
            )}
          </div>
        </div>
      </Modal>
    </>
  );
}
