import { useState } from "react";
import { Drawer, Form, Input, Switch, Button } from "@/ui";
import type { MCPClientInfo } from "../../../../api/types";

interface MCPClientDrawerProps {
  open: boolean;
  client: MCPClientInfo | null;
  onClose: () => void;
  onSubmit: (
    key: string,
    values: {
      name: string;
      command?: string;
      enabled?: boolean;
      transport?: "stdio" | "streamable_http" | "sse";
      url?: string;
      headers?: Record<string, string>;
      args?: string[];
      env?: Record<string, string>;
      cwd?: string;
    },
  ) => Promise<boolean>;
  form: any;
}

export function MCPClientDrawer({
  open,
  client,
  onClose,
  onSubmit,
  form,
}: MCPClientDrawerProps) {
  const [submitting, setSubmitting] = useState(false);
  const isEditing = !!client;

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);

      const clientData = {
        name: values.name,
        command: values.command,
        enabled: values.enabled ?? true,
        args: values.args ? values.args.split(" ").filter(Boolean) : [],
        env: values.env ? JSON.parse(values.env) : {},
      };

      const key = isEditing ? client.key : values.key;
      const success = await onSubmit(key, clientData);

      if (success) {
        onClose();
      }
    } catch (error) {
      console.error("Form validation failed:", error);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Drawer
      title={
        isEditing
          ? "编辑模型上下文协议客户端"
          : "新建模型上下文协议客户端"
      }
      placement="right"
      onClose={onClose}
      open={open}
      width={600}
      footer={
        <div style={{ textAlign: "right" }}>
          <Button onClick={onClose} style={{ marginRight: 8 }}>
            {"取消"}
          </Button>
          <Button type="primary" onClick={handleSubmit} loading={submitting}>
            {isEditing ? "保存" : "创建"}
          </Button>
        </div>
      }
    >
      <Form form={form} layout="vertical">
        {!isEditing && (
          <Form.Item
            name="key"
            label={"客户端键名"}
            rules={[
              {
                required: true,
                message: "请输入客户端键名",
              },
            ]}
          >
            <Input placeholder={"请输入客户端键名"} />
          </Form.Item>
        )}

        <Form.Item
          name="name"
          label={"客户端名称"}
          rules={[
            {
              required: true,
              message: "请输入客户端名称",
            },
          ]}
        >
          <Input placeholder={"请输入客户端名称"} />
        </Form.Item>

        <Form.Item name="description" label={"描述"}>
          <Input.TextArea
            rows={2}
            placeholder={"请输入描述"}
          />
        </Form.Item>

        <Form.Item
          name="command"
          label={"启动命令"}
          rules={[
            {
              required: true,
              message: "请输入启动命令",
            },
          ]}
        >
          <Input placeholder={"请输入启动命令"} />
        </Form.Item>

        <Form.Item
          name="args"
          label={"命令参数"}
          extra={"多个参数请用空格分隔"}
        >
          <Input placeholder={"请输入命令参数"} />
        </Form.Item>

        <Form.Item
          name="env"
          label={"环境变量"}
          extra={"请输入 JSON 格式的环境变量"}
        >
          <Input.TextArea rows={4} placeholder='{"API_KEY":"<YOUR_API_KEY>"}' />
        </Form.Item>

        <Form.Item
          name="enabled"
          label={"启用"}
          valuePropName="checked"
        >
          <Switch />
        </Form.Item>
      </Form>
    </Drawer>
  );
}
