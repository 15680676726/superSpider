import React from "react";
import { Form, Input, ColorPicker, Flex, Divider, InputNumber } from "antd";
import { createStyles } from "antd-style";
import { Button, IconButton, Switch } from "@/ui";
import { SparkDeleteLine, SparkPlusLine } from "@agentscope-ai/icons";
import FormItem from "./FormItem";
import defaultConfig from "./defaultConfig";

const useStyles = createStyles(({ token }) => ({
  container: {
    height: "100%",
    display: "flex",
    flexDirection: "column",
  },

  form: {
    height: 0,
    flex: 1,
    padding: "8px 16px 16px 16px",
    overflow: "auto",
  },
  actions: {
    padding: 16,
    display: "flex",
    borderTop: `1px solid ${token.colorBorderSecondary}`,
    justifyContent: "flex-end",
    gap: 16,
  },
}));

const TEXT = {
  themeSection: "主题配置",
  colorPrimary: "主色",
  colorBgBase: "背景色",
  colorTextBase: "主文字颜色",
  darkMode: "暗色模式",
  leftHeaderLogo: "左侧头图 Logo",
  leftHeaderTitle: "左侧标题",
  senderSection: "发送者配置",
  disclaimer: "提示语",
  maxLength: "最大长度",
  welcomeSection: "欢迎语配置",
  greeting: "问候语",
  description: "描述",
  avatar: "头像",
  prompts: "预置提示",
  apiSection: "API 配置",
  baseUrl: "服务地址",
  token: "接口令牌",
  saveAndCopy: "保存",
  reset: "重置",
} as const;

interface OptionsEditorProps {
  value?: Record<string, unknown>;
  onChange?: (value: Record<string, unknown>) => void;
}

const OptionsEditor: React.FC<OptionsEditorProps> = ({ value, onChange }) => {
  const { styles } = useStyles();
  const [form] = Form.useForm();

  const handleSave = () => {
    form
      .validateFields()
      .then((values) => {
        onChange?.(values);
      })
      .catch((error) => {
        console.error("Validation failed:", error);
      });
  };

  const handleReset = () => {
    form.setFieldsValue(defaultConfig);
  };

  return (
    <div className={styles.container}>
      <Form
        className={styles.form}
        form={form}
        layout="vertical"
        initialValues={value}
      >
        <Divider orientation="left">{TEXT.themeSection}</Divider>

        <FormItem
          name={["theme", "colorPrimary"]}
          label={TEXT.colorPrimary}
          normalize={(value) => value.toHexString()}
        >
          <ColorPicker />
        </FormItem>

        <FormItem
          name={["theme", "colorBgBase"]}
          label={TEXT.colorBgBase}
          normalize={(value) => value.toHexString()}
        >
          <ColorPicker />
        </FormItem>

        <FormItem
          name={["theme", "colorTextBase"]}
          label={TEXT.colorTextBase}
          normalize={(value) => value.toHexString()}
        >
          <ColorPicker />
        </FormItem>

        <FormItem name={["theme", "darkMode"]} label={TEXT.darkMode}>
          <Switch />
        </FormItem>

        <FormItem
          name={["theme", "leftHeader", "logo"]}
          label={TEXT.leftHeaderLogo}
        >
          <Input />
        </FormItem>

        <FormItem
          name={["theme", "leftHeader", "title"]}
          label={TEXT.leftHeaderTitle}
        >
          <Input />
        </FormItem>

        <Divider orientation="left">{TEXT.senderSection}</Divider>

        <FormItem name={["sender", "disclaimer"]} label={TEXT.disclaimer}>
          <Input />
        </FormItem>

        <FormItem name={["sender", "maxLength"]} label={TEXT.maxLength}>
          <InputNumber min={1000} />
        </FormItem>

        <Divider orientation="left">{TEXT.welcomeSection}</Divider>

        <FormItem name={["welcome", "greeting"]} label={TEXT.greeting}>
          <Input />
        </FormItem>

        <FormItem name={["welcome", "description"]} label={TEXT.description}>
          <Input />
        </FormItem>

        <FormItem name={["welcome", "avatar"]} label={TEXT.avatar}>
          <Input />
        </FormItem>

        <FormItem name={["welcome", "prompts"]} isList label={TEXT.prompts}>
          {(
            fields: { key: string; name: string }[],
            {
              add,
              remove,
            }: { add: (item: any) => void; remove: (name: string) => void },
          ) => (
            <div>
              {fields.map((field) => (
                <Flex key={field.key} gap={6}>
                  <Form.Item
                    style={{ flex: 1 }}
                    key={field.key}
                    name={[field.name, "value"]}
                  >
                    <Input />
                  </Form.Item>
                  <IconButton icon={<SparkPlusLine />} onClick={() => add({})} />
                  <IconButton
                    icon={<SparkDeleteLine />}
                    onClick={() => remove(field.name)}
                  />
                </Flex>
              ))}
            </div>
          )}
        </FormItem>

        <Divider orientation="left">{TEXT.apiSection}</Divider>

        <FormItem name={["api", "baseURL"]} label={TEXT.baseUrl}>
          <Input />
        </FormItem>

        <FormItem name={["api", "token"]} label={TEXT.token}>
          <Input />
        </FormItem>
      </Form>

      <div className={styles.actions}>
        <Button onClick={handleReset}>{TEXT.reset}</Button>
        <Button type="primary" onClick={handleSave}>
          {TEXT.saveAndCopy}
        </Button>
      </div>
    </div>
  );
};

export default OptionsEditor;
