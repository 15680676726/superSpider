// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const {
  configureProviderMock,
  testProviderConnectionMock,
  messageSuccessMock,
  messageErrorMock,
  messageWarningMock,
  modalConfirmMock,
} = vi.hoisted(() => ({
  configureProviderMock: vi.fn(),
  testProviderConnectionMock: vi.fn(),
  messageSuccessMock: vi.fn(),
  messageErrorMock: vi.fn(),
  messageWarningMock: vi.fn(),
  modalConfirmMock: vi.fn(),
}));

vi.mock("@/ui", async () => {
  const actual = await vi.importActual<typeof import("@/ui")>("@/ui");
  (actual.Modal as typeof actual.Modal & { confirm?: typeof modalConfirmMock }).confirm =
    modalConfirmMock;
  return {
    ...actual,
    message: {
      success: messageSuccessMock,
      error: messageErrorMock,
      warning: messageWarningMock,
    },
    Modal: actual.Modal,
  };
});

vi.mock("../../../../../api", () => ({
  default: {
    configureProvider: configureProviderMock,
    testProviderConnection: testProviderConnectionMock,
  },
}));

import { ProviderConfigModal } from "./ProviderConfigModal";

describe("ProviderConfigModal", () => {
  it("shows a clean revoke-success message for the active chat provider", async () => {
    configureProviderMock.mockResolvedValue(undefined);
    testProviderConnectionMock.mockResolvedValue({ success: true });
    const onSaved = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();

    modalConfirmMock.mockImplementation(({ onOk }: { onOk: () => Promise<void> }) => {
      void onOk();
    });

    render(
      <ProviderConfigModal
        provider={{
          id: "openai",
          name: "OpenAI",
          api_key: "secret",
          freeze_url: false,
          is_custom: false,
          chat_model: "OpenAIChatModel",
        }}
        activeModels={{
          active_llm: {
            provider_id: "openai",
            model: "gpt-4.1",
          },
        }}
        open
        onClose={onClose}
        onSaved={onSaved}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "撤销授权" }));

    await waitFor(() => {
      expect(messageSuccessMock).toHaveBeenCalledWith(
        "OpenAI 授权已撤销，对话模型已清除",
      );
    });
  });
});
