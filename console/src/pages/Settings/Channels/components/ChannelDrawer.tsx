import {
  Alert,
  Button,
  Drawer,
  Form,
  Input,
  InputNumber,
  Select,
  Switch,
} from "@/ui";
import { LinkOutlined } from "@ant-design/icons";
import type { FormInstance } from "antd";
import type { WeixinILinkLoginRuntimeState } from "../../../../api/types";
import { getChannelLabel, type ChannelKey } from "./constants";
import styles from "../index.module.less";

const CHANNEL_DOC_URLS: Partial<Record<ChannelKey, string>> = {
  dingtalk: "https://copaw.agentscope.io/docs/channels",
  feishu: "https://copaw.agentscope.io/docs/channels",
  imessage: "https://copaw.agentscope.io/docs/channels",
  discord: "https://copaw.agentscope.io/docs/channels",
  qq: "https://copaw.agentscope.io/docs/channels",
  telegram: "https://copaw.agentscope.io/docs/channels",
  weixin_ilink: "https://copaw.agentscope.io/docs/channels",
  mqtt: "https://copaw.agentscope.io/docs/channels",
};

const CHANNELS_WITH_ACCESS_CONTROL: ChannelKey[] = [
  "telegram",
  "dingtalk",
  "discord",
  "feishu",
  "weixin_ilink",
];

const twilioConsoleUrl = "https://console.twilio.com";

const LOGIN_STATUS_LABELS: Record<string, string> = {
  unconfigured: "未配置",
  waiting_scan: "等待扫码",
  authorized_pending_save: "已授权，待保存",
  auth_expired: "授权失效",
};

const POLLING_STATUS_LABELS: Record<string, string> = {
  stopped: "未运行",
  running: "运行中",
};

interface ChannelDrawerProps {
  open: boolean;
  activeKey: ChannelKey | null;
  activeLabel: string;
  form: FormInstance<Record<string, unknown>>;
  saving: boolean;
  initialValues: Record<string, unknown> | undefined;
  isBuiltin: boolean;
  loginRuntime?: WeixinILinkLoginRuntimeState | null;
  loginActionLoading?: "qr" | "status" | "rebind" | null;
  onClose: () => void;
  onSubmit: (values: Record<string, unknown>) => void;
  onFetchWeixinLoginQr?: () => void;
  onRefreshWeixinLoginStatus?: () => void;
  onRebindWeixinLogin?: () => void;
}

function labelForLoginStatus(status?: string) {
  return LOGIN_STATUS_LABELS[status ?? ""] ?? status ?? "未配置";
}

function labelForPollingStatus(status?: string) {
  return POLLING_STATUS_LABELS[status ?? ""] ?? status ?? "未运行";
}

export function ChannelDrawer({
  open,
  activeKey,
  activeLabel,
  form,
  saving,
  initialValues,
  isBuiltin,
  loginRuntime,
  loginActionLoading = null,
  onClose,
  onSubmit,
  onFetchWeixinLoginQr,
  onRefreshWeixinLoginStatus,
  onRebindWeixinLogin,
}: ChannelDrawerProps) {
  const label = activeKey ? getChannelLabel(activeKey) : activeLabel;

  const renderAccessControlFields = () => (
    <>
      <Form.Item
        name="dm_policy"
        label="私聊策略"
        tooltip="控制谁可以通过私聊与主脑交互。开放表示所有联系人都可进入；白名单表示仅允许已授权对象。"
        initialValue="open"
      >
        <Select
          options={[
            { value: "open", label: "开放" },
            { value: "allowlist", label: "白名单" },
          ]}
        />
      </Form.Item>
      <Form.Item
        name="group_policy"
        label="群聊策略"
        tooltip="控制群聊消息是否有资格进入主脑前门。开放表示允许群内消息触发；白名单表示只有授权群或授权用户可触发。"
        initialValue="open"
      >
        <Select
          options={[
            { value: "open", label: "开放" },
            { value: "allowlist", label: "白名单" },
          ]}
        />
      </Form.Item>
      <Form.Item
        name="allow_from"
        label="白名单对象"
        tooltip="允许与主脑交互的对象列表。可填写用户、联系人或其他渠道侧的标识。"
        initialValue={[]}
      >
        <Select
          mode="tags"
          placeholder="输入标识后按回车添加"
          tokenSeparators={[","]}
        />
      </Form.Item>
    </>
  );

  const renderWeixinILinkRuntimeCard = () => {
    if (activeKey !== "weixin_ilink") {
      return null;
    }

    const runtime = loginRuntime ?? {
      login_status: "unconfigured",
      polling_status: "stopped",
      token_source: "",
      last_qr_issued_at: null,
      last_update_id: null,
      last_receive_at: null,
      last_send_at: null,
      last_error: "",
      qrcode: "",
      qrcode_img_content: "",
      bot_token: "",
      base_url: "",
      ilink_bot_id: "",
      ilink_user_id: "",
    };

    return (
      <Alert
        type={runtime.last_error ? "warning" : "info"}
        showIcon
        style={{ marginBottom: 24 }}
        message="iLink 登录与运行状态"
        description={
          <div style={{ display: "grid", gap: 8 }}>
            <div>登录状态：{labelForLoginStatus(runtime.login_status)}</div>
            <div>轮询状态：{labelForPollingStatus(runtime.polling_status)}</div>
            <div>Token 来源：{runtime.token_source || "未获取"}</div>
            {runtime.qrcode ? <div>当前二维码：{runtime.qrcode}</div> : null}
            {runtime.qrcode_img_content ? (
              <div>二维码地址：{runtime.qrcode_img_content}</div>
            ) : null}
            {runtime.last_qr_issued_at ? (
              <div>最近发码时间：{runtime.last_qr_issued_at}</div>
            ) : null}
            {runtime.last_error ? <div>最近错误：{runtime.last_error}</div> : null}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <Button
                type="default"
                loading={loginActionLoading === "qr"}
                onClick={onFetchWeixinLoginQr}
              >
                获取登录二维码
              </Button>
              <Button
                type="default"
                loading={loginActionLoading === "status"}
                onClick={onRefreshWeixinLoginStatus}
              >
                检查登录状态
              </Button>
              <Button
                danger
                loading={loginActionLoading === "rebind"}
                onClick={onRebindWeixinLogin}
              >
                重新扫码授权
              </Button>
            </div>
          </div>
        }
      />
    );
  };

  const renderBuiltinExtraFields = (key: ChannelKey) => {
    switch (key) {
      case "imessage":
        return (
          <>
            <Form.Item
              name="db_path"
              label="数据库路径"
              rules={[{ required: true, message: "请输入数据库路径" }]}
            >
              <Input placeholder="~/Library/Messages/chat.db" />
            </Form.Item>
            <Form.Item
              name="poll_sec"
              label="轮询间隔（秒）"
              rules={[{ required: true, message: "请输入轮询间隔" }]}
            >
              <InputNumber min={0.1} step={0.1} style={{ width: "100%" }} />
            </Form.Item>
          </>
        );
      case "discord":
        return (
          <>
            <Form.Item name="bot_token" label="Bot Token">
              <Input.Password placeholder="Discord Bot Token" />
            </Form.Item>
            <Form.Item name="http_proxy" label="HTTP 代理">
              <Input placeholder="http://127.0.0.1:18118" />
            </Form.Item>
            <Form.Item name="http_proxy_auth" label="HTTP 代理认证">
              <Input placeholder="用户名:密码" />
            </Form.Item>
          </>
        );
      case "dingtalk":
        return (
          <>
            <Form.Item name="client_id" label="应用 ID">
              <Input />
            </Form.Item>
            <Form.Item name="client_secret" label="应用密钥">
              <Input.Password />
            </Form.Item>
          </>
        );
      case "feishu":
        return (
          <>
            <Form.Item name="app_id" label="应用 ID" rules={[{ required: true }]}>
              <Input placeholder="cli_xxx" />
            </Form.Item>
            <Form.Item
              name="app_secret"
              label="应用密钥"
              rules={[{ required: true }]}
            >
              <Input.Password placeholder="请输入应用密钥" />
            </Form.Item>
            <Form.Item name="encrypt_key" label="加密密钥">
              <Input placeholder="请输入加密密钥" />
            </Form.Item>
            <Form.Item name="verification_token" label="验证令牌">
              <Input placeholder="选填" />
            </Form.Item>
            <Form.Item name="media_dir" label="媒体目录">
              <Input placeholder="请输入媒体目录" />
            </Form.Item>
          </>
        );
      case "qq":
        return (
          <>
            <Form.Item name="app_id" label="应用 ID">
              <Input />
            </Form.Item>
            <Form.Item name="client_secret" label="应用密钥">
              <Input.Password />
            </Form.Item>
          </>
        );
      case "telegram":
        return (
          <>
            <Form.Item name="bot_token" label="Bot Token">
              <Input.Password placeholder="请输入 Telegram Bot Token" />
            </Form.Item>
            <Form.Item name="http_proxy" label="HTTP 代理">
              <Input placeholder="http://127.0.0.1:18118" />
            </Form.Item>
            <Form.Item name="http_proxy_auth" label="HTTP 代理认证">
              <Input placeholder="用户名:密码" />
            </Form.Item>
            <Form.Item
              name="show_typing"
              label="显示输入中状态"
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
          </>
        );
      case "weixin_ilink":
        return (
          <>
            <Form.Item
              name="bot_token"
              label="Bot Token"
              tooltip="扫码成功后会自动回填，也可以手工粘贴已有 token。"
            >
              <Input.Password placeholder="扫码后自动回填或手工输入" />
            </Form.Item>
            <Form.Item name="bot_token_file" label="Bot Token 文件">
              <Input placeholder="~/.qwenpaw/weixin_bot_token" />
            </Form.Item>
            <Form.Item name="base_url" label="iLink API 地址">
              <Input placeholder="留空使用官方默认地址" />
            </Form.Item>
            <Form.Item name="media_dir" label="媒体目录">
              <Input placeholder="~/.qwenpaw/media" />
            </Form.Item>
            <Form.Item name="group_reply_mode" label="群回复模式">
              <Select
                options={[
                  { value: "mention_or_prefix", label: "@主脑或前缀才回复" },
                  {
                    value: "whitelist_full_open",
                    label: "白名单群可全量响应",
                  },
                ]}
              />
            </Form.Item>
            <Form.Item name="group_allowlist" label="群白名单">
              <Select
                mode="tags"
                placeholder="输入群标识后按回车添加"
                tokenSeparators={[","]}
              />
            </Form.Item>
            <Form.Item name="proactive_targets" label="主动汇报目标">
              <Select
                mode="tags"
                placeholder="例如 dm:user-alpha 或 group:group-alpha"
                tokenSeparators={[","]}
              />
            </Form.Item>
          </>
        );
      case "mqtt":
        return (
          <>
            <Form.Item name="host" label="MQTT 主机" rules={[{ required: true }]}>
              <Input placeholder="127.0.0.1" />
            </Form.Item>
            <Form.Item
              name="port"
              label="MQTT 端口"
              rules={[
                { required: true },
                {
                  type: "number",
                  min: 1,
                  max: 65535,
                  message: "端口范围应在 1 到 65535 之间",
                },
              ]}
            >
              <InputNumber
                min={1}
                max={65535}
                style={{ width: "100%" }}
                placeholder="1883"
              />
            </Form.Item>
            <Form.Item
              name="transport"
              label="传输协议"
              initialValue="tcp"
              rules={[{ required: true }]}
            >
              <Select
                options={[
                  { value: "tcp", label: "TCP" },
                  { value: "websockets", label: "WebSocket" },
                ]}
              />
            </Form.Item>
            <Form.Item
              name="clean_session"
              label="清理会话"
              valuePropName="checked"
            >
              <Switch defaultChecked />
            </Form.Item>
            <Form.Item
              name="qos"
              label="QoS"
              initialValue="2"
              rules={[{ required: true }]}
            >
              <Select
                options={[
                  { value: "0", label: "QoS 0" },
                  { value: "1", label: "QoS 1" },
                  { value: "2", label: "QoS 2" },
                ]}
              />
            </Form.Item>
            <Form.Item name="username" label="MQTT 用户名">
              <Input placeholder="留空则不启用" />
            </Form.Item>
            <Form.Item name="password" label="MQTT 密码">
              <Input.Password placeholder="留空则不启用" />
            </Form.Item>
            <Form.Item
              name="subscribe_topic"
              label="订阅主题"
              rules={[{ required: true }]}
            >
              <Input placeholder="server/+/up" />
            </Form.Item>
            <Form.Item
              name="publish_topic"
              label="发布主题"
              rules={[{ required: true }]}
            >
              <Input placeholder="client/{client_id}/down" />
            </Form.Item>
            <Form.Item
              name="tls_enabled"
              label="启用 TLS"
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
            <Form.Item name="tls_ca_certs" label="TLS CA 证书">
              <Input placeholder="请输入 CA 证书路径" />
            </Form.Item>
            <Form.Item name="tls_certfile" label="TLS 证书">
              <Input placeholder="请输入 TLS 证书路径" />
            </Form.Item>
            <Form.Item name="tls_keyfile" label="TLS 私钥">
              <Input placeholder="请输入 TLS 私钥路径" />
            </Form.Item>
          </>
        );
      case "voice":
        return (
          <>
            <Alert
              type="info"
              showIcon
              message="请先注册 Twilio 账号并购买电话号码，然后在下方填写凭据。账户编号和认证令牌可在 Twilio 控制台首页找到，号码 SID 可在电话号码列表中查看。"
              style={{ marginBottom: 32 }}
            />
            <Form.Item name="twilio_account_sid" label="Twilio 账户 SID">
              <Input placeholder="ACxxxxxxxx" />
            </Form.Item>
            <Form.Item name="twilio_auth_token" label="Twilio 认证令牌">
              <Input.Password />
            </Form.Item>
            <Form.Item name="phone_number" label="电话号码">
              <Input placeholder="+15551234567" />
            </Form.Item>
            <Form.Item
              name="phone_number_sid"
              label="电话号码 SID"
              tooltip="可在 Twilio 控制台的电话号码列表中找到。"
            >
              <Input placeholder="PNxxxxxxxx" />
            </Form.Item>
            <Form.Item name="tts_provider" label="语音合成提供方">
              <Input placeholder="google" />
            </Form.Item>
            <Form.Item name="tts_voice" label="语音合成音色">
              <Input placeholder="en-US-Journey-D" />
            </Form.Item>
            <Form.Item name="stt_provider" label="语音识别提供方">
              <Input placeholder="deepgram" />
            </Form.Item>
            <Form.Item name="language" label="语言">
              <Input placeholder="en-US" />
            </Form.Item>
            <Form.Item name="welcome_greeting" label="欢迎语">
              <Input.TextArea rows={2} />
            </Form.Item>
          </>
        );
      default:
        return null;
    }
  };

  const renderCustomExtraFields = (
    customInitialValues: Record<string, unknown> | undefined,
  ) => {
    if (!customInitialValues) {
      return null;
    }

    const baseFields = [
      "enabled",
      "bot_prefix",
      "filter_tool_messages",
      "filter_thinking",
      "isBuiltin",
    ];
    const extraKeys = Object.keys(customInitialValues).filter(
      (key) => !baseFields.includes(key),
    );

    if (extraKeys.length === 0) {
      return null;
    }

    return (
      <>
        <div style={{ marginBottom: 8, fontWeight: 500 }}>自定义字段</div>
        {extraKeys.map((fieldKey) => {
          const value = customInitialValues[fieldKey];
          const isBoolean = typeof value === "boolean";
          const isNumber = typeof value === "number";

          return (
            <Form.Item key={fieldKey} name={fieldKey} label={fieldKey}>
              {isBoolean ? (
                <Switch />
              ) : isNumber ? (
                <InputNumber style={{ width: "100%" }} />
              ) : (
                <Input />
              )}
            </Form.Item>
          );
        })}
      </>
    );
  };

  return (
    <Drawer
      width={420}
      placement="right"
      title={
        <div className={styles.drawerTitle}>
          <span>{label ? `${label} 设置` : "频道设置"}</span>
          {activeKey && CHANNEL_DOC_URLS[activeKey] ? (
            <Button
              type="text"
              size="small"
              icon={<LinkOutlined />}
              onClick={() => window.open(CHANNEL_DOC_URLS[activeKey], "_blank")}
              className={styles.dingtalkDocBtn}
            >
              {label} 指南
            </Button>
          ) : null}
          {activeKey === "voice" ? (
            <Button
              type="text"
              size="small"
              icon={<LinkOutlined />}
              onClick={() =>
                window.open(twilioConsoleUrl, "_blank", "noopener,noreferrer")
              }
              className={styles.dingtalkDocBtn}
            >
              打开 Twilio 控制台
            </Button>
          ) : null}
        </div>
      }
      open={open}
      onClose={onClose}
      destroyOnClose
    >
      {activeKey ? (
        <Form
          form={form}
          layout="vertical"
          initialValues={initialValues}
          onFinish={onSubmit}
        >
          {renderWeixinILinkRuntimeCard()}

          <Form.Item name="enabled" label="已启用" valuePropName="checked">
            <Switch />
          </Form.Item>

          {activeKey !== "voice" ? (
            <Form.Item name="bot_prefix" label="机器人前缀">
              <Input placeholder="@bot" />
            </Form.Item>
          ) : null}

          {activeKey !== "console" ? (
            <>
              <Form.Item
                name="filter_tool_messages"
                label="显示工具消息"
                valuePropName="checked"
                tooltip="向用户显示工具调用与工具输出消息；关闭后将隐藏。"
              >
                <Switch />
              </Form.Item>
              <Form.Item
                name="filter_thinking"
                label="显示思考过程"
                valuePropName="checked"
                tooltip="向用户显示模型的思考与推理内容；关闭后将隐藏。"
              >
                <Switch />
              </Form.Item>
            </>
          ) : null}

          {isBuiltin
            ? renderBuiltinExtraFields(activeKey)
            : renderCustomExtraFields(initialValues)}

          {CHANNELS_WITH_ACCESS_CONTROL.includes(activeKey)
            ? renderAccessControlFields()
            : null}

          <Form.Item>
            <div className={styles.formActions}>
              <Button onClick={onClose}>取消</Button>
              <Button type="primary" htmlType="submit" loading={saving}>
                保存
              </Button>
            </div>
          </Form.Item>
        </Form>
      ) : null}
    </Drawer>
  );
}
