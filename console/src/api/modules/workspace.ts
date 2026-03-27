import { request, authenticatedFetch } from "../request";
import type { MdFileInfo, MdFileContent, DailyMemoryFile } from "../types";

export const workspaceApi = {
  listFiles: () =>
    request<MdFileInfo[]>("/agent/files").then((files) =>
      files.map((file) => ({
        ...file,
        updated_at: new Date(file.modified_time).getTime(),
      })),
    ),

  loadFile: (fileName: string) =>
    request<MdFileContent>(`/agent/files/${encodeURIComponent(fileName)}`),

  saveFile: (fileName: string, content: string) =>
    request<Record<string, unknown>>(
      `/agent/files/${encodeURIComponent(fileName)}`,
      {
        method: "PUT",
        body: JSON.stringify({ content }),
      },
    ),

  downloadWorkspace: async (): Promise<Blob> => {
    const response = await authenticatedFetch("/workspace/download", {
      method: "GET",
    });
    return await response.blob();
  },

  uploadFile: async (
    file: File,
  ): Promise<{ success: boolean; message: string }> => {
    const formData = new FormData();
    formData.append("file", file);
    const response = await authenticatedFetch("/workspace/upload", {
      method: "POST",
      body: formData,
    });
    return await response.json();
  },

  listDailyMemory: () =>
    request<MdFileInfo[]>("/agent/memory").then((files) =>
      files.map((file) => {
        const date = file.filename.replace(".md", "");
        return {
          ...file,
          date,
          updated_at: new Date(file.modified_time).getTime(),
        } as DailyMemoryFile;
      }),
    ),

  loadDailyMemory: (date: string) =>
    request<MdFileContent>(`/agent/memory/${encodeURIComponent(date)}.md`),

  saveDailyMemory: (date: string, content: string) =>
    request<Record<string, unknown>>(
      `/agent/memory/${encodeURIComponent(date)}.md`,
      {
        method: "PUT",
        body: JSON.stringify({ content }),
      },
    ),
};
