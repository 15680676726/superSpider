import { describe, expect, it } from "vitest";

import { normalizeDisplayChinese } from "./text";

describe("shared text normalization", () => {
  it("translates retired workflow-templates product copy into automation wording", () => {
    expect(normalizeDisplayChinese("Workflow Templates")).toBe("自动化模板");
  });
});
