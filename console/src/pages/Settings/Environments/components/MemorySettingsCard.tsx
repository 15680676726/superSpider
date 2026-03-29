import { Alert, Button, Input, Select, Switch, Tag } from "antd";
import { useMemo } from "react";
import styles from "../index.module.less";

const DEFAULT_EMBEDDING_BASE_URL =
  "https://dashscope.aliyuncs.com/compatible-mode/v1";
const DEFAULT_EMBEDDING_MODEL_BY_BASE_URL: Record<string, string> = {
  [DEFAULT_EMBEDDING_BASE_URL]: "text-embedding-v4",
  "https://api.openai.com/v1": "text-embedding-3-small",
};
const DEFAULT_EMBEDDING_MODEL_BY_PROVIDER_ID: Record<string, string> = {
  dashscope: "text-embedding-v4",
  openai: "text-embedding-3-small",
};

type RetrievalMode = "hybrid" | "vector" | "full-text" | "none";
type MemoryRecallMode = "hybrid-local" | "qmd";

interface MemorySettingsCardProps {
  memoryRecallMode: MemoryRecallMode;
  memoryRecallBackendRaw: string;
  embeddingApiKey: string;
  embeddingBaseUrl: string;
  embeddingModelName: string;
  followActiveProvider: boolean;
  ftsEnabled: boolean;
  memoryStoreBackend: string;
  dirty: boolean;
  saving: boolean;
  activeProviderId?: string;
  activeProviderName?: string;
  activeProviderModel?: string;
  activeProviderBaseUrl?: string;
  activeProviderHasApiKey?: boolean;
  onTextChange: (
    key: "EMBEDDING_API_KEY" | "EMBEDDING_BASE_URL" | "EMBEDDING_MODEL_NAME",
    value: string,
  ) => void;
  onFollowActiveProviderChange: (value: boolean) => void;
  onFtsEnabledChange: (value: boolean) => void;
  onMemoryStoreBackendChange: (value: string) => void;
  onMemoryRecallModeChange: (value: MemoryRecallMode) => void;
  onApplyRecommendedDefaults: () => void;
  onSave: () => void;
}

function normalizeBaseUrl(value: string): string {
  return value.trim().replace(/\/+$/, "");
}

function retrievalTagColor(mode: RetrievalMode): string {
  if (mode === "hybrid") return "success";
  if (mode === "vector") return "processing";
  if (mode === "full-text") return "warning";
  return "default";
}

function resolveDefaultEmbeddingModel(
  providerId: string | undefined,
  baseUrl: string,
): string {
  const normalizedProviderId = (providerId || "").trim().toLowerCase();
  if (
    normalizedProviderId &&
    DEFAULT_EMBEDDING_MODEL_BY_PROVIDER_ID[normalizedProviderId]
  ) {
    return DEFAULT_EMBEDDING_MODEL_BY_PROVIDER_ID[normalizedProviderId];
  }
  return DEFAULT_EMBEDDING_MODEL_BY_BASE_URL[normalizeBaseUrl(baseUrl)] || "";
}

const RETRIEVAL_LABELS: Record<RetrievalMode, string> = {
  hybrid: "混合",
  vector: "向量",
  "full-text": "全文",
  none: "未启用",
};

export function MemorySettingsCard({
  memoryRecallMode,
  memoryRecallBackendRaw,
  embeddingApiKey,
  embeddingBaseUrl,
  embeddingModelName,
  followActiveProvider,
  ftsEnabled,
  memoryStoreBackend,
  dirty,
  saving,
  activeProviderId,
  activeProviderName,
  activeProviderModel,
  activeProviderBaseUrl,
  activeProviderHasApiKey,
  onTextChange,
  onFollowActiveProviderChange,
  onFtsEnabledChange,
  onMemoryStoreBackendChange,
  onMemoryRecallModeChange,
  onApplyRecommendedDefaults,
  onSave,
}: MemorySettingsCardProps) {
  const configuredApiKey = embeddingApiKey.trim();
  const configuredBaseUrl = embeddingBaseUrl.trim();
  const configuredModelName = embeddingModelName.trim();
  const explicitProviderOverride =
    configuredApiKey.length > 0 || configuredBaseUrl.length > 0;
  const inheritedProviderActive =
    followActiveProvider && !explicitProviderOverride && !!activeProviderId;
  const inheritedBaseUrl = inheritedProviderActive
    ? (activeProviderBaseUrl || "").trim()
    : "";
  const effectiveBaseUrl =
    configuredBaseUrl || inheritedBaseUrl || DEFAULT_EMBEDDING_BASE_URL;
  const defaultEmbeddingModel = resolveDefaultEmbeddingModel(
    inheritedProviderActive ? activeProviderId : undefined,
    effectiveBaseUrl,
  );
  const serverWillInferDefaultModel =
    configuredModelName.length === 0 && defaultEmbeddingModel.length > 0;
  const effectiveModelName =
    configuredModelName ||
    (serverWillInferDefaultModel ? defaultEmbeddingModel : "");
  const effectiveApiKeyPresent =
    configuredApiKey.length > 0 ||
    (inheritedProviderActive && Boolean(activeProviderHasApiKey));
  const vectorReady = effectiveApiKeyPresent && effectiveModelName.length > 0;
  const retrievalMode: RetrievalMode = vectorReady
    ? ftsEnabled
      ? "hybrid"
      : "vector"
    : ftsEnabled
      ? "full-text"
      : "none";
  const normalizedMemoryRecallBackendRaw = memoryRecallBackendRaw
    .trim()
    .toLowerCase();
  const hasLegacyRecallBackend =
    normalizedMemoryRecallBackendRaw.length > 0 &&
    !["hybrid-local", "qmd"].includes(normalizedMemoryRecallBackendRaw);
  const memoryRecallModeLabel =
    memoryRecallMode === "qmd" ? "QMD 语义召回" : "Hybrid Local";
  const qmdPrewarmEnabled = memoryRecallMode === "qmd";
  const qmdQueryMode = memoryRecallMode === "qmd" ? "query" : "未启用";

  const backendOptions = useMemo(
    () => [
      {
        value: "auto",
        label: "自动",
      },
      {
        value: "local",
        label: "本地",
      },
      {
        value: "chroma",
        label: "Chroma 向量库",
      },
      {
        value: "sqlite",
        label: "SQLite 数据库",
      },
    ],
    [],
  );
  const memoryRecallOptions = useMemo(
    () => [
      {
        value: "hybrid-local",
        label: "Hybrid Local",
      },
      {
        value: "qmd",
        label: "QMD 语义召回",
      },
    ],
    [],
  );

  const alertType = vectorReady
    ? "success"
    : effectiveApiKeyPresent
      ? "warning"
      : inheritedProviderActive
        ? "warning"
        : "info";
  const alertMessage = vectorReady
    ? inheritedProviderActive
      ? "向量检索将跟随当前激活提供方，建议保留全文检索以获得混合召回。"
      : "向量检索已可用，建议保留全文检索以获得混合召回。"
    : effectiveApiKeyPresent
      ? "已配置接口密钥，但向量模型尚未确定，请补充模型名。"
      : inheritedProviderActive
        ? "服务端会在可复用时继承当前激活提供方的向量凭据。"
        : "未配置向量接口密钥，目前仅可使用全文检索。";

  const backendLabel =
    backendOptions.find((option) => option.value === memoryStoreBackend)
      ?.label ?? memoryStoreBackend;
  const configSourceLabel = explicitProviderOverride
    ? "显式向量配置"
    : followActiveProvider
      ? "跟随当前提供方"
      : "独立环境配置";
  const activeProviderDisplayText = activeProviderId
    ? `${activeProviderName || activeProviderId} / ${activeProviderModel || "-"}`
    : "暂无激活提供方";
  const modelInferenceText = serverWillInferDefaultModel
    ? `服务端将自动推断 ${defaultEmbeddingModel}`
    : "需显式指定模型或改用自定义提供方";

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
          <h3 className={styles.memoryCardTitle}>记忆 / 向量检索</h3>
          <p className={styles.memoryCardDesc}>
            直接配置向量模型与检索策略，写入同一份 /envs 环境变量存储。
          </p>
        </div>

        <div className="baize-page-header-actions">
          <Button onClick={onApplyRecommendedDefaults}>
            应用推荐默认值
          </Button>
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

      <div className={styles.memoryGrid}>
        <label className={styles.memoryField}>
          <span className={styles.memoryFieldLabel}>记忆主模式</span>
          <span className={styles.memoryFieldCode}>
            COPAW_MEMORY_RECALL_BACKEND
          </span>
          <Select
            value={memoryRecallMode}
            options={memoryRecallOptions}
            onChange={(value) =>
              onMemoryRecallModeChange(String(value) as MemoryRecallMode)
            }
          />
          <span className={styles.memoryFieldHelp}>
            {memoryRecallMode === "qmd"
              ? "会同时启用 COPAW_MEMORY_QMD_QUERY_MODE=query 和 COPAW_MEMORY_QMD_PREWARM=true，走全量语义召回。"
              : "默认走本地 hybrid-local；QMD 继续保持已安装但不作为默认在线召回路径。"}
          </span>
          {hasLegacyRecallBackend ? (
            <span className={styles.memoryFieldHelp}>
              {`当前环境变量仍是 ${memoryRecallBackendRaw}；本页只收口 qmd / hybrid-local 两种模式，保存后会规范化。`}
            </span>
          ) : null}
        </label>

        <label className={styles.memoryField}>
          <span className={styles.memoryFieldLabel}>向量接口密钥</span>
          <span className={styles.memoryFieldCode}>EMBEDDING_API_KEY</span>
          <Input.Password
            value={embeddingApiKey}
            onChange={(event) =>
              onTextChange("EMBEDDING_API_KEY", event.target.value)
            }
            placeholder="留空则关闭向量检索"
          />
          {followActiveProvider && configuredApiKey.length === 0 ? (
            <span className={styles.memoryFieldHelp}>
              留空后会优先复用当前激活提供方的接口密钥。
            </span>
          ) : null}
        </label>

        <label className={styles.memoryField}>
          <span className={styles.memoryFieldLabel}>向量服务地址</span>
          <span className={styles.memoryFieldCode}>EMBEDDING_BASE_URL</span>
          <Input
            value={embeddingBaseUrl}
            onChange={(event) =>
              onTextChange("EMBEDDING_BASE_URL", event.target.value)
            }
            placeholder="留空则使用内置默认地址"
          />
          {configuredBaseUrl.length === 0 ? (
            <span className={styles.memoryFieldHelp}>
              {inheritedProviderActive && inheritedBaseUrl
                ? "当前将使用激活提供方的服务地址。"
                : "当前使用系统内置默认服务地址。"}
            </span>
          ) : null}
        </label>

        <label className={styles.memoryField}>
          <span className={styles.memoryFieldLabel}>向量模型</span>
          <span className={styles.memoryFieldCode}>EMBEDDING_MODEL_NAME</span>
          <Input
            value={embeddingModelName}
            onChange={(event) =>
              onTextChange("EMBEDDING_MODEL_NAME", event.target.value)
            }
            placeholder="留空时由服务端按提供方默认值推断"
          />
          {serverWillInferDefaultModel ? (
            <span className={styles.memoryFieldHelp}>
              {`服务端将自动推断 ${defaultEmbeddingModel}`}
            </span>
          ) : null}
        </label>

        <div className={styles.memoryField}>
          <div className={styles.memorySwitchRow}>
            <div className={styles.memorySwitchMeta}>
              <span className={styles.memoryFieldLabel}>
                跟随当前激活提供方
              </span>
              <span className={styles.memoryFieldCode}>
                EMBEDDING_FOLLOW_ACTIVE_PROVIDER
              </span>
              <span className={styles.memoryFieldHelp}>
                开启后，当接口密钥和服务地址留空时会尝试复用当前激活提供方。
              </span>
            </div>
            <Switch
              checked={followActiveProvider}
              onChange={onFollowActiveProviderChange}
            />
          </div>
        </div>

        <div className={styles.memoryField}>
          <div className={styles.memorySwitchRow}>
            <div className={styles.memorySwitchMeta}>
              <span className={styles.memoryFieldLabel}>
                全文检索
              </span>
              <span className={styles.memoryFieldCode}>FTS_ENABLED</span>
            </div>
            <Switch checked={ftsEnabled} onChange={onFtsEnabledChange} />
          </div>
        </div>

        <label className={styles.memoryField}>
          <span className={styles.memoryFieldLabel}>记忆后端</span>
          <span className={styles.memoryFieldCode}>MEMORY_STORE_BACKEND</span>
          <Select
            value={memoryStoreBackend}
            options={backendOptions}
            onChange={(value) => onMemoryStoreBackendChange(String(value))}
          />
        </label>
      </div>

      <div className={styles.memoryStatusPanel}>
        <div className={styles.memoryStatusHeader}>
          当前生效状态
        </div>
        <div className={styles.memoryStatusGrid}>
          <div className={styles.memoryStatusItem}>
            <span className={styles.memoryStatusLabel}>记忆主模式</span>
            {renderStatusTag(
              memoryRecallModeLabel,
              memoryRecallMode === "qmd" ? "processing" : "default",
            )}
          </div>

          <div className={styles.memoryStatusItem}>
            <span className={styles.memoryStatusLabel}>QMD 启动预热</span>
            {renderStatusTag(
              qmdPrewarmEnabled ? "已启用" : "未启用",
              qmdPrewarmEnabled ? "success" : "default",
            )}
          </div>

          <div className={styles.memoryStatusItem}>
            <span className={styles.memoryStatusLabel}>QMD 查询模式</span>
            <span className={styles.memoryStatusValue} title={qmdQueryMode}>
              {qmdQueryMode}
            </span>
          </div>

          <div className={styles.memoryStatusItem}>
            <span className={styles.memoryStatusLabel}>
              配置来源
            </span>
            {renderStatusTag(configSourceLabel)}
          </div>

          <div className={styles.memoryStatusItem}>
            <span className={styles.memoryStatusLabel}>
              实际服务地址
            </span>
            <span className={styles.memoryStatusValue} title={effectiveBaseUrl}>
              {effectiveBaseUrl}
            </span>
          </div>

          <div className={styles.memoryStatusItem}>
            <span className={styles.memoryStatusLabel}>
              实际模型
            </span>
            <span
              className={styles.memoryStatusValue}
              title={effectiveModelName || "未解析"}
            >
              {effectiveModelName || "未解析"}
            </span>
          </div>

          <div className={styles.memoryStatusItem}>
            <span className={styles.memoryStatusLabel}>
              检索模式
            </span>
            {renderStatusTag(
              RETRIEVAL_LABELS[retrievalMode],
              retrievalTagColor(retrievalMode),
            )}
          </div>

          <div className={styles.memoryStatusItem}>
            <span className={styles.memoryStatusLabel}>
              模型推断
            </span>
            {renderStatusTag(
              modelInferenceText,
              serverWillInferDefaultModel ? "gold" : "default",
            )}
          </div>

          <div className={styles.memoryStatusItem}>
            <span className={styles.memoryStatusLabel}>
              记忆后端
            </span>
            {renderStatusTag(backendLabel)}
          </div>

          <div className={styles.memoryStatusItem}>
            <span className={styles.memoryStatusLabel}>
              当前激活提供方
            </span>
            <span
              className={styles.memoryStatusValue}
              title={activeProviderDisplayText}
            >
              {activeProviderDisplayText}
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}
