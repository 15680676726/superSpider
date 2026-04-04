import { request } from "../request";
import { invalidateActiveModelsCache } from "../../runtime/activeModelsCache";
import type {
  LocalModelResponse,
  DownloadModelRequest,
  DownloadTaskResponse,
} from "../types";

export const localModelApi = {
  listLocalModels: (backend?: string) => {
    const params = backend ? `?backend=${encodeURIComponent(backend)}` : "";
    return request<LocalModelResponse[]>(`/local-models${params}`);
  },

  downloadModel: (body: DownloadModelRequest) =>
    request<DownloadTaskResponse>("/providers/admin/local-models/download", {
      method: "POST",
      body: JSON.stringify(body),
    }).then((payload) => {
      invalidateActiveModelsCache();
      return payload;
    }),

  getDownloadStatus: (backend?: string) => {
    const params = backend ? `?backend=${encodeURIComponent(backend)}` : "";
    return request<DownloadTaskResponse[]>(
      `/local-models/download-status${params}`,
    );
  },

  cancelDownload: (taskId: string) =>
    request<{ status: string; task_id: string }>(
      `/providers/admin/local-models/cancel-download/${encodeURIComponent(taskId)}`,
      { method: "POST" },
    ).then((payload) => {
      invalidateActiveModelsCache();
      return payload;
    }),

  deleteLocalModel: (modelId: string) =>
    request<{ status: string; model_id: string }>(
      `/providers/admin/local-models/${encodeURIComponent(modelId)}`,
      { method: "DELETE" },
    ).then((payload) => {
      invalidateActiveModelsCache();
      return payload;
    }),
};
