import { useState, useEffect, useCallback, useRef } from "react";
import { Button, Form, Input, Modal, message } from "@/ui";
import {
  CloseOutlined,
  DeleteOutlined,
  DownloadOutlined,
  LoadingOutlined,
  ApiOutlined,
} from "@ant-design/icons";
import type {
  ProviderInfo,
  OllamaModelResponse,
  OllamaDownloadTaskResponse,
} from "../../../../../api/types";
import api from "../../../../../api";
import styles from "../../index.module.less";

const POLL_INTERVAL_MS = 3000;

interface OllamaModelManageModalProps {
  provider: ProviderInfo;
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

export function OllamaModelManageModal({
  provider,
  open,
  onClose,
  onSaved,
}: OllamaModelManageModalProps) {
  const [adding, setAdding] = useState(false);
  const [testingModelId, setTestingModelId] = useState<string | null>(null);
  const [form] = Form.useForm();
  const [ollamaModels, setOllamaModels] = useState<OllamaModelResponse[]>([]);
  const [loadingOllama, setLoadingOllama] = useState(false);
  const [ollamaTasks, setOllamaTasks] = useState<OllamaDownloadTaskResponse[]>(
    [],
  );
  const ollamaPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const ollamaNotifiedRef = useRef<Set<string>>(new Set());

  const stopOllamaPolling = useCallback(() => {
    if (ollamaPollRef.current) {
      clearInterval(ollamaPollRef.current);
      ollamaPollRef.current = null;
    }
  }, []);

  const fetchOllamaModels = useCallback(async () => {
    setLoadingOllama(true);
    try {
      const data = await api.listOllamaModels();
      setOllamaModels(Array.isArray(data) ? data : []);
    } catch {
      setOllamaModels([]);
    } finally {
      setLoadingOllama(false);
    }
  }, []);

  const pollOllamaDownloads = useCallback(async () => {
    try {
      const tasksStatus = await api.getOllamaDownloadStatus();
      const tasks = Array.isArray(tasksStatus) ? tasksStatus : [];
      const active = tasks.filter(
        (t) => t.status === "pending" || t.status === "downloading",
      );
      const terminal = tasks.filter(
        (t) =>
          t.status === "completed" ||
          t.status === "failed" ||
          t.status === "cancelled",
      );

      let needsRefresh = false;
      for (const task of terminal) {
        if (!ollamaNotifiedRef.current.has(task.task_id)) {
          ollamaNotifiedRef.current.add(task.task_id);
          if (task.status === "completed") {
            message.success("模型下载成功");
            needsRefresh = true;
          } else if (task.status === "cancelled") {
            message.info("下载已取消");
          } else {
            message.error(task.error || "模型下载失败");
          }
        }
      }

      if (needsRefresh) {
        onSaved();
        fetchOllamaModels();
      }

      setOllamaTasks(active);

      if (active.length === 0) {
        stopOllamaPolling();
      }
    } catch {
      /* ignore polling errors */
    }
  }, [onSaved, fetchOllamaModels, stopOllamaPolling]);

  const startOllamaPolling = useCallback(() => {
    if (ollamaPollRef.current) return;
    ollamaPollRef.current = setInterval(pollOllamaDownloads, POLL_INTERVAL_MS);
  }, [pollOllamaDownloads]);

  useEffect(() => {
    if (!open) return;

    fetchOllamaModels();
    setAdding(false);
    form.resetFields();
    ollamaNotifiedRef.current.clear();

    api
      .getOllamaDownloadStatus()
      .then((tasks) => {
        const active = tasks.filter(
          (t) => t.status === "pending" || t.status === "downloading",
        );
        setOllamaTasks(active);
        if (active.length > 0) {
          startOllamaPolling();
        }
      })
      .catch(() => {});

    return () => stopOllamaPolling();
  }, [open, fetchOllamaModels, form, startOllamaPolling, stopOllamaPolling]);

  const handleOllamaDownload = async () => {
    try {
      const values = await form.validateFields();
      const task = await api.downloadOllamaModel({ name: values.name.trim() });
      setOllamaTasks((prev) => [...prev, task]);
      setAdding(false);
      form.resetFields();
      startOllamaPolling();
    } catch (error) {
      if (error && typeof error === "object" && "errorFields" in error) return;
      const errMsg =
        error instanceof Error
          ? error.message
          : "下载模型失败";
      message.error(errMsg);
    }
  };

  const handleOllamaDelete = (model: OllamaModelResponse) => {
    Modal.confirm({
      title: "删除模型",
      content: `确定删除本地模型 "${model.name}"？模型文件将从磁盘中删除。`,
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        try {
          await api.deleteOllamaModel(model.name);
          message.success(`模型 "${model.name}" 已删除`);
          onSaved();
          fetchOllamaModels();
        } catch (error) {
          const errMsg =
            error instanceof Error
              ? error.message
              : "删除模型失败";
          message.error(errMsg);
        }
      },
    });
  };

  const handleCancelOllamaDownload = (task: OllamaDownloadTaskResponse) => {
    Modal.confirm({
      title: "取消下载",
      content: `确定取消下载 "${task.name}"？`,
      okText: "取消下载",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        try {
          await api.cancelOllamaDownload(task.task_id);
          message.success("下载已取消");
          setOllamaTasks((prev) =>
            prev.filter((t) => t.task_id !== task.task_id),
          );
        } catch (error) {
          const errMsg =
            error instanceof Error
              ? error.message
              : "取消下载失败";
          message.error(errMsg);
        }
      },
    });
  };

  const handleTest = async (modelName: string) => {
    setTestingModelId(modelName);
    try {
      const result = await api.testModelConnection(provider.id, {
        model_id: modelName,
      });
      if (result.success) {
        message.success(result.message || "连接测试成功");
        // Refresh model list on successful test
        fetchOllamaModels();
      } else {
        message.warning(result.message || "连接测试失败");
      }
    } catch (error) {
      const errMsg =
        error instanceof Error
          ? error.message
          : "测试连接时发生错误";
      message.error(errMsg);
    } finally {
      setTestingModelId(null);
    }
  };

  const handleClose = () => {
    setAdding(false);
    form.resetFields();
    onClose();
  };

  return (
    <Modal
      title={`${provider.name} — 本地模型`}
      open={open}
      onCancel={handleClose}
      footer={
        <div className={styles.modalFooter}>
          <div className={styles.modalFooterRight}>
            <Button onClick={handleClose}>{"取消"}</Button>
          </div>
        </div>
      }
      width={600}
      destroyOnHidden
    >
      {/* Active download statuses */}
      {ollamaTasks.map((task) => (
        <div
          key={task.task_id}
          style={{
            padding: "12px 16px",
            marginBottom: 8,
            background: "#f6f8fa",
            borderRadius: 8,
            border: "var(--baize-border)",
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          <LoadingOutlined spin style={{ fontSize: 16, color: "#615CED" }} />
          <span style={{ color: "var(--baize-text-main)", fontSize: 13, flex: 1 }}>
            {task.status === "pending"
              ? "准备下载..."
              : `正在下载 ${task.name}... 可能需要几分钟。`}
          </span>
          <Button
            type="text"
            size="small"
            danger
            icon={<CloseOutlined />}
            onClick={() => handleCancelOllamaDownload(task)}
            style={{ marginLeft: "auto" }}
          />
        </div>
      ))}

      {/* Downloaded models list */}
      <div className={styles.modelList}>
        {loadingOllama ? (
          <div className={styles.modelListEmpty}>{"加载中..."}</div>
        ) : ollamaModels.length === 0 ? (
          <div className={styles.modelListEmpty}>
            {"暂无已下载的模型"}
          </div>
        ) : (
          ollamaModels.map((m) => (
            <div key={m.name} className={styles.modelListItem}>
              <div className={styles.modelListItemInfo}>
                <span className={styles.modelListItemName}>{m.name}</span>
              </div>
              <div className={styles.modelListItemActions}>
                <span
                  className={styles.modelListItemId}
                  style={{ marginRight: 8 }}
                >
                  {formatFileSize(m.size)}
                </span>
                <Button
                  type="text"
                  size="small"
                  icon={<ApiOutlined />}
                  onClick={() => handleTest(m.name)}
                  loading={testingModelId === m.name}
                  style={{ marginRight: 4 }}
                >
                  {"测试连接"}
                </Button>
                <Button
                  type="text"
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => handleOllamaDelete(m)}
                />
              </div>
            </div>
          ))
        )}
      </div>

      {/* Download form */}
      {adding ? (
        <div className={styles.modelAddForm}>
          <Form form={form} layout="vertical" style={{ marginBottom: 0 }}>
            <Form.Item
              name="name"
              label={"模型名称"}
              rules={[
                { required: true, message: "请输入模型名称" },
              ]}
              style={{ marginBottom: 32 }}
            >
              <Input placeholder={"例如 mistral:7b, qwen3:8b"} />
            </Form.Item>
            <div
              style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}
            >
              <Button
                size="small"
                onClick={() => {
                  setAdding(false);
                  form.resetFields();
                }}
              >
                {"取消"}
              </Button>
              <Button
                type="primary"
                size="small"
                onClick={handleOllamaDownload}
                icon={<DownloadOutlined />}
              >
                {"下载模型"}
              </Button>
            </div>
          </Form>
        </div>
      ) : (
        <Button
          type="dashed"
          block
          icon={<DownloadOutlined />}
          onClick={() => setAdding(true)}
          style={{ marginTop: 12 }}
        >
          {"下载模型"}
        </Button>
      )}
    </Modal>
  );
}

