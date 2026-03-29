import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Empty,
  List,
  Select,
  Space,
  Spin,
  Statistic,
  Switch,
  Tag,
  Typography,
  Upload,
  message,
  type UploadFile,
} from "antd";
import {
  Activity,
  Download,
  HardDriveDownload,
  ShieldCheck,
  ShieldX,
  RefreshCw,
  UploadCloud,
  ServerCrash,
  Layers3,
  Trash2,
  Plus,
} from "lucide-react";
import api, { request } from "../../../api";
import { runtimeRiskColor, runtimeRiskLabel } from "../../../runtime/tagSemantics";
import type {
  ProviderFallbackConfig,
  ProviderInfo,
  SystemOverview,
  SystemSelfCheck,
  StartupRecoverySummary,
} from "../../../api/types";
import styles from "./index.module.less";

interface SystemAgentProfile {
  agent_id: string;
  name: string;
  role_name: string;
  role_summary: string;
  status: string;
  risk_level: string;
  current_focus?: string | null;
}

const SYSTEM_AGENTS_ROUTE = "/runtime-center/agents?view=system";

function statusColor(status: string) {
  if (status === "pass") return "success";
  if (status === "warn") return "warning";
  if (status === "fail") return "error";
  return "default";
}

function runtimeStatusColor(status: string) {
  if (status === "running" || status === "active") return "success";
  if (status === "needs-confirm") return "warning";
  if (status === "waiting" || status === "paused") return "processing";
  if (status === "blocked" || status === "failed" || status === "degraded") return "error";
  return "default";
}

function formatBytes(value?: number) {
  if (!value) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size.toFixed(size >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
}

function providerModelOptions(providers: ProviderInfo[]) {
  return providers.flatMap((provider) =>
    provider.models.map((model) => ({
      value: `${provider.id}::${model.id}`,
      label: `${provider.name} / ${model.name}`,
      provider_id: provider.id,
      model: model.id,
    })),
  );
}

function parseCandidate(value: string) {
  const [provider_id, model] = value.split("::");
  return { provider_id, model };
}

function formatDateTime(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

function humanizeToken(value: string) {
  return value
    .replace(/_/g, " ")
    .replace(/\w/g, (chunk) => chunk.toUpperCase());
}

function localizeSystemStatus(status: string) {
  const map: Record<string, string> = {
    pass: "通过",
    warn: "警告",
    fail: "失败",
  };
  return map[status] || humanizeToken(status);
}

function localizeRuntimeStatus(status: string) {
  const map: Record<string, string> = {
    running: "运行中",
    active: "运行中",
    idle: "空闲",
    paused: "已暂停",
    scheduled: "已调度",
    persistent: "常驻",
    "on-demand": "按需",
    waiting: "等待中",
    blocked: "阻塞",
    failed: "失败",
    degraded: "降级",
    "needs-confirm": "待确认",
  };
  return map[status] || humanizeToken(status);
}

function localizeRiskLevel(level: string) {
  return runtimeRiskLabel(level) || humanizeToken(level);
}

function localizeCheckName(name: string) {
  const map: Record<string, string> = {
    working_dir: "工作目录",
    state_store: "状态存储",
    evidence_ledger: "证据账本",
    core_runtime_ready: "核心运行时就绪",
    memory_vector_ready: "记忆向量检索就绪",
    memory_embedding_config: "记忆嵌入配置",
    browser_surface_ready: "浏览器执行面就绪",
    desktop_surface_ready: "桌面执行面就绪",
    kernel_dispatcher: "内核分发器",
    runtime_event_bus: "运行事件总线",
    cron_manager: "定时任务管理",
    provider_active_model: "当前激活模型",
    provider_fallback: "提供方回退",
    startup_recovery: "启动恢复",
  };
  return map[name] || humanizeToken(name);
}

function localizeCheckSummary(item: SystemSelfCheck["checks"][number]) {
  const meta = item.meta || {};
  if (item.name === "working_dir") {
    return item.status === "pass"
      ? "工作目录存在。"
      : "工作目录缺失。";
  }
  if (item.name === "state_store") {
    return item.status === "pass"
      ? "状态存储可用。"
      : item.status === "warn"
        ? "状态存储存在警告。"
        : "状态存储不可用。";
  }
  if (item.name === "evidence_ledger") {
    return item.status === "pass"
      ? "证据账本可用。"
      : item.status === "warn"
        ? "证据账本存在警告。"
        : "证据账本不可用。";
  }
  if (
    item.name.endsWith("_service") ||
    item.name === "state_store" ||
    item.name === "evidence_ledger" ||
    item.name === "kernel_dispatcher" ||
    item.name === "runtime_event_bus" ||
    item.name === "cron_manager"
  ) {
    return `${localizeCheckName(item.name)}?${localizeSystemStatus(item.status)}`;
  }
  if (item.name === "provider_active_model") {
    const activeModel = meta.active_model as { provider_id?: string | null } | undefined;
    return item.status === "pass"
      ? `当前激活模型提供方?${activeModel?.provider_id || "-"}`
      : "未检测到激活模型提供方。";
  }
  if (item.name === "provider_fallback") {
    return item.status === "pass"
      ? "提供方回退链路可用。"
      : item.status === "warn"
        ? "提供方回退链路存在警告。"
        : "提供方回退链路不可用。";
  }
  if (item.name === "startup_recovery") {
    return item.status === "pass"
      ? "启动恢复检查正常。"
      : item.status === "warn"
        ? "启动恢复存在警告。"
        : "启动恢复检查失败。";
  }
  return item.summary;
}

function localizeRecoveryField(key: string) {
  const map: Record<string, string> = {
    last_attempt_at: "上次尝试时间",
    recovered_at: "恢复时间",
    pending_actions: "待处理项",
    pending_decisions: "待确认项",
    last_error: "上次错误",
    summary: "摘要",
    status: "状态",
  };
  return map[key] || humanizeToken(key);
}

function localizeRecoveryValue(key: string, value: unknown) {
  if (value == null) {
    return "无";
  }
  if (Array.isArray(value)) {
    return value.length > 0 ? value.map((item) => String(item)).join(", ") : "无";
  }
  if (typeof value === "string" && key.endsWith("_at")) {
    return formatDateTime(value);
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

export default function SystemSettingsPage() {
  const [overview, setOverview] = useState<SystemOverview | null>(null);
  const [systemAgents, setSystemAgents] = useState<SystemAgentProfile[]>([]);
  const [selfCheck, setSelfCheck] = useState<SystemSelfCheck | null>(null);
  const [fallbackConfig, setFallbackConfig] = useState<ProviderFallbackConfig>({
    enabled: false,
    candidates: [],
  });
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [runningSelfCheck, setRunningSelfCheck] = useState(false);
  const [savingFallback, setSavingFallback] = useState(false);
  const [restoringBackup, setRestoringBackup] = useState(false);
  const [restoreFiles, setRestoreFiles] = useState<UploadFile[]>([]);
  const [error, setError] = useState<string | null>(null);

  const modelOptions = useMemo(() => providerModelOptions(providers), [providers]);
  const recoverySummary: StartupRecoverySummary | null = overview?.runtime.startup_recovery ?? null;
  const localizedRecoveryEntries = useMemo(
    () =>
      recoverySummary
        ? Object.entries(recoverySummary).map(([key, value]) => ({
            key,
            label: localizeRecoveryField(key),
            value: localizeRecoveryValue(key, value),
          }))
        : [],
    [recoverySummary],
  );
  const localizedChecks = useMemo(
    () =>
      selfCheck?.checks.map((item) => ({
        ...item,
        localizedName: localizeCheckName(item.name),
        localizedStatus: localizeSystemStatus(item.status),
        localizedSummary: localizeCheckSummary(item),
      })) ?? [],
    [selfCheck],
  );

  const loadAll = async (mode: "initial" | "refresh" = "refresh") => {
    if (mode === "initial") {
      setLoading(true);
    } else {
      setRefreshing(true);
    }
    try {
      const [
        overviewPayload,
        selfCheckPayload,
        fallbackPayload,
        providerPayload,
        systemAgentPayload,
      ] = await Promise.all([
        api.getSystemOverview(),
        api.runSystemSelfCheck(),
        api.getProviderFallback(),
        api.listProviders(),
        request<SystemAgentProfile[]>(SYSTEM_AGENTS_ROUTE).catch(() => []),
      ]);
      setOverview(overviewPayload);
      setSelfCheck(selfCheckPayload);
      setFallbackConfig(fallbackPayload);
      setProviders(providerPayload);
      setSystemAgents(Array.isArray(systemAgentPayload) ? systemAgentPayload : []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void loadAll("initial");
  }, []);

  const runSelfCheck = async () => {
    setRunningSelfCheck(true);
    try {
      const payload = await api.runSystemSelfCheck();
      setSelfCheck(payload);
      message.success("自检已完成");
    } catch (err) {
      message.error(err instanceof Error ? err.message : String(err));
    } finally {
      setRunningSelfCheck(false);
    }
  };

  const downloadBackup = async () => {
    try {
      const blob = await api.downloadSystemBackup();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `copaw-backup-${new Date().toISOString().replace(/[:.]/g, "-")}.zip`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      message.success("备份下载已开始");
    } catch (err) {
      message.error(err instanceof Error ? err.message : String(err));
    }
  };

  const restoreBackup = async () => {
    const file = restoreFiles[0]?.originFileObj;
    if (!file) {
      message.warning("请先选择备份文件");
      return;
    }
    setRestoringBackup(true);
    try {
      await api.restoreSystemBackup(file as File);
      message.success("备份恢复成功");
      setRestoreFiles([]);
      await loadAll();
    } catch (err) {
      message.error(err instanceof Error ? err.message : String(err));
    } finally {
      setRestoringBackup(false);
    }
  };

  const updateCandidate = (index: number, value: string) => {
    const next = [...fallbackConfig.candidates];
    next[index] = parseCandidate(value);
    setFallbackConfig({ ...fallbackConfig, candidates: next });
  };

  const addCandidate = () => {
    if (modelOptions.length === 0) {
      message.warning("当前还没有可用的提供商模型");
      return;
    }
    const first = modelOptions[0];
    setFallbackConfig((current) => ({
      ...current,
      candidates: [...current.candidates, { provider_id: first.provider_id, model: first.model }],
    }));
  };

  const removeCandidate = (index: number) => {
    setFallbackConfig((current) => ({
      ...current,
      candidates: current.candidates.filter((_, currentIndex) => currentIndex !== index),
    }));
  };

  const saveFallback = async () => {
    setSavingFallback(true);
    try {
      const payload = await api.setProviderFallback(fallbackConfig);
      setFallbackConfig(payload);
      message.success("回退策略已保存");
      await loadAll();
    } catch (err) {
      message.error(err instanceof Error ? err.message : String(err));
    } finally {
      setSavingFallback(false);
    }
  };

  if (loading) {
    return (
      <div className={styles.loadingWrap}>
        <Spin />
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <Card className="baize-page-header">
        <div className="baize-page-header-content">
          <div>
            <h1 className="baize-page-header-title">系统</h1>
            <p className="baize-page-header-description">管理备份恢复、启动自检和模型回退链。</p>
          </div>
          <div className="baize-page-header-actions">
            <Button icon={<RefreshCw size={14} />} loading={refreshing} onClick={() => void loadAll()}>
              刷新
            </Button>
            <Button icon={<Activity size={14} />} loading={runningSelfCheck} onClick={() => void runSelfCheck()}>
              执行自检
            </Button>
          </div>
        </div>
      </Card>

      {error ? (
        <Alert
          type="error"
          showIcon
          message={"系统页面当前不可用"}
          description={error}
        />
      ) : null}

      <section className={styles.metrics}>
        <Card className={`${styles.metricCard} baize-card baize-depth-card`}>
          <Statistic
            title={"备份文件数"}
            value={overview?.backup.file_count ?? 0}
            prefix={<HardDriveDownload size={16} />}
          />
        </Card>
        <Card className={`${styles.metricCard} baize-card baize-depth-card`}>
          <Statistic
            title={"工作区大小"}
            value={formatBytes(overview?.backup.total_size)}
            prefix={<Layers3 size={16} />}
          />
        </Card>
        <Card className={`${styles.metricCard} baize-card baize-depth-card`}>
          <Statistic
            title={"回退候选数"}
            value={fallbackConfig.candidates.length}
            prefix={<ServerCrash size={16} />}
          />
        </Card>
        <Card className={`${styles.metricCard} baize-card baize-depth-card`}>
          <Statistic
            title={"健康检查项"}
            value={selfCheck?.checks.length ?? 0}
            prefix={<ShieldCheck size={16} />}
          />
        </Card>
      </section>

      <section className={styles.grid}>
        <Card className={`${styles.panelCard} baize-card baize-depth-card`}>
          <Space direction="vertical" size={18} style={{ width: "100%" }}>
            <div>
              <Typography.Title level={4} className={styles.sectionTitle}>
                {"平台中枢"}
              </Typography.Title>
              <Typography.Paragraph className={styles.sectionDescription}>
                {"系统页现在只保留调度与治理中枢；Spider Mesh 主脑已经收口到身份工作面。"}
              </Typography.Paragraph>
            </div>
            {systemAgents.length > 0 ? (
              <List
                dataSource={systemAgents}
                renderItem={(agent) => (
                  <List.Item className={styles.checkRow}>
                    <Space direction="vertical" size={4} style={{ width: "100%" }}>
                      <Space size={8} wrap>
                        <span className={styles.checkTitle}>{agent.name}</span>
                        <Tag>{agent.role_name}</Tag>
                        <Tag color={runtimeStatusColor(agent.status)}>
                          {localizeRuntimeStatus(agent.status)}
                        </Tag>
                        <Tag color={runtimeRiskColor(agent.risk_level)}>
                          {localizeRiskLevel(agent.risk_level)}
                        </Tag>
                      </Space>
                      <Typography.Text type="secondary">
                        {agent.current_focus || agent.role_summary}
                      </Typography.Text>
                      <Typography.Text type="secondary">
                        {agent.agent_id}
                      </Typography.Text>
                    </Space>
                  </List.Item>
                )}
              />
            ) : (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={"当前没有可见的平台中枢。"}
              />
            )}
          </Space>
        </Card>

        <Card className={`${styles.panelCard} baize-card baize-depth-card`}>
          <Space direction="vertical" size={18} style={{ width: "100%" }}>
            <div>
              <Typography.Title level={4} className={styles.sectionTitle}>
                {"备份与恢复"}
              </Typography.Title>
              <Typography.Paragraph className={styles.sectionDescription}>
                {"把当前工作区下载为系统备份，或把历史归档恢复回本地运行时。"}
              </Typography.Paragraph>
            </div>
            <div className={styles.kvList}>
              <div>
                <span>{"工作区"}</span>
                <code>{overview?.backup.root_path}</code>
              </div>
              <div>
                <span>{"状态库"}</span>
                <code>{overview?.self_check.state_db_path}</code>
              </div>
              <div>
                <span>{"证据库"}</span>
                <code>{overview?.self_check.evidence_db_path}</code>
              </div>
            </div>
            <Space wrap>
              <Button type="primary" className="baize-btn" icon={<Download size={14} />} onClick={() => void downloadBackup()}>
                {"下载"}
              </Button>
              <Upload
                beforeUpload={(file) => {
                  setRestoreFiles([
                    {
                      uid: file.uid,
                      name: file.name,
                      status: "done",
                      originFileObj: file,
                    },
                  ]);
                  return false;
                }}
                fileList={restoreFiles}
                onRemove={() => {
                  setRestoreFiles([]);
                  return true;
                }}
                maxCount={1}
              >
                <Button icon={<UploadCloud size={14} />}>
                  {"上传"}
                </Button>
              </Upload>
              <Button type="primary" className="baize-btn" ghost loading={restoringBackup} onClick={() => void restoreBackup()}>
                {"恢复备份"}
              </Button>
            </Space>
          </Space>
        </Card>

        <Card className={`${styles.panelCard} baize-card baize-depth-card`}>
          <Space direction="vertical" size={18} style={{ width: "100%" }}>
            <div>
              <Typography.Title level={4} className={styles.sectionTitle}>
                {"启动恢复与健康状态"}
              </Typography.Title>
              <Typography.Paragraph className={styles.sectionDescription}>
                {"在恢复运行或排查问题前，先查看最近一次恢复摘要和当前自检矩阵。"}
              </Typography.Paragraph>
            </div>
            {recoverySummary ? (
              <div className={styles.recoveryGrid}>
                {localizedRecoveryEntries.map(({ key, label, value }) => (
                  <div key={key} className={styles.recoveryItem}>
                    <span className={styles.recoveryLabel}>{label}</span>
                    <strong>{value}</strong>
                  </div>
                ))}
              </div>
            ) : (
              <Alert
                showIcon
                type="warning"
                message={"当前没有启动恢复摘要"}
              />
            )}
            {selfCheck ? (
              <>
                <Tag color={statusColor(selfCheck.overall_status)} className={styles.statusTag}>
                  {localizeSystemStatus(selfCheck.overall_status)}
                </Tag>
                <List
                  dataSource={localizedChecks}
                  renderItem={(item) => (
                    <List.Item className={styles.checkRow}>
                      <Space direction="vertical" size={4} style={{ width: "100%" }}>
                        <Space size={8} wrap>
                          <span className={styles.checkTitle}>{item.localizedName}</span>
                          <Tag color={statusColor(item.status)}>{item.localizedStatus}</Tag>
                        </Space>
                        <Typography.Text type="secondary">
                          {item.localizedSummary}
                        </Typography.Text>
                      </Space>
                    </List.Item>
                  )}
                />
              </>
            ) : (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={"当前没有自检结果"} />
            )}
          </Space>
        </Card>
      </section>

      <section className={styles.grid}>
        <Card className={`${styles.panelCard} baize-card baize-depth-card`}>
          <Space direction="vertical" size={18} style={{ width: "100%" }}>
            <div>
              <Typography.Title level={4} className={styles.sectionTitle}>
                {"提供商回退"}
              </Typography.Title>
              <Typography.Paragraph className={styles.sectionDescription}>
                {"定义当当前模型不可用时，运行时可以接管的提供商 / 模型链。"}
              </Typography.Paragraph>
            </div>
            <div className={styles.toggleRow}>
              <Space size={10}>
                {fallbackConfig.enabled ? <ShieldCheck size={16} /> : <ShieldX size={16} />}
                <span>{"启用回退链"}</span>
              </Space>
              <Switch
                checked={fallbackConfig.enabled}
                onChange={(checked) => setFallbackConfig((current) => ({ ...current, enabled: checked }))}
              />
            </div>
            <div className={styles.candidateStack}>
              {fallbackConfig.candidates.map((candidate, index) => {
                const currentValue = `${candidate.provider_id}::${candidate.model}`;
                return (
                  <div key={`${candidate.provider_id}:${candidate.model}:${index}`} className={styles.candidateRow}>
                    <Select
                      value={currentValue}
                      options={modelOptions}
                      style={{ flex: 1 }}
                      onChange={(value) => updateCandidate(index, value)}
                    />
                    <Button danger icon={<Trash2 size={14} />} onClick={() => removeCandidate(index)} />
                  </div>
                );
              })}
              {fallbackConfig.candidates.length === 0 ? (
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description={"还没有配置回退候选"}
                />
              ) : null}
            </div>
            <Space wrap>
              <Button icon={<Plus size={14} />} onClick={addCandidate}>
                {"添加候选"}
              </Button>
              <Button type="primary" className="baize-btn" loading={savingFallback} onClick={() => void saveFallback()}>
                {"保存"}
              </Button>
            </Space>
          </Space>
        </Card>

        <Card className={`${styles.panelCard} baize-card baize-depth-card`}>
          <Space direction="vertical" size={18} style={{ width: "100%" }}>
            <div>
              <Typography.Title level={4} className={styles.sectionTitle}>
                {"运行时链接"}
              </Typography.Title>
              <Typography.Paragraph className={styles.sectionDescription}>
                {"V3 后端当前暴露的治理、恢复和事件流正式路由。"}
              </Typography.Paragraph>
            </div>
            <div className={styles.kvList}>
              <div>
                <span>{"当前模型"}</span>
                <code>
                  {overview?.providers.active_model
                    ? `${overview.providers.active_model.provider_id} / ${overview.providers.active_model.model}`
                    : "-"}
                </code>
              </div>
              <div>
                <span>{"治理"}</span>
                <code>{overview?.runtime.governance_route}</code>
              </div>
              <div>
                <span>{"恢复"}</span>
                <code>{overview?.runtime.recovery_route}</code>
              </div>
              <div>
                <span>{"事件流"}</span>
                <code>{overview?.runtime.events_route}</code>
              </div>
            </div>
          </Space>
        </Card>
      </section>
    </div>
  );
}


