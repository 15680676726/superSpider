export * from "./types";

export { request, authenticatedFetch, onResponseError } from "./request";
export type { RequestOptions, ResponseInterceptor } from "./request";
export { ApiError, isApiError, wrapNetworkError } from "./errors";

export { getApiUrl, getApiToken } from "./config";

import { rootApi } from "./modules/root";
import { capabilityMarketApi } from "./modules/capabilityMarket";
import { channelApi } from "./modules/channel";
import { consoleApi } from "./modules/console";
import { conversationApi } from "./modules/conversation";
import { envApi } from "./modules/env";
import { providerApi } from "./modules/provider";
import { runtimeCenterApi } from "./modules/runtimeCenter";
import { systemApi } from "./modules/system";
import { agentApi } from "./modules/agent";
import { workspaceApi } from "./modules/workspace";
import { localModelApi } from "./modules/localModel";
import { mediaApi } from "./modules/media";
import { ollamaModelApi } from "./modules/ollamaModel";
import { industryApi } from "./modules/industry";
import { fixedSopsApi } from "./modules/fixedSops";
import { predictionsApi } from "./modules/predictions";

export const api = {
  // Root
  ...rootApi,

  // Capabilities
  ...capabilityMarketApi,

  // Channels
  ...channelApi,

  // Console push messages
  ...consoleApi,

  // Runtime Center
  ...runtimeCenterApi,

  // Runtime conversations
  ...conversationApi,

  // Environment Variables
  ...envApi,

  // Providers
  ...providerApi,

  // System delivery surfaces
  ...systemApi,

  // Agent
  ...agentApi,

  // Workspace
  ...workspaceApi,

  // Local Models
  ...localModelApi,

  // Media ingestion + analysis
  ...mediaApi,

  // Ollama Models
  ...ollamaModelApi,

  // Industry MVP
  ...industryApi,

  // Native fixed SOP kernel
  ...fixedSopsApi,

  // Predictions
  ...predictionsApi,
};

export default api;
