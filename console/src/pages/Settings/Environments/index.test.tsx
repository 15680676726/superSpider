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
  Checkbox: ({
    checked,
    onChange,
    className,
  }: {
    checked?: boolean;
    onChange?: () => void;
    className?: string;
  }) => (
    <input
      type="checkbox"
      checked={checked}
      onChange={onChange}
      className={className}
      readOnly
    />
  ),
  Input: ({
    value,
    onChange,
    className,
    disabled,
    type,
    placeholder,
  }: {
    value?: string;
    onChange?: (event: { target: { value: string } }) => void;
    className?: string;
    disabled?: boolean;
    type?: string;
    placeholder?: string;
  }) => (
    <input
      value={value}
      onChange={(event) => onChange?.({ target: { value: event.target.value } })}
      className={className}
      disabled={disabled}
      type={type}
      placeholder={placeholder}
      readOnly
    />
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

  it("renders the env page with the simplified truth-first memory card", async () => {
    apiMock.listEnvs.mockResolvedValue([
      { key: "OPENAI_API_KEY", value: "test-openai" },
      { key: "EMBEDDING_API_KEY", value: "legacy-key" },
      { key: "EMBEDDING_MODEL_NAME", value: "legacy-model" },
    ]);

    render(<EnvironmentsPage />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "环境变量" })).toBeInTheDocument();
    });

    expect(screen.getByText("记忆配置")).toBeInTheDocument();
    expect(screen.queryByText("记忆 / 向量检索")).toBeNull();
    expect(screen.queryByText("私有压缩接口密钥")).toBeNull();
    expect(screen.queryByText("私有压缩模型")).toBeNull();
    expect(screen.getAllByText("本地全文检索").length).toBeGreaterThan(0);
    expect(screen.getByText("检测到 2 个退役记忆变量")).toBeInTheDocument();
    expect(screen.getByDisplayValue("OPENAI_API_KEY")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("EMBEDDING_API_KEY")).toBeNull();
  });
});
