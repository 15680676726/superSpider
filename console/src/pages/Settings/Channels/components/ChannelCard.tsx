import { Card, Tooltip } from "@/ui";
import { getChannelLabel, type ChannelKey } from "./constants";
import styles from "../index.module.less";

interface ChannelCardProps {
  channelKey: ChannelKey;
  config: Record<string, unknown>;
  isHover: boolean;
  onClick: () => void;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}

export function ChannelCard({
  channelKey,
  config,
  isHover,
  onClick,
  onMouseEnter,
  onMouseLeave,
}: ChannelCardProps) {  const enabled = Boolean(config.enabled);
  const isBuiltin = Boolean(config.isBuiltin);
  const label = getChannelLabel(channelKey);
  const getConfigString = (key: string) =>
    typeof config[key] === "string" ? config[key] : "";
  const phoneNumber = getConfigString("phone_number");
  const botPrefix = getConfigString("bot_prefix");

  const getCardClassNames = () => {
    if (isHover) return `${styles.channelCard} ${styles.hover}`;
    if (enabled) return `${styles.channelCard} ${styles.enabled}`;
    return `${styles.channelCard} ${styles.normal}`;
  };

  return (
    <Card
      hoverable
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      className={getCardClassNames()}
      bodyStyle={{ padding: 20 }}
    >
      <div className={styles.cardHeader}>
        <Tooltip title={label} placement="top">
          <div className={styles.cardTitleRow}>
            <div className={styles.cardTitle}>{label}</div>
            {isBuiltin ? (
              <span className={styles.builtinTag}>{"内置"}</span>
            ) : (
              <span className={styles.customTag}>{"自定义"}</span>
            )}
          </div>
        </Tooltip>

        <div className={styles.statusContainer}>
          <div
            className={`${styles.statusDot} ${
              enabled ? styles.enabled : styles.disabled
            }`}
          />
          <div>{enabled ? "已启用" : "已禁用"}</div>
        </div>
      </div>

      <div className={styles.cardDescription}>
        {channelKey === "voice" ? (
          <>
            {"电话号码"}: {phoneNumber || "未设置"}
          </>
        ) : (
          <>
            {"机器人前缀"}: {botPrefix || "未设置"}
          </>
        )}
      </div>

      <div className={styles.cardHint}>{"点击卡片进行编辑"}</div>
    </Card>
  );
}
