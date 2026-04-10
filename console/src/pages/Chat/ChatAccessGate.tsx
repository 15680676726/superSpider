import { ExclamationCircleOutlined, SettingOutlined } from "@ant-design/icons";
import { Button, Modal, Result, Spin } from "antd";

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

const noticeCopyMap: Record<
  Exclude<ChatNoticeVariant, "loading" | null>,
  {
    status: "info" | "warning";
    title: string;
    description: string;
  }
> = {
  binding: {
    status: "info",
    title: "正在准备聊天通道",
    description: "完成身份确认后即可继续使用，系统已在后台接续。",
  },
  blocked: {
    status: "warning",
    title: "当前无法进入聊天",
    description: "请前往身份中心完成绑定与权限检查，再返回查看。",
  },
};

export function ChatAccessGate({
  chatNoticeVariant,
  threadBootstrapError,
  requestedThreadId,
  showModelPrompt,
  onCloseModelPrompt,
  onOpenModelSettings,
  onOpenIdentityCenter,
  onReload,
}: ChatAccessGateProps) {
  const isLoading = chatNoticeVariant === "loading";
  const isGateActive = Boolean(chatNoticeVariant);
  let noticeCopy: (typeof noticeCopyMap)[keyof typeof noticeCopyMap] | null = null;
  const showThreadRecovery =
    Boolean(threadBootstrapError) &&
    typeof requestedThreadId === "string" &&
    requestedThreadId.length > 0;

  if (chatNoticeVariant && chatNoticeVariant !== "loading") {
    noticeCopy = noticeCopyMap[chatNoticeVariant];
  }

  return (
    <>
      {isGateActive ? (
        <div className={styles.noticeWrap}>
          {isLoading ? (
            <div className={styles.centerSpinner}>
              <Spin size="large" />
              <div>正在进入聊天，请稍候</div>
            </div>
          ) : (
            <div className={styles.centerResult}>
              <Result
                status={noticeCopy?.status}
                title={showThreadRecovery ? "这段聊天暂时打不开" : noticeCopy?.title}
                subTitle={
                  showThreadRecovery
                    ? "先重新加载这段聊天；如果还是不行，再回到建档入口。"
                    : noticeCopy?.description
                }
                extra={
                  showThreadRecovery
                    ? [
                        <Button key="reload" type="primary" onClick={onReload}>
                          重新加载
                        </Button>,
                        <Button key="identity" onClick={onOpenIdentityCenter}>
                          前往身份中心
                        </Button>,
                      ]
                    : (
                      <Button type="primary" onClick={onOpenIdentityCenter}>
                        前往身份中心
                      </Button>
                    )
                }
              />
            </div>
          )}
        </div>
      ) : null}

      <Modal open={showModelPrompt} closable={false} footer={null} width={480} centered>
        <Result
          icon={<ExclamationCircleOutlined style={{ color: "#7170FF" }} />}
          title="请先完成模型配置"
          subTitle="确认模型设置后才能继续使用聊天。"
          extra={[
            <Button key="skip" onClick={onCloseModelPrompt}>
              稍后再说
            </Button>,
            <Button
              key="go"
              type="primary"
              icon={<SettingOutlined />}
              onClick={onOpenModelSettings}
            >
              去模型设置
            </Button>,
          ]}
        />
      </Modal>
    </>
  );
}
