import { useState } from "react";
import { Button, Form, Modal } from "@/ui";
import { DownloadOutlined, PlusOutlined } from "@ant-design/icons";
import type { SkillSpec } from "../../../api/types";
import { SkillCard, SkillDrawer } from "./components";
import { useSkills, type SkillCapabilityView } from "./useSkills";
import styles from "./index.module.less";

const SUPPORTED_PREFIXES = [
  "https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/",
  "https://lightmake.site/api/v1/download",
];

export default function SkillsPage() {
  const {
    skills,
    loading,
    importing,
    createSkill,
    importFromHub,
    toggleEnabled,
    deleteSkill,
  } = useSkills();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importUrl, setImportUrl] = useState("");
  const [importUrlError, setImportUrlError] = useState("");
  const [editingSkill, setEditingSkill] = useState<SkillSpec | null>(null);
  const [hoverKey, setHoverKey] = useState<string | null>(null);
  const [form] = Form.useForm<SkillSpec>();

  const isSupportedSkillUrl = (url: string) =>
    SUPPORTED_PREFIXES.some((prefix) => url.startsWith(prefix));

  const handleCreate = () => {
    setEditingSkill(null);
    form.resetFields();
    form.setFieldsValue({
      enabled: false,
    });
    setDrawerOpen(true);
  };

  const closeImportModal = () => {
    if (importing) {
      return;
    }
    setImportModalOpen(false);
    setImportUrl("");
    setImportUrlError("");
  };

  const handleImportUrlChange = (value: string) => {
    setImportUrl(value);
    const trimmed = value.trim();
    if (trimmed && !isSupportedSkillUrl(trimmed)) {
      setImportUrlError("暂不支持该技能地址来源");
      return;
    }
    setImportUrlError("");
  };

  const handleConfirmImport = async () => {
    if (importing) return;
    const trimmed = importUrl.trim();
    if (!trimmed) return;
    if (!isSupportedSkillUrl(trimmed)) {
      setImportUrlError("暂不支持该技能地址来源");
      return;
    }
    const success = await importFromHub(trimmed);
    if (success) {
      closeImportModal();
    }
  };

  const handleEdit = (skill: SkillCapabilityView) => {
    setEditingSkill(skill);
    form.setFieldsValue(skill);
    setDrawerOpen(true);
  };

  const handleToggleEnabled = async (
    skill: SkillCapabilityView,
    e: React.MouseEvent,
  ) => {
    e.stopPropagation();
    await toggleEnabled(skill);
  };

  const handleDelete = async (skill: SkillCapabilityView, e?: React.MouseEvent) => {
    e?.stopPropagation();
    await deleteSkill(skill);
  };

  const handleSubmit = async (values: { name: string; content: string }) => {
    const success = await createSkill(values.name, values.content);
    if (success) {
      setDrawerOpen(false);
    }
  };

  return (
    <div className={styles.skillsPage}>
      <div className={styles.header}>
        <div className={styles.headerInfo}>
          <h1 className={styles.title}>{"技能管理"}</h1>
          <p className={styles.description}>
            {
              "管理本地技能、导入技能包，并统一控制启停状态。"
            }
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Button
            type="primary"
            onClick={() => setImportModalOpen(true)}
            icon={<DownloadOutlined />}
          >
            {"导入技能"}
          </Button>
          <Button type="primary" onClick={handleCreate} icon={<PlusOutlined />}>
            {"新建技能"}
          </Button>
        </div>
      </div>

      <Modal
        title={"导入技能"}
        open={importModalOpen}
        onCancel={closeImportModal}
        maskClosable={!importing}
        closable={!importing}
        keyboard={!importing}
        footer={
          <div style={{ textAlign: "right" }}>
            <Button
              onClick={closeImportModal}
              style={{ marginRight: 8 }}
              disabled={importing}
            >
              {"取消"}
            </Button>
            <Button
              type="primary"
              onClick={() => void handleConfirmImport()}
              loading={importing}
              disabled={importing || !importUrl.trim() || !!importUrlError}
            >
              {"导入技能"}
            </Button>
          </div>
        }
        width={760}
      >
        <div className={styles.importHintBlock}>
          <p className={styles.importHintTitle}>
            {"支持的技能地址来源"}
          </p>
          <ul className={styles.importHintList}>
            {SUPPORTED_PREFIXES.map((prefix) => (
              <li key={prefix}>{prefix}</li>
            ))}
          </ul>
          <p className={styles.importHintTitle}>{"示例地址"}</p>
          <ul className={styles.importHintList}>
            <li>https://skillhub-1388575217.cos.ap-guangzhou.myqcloud.com/skills/find-skills.zip</li>
            <li>https://lightmake.site/api/v1/download?slug=find-skills</li>
          </ul>
        </div>

        <input
          className={styles.importUrlInput}
          value={importUrl}
          onChange={(e) => handleImportUrlChange(e.target.value)}
          placeholder={"请输入技能地址"}
          disabled={importing}
        />
        {importUrlError ? (
          <div className={styles.importUrlError}>{importUrlError}</div>
        ) : null}
        {importing ? (
          <div className={styles.importLoadingText}>{"加载中..."}</div>
        ) : null}
      </Modal>

      {loading ? (
        <div className={styles.loading}>
          <span className={styles.loadingText}>{"加载中..."}</span>
        </div>
      ) : (
        <div className={styles.skillsGrid}>
          {skills
            .slice()
            .sort((a, b) => {
              if (a.enabled && !b.enabled) return -1;
              if (!a.enabled && b.enabled) return 1;
              return a.name.localeCompare(b.name);
            })
            .map((skill) => (
              <SkillCard
                key={skill.name}
                skill={skill}
                isHover={hoverKey === skill.name}
                onClick={() => handleEdit(skill)}
                onMouseEnter={() => setHoverKey(skill.name)}
                onMouseLeave={() => setHoverKey(null)}
                onToggleEnabled={(e) => void handleToggleEnabled(skill, e)}
                onDelete={(e) => void handleDelete(skill, e)}
              />
            ))}
        </div>
      )}

      <SkillDrawer
        open={drawerOpen}
        editingSkill={editingSkill}
        form={form}
        onClose={() => {
          setDrawerOpen(false);
          setEditingSkill(null);
        }}
        onSubmit={handleSubmit}
      />
    </div>
  );
}
