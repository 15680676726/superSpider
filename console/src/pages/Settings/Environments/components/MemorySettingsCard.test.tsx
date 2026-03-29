// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemorySettingsCard } from "./MemorySettingsCard";

describe("MemorySettingsCard", () => {
  it("adds hover titles to long status values and model inference text", () => {
    const activeProviderValue = "超长自定义提供方 / 这是一个明显会超过卡片宽度的超长模型名称用于验证单行省略和悬浮全文";
    const modelInferenceText = "需显式指定模型或改用自定义提供方";

    render(
      <MemorySettingsCard
        memoryRecallMode="hybrid-local"
        memoryRecallBackendRaw="hybrid-local"
        embeddingApiKey=""
        embeddingBaseUrl="https://example.invalid/v1"
        embeddingModelName=""
        followActiveProvider={false}
        ftsEnabled
        memoryStoreBackend="local"
        dirty={false}
        saving={false}
        activeProviderId="custom-provider"
        activeProviderName="超长自定义提供方"
        activeProviderModel="这是一个明显会超过卡片宽度的超长模型名称用于验证单行省略和悬浮全文"
        activeProviderBaseUrl="https://example.invalid/v1"
        activeProviderHasApiKey={false}
        onTextChange={vi.fn()}
        onFollowActiveProviderChange={vi.fn()}
        onFtsEnabledChange={vi.fn()}
        onMemoryStoreBackendChange={vi.fn()}
        onMemoryRecallModeChange={vi.fn()}
        onApplyRecommendedDefaults={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    expect(screen.getByText(modelInferenceText)).toHaveAttribute("title", modelInferenceText);
    expect(screen.getByText(activeProviderValue)).toHaveAttribute("title", activeProviderValue);
  });
});
