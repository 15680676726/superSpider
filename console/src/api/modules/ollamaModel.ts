import { request } from "../request";
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
    }),

  getOllamaDownloadStatus: () =>
    request<OllamaDownloadTaskResponse[]>("/ollama-models/download-status"),

  cancelOllamaDownload: (taskId: string) =>
    request<{ status: string; task_id: string }>(
      `/providers/admin/ollama-models/download/${encodeURIComponent(taskId)}`,
      { method: "DELETE" },
    ),

  deleteOllamaModel: (name: string) =>
    request<{ status: string; name: string }>(
      `/providers/admin/ollama-models/${encodeURIComponent(name)}`,
      { method: "DELETE" },
    ),
};
