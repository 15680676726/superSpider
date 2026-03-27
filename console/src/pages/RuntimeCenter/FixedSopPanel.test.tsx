// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../api", async () => {
  const actual = await vi.importActual<typeof import("../../api")>(
    "../../api",
  );
  return {
    ...actual,
    default: {
      ...actual.default,
      listFixedSopTemplates: vi.fn(),
      listFixedSopBindings: vi.fn(),
      listIndustryInstances: vi.fn(),
      runFixedSopBinding: vi.fn(),
      createFixedSopBinding: vi.fn(),
      runFixedSopDoctor: vi.fn(),
      getFixedSopRun: vi.fn(),
    },
  };
});

import api from "../../api";
import FixedSopPanel from "./FixedSopPanel";

const mockedApi = api as typeof api & {
  listFixedSopTemplates: ReturnType<typeof vi.fn>;
  listFixedSopBindings: ReturnType<typeof vi.fn>;
  listIndustryInstances: ReturnType<typeof vi.fn>;
  runFixedSopBinding: ReturnType<typeof vi.fn>;
  createFixedSopBinding: ReturnType<typeof vi.fn>;
  runFixedSopDoctor: ReturnType<typeof vi.fn>;
  getFixedSopRun: ReturnType<typeof vi.fn>;
};

const TEMPLATE = {
  template_id: "fixed-sop-http-routine-bridge",
  name: "HTTP Routine Bridge",
  summary: "Bridge a webhook or HTTP request into a routine call.",
  description: "Builtin template",
  status: "active",
  version: "v1",
  source_kind: "builtin",
  source_ref: null,
  owner_role_id: null,
  suggested_role_ids: [],
  industry_tags: ["retail"],
  capability_tags: ["http", "routine"],
  risk_baseline: "guarded",
  input_schema: {},
  output_schema: {},
  writeback_contract: {},
  node_graph: [],
  metadata: {},
  created_at: "2026-03-26T08:00:00Z",
  updated_at: "2026-03-26T08:00:00Z",
};

const BINDING = {
  binding_id: "binding-1",
  template_id: TEMPLATE.template_id,
  binding_name: "Retail Follow-up",
  status: "active",
  owner_scope: "retail-demo",
  owner_agent_id: "agent-sales",
  industry_instance_id: "industry-demo",
  workflow_template_id: null,
  trigger_mode: "manual",
  trigger_ref: null,
  input_mapping: {},
  output_mapping: {},
  timeout_policy: {},
  retry_policy: {},
  risk_baseline: "guarded",
  last_run_id: "workflow-run-1",
  last_verified_at: "2026-03-26T09:00:00Z",
  metadata: {},
  created_at: "2026-03-26T08:30:00Z",
  updated_at: "2026-03-26T09:00:00Z",
};

describe("FixedSopPanel", () => {
  it("loads fixed SOP templates and bindings, then runs a binding from Runtime Center", async () => {
    mockedApi.listFixedSopTemplates.mockResolvedValue({
      items: [
        {
          template: TEMPLATE,
          binding_count: 1,
          routes: {
            detail: `/api/fixed-sops/templates/${TEMPLATE.template_id}`,
          },
        },
      ],
      total: 1,
    });
    mockedApi.listFixedSopBindings.mockResolvedValue([
      {
        binding: BINDING,
        template: TEMPLATE,
        routes: {
          detail: `/api/fixed-sops/bindings/${BINDING.binding_id}`,
          run: `/api/fixed-sops/bindings/${BINDING.binding_id}/run`,
        },
      },
    ]);
    mockedApi.listIndustryInstances.mockResolvedValue([]);
    mockedApi.getFixedSopRun.mockResolvedValue({
      run: {
        run_id: "workflow-run-1",
        template_id: TEMPLATE.template_id,
        title: "Retail Follow-up",
        summary: "Run completed",
        status: "completed",
        owner_scope: "retail-demo",
        owner_agent_id: "agent-sales",
        industry_instance_id: "industry-demo",
        parameter_payload: {},
        preview_payload: {},
        goal_ids: [],
        schedule_ids: [],
        task_ids: [],
        decision_ids: [],
        evidence_ids: ["evidence-1"],
        metadata: {},
        created_at: "2026-03-26T09:00:00Z",
        updated_at: "2026-03-26T09:01:00Z",
      },
      binding: BINDING,
      template: TEMPLATE,
    });
    mockedApi.runFixedSopBinding.mockResolvedValue({
      binding_id: BINDING.binding_id,
      status: "success",
      summary: "Run completed",
      workflow_run_id: "workflow-run-1",
      evidence_id: "evidence-1",
      routes: {
        run: "/api/fixed-sops/runs/workflow-run-1",
      },
    });

    const openDetail = vi.fn().mockResolvedValue(undefined);
    const onRuntimeChanged = vi.fn().mockResolvedValue(undefined);

    render(
      <FixedSopPanel
        focusScope="retail-demo"
        openDetail={openDetail}
        onRuntimeChanged={onRuntimeChanged}
      />,
    );

    await waitFor(() => {
      expect(mockedApi.listFixedSopTemplates).toHaveBeenCalledTimes(1);
      expect(mockedApi.listFixedSopBindings).toHaveBeenCalledTimes(1);
    });

    expect((await screen.findAllByText("HTTP Routine Bridge")).length).toBeGreaterThan(0);
    expect(screen.getByText("Retail Follow-up")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Run" }));

    await waitFor(() => {
      expect(mockedApi.runFixedSopBinding).toHaveBeenCalledWith(
        BINDING.binding_id,
        expect.objectContaining({
          owner_scope: "retail-demo",
          dry_run: false,
        }),
      );
    });
    expect(onRuntimeChanged).toHaveBeenCalled();
  });
});
