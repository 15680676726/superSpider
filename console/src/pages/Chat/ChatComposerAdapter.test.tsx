// @vitest-environment jsdom

import type { ComponentProps } from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChatComposerAdapter } from "./ChatComposerAdapter";

describe("ChatComposerAdapter", () => {
  it("renders the runtime ui through an explicit adapter without DOM unlock surgery", () => {
    const mutationObserverSpy = vi.fn();
    const originalMutationObserver = globalThis.MutationObserver;
    globalThis.MutationObserver = class {
      constructor() {
        mutationObserverSpy();
      }

      disconnect() {}

      observe() {}

      takeRecords() {
        return [];
      }
    } as unknown as typeof MutationObserver;

    const FakeRuntime: NonNullable<
      ComponentProps<typeof ChatComposerAdapter>["RuntimeComponent"]
    > = ({ options }) => (
      <div>{String((options as { api_endpoint?: string }).api_endpoint || "")}</div>
    );

    render(
      <ChatComposerAdapter
        chatUiKey="thread-1"
        options={{ api_endpoint: "/runtime-center/chat/run" } as never}
        RuntimeComponent={FakeRuntime}
      />,
    );

    expect(screen.getByText("/runtime-center/chat/run")).toBeTruthy();
    expect(mutationObserverSpy).not.toHaveBeenCalled();

    globalThis.MutationObserver = originalMutationObserver;
  });
});
