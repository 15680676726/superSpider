// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EvidencePanel } from "./detailPanels";

describe("EvidencePanel", () => {
  it("surfaces artifact and replay counts for execution evidence", () => {
    render(
      <EvidencePanel
        agents={[]}
        evidence={
          [
            {
              id: "evidence-file-1",
              action_summary: "Write report file",
              result_summary: "Saved the latest operator report.",
              risk_level: "auto",
              environment_ref: "session:web:main",
              capability_ref: "tool:write_file",
              created_at: "2026-04-14T10:00:00Z",
              artifact_count: 2,
              replay_count: 1,
            },
          ] as never
        }
      />,
    );

    expect(screen.getByText("产物 2")).toBeTruthy();
    expect(screen.getByText("回放 1")).toBeTruthy();
  });

  it("renders nested artifact and replay details when evidence payload includes them", () => {
    render(
      <EvidencePanel
        agents={[]}
        evidence={
          [
            {
              id: "evidence-file-2",
              action_summary: "Persist execution outputs",
              result_summary: "Saved the latest operator report.",
              risk_level: "auto",
              environment_ref: "session:web:main",
              capability_ref: "tool:write_file",
              created_at: "2026-04-14T10:05:00Z",
              artifact_count: 1,
              replay_count: 1,
              artifacts: [
                {
                  id: "artifact-1",
                  artifact_type: "file",
                  storage_uri: "file:///tmp/report.md",
                  summary: "运营日报文件",
                },
              ],
              replay_pointers: [
                {
                  id: "replay-1",
                  replay_type: "browser",
                  storage_uri: "replay://trace-1",
                  summary: "浏览器执行回放",
                },
              ],
            },
          ] as never
        }
      />,
    );

    expect(screen.getByText(/运营日报文件/)).toBeTruthy();
    expect(screen.getByText(/file:\/\/\/tmp\/report\.md/)).toBeTruthy();
    expect(screen.getByText(/浏览器执行回放/)).toBeTruthy();
    expect(screen.getByText(/replay:\/\/trace-1/)).toBeTruthy();
  });
});
