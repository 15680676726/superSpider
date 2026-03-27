import { request, authenticatedFetch } from "../request";
import type { SystemOverview, SystemSelfCheck } from "../types";

export const systemApi = {
  getSystemOverview: () => request<SystemOverview>("/system/overview"),

  runSystemSelfCheck: () => request<SystemSelfCheck>("/system/self-check"),

  downloadSystemBackup: async (): Promise<Blob> => {
    const response = await authenticatedFetch("/system/backup/download", {
      method: "GET",
    });
    return await response.blob();
  },

  restoreSystemBackup: async (
    file: File,
  ): Promise<Record<string, unknown>> => {
    const formData = new FormData();
    formData.append("file", file);
    const response = await authenticatedFetch("/system/backup/restore", {
      method: "POST",
      body: formData,
    });
    return await response.json();
  },
};
