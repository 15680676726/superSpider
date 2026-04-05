import { ExclamationCircleOutlined, SettingOutlined } from "@ant-design/icons";
import { Alert, Button, Modal, Result, Space, Spin } from "antd";

import type { IndustryInstanceSummary } from "../../api/modules/industry";
import type { ChatNoticeVariant } from "./noticeState";
import styles from "./index.module.less";

type ChatAccessGateProps = {
  chatNoticeVariant: ChatNoticeVariant;
  threadBootstrapError: string | null;
  autoBindingPending: boolean;
  requestedThreadId: string | null;
  industryTeamsError: string | null;
  hasSuggestedTeams: boolean;
  executionCoreSuggestions: IndustryInstanceSummary[];
  effectiveThreadPending: boolean;
  showModelPrompt: boolean;
  onCloseModelPrompt: () => void;
  onOpenModelSettings: () => void;
  onOpenIdentityCenter: () => void;
  onOpenWorkbench: () => void;
  onReload: () => void;
  onOpenSuggestedIndustryChat: (instance: IndustryInstanceSummary) => Promise<boolean>;
};

export function ChatAccessGate({
  chatNoticeVariant,
  threadBootstrapError,
  autoBindingPending,
  requestedThreadId,
  industryTeamsError,
  hasSuggestedTeams,
  executionCoreSuggestions,
  effectiveThreadPending,
  showModelPrompt,
  onCloseModelPrompt,
  onOpenModelSettings,
  onOpenIdentityCenter,
  onOpenWorkbench,
  onReload,
  onOpenSuggestedIndustryChat,
}: ChatAccessGateProps) {
  return (
    <>
      {chatNoticeVariant ? (
        <div className={styles.noticeWrap}>
          {chatNoticeVariant === "loading" ? (
            <div className={styles.centerSpinner}>
              <Spin size="large" tip="正在加载对话线程…" />
            </div>
          ) : chatNoticeVariant === "binding" ? (
            <Alert
              type={threadBootstrapError ? "warning" : "info"}
              showIcon
              className={styles.noticeAlert}
              message={
                autoBindingPending && !requestedThreadId
                  ? "正在绑定主脑控制线程"
                  : "正在解析聊天线程"
              }
              description={
                <Space size={4} wrap>
                  <span>
                    {threadBootstrapError ||
                      (autoBindingPending && !requestedThreadId
                        ? "正在将对话绑定至可用的主脑控制线程。"
                        : "正在解析当前线程的运行主体和绑定上下文。")}
                  </span>
                  <Button size="small" type="link" onClick={onOpenIdentityCenter}>
                    打开身份中心
                  </Button>
                  <Button size="small" type="link" onClick={onOpenWorkbench}>
                    智能体工作台
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
                        : hasSuggestedTeams
                          ? "warning"
                          : "403"
                }
                title={
                  effectiveThreadPending
                    ? autoBindingPending && !requestedThreadId
                      ? "正在绑定主脑控制线程"
                      : "正在解析聊天线程"
                    : requestedThreadId
                      ? "正在绑定主脑控制线程"
                    : industryTeamsError
                      ? "身份列表加载失败"
                      : hasSuggestedTeams
                        ? "请先绑定主脑线程"
                        : "请先完成伙伴建档"
                }
                subTitle={
                  effectiveThreadPending
                    ? autoBindingPending && !requestedThreadId
                      ? "正在将对话绑定至可用的主脑控制线程。"
                      : "正在解析当前聊天线程的运行主体和绑定上下文。"
                    : requestedThreadId
                      ? threadBootstrapError || "正在将对话绑定至可用的主脑控制线程。"
                    : industryTeamsError
                      ? `身份列表或主脑投影不可用。${industryTeamsError}`
                      : executionCoreSuggestions.length > 0
                        ? "请从身份中心或智能体工作台进入聊天，这样线程才会绑定到真实的执行主体。"
                        : "暂无可用的伙伴身份主体。请先完成伙伴建档，再进入聊天。"
                }
                extra={
                  <Space wrap>
                    <Button type="primary" onClick={onOpenIdentityCenter}>
                      打开身份中心
                    </Button>
                    <Button onClick={onOpenWorkbench}>智能体工作台</Button>
                    {industryTeamsError ? <Button onClick={onReload}>刷新页面</Button> : null}
                    {executionCoreSuggestions.map((instance) => (
                      <Button
                        key={instance.instance_id}
                        onClick={() => void onOpenSuggestedIndustryChat(instance)}
                      >
                        {`打开 ${instance.label} 主脑`}
                      </Button>
                    ))}
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
