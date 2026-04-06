// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ModelsSection } from "./ModelsSection";

describe("ModelsSection", () => {
  it("renders the slot title in clean Chinese", () => {
    render(
      <ModelsSection
        providers={[
          {
            id: "openai",
            name: "OpenAI",
            models: [{ id: "gpt-4.1", name: "GPT-4.1" }],
            extra_models: [],
            api_key: "secret",
            is_custom: false,
          },
        ]}
        activeModels={null}
        onSaved={() => undefined}
      />,
    );

    expect(screen.getByRole("heading", { name: "对话模型配置" })).toBeInTheDocument();
  });
});
