import { useEffect, useMemo, useState } from "react";
import { SaveOutlined } from "@ant-design/icons";
import { Button, Select, message } from "@/ui";

import api from "../../../../../api";
import type { ActiveModelsInfo, ModelSlotRequest } from "../../../../../api/types";
import styles from "../../index.module.less";

interface ModelsSectionProps {
  providers: Array<{
    id: string;
    name: string;
    models?: Array<{ id: string; name: string }>;
    extra_models?: Array<{ id: string; name: string }>;
    base_url?: string;
    api_key?: string;
    is_custom: boolean;
    is_local?: boolean;
  }>;
  activeModels: ActiveModelsInfo | null;
  onSaved: () => void;
}

export function ModelsSection({
  providers,
  activeModels,
  onSaved,
}: ModelsSectionProps) {
  const [saving, setSaving] = useState(false);
  const [selectedProviderId, setSelectedProviderId] = useState<string | undefined>(
    undefined,
  );
  const [selectedModel, setSelectedModel] = useState<string | undefined>(undefined);
  const [dirty, setDirty] = useState(false);

  const currentSlot = activeModels?.active_llm;

  const eligible = useMemo(
    () =>
      providers.filter((provider) => {
        const hasModels =
          (provider.models?.length ?? 0) + (provider.extra_models?.length ?? 0) > 0;
        if (!hasModels) return false;
        if (provider.is_local) return true;
        if (provider.id === "ollama") return Boolean(provider.base_url);
        if (provider.is_custom) return Boolean(provider.base_url);
        return Boolean(provider.api_key);
      }),
    [providers],
  );

  useEffect(() => {
    if (currentSlot) {
      setSelectedProviderId(currentSlot.provider_id || undefined);
      setSelectedModel(currentSlot.model || undefined);
    }
    setDirty(false);
  }, [currentSlot]);

  const chosenProvider = providers.find((provider) => provider.id === selectedProviderId);
  const modelOptions = [
    ...(chosenProvider?.models ?? []),
    ...(chosenProvider?.extra_models ?? []),
  ];
  const hasModels = modelOptions.length > 0;

  const handleProviderChange = (providerId: string) => {
    setSelectedProviderId(providerId);
    setSelectedModel(undefined);
    setDirty(true);
  };

  const handleModelChange = (model: string) => {
    setSelectedModel(model);
    setDirty(true);
  };

  const handleSave = async () => {
    if (!selectedProviderId || !selectedModel) {
      return;
    }

    const body: ModelSlotRequest = {
      provider_id: selectedProviderId,
      model: selectedModel,
    };

    setSaving(true);
    try {
      await api.setActiveLlm(body);
      message.success("对话模型已更新");
      setDirty(false);
      onSaved();
    } catch (error) {
      const errMsg = error instanceof Error ? error.message : "保存失败";
      message.error(errMsg);
    } finally {
      setSaving(false);
    }
  };

  const isActive =
    currentSlot &&
    currentSlot.provider_id === selectedProviderId &&
    currentSlot.model === selectedModel;
  const canSave = dirty && Boolean(selectedProviderId) && Boolean(selectedModel);

  return (
    <div className={styles.slotSection}>
      <div className={styles.slotHeader}>
        <h3 className={styles.slotTitle}>对话模型配置</h3>
        {currentSlot?.provider_id && currentSlot?.model ? (
          <span className={styles.slotCurrent}>
            {`当前：${currentSlot.provider_id} / ${currentSlot.model}`}
          </span>
        ) : null}
      </div>

      <div className={styles.slotForm}>
        <div className={styles.slotField}>
          <label className={styles.slotLabel}>提供商</label>
          <Select
            style={{ width: "100%" }}
            placeholder="选择提供商（必须已授权）"
            value={selectedProviderId}
            onChange={handleProviderChange}
            options={eligible.map((provider) => ({
              value: provider.id,
              label: provider.name,
            }))}
          />
        </div>

        <div className={styles.slotField}>
          <label className={styles.slotLabel}>模型</label>
          <Select
            style={{ width: "100%" }}
            placeholder={hasModels ? "选择模型" : "请先添加模型"}
            disabled={!hasModels}
            showSearch
            optionFilterProp="label"
            value={selectedModel}
            onChange={handleModelChange}
            options={modelOptions.map((model) => ({
              value: model.id,
              label: `${model.name} (${model.id})`,
            }))}
          />
        </div>

        <div
          className={styles.slotField}
          style={{ flex: "0 0 auto", minWidth: "120px" }}
        >
          <label className={styles.slotLabel} style={{ visibility: "hidden" }}>
            操作
          </label>
          <Button
            type="primary"
            loading={saving}
            disabled={!canSave}
            onClick={handleSave}
            block
            icon={<SaveOutlined />}
          >
            {isActive ? "已保存" : "保存"}
          </Button>
        </div>
      </div>
    </div>
  );
}
