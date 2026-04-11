// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor } from "@testing-library/react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import EnvironmentsPage from "./index";

const apiMock = vi.hoisted(() => ({
  listEnvs: vi.fn(),
  listProviders: vi.fn(),
  getActiveModels: vi.fn(),
  updateEnvs: vi.fn(),
}));

vi.mock("../../../api", () => ({
  default: apiMock,
}));

vi.mock("@/ui", () => ({
  Button: (props: ButtonHTMLAttributes<HTMLButtonElement>) => (
    <button type="button" {...props} />
  ),
  Card: ({ children, className }: { children: ReactNode; className?: string }) => (
    <div className={className}>{children}</div>
  ),
  Modal: ({ open, children }: { open?: boolean; children?: ReactNode }) =>
    open ? <div>{children}</div> : null,
}));

vi.mock("@agentscope-ai/icons", () => ({
  SparkDeleteLine: () => <span data-testid="spark-delete" />,
  SparkPlusLine: () => <span data-testid="spark-plus" />,
}));

describe("EnvironmentsPage", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("renders the env page before provider context finishes loading", async () => {
    let resolveProviders!: (value: unknown) => void;
    let resolveActiveModels!: (value: unknown) => void;

    apiMock.listEnvs.mockResolvedValue([]);
    apiMock.listProviders.mockReturnValue(
      new Promise((resolve) => {
        resolveProviders = resolve;
      }),
    );
    apiMock.getActiveModels.mockReturnValue(
      new Promise((resolve) => {
        resolveActiveModels = resolve;
      }),
    );

    render(<EnvironmentsPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "环境变量" }),
      ).toBeInTheDocument();
    });

    expect(screen.getByText("记忆 / 向量检索")).toBeInTheDocument();

    resolveProviders([]);
    resolveActiveModels(null);
  });
});
