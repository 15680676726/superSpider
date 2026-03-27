import { Card, Button, Tooltip, Tag } from "@/ui";
import {
  DeleteOutlined,
  FileTextFilled,
  FileZipFilled,
  FilePdfFilled,
  FileWordFilled,
  FileExcelFilled,
  FilePptFilled,
  FileImageFilled,
  CodeFilled,
} from "@ant-design/icons";
import { runtimeRiskColor, runtimeRiskLabel } from "../../../../runtime/tagSemantics";
import type { SkillCapabilityView } from "../useSkills";
import styles from "../index.module.less";

interface SkillCardProps {
  skill: SkillCapabilityView;
  isHover: boolean;
  onClick: () => void;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
  onToggleEnabled: (e: React.MouseEvent) => void;
  onDelete?: (e?: React.MouseEvent) => void;
}

const getFileIcon = (filePath: string) => {
  const extension = filePath.split(".").pop()?.toLowerCase() || "";

  switch (extension) {
    case "txt":
    case "md":
    case "markdown":
      return <FileTextFilled style={{ color: "#1890ff" }} />;
    case "zip":
    case "rar":
    case "7z":
    case "tar":
    case "gz":
      return <FileZipFilled style={{ color: "#fa8c16" }} />;
    case "pdf":
      return <FilePdfFilled style={{ color: "#f5222d" }} />;
    case "doc":
    case "docx":
      return <FileWordFilled style={{ color: "#2b579a" }} />;
    case "xls":
    case "xlsx":
      return <FileExcelFilled style={{ color: "#217346" }} />;
    case "ppt":
    case "pptx":
      return <FilePptFilled style={{ color: "#d24726" }} />;
    case "jpg":
    case "jpeg":
    case "png":
    case "gif":
    case "svg":
    case "webp":
      return <FileImageFilled style={{ color: "#eb2f96" }} />;
    case "py":
    case "js":
    case "ts":
    case "jsx":
    case "tsx":
    case "java":
    case "cpp":
    case "c":
    case "go":
    case "rs":
    case "rb":
    case "php":
      return <CodeFilled style={{ color: "#52c41a" }} />;
    default:
      return <FileTextFilled style={{ color: "#1890ff" }} />;
  }
};

export function SkillCard({
  skill,
  isHover,
  onClick,
  onMouseEnter,
  onMouseLeave,
  onToggleEnabled,
  onDelete,
}: SkillCardProps) {
  const isCustomized = skill.source === "customized";
  const capability = skill.capability;
  const summary =
    capability?.summary ||
    skill.content.split("\n")[0]?.replace(/^#+\s*/, "") ||
    skill.name;
  const envPreview =
    capability?.environment_requirements.slice(0, 2).join(" / ") ||
    "无特定环境要求";
  const evidencePreview =
    capability?.evidence_contract.slice(0, 2).join(" / ") ||
    "无证据约定";
  const riskLevel = capability?.risk_level || "auto";
  const riskColor = runtimeRiskColor(riskLevel);

  return (
    <Card
      hoverable
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      className={`${styles.skillCard} ${
        skill.enabled ? styles.enabledCard : ""
      } ${isHover ? styles.hover : styles.normal}`}
    >
      <div
        style={{
          marginBottom: 32,
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
        }}
      >
        <div className={styles.cardHeader}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span className={styles.fileIcon}>{getFileIcon(skill.name)}</span>
            <h3 className={styles.skillTitle}>{skill.name}</h3>
          </div>
          <div className={styles.statusContainer}>
            <span
              className={`${styles.statusDot} ${
                skill.enabled ? styles.enabled : styles.disabled
              }`}
            />
            <span
              className={`${styles.statusText} ${
                skill.enabled ? styles.enabled : styles.disabled
              }`}
            >
              {skill.enabled ? "已启用" : "已停用"}
            </span>
          </div>
        </div>

        <div className={styles.infoSection}>
          <div className={styles.infoLabel}>{"来源"}</div>
          <code className={styles.infoCode}>{skill.source}</code>
        </div>

        <div className={styles.summarySection}>
          <div className={styles.infoLabel}>{"能力摘要"}</div>
          <div className={styles.summaryText}>{summary}</div>
        </div>

        {capability ? (
          <div className={styles.capabilityMeta}>
            <Tooltip title={capability.risk_description || riskLevel}>
              <Tag color={riskColor}>{runtimeRiskLabel(riskLevel) || riskLevel}</Tag>
            </Tooltip>
            <Tooltip title={capability.environment_description || envPreview}>
              <Tag color="blue">{envPreview}</Tag>
            </Tooltip>
            <Tooltip title={capability.evidence_description || evidencePreview}>
              <Tag color="purple">{evidencePreview}</Tag>
            </Tooltip>
            {capability.tags?.slice(0, 3).map((tag) => (
              <Tag key={tag}>{tag}</Tag>
            ))}
          </div>
        ) : null}

        <div className={styles.infoSection}>
          <div className={styles.infoLabel}>{"路径"}</div>
          <code className={`${styles.infoCode} ${styles.path}`}>{skill.path}</code>
        </div>
      </div>

      <div className={styles.cardFooter}>
        <Button
          type="link"
          size="small"
          onClick={onToggleEnabled}
          className={styles.actionButton}
        >
          {skill.enabled ? "停用" : "启用"}
        </Button>

        {isCustomized && onDelete && (
          <Button
            type="text"
            size="small"
            danger
            icon={<DeleteOutlined />}
            className={styles.deleteButton}
            onClick={(e) => {
              e.stopPropagation();
              if (!skill.enabled) {
                onDelete(e);
              }
            }}
            disabled={skill.enabled}
          />
        )}
      </div>
    </Card>
  );
}
