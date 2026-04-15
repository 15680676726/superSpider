// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemorySettingsCard } from "./MemorySettingsCard";

describe("MemorySettingsCard", () => {
  it("renders only truth-first memory and real private compaction controls", () => {
    render(
      <MemorySettingsCard
        memoryRecallBackendRaw="hybrid-local"
        retiredMemoryKeys={["EMBEDDING_API_KEY", "EMBEDDING_MODEL_NAME"]}
        ftsEnabled
        memoryStoreBackend="local"
        dirty={false}
        saving={false}
        onFtsEnabledChange={vi.fn()}
        onMemoryStoreBackendChange={vi.fn()}
        onApplyRecommendedDefaults={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    expect(screen.getAllByText("truth-first").length).toBeGreaterThan(0);
    expect(screen.queryByText(/Hybrid Local/i)).toBeNull();
    expect(screen.queryByText(/QMD/i)).toBeNull();
    expect(screen.queryByText(/向量检索/)).toBeNull();
    expect(screen.queryByText("私有压缩接口密钥")).toBeNull();
    expect(screen.queryByText("私有压缩服务地址")).toBeNull();
    expect(screen.queryByText("私有压缩模型")).toBeNull();
    expect(screen.queryByText("复用当前激活提供方")).toBeNull();
    expect(screen.getAllByText("本地全文检索").length).toBeGreaterThan(0);
    expect(screen.getByText("私有压缩存储后端")).toBeInTheDocument();
    expect(screen.getByText("检测到 2 个退役记忆变量")).toBeInTheDocument();
    expect(screen.getByText(/EMBEDDING_API_KEY/)).toBeInTheDocument();
  });
});
