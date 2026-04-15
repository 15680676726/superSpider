import { describe, expect, it } from "vitest";

import { normalizeDisplayChinese } from "./text";

describe("shared text normalization", () => {
  it("translates retired workflow-templates product copy into automation wording", () => {
    expect(normalizeDisplayChinese("Workflow Templates")).toBe("自动化模板");
  });

  it("uses neutral embedding wording instead of retired vector wording", () => {
    expect(normalizeDisplayChinese("Embedding API Key")).toBe("退役私有压缩接口密钥");
    expect(normalizeDisplayChinese("Embedding Base URL")).toBe("退役私有压缩服务地址");
  });
});
