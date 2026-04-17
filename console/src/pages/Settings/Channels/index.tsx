import { useMemo, useState } from "react";
import { Form, message } from "@/ui";

import api from "../../../api";
import type { WeixinILinkLoginRuntimeState } from "../../../api/types";
import {
  ChannelCard,
  ChannelDrawer,
  useChannels,
  getChannelLabel,
  type ChannelKey,
} from "./components";
import { PageHeader } from "../../../components/PageHeader";
import styles from "./index.module.less";

type FilterType = "all" | "builtin" | "custom";

function ChannelsPage() {
  const { channels, orderedKeys, isBuiltin, loading, fetchChannels } =
    useChannels();
  const [filter, setFilter] = useState<FilterType>("all");
  const [saving, setSaving] = useState(false);
  const [hoverKey, setHoverKey] = useState<ChannelKey | null>(null);
  const [activeKey, setActiveKey] = useState<ChannelKey | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [weixinLoginRuntime, setWeixinLoginRuntime] =
    useState<WeixinILinkLoginRuntimeState | null>(null);
  const [weixinLoginActionLoading, setWeixinLoginActionLoading] = useState<
    "qr" | "status" | "rebind" | null
  >(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [form] = Form.useForm<any>();

  const cards = useMemo(() => {
    const enabledCards: { key: ChannelKey; config: Record<string, unknown> }[] =
      [];
    const disabledCards: {
      key: ChannelKey;
      config: Record<string, unknown>;
    }[] = [];

    orderedKeys.forEach((key) => {
      const config = channels[key] || { enabled: false, bot_prefix: "" };
      const builtin = isBuiltin(key);
      if (filter === "builtin" && !builtin) return;
      if (filter === "custom" && builtin) return;
      if (config.enabled) {
        enabledCards.push({ key, config });
      } else {
        disabledCards.push({ key, config });
      }
    });

    return [...enabledCards, ...disabledCards];
  }, [channels, orderedKeys, filter, isBuiltin]);

  const applyWeixinLoginRuntime = (runtime: WeixinILinkLoginRuntimeState) => {
    setWeixinLoginRuntime(runtime);
    form.setFieldsValue({
      bot_token: runtime.bot_token || form.getFieldValue("bot_token"),
      base_url: runtime.base_url || form.getFieldValue("base_url"),
    });
  };

  const runWeixinLoginAction = async (
    action: "qr" | "status" | "rebind",
    request: () => Promise<WeixinILinkLoginRuntimeState>,
    successMessage: string,
  ) => {
    setWeixinLoginActionLoading(action);
    try {
      const runtime = await request();
      applyWeixinLoginRuntime(runtime);
      message.success(successMessage);
    } catch (error) {
      console.error(`Failed to run weixin iLink ${action}:`, error);
      message.error("微信个人（iLink）操作失败");
    } finally {
      setWeixinLoginActionLoading(null);
    }
  };

  const handleFetchWeixinLoginQr = async () =>
    runWeixinLoginAction(
      "qr",
      () => api.createWeixinILinkLoginQr(),
      "登录二维码已生成",
    );

  const handleRefreshWeixinLoginStatus = async () =>
    runWeixinLoginAction(
      "status",
      () => api.getWeixinILinkLoginStatus(),
      "已刷新登录状态",
    );

  const handleRebindWeixinLogin = async () =>
    runWeixinLoginAction(
      "rebind",
      () => api.rebindWeixinILinkLogin(),
      "已标记为重新扫码授权",
    );

  const handleCardClick = (key: ChannelKey) => {
    setActiveKey(key);
    setDrawerOpen(true);
    const channelConfig = channels[key] || { enabled: false, bot_prefix: "" };
    form.setFieldsValue({
      ...channelConfig,
      filter_tool_messages: !channelConfig.filter_tool_messages,
      filter_thinking: !channelConfig.filter_thinking,
    });
    if (key === "weixin_ilink") {
      void handleRefreshWeixinLoginStatus();
    } else {
      setWeixinLoginRuntime(null);
    }
  };

  const handleDrawerClose = () => {
    setDrawerOpen(false);
    setActiveKey(null);
    setWeixinLoginActionLoading(null);
  };

  const handleSubmit = async (values: Record<string, unknown>) => {
    if (!activeKey) return;

    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { isBuiltin: _isBuiltin, ...savedConfig } = channels[activeKey] || {};
    const updatedChannel: Record<string, unknown> = {
      ...savedConfig,
      ...values,
      filter_tool_messages: !values.filter_tool_messages,
      filter_thinking: !values.filter_thinking,
    };

    setSaving(true);
    try {
      await api.updateChannelConfig(
        activeKey,
        updatedChannel as unknown as Parameters<
          typeof api.updateChannelConfig
        >[1],
      );
      await fetchChannels();

      setDrawerOpen(false);
      message.success("配置保存成功");
    } catch (error) {
      console.error("Failed to update channel config:", error);
      message.error("配置保存失败");
    } finally {
      setSaving(false);
    }
  };

  const activeLabel = activeKey ? getChannelLabel(activeKey) : "";

  const FILTER_TABS: { key: FilterType; label: string }[] = [
    { key: "all", label: "全部" },
    { key: "builtin", label: "内置" },
    { key: "custom", label: "自定义" },
  ];
  const enabledCount = cards.filter(({ config }) => Boolean(config.enabled)).length;
  const customCount = cards.filter(({ key }) => !isBuiltin(key)).length;

  return (
    <div className={`${styles.channelsPage} page-container`}>
      <PageHeader
        eyebrow="渠道设置"
        title="渠道中心"
        description="管理和配置消息频道，让主脑的输入输出链路保持稳定。"
        stats={[
          { label: "当前可见", value: String(cards.length).padStart(2, "0") },
          { label: "已启用", value: String(enabledCount).padStart(2, "0") },
          { label: "自定义", value: String(customCount).padStart(2, "0") },
        ]}
        actions={(
          <div className={styles.filterTabs}>
            {FILTER_TABS.map(({ key, label }) => (
              <button
                key={key}
                className={`${styles.filterTab} ${
                  filter === key ? styles.filterTabActive : ""
                }`}
                onClick={() => setFilter(key)}
              >
                {label}
              </button>
            ))}
          </div>
        )}
      />

      {loading ? (
        <div className={styles.loading}>
          <span className={styles.loadingText}>{"正在加载频道..."}</span>
        </div>
      ) : (
        <div className={styles.channelsGrid}>
          {cards.map(({ key, config }) => (
            <ChannelCard
              key={key}
              channelKey={key}
              config={config}
              isHover={hoverKey === key}
              onClick={() => handleCardClick(key)}
              onMouseEnter={() => setHoverKey(key)}
              onMouseLeave={() => setHoverKey(null)}
            />
          ))}
        </div>
      )}

      <ChannelDrawer
        open={drawerOpen}
        activeKey={activeKey}
        activeLabel={activeLabel}
        form={form}
        saving={saving}
        initialValues={activeKey ? channels[activeKey] : undefined}
        isBuiltin={activeKey ? isBuiltin(activeKey) : true}
        loginRuntime={weixinLoginRuntime}
        loginActionLoading={weixinLoginActionLoading}
        onClose={handleDrawerClose}
        onSubmit={handleSubmit}
        onFetchWeixinLoginQr={() => {
          void handleFetchWeixinLoginQr();
        }}
        onRefreshWeixinLoginStatus={() => {
          void handleRefreshWeixinLoginStatus();
        }}
        onRebindWeixinLogin={() => {
          void handleRebindWeixinLogin();
        }}
      />
    </div>
  );
}

export default ChannelsPage;
