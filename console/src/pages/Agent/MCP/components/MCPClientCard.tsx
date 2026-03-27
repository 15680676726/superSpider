import { useState } from "react";
import { Card, Button, Modal, Tooltip, Tag } from "@/ui";
import { DeleteOutlined } from "@ant-design/icons";
import { Server } from "lucide-react";
import { normalizeDisplayChinese } from "../../../../text";
import { runtimeRiskColor, runtimeRiskLabel } from "../../../../runtime/tagSemantics";
import type { MCPClientCapabilityView } from "../useMCP";
import styles from "../index.module.less";

interface MCPClientCardProps {
  client: MCPClientCapabilityView;
  onToggle: (client: MCPClientCapabilityView, e: React.MouseEvent) => void;
  onDelete: (client: MCPClientCapabilityView, e: React.MouseEvent) => void;
  onUpdate: (key: string, updates: any) => Promise<boolean>;
  isHovered: boolean;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
}

export function MCPClientCard({
  client,
  onToggle,
  onDelete,
  onUpdate,
  isHovered,
  onMouseEnter,
  onMouseLeave,
}: MCPClientCardProps) {
  const [jsonModalOpen, setJsonModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [editedJson, setEditedJson] = useState("");
  const [isEditing, setIsEditing] = useState(false);

  const isRemote =
    client.transport === "streamable_http" || client.transport === "sse";
  const clientType = isRemote ? "远程" : "本地";
  const capability = client.capability;
  const envPreview =
    normalizeDisplayChinese(
      capability?.environment_requirements.slice(0, 2).join(" / ") ||
        "无特定环境要求",
    ) ||
    "无特定环境要求";
  const evidencePreview =
    normalizeDisplayChinese(
      capability?.evidence_contract.slice(0, 2).join(" / ") ||
        "无证据约定",
    ) ||
    "无证据约定";
  const riskLevel = capability?.risk_level || "auto";
  const riskColor = runtimeRiskColor(riskLevel);

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setDeleteModalOpen(true);
  };

  const handleCardClick = () => {
    setEditedJson(JSON.stringify(client, null, 2));
    setIsEditing(false);
    setJsonModalOpen(true);
  };

  const handleSaveJson = async () => {
    try {
      const parsed = JSON.parse(editedJson);
      const updates = { ...parsed };
      delete updates.key;
      const success = await onUpdate(client.key, updates);
      if (success) {
        setJsonModalOpen(false);
        setIsEditing(false);
      }
    } catch {
      window.alert("JSON 格式无效");
    }
  };

  return (
    <>
      <Card
        hoverable
        onClick={handleCardClick}
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}
        className={`${styles.mcpCard} ${
          client.enabled ? styles.enabledCard : ""
        } ${isHovered ? styles.hover : styles.normal}`}
      >
        <div className={styles.cardHeader}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span className={styles.fileIcon}>
              <Server style={{ color: "#1890ff", fontSize: 20 }} />
            </span>
            <Tooltip title={client.name}>
              <h3 className={styles.mcpTitle}>{client.name}</h3>
            </Tooltip>
            <span
              className={`${styles.typeBadge} ${
                isRemote ? styles.remote : styles.local
              }`}
            >
              {clientType}
            </span>
          </div>
          <div className={styles.statusContainer}>
            <span
              className={`${styles.statusDot} ${
                client.enabled ? styles.enabled : styles.disabled
              }`}
            />
            <span
              className={`${styles.statusText} ${
                client.enabled ? styles.enabled : styles.disabled
              }`}
            >
              {client.enabled ? "已启用" : "已停用"}
            </span>
          </div>
        </div>

        <div className={styles.description}>
          {normalizeDisplayChinese(client.description || "") || " "}
        </div>

        {capability ? (
          <div className={styles.capabilityMeta}>
            <Tooltip
              title={normalizeDisplayChinese(capability.risk_description || riskLevel)}
            >
              <Tag color={riskColor}>
                {runtimeRiskLabel(riskLevel) || riskLevel}
              </Tag>
            </Tooltip>
            <Tooltip
              title={normalizeDisplayChinese(capability.environment_description || envPreview)}
            >
              <Tag color="blue">{envPreview}</Tag>
            </Tooltip>
            <Tooltip
              title={normalizeDisplayChinese(capability.evidence_description || evidencePreview)}
            >
              <Tag color="purple">{evidencePreview}</Tag>
            </Tooltip>
            {capability.tags?.slice(0, 3).map((tag) => (
              <Tag key={tag}>{normalizeDisplayChinese(tag)}</Tag>
            ))}
          </div>
        ) : null}

        <div className={styles.cardFooter}>
          <Button
            type="link"
            size="small"
            onClick={(event) => onToggle(client, event)}
            className={styles.actionButton}
          >
            {client.enabled ? "停用" : "启用"}
          </Button>

          <Button
            type="text"
            size="small"
            danger
            icon={<DeleteOutlined />}
            className={styles.deleteButton}
            onClick={handleDeleteClick}
            disabled={client.enabled}
          />
        </div>
      </Card>

      <Modal
        title={"确认"}
        open={deleteModalOpen}
        onOk={() => {
          setDeleteModalOpen(false);
          onDelete(client, null as any);
        }}
        onCancel={() => setDeleteModalOpen(false)}
        okText={"确认"}
        cancelText={"取消"}
        okButtonProps={{ danger: true }}
      >
        <p>{"删除这个模型上下文协议客户端吗？"}</p>
      </Modal>

      <Modal
        title={`${client.name} / 配置`}
        open={jsonModalOpen}
        onCancel={() => setJsonModalOpen(false)}
        footer={
          <div style={{ textAlign: "right" }}>
            <Button
              onClick={() => setJsonModalOpen(false)}
              style={{ marginRight: 8 }}
            >
              {"取消"}
            </Button>
            {isEditing ? (
              <Button type="primary" onClick={handleSaveJson}>
                {"保存"}
              </Button>
            ) : (
              <Button type="primary" onClick={() => setIsEditing(true)}>
                {"编辑"}
              </Button>
            )}
          </div>
        }
        width={700}
      >
        {isEditing ? (
          <textarea
            value={editedJson}
            onChange={(e) => setEditedJson(e.target.value)}
            className={styles.editJsonTextArea}
          />
        ) : (
          <pre className={styles.preformattedText}>
            {JSON.stringify(client, null, 2)}
          </pre>
        )}
      </Modal>
    </>
  );
}
