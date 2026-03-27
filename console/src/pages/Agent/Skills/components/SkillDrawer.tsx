import { useState, useEffect, useCallback } from "react";
import { Drawer, Form, Input, Button, message } from "@/ui";
import type { FormInstance } from "antd";
import type { SkillSpec } from "../../../../api/types";
import { MarkdownCopy } from "../../../../components/MarkdownCopy/MarkdownCopy";

function parseFrontmatter(content: string): Record<string, string> | null {
  const trimmed = content.trim();
  if (!trimmed.startsWith("---")) return null;

  const endIndex = trimmed.indexOf("---", 3);
  if (endIndex === -1) return null;

  const frontmatterBlock = trimmed.slice(3, endIndex).trim();
  if (!frontmatterBlock) return null;

  const result: Record<string, string> = {};
  for (const line of frontmatterBlock.split("\n")) {
    const colonIndex = line.indexOf(":");
    if (colonIndex > 0) {
      const key = line.slice(0, colonIndex).trim();
      const value = line.slice(colonIndex + 1).trim();
      result[key] = value;
    }
  }
  return result;
}

const CONTENT_PLACEHOLDER = [
  "---",
  "name: <技能名称>",
  "description: <技能描述>",
  "---",
  "",
  "请在此输入技能内容...",
].join("\n");

interface SkillDrawerProps {
  open: boolean;
  editingSkill: SkillSpec | null;
  form: FormInstance<SkillSpec>;
  onClose: () => void;
  onSubmit: (values: SkillSpec) => void;
  onContentChange?: (content: string) => void;
}

export function SkillDrawer({
  open,
  editingSkill,
  form,
  onClose,
  onSubmit,
  onContentChange,
}: SkillDrawerProps) {
  const [showMarkdown, setShowMarkdown] = useState(true);
  const [contentValue, setContentValue] = useState("");

  const validateFrontmatter = useCallback(
    (_: unknown, value: string) => {
      const content = contentValue || value;
      if (!content || !content.trim()) {
        return Promise.reject(new Error("请输入技能内容"));
      }
      const fm = parseFrontmatter(content);
      if (!fm) {
        return Promise.reject(
          new Error("技能内容必须包含 frontmatter"),
        );
      }
      if (!fm.name) {
        return Promise.reject(
          new Error("frontmatter 中必须包含 name"),
        );
      }
      if (!fm.description) {
        return Promise.reject(
          new Error("frontmatter 中必须包含 description"),
        );
      }
      return Promise.resolve();
    },
    [contentValue],
  );

  useEffect(() => {
    if (editingSkill) {
      setContentValue(editingSkill.content);
      form.setFieldsValue({
        name: editingSkill.name,
        content: editingSkill.content,
      });
      return;
    }
    setContentValue("");
    form.resetFields();
  }, [editingSkill, form]);

  const handleSubmit = (values: { name: string; content: string }) => {
    if (editingSkill) {
      message.warning("暂不支持直接编辑现有技能");
      onClose();
      return;
    }
    onSubmit({
      ...values,
      content: contentValue || values.content,
      source: "",
      path: "",
    });
  };

  const handleContentChange = (content: string) => {
    setContentValue(content);
    form.setFieldsValue({ content });
    form.validateFields(["content"]).catch(() => {});
    onContentChange?.(content);
  };

  return (
    <Drawer
      width={520}
      placement="right"
      title={editingSkill ? "查看技能" : "新建技能"}
      open={open}
      onClose={onClose}
      destroyOnClose
    >
      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        {!editingSkill && (
          <>
            <Form.Item
              name="name"
              label={"技能名称"}
              rules={[
                {
                  required: true,
                  message: "请输入技能名称",
                },
              ]}
            >
              <Input placeholder={"请输入技能名称"} />
            </Form.Item>

            <Form.Item
              name="content"
              label={"技能内容"}
              rules={[{ required: true, validator: validateFrontmatter }]}
            >
              <MarkdownCopy
                content={contentValue}
                showMarkdown={showMarkdown}
                onShowMarkdownChange={setShowMarkdown}
                editable
                onContentChange={handleContentChange}
                textareaProps={{
                  placeholder: CONTENT_PLACEHOLDER,
                  rows: 12,
                }}
              />
            </Form.Item>

            <Form.Item>
              <div
                style={{
                  display: "flex",
                  justifyContent: "flex-end",
                  gap: 8,
                  marginTop: 16,
                }}
              >
                <Button onClick={onClose}>{"取消"}</Button>
                <Button type="primary" htmlType="submit">
                  {"创建"}
                </Button>
              </div>
            </Form.Item>
          </>
        )}

        {editingSkill && (
          <>
            <Form.Item name="name" label={"技能名称"}>
              <Input disabled />
            </Form.Item>

            <Form.Item name="content" label={"技能内容"}>
              <MarkdownCopy
                content={editingSkill.content}
                showMarkdown={showMarkdown}
                onShowMarkdownChange={setShowMarkdown}
                textareaProps={{
                  disabled: true,
                  rows: 12,
                }}
              />
            </Form.Item>

            <Form.Item name="source" label={"来源"}>
              <Input disabled />
            </Form.Item>

            <Form.Item name="path" label={"路径"}>
              <Input disabled />
            </Form.Item>

            <div
              style={{
                padding: 12,
                backgroundColor: "#fffbe6",
                border: "1px solid #ffe58f",
                borderRadius: 4,
                marginTop: 16,
              }}
            >
              <p style={{ margin: 0, fontSize: 12, color: "#8c8c8c" }}>
                {
                  "当前只支持查看技能详情，暂不支持在此页面直接编辑。"
                }
              </p>
            </div>
          </>
        )}
      </Form>
    </Drawer>
  );
}
