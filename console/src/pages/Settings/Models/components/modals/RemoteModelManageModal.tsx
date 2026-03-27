import { useState, useEffect } from "react";
import {
  Button,
  Form,
  Input,
  Modal,
  Tag,
  message,
} from "@/ui";
import {
  DeleteOutlined,
  PlusOutlined,
  ApiOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import type { ProviderInfo } from "../../../../../api/types";
import api from "../../../../../api";
import styles from "../../index.module.less";

interface RemoteModelManageModalProps {
  provider: ProviderInfo;
  open: boolean;
  onClose: () => void;
  onSaved: () => void | Promise<void>;
}

export function RemoteModelManageModal({
  provider,
  open,
  onClose,
  onSaved,
}: RemoteModelManageModalProps) {
  const [adding, setAdding] = useState(false);
  const [saving, setSaving] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [testingModelId, setTestingModelId] = useState<string | null>(null);
  const [form] = Form.useForm();
  const canDiscover = false;

  // For custom providers ALL models are deletable.
  // For built-in providers only extra_models are deletable.
  const extraModelIds = new Set((provider.extra_models || []).map((m) => m.id));

  const doAddModel = async (id: string, name: string) => {
    await api.addModel(provider.id, { id, name });
    message.success(`已添加模型：${name}`);
    form.resetFields();
    setAdding(false);
    onSaved();
  };

  const handleAddModel = async () => {
    try {
      const values = await form.validateFields();
      const id = values.id.trim();
      const name = values.name?.trim() || id;

      // Step 1: Test the model connection first
      setSaving(true);
      const testResult = await api.testModelConnection(provider.id, {
        model_id: id,
      });

      if (!testResult.success) {
        // Test failed, ask user whether to proceed anyway
        setSaving(false);
        Modal.confirm({
          title: "连接测试失败",
          content: `模型连接测试失败：${
            testResult.message || "模型测试失败"
          }。是否仍要添加此模型？`,
          okText: "添加模型",
          cancelText: "取消",
          onOk: async () => {
            setSaving(true);
            try {
              await doAddModel(id, name);
            } catch (error) {
              const errMsg =
                error instanceof Error
                  ? error.message
                  : "添加模型失败";
              message.error(errMsg);
            } finally {
              setSaving(false);
            }
          },
        });
        return;
      }

      // Step 2: If test passed, add the model
      await doAddModel(id, name);
    } catch (error) {
      if (error && typeof error === "object" && "errorFields" in error) return;
      const errMsg =
        error instanceof Error ? error.message : "添加模型失败";
      message.error(errMsg);
    } finally {
      setSaving(false);
    }
  };

  const handleTestModel = async (modelId: string) => {
    setTestingModelId(modelId);
    try {
      const result = await api.testModelConnection(provider.id, {
        model_id: modelId,
      });
      if (result.success) {
        message.success(result.message || "连接测试成功");
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
          await onSaved();
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

  const handleClose = () => {
    setAdding(false);
    form.resetFields();
    onClose();
  };

  const handleDiscoverModels = async () => {
    setDiscovering(true);
    try {
      const result = await api.discoverModels(provider.id);
      if (!result.success) {
        message.warning(result.message || "自动获取模型失败");
        return;
      }

      if (result.added_count > 0) {
        message.success(
          `已自动获取 ${result.models.length} 个模型，并新增 ${result.added_count} 个到可选列表`,
        );
        await onSaved();
      } else if (result.models.length > 0) {
        message.info(
          `已自动获取 ${result.models.length} 个模型，当前列表已是最新`,
        );
        await onSaved();
      } else {
        message.info(result.message || "暂无模型");
      }
    } catch (error) {
      const errMsg =
        error instanceof Error
          ? error.message
          : "自动获取模型失败";
      message.error(errMsg);
    } finally {
      setDiscovering(false);
    }
  };

  useEffect(() => {
    // Do not auto-discover models when modal opens, as it may take some time and we don't want to block the UI.
    // Instead, users can click the "Discover Models" button to trigger discovery when needed.
  }, [open, canDiscover, provider.id, provider.models.length]);

  const all_models = [
    ...(provider.models ?? []),
    ...(provider.extra_models ?? []),
  ];

  return (
    <Modal
      title={`${provider.name} — 模型管理`}
      open={open}
      onCancel={handleClose}
      footer={
        <div className={styles.modalFooter}>
          <div className={styles.modalFooterRight}>
            <Button onClick={handleClose}>{"取消"}</Button>
          </div>
        </div>
      }
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
                        icon={<ApiOutlined />}
                        onClick={() => handleTestModel(m.id)}
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
                        onClick={() => handleRemoveModel(m.id, m.name)}
                      />
                    </>
                  ) : (
                    <>
                      <Tag
                        color="green"
                        style={{ fontSize: 11, marginRight: 4 }}
                      >
                        {"内置"}
                      </Tag>
                      <Button
                        type="text"
                        size="small"
                        icon={<ApiOutlined />}
                        onClick={() => handleTestModel(m.id)}
                        loading={testingModelId === m.id}
                      >
                        {"测试连接"}
                      </Button>
                    </>
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
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          <Button
            icon={<SyncOutlined />}
            onClick={handleDiscoverModels}
            loading={discovering}
            disabled={!canDiscover}
            style={{ flex: 1 }}
          >
            {"自动获取模型"}
          </Button>
          <Button
            type="dashed"
            icon={<PlusOutlined />}
            onClick={() => setAdding(true)}
            style={{ flex: 1 }}
          >
            {"添加模型"}
          </Button>
        </div>
      )}
    </Modal>
  );
}
