import { useState, useEffect, useCallback, useRef } from "react";
import {
  Button,
  Form,
  Input,
  Modal,
  Select,
  Tag,
  message,
} from "@/ui";
import {
  CloseOutlined,
  DeleteOutlined,
  DownloadOutlined,
  LoadingOutlined,
  ApiOutlined,
} from "@ant-design/icons";
import type {
  ProviderInfo,
  LocalModelResponse,
  DownloadTaskResponse,
} from "../../../../../api/types";
import api from "../../../../../api";
import styles from "../../index.module.less";

const POLL_INTERVAL_MS = 3000;

interface LocalModelManageModalProps {
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

export function LocalModelManageModal({
  provider,
  open,
  onClose,
  onSaved,
}: LocalModelManageModalProps) {
  const [adding, setAdding] = useState(false);
  const [testingModelId, setTestingModelId] = useState<string | null>(null);
  const [form] = Form.useForm();
  const [localModels, setLocalModels] = useState<LocalModelResponse[]>([]);
  const [loadingLocal, setLoadingLocal] = useState(false);
  const [activeTasks, setActiveTasks] = useState<DownloadTaskResponse[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const notifiedRef = useRef<Set<string>>(new Set());

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const fetchLocalModels = useCallback(async () => {
    setLoadingLocal(true);
    try {
      const data = await api.listLocalModels(provider.id);
      setLocalModels(Array.isArray(data) ? data : []);
    } catch {
      setLocalModels([]);
    } finally {
      setLoadingLocal(false);
    }
  }, [provider.id]);

  const pollDownloads = useCallback(async () => {
    try {
      const tasks = await api.getDownloadStatus(provider.id);
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
        if (!notifiedRef.current.has(task.task_id)) {
          notifiedRef.current.add(task.task_id);
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
        fetchLocalModels();
      }

      setActiveTasks(active);

      if (active.length === 0) {
        stopPolling();
      }
    } catch {
      /* ignore polling errors */
    }
  }, [provider.id,  onSaved, fetchLocalModels, stopPolling]);

  const startPolling = useCallback(() => {
    if (pollRef.current) return;
    pollRef.current = setInterval(pollDownloads, POLL_INTERVAL_MS);
  }, [pollDownloads]);

  useEffect(() => {
    if (!open) return;

    fetchLocalModels();
    setAdding(false);
    form.resetFields();
    notifiedRef.current.clear();

    api
      .getDownloadStatus(provider.id)
      .then((tasks) => {
        const taskList = Array.isArray(tasks) ? tasks : [];
        const active = taskList.filter(
          (t) => t.status === "pending" || t.status === "downloading",
        );
        setActiveTasks(active);
        if (active.length > 0) {
          startPolling();
        }
      })
      .catch(() => {});

    return () => stopPolling();
  }, [open, provider.id, fetchLocalModels, form, startPolling, stopPolling]);

  const handleDownload = async () => {
    try {
      const values = await form.validateFields();
      const task = await api.downloadModel({
        repo_id: values.repo_id.trim(),
        filename: values.filename?.trim() || undefined,
        backend: provider.id,
        source: values.source || "huggingface",
      });
      setActiveTasks((prev) => [...prev, task]);
      setAdding(false);
      form.resetFields();
      startPolling();
    } catch (error) {
      if (error && typeof error === "object" && "errorFields" in error) return;
      const errMsg =
        error instanceof Error
          ? error.message
          : "下载模型失败";
      message.error(errMsg);
    }
  };

  const handleDeleteLocal = (model: LocalModelResponse) => {
    Modal.confirm({
      title: "删除模型",
      content: `确定删除本地模型 "${model.display_name}"？模型文件将从磁盘中删除。`,
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        try {
          await api.deleteLocalModel(model.id);
          message.success(
            `模型 "${model.display_name}" 已删除`,
          );
          onSaved();
          fetchLocalModels();
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

  const handleCancelDownload = (task: DownloadTaskResponse) => {
    Modal.confirm({
      title: "取消下载",
      content: `确定取消下载 "${task.repo_id}"？`,
      okText: "取消下载",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        try {
          await api.cancelDownload(task.task_id);
          message.success("下载已取消");
          setActiveTasks((prev) =>
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

  const handleTest = async (modelId: string) => {
    setTestingModelId(modelId);
    try {
      const result = await api.testModelConnection(provider.id, {
        model_id: modelId,
      });
      if (result.success) {
        message.success(result.message || "连接测试成功");
        // Refresh model list on successful test
        fetchLocalModels();
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
      {activeTasks.map((task) => (
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
              : `正在下载 ${task.repo_id}... 可能需要几分钟。`}
          </span>
          <Button
            type="text"
            size="small"
            danger
            icon={<CloseOutlined />}
            onClick={() => handleCancelDownload(task)}
            style={{ marginLeft: "auto" }}
          />
        </div>
      ))}

      {/* Downloaded models list */}
      <div className={styles.modelList}>
        {loadingLocal ? (
          <div className={styles.modelListEmpty}>{"加载中..."}</div>
        ) : localModels.length === 0 ? (
          <div className={styles.modelListEmpty}>
            {"暂无已下载的模型"}
          </div>
        ) : (
          localModels.map((m) => (
            <div key={m.id} className={styles.modelListItem}>
              <div className={styles.modelListItemInfo}>
                <span className={styles.modelListItemName}>
                  {m.display_name}
                </span>
                <span className={styles.modelListItemId}>
                  {m.repo_id}/{m.filename} &middot;{" "}
                  {formatFileSize(m.file_size)}
                </span>
              </div>
              <div className={styles.modelListItemActions}>
                <Tag
                  color={m.source === "huggingface" ? "orange" : "blue"}
                  style={{ fontSize: 11, marginRight: 4 }}
                >
                  {m.source === "huggingface" ? "HF" : "MS"}
                </Tag>
                <Button
                  type="text"
                  size="small"
                  icon={<ApiOutlined />}
                  onClick={() => handleTest(m.id)}
                  loading={testingModelId === m.id}
                  style={{ marginRight: 4 }}
                >
                  {"测试连接"}
                </Button>
                <Button
                  type="text"
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => handleDeleteLocal(m)}
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
              name="repo_id"
              label={"仓库编号"}
              rules={[
                { required: true, message: "请输入仓库编号" },
              ]}
              style={{ marginBottom: 32 }}
            >
              <Input placeholder={"例如 TheBloke/Mistral-7B-GGUF"} />
            </Form.Item>
            <Form.Item
              name="filename"
              label={"文件名（可选）"}
              extra={"留空将自动选择最佳量化版本"}
              style={{ marginBottom: 32 }}
            >
              <Input placeholder={"例如 mistral-7b.Q4_K_M.gguf"} />
            </Form.Item>
            <Form.Item
              name="source"
              label={"来源"}
              initialValue="huggingface"
              style={{ marginBottom: 32 }}
            >
              <Select
                options={[
                  { value: "huggingface", label: "Hugging Face" },
                  { value: "modelscope", label: "ModelScope" },
                ]}
              />
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
                onClick={handleDownload}
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

