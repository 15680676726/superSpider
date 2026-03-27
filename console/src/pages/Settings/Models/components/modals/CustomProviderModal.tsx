import { useState, useEffect } from "react";
import { Form, Input, Modal, Select, message } from "@/ui";
import api from "../../../../../api";

interface CustomProviderModalProps {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}

export function CustomProviderModal({
  open,
  onClose,
  onSaved,
}: CustomProviderModalProps) {  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    if (open) {
      form.resetFields();
    }
  }, [open, form]);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      await api.createCustomProvider({
        id: values.id.trim(),
        name: values.name.trim(),
        default_base_url: values.default_base_url?.trim() || "",
        api_key_prefix: values.api_key_prefix?.trim() || "",
        chat_model: values.chat_model || "OpenAIChatModel",
      });
      message.success(
        `提供方“${values.name.trim()}”已创建`,
      );
      onSaved();
      onClose();
    } catch (error) {
      if (error && typeof error === "object" && "errorFields" in error) return;
      const errMsg =
        error instanceof Error
          ? error.message
          : "创建提供方失败";
      message.error(errMsg);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      title={"添加自定义提供方"}
      open={open}
      onCancel={onClose}
      onOk={handleSubmit}
      confirmLoading={saving}
      okText={"创建"}
      cancelText={"取消"}
      destroyOnHidden
    >
      <Form
        form={form}
        layout="vertical"
        style={{ marginTop: 16 }}
        initialValues={{ chat_model: "OpenAIChatModel" }}
      >
        <Form.Item
          name="id"
          label={"提供方编号"}
          extra={"仅支持小写字母、数字、连字符和下划线，创建后不可更改。"}
          rules={[
            { required: true, message: "请输入提供方编号" },
            {
              pattern: /^[a-z][a-z0-9_-]{0,63}$/,
              message: "仅支持小写字母、数字、连字符和下划线，创建后不可更改。",
            },
          ]}
        >
          <Input placeholder={"例如 openai, google, anthropic"} />
        </Form.Item>

        <Form.Item
          name="name"
          label={"显示名称"}
          rules={[{ required: true, message: "显示名称" }]}
        >
          <Input placeholder={"例如 OpenAI, Google Gemini"} />
        </Form.Item>

        <Form.Item
          name="default_base_url"
          label={"默认服务地址"}
        >
          <Input placeholder={"例如 https://api.example.com"} />
        </Form.Item>

        <Form.Item
          name="chat_model"
          label={"接口协议"}
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
      </Form>
    </Modal>
  );
}
