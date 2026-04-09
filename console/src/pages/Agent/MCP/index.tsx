import { useState } from "react";
import { Button, Empty, Modal } from "@/ui";
import type { MCPClientCreateRequest } from "../../../api/types";
import { MCPClientCard } from "./components";
import { useMCP, type MCPClientCapabilityView } from "./useMCP";

type MCPTransport = "stdio" | "streamable_http" | "sse";
type JsonRecord = Record<string, unknown>;
type MCPClientInput = MCPClientCreateRequest["client"];

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

function toRecord(value: unknown): JsonRecord | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as JsonRecord)
    : null;
}

function toStringValue(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (value == null) {
    return "";
  }
  return String(value);
}

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => toStringValue(item)).filter(Boolean);
}

function toStringRecord(value: unknown): Record<string, string> {
  const record = toRecord(value);
  if (!record) {
    return {};
  }
  return Object.fromEntries(
    Object.entries(record)
      .map(([key, entryValue]) => [key, toStringValue(entryValue)] as const)
      .filter(([, entryValue]) => entryValue.length > 0),
  );
}

function hasClientEndpoint(record: JsonRecord): boolean {
  return Boolean(record.command || record.url || record.baseUrl);
}

function normalizeClientData(key: string, rawData: JsonRecord): MCPClientInput {
  const commandCandidate = toStringValue(rawData.command);
  const urlCandidate = toStringValue(rawData.url ?? rawData.baseUrl);
  const enabledCandidate = rawData.enabled ?? rawData.isActive;
  const transport =
    normalizeTransport(rawData.transport ?? rawData.type)
    ?? (urlCandidate || !commandCandidate ? "streamable_http" : "stdio");

  const command = transport === "stdio" ? commandCandidate : "";

  return {
    name: toStringValue(rawData.name) || key,
    description: toStringValue(rawData.description),
    enabled: typeof enabledCandidate === "boolean" ? enabledCandidate : true,
    transport,
    url: urlCandidate,
    headers: toStringRecord(rawData.headers),
    command,
    args: toStringArray(rawData.args),
    env: toStringRecord(rawData.env),
    cwd: toStringValue(rawData.cwd),
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
      const parsed = JSON.parse(newClientJson) as unknown;
      const parsedRecord = toRecord(parsed);
      if (!parsedRecord) {
        throw new Error("invalid-client-json");
      }
      const clientsToCreate: Array<{ key: string; data: MCPClientInput }> = [];

      const mcpServers = toRecord(parsedRecord.mcpServers);
      if (mcpServers) {
        Object.entries(mcpServers).forEach(([key, data]) => {
          const clientRecord = toRecord(data);
          if (!clientRecord) {
            return;
          }
          clientsToCreate.push({
            key,
            data: normalizeClientData(key, clientRecord),
          });
        });
      } else if (
        typeof parsedRecord.key === "string"
        && hasClientEndpoint(parsedRecord)
      ) {
        const { key, ...clientData } = parsedRecord;
        clientsToCreate.push({
          key,
          data: normalizeClientData(key, clientData),
        });
      } else {
        Object.entries(parsedRecord).forEach(([key, data]) => {
          const clientRecord = toRecord(data);
          if (!clientRecord || !hasClientEndpoint(clientRecord)) {
            return;
          }
          clientsToCreate.push({
            key,
            data: normalizeClientData(key, clientRecord),
          });
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
