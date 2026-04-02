import {
  AppstoreOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  InfoCircleOutlined,
  LoadingOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { Button, Tag, Tooltip } from "antd";

import type {
  RuntimeHealthNotice,
  RuntimeLifecycleState,
  RuntimeWaitState,
} from "./runtimeDiagnostics";
import {
  formatRuntimeIntentShellSidebarHint,
  type RuntimeIntentShellSurface,
} from "./runtimeSidecarEvents";
import styles from "./index.module.less";

const APPROVAL_DEFAULT_LABEL = "\u5ba1\u6279";
const READY_STATUS_TEXT = "\u5c31\u7eea";
const TOP_BAR_TITLE = "\u4e3b\u8111\u5bf9\u8bdd";
const WAITING_STATUS_PREFIX = "\u7b49\u5f85\u54cd\u5e94";

type ChatRuntimeSidebarProps = {
  approvalButtonLabel: string;
  bindingLabel: string | null;
  focusHint?: string | null;
  focusLabel?: string | null;
  onOpenGovernanceApprovals: () => void;
  runtimeFallbackLabel: string | null;
  runtimeHealthNotice: RuntimeHealthNotice | null;
  runtimeLifecycleState?: RuntimeLifecycleState | null;
  runtimeModelHint: string;
  runtimeModelLabel: string;
  runtimeIntentShell?: RuntimeIntentShellSurface | null;
  runtimeWaitDescription: string | null;
  runtimeWaitSeconds: number;
  runtimeWaitState: RuntimeWaitState | null;
  threadKindHint?: string | null;
  threadKindLabel?: string | null;
  writebackHint?: string | null;
  writebackLabel?: string | null;
};

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
  runtimeIntentShell,
  runtimeWaitDescription,
  runtimeWaitSeconds,
  runtimeWaitState,
  threadKindHint,
  threadKindLabel,
  writebackHint,
  writebackLabel,
}: ChatRuntimeSidebarProps) {
  const renderMetaChip = (
    label: string | null | undefined,
    hint?: string | null,
  ) => {
    if (!label) {
      return null;
    }
    return (
      <div className={styles.topBarChip}>
        <span className={styles.topBarChipDot} />
        <span className={styles.topBarChipText} title={hint || label}>
          {label}
        </span>
      </div>
    );
  };

  const hasPendingApprovals = approvalButtonLabel !== APPROVAL_DEFAULT_LABEL;
  const shellModeLabel = runtimeIntentShell
    ? `Shell: ${runtimeIntentShell.label}`
    : null;
  const shellModeHint = formatRuntimeIntentShellSidebarHint(
    runtimeIntentShell ?? null,
  );

  const renderStatus = () => {
    if (runtimeWaitState) {
      return (
        <Tooltip title={runtimeWaitDescription || undefined}>
          <div className={`${styles.topBarStatus} ${styles.topBarStatusBusy}`}>
            <LoadingOutlined spin />
            <span>{`${WAITING_STATUS_PREFIX} ${runtimeWaitSeconds}s`}</span>
          </div>
        </Tooltip>
      );
    }

    if (runtimeLifecycleState) {
      const tone = runtimeLifecycleState.tone;
      const className =
        tone === "error"
          ? styles.topBarStatusError
          : tone === "warning"
            ? styles.topBarStatusWarn
            : tone === "success"
              ? styles.topBarStatusOk
              : styles.topBarStatusBusy;
      const icon =
        tone === "error" ? (
          <CloseCircleOutlined />
        ) : tone === "warning" ? (
          <WarningOutlined />
        ) : tone === "success" ? (
          <CheckCircleOutlined />
        ) : (
          <LoadingOutlined spin />
        );
      return (
        <Tooltip title={runtimeLifecycleState.description || undefined}>
          <div className={`${styles.topBarStatus} ${className}`}>
            {icon}
            <span>{runtimeLifecycleState.title}</span>
          </div>
        </Tooltip>
      );
    }

    if (runtimeHealthNotice) {
      return (
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
      );
    }

    return (
      <div className={`${styles.topBarStatus} ${styles.topBarStatusOk}`}>
        <CheckCircleOutlined />
        <span>{READY_STATUS_TEXT}</span>
      </div>
    );
  };

  return (
    <div className={styles.topBar}>
      <div className={styles.topBarLeft}>
        <div className={styles.topBarLogo}>
          <AppstoreOutlined className={styles.topBarLogoIcon} />
          <span className={styles.topBarLogoText}>{TOP_BAR_TITLE}</span>
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
        {renderStatus()}

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
