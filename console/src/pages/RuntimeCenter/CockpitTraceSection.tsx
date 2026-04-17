import { Empty } from "antd";

import { normalizeDisplayChinese } from "../../text";
import { formatTimestamp } from "./viewHelpers";
import styles from "./index.module.less";

export interface CockpitTraceLine {
  timestamp: string;
  level: "info" | "warn" | "error";
  message: string;
  route?: string | null;
}

type CockpitTraceSectionProps = {
  trace: CockpitTraceLine[];
};

function levelLabel(level: CockpitTraceLine["level"]): string {
  switch (level) {
    case "warn":
      return "WARN";
    case "error":
      return "ERROR";
    default:
      return "INFO";
  }
}

export default function CockpitTraceSection({
  trace,
}: CockpitTraceSectionProps) {
  const items = [...trace].sort((left, right) =>
    String(left.timestamp).localeCompare(String(right.timestamp)),
  );

  if (items.length === 0) {
    return (
      <div className={styles.cockpitEmptyWrap}>
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="今天还没有新的追溯记录。"
        />
      </div>
    );
  }

  return (
    <div className={styles.cockpitTraceList}>
      {items.map((item) => (
        <div
          key={`${item.timestamp}:${item.message}:${item.route ?? ""}`}
          className={styles.cockpitTraceItem}
          data-testid="cockpit-trace-line"
        >
          <div className={styles.cockpitTraceTime}>
            {formatTimestamp(item.timestamp)}
          </div>
          <div className={styles.cockpitTraceBody}>
            <div className={styles.cockpitTraceMessageRow}>
              <span
                className={`${styles.cockpitTraceLevel} ${
                  item.level === "error"
                    ? styles.cockpitTraceLevelError
                    : item.level === "warn"
                      ? styles.cockpitTraceLevelWarn
                      : styles.cockpitTraceLevelInfo
                }`}
              >
                {levelLabel(item.level)}
              </span>
              <span className={styles.cockpitTraceMessage}>
                {normalizeDisplayChinese(item.message)}
              </span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
