import { useState, useEffect, useMemo } from "react";
import {
  Form,
  Input,
  Modal,
  message,
  Button,
  Select,
} from "@/ui";
import { ApiOutlined } from "@ant-design/icons";
import type { ProviderConfigRequest } from "../../../../../api/types";
import api from "../../../../../api";
import styles from "../../index.module.less";

interface ProviderConfigModalProps {
  provider: {
    id: string;
    name: string;
    api_key?: string;
    api_key_prefix?: string;
    base_url?: string;
    is_custom: boolean;
    freeze_url: boolean;
    chat_model: string;
  };
  activeModels: any;
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}

export function ProviderConfigModal({
  provider,
  activeModels,
  open,
  onClose,
  onSaved,
}: ProviderConfigModalProps) {
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [formDirty, setFormDirty] = useState(false);
  const [form] = Form.useForm<ProviderConfigRequest>();
  const selectedChatModel = Form.useWatch("chat_model", form);
  const canEditBaseUrl = !provider.freeze_url;

  const effectiveChatModel = useMemo(() => {
    if (!provider.is_custom) {
      return provider.chat_model;
    }
    return selectedChatModel || provider.chat_model || "OpenAIChatModel";
  }, [provider.chat_model, provider.is_custom, selectedChatModel]);

  const apiKeyPlaceholder = useMemo(() => {
    if (provider.api_key) {
      return "留空以保持当前密钥";
    }
    if (provider.api_key_prefix) {
      return `输入接口密钥（${provider.api_key_prefix}...）`;
    }
    return "输入接口密钥（可选）";
  }, [provider.api_key, provider.api_key_prefix ]);

  const baseUrlExtra = useMemo(() => {
    if (!canEditBaseUrl) {
      return undefined;
    }
    if (provider.id === "azure-openai") {
      return "Azure OpenAI 端点，例如 https://<resource>.openai.azure.com/openai/v1";
    }
    if (provider.id === "anthropic") {
      return "Anthropic 端点，例如 https://api.anthropic.com（仅在部署要求时再追加 /v1）";
    }
    if (provider.id === "openai") {
      return "OpenAI 端点，例如 https://api.openai.com/v1";
    }
    if (provider.id === "ollama") {
      return "Ollama OpenAI 兼容端点，例如 http://localhost:11434/v1";
    }
    if (provider.is_custom) {
      return effectiveChatModel === "AnthropicChatModel"
        ? "Anthropic 端点，例如 https://api.anthropic.com（仅在部署要求时再追加 /v1）"
        : "OpenAI 兼容端点，例如 https://api.example.com（仅在你的服务要求时再追加 /v1）";
    }
    return "服务端点，例如 https://api.example.com";
  }, [canEditBaseUrl, provider.id, provider.is_custom, effectiveChatModel ]);

  const baseUrlPlaceholder = useMemo(() => {
    if (!canEditBaseUrl) {
      return "";
    }
    if (provider.id === "azure-openai") {
      return "https://<resource>.openai.azure.com/openai/v1";
    }
    if (provider.id === "anthropic") {
      return "https://api.anthropic.com/v1";
    }
    if (provider.id === "openai") {
      return "https://api.openai.com/v1";
    }
    if (provider.id === "ollama") {
      return "http://localhost:11434/v1";
    }
    if (provider.is_custom && effectiveChatModel === "AnthropicChatModel") {
      return "https://api.anthropic.com/v1";
    }
    return "https://api.example.com";
  }, [canEditBaseUrl, provider.id, provider.is_custom, effectiveChatModel]);

  // Sync form when modal opens or provider data changes
  useEffect(() => {
    if (open) {
      form.setFieldsValue({
        api_key: undefined,
        base_url: provider.base_url || undefined,
        chat_model: provider.chat_model || "OpenAIChatModel",
      });
      setFormDirty(false);
    }
  }, [provider, form, open]);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);

      // Validate connection before saving
      // For local providers, we might skip this or just check if models exist (which the backend does)
      const result = await api.testProviderConnection(provider.id, {
        api_key: values.api_key,
        base_url: values.base_url,
        chat_model: values.chat_model,
      });

      if (!result.success) {
        message.error(result.message || "连接测试失败");
        if (!provider.is_custom) {
          // For built-in providers, we want to enforce valid config before saving
          return;
        }
      }

      await api.configureProvider(provider.id, values);

      await onSaved();
      setFormDirty(false);
      onClose();
      message.success(`${provider.name} 配置已保存`);
    } catch (error) {
      if (error && typeof error === "object" && "errorFields" in error) return;
      const errMsg =
        error instanceof Error ? error.message : "保存配置失败";
      message.error(errMsg);
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      const values = await form.validateFields();
      const result = await api.testProviderConnection(provider.id, {
        api_key: values.api_key,
        base_url: values.base_url,
        chat_model: values.chat_model,
      });
      if (result.success) {
        message.success(result.message || "连接测试成功");
      } else {
        message.warning(result.message || "连接测试失败");
      }
    } catch (error) {
      if (error && typeof error === "object" && "errorFields" in error) return;
      const errMsg =
        error instanceof Error
          ? error.message
          : "测试连接时发生错误";
      message.error(errMsg);
    } finally {
      setTesting(false);
    }
  };

  const isActiveLlmProvider =
    activeModels?.active_llm?.provider_id === provider.id;

  const handleRevoke = () => {
    const confirmContent = isActiveLlmProvider
      ? `确定要移除 ${provider.name} 的接口密钥吗？当前对话模型配置也会一并清除。`
      : `确定要移除 ${provider.name} 的接口密钥吗？`;

    Modal.confirm({
      title: "撤销授权",
      content: confirmContent,
      okText: "撤销授权",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        try {
          await api.configureProvider(provider.id, { api_key: "" });
          await onSaved();
          onClose();
          if (isActiveLlmProvider) {
            message.success(
              `${provider.name} 授权已撤销，对话模型已清除`,
            );
          } else {
            message.success(
              `${provider.name} 授权已撤销`,
            );
          }
        } catch (error) {
          const errMsg =
            error instanceof Error ? error.message : "撤销授权失败";
          message.error(errMsg);
        }
      },
    });
  };

  return (
    <Modal
      title={`配置 ${provider.name}`}
      open={open}
      onCancel={onClose}
      footer={
        <div className={styles.modalFooter}>
          <div className={styles.modalFooterLeft}>
            {provider.api_key && (
              <Button danger size="small" onClick={handleRevoke}>
                {"撤销授权"}
              </Button>
            )}
            <Button
              size="small"
              icon={<ApiOutlined />}
              onClick={handleTest}
              loading={testing}
            >
              {"测试连接"}
            </Button>
          </div>
          <div className={styles.modalFooterRight}>
            <Button onClick={onClose}>{"取消"}</Button>
            <Button
              type="primary"
              loading={saving}
              disabled={!formDirty}
              onClick={handleSubmit}
            >
              {"保存"}
            </Button>
          </div>
        </div>
      }
      destroyOnHidden
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          base_url: provider.base_url || undefined,
          chat_model: provider.chat_model || "OpenAIChatModel",
        }}
        onValuesChange={() => setFormDirty(true)}
      >
        {provider.is_custom && (
          <Form.Item
            name="chat_model"
            label={"协议"}
            rules={[
              {
                required: true,
                message: "请选择协议",
              },
            ]}
            extra={"为当前配置选择提供方接口协议。"}
          >
            <Select
              options={[
                {
                  value: "OpenAIChatModel",
                  label: "OpenAI 兼容接口（聊天补全）",
                },
                {
                  value: "AnthropicChatModel",
                  label: "Anthropic（消息接口）",
                },
              ]}
            />
          </Form.Item>
        )}

        <Form.Item
          name="base_url"
          label={"服务地址"}
          rules={
            canEditBaseUrl
              ? [
                  ...(!provider.freeze_url
                    ? [
                        {
                          required: true,
                          message: "请输入服务地址",
                        },
                      ]
                    : []),
                  { type: "url", message: "请输入有效的地址" },
                ]
              : []
          }
          extra={baseUrlExtra}
        >
          <Input placeholder={baseUrlPlaceholder} disabled={!canEditBaseUrl} />
        </Form.Item>

        <Form.Item
          name="api_key"
          label={"接口密钥"}
          rules={[
            {
              validator: (_, value) => {
                if (
                  value &&
                  provider.api_key_prefix &&
                  !value.startsWith(provider.api_key_prefix)
                ) {
                  return Promise.reject(
                    new Error(
                      `接口密钥应以“${provider.api_key_prefix}”开头`,
                    ),
                  );
                }
                return Promise.resolve();
              },
            },
          ]}
        >
          <Input.Password placeholder={apiKeyPlaceholder} />
        </Form.Item>
      </Form>
    </Modal>
  );
}

