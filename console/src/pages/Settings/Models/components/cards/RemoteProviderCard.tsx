import { useState } from "react";
import { Card, Button, Tag, Modal, message } from "@/ui";
import {
  EditOutlined,
  DeleteOutlined,
  AppstoreOutlined,
} from "@ant-design/icons";
import type { ProviderInfo, ActiveModelsInfo } from "../../../../../api/types";
import { ProviderConfigModal } from "../modals/ProviderConfigModal";
import { ModelManageModal } from "../modals/ModelManageModal";
import api from "../../../../../api";
import styles from "../../index.module.less";

interface RemoteProviderCardProps {
  provider: ProviderInfo;
  activeModels: ActiveModelsInfo | null;
  onSaved: () => void;
  isHover: boolean;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}

export function RemoteProviderCard({
  provider,
  activeModels,
  onSaved,
  isHover,
  onMouseEnter,
  onMouseLeave,
}: RemoteProviderCardProps) {
  const [modalOpen, setModalOpen] = useState(false);
  const [modelManageOpen, setModelManageOpen] = useState(false);

  const handleDeleteProvider = (e: React.MouseEvent) => {
    e.stopPropagation();
    Modal.confirm({
      title: "删除提供方",
      content: `确定删除自定义提供方“${provider.name}”及其所有模型吗？此操作不可撤销。`,
      okText: "删除",
      okButtonProps: { danger: true },
      cancelText: "取消",
      onOk: async () => {
        try {
          await api.deleteCustomProvider(provider.id);
          message.success(`提供方“${provider.name}”已删除`);
          onSaved();
        } catch (error) {
          const errMsg =
            error instanceof Error
              ? error.message
              : "删除提供方失败";
          message.error(errMsg);
        }
      },
    });
  };

  const totalCount = provider.models.length + provider.extra_models.length;

  const isConfigured =
    provider.is_local ||
    (provider.is_custom && provider.base_url) ||
    provider.api_key;
  const hasModels = totalCount > 0;
  const isAvailable = isConfigured && hasModels;

  const providerTag = provider.is_custom ? (
    <Tag color="blue" style={{ marginLeft: 8, fontSize: 11 }}>
      {"自定义"}
    </Tag>
  ) : (
    <Tag color="green" style={{ marginLeft: 8, fontSize: 11 }}>
      {"内置"}
    </Tag>
  );

  const statusLabel = isAvailable
    ? "可用（有模型）"
    : isConfigured
    ? "未就绪（无模型）"
    : "未就绪（未配置）";
  const statusType = isAvailable
    ? "enabled"
    : isConfigured
    ? "partial"
    : "disabled";
  const statusDotColor = isAvailable
    ? "#52c41a"
    : isConfigured
    ? "#faad14"
    : "#d9d9d9";
  const statusDotShadow = isAvailable
    ? "0 0 0 2px rgba(82, 196, 26, 0.2)"
    : isConfigured
    ? "0 0 0 2px rgba(250, 173, 20, 0.2)"
    : "none";

  return (
    <Card
      hoverable
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      className={`${styles.providerCard} ${
        isAvailable ? styles.enabledCard : ""
      } ${isHover ? styles.hover : styles.normal}`}
    >
      <div style={{ marginBottom: 32 }}>
        <div className={styles.cardHeader}>
          <span className={styles.cardName}>
            {provider.name}
            {providerTag}
          </span>
          <div className={styles.statusContainer}>
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                backgroundColor: statusDotColor,
                boxShadow: statusDotShadow,
              }}
            />
            <span
              className={`${styles.statusText} ${
                statusType === "enabled"
                  ? styles.enabled
                  : statusType === "partial"
                  ? styles.partial
                  : styles.disabled
              }`}
            >
              {statusLabel}
            </span>
          </div>
        </div>

        <div className={styles.cardInfo}>
          <div className={styles.infoRow}>
            <span className={styles.infoLabel}>{"基础 URL"}:</span>
            {provider.base_url ? (
              <span className={styles.infoValue} title={provider.base_url}>
                {provider.base_url}
              </span>
            ) : (
              <span className={styles.infoEmpty}>{"未设置"}</span>
            )}
          </div>
          <div className={styles.infoRow}>
            <span className={styles.infoLabel}>{"接口密钥"}:</span>
            {provider.api_key ? (
              <span className={styles.infoValue}>{provider.api_key}</span>
            ) : (
              <span className={styles.infoEmpty}>{"未设置"}</span>
            )}
          </div>
          <div className={styles.infoRow}>
            <span className={styles.infoLabel}>{"模型"}:</span>
            <span className={styles.infoValue}>
              {totalCount > 0
                ? `${totalCount} 个模型`
                : "暂无模型"}
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
        <Button
          type="link"
          size="small"
          onClick={(e) => {
            e.stopPropagation();
            setModalOpen(true);
          }}
          className={styles.configBtn}
          icon={<EditOutlined />}
        >
          {"设置"}
        </Button>
        {provider.is_custom && (
          <Button
            type="link"
            size="small"
            danger
            onClick={handleDeleteProvider}
            icon={<DeleteOutlined />}
          >
            {"删除提供方"}
          </Button>
        )}
      </div>

      <ProviderConfigModal
        provider={provider}
        activeModels={activeModels}
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSaved={onSaved}
      />
      <ModelManageModal
        provider={provider}
        open={modelManageOpen}
        onClose={() => setModelManageOpen(false)}
        onSaved={onSaved}
      />
    </Card>
  );
}
