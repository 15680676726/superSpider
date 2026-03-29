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
import { useIndustryPageState } from "./useIndustryPageState";

const mockedListIndustryInstances = vi.mocked(api.listIndustryInstances);
const mockedGetRuntimeIndustryDetail = vi.mocked(api.getRuntimeIndustryDetail);
const mockedBuildIndustryRoleChatBinding = vi.mocked(buildIndustryRoleChatBinding);
const mockedOpenRuntimeChat = vi.mocked(openRuntimeChat);

describe("useIndustryPageState", () => {
  afterEach(() => {
    mockedListIndustryInstances.mockReset();
    mockedGetRuntimeIndustryDetail.mockReset();
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
