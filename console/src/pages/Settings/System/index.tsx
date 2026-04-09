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
  Layers3,
  Plus,
  RefreshCw,
  ServerCrash,
  ShieldCheck,
  ShieldX,
  Trash2,
  UploadCloud,
} from "lucide-react";

import api from "../../../api";
import type {
  ProviderFallbackConfig,
  ProviderInfo,
  SystemOverview,
  SystemSelfCheck,
} from "../../../api/types";
import styles from "./index.module.less";

function statusColor(status: string) {
  if (status === "pass") return "success";
  if (status === "warn") return "warning";
  if (status === "fail") return "error";
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

function humanizeToken(value: string) {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (chunk) => chunk.toUpperCase());
}

function localizeSystemStatus(status: string) {
  const map: Record<string, string> = {
    pass: "通过",
    warn: "警告",
    fail: "失败",
  };
  return map[status] || humanizeToken(status);
}

function localizeCheckName(name: string) {
  const map: Record<string, string> = {
    working_dir: "工作目录",
    state_store: "状态存储",
    evidence_ledger: "证据账本",
    core_runtime_ready: "核心运行时就绪",
    browser_surface_ready: "浏览器执行面",
    desktop_surface_ready: "桌面执行面",
    kernel_dispatcher: "内核分发器",
    runtime_event_bus: "运行事件总线",
    cron_manager: "定时任务管理",
    provider_active_model: "当前激活模型",
    provider_fallback: "提供商回退",
    startup_recovery: "启动恢复检查",
  };
  return map[name] || humanizeToken(name);
}

function localizeCheckSummary(item: SystemSelfCheck["checks"][number]) {
  const meta = item.meta || {};
  if (item.name === "working_dir") {
    return item.status === "pass" ? "工作目录可用。" : "工作目录缺失。";
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
  if (item.name === "provider_active_model") {
    const activeModel = meta.active_model as { provider_id?: string | null } | undefined;
    return item.status === "pass"
      ? `当前激活模型提供商：${activeModel?.provider_id || "-"}`
      : "未检测到激活模型提供商。";
  }
  if (item.name === "provider_fallback") {
    return item.status === "pass"
      ? "提供商回退链路可用。"
      : item.status === "warn"
        ? "提供商回退链路存在警告。"
        : "提供商回退链路不可用。";
  }
  if (item.name === "startup_recovery") {
    return item.status === "pass"
      ? "启动恢复检查正常。"
      : item.status === "warn"
        ? "启动恢复检查存在警告。"
        : "启动恢复检查失败。";
  }
  return item.summary;
}

const MAINTENANCE_CHECK_NAMES = new Set<string>([
  "working_dir",
  "state_store",
  "evidence_ledger",
  "provider_active_model",
  "provider_fallback",
]);

function isMaintenanceCheck(name: string) {
  return MAINTENANCE_CHECK_NAMES.has(name);
}

function summarizeMaintenanceStatus(
  checks: SystemSelfCheck["checks"],
): SystemSelfCheck["overall_status"] {
  if (checks.some((item) => item.status === "fail")) return "fail";
  if (checks.some((item) => item.status === "warn")) return "warn";
  return "pass";
}

export default function SystemSettingsPage() {
  const [overview, setOverview] = useState<SystemOverview | null>(null);
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
  const maintenanceChecks = useMemo(
    () => selfCheck?.checks.filter((item) => isMaintenanceCheck(item.name)) ?? [],
    [selfCheck],
  );
  const maintenanceOverallStatus = useMemo(
    () => summarizeMaintenanceStatus(maintenanceChecks),
    [maintenanceChecks],
  );
  const localizedChecks = useMemo(
    () =>
      maintenanceChecks.map((item) => ({
        ...item,
        localizedName: localizeCheckName(item.name),
        localizedStatus: localizeSystemStatus(item.status),
        localizedSummary: localizeCheckSummary(item),
      })),
    [maintenanceChecks],
  );

  const loadAll = async (mode: "initial" | "refresh" = "refresh") => {
    if (mode === "initial") {
      setLoading(true);
    } else {
      setRefreshing(true);
    }
    try {
      const [overviewPayload, selfCheckPayload, fallbackPayload, providerPayload] =
        await Promise.all([
          api.getSystemOverview(),
          api.runSystemSelfCheck(),
          api.getProviderFallback(),
          api.listProviders(),
        ]);
      setOverview(overviewPayload);
      setSelfCheck(selfCheckPayload);
      setFallbackConfig(fallbackPayload);
      setProviders(providerPayload);
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
      candidates: [
        ...current.candidates,
        { provider_id: first.provider_id, model: first.model },
      ],
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
            <h1 className="baize-page-header-title">系统维护</h1>
            <p className="baize-page-header-description">
              管理备份恢复、自检健康和提供商回退。正式运行事实、治理和恢复闭环统一前往主脑驾驶舱。
            </p>
          </div>
          <div className="baize-page-header-actions">
            <Button
              icon={<RefreshCw size={14} />}
              loading={refreshing}
              onClick={() => void loadAll()}
            >
              刷新
            </Button>
            <Button
              icon={<Activity size={14} />}
              loading={runningSelfCheck}
              onClick={() => void runSelfCheck()}
            >
              执行自检
            </Button>
          </div>
        </div>
      </Card>

      {error ? (
        <Alert
          type="error"
          showIcon
          message="系统页面当前不可用"
          description={error}
        />
      ) : null}

      <Alert
        type="info"
        showIcon
        message="运行事实请前往主脑驾驶舱"
        description={
          <Space size={12} wrap>
            <span>系统维护页只保留维护、自检和回退设置，不再承载正式运行事实摘要。</span>
            <Button type="link" href="/runtime-center" style={{ paddingInline: 0 }}>
              前往主脑驾驶舱
            </Button>
          </Space>
        }
      />

      <section className={styles.metrics}>
        <Card className={`${styles.metricCard} baize-card baize-depth-card`}>
          <Statistic
            title="备份文件数"
            value={overview?.backup.file_count ?? 0}
            prefix={<HardDriveDownload size={16} />}
          />
        </Card>
        <Card className={`${styles.metricCard} baize-card baize-depth-card`}>
          <Statistic
            title="工作区大小"
            value={formatBytes(overview?.backup.total_size)}
            prefix={<Layers3 size={16} />}
          />
        </Card>
        <Card className={`${styles.metricCard} baize-card baize-depth-card`}>
          <Statistic
            title="回退候选数"
            value={fallbackConfig.candidates.length}
            prefix={<ServerCrash size={16} />}
          />
        </Card>
        <Card className={`${styles.metricCard} baize-card baize-depth-card`}>
          <Statistic
            title="健康检查项"
            value={maintenanceChecks.length}
            prefix={<ShieldCheck size={16} />}
          />
        </Card>
      </section>

      <section className={styles.grid}>
        <Card className={`${styles.panelCard} baize-card baize-depth-card`}>
          <Space direction="vertical" size={18} style={{ width: "100%" }}>
            <div>
              <Typography.Title level={4} className={styles.sectionTitle}>
                备份与恢复
              </Typography.Title>
              <Typography.Paragraph className={styles.sectionDescription}>
                下载当前工作区的系统备份，或把历史归档恢复回本地运行时。
              </Typography.Paragraph>
            </div>
            <div className={styles.kvList}>
              <div>
                <span>工作区</span>
                <code>{overview?.backup.root_path}</code>
              </div>
              <div>
                <span>状态库</span>
                <code>{overview?.self_check.state_db_path}</code>
              </div>
              <div>
                <span>证据库</span>
                <code>{overview?.self_check.evidence_db_path}</code>
              </div>
            </div>
            <Space wrap>
              <Button
                type="primary"
                className="baize-btn"
                icon={<Download size={14} />}
                onClick={() => void downloadBackup()}
              >
                下载
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
                <Button icon={<UploadCloud size={14} />}>上传</Button>
              </Upload>
              <Button
                type="primary"
                className="baize-btn"
                ghost
                loading={restoringBackup}
                onClick={() => void restoreBackup()}
              >
                恢复备份
              </Button>
            </Space>
          </Space>
        </Card>

        <Card className={`${styles.panelCard} baize-card baize-depth-card`}>
          <Space direction="vertical" size={18} style={{ width: "100%" }}>
            <div>
              <Typography.Title level={4} className={styles.sectionTitle}>
                健康自检与维护
              </Typography.Title>
              <Typography.Paragraph className={styles.sectionDescription}>
                这里只保留系统维护需要的自检结果；正式恢复事实、治理状态和运行闭环请去主脑驾驶舱查看。
              </Typography.Paragraph>
            </div>
            {selfCheck ? (
              <>
                <Tag color={statusColor(maintenanceOverallStatus)} className={styles.statusTag}>
                  {localizeSystemStatus(maintenanceOverallStatus)}
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
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前没有自检结果" />
            )}
          </Space>
        </Card>
      </section>

      <section className={styles.grid}>
        <Card className={`${styles.panelCard} baize-card baize-depth-card`}>
          <Space direction="vertical" size={18} style={{ width: "100%" }}>
            <div>
              <Typography.Title level={4} className={styles.sectionTitle}>
                提供商回退
              </Typography.Title>
              <Typography.Paragraph className={styles.sectionDescription}>
                定义当前模型不可用时，系统可接管的提供商 / 模型链路。
              </Typography.Paragraph>
            </div>
            <div className={styles.toggleRow}>
              <Space size={10}>
                {fallbackConfig.enabled ? <ShieldCheck size={16} /> : <ShieldX size={16} />}
                <span>启用回退链</span>
              </Space>
              <Switch
                checked={fallbackConfig.enabled}
                onChange={(checked) =>
                  setFallbackConfig((current) => ({ ...current, enabled: checked }))
                }
              />
            </div>
            <div className={styles.candidateStack}>
              {fallbackConfig.candidates.map((candidate, index) => {
                const currentValue = `${candidate.provider_id}::${candidate.model}`;
                return (
                  <div
                    key={`${candidate.provider_id}:${candidate.model}:${index}`}
                    className={styles.candidateRow}
                  >
                    <Select
                      value={currentValue}
                      options={modelOptions}
                      style={{ flex: 1 }}
                      onChange={(value) => updateCandidate(index, value)}
                    />
                    <Button
                      danger
                      icon={<Trash2 size={14} />}
                      onClick={() => removeCandidate(index)}
                    />
                  </div>
                );
              })}
              {fallbackConfig.candidates.length === 0 ? (
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description="还没有配置回退候选。"
                />
              ) : null}
            </div>
            <Space wrap>
              <Button icon={<Plus size={14} />} onClick={addCandidate}>
                添加候选
              </Button>
              <Button
                type="primary"
                className="baize-btn"
                loading={savingFallback}
                onClick={() => void saveFallback()}
              >
                保存回退策略
              </Button>
            </Space>
          </Space>
        </Card>
      </section>
    </div>
  );
}
