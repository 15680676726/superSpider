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
  RuntimeLifecycleState,
  RuntimeWaitState,
} from "./runtimeDiagnostics";
import styles from "./index.module.less";

export function ChatRuntimeSidebar({
  approvalButtonLabel,
  bindingLabel,
  focusHint,
  focusLabel,
  onOpenGovernanceApprovals,
  runtimeFallbackLabel,
  runtimeHealthNotice,
  runtimeLifecycleState,
  runtimeModelHint,
  runtimeModelLabel,
  runtimeWaitDescription,
  runtimeWaitSeconds,
  runtimeWaitState,
  threadKindHint,
  threadKindLabel,
  writebackHint,
  writebackLabel,
}: {
  approvalButtonLabel: string;
  bindingLabel: string | null;
  focusHint?: string | null;
  focusLabel?: string | null;
  onOpenGovernanceApprovals: () => void;
  runtimeFallbackLabel: string | null;
  runtimeHealthNotice: RuntimeHealthNotice | null;
  runtimeLifecycleState: RuntimeLifecycleState | null;
  runtimeModelHint: string;
  runtimeModelLabel: string;
  runtimeWaitDescription: string | null;
  runtimeWaitSeconds: number;
  runtimeWaitState: RuntimeWaitState | null;
  threadKindHint?: string | null;
  threadKindLabel?: string | null;
  writebackHint?: string | null;
  writebackLabel?: string | null;
}) {
  const renderMetaChip = (
    label: string | null | undefined,
    hint?: string | null,
  ) => {
    if (!label) return null;
    return (
      <div className={styles.topBarChip}>
        <span className={styles.topBarChipDot} />
        <span className={styles.topBarChipText} title={hint || label}>
          {label}
        </span>
      </div>
    );
  };
  const hasPendingApprovals = approvalButtonLabel !== "审批";

  return (
    <div className={styles.topBar}>
      {/* 左侧：绑定信息 */}
      <div className={styles.topBarLeft}>
        <div className={styles.topBarLogo}>
          <AppstoreOutlined className={styles.topBarLogoIcon} />
          <span className={styles.topBarLogoText}>主脑对话</span>
        </div>
        {renderMetaChip(bindingLabel, bindingLabel)}
        {renderMetaChip(threadKindLabel, threadKindHint)}
        {renderMetaChip(focusLabel, focusHint)}
        {renderMetaChip(writebackLabel, writebackHint)}
      </div>

      {/* 中间：运行状态 */}
      <div className={styles.topBarCenter}>
        <Tooltip title={runtimeModelHint}>
          <div className={styles.topBarModel}>
            <InfoCircleOutlined />
            <span className={styles.topBarModelText} title={runtimeModelLabel}>
              {runtimeModelLabel}
            </span>
            {runtimeFallbackLabel ? (
              <Tag bordered={false} className={styles.topBarModelBadge}>
                {runtimeFallbackLabel}
              </Tag>
            ) : null}
          </div>
        </Tooltip>
      </div>

      {/* 右侧：状态 + 审批 */}
      <div className={styles.topBarRight}>
        {runtimeWaitState ? (
          <Tooltip title={runtimeWaitDescription || undefined}>
            <div className={`${styles.topBarStatus} ${styles.topBarStatusBusy}`}>
              <LoadingOutlined spin />
              <span>{`等待响应 ${runtimeWaitSeconds}s`}</span>
            </div>
          </Tooltip>
        ) : runtimeLifecycleState ? (
          <Tooltip title={runtimeLifecycleState.description || undefined}>
            <div
              className={`${styles.topBarStatus} ${
                runtimeLifecycleState.tone === "busy"
                  ? styles.topBarStatusBusy
                  : runtimeLifecycleState.tone === "success"
                    ? styles.topBarStatusOk
                    : runtimeLifecycleState.tone === "error"
                      ? styles.topBarStatusError
                      : styles.topBarStatusWarn
              }`}
            >
              {runtimeLifecycleState.tone === "busy" ? (
                <LoadingOutlined spin />
              ) : runtimeLifecycleState.tone === "success" ? (
                <CheckCircleOutlined />
              ) : (
                <WarningOutlined />
              )}
              <span>{runtimeLifecycleState.title}</span>
            </div>
          </Tooltip>
        ) : runtimeHealthNotice ? (
          <Tooltip title={runtimeHealthNotice.description}>
            <div
              className={`${styles.topBarStatus} ${
                runtimeHealthNotice.type === "error"
                  ? styles.topBarStatusError
                  : styles.topBarStatusWarn
              }`}
            >
              <WarningOutlined />
              <span>{runtimeHealthNotice.title}</span>
            </div>
          </Tooltip>
        ) : (
          <div className={`${styles.topBarStatus} ${styles.topBarStatusOk}`}>
            <CheckCircleOutlined />
            <span>就绪</span>
          </div>
        )}

        {hasPendingApprovals ? (
          <Button
            size="small"
            className={styles.topBarApprovalBtn}
            onClick={onOpenGovernanceApprovals}
          >
            {approvalButtonLabel}
          </Button>
        ) : null}
      </div>
    </div>
  );
}
