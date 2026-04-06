import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const panelPath = path.join(__dirname, "V7ExecutionSeatPanel.tsx");

describe("V7ExecutionSeatPanel copy", () => {
  it("removes known English residue and keeps Chinese wording", () => {
    const source = fs.readFileSync(panelPath, "utf8");
    expect(source).not.toContain("Seat lifecycle");
    expect(source).not.toContain("Mailbox");
    expect(source).not.toContain("focus lane");
    expect(source).not.toContain("Main-brain control chain");
    expect(source).not.toContain("This seat");
    expect(source).not.toContain("No chain summary yet.");
    expect(source).not.toContain("Synthesis:");
    expect(source).not.toContain("No main-brain control chain is available yet.");
    expect(source).not.toContain("，decision ");

    expect(source).toContain("岗位生命周期");
    expect(source).not.toContain("所属目标");
    expect(source).toContain("关联事项编号");
    expect(source).toContain("主脑控制链");
  });
});
