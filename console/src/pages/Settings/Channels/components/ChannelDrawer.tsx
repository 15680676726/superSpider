import {
  Alert,
  Drawer,
  Form,
  Input,
  InputNumber,
  Switch,
  Button,
  Select,
} from "@/ui";
import { LinkOutlined } from "@ant-design/icons";
import type { FormInstance } from "antd";
import { getChannelLabel, type ChannelKey } from "./constants";
import styles from "../index.module.less";

const CHANNEL_TEXT: Record<string, string> = {
  "channels.appId": "应用 ID",
  "channels.appSecret": "应用密钥",
  "channels.blankToDisablePlaceholder": "留空则不启用",
  "channels.botToken": "机器人令牌",
  "channels.cleanSession": "清理会话",
  "channels.clientId": "客户端编号",
  "channels.clientSecret": "客户端密钥",
  "channels.customFields": "自定义字段",
  "channels.dbPath": "数据库路径",
  "channels.encryptKey": "加密密钥",
  "channels.encryptKeyPlaceholder": "请输入加密密钥",
  "channels.guide": "指南",
  "channels.httpProxy": "HTTP 代理",
  "channels.httpProxyAuth": "HTTP 代理认证",
  "channels.mediaDir": "媒体目录",
  "channels.mediaDirPlaceholder": "请输入媒体目录",
  "channels.mqttHost": "MQTT 主机",
  "channels.mqttPassword": "MQTT 密码",
  "channels.mqttPort": "MQTT 端口",
  "channels.mqttUsername": "MQTT 用户名",
  "channels.optionalPlaceholder": "选填",
  "channels.pollIntervalSeconds": "轮询间隔（秒）",
  "channels.portRangeMessage": "端口范围应在 1 到 65535 之间",
  "channels.publishTopic": "发布主题",
  "channels.qos": "QoS",
  "channels.qos0": "QoS 0",
  "channels.qos1": "QoS 1",
  "channels.qos2": "QoS 2",
  "channels.showTyping": "显示输入中状态",
  "channels.subscribeTopic": "订阅主题",
  "channels.telegramBotToken": "请输入 Telegram 机器人令牌",
  "channels.tlsCaCerts": "TLS CA 证书",
  "channels.tlsCaCertsPlaceholder": "请输入 CA 证书路径",
  "channels.tlsCertfile": "TLS 证书",
  "channels.tlsCertfilePlaceholder": "请输入 TLS 证书路径",
  "channels.tlsEnabled": "启用 TLS",
  "channels.tlsKeyfile": "TLS 私钥",
  "channels.tlsKeyfilePlaceholder": "请输入 TLS 私钥路径",
  "channels.transport": "传输协议",
  "channels.transportTcp": "TCP",
  "channels.transportWebsockets": "WebSocket",
  "channels.verificationToken": "验证令牌",
};

function zh(key: string) {
  return CHANNEL_TEXT[key] || key;
}


const CHANNELS_WITH_ACCESS_CONTROL: ChannelKey[] = [
  "telegram",
  "dingtalk",
  "discord",
  "feishu",
];

interface ChannelDrawerProps {
  open: boolean;
  activeKey: ChannelKey | null;
  activeLabel: string;
  form: FormInstance<Record<string, unknown>>;
  saving: boolean;
  initialValues: Record<string, unknown> | undefined;
  isBuiltin: boolean;
  onClose: () => void;
  onSubmit: (values: Record<string, unknown>) => void;
}

const CHANNEL_DOC_URLS: Partial<Record<ChannelKey, string>> = {
  dingtalk: "https://copaw.agentscope.io/docs/channels",
  feishu: "https://copaw.agentscope.io/docs/channels",
  imessage: "https://copaw.agentscope.io/docs/channels",
  discord: "https://copaw.agentscope.io/docs/channels",
  qq: "https://copaw.agentscope.io/docs/channels",
  telegram: "https://copaw.agentscope.io/docs/channels",
  mqtt: "https://copaw.agentscope.io/docs/channels",
};
const twilioConsoleUrl = "https://console.twilio.com";

export function ChannelDrawer({
  open,
  activeKey,
  activeLabel,
  form,
  saving,
  initialValues,
  isBuiltin,
  onClose,
  onSubmit,
}: ChannelDrawerProps) {
  const label = activeKey ? getChannelLabel(activeKey) : activeLabel;

  const renderAccessControlFields = () => (
    <>
      <Form.Item
        name="dm_policy"
        label={"私聊策略"}
        tooltip={"控制谁可以通过私聊与机器人交互。开放：所有人；白名单：仅限授权用户"}
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
        label={"群聊策略"}
        tooltip={"控制谁可以在群聊中与机器人交互。开放：所有人；白名单：仅限授权用户"}
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
        label={"白名单用户"}
        tooltip={"允许与机器人交互的用户编号列表（格式：昵称#后4位，如 张三#1234）"}
        initialValue={[]}
      >
        <Select
          mode="tags"
          placeholder={"输入用户编号后按回车添加"}
          tokenSeparators={[","]}
        />
      </Form.Item>
    </>
  );

  const renderBuiltinExtraFields = (key: ChannelKey) => {
    switch (key) {
      case "imessage":
        return (
          <>
            <Form.Item
              name="db_path"
              label={zh("channels.dbPath")}
              rules={[{ required: true, message: "请输入数据库路径" }]}
            >
              <Input placeholder={"~/Library/Messages/chat.db"} />
            </Form.Item>
            <Form.Item
              name="poll_sec"
              label={zh("channels.pollIntervalSeconds")}
              rules={[
                { required: true, message: "请输入轮询间隔" },
              ]}
            >
              <InputNumber min={0.1} step={0.1} style={{ width: "100%" }} />
            </Form.Item>
          </>
        );
      case "discord":
        return (
          <>
            <Form.Item name="bot_token" label={zh("channels.botToken")}>
              <Input.Password placeholder={"Discord机器人令牌"} />
            </Form.Item>
            <Form.Item name="http_proxy" label={zh("channels.httpProxy")}>
              <Input placeholder={"http://127.0.0.1:18118"} />
            </Form.Item>
            <Form.Item name="http_proxy_auth" label={zh("channels.httpProxyAuth")}>
              <Input placeholder={"用户名:密码"} />
            </Form.Item>
          </>
        );
      case "dingtalk":
        return (
          <>
            <Form.Item name="client_id" label={zh("channels.clientId")}>
              <Input />
            </Form.Item>
            <Form.Item name="client_secret" label={zh("channels.clientSecret")}>
              <Input.Password />
            </Form.Item>
          </>
        );
      case "feishu":
        return (
          <>
            <Form.Item
              name="app_id"
              label={zh("channels.appId")}
              rules={[{ required: true }]}
            >
              <Input placeholder="cli_xxx" />
            </Form.Item>
            <Form.Item
              name="app_secret"
              label={zh("channels.appSecret")}
              rules={[{ required: true }]}
            >
              <Input.Password placeholder={zh("channels.appSecret")} />
            </Form.Item>
            <Form.Item name="encrypt_key" label={zh("channels.encryptKey")}>
              <Input placeholder={zh("channels.encryptKeyPlaceholder")} />
            </Form.Item>
            <Form.Item
              name="verification_token"
              label={zh("channels.verificationToken")}
            >
              <Input placeholder={zh("channels.optionalPlaceholder")} />
            </Form.Item>
            <Form.Item name="media_dir" label={zh("channels.mediaDir")}>
              <Input placeholder={zh("channels.mediaDirPlaceholder")} />
            </Form.Item>
          </>
        );
      case "qq":
        return (
          <>
            <Form.Item name="app_id" label={zh("channels.appId")}>
              <Input />
            </Form.Item>
            <Form.Item name="client_secret" label={zh("channels.clientSecret")}>
              <Input.Password />
            </Form.Item>
          </>
        );
      case "telegram":
        return (
          <>
            <Form.Item name="bot_token" label={zh("channels.botToken")}>
              <Input.Password placeholder={zh("channels.telegramBotToken")} />
            </Form.Item>
            <Form.Item name="http_proxy" label={zh("channels.httpProxy")}>
              <Input placeholder={"http://127.0.0.1:18118"} />
            </Form.Item>
            <Form.Item name="http_proxy_auth" label={zh("channels.httpProxyAuth")}>
              <Input placeholder={"用户名:密码"} />
            </Form.Item>
            <Form.Item
              name="show_typing"
              label={zh("channels.showTyping")}
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
          </>
        );
      case "mqtt":
        return (
          <>
            <Form.Item
              name="host"
              label={zh("channels.mqttHost")}
              rules={[{ required: true }]}
            >
              <Input placeholder="127.0.0.1" />
            </Form.Item>
            <Form.Item
              name="port"
              label={zh("channels.mqttPort")}
              rules={[
                { required: true },
                {
                  type: "number",
                  min: 1,
                  max: 65535,
                  message: zh("channels.portRangeMessage"),
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
              label={zh("channels.transport")}
              initialValue="tcp"
              rules={[{ required: true }]}
            >
              <Select>
                <Select.Option value="tcp">
                  {zh("channels.transportTcp")}
                </Select.Option>
                <Select.Option value="websockets">
                  {zh("channels.transportWebsockets")}
                </Select.Option>
              </Select>
            </Form.Item>
            <Form.Item
              name="clean_session"
              label={zh("channels.cleanSession")}
              valuePropName="checked"
            >
              <Switch defaultChecked />
            </Form.Item>
            <Form.Item
              name="qos"
              label={zh("channels.qos")}
              initialValue="2"
              rules={[{ required: true }]}
            >
              <Select>
                <Select.Option value="0">{zh("channels.qos0")}</Select.Option>
                <Select.Option value="1">{zh("channels.qos1")}</Select.Option>
                <Select.Option value="2">{zh("channels.qos2")}</Select.Option>
              </Select>
            </Form.Item>
            <Form.Item name="username" label={zh("channels.mqttUsername")}>
              <Input placeholder={zh("channels.blankToDisablePlaceholder")} />
            </Form.Item>
            <Form.Item name="password" label={zh("channels.mqttPassword")}>
              <Input.Password placeholder={zh("channels.blankToDisablePlaceholder")} />
            </Form.Item>
            <Form.Item
              name="subscribe_topic"
              label={zh("channels.subscribeTopic")}
              rules={[{ required: true }]}
            >
              <Input placeholder="server/+/up" />
            </Form.Item>
            <Form.Item
              name="publish_topic"
              label={zh("channels.publishTopic")}
              rules={[{ required: true }]}
            >
              <Input placeholder="client/{client_id}/down" />
            </Form.Item>
            <Form.Item
              name="tls_enabled"
              label={zh("channels.tlsEnabled")}
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
            <Form.Item name="tls_ca_certs" label={zh("channels.tlsCaCerts")}>
              <Input placeholder={zh("channels.tlsCaCertsPlaceholder")} />
            </Form.Item>
            <Form.Item name="tls_certfile" label={zh("channels.tlsCertfile")}>
              <Input placeholder={zh("channels.tlsCertfilePlaceholder")} />
            </Form.Item>
            <Form.Item name="tls_keyfile" label={zh("channels.tlsKeyfile")}>
              <Input placeholder={zh("channels.tlsKeyfilePlaceholder")} />
            </Form.Item>
          </>
        );
      case "voice":
        return (
          <>
            <Alert
              type="info"
              showIcon
              message={"请先注册 Twilio 账户并购买电话号码，然后在下方填写凭据。账户编号和认证令牌可在 Twilio 控制台首页找到，号码编号可在电话号码列表中查看。"}
              style={{ marginBottom: 32 }}
            />
            <Form.Item
              name="twilio_account_sid"
              label={"Twilio 账户编号"}
            >
              <Input placeholder="ACxxxxxxxx" />
            </Form.Item>
            <Form.Item
              name="twilio_auth_token"
              label={"Twilio 认证令牌"}
            >
              <Input.Password />
            </Form.Item>
            <Form.Item name="phone_number" label={"电话号码"}>
              <Input placeholder="+15551234567" />
            </Form.Item>
            <Form.Item
              name="phone_number_sid"
              label={"电话号码编号"}
              tooltip={"可在 Twilio 控制台的电话号码列表中找到。"}
            >
              <Input placeholder="PNxxxxxxxx" />
            </Form.Item>
            <Form.Item name="tts_provider" label={"语音合成提供方"}>
              <Input placeholder="google" />
            </Form.Item>
            <Form.Item name="tts_voice" label={"语音合成音色"}>
              <Input placeholder="en-US-Journey-D" />
            </Form.Item>
            <Form.Item name="stt_provider" label={"语音识别提供方"}>
              <Input placeholder="deepgram" />
            </Form.Item>
            <Form.Item name="language" label={"语言"}>
              <Input placeholder="en-US" />
            </Form.Item>
            <Form.Item
              name="welcome_greeting"
              label={"欢迎语"}
            >
              <Input.TextArea rows={2} />
            </Form.Item>
          </>
        );
      default:
        return null;
    }
  };

  const renderCustomExtraFields = (
    initialValues: Record<string, unknown> | undefined,
  ) => {
    if (!initialValues) return null;

    const baseFields = [
      "enabled",
      "bot_prefix",
      "filter_tool_messages",
      "filter_thinking",
      "isBuiltin",
    ];
    const extraKeys = Object.keys(initialValues).filter(
      (k) => !baseFields.includes(k),
    );

    if (extraKeys.length === 0) return null;

    return (
      <>
        <div style={{ marginBottom: 8, fontWeight: 500 }}>
          {zh("channels.customFields")}
        </div>
        {extraKeys.map((fieldKey) => {
          const value = initialValues[fieldKey];
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
          <span>
            {label
              ? `${label} ${"设置"}`
              : "频道设置"}
          </span>
          {activeKey && CHANNEL_DOC_URLS[activeKey] && (
            <Button
              type="text"
              size="small"
              icon={<LinkOutlined />}
              onClick={() => window.open(CHANNEL_DOC_URLS[activeKey], "_blank")}
              className={styles.dingtalkDocBtn}
            >
              {label} {zh("channels.guide")}
            </Button>
          )}
          {activeKey === "voice" && (
            <Button
              type="text"
              size="small"
              icon={<LinkOutlined />}
              onClick={() =>
                window.open(twilioConsoleUrl, "_blank", "noopener,noreferrer")
              }
              className={styles.dingtalkDocBtn}
            >
              {"打开 Twilio 控制台"}
            </Button>
          )}
        </div>
      }
      open={open}
      onClose={onClose}
      destroyOnClose
    >
      {activeKey && (
        <Form
          form={form}
          layout="vertical"
          initialValues={initialValues}
          onFinish={onSubmit}
        >
          <Form.Item
            name="enabled"
            label={"已启用"}
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>

          {activeKey !== "voice" && (
            <Form.Item name="bot_prefix" label={"机器人前缀"}>
              <Input placeholder={"@bot"} />
            </Form.Item>
          )}

          {activeKey !== "console" && (
            <>
              <Form.Item
                name="filter_tool_messages"
                label={"显示工具消息"}
                valuePropName="checked"
                tooltip={"向用户显示工具调用和输出消息（关闭则隐藏）"}
              >
                <Switch />
              </Form.Item>
              <Form.Item
                name="filter_thinking"
                label={"显示思考过程"}
                valuePropName="checked"
                tooltip={"向用户显示模型的思考/推理内容（关闭则隐藏）"}
              >
                <Switch />
              </Form.Item>
            </>
          )}

          {isBuiltin
            ? renderBuiltinExtraFields(activeKey)
            : renderCustomExtraFields(initialValues)}

          {CHANNELS_WITH_ACCESS_CONTROL.includes(activeKey) &&
            renderAccessControlFields()}

          <Form.Item>
            <div className={styles.formActions}>
              <Button onClick={onClose}>{"取消"}</Button>
              <Button type="primary" htmlType="submit" loading={saving}>
                {"保存"}
              </Button>
            </div>
          </Form.Item>
        </Form>
      )}
    </Drawer>
  );
}
