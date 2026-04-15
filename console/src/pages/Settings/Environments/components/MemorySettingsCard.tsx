import { Alert, Button, Input, Select, Switch, Tag } from "antd";
import { useMemo } from "react";
import styles from "../index.module.less";

type PrivateCompactionMode = "fts" | "basic";

interface MemorySettingsCardProps {
  memoryRecallBackendRaw: string;
  retiredMemoryKeys: string[];
  ftsEnabled: boolean;
  memoryStoreBackend: string;
  dirty: boolean;
  saving: boolean;
  onFtsEnabledChange: (value: boolean) => void;
  onMemoryStoreBackendChange: (value: string) => void;
  onApplyRecommendedDefaults: () => void;
  onSave: () => void;
}

function privateCompactionLabel(mode: PrivateCompactionMode): string {
  return mode === "fts" ? "全文增强" : "基础模式";
}

function privateCompactionColor(mode: PrivateCompactionMode): string {
  return mode === "fts" ? "success" : "default";
}

export function MemorySettingsCard({
  memoryRecallBackendRaw,
  retiredMemoryKeys,
  ftsEnabled,
  memoryStoreBackend,
  dirty,
  saving,
  onFtsEnabledChange,
  onMemoryStoreBackendChange,
  onApplyRecommendedDefaults,
  onSave,
}: MemorySettingsCardProps) {
  const normalizedMemoryRecallBackendRaw = memoryRecallBackendRaw
    .trim()
    .toLowerCase();
  const recallBackendDisplay = normalizedMemoryRecallBackendRaw || "未设置";
  const recallBackendMismatched =
    normalizedMemoryRecallBackendRaw.length > 0 &&
    normalizedMemoryRecallBackendRaw !== "truth-first";
  const privateCompactionMode: PrivateCompactionMode = ftsEnabled
    ? "fts"
    : "basic";

  const backendOptions = useMemo(
    () => [
      {
        value: "auto",
        label: "自动",
      },
      {
        value: "local",
        label: "本地文件",
      },
      {
        value: "chroma",
        label: "Chroma 本地索引",
      },
      {
        value: "sqlite",
        label: "SQLite",
      },
    ],
    [],
  );

  const backendLabel =
    backendOptions.find((option) => option.value === memoryStoreBackend)
      ?.label ?? memoryStoreBackend;

  const alertType = recallBackendMismatched ? "warning" : "info";
  const alertMessage = recallBackendMismatched
    ? `当前环境变量仍是 ${memoryRecallBackendRaw}，但正式共享记忆主链只认 truth-first；运行时会自动回退到 truth-first。`
    : "正式共享记忆已经固定为 truth-first。下面只保留私有聊天压缩仍在使用的全文检索和存储项。";

  const renderStatusTag = (text: string, color?: string) => (
    <Tag color={color} title={text}>
      <span className={styles.memoryStatusTagText} title={text}>
        {text}
      </span>
    </Tag>
  );

  return (
    <section className={styles.memoryCard}>
      <div className={styles.memoryCardHeader}>
        <div>
          <h3 className={styles.memoryCardTitle}>记忆配置</h3>
          <p className={styles.memoryCardDesc}>
            正式共享记忆已经收口为 truth-first。环境页这里只保留私有聊天压缩仍在使用的全文检索和存储项。
          </p>
        </div>

        <div className="baize-page-header-actions">
          <Button onClick={onApplyRecommendedDefaults}>应用正式默认值</Button>
          <Button
            type="primary"
            onClick={onSave}
            loading={saving}
            disabled={!dirty}
          >
            保存记忆配置
          </Button>
        </div>
      </div>

      <Alert
        showIcon
        type={alertType}
        message={alertMessage}
        className={styles.memoryAlert}
      />

      {retiredMemoryKeys.length > 0 ? (
        <Alert
          showIcon
          type="warning"
          message={`检测到 ${retiredMemoryKeys.length} 个退役记忆变量`}
          description={`这些旧键已经不参与正式记忆主链，也不再驱动私有聊天压缩：${retiredMemoryKeys.join("、")}。应用正式默认值可一键清理。`}
          className={styles.memoryAlert}
        />
      ) : null}

      <div className={styles.memoryGrid}>
        <div className={styles.memoryField}>
          <span className={styles.memoryFieldLabel}>正式召回主链</span>
          <span className={styles.memoryFieldCode}>COPAW_MEMORY_RECALL_BACKEND</span>
          <Input value="truth-first" readOnly />
          <span className={styles.memoryFieldHelp}>
            这是当前正式共享记忆的唯一后端，不再开放旧召回模式选择。
          </span>
        </div>

        <div className={styles.memoryField}>
          <span className={styles.memoryFieldLabel}>当前环境变量</span>
          <span className={styles.memoryFieldCode}>COPAW_MEMORY_RECALL_BACKEND</span>
          <Input value={recallBackendDisplay} readOnly />
          <span className={styles.memoryFieldHelp}>
            不管这里历史上写过什么，运行时都会按 truth-first 收口。
          </span>
        </div>

        <div className={styles.memoryField}>
          <div className={styles.memorySwitchRow}>
            <div className={styles.memorySwitchMeta}>
              <span className={styles.memoryFieldLabel}>本地全文检索</span>
              <span className={styles.memoryFieldCode}>FTS_ENABLED</span>
              <span className={styles.memoryFieldHelp}>
                这是私有聊天压缩的本地补充检索，不是正式共享记忆召回模式。
              </span>
            </div>
            <Switch checked={ftsEnabled} onChange={onFtsEnabledChange} />
          </div>
        </div>

        <label className={styles.memoryField}>
          <span className={styles.memoryFieldLabel}>私有压缩存储后端</span>
          <span className={styles.memoryFieldCode}>MEMORY_STORE_BACKEND</span>
          <Select
            value={memoryStoreBackend}
            options={backendOptions}
            onChange={(value) => onMemoryStoreBackendChange(String(value))}
          />
          <span className={styles.memoryFieldHelp}>
            这只影响私有聊天压缩的本地落盘方式，不影响正式共享记忆主链。
          </span>
        </label>
      </div>

      <div className={styles.memoryStatusPanel}>
        <div className={styles.memoryStatusHeader}>当前生效状态</div>
        <div className={styles.memoryStatusGrid}>
          <div className={styles.memoryStatusItem}>
            <span className={styles.memoryStatusLabel}>正式记忆主链</span>
            {renderStatusTag("truth-first", "success")}
          </div>

          <div className={styles.memoryStatusItem}>
            <span className={styles.memoryStatusLabel}>记忆整理层</span>
            {renderStatusTag("sleep", "processing")}
          </div>

          <div className={styles.memoryStatusItem}>
            <span className={styles.memoryStatusLabel}>环境变量值</span>
            <span className={styles.memoryStatusValue} title={recallBackendDisplay}>
              {recallBackendDisplay}
            </span>
          </div>

          <div className={styles.memoryStatusItem}>
            <span className={styles.memoryStatusLabel}>运行时效果</span>
            {renderStatusTag("truth-first", "success")}
          </div>

          <div className={styles.memoryStatusItem}>
            <span className={styles.memoryStatusLabel}>私有聊天压缩</span>
            {renderStatusTag(
              privateCompactionLabel(privateCompactionMode),
              privateCompactionColor(privateCompactionMode),
            )}
          </div>

          <div className={styles.memoryStatusItem}>
            <span className={styles.memoryStatusLabel}>本地全文检索</span>
            {renderStatusTag(ftsEnabled ? "已开启" : "已关闭", ftsEnabled ? "success" : "default")}
          </div>

          <div className={styles.memoryStatusItem}>
            <span className={styles.memoryStatusLabel}>私有存储后端</span>
            {renderStatusTag(backendLabel)}
          </div>
        </div>
      </div>
    </section>
  );
}
