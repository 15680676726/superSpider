import styles from "./index.module.less";
import type { RuntimeIntentShellSurface } from "./runtimeSidecarEvents";

export function ChatIntentShellCard({
  shell,
}: {
  shell: RuntimeIntentShellSurface | null;
}) {
  if (!shell) {
    return null;
  }

  const metaParts = [
    shell.triggerSource ? `trigger=${shell.triggerSource}` : "",
    shell.matchedText ? `match=${shell.matchedText}` : "",
    typeof shell.confidence === "number"
      ? `confidence=${shell.confidence.toFixed(2)}`
      : "",
  ].filter(Boolean);

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
      {metaParts.length > 0 ? (
        <div className={styles.humanAssistStripActions}>
          <span className={styles.humanAssistStripSummary} title={metaParts.join(" | ")}>
            {metaParts.join(" | ")}
          </span>
        </div>
      ) : null}
    </div>
  );
}
