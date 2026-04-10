import { Button } from "antd";

import styles from "./index.module.less";
import type { RuntimeIntentShellSurface } from "./runtimeSidecarEvents";

export function ChatIntentShellCard({
  shell,
  onViewDetails,
}: {
  shell: RuntimeIntentShellSurface | null;
  onViewDetails?: (() => void) | null;
}) {
  if (!shell) {
    return null;
  }

  return (
    <div className={`${styles.humanAssistStrip} ${styles.humanAssistStripIdle}`}>
      <div className={styles.humanAssistStripMain}>
        <div className={styles.humanAssistStripBadge}>{shell.label}</div>
        <div className={styles.humanAssistStripBody}>
          <div className={styles.humanAssistStripTitleRow}>
            <span
              className={styles.humanAssistStripTitle}
              title={shell.summary ?? shell.label}
            >
              {shell.summary ?? shell.label}
            </span>
          </div>
          {shell.hint ? (
            <div className={styles.humanAssistStripSummary} title={shell.hint}>
              {shell.hint}
            </div>
          ) : null}
        </div>
      </div>
      {shell.metaSummary ? (
        <div className={styles.humanAssistStripActions}>
          <span
            className={styles.humanAssistStripSummary}
            title={shell.metaSummary}
          >
            {shell.metaSummary}
          </span>
          {onViewDetails ? (
            <Button size="small" type="link" onClick={onViewDetails}>
              查看详情
            </Button>
          ) : null}
        </div>
      ) : onViewDetails ? (
        <div className={styles.humanAssistStripActions}>
          <Button size="small" type="link" onClick={onViewDetails}>
            查看详情
          </Button>
        </div>
      ) : null}
    </div>
  );
}
