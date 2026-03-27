import { useMemo, useState } from "react";
import { Card, Form, message } from "@/ui";

import api from "../../../api";
import {
  ChannelCard,
  ChannelDrawer,
  useChannels,
  getChannelLabel,
  type ChannelKey,
} from "./components";
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

  const handleCardClick = (key: ChannelKey) => {
    setActiveKey(key);
    setDrawerOpen(true);
    const channelConfig = channels[key] || { enabled: false, bot_prefix: "" };
    form.setFieldsValue({
      ...channelConfig,
      filter_tool_messages: !channelConfig.filter_tool_messages,
      filter_thinking: !channelConfig.filter_thinking,
    });
  };

  const handleDrawerClose = () => {
    setDrawerOpen(false);
    setActiveKey(null);
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

  return (
    <div className={styles.channelsPage}>
      <Card className="baize-page-header">
        <div className="baize-page-header-content">
          <div>
            <h1 className="baize-page-header-title">频道</h1>
            <p className="baize-page-header-description">管理和配置消息频道</p>
          </div>
          <div className="baize-page-header-actions">
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
          </div>
        </div>
      </Card>

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
        onClose={handleDrawerClose}
        onSubmit={handleSubmit}
      />
    </div>
  );
}

export default ChannelsPage;
