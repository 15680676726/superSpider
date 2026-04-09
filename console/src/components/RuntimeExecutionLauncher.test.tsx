// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { pulseHookMock } = vi.hoisted(() => ({
  pulseHookMock: vi.fn(),
}));

vi.mock("../hooks/useRuntimeExecutionPulse", () => ({
  useRuntimeExecutionPulse: pulseHookMock,
}));

vi.mock("./RuntimeExecutionStrip", () => ({
  __esModule: true,
  default: () => <div data-testid="runtime-execution-strip" />,
}));

import RuntimeExecutionLauncher from "./RuntimeExecutionLauncher";

describe("RuntimeExecutionLauncher", () => {
  beforeEach(() => {
    pulseHookMock.mockReset();
    pulseHookMock.mockReturnValue({
      items: [],
      loading: false,
      error: null,
      actorBusyKey: null,
      pauseActor: vi.fn(),
      resumeActor: vi.fn(),
      cancelActor: vi.fn(),
    });
  });

  it("keeps pulse inactive while the launcher is closed", () => {
    render(
      <MemoryRouter initialEntries={["/chat"]}>
        <RuntimeExecutionLauncher />
      </MemoryRouter>,
    );

    expect(pulseHookMock).toHaveBeenCalledWith(
      expect.objectContaining({
        actor: "runtime-floating-launcher",
        maxItems: 6,
        active: false,
      }),
    );
  });

  it("activates pulse after the launcher opens", () => {
    render(
      <MemoryRouter initialEntries={["/chat"]}>
        <RuntimeExecutionLauncher />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button"));

    expect(pulseHookMock).toHaveBeenLastCalledWith(
      expect.objectContaining({
        actor: "runtime-floating-launcher",
        maxItems: 6,
        active: true,
      }),
    );
    expect(screen.getByTestId("runtime-execution-strip")).toBeInTheDocument();
  });
});
