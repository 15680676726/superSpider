import { describe, expect, it } from "vitest";
import { resolveSelectedKey } from "../routes";

describe("resolveSelectedKey", () => {
  it("maps exact paths to correct keys", () => {
    expect(resolveSelectedKey("/chat")).toBe("chat");
    expect(resolveSelectedKey("/runtime-center")).toBe("runtime-center");
    expect(resolveSelectedKey("/agents")).toBe("agents");
    expect(resolveSelectedKey("/industry")).toBe("industry");
    expect(resolveSelectedKey("/knowledge")).toBe("knowledge");
    expect(resolveSelectedKey("/reports")).toBe("reports");
    expect(resolveSelectedKey("/performance")).toBe("performance");
    expect(resolveSelectedKey("/calendar")).toBe("calendar");
    expect(resolveSelectedKey("/predictions")).toBe("predictions");
    expect(resolveSelectedKey("/capability-market")).toBe(
      "capability-market",
    );
  });

  it("maps retired workflows tab aliases back to capability-market", () => {
    expect(resolveSelectedKey("/capability-market", "?tab=workflows")).toBe(
      "capability-market",
    );
    expect(resolveSelectedKey("/capability-market/browse", "?tab=workflows")).toBe(
      "capability-market",
    );
  });

  it("maps settings sub-paths", () => {
    expect(resolveSelectedKey("/settings/system")).toBe("system");
    expect(resolveSelectedKey("/settings/channels")).toBe("channels");
    expect(resolveSelectedKey("/settings/models")).toBe("models");
    expect(resolveSelectedKey("/settings/environments")).toBe("environments");
    expect(resolveSelectedKey("/settings/agent-config")).toBe("agent-config");
  });

  it("treats retired workflow routes as unknown paths", () => {
    expect(resolveSelectedKey("/workflow-templates")).toBe("runtime-center");
    expect(resolveSelectedKey("/workflow-templates/abc-123")).toBe(
      "runtime-center",
    );
    expect(resolveSelectedKey("/workflow-runs/run-456")).toBe("runtime-center");
  });

  it("maps nested and deep paths via prefix matching", () => {
    expect(resolveSelectedKey("/chat/session/123")).toBe("chat");
    expect(resolveSelectedKey("/runtime-center/details")).toBe(
      "runtime-center",
    );
    expect(resolveSelectedKey("/capability-market/browse")).toBe(
      "capability-market",
    );
  });

  it("falls back to runtime-center for unknown paths", () => {
    expect(resolveSelectedKey("/")).toBe("runtime-center");
    expect(resolveSelectedKey("/unknown")).toBe("runtime-center");
    expect(resolveSelectedKey("/foo/bar")).toBe("runtime-center");
    expect(resolveSelectedKey("")).toBe("runtime-center");
  });
});
