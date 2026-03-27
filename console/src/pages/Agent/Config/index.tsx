import { useState, useEffect } from "react";
import { Form, InputNumber, Button, Card, message } from "@/ui";
import api from "../../../api";
import styles from "./index.module.less";
import type { AgentsRunningConfig } from "../../../api/types";

const PAGE_TITLE = "智能体运行配置";
const PAGE_DESCRIPTION = "配置智能体的最大迭代次数和输入长度限制。";
const LOAD_FAILED = "加载智能体运行配置失败";
const SAVE_SUCCESS = "智能体运行配置已保存";
const SAVE_FAILED = "保存智能体运行配置失败";
const LOADING = "加载中...";
const RETRY = "重试";
const MAX_ITERS_LABEL = "最大迭代次数";
const MAX_ITERS_REQUIRED = "请输入最大迭代次数";
const MAX_ITERS_MIN = "最大迭代次数不能小于 1";
const MAX_ITERS_TOOLTIP = "单次任务允许执行的最大轮数。";
const MAX_INPUT_LABEL = "最大输入长度";
const MAX_INPUT_REQUIRED = "请输入最大输入长度";
const MAX_INPUT_MIN = "最大输入长度不能小于 1000";
const MAX_INPUT_TOOLTIP = "限制 Agent 单次可处理的最大输入字符数。";
const RESET = "重置";
const SAVE = "保存";

function AgentConfigPage() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetchConfig();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchConfig = async () => {
    setLoading(true);
    setError(null);
    try {
      const config = await api.getAgentRunningConfig();
      form.setFieldsValue(config);
    } catch (err) {
      setError(err instanceof Error ? err.message : LOAD_FAILED);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      await api.updateAgentRunningConfig(values as AgentsRunningConfig);
      message.success(SAVE_SUCCESS);
    } catch (err) {
      if (err instanceof Error && "errorFields" in err) {
        return;
      }
      message.error(err instanceof Error ? err.message : SAVE_FAILED);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={styles.page}>
      {loading && (
        <div className={styles.centerState}>
          <span className={styles.stateText}>{LOADING}</span>
        </div>
      )}

      {error && !loading && (
        <div className={styles.centerState}>
          <span className={styles.stateTextError}>{error}</span>
          <Button size="small" onClick={() => void fetchConfig()} style={{ marginTop: 12 }}>
            {RETRY}
          </Button>
        </div>
      )}

      <div style={{ display: loading || error ? "none" : "block" }}>
        <Card className="baize-page-header">
          <div className="baize-page-header-content">
            <div>
              <h1 className="baize-page-header-title">{PAGE_TITLE}</h1>
              <p className="baize-page-header-description">{PAGE_DESCRIPTION}</p>
            </div>
          </div>
        </Card>

        <Card className={styles.formCard}>
          <Form form={form} layout="vertical" className={styles.form}>
            <Form.Item
              label={MAX_ITERS_LABEL}
              name="max_iters"
              rules={[
                { required: true, message: MAX_ITERS_REQUIRED },
                {
                  type: "number",
                  min: 1,
                  message: MAX_ITERS_MIN,
                },
              ]}
              tooltip={MAX_ITERS_TOOLTIP}
            >
              <InputNumber
                style={{ width: "100%" }}
                min={1}
                placeholder={MAX_ITERS_REQUIRED}
              />
            </Form.Item>

            <Form.Item
              label={MAX_INPUT_LABEL}
              name="max_input_length"
              rules={[
                {
                  required: true,
                  message: MAX_INPUT_REQUIRED,
                },
                {
                  type: "number",
                  min: 1000,
                  message: MAX_INPUT_MIN,
                },
              ]}
              tooltip={MAX_INPUT_TOOLTIP}
            >
              <InputNumber
                style={{ width: "100%" }}
                min={1000}
                step={1024}
                placeholder={MAX_INPUT_REQUIRED}
              />
            </Form.Item>

            <Form.Item className={styles.buttonGroup}>
              <Button
                onClick={() => void fetchConfig()}
                disabled={saving}
                style={{ marginRight: 8 }}
              >
                {RESET}
              </Button>
              <Button type="primary" onClick={handleSave} loading={saving}>
                {SAVE}
              </Button>
            </Form.Item>
          </Form>
        </Card>
      </div>
    </div>
  );
}

export default AgentConfigPage;
