import { describe, expect, it } from "vitest";
import { api } from "./index";

describe("api root exports", () => {
  it("exposes fixed sop APIs and does not expose retired sop adapter APIs", () => {
    expect(typeof api.listFixedSopTemplates).toBe("function");
    expect("listSopAdapterTemplates" in api).toBe(false);
    expect("listWorkflowTemplates" in api).toBe(false);
  });
});
