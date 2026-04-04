import { beforeEach, describe, expect, it, vi } from "vitest";

const requestMock = vi.fn();
const invalidateActiveModelsCacheMock = vi.fn();

vi.mock("../request", () => ({
  request: (...args: unknown[]) => requestMock(...args),
}));

vi.mock("../../runtime/activeModelsCache", () => ({
  invalidateActiveModelsCache: () => invalidateActiveModelsCacheMock(),
}));

import { localModelApi } from "./localModel";
import { ollamaModelApi } from "./ollamaModel";
import { providerApi } from "./provider";

describe("model mutation invalidation", () => {
  beforeEach(() => {
    requestMock.mockReset();
    invalidateActiveModelsCacheMock.mockReset();
    requestMock.mockResolvedValue({ ok: true });
  });

  it("invalidates active-model cache for provider mutations", async () => {
    await providerApi.configureProvider("openai", {});
    await providerApi.setActiveLlm({ provider_id: "openai", model: "gpt-5" });
    await providerApi.setProviderFallback({ enabled: true, candidates: [] });
    await providerApi.createCustomProvider({
      id: "custom",
      name: "Custom",
      models: [],
    });
    await providerApi.deleteCustomProvider("custom");
    await providerApi.addModel("openai", { id: "gpt-5", name: "GPT-5" });
    await providerApi.removeModel("openai", "gpt-5");
    await providerApi.discoverModels("openai");

    expect(invalidateActiveModelsCacheMock).toHaveBeenCalledTimes(8);
  });

  it("invalidates active-model cache for local and ollama mutations", async () => {
    await localModelApi.downloadModel({
      backend: "huggingface",
      repo_id: "Qwen/Qwen3",
      source: "huggingface",
    });
    await localModelApi.cancelDownload("task-1");
    await localModelApi.deleteLocalModel("qwen");
    await ollamaModelApi.downloadOllamaModel({ name: "qwen3:latest" });
    await ollamaModelApi.cancelOllamaDownload("task-2");
    await ollamaModelApi.deleteOllamaModel("qwen3:latest");

    expect(invalidateActiveModelsCacheMock).toHaveBeenCalledTimes(6);
  });

  it("does not invalidate active-model cache for provider read calls", async () => {
    await providerApi.listProviders();
    await providerApi.getActiveModels();
    await providerApi.getProviderFallback();
    await providerApi.testProviderConnection("openai");
    await providerApi.testModelConnection("openai", { model_id: "gpt-5" });

    expect(invalidateActiveModelsCacheMock).not.toHaveBeenCalled();
  });
});
