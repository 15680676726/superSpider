import { Form, message } from "antd";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormInstance } from "antd";
import type { NavigateFunction } from "react-router-dom";

import api from "../../api";
import type { AnalysisMode } from "../../api/modules/media";
import {
  resolveCanonicalBuddyProfileId,
} from "../../runtime/buddyProfileBinding";
import type {
  IndustryBootstrapResponse,
  IndustryCapabilityRecommendation,
  IndustryCapabilityRecommendationSection,
  IndustryDraftGoal,
  IndustryDraftPlan,
  IndustryDraftSchedule,
  IndustryInstanceDetail,
  IndustryInstanceSummary,
  IndustryPreviewResponse,
  IndustryRuntimeAgentReport,
  IndustryRoleBlueprint,
} from "../../api/modules/industry";
import { buildIndustryRoleChatBinding, openRuntimeChat, resolveIndustryExecutionCoreRole } from "../../utils/runtimeChat";
import { normalizeSpiderMeshBrand } from "../../utils/brand";
import {
  INDUSTRY_TEXT,
  buildFallbackRecommendationSections,
  createBlankInstallPlanItem,
  detailToDraftPlan,
  normalizeDraftPlan,
  recommendationToInstallItem,
  stripInstallPlanDraftItem,
  toPreviewPayload,
  uniqueStrings,
  type IndustryBriefFormValues,
  type IndustryBriefMediaItem,
  type InstallPlanDraftItem,
} from "./pageHelpers";

export function resolvePreferredIndustryInstanceId({
  instances,
  preferredInstanceId,
  buddyCarrierInstanceId,
  buddyProfileId,
}: {
  instances: IndustryInstanceSummary[];
  preferredInstanceId?: string | null;
  buddyCarrierInstanceId?: string | null;
  buddyProfileId?: string | null;
}): string | null {
  const canonicalBuddyCarrierId = buddyCarrierInstanceId?.trim() || null;
  if (
    canonicalBuddyCarrierId
    && instances.some((item) => item.instance_id === canonicalBuddyCarrierId)
  ) {
    return canonicalBuddyCarrierId;
  }
  const legacyBuddyCarrierId = buddyProfileId?.trim()
    ? `buddy:${buddyProfileId.trim()}`
    : null;
  if (legacyBuddyCarrierId) {
    return instances.some((item) => item.instance_id === legacyBuddyCarrierId)
      ? legacyBuddyCarrierId
      : null;
  }
  if (
    preferredInstanceId
    && instances.some((item) => item.instance_id === preferredInstanceId)
  ) {
    return preferredInstanceId;
  }
  return instances[0]?.instance_id || null;
}

export function resolveProtectedCarrierInstanceId(
  {
    buddyCarrierInstanceId,
    buddyProfileId,
  }: {
    buddyCarrierInstanceId?: string | null;
    buddyProfileId?: string | null;
  },
): string | null {
  const canonical = buddyCarrierInstanceId?.trim();
  if (canonical) {
    return canonical;
  }
  const normalized = buddyProfileId?.trim();
  return normalized ? `buddy:${normalized}` : null;
}

type RecommendationDisplayGroup = {
  group_id: "execution-core" | "delivery";
  title: string;
  summary: string;
  sections: IndustryCapabilityRecommendationSection[];
};

type IndustryDetailLoadOptions = {
  assignmentId?: string | null;
  backlogItemId?: string | null;
};

type IndustryPageStateCache = {
  instances: IndustryInstanceSummary[];
  retiredInstances: IndustryInstanceSummary[];
  selectedInstanceId: string | null;
  currentBuddyProfileId: string | null;
  currentBuddyCarrierInstanceId: string | null;
  detailByInstanceId: Record<string, IndustryInstanceDetail>;
};

let industryPageStateCache: IndustryPageStateCache = {
  instances: [],
  retiredInstances: [],
  selectedInstanceId: null,
  currentBuddyProfileId: null,
  currentBuddyCarrierInstanceId: null,
  detailByInstanceId: {},
};

function readCachedIndustryDetail(
  instanceId: string | null,
): IndustryInstanceDetail | null {
  if (!instanceId) {
    return null;
  }
  return industryPageStateCache.detailByInstanceId[instanceId] ?? null;
}

export function useIndustryPageState({
  briefForm,
  draftForm,
  navigate,
}: {
  briefForm: FormInstance<IndustryBriefFormValues>;
  draftForm: FormInstance<IndustryDraftPlan>;
  navigate: NavigateFunction;
}) {
  const [instances, setInstances] = useState<IndustryInstanceSummary[]>(
    () => industryPageStateCache.instances,
  );
  const [retiredInstances, setRetiredInstances] = useState<IndustryInstanceSummary[]>(
    () => industryPageStateCache.retiredInstances,
  );
  const [selectedInstanceId, setSelectedInstanceId] = useState<string | null>(
    () => industryPageStateCache.selectedInstanceId,
  );
  const [detail, setDetail] = useState<IndustryInstanceDetail | null>(
    () => readCachedIndustryDetail(industryPageStateCache.selectedInstanceId),
  );
  const [preview, setPreview] = useState<IndustryPreviewResponse | null>(null);
  const [draftSourceInstanceId, setDraftSourceInstanceId] = useState<string | null>(null);
  const [installPlan, setInstallPlan] = useState<InstallPlanDraftItem[]>([]);
  const [loadingInstances, setLoadingInstances] = useState(
    () =>
      industryPageStateCache.instances.length === 0 &&
      industryPageStateCache.retiredInstances.length === 0,
  );
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [applyCarrierLoading, setApplyCarrierLoading] = useState(false);
  const [deletingInstanceId, setDeletingInstanceId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [briefModalOpen, setBriefModalOpen] = useState(false);
  const briefUploadInputRef = useRef<HTMLInputElement | null>(null);
  const selectedInstanceIdRef = useRef<string | null>(null);
  const [briefMediaItems, setBriefMediaItems] = useState<IndustryBriefMediaItem[]>([]);
  const [briefMediaLink, setBriefMediaLink] = useState("");
  const [briefMediaBusy, setBriefMediaBusy] = useState(false);
  const [currentBuddyProfileId, setCurrentBuddyProfileId] = useState<string | null>(
    () => industryPageStateCache.currentBuddyProfileId,
  );
  const [currentBuddyCarrierInstanceId, setCurrentBuddyCarrierInstanceId] = useState<string | null>(
    () => industryPageStateCache.currentBuddyCarrierInstanceId,
  );
  const protectedCarrierInstanceId = resolveProtectedCarrierInstanceId(
    {
      buddyCarrierInstanceId: currentBuddyCarrierInstanceId,
      buddyProfileId: currentBuddyProfileId,
    },
  );

  const watchedExperienceMode =
    Form.useWatch("experience_mode", briefForm) || "system-led";
  const draftTeamLabel = Form.useWatch(["team", "label"], draftForm);
  const draftTeamSummary = Form.useWatch(["team", "summary"], draftForm);
  const draftGenerationSummary = Form.useWatch("generation_summary", draftForm);
  const watchedDraftAgents = Form.useWatch(["team", "agents"], draftForm) as
    | IndustryRoleBlueprint[]
    | undefined;
  const draftAgents = useMemo(
    () => watchedDraftAgents ?? preview?.draft.team.agents ?? [],
    [preview?.draft.team.agents, watchedDraftAgents],
  );
  const draftGoals =
    (Form.useWatch("goals", draftForm) as IndustryDraftGoal[] | undefined) ||
    preview?.draft.goals ||
    [];
  const draftSchedules =
    (Form.useWatch("schedules", draftForm) as IndustryDraftSchedule[] | undefined) ||
    preview?.draft.schedules ||
    [];

  useEffect(() => {
    selectedInstanceIdRef.current = selectedInstanceId;
  }, [selectedInstanceId]);

  useEffect(() => {
    if (!selectedInstanceId) {
      setDetail(null);
      return;
    }
    const cachedDetail = readCachedIndustryDetail(selectedInstanceId);
    if (cachedDetail) {
      setDetail(cachedDetail);
      return;
    }
    setDetail(null);
  }, [selectedInstanceId]);

  const loadInstances = useCallback(
    async (preferredInstanceId?: string | null) => {
      const hasCachedInstances =
        industryPageStateCache.instances.length > 0 ||
        industryPageStateCache.retiredInstances.length > 0;
      if (!hasCachedInstances) {
        setLoadingInstances(true);
      }
      try {
        setError(null);
        const buddySurfacePromise = Promise.resolve(api.getBuddySurface()).catch(
          () => null,
        );
        const [buddySurface, activePayload, retiredPayload] = await Promise.all([
          buddySurfacePromise,
          api.listIndustryInstances({ status: "active" }),
          api.listIndustryInstances({ status: "retired" }),
        ]);
        const resolvedBuddyProfileId = resolveCanonicalBuddyProfileId(
          buddySurface?.profile?.profile_id,
        );
        const resolvedBuddyCarrierInstanceId =
          typeof buddySurface?.execution_carrier?.instance_id === "string"
            ? buddySurface.execution_carrier.instance_id.trim() || null
            : null;
        setCurrentBuddyProfileId(resolvedBuddyProfileId || null);
        setCurrentBuddyCarrierInstanceId(resolvedBuddyCarrierInstanceId);
        const nextInstances = Array.isArray(activePayload) ? activePayload : [];
        const nextRetiredInstances = Array.isArray(retiredPayload)
          ? retiredPayload
          : [];
        const knownInstanceIds = new Set(
          [...nextInstances, ...nextRetiredInstances].map((item) => item.instance_id),
        );
        let hydratedCurrentCarrier: IndustryInstanceDetail | null = null;
        if (
          resolvedBuddyCarrierInstanceId
          && !knownInstanceIds.has(resolvedBuddyCarrierInstanceId)
        ) {
          try {
            hydratedCurrentCarrier = await api.getRuntimeIndustryDetail(
              resolvedBuddyCarrierInstanceId,
            );
          } catch {
            hydratedCurrentCarrier = null;
          }
          if (hydratedCurrentCarrier) {
            const targetBucket =
              hydratedCurrentCarrier.status === "retired"
                ? nextRetiredInstances
                : nextInstances;
            targetBucket.unshift(hydratedCurrentCarrier);
          }
        }
        setInstances(nextInstances);
        setRetiredInstances(nextRetiredInstances);
        const candidateId = preferredInstanceId ?? selectedInstanceIdRef.current;
        const nextSelected = resolvePreferredIndustryInstanceId({
          instances: [...nextInstances, ...nextRetiredInstances],
          preferredInstanceId: candidateId,
          buddyCarrierInstanceId: resolvedBuddyCarrierInstanceId,
          buddyProfileId: resolvedBuddyProfileId,
        });
        setSelectedInstanceId(nextSelected);
        const nextDetailByInstanceId = hydratedCurrentCarrier
          ? {
              ...industryPageStateCache.detailByInstanceId,
              [hydratedCurrentCarrier.instance_id]: hydratedCurrentCarrier,
            }
          : industryPageStateCache.detailByInstanceId;
        industryPageStateCache = {
          ...industryPageStateCache,
          instances: nextInstances,
          retiredInstances: nextRetiredInstances,
          selectedInstanceId: nextSelected,
          currentBuddyProfileId: resolvedBuddyProfileId || null,
          currentBuddyCarrierInstanceId: resolvedBuddyCarrierInstanceId,
          detailByInstanceId: nextDetailByInstanceId,
        };
      } catch (fetchError) {
        setError(
          fetchError instanceof Error ? fetchError.message : String(fetchError),
        );
      } finally {
        setLoadingInstances(false);
      }
    },
    [],
  );

  const loadDetail = useCallback(async (
    instanceId: string | null,
    options?: IndustryDetailLoadOptions,
  ) => {
    if (!instanceId) {
      setDetail(null);
      return null;
    }
    const canUseCachedDetail = !options?.assignmentId && !options?.backlogItemId;
    const cachedDetail = canUseCachedDetail ? readCachedIndustryDetail(instanceId) : null;
    if (!cachedDetail) {
      setLoadingDetail(true);
    }
    try {
      setError(null);
      const payload = await api.getRuntimeIndustryDetail(instanceId, options);
      setDetail(payload);
      if (canUseCachedDetail) {
        industryPageStateCache = {
          ...industryPageStateCache,
          detailByInstanceId: {
            ...industryPageStateCache.detailByInstanceId,
            [instanceId]: payload,
          },
        };
      }
      return payload;
    } catch (fetchError) {
      setError(
        fetchError instanceof Error ? fetchError.message : String(fetchError),
      );
      if (!cachedDetail) {
        setDetail(null);
      }
      return null;
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  const appendBriefMediaItem = useCallback((nextItem: IndustryBriefMediaItem) => {
    const nextKey =
      nextItem.source.url ||
      nextItem.source.storage_uri ||
      `${nextItem.source.filename || nextItem.id}:${nextItem.source.size_bytes || ""}`;
    setBriefMediaItems((current) => {
      const filtered = current.filter((item) => {
        const itemKey =
          item.source.url ||
          item.source.storage_uri ||
          `${item.source.filename || item.id}:${item.source.size_bytes || ""}`;
        return itemKey !== nextKey;
      });
      return [...filtered, nextItem];
    });
  }, []);

  const handleAddBriefMediaLink = useCallback(async () => {
    const normalizedLink = briefMediaLink.trim();
    if (!normalizedLink) {
      return;
    }
    setBriefMediaBusy(true);
    try {
      const payload = await api.resolveMediaLink({
        url: normalizedLink,
        entry_point: "industry-preview",
        purpose: "draft-enrichment",
      });
      appendBriefMediaItem({
        id: payload.resolved_source.source_id || payload.normalized_url,
        source: payload.resolved_source,
        analysis_mode_options: payload.analysis_mode_options || [],
        warnings: payload.warnings || [],
      });
      setBriefMediaLink("");
      message.success("已添加媒体链接。");
    } catch (nextError) {
      message.error(nextError instanceof Error ? nextError.message : String(nextError));
    } finally {
      setBriefMediaBusy(false);
    }
  }, [appendBriefMediaItem, briefMediaLink]);

  const handleBriefUploadChange = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from((event?.target?.files || []) as File[]);
    if (!files.length) {
      return;
    }
    setBriefMediaBusy(true);
    try {
      for (const file of files) {
        const payload = await api.ingestMedia(
          {
            source_kind: "upload",
            entry_point: "industry-preview",
            purpose: "draft-enrichment",
            filename: file.name,
            mime_type: file.type || undefined,
            size_bytes: file.size,
          },
          file,
        );
        appendBriefMediaItem({
          id: payload.source.source_id || `${file.name}:${file.size}`,
          source: payload.source,
          analysis_mode_options: payload.analysis_mode_options || [],
          warnings: payload.warnings || [],
        });
      }
      message.success("已上传媒体文件。");
    } catch (nextError) {
      message.error(nextError instanceof Error ? nextError.message : String(nextError));
    } finally {
      if (event?.target) {
        event.target.value = "";
      }
      setBriefMediaBusy(false);
    }
  }, [appendBriefMediaItem]);

  const handleBriefMediaModeChange = useCallback((itemId: string, analysisMode: AnalysisMode) => {
    setBriefMediaItems((current) =>
      current.map((item) =>
        item.id === itemId
          ? {
              ...item,
              source: {
                ...item.source,
                analysis_mode: analysisMode,
              },
            }
          : item,
      ),
    );
  }, []);

  const handleRemoveBriefMediaItem = useCallback((itemId: string) => {
    setBriefMediaItems((current) => current.filter((item) => item.id !== itemId));
  }, []);

  const loadInstanceIntoDraft = useCallback(() => {
    if (!detail) {
      return;
    }
    const draft = detailToDraftPlan(detail);
    setPreview({
      profile: detail.profile,
      draft,
      recommendation_pack: {
        summary: "",
        items: [],
        warnings: [],
        sections: [],
      },
      readiness_checks: [],
      can_activate: true,
      media_analyses: detail.media_analyses || [],
      media_warnings: [],
    });
    setInstallPlan([]);
    setDraftSourceInstanceId(detail.instance_id);
    draftForm.resetFields();
    draftForm.setFieldsValue(draft);
    message.success(INDUSTRY_TEXT.loadIntoDraft);
  }, [detail, draftForm]);

  useEffect(() => {
    void loadInstances();
  }, [loadInstances]);

  useEffect(() => {
    void loadDetail(selectedInstanceId);
  }, [loadDetail, selectedInstanceId]);

  const handlePreview = useCallback(async (values: IndustryBriefFormValues) => {
    setPreviewLoading(true);
    try {
      setError(null);
      const payload = await api.previewIndustry(
        toPreviewPayload(values, briefMediaItems),
      );
      const nextDraftSourceInstanceId =
        draftSourceInstanceId || detail?.instance_id || null;
      setPreview(payload);
      setDraftSourceInstanceId(nextDraftSourceInstanceId);
      setInstallPlan(
        (payload.recommendation_pack?.items || [])
          .filter((item) => item.selected)
          .map((item) => recommendationToInstallItem(item)),
      );
      draftForm.resetFields();
      draftForm.setFieldsValue(normalizeDraftPlan(payload.draft));
      if (payload.can_activate) {
        message.success(INDUSTRY_TEXT.previewPlan);
      } else {
        message.warning(INDUSTRY_TEXT.previewBlockedWarning);
      }
      return true;
    } catch (previewError) {
      const nextError =
        previewError instanceof Error ? previewError.message : String(previewError);
      setError(nextError);
      message.error(nextError);
      return false;
    } finally {
      setPreviewLoading(false);
    }
  }, [briefMediaItems, detail?.instance_id, draftForm, draftSourceInstanceId]);

  const handleApplyCarrierAdjustment = useCallback(async () => {
    if (!preview) {
      message.warning(INDUSTRY_TEXT.previewBeforeActivate);
      return;
    }
    const boundCarrierInstanceId = draftSourceInstanceId?.trim() || "";
    if (!boundCarrierInstanceId) {
      const nextError = "当前没有可调整的执行载体，请先完成伙伴建档。";
      setError(nextError);
      message.error(nextError);
      return;
    }
    setApplyCarrierLoading(true);
    try {
      setError(null);
      const draft = normalizeDraftPlan(draftForm.getFieldsValue(true));
      const requestPayload = {
        profile: preview.profile,
        draft,
        install_plan: installPlan.map((item) => stripInstallPlanDraftItem(item)),
        auto_activate: true,
        auto_dispatch: false,
        execute: false,
        media_analysis_ids: (preview.media_analyses || []).map((item) => item.analysis_id),
      };
      const payload: IndustryBootstrapResponse = await api.updateIndustryTeam(
        boundCarrierInstanceId,
        requestPayload,
      );
      const instanceId = payload.team.team_id;
      setSelectedInstanceId(instanceId);
      setPreview(null);
      setDraftSourceInstanceId(null);
      setInstallPlan([]);
      setBriefMediaItems([]);
      setBriefMediaLink("");
      draftForm.resetFields();
      message.success(INDUSTRY_TEXT.updateSuccess);
      await loadInstances(instanceId);
      await loadDetail(instanceId);
    } catch (bootstrapError) {
      const nextError =
        bootstrapError instanceof Error
          ? bootstrapError.message
          : String(bootstrapError);
      setError(nextError);
      message.error(nextError);
    } finally {
      setApplyCarrierLoading(false);
    }
  }, [draftForm, draftSourceInstanceId, installPlan, loadDetail, loadInstances, preview]);

  const handleDeleteInstance = useCallback(
    async (instanceId: string) => {
      setDeletingInstanceId(instanceId);
      try {
        setError(null);
        await api.deleteIndustryInstance(instanceId);
        if (selectedInstanceId === instanceId) {
          setDetail(null);
        }
        message.success("已删除团队。");
        await loadInstances(selectedInstanceId === instanceId ? null : selectedInstanceId);
      } catch (deleteError) {
        const nextError =
          deleteError instanceof Error ? deleteError.message : String(deleteError);
        setError(nextError);
        message.error(nextError);
      } finally {
        setDeletingInstanceId(null);
        if (draftSourceInstanceId === instanceId) {
          setDraftSourceInstanceId(null);
        }
        if (industryPageStateCache.detailByInstanceId[instanceId]) {
          const nextDetailByInstanceId = { ...industryPageStateCache.detailByInstanceId };
          delete nextDetailByInstanceId[instanceId];
          industryPageStateCache = {
            ...industryPageStateCache,
            detailByInstanceId: nextDetailByInstanceId,
          };
        }
      }
    },
    [draftSourceInstanceId, loadInstances, selectedInstanceId],
  );

  const selectedSummary = useMemo(
    () =>
      instances.find((item) => item.instance_id === selectedInstanceId) ||
      retiredInstances.find((item) => item.instance_id === selectedInstanceId) ||
      instances[0] ||
      null,
    [instances, retiredInstances, selectedInstanceId],
  );
  const selectedExecutionCoreRole = useMemo(
    () => (detail ? resolveIndustryExecutionCoreRole(detail) : null),
    [detail],
  );

  const handleOpenExecutionCoreChat = useCallback(async () => {
    if (!detail || !selectedExecutionCoreRole) {
      return;
    }
    try {
      await openRuntimeChat(
        buildIndustryRoleChatBinding(detail, selectedExecutionCoreRole),
        navigate,
      );
    } catch (chatError) {
      message.error(
        chatError instanceof Error
          ? chatError.message
          : INDUSTRY_TEXT.chatOpenFailed,
      );
    }
  }, [detail, navigate, selectedExecutionCoreRole]);

  const handleSelectAssignmentFocus = useCallback(
    async (assignmentId: string) => {
      if (!selectedInstanceId) {
        return null;
      }
      return loadDetail(selectedInstanceId, {
        assignmentId,
      });
    },
    [loadDetail, selectedInstanceId],
  );

  const handleSelectBacklogFocus = useCallback(
    async (backlogItemId: string) => {
      if (!selectedInstanceId) {
        return null;
      }
      return loadDetail(selectedInstanceId, {
        backlogItemId,
      });
    },
    [loadDetail, selectedInstanceId],
  );

  const handleClearRuntimeFocus = useCallback(async () => {
    if (!selectedInstanceId) {
      return null;
    }
    return loadDetail(selectedInstanceId);
  }, [loadDetail, selectedInstanceId]);

  const handleOpenAgentReportChat = useCallback(
    async (report: IndustryRuntimeAgentReport) => {
      if (!detail || !selectedExecutionCoreRole) {
        return;
      }
      const reportMetadata =
        report.metadata && typeof report.metadata === "object" ? report.metadata : {};
      const workContextId =
        report.work_context_id?.trim() ||
        (typeof reportMetadata.work_context_id === "string"
          ? reportMetadata.work_context_id.trim()
          : "") ||
        undefined;
      const contextKey =
        report.context_key?.trim() ||
        (typeof reportMetadata.context_key === "string"
          ? reportMetadata.context_key.trim()
          : "") ||
        undefined;
      try {
        const binding = buildIndustryRoleChatBinding(detail, selectedExecutionCoreRole);
        await openRuntimeChat(
          {
            ...binding,
            meta: {
              ...(binding.meta || {}),
              work_context_id: workContextId,
              context_key: contextKey || binding.meta?.context_key,
              current_focus_kind: "agent-report",
              current_focus_id: report.report_id,
              current_focus: report.headline || report.summary || undefined,
              assignment_id: report.assignment_id || undefined,
            },
          },
          navigate,
        );
      } catch (chatError) {
        message.error(
          chatError instanceof Error
            ? chatError.message
            : INDUSTRY_TEXT.chatOpenFailed,
        );
      }
    },
    [detail, navigate, selectedExecutionCoreRole],
  );

  const roleOptions = useMemo(() => {
    const seen = new Set<string>();
    return draftAgents.reduce<Array<{ label: string; value: string }>>((items, role, index) => {
      const value = [role.agent_id, role.role_id, role.role_name, role.name].find(
        (entry) => Boolean(entry?.trim()),
      );
      if (!value || seen.has(value)) {
        return items;
      }
      seen.add(value);
      items.push({
        label:
          normalizeSpiderMeshBrand(role.role_name || role.name) ||
          role.role_id ||
          `${INDUSTRY_TEXT.roleFallback} ${index + 1}`,
        value,
      });
      return items;
    }, []);
  }, [draftAgents]);

  const recommendationById = useMemo(
    () =>
      new Map(
        (preview?.recommendation_pack?.items || []).map((item) => [
          item.recommendation_id,
          item,
        ]),
      ),
    [preview],
  );

  const recommendationSections = useMemo(() => {
    if (!preview?.recommendation_pack) {
      return [];
    }
    if (preview.recommendation_pack.sections?.length) {
      return preview.recommendation_pack.sections;
    }
    return buildFallbackRecommendationSections(
      preview.recommendation_pack.items || [],
      draftAgents,
    );
  }, [draftAgents, preview]);

  const recommendationDisplayGroups = useMemo<RecommendationDisplayGroup[]>(() => {
    const executionCoreSections = recommendationSections.filter(
      (section) => section.section_kind === "execution-core" && section.items.length,
    );
    const deliverySections = recommendationSections.filter(
      (section) => section.section_kind !== "execution-core" && section.items.length,
    );
    const groups: RecommendationDisplayGroup[] = [];
    if (executionCoreSections.length) {
      groups.push({
        group_id: "execution-core",
        title: "主脑推荐",
        summary: "展示主脑控制核相关的能力建议与安装项。",
        sections: executionCoreSections,
      });
    }
    if (deliverySections.length) {
      groups.push({
        group_id: "delivery",
        title: "执行位推荐",
        summary: "展示执行岗位可承接的能力建议与安装项。",
        sections: deliverySections,
      });
    }
    return groups;
  }, [recommendationSections]);

  const recommendationWarnings = preview?.recommendation_pack?.warnings || [];
  const hasCapabilityPlanning =
    recommendationDisplayGroups.length > 0 || installPlan.length > 0;

  const draftCounts = useMemo(
    () => ({
      roles: draftAgents.length,
      goals: draftGoals.length,
      schedules: draftSchedules.length,
    }),
    [draftAgents.length, draftGoals.length, draftSchedules.length],
  );
  const isEditingExistingTeam = Boolean(draftSourceInstanceId);

  const installPlanByRecommendationId = useMemo(
    () =>
      installPlan.reduce<Record<string, InstallPlanDraftItem>>((items, item) => {
        const key = item.recommendation_id?.trim();
        if (key) {
          items[key] = item;
        }
        return items;
      }, {}),
    [installPlan],
  );

  const handleToggleRecommendation = useCallback(
    (recommendation: IndustryCapabilityRecommendation, checked: boolean) => {
      setInstallPlan((current) => {
        const next = current.filter(
          (item) => item.recommendation_id !== recommendation.recommendation_id,
        );
        if (!checked) {
          return next;
        }
        return [...next, recommendationToInstallItem(recommendation)];
      });
    },
    [],
  );

  const handleAddCustomInstallItem = useCallback(() => {
    setInstallPlan((current) => [
      ...current,
      createBlankInstallPlanItem(draftAgents[0]?.agent_id),
    ]);
  }, [draftAgents]);

  const handleRemoveInstallPlanItem = useCallback((planItemKey: string) => {
    setInstallPlan((current) =>
      current.filter((item) => item.plan_item_key !== planItemKey),
    );
  }, []);

  const handlePatchInstallPlanItem = useCallback(
    (planItemKey: string, patch: Partial<InstallPlanDraftItem>) => {
      setInstallPlan((current) =>
        current.map((item) =>
          item.plan_item_key === planItemKey
            ? {
                ...item,
                ...patch,
              }
            : item,
        ),
      );
    },
    [],
  );

  const handleChangeRecommendationReviewAcknowledgement = useCallback(
    (recommendationId: string, checked: boolean) => {
      const planItemKey =
        installPlanByRecommendationId[recommendationId]?.plan_item_key;
      if (!planItemKey) {
        return;
      }
      handlePatchInstallPlanItem(planItemKey, {
        review_acknowledged: checked,
      });
    },
    [handlePatchInstallPlanItem, installPlanByRecommendationId],
  );

  const handleChangeRecommendationTargets = useCallback(
    (recommendationId: string, targetAgentIds: string[]) => {
      const planItemKey =
        installPlanByRecommendationId[recommendationId]?.plan_item_key;
      if (!planItemKey) {
        return;
      }
      handlePatchInstallPlanItem(planItemKey, {
        target_agent_ids: uniqueStrings(targetAgentIds),
      });
    },
    [handlePatchInstallPlanItem, installPlanByRecommendationId],
  );

  const allTeams = useMemo(() => {
    const seen = new Set<string>();
    const merged: IndustryInstanceSummary[] = [];
    for (const item of instances) {
      if (!seen.has(item.instance_id)) { seen.add(item.instance_id); merged.push(item); }
    }
    for (const item of retiredInstances) {
      if (!seen.has(item.instance_id)) { seen.add(item.instance_id); merged.push(item); }
    }
    return merged;
  }, [instances, retiredInstances]);

  const isEditing = Boolean(preview);

  return {
    allTeams,
    applyCarrierLoading,
    briefMediaBusy,
    briefMediaItems,
    briefMediaLink,
    briefModalOpen,
    briefUploadInputRef,
    deletingInstanceId,
    detail,
    draftAgents,
    draftCounts,
    draftForm,
    draftGenerationSummary,
    draftGoals,
    draftSchedules,
    draftSourceInstanceId,
    draftTeamLabel,
    draftTeamSummary,
    error,
    handleAddBriefMediaLink,
    handleAddCustomInstallItem,
    handleApplyCarrierAdjustment,
    handleBriefMediaModeChange,
    handleBriefUploadChange,
    handleChangeRecommendationReviewAcknowledgement,
    handleChangeRecommendationTargets,
    handleDeleteInstance,
    handleClearRuntimeFocus,
    handleOpenAgentReportChat,
    handleOpenExecutionCoreChat,
    handlePatchInstallPlanItem,
    handlePreview,
    handleRemoveBriefMediaItem,
    handleRemoveInstallPlanItem,
    handleSelectAssignmentFocus,
    handleSelectBacklogFocus,
    handleToggleRecommendation,
    hasCapabilityPlanning,
    installPlan,
    installPlanByRecommendationId,
    instances,
    isEditing,
    isEditingExistingTeam,
    loadDetail,
    loadInstanceIntoDraft,
    loadInstances,
    loadingDetail,
    loadingInstances,
    preview,
    previewLoading,
    recommendationById,
    recommendationDisplayGroups,
    recommendationSections,
    recommendationWarnings,
    currentBuddyProfileId,
    retiredInstances,
    roleOptions,
    protectedCarrierInstanceId,
    selectedExecutionCoreRole,
    selectedInstanceId,
    selectedSummary,
    setBriefMediaLink,
    setBriefModalOpen,
    setDraftSourceInstanceId,
    setError,
    setInstallPlan,
    setPreview,
    setSelectedInstanceId,
    watchedExperienceMode,
  };
}

export function resetIndustryPageStateCache(): void {
  industryPageStateCache = {
    instances: [],
    retiredInstances: [],
    selectedInstanceId: null,
    currentBuddyProfileId: null,
    currentBuddyCarrierInstanceId: null,
    detailByInstanceId: {},
  };
}
