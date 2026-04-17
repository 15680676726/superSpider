import {
  Alert,
  Button,
  Card,
  Empty,
  Space,
  Tabs,
  Tag,
  message,
} from "antd";
import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw, RotateCcw, ShieldAlert, ShieldCheck } from "lucide-react";

import {
  api,
  type GovernanceStatus,
  type RuntimeChannelRuntimeRecord,
  type StartupRecoverySummary,
  type SystemSelfCheck,
} from "../../api";
import { normalizeDisplayChinese } from "../../text";
import { presentRuntimeStatusLabel } from "../../runtime/executionPresentation";
import { runtimeStatusColor } from "../../runtime/tagSemantics";
import AutomationTab from "./AutomationTab";
import styles from "./index.module.less";

type SystemManagementTabKey =
  | "automation"
  | "governance"
  | "channels"
  | "recovery";

export interface MainBrainSystemManagementProps {
  focusScope?: string | null;
  refreshSignal?: string | null;
  channelRuntimes?: RuntimeChannelRuntimeRecord[];
  onOpenDetail: (route: string, title: string) => void;
  onRuntimeChanged?: () => void;
}

const DEFAULT_ACTOR = "runtime-center";

function numberValue(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function textValue(value: unknown, fallback = "暂无"): string {
  if (typeof value === "string" && value.trim()) {
    return normalizeDisplayChinese(value.trim());
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return String(value);
  }
  return fallback;
}

function channelLabel(channel: string): string {
  if (channel === "weixin_ilink") {
    return "微信个人（iLink）";
  }
  return normalizeDisplayChinese(channel || "未知渠道");
}

function channelRuntimeStatusLabel(status?: string): string {
  switch ((status || "").trim()) {
    case "waiting_scan":
      return "等待扫码";
    case "authorized_pending_save":
      return "已授权，待保存";
    case "auth_expired":
      return "授权失效";
    case "running":
      return "运行中";
    case "stopped":
      return "未运行";
    case "unconfigured":
      return "未配置";
    default:
      return normalizeDisplayChinese(status || "未知");
  }
}

function recoveryMetricItems(summary: StartupRecoverySummary | null) {
  if (!summary) {
    return [];
  }

  return [
    { label: "恢复原因", value: textValue(summary.reason, "启动恢复") },
    {
      label: "过期决策",
      value: String(numberValue(summary.expired_decisions)),
    },
    {
      label: "恢复任务",
      value: String(numberValue(summary.hydrated_waiting_tasks)),
    },
    {
      label: "恢复计划",
      value: String(numberValue(summary.resumed_schedules)),
    },
  ];
}

export default function MainBrainSystemManagement({
  focusScope,
  refreshSignal,
  channelRuntimes = [],
  onOpenDetail,
  onRuntimeChanged,
}: MainBrainSystemManagementProps) {
  const [activeTab, setActiveTab] = useState<SystemManagementTabKey>("automation");
  const [governanceStatus, setGovernanceStatus] = useState<GovernanceStatus | null>(
    null,
  );
  const [governanceLoading, setGovernanceLoading] = useState(false);
  const [governanceError, setGovernanceError] = useState<string | null>(null);
  const [governanceBusyKey, setGovernanceBusyKey] = useState<string | null>(null);
  const [recoverySummary, setRecoverySummary] =
    useState<StartupRecoverySummary | null>(null);
  const [selfCheck, setSelfCheck] = useState<SystemSelfCheck | null>(null);
  const [recoveryLoading, setRecoveryLoading] = useState(false);
  const [recoveryBusyKey, setRecoveryBusyKey] = useState<string | null>(null);
  const [recoveryError, setRecoveryError] = useState<string | null>(null);

  const loadGovernance = useCallback(async () => {
    setGovernanceLoading(true);
    try {
      const payload = await api.getGovernanceStatus();
      setGovernanceStatus(payload);
      setGovernanceError(null);
    } catch (error) {
      setGovernanceError(
        normalizeDisplayChinese(
          error instanceof Error ? error.message : String(error),
        ),
      );
    } finally {
      setGovernanceLoading(false);
    }
  }, []);

  const loadRecovery = useCallback(async () => {
    setRecoveryLoading(true);
    try {
      const [recoveryPayload, selfCheckPayload] = await Promise.all([
        api.getLatestRecoveryReport(),
        api.runSystemSelfCheck(),
      ]);
      setRecoverySummary(recoveryPayload);
      setSelfCheck(selfCheckPayload);
      setRecoveryError(null);
    } catch (error) {
      setRecoveryError(
        normalizeDisplayChinese(
          error instanceof Error ? error.message : String(error),
        ),
      );
    } finally {
      setRecoveryLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === "governance") {
      void loadGovernance();
    }
    if (activeTab === "recovery") {
      void loadRecovery();
    }
  }, [activeTab, loadGovernance, loadRecovery, refreshSignal]);

  const handleGovernanceAction = useCallback(
    async (key: "emergency-stop" | "resume") => {
      setGovernanceBusyKey(key);
      try {
        if (key === "emergency-stop") {
          await api.emergencyStopRuntime({
            actor: DEFAULT_ACTOR,
            reason: "运行中心手动暂停运行",
          });
          message.success("已提交紧急暂停");
        } else {
          await api.resumeGovernedRuntime({
            actor: DEFAULT_ACTOR,
            reason: "运行中心手动恢复运行",
          });
          message.success("已提交恢复运行");
        }
        await loadGovernance();
        onRuntimeChanged?.();
      } catch (error) {
        message.error(
          normalizeDisplayChinese(
            error instanceof Error ? error.message : String(error),
          ),
        );
      } finally {
        setGovernanceBusyKey(null);
      }
    },
    [loadGovernance, onRuntimeChanged],
  );

  const handleSelfCheck = useCallback(async () => {
    setRecoveryBusyKey("self-check");
    try {
      const payload = await api.runSystemSelfCheck();
      setSelfCheck(payload);
      message.success("系统自检已完成");
    } catch (error) {
      message.error(
        normalizeDisplayChinese(
          error instanceof Error ? error.message : String(error),
        ),
      );
    } finally {
      setRecoveryBusyKey(null);
    }
  }, []);

  const recoveryMetrics = useMemo(
    () => recoveryMetricItems(recoverySummary),
    [recoverySummary],
  );

  return (
    <div className={styles.systemManagementWrap}>
      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as SystemManagementTabKey)}
        items={[
          { key: "automation", label: "自动化" },
          { key: "governance", label: "治理" },
          { key: "channels", label: "渠道" },
          { key: "recovery", label: "恢复" },
        ]}
      />

      {activeTab === "automation" ? (
        <AutomationTab
          focusScope={focusScope}
          refreshSignal={refreshSignal ?? undefined}
          openDetail={async (route, title) => {
            onOpenDetail(route, title);
          }}
          onRuntimeChanged={onRuntimeChanged ?? (() => undefined)}
        />
      ) : null}

      {activeTab === "governance" ? (
        <div className={styles.systemPanelStack}>
          {governanceError ? <Alert showIcon type="error" message={governanceError} /> : null}

          <div className={styles.systemMetricGrid}>
            <Card className={styles.systemMetricCard}>
              <div className={styles.systemMetricIcon}>
                {governanceStatus?.emergency_stop_active ? (
                  <ShieldAlert size={18} />
                ) : (
                  <ShieldCheck size={18} />
                )}
              </div>
              <div className={styles.systemMetricLabel}>系统状态</div>
              <div className={styles.systemMetricValue}>
                {governanceStatus?.emergency_stop_active ? "已暂停" : "运行中"}
              </div>
            </Card>

            <Card className={styles.systemMetricCard}>
              <div className={styles.systemMetricIcon}>
                <ShieldAlert size={18} />
              </div>
              <div className={styles.systemMetricLabel}>待处理决策</div>
              <div className={styles.systemMetricValue}>
                {numberValue(governanceStatus?.pending_decisions)}
              </div>
            </Card>

            <Card className={styles.systemMetricCard}>
              <div className={styles.systemMetricIcon}>
                <RotateCcw size={18} />
              </div>
              <div className={styles.systemMetricLabel}>待处理补丁</div>
              <div className={styles.systemMetricValue}>
                {numberValue(governanceStatus?.pending_patches)}
              </div>
            </Card>

            <Card className={styles.systemMetricCard}>
              <div className={styles.systemMetricIcon}>
                <RefreshCw size={18} />
              </div>
              <div className={styles.systemMetricLabel}>暂停计划</div>
              <div className={styles.systemMetricValue}>
                {governanceStatus?.paused_schedule_ids.length ?? 0}
              </div>
            </Card>
          </div>

          <Card className="baize-card">
            <div className={styles.panelHeader}>
              <div>
                <h3 className={styles.cardTitle}>治理控制</h3>
                <p className={styles.cardSummary}>
                  这里只保留需要人工拍板的系统级控制项。
                </p>
              </div>
              <Space size={8}>
                <Tag color={governanceStatus?.emergency_stop_active ? "error" : "success"}>
                  {governanceStatus?.emergency_stop_active ? "已暂停" : "可继续运行"}
                </Tag>
                <Button
                  size="small"
                  icon={<RefreshCw size={14} />}
                  loading={governanceLoading}
                  onClick={() => {
                    void loadGovernance();
                  }}
                >
                  刷新
                </Button>
              </Space>
            </div>

            <div className={styles.systemActionRow}>
              <Button
                danger
                type="primary"
                loading={governanceBusyKey === "emergency-stop"}
                onClick={() => {
                  void handleGovernanceAction("emergency-stop");
                }}
              >
                紧急暂停
              </Button>
              <Button
                loading={governanceBusyKey === "resume"}
                onClick={() => {
                  void handleGovernanceAction("resume");
                }}
              >
                恢复运行
              </Button>
              <Button
                onClick={() => {
                  onOpenDetail("/api/runtime-center/governance/status", "治理详情");
                }}
              >
                查看详情
              </Button>
            </div>

            <div className={styles.systemNoteList}>
              <div className={styles.systemNoteItem}>
                <span>当前状态</span>
                <strong>
                  {governanceStatus
                    ? presentRuntimeStatusLabel(
                        governanceStatus.emergency_stop_active ? "paused" : "running",
                      )
                    : "加载中"}
                </strong>
              </div>
              <div className={styles.systemNoteItem}>
                <span>阻断能力</span>
                <strong>{governanceStatus?.blocked_capability_refs.length ?? 0}</strong>
              </div>
              <div className={styles.systemNoteItem}>
                <span>渠道停机</span>
                <strong>{governanceStatus?.channel_shutdown_applied ? "是" : "否"}</strong>
              </div>
              <div className={styles.systemNoteItem}>
                <span>最后更新</span>
                <strong>{textValue(governanceStatus?.updated_at, "暂无")}</strong>
              </div>
            </div>
          </Card>
        </div>
      ) : null}

      {activeTab === "channels" ? (
        <div className={styles.systemPanelStack}>
          <Card className="baize-card">
            <div className={styles.panelHeader}>
              <div>
                <h3 className={styles.cardTitle}>渠道运行态</h3>
                <p className={styles.cardSummary}>
                  把正式消息通道的登录态和轮询态纳入运行中心，不再只藏在设置页。
                </p>
              </div>
              <Space size={8}>
                <Button
                  size="small"
                  icon={<RefreshCw size={14} />}
                  onClick={() => {
                    onRuntimeChanged?.();
                  }}
                >
                  刷新
                </Button>
              </Space>
            </div>

            {channelRuntimes.length === 0 ? (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="暂无渠道运行态"
              />
            ) : (
              <div className={styles.systemCheckList}>
                {channelRuntimes.map((runtime) => (
                  <div
                    key={`${runtime.channel}:${runtime.route}`}
                    className={styles.systemCheckItem}
                  >
                    <div>
                      <div className={styles.systemCheckName}>
                        {channelLabel(runtime.channel)}
                      </div>
                      <div className={styles.systemCheckSummary}>
                        {`登录 ${channelRuntimeStatusLabel(runtime.login_status)} | 轮询 ${channelRuntimeStatusLabel(runtime.polling_status)}`}
                      </div>
                      {runtime.qrcode ? (
                        <div className={styles.systemCheckSummary}>
                          {`当前二维码：${runtime.qrcode}`}
                        </div>
                      ) : null}
                      {runtime.last_error ? (
                        <div className={styles.systemCheckSummary}>
                          {`最近错误：${normalizeDisplayChinese(runtime.last_error)}`}
                        </div>
                      ) : null}
                    </div>
                    <Space size={8}>
                      <Tag color={runtimeStatusColor(runtime.polling_status || "unknown")}>
                        {channelRuntimeStatusLabel(runtime.polling_status)}
                      </Tag>
                      <Tag color={runtimeStatusColor(runtime.login_status || "unknown")}>
                        {channelRuntimeStatusLabel(runtime.login_status)}
                      </Tag>
                      <Button
                        size="small"
                        onClick={() => {
                          onOpenDetail(
                            runtime.route,
                            `${channelLabel(runtime.channel)} 运行态`,
                          );
                        }}
                      >
                        查看详情
                      </Button>
                    </Space>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      ) : null}

      {activeTab === "recovery" ? (
        <div className={styles.systemPanelStack}>
          {recoveryError ? <Alert showIcon type="error" message={recoveryError} /> : null}

          <div className={styles.systemMetricGrid}>
            {recoveryMetrics.length > 0 ? (
              recoveryMetrics.map((item) => (
                <Card key={item.label} className={styles.systemMetricCard}>
                  <div className={styles.systemMetricLabel}>{item.label}</div>
                  <div className={styles.systemMetricValue}>{item.value}</div>
                </Card>
              ))
            ) : (
              <Card className={styles.systemMetricCard}>
                <div className={styles.systemMetricLabel}>恢复状态</div>
                <div className={styles.systemMetricValue}>暂无记录</div>
              </Card>
            )}
          </div>

          <Card className="baize-card">
            <div className={styles.panelHeader}>
              <div>
                <h3 className={styles.cardTitle}>恢复与自检</h3>
                <p className={styles.cardSummary}>
                  看系统是否恢复稳定，以及当前自检有没有异常。
                </p>
              </div>
              <Space size={8}>
                <Button
                  size="small"
                  icon={<RefreshCw size={14} />}
                  loading={recoveryLoading}
                  onClick={() => {
                    void loadRecovery();
                  }}
                >
                  刷新
                </Button>
                <Button
                  size="small"
                  loading={recoveryBusyKey === "self-check"}
                  onClick={() => {
                    void handleSelfCheck();
                  }}
                >
                  运行自检
                </Button>
                <Button
                  size="small"
                  onClick={() => {
                    onOpenDetail("/api/runtime-center/recovery/latest", "恢复详情");
                  }}
                >
                  查看详情
                </Button>
              </Space>
            </div>

            {recoveryLoading && !recoverySummary && !selfCheck ? (
              <div className={styles.cockpitEmptyWrap}>正在加载恢复状态...</div>
            ) : null}

            {selfCheck ? (
              <div className={styles.systemCheckList}>
                <div className={styles.systemCheckHeader}>
                  <Tag color={runtimeStatusColor(selfCheck.overall_status)}>
                    {presentRuntimeStatusLabel(selfCheck.overall_status)}
                  </Tag>
                  <span className={styles.systemCheckHint}>
                    共 {selfCheck.checks.length} 项检查
                  </span>
                </div>

                {selfCheck.checks.length > 0 ? (
                  selfCheck.checks.slice(0, 6).map((check) => (
                    <div key={check.name} className={styles.systemCheckItem}>
                      <div>
                        <div className={styles.systemCheckName}>
                          {normalizeDisplayChinese(check.name)}
                        </div>
                        <div className={styles.systemCheckSummary}>
                          {normalizeDisplayChinese(check.summary)}
                        </div>
                      </div>
                      <Tag color={runtimeStatusColor(check.status)}>
                        {presentRuntimeStatusLabel(check.status)}
                      </Tag>
                    </div>
                  ))
                ) : (
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description="暂无自检结果"
                  />
                )}
              </div>
            ) : null}
          </Card>
        </div>
      ) : null}
    </div>
  );
}
