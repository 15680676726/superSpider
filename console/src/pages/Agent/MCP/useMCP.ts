import { useCallback, useEffect, useState } from "react";
import { message } from "@/ui";
import {
  capabilityMutationRequiresConfirmation,
  type CapabilityMutationResponse,
} from "../../../api/modules/capability";
import { capabilityMarketApi } from "../../../api/modules/capabilityMarket";
import type { CapabilityMount, MCPClientInfo } from "../../../api/types";

export type MCPClientCapabilityView = MCPClientInfo & {
  capability?: CapabilityMount;
};

function confirmationMessage(result: CapabilityMutationResponse): string {
  return result.decision_request_id
    ? `等待确认：${result.decision_request_id}`
    : "等待确认";
}

export function useMCP() {
  const [clients, setClients] = useState<MCPClientCapabilityView[]>([]);
  const [loading, setLoading] = useState(false);

  const loadClients = useCallback(async () => {
    setLoading(true);
    try {
      const [data, capabilities] = await Promise.all([
        capabilityMarketApi.listCapabilityMarketMCPClients(),
        capabilityMarketApi
          .listCapabilityMarketCapabilities({ kind: "remote-mcp" })
          .catch(() => []),
      ]);
      setClients(mergeClientsWithCapabilities(data, capabilities));
    } catch (error) {
      console.error("Failed to load MCP clients:", error);
      message.error("加载模型上下文协议客户端失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadClients();
  }, [loadClients]);

  const createClient = useCallback(
    async (
      key: string,
      clientData: {
        name: string;
        description?: string;
        command: string;
        enabled?: boolean;
        transport?: "stdio" | "streamable_http" | "sse";
        url?: string;
        headers?: Record<string, string>;
        args?: string[];
        env?: Record<string, string>;
        cwd?: string;
      },
    ) => {
      try {
        await capabilityMarketApi.createCapabilityMarketMCPClient({
          client_key: key,
          client: clientData,
        });
        message.success("模型上下文协议客户端创建成功");
        await loadClients();
        return true;
      } catch (error: any) {
        message.error(error?.message || "创建模型上下文协议客户端失败");
        return false;
      }
    },
    [loadClients],
  );

  const updateClient = useCallback(
    async (
      key: string,
      updates: {
        name?: string;
        description?: string;
        command?: string;
        enabled?: boolean;
        transport?: "stdio" | "streamable_http" | "sse";
        url?: string;
        headers?: Record<string, string>;
        args?: string[];
        env?: Record<string, string>;
        cwd?: string;
      },
    ) => {
      try {
        await capabilityMarketApi.updateCapabilityMarketMCPClient(key, updates);
        message.success("模型上下文协议客户端已更新");
        await loadClients();
        return true;
      } catch (error: any) {
        message.error(error?.message || "更新模型上下文协议客户端失败");
        return false;
      }
    },
    [loadClients],
  );

  const toggleEnabled = useCallback(
    async (client: MCPClientInfo) => {
      try {
        const capabilityId = `mcp:${client.key}`;
        const result =
          await capabilityMarketApi.toggleCapabilityMarketCapability(
            capabilityId,
          );
        if (capabilityMutationRequiresConfirmation(result)) {
          message.warning(confirmationMessage(result));
          return;
        }
        if (result?.toggled) {
          message.success(
            result.summary ||
              (client.enabled
                ? "模型上下文协议客户端已停用"
                : "模型上下文协议客户端已启用"),
          );
          await loadClients();
          return;
        }
        message.error(
          result?.error ||
            result?.summary ||
            "切换模型上下文协议客户端状态失败",
        );
      } catch (error) {
        message.error("切换模型上下文协议客户端状态失败");
      }
    },
    [loadClients],
  );

  const deleteClient = useCallback(
    async (client: MCPClientInfo) => {
      try {
        const capabilityId = `mcp:${client.key}`;
        const result =
          await capabilityMarketApi.deleteCapabilityMarketCapability(
            capabilityId,
          );
        if (capabilityMutationRequiresConfirmation(result)) {
          message.warning(confirmationMessage(result));
          return;
        }
        if (result?.deleted) {
          message.success(result.summary || "模型上下文协议客户端已删除");
          await loadClients();
          return;
        }
        message.error(
          result?.error ||
            result?.summary ||
            "删除模型上下文协议客户端失败",
        );
      } catch (error) {
        message.error("删除模型上下文协议客户端失败");
      }
    },
    [loadClients],
  );

  return {
    clients,
    loading,
    createClient,
    updateClient,
    toggleEnabled,
    deleteClient,
  };
}

function mergeClientsWithCapabilities(
  clients: MCPClientInfo[],
  capabilities: CapabilityMount[],
): MCPClientCapabilityView[] {
  const capabilityMap = new Map(
    capabilities.map((capability) => [capability.id, capability]),
  );
  return clients.map((client) => ({
    ...client,
    capability: capabilityMap.get(`mcp:${client.key}`),
  }));
}
