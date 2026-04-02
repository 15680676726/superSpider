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
  focusHint,
  focusLabel,
  onOpenGovernanceApprovals,
  runtimeFallbackLabel,
  runtimeHealthNotice,
  runtimeModelHint,
  runtimeModelLabel,
  runtimeWaitDescription,
  runtimeWaitSeconds,
  runtimeWaitState,
  shellModeHint,
  shellModeLabel,
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
  runtimeModelHint: string;
  runtimeModelLabel: string;
  runtimeWaitDescription: string | null;
  runtimeWaitSeconds: number;
  runtimeWaitState: RuntimeWaitState | null;
  shellModeHint?: string | null;
  shellModeLabel?: string | null;
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
      <div className={styles.topBarLeft}>
        <div className={styles.topBarLogo}>
          <AppstoreOutlined className={styles.topBarLogoIcon} />
          <span className={styles.topBarLogoText}>主脑对话</span>
        </div>
        {renderMetaChip(bindingLabel, bindingLabel)}
        {renderMetaChip(shellModeLabel, shellModeHint)}
        {renderMetaChip(threadKindLabel, threadKindHint)}
        {renderMetaChip(focusLabel, focusHint)}
        {renderMetaChip(writebackLabel, writebackHint)}
      </div>

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

      <div className={styles.topBarRight}>
        {runtimeWaitState ? (
          <Tooltip title={runtimeWaitDescription || undefined}>
            <div className={`${styles.topBarStatus} ${styles.topBarStatusBusy}`}>
              <LoadingOutlined spin />
              <span>{`等待响应 ${runtimeWaitSeconds}s`}</span>
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
