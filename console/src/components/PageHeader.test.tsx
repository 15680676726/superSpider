// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PageHeader } from "./PageHeader";

describe("PageHeader", () => {
  it("renders runtime eyebrow, stats and actions", () => {
    render(
      <PageHeader
          eyebrow="Runtime Center"
          title="主脑驾驶舱"
          description="让运行事实、风险与证据优先可见。"
          stats={[
            { label: "运行中", value: "06" },
            { label: "待确认", value: "02" },
          ]}
          actions={<button type="button">刷新</button>}
      />,
    );

    expect(screen.getByText("Runtime Center")).toBeInTheDocument();
    expect(screen.getByText("主脑驾驶舱")).toBeInTheDocument();
    expect(screen.getByText("让运行事实、风险与证据优先可见。")).toBeInTheDocument();
    expect(screen.getByText("运行中")).toBeInTheDocument();
    expect(screen.getByText("06")).toBeInTheDocument();
    expect(screen.getByText("待确认")).toBeInTheDocument();
    expect(screen.getByText("02")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "刷新" })).toBeInTheDocument();
  });
});
