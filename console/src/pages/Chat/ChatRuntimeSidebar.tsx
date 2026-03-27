import {
  InfoCircleOutlined,
  LoadingOutlined,
  WarningOutlined,
  AppstoreOutlined,
  CheckCircleOutlined,
} from "@ant-design/icons";
import { Button, Tag, Tooltip } from "antd";

import type {
  RuntimeHealthNotice,
  RuntimeWaitState,
} from "./runtimeDiagnostics";
import styles from "./index.module.less";

export function ChatRuntimeSidebar({
  approvalButtonLabel,
  bindingLabel,
  onOpenGovernanceApprovals,
  runtimeFallbackLabel,
  runtimeHealthNotice,
  runtimeModelHint,
  runtimeModelLabel,
  runtimeWaitDescription,
  runtimeWaitSeconds,
  runtimeWaitState,
}: {
  approvalButtonLabel: string;
  bindingLabel: string | null;
  onOpenGovernanceApprovals: () => void;
  runtimeFallbackLabel: string | null;
  runtimeHealthNotice: RuntimeHealthNotice | null;
  runtimeModelHint: string;
  runtimeModelLabel: string;
  runtimeWaitDescription: string | null;
  runtimeWaitSeconds: number;
  runtimeWaitState: RuntimeWaitState | null;
}) {
  const hasPendingApprovals = approvalButtonLabel !== "审批";

  return (
    <div className={styles.chatTopBar}>
      {/* 左侧：绑定信息 */}
      <div className={styles.chatTopBarLeft}>
        <div className={styles.chatTopBarBrand}>
          <AppstoreOutlined className={styles.chatTopBarBrandIcon} />
          <span className={styles.chatTopBarBrandLabel}>主脑对话</span>
        </div>
        {bindingLabel ? (
          <div className={styles.chatTopBarBinding}>
            <span className={styles.chatTopBarBindingDot} />
            <span className={styles.chatTopBarBindingText}>{bindingLabel}</span>
          </div>
        ) : null}
      </div>

      {/* 中间：运行状态 */}
      <div className={styles.chatTopBarCenter}>
        <Tooltip title={runtimeModelHint}>
          <div className={styles.chatTopBarModel}>
            <InfoCircleOutlined className={styles.chatTopBarModelIcon} />
            <span className={styles.chatTopBarModelLabel}>
              {runtimeModelLabel}
            </span>
            {runtimeFallbackLabel ? (
              <Tag bordered={false} className={styles.chatTopBarFallbackTag}>
                {runtimeFallbackLabel}
              </Tag>
            ) : null}
          </div>
        </Tooltip>
      </div>

      {/* 右侧：状态 + 审批 */}
      <div className={styles.chatTopBarRight}>
        {runtimeWaitState ? (
          <Tooltip title={runtimeWaitDescription || undefined}>
            <div className={`${styles.chatTopBarStatus} ${styles.chatTopBarStatusWaiting}`}>
              <LoadingOutlined spin />
              <span>{`等待响应 ${runtimeWaitSeconds}s`}</span>
            </div>
          </Tooltip>
        ) : runtimeHealthNotice ? (
          <Tooltip title={runtimeHealthNotice.description}>
            <div
              className={`${styles.chatTopBarStatus} ${
                runtimeHealthNotice.type === "error"
                  ? styles.chatTopBarStatusError
                  : styles.chatTopBarStatusWarning
              }`}
            >
              <WarningOutlined />
              <span>{runtimeHealthNotice.title}</span>
            </div>
          </Tooltip>
        ) : (
          <div className={`${styles.chatTopBarStatus} ${styles.chatTopBarStatusIdle}`}>
            <CheckCircleOutlined />
            <span>就绪</span>
          </div>
        )}

        {hasPendingApprovals ? (
          <Button
            size="small"
            className={styles.chatTopBarApprovalBtn}
            onClick={onOpenGovernanceApprovals}
          >
            {approvalButtonLabel}
          </Button>
        ) : null}
      </div>
    </div>
  );
}
