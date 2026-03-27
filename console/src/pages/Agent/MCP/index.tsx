import { useState } from "react";
import { Button, Empty, Modal } from "@/ui";
import { MCPClientCard } from "./components";
import { useMCP, type MCPClientCapabilityView } from "./useMCP";

type MCPTransport = "stdio" | "streamable_http" | "sse";

const DEFAULT_CLIENT_JSON = `{
  "mcpServers": {
    "example-client": {
      "command": "npx",
      "args": ["-y", "@example/mcp-server"],
      "env": {
        "API_KEY": "<YOUR_API_KEY>"
      }
    }
  }
}`;

function normalizeTransport(raw?: unknown): MCPTransport | undefined {
  if (typeof raw !== "string") return undefined;
  const value = raw.trim().toLowerCase();
  switch (value) {
    case "stdio":
      return "stdio";
    case "sse":
      return "sse";
    case "streamablehttp":
    case "streamable_http":
    case "http":
      return "streamable_http";
    default:
      return undefined;
  }
}

function normalizeClientData(key: string, rawData: any) {
  const transport =
    normalizeTransport(rawData.transport ?? rawData.type) ??
    (rawData.url || rawData.baseUrl || !rawData.command
      ? "streamable_http"
      : "stdio");

  const command =
    transport === "stdio" ? (rawData.command ?? "").toString() : "";

  return {
    name: rawData.name || key,
    description: rawData.description || "",
    enabled: rawData.enabled ?? rawData.isActive ?? true,
    transport,
    url: (rawData.url || rawData.baseUrl || "").toString(),
    headers: rawData.headers || {},
    command,
    args: Array.isArray(rawData.args) ? rawData.args : [],
    env: rawData.env || {},
    cwd: (rawData.cwd || "").toString(),
  };
}

function MCPPage() {
  const { clients, loading, toggleEnabled, deleteClient, createClient, updateClient } =
    useMCP();
  const [hoverKey, setHoverKey] = useState<string | null>(null);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [newClientJson, setNewClientJson] = useState(DEFAULT_CLIENT_JSON);

  const handleToggleEnabled = async (
    client: MCPClientCapabilityView,
    e?: React.MouseEvent,
  ) => {
    e?.stopPropagation();
    await toggleEnabled(client);
  };

  const handleDelete = async (
    client: MCPClientCapabilityView,
    e?: React.MouseEvent,
  ) => {
    e?.stopPropagation();
    await deleteClient(client);
  };

  const handleCreateClient = async () => {
    try {
      const parsed = JSON.parse(newClientJson);
      const clientsToCreate: Array<{ key: string; data: any }> = [];

      if (parsed.mcpServers) {
        Object.entries(parsed.mcpServers).forEach(([key, data]: [string, any]) => {
          clientsToCreate.push({
            key,
            data: normalizeClientData(key, data),
          });
        });
      } else if (parsed.key && (parsed.command || parsed.url || parsed.baseUrl)) {
        const { key, ...clientData } = parsed;
        clientsToCreate.push({
          key,
          data: normalizeClientData(key, clientData),
        });
      } else {
        Object.entries(parsed).forEach(([key, data]: [string, any]) => {
          if (
            typeof data === "object" &&
            (data.command || data.url || data.baseUrl)
          ) {
            clientsToCreate.push({
              key,
              data: normalizeClientData(key, data),
            });
          }
        });
      }

      let allSuccess = true;
      for (const { key, data } of clientsToCreate) {
        const success = await createClient(key, data);
        if (!success) {
          allSuccess = false;
        }
      }

      if (allSuccess) {
        setCreateModalOpen(false);
        setNewClientJson(DEFAULT_CLIENT_JSON);
      }
    } catch {
      window.alert("JSON 格式无效");
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 32,
        }}
      >
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 600, marginBottom: 4 }}>
            模型上下文协议客户端
          </h1>
          <p style={{ margin: 0, color: "var(--baize-text-main)", fontSize: 14 }}>
            {"统一管理模型上下文协议客户端的接入、启停与配置。"}
          </p>
        </div>
        <Button type="primary" onClick={() => setCreateModalOpen(true)}>
          {"新建模型上下文协议客户端"}
        </Button>
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: 60 }}>
          <p style={{ color: "var(--baize-text-main)" }}>{"加载中..."}</p>
        </div>
      ) : clients.length === 0 ? (
        <Empty description={"暂无模型上下文协议客户端"} />
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))",
            gap: 20,
          }}
        >
          {clients.map((client) => (
            <MCPClientCard
              key={client.key}
              client={client}
              onToggle={handleToggleEnabled}
              onDelete={handleDelete}
              onUpdate={updateClient}
              isHovered={hoverKey === client.key}
              onMouseEnter={() => setHoverKey(client.key)}
              onMouseLeave={() => setHoverKey(null)}
            />
          ))}
        </div>
      )}

      <Modal
        title={"新建模型上下文协议客户端"}
        open={createModalOpen}
        onCancel={() => setCreateModalOpen(false)}
        footer={
          <div style={{ textAlign: "right" }}>
            <Button
              onClick={() => setCreateModalOpen(false)}
              style={{ marginRight: 8 }}
            >
              {"取消"}
            </Button>
            <Button type="primary" onClick={handleCreateClient}>
              {"创建"}
            </Button>
          </div>
        }
        width={800}
      >
        <div style={{ marginBottom: 32 }}>
          <p style={{ margin: 0, fontSize: 13, color: "var(--baize-text-main)" }}>
            {"支持以下 JSON 格式："}
          </p>
          <ul
            style={{
              margin: "8px 0",
              padding: "0 0 0 20px",
              fontSize: 12,
              color: "var(--baize-text-main)",
            }}
          >
            <li>
              {"标准格式"}:{" "}
              <code>{`{ "mcpServers": { "key": {...} } }`}</code>
            </li>
            <li>
              {"直接映射"}: <code>{`{ "key": {...} }`}</code>
            </li>
            <li>
              {"单客户端格式"}:{" "}
              <code>{`{ "key": "...", "name": "...", "command": "..." }`}</code>
            </li>
          </ul>
        </div>
        <textarea
          value={newClientJson}
          onChange={(e) => setNewClientJson(e.target.value)}
          style={{
            width: "100%",
            minHeight: 400,
            fontFamily: "Monaco, Courier New, monospace",
            fontSize: 13,
            padding: 16,
            border: "1px solid #d9d9d9",
            borderRadius: 4,
            resize: "vertical",
          }}
        />
      </Modal>
    </div>
  );
}

export default MCPPage;
