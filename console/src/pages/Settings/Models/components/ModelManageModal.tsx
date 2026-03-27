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
  PlusOutlined,
} from "@ant-design/icons";
import type {
  ProviderInfo,
  LocalModelResponse,
  DownloadTaskResponse,
  OllamaModelResponse,
  OllamaDownloadTaskResponse,
} from "../../../../api/types";
import api from "../../../../api";
import styles from "../index.module.less";

const POLL_INTERVAL_MS = 3000;

interface ModelManageModalProps {
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

export function ModelManageModal({
  provider,
  open,
  onClose,
  onSaved,
}: ModelManageModalProps) {
  const [adding, setAdding] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();

  // --- Local provider state ---
  const [localModels, setLocalModels] = useState<LocalModelResponse[]>([]);
  const [loadingLocal, setLoadingLocal] = useState(false);
  const [activeTasks, setActiveTasks] = useState<DownloadTaskResponse[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Track task IDs we've already shown completion/failure messages for
  const notifiedRef = useRef<Set<string>>(new Set());

  // --- Ollama provider state ---
  const [ollamaModels, setOllamaModels] = useState<OllamaModelResponse[]>([]);
  const [loadingOllama, setLoadingOllama] = useState(false);
  const [ollamaTasks, setOllamaTasks] = useState<OllamaDownloadTaskResponse[]>(
    [],
  );
  const ollamaPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const ollamaNotifiedRef = useRef<Set<string>>(new Set());

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const stopOllamaPolling = useCallback(() => {
    if (ollamaPollRef.current) {
      clearInterval(ollamaPollRef.current);
      ollamaPollRef.current = null;
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

      // Notify for newly completed/failed/cancelled tasks
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

      // Stop polling when no active tasks remain
      if (active.length === 0) {
        stopPolling();
      }
    } catch {
      /* ignore polling errors */
    }
  }, [provider.id, onSaved, fetchLocalModels, stopPolling]);

  const startPolling = useCallback(() => {
    if (pollRef.current) return; // already polling
    pollRef.current = setInterval(pollDownloads, POLL_INTERVAL_MS);
  }, [pollDownloads]);

  // --- Ollama-specific fetch & poll functions ---

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

  // On open for local providers: fetch models and check for active downloads
  useEffect(() => {
    if (!open || !provider.is_local) return;

    fetchLocalModels();
    setAdding(false);
    form.resetFields();
    notifiedRef.current.clear();

    // Initial check
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
  }, [
    open,
    provider.is_local,
    provider.id,
    fetchLocalModels,
    form,
    startPolling,
    stopPolling,
  ]);

  // On open for Ollama provider: fetch models and check for active downloads
  useEffect(() => {
    if (!open || provider.id !== "ollama") return;

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
  }, [
    open,
    provider.id,
    fetchOllamaModels,
    form,
    startOllamaPolling,
    stopOllamaPolling,
  ]);

  // --- Remote provider logic ---

  // For custom providers ALL models are deletable.
  // For built-in providers only extra_models are deletable.
  const extraModelIds = new Set(
    provider.is_custom
      ? provider.models.map((m) => m.id)
      : (provider.extra_models || []).map((m) => m.id),
  );

  const handleAddModel = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const id = values.id.trim();
      const name = values.name?.trim() || id;
      await api.addModel(provider.id, { id, name });
      message.success(`已添加模型：${name}`);
      form.resetFields();
      setAdding(false);
      onSaved();
    } catch (error) {
      if (error && typeof error === "object" && "errorFields" in error) return;
      const errMsg =
        error instanceof Error ? error.message : "添加模型失败";
      message.error(errMsg);
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveModel = (modelId: string, modelName: string) => {
    Modal.confirm({
      title: "移除",
      content: `确定从 ${provider.name} 中移除模型 "${modelName}"？`,
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        try {
          await api.removeModel(provider.id, modelId);
          message.success(`模型 "${modelName}" 已移除`);
          onSaved();
        } catch (error) {
          const errMsg =
            error instanceof Error
              ? error.message
              : "移除模型失败";
          message.error(errMsg);
        }
      },
    });
  };

  // --- Local provider: download & delete ---

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

  // --- Ollama provider: download & delete ---

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
          // Remove from active tasks immediately
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
          // Remove from active tasks immediately
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

  const handleClose = () => {
    setAdding(false);
    form.resetFields();
    onClose();
  };

  // --- Render: Ollama provider ---
  if (provider.id === "ollama") {
    return (
      <Modal
        title={`${provider.name} — 本地模型`}
        open={open}
        onCancel={handleClose}
        footer={null}
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
                    danger
                    icon={<DeleteOutlined />}
                    onClick={() => handleOllamaDelete(m)}
                  />
                </div>
              </div>
            ))
          )}
        </div>

        {/* Download form, always available */}
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

  // --- Render: local provider ---
  if (provider.is_local) {
    return (
      <Modal
        title={`${provider.name} — 本地模型`}
        open={open}
        onCancel={handleClose}
        footer={null}
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
                    danger
                    icon={<DeleteOutlined />}
                    onClick={() => handleDeleteLocal(m)}
                  />
                </div>
              </div>
            ))
          )}
        </div>

        {/* Download form, always available */}
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

  // --- Remote provider ---
  const all_models = [
    ...(provider.models || []),
    ...(provider.extra_models || []),
  ];
  return (
    <Modal
      title={`${provider.name} — 模型管理`}
      open={open}
      onCancel={handleClose}
      footer={null}
      width={560}
      destroyOnHidden
    >
      {/* Model list */}
      <div className={styles.modelList}>
        {all_models.length === 0 ? (
          <div className={styles.modelListEmpty}>{"暂无模型"}</div>
        ) : (
          all_models.map((m) => {
            const isDeletable = extraModelIds.has(m.id);
            return (
              <div key={m.id} className={styles.modelListItem}>
                <div className={styles.modelListItemInfo}>
                  <span className={styles.modelListItemName}>{m.name}</span>
                  <span className={styles.modelListItemId}>{m.id}</span>
                </div>
                <div className={styles.modelListItemActions}>
                  {isDeletable ? (
                    <>
                      <Tag
                        color="blue"
                        style={{ fontSize: 11, marginRight: 4 }}
                      >
                        {"用户添加"}
                      </Tag>
                      <Button
                        type="text"
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={() => handleRemoveModel(m.id, m.name)}
                      />
                    </>
                  ) : (
                    <Tag color="green" style={{ fontSize: 11 }}>
                      {"内置"}
                    </Tag>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Add model section */}
      {adding ? (
        <div className={styles.modelAddForm}>
          <Form form={form} layout="vertical" style={{ marginBottom: 0 }}>
            <Form.Item
              name="id"
              label={"模型编号"}
              rules={[{ required: true, message: "请输入模型编号" }]}
              style={{ marginBottom: 32 }}
            >
              <Input placeholder={"例如 gpt-4o, gemini-2.0-flash"} />
            </Form.Item>
            <Form.Item
              name="name"
              label={"模型名称"}
              style={{ marginBottom: 32 }}
            >
              <Input placeholder={"例如 GPT-4o, Gemini 2.0 Flash"} />
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
                loading={saving}
                onClick={handleAddModel}
              >
                {"添加模型"}
              </Button>
            </div>
          </Form>
        </div>
      ) : (
        <Button
          type="dashed"
          block
          icon={<PlusOutlined />}
          onClick={() => setAdding(true)}
          style={{ marginTop: 12 }}
        >
          {"添加模型"}
        </Button>
      )}
    </Modal>
  );
}
