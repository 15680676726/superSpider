import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Empty,
  Form,
  Input,
  List,
  Select,
  Space,
  Spin,
  Switch,
  Tabs,
  Tag,
  Typography,
  message,
} from "antd";
import {
  DatabaseOutlined,
  DeploymentUnitOutlined,
  ReloadOutlined,
  SearchOutlined,
} from "@ant-design/icons";
import { request } from "../../api";
import type {
  AgentDetail,
  AgentProfile,
} from "../AgentWorkbench/useAgentWorkbench";
import {
  presentExecutionActorName,
  presentRuntimeStatusLabel,
} from "../../runtime/executionPresentation";
import {
  getChangeTypeLabel,
  getLeaseKindLabel,
  getPhaseLabel,
  getStatusLabel,
} from "../AgentWorkbench/copy";
import { normalizeSpiderMeshBrand } from "../../utils/brand";

const { Paragraph, Text, Title } = Typography;
const { TextArea } = Input;
const EXECUTION_CORE_ROLE_ID = "execution-core";

type StrategyItem = {
  strategy_id: string;
  scope_type: "global" | "industry";
  title: string;
  summary: string;
  mission: string;
  north_star: string;
  thinking_axes: string[];
  delegation_policy: string[];
  evidence_requirements: string[];
  status: string;
};

type DocItem = {
  document_id: string;
  title: string;
  chunk_count: number;
  tags: string[];
};

type ChunkItem = {
  id: string;
  document_id: string;
  title: string;
  content: string;
  tags: string[];
};

type MemoryItem = {
  id: string;
  title: string;
  summary?: string;
  scope_type?: string;
  scope_id?: string;
  tags: string[];
};

type MemoryScopeType = "global" | "industry" | "agent" | "task";

type MemoryBackendItem = {
  backend_id: string;
  label: string;
  available: boolean;
  is_default?: boolean;
  reason?: string | null;
};

type MemoryRecallHit = {
  entry_id: string;
  kind: string;
  title: string;
  summary: string;
  content_excerpt: string;
  source_type: string;
  source_ref: string;
  source_route?: string | null;
  scope_type: string;
  scope_id: string;
  confidence: number;
  quality_score: number;
  score: number;
  backend: string;
  evidence_refs: string[];
  entity_keys: string[];
  opinion_keys: string[];
  source_updated_at?: string | null;
};

type MemoryRecallResponse = {
  query: string;
  backend_requested?: string | null;
  backend_used: string;
  fallback_reason?: string | null;
  hits: MemoryRecallHit[];
};

type MemoryFactIndexEntry = {
  id: string;
  source_type: string;
  source_ref: string;
  scope_type: string;
  scope_id: string;
  owner_agent_id?: string | null;
  industry_instance_id?: string | null;
  title: string;
  summary: string;
  content_excerpt: string;
  entity_keys: string[];
  opinion_keys: string[];
  tags: string[];
  evidence_refs: string[];
  confidence: number;
  quality_score: number;
  source_updated_at?: string | null;
};

type MemoryEntityView = {
  entity_id: string;
  entity_key: string;
  scope_type: string;
  scope_id: string;
  display_name: string;
  entity_type: string;
  summary: string;
  confidence: number;
  supporting_refs: string[];
  contradicting_refs: string[];
  related_entities: string[];
  source_refs: string[];
  updated_at?: string | null;
};

type MemoryOpinionView = {
  opinion_id: string;
  subject_key: string;
  scope_type: string;
  scope_id: string;
  opinion_key: string;
  stance: string;
  summary: string;
  confidence: number;
  supporting_refs: string[];
  contradicting_refs: string[];
  entity_keys: string[];
  source_refs: string[];
  updated_at?: string | null;
};

type MemoryReflectionRun = {
  run_id: string;
  scope_type: string;
  scope_id: string;
  trigger_kind: string;
  status: string;
  summary: string;
  generated_entity_ids: string[];
  generated_opinion_ids: string[];
  metadata?: {
    proposal_ids?: string[];
    entity_count?: number;
    opinion_count?: number;
  };
  started_at?: string | null;
  completed_at?: string | null;
};

type MemoryRebuildSummary = {
  fact_index_count: number;
  completed_at?: string | null;
};

type MemoryReflectionSummary = {
  entity_count: number;
  opinion_count: number;
  proposal_ids: string[];
  summary: string;
};

function parseCsv(value: string): string[] {
  return value
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function isExecutionCore(agent: AgentProfile | null | undefined): boolean {
  return Boolean(
    agent &&
      (agent.industry_role_id === EXECUTION_CORE_ROLE_ID ||
        agent.agent_id === "copaw-agent-runner"),
  );
}

function appendSearchParam(
  search: URLSearchParams,
  key: string,
  value: string | number | boolean | null | undefined,
) {
  if (value === null || value === undefined) {
    return;
  }
  const normalized =
    typeof value === "string" ? value.trim() : String(value).trim();
  if (!normalized) {
    return;
  }
  search.set(key, normalized);
}

function buildMemoryScopeSearch(scopeType: MemoryScopeType, scopeId: string) {
  const normalizedScopeId = scopeId.trim() || (scopeType === "global" ? "runtime" : "");
  const search = new URLSearchParams();
  appendSearchParam(search, "scope_type", scopeType);
  appendSearchParam(search, "scope_id", normalizedScopeId);
  if (scopeType === "industry") {
    appendSearchParam(search, "industry_instance_id", normalizedScopeId);
  }
  if (scopeType === "agent") {
    appendSearchParam(search, "owner_agent_id", normalizedScopeId);
    appendSearchParam(search, "agent_id", normalizedScopeId);
  }
  if (scopeType === "task") {
    appendSearchParam(search, "task_id", normalizedScopeId);
  }
  if (scopeType === "global") {
    appendSearchParam(search, "global_scope_id", normalizedScopeId);
  }
  return { scopeId: normalizedScopeId, search };
}

function formatScope(scopeType?: string | null, scopeId?: string | null): string {
  if (!scopeType && !scopeId) {
    return "n/a";
  }
  return `${scopeType || "scope"}:${scopeId || "runtime"}`;
}

function formatPercent(value?: number | null): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "n/a";
  }
  return `${Math.round(value * 100)}%`;
}

function formatDateTime(value?: string | null): string {
  if (!value) {
    return "n/a";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function compactText(value: string | null | undefined, maxLength = 180): string {
  const normalized = (value || "").trim();
  if (!normalized) {
    return "n/a";
  }
  if (normalized.length <= maxLength) {
    return normalized;
  }
  return `${normalized.slice(0, maxLength - 3).trimEnd()}...`;
}

function stanceColor(stance: string): "default" | "blue" | "gold" | "red" | "green" {
  switch (stance) {
    case "recommendation":
      return "blue";
    case "requirement":
      return "gold";
    case "caution":
      return "red";
    case "preference":
      return "green";
    default:
      return "default";
  }
}

export default function KnowledgePage() {
  const [docForm] = Form.useForm();
  const [memoryForm] = Form.useForm();

  const [strategies, setStrategies] = useState<StrategyItem[]>([]);
  const [documents, setDocuments] = useState<DocItem[]>([]);
  const [chunks, setChunks] = useState<ChunkItem[]>([]);
  const [memoryItems, setMemoryItems] = useState<MemoryItem[]>([]);
  const [agents, setAgents] = useState<AgentProfile[]>([]);
  const [detail, setDetail] = useState<AgentDetail | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [memoryLoading, setMemoryLoading] = useState(false);
  const [memoryBusy, setMemoryBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [memoryScopeType, setMemoryScopeType] = useState<MemoryScopeType>("global");
  const [memoryScopeId, setMemoryScopeId] = useState("runtime");
  const [memoryRole, setMemoryRole] = useState("");
  const [memoryBackend, setMemoryBackend] = useState("");
  const [recallQuery, setRecallQuery] = useState("");
  const [createLearningProposals, setCreateLearningProposals] = useState(true);

  const [memoryBackends, setMemoryBackends] = useState<MemoryBackendItem[]>([]);
  const [recallResponse, setRecallResponse] = useState<MemoryRecallResponse | null>(null);
  const [memoryIndex, setMemoryIndex] = useState<MemoryFactIndexEntry[]>([]);
  const [entityViews, setEntityViews] = useState<MemoryEntityView[]>([]);
  const [opinionViews, setOpinionViews] = useState<MemoryOpinionView[]>([]);
  const [reflectionRuns, setReflectionRuns] = useState<MemoryReflectionRun[]>([]);
  const [lastRebuildSummary, setLastRebuildSummary] = useState<MemoryRebuildSummary | null>(null);
  const [lastReflectSummary, setLastReflectSummary] = useState<MemoryReflectionSummary | null>(null);

  const selectedAgent =
    agents.find((agent) => agent.agent_id === selectedAgentId) ||
    agents.find((agent) => isExecutionCore(agent)) ||
    agents[0] ||
    null;

  const loadPage = useCallback(async () => {
    setLoading(true);
    try {
      setError(null);
      const factParams = query.trim()
        ? `?query=${encodeURIComponent(query.trim())}`
        : "";
      const [
        strategyPayload,
        documentPayload,
        chunkPayload,
        memoryPayload,
        agentPayload,
      ] = await Promise.all([
        request<StrategyItem[]>("/runtime-center/strategy-memory?status=active&limit=20"),
        request<DocItem[]>(`/runtime-center/knowledge/documents${factParams}`),
        request<ChunkItem[]>(`/runtime-center/knowledge${factParams}`),
        request<MemoryItem[]>(`/runtime-center/knowledge/memory${factParams}`),
        request<AgentProfile[]>("/runtime-center/agents?view=business"),
      ]);
      const nextAgents = Array.isArray(agentPayload) ? agentPayload : [];
      setStrategies(Array.isArray(strategyPayload) ? strategyPayload : []);
      setDocuments(Array.isArray(documentPayload) ? documentPayload : []);
      setChunks(Array.isArray(chunkPayload) ? chunkPayload : []);
      setMemoryItems(Array.isArray(memoryPayload) ? memoryPayload : []);
      setAgents(nextAgents);
      setSelectedAgentId((current) =>
        current && nextAgents.some((agent) => agent.agent_id === current)
          ? current
          : nextAgents.find((agent) => isExecutionCore(agent))?.agent_id ||
            nextAgents[0]?.agent_id ||
            null,
      );
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : String(fetchError));
    } finally {
      setLoading(false);
    }
  }, [query]);

  async function loadDetail(agentId: string) {
    setDetailLoading(true);
    try {
      setDetail(
        await request<AgentDetail>(
          `/runtime-center/agents/${encodeURIComponent(agentId)}`,
        ),
      );
    } catch (fetchError) {
      setDetail(null);
      setError(fetchError instanceof Error ? fetchError.message : String(fetchError));
    } finally {
      setDetailLoading(false);
    }
  }

  const loadMemoryWorkspace = useCallback(async (options?: { includeRecall?: boolean }) => {
    const { scopeId, search } = buildMemoryScopeSearch(
      memoryScopeType,
      memoryScopeId,
    );
    if (!scopeId) {
      return;
    }
    setMemoryLoading(true);
    try {
      const indexSearch = new URLSearchParams(search);
      indexSearch.set("limit", "40");
      const entitySearch = new URLSearchParams(search);
      entitySearch.set("limit", "24");
      const opinionSearch = new URLSearchParams(search);
      opinionSearch.set("limit", "24");
      const reflectionSearch = new URLSearchParams(search);
      reflectionSearch.set("limit", "20");

      const [
        backendsPayload,
        indexPayload,
        entityPayload,
        opinionPayload,
        reflectionPayload,
      ] = await Promise.all([
        request<MemoryBackendItem[]>("/runtime-center/memory/backends"),
        request<MemoryFactIndexEntry[]>(
          `/runtime-center/memory/index?${indexSearch.toString()}`,
        ),
        request<MemoryEntityView[]>(
          `/runtime-center/memory/entities?${entitySearch.toString()}`,
        ),
        request<MemoryOpinionView[]>(
          `/runtime-center/memory/opinions?${opinionSearch.toString()}`,
        ),
        request<MemoryReflectionRun[]>(
          `/runtime-center/memory/reflections?${reflectionSearch.toString()}`,
        ),
      ]);

      setMemoryBackends(Array.isArray(backendsPayload) ? backendsPayload : []);
      setMemoryBackend((current) => {
        if (
          current &&
          Array.isArray(backendsPayload) &&
          backendsPayload.some((item) => item.backend_id === current)
        ) {
          return current;
        }
        return (
          backendsPayload.find((item) => item.is_default && item.available)
            ?.backend_id ||
          backendsPayload.find((item) => item.available)?.backend_id ||
          ""
        );
      });
      setMemoryIndex(Array.isArray(indexPayload) ? indexPayload : []);
      setEntityViews(Array.isArray(entityPayload) ? entityPayload : []);
      setOpinionViews(Array.isArray(opinionPayload) ? opinionPayload : []);
      setReflectionRuns(Array.isArray(reflectionPayload) ? reflectionPayload : []);

      if (options?.includeRecall) {
        if (!recallQuery.trim()) {
          setRecallResponse(null);
        } else {
          const recallSearch = new URLSearchParams(search);
          appendSearchParam(recallSearch, "query", recallQuery.trim());
          appendSearchParam(recallSearch, "role", memoryRole.trim() || null);
          appendSearchParam(recallSearch, "backend", memoryBackend || null);
          appendSearchParam(
            recallSearch,
            "include_related_scopes",
            memoryScopeType === "task" ? false : true,
          );
          appendSearchParam(recallSearch, "limit", 8);
          const recallPayload = await request<MemoryRecallResponse>(
            `/runtime-center/memory/recall?${recallSearch.toString()}`,
          );
          setRecallResponse(recallPayload);
        }
      }
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : String(fetchError));
    } finally {
      setMemoryLoading(false);
    }
  }, [memoryBackend, memoryRole, memoryScopeId, memoryScopeType, recallQuery]);

  useEffect(() => {
    void loadPage();
    void loadMemoryWorkspace();
  }, [loadMemoryWorkspace, loadPage]);

  useEffect(() => {
    if (selectedAgent?.agent_id) {
      void loadDetail(selectedAgent.agent_id);
    }
  }, [selectedAgent?.agent_id]);

  const handleImport = async (values: Record<string, string>) => {
    try {
      await request("/runtime-center/knowledge/import", {
        method: "POST",
        body: JSON.stringify({
          title: values.title,
          content: values.content,
          source_ref: values.source_ref || null,
          role_bindings: parseCsv(values.role_bindings || ""),
          tags: parseCsv(values.tags || ""),
        }),
      });
      message.success("已将文档导入核心知识库。");
      docForm.resetFields();
      await loadPage();
    } catch (saveError) {
      message.error(saveError instanceof Error ? saveError.message : String(saveError));
    }
  };

  const handleRemember = async (values: Record<string, string>) => {
    try {
      await request("/runtime-center/knowledge/memory", {
        method: "POST",
        body: JSON.stringify({
          title: values.memory_title,
          content: values.memory_content,
          scope_type: values.scope_type || "agent",
          scope_id: values.scope_id,
          source_ref: values.memory_source_ref || null,
          tags: parseCsv(values.memory_tags || ""),
        }),
      });
      message.success("持久事实已保存至核心记忆。");
      memoryForm.resetFields();
      await Promise.all([loadPage(), loadMemoryWorkspace()]);
    } catch (saveError) {
      message.error(saveError instanceof Error ? saveError.message : String(saveError));
    }
  };

  const handleRefreshMemory = async (includeRecall = false) => {
    await loadMemoryWorkspace({ includeRecall });
  };

  const handleRunRecall = async () => {
    if (!recallQuery.trim()) {
      message.warning("请先输入查询条件。");
      return;
    }
    setMemoryBusy(true);
    try {
      await loadMemoryWorkspace({ includeRecall: true });
    } finally {
      setMemoryBusy(false);
    }
  };

  const handleRebuild = async () => {
    const { scopeId } = buildMemoryScopeSearch(memoryScopeType, memoryScopeId);
    if (!scopeId) {
      message.warning("索引重建需要作用域 ID。");
      return;
    }
    setMemoryBusy(true);
    try {
      const summary = await request<MemoryRebuildSummary>("/runtime-center/memory/rebuild", {
        method: "POST",
        body: JSON.stringify({
          scope_type: memoryScopeType,
          scope_id: scopeId,
          include_reporting: true,
          include_learning: true,
          evidence_limit: 200,
        }),
      });
      setLastRebuildSummary(summary);
      await loadMemoryWorkspace({ includeRecall: Boolean(recallQuery.trim()) });
      message.success("派生记忆索引重建完成。");
    } catch (saveError) {
      message.error(saveError instanceof Error ? saveError.message : String(saveError));
    } finally {
      setMemoryBusy(false);
    }
  };

  const handleReflect = async () => {
    const { scopeId } = buildMemoryScopeSearch(memoryScopeType, memoryScopeId);
    if (!scopeId) {
      message.warning("进行反思需要作用域 ID。");
      return;
    }
    setMemoryBusy(true);
    try {
      const summary = await request<MemoryReflectionSummary>("/runtime-center/memory/reflect", {
        method: "POST",
        body: JSON.stringify({
          scope_type: memoryScopeType,
          scope_id: scopeId,
          owner_agent_id: memoryScopeType === "agent" ? scopeId : null,
          industry_instance_id: memoryScopeType === "industry" ? scopeId : null,
          trigger_kind: "manual",
          create_learning_proposals: createLearningProposals,
        }),
      });
      setLastReflectSummary(summary);
      await loadMemoryWorkspace({ includeRecall: Boolean(recallQuery.trim()) });
      message.success("记忆反思完成。");
    } catch (saveError) {
      message.error(saveError instanceof Error ? saveError.message : String(saveError));
    } finally {
      setMemoryBusy(false);
    }
  };

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Card className="baize-card">
        <Space style={{ width: "100%", justifyContent: "space-between" }}>
          <div>
            <Title level={3} style={{ margin: 0 }}>
              记忆控制台
            </Title>
            <Paragraph type="secondary" style={{ margin: "8px 0 0" }}>
              战略记忆、系统事实、派生召回、反思视图与执行上下文，现已统一至该操作台。
            </Paragraph>
          </div>
          <Space>
            <Input
              placeholder="搜索核心事实"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              style={{ width: 240 }}
            />
            <Button icon={<ReloadOutlined />} onClick={() => void loadPage()}>
              刷新记忆
            </Button>
          </Space>
        </Space>
      </Card>

      {error ? <Alert type="error" showIcon message={error} /> : null}

      <Tabs
        items={[
          {
            key: "strategy",
            label: (
              <span>
                <DeploymentUnitOutlined /> 战略记忆
              </span>
            ),
            children: loading ? (
              <Spin />
            ) : (
              <List
                locale={{ emptyText: <Empty description="暂无活跃战略记忆。" /> }}
                dataSource={strategies}
                renderItem={(item) => (
                  <List.Item key={item.strategy_id}>
                    <Card className="baize-card" style={{ width: "100%" }}>
                      <Space direction="vertical" size={10} style={{ width: "100%" }}>
                        <Space wrap>
                          <Text strong>{item.title}</Text>
                          <Tag color="blue">
                            {item.scope_type === "industry" ? "industry" : "global"}
                          </Tag>
                          <Tag>{item.status}</Tag>
                        </Space>
                        <Paragraph style={{ marginBottom: 0 }}>
                          {item.summary || "暂无战略摘要。"}
                        </Paragraph>
                        {item.mission ? (
                          <Text>使命: {normalizeSpiderMeshBrand(item.mission)}</Text>
                        ) : null}
                        {item.north_star ? (
                          <Text>北极星指标: {item.north_star}</Text>
                        ) : null}
                        {item.thinking_axes.length > 0 ? (
                          <Text>思考轴线: {item.thinking_axes.join(" / ")}</Text>
                        ) : null}
                        {item.delegation_policy.length > 0 ? (
                          <Text>
                            委派策略: {item.delegation_policy.join(" | ")}
                          </Text>
                        ) : null}
                        {item.evidence_requirements.length > 0 ? (
                          <Text>
                            证据预期:{" "}
                            {item.evidence_requirements.join(" | ")}
                          </Text>
                        ) : null}
                      </Space>
                    </Card>
                  </List.Item>
                )}
              />
            ),
          },
          {
            key: "facts",
            label: (
              <span>
                <DatabaseOutlined /> 事实仓库
              </span>
            ),
            children: (
              <Space direction="vertical" size={16} style={{ width: "100%" }}>
                <Card className="baize-card" title="导入核心知识">
                  <Form
                    form={docForm}
                    layout="vertical"
                    onFinish={(values) =>
                      void handleImport(values as Record<string, string>)
                    }
                  >
                    <Form.Item
                      name="title"
                      label="标题"
                      rules={[{ required: true, message: "标题不能为空。" }]}
                    >
                      <Input />
                    </Form.Item>
                    <Form.Item name="source_ref" label="来源引用">
                      <Input />
                    </Form.Item>
                    <Form.Item name="role_bindings" label="绑定角色">
                      <Input placeholder="以逗号分隔" />
                    </Form.Item>
                    <Form.Item name="tags" label="标签">
                      <Input placeholder="以逗号分隔" />
                    </Form.Item>
                    <Form.Item
                      name="content"
                      label="内容"
                      rules={[{ required: true, message: "内容不能为空。" }]}
                    >
                      <TextArea rows={6} />
                    </Form.Item>
                    <Button type="primary" htmlType="submit">
                      导入文档
                    </Button>
                  </Form>
                </Card>

                <Card className="baize-card" title="写入持久事实">
                  <Form
                    form={memoryForm}
                    layout="vertical"
                    onFinish={(values) =>
                      void handleRemember(values as Record<string, string>)
                    }
                  >
                    <Form.Item name="scope_type" label="作用域类型" initialValue="agent">
                      <Select
                        options={[
                          { label: "全局", value: "global" },
                          { label: "行业", value: "industry" },
                          { label: "执行位", value: "agent" },
                          { label: "任务", value: "task" },
                        ]}
                      />
                    </Form.Item>
                    <Form.Item
                      name="scope_id"
                      label="作用域 ID"
                      rules={[{ required: true, message: "作用域 ID 不能为空。" }]}
                    >
                      <Input />
                    </Form.Item>
                    <Form.Item
                      name="memory_title"
                      label="标题"
                      rules={[{ required: true, message: "标题不能为空。" }]}
                    >
                      <Input />
                    </Form.Item>
                    <Form.Item name="memory_source_ref" label="来源引用">
                      <Input />
                    </Form.Item>
                    <Form.Item name="memory_tags" label="标签">
                      <Input placeholder="以逗号分隔" />
                    </Form.Item>
                    <Form.Item
                      name="memory_content"
                      label="事实内容"
                      rules={[{ required: true, message: "事实内容不能为空。" }]}
                    >
                      <TextArea rows={4} />
                    </Form.Item>
                    <Button type="primary" htmlType="submit">
                      保存持久事实
                    </Button>
                  </Form>
                </Card>

                <Card className="baize-card" title={`文档库 ${documents.length}`}>
                  <List
                    locale={{ emptyText: <Empty description="暂无文档。" /> }}
                    dataSource={documents}
                    renderItem={(item) => (
                      <List.Item key={item.document_id}>
                        <Space direction="vertical" size={4} style={{ width: "100%" }}>
                          <Space wrap>
                            <Text strong>{item.title}</Text>
                            <Tag>{item.document_id}</Tag>
                            <Tag color="blue">{item.chunk_count} 个切片</Tag>
                          </Space>
                          {item.tags.length > 0 ? (
                            <Space wrap>
                              {item.tags.slice(0, 6).map((tag) => (
                                <Tag key={tag}>{tag}</Tag>
                              ))}
                            </Space>
                          ) : null}
                        </Space>
                      </List.Item>
                    )}
                  />
                </Card>

                <Card className="baize-card" title={`知识切片 ${chunks.length}`}>
                  <List
                    locale={{ emptyText: <Empty description="暂无切片。" /> }}
                    dataSource={chunks.slice(0, 12)}
                    renderItem={(item) => (
                      <List.Item key={item.id}>
                        <Space direction="vertical" size={4} style={{ width: "100%" }}>
                          <Space wrap>
                            <Text strong>{item.title}</Text>
                            <Tag>{item.document_id}</Tag>
                          </Space>
                          <Paragraph style={{ marginBottom: 0 }}>
                            {compactText(item.content, 220)}
                          </Paragraph>
                        </Space>
                      </List.Item>
                    )}
                  />
                </Card>

                <Card className="baize-card" title={`持久事实 ${memoryItems.length}`}>
                  <List
                    locale={{ emptyText: <Empty description="暂无持久事实。" /> }}
                    dataSource={memoryItems.slice(0, 12)}
                    renderItem={(item) => (
                      <List.Item key={item.id}>
                        <Space direction="vertical" size={4} style={{ width: "100%" }}>
                          <Space wrap>
                            <Text strong>{item.title}</Text>
                            <Tag>{formatScope(item.scope_type, item.scope_id)}</Tag>
                          </Space>
                          <Paragraph style={{ marginBottom: 0 }}>
                            {compactText(item.summary, 220)}
                          </Paragraph>
                          {item.tags.length > 0 ? (
                            <Space wrap>
                              {item.tags.slice(0, 6).map((tag) => (
                                <Tag key={tag}>{tag}</Tag>
                              ))}
                            </Space>
                          ) : null}
                        </Space>
                      </List.Item>
                    )}
                  />
                </Card>
              </Space>
            ),
          },
          {
            key: "memory",
            label: (
              <span>
                <SearchOutlined /> 检索与反思
              </span>
            ),
            children: (
              <Space direction="vertical" size={16} style={{ width: "100%" }}>
                <Card className="baize-card" title="派生记忆工作台">
                  <Space direction="vertical" size={12} style={{ width: "100%" }}>
                    <Space wrap>
                      <Select<MemoryScopeType>
                        value={memoryScopeType}
                        onChange={setMemoryScopeType}
                        style={{ width: 140 }}
                        options={[
                          { label: "全局", value: "global" },
                          { label: "行业", value: "industry" },
                          { label: "执行位", value: "agent" },
                          { label: "任务", value: "task" },
                        ]}
                      />
                      <Input
                        value={memoryScopeId}
                        onChange={(event) => setMemoryScopeId(event.target.value)}
                        placeholder="填入作用域 ID"
                        style={{ width: 220 }}
                      />
                      <Input
                        value={memoryRole}
                        onChange={(event) => setMemoryRole(event.target.value)}
                        placeholder="角色过滤"
                        style={{ width: 180 }}
                      />
                      <Select
                        value={memoryBackend || undefined}
                        onChange={(value) => setMemoryBackend(value)}
                        style={{ width: 220 }}
                        placeholder="召回引擎"
                        options={memoryBackends.map((backend) => ({
                          label: backend.label,
                          value: backend.backend_id,
                          disabled: !backend.available,
                        }))}
                      />
                    </Space>
                    <Space wrap>
                      <Input
                        value={recallQuery}
                        onChange={(event) => setRecallQuery(event.target.value)}
                        placeholder="输入查询进行记忆召回"
                        style={{ width: 420 }}
                      />
                      <Button
                        icon={<ReloadOutlined />}
                        onClick={() => void handleRefreshMemory(Boolean(recallQuery.trim()))}
                      >
                        加载作用域
                      </Button>
                      <Button
                        type="primary"
                        icon={<SearchOutlined />}
                        loading={memoryBusy}
                        onClick={() => void handleRunRecall()}
                      >
                        召回检索
                      </Button>
                      <Button loading={memoryBusy} onClick={() => void handleRebuild()}>
                        重建索引
                      </Button>
                      <Button loading={memoryBusy} onClick={() => void handleReflect()}>
                        反思总结
                      </Button>
                      <Space>
                        <Text type="secondary">生成学习提案</Text>
                        <Switch
                          checked={createLearningProposals}
                          onChange={setCreateLearningProposals}
                        />
                      </Space>
                    </Space>
                  </Space>
                </Card>

                <Card className="baize-card" title="记忆统计摘要">
                  <Descriptions bordered size="small" column={2}>
                    <Descriptions.Item label="当前作用域">
                      {formatScope(memoryScopeType, memoryScopeId)}
                    </Descriptions.Item>
                    <Descriptions.Item label="召回使用引擎">
                      {recallResponse?.backend_used || memoryBackend || "n/a"}
                    </Descriptions.Item>
                    <Descriptions.Item label="事实索引数">
                      {memoryIndex.length}
                    </Descriptions.Item>
                    <Descriptions.Item label="实体对象数">
                      {entityViews.length}
                    </Descriptions.Item>
                    <Descriptions.Item label="主观观点数">
                      {opinionViews.length}
                    </Descriptions.Item>
                    <Descriptions.Item label="反思执行次数">
                      {reflectionRuns.length}
                    </Descriptions.Item>
                    <Descriptions.Item label="最近一次重建">
                      {lastRebuildSummary
                        ? `${lastRebuildSummary.fact_index_count} entries at ${formatDateTime(
                            lastRebuildSummary.completed_at,
                          )}`
                        : "n/a"}
                    </Descriptions.Item>
                    <Descriptions.Item label="最近一次反思">
                      {lastReflectSummary
                        ? `${lastReflectSummary.entity_count} entities / ${lastReflectSummary.opinion_count} opinions`
                        : "n/a"}
                    </Descriptions.Item>
                  </Descriptions>
                </Card>

                <Card className="baize-card" title="可用召回引擎">
                  <Space wrap>
                    {memoryBackends.length === 0 ? (
                      <Empty description="尚未接入任何引擎。" />
                    ) : (
                      memoryBackends.map((backend) => (
                        <Tag
                          key={backend.backend_id}
                          color={backend.available ? "blue" : "default"}
                        >
                          {backend.label}
                          {backend.is_default ? " / default" : ""}
                          {!backend.available && backend.reason
                            ? ` / ${backend.reason}`
                            : ""}
                        </Tag>
                      ))
                    )}
                  </Space>
                </Card>

                {memoryLoading ? (
                  <Spin />
                ) : (
                  <>
                    <Card
                      className="baize-card"
                      title={
                        recallResponse
                          ? `召回命中 (${recallResponse.hits.length})`
                          : "召回命中"
                      }
                    >
                      <List
                        locale={{
                          emptyText: (
                            <Empty description="请输入查询条件以查看召回结果。" />
                          ),
                        }}
                        dataSource={recallResponse?.hits || []}
                        renderItem={(item) => (
                          <List.Item key={item.entry_id}>
                            <Space direction="vertical" size={6} style={{ width: "100%" }}>
                              <Space wrap>
                                <Text strong>{item.title}</Text>
                                <Tag color="blue">{item.kind}</Tag>
                                <Tag>{formatScope(item.scope_type, item.scope_id)}</Tag>
                                <Tag>{`得分 ${item.score.toFixed(2)}`}</Tag>
                                <Tag>{`置信度 ${formatPercent(item.confidence)}`}</Tag>
                              </Space>
                              <Paragraph style={{ marginBottom: 0 }}>
                                {compactText(item.summary || item.content_excerpt, 240)}
                              </Paragraph>
                              <Space wrap>
                                <Tag>{`来源 ${item.source_type}:${item.source_ref}`}</Tag>
                                {item.entity_keys.slice(0, 4).map((entityKey) => (
                                  <Tag key={entityKey}>{entityKey}</Tag>
                                ))}
                                {item.opinion_keys.slice(0, 3).map((opinionKey) => (
                                  <Tag key={opinionKey} color="gold">
                                    {opinionKey}
                                  </Tag>
                                ))}
                              </Space>
                            </Space>
                          </List.Item>
                        )}
                      />
                    </Card>

                    <Card className="baize-card" title={`事实索引 (${memoryIndex.length})`}>
                      <List
                        locale={{ emptyText: <Empty description="暂无事实索引条目。" /> }}
                        dataSource={memoryIndex}
                        renderItem={(item) => (
                          <List.Item key={item.id}>
                            <Space direction="vertical" size={6} style={{ width: "100%" }}>
                              <Space wrap>
                                <Text strong>{item.title}</Text>
                                <Tag color="blue">{item.source_type}</Tag>
                                <Tag>{formatScope(item.scope_type, item.scope_id)}</Tag>
                                <Tag>{`质量 ${formatPercent(item.quality_score)}`}</Tag>
                                <Tag>{`置信度 ${formatPercent(item.confidence)}`}</Tag>
                              </Space>
                              <Paragraph style={{ marginBottom: 0 }}>
                                {compactText(item.summary || item.content_excerpt, 240)}
                              </Paragraph>
                              <Space wrap>
                                <Tag>{`来源引用 ${item.source_ref}`}</Tag>
                                {item.entity_keys.slice(0, 5).map((entityKey) => (
                                  <Tag key={entityKey}>{entityKey}</Tag>
                                ))}
                                {item.tags.slice(0, 5).map((tag) => (
                                  <Tag key={tag} color="green">
                                    {tag}
                                  </Tag>
                                ))}
                                {item.evidence_refs.slice(0, 3).map((ref) => (
                                  <Tag key={ref} color="gold">
                                    {ref}
                                  </Tag>
                                ))}
                              </Space>
                            </Space>
                          </List.Item>
                        )}
                      />
                    </Card>

                    <Card className="baize-card" title={`实体对象视图 (${entityViews.length})`}>
                      <List
                        locale={{ emptyText: <Empty description="暂无实体对象。" /> }}
                        dataSource={entityViews}
                        renderItem={(item) => (
                          <List.Item key={item.entity_id}>
                            <Space direction="vertical" size={6} style={{ width: "100%" }}>
                              <Space wrap>
                                <Text strong>{item.display_name}</Text>
                                <Tag>{item.entity_type}</Tag>
                                <Tag>{formatScope(item.scope_type, item.scope_id)}</Tag>
                                <Tag>{`置信度 ${formatPercent(item.confidence)}`}</Tag>
                              </Space>
                              <Paragraph style={{ marginBottom: 0 }}>
                                {compactText(item.summary, 240)}
                              </Paragraph>
                              <Space wrap>
                                {item.related_entities.slice(0, 5).map((entityKey) => (
                                  <Tag key={entityKey} color="blue">
                                    {entityKey}
                                  </Tag>
                                ))}
                                {item.supporting_refs.slice(0, 3).map((ref) => (
                                  <Tag key={ref} color="green">
                                    {ref}
                                  </Tag>
                                ))}
                                {item.contradicting_refs.slice(0, 3).map((ref) => (
                                  <Tag key={ref} color="red">
                                    {ref}
                                  </Tag>
                                ))}
                              </Space>
                            </Space>
                          </List.Item>
                        )}
                      />
                    </Card>

                    <Card className="baize-card" title={`主观观点视图 (${opinionViews.length})`}>
                      <List
                        locale={{ emptyText: <Empty description="暂无主观观点。" /> }}
                        dataSource={opinionViews}
                        renderItem={(item) => (
                          <List.Item key={item.opinion_id}>
                            <Space direction="vertical" size={6} style={{ width: "100%" }}>
                              <Space wrap>
                                <Text strong>{item.subject_key}</Text>
                                <Tag color={stanceColor(item.stance)}>{item.stance}</Tag>
                                <Tag>{formatScope(item.scope_type, item.scope_id)}</Tag>
                                <Tag>{`置信度 ${formatPercent(item.confidence)}`}</Tag>
                              </Space>
                              <Paragraph style={{ marginBottom: 0 }}>
                                {compactText(item.summary, 240)}
                              </Paragraph>
                              <Space wrap>
                                {item.entity_keys.slice(0, 5).map((entityKey) => (
                                  <Tag key={entityKey}>{entityKey}</Tag>
                                ))}
                                {item.supporting_refs.slice(0, 3).map((ref) => (
                                  <Tag key={ref} color="green">
                                    {ref}
                                  </Tag>
                                ))}
                                {item.contradicting_refs.slice(0, 3).map((ref) => (
                                  <Tag key={ref} color="red">
                                    {ref}
                                  </Tag>
                                ))}
                              </Space>
                            </Space>
                          </List.Item>
                        )}
                      />
                    </Card>

                    <Card className="baize-card" title={`反思执行记录 (${reflectionRuns.length})`}>
                      <List
                        locale={{ emptyText: <Empty description="暂无反思执行记录。" /> }}
                        dataSource={reflectionRuns}
                        renderItem={(item) => (
                          <List.Item key={item.run_id}>
                            <Space direction="vertical" size={6} style={{ width: "100%" }}>
                              <Space wrap>
                                <Text strong>{item.run_id}</Text>
                                <Tag>{item.status}</Tag>
                                <Tag>{formatScope(item.scope_type, item.scope_id)}</Tag>
                                <Tag>{item.trigger_kind}</Tag>
                              </Space>
                              <Paragraph style={{ marginBottom: 0 }}>
                                {compactText(item.summary, 240)}
                              </Paragraph>
                              <Space wrap>
                                <Tag>
                                  {`实体数 ${item.metadata?.entity_count ?? item.generated_entity_ids.length}`}
                                </Tag>
                                <Tag>
                                  {`观点数 ${item.metadata?.opinion_count ?? item.generated_opinion_ids.length}`}
                                </Tag>
                                <Tag>{`开始时间 ${formatDateTime(item.started_at)}`}</Tag>
                                <Tag>{`完成时间 ${formatDateTime(item.completed_at)}`}</Tag>
                                {(item.metadata?.proposal_ids || []).slice(0, 3).map((proposalId) => (
                                  <Tag key={proposalId} color="gold">
                                    {proposalId}
                                  </Tag>
                                ))}
                              </Space>
                            </Space>
                          </List.Item>
                        )}
                      />
                    </Card>
                  </>
                )}
              </Space>
            ),
          },
          {
            key: "records",
            label: (
              <span>
                <DatabaseOutlined /> 执行记录
              </span>
            ),
            children: loading ? (
              <Spin />
            ) : (
              <Space direction="vertical" size={16} style={{ width: "100%" }}>
                <Card className="baize-card" title="执行器列表">
                  <Space wrap>
                    {agents.map((agent) => (
                      <Card
                        className="baize-card"
                        key={agent.agent_id}
                        size="small"
                        hoverable
                        onClick={() => setSelectedAgentId(agent.agent_id)}
                        style={{
                          minWidth: 220,
                          borderColor:
                            selectedAgent?.agent_id === agent.agent_id
                              ? "var(--baize-selected-border)"
                              : undefined,
                        }}
                      >
                        <Space wrap>
                          <Text strong>
                            {presentExecutionActorName(agent.agent_id, agent.name)}
                          </Text>
                          <Tag color={isExecutionCore(agent) ? "blue" : "default"}>
                            {isExecutionCore(agent) ? "主脑" : "执行位"}
                          </Tag>
                          <Tag>{presentRuntimeStatusLabel(agent.status)}</Tag>
                        </Space>
                        <div style={{ marginTop: 8 }}>
                          <Text type="secondary">
                            {normalizeSpiderMeshBrand(agent.role_name) ||
                              "尚未分配角色"}
                          </Text>
                        </div>
                      </Card>
                    ))}
                  </Space>
                </Card>

                {detailLoading ? (
                  <Spin />
                ) : detail ? (
                  <>
                    <Card className="baize-card">
                      <Space direction="vertical" size={8}>
                        <Space wrap>
                          <Title level={4} style={{ margin: 0 }}>
                            {presentExecutionActorName(
                              selectedAgent?.agent_id || detail.agent.agent_id,
                              selectedAgent?.name || detail.agent.name,
                            )}
                          </Title>
                          <Tag color={isExecutionCore(selectedAgent) ? "blue" : "default"}>
                            {isExecutionCore(selectedAgent)
                              ? "超级伙伴核心主脑"
                              : "全职执行位"}
                          </Tag>
                        </Space>
                        <Text>
                          {normalizeSpiderMeshBrand(
                            selectedAgent?.current_focus ||
                              selectedAgent?.role_summary ||
                              "暂无执行摘要。",
                          )}
                        </Text>
                        <Space wrap>
                          <Tag>{`信件 ${detail.mailbox.length}`}</Tag>
                          <Tag>{`检查点 ${detail.checkpoints.length}`}</Tag>
                          <Tag>{`租约 ${detail.leases.length}`}</Tag>
                          <Tag>{`成长轨迹 ${detail.growth.length}`}</Tag>
                        </Space>
                      </Space>
                    </Card>

                    <Card className="baize-card" title="信箱 / 检查点 / 租约 / 成长记录">
                      <List
                        dataSource={[
                          ...detail.mailbox
                            .slice(0, 4)
                            .map(
                              (item) =>
                                `信件 | ${item.title} | ${getStatusLabel(item.status)}`,
                            ),
                          ...detail.checkpoints
                            .slice(0, 4)
                            .map(
                              (item) =>
                                `检查点 | ${getPhaseLabel(item.phase || item.checkpoint_kind)} | ${getStatusLabel(item.status)}`,
                            ),
                          ...detail.leases
                            .slice(0, 4)
                            .map(
                              (item) =>
                                `租约 | ${getLeaseKindLabel(item.lease_kind)} | ${getStatusLabel(item.lease_status)}`,
                            ),
                          ...detail.growth
                            .slice(0, 4)
                            .map(
                              (item) =>
                                `成长 | ${getChangeTypeLabel(item.change_type)} | ${item.description}`,
                            ),
                        ]}
                        locale={{ emptyText: <Empty description="暂无执行记录。" /> }}
                        renderItem={(item) => <List.Item>{item}</List.Item>}
                      />
                    </Card>
                  </>
                ) : (
                  <Empty description="请在左侧选择一个执行器以查看记录。" />
                )}
              </Space>
            ),
          },
        ]}
      />
    </Space>
  );
}
