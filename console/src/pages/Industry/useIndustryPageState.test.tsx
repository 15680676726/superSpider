// @vitest-environment jsdom

import { renderHook, waitFor } from "@testing-library/react";
import { Form } from "antd";
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../../api", async () => {
  const actual = await vi.importActual<typeof import("../../api")>(
    "../../api",
  );
  return {
    ...actual,
    default: {
      ...actual.default,
      listIndustryInstances: vi.fn(),
      getRuntimeIndustryDetail: vi.fn(),
      getBuddySurface: vi.fn(),
      previewIndustry: vi.fn(),
      bootstrapIndustry: vi.fn(),
      updateIndustryTeam: vi.fn(),
    },
  };
});

vi.mock("../../utils/runtimeChat", () => ({
  buildIndustryRoleChatBinding: vi.fn(),
  openRuntimeChat: vi.fn(),
  resolveIndustryExecutionCoreRole: vi.fn((detail: { team?: { agents?: Array<{ role_id?: string }> } }) =>
    detail?.team?.agents?.find((agent) => agent.role_id === "execution-core") || null
  ),
}));

import api from "../../api";
import {
  buildIndustryRoleChatBinding,
  openRuntimeChat,
} from "../../utils/runtimeChat";
import {
  resetIndustryPageStateCache,
  resolveProtectedCarrierInstanceId,
  useIndustryPageState,
} from "./useIndustryPageState";

const mockedListIndustryInstances = vi.mocked(api.listIndustryInstances);
const mockedGetRuntimeIndustryDetail = vi.mocked(api.getRuntimeIndustryDetail);
const mockedGetBuddySurface = vi.mocked(api.getBuddySurface);
const mockedPreviewIndustry = vi.mocked(api.previewIndustry);
const mockedBootstrapIndustry = vi.mocked(api.bootstrapIndustry);
const mockedUpdateIndustryTeam = vi.mocked(api.updateIndustryTeam);
const mockedBuildIndustryRoleChatBinding = vi.mocked(buildIndustryRoleChatBinding);
const mockedOpenRuntimeChat = vi.mocked(openRuntimeChat);

describe("useIndustryPageState", () => {
  afterEach(() => {
    window.localStorage.clear();
    resetIndustryPageStateCache();
    mockedListIndustryInstances.mockReset();
    mockedGetRuntimeIndustryDetail.mockReset();
    mockedGetBuddySurface.mockReset();
    mockedPreviewIndustry.mockReset();
    mockedBootstrapIndustry.mockReset();
    mockedUpdateIndustryTeam.mockReset();
    mockedBuildIndustryRoleChatBinding.mockReset();
    mockedOpenRuntimeChat.mockReset();
  });

  it("loads active and retired teams through the extracted page-state hook", async () => {
    mockedListIndustryInstances.mockImplementation(async (options) => {
      const status =
        typeof options === "object" && options ? options.status : undefined;
      if (status === "retired") {
        return [
          {
            instance_id: "industry-retired",
            label: "Retired Team",
            owner_scope: "industry-retired",
          },
        ] as never;
      }
      return [
        {
          instance_id: "industry-active",
          label: "Active Team",
          owner_scope: "industry-active",
          team: { agents: [] },
        },
      ] as never;
    });
    mockedGetRuntimeIndustryDetail.mockResolvedValue({
      instance_id: "industry-active",
      label: "Active Team",
      owner_scope: "industry-active",
      profile: { industry: "Retail" },
      team: { agents: [] },
      media_analyses: [],
    } as never);

    const { result } = renderHook(() => {
      const [briefForm] = Form.useForm();
      const [draftForm] = Form.useForm();
      return useIndustryPageState({
        briefForm,
        draftForm,
        navigate: vi.fn() as never,
      });
    });

    await waitFor(() => {
      expect(result.current.instances).toHaveLength(1);
      expect(result.current.retiredInstances).toHaveLength(1);
      expect(result.current.detail?.instance_id).toBe("industry-active");
    });

    expect(result.current.selectedInstanceId).toBe("industry-active");
    expect(mockedListIndustryInstances).toHaveBeenCalledTimes(2);
    expect(mockedGetRuntimeIndustryDetail).toHaveBeenCalledWith(
      "industry-active",
      undefined,
    );
  });

  it("shows the active list before retired carriers finish loading", async () => {
    let resolveRetired!: (value: unknown) => void;
    mockedListIndustryInstances.mockImplementation((options) => {
      const status =
        typeof options === "object" && options ? options.status : undefined;
      if (status === "retired") {
        return new Promise((resolve) => {
          resolveRetired = resolve;
        }) as never;
      }
      return Promise.resolve([
        {
          instance_id: "industry-active",
          label: "Active Team",
          owner_scope: "industry-active",
          team: { agents: [] },
        },
      ]) as never;
    });
    mockedGetRuntimeIndustryDetail.mockResolvedValue({
      instance_id: "industry-active",
      label: "Active Team",
      owner_scope: "industry-active",
      profile: { industry: "Retail" },
      team: { agents: [] },
      media_analyses: [],
    } as never);

    const { result } = renderHook(() => {
      const [briefForm] = Form.useForm();
      const [draftForm] = Form.useForm();
      return useIndustryPageState({
        briefForm,
        draftForm,
        navigate: vi.fn() as never,
      });
    });

    await waitFor(() => {
      expect(result.current.instances).toHaveLength(1);
    });

    expect(result.current.loadingInstances).toBe(false);
    expect(result.current.retiredInstances).toHaveLength(0);

    await act(async () => {
      resolveRetired([]);
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(result.current.retiredInstances).toHaveLength(0);
    });
  });

  it("prefers the buddy-generated execution carrier over unrelated active instances", async () => {
    mockedGetBuddySurface.mockResolvedValue({
      profile: {
        profile_id: "profile-1",
      },
      execution_carrier: {
        instance_id: "buddy:profile-1:stocks",
      },
    } as never);
    mockedListIndustryInstances.mockImplementation(async (options) => {
      const status =
        typeof options === "object" && options ? options.status : undefined;
      if (status === "retired") {
        return [] as never;
      }
      return [
        {
          instance_id: "industry-other",
          label: "Other Team",
          owner_scope: "industry-other",
          team: { agents: [] },
        },
      ] as never;
    });
    mockedGetRuntimeIndustryDetail.mockImplementation(async (instanceId) => ({
      instance_id: instanceId,
      label:
        instanceId === "buddy:profile-1:stocks" ? "Buddy Carrier" : "Other Team",
      owner_scope:
        instanceId === "buddy:profile-1:stocks" ? "profile-1" : "industry-other",
      profile: { industry: "Retail" },
      team: { agents: [] },
      media_analyses: [],
    } as never));

    const { result } = renderHook(() => {
      const [briefForm] = Form.useForm();
      const [draftForm] = Form.useForm();
      return useIndustryPageState({
        briefForm,
        draftForm,
        navigate: vi.fn() as never,
      });
    });

    await waitFor(() => {
      expect(result.current.selectedInstanceId).toBe("buddy:profile-1:stocks");
      expect(result.current.detail?.instance_id).toBe("buddy:profile-1:stocks");
    });

    expect(
      mockedGetRuntimeIndustryDetail.mock.calls.some(
        ([instanceId]) => instanceId === "buddy:profile-1:stocks",
      ),
    ).toBe(true);
  });

  it("protects the current buddy carrier from server truth even when local storage is empty", async () => {
    mockedGetBuddySurface.mockResolvedValue({
      profile: {
        profile_id: "profile-7",
      },
      execution_carrier: {
        instance_id: "buddy:profile-7:design",
      },
    } as never);
    mockedListIndustryInstances.mockImplementation(async (options) => {
      const status =
        typeof options === "object" && options ? options.status : undefined;
      if (status === "retired") {
        return [] as never;
      }
      return [
        {
          instance_id: "industry-other",
          label: "Other Team",
          owner_scope: "industry-other",
          team: { agents: [] },
        },
      ] as never;
    });
    mockedGetRuntimeIndustryDetail.mockImplementation(async (instanceId) => ({
      instance_id: instanceId,
      label:
        instanceId === "buddy:profile-7:design" ? "Buddy Carrier" : "Other Team",
      owner_scope:
        instanceId === "buddy:profile-7:design" ? "profile-7" : "industry-other",
      profile: { industry: "Retail" },
      team: { agents: [] },
      media_analyses: [],
    } as never));

    const { result } = renderHook(() => {
      const [briefForm] = Form.useForm();
      const [draftForm] = Form.useForm();
      return useIndustryPageState({
        briefForm,
        draftForm,
        navigate: vi.fn() as never,
      });
    });

    await waitFor(() => {
      expect(result.current.protectedCarrierInstanceId).toBe("buddy:profile-7:design");
      expect(result.current.selectedInstanceId).toBe("buddy:profile-7:design");
    });
  });

  it("resolves the current buddy carrier as the protected instance id", () => {
    expect(
      resolveProtectedCarrierInstanceId({
        buddyCarrierInstanceId: "buddy:profile-1:stocks",
        buddyProfileId: "profile-1",
      }),
    ).toBe("buddy:profile-1:stocks");
    expect(
      resolveProtectedCarrierInstanceId({
        buddyCarrierInstanceId: "  ",
        buddyProfileId: "  profile-2  ",
      }),
    ).toBe("buddy:profile-2");
    expect(
      resolveProtectedCarrierInstanceId({
        buddyCarrierInstanceId: "",
        buddyProfileId: "",
      }),
    ).toBeNull();
    expect(
      resolveProtectedCarrierInstanceId({
        buddyCarrierInstanceId: null,
        buddyProfileId: null,
      }),
    ).toBeNull();
  });

  it("reuses the last industry list and detail snapshot on remount while refreshing in the background", async () => {
    mockedListIndustryInstances.mockImplementation(async (options) => {
      const status =
        typeof options === "object" && options ? options.status : undefined;
      if (status === "retired") {
        return [] as never;
      }
      return [
        {
          instance_id: "industry-active",
          label: "Active Team",
          owner_scope: "industry-active",
          team: { agents: [] },
        },
      ] as never;
    });
    mockedGetRuntimeIndustryDetail.mockResolvedValue({
      instance_id: "industry-active",
      label: "Active Team",
      owner_scope: "industry-active",
      profile: { industry: "Retail" },
      team: { agents: [] },
      media_analyses: [],
    } as never);

    const first = renderHook(() => {
      const [briefForm] = Form.useForm();
      const [draftForm] = Form.useForm();
      return useIndustryPageState({
        briefForm,
        draftForm,
        navigate: vi.fn() as never,
      });
    });

    await waitFor(() => {
      expect(first.result.current.instances).toHaveLength(1);
      expect(first.result.current.detail?.instance_id).toBe("industry-active");
    });

    first.unmount();

    mockedListIndustryInstances.mockImplementation(async (options) => {
      const status =
        typeof options === "object" && options ? options.status : undefined;
      if (status === "retired") {
        return [] as never;
      }
      return [
        {
          instance_id: "industry-next",
          label: "Next Team",
          owner_scope: "industry-next",
          team: { agents: [] },
        },
      ] as never;
    });
    mockedGetRuntimeIndustryDetail.mockResolvedValue({
      instance_id: "industry-next",
      label: "Next Team",
      owner_scope: "industry-next",
      profile: { industry: "Retail" },
      team: { agents: [] },
      media_analyses: [],
    } as never);

    const remounted = renderHook(() => {
      const [briefForm] = Form.useForm();
      const [draftForm] = Form.useForm();
      return useIndustryPageState({
        briefForm,
        draftForm,
        navigate: vi.fn() as never,
      });
    });

    expect(remounted.result.current.loadingInstances).toBe(false);
    expect(remounted.result.current.instances.map((item) => item.instance_id)).toEqual([
      "industry-active",
    ]);
    expect(remounted.result.current.detail?.instance_id).toBe("industry-active");

    await waitFor(() => {
      expect(remounted.result.current.instances.map((item) => item.instance_id)).toEqual([
        "industry-next",
      ]);
      expect(remounted.result.current.detail?.instance_id).toBe("industry-next");
    });
  });

  it("does not fall back to an unrelated team when the bound buddy carrier is missing", async () => {
    window.localStorage.setItem("copaw.buddy_profile_id", "profile-missing");
    mockedGetRuntimeIndustryDetail.mockResolvedValue({
      instance_id: "industry-other",
      label: "Other Team",
      owner_scope: "industry-other",
      profile: { industry: "Retail" },
      team: { agents: [] },
      media_analyses: [],
    } as never);
    mockedListIndustryInstances.mockResolvedValue([
      {
        instance_id: "industry-other",
        label: "Other Team",
        owner_scope: "industry-other",
        team: { agents: [] },
      },
    ] as never);

    const { result } = renderHook(() => {
      const [briefForm] = Form.useForm();
      const [draftForm] = Form.useForm();
      return useIndustryPageState({
        briefForm,
        draftForm,
        navigate: vi.fn() as never,
      });
    });

    await waitFor(() => {
      expect(result.current.instances).toHaveLength(1);
    });

    expect(result.current.selectedInstanceId).toBe("industry-other");
    expect(result.current.detail?.instance_id).toBe("industry-other");
    expect(mockedGetRuntimeIndustryDetail).toHaveBeenCalledWith(
      "industry-other",
      undefined,
    );
  });

  it("keeps the current carrier in update mode after regenerating a draft preview", async () => {
    mockedGetBuddySurface.mockResolvedValue({
      profile: {
        profile_id: "profile-1",
      },
    } as never);
    mockedListIndustryInstances.mockResolvedValue([
      {
        instance_id: "buddy:profile-1",
        label: "Buddy Carrier",
        owner_scope: "profile-1",
        team: {
          agents: [
            {
              role_id: "execution-core",
              agent_id: "agent-main-brain",
              name: "Spider Mesh 主脑",
            },
          ],
        },
      },
    ] as never);
    mockedGetRuntimeIndustryDetail.mockResolvedValue({
      instance_id: "buddy:profile-1",
      label: "Buddy Carrier",
      owner_scope: "profile-1",
      profile: { industry: "Retail" },
      team: {
        agents: [
          {
            role_id: "execution-core",
            agent_id: "agent-main-brain",
            name: "Spider Mesh 主脑",
          },
        ],
      },
      goals: [],
      schedules: [],
      media_analyses: [],
    } as never);
    mockedPreviewIndustry.mockResolvedValue({
      profile: { industry: "Retail" },
      draft: {
        team: {
          label: "Buddy Carrier",
          summary: "Adjusted carrier",
          agents: [],
        },
        goals: [],
        schedules: [],
        generation_summary: "Adjusted draft",
      },
      recommendation_pack: {
        summary: "",
        items: [],
        warnings: [],
        sections: [],
      },
      readiness_checks: [],
      can_activate: true,
      media_analyses: [],
      media_warnings: [],
    } as never);
    mockedUpdateIndustryTeam.mockResolvedValue({
      team: {
        team_id: "buddy:profile-1",
        label: "Buddy Carrier",
        agents: [
          {
            role_id: "execution-core",
            agent_id: "agent-main-brain",
            name: "Spider Mesh 主脑",
          },
        ],
      },
      routes: {
        instance_summary: {
          instance_id: "buddy:profile-1",
          label: "Buddy Carrier",
          owner_scope: "profile-1",
          team: {
            agents: [
              {
                role_id: "execution-core",
                agent_id: "agent-main-brain",
                name: "Spider Mesh 主脑",
              },
            ],
          },
        },
      },
    } as never);
    mockedBootstrapIndustry.mockResolvedValue({
      team: {
        team_id: "industry-new",
        label: "Wrong branch",
        agents: [],
      },
      routes: {},
    } as never);

    const { result } = renderHook(() => {
      const [briefForm] = Form.useForm();
      const [draftForm] = Form.useForm();
      return useIndustryPageState({
        briefForm,
        draftForm,
        navigate: vi.fn() as never,
      });
    });

    await waitFor(() => {
      expect(result.current.selectedInstanceId).toBe("buddy:profile-1");
    });

    act(() => {
      result.current.loadInstanceIntoDraft();
    });

    await waitFor(() => {
      expect(result.current.draftSourceInstanceId).toBe("buddy:profile-1");
    });

    await act(async () => {
      const ok = await result.current.handlePreview({
        industry: "Retail",
        company_name: "Buddy Co",
        product: "Companion",
        target_customers: "Creators",
        goals: "Long-term growth",
        constraints: "Time",
        notes: "",
        experience_mode: "system-led",
        experience_notes: "",
        operator_requirements: "",
      });
      expect(ok).toBe(true);
    });

    expect(result.current.draftSourceInstanceId).toBe("buddy:profile-1");

    await act(async () => {
      await result.current.handleApplyCarrierAdjustment();
    });

    expect(mockedUpdateIndustryTeam).toHaveBeenCalledWith(
      "buddy:profile-1",
      expect.any(Object),
    );
    expect(mockedBootstrapIndustry).not.toHaveBeenCalled();
  });

  it("blocks carrier adjustment when no existing carrier is bound", async () => {
    mockedListIndustryInstances.mockResolvedValue([] as never);
    mockedPreviewIndustry.mockResolvedValue({
      profile: { industry: "Retail" },
      draft: {
        team: {
          label: "Unbound Carrier",
          summary: "Should never bootstrap from industry page",
          agents: [],
        },
        goals: [],
        schedules: [],
        generation_summary: "Preview only",
      },
      recommendation_pack: {
        summary: "",
        items: [],
        warnings: [],
        sections: [],
      },
      readiness_checks: [],
      can_activate: true,
      media_analyses: [],
      media_warnings: [],
    } as never);

    const { result } = renderHook(() => {
      const [briefForm] = Form.useForm();
      const [draftForm] = Form.useForm();
      return useIndustryPageState({
        briefForm,
        draftForm,
        navigate: vi.fn() as never,
      });
    });

    await waitFor(() => {
      expect(result.current.instances).toHaveLength(0);
      expect(result.current.detail).toBeNull();
    });

    await act(async () => {
      const ok = await result.current.handlePreview({
        industry: "Retail",
        company_name: "No Carrier Co",
        product: "Companion",
        target_customers: "Creators",
        goals: "Long-term growth",
        constraints: "Time",
        notes: "",
        experience_mode: "system-led",
        experience_notes: "",
        operator_requirements: "",
      });
      expect(ok).toBe(true);
    });

    expect(result.current.draftSourceInstanceId).toBeNull();

    await act(async () => {
      await result.current.handleApplyCarrierAdjustment();
    });

    expect(mockedUpdateIndustryTeam).not.toHaveBeenCalled();
    expect(mockedBootstrapIndustry).not.toHaveBeenCalled();
    expect(result.current.error).toBe("当前没有可调整的执行载体，请先完成伙伴建档。");
  });

  it("reloads detail with a focused runtime subview when selecting an assignment or backlog item", async () => {
    mockedListIndustryInstances.mockResolvedValue([
      {
        instance_id: "industry-active",
        label: "Active Team",
        owner_scope: "industry-active",
        team: { agents: [] },
      },
    ] as never);
    mockedGetRuntimeIndustryDetail.mockImplementation(
      async (instanceId, options) =>
        ({
          instance_id: instanceId,
          label: "Active Team",
          owner_scope: "industry-active",
          profile: { industry: "Retail" },
          team: {
            agents: [
              {
                role_id: "execution-core",
                agent_id: "agent-main-brain",
                name: "Spider Mesh 主脑",
              },
            ],
          },
          focus_selection: options?.assignmentId
            ? {
                selection_kind: "assignment",
                assignment_id: options.assignmentId,
                title: "Focused assignment",
              }
            : options?.backlogItemId
              ? {
                  selection_kind: "backlog",
                  backlog_item_id: options.backlogItemId,
                  title: "Focused backlog",
                }
              : null,
          assignments: [
            {
              assignment_id: "assignment-1",
              title: "Assignment 1",
              status: "running",
              selected: options?.assignmentId === "assignment-1",
              evidence_ids: [],
              metadata: {},
            },
          ],
          backlog: [
            {
              backlog_item_id: "backlog-1",
              title: "Backlog 1",
              status: "open",
              priority: 1,
              source_kind: "chat-writeback",
              evidence_ids: [],
              metadata: {},
              selected: options?.backlogItemId === "backlog-1",
            },
          ],
          staffing: {
            pending_proposals: [],
            temporary_seats: [],
          },
          goals: [],
          agents: [],
          schedules: [],
          lanes: [],
          current_cycle: null,
          cycles: [],
          agent_reports: [],
          tasks: [],
          decisions: [],
          evidence: [],
          patches: [],
          growth: [],
          proposals: [],
          reports: {
            daily: {
              window: "daily",
              since: "2026-03-26T00:00:00Z",
              until: "2026-03-26T23:59:59Z",
              evidence_count: 0,
              proposal_count: 0,
              patch_count: 0,
              applied_patch_count: 0,
              growth_count: 0,
              decision_count: 0,
              recent_evidence: [],
              highlights: [],
            },
            weekly: {
              window: "weekly",
              since: "2026-03-20T00:00:00Z",
              until: "2026-03-26T23:59:59Z",
              evidence_count: 0,
              proposal_count: 0,
              patch_count: 0,
              applied_patch_count: 0,
              growth_count: 0,
              decision_count: 0,
              recent_evidence: [],
              highlights: [],
            },
          },
          media_analyses: [],
        }) as never,
    );

    const { result } = renderHook(() => {
      const [briefForm] = Form.useForm();
      const [draftForm] = Form.useForm();
      return useIndustryPageState({
        briefForm,
        draftForm,
        navigate: vi.fn() as never,
      });
    });

    await waitFor(() => {
      expect(result.current.detail?.instance_id).toBe("industry-active");
    });

    await act(async () => {
      await result.current.handleSelectAssignmentFocus("assignment-1");
    });

    expect(mockedGetRuntimeIndustryDetail).toHaveBeenLastCalledWith(
      "industry-active",
      { assignmentId: "assignment-1" },
    );
    expect(result.current.detail?.focus_selection?.assignment_id).toBe(
      "assignment-1",
    );

    await act(async () => {
      await result.current.handleSelectBacklogFocus("backlog-1");
    });

    expect(mockedGetRuntimeIndustryDetail).toHaveBeenLastCalledWith(
      "industry-active",
      { backlogItemId: "backlog-1" },
    );
    expect(result.current.detail?.focus_selection?.backlog_item_id).toBe(
      "backlog-1",
    );
  });

  it("opens report drill-down chat with the report work_context_id preserved", async () => {
    mockedListIndustryInstances.mockResolvedValue([
      {
        instance_id: "industry-active",
        label: "Active Team",
        owner_scope: "industry-active",
        team: {
          agents: [
            {
              role_id: "execution-core",
              agent_id: "agent-main-brain",
              name: "Spider Mesh 主脑",
            },
          ],
        },
      },
    ] as never);
    mockedGetRuntimeIndustryDetail.mockResolvedValue({
      instance_id: "industry-active",
      label: "Active Team",
      owner_scope: "industry-active",
      profile: { industry: "Retail" },
      team: {
        agents: [
          {
            role_id: "execution-core",
            agent_id: "agent-main-brain",
            name: "Spider Mesh 主脑",
          },
        ],
      },
      goals: [],
      agents: [],
      schedules: [],
      lanes: [],
      backlog: [],
      staffing: {
        pending_proposals: [],
        temporary_seats: [],
      },
      current_cycle: null,
      cycles: [],
      assignments: [],
      agent_reports: [
        {
          report_id: "report-1",
          headline: "Agent report",
          report_kind: "summary",
          status: "recorded",
          findings: [],
          uncertainties: [],
          needs_followup: false,
          evidence_ids: [],
          decision_ids: [],
          processed: false,
          metadata: {},
          work_context_id: "ctx-industry-report-1",
        },
      ],
      tasks: [],
      decisions: [],
      evidence: [],
      patches: [],
      growth: [],
      proposals: [],
      reports: {
        daily: {
          window: "daily",
          since: "2026-03-26T00:00:00Z",
          until: "2026-03-26T23:59:59Z",
          evidence_count: 0,
          proposal_count: 0,
          patch_count: 0,
          applied_patch_count: 0,
          growth_count: 0,
          decision_count: 0,
          recent_evidence: [],
          highlights: [],
        },
        weekly: {
          window: "weekly",
          since: "2026-03-20T00:00:00Z",
          until: "2026-03-26T23:59:59Z",
          evidence_count: 0,
          proposal_count: 0,
          patch_count: 0,
          applied_patch_count: 0,
          growth_count: 0,
          decision_count: 0,
          recent_evidence: [],
          highlights: [],
        },
      },
      media_analyses: [],
    } as never);
    mockedBuildIndustryRoleChatBinding.mockReturnValue({
      name: "Demo binding",
      threadId: "industry-chat:industry-active:execution-core",
      userId: "agent-main-brain",
      channel: "console",
      meta: {},
    });
    mockedOpenRuntimeChat.mockResolvedValue(undefined);

    const navigate = vi.fn();
    const { result } = renderHook(() => {
      const [briefForm] = Form.useForm();
      const [draftForm] = Form.useForm();
      return useIndustryPageState({
        briefForm,
        draftForm,
        navigate: navigate as never,
      });
    });

    await waitFor(() => {
      expect(result.current.detail?.agent_reports).toHaveLength(1);
    });

    await act(async () => {
      await result.current.handleOpenAgentReportChat(
        result.current.detail!.agent_reports[0],
      );
    });

    expect(mockedBuildIndustryRoleChatBinding).toHaveBeenCalled();
    expect(mockedOpenRuntimeChat).toHaveBeenCalledWith(
      expect.objectContaining({
        meta: expect.objectContaining({
          work_context_id: "ctx-industry-report-1",
          current_focus_kind: "agent-report",
          current_focus_id: "report-1",
        }),
      }),
      navigate,
    );
  });
});
