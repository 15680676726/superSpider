import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Empty,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import api from "../../api";
import type { RuntimeScheduleSummary } from "../../api";

const { Paragraph, Text, Title } = Typography;

const ACTION_LABELS: Record<"run" | "pause" | "resume", string> = {
  run: "立即执行",
  pause: "暂停",
  resume: "恢复",
};

const STATUS_LABELS: Record<string, string> = {
  success: "成功",
  running: "运行中",
  scheduled: "已排程",
  paused: "已暂停",
  error: "异常",
  deleted: "已删除",
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
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

function statusColor(status: string): string {
  if (["success", "running", "scheduled"].includes(status)) return "green";
  if (["paused"].includes(status)) return "orange";
  if (["error", "deleted"].includes(status)) return "red";
  return "default";
}

function statusLabel(status?: string | null): string {
  if (!status) {
    return "-";
  }
  return STATUS_LABELS[status] || status;
}

export default function CalendarPage() {
  const [items, setItems] = useState<RuntimeScheduleSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mutatingId, setMutatingId] = useState<string | null>(null);

  const loadSchedules = useCallback(async () => {
    setLoading(true);
    try {
      setError(null);
      const payload = await api.listRuntimeSchedules();
      setItems(Array.isArray(payload) ? payload : []);
    } catch (fetchError) {
      setError(
        fetchError instanceof Error ? fetchError.message : String(fetchError),
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSchedules();
  }, [loadSchedules]);

  const handleAction = async (
    scheduleId: string,
    action: "run" | "pause" | "resume",
  ) => {
    setMutatingId(scheduleId);
    try {
      if (action === "run") {
        await api.runRuntimeSchedule(scheduleId);
      } else if (action === "pause") {
        await api.pauseRuntimeSchedule(scheduleId);
      } else {
        await api.resumeRuntimeSchedule(scheduleId);
      }
      message.success(`${ACTION_LABELS[action]}: ${scheduleId}`);
      await loadSchedules();
    } catch (mutationError) {
      message.error(
        mutationError instanceof Error
          ? mutationError.message
          : String(mutationError),
      );
    } finally {
      setMutatingId(null);
    }
  };

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Card>
        <Space
          align="start"
          style={{ width: "100%", justifyContent: "space-between" }}
        >
          <div>
            <Title level={3} style={{ marginTop: 0, marginBottom: 8 }}>
              运营日历
            </Title>
            <Paragraph type="secondary" style={{ marginBottom: 0 }}>
              查看运行计划、下次触发时间与手动调度入口。
            </Paragraph>
          </div>
          <Button icon={<ReloadOutlined />} onClick={() => void loadSchedules()}>
            刷新
          </Button>
        </Space>
      </Card>

      {error ? <Alert type="error" showIcon message={error} /> : null}
      {loading ? (
        <Card>
          <Spin />
        </Card>
      ) : items.length === 0 ? (
        <Card>
          <Empty description="暂无运行计划" />
        </Card>
      ) : (
        <Card title="运行计划">
          <Table
            rowKey="id"
            dataSource={items}
            pagination={false}
            columns={[
              {
                title: "计划",
                key: "title",
                render: (_: unknown, record: RuntimeScheduleSummary) => (
                  <Space direction="vertical" size={0}>
                    <Text strong>{record.title || record.name || record.id}</Text>
                    <Text type="secondary">{record.id}</Text>
                  </Space>
                ),
              },
              {
                title: "状态",
                dataIndex: "status",
                key: "status",
                render: (value: string) => (
                  <Tag color={statusColor(value)}>{statusLabel(value)}</Tag>
                ),
              },
              {
                title: "执行规则",
                dataIndex: "cron",
                key: "cron",
                render: (value: string | null | undefined) => value || "-",
              },
              {
                title: "下次运行",
                dataIndex: "next_run_at",
                key: "next_run_at",
                render: (value: string | null | undefined) => formatTime(value),
              },
              {
                title: "上次运行",
                dataIndex: "last_run_at",
                key: "last_run_at",
                render: (value: string | null | undefined) => formatTime(value),
              },
              {
                title: "操作",
                key: "actions",
                render: (_: unknown, record: RuntimeScheduleSummary) => (
                  <Space wrap>
                    <Button
                      size="small"
                      loading={mutatingId === record.id}
                      onClick={() => void handleAction(record.id, "run")}
                    >
                      立即执行
                    </Button>
                    {record.status === "paused" || record.enabled === false ? (
                      <Button
                        size="small"
                        loading={mutatingId === record.id}
                        onClick={() => void handleAction(record.id, "resume")}
                      >
                        恢复
                      </Button>
                    ) : (
                      <Button
                        size="small"
                        loading={mutatingId === record.id}
                        onClick={() => void handleAction(record.id, "pause")}
                      >
                        暂停
                      </Button>
                    )}
                  </Space>
                ),
              },
            ]}
          />
        </Card>
      )}
    </Space>
  );
}
