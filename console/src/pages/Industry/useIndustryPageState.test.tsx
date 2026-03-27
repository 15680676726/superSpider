// @vitest-environment jsdom

import { renderHook, waitFor } from "@testing-library/react";
import { Form } from "antd";
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

import api from "../../api";
import { useIndustryPageState } from "./useIndustryPageState";

const mockedListIndustryInstances = vi.mocked(api.listIndustryInstances);
const mockedGetRuntimeIndustryDetail = vi.mocked(api.getRuntimeIndustryDetail);

describe("useIndustryPageState", () => {
  afterEach(() => {
    mockedListIndustryInstances.mockReset();
    mockedGetRuntimeIndustryDetail.mockReset();
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
    );
  });
});
