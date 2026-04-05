import { useCallback, useEffect, useMemo, useState } from "react";
import type { FormInstance } from "antd";

import api, {
  type CapabilityMarketOverview,
  type CuratedSkillCatalogSearchResponse,
  type MCPClientInfo,
  type SkillSpec,
} from "../../api";
import type {
  CapabilityMarketInstallTemplateDoctorReport,
  CapabilityMarketInstallTemplateExampleRunRecord,
  CapabilityMarketProjectCandidate,
  CapabilityMarketInstallTemplateSpec,
  McpRegistryCatalogDetailResponse,
  McpRegistryCatalogSearchResponse,
} from "../../api/modules/capabilityMarket";
import type { IndustryInstanceSummary } from "../../api/modules/industry";
import {
  buildMcpFieldDefaults,
  buildTemplateConfigDefaults,
  CURATED_CATEGORY_DEFINITIONS,
  CURATED_FETCH_LIMIT,
  CURATED_PAGE_SIZE,
  inferCuratedCategoryKeys,
  MCP_PAGE_SIZE,
  normalizeMarketTabKey,
  type ConcreteCuratedCategoryKey,
  type CuratedCategoryKey,
  type CuratedDisplayEntry,
} from "./presentation";

export function useCapabilityMarketState({
  templateForm,
  mcpForm,
  searchParams,
  setSearchParams,
}: {
  templateForm: FormInstance<Record<string, unknown>>;
  mcpForm: FormInstance<Record<string, any>>;
  searchParams: URLSearchParams;
  setSearchParams: (next: URLSearchParams) => void;
}) {
  const requestedTab = searchParams.get("tab");
  const activeTab = normalizeMarketTabKey(requestedTab);
  const requestedTemplateId = searchParams.get("template")?.trim() || null;

  const [overview, setOverview] = useState<CapabilityMarketOverview | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [overviewError, setOverviewError] = useState<string | null>(null);

  const [templates, setTemplates] = useState<CapabilityMarketInstallTemplateSpec[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [templatesError, setTemplatesError] = useState<string | null>(null);
  const [templateDetail, setTemplateDetail] =
    useState<CapabilityMarketInstallTemplateSpec | null>(null);
  const [templateDetailLoading, setTemplateDetailLoading] = useState(false);
  const [templateDetailError, setTemplateDetailError] = useState<string | null>(null);
  const [templateActionKey, setTemplateActionKey] = useState<string | null>(null);
  const [templateDoctorReport, setTemplateDoctorReport] =
    useState<CapabilityMarketInstallTemplateDoctorReport | null>(null);
  const [templateExampleRun, setTemplateExampleRun] =
    useState<CapabilityMarketInstallTemplateExampleRunRecord | null>(null);
  const [templateInstallSummary, setTemplateInstallSummary] = useState<string | null>(null);

  const [curatedQuery, setCuratedQuery] = useState("");
  const [curatedPayload, setCuratedPayload] =
    useState<CuratedSkillCatalogSearchResponse | null>(null);
  const [curatedLoading, setCuratedLoading] = useState(false);
  const [curatedError, setCuratedError] = useState<string | null>(null);
  const [curatedCategory, setCuratedCategory] = useState<CuratedCategoryKey>("all");
  const [curatedPage, setCuratedPage] = useState(1);
  const [installingCuratedId, setInstallingCuratedId] = useState<string | null>(null);
  const [curatedReviewAcknowledgements, setCuratedReviewAcknowledgements] =
    useState<Record<string, boolean>>({});

  const [projectQuery, setProjectQuery] = useState("");
  const [projectResults, setProjectResults] = useState<CapabilityMarketProjectCandidate[]>([]);
  const [projectLoading, setProjectLoading] = useState(false);
  const [projectError, setProjectError] = useState<string | null>(null);
  const [projectInstallKey, setProjectInstallKey] = useState<string | null>(null);

  const [mcpQuery, setMcpQuery] = useState("");
  const [mcpCategory, setMcpCategory] = useState("all");
  const [mcpPage, setMcpPage] = useState(1);
  const [mcpCursorHistory, setMcpCursorHistory] = useState<Array<string | null>>([null]);
  const [mcpCatalog, setMcpCatalog] = useState<McpRegistryCatalogSearchResponse | null>(null);
  const [mcpCatalogLoading, setMcpCatalogLoading] = useState(false);
  const [mcpCatalogError, setMcpCatalogError] = useState<string | null>(null);
  const [mcpDetail, setMcpDetail] = useState<McpRegistryCatalogDetailResponse | null>(null);
  const [mcpDetailOpen, setMcpDetailOpen] = useState(false);
  const [mcpDetailLoading, setMcpDetailLoading] = useState(false);
  const [mcpDetailError, setMcpDetailError] = useState<string | null>(null);
  const [mcpSelectedOptionKey, setMcpSelectedOptionKey] = useState<string | null>(null);
  const [mcpActionKey, setMcpActionKey] = useState<string | null>(null);
  const [mcpInstallSummary, setMcpInstallSummary] = useState<string | null>(null);
  const [industryInstances, setIndustryInstances] = useState<IndustryInstanceSummary[]>([]);
  const [mcpTargetInstanceId, setMcpTargetInstanceId] = useState<string | undefined>(undefined);
  const [mcpTargetAgentIds, setMcpTargetAgentIds] = useState<string[]>([]);

  const updateSearchParams = useCallback(
    (patch: Record<string, string | null>) => {
      const next = new URLSearchParams(searchParams);
      Object.entries(patch).forEach(([key, value]) => {
        if (value == null || value === "") {
          next.delete(key);
          return;
        }
        next.set(key, value);
      });
      setSearchParams(next);
    },
    [searchParams, setSearchParams],
  );

  const loadOverview = useCallback(async () => {
    setOverviewLoading(true);
    setOverviewError(null);
    try {
      const payload = await api.getCapabilityMarketOverview();
      setOverview(payload);
    } catch (error) {
      setOverviewError(error instanceof Error ? error.message : String(error));
    } finally {
      setOverviewLoading(false);
    }
  }, []);

  const loadMcpCatalog = useCallback(
    async (options?: {
      query?: string;
      category?: string;
      cursor?: string | null;
      page?: number;
    }) => {
      const nextQuery = (options?.query ?? mcpQuery).trim();
      const nextCategory = options?.category ?? mcpCategory;
      const nextCursor =
        options?.cursor === undefined ? mcpCursorHistory[mcpPage - 1] || null : options.cursor;
      const nextPage = options?.page ?? mcpPage;
      setMcpCatalogLoading(true);
      setMcpCatalogError(null);
      try {
        const payload = await api.searchCapabilityMarketMcpCatalog({
          query: nextQuery,
          category: nextCategory,
          cursor: nextCursor,
          limit: MCP_PAGE_SIZE,
        });
        setMcpCatalog(payload);
        setMcpPage(nextPage);
      } catch (error) {
        setMcpCatalogError(error instanceof Error ? error.message : String(error));
      } finally {
        setMcpCatalogLoading(false);
      }
    },
    [mcpCategory, mcpCursorHistory, mcpPage, mcpQuery],
  );

  const loadMcpDetail = useCallback(
    async (serverName: string) => {
      setMcpDetailLoading(true);
      setMcpDetailError(null);
      try {
        const payload = await api.getCapabilityMarketMcpCatalogDetail(serverName);
        const defaultOption =
          payload.install_options.find((item) => item.supported) ||
          payload.install_options[0] ||
          null;
        const matchedClient = payload.item.installed_client_key
          ? (overview?.mcp_clients || []).find(
              (item) => item.key === payload.item.installed_client_key,
            ) || null
          : null;
        setMcpDetail(payload);
        setMcpSelectedOptionKey(defaultOption?.key || null);
        setMcpInstallSummary(null);
        setMcpTargetAgentIds([]);
        const allFieldKeys = payload.install_options.flatMap((option) =>
          option.input_fields.map((field) => field.key),
        );
        const resetValues = Object.fromEntries(allFieldKeys.map((key) => [key, undefined]));
        mcpForm.setFieldsValue({
          ...resetValues,
          ...buildMcpFieldDefaults(payload, defaultOption),
          client_key: payload.item.installed_client_key || payload.item.suggested_client_key,
          enabled: matchedClient?.enabled ?? true,
        });
      } catch (error) {
        setMcpDetail(null);
        setMcpDetailError(error instanceof Error ? error.message : String(error));
      } finally {
        setMcpDetailLoading(false);
      }
    },
    [mcpForm, overview?.mcp_clients],
  );

  const loadTemplates = useCallback(async () => {
    setTemplatesLoading(true);
    setTemplatesError(null);
    try {
      const payload = await api.listCapabilityMarketInstallTemplates();
      setTemplates(Array.isArray(payload) ? payload : []);
    } catch (error) {
      setTemplatesError(error instanceof Error ? error.message : String(error));
    } finally {
      setTemplatesLoading(false);
    }
  }, []);

  const loadTemplateDetail = useCallback(
    async (templateId: string) => {
      setTemplateDetailLoading(true);
      setTemplateDetailError(null);
      try {
        const payload = await api.getCapabilityMarketInstallTemplate(templateId);
        setTemplateDetail(payload);
        setTemplateDoctorReport(null);
        setTemplateExampleRun(null);
        setTemplateInstallSummary(null);
        templateForm.setFieldsValue(buildTemplateConfigDefaults(payload));
      } catch (error) {
        setTemplateDetail(null);
        setTemplateDetailError(error instanceof Error ? error.message : String(error));
      } finally {
        setTemplateDetailLoading(false);
      }
    },
    [templateForm],
  );

  const loadCurated = useCallback(async (query = "") => {
    setCuratedLoading(true);
    setCuratedError(null);
    try {
      const payload = await api.searchCapabilityMarketCuratedCatalog(query, CURATED_FETCH_LIMIT);
      setCuratedPayload(payload);
    } catch (error) {
      setCuratedError(error instanceof Error ? error.message : String(error));
    } finally {
      setCuratedLoading(false);
    }
  }, []);

  const loadProjects = useCallback(async (query = "") => {
    setProjectLoading(true);
    setProjectError(null);
    try {
      const payload = await api.searchCapabilityMarketProjects(query, 20);
      setProjectResults(Array.isArray(payload) ? payload : []);
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : String(error));
    } finally {
      setProjectLoading(false);
    }
  }, []);

  const loadIndustryInstances = useCallback(async () => {
    try {
      const payload = await api.listIndustryInstances({ limit: 50 });
      setIndustryInstances(Array.isArray(payload) ? payload : []);
    } catch {
      setIndustryInstances([]);
    }
  }, []);

  useEffect(() => {
    void loadOverview();
    void loadProjects("");
    void loadMcpCatalog({ query: "", category: "all", cursor: null, page: 1 });
    void loadTemplates();
    void loadCurated("");
    void loadIndustryInstances();
  }, [loadCurated, loadIndustryInstances, loadMcpCatalog, loadOverview, loadProjects, loadTemplates]);

  useEffect(() => {
    if (activeTab === "install-templates" && !requestedTemplateId && templates[0]?.id) {
      updateSearchParams({ template: templates[0].id });
    }
  }, [activeTab, requestedTemplateId, templates, updateSearchParams]);

  useEffect(() => {
    if (!requestedTemplateId) {
      setTemplateDetail(null);
      templateForm.resetFields();
      return;
    }
    void loadTemplateDetail(requestedTemplateId);
  }, [loadTemplateDetail, requestedTemplateId, templateForm]);

  useEffect(() => {
    setCuratedPage(1);
  }, [curatedCategory, curatedPayload]);

  const selectedTemplate =
    templateDetail || templates.find((item) => item.id === requestedTemplateId) || null;

  const curatedEntries = useMemo<CuratedDisplayEntry[]>(
    () =>
      (curatedPayload?.items || []).map((item) => ({
        item,
        categoryKeys: inferCuratedCategoryKeys(item),
      })),
    [curatedPayload],
  );

  const categoryCounts = useMemo(
    () =>
      Object.fromEntries(
        CURATED_CATEGORY_DEFINITIONS.map((definition) => [
          definition.key,
          definition.key === "all"
            ? curatedEntries.length
            : curatedEntries.filter((entry) =>
                entry.categoryKeys.includes(definition.key as ConcreteCuratedCategoryKey),
              ).length,
        ]),
      ) as Record<CuratedCategoryKey, number>,
    [curatedEntries],
  );

  const filteredCuratedItems = useMemo(
    () =>
      curatedEntries.filter((entry) => {
        if (curatedCategory === "all") {
          return true;
        }
        return entry.categoryKeys.includes(curatedCategory as ConcreteCuratedCategoryKey);
      }),
    [curatedCategory, curatedEntries],
  );

  const pagedCuratedItems = useMemo(() => {
    const start = (curatedPage - 1) * CURATED_PAGE_SIZE;
    return filteredCuratedItems.slice(start, start + CURATED_PAGE_SIZE);
  }, [curatedPage, filteredCuratedItems]);

  const curatedRangeText = useMemo(() => {
    if (!filteredCuratedItems.length) {
      return "暂无结果";
    }
    const start = (curatedPage - 1) * CURATED_PAGE_SIZE + 1;
    const end = Math.min(curatedPage * CURATED_PAGE_SIZE, filteredCuratedItems.length);
    return `${start}-${end} / ${filteredCuratedItems.length}`;
  }, [curatedPage, filteredCuratedItems.length]);

  const installedCapabilities = useMemo(
    () =>
      [...(overview?.installed || [])].sort((left, right) => {
        if (left.enabled !== right.enabled) {
          return Number(right.enabled) - Number(left.enabled);
        }
        return left.name.localeCompare(right.name);
      }),
    [overview?.installed],
  );

  const skills = useMemo<SkillSpec[]>(
    () => (overview?.available_skills?.length ? overview.available_skills : overview?.skills || []),
    [overview],
  );

  const mcpClients = useMemo<MCPClientInfo[]>(
    () =>
      [...(overview?.mcp_clients || [])].sort((left, right) => left.name.localeCompare(right.name)),
    [overview?.mcp_clients],
  );

  const selectedMcpOption = useMemo(
    () =>
      mcpDetail?.install_options.find((item) => item.key === mcpSelectedOptionKey) ||
      mcpDetail?.install_options.find((item) => item.supported) ||
      mcpDetail?.install_options[0] ||
      null,
    [mcpDetail, mcpSelectedOptionKey],
  );

  const selectedMcpInstance = useMemo(
    () => industryInstances.find((item) => item.instance_id === mcpTargetInstanceId) || null,
    [industryInstances, mcpTargetInstanceId],
  );

  const mcpTargetAgentOptions = useMemo(
    () =>
      (selectedMcpInstance?.team?.agents || []).map((agent) => ({
        label: `${agent.name} / ${agent.role_name}`,
        value: agent.agent_id,
      })),
    [selectedMcpInstance],
  );

  const mcpCategoryOptions = useMemo(
    () => (mcpCatalog?.categories?.length ? mcpCatalog.categories : [{ key: "all", label: "全部" }]),
    [mcpCatalog],
  );

  useEffect(() => {
    if (!mcpTargetInstanceId && industryInstances[0]?.instance_id) {
      setMcpTargetInstanceId(industryInstances[0].instance_id);
    }
  }, [industryInstances, mcpTargetInstanceId]);

  useEffect(() => {
    if (!mcpTargetAgentOptions.length) {
      if (mcpTargetAgentIds.length) {
        setMcpTargetAgentIds([]);
      }
      return;
    }
    setMcpTargetAgentIds((current) =>
      current.filter((value) => mcpTargetAgentOptions.some((item) => item.value === value)),
    );
  }, [mcpTargetAgentIds.length, mcpTargetAgentOptions]);

  const handleRefreshAll = useCallback(async () => {
    await Promise.all([
      loadOverview(),
      loadProjects(projectQuery.trim()),
      loadMcpCatalog({
        query: mcpQuery,
        category: mcpCategory,
        cursor: mcpCursorHistory[mcpPage - 1] || null,
        page: mcpPage,
      }),
      loadTemplates(),
      loadCurated(curatedQuery.trim()),
      loadIndustryInstances(),
    ]);
    if (requestedTemplateId) {
      await loadTemplateDetail(requestedTemplateId);
    }
    if (mcpDetail?.item.server_name) {
      await loadMcpDetail(mcpDetail.item.server_name);
    }
  }, [
    curatedQuery,
    loadCurated,
    loadIndustryInstances,
    loadMcpCatalog,
    loadMcpDetail,
    loadOverview,
    loadProjects,
    loadTemplateDetail,
    loadTemplates,
    mcpCategory,
    mcpCursorHistory,
    mcpDetail?.item.server_name,
    mcpPage,
    mcpQuery,
    projectQuery,
    requestedTemplateId,
  ]);

  return {
    activeTab,
    categoryCounts,
    curatedCategory,
    curatedEntries,
    curatedError,
    curatedLoading,
    curatedPage,
    curatedPayload,
    curatedQuery,
    curatedRangeText,
    curatedReviewAcknowledgements,
    filteredCuratedItems,
    handleRefreshAll,
    installedCapabilities,
    installingCuratedId,
    loadCurated,
    loadIndustryInstances,
    loadMcpCatalog,
    loadMcpDetail,
    loadOverview,
    loadProjects,
    loadTemplateDetail,
    loadTemplates,
    mcpActionKey,
    mcpCatalog,
    mcpCatalogError,
    mcpCatalogLoading,
    mcpCategory,
    mcpCategoryOptions,
    mcpClients,
    mcpCursorHistory,
    mcpDetail,
    mcpDetailError,
    mcpDetailLoading,
    mcpDetailOpen,
    mcpInstallSummary,
    mcpPage,
    mcpQuery,
    mcpSelectedOptionKey,
    mcpTargetAgentIds,
    mcpTargetAgentOptions,
    mcpTargetInstanceId,
    industryInstances,
    overview,
    overviewError,
    overviewLoading,
    pagedCuratedItems,
    projectError,
    projectInstallKey,
    projectLoading,
    projectQuery,
    projectResults,
    requestedTemplateId,
    selectedMcpInstance,
    selectedMcpOption,
    selectedTemplate,
    setCuratedCategory,
    setCuratedPage,
    setCuratedQuery,
    setCuratedReviewAcknowledgements,
    setInstallingCuratedId,
    setMcpActionKey,
    setMcpCategory,
    setMcpCursorHistory,
    setMcpDetailOpen,
    setMcpInstallSummary,
    setMcpPage,
    setMcpQuery,
    setMcpSelectedOptionKey,
    setMcpTargetAgentIds,
    setMcpTargetInstanceId,
    setProjectInstallKey,
    setProjectQuery,
    setTemplateActionKey,
    setTemplateDoctorReport,
    setTemplateExampleRun,
    setTemplateInstallSummary,
    skills,
    templateActionKey,
    templateDetail,
    templateDetailError,
    templateDetailLoading,
    templateDoctorReport,
    templateExampleRun,
    templateInstallSummary,
    templates,
    templatesError,
    templatesLoading,
    updateSearchParams,
  };
}
