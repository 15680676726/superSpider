import { request } from "../request";
import { invalidateActiveModelsCache } from "../../runtime/activeModelsCache";
import type {
  OllamaModelResponse,
  OllamaDownloadRequest,
  OllamaDownloadTaskResponse,
} from "../types";

export const ollamaModelApi = {
  listOllamaModels: () => request<OllamaModelResponse[]>("/ollama-models"),

  downloadOllamaModel: (body: OllamaDownloadRequest) =>
    request<OllamaDownloadTaskResponse>("/providers/admin/ollama-models/download", {
      method: "POST",
      body: JSON.stringify(body),
    }).then((payload) => {
      invalidateActiveModelsCache();
      return payload;
    }),

  getOllamaDownloadStatus: () =>
    request<OllamaDownloadTaskResponse[]>("/ollama-models/download-status"),

  cancelOllamaDownload: (taskId: string) =>
    request<{ status: string; task_id: string }>(
      `/providers/admin/ollama-models/download/${encodeURIComponent(taskId)}`,
      { method: "DELETE" },
    ).then((payload) => {
      invalidateActiveModelsCache();
      return payload;
    }),

  deleteOllamaModel: (name: string) =>
    request<{ status: string; name: string }>(
      `/providers/admin/ollama-models/${encodeURIComponent(name)}`,
      { method: "DELETE" },
    ).then((payload) => {
      invalidateActiveModelsCache();
      return payload;
    }),
};
