import { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, Button, Empty, Modal, Skeleton, Space, Tag } from "antd";

import api from "../../api";
import { isApiError } from "../../api/errors";
import type {
  RuntimeHumanAssistTaskDetail,
  RuntimeHumanAssistTaskSummary,
} from "../../api/modules/runtimeCenter";
import { queueHumanAssistSubmissionForNextMessage } from "./runtimeTransport";
import styles from "./index.module.less";

type ChatHumanAssistPanelProps = {
  activeChatThreadId: string | null;
  threadMeta: Record<string, unknown>;
};

function firstNonEmptyString(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value !== "string") {
      continue;
    }
    const normalized = value.trim();
    if (normalized) {
      return normalized;
    }
  }
  return null;
}

function normalizeTaskSummary(value: unknown): RuntimeHumanAssistTaskSummary | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const candidate = value as Partial<RuntimeHumanAssistTaskSummary>;
  const id = firstNonEmptyString(candidate.id);
  const title = firstNonEmptyString(candidate.title);
  const chatThreadId = firstNonEmptyString(candidate.chat_thread_id);
  const route = firstNonEmptyString(candidate.route);
  const status = firstNonEmptyString(candidate.status);
  if (!id || !title || !chatThreadId || !route || !status) {
    return null;
  }
  return {
    ...candidate,
    id,
    title,
    chat_thread_id: chatThreadId,
    route,
    status,
  } as RuntimeHumanAssistTaskSummary;
}

export function resolveHumanAssistStatusPresentation(
  status: string | null | undefined,
): { label: string; color: string } {
  const normalized = String(status || "").trim().toLowerCase();
  if (normalized === "issued") return { label: "待提交", color: "blue" };
  if (normalized === "submitted") return { label: "已提交", color: "gold" };
  if (normalized === "verifying") return { label: "验证中", color: "processing" };
  if (normalized === "accepted") return { label: "已通过", color: "success" };
  if (normalized === "need_more_evidence") return { label: "待补证", color: "warning" };
  if (normalized === "resume_queued") return { label: "已验收", color: "success" };
  if (normalized === "handoff_blocked") {
    return { label: "\u6062\u590d\u53d7\u963b", color: "warning" };
  }
  if (normalized === "rejected") return { label: "未通过", color: "warning" };
  if (normalized === "closed") return { label: "已关闭", color: "default" };
  if (normalized === "expired") return { label: "已过期", color: "default" };
  if (normalized === "cancelled") return { label: "已取消", color: "default" };
  return { label: status || "未知", color: "default" };
}

function formatDateTime(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", {
    hour12: false,
  });
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => (typeof item === "string" ? item.trim() : ""))
    .filter(Boolean);
}

function entryList(value: unknown): Array<[string, string]> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return [];
  }
  return Object.entries(value as Record<string, unknown>)
    .filter(([key, entryValue]) => key !== "granted" && entryValue != null && entryValue !== "")
    .map(([key, entryValue]) => [key, String(entryValue)]);
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
      setPanelError(buildErrorMessage(error, "任务状态刷新失败"));
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
      setPanelError(buildErrorMessage(error, "任务详情加载失败"));
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
        setPanelError(buildErrorMessage(error, "任务记录加载失败"));
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

  const acceptanceSpec =
    selectedTaskDetail?.task.acceptance_spec &&
    typeof selectedTaskDetail.task.acceptance_spec === "object"
      ? selectedTaskDetail.task.acceptance_spec
      : {};
  const hardAnchors = stringList((acceptanceSpec as Record<string, unknown>).hard_anchors);
  const resultAnchors = stringList((acceptanceSpec as Record<string, unknown>).result_anchors);
  const negativeAnchors = stringList((acceptanceSpec as Record<string, unknown>).negative_anchors);
  const rewardPreview = entryList(selectedTaskDetail?.task.reward_preview);
  const rewardResult = entryList(selectedTaskDetail?.task.reward_result);
  const hasTaskStrip = Boolean(activeChatThreadId);
  const currentTaskTitle = currentTask ? currentTask.title : "当前无待协作任务";
  const currentTaskStatusPresentation = resolveHumanAssistStatusPresentation(
    currentTask?.status,
  );
  const currentTaskSummary = currentTask
    ? firstNonEmptyString(
        currentTask.required_action,
        currentTask.summary,
        currentTask.reason_summary,
      ) || "请在聊天窗口提交完成证明，系统会自动验收。"
    : "点击任务记录查看本线程的协作任务历史、验收结果和奖励记录。";
  const detailSummary = selectedTaskDetail
    ? firstNonEmptyString(
        selectedTaskDetail.task.summary,
        selectedTaskDetail.task.reason_summary,
      ) || "无补充说明"
    : null;
  const detailAction = selectedTaskDetail
    ? firstNonEmptyString(selectedTaskDetail.task.required_action) || "无"
    : null;
  const detailStatusPresentation = selectedTaskDetail
    ? resolveHumanAssistStatusPresentation(selectedTaskDetail.task.status)
    : null;
  const armHumanAssistSubmission = useCallback(() => {
    if (!activeChatThreadId || !currentTask) {
      return;
    }
    queueHumanAssistSubmissionForNextMessage(activeChatThreadId);
  }, [activeChatThreadId, currentTask]);

  if (!hasTaskStrip) {
    return null;
  }

  return (
    <>
      <div
        className={`${styles.humanAssistStrip} ${
          currentTask ? styles.humanAssistStripActive : styles.humanAssistStripIdle
        }`}
      >
        <div className={styles.humanAssistStripMain}>
          <div className={styles.humanAssistStripBadge}>任务</div>
          <div className={styles.humanAssistStripBody}>
            <div className={styles.humanAssistStripTitleRow}>
              <span className={styles.humanAssistStripTitle} title={currentTaskTitle}>
                {currentTaskTitle}
              </span>
              <Tag bordered={false} color={currentTaskStatusPresentation.color}>
                {currentTask ? currentTaskStatusPresentation.label : "空闲"}
              </Tag>
            </div>
            <div className={styles.humanAssistStripSummary} title={currentTaskSummary}>
              {currentTaskSummary}
            </div>
          </div>
        </div>
        <div className={styles.humanAssistStripActions}>
          {currentTask ? (
            <>
              <Button size="small" type="primary" onClick={armHumanAssistSubmission}>
                提交任务
              </Button>
              <Button size="small" onClick={() => void openTaskList(currentTask.id)}>
                查看详情
              </Button>
            </>
          ) : null}
          <Button
            size="small"
            type={currentTask ? "primary" : "default"}
            onClick={() => void openTaskList(currentTask?.id || null)}
          >
            任务记录
          </Button>
        </div>
      </div>

      <Modal
        open={taskListOpen}
        onCancel={() => setTaskListOpen(false)}
        footer={null}
        width={980}
        centered
        destroyOnHidden={false}
        title="共生协作任务"
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
            <div className={styles.humanAssistSectionTitle}>任务列表</div>
            {taskListLoading ? (
              <Skeleton active paragraph={{ rows: 8 }} />
            ) : tasks.length === 0 ? (
              <Empty description="当前线程还没有协作任务记录" />
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
                    ) || "无说明";
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
            <div className={styles.humanAssistSectionTitle}>任务详情</div>
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
                    {detailStatusPresentation?.label || "未知"}
                  </Tag>
                </div>

                <div className={styles.humanAssistDetailBlock}>
                  <div className={styles.humanAssistDetailLabel}>宿主动作</div>
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
                      {hardAnchors.length > 0 ? hardAnchors.map((item) => (
                        <Tag key={item}>{item}</Tag>
                      )) : <span className={styles.humanAssistMuted}>未定义</span>}
                    </Space>
                  </div>
                  <div className={styles.humanAssistDetailBlock}>
                    <div className={styles.humanAssistDetailLabel}>结果锚点</div>
                    <Space size={[6, 6]} wrap>
                      {resultAnchors.length > 0 ? resultAnchors.map((item) => (
                        <Tag key={item}>{item}</Tag>
                      )) : <span className={styles.humanAssistMuted}>未定义</span>}
                    </Space>
                  </div>
                </div>

                <div className={styles.humanAssistDetailBlock}>
                  <div className={styles.humanAssistDetailLabel}>负向锚点</div>
                  <Space size={[6, 6]} wrap>
                    {negativeAnchors.length > 0 ? negativeAnchors.map((item) => (
                      <Tag key={item} color="warning">
                        {item}
                      </Tag>
                    )) : <span className={styles.humanAssistMuted}>未定义</span>}
                  </Space>
                </div>

                <div className={styles.humanAssistDetailGrid}>
                  <div className={styles.humanAssistDetailBlock}>
                    <div className={styles.humanAssistDetailLabel}>预览奖励</div>
                    <Space size={[6, 6]} wrap>
                      {rewardPreview.length > 0 ? rewardPreview.map(([key, value]) => (
                        <Tag key={`${key}:${value}`} color="blue">
                          {`${key} +${value}`}
                        </Tag>
                      )) : <span className={styles.humanAssistMuted}>暂无</span>}
                    </Space>
                  </div>
                  <div className={styles.humanAssistDetailBlock}>
                    <div className={styles.humanAssistDetailLabel}>已发奖励</div>
                    <Space size={[6, 6]} wrap>
                      {rewardResult.length > 0 ? rewardResult.map(([key, value]) => (
                        <Tag key={`${key}:${value}`} color="success">
                          {`${key} +${value}`}
                        </Tag>
                      )) : <span className={styles.humanAssistMuted}>暂无</span>}
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
              <Empty description="选择左侧任务以查看详情" />
            )}
          </div>
        </div>
      </Modal>
    </>
  );
}
