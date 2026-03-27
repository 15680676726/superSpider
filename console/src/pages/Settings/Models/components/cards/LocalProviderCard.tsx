import { useState } from "react";
import { Card, Button, Tag } from "@/ui";
import { AppstoreOutlined } from "@ant-design/icons";
import type { ProviderInfo } from "../../../../../api/types";
import { ModelManageModal } from "../modals/ModelManageModal";
import styles from "../../index.module.less";

interface LocalProviderCardProps {
  provider: ProviderInfo;
  onSaved: () => void;
  isHover: boolean;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}

export function LocalProviderCard({
  provider,
  onSaved,
  isHover,
  onMouseEnter,
  onMouseLeave,
}: LocalProviderCardProps) {
  const [modelManageOpen, setModelManageOpen] = useState(false);

  const totalCount = provider.models.length + provider.extra_models.length;
  const statusReady = totalCount > 0;
  const statusLabel = statusReady
    ? "可用"
    : "不可用";

  return (
    <Card
      hoverable
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      className={`${styles.providerCard} ${
        statusReady ? styles.enabledCard : ""
      } ${isHover ? styles.hover : styles.normal}`}
    >
      <div style={{ marginBottom: 32 }}>
        <div className={styles.cardHeader}>
          <span className={styles.cardName}>
            {provider.name}
            <Tag color="purple" style={{ marginLeft: 8, fontSize: 11 }}>
              {"本地"}
            </Tag>
          </span>
          <div className={styles.statusContainer}>
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                backgroundColor: statusReady ? "#52c41a" : "#d9d9d9",
                boxShadow: statusReady
                  ? "0 0 0 2px rgba(82, 196, 26, 0.2)"
                  : "none",
              }}
            />
            <span
              className={`${styles.statusText} ${
                statusReady ? styles.enabled : styles.disabled
              }`}
            >
              {statusLabel}
            </span>
          </div>
        </div>

        <div className={styles.cardInfo}>
          <div className={styles.infoRow}>
            <span className={styles.infoLabel}>{"类型"}:</span>
            <span className={styles.infoValue}>
              {"嵌入式（进程内）"}
            </span>
          </div>
          <div className={styles.infoRow}>
            <span className={styles.infoLabel}>{"模型"}:</span>
            <span className={styles.infoValue}>
              {totalCount > 0
                ? `${totalCount} 个模型`
                : "请先下载模型"}
            </span>
          </div>
        </div>
      </div>

      <div className={styles.cardActions}>
        <Button
          type="link"
          size="small"
          onClick={(e) => {
            e.stopPropagation();
            setModelManageOpen(true);
          }}
          className={styles.configBtn}
          icon={<AppstoreOutlined />}
        >
          {"模型"}
        </Button>
      </div>

      <ModelManageModal
        provider={provider}
        open={modelManageOpen}
        onClose={() => setModelManageOpen(false)}
        onSaved={onSaved}
      />
    </Card>
  );
}
