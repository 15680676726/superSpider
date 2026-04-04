import { request } from "../request";
import { invalidateActiveModelsCache } from "../../runtime/activeModelsCache";
import type {
  ProviderInfo,
  ProviderConfigRequest,
  ActiveModelsInfo,
  ModelSlotRequest,
  CreateCustomProviderRequest,
  AddModelRequest,
  TestConnectionResponse,
  TestProviderRequest,
  TestModelRequest,
  DiscoverModelsResponse,
  ProviderFallbackConfig,
} from "../types";

export const providerApi = {
  listProviders: () => request<ProviderInfo[]>("/models"),

  configureProvider: (providerId: string, body: ProviderConfigRequest) =>
    request<ProviderInfo>(`/providers/admin/${encodeURIComponent(providerId)}/config`, {
      method: "PUT",
      body: JSON.stringify(body),
    }).then((payload) => {
      invalidateActiveModelsCache();
      return payload;
    }),

  getActiveModels: () => request<ActiveModelsInfo>("/models/active"),

  setActiveLlm: (body: ModelSlotRequest) =>
    request<ActiveModelsInfo>("/providers/admin/active", {
      method: "PUT",
      body: JSON.stringify(body),
    }).then((payload) => {
      invalidateActiveModelsCache();
      return payload;
    }),

  getProviderFallback: () =>
    request<ProviderFallbackConfig>("/models/fallback"),

  setProviderFallback: (body: ProviderFallbackConfig) =>
    request<ProviderFallbackConfig>("/providers/admin/fallback", {
      method: "PUT",
      body: JSON.stringify(body),
    }).then((payload) => {
      invalidateActiveModelsCache();
      return payload;
    }),

  /* ---- Custom provider CRUD ---- */

  createCustomProvider: (body: CreateCustomProviderRequest) =>
    request<ProviderInfo>("/providers/admin/custom-providers", {
      method: "POST",
      body: JSON.stringify(body),
    }).then((payload) => {
      invalidateActiveModelsCache();
      return payload;
    }),

  deleteCustomProvider: (providerId: string) =>
    request<ProviderInfo[]>(
      `/providers/admin/custom-providers/${encodeURIComponent(providerId)}`,
      { method: "DELETE" },
    ).then((payload) => {
      invalidateActiveModelsCache();
      return payload;
    }),

  /* ---- Model CRUD (works for both built-in and custom providers) ---- */

  addModel: (providerId: string, body: AddModelRequest) =>
    request<ProviderInfo>(`/providers/admin/${encodeURIComponent(providerId)}/models`, {
      method: "POST",
      body: JSON.stringify(body),
    }).then((payload) => {
      invalidateActiveModelsCache();
      return payload;
    }),

  removeModel: (providerId: string, modelId: string) =>
    request<ProviderInfo>(
      `/providers/admin/${encodeURIComponent(providerId)}/models/${encodeURIComponent(
        modelId,
      )}`,
      { method: "DELETE" },
    ).then((payload) => {
      invalidateActiveModelsCache();
      return payload;
    }),

  /* ---- Test Connection ---- */

  testProviderConnection: (providerId: string, body?: TestProviderRequest) =>
    request<TestConnectionResponse>(
      `/models/${encodeURIComponent(providerId)}/test`,
      {
        method: "POST",
        body: body ? JSON.stringify(body) : undefined,
      },
    ),

  testModelConnection: (providerId: string, body: TestModelRequest) =>
    request<TestConnectionResponse>(
      `/models/${encodeURIComponent(providerId)}/models/test`,
      {
        method: "POST",
        body: JSON.stringify(body),
      },
    ),

  discoverModels: (providerId: string, body?: TestProviderRequest) =>
    request<DiscoverModelsResponse>(
      `/providers/admin/${encodeURIComponent(providerId)}/discover`,
      {
        method: "POST",
        body: body ? JSON.stringify(body) : undefined,
      },
    ).then((payload) => {
      invalidateActiveModelsCache();
      return payload;
    }),
};
