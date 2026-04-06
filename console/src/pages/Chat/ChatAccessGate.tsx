import { ExclamationCircleOutlined, SettingOutlined } from "@ant-design/icons";
import { Alert, Button, Modal, Result, Space, Spin } from "antd";

import type { ChatNoticeVariant } from "./noticeState";
import styles from "./index.module.less";

type ChatAccessGateProps = {
  chatNoticeVariant: ChatNoticeVariant;
  threadBootstrapError: string | null;
  autoBindingPending: boolean;
  requestedThreadId: string | null;
  industryTeamsError: string | null;
  hasSuggestedTeams: boolean;
  effectiveThreadPending: boolean;
  showModelPrompt: boolean;
  onCloseModelPrompt: () => void;
  onOpenModelSettings: () => void;
  onOpenIdentityCenter: () => void;
  onReload: () => void;
};

function resolveBindingMessage(params: {
  autoBindingPending: boolean;
  requestedThreadId: string | null;
  threadBootstrapError: string | null;
}): { title: string; description: string } {
  const { autoBindingPending, requestedThreadId, threadBootstrapError } = params;
  if (threadBootstrapError) {
    return {
      title: "当前对话还没准备好",
      description: threadBootstrapError,
    };
  }
  if (autoBindingPending && !requestedThreadId) {
    return {
      title: "正在接入伙伴主场",
      description: "正在把当前对话接入伙伴的正式协作通道。",
    };
  }
  return {
    title: "正在准备当前对话",
    description: "正在校准当前对话对应的协作上下文。",
  };
}

export function ChatAccessGate({
  chatNoticeVariant,
  threadBootstrapError,
  autoBindingPending,
  requestedThreadId,
  industryTeamsError,
  hasSuggestedTeams,
  effectiveThreadPending,
  showModelPrompt,
  onCloseModelPrompt,
  onOpenModelSettings,
  onOpenIdentityCenter,
  onReload,
}: ChatAccessGateProps) {
  const bindingCopy = resolveBindingMessage({
    autoBindingPending,
    requestedThreadId,
    threadBootstrapError,
  });

  return (
    <>
      {chatNoticeVariant ? (
        <div className={styles.noticeWrap}>
          {chatNoticeVariant === "loading" ? (
            <div className={styles.centerSpinner}>
              <Spin size="large" />
              <div>正在进入伙伴对话...</div>
            </div>
          ) : chatNoticeVariant === "binding" ? (
            <Alert
              type={threadBootstrapError ? "warning" : "info"}
              showIcon
              className={styles.noticeAlert}
              message={bindingCopy.title}
              description={
                <Space size={4} wrap>
                  <span>{bindingCopy.description}</span>
                  <Button size="small" type="link" onClick={onOpenIdentityCenter}>
                    打开身份中心
                  </Button>
                </Space>
              }
            />
          ) : (
            <div className={styles.centerResult}>
              <Result
                status={
                  effectiveThreadPending
                    ? "info"
                    : requestedThreadId
                      ? "info"
                      : industryTeamsError
                        ? "warning"
                        : "403"
                }
                title={
                  effectiveThreadPending || requestedThreadId
                    ? bindingCopy.title
                    : industryTeamsError
                      ? "身份列表加载失败"
                      : "请先完成伙伴建档"
                }
                subTitle={
                  effectiveThreadPending || requestedThreadId
                    ? bindingCopy.description
                    : industryTeamsError
                      ? `身份列表或主脑投影不可用。${industryTeamsError}`
                      : hasSuggestedTeams
                        ? "请先从伙伴建档进入聊天，这样当前对话才会绑定到你的伙伴主场。"
                        : "当前还没有可用的伙伴主体。请先完成伙伴建档，再进入聊天。"
                }
                extra={
                  <Space wrap>
                    <Button type="primary" onClick={onOpenIdentityCenter}>
                      打开身份中心
                    </Button>
                    {industryTeamsError ? <Button onClick={onReload}>刷新页面</Button> : null}
                  </Space>
                }
              />
            </div>
          )}
        </div>
      ) : null}

      <Modal open={showModelPrompt} closable={false} footer={null} width={480} centered>
        <Result
          icon={<ExclamationCircleOutlined style={{ color: "#C9A84C" }} />}
          title="需要配置对话模型"
          subTitle="聊天功能需要先配置对话模型才能运行。未配置模型时，对话消息无法发送到后端处理。"
          extra={[
            <Button key="skip" onClick={onCloseModelPrompt}>
              暂不配置
            </Button>,
            <Button
              key="go"
              type="primary"
              icon={<SettingOutlined />}
              onClick={onOpenModelSettings}
            >
              前往配置
            </Button>,
          ]}
        />
      </Modal>
    </>
  );
}
